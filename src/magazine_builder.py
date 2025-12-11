from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import List, Dict
from datetime import datetime, timedelta
import yaml
import json
import glob


BASE_DIR = Path(__file__).resolve().parent.parent

# Sorgente report (generati da main.py)
HTML_SRC_DIR = BASE_DIR / "reports" / "html"
PDF_SRC_DIR = BASE_DIR / "reports" / "pdf"

# Cartella pubblica per GitHub Pages
DOCS_DIR = BASE_DIR / "docs"
HTML_DST_DIR = DOCS_DIR / "reports" / "html"
PDF_DST_DIR = DOCS_DIR / "reports" / "pdf"

JSON_REPORTS_DIR = BASE_DIR / "reports" / "json"


# -------------------------------------------------------------------
#  REPORT DAILY (HTML/PDF)
# -------------------------------------------------------------------

def _find_reports() -> List[Dict]:
    """
    Cerca tutti i report HTML in reports/html, estrae la data dal nome file,
    e costruisce una lista ordinata per data (desc).
    """
    reports: List[Dict] = []
    if not HTML_SRC_DIR.exists():
        print(f"[MAG] HTML source dir not found: {HTML_SRC_DIR}")
        return reports

    pattern = re.compile(r"report_(\d{4}-\d{2}-\d{2})\.html$")

    for f in HTML_SRC_DIR.glob("report_*.html"):
        m = pattern.match(f.name)
        if not m:
            continue
        date_str = m.group(1)
        pdf_file = PDF_SRC_DIR / f"report_{date_str}.pdf"
        reports.append(
            {
                "date": date_str,
                "html_file": f,
                "pdf_file": pdf_file if pdf_file.exists() else None,
            }
        )

    reports.sort(key=lambda x: x["date"], reverse=True)
    print(f"[MAG] Found {len(reports)} reports in {HTML_SRC_DIR}")
    return reports


def _copy_last_reports_to_docs(reports: List[Dict], max_reports: int = 7) -> List[Dict]:
    """
    Copia gli ultimi max_reports report in docs/reports/html e docs/reports/pdf.

    Se il file sorgente e destinazione coincidono, non copia (evita SameFileError).

    Ritorna una lista riferita ai file di destinazione:
      { "date": "YYYY-MM-DD", "html_file": Path(...), "pdf_file": Path(...) or None }
    """
    HTML_DST_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DST_DIR.mkdir(parents=True, exist_ok=True)

    selected = reports[:max_reports]
    out: List[Dict] = []

    for r in selected:
        date = r["date"]
        src_html = r["html_file"]
        dst_html = HTML_DST_DIR / src_html.name

        try:
            if src_html.resolve() != dst_html.resolve():
                shutil.copy2(src_html, dst_html)
                print(f"[MAG] Copied HTML for {date} -> {dst_html}")
            else:
                print(f"[MAG] HTML for {date} already in docs/, skipping copy.")
        except Exception as e:
            print(f"[MAG][WARN] Cannot copy HTML for {date}: {e!r}")

        dst_pdf = None
        if r["pdf_file"] is not None:
            src_pdf = r["pdf_file"]
            dst_pdf = PDF_DST_DIR / src_pdf.name
            try:
                if src_pdf.resolve() != dst_pdf.resolve():
                    shutil.copy2(src_pdf, dst_pdf)
                    print(f"[MAG] Copied PDF for {date} -> {dst_pdf}")
                else:
                    print(f"[MAG] PDF for {date} already in docs/, skipping copy.")
            except Exception as e:
                print(f"[MAG][WARN] Cannot copy PDF for {date}: {e!r}")
                dst_pdf = None
        else:
            print(f"[MAG] No PDF for {date}, skipping PDF copy.")

        out.append(
            {
                "date": date,
                "html_file": dst_html,
                "pdf_file": dst_pdf,
            }
        )

    return out


def _build_previous_reports_list(reports_for_docs: List[Dict]) -> str:
    """
    HTML per la sidebar: link ai 6 giorni precedenti (salta il più recente).
    """
    if len(reports_for_docs) <= 1:
        return '<p style="font-size:12px; color:#6b7280;">No previous reports yet.</p>'

    items: List[str] = []

    for r in reports_for_docs[1:7]:  # max 6 giorni precedenti
        date = r["date"]
        html_rel = f"reports/html/{r['html_file'].name}"
        pdf_rel = f"reports/pdf/{r['pdf_file'].name}" if r["pdf_file"] else None

        if pdf_rel:
            links_html = (
                f'<a href="{html_rel}" target="_blank" rel="noopener">HTML</a>'
                f'<span class="dot">·</span>'
                f'<a href="{pdf_rel}" target="_blank" rel="noopener">PDF</a>'
            )
        else:
            links_html = f'<a href="{html_rel}" target="_blank" rel="noopener">HTML</a>'

        item = f"""
        <li class="side-report-item">
          <div class="side-report-main">
            <span class="side-report-date">{date}</span>
            <span class="side-report-links">{links_html}</span>
          </div>
        </li>"""
        items.append(item)

    return "\n".join(items)


# -------------------------------------------------------------------
#  EXTRA REPORTS (YAML + 30 giorni)
# -------------------------------------------------------------------

def _load_extra_reports() -> List[Dict]:
    """
    Legge config/extra_reports.yaml e restituisce solo i report con data
    negli ultimi 30 giorni.
    """
    cfg_path = BASE_DIR / "config" / "extra_reports.yaml"
    if not cfg_path.exists():
        print(f"[MAG] No extra_reports.yaml at {cfg_path}")
        return []

    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"[MAG] Cannot parse extra_reports.yaml: {e!r}")
        return []

    raw_list = data.get("extra_reports", []) or []
    if not isinstance(raw_list, list):
        print("[MAG] extra_reports.yaml: 'extra_reports' must be a list")
        return []

    today = datetime.utcnow().date()
    cutoff = today - timedelta(days=30)

    out: List[Dict] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        date_str = str(item.get("date") or "").strip()

        if not (title and url and date_str):
            continue

        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue

        if d < cutoff or d > today:
            continue

        age_days = (today - d).days
        days_left = max(0, 30 - age_days)

        out.append(
            {
                "title": title,
                "url": url,
                "date": date_str,
                "days_left": days_left,
            }
        )

    out.sort(key=lambda x: x["date"], reverse=True)
    print(f"[MAG] Loaded {len(out)} extra reports (<= 30 days)")
    return out


def _build_extra_reports_sidebar_html(extra_reports: List[Dict]) -> str:
    """
    HTML per la sezione "Extra reports (30 days)".
    """
    if not extra_reports:
        return '<p style="font-size:12px; color:#6b7280;">No extra reports (last 30 days).</p>'

    items: List[str] = []

    for rep in extra_reports:
        title = rep["title"]
        url = rep["url"]
        date_str = rep["date"]
        days_left = rep.get("days_left", 0)

        if days_left <= 0:
            pill = "expires today"
            pill_class = "expiring"
        elif days_left == 1:
            pill = "1 day left"
            pill_class = "expiring"
        else:
            pill = f"{days_left} days left"
            pill_class = "ok"

        item_html = f"""
        <li class="extra-report-item">
          <a href="{url}" target="_blank" rel="noopener" class="extra-report-link">{title}</a>
          <div class="extra-report-meta">
            <span class="extra-report-date">{date_str}</span>
            <span class="extra-report-pill extra-report-pill-{pill_class}">{pill}</span>
          </div>
        </li>
        """
        items.append(item_html)

    return "\n".join(items)


# -------------------------------------------------------------------
#  MARKET SNAPSHOT (static JSON, es. 10:00 e 20:00)
# -------------------------------------------------------------------

def _load_market_snapshot() -> Dict | None:
    """
    Cerca il market snapshot più recente in reports/json:

      market_snapshot_YYYY-MM-DD.json   oppure   market_snapshot_latest.json

    Formato atteso:
      {
        "updated_at": "2025-12-10 20:00 CET",
        "items": [
          {"name": "Google", "symbol": "GOOGL", "price": 142.35, "change_pct": 1.23},
          ...
        ]
      }
    """
    if not JSON_REPORTS_DIR.exists():
        return None

    # prima prova con pattern market_snapshot_*.json
    candidates = sorted(JSON_REPORTS_DIR.glob("market_snapshot_*.json"))
    target = None
    if candidates:
        target = candidates[-1]
    else:
        alt = JSON_REPORTS_DIR / "market_snapshot_latest.json"
        if alt.exists():
            target = alt

    if not target:
        print("[MAG] No market snapshot JSON found.")
        return None

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except Exception as e:
        print(f"[MAG] Cannot parse market snapshot {target}: {e!r}")
        return None


def _build_market_snapshot_html(snapshot: Dict | None) -> (str, str):
    """
    Ritorna (html_items, updated_label).
    """
    if not snapshot:
        html = """
        <li class="market-item">
          <div class="market-left">Google<span class="market-symbol">GOOGL</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        <li class="market-item">
          <div class="market-left">Tesla<span class="market-symbol">TSLA</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        <li class="market-item">
          <div class="market-left">Apple<span class="market-symbol">AAPL</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        <li class="market-item">
          <div class="market-left">NVIDIA<span class="market-symbol">NVDA</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        <li class="market-item">
          <div class="market-left">Meta<span class="market-symbol">META</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        <li class="market-item">
          <div class="market-left">Microsoft<span class="market-symbol">MSFT</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        <li class="market-item">
          <div class="market-left">Amazon<span class="market-symbol">AMZN</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        <li class="market-item">
          <div class="market-left">Bitcoin<span class="market-symbol">BTC</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        <li class="market-item">
          <div class="market-left">Ethereum<span class="market-symbol">ETH</span></div>
          <div><span class="market-price">—</span><span class="market-change"></span></div>
        </li>
        """
        return html, "not available"

    items = snapshot.get("items") or []
    updated_at = snapshot.get("updated_at", "n/a")

    # mantieni l'ordine fisso dei titoli principali se possibile
    desired_order = [
        "GOOGL", "TSLA", "AAPL", "NVDA", "META", "MSFT", "AMZN", "BTC", "ETH",
    ]
    lookup = {str(it.get("symbol")): it for it in items}

    ordered_items: List[Dict] = []
    for sym in desired_order:
        if sym in lookup:
            ordered_items.append(lookup[sym])

    html_items: List[str] = []
    for it in ordered_items:
        name = it.get("name", "")
        sym = it.get("symbol", "")
        price = it.get("price", None)
        pct = it.get("change_pct", None)

        if isinstance(price, (int, float)):
            price_str = f"{price:.2f}"
        else:
            price_str = "—"

        if isinstance(pct, (int, float)):
            if pct > 0:
                cls = "market-change up"
                pct_str = f"+{pct:.2f}%"
            elif pct < 0:
                cls = "market-change down"
                pct_str = f"{pct:.2f}%"
            else:
                cls = "market-change"
                pct_str = "0.00%"
        else:
            cls = "market-change"
            pct_str = ""
        html_items.append(
            f"""
        <li class="market-item">
          <div class="market-left">{name}<span class="market-symbol">{sym}</span></div>
          <div>
            <span class="market-price">{price_str}</span>
            <span class="{cls}">{pct_str}</span>
          </div>
        </li>
        """
        )

    return "\n".join(html_items), updated_at


# -------------------------------------------------------------------
#  INDEX.HTML TEMPLATE
# -------------------------------------------------------------------

def _build_index_content(reports_for_docs: List[Dict]) -> str:
    if not reports_for_docs:
        print("[MAG] No reports found, generating minimal placeholder index.")
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Daily Tech Intelligence</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body style="margin:0;padding:32px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7;color:#111827;">
  <div style="max-width:960px;margin:0 auto;">
    <h1 style="font-size:24px;margin-bottom:10px;">MaxBits Mag</h1>
    <p style="font-size:14px;color:#4b5563;">
      No reports available yet. Once the first daily report is generated, this page will show the latest report and the last days.
    </p>
  </div>
</body>
</html>
"""

    latest = reports_for_docs[0]
    latest_date = latest["date"]
    latest_html_rel = f"reports/html/{latest['html_file'].name}"
    previous_list_html = _build_previous_reports_list(reports_for_docs)
    extra_reports = _load_extra_reports()
    extra_reports_html = _build_extra_reports_sidebar_html(extra_reports)

    snapshot = _load_market_snapshot()
    market_html, market_updated = _build_market_snapshot_html(snapshot)

    template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MaxBits · Daily Tech Intelligence</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

  <style>
    :root {
      --bg: #f5f7fa;
      --card-bg: #ffffff;
      --accent: #25A7FF;
      --accent-dark: #006fd6;
      --text-main: #111111;
      --text-muted: #6b7280;
      --border: #e5e7eb;
      --radius-lg: 16px;
      --shadow-soft: 0 18px 40px rgba(15, 23, 42, 0.18);
    }

    body[data-theme="dark"] {
      --bg: #020617;
      --card-bg: #020617;
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
      --border: #1f2937;
      --shadow-soft: 0 18px 40px rgba(0, 0, 0, 0.8);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      padding: 0;
      background: radial-gradient(circle at top left, #e5f3ff, #f5f7fa);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      transition: background 0.35s ease, color 0.25s ease;
    }

    body[data-theme="dark"] {
      background: radial-gradient(circle at top left, #020617, #020617);
    }

    .page {
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px 16px 40px;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 8px 4px 22px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .brand-mark {
      background:#ffffff;
      padding:6px 12px;
      border-radius:999px;
      box-shadow:0 12px 30px rgba(15,23,42,0.18);
      font-weight:700;
      letter-spacing:0.06em;
      font-size:16px;
    }

    .brand-mark span:first-child { color:#111827; }
    .brand-mark span:last-child { color:#0ea5e9; }

    .brand-subtitle {
      margin:0;
      font-size:12px;
      color:var(--text-muted);
    }

    .header-controls {
      display:flex;
      flex-direction:column;
      align-items:flex-end;
      gap:6px;
    }

    .viewmode-pill {
      font-size:11px;
      text-transform:uppercase;
      letter-spacing:0.16em;
      padding:4px 10px;
      border-radius:999px;
      border:1px solid var(--border);
      color:var(--text-muted);
      background:rgba(255,255,255,0.9);
      cursor:pointer;
      display:inline-flex;
      align-items:center;
      gap:6px;
    }

    body[data-theme="dark"] .viewmode-pill {
      background:#020617;
    }

    .theme-toggle {
      width:36px;
      height:18px;
      padding:2px;
      border-radius:999px;
      border:1px solid var(--border);
      display:flex;
      align-items:center;
      background:rgba(255,255,255,0.85);
      cursor:pointer;
    }

    body[data-theme="dark"] .theme-toggle {
      background:#020617;
    }

    .theme-thumb {
      width:13px;
      height:13px;
      border-radius:999px;
      background:#020617;
      transform:translateX(0);
      transition:transform 0.22s ease, background 0.22s ease;
    }

    body[data-theme="dark"] .theme-thumb {
      transform:translateX(16px);
      background:#facc15;
    }

    .exit-btn {
      font-size:11px;
      padding:4px 10px;
      border-radius:999px;
      border:1px solid #ef4444;
      color:#b91c1c;
      background:rgba(254,242,242,0.95);
      cursor:pointer;
    }

    body[data-theme="dark"] .exit-btn {
      background:rgba(127,29,29,0.85);
      color:#fee2e2;
      border-color:#b91c1c;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 2.7fr) minmax(270px, 1fr);
      gap: 20px;
    }

    .main-card {
      background: radial-gradient(circle at top left, rgba(37,167,255,0.12), rgba(255,255,255,0.96));
      padding: 20px 20px 18px;
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-soft);
      border: 1px solid rgba(255,255,255,0.4);
      backdrop-filter: blur(10px);
    }

    body[data-theme="dark"] .main-card {
      background: radial-gradient(circle at top left, rgba(15,118,255,0.35), #020617);
      border-color: #1f2937;
    }

    .main-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 12px;
    }

    .main-title {
      margin: 0;
      font-size: 20px;
      letter-spacing: 0.02em;
    }

    .main-meta {
      margin: 3px 0 0;
      font-size: 12px;
      color: var(--text-muted);
    }

    .badge-today {
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(37,167,255,0.12);
      color: var(--accent-dark);
      border: 1px solid rgba(37,167,255,0.4);
      white-space: nowrap;
      cursor:pointer;
    }

    body[data-theme="dark"] .badge-today {
      background: rgba(37,167,255,0.15);
      color: #e0f2fe;
      border-color: rgba(59,130,246,0.6);
    }

    .iframe-wrapper {
      margin-top: 10px;
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid rgba(148,163,184,0.5);
      background: #ffffff;
    }

    body[data-theme="dark"] .iframe-wrapper {
      background: #020617;
      border-color: #1f2937;
    }

    .iframe-wrapper iframe {
      width: 100%;
      height: 78vh;
      border: none;
    }

    /* Sidebar */
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .side-card {
      background: var(--card-bg);
      border-radius: 14px;
      padding: 14px 14px 12px;
      border: 1px solid var(--border);
      box-shadow: 0 10px 26px rgba(15,23,42,0.08);
    }

    body[data-theme="dark"] .side-card {
      box-shadow: 0 16px 40px rgba(0,0,0,0.85);
    }

    .side-title {
      margin: 0 0 6px 0;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--text-muted);
    }

    /* Clock + weather */
    .time-row {
      display:flex;
      justify-content:space-between;
      align-items:baseline;
      font-size:13px;
      margin-top:4px;
      color:var(--text-main);
    }

    .time-label {
      font-size:11px;
      text-transform:uppercase;
      letter-spacing:0.14em;
      color:var(--text-muted);
    }

    .time-main {
      font-size:20px;
      font-weight:600;
    }

    .time-sub {
      font-size:11px;
      color:var(--text-muted);
    }

    .time-weather {
      margin-top:6px;
      font-size:12px;
      color:var(--text-muted);
    }

    /* Previous reports */
    .side-report-list {
      list-style: none;
      padding-left: 0;
      margin: 6px 0 0 0;
    }

    .side-report-item + .side-report-item {
      margin-top: 4px;
    }

    .side-report-date {
      font-size: 12px;
      font-weight: 500;
    }

    .side-report-links {
      font-size: 11px;
      color: var(--text-muted);
    }

    .side-report-links a {
      color: var(--accent-dark);
      text-decoration: none;
      font-weight: 500;
    }

    body[data-theme="dark"] .side-report-links a {
      color: #60a5fa;
    }

    .side-report-links .dot {
      color: #d1d5db;
      margin: 0 4px;
    }

    /* Extra reports */
    .extra-report-list {
      list-style: none;
      padding-left: 0;
      margin: 8px 0 0 0;
    }

    .extra-report-item {
      margin-bottom: 8px;
    }

    .extra-report-link {
      font-size: 12px;
      font-weight: 500;
      color: var(--accent-dark);
      text-decoration: none;
    }

    .extra-report-link:hover {
      text-decoration: underline;
    }

    body[data-theme="dark"] .extra-report-link {
      color: #60a5fa;
    }

    .extra-report-meta {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 6px;
      margin-top: 2px;
      font-size: 10px;
      color: var(--text-muted);
    }

    .extra-report-pill {
      padding: 1px 6px;
      border-radius: 999px;
      border: 1px solid #e5e7eb;
      font-size: 10px;
      white-space: nowrap;
    }

    .extra-report-pill-ok {
      background: rgba(22, 163, 74, 0.08);
      border-color: rgba(22, 163, 74, 0.35);
      color: #166534;
    }

    .extra-report-pill-expiring {
      background: rgba(234, 179, 8, 0.1);
      border-color: rgba(234, 179, 8, 0.45);
      color: #92400e;
    }

    body[data-theme="dark"] .extra-report-pill-ok {
      background: rgba(34,197,94,0.15);
      border-color: rgba(34,197,94,0.6);
      color: #bbf7d0;
    }

    body[data-theme="dark"] .extra-report-pill-expiring {
      background: rgba(250,204,21,0.1);
      border-color: rgba(250,204,21,0.6);
      color: #facc15;
    }

    /* Market snapshot */
    .market-list {
      list-style: none;
      padding-left: 0;
      margin: 6px 0 0 0;
    }

    .market-item {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 6px;
      font-size: 12px;
      padding: 2px 0;
    }

    .market-left {
      font-weight: 500;
      color: var(--text-main);
    }

    .market-symbol {
      font-size: 10px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-left: 4px;
    }

    .market-price {
      font-weight: 500;
      color: var(--text-main);
      margin-right:4px;
    }

    .market-change {
      font-size: 11px;
    }

    .market-change.up { color: #16a34a; }
    .market-change.down { color: #dc2626; }

    body[data-theme="dark"] .market-change.up { color: #4ade80; }
    body[data-theme="dark"] .market-change.down { color: #f97373; }

    footer {
      margin-top: 22px;
      font-size: 11px;
      color: var(--text-muted);
      text-align: left;
    }

    footer a {
      color: var(--accent-dark);
      text-decoration: none;
    }

    body[data-theme="dark"] footer a {
      color: #60a5fa;
    }

    @media (max-width: 900px) {
      .layout {
        grid-template-columns: minmax(0, 1fr);
      }
    }
  </style>
</head>

<body>
  <div class="page">

    <header>
      <div class="brand">
        <div class="brand-mark"><span>Max</span> <span>Bits</span></div>
        <p class="brand-subtitle">Daily Tech Intelligence · Telco · Media · AI · Cloud · Space · Patents</p>
      </div>

      <div class="header-controls">
        <button class="viewmode-pill" id="viewmode-btn">
          <span>View mode</span>
        </button>
        <div class="theme-toggle" id="theme-toggle">
          <div class="theme-thumb"></div>
        </div>
        <button class="exit-btn" id="exit-btn">Exit</button>
      </div>
    </header>

    <div class="layout">
      <!-- MAIN COLUMN -->
      <main class="main-card">
        <div class="main-header">
          <div>
            <h1 class="main-title">Latest report · __LATEST_DATE__</h1>
            <p class="main-meta">
              Curated news + deep-dives designed for busy tech leaders. Updated every morning.
            </p>
          </div>
          <span class="badge-today" id="today-pill">Today’s edition</span>
        </div>

        <div class="iframe-wrapper">
          <iframe src="__LATEST_HTML__" loading="lazy"></iframe>
        </div>
      </main>

      <!-- SIDEBAR -->
      <aside class="sidebar">

        <!-- TIME & WEATHER (time locale + placeholder meteo) -->
        <section class="side-card">
          <h2 class="side-title">Local time & weather</h2>
          <div class="time-row">
            <div>
              <div class="time-main" id="clock-main">--:--:--</div>
              <div class="time-sub" id="clock-sub">--</div>
            </div>
            <div class="time-weather">
              <div>Your location</div>
              <div id="weather-temp">--°C</div>
            </div>
          </div>
        </section>

        <!-- PREVIOUS REPORTS -->
        <section class="side-card">
          <h2 class="side-title">Previous 6 reports</h2>
          <ul class="side-report-list">
__PREVIOUS_LIST__
          </ul>
        </section>

        <!-- EXTRA REPORTS -->
        <section class="side-card">
          <h2 class="side-title">Extra reports (30 days)</h2>
          <ul class="extra-report-list">
__EXTRA_REPORTS__
          </ul>
        </section>

        <!-- MARKET SNAPSHOT -->
        <section class="side-card">
          <h2 class="side-title">Market snapshot*</h2>
          <ul class="market-list">
__MARKET_ITEMS__
          </ul>
          <p style="margin:6px 0 0; font-size:10px; color:#9ca3af;">
            *Static snapshot updated at __MARKET_UPDATED__. Values are indicative only.
          </p>
        </section>

      </aside>
    </div>

    <footer>
      MaxBits is generated automatically from curated RSS sources, CEO statements, patents and external reports.
      Reports are published as static HTML &amp; PDF via GitHub Pages.
    </footer>
  </div>

  <script>
    // THEME TOGGLE (light / dark) + VIEW MODE BUTTON
    (function() {
      const key = "maxbits_theme";
      const root = document.body;

      function applyTheme(t) {
        if (t === "dark") {
          root.setAttribute("data-theme", "dark");
        } else {
          root.setAttribute("data-theme", "light");
        }
      }

      function toggleTheme() {
        const current = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
        const next = current === "dark" ? "light" : "dark";
        applyTheme(next);
        try { localStorage.setItem(key, next); } catch(e) {}
      }

      const stored = localStorage.getItem(key);
      if (stored === "light" || stored === "dark") {
        applyTheme(stored);
      } else {
        applyTheme("light");
      }

      const toggle = document.getElementById("theme-toggle");
      if (toggle) {
        toggle.addEventListener("click", toggleTheme);
      }

      const viewBtn = document.getElementById("viewmode-btn");
      if (viewBtn) {
        viewBtn.addEventListener("click", toggleTheme);
      }
    })();

    // Digital clock (locale) + simple weather placeholder
    function updateClock() {
      const now = new Date();
      const main = document.getElementById('clock-main');
      const sub = document.getElementById('clock-sub');

      if (main) {
        main.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      }
      if (sub) {
        sub.textContent = now.toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
      }
    }
    setInterval(updateClock, 1000);
    updateClock();

    // Weather: best effort (navigator.geolocation required + open-meteo)
    (function() {
      const out = document.getElementById("weather-temp");
      if (!navigator.geolocation || !out) return;

      navigator.geolocation.getCurrentPosition(function(pos) {
        const lat = pos.coords.latitude.toFixed(4);
        const lon = pos.coords.longitude.toFixed(4);
        const url = "https://api.open-meteo.com/v1/forecast?latitude=" + lat + "&longitude=" + lon + "&current_weather=true";

        fetch(url).then(function(resp) {
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          return resp.json();
        }).then(function(data) {
          if (data && data.current_weather && typeof data.current_weather.temperature !== "undefined") {
            out.textContent = data.current_weather.temperature.toFixed(1) + "°C";
          }
        }).catch(function() {
          // silenzio in caso di errore
        });
      }, function() {
        // se l'utente rifiuta la geolocalizzazione, non facciamo nulla
      }, { timeout: 5000 });
    })();

    // "Today’s edition" = BACK HOME (sempre disponibile)
    (function() {
      const pill = document.getElementById("today-pill");
      if (!pill) return;
      pill.addEventListener("click", function() {
        // torna sempre alla home del sito (index.html) senza password
        var path = window.location.pathname || "/";
        path = path.replace(/index\\.html?$/i, "");
        if (!path.endsWith("/")) path += "/";
        window.location.href = path;
      });
    })();

    // EXIT button: prova a chiudere la tab, poi redirect al profilo GitHub
    (function() {
      const btn = document.getElementById("exit-btn");
      if (!btn) return;
      btn.addEventListener("click", function() {
        try { window.close(); } catch(e) {}
        setTimeout(function() {
          window.location.href = "https://github.com/MaxBertolo";
        }, 150);
      });
    })();
  </script>

</body>
</html>
"""

    return (
        template
        .replace("__LATEST_DATE__", latest_date)
        .replace("__LATEST_HTML__", latest_html_rel)
        .replace("__PREVIOUS_LIST__", previous_list_html)
        .replace("__EXTRA_REPORTS__", extra_reports_html)
        .replace("__MARKET_ITEMS__", market_html)
        .replace("__MARKET_UPDATED__", market_updated)
    )


def build_magazine(max_reports: int = 7) -> None:
    """
    Entry point:
      - legge i report sorgente
      - copia gli ultimi N in docs/reports
      - genera docs/index.html con layout moderno + sidebar
    """
    raw_reports = _find_reports()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    reports_for_docs = _copy_last_reports_to_docs(raw_reports, max_reports=max_reports)
    index_path = DOCS_DIR / "index.html"

    index_content = _build_index_content(reports_for_docs)
    index_path.write_text(index_content, encoding="utf-8")
    print(f"[MAG] MaxBits magazine index generated at: {index_path}")


if __name__ == "__main__":
    build_magazine()
