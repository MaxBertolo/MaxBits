from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Tuple
import datetime as dt
import math
import textwrap

import yaml
import feedparser
import requests


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "sources_rss.yaml"

# -------------------------------------------------------------------
#  DATA MODEL
# -------------------------------------------------------------------


@dataclass
class Article:
    title: str
    url: str
    source: str
    topic: str
    published: dt.datetime | None
    summary: str
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.published is not None:
            d["published"] = self.published.isoformat()
        else:
            d["published"] = None
        return d


# -------------------------------------------------------------------
#  CONFIG
# -------------------------------------------------------------------


def _load_sources_config(path: Path = DEFAULT_CONFIG_PATH) -> List[Dict[str, Any]]:
    """
    Legge config/sources_rss.yaml.

    Formato atteso:

      sources:
        - name: "VentureBeat – AI"
          url: "https://venturebeat.com/tag/ai/feed/"
          topic: "AI/Cloud/Quantum"
          weight: 1.2          # opzionale
          enabled: true        # opzionale
    """
    if not path.exists():
        print(f"[RSS][WARN] Config file not found: {path}")
        return []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"[RSS][ERR] Cannot parse {path}: {e!r}")
        return []

    sources = data.get("sources") or []
    if not isinstance(sources, list):
        print(f"[RSS][ERR] 'sources' in {path} must be a list.")
        return []

    enabled_sources: List[Dict[str, Any]] = []
    for raw in sources:
        if not isinstance(raw, dict):
            continue
        if raw.get("enabled") is False:
            continue
        name = str(raw.get("name") or "").strip()
        url = str(raw.get("url") or "").strip()
        topic = str(raw.get("topic") or "").strip() or "General"
        weight = float(raw.get("weight") or 1.0)
        if not (name and url):
            continue
        enabled_sources.append(
            {
                "name": name,
                "url": url,
                "topic": topic,
                "weight": weight,
            }
        )

    print(f"[RSS] Loaded {len(enabled_sources)} sources from {path}")
    return enabled_sources


# -------------------------------------------------------------------
#  FETCHING & PARSING (ROBUSTO)
# -------------------------------------------------------------------


def _safe_request(url: str, timeout: int = 20) -> bytes | None:
    """
    HTTP GET robusto: se il sito è giù o dà errore,
    ritorna None senza alzare eccezioni.
    """
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": "MaxBitsBot/1.0 (+https://github.com/MaxBertolo/MaxBits)"
            },
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"[RSS][ERR] HTTP error for {url}: {e!r}")
        return None


def _parse_date(entry: Any) -> dt.datetime | None:
    """
    Prova a estrarre una data dall'entry RSS.
    In caso di problemi, ritorna None.
    """
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return dt.datetime(*t[:6], tzinfo=dt.timezone.utc)
            except Exception:
                pass
    return None


def _fetch_feed_for_source(source_cfg: Dict[str, Any]) -> List[Article]:
    """
    Scarica e parse-a un singolo feed.
    Qualsiasi errore di rete o parsing NON fa crashare il processo:
    ritorna semplicemente una lista vuota.
    """
    name = source_cfg["name"]
    url = source_cfg["url"]
    topic = source_cfg["topic"]
    weight = float(source_cfg.get("weight") or 1.0)

    print(f"[RSS] Fetching feed: {name} – {url}")

    content = _safe_request(url)
    if content is None:
        print(f"[RSS][WARN] {name}: no content received. Skipping this feed.")
        return []

    try:
        parsed = feedparser.parse(content)
    except Exception as e:
        print(f"[RSS][ERR] {name}: failed to parse feed: {e!r}. Skipping this feed.")
        return []

    if parsed.bozo and getattr(parsed, "bozo_exception", None):
        # Feed malformato: logghiamo ma NON interrompiamo il job
        print(
            f"[RSS][WARN] {name}: bozo feed "
            f"({parsed.bozo_exception!r}). Continuing with available entries."
        )

    articles: List[Article] = []
    now = dt.datetime.now(dt.timezone.utc)

    for entry in parsed.entries[:50]:
        title = (getattr(entry, "title", "") or "").strip()
        link = (getattr(entry, "link", "") or "").strip()
        if not (title and link):
            continue

        summary_raw = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        summary = " ".join(summary_raw.split())
        if len(summary) > 800:
            summary = summary[:800] + "…"

        published = _parse_date(entry)
        if published is None:
            # articoli senza data li teniamo, ma penalizzati nel ranking
            age_days = 30.0
        else:
            age = now - published
            age_days = max(age.total_seconds() / 86400.0, 0.0)

        # Score di base (più recente + più pesato)
        recency_factor = max(0.0, 30.0 - age_days) / 30.0  # 0..1
        base_score = weight * (0.5 + 0.5 * recency_factor)

        articles.append(
            Article(
                title=title,
                url=link,
                source=name,
                topic=topic,
                published=published,
                summary=summary,
                score=base_score,
            )
        )

    print(f"[RSS] {name}: collected {len(articles)} entries.")
    return articles


# -------------------------------------------------------------------
#  CLEAN & RANK
# -------------------------------------------------------------------


def _deduplicate(articles: List[Article]) -> List[Article]:
    """
    Rimuove duplicati per URL (tiene quello con score più alto).
    """
    best_by_url: Dict[str, Article] = {}
    for art in articles:
        existing = best_by_url.get(art.url)
        if not existing or art.score > existing.score:
            best_by_url[art.url] = art
    return list(best_by_url.values())


def rank_articles(articles: List[Article], max_articles: int = 15) -> List[Article]:
    """
    Calcola uno score finale e ritorna i top N.
    Lo score può essere raffinato, per ora usiamo:
      - base_score (da fonte + recency)
      - boost se titolo contiene parole chiave interessanti
    """
    if not articles:
        print("[RANK] No articles to rank.")
        return []

    KEYWORDS_BOOST = [
        "ai",
        "artificial intelligence",
        "machine learning",
        "cloud",
        "quantum",
        "satellite",
        "space",
        "5g",
        "telco",
        "streaming",
    ]

    for art in articles:
        title_lower = art.title.lower()
        bonus = 0.0
        for kw in KEYWORDS_BOOST:
            if kw in title_lower:
                bonus += 0.15
        art.score += bonus

    articles_sorted = sorted(articles, key=lambda a: a.score, reverse=True)
    selected = articles_sorted[:max_articles]

    print(
        f"[RANK] Selected top {len(selected)} articles out of {len(articles_sorted)}"
    )
    return selected


# -------------------------------------------------------------------
#  HIGH-LEVEL API USATA DA main.py
# -------------------------------------------------------------------


def collect_rss_articles(
    config_path: Path = DEFAULT_CONFIG_PATH,
    max_articles: int = 15,
) -> List[Dict[str, Any]]:
    """
    API principale: usata da main.py

    - Carica la config
    - Fetch di tutti i feed, in modo robusto (errori di rete non fanno crashare)
    - Deduplica
    - Ranking
    - Ritorna una lista di dict pronti da serializzare in JSON
    """
    sources = _load_sources_config(config_path)
    if not sources:
        print("[RSS][WARN] No RSS sources configured. Returning empty list.")
        return []

    raw_articles: List[Article] = []

    for src in sources:
        try:
            arts = _fetch_feed_for_source(src)
            raw_articles.extend(arts)
        except Exception as e:
            # protezione extra: qualsiasi eccezione qui NON deve far fallire il job
            print(
                f"[RSS][ERR] Unexpected error while fetching '{src['name']}': {e!r}. "
                f"Skipping this source."
            )

    print(f"[RSS] Total raw articles collected: {len(raw_articles)}")

    cleaned = _deduplicate(raw_articles)
    print(f"[RSS] After cleaning: {len(cleaned)} articles")

    ranked = rank_articles(cleaned, max_articles=max_articles)
    return [art.to_dict() for art in ranked]


def collect_and_rank_articles(
    config_path: Path = DEFAULT_CONFIG_PATH,
    max_articles: int = 15,
) -> List[Dict[str, Any]]:
    """
    Alias compatibile, nel caso main.py usi questo nome.
    """
    return collect_rss_articles(config_path=config_path, max_articles=max_articles)


def main() -> None:
    """
    Permette di lanciare:
      python -m src.rss_collector
    solo per debug/manual run.
    """
    articles = collect_rss_articles()
    print("")
    print("-------------------------------------------------")
    print(f"Collected & ranked {len(articles)} articles:")
    for i, a in enumerate(articles, start=1):
        print(
            textwrap.shorten(
                f"{i:02d}. [{a['topic']}] {a['source']} – {a['title']}",
                width=120,
            )
        )


if __name__ == "__main__":
    main()
