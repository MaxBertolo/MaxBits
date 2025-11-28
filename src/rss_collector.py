import feedparser
from datetime import datetime, timezone
from typing import List

from .models import RawArticle


def parse_datetime(entry) -> datetime:
    """
    Prova a estrarre la data di pubblicazione dall'entry RSS.
    Se non disponibile, usa 'adesso' in UTC.
    """
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        # published_parsed è una time.struct_time
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    else:
        return datetime.now(timezone.utc)


def collect_from_rss(feeds_config) -> List[RawArticle]:
    """
    Legge tutti i feed RSS indicati in feeds_config (lista di dict con name, url)
    e restituisce una lista di RawArticle (NON puliti, NON deduplicati).
    """
    articles: List[RawArticle] = []

    for feed_cfg in feeds_config:
        name = feed_cfg["name"]
        url = feed_cfg["url"]

        print(f"[RSS] Fetching feed: {name} – {url}")
        parsed = feedparser.parse(url)

        for entry in parsed.entries:
            published_at = parse_datetime(entry)
            content = (
                entry.get("summary", "")
                or entry.get("description", "")
                or ""
            )

            art = RawArticle(
                id=entry.get("id", entry.get("link", "")),
                title=(entry.get("title") or "").strip(),
                url=entry.get("link", ""),
                source=name,
                published_at=published_at,
                content=content,
            )
            articles.append(art)

    print(f"[RSS] Total raw articles collected: {len(articles)}")
    return articles


def rank_articles(articles: List[RawArticle]) -> List[RawArticle]:
    """
    Seleziona e ordina le 15 migliori notizie.

    Criteri:
    1) Fonti più autorevoli (peso alto)
    2) Lunghezza del contenuto (articoli più ricchi)
    3) Presenza di parole chiave tecnologiche
    """

    authoritative_sources = [
        "TechCrunch", "The Verge", "Wired", "Ars Technica",
        "Light Reading", "Telecoms.com", "Fierce Telecom",
        "Data Center Knowledge", "MIT Technology Review",
        "Space News", "Advanced Television",
        "Broadband TV News", "Advanced Television", "VentureBeat",
    ]

    keywords = [
        "ai", "machine learning", "deep learning",
        "gen ai", "llm", "5g", "6g", "fiber", "fibre",
        "cloud", "edge", "satellite", "space", "orbit",
        "robot", "robotics", "datacenter", "data center",
        "telco", "5g core", "network", "optical", "photonic",
        "broadcast", "streaming", "ott", "video processing",
    ]

    def score(article: RawArticle) -> int:
        score = 0

        # 1) Fonte autorevole
        for s in authoritative_sources:
            if s.lower() in article.source.lower():
                score += 50
                break

        # 2) Lunghezza contenuto (più testo = più informazione)
        score += min(len(article.content) // 200, 50)

        # 3) Parole chiave tecnologiche
        text = (article.content or "").lower()
        score += sum(5 for k in keywords if k in text)

        return score

    ranked = sorted(articles, key=score, reverse=True)
    top = ranked[:15]
    print(f"[RANK] Selected top {len(top)} articles out of {len(articles)}")
    return top
