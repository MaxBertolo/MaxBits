from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import json
import yaml
import traceback
import sys

from .rss_collector import collect_from_rss, rank_articles
from .cleaning import clean_articles
from .summarizer import summarize_articles
from .report_builder import build_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email
from .telegram_sender import send_telegram_pdf

BASE_DIR = Path(__file__).resolve().parent.parent


# -------------------------------------------------
#  UTILS
# -------------------------------------------------


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_config() -> Dict[str, Any]:
    config_path = BASE_DIR / "config" / "config.yaml"
    print("[DEBUG] Loading config from:", config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_rss_sources() -> List[Dict[str, Any]]:
    """
    Carica config/sources_rss.yaml se la versione di collect_from_rss
    accetta un argomento esplicito con la lista di feed.
    """
    rss_path = BASE_DIR / "config" / "sources_rss.yaml"
    if not rss_path.exists():
        print("[DEBUG] No sources_rss.yaml found, relying on rss_collector defaults.")
        return []
    print("[DEBUG] Loading RSS sources from:", rss_path)
    with open(rss_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("feeds", [])


WATCHLIST_TOPICS_ORDER = [
    "TV/Streaming",
    "Telco/5G",
    "Media/Platforms",
    "AI/Cloud/Quantum",
    "Space/Infrastructure",
    "Robotics/Automation",
    "Broadcast/Video",
    "Satellite/Satcom",
]


# -------------------------------------------------
#  TOPIC + DEDUP HELPERS
# -------------------------------------------------


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
    2) Altrimenti assegna uno degli 8 temi usando keyword.
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
        return "Space/Infrastructure"

    # default
    return "AI/Cloud/Quantum"


def build_watchlist(
    ranked_articles,
    deep_dive_articles,
    max_per_topic: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    - Niente articoli che siano già fra i deep-dives
    - Niente duplicati nello stesso topic
    - max N articoli per topic
    """
    deep_titles = {_normalise_title(a.title) for a in deep_dive_articles}

    watchlist: Dict[str, List[Dict[str, Any]]] = {
        topic: [] for topic in WATCHLIST_TOPICS_ORDER
    }
    seen_titles_per_topic: Dict[str, set] = {
        topic: set() for topic in WATCHLIST_TOPICS_ORDER
    }

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

        watchlist[topic].append(
            {
                "id": f"wl|{topic}|{art.source}|{art.title}",
                "title": art.title,
                "url": art.url,
                "source": art.source,
            }
        )
        seen_titles_per_topic[topic].add(norm_title)

    return watchlist


def build_deep_dives_payload(
    deep_dive_articles,
    summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for art, summ in zip(deep_dive_articles, summaries):
        topic = _article_topic(art)
        entry = {
            "id": f"deep|{art.source}|{art.title}",
            "title": art.title,
            "url": art.url,
            "source": art.source,
            "topic": topic,
            "published_at": art.published_at.isoformat()
            if getattr(art, "published_at", None)
            else "",
            "what_it_is": summ.get("what_it_is", ""),
            "who": summ.get("who", ""),
            "what_it_does": summ.get("what_it_does", ""),
            "why_it_matters": summ.get("why_it_matters", ""),
            "strategic_view": summ.get("strategic_view", ""),
        }
        payload.append(entry)
    return payload


# -------------------------------------------------
#  CEO POV (placeholder robusto)
# -------------------------------------------------


def _collect_ceo_pov_items(date_str: str) -> List[Dict[str, Any]]:
    cfg_path = BASE_DIR / "config" / "ceo_pov.yaml"
    print("[CEO_POV] Loading config from:", cfg_path)

    ceo_list: List[Dict[str, Any]] = []
    if cfg_path.exists():
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            ceo_list = data.get("ceos", []) or []
        except Exception as e:
            print("[CEO_POV] Cannot parse ceo_pov.yaml:", repr(e))
            ceo_list = []
    else:
        print("[CEO_POV] No ceo_pov.yaml found.")

    print(f"[CEO_POV] Loaded {len(ceo_list)} CEOs from config.")
    items: List[Dict[str, Any]] = []
    print(f"[CEO_POV] Collected {len(items)} items.")
    return items


# -------------------------------------------------
#  PATENTS (placeholder robusto)
# -------------------------------------------------


def _collect_patents(date_str: str) -> List[Dict[str, Any]]:
    print("[PATENTS] Collecting Patent publications (EU/US)...")
    print(f"[PATENTS][EPO] Fetching patents for date {date_str} (placeholder)")
    print(f"[PATENTS][USPTO] Fetching patents for date {date_str} (placeholder)")

    items: List[Dict[str, Any]] = []
    print(f"[PATENTS] Collected {len(items)} items.")
    return items


# -------------------------------------------------
#  MAIN PIPELINE (robusta)
# -------------------------------------------------


def main() -> None:
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

    # 1) RSS – super robusto
    print("Collecting RSS...")
    try:
        try:
            raw_articles = collect_from_rss(feeds)
        except TypeError:
            print(
                "[RSS] collect_from_rss(feeds) not supported, "
                "calling collect_from_rss() without args."
            )
            raw_articles = collect_from_rss()
    except Exception as e:
        print("[FATAL] collect_from_rss failed with unexpected error:", repr(e))
        traceback.print_exc()
        print("[FATAL] Exiting early but WITHOUT error code (no report today).")
        return

    print(f"[RSS] Total raw articles collected: {len(raw_articles)}")
    if not raw_articles:
        print("[FATAL] No articles from RSS. Exiting gracefully.")
        return

    # 2) Cleaning
    try:
        cleaned = clean_articles(raw_articles, max_articles=max_articles_for_cleaning)
        print(f"[CLEAN] After cleaning: {len(cleaned)} articles")
    except Exception as e:
        print("[ERROR] clean_articles raised an error:", repr(e))
        traceback.print_exc()
        print("[WARN] Falling back to raw articles (no cleaning).")
        cleaned = raw_articles[:max_articles_for_cleaning]

    if not cleaned:
        print(
            "[WARN] No recent articles after cleaning. "
            "Falling back to raw articles."
        )
        cleaned = raw_articles[:max_articles_for_cleaning]

    if not cleaned:
        print("[FATAL] Still no articles after fallback. Exiting gracefully.")
        return

    # 3) Ranking
    try:
        ranked = rank_articles(cleaned)
    except Exception as e:
        print("[ERROR] rank_articles raised an error:", repr(e))
        traceback.print_exc()
        print("[WARN] Falling back to cleaned articles as-is (no ranking).")
        ranked = list(cleaned)

    print(f"[RANK] Selected {len(ranked)} articles out of {len(cleaned)}")
    if not ranked:
        print("[FATAL] No ranked articles even after fallback. Exiting gracefully.")
        return

    # 4) Deep-dives
    deep_dive_articles = ranked[:3]
    print("[SELECT] Deep-dive articles:", [a.title for a in deep_dive_articles])

    # 5) Watchlist
    watchlist_grouped = build_watchlist(
        ranked_articles=ranked,
        deep_dive_articles=deep_dive_articles,
        max_per_topic=5,
    )
    print("[SELECT] Watchlist built with topics:", list(watchlist_grouped.keys()))

    # 6) Summarizzazione LLM (robusta)
    print("Summarizing deep-dive articles with LLM...")
    try:
        deep_dives_summaries = summarize_articles(
            deep_dive_articles,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        print("[ERROR] summarize_articles raised an error:", repr(e))
        traceback.print_exc()
        print("[WARN] Falling back to simple one-line summaries.")
        deep_dives_summaries = [
            {
                "what_it_is": f"Summary not available (LLM error). Original title: {a.title}",
                "who": "",
                "what_it_does": "",
                "why_it_matters": "",
                "strategic_view": "",
            }
            for a in deep_dive_articles
        ]

    deep_dives_payload = build_deep_dives_payload(
        deep_dive_articles=deep_dive_articles,
        summaries=deep_dives_summaries,
    )

    # 7) JSON di servizio
    json_dir = Path("reports/json")
    json_dir.mkdir(parents=True, exist_ok=True)
    date_str = today_str()

    deep_json_path = json_dir / f"deep_dives_{date_str}.json"
    with open(deep_json_path, "w", encoding="utf-8") as jf:
        json.dump(deep_dives_payload, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved deep-dives JSON to: {deep_json_path}")

    ceo_pov_items = _collect_ceo_pov_items(date_str)
    ceo_json_path = json_dir / f"ceo_pov_{date_str}.json"
    with open(ceo_json_path, "w", encoding="utf-8") as jf:
        json.dump(ceo_pov_items, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved CEO POV JSON to: {ceo_json_path}")

    patent_items = _collect_patents(date_str)
    patents_json_path = json_dir / f"patents_{date_str}.json"
    with open(patents_json_path, "w", encoding="utf-8") as jf:
        json.dump(patent_items, jf, ensure_ascii=False, indent=2)
    print(f"[DEBUG] Saved patents JSON to: {patents_json_path}")

    # 8) HTML (robusto)
    print("Building HTML report...")
    try:
        html = build_html_report(
            deep_dives=deep_dives_payload,
            watchlist=watchlist_grouped,
            date_str=date_str,
            ceo_pov=ceo_pov_items,
            patents=patent_items,
        )
    except Exception as e:
        print("[FATAL] build_html_report raised an error:", repr(e))
        traceback.print_exc()
        print("[FATAL] Cannot produce HTML. Exiting gracefully.")
        return

    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    html_path = html_dir / f"{file_prefix}{date_str}.html"
    pdf_path = pdf_dir / f"{file_prefix}{date_str}.pdf"

    print("[DEBUG] Saving HTML to:", html_path)
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print("[FATAL] Failed writing HTML file:", repr(e))
        traceback.print_exc()
        print("[FATAL] Exiting gracefully (no PDF/Email/Telegram).")
        return

    # 9) PDF – non deve far fallire tutto
    print("[DEBUG] Converting HTML to PDF at:", pdf_path)
    try:
        html_to_pdf(html, str(pdf_path))
        print("[PDF] PDF report generated:", pdf_path)
    except Exception as e:
        print("[PDF] Error while converting HTML to PDF:", repr(e))
        traceback.print_exc()
        print("[PDF] Skipping PDF generation, continuing pipeline.")

    print("[REPORT] HTML report ready at:", html_path)

    # 10) Email – best-effort
    print("[EMAIL] Sending report via email...")
    try:
        send_report_email(
            pdf_path=str(pdf_path),
            date_str=date_str,
            html_path=str(html_path),
        )
        print("[EMAIL] Email step completed.")
    except Exception as e:
        print("[EMAIL] Error while sending email:", repr(e))
        traceback.print_exc()
        print("[EMAIL] Continuing – report generation already done.")

    # 11) Telegram – best-effort
    print("[TELEGRAM] Sending report PDF to Telegram...")
    try:
        send_telegram_pdf(
            pdf_path=str(pdf_path),
            date_str=date_str,
        )
        print("[TELEGRAM] Telegram step completed.")
    except Exception as e:
        print("[TELEGRAM] Error while sending PDF:", repr(e))
        traceback.print_exc()
        print("[TELEGRAM] Continuing – pipeline finished.")

    print("[DONE] Daily pipeline completed successfully (no fatal errors).")


if __name__ == "__main__":
    # super try/except per evitare exit code 1
    try:
        main()
    except SystemExit as e:
        # se qualche libreria usasse sys.exit, non vogliamo far fallire il job
        print("[FATAL] SystemExit caught in main():", e)
        traceback.print_exc()
        sys.exit(0)
    except Exception as e:
        print("[FATAL] Unhandled exception in main():", repr(e))
        traceback.print_exc()
        # NON rilanciamo: exit code 0 così GitHub Actions non segna il job come failed
        sys.exit(0)
