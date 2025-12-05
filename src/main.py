# src/main.py

from __future__ import annotations

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


# -------------------------
#   UTILITIES
# -------------------------

def today_str() -> str:
    """Return today's date as 'YYYY-MM-DD'."""
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> dict:
    """Load config/config.yaml."""
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_rss_sources() -> list:
    """Load feed list from config/sources_rss.yaml."""
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    feeds = data.get("feeds", []) or []
    print(f"[DEBUG] Loaded {len(feeds)} RSS feeds")
    return feeds


# -------------------------
#   TOPICS & DEDUP
# -------------------------

WATCHLIST_TOPICS_ORDER = [
    "TV/Streaming",
    "Telco/5G",
    "Media/Platforms",
    "AI/Cloud/Quantum",
    "Space/Infra",
    "Robotics/Automation",
    "Broadcast/Video",
    "Satellite/Satcom",
    "CorCom/Digital",
]


def _normalise_title(title: str) -> str:
    """Normalize title for comparisons (lowercase + strip + trim punctuation)."""
    if not title:
        return ""
    t = title.strip().lower()
    while t.endswith((" .", ".", "!", "?", "…")):
        t = t[:-1].strip()
    return t


def _article_topic(article) -> str:
    """
    Decide the topic for a RawArticle.

    Priority:
      1) If article.topic is already an exact WATCHLIST_TOPICS_ORDER value → use it.
      2) Otherwise infer from source / topic string using explicit source mapping + keywords.
      3) Fallback: 'AI/Cloud/Quantum'.
    """
    raw_topic = getattr(article, "topic", "") or ""
    if raw_topic in WATCHLIST_TOPICS_ORDER:
        return raw_topic

    source = (getattr(article, "source", "") or "").lower()
    base = (raw_topic or source).lower()

    # --- explicit mappings for important sources ---
    if "gigaom" in source:
        return "Telco/5G"

    if "technologymagazine" in source or "technology magazine" in source:
        return "AI/Cloud/Quantum"

    if "venturebeat" in source:
        return "AI/Cloud/Quantum"

    if "corrierecomunicazioni" in source or "corcom" in source:
        return "CorCom/Digital"

    # --- topic by keywords in source/topic string ---
    if any(k in base for k in ("tv", "stream", "ott", "vod", "video on demand")):
        return "TV/Streaming"

    if any(k in base for k in ("5g", "6g", "telco", "carrier", "network", "mobile", "operator")):
        return "Telco/5G"

    if any(k in base for k in ("media", "platform", "social", "adtech", "advertising", "creator")):
        return "Media/Platforms"

    if any(k in base for k in ("robot", "robotics", "automation", "cobot")):
        return "Robotics/Automation"

    if any(k in base for k in ("broadcast", "linear", "dvb", "dtt")):
        return "Broadcast/Video"

    if any(k in base for k in ("satcom", "satellite", "geo", "leo", "meo")):
        return "Satellite/Satcom"

    if any(k in base for k in ("space", "orbital", "launch", "rocket", "spacex")):
        return "Space/Infra"

    # default bucket
    return "AI/Cloud/Quantum"


def build_watchlist(
    ranked_articles,
    deep_dive_articles,
    max_per_topic: int = 5,
) -> Dict[str, List[Dict]]:
    """
    Build watchlist grouped by topic, with strong dedup rules:

      - no article already used as deep-dive (title match)
      - no duplicate title inside the same topic
      - max N articles per topic (default 5)
      - skip articles without a usable title or URL
    """
    deep_titles = {_normalise_title(a.title) for a in deep_dive_articles}

    watchlist: Dict[str, List[Dict]] = {topic: [] for topic in WATCHLIST_TOPICS_ORDER}
    seen_titles_per_topic: Dict[str, set] = {topic: set() for topic in WATCHLIST_TOPICS_ORDER}

    for art in ranked_articles:
        # skip exact same object already chosen as deep-dive
        if art in deep_dive_articles:
            continue

        topic = _article_topic(art)
        if topic not in watchlist:
            continue

        if not getattr(art, "title", None):
            continue
        if not getattr(art, "url", None):
            continue

        norm_title = _normalise_title(art.title)
        if not norm_title:
            continue

        # skip if same title as any deep-dive
        if norm_title in deep_titles:
            continue

        # skip if already present in same topic
        if norm_title in seen_titles_per_topic[topic]:
            continue

        if len(watchlist[topic]) >= max_per_topic:
            continue

        item = {
            "id": f"wl|{topic}|{art.source}|{art.title}",
            "title": art.title.strip(),
            "url": art.url,
            "source": art.source,
        }
        watchlist[topic].append(item)
        seen_titles_per_topic[topic].add(norm_title)

    # log per-topic sizes
    for t in WATCHLIST_TOPICS_ORDER:
        print(f"[WATCHLIST] {t}: {len(watchlist[t])} items")

    return watchlist


def build_deep_dives_payload(
    deep_dive_articles,
    summaries: List[Dict],
) -> List[Dict]:
    """
    Combine RawArticle deep-dives and LLM summaries into final payload.

    IMPORTANT:
      - title is ALWAYS taken 1:1 from the original article (no LLM rewriting)
      - we defensively strip and fallback to 'Untitled' if something is broken
    """
    payload: List[Dict] = []

    for art, summ in zip(deep_dive_articles, summaries):
        title = (getattr(art, "title", "") or "").strip() or "Untitled"
        topic = _article_topic(art)
        published_at = getattr(art, "published_at", None)

        entry = {
            "id": f"deep|{art.source}|{title}",
            "title": title,
            "url": getattr(art, "url", "") or "",
            "source": getattr(art, "source", "") or "",
            "topic": topic,
            "published_at": published_at.isoformat() if published_at else "",
            "what_it_is": (summ.get("what_it_is", "") or "").strip(),
            "who": (summ.get("who", "") or "").strip(),
            "what_it_does": (summ.get("what_it_does", "") or "").strip(),
            "why_it_matters": (summ.get("why_it_matters", "") or "").strip(),
            "strategic_view": (summ.get("strategic_view", "") or "").strip(),
        }
        payload.append(entry)

    print(f"[DEEP_DIVES] Built payload for {len(payload)} articles")
    return payload


# -------------------------
#   MAIN ORCHESTRATION
# -------------------------

def main():
    # Debug info for GitHub Actions
    cwd = Path.cwd()
    print("[DEBUG] CWD:", cwd)
    try:
        print("[DEBUG] Repo contents:", [p.name for p in cwd.iterdir()])
    except Exception as e:
        print("[DEBUG] Cannot list repo contents:", repr(e))

    # 1) Config + RSS feeds
    cfg = load_config()
    feeds = load_rss_sources()

    # LLM config
    llm_cfg = cfg.get("llm", {}) or {}
    model = llm_cfg.get("model", "")
    temperature = float(llm_cfg.get("temperature", 0.25))
    max_tokens = int(llm_cfg.get("max_tokens", 900))

    # Output settings
    output_cfg = cfg.get("output", {}) or {}
    html_dir = Path(output_cfg.get("html_dir", "reports/html"))
    pdf_dir = Path(output_cfg.get("pdf_dir", "reports/pdf"))
    file_prefix = output_cfg.get("file_prefix", "report_")

    max_articles_for_cleaning = int(cfg.get("max_articles_per_day", 50))

    # 2) Collect RSS
    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"Collected {len(raw_articles)} raw articles")
    if not raw_articles:
        print("No articles collected from RSS. Exiting.")
        return

    # 3) Cleaning (freshness, dedup, max N)
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

    # 5) Pick deep-dives (top 3 ranked)
    deep_dive_articles = ranked[:3]
    print("[SELECT] Deep-dive articles:", [getattr(a, "title", "?") for a in deep_dive_articles])

    # 6) Build watchlist by topic (max 5 per topic, no duplicates, no deep-dives)
    watchlist_grouped = build_watchlist(
        ranked_articles=ranked,
        deep_dive_articles=deep_dive_articles,
        max_per_topic=5,
    )
    print("[SELECT] Watchlist topics:", list(watchlist_grouped.keys()))

    # 7) LLM summarization ONLY on the 3 deep-dives
    print("Summarizing deep-dive articles with LLM...")
    deep_dives_summaries = summarize_articles(
        deep_dive_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # 8) Build final deep-dives payload
    deep_dives_payload = build_deep_dives_payload(
        deep_dive_articles=deep_dive_articles,
        summaries=deep_dives_summaries,
    )

    # Save JSON snapshot (debug / future weekly)
    json_dir = Path("reports/json")
    json_dir.mkdir(parents=True, exist_ok=True)
    date_str = today_str()
    json_path = json_dir / f"deep_dives_{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(deep_dives_payload, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved deep-dives JSON to: {json_path}")

    # 9) Build HTML report
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

    # 11) Send email (best effort)
    print("Sending report via email...")
    try:
        send_report_email(
            pdf_path=str(pdf_path),
            date_str=date_str,
            html_path=str(html_path),
        )
        print("[EMAIL] Email step completed (check SMTP / mailbox).")
    except Exception as e:
        print("[EMAIL] Unhandled error while sending email:", repr(e))
        print("[EMAIL] Continuing anyway – report generation completed.")

    # 12) Send PDF to Telegram bot (best effort)
    print("Sending report PDF to Telegram...")
    try:
        send_telegram_pdf(
            pdf_path=str(pdf_path),
            date_str=date_str,
        )
        print("[TELEGRAM] Telegram step completed (check bot/chat).")
    except Exception as e:
        print("[TELEGRAM] Unhandled error while sending PDF:", repr(e))
        print("[TELEGRAM] Continuing – report generation already completed.")

    print("Process completed.")


if __name__ == "__main__":
    main()
