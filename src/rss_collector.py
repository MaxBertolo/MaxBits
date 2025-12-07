# src/rss_collector.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import feedparser

from .models import RawArticle
from .ceo_pov_collector import load_ceo_config


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


# Precarichiamo i CEO per dare un piccolo boost agli articoli che li citano
_CEO_CFG = load_ceo_config()
_CEO_NAMES_LOWER = [c["name"].lower() for c in _CEO_CFG]


def rank_articles(articles: List[RawArticle]) -> List[RawArticle]:
    """
    Seleziona e ordina le 15 migliori notizie.

    Criteri:
      1) Fonti più autorevoli (peso alto)
      2) Lunghezza del contenuto (articoli più ricchi)
      3) Presenza di parole chiave tecnologiche (ai, cloud, 5G, space, crypto, ecc.)
      4) MICRO-BOOST agli articoli che citano uno dei CEO in config/ceo_pov.yaml
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
        score_val = 0

        # 1) Fonte autorevole
        for s in authoritative_sources:
            if s.lower() in article.source.lower():
                score_val += 50
                break

        # 2) Lunghezza contenuto
        score_val += min(len(article.content) // 200, 50)

        # 3) Keyword tecnologiche
        text = (article.content or "").lower()
        score_val += sum(5 for k in keywords if k in text)

        # 4) Micro-boost CEO
        title_text = (article.title or "").lower()
        full_text = f"{title_text} {text}"
        if any(ceo_name in full_text for ceo_name in _CEO_NAMES_LOWER):
            # Boost moderato: vogliamo che emergano, ma senza distruggere il ranking base
            score_val += 25

        return score_val

    ranked = sorted(articles, key=score, reverse=True)
    top = ranked[:15]
    print(f"[RANK] Selected top {len(top)} articles out of {len(articles)}")
    return top
