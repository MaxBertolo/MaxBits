import feedparser
from datetime import datetime, timezone
from typing import List
from .models import RawArticle


def parse_datetime(entry) -> datetime:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    else:
        return datetime.now(timezone.utc)


def collect_from_rss(feeds_config) -> List[RawArticle]:
    articles: List[RawArticle] = []
    for feed_cfg in feeds_config:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        parsed = feedparser.parse(url)

        for entry in parsed.entries:
            published_at = parse_datetime(entry)
            content = entry.get("summary", "") or entry.get("description", "")
            art = RawArticle(
                id=entry.get("id", entry.get("link", "")),
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                source=name,
                published_at=published_at,
                content=content,
            )
            articles.append(art)
    return articles
