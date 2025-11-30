from pathlib import Path
from datetime import datetime
import re
import yaml

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


# ---------- HELPERS PER DEDUPLICA / WATCHLIST ----------

def _normalize_title(raw_title: str) -> str:
    """
    Normalizza il titolo per confrontarlo:
    - rimuove eventuali tag HTML
    - abbassa in minuscolo
    - comprime spazi
    """
    if not raw_title:
        return ""
    # togli tag HTML tipo <a> ecc
    text = re.sub(r"<[^>]+>", "", raw_title)
    # minuscolo
    text = text.lower()
    # spazio singolo
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_watchlist_by_topic(candidates, max_per_topic: int = 5):
    """
    Crea la watchlist per topic, SENZA duplicati di titolo
    e SENZA includere i deep-dive (che sono già stati rimossi dai candidates).

    Ritorna un dict: topic -> lista di {title, url, source}
    """

    # struttura base
    grouped = {topic: [] for topic in TOPIC_KEYS}
    seen_titles = set()  # normalizzati, per dedup globale

    for art in candidates:
        norm_title = _normalize_title(art.title)

        # 1) Niente duplicati di titolo, anche se cambia URL
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)

        # 2) Topic dell'articolo (assegnato in rss_collector a partire dal feed)
        topic = getattr(art, "topic", None) or "AI/Cloud/Quantum"
        if topic not in grouped:
            # se arriva un topic "strano" lo scartiamo dalla watchlist
            continue

        # 3) Rispetta il massimo per topic
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

    # Rimuoviamo i topic vuoti: il report_builder mostrerà solo quelli presenti
    grouped_non_empty = {k: v for k, v in grouped.items() if v}
    print("[SELECT] Watchlist built with topics:", list(grouped_non_empty.keys()))
    return grouped_non_empty


def select_deep_dives_and_watchlist(articles, deep_dives_count: int = 3, max_watchlist_per_topic: int = 5):
    """
    - Prende i primi N articoli come deep-dives (già ordinati da rank_articles).
    - Usa TUTTI gli altri come candidati per la watchlist.
    - Deduplica per titolo e NON rimette i deep-dives in watchlist.
    """
    if not articles:
        return [], {}

    # 1) Deep-dives
    deep_dives = articles[:deep_dives_count]
    deep_norm_titles = {_normalize_title(a.title) for a in deep_dives}

    # 2) Candidati watchlist = tutti gli altri articoli,
    #    escludendo qualsiasi cosa che abbia lo stesso titolo dei deep-dives
    watch_candidates = []
    for art in articles[deep_dives_count:]:
        norm_title = _normalize_title(art.title)
        if norm_title in deep_norm_titles:
            # non rimettiamo i deep-dive in watchlist
            continue
        watch_candidates.append(art)

    # 3) Costruisce watchlist per topic con dedup
    watchlist_by_topic = build_watchlist_by_topic(
        watch_candidates,
        max_per_topic=max_watchlist_per_topic,
    )

    return deep_dives, watchlist_by_topic


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
    language = llm_cfg.get("language", "en")

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

    # 4) Ranking globale
    ranked = rank_articles(cleaned)
    print(f"[RANK] Selected top {len(ranked)} articles out of {len(cleaned)}")

    # 5) Selezione 3 deep-dives + watchlist per topic (NO duplicati)
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

    # 6) Summarization con LLM (solo per i 3 deep-dives)
    print("Summarizing deep-dive articles with LLM...")
    summaries = summarize_articles(
        deep_articles,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

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
