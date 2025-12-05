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

    Qualsiasi errore di rete su un singolo feed viene loggato e ignorato,
    così il workflow non fallisce per un RemoteDisconnected o simili.
    """
    articles: List[RawArticle] = []

    for feed_cfg in feeds_config:
        name = feed_cfg["name"]
        url = feed_cfg["url"]

        print(f"[RSS] Fetching feed: {name} – {url}")

        # ---- fetch robusto del feed ----
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"[RSS][ERROR] {name}: failed to fetch/parse feed ({repr(e)}). Skipping this feed.")
            continue

        # Anche quando feedparser non lancia eccezione può mettere bozo=True
        if getattr(parsed, "bozo", False):
            err = getattr(parsed, "bozo_exception", None)
            print(f"[RSS][WARN] {name}: bozo feed ({repr(err)}). Continuing with whatever entries are available.")

        # ---- parsing delle entry, con guard-rail ----
        try:
            entries = parsed.entries or []
        except Exception as e:
            print(f"[RSS][ERROR] {name}: cannot read entries ({repr(e)}). Skipping this feed.")
            continue

        for entry in entries:
            try:
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
            except Exception as e:
                # Problema su una singola entry: la saltiamo, ma continuiamo
                print(f"[RSS][WARN] {name}: skipping one entry due to error ({repr(e)}).")
                continue

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

    keywords = [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "gen ai", "generative ai", "llm", "agentic", "autonomous agent",
        "5g", "6g", "fiber", "fibre", "backhaul", "telco", "network",
        "cloud", "edge", "edge cloud", "data center", "datacenter",
        "satellite", "space", "orbit", "orbital", "leo", "meo", "geo",
        "starlink", "kuiper",
        "robot", "robotics", "automation",
        "broadcast", "streaming", "ott", "video processing",
        "crypto", "cryptocurrency", "bitcoin", "ethereum", "ether",
        "blockchain", "web3",
    ]

    def score(article: RawArticle) -> int:
        score = 0

        for s in authoritative_sources:
            if s.lower() in article.source.lower():
                score += 50
                break

        score += min(len(article.content) // 200, 50)

        text = (article.content or "").lower()
        score += sum(5 for k in keywords if k in text)

        return score

    ranked = sorted(articles, key=score, reverse=True)
    top = ranked[:15]
    print(f"[RANK] Selected top {len(top)} articles out of {len(articles)}")
    return top
