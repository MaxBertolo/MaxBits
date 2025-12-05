# src/rss_collector.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime, timedelta

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .models import RawArticle


# -------------------------------------------------
#  PULIZIA TESTO / TITOLI (FIX FIERCE TELECOM)
# -------------------------------------------------

def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(" ", strip=True)
    return text


def _clean_title(raw: str) -> str:
    """
    Pulisce il titolo mantenendo il contenuto,
    ma rimuovendo caratteri “sporchi” (Fierce Telecom, ecc.).
    """
    if not raw:
        return ""

    text = _strip_html(raw)

    # rimuove soft hyphen, zero-width, separatori strani
    bad_chars = [
        "\u00ad",  # soft hyphen
        "\u200b",  # zero-width space
        "\u200c",  # zero-width non-joiner
        "\u200d",  # zero-width joiner
        "\u2028",  # line separator
        "\u2029",  # paragraph separator
        "\ufffe",  # special
    ]
    for ch in bad_chars:
        text = text.replace(ch, "")

    # normalizza spazi e newline → una riga sola
    text = " ".join(text.split())

    return text.strip()


def _clean_content(raw: str) -> str:
    if not raw:
        return ""
    text = _strip_html(raw)
    text = " ".join(text.split())
    return text.strip()


def _parse_date(entry) -> datetime:
    # prova published, poi updated, altrimenti ora
    for field in ("published", "updated"):
        val = entry.get(field)
        if not val:
            continue
        try:
            return dateparser.parse(val)
        except Exception:
            continue
    return datetime.utcnow()


# -------------------------------------------------
#  RACCOLTA RSS
# -------------------------------------------------

def collect_from_rss(feeds: List[Dict]) -> List[RawArticle]:
    """
    feeds: lista di dict dal config/sources_rss.yaml
      - name
      - url
      - topic
      - enabled
    """
    articles: List[RawArticle] = []
    now = datetime.utcnow()
    cutoff = now - timedelta(days=2)  # prendiamo solo ultime 48h per sicurezza

    for feed_cfg in feeds:
        if not feed_cfg.get("enabled", True):
            continue

        name = feed_cfg.get("name", "Unknown Source")
        url = feed_cfg.get("url")
        topic = feed_cfg.get("topic") or ""

        if not url:
            continue

        print(f"[RSS] Fetching: {name} – {url}")
        parsed = feedparser.parse(url)

        for entry in parsed.entries:
            try:
                pub_date = _parse_date(entry)
            except Exception:
                pub_date = now

            if pub_date < cutoff:
                continue

            raw_title = entry.get("title", "") or ""
            raw_summary = entry.get("summary", "") or ""
            raw_content = ""

            # se il feed ha contenuti più ricchi
            if "content" in entry and entry.content:
                # normalmente una lista con dict {"value": "...", "type": "..."}
                raw_content = entry.content[0].get("value", "") or ""

            final_content = raw_content or raw_summary

            clean_title = _clean_title(raw_title)      # <-- FIX FIERCE QUI
            clean_content = _clean_content(final_content)

            link = entry.get("link", "")

            art = RawArticle(
                title=clean_title,
                url=link,
                source=name,
                content=clean_content,
                published_at=pub_date,
                topic=topic,
            )
            articles.append(art)

    print(f"[RSS] Total collected (after cleaning titles/content): {len(articles)}")
    return articles


# -------------------------------------------------
#  RANKING (priorità, incl. Crypto / LEO / Edge / Agentic)
# -------------------------------------------------

def rank_articles(articles: List[RawArticle]) -> List[RawArticle]:
    """
    Ritorna una lista ordinata (best first).
    Criteri:
      1) Fonte autorevole
      2) Lunghezza contenuto
      3) Parole chiave tecnologiche (estese: Crypto, LEO, Starlink, Edge, Agentic, ecc.)
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
        "McKinsey",
    ]

    # estendo con i temi che ti interessano di più
    keywords = [
        # AI / Cloud / Edge / Agentic
        "ai", "gen ai", "artificial intelligence",
        "cloud", "saas", "edge", "edge cloud", "edge computing",
        "agentic", "ai agents", "autonomous agents",

        # Telco / 5G / network
        "5g", "6g", "telco", "fiber", "fibre", "network", "latency", "spectrum",

        # Crypto / Web3
        "crypto", "bitcoin", "btc", "ethereum", "ether", "eth", "defi", "web3",

        # Satellite / LEO / Starlink / Amazon LEO project Kuiper
        "satellite", "satcom", "leo", "starlink", "oneweb", "kuiper", "amazon leo",

        # Data / infra
        "data center", "datacenter", "infrastructure", "hyperscaler",
        "robot", "robotics", "automation",
    ]

    def score(article: RawArticle) -> int:
        score = 0

        # 1) Fonte autorevole
        src_lower = (article.source or "").lower()
        for s in authoritative_sources:
            if s.lower() in src_lower:
                score += 50
                break

        # 2) Lunghezza contenuto
        score += min(len(article.content or "") // 250, 50)

        # 3) Parole chiave
        text = (article.content or "").lower() + " " + (article.title or "").lower()
        for k in keywords:
            if k in text:
                score += 6  # leggero boost per ogni keyword rilevante

        return score

    ranked = sorted(articles, key=score, reverse=True)
    return ranked
