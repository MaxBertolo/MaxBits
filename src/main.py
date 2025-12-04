from pathlib import Path
from datetime import datetime
from typing import Dict, List
import json
import yaml

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email
from .telegram_sender import send_telegram_pdf


BASE_DIR = Path(__file__).resolve().parent.parent


def today_str() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> dict:
    """Load config/config.yaml."""
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_rss_sources() -> list:
    """Load RSS feeds from config/sources_rss.yaml."""
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("feeds", [])


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


# -------------------------
#   TOPIC + DEDUP HELPERS
# -------------------------

def _normalise_title(title: str) -> str:
    if not title:
        return ""
    t = title.strip().lower()
    while t.endswith((" .", ".", "!", "?", "…")):
        t = t[:-1].strip()
    return t


def _article_topic(article) -> str:
    """
    1) Se rss_collector ha già messo topic esatto in WATCHLIST_TOPICS_ORDER → usalo.
    2) Altrimenti usa keyword (topic o source) per assegnare uno degli 8 temi.
    """
    raw_topic = getattr(article, "topic", "") or ""
    if raw_topic in WATCHLIST_TOPICS_ORDER:
        return raw_topic

    base = raw_topic or getattr(article, "source", "") or ""
    t = base.lower()

    if any(k in t for k in ("tv", "stream", "ott", "vod")):
        return "TV/Streaming"
    if any(k in t for k in ("5g", "telco", "mobile", "network", "carrier", "operator")):
        return "Telco/5G"
    if any(k in t for k in ("media", "platform", "social", "adtech", "advertising")):
        return "Media/Platforms"
    if any(k in t for k in ("robot", "automation")):
        return "Robotics/Automation"
    if any(k in t for k in ("broadcast", "video", "linear")):
        return "Broadcast/Video"
    if any(k in t for k in ("satcom", "satellite")):
        return "Satellite/Satcom"
    if any(k in t for k in ("space", "orbital", "launch", "rocket")):
        return "Space/Infra"

    return "AI/Cloud/Quantum"


def build_watchlist(
    ranked_articles,
    deep_dive_articles,
    max_per_topic: int = 5,
) -> Dict[str, List[Dict]]:
    """
    Crea la watchlist per topic:
      - esclude i 3 deep-dives
      - niente duplicazioni per titolo
      - max max_per_topic articoli per topic
    """
    deep_titles = {_normalise_title(a.title) for a in deep_dive_articles}

    watchlist: Dict[str, List[Dict]] = {topic: [] for topic in WATCHLIST_TOPICS_ORDER}
    seen_titles_per_topic: Dict[str, set] = {topic: set() for topic in WATCHLIST_TOPICS_ORDER}

    for art in ranked_articles:
        if art in deep_dive_articles:
            continue

        topic = _article_topic(art)
        if topic not in watchlist:
            continue

        norm_title = _normalise_title(art.title)
        if not norm_title:
            continue

        if norm_title in deep_titles:
            continue

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
    Combina i RawArticle deep-dive con i riassunti LLM in un payload unico.
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
    # Debug sul workspace GitHub Actions
    cwd = Path.cwd()
    print("[DEBUG] CWD:", cwd)
    try:
        print("[DEBUG] Repo contents:", [p.name for p in cwd.iterdir()])
    except Exception as e:
        print("[DEBUG] Cannot list repo contents:", repr(e))

    # 1) Config + fonti RSS
    cfg = load_config()
    feeds = load_rss_sources()

    llm_cfg = cfg.get("llm", {})
    model = llm_cfg.get("model", "")
    temperature = float(llm_cfg.get("temperature", 0.25))
    max_tokens = int(llm_cfg.get("max_tokens", 900))

    output_cfg = cfg.get("output", {})
    html_dir = Path(output_cfg.get("html_dir", "reports/html"))
    pdf_dir = Path(output_cfg.get("pdf_dir", "reports/pdf"))
    file_prefix = output_cfg.get("file_prefix", "report_")

    max_articles_for_cleaning = int(cfg.get("max_articles_per_day", 50))

    # 2) RSS → raw articles
    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"Collected {len(raw_articles)} raw articles")
    if not raw_articles:
        print("No articles collected from RSS. Exiting.")
        return

    # 3) Cleaning
    cleaned = clean_articles(raw_articles, max_articles=max_articles_for_cleaning)
    print(f"After cleaning: {len(cleaned)} articles")
    if not cleaned:
        print("No recent articles after cleaning. Exiting.")
        return

    # 4) Ranking
    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")
    if not ranked:
        print("No ranked articles. Exiting.")
        return

    # 5) Deep-dives (top 3)
    deep_dive_articles = ranked[:3]
    print("[SELECT] Deep-dive articles:", [a.title for a in deep_dive_articles])

    # 6) Watchlist per topic
    watchlist_grouped = build_watchlist(
        ranked_articles=ranked,
        deep_dive_articles=deep_dive_articles,
        max_per_topic=5,
    )
    print("[SELECT] Watchlist built with topics:", list(watchlist_grouped.keys()))

    # 7) Summarization deep-dives
    print("Summarizing deep-dive articles with LLM...")
    deep_dives_summaries = summarize_articles(
        deep_dive_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    deep_dives_payload = build_deep_dives_payload(
        deep_dive_articles=deep_dive_articles,
        summaries=deep_dives_summaries,
    )

    # 8) Salva JSON per debug
    json_dir = Path("reports/json")
    json_dir.mkdir(parents=True, exist_ok=True)
    date_str = today_str()
    json_path = json_dir / f"deep_dives_{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(deep_dives_payload, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved deep-dives JSON to: {json_path}")

    # 9) Build HTML
    print("Building HTML report...")
    html = build_html_report(
        deep_dives=deep_dives_payload,
        watchlist=watchlist_grouped,
        date_str=date_str,
    )

    # 10) Save HTML + PDF
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

    # 11) Email
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

    # 12) Telegram PDF
    print("Sending report PDF to Telegram...")
    try:
        send_telegram_pdf(str(pdf_path), date_str)
        print("[TELEGRAM] Telegram step completed (check bot/chat).")
    except Exception as e:
        print("[TELEGRAM] Unhandled error while sending Telegram PDF:", repr(e))

    print("Process completed.")


if __name__ == "__main__":
    main()
