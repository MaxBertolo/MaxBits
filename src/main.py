from pathlib import Path
from datetime import datetime
from collections import defaultdict
import yaml

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email


# Root del repo (cartella padre di src/)
BASE_DIR = Path(__file__).resolve().parent.parent


def today_str() -> str:
    """Restituisce la data di oggi come stringa YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def load_config():
    """Carica config/config.yaml."""
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def load_rss_sources():
    """Carica la lista dei feed da config/sources_rss.yaml."""
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["feeds"]


# -------------------------------------------------------------------
# CATEGORIZZAZIONE SEMPLICE PER ARGOMENTO
# -------------------------------------------------------------------

TOPIC_KEYWORDS = {
    "Telco & 5G": [
        "5g", "6g", "telco", "telecom", "mobile", "operator", "carrier",
        "spectrum", "fiber", "ftth", "broadband", "network", "edge"
    ],
    "Media, TV & Streaming": [
        "tv", "broadcast", "streaming", "ott", "video", "vod",
        "content", "sport rights", "ad tech", "advertising"
    ],
    "AI & GenAI": [
        "ai", "artificial intelligence", "genai", "foundation model",
        "llm", "machine learning", "chatbot"
    ],
    "Cloud & Data Center": [
        "cloud", "datacenter", "data center", "colocation", "hyperscaler",
        "aws", "azure", "google cloud"
    ],
    "Robotics, Space & IoT": [
        "robot", "robotics", "space", "satellite", "orbit", "launch",
        "iot", "drones"
    ],
    "Cybersecurity & Privacy": [
        "cyber", "security", "ransomware", "breach", "vulnerability",
        "encryption", "privacy", "zero trust"
    ],
}


def categorize_article(article) -> str:
    """
    Ritorna una categoria testuale basata su parole chiave
    nel titolo + contenuto + fonte.
    """
    text = f"{article.title} {article.content} {article.source}".lower()

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(k in text for k in keywords):
            return topic

    return "Other Tech Topics"


def build_watchlist_grouped(articles, max_total: int = 15, max_per_topic: int = 3):
    """
    Prende una lista di articoli (già ordinati per importanza) e costruisce:
    - massimo max_total articoli totali
    - massimo max_per_topic articoli per categoria

    Ritorna:
        dict(topic -> list[ {title, url, source} ])
    """
    grouped = defaultdict(list)
    total_added = 0

    for art in articles:
        if total_added >= max_total:
            break

        topic = categorize_article(art)

        if len(grouped[topic]) >= max_per_topic:
            continue  # questa categoria ha già abbastanza articoli

        grouped[topic].append(
            {
                "title": art.title,
                "url": art.url,
                "source": art.source,
            }
        )
        total_added += 1

    return grouped


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

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

    max_articles_for_cleaning = int(cfg.get("max_articles_per_day", 50))
    llm_cfg = cfg.get("llm", {})
    model = llm_cfg.get("model", "")
    temperature = float(llm_cfg.get("temperature", 0.25))
    max_tokens = int(llm_cfg.get("max_tokens", 900))

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

    # 4) Ranking complessivo
    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")

    if not ranked:
        print("No ranked articles found. Exiting.")
        return

    # 5) Selezione:
    #    - 3 articoli per deep dive (riassunto completo con LLM)
    #    - il resto per la watchlist (solo titolo + link)
    deep_dive_articles = ranked[:3]
    watchlist_candidates = ranked[3:]  # gli altri, in ordine di importanza

    print(f"[SELECT] Deep-dive articles: {len(deep_dive_articles)}")
    print(f"[SELECT] Watchlist candidates: {len(watchlist_candidates)}")

    # 6) Summarization con LLM SOLO per i 3 deep-dive
    print("Summarizing deep-dive articles with LLM...")
    deep_dive_summaries = summarize_articles(
        deep_dive_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # 7) Costruzione della watchlist (max 15, max 3 per topic)
    watchlist_grouped = build_watchlist_grouped(
        watchlist_candidates,
        max_total=15,
        max_per_topic=3,
    )

    # 8) Costruzione HTML
    print("Building HTML report...")
    date_str = today_str()
    html = build_html_report(
        deep_dives=deep_dive_summaries,
        watchlist_grouped=watchlist_grouped,
        date_str=date_str,
    )

    # 9) Salvataggio HTML + PDF
    html_dir = Path("reports/html")
    pdf_dir = Path("reports/pdf")
    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    html_path = html_dir / f"report_{date_str}.html"
    pdf_path = pdf_dir / f"report_{date_str}.pdf"

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
