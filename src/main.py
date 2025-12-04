from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import re
import json
import yaml

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email
from .models import RawArticle


BASE_DIR = Path(__file__).resolve().parent.parent

TOPIC_KEYS = [
    "TV/Streaming",
    "Telco/5G",
    "Media/Platforms",
    "AI/Cloud/Quantum",
    "Space/Infra",
    "Robotics/Automation",
    "Broadcast/Video",
    "Satellite/Satcom",
]


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> Dict:
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_rss_sources() -> List[Dict]:
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("feeds", [])


# ---------- HELPERS PER DEDUPLICA / WATCHLIST ----------

def _normalize_title(raw_title: str) -> str:
    if not raw_title:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_title)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_watchlist_by_topic(candidates: List[RawArticle], max_per_topic: int = 5) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = {topic: [] for topic in TOPIC_KEYS}
    seen_titles_global = set()

    for art in candidates:
        norm_title = _normalize_title(art.title)
        if norm_title in seen_titles_global:
            continue
        seen_titles_global.add(norm_title)

        topic = getattr(art, "topic", None) or "AI/Cloud/Quantum"
        if topic not in grouped:
            topic = "AI/Cloud/Quantum"

        bucket = grouped[topic]
        if len(bucket) >= max_per_topic:
            continue

        bucket.append(
            {
                "title": art.title,
                "url": art.url,
                "source": art.source,
            }
        )

    return grouped


def select_deep_dives_and_watchlist(
    articles: List[RawArticle],
    deep_dives_count: int = 3,
    max_watchlist_per_topic: int = 5,
):
    if not articles:
        return [], {topic: [] for topic in TOPIC_KEYS}

    deep_dives = articles[:deep_dives_count]
    deep_norm_titles = {_normalize_title(a.title) for a in deep_dives}

    watch_candidates: List[RawArticle] = []
    for art in articles[deep_dives_count:]:
        norm_title = _normalize_title(art.title)
        if norm_title in deep_norm_titles:
            continue
        watch_candidates.append(art)

    watchlist_by_topic = build_watchlist_by_topic(
        watch_candidates,
        max_per_topic=max_watchlist_per_topic,
    )

    return deep_dives, watchlist_by_topic


def _collect_recent_daily_pdfs(
    *,
    base_pdf_dir: Path,
    prefix: str,
    today: datetime,
    days_back: int = 6,
) -> List[Dict]:
    """
    Ritorna i PDF esistenti dei giorni precedenti (max days_back),
    in ordine dal più recente al meno recente.
    """
    items: List[Dict] = []
    for delta in range(1, days_back + 1):
        d = (today - timedelta(days=delta)).date()
        date_str = d.strftime("%Y-%m-%d")
        filename = f"{prefix}{date_str}.pdf"
        pdf_path = base_pdf_dir / filename
        if pdf_path.exists():
            # dal punto di vista dell'HTML (reports/html), il PDF è in ../pdf/
            href = f"../pdf/{filename}"
            items.append({"date": date_str, "href": href})
    return items


def _find_latest_weekly_pdf(base_weekly_dir: Path) -> str | None:
    """
    Cerca l'ultimo weekly report generato (pattern 'weekly_*.pdf').
    Ritorna l'href relativo visto dall'HTML daily (../weekly/xxx.pdf) o None.
    """
    if not base_weekly_dir.exists():
        return None

    pdfs = sorted(base_weekly_dir.glob("weekly_*.pdf"))
    if not pdfs:
        return None

    latest = pdfs[-1].name
    # l'HTML daily è in reports/html, i weekly PDF in reports/weekly
    return f"../weekly/{latest}"


# ------------------------ MAIN ------------------------

def main():
    cwd = Path.cwd()
    print("[DEBUG] CWD:", cwd)
    try:
        print("[DEBUG] Repo contents:", [p.name for p in cwd.iterdir()])
    except Exception as e:
        print("[DEBUG] Cannot list repo contents:", repr(e))

    cfg = load_config()
    feeds = load_rss_sources()

    max_articles_for_cleaning = int(cfg.get("max_articles_per_day", 50))
    llm_cfg = cfg.get("llm", {})
    model = llm_cfg.get("model", "")
    temperature = float(llm_cfg.get("temperature", 0.25))
    max_tokens = int(llm_cfg.get("max_tokens", 900))
    language = llm_cfg.get("language", "en")

    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"[RSS] Total raw articles collected: {len(raw_articles)}")

    if not raw_articles:
        print("No articles collected from RSS. Exiting.")
        return

    cleaned = clean_articles(raw_articles, max_articles=max_articles_for_cleaning)
    print(f"After cleaning: {len(cleaned)} articles")

    if not cleaned:
        print("No recent articles after cleaning. Exiting.")
        return

    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")

    if not ranked:
        print("No ranked articles. Exiting.")
        return

    deep_articles, watchlist_grouped = select_deep_dives_and_watchlist(
        ranked,
        deep_dives_count=3,
        max_watchlist_per_topic=5,
    )

    print(f"[SELECT] Deep-dives: {len(deep_articles)}")
    print(f"[SELECT] Watchlist topics: {list(watchlist_grouped.keys())}")

    if not deep_articles:
        print("No deep-dive candidates. Exiting.")
        return

    print("Summarizing deep-dive articles with LLM...")
    deep_dives_summaries = summarize_articles(
        deep_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # aggiungo topic ai deep-dives
    for art, summary in zip(deep_articles, deep_dives_summaries):
        topic = getattr(art, "topic", None)
        if topic not in TOPIC_KEYS:
            topic = "AI/Cloud/Quantum"
        summary["topic"] = topic

    # ---------- OUTPUT PATHS ----------

    out_cfg = cfg.get("output", {})
    html_dir = Path(out_cfg.get("html_dir", "reports/html"))
    pdf_dir = Path(out_cfg.get("pdf_dir", "reports/pdf"))
    weekly_dir = Path(out_cfg.get("weekly_dir", "reports/weekly"))
    json_dir = Path(out_cfg.get("json_dir", "reports/json"))
    prefix = out_cfg.get("file_prefix", "report_")

    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    weekly_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    date_str = today_str()
    html_path = html_dir / f"{prefix}{date_str}.html"
    pdf_path = pdf_dir / f"{prefix}{date_str}.pdf"

    # ---------- STORICO 7 GIORNI + WEEKLY LINK ----------

    today_dt = datetime.now()
    recent_reports = _collect_recent_daily_pdfs(
        base_pdf_dir=pdf_dir,
        prefix=prefix,
        today=today_dt,
        days_back=6,
    )
    latest_weekly_href = _find_latest_weekly_pdf(weekly_dir)

    # ---------- SALVA JSON DEI DEEP-DIVE (per weekly) ----------

    json_path = json_dir / f"deep_dives_{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(deep_dives_summaries, jf, ensure_ascii=False, indent=2)
    print("[DEBUG] Saved deep-dives JSON to:", json_path)

    # ---------- COSTRUZIONE HTML + PDF ----------

    print("Building HTML report...")
    html = build_html_report(
        deep_dives=deep_dives_summaries,
        watchlist=watchlist_grouped,
        date_str=date_str,
        recent_reports=recent_reports,
        weekly_pdf=latest_weekly_href,
    )

    print("[DEBUG] Saving HTML to:", html_path)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("[DEBUG] Converting HTML to PDF at:", pdf_path)
    html_to_pdf(html, str(pdf_path))

    print("Done. HTML report:", html_path)
    print("Done. PDF report:", pdf_path)

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
