from pathlib import Path
from datetime import datetime, timedelta
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

from .ceo_pov_collector import collect_ceo_pov
from .patent_collector import collect_patent_publications


BASE_DIR = Path(__file__).resolve().parent.parent


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> dict:
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_rss_sources() -> list:
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
    - Nessun articolo che sia già fra i deep-dives
    - Nessun titolo duplicato nello stesso topic
    - max N articoli per topic
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
    payload: List[Dict] = []
    for art, summ in zip(deep_dive_articles, summaries):
        topic = _article_topic(art)
        entry = {
            "id": f"deep|{art.source}|{art.title}",
            "title": art.title,  # titolo originale dell'articolo
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


# -------------------------
#   HISTORY FOR FRONTEND
# -------------------------

def build_history_payload(
    date_str: str,
    html_dir: Path,
    pdf_dir: Path,
    file_prefix: str,
    max_reports: int = 7,
) -> List[Dict]:
    """
    Costruisce lista degli ultimi report (oggi + fino a 6 giorni prima)
    che il front-end usa per riempire il box "Last 7 daily reports".

    I path sono RELATIVI alla cartella HTML dei report, quindi:
      - html: es. "report_2025-12-08.html"
      - pdf:  es. "../pdf/report_2025-12-08.pdf"
    """
    history: List[Dict] = []

    base_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Cerchiamo indietro fino a 30 giorni, ma ci fermiamo dopo max_reports trovati.
    for i in range(0, 30):
        day = base_date - timedelta(days=i)
        d_str = day.strftime("%Y-%m-%d")

        html_name = f"{file_prefix}{d_str}.html"
        pdf_name = f"{file_prefix}{d_str}.pdf"

        html_path = html_dir / html_name
        pdf_path = pdf_dir / pdf_name

        if i == 0:
            # giorno corrente: lo includiamo comunque
            html_rel = html_name
            pdf_rel = f"../pdf/{pdf_name}"
        else:
            # per i giorni passati includiamo solo se esiste l'HTML
            if not html_path.exists():
                continue
            html_rel = html_name
            pdf_rel = f"../pdf/{pdf_name}" if pdf_path.exists() else None

        history.append(
            {
                "date": d_str,
                "html": html_rel,
                "pdf": pdf_rel,
            }
        )

        if len(history) >= max_reports:
            break

    return history


# -----------
#   MAIN
# -----------

def main():
    cwd = Path.cwd()
    print("[DEBUG] CWD:", cwd)
    try:
        print("[DEBUG] Repo contents:", [p.name for p in cwd.iterdir()])
    except Exception as e:
        print("[DEBUG] Cannot list repo contents:", repr(e))

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

    # 1) RSS
    print("Collecting RSS...")
    raw_articles = collect_from_rss(feeds)
    print(f"[RSS] Total raw articles collected: {len(raw_articles)}")
    if not raw_articles:
        print("[FATAL] No articles collected from RSS. Exiting.")
        return

    # 2) Cleaning (finestra temporale, dedup, limite massimo)
    cleaned = clean_articles(raw_articles, max_articles=max_articles_for_cleaning)
    print(f"After cleaning: {len(cleaned)} articles")

    # ---- FALLBACK ROBUSTO ----
    if not cleaned:
        print(
            "[WARN] No recent articles after cleaning. "
            "Falling back to top raw articles (ignoring recency window)."
        )
        cleaned = raw_articles[:max_articles_for_cleaning]
        print(f"[WARN] Fallback: using {len(cleaned)} raw articles as cleaned set.")

    if not cleaned:
        print("[FATAL] Still no articles after fallback. Exiting.")
        return
    # ---------------------------

    # 3) Ranking globale
    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")
    if not ranked:
        print("[FATAL] No ranked articles. Exiting.")
        return

    # 4) Deep-dives (3 migliori)
    deep_dive_articles = ranked[:3]
    print("[SELECT] Deep-dive articles:", [a.title for a in deep_dive_articles])

    # 5) Watchlist per topic (3–5 articoli max per topic)
    watchlist_grouped = build_watchlist(
        ranked_articles=ranked,
        deep_dive_articles=deep_dive_articles,
        max_per_topic=5,
    )
    print("[SELECT] Watchlist built with topics:", list(watchlist_grouped.keys()))

    # 6) Summarization con LLM
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

    # 7) CEO POV + PATENT WATCH
    print("Collecting CEO POV items...")
    ceo_pov_items = collect_ceo_pov(
        articles=ranked,
        max_items=5,
    )
    print(f"[CEO_POV] Collected {len(ceo_pov_items)} items.")

    print("Collecting Patent publications (EU/US)...")
    date_str = today_str()
    patents_items = collect_patent_publications(
        today_date_str=date_str,
        max_items=20,
    )
    print(f"[PATENTS] Collected {len(patents_items)} items.")

    # 8) Salva JSON (deep-dives + CEO POV + PATENTS)
    json_dir = Path("reports/json")
    json_dir.mkdir(parents=True, exist_ok=True)

    deep_json_path = json_dir / f"deep_dives_{date_str}.json"
    with open(deep_json_path, "w", encoding="utf-8") as jf:
        json.dump(deep_dives_payload, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved deep-dives JSON to: {deep_json_path}")

    ceo_json_path = json_dir / f"ceo_pov_{date_str}.json"
    with open(ceo_json_path, "w", encoding="utf-8") as jf:
        json.dump(ceo_pov_items, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved CEO POV JSON to: {ceo_json_path}")

    patents_json_path = json_dir / f"patents_{date_str}.json"
    with open(patents_json_path, "w", encoding="utf-8") as jf:
        json.dump(patents_items, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved patents JSON to: {patents_json_path}")

    # 9) Costruisci payload storico per il box "Last 7 daily reports"
    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    history_payload = build_history_payload(
        date_str=date_str,
        html_dir=html_dir,
        pdf_dir=pdf_dir,
        file_prefix=file_prefix,
        max_reports=7,
    )

    # 10) HTML
    print("Building HTML report...")
    html = build_html_report(
        deep_dives=deep_dives_payload,
        watchlist=watchlist_grouped,
        date_str=date_str,
        ceo_pov=ceo_pov_items,
        patents=patents_items,
        history=history_payload,
    )

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

    # 12) Telegram (PDF al bot)
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
