# src/ceo_pov_collector.py

from __future__ import annotations

from typing import List, Dict
import re
from datetime import datetime

from .models import RawArticle


# -------------------------------------------------------
# CONFIG: CEO + KEYWORDS
# -------------------------------------------------------

CEOS = [
    {"name": "Tim Cook",       "company": "Apple"},
    {"name": "Satya Nadella",  "company": "Microsoft"},
    {"name": "Sundar Pichai",  "company": "Alphabet / Google"},
    {"name": "Mark Zuckerberg","company": "Meta"},
    {"name": "Elon Musk",      "company": "Tesla / SpaceX"},
    {"name": "Jeff Bezos",     "company": "Amazon / Blue Origin"},
    {"name": "Larry Fink",     "company": "BlackRock"},
    {"name": "Jensen Huang",   "company": "NVIDIA"},
]

AI_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "gen ai",
    "generative ai",
    "llm",
    "model",
    "large language model",
    "gpu",
    "accelerator",
    "chip",
    "compute",
]

SPACE_KEYWORDS = [
    "space",
    "space economy",
    "orbital",
    "orbit",
    "leo",
    "meo",
    "geo",
    "satellite",
    "constellation",
    "launch",
    "rocket",
    "spacecraft",
]


# Frasi tra virgolette “...” o "..."
QUOTE_RE = re.compile(r"[\"“](.{20,280}?)[\"”]", re.IGNORECASE | re.DOTALL)


# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _contains_any(text: str, keywords: List[str]) -> bool:
    t = _norm(text)
    return any(k in t for k in keywords)


def _topic_for_quote(quote: str) -> str:
    q = _norm(quote)
    ai = _contains_any(q, AI_KEYWORDS)
    space = _contains_any(q, SPACE_KEYWORDS)

    if ai and space:
        return "AI & Space"
    if ai:
        return "AI"
    if space:
        return "Space Economy"
    return "Other"


def _tags_for_quote(quote: str) -> List[str]:
    q = _norm(quote)
    tags: List[str] = []
    if _contains_any(q, AI_KEYWORDS):
        tags.append("AI")
    if _contains_any(q, SPACE_KEYWORDS):
        tags.append("Space")
    return sorted(set(tags))


# -------------------------------------------------------
# MAIN ENTRYPOINT
# -------------------------------------------------------

def collect_ceo_pov(
    articles: List[RawArticle],
    max_items: int = 5,
) -> List[Dict]:
    """
    Estrae 3–5 citazioni di CEO da articoli RSS già raccolti.

    Heuristics:
      - l'articolo contiene il nome del CEO (in titolo+contenuto)
      - estraiamo frasi tra virgolette dal contenuto
      - teniamo solo quelle con keyword AI/Space
      - dedup su (ceo, quote normalizzata)
    """
    results: List[Dict] = []
    seen = set()  # set[(ceo_name_lower, quote_norm)]

    if not articles:
        return results

    for art in articles:
        if len(results) >= max_items:
            break

        # Contesto testo: titolo + summary/description
        full_text = f"{art.title or ''} {art.content or ''}"
        full_norm = _norm(full_text)

        for ceo in CEOS:
            ceo_name = ceo["name"]
            ceo_company = ceo["company"]

            if ceo_name.lower() not in full_norm:
                # L'articolo non cita esplicitamente il CEO → saltiamo
                continue

            # Cerchiamo frasi tra virgolette solo nel contenuto (summary/description)
            content = art.content or ""
            for m in QUOTE_RE.finditer(content):
                quote_raw = m.group(1).strip()
                if not quote_raw:
                    continue

                # Filtra frasi molto corte o troppo lunghe (limite già nel regex)
                if len(quote_raw) < 20:
                    continue

                # Deve contenere almeno una keyword AI o Space
                if not (_contains_any(quote_raw, AI_KEYWORDS) or _contains_any(quote_raw, SPACE_KEYWORDS)):
                    continue

                # Dedup
                fp = (ceo_name.lower(), _norm(quote_raw))
                if fp in seen:
                    continue
                seen.add(fp)

                topic = _topic_for_quote(quote_raw)
                if topic == "Other":
                    # teoricamente non dovremmo arrivarci, ma per sicurezza
                    continue

                item = {
                    "ceo": ceo_name,
                    "company": ceo_company,
                    "topic": topic,
                    "quote": quote_raw,
                    "context": art.title or "",
                    "source": art.source or "",
                    "source_url": art.url or "",
                    "tags": _tags_for_quote(quote_raw),
                    "published_at": art.published_at.isoformat()
                    if isinstance(art.published_at, datetime) else "",
                }

                results.append(item)
                if len(results) >= max_items:
                    break

            if len(results) >= max_items:
                break

    return results
