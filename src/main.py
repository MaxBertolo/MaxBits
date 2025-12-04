# src/main.py

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import json
import yaml

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email


BASE_DIR = Path(__file__).resolve().parent.parent


def today_str() -> str:
    """Restituisce la data di oggi come stringa YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> dict:
    """Carica config/config.yaml."""
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_rss_sources() -> list:
    """Carica la lista dei feed da config/sources_rss.yaml."""
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("feeds", [])


# -------------------------------
#  HELPERS PER WATCHLIST & DEDUP
# -------------------------------

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


def _normalise_title(title: str) -> str:
    """Titolo normalizzato per il confronto dedup."""
    if not title:
        return ""
    t = title.strip().lower()
    # rimuovo alcuni caratteri finali inutili
    while t.endswith((" .", ".", "!", "?", "…")):
        t = t[:-1].strip()
    return t


def _article_topic(article) -> str:
    """
    Ritorna il topic dell'articolo.
    Assume che rss_collector abbia impostato article.topic in base al feed.
    Se manca, lo mette in 'AI/Cloud/Quantum' come default.
    """
    topic = getattr(article, "topic", None) or "AI/Cloud/Quantum"
    if topic not in WATCHLIST_TOPICS_ORDER:
        # topic non previsto -> mappiamo su uno sensato
        if "space" in topic.lower() or "sat" in topic.lower():
            return "Space/Infra"
        return "AI/Cloud/Quantum"
    return topic


def build_watchlist(
    ranked_articles,
    deep_dive_articles,
    max_per_topic: int = 5,
) -> Dict[str, List[Dict]]:
    """
    Costruisce la watchlist per topic, senza duplicazioni:
      - nessun articolo che sia già fra i deep-dives (per titolo)
      - nessun titolo duplicato all'interno della watchlist stessa
      - max 3–5 (configurabile) articoli per topic
    """

    deep_titles = {_normalise_title(a.title) for a in deep_dive_articles}

    watchlist: Dict[str, List[Dict]] = {topic: [] for topic in WATCHLIST_TOPICS_ORDER}
    seen_titles_per_topic: Dict[str, set] = {topic: set() for topic in WATCHLIST_TOPICS_ORDER}

    for art in ranked_articles:
        # salta gli stessi oggetti già usati nei deep-dives
        if art in deep_dive_articles:
            continue

        topic = _article_topic(art)
        if topic not in watchlist:
            continue

        norm_title = _normalise_title(art.title)
        if not norm_title:
            continue

        # salta se è uno dei deep-dives (stesso titolo)
        if norm_title in deep_titles:
            continue

        # salta se già presente nello stesso topic
        if norm_title in seen_titles_per_topic[topic]:
            continue

        if len(watchlist[topic]) >= max_per_topic:
            continue

        item = {
            "id": f"wl|{topic}|{art.source}|{art.title}",
            "title": art.title,
            "url": art.url,
            "source": art.source,
        }
        watchlist[topic].append(item)
        seen_titles_per_topic[topic].add(norm_title)

    return watchlist


def build_deep_dives_payload(
    deep_dive_articles,
    summaries: List[Dict],
) -> List[Dict]:
    """
    Combina i RawArticle deep-dive con i riassunti dello summarizer
    in un payload unico per il report builder.
    """
    payload: List[Dict] = []
    for art, summ in zip(deep_dive_articles, summaries):
        topic = _article_topic(art)
        entry = {
            "id": f"deep|{art.source}|{art.title}",
            "title": art.title,
            "url": art.url,
            "source": art.source,
            "topic": topic,
            "published_at": art.published_at.isoformat(),
            "what_it_is": summ.get("what_it_is", ""),
            "who": summ.get("who", ""),
            "what_it_does": summ.get("what_it_does", ""),
            "why_it_matters": summ.get("why_it_matters", ""),
            "strategic_view": summ.get("strategic_view", ""),
        }
        payload.append(entry)
    return payload


# -----------
#   MAIN
# -----------

def main():
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

    # parametri LLM
    llm_cfg = cfg.get("llm", {})
    model = llm_cfg.get("model", "")
    temperature = float(llm_cfg.get("temperature", 0.25))
    max_tokens = int(llm_cfg.get("max_tokens", 900))
    language = llm_cfg.get("language", "en")

    # impostazioni output
    output_cfg = cfg.get("output", {})
    html_dir = Path(output_cfg.get("html_dir", "reports/html"))
    pdf_dir = Path(output_cfg.get("pdf_dir", "reports/pdf"))
    file_prefix = output_cfg.get("file_prefix", "report_")

    max_articles_for_cleaning = int(cfg.get("max_articles_per_day", 50))

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

    # 4) Ranking globale (priorità fonti + keyword, ecc.)
    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")

    if not ranked:
        print("No ranked articles. Exiting.")
        return

    # 5) Selezione deep-dives (3 articoli migliori)
    deep_dive_articles = ranked[:3]
    print("[SELECT] Deep-dive articles:", [a.title for a in deep_dive_articles])

    # 6) Watchlist per topic (3–5 articoli max per topic) senza duplicazioni
    watchlist_grouped = build_watchlist(
        ranked_articles=ranked,
        deep_dive_articles=deep_dive_articles,
        max_per_topic=5,
    )
    print("[SELECT] Watchlist built with topics:",
          list(watchlist_grouped.keys()))

    # 7) Summarization con LLM – SOLO sui 3 deep-dives
    print("Summarizing deep-dive articles with LLM...")
    deep_dives_summaries = summarize_articles(
        deep_dive_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # 8) Prepara payload finale per il report builder
    deep_dives_payload = build_deep_dives_payload(
        deep_dive_articles=deep_dive_articles,
        summaries=deep_dives_summaries,
    )

    # salva anche un JSON dei deep-dives (utile per debug / future feature)
    json_dir = Path("reports/json")
    json_dir.mkdir(parents=True, exist_ok=True)
    date_str = today_str()
    json_path = json_dir / f"deep_dives_{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(deep_dives_payload, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved deep-dives JSON to: {json_path}")

    # 9) Costruzione HTML
    print("Building HTML report...")
    html = build_html_report(
        deep_dives=deep_dives_payload,
        watchlist=watchlist_grouped,
        date_str=date_str,
    )

    # 10) Salvataggio HTML + PDF
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

    # 11) Invio email (se configurato) – non deve far fallire il job
    print("Sending report via email...")
    try:
        send_report_email(
            pdf_path=str(pdf_path),
            date_str=date_str,
            html_path=str(html_path),
        )
        print("[EMAIL] Email step completed (check SMTP / mailbox for details).")
    except Exception as e:
        print("[EMAIL] Unhandled error while sending email:", repr(e))
        print("[EMAIL] Continuing anyway – report generation completed.")

    print("Process completed.")


if __name__ == "__main__":
    main()
