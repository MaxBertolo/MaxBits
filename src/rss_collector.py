# src/rss_collector.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import feedparser

from .models import RawArticle


def parse_datetime(entry) -> datetime:
    """
    Estrae una data di pubblicazione dall'entry RSS.
    Se non disponibile, usa 'adesso' in UTC.
    """
    try:
        if getattr(entry, "published_parsed", None):
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if getattr(entry, "updated_parsed", None):
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        # Qualsiasi problema sul parsing della data → fallback a now()
        pass

    return datetime.now(timezone.utc)


def collect_from_rss(feeds_config) -> List[RawArticle]:
    """
    Legge tutti i feed RSS indicati in feeds_config (lista di dict con name, url)
    e restituisce una lista di RawArticle (NON puliti, NON deduplicati).

    È *robusto*: errori di rete o feed rotti vengono loggati e saltati,
    senza far fallire il job.
    """
    articles: List[RawArticle] = []

    for feed_cfg in feeds_config:
        name = feed_cfg.get("name", "Unknown")
        url = feed_cfg.get("url", "").strip()

        if not url:
            print(f"[RSS] Skipping feed with empty URL (name={name})")
            continue

        print(f"[RSS] Fetching feed: {name} – {url}")

        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"[RSS] ERROR: cannot fetch '{name}' – {repr(e)}")
            continue

        # feedparser non lancia eccezione ma segnala problemi qui
        if getattr(parsed, "bozo", False):
            print(f"[RSS] Warning: feed '{name}' is bozo: {parsed.bozo_exception!r}")

        if not getattr(parsed, "entries", None):
            print(f"[RSS] No entries parsed for feed '{name}', skipping.")
            continue

        for entry in parsed.entries:
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
                # Una entry rotta non deve bloccare il feed
                print(f"[RSS] Skipping broken entry in '{name}': {repr(e)}")
                continue

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
        "TechCrunch",
        "The Verge",
        "Wired",
        "Ars Technica",
        "Light Reading",
        "Telecoms.com",
        "Fierce Telecom",
        "Data Center Knowledge",
        "MIT Technology Review",
        "Space News",
        "Advanced Television",
        "Broadband TV News",
        "VentureBeat",
        "The Information",
        "McKinsey",
    ]

    # Parole chiave estese (AI, telco, space, crypto, edge, agentic, ecc.)
    keywords = [
        # AI / GenAI / LLM
        "ai",
        "gen ai",
        "generative ai",
        "machine learning",
        "deep learning",
        "neural network",
        "llm",
        "agentic",
        "ai agent",
        "agent platform",
        "agentic platform",

        # Telco / network
        "5g",
        "6g",
        "fiber",
        "fibre",
        "telco",
        "network",
        "carrier",
        "operator",
        "5g core",
        "open ran",
        "o-ran",

        # Cloud / edge / data
        "cloud",
        "edge",
        "edge cloud",
        "data center",
        "datacenter",
        "database",
        "analytics",
        "data platform",

        # Space / satellite / LEO
        "satellite",
        "satcom",
        "space",
        "orbit",
        "leo",
        "starlink",
        "kuiper",
        "amazon kuiper",
        "amazon leo",

        # Media / video / broadcast
        "broadcast",
        "streaming",
        "ott",
        "vod",
        "video processing",

        # Robotics / automation
        "robot",
        "robotics",
        "automation",

        # Crypto / web3
        "crypto",
        "cryptocurrency",
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "defi",
        "web3",
    ]

    def score(article: RawArticle) -> int:
        s = 0

        # 1) Fonte autorevole
        for src in authoritative_sources:
            if src.lower() in (article.source or "").lower():
                s += 50
                break

        # 2) Lunghezza contenuto (più testo = più informazione), max +50
        s += min(len(article.content or "") // 200, 50)

        # 3) Keyword nel titolo + contenuto
        txt = (f"{article.title} {article.content}").lower()
        s += sum(5 for k in keywords if k in txt)

        return s

    ranked = sorted(articles, key=score, reverse=True)
    top = ranked[:15]
    print(f"[RANK] Selected top {len(top)} articles out of {len(articles)}")
    return top
