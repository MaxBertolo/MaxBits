from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import feedparser


# -----------------------------------------------------------------------------
# Data models
# -----------------------------------------------------------------------------

@dataclass
class RssFeedConfig:
    name: str
    url: str
    topic: str = "General"
    weight: float = 1.0
    enabled: bool = True


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _safe_parse_datetime(entry: Dict[str, Any]) -> Optional[datetime]:
    """
    Try to extract a datetime from a feedparser entry.
    Always return either a timezone-aware UTC datetime or None.
    Never raises.
    """
    try_keys = ["published_parsed", "updated_parsed", "created_parsed"]

    for key in try_keys:
        st = entry.get(key)
        if st is None:
            continue

        try:
            # st is a time.struct_time
            dt = datetime(
                year=st.tm_year,
                month=st.tm_mon,
                day=st.tm_mday,
                hour=st.tm_hour,
                minute=st.tm_min,
                second=st.tm_sec,
                tzinfo=timezone.utc,
            )
            return dt
        except Exception:
            continue

    return None


def _normalise_feeds(feeds_cfg: Iterable[Dict[str, Any]]) -> List[RssFeedConfig]:
    """Convert raw YAML dicts into RssFeedConfig objects. Completely defensive."""
    out: List[RssFeedConfig] = []

    for raw in feeds_cfg or []:
        if not isinstance(raw, dict):
            continue

        enabled = raw.get("enabled", True)
        if enabled is False:
            continue

        url = str(raw.get("url") or "").strip()
        name = str(raw.get("name") or "").strip() or url or "Unknown feed"
        if not url:
            print(f"[RSS][WARN] Feed '{name}' has empty URL – skipped.")
            continue

        topic = str(raw.get("topic") or "General").strip()
        try:
            weight = float(raw.get("weight", 1.0))
        except Exception:
            weight = 1.0

        out.append(
            RssFeedConfig(
                name=name,
                url=url,
                topic=topic,
                weight=weight,
                enabled=True,
            )
        )

    print(f"[RSS] Normalised {len(out)} feeds from config.")
    return out


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def collect_from_rss(
    feeds_cfg: Iterable[Dict[str, Any]],
    max_per_feed: int = 30,
    max_total: int = 200,
) -> List[Dict[str, Any]]:
    """
    Fetch and parse articles from a list of RSS feeds.

    * Never raises because of network / parsing problems.
    * If a feed is broken, it logs a warning and continues with the next one.
    * Returns a flat list of article dicts.

    Each article dict has at least:
      - title
      - link
      - summary
      - source
      - topic
      - weight
      - published  (ISO string or None)
    """
    feeds = _normalise_feeds(feeds_cfg)
    articles: List[Dict[str, Any]] = []

    if not feeds:
        print("[RSS][WARN] No enabled feeds in config. Returning empty list.")
        return articles

    for feed in feeds:
        if len(articles) >= max_total:
            break

        print(f"[RSS] Fetching feed: {feed.name} — {feed.url}")

        # Network / parse errors are fully swallowed here
        try:
            parsed = feedparser.parse(feed.url)
        except Exception as e:
            print(
                f"[RSS][WARN] {feed.name}: failed to fetch/parse feed "
                f"({e!r}). Skipping this feed."
            )
            continue

        # "bozo" feeds: something went wrong while parsing.
        # We *log* the problem but still *try* to use entries, because
        # often the content is still partially usable.
        if getattr(parsed, "bozo", False):
            err = getattr(parsed, "bozo_exception", None)
            print(
                f"[RSS][WARN] {feed.name}: bozo feed "
                f"(parse error: {err!r}). Trying to use entries anyway."
            )

        entries = getattr(parsed, "entries", []) or []
        if not entries:
            print(f"[RSS][WARN] {feed.name}: no entries found.")
            continue

        count_for_feed = 0

        for entry in entries:
            if count_for_feed >= max_per_feed or len(articles) >= max_total:
                break

            try:
                title = (entry.get("title") or "").strip()
                link = (entry.get("link") or "").strip()
            except Exception:
                # completely broken entry – skip
                continue

            if not title or not link:
                continue

            summary = (
                (entry.get("summary") or entry.get("description") or "").strip()
            )

            published_dt = _safe_parse_datetime(entry)
            published_iso = (
                published_dt.isoformat() if published_dt is not None else None
            )

            art: Dict[str, Any] = {
                "title": title,
                "link": link,
                "summary": summary,
                "source": feed.name,
                "topic": feed.topic,
                "weight": feed.weight,
                "published": published_iso,
            }
            articles.append(art)
            count_for_feed += 1

        print(
            f"[RSS] {feed.name}: collected {count_for_feed} entries "
            f"(running total: {len(articles)})"
        )

    print(f"[RSS] Total raw articles collected: {len(articles)}")
    return articles


def rank_articles(
    articles: List[Dict[str, Any]],
    max_articles: int = 15,
) -> List[Dict[str, Any]]:
    """
    Rank articles using a simple scoring function:

      score = weight * recency_factor

    where recency_factor favours more recent content (last ~3 days).
    If anything goes wrong with a single article, that article is skipped,
    but the function never raises.
    """
    if not articles:
        print("[RANK] No articles to rank; returning empty list.")
        return []

    now = datetime.now(timezone.utc)
    ranked: List[Dict[str, Any]] = []

    for art in articles:
        try:
            weight = float(art.get("weight") or 1.0)
        except Exception:
            weight = 1.0

        published_iso = art.get("published")
        published_dt: Optional[datetime] = None

        if isinstance(published_iso, str) and published_iso:
            try:
                published_dt = datetime.fromisoformat(published_iso)
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
            except Exception:
                published_dt = None

        if published_dt:
            age_hours = max(
                1.0, (now - published_dt).total_seconds() / 3600.0
            )
            # ~72 ore molto premiate, poi decresce
            recency_factor = max(0.1, 72.0 / age_hours)
        else:
            recency_factor = 0.5  # unknown date → mid-level relevance

        score = weight * recency_factor

        clone = dict(art)
        clone["score"] = score
        ranked.append(clone)

    ranked.sort(key=lambda a: a.get("score", 0.0), reverse=True)
    top = ranked[:max_articles]
    print(f"[RANK] Selected top {len(top)} articles out of {len(articles)}")
    return top
