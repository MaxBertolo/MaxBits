from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import time
import logging

import yaml
import feedparser


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "sources_rss.yaml"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# -------------------------------------------------------------------
#  DATA MODEL
# -------------------------------------------------------------------

@dataclass
class Article:
    id: str
    title: str
    link: str
    source: str
    topic: str
    published: Optional[datetime]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "topic": self.topic,
            "published": self.published.isoformat() if self.published else None,
            "summary": self.summary,
        }


# -------------------------------------------------------------------
#  CONFIG LOADER
# -------------------------------------------------------------------

def _load_sources_config() -> List[Dict[str, str]]:
    """
    Legge config/sources_rss.yaml e restituisce una lista di feed:

      [
        {"name": "...", "url": "...", "topic": "..."},
        ...
      ]

    Supporta due forme di YAML:

    1)  feeds:
          - name: "Wired – Business"
            url: "https://..."
            topic: "AI/Cloud/Quantum"

    2)  topics:
          - topic: "AI/Cloud/Quantum"
            feeds:
              - name: "Wired – Business"
                url: "https://..."
    """
    if not CONFIG_PATH.exists():
        logger.warning("[RSS] sources_rss.yaml not found at %s", CONFIG_PATH)
        return []

    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.error("[RSS] Cannot parse sources_rss.yaml: %r", e)
        return []

    feeds: List[Dict[str, str]] = []

    # Case 1: flat "feeds"
    for item in raw.get("feeds", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        topic = str(item.get("topic") or item.get("category") or "Misc").strip()
        if not (name and url):
            continue
        feeds.append({"name": name, "url": url, "topic": topic})

    # Case 2: grouped by "topics"
    for topic_group in raw.get("topics", []) or []:
        if not isinstance(topic_group, dict):
            continue
        topic_name = str(
            topic_group.get("topic")
            or topic_group.get("name")
            or "Misc"
        ).strip()
        for item in topic_group.get("feeds", []) or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            url = str(item.get("url") or "").strip()
            if not (name and url):
                continue
            feeds.append({"name": name, "url": url, "topic": topic_name})

    logger.info("[RSS] Loaded %d RSS feeds from config", len(feeds))
    return feeds


# -------------------------------------------------------------------
#  FEED FETCHING
# -------------------------------------------------------------------

def _parse_datetime(entry: Any) -> Optional[datetime]:
    """
    Converte published_parsed / updated_parsed in datetime.
    Se non disponibile, ritorna None.
    """
    for key in ("published_parsed", "updated_parsed"):
        value = getattr(entry, key, None) or entry.get(key) if isinstance(entry, dict) else None
        if value:
            try:
                # feedparser dà time.struct_time
                return datetime.fromtimestamp(time.mktime(value))
            except Exception:
                continue
    return None


def _fetch_feed(feed_cfg: Dict[str, str]) -> List[Article]:
    """
    Scarica un singolo feed RSS. In caso di errore logga e ritorna [].
    """
    name = feed_cfg["name"]
    url = feed_cfg["url"]
    topic = feed_cfg["topic"]

    logger.info("[RSS] Fetching feed: %s — %s", name, url)

    try:
        parsed = feedparser.parse(url)
    except Exception as e:
        logger.error(
            "[RSS] ERROR %s: failed to fetch/parse feed (%r). Skipping this feed.",
            name,
            e,
        )
        return []

    if parsed.bozo:
        # bozo_exception può essere innocua: logghiamo e continuiamo.
        logger.warning(
            "[RSS][WARN] %s: bozo feed (%r). Continuing with available entries.",
            name,
            parsed.bozo_exception,
        )

    articles: List[Article] = []
    for entry in parsed.entries:
        link = getattr(entry, "link", None) or ""
        title = getattr(entry, "title", None) or ""
        if not (title and link):
            continue

        art_id = getattr(entry, "id", None) or link

        published_dt = _parse_datetime(entry)

        summary = (
            getattr(entry, "summary", None)
            or getattr(entry, "description", None)
            or ""
        )
        summary = str(summary).strip()

        articles.append(
            Article(
                id=str(art_id),
                title=str(title).strip(),
                link=str(link).strip(),
                source=name,
                topic=topic,
                published=published_dt,
                summary=summary,
            )
        )

    logger.info(
        "[RSS] Collected %d entries from %s",
        len(articles),
        name,
    )
    return articles


# -------------------------------------------------------------------
#  PUBLIC API (compatibile con main.py)
# -------------------------------------------------------------------

def collect_from_rss() -> List[Dict[str, Any]]:
    """
    Funzione compatibile con la vecchia main.py.

    - Carica la config;
    - Scarica tutti i feed;
    - Skippa quelli che falliscono SENZA far fallire il job;
    - Ritorna una lista di dict (uno per articolo).
    """
    feeds_cfg = _load_sources_config()
    if not feeds_cfg:
        logger.warning("[RSS] No feeds configured. Returning empty list.")
        return []

    all_articles: List[Article] = []
    for feed_cfg in feeds_cfg:
        try:
            arts = _fetch_feed(feed_cfg)
            all_articles.extend(arts)
        except Exception as e:
            # robustezza massima: nessun feed deve far crashare tutto
            logger.error(
                "[RSS] Unexpected error while fetching %s (%s): %r",
                feed_cfg.get("name"),
                feed_cfg.get("url"),
                e,
            )

    logger.info("[RSS] Total raw articles collected: %d", len(all_articles))

    # Convertiamo in dict per compatibilità con il resto del codice
    return [a.to_dict() for a in all_articles]


def rank_articles(
    articles: List[Dict[str, Any]],
    max_articles: int = 50,
) -> List[Dict[str, Any]]:
    """
    Funzione compatibile con la vecchia main.py.

    - Prende una lista di dict (ritornata da collect_from_rss());
    - Ordina per data di pubblicazione (più recenti prima);
    - Ritorna al massimo max_articles articoli.

    Se un articolo non ha "published", viene messo in fondo,
    ma NON fa mai crashare il processo.
    """
    def _parse_iso(dt_str: Optional[str]) -> float:
        if not dt_str:
            return 0.0
        try:
            return datetime.fromisoformat(dt_str).timestamp()
        except Exception:
            return 0.0

    if not articles:
        logger.warning("[RANK] Empty article list, nothing to rank.")
        return []

    sorted_articles = sorted(
        articles,
        key=lambda a: _parse_iso(a.get("published")),
        reverse=True,
    )

    selected = sorted_articles[:max_articles]
    logger.info(
        "[RANK] Selected top %d articles out of %d",
        len(selected),
        len(articles),
    )
    return selected
