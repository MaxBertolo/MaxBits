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
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> dict:
    config_path = BASE_DIR / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_rss_sources() -> list:
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("feeds", [])


# -----------------------------
# TOPIC DETECTION + NORMALISATION
# -----------------------------

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
    if not title:
        return ""
    t = title.strip().lower()
    while t.endswith((" .", ".", "!", "?", "…")):
        t = t[:-1].strip()
    return t


def _article_topic(article) -> str:
    raw_topic = getattr(article, "topic", "") or ""
    if raw_topic in WATCHLIST_TOPICS_ORDER:
        return raw_topic

    base = raw_topic or getattr(article, "source", "") or ""
    t = base.lower()

    if any(k in t for k in ("tv", "stream", "ott", "vod")):
        return "TV/Streaming"
    if any(k in t for k in ("5g", "telco", "mobile", "network", "carrier")):
        return "Telco/5G"
    if any(k in t for k in ("media", "platform", "social", "adtech")):
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


# -----------------------------
# WATCHLIST BUILDER
# -----------------------------

def build_watchlist(ranked, deep_dives, max_per_topic=5):
    deep_titles = {_normalise_title(a.title) for a in deep_dives}

    watchlist = {t: [] for t in WATCHLIST_TOPICS_ORDER}
    seen_titles = {t: set() for t in WATCHLIST_TOPICS_ORDER}

    for art in ranked:
        if art in deep_dives:
            continue

        topic = _article_topic(art)
        if topic not in watchlist:
            continue

        norm = _normalise_title(art.title)
        if not norm or norm in deep_titles or norm in seen_titles[topic]:
            continue

        if len(watchlist[topic]) >= max_per_topic:
            continue

        watchlist[topic].append({
            "id": f"wl|{topic}|{art.source}|{art.title}",
            "title": art.title,
            "url": art.url,
            "source": art.source,
        })
        seen_titles[topic].add(norm)

    return watchlist


# -----------------------------
# DEEP DIVES PAYLOAD
# -----------------------------

def build_deep_dives_payload(deep_dives, summaries):
    payload = []
    for art, summ in zip(deep_dives, summaries):
        payload.append({
            "id": f"deep|{art.source}|{art.title}",
            "title": art.title,
            "url": art.url,
            "source": art.source,
            "topic": _article_topic(art),
            "published_at": art.published_at.isoformat(),
            "what_it_is": summ.get("what_it_is", "").strip(),
            "who": summ.get("who", "").strip(),
            "what_it_does": summ.get("what_it_does", "").strip(),
            "why_it_matters": summ.get("why_it_matters", "").strip(),
            "strategic_view": summ.get("strategic_view", "").strip(),
        })
    return payload


# -----------------------------
# MAIN
# -----------------------------

def main():
    cfg = load_config()
    feeds = load_rss_sources()

    llm = cfg.get("llm", {})
    model = llm.get("model", "")
    temperature = float(llm.get("temperature", 0.25))
    max_tokens = int(llm.get("max_tokens", 900))

    out_cfg = cfg.get("output", {})
    html_dir = Path(out_cfg.get("html_dir", "reports/html"))
    pdf_dir = Path(out_cfg.get("pdf_dir", "reports/pdf"))
    file_prefix = out_cfg.get("file_prefix", "report_")

    max_articles_clean = int(cfg.get("max_articles_per_day", 50))

    # ---------------------
    # 1. RSS COLLECTION
    # ---------------------
    raw = collect_from_rss(feeds)
    if not raw:
        print("No articles collected. Stopping.")
        return

    cleaned = clean_articles(raw, max_articles=max_articles_clean)
    ranked = rank_articles(cleaned)

    if not ranked:
        print("No ranked articles. Stopping.")
        return

    # ---------------------
    # 2. DEEP DIVES + WATCHLIST
    # ---------------------
    deep_dives = ranked[:3]
    watchlist = build_watchlist(ranked, deep_dives)

    summaries = summarize_articles(
        deep_dives,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    deep_payload = build_deep_dives_payload(deep_dives, summaries)

    # ---------------------
    # 3. SAVE JSON
    # ---------------------
    date = today_str()
    json_dir = Path("reports/json")
    json_dir.mkdir(parents=True, exist_ok=True)
    with open(json_dir / f"deep_dives_{date}.json", "w", encoding="utf-8") as jf:
        json.dump(deep_payload, jf, ensure_ascii=False, indent=2)

    # ---------------------
    # 4. BUILD HTML + PDF
    # ---------------------
    html = build_html_report(
        deep_dives=deep_payload,
        watchlist=watchlist,
        date_str=date,
    )

    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    html_path = html_dir / f"{file_prefix}{date}.html"
    pdf_path = pdf_dir / f"{file_prefix}{date}.pdf"

    html_path.write_text(html, encoding="utf-8")
    html_to_pdf(html, str(pdf_path))

    # ---------------------
    # 5. SEND EMAIL
    # ---------------------
    send_report_email(str(pdf_path), date_str=date, html_path=str(html_path))

    # ---------------------
    # 6. SEND TELEGRAM
    # ---------------------
    send_telegram_pdf(str(pdf_path), date)

    print("Daily pipeline completed.")


if __name__ == "__main__":
    main()
