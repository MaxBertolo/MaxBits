from datetime import datetime, timedelta, timezone
from typing import List
from .models import RawArticle


def filter_last_24h(articles: List[RawArticle]) -> List[RawArticle]:
    now = datetime.now(timezone.utc)
    limit = now - timedelta(days=1)
    return [a for a in articles if a.published_at >= limit]


def deduplicate(articles: List[RawArticle]) -> List[RawArticle]:
    seen_urls = set()
    result = []
    for a in articles:
        if a.url in seen_urls:
            continue
        seen_urls.add(a.url)
        result.append(a)
    return result


def clean_articles(articles: List[RawArticle], max_articles: int) -> List[RawArticle]:
    filtered = filter_last_24h(articles)
    deduped = deduplicate(filtered)
    deduped.sort(key=lambda a: a.published_at, reverse=True)
    return deduped[:max_articles]
