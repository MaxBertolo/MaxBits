from pathlib import Path
from datetime import datetime
import re
import yaml
from typing import Dict, List, Any

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email


# Root del repo (cartella padre di src/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Tutti i topic possibili che vogliamo gestire in watchlist
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
    """Restituisce la data di oggi come stringa YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> Dict[str, Any]:
    """Carica config/config.yaml."""
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def load_rss_sources() -> List[Dict[str, Any]]:
    """Carica la lista dei feed da config/sources_rss.yaml."""
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["feeds"]


# ---------- HELPERS: NORMALIZZAZIONE TITOLI ----------

def _normalize_title(raw_title: str) -> str:
    """
    Normalizza il titolo per confrontarlo:
    - rimuove eventuali tag HTML
    - abbassa in minuscolo
    - comprime spazi
    """
    if not raw_title:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_title)  # togli tag HTML
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------- TOPIC ASSIGNMENT (feed-name + keywords) ----------

FEED_TOPIC_MAP: Dict[str, str] = {
    # --- AI / TECH NEWS ---
    "TechCrunch AI": "AI/Cloud/Quantum",
    "TechCrunch Mobility": "Telco/5G",
    "The Verge": "AI/Cloud/Quantum",
    "Ars Technica": "AI/Cloud/Quantum",
    "Wired – Tech": "AI/Cloud/Quantum",
    "Wired – Business": "Media/Platforms",
    "The Information": "Media/Platforms",

    # --- TELECOM / NETWORK / 5G / FIBER ---
    "Light Reading": "Telco/5G",
    "Fierce Telecom": "Telco/5G",
    "Telecoms.com": "Telco/5G",
    "Capacity Media": "Telco/5G",

    # --- MEDIA / TV / BROADCAST / SATELLITE ---
    "Advanced Television": "Broadcast/Video",
    "Broadband TV News": "TV/Streaming",
    "SatNews": "Satellite/Satcom",
    "Space News": "Space/Infra",

    # --- SOCIAL / ADVERTISING / DIGITAL MEDIA ---
    "Social Media Today": "Media/Platforms",
    "Marketing Dive": "Media/Platforms",
    "AdWeek": "Media/Platforms",

    # --- DATA CENTER / CLOUD / CYBER ---
    "Data Center Knowledge": "AI/Cloud/Quantum",
    "Data Center Dynamics": "AI/Cloud/Quantum",
    "CyberSecurity News": "AI/Cloud/Quantum",

    # --- ROBOTICS ---
    "Robotics 24/7": "Robotics/Automation",
    "IEEE Spectrum": "Robotics/Automation",

    # --- ANALYTICS / DEEPTECH ---
    "MIT Technology Review": "AI/Cloud/Quantum",
    "VentureBeat": "AI/Cloud/Quantum",
}

TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "TV/Streaming": [
        "streaming", "vod", "svod", "avod", "netflix", "disney+", "disney plus",
        "prime video", "hulu", "skyshowtime", "iptv",
    ],
    "Telco/5G": [
        "5g", "6g", "fiber", "fibre", "broadband", "spectrum", "telco",
        "mobile network", "mobile operator", "mno", "ftth", "fttx",
        "verizon", "at&t", "vodafone", "tim", "bt", "orange",
    ],
    "Media/Platforms": [
        "platform", "social", "social media", "meta", "facebook", "instagram",
        "tiktok", "snap", "snapchat", "youtube", "creator", "influencer",
        "advertising", "adtech", "ad tech",
    ],
    "AI/Cloud/Quantum": [
        "ai", "artificial intelligence", "gen ai", "llm", "machine learning",
        "deep learning", "inference", "datacenter", "data center", "cloud",
        "aws", "azure", "google cloud", "gcp", "nvidia", "openai", "model",
        "foundation model", "quantum",
    ],
    "Space/Infra": [
        "space", "launch", "payload", "rocket", "booster", "spacex", "nasa",
    ],
    "Robotics/Automation": [
        "robot", "robotics", "autonomous", "automation", "drone", "cobot",
    ],
    "Broadcast/Video": [
        "broadcast", "video tech", "video technology", "encoding", "ott",
        "video processing", "mpeg", "dvb", "atsc",
    ],
    "Satellite/Satcom": [
        "satellite", "satcom", "orbital", "orbit", "leo", "meo", "geo",
        "satellite launch", "ground station",
    ],
}


def _assign_topic_by_source(source: str) -> str | None:
    """Prova a derivare il topic in base al nome del feed."""
    src = (source or "").lower()
    for key, topic in FEED_TOPIC_MAP.items():
        if key.lower() in src:
            return topic
    return None


def _assign_topic_by_keywords(title: str, content: str, source: str) -> str:
    """
    Fallback: cerca keyword nel titolo + contenuto + sorgente.
    Se nessuna matcha, ritorna AI/Cloud/Quantum come default.
    """
    text = f"{title} {content} {source}".lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return topic
    return "AI/Cloud/Quantum"


def assign_topic(article) -> str:
    """
    Funzione unica per assegnare il topic a un articolo.
    1) prova via nome feed (FEED_TOPIC_MAP)
    2) se non trova, usa keyword sul testo
    """
    source = getattr(article, "source", "") or ""
    title = getattr(article, "title", "") or ""
    content = getattr(article, "content", "") or ""

    topic = _assign_topic_by_source(source)
    if topic:
        return topic

    return _assign_topic_by_keywords(title, content, source)


# ---------- WATCHLIST BUILDING (no dup + min 1 per topic) ----------

def build_watchlist_by_topic(
    candidates,
    max_per_topic: int = 5,
    min_per_topic: int = 1,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Crea la watchlist per topic.

    - dedup globale per titolo normalizzato
    - non include i deep-dives (che sono già stati rimossi dai candidates)
    - prova a garantire almeno `min_per_topic` articoli per topic,
      se esiste almeno un candidato per quel topic.

    Ritorna un dict: topic_key -> lista di {title, url, source}
    """
    grouped: Dict[str, List[Dict[str, str]]] = {topic: [] for topic in TOPIC_KEYS}
    seen_titles = set()  # normalizzati, per dedup globale

    # Primo pass: riempi bucket fino a max_per_topic
    for art in candidates:
        title = getattr(art, "title", "") or ""
        norm_title = _normalize_title(title)
        if not norm_title:
            continue

        if norm_title in seen_titles:
            continue

        topic = getattr(art, "topic", None) or assign_topic(art)
        if topic not in grouped:
            continue

        bucket = grouped[topic]
        if len(bucket) >= max_per_topic:
            continue

        bucket.append(
            {
                "title": title,
                "url": getattr(art, "url", "") or "",
                "source": getattr(art, "source", "") or "",
            }
        )
        seen_titles.add(norm_title)

    # Secondo pass: prova a garantire almeno 1 per topic,
    # usando SEMPRE i candidates (tutto il pool passato).
    for topic in TOPIC_KEYS:
        if len(grouped[topic]) >= min_per_topic:
            continue

        for art in candidates:
            art_topic = getattr(art, "topic", None) or assign_topic(art)
            if art_topic != topic:
                continue

            title = getattr(art, "title", "") or ""
            norm_title = _normalize_title(title)
            if not norm_title or norm_title in seen_titles:
                continue

            grouped[topic].append(
                {
                    "title": title,
                    "url": getattr(art, "url", "") or "",
                    "source": getattr(art, "source", "") or "",
                }
            )
            seen_titles.add(norm_title)
            break  # basta 1 per soddisfare il minimo

    print("[SELECT] Watchlist built with topics:", {k: len(v) for k, v in grouped.items()})
    return grouped


def select_deep_dives_and_watchlist(
    ranked,
    cleaned,
    deep_dives_count: int = 3,
    max_watchlist_per_topic: int = 5,
) -> tuple[list, Dict[str, List[Dict[str, str]]]]:
    """
    - Deep-dives: primi N articoli da 'ranked'
    - Watchlist: usa TUTTI gli articoli 'cleaned' (più ampio del solo ranked)
                 meno i deep-dives, per avere più copertura per topic.
    """
    if not ranked or not cleaned:
        return [], {}

    # Assicura che tutti i cleaned abbiano un topic
    for art in cleaned:
        setattr(art, "topic", assign_topic(art))

    # Deep-dives = primi N del ranked
    deep_dives: List[Any] = []
    for art in ranked:
        if len(deep_dives) >= deep_dives_count:
            break
        deep_dives.append(art)

    deep_norm_titles = {_normalize_title(a.title) for a in deep_dives}

    # Candidati watchlist = tutti i cleaned esclusi i deep-dives (per titolo)
    watch_candidates = []
    for art in cleaned:
        norm_title = _normalize_title(getattr(art, "title", "") or "")
        if norm_title in deep_norm_titles:
            continue
        watch_candidates.append(art)

    # Costruisci watchlist con dedup + min_per_topic
    watchlist_by_topic = build_watchlist_by_topic(
        watch_candidates,
        max_per_topic=max_watchlist_per_topic,
        min_per_topic=1,
    )

    return deep_dives, watchlist_by_topic


# ---------- NORMALIZZAZIONE DELLE DEEP-DIVES (no sezioni vuote) ----------

DEEP_DIVE_FIELDS = [
    "what_it_is",
    "who",
    "what_it_does",
    "why_it_matters",
    "strategic_view",
]


def _ensure_deep_dive_sections(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Garantisce che ogni deep-dive abbia tutte le sezioni valorizzate.
    """
    out = dict(entry) if entry is not None else {}

    title = out.get("title_clean") or out.get("title") or "this article"
    topic = out.get("topic") or "General"

    fallbacks = {
        "what_it_is": f"A news or analysis piece about {title}.",
        "who": "Key players include the companies, vendors and stakeholders mentioned in the article.",
        "what_it_does": "It describes concrete actions, launches, deployments or technology moves that impact the market.",
        "why_it_matters": "This matters for Telco/Media/Tech decision-makers because it highlights a tangible technology or market shift that could influence strategy, investments or competitive positioning.",
        "strategic_view": f"Monitor how this story evolves over the next 6–18 months and assess implications for your roadmap, partnerships and {topic.lower()} investments.",
    }

    for field in DEEP_DIVE_FIELDS:
        value = (out.get(field) or "").strip()
        if not value:
            out[field] = fallbacks[field]

    if "topic" not in out or not out["topic"]:
        out["topic"] = topic

    return out


def _normalize_deep_dives(summaries: List[Dict[str, Any]], deep_articles) -> List[Dict[str, Any]]:
    """
    Allinea titolo/source/url/topic dalle deep-dives originali
    e garantisce che tutte le sezioni siano compilate.
    """
    normalized: List[Dict[str, Any]] = []

    for idx, s in enumerate(summaries or []):
        base = dict(s) if s is not None else {}

        if idx < len(deep_articles):
            art = deep_articles[idx]
            base.setdefault("title", getattr(art, "title", "") or "")
            base.setdefault("title_clean", getattr(art, "title", "") or "")
            base.setdefault("url", getattr(art, "url", "") or "")
            base.setdefault("source", getattr(art, "source", "") or "")
            base.setdefault("topic", getattr(art, "topic", "") or "General")

        normalized.append(_ensure_deep_dive_sections(base))

    return normalized


# ------------------------ MAIN ------------------------


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
    language = llm_cfg.get("language", "en")  # pronto per estensioni future

    # 2) Raccolta RSS
    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"[RSS] Total raw articles collected: {len(raw_articles)}")

    if not raw_articles:
        print("No articles collected from RSS. Exiting.")
        return

    # 3) Cleaning (es. ultime 24h, dedup base per URL, ecc.)
    cleaned = clean_articles(raw_articles, max_articles=max_articles_for_cleaning)
    print(f"After cleaning: {len(cleaned)} articles")

    if not cleaned:
        print("No recent articles after cleaning. Exiting.")
        return

    # 4) Ranking globale (per scegliere le 3 deep-dives)
    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")

    # 5) Selezione 3 deep-dives + watchlist per topic (NO duplicati)
    deep_articles, watchlist_grouped = select_deep_dives_and_watchlist(
        ranked=ranked,
        cleaned=cleaned,
        deep_dives_count=3,
        max_watchlist_per_topic=5,
    )

    print(f"[SELECT] Deep-dives: {len(deep_articles)}")
    print(f"[SELECT] Watchlist topics: {list(watchlist_grouped.keys())}")

    if not deep_articles:
        print("No deep-dive candidates. Exiting.")
        return

    # 6) Summarization con LLM (solo per i 3 deep-dives)
    print("Summarizing deep-dive articles with LLM...")
    summaries = summarize_articles(
        deep_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Normalizza le deep-dives per avere sempre tutte le sezioni compilate
    summaries = _normalize_deep_dives(summaries, deep_articles)

    # 7) Costruzione HTML
    print("Building HTML report...")
    date_str = today_str()
    html = build_html_report(
        deep_dives=summaries,
        watchlist=watchlist_grouped,
        date_str=date_str,
    )

    # 8) Salvataggio HTML + PDF
    output_cfg = cfg.get("output", {})
    html_dir = Path(output_cfg.get("html_dir", "reports/html"))
    pdf_dir = Path(output_cfg.get("pdf_dir", "reports/pdf"))
    prefix = output_cfg.get("file_prefix", "report_")

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

    # 9) Invio email (NON fa fallire il job se qualcosa va storto)
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
