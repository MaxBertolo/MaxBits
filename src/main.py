from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set

import yaml

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email
from .models import RawArticle


# Root del repo (cartella padre di src/)
BASE_DIR = Path(__file__).resolve().parent.parent


def today_str() -> str:
    """Restituisce la data di oggi come stringa YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> Dict:
    """Carica config/config.yaml."""
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def load_rss_sources() -> List[Dict]:
    """Carica la lista dei feed da config/sources_rss.yaml."""
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["feeds"]


# ---------------------------------------------------------------------------
#  WATCHLIST HELPERS
# ---------------------------------------------------------------------------

WATCHLIST_TOPICS_ORDER = [
    "TV/Streaming",
    "Telco/5G",
    "Media/Platforms",
    "AI/Cloud/Quantum",
    "Space/Infra",
    "Robotics/Automation",
    "Broadcast/Video",
    "Satellite/Satcom",
]


def _canonical_title(title: str) -> str:
    return (title or "").strip().lower()


def build_watchlist(
    ranked_articles: List[RawArticle],
    deep_dives: List[RawArticle],
    per_topic_min: int = 3,
    per_topic_max: int = 5,
) -> Dict[str, List[Dict]]:
    """
    Costruisce la watchlist per topic, senza duplicazioni:

    - Nessun articolo può comparire sia nei deep-dives sia nella watchlist.
    - Nessun articolo può essere duplicato in più topic (vince il primo in ordine).
    - Ogni topic ha 0–per_topic_max articoli.
    """

    # titoli già usati nei deep-dives
    used_titles: Set[str] = {_canonical_title(a.title) for a in deep_dives}

    buckets: Dict[str, List[Dict]] = {t: [] for t in WATCHLIST_TOPICS_ORDER}

    for art in ranked_articles:
        title_key = _canonical_title(art.title)
        if not art.title:
            continue
        if title_key in used_titles:
            # già usato in deep-dives o watchlist
            continue

        topic = getattr(art, "topic", None)
        if topic not in WATCHLIST_TOPICS_ORDER:
            # se non mappato, per ora lo ignoriamo
            continue

        if len(buckets[topic]) >= per_topic_max:
            continue

        buckets[topic].append(
            {
                "id": f"{topic.replace('/', '_')}_{len(buckets[topic]) + 1}",
                "title": art.title,
                "url": art.url,
                "source": art.source,
            }
        )
        used_titles.add(title_key)

    # log di servizio
    for t in WATCHLIST_TOPICS_ORDER:
        print(f"[WATCHLIST] {t}: {len(buckets[t])} items")

    return buckets


# ---------------------------------------------------------------------------
#  MAIN PIPELINE
# ---------------------------------------------------------------------------


def main() -> None:
    # Info utili per il debug su GitHub Actions
    cwd = Path.cwd()
    print("[DEBUG] CWD:", cwd)
    try:
        print("[DEBUG] Repo contents:", [p.name for p in cwd.iterdir()])
    except Exception as e:
        print("[DEBUG] Cannot list repo contents:", repr(e))

    # 1) Config + fonti RSS
    cfg = load_config()
    feeds = load_rss_sources()

    max_articles_for_cleaning = int(cfg.get("max_articles_per_day", 50))
    llm_cfg = cfg.get("llm", {})
    model = llm_cfg.get("model", "")
    temperature = float(llm_cfg.get("temperature", 0.25))
    max_tokens = int(llm_cfg.get("max_tokens", 900))
    language = llm_cfg.get("language", "en")

    output_cfg = cfg.get("output", {})
    html_dir_cfg = output_cfg.get("html_dir", "reports/html")
    pdf_dir_cfg = output_cfg.get("pdf_dir", "reports/pdf")
    file_prefix = output_cfg.get("file_prefix", "report_")

    # 2) Raccolta RSS
    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"Collected {len(raw_articles)} raw articles")

    if not raw_articles:
        print("No articles collected from RSS. Exiting.")
        return

    # 3) Cleaning (es. ultime 24h, dedup, sort, limite massimo)
    cleaned = clean_articles(raw_articles, max_articles=max_articles_for_cleaning)
    print(f"After cleaning: {len(cleaned)} articles")

    if not cleaned:
        print("No recent articles after cleaning. Exiting.")
        return

    # 4) Ranking
    ranked = rank_articles(cleaned)
    print(f"After ranking: {len(ranked)} articles")

    if not ranked:
        print("No ranked articles, exiting.")
        return

    # 5) Selezione deep-dives + watchlist
    #    - primi 3: deep dives
    #    - successivi: pool per watchlist
    deep_dives_articles: List[RawArticle] = ranked[:3]
    watchlist_pool: List[RawArticle] = ranked[3:]

    print(f"[SELECT] Deep-dives articles: {len(deep_dives_articles)}")
    print(f"[SELECT] Watchlist candidates: {len(watchlist_pool)}")

    # 6) Summarization dei 3 deep-dives
    print("Summarizing deep-dive articles with LLM...")
    deep_dives_summaries = summarize_articles(
        deep_dives_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # arricchiamo i summaries con topic e id
    deep_dives_payload: List[Dict] = []
    for idx, (art, summary) in enumerate(zip(deep_dives_articles, deep_dives_summaries)):
        topic = getattr(art, "topic", "General")
        payload = {
            **summary,
            "id": summary.get("id") or f"deep_{idx + 1}",
            "topic": topic,
        }
        deep_dives_payload.append(payload)

    # salviamo anche un JSON "raw" per eventuali usi futuri
    json_dir = BASE_DIR / "reports" / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    date_str = today_str()
    json_path = json_dir / f"deep_dives_{date_str}.json"

    import json

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(deep_dives_payload, f, ensure_ascii=False, indent=2)

    print(f"[DEBUG] Saved deep-dives JSON to: {json_path}")

    # 7) Costruzione watchlist per topic, senza duplicazioni
    print("Building watchlist by topic...")
    watchlist_grouped = build_watchlist(
        ranked_articles=watchlist_pool,
        deep_dives=deep_dives_articles,
        per_topic_min=3,
        per_topic_max=5,
    )

    print("[SELECT] Watchlist built with topics:",
          list(watchlist_grouped.keys()))

    # 8) Costruzione HTML
    print("Building HTML report...")
    html = build_html_report(
        deep_dives=deep_dives_payload,
        watchlist=watchlist_grouped,
        date_str=date_str,
    )

    # 9) Salvataggio HTML + PDF
    html_dir = BASE_DIR / html_dir_cfg
    pdf_dir = BASE_DIR / pdf_dir_cfg
    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    html_path = html_dir / f"{file_prefix}{date_str}.html"
    pdf_path = pdf_dir / f"{file_prefix}{date_str}.pdf"

    print("[DEBUG] Saving HTML to:", html_path)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("[DEBUG] Converting HTML to PDF at:", pdf_path)
    html_to_pdf(html, str(pdf_path))

    print("Done. HTML report:", html_path)
    print("Done. PDF report:", pdf_path)

    # 10) Invio email (NON fa fallire il job se qualcosa va storto)
    print("Sending report via email...")
    try:
        send_report_email(
            pdf_path=str(pdf_path),
            date_str=date_str,
            html_path=str(html_path),
        )
        print("Email step completed (check [EMAIL] logs for details).")
    except Exception as e:
        print("[EMAIL] Unhandled error while sending email:", repr(e))
        print("Continuing anyway – report generation completed.")

    print("Process completed.")


if __name__ == "__main__":
    main()
