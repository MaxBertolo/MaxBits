from pathlib import Path
from datetime import datetime
from typing import Dict, List
import yaml

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles, strip_html_title
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email
from .models import RawArticle


# Root del repo (cartella padre di src/)
BASE_DIR = Path(__file__).resolve().parent.parent


# =============================
# UTILITY
# =============================

def today_str() -> str:
    """Restituisce la data di oggi come stringa YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> Dict:
    """Carica config/config.yaml."""
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_rss_sources() -> List[Dict]:
    """Carica la lista dei feed da config/sources_rss.yaml."""
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("feeds", [])


# =============================
# WATCHLIST: CATEGORIE & LOGICA
# =============================

WATCHLIST_TOPICS = [
    "TV/Streaming",
    "Telco/5G",
    "Media/Platforms",
    "AI/Cloud/Quantum",
    "Space/Infra",
]


def categorize_article_for_watchlist(article: RawArticle) -> str:
    """
    Prova a capire in che “bucket” mettere l’articolo
    guardando titolo + sorgente.
    """
    title = (article.title or "").lower()
    source = (article.source or "").lower()
    text = title + " " + source

    # TV / Streaming
    if any(k in text for k in ["netflix", "disney+", "prime video", "hbo", "streaming", "vod", "tv"]):
        return "TV/Streaming"

    # Telco / 5G
    if any(k in text for k in ["5g", "telco", "telecom", "verizon", "vodafone", "bt", "mobile", "broadband"]):
        return "Telco/5G"

    # Media / piattaforme / social
    if any(k in text for k in ["social", "tiktok", "youtube", "meta", "facebook", "instagram", "x.com", "twitter"]):
        return "Media/Platforms"

    # AI / Cloud / Quantum
    if any(k in text for k in ["ai", "artificial intelligence", "cloud", "saas", "data center", "ml", "quantum", "gpu"]):
        return "AI/Cloud/Quantum"

    # Space / Infrastructure
    if any(k in text for k in ["space", "satellite", "launch", "spacex", "rocket", "orbit", "leo", "geo"]):
        return "Space/Infra"

    # Default: Telco/5G (verrà comunque ribilanciato nell’aggregazione)
    return "Telco/5G"


def build_watchlist(articles: List[RawArticle]) -> Dict[str, List[Dict]]:
    """
    Distribuisce gli articoli su 5 topic.
    Obiettivo: 3–5 elementi per categoria (se ci sono abbastanza articoli).
    Gli elementi sono dizionari semplici: title/title_clean/url/source.
    """
    # 1) prima passata: assegnazione “naturale”
    grouped: Dict[str, List[Dict]] = {topic: [] for topic in WATCHLIST_TOPICS}
    global_pool: List[Dict] = []

    for art in articles:
        cat = categorize_article_for_watchlist(art)
        item = {
            "title": art.title,
            "title_clean": strip_html_title(art.title),
            "url": art.url,
            "source": art.source,
        }
        grouped.setdefault(cat, []).append(item)
        global_pool.append(item)

    # 2) seconda passata: garantire almeno 3 elementi per categoria
    #    prelevando, se serve, dal pool globale (senza duplicati grossolani)
    for cat in WATCHLIST_TOPICS:
        items = grouped.get(cat, [])
        if len(items) < 3:
            for cand in global_pool:
                if cand in items:
                    continue
                items.append(cand)
                if len(items) >= 3:
                    break
        # massimo 5 per non allungare troppo il report
        grouped[cat] = items[:5]

    return grouped


# =============================
# MAIN
# =============================

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
    # language = llm_cfg.get("language", "en")  # già implicito nel prompt, se ti serve

    # 2) Raccolta RSS
    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"[RSS] Total raw articles collected: {len(raw_articles)}")

    if not raw_articles:
        print("No articles collected from RSS. Exiting.")
        return

    # 3) Cleaning (es. ultime 24h, dedup, limit)
    cleaned = clean_articles(raw_articles, max_articles=max_articles_for_cleaning)
    print(f"[CLEAN] After cleaning: {len(cleaned)} articles")

    if not cleaned:
        print("No recent articles after cleaning. Exiting.")
        return

    # 4) Ranking
    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")

    if not ranked:
        print("No ranked articles found. Exiting.")
        return

    # 5) Selezione deep-dives (max 3) + watchlist (altri ~15)
    deep_dives_raw: List[RawArticle] = ranked[:3]
    watchlist_candidates: List[RawArticle] = ranked[3:3 + 20]  # es. altri 20 candidati

    print(f"[SELECT] Deep-dive articles: {len(deep_dives_raw)}")
    print(f"[SELECT] Watchlist candidates: {len(watchlist_candidates)}")

    # 6) Summarization con LLM per i soli deep-dives
    print("Summarizing deep–dive articles with LLM...")
    deep_dives_summaries = summarize_articles(
        deep_dives_raw,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Aggiungo il topic a ciascun deep-dive (per mostrarlo nel report)
    for art, summary in zip(deep_dives_raw, deep_dives_summaries):
        summary["topic"] = categorize_article_for_watchlist(art)

    # 7) Costruzione watchlist per topic (3–5 link per categoria)
    print("Building watchlist by topic...")
    watchlist_grouped = build_watchlist(watchlist_candidates)
    print(f"[SELECT] Watchlist built with topics: {list(watchlist_grouped.keys())}")

    # 8) Costruzione HTML
    print("Building HTML report...")
    date_str = today_str()
    html = build_html_report(
        deep_dives=deep_dives_summaries,
        watchlist=watchlist_grouped,
        date_str=date_str,
    )

    # 9) Output: HTML + PDF (usa i path da config.yaml se presenti)
    out_cfg = cfg.get("output", {})
    html_dir = Path(out_cfg.get("html_dir", "reports/html"))
    pdf_dir = Path(out_cfg.get("pdf_dir", "reports/pdf"))
    prefix = out_cfg.get("file_prefix", "report_")

    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    html_path = html_dir / f"{prefix}{date_str}.html"
    pdf_path = pdf_dir / f"{prefix}{date_str}.pdf"

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
        print("[EMAIL] Email step completed (check SMTP / mailbox for details).")
    except Exception as e:
        print("[EMAIL] Unhandled error while sending email:", repr(e))
        print("[EMAIL] Continuing anyway – report generation completed.")

    print("Process completed.")


if __name__ == "__main__":
    main()
