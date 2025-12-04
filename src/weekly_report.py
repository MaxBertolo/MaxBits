# src/weekly_report.py

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import json
from datetime import datetime

from .models import RawArticle
from .summarizer import summarize_article
from .weekly_report_builder import build_weekly_html_report
from .pdf_export import html_to_pdf


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WEEKLY_JSON = DATA_DIR / "weekly_votes.json"


def _load_weekly_votes() -> Dict[str, Dict]:
    """
    Legge data/weekly_votes.json che contiene tutti gli articoli flaggati
    durante la settimana, con struttura tipo:

    {
      "some-id": {
        "id": "...",
        "title": "...",
        "url": "...",
        "source": "...",
        "topic": "...",
        "votes": 5,
        "content": "...",
        "what_it_is": "... (opzionale)",
        "who": "...",
        "what_it_does": "...",
        "why_it_matters": "...",
        "strategic_view": "..."
      },
      ...
    }
    """
    if not WEEKLY_JSON.exists():
        print(f"[WEEKLY] No weekly_votes.json found at {WEEKLY_JSON}")
        return {}
    with open(WEEKLY_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        print("[WEEKLY] weekly_votes.json is not a dict, ignoring.")
        return {}
    return data


def _select_top15(votes_dict: Dict[str, Dict]) -> List[Dict]:
    """
    Prende tutti i candidati dal JSON, li ordina per numero di voti
    e ritorna i migliori 15 (o meno se ce ne sono meno).
    """
    articles: List[Dict] = []
    for art_id, payload in votes_dict.items():
        v = payload.get("votes", 0)
        try:
            v = int(v)
        except Exception:
            v = 0

        payload["votes"] = v
        payload["id"] = payload.get("id", art_id)
        articles.append(payload)

    # ordina per votes desc, poi per titolo
    articles.sort(key=lambda a: (-a["votes"], a.get("title", "")))
    top_15 = articles[:15]

    print(f"[WEEKLY] Selected {len(top_15)} articles for weekly (top by votes).")
    return top_15


def _raw_article_from_candidate(c: Dict) -> RawArticle:
    """
    Costruisce un RawArticle minimo per poter usare summarize_article.
    """
    published = datetime.now()
    try:
        if "published_at" in c:
            published = datetime.fromisoformat(c["published_at"])
    except Exception:
        pass

    return RawArticle(
        title=c.get("title", ""),
        url=c.get("url", ""),
        source=c.get("source", ""),
        content=c.get("content", "") or (c.get("title", "") + " " + c.get("url", "")),
        published_at=published,
    )


def _ensure_summary_for_candidate(c: Dict) -> Dict:
    """
    Garantisce che il candidato abbia tutti i campi:
      what_it_is, who, what_it_does, why_it_matters, strategic_view

    Se mancano o sono troppo corti → chiama il summarizer (Gemini + fallback).
    """
    needed_keys = [
        "what_it_is",
        "who",
        "what_it_does",
        "why_it_matters",
        "strategic_view",
    ]

    already_ok = True
    for k in needed_keys:
        v = c.get(k, "") or ""
        if len(v.strip()) < 20:   # se corto/vuoto → da arricchire
            already_ok = False
            break

    if already_ok:
        return c

    print(f"[WEEKLY] Enriching article via LLM: {c.get('title','')}")
    ra = _raw_article_from_candidate(c)

    summary = summarize_article(
        ra,
        model="",          # usa default del summarizer (GEMINI_MODEL)
        temperature=0.3,
        max_tokens=900,
        language="en",
    )

    for k in needed_keys:
        if summary.get(k):
            c[k] = summary[k]

    return c


def build_weekly_report():
    """
    Pipeline weekly:
      - legge i voti da data/weekly_votes.json
      - seleziona le top 15 per numero di voti
      - arricchisce ogni articolo con i 5 campi (se mancano)
      - genera HTML + PDF in reports/weekly/html|pdf
    """
    votes_dict = _load_weekly_votes()
    if not votes_dict:
        print("[WEEKLY] No votes found – skipping weekly generation.")
        return

    top_articles = _select_top15(votes_dict)

    enriched: List[Dict] = []
    for c in top_articles:
        enriched.append(_ensure_summary_for_candidate(c))

    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    week_label = f"Week of {date_str}"

    html = build_weekly_html_report(
        articles=enriched,
        week_label=week_label,
    )

    weekly_html_dir = BASE_DIR / "reports" / "weekly" / "html"
    weekly_pdf_dir = BASE_DIR / "reports" / "weekly" / "pdf"
    weekly_html_dir.mkdir(parents=True, exist_ok=True)
    weekly_pdf_dir.mkdir(parents=True, exist_ok=True)

    html_path = weekly_html_dir / f"weekly_{date_str}.html"
    pdf_path = weekly_pdf_dir / f"weekly_{date_str}.pdf"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    html_to_pdf(html, str(pdf_path))

    print(f"[WEEKLY] Weekly HTML: {html_path}")
    print(f"[WEEKLY] Weekly PDF: {pdf_path}")


if __name__ == "__main__":
    build_weekly_report()
