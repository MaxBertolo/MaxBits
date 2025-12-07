# src/ceo_pov_collector.py

from __future__ import annotations

from typing import List, Dict
import re
from datetime import datetime, timezone

from .models import RawArticle


CEOS = [
    {"name": "Tim Cook", "company": "Apple"},
    {"name": "Satya Nadella", "company": "Microsoft"},
    {"name": "Sundar Pichai", "company": "Alphabet / Google"},
    {"name": "Mark Zuckerberg", "company": "Meta"},
    {"name": "Elon Musk", "company": "Tesla / SpaceX"},
    {"name": "Jeff Bezos", "company": "Amazon / Blue Origin"},
    {"name": "Larry Fink", "company": "BlackRock"},
    {"name": "Jensen Huang", "company": "NVIDIA"},
]

AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "gen ai", "generative ai", "llm", "model", "gpu", "accelerator",
]

SPACE_KEYWORDS = [
    "space", "orbit", "orbital", "satellite", "launch", "rocket", "space economy",
]

QUOTE_RE = re.compile(r"[\"“](.{20,280}?)[\"”]", re.IGNORECASE | re.DOTALL)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _contains_keywords(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in AI_KEYWORDS + SPACE_KEYWORDS)


def collect_ceo_pov(
    articles: List[RawArticle],
    max_items: int = 5,
) -> List[Dict]:
    """
    Estrae 3–5 citazioni CEO da articoli già raccolti via RSS.
    Heuristics:
      - l'articolo contiene il nome del CEO
      - esiste almeno una frase tra virgolette con keyword AI/Space
      - dedup su (ceo, quote)
    """
    results: List[Dict] = []
    seen = set()  # fingerprint per dedup

    # preferiamo i primi articoli già 'ranked' (passali da main)
    for art in articles:
        if len(results) >= max_items:
            break

        text = (art.content or "") + " " + (art.title or "")
        text_norm = _norm(text)

        for ceo in CEOS:
            name = ceo["name"]
            company = ceo["company"]

            if name.lower() not in text_norm:
                continue

            # cerca frasi tra virgolette nell'entry RSS (summary/description)
            for m in QUOTE_RE.finditer(art.content or ""):
                quote = m.group(1).strip()
                if not _contains_keywords(quote):
                    continue

                fp = (name.lower(), _norm(quote))
                if fp in seen:
                    continue
                seen.add(fp)

                item = {
                    "ceo": name,
                    "company": company,
                    "topic": "AI" if any(k in _norm(quote) for k in AI_KEYWORDS) else "Space Economy",
                    "quote": quote,
                    "context": art.title or "",
                    "source": art.source or "",
                    "source_url": art.url or "",
                    "tags": [],
                    "published_at": art.published_at.isoformat()
                    if isinstance(art.published_at, datetime) else "",
                }
                # tagging veloce
                t = _norm(quote)
                tags = []
                if any(k in t for k in AI_KEYWORDS):
                    tags.append("AI")
                if any(k in t for k in SPACE_KEYWORDS):
                    tags.append("Space")
                item["tags"] = tags

                results.append(item)
                if len(results) >= max_items:
                    break

            if len(results) >= max_items:
                break

    return results

