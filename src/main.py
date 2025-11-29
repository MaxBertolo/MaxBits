from pathlib import Path
from datetime import datetime
from typing import Dict, List
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


# ---------------------------------------------------------------------
# TOPIC CATEGORIZATION FOR WATCHLIST
# ---------------------------------------------------------------------

def _topic_for_article(article: RawArticle) -> str:
    """
    Ritorna una categoria testuale per la watchlist.
    Le categorie sono le stesse usate in report_builder:
      - "TV/Streaming"
      - "Telco/5G"
      - "Media/Platforms"
      - "AI/Cloud/Quantum"
      - "Space/Infra"
    """
    title = (article.title or "").lower()
    source = (article.source or "").lower()
    text = title + " " + source

    # TV / Streaming
    if any(k in text for k in ["netflix", "disney+", "disney plus", "hulu", "amazon prime", "prime video",
                               "hbo", "sky", "streaming", "vod", "ott", "tv", "broadcast"]):
        return "TV/Streaming"

    # Space / Infrastructure
    if any(k in text for k in ["spacex", "space", "satellite", "satcom", "orbit", "nasa", "esa", "launch vehicle"]):
        return "Space/Infra"

    # Telco / 5G / Networks
    if any(k in text for k in ["5g", "4g", "lte", "spectrum", "fiber", "broadband",
                               "telecom", "telco", "operator", "carrier", "network"]):
        return "Telco/5G"

    # AI / Cloud / Quantum / Data
    if any(k in text for k in ["ai", "artificial intelligence", "machine learning", "gen ai",
                               "cloud", "data center", "datacenter", "saas", "iaas",
                               "quantum", "llm"]):
        return "AI/Cloud/Quantum"

    # Media / Platforms / Social
    if any(k in text for k in ["meta", "facebook", "instagram", "tiktok", "youtube",
                               "x.com", "twitter", "snap", "social", "creator", "advertising"]):
        return "Media/Platforms"

    # Default: prova a mappare su Media/Platforms o Telco
    if "media" in text:
        return "Media/Platforms"
    if "telecom" in text or "operator" in text:
        return "Telco/5G"

    return "Media/Platforms"  # fallback neutro


def build_watchlist(articles: List[RawArticle], max_per_topic: int = 5) -> Dict[str, List[Dict]]:
    """
    Crea la watchlist:
      - prende gli articoli "non deep–dive"
      - li distribuisce nelle categorie
      - limita a max_per_topic per categoria
    Ritorna dict: topic -> list[{title, url, source}]
    """
    buckets: Dict[str, List[Dict]] = {
        "TV/Streaming": [],
        "Telco/5G": [],
        "Media/Platforms": [],
        "AI/Cloud/Quantum": [],
        "Space/Infra": [],
    }

    for art in articles:
        topic = _topic_for_article(art)
        lst = buckets.setdefault(topic, [])
        if len(lst) >= max_per_topic:
            continue
        lst.append(
            {
                "title": art.title,
                "url": art.url,
                "source": art.source,
            }
        )

    # log di debug
    for k, v in buckets.items():
        print(f"[WATCHLIST] {k}: {len(v)} items")

    return buckets


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

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
    language = llm_cfg.get("language", "en")

    # 2) Raccolta RSS
    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"[RSS] Total raw articles collected: {len(raw_articles)}")

    if not raw_articles:
        print("No articles collected from RSS. Exiting.")
        return

    # 3) Cleaning (es. ultime 24h, dedup, limite massimo)
    cleaned = clean_articles(raw_articles, max_articles=max_articles_for_cleaning)
    print(f"After cleaning: {len(cleaned)} articles")

    if not cleaned:
        print("No recent articles after cleaning. Exiting.")
        return

    # 4) Ranking globale
    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")

    if not ranked:
        print("No ranked articles found. Exiting.")
        return

    # 5) Selezione: 3 deep–dive + watchlist (resto)
    deep_raw = ranked[:3]
    watch_candidates = ranked[3:]  # il resto va in watchlist

    print(f"[SELECT] Deep–dives: {len(deep_raw)}")
    print(f"[SELECT] Watchlist candidates: {len(watch_candidates)}")

    # 6) Summarization per i 3 deep–dive
    print("Summarizing deep-dive articles with LLM...")
    deep_dives = summarize_articles(
        deep_raw,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # 7) Costruzione watchlist (solo titolo+url+source)
    watchlist = build_watchlist(watch_candidates, max_per_topic=5)

    # 8) Costruzione HTML
    print("Building HTML report...")
    date_str = today_str()
    html = build_html_report(
        deep_dives=deep_dives,
        watchlist=watchlist,
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
