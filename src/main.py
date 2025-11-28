from pathlib import Path
from datetime import datetime
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
    temperature = float(llm_cfg.get("temperature", 0.2))
    max_tokens = int(llm_cfg.get("max_tokens", 600))

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

    # 4) Ranking → TOP 15
    top_articles = rank_articles(cleaned)
    print(f"After ranking: {len(top_articles)} articles (top 15)")

    if not top_articles:
        print("No ranked articles found. Exiting.")
        return

    # 5) Summarization con LLM
    print("Summarizing with LLM...")
    summaries = summarize_articles(
        top_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # 6) Costruzione HTML
    print("Building HTML report...")
    date_str = today_str()
    html = build_html_report(summaries, date_str=date_str)

    # 7) Salvataggio HTML + PDF
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

    # 8) Invio email (NON fa fallire il job se qualcosa va storto)
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
