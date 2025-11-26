from pathlib import Path
from datetime import datetime
import yaml

from .rss_collector import collect_from_rss
from .cleaning import clean_articles
from summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf


BASE_DIR = Path(__file__).resolve().parent.parent


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_config():
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def load_rss_sources():
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["feeds"]


def main():
    cwd = Path.cwd()
    print("[DEBUG] CWD:", cwd)
    print("[DEBUG] Repo contents:", list(cwd.iterdir()))

    cfg = load_config()
    feeds = load_rss_sources()

    max_articles = int(cfg.get("max_articles_per_day", 10))
    llm_cfg = cfg["llm"]
    model = llm_cfg["model"]
    temperature = float(llm_cfg["temperature"])
    max_tokens = int(llm_cfg["max_tokens"])

    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"Collected {len(raw_articles)} raw articles")

    cleaned = clean_articles(raw_articles, max_articles=max_articles)
    print(f"After cleaning: {len(cleaned)} articles")

    if not cleaned:
        print("No recent articles found. Exiting.")
        return

    print("Summarizing with LLM...")
    summaries = summarize_articles(cleaned, model=model, temperature=temperature, max_tokens=max_tokens)

    print("Building HTML report...")
    date_str = today_str()
    html = build_html_report(summaries, date_str=date_str)

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


if __name__ == "__main__":
    main()
