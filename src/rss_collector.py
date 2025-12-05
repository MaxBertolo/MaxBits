# src/rss_collector.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import feedparser

from .models import RawArticle


def parse_datetime(entry) -> datetime:
    """
    Prova a estrarre la data di pubblicazione dall'entry RSS.
    Se non disponibile, usa 'adesso' in UTC.
    """
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if getattr(entry, "updated_parsed", None):
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
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
      3) Presenza di parole chiave tecnologiche (ai, cloud, 5G, space, crypto, ecc.)
    """

    # NIENTE Fierce Telecom qui
    authoritative_sources = [
        "TechCrunch",
        "The Verge",
        "Wired",
        "Ars Technica",
        "Light Reading",
        "Telecoms.com",
        "Data Center Knowledge",
        "MIT Technology Review",
        "Space News",
        "Advanced Television",
        "Broadband TV News",
        "VentureBeat",
        "The Information",
        "McKinsey",
        "Corriere Comunicazioni",
    ]

    # parole chiave potenziate (inclusi crypto, LEO, Starlink, edge cloud, agenti, ecc.)
    keywords = [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "gen ai", "generative ai", "llm", "agentic", "autonomous agent",
        "5g", "6g", "fiber", "fibre", "backhaul", "telco", "network",
        "cloud", "edge", "edge cloud", "data center", "datacenter",
        "satellite", "space", "orbit", "orbital", "leo", "mEO", "geo",
        "starlink", "kuiper",
        "robot", "robotics", "automation",
        "broadcast", "streaming", "ott", "video processing",
        "crypto", "cryptocurrency", "bitcoin", "ethereum", "ether",
        "blockchain", "web3",
    ]

    def score(article: RawArticle) -> int:
        score = 0

        # 1) Fonte autorevole
        for s in authoritative_sources:
            if s.lower() in article.source.lower():
                score += 50
                break

        # 2) Lunghezza del contenuto (max +50)
        score += min(len(article.content) // 200, 50)

        # 3) Parole chiave
        text = (article.content or "").lower()
        score += sum(5 for k in keywords if k in text)

        return score

    ranked = sorted(articles, key=score, reverse=True)
    top = ranked[:15]
    print(f"[RANK] Selected top {len(top)} articles out of {len(articles)}")
    return top
