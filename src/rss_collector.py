from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import feedparser


@dataclass
class RssSource:
    name: str
    url: str
    topic: Optional[str] = None
    weight: float = 1.0
    enabled: bool = True


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _normalize_sources(feeds_cfg: List[Dict[str, Any]]) -> List[RssSource]:
    """
    Converte la lista di dict letta da sources_rss.yaml in RssSource,
    e filtra i feed disabilitati o senza URL.
    """
    sources: List[RssSource] = []

    if not isinstance(feeds_cfg, list):
        print("[RSS] feeds_cfg is not a list, nothing to do.")
        return sources

    for idx, raw in enumerate(feeds_cfg, start=1):
        if not isinstance(raw, dict):
            continue

        url = str(raw.get("url") or "").strip()
        if not url:
            continue

        enabled = raw.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() not in {"false", "0", "no"}

        if not enabled:
            continue

        name = str(raw.get("name") or f"Feed {idx}").strip()
        topic = str(raw.get("topic") or "").strip() or None
        weight = raw.get("weight", 1.0)

        try:
            weight = float(weight)
        except Exception:
            weight = 1.0

        sources.append(
            RssSource(
                name=name,
                url=url,
                topic=topic,
                weight=weight,
                enabled=True,
            )
        )

    print(f"[RSS] Normalized {len(sources)} enabled feeds.")
    return sources


def _entry_datetime(entry: Any) -> Optional[datetime]:
    """
    Prova a estrarre una datetime UTC da un entry (published/updated).
    Ritorna None se non disponibile.
    """
    tm = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if not tm:
        return None
    try:
        return datetime(
            tm.tm_year,
            tm.tm_mon,
            tm.tm_mday,
            tm.tm_hour,
            tm.tm_min,
            tm.tm_sec,
            tzinfo=timezone.utc,
        )
    except Exception:
        return None


# -------------------------------------------------------------------
# API principale
# -------------------------------------------------------------------

def collect_from_rss(feeds_cfg: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Legge i feed RSS definiti in feeds_cfg (già caricati da sources_rss.yaml)
    e restituisce una lista di articoli "raw":

      {
        "title": ...,
        "url": ...,
        "summary": ...,
        "source": ...,
        "topic": ...,
        "published": "ISO-8601",
        "source_weight": float,
      }

    La funzione è ROBUSTA:
    - se un feed non risponde / dà errore XML → logga e continua
    - se il feed è vuoto → semplicemente salta
    """
    sources = _normalize_sources(feeds_cfg)
    all_articles: List[Dict[str, Any]] = []

    print("Collecting RSS...")

    for src in sources:
        try:
            parsed = feedparser.parse(src.url)
        except Exception as e:
            print(
                f"[RSS][ERROR] {src.name}: failed to fetch/parsing feed "
                f"({e!r}). Skipping this feed."
            )
            continue

        if getattr(parsed, "bozo", False):
            # feedparser non lancia eccezione, ma segnala bozo = True
            exc = getattr(parsed, "bozo_exception", None)
            print(
                f"[RSS][WARN] {src.name}: bozo feed (parse error: {exc!r}). "
                f"Skipping entries from this feed."
            )
            continue

        entries = getattr(parsed, "entries", []) or []
        if not entries:
            print(f"[RSS][WARN] {src.name}: no entries found.")
            continue

        for entry in entries:
            title = (getattr(entry, "title", "") or "").strip()
            link = (
                getattr(entry, "link", "")
                or getattr(entry, "id", "")
                or ""
            ).strip()

            if not title or not link:
                continue

            summary = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
                or ""
            )

            dt = _entry_datetime(entry)
            published_iso = dt.isoformat() if dt is not None else ""

            art: Dict[str, Any] = {
                "title": title,
                "url": link,
                "link": link,  # alias
                "summary": summary,
                "source": src.name,
                "topic": src.topic,
                "published": published_iso,
                "source_weight": src.weight,
            }
            all_articles.append(art)

        print(
            f"[RSS] {src.name}: collected {len(entries)} entries "
            f"(running total: {len(all_articles)})"
        )

    print(f"[RSS] Total raw articles collected: {len(all_articles)}")
    return all_articles


def rank_articles(
    articles: List[Dict[str, Any]],
    ceo_names: Optional[List[str]] = None,
    max_articles: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Ranking semplice ma robusto:
    - base score da "source_weight"
    - bonus per recency (fino a ~7 giorni)
    - micro-boost se nel titolo compare un CEO (case-insensitive)

    Ritorna la lista ordinata desc per 'score'.
    """
    now = datetime.now(timezone.utc)
    ceo_names = [c.lower() for c in (ceo_names or [])]

    ranked: List[Dict[str, Any]] = []

    for art in articles:
        score = float(art.get("source_weight", 1.0))

        # recency: se published entro 7 giorni
        published_str = str(art.get("published") or "")
        if published_str:
            try:
                dt = datetime.fromisoformat(published_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_days = (now - dt).total_seconds() / 86400.0
                if age_days <= 7:
                    # più recente → più score, ma senza esagerare
                    score += max(0.0, 2.0 - age_days * 0.2)
            except Exception:
                pass

        # micro-boost se contiene un CEO nel titolo
        title_l = str(art.get("title") or "").lower()
        if ceo_names:
            for name in ceo_names:
                if name and name in title_l:
                    score += 0.5
                    break

        art = dict(art)  # copia
        art["score"] = score
        ranked.append(art)

    ranked.sort(key=lambda a: a.get("score", 0.0), reverse=True)

    if isinstance(max_articles, int) and max_articles > 0:
        ranked = ranked[:max_articles]

    print(f"[RANK] Ranked {len(ranked)} articles.")
    return ranked
