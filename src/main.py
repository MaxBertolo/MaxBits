from pathlib import Path
from datetime import datetime
import re
from typing import Dict, List, Any
import yaml

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .telegram_sender import send_telegram_pdf


# =========================================================
# ROOT DEL PROGETTO
# =========================================================

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


# =========================================================
# CONFIGURATION LOADERS
# =========================================================

def load_config() -> Dict[str, Any]:
    path = BASE_DIR / "config" / "config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_rss_sources() -> List[Dict[str, str]]:
    path = BASE_DIR / "config" / "sources_rss.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["feeds"]


# =========================================================
# TITLE CLEANING + NORMALIZATION
# =========================================================

def _strip_html_tags(text: str) -> str:
    """Rimuove *qualunque* tag HTML da un titolo."""
    if not text:
        return ""
    x = re.sub(r"<[^>]+>", "", text)
    x = re.sub(r"\s+", " ", x)
    return x.strip()


def _normalize_title(text: str) -> str:
    """Usato per dedup e matching."""
    if not text:
        return ""
    text = _strip_html_tags(text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================================================
# TOPIC ASSIGNMENT (feed → keywords → fallback)
# =========================================================

FEED_TOPIC_MAP = {
    "TechCrunch AI": "AI/Cloud/Quantum",
    "TechCrunch Mobility": "Telco/5G",
    "The Verge": "AI/Cloud/Quantum",
    "Ars Technica": "AI/Cloud/Quantum",
    "Wired – Tech": "AI/Cloud/Quantum",
    "Wired – Business": "Media/Platforms",
    "The Information": "Media/Platforms",
    "Light Reading": "Telco/5G",
    "Fierce Telecom": "Telco/5G",
    "Telecoms.com": "Telco/5G",
    "Capacity Media": "Telco/5G",
    "Advanced Television": "Broadcast/Video",
    "Broadband TV News": "TV/Streaming",
    "SatNews": "Satellite/Satcom",
    "Space News": "Space/Infra",
    "Social Media Today": "Media/Platforms",
    "Marketing Dive": "Media/Platforms",
    "AdWeek": "Media/Platforms",
    "Data Center Knowledge": "AI/Cloud/Quantum",
    "Data Center Dynamics": "AI/Cloud/Quantum",
    "CyberSecurity News": "AI/Cloud/Quantum",
    "Robotics 24/7": "Robotics/Automation",
    "IEEE Spectrum": "Robotics/Automation",
    "MIT Technology Review": "AI/Cloud/Quantum",
    "VentureBeat": "AI/Cloud/Quantum",
}

TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "TV/Streaming": ["streaming", "vod", "svod", "hulu", "netflix", "iptv"],
    "Telco/5G": ["5g", "6g", "fiber", "ftth", "mno", "operator", "broadband"],
    "Media/Platforms": ["social", "platform", "instagram", "tiktok", "advertising"],
    "AI/Cloud/Quantum": ["ai", "gen ai", "llm", "inference", "cloud", "nvidia"],
    "Space/Infra": ["space", "launch", "orbit", "payload"],
    "Robotics/Automation": ["robot", "autonomous", "automation", "drone"],
    "Broadcast/Video": ["broadcast", "ott", "encoding"],
    "Satellite/Satcom": ["satellite", "satcom", "leo", "meo", "geo"],
}


def assign_topic(article) -> str:
    source = getattr(article, "source", "").lower()
    title = getattr(article, "title", "")
    content = getattr(article, "content", "")

    # 1) feed-based
    for k, topic in FEED_TOPIC_MAP.items():
        if k.lower() in source:
            return topic

    # 2) keyword-based
    text = f"{title} {content}".lower()
    for topic, kws in TOPIC_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return topic

    # 3) fallback
    return "AI/Cloud/Quantum"


# =========================================================
# WATCHLIST (dedup intelligente, min 1 per topic)
# =========================================================

def build_watchlist_by_topic(candidates, max_per_topic=5, min_per_topic=1):
    grouped = {t: [] for t in TOPIC_KEYS}
    seen = set()

    # FIRST PASS — riempi fino a max_per_topic
    for art in candidates:
        raw = getattr(art, "title", "")
        title = _strip_html_tags(raw)
        if not title:
            continue

        norm = _normalize_title(title)
        if norm in seen:
            continue

        topic = getattr(art, "topic", None) or assign_topic(art)
        if topic not in grouped:
            continue

        if len(grouped[topic]) < max_per_topic:
            grouped[topic].append({
                "title": title,
                "url": getattr(art, "url", ""),
                "source": getattr(art, "source", "")
            })
            seen.add(norm)

    # SECOND PASS — garantire almeno 1 item
    for topic in TOPIC_KEYS:
        if len(grouped[topic]) >= min_per_topic:
            continue

        for art in candidates:
            if assign_topic(art) != topic:
                continue

            raw = getattr(art, "title", "")
            title = _strip_html_tags(raw)
            if not title:
                continue

            norm = _normalize_title(title)
            if norm in seen:
                continue

            grouped[topic].append({
                "title": title,
                "url": getattr(art, "url", ""),
                "source": getattr(art, "source", "")
            })
            seen.add(norm)
            break

    return grouped


# =========================================================
# DEEP-DIVE NORMALIZATION
# =========================================================

DEEP_FIELDS = [
    "what_it_is",
    "who",
    "what_it_does",
    "why_it_matters",
    "strategic_view",
]


def _ensure_deep_fields(entry: Dict[str, Any]):
    """Fallback testuale per deep-dive mancanti."""
    title = entry.get("title") or "This article"
    topic = entry.get("topic", "General")

    fallback = {
        "what_it_is": f"Overview of {title}.",
        "who": "Key stakeholders mentioned in the article.",
        "what_it_does": "Describes relevant actions, launches or decisions.",
        "why_it_matters": "Explains impact for Telco/Media/AI decision-makers.",
        "strategic_view": f"Track how this evolves across {topic}.",
    }

    for f in DEEP_FIELDS:
        if not entry.get(f):
            entry[f] = fallback[f]

    return entry


def normalize_deep_dives(summaries, deep_articles):
    out = []
    for i, s in enumerate(summaries):
        d = dict(s)
        art = deep_articles[i]

        d.setdefault("title", art.title)
        d.setdefault("title_clean", art.title)
        d.setdefault("url", art.url)
        d.setdefault("source", art.source)
        d.setdefault("topic", art.topic)

        d = _ensure_deep_fields(d)

        out.append(d)
    return out


# =========================================================
# MAIN PIPELINE
# =========================================================

def main():
    print("[INIT] Loading configuration...")
    cfg = load_config()
    feeds = load_rss_sources()

    max_articles = cfg.get("max_articles_per_day", 50)
    model_cfg = cfg["llm"]

    # =====================================================
    # 1) RSS COLLECTION
    # =====================================================
    print("[RSS] Collecting...")
    raw_articles = collect_from_rss(feeds)

    cleaned = clean_articles(raw_articles, max_articles=max_articles)
    ranked = rank_articles(cleaned)

    # Assign topics
    for art in cleaned:
        setattr(art, "topic", assign_topic(art))

    # =====================================================
    # 2) Deep-dives + Watchlist
    # =====================================================
    deep_articles = ranked[:3]
    deep_titles = {_normalize_title(a.title) for a in deep_articles}

    watch_candidates = [a for a in cleaned if _normalize_title(a.title) not in deep_titles]
    watchlist = build_watchlist_by_topic(watch_candidates)

    # =====================================================
    # 3) Summaries
    # =====================================================
    print("[LLM] Summarizing deep-dives...")
    summaries = summarize_articles(
        deep_articles,
        model=model_cfg["model"],
        temperature=model_cfg["temperature"],
        max_tokens=model_cfg["max_tokens"],
    )

    deep_dives = normalize_deep_dives(summaries, deep_articles)

    # =====================================================
    # 4) HTML REPORT
    # =====================================================
    print("[BUILD] HTML...")
    date_str = today_str()
    html = build_html_report(
        deep_dives=deep_dives,
        watchlist=watchlist,
        date_str=date_str,
    )

    # =====================================================
    # 5) SAVE HTML + PDF
    # =====================================================
    out = cfg["output"]
    html_dir = Path(out["html_dir"])
    pdf_dir = Path(out["pdf_dir"])
    prefix = out["file_prefix"]

    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    html_path = html_dir / f"{prefix}{date_str}.html"
    pdf_path = pdf_dir / f"{prefix}{date_str}.pdf"

    html_path.write_text(html, encoding="utf-8")
    html_to_pdf(html, str(pdf_path))

    print(f"[DONE] HTML → {html_path}")
    print(f"[DONE] PDF  → {pdf_path}")

    # =====================================================
    # 6) TELEGRAM DELIVERY
    # =====================================================
    print("[TG] Sending PDF to Telegram...")
    send_telegram_pdf(str(pdf_path), date_str)

    print("[DONE] Process completed successfully.")


if __name__ == "__main__":
    main()
