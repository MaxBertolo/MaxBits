# src/rss_collector.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Dict

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
    ma rimuove caratteri “sporchi” o invisibili.
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
        "\ufffe",
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
    """
    Ritorna un datetime *aware* in UTC.
    """
    for field in ("published", "updated"):
        val = entry.get(field)
        if not val:
            continue
        try:
            dt = dateparser.parse(val)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc)
            else:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue

    # fallback: adesso in UTC, aware
    return datetime.now(timezone.utc)


# -------------------------------------------------
#  RACCOLTA RSS
# -------------------------------------------------

def collect_from_rss(feeds: List[Dict]) -> List[RawArticle]:
    """
    feeds: lista di dict da config/sources_rss.yaml
      - name
      - url
      - topic
      - enabled
    """
    articles: List[RawArticle] = []

    # cutoff aware in UTC (ultime 48h)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=2)

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
            pub_date = _parse_date(entry)

            # confrontiamo aware vs aware → OK
            if pub_date < cutoff:
                continue

            raw_title = entry.get("title", "") or ""
            raw_summary = entry.get("summary", "") or ""
            raw_content = ""

            if "content" in entry and entry.content:
                raw_content = entry.content[0].get("value", "") or ""

            final_content = raw_content or raw_summary

            clean_title = _clean_title(raw_title)
            clean_content = _clean_content(final_content)
            link = entry.get("link", "") or ""

            # ---- ID OBBLIGATORIO PER RawArticle ----
            # se non c'è link uso una stringa sintetica ma stabile
            article_id = link or f"{name}:{clean_title}:{pub_date.isoformat()}"

            art = RawArticle(
                id=article_id,
                title=clean_title,
                url=link,
                source=name,
                content=clean_content,
                published_at=pub_date,  # UTC aware
            )

            # salviamo il topic come attributo aggiuntivo (se possibile)
            try:
                setattr(art, "topic", topic)
            except Exception:
                pass

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

    keywords = [
        # AI / Cloud / Edge / Agentic
        "ai", "gen ai", "artificial intelligence",
        "cloud", "saas", "edge", "edge cloud", "edge computing",
        "agentic", "ai agents", "autonomous agents",

        # Telco / 5G / network
        "5g", "6g", "telco", "fiber", "fibre", "network", "latency", "spectrum",

        # Crypto / Web3
        "crypto", "bitcoin", "btc", "ethereum", "ether", "eth", "defi", "web3",

        # Satellite / LEO / Starlink / Kuiper
        "satellite", "satcom", "leo", "starlink", "oneweb", "kuiper", "amazon leo",

        # Data / infra / robotics
        "data center", "datacenter", "infrastructure", "hyperscaler",
        "robot", "robotics", "automation",
    ]

    def score(article: RawArticle) -> int:
        score_val = 0

        # 1) Fonte autorevole
        src_lower = (article.source or "").lower()
        for s in authoritative_sources:
            if s.lower() in src_lower:
                score_val += 50
                break

        # 2) Lunghezza contenuto (max +50)
        score_val += min(len(article.content or "") // 250, 50)

        # 3) Parole chiave
        text = (article.content or "").lower() + " " + (article.title or "").lower()
        for k in keywords:
            if k in text:
                score_val += 6

        return score_val

    ranked = sorted(articles, key=score, reverse=True)
    return ranked
