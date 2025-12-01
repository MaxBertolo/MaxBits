from pathlib import Path
from datetime import datetime
import re
from typing import Dict, List, Any
import yaml

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from . import report_builder            # <— IMPORT CORRETTO
from .pdf_export import html_to_pdf
from .telegram_sender import send_telegram_pdf


# =========================
#  COSTANTI GLOBALI
# =========================

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


# =========================
#  FUNZIONI UTILI
# =========================

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> Dict[str, Any]:
    cfg_path = BASE_DIR / "config" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_rss_sources() -> List[Dict[str, Any]]:
    src = BASE_DIR / "config" / "sources_rss.yaml"
    with open(src, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["feeds"]


def _strip_html_tags(text: str) -> str:
    """Rimuove completamente tag HTML dai titoli."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def _normalize_title(text: str) -> str:
    """Titolo normalizzato per dedup."""
    if not text:
        return ""
    text = _strip_html_tags(text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================
# TOPIC ASSIGNMENT
# =========================

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

TOPIC_KEYWORDS = {
    "TV/Streaming": [
        "streaming", "vod", "svod", "hulu", "netflix", "prime video", "disney",
    ],
    "Telco/5G": [
        "5g", "6g", "fiber", "broadband", "spectrum", "network", "mobile operator"
    ],
    "Media/Platforms": [
        "social", "platform", "instagram", "tiktok", "facebook", "adtech", "creator",
    ],
    "AI/Cloud/Quantum": [
        "ai", "machine learning", "gen ai", "llm", "cloud", "nvidia", "gpt", "openai"
    ],
    "Space/Infra": [
        "space", "launch", "orbit", "payload"
    ],
    "Robotics/Automation": [
        "robot", "robotics", "autonomous", "drone"
    ],
    "Broadcast/Video": [
        "broadcast", "ott", "video tech", "encoding"
    ],
    "Satellite/Satcom": [
        "satellite", "satcom", "ground station", "orbit"
    ],
}


def assign_topic(article) -> str:
    """Assegna topic usando feed → keywords → default."""
    source = getattr(article, "source", "").lower()
    title = getattr(article, "title", "")
    content = getattr(article, "content", "")

    # 1) Mappa della fonte
    for key, topic in FEED_TOPIC_MAP.items():
        if key.lower() in source:
            return topic

    # 2) Keywords
    full = f"{title} {content} {source}".lower()
    for topic, keys in TOPIC_KEYWORDS.items():
        for k in keys:
            if k in full:
                return topic

    # 3) Default
    return "AI/Cloud/Quantum"


# =========================
# WATCHLIST
# =========================

def build_watchlist_by_topic(candidates, max_per_topic=5, min_per_topic=1):
    grouped = {k: [] for k in TOPIC_KEYS}
    seen = set()

    # Primo passaggio
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

    # Secondo passaggio: garantire almeno 1
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


# =========================
# DEEP-DIVE NORMALIZATION
# =========================

DEEP_FIELDS = [
    "what_it_is",
    "who",
    "what_it_does",
    "why_it_matters",
    "strategic_view",
]


def _ensure_deep_fields(d: Dict[str, Any]):
    """Garantisce che le 5 sezioni siano piene."""
    title = d.get("title_clean") or d.get("title") or "this article"
    topic = d.get("topic", "General")

    fallback = {
        "what_it_is": f"Overview of {title}.",
        "who": "Mentioned companies and stakeholders.",
        "what_it_does": "Describes actions, deployments or launches.",
        "why_it_matters": "Explains its relevance for the industry.",
        "strategic_view": f"Monitor evolution of this topic in {topic}.",
    }

    for f in DEEP_FIELDS:
        v = (d.get(f) or "").strip()
        if not v:
            d[f] = fallback[f]

    return d


def normalize_deep_dives(summaries, deep_articles):
    out = []
    for i, s in enumerate(summaries):
        base = dict(s)
        art = deep_articles[i]

        base.setdefault("title", getattr(art, "title", ""))
        base.setdefault("title_clean", getattr(art, "title", ""))
        base.setdefault("url", getattr(art, "url", ""))
        base.setdefault("source", getattr(art, "source", ""))
        base.setdefault("topic", getattr(art, "topic", ""))

        out.append(_ensure_deep_fields(base))

    return out


# =========================
# MAIN
# =========================

def main():
    print("[DEBUG] Loading config...")
    cfg = load_config()

    feeds = load_rss_sources()

    # PARAMETERS
    max_articles = int(cfg.get("max_articles_per_day", 50))
    llm = cfg["llm"]
    model = llm["model"]
    temperature = float(llm["temperature"])
    max_tokens = int(llm["max_tokens"])

    # 1) RSS
    print("Collecting RSS...")
    raw = collect_from_rss(feeds)

    cleaned = clean_articles(raw, max_articles=max_articles)
    ranked = rank_articles(cleaned)

    print(f"[DEBUG] Cleaned: {len(cleaned)} | Ranked: {len(ranked)}")

    # 2) Topic assignment
    for art in cleaned:
        setattr(art, "topic", assign_topic(art))

    # 3) Deep-dives + Watchlist
    deep_articles = ranked[:3]
    deep_norm = {_normalize_title(a.title) for a in deep_articles}

    candidates = [a for a in cleaned if _normalize_title(a.title) not in deep_norm]

    watchlist = build_watchlist_by_topic(candidates)

    # 4) Summaries LLM
    print("Summarizing deep dives...")
    summaries = summarize_articles(
        deep_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    deep_dives = normalize_deep_dives(summaries, deep_articles)

    # 5) Build HTML
    date_str = today_str()
    print("Building HTML...")
    html = report_builder.build_html_report(
        deep_dives=deep_dives,
        watchlist=watchlist,
        date_str=date_str,
    )

    # 6) Save HTML + PDF
    out_cfg = cfg["output"]
    html_dir = Path(out_cfg["html_dir"])
    pdf_dir = Path(out_cfg["pdf_dir"])
    prefix = out_cfg["file_prefix"]

    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    html_path = html_dir / f"{prefix}{date_str}.html"
    pdf_path = pdf_dir / f"{prefix}{date_str}.pdf"

    html_path.write_text(html, encoding="utf-8")
    html_to_pdf(html, str(pdf_path))

    print(f"[DONE] Report saved: {html_path}, {pdf_path}")

    # 7) Send to Telegram
    send_telegram_pdf(str(pdf_path), date_str)

    print("Process completed successfully.")


if __name__ == "__main__":
    main()
