from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import List, Dict, Tuple

from datetime import datetime, timedelta
import yaml


BASE_DIR = Path(__file__).resolve().parent.parent

# Sorgente report (generati da main.py)
HTML_SRC_DIR = BASE_DIR / "reports" / "html"
PDF_SRC_DIR = BASE_DIR / "reports" / "pdf"

# Cartella pubblica per GitHub Pages
DOCS_DIR = BASE_DIR / "docs"
HTML_DST_DIR = DOCS_DIR / "reports" / "html"
PDF_DST_DIR = DOCS_DIR / "reports" / "pdf"


# -------------------------------------------------------------------
#  TROVA TUTTI I REPORT (ARCHIVIO + FRESCHI)
# -------------------------------------------------------------------

def _find_reports() -> List[Dict]:
    """
    Costruisce la lista dei report disponibili unendo:
      - archivio già presente in docs/reports/html + docs/reports/pdf
      - report freschi del giorno in reports/html + reports/pdf

    Per ogni data tiene un solo record (se esiste sia in docs che in reports,
    vince la versione 'fresh' in reports/).
    """
    reports_by_date: Dict[str, Dict] = {}

    pattern = re.compile(r"report_(\d{4}-\d{2}-\d{2})\.html$")

    # 1) ARCHIVIO GIA' PUBBLICATO
    archive_html_dir = DOCS_DIR / "reports" / "html"
    archive_pdf_dir = DOCS_DIR / "reports" / "pdf"

    if archive_html_dir.exists():
        for f in archive_html_dir.glob("report_*.html"):
            m = pattern.match(f.name)
            if not m:
                continue
            date_str = m.group(1)
            pdf_file = archive_pdf_dir / f"report_{date_str}.pdf"
            reports_by_date[date_str] = {
                "date": date_str,
                "html_file": f,
                "pdf_file": pdf_file if pdf_file.exists() else None,
            }

    # 2) REPORT FRESCHI DEL RUN CORRENTE
    if HTML_SRC_DIR.exists():
        for f in HTML_SRC_DIR.glob("report_*.html"):
            m = pattern.match(f.name)
            if not m:
                continue
            date_str = m.group(1)
            pdf_file = PDF_SRC_DIR / f"report_{date_str}.pdf"
            # sovrascrive eventuale archivio per la stessa data
            reports_by_date[date_str] = {
                "date": date_str,
                "html_file": f,
                "pdf_file": pdf_file if pdf_file.exists() else None,
            }

    reports = list(reports_by_date.values())
    reports.sort(key=lambda x: x["date"], reverse=True)
    print(f"[MAG] Found {len(reports)} reports (docs + fresh)")
    return reports


# -------------------------------------------------------------------
#  COPIA GLI ULTIMI N REPORT IN /docs (EVITA SameFileError)
# -------------------------------------------------------------------

def _copy_last_reports_to_docs(reports: List[Dict], max_reports: int = 7) -> List[Dict]:
    """
    Copia gli ultimi max_reports report in docs/reports/html e docs/reports/pdf.

    Se il file sorgente è già in docs/, NON viene ricopiato (per evitare SameFileError).

    Ritorna una lista di dict riferiti ai FILE DI DESTINAZIONE:
      {
        "date": "YYYY-MM-DD",
        "html_file": Path(...),  # sotto docs/reports/html
        "pdf_file": Path(...) or None,  # sotto docs/reports/pdf
      }
    """
    HTML_DST_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DST_DIR.mkdir(parents=True, exist_ok=True)

    selected = reports[:max_reports]
    out: List[Dict] = []

    for r in selected:
        date = r["date"]
        src_html: Path = r["html_file"]
        dst_html = HTML_DST_DIR / src_html.name

        # Evita SameFileError se src e dst sono lo stesso file
        if src_html.resolve() != dst_html.resolve():
            shutil.copy2(src_html, dst_html)
            print(f"[MAG] Copied HTML for {date} -> {dst_html}")
        else:
            print(f"[MAG] HTML for {date} already in docs, skip copy.")

        dst_pdf = None
        if r["pdf_file"] is not None:
            src_pdf: Path = r["pdf_file"]
            dst_pdf = PDF_DST_DIR / src_pdf.name
            if src_pdf.exists():
                if src_pdf.resolve() != dst_pdf.resolve():
                    shutil.copy2(src_pdf, dst_pdf)
                    print(f"[MAG] Copied PDF for {date} -> {dst_pdf}")
                else:
                    print(f"[MAG] PDF for {date} already in docs, skip copy.")
            else:
                print(f"[MAG] PDF source for {date} not found: {src_pdf}")
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


# -------------------------------------------------------------------
#  PREVIOUS 6 REPORTS (SIDEBAR)
# -------------------------------------------------------------------

def _build_previous_reports_list(reports_for_docs: List[Dict]) -> str:
    """
    Genera la lista dei 6 report precedenti per la sidebar.
    Ogni item mostra link HTML + PDF.
    """
    if len(reports_for_docs) <= 1:
        return '<p style="font-size:12px; color:#6b7280;">No previous reports yet.</p>'

    items: List[str] = []

    # r[0] = latest, r[1:7] = 6 giorni precedenti
    for r in reports_for_docs[1:7]:
        date = r["date"]
        html_rel = f"reports/html/{r['html_file'].name}"
        pdf_rel = f"reports/pdf/{r['pdf_file'].name}" if r["pdf_file"] else None

        if pdf_rel:
            links_html = (
                f'<a href="{html_rel}" target="_blank">HTML</a>'
                f'<span class="dot"> · </span>'
                f'<a href="{pdf_rel}" target="_blank">PDF</a>'
            )
        else:
            links_html = f'<a href="{html_rel}" target="_blank">HTML</a>'

        items.append(f"""
        <li class="side-report-item">
          <div class="side-report-main">
            <span class="side-report-date">{date}</span>
            <span class="side-report-links">{links_html}</span>
          </div>
        </li>
        """)

    return "\n".join(items)


# -------------------------------------------------------------------
#  EXTRA REPORTS (YAML + 30 giorni)
# -------------------------------------------------------------------

def _load_extra_reports() -> List[Dict]:
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
#  MARKET SNAPSHOT (STATICO DA YAML)
# -------------------------------------------------------------------

def _load_market_snapshot() -> Tuple[List[Dict], str]:
    """
    Legge config/market_snapshot.yaml.

    Struttura attesa:
      market_snapshot:
        updated_at: "2025-12-09 10:00 CET"
        items:
          - name: "Google"
            symbol: "GOOGL"
            price: 142.35
            change_percent: 1.23
    """
    cfg_path = BASE_DIR / "config" / "market_snapshot.yaml"
    if not cfg_path.exists():
        print(f"[MAG] No market_snapshot.yaml at {cfg_path}")
        return [], "n/a"

    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"[MAG] Cannot parse market_snapshot.yaml: {e!r}")
        return [], "n/a"

    ms = data.get("market_snapshot") or {}
    if not isinstance(ms, dict):
        return [], "n/a"

    updated_at = str(ms.get("updated_at") or "n/a").strip()
    items_raw = ms.get("items") or []
    if not isinstance(items_raw, list):
        items_raw = []

    items: List[Dict] = []
    for it in items_raw:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        symbol = str(it.get("symbol") or "").strip()
        price = it.get("price")
        change_pct = it.get("change_percent")
        if not name or not symbol:
            continue
        items.append(
            {
                "name": name,
                "symbol": symbol,
                "price": price,
                "change_percent": change_pct,
            }
        )

    return items, updated_at


def _build_market_sidebar_html(items: List[Dict], updated_at: str) -> str:
    if not items:
        return """
<ul class="market-list">
  <li class="market-item">
    <div class="market-left">No data</div>
    <div><span class="market-price">n/a</span></div>
  </li>
</ul>
<p style="margin:6px 0 0; font-size:10px; color:#9ca3af;">
  *No market snapshot available.
</p>
"""

    rows: List[str] = []
    for it in items:
        name = it["name"]
        symbol = it["symbol"]
        price = it.get("price")
        change = it.get("change_percent")

        if isinstance(price, (int, float)):
            price_txt = f"{price:.2f}"
        else:
            price_txt = "n/a"

        change_txt = ""
        cls = "market-change"
        if isinstance(change, (int, float)):
            if change > 0:
                cls += " up"
                change_txt = f"+{change:.2f}%"
            elif change < 0:
                cls += " down"
                change_txt = f"{change:.2f}%"
            else:
                change_txt = "0.00%"

        row = f"""
        <li class="market-item">
          <div class="market-left">{name}<span class="market-symbol">{symbol}</span></div>
          <div>
            <span class="market-price">{price_txt}</span>
            <span class="{cls}">{change_txt}</span>
          </div>
        </li>
        """
        rows.append(row)

    html_rows = "\n".join(rows)
    footer = f"""
<p style="margin:6px 0 0; font-size:10px; color:#9ca3af;">
  *Static snapshot updated at {updated_at}. Values are indicative only.
</p>
"""
    return f"<ul class=\"market-list\">\n{html_rows}\n</ul>\n{footer}"


# -------------------------------------------------------------------
#  INDEX.HTML TEMPLATE (CLOCK DIGITALE, METEO, LOGO, PASSWORD)
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
  <style>
    body {
      margin: 0;
      padding: 32px 16px;
      font-family: -apple-system, BlinkMacSystemFont, system-ui, "Segoe UI", sans-serif;
      background: #f5f5f7;
      color: #111827;
    }
    .page {
      max-width: 960px;
      margin: 0 auto;
    }
    h1 {
      font-size: 24px;
      margin-bottom: 10px;
    }
    p {
      font-size: 14px;
      color: #4b5563;
    }
  </style>
</head>
<body>
  <div class="page">
    <h1>MaxBits Mag</h1>
    <p>No reports available yet. Once the first daily report is generated, this page will show the latest report and the last days.</p>
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

    market_items, market_updated_at = _load_market_snapshot()
    market_html = _build_market_sidebar_html(market_items, market_updated_at)

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

    .brand img {
      height: 36px;
      width: auto;
      display: block;
    }

    .tagline {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      padding: 4px 9px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--text-muted);
      white-space: nowrap;
    }

    .theme-toggle {
      border-radius: 999px;
      width: 40px;
      height: 22px;
      padding: 2px;
      border: 1px solid var(--border);
      display: flex;
      align-items: center;
      background: rgba(255,255,255,0.85);
      cursor: pointer;
      position: relative;
    }

    body[data-theme="dark"] .theme-toggle {
      background: #020617;
    }

    .theme-thumb {
      width: 16px;
      height: 16px;
      border-radius: 999px;
      background: #020617;
      transform: translateX(0);
      transition: transform 0.22s ease, background 0.22s ease;
    }

    body[data-theme="dark"] .theme-thumb {
      transform: translateX(16px);
      background: #facc15;
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

    .clock-digital {
      font-size: 24px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-align: center;
      margin-bottom: 4px;
    }

    .clock-label {
      margin: 0;
      font-size: 11px;
      color: var(--text-muted);
      text-align: center;
    }

    .weather-row {
      margin-top: 10px;
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 11px;
      color: var(--text-muted);
    }

    .weather-temp-strong {
      font-weight: 600;
      color: var(--text-main);
    }

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
    }

    .market-change {
      font-size: 11px;
    }

    .market-change.up { color: #16a34a; }
    .market-change.down { color: #dc2626; }

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

    @media (max-width: 900px) {
      .layout {
        grid-template-columns: minmax(0, 1fr);
      }
    }

    #login-screen {
      position: fixed;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: radial-gradient(circle at top, #0b1120, #020617);
      z-index: 9999;
    }

    #login-card {
      background: #020617;
      border-radius: 16px;
      padding: 24px 22px 20px;
      width: 320px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.7);
      color: #e5e7eb;
      text-align: left;
      border: 1px solid #1f2937;
    }

    #login-card h1 {
      margin: 0 0 8px 0;
      font-size: 20px;
    }

    #login-card p {
      margin: 0 0 16px 0;
      font-size: 13px;
      color: #9ca3af;
    }

    #login-card label {
      display: block;
      font-size: 12px;
      margin-bottom: 4px;
      color: #cbd5f5;
    }

    #login-password {
      width: 100%;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid #4b5563;
      background: #020617;
      color: #e5e7eb;
      font-size: 13px;
      margin-bottom: 10px;
    }

    #login-btn {
      width: 100%;
      padding: 8px 10px;
      border: none;
      border-radius: 999px;
      background: #25A7FF;
      color: #0b1120;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
    }

    #login-error {
      margin-top: 8px;
      font-size: 12px;
      color: #fca5a5;
      min-height: 16px;
    }

    #protected-root {
      display: none;
    }
  </style>
</head>

<body>

  <div id="login-screen">
    <div id="login-card">
      <h1>MaxBits</h1>
      <p>Private daily tech report. Enter access password to continue.</p>
      <label for="login-password">Access password</label>
      <input type="password" id="login-password" placeholder="Password" />
      <button id="login-btn">Enter</button>
      <div id="login-error"></div>
    </div>
  </div>

  <div id="protected-root">
    <div class="page">

      <header>
        <div class="brand">
          <img src="assets/maxbits-logo.svg" alt="MaxBits">
        </div>

        <div style="display:flex; align-items:center; gap:10px;">
          <div class="tagline">Daily briefing</div>
          <div class="theme-toggle" id="theme-toggle">
            <div class="theme-thumb"></div>
          </div>
        </div>
      </header>

      <div class="layout">
        <main class="main-card">
          <div class="main-header">
            <div>
              <h1 class="main-title">Latest report · __LATEST_DATE__</h1>
              <p class="main-meta">
                Curated news + deep-dives designed for busy tech leaders. Updated every morning.
              </p>
            </div>
            <span class="badge-today">Today’s edition</span>
          </div>

          <div class="iframe-wrapper">
            <iframe src="__LATEST_HTML__" loading="lazy"></iframe>
          </div>
        </main>

        <aside class="sidebar">

          <section class="side-card">
            <h2 class="side-title">Local time & weather</h2>
            <div class="clock-digital" id="clock-digital">--:--</div>
            <p class="clock-label" id="clock-label-text"></p>
            <div class="weather-row" id="weather-row">
              <span id="weather-location">Detecting location…</span>
              <span id="weather-temp"></span>
            </div>
          </section>

          <section class="side-card">
            <h2 class="side-title">Previous 6 reports</h2>
            <ul class="side-report-list">
__PREVIOUS_LIST__
            </ul>
          </section>

          <section class="side-card">
            <h2 class="side-title">Extra reports (30 days)</h2>
            <ul class="extra-report-list">
__EXTRA_REPORTS__
            </ul>
          </section>

          <section class="side-card">
            <h2 class="side-title">Market snapshot*</h2>
__MARKET_HTML__
          </section>

        </aside>
      </div>

      <footer>
        MaxBits is generated automatically from curated RSS sources, CEO statements, patents and external reports.
        Reports are published as static HTML &amp; PDF via GitHub Pages.
      </footer>

    </div>
  </div>

  <script>
    // LOGIN (password lato client)
    (function() {
      const PASSWORD = "MaxBites1972!";   // <--- PUOI CAMBIARLA QUI
      const loginScreen = document.getElementById("login-screen");
      const root = document.getElementById("protected-root");
      const input = document.getElementById("login-password");
      const btn = document.getElementById("login-btn");
      const errorBox = document.getElementById("login-error");

      function unlock() {
        const val = (input.value || "").trim();
        if (val === PASSWORD) {
          loginScreen.style.display = "none";
          root.style.display = "block";
        } else {
          errorBox.textContent = "Wrong password. Please try again.";
        }
      }

      btn.addEventListener("click", unlock);
      input.addEventListener("keydown", function(ev) {
        if (ev.key === "Enter") unlock();
      });
    })();
  </script>

  <script>
    // THEME TOGGLE
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

      const stored = localStorage.getItem(key);
      if (stored === "light" || stored === "dark") {
        applyTheme(stored);
      } else {
        applyTheme("light");
      }

      const btn = document.getElementById("theme-toggle");
      if (btn) {
        btn.addEventListener("click", () => {
          const current = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
          const next = current === "dark" ? "light" : "dark";
          applyTheme(next);
          try { localStorage.setItem(key, next); } catch(e) {}
        });
      }
    })();

    // CLOCK DIGITALE
    function updateClock() {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, "0");
      const mm = String(now.getMinutes()).padStart(2, "0");
      const ss = String(now.getSeconds()).padStart(2, "0");

      const clockMain = document.getElementById("clock-digital");
      const clockLabel = document.getElementById("clock-label-text");
      if (clockMain) clockMain.textContent = hh + ":" + mm + ":" + ss;
      if (clockLabel) {
        clockLabel.textContent = now.toLocaleDateString(undefined, {
          weekday: "short",
          year: "numeric",
          month: "short",
          day: "numeric"
        });
      }
    }
    setInterval(updateClock, 1000);
    updateClock();

    // METEO (Open-Meteo)
    async function loadWeather() {
      const locEl = document.getElementById("weather-location");
      const tempEl = document.getElementById("weather-temp");
      if (!locEl || !tempEl) return;

      if (!navigator.geolocation) {
        locEl.textContent = "Location not available";
        tempEl.textContent = "";
        return;
      }

      function setError(msg) {
        locEl.textContent = msg;
        tempEl.textContent = "";
      }

      navigator.geolocation.getCurrentPosition(async (pos) => {
        try {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;

          const url = "https://api.open-meteo.com/v1/forecast?latitude="
                      + encodeURIComponent(lat)
                      + "&longitude=" + encodeURIComponent(lon)
                      + "&current_weather=true";

          const resp = await fetch(url);
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          const data = await resp.json();
          const cw = data.current_weather;
          if (!cw) {
            setError("Weather unavailable");
            return;
          }

          const t = cw.temperature;
          locEl.textContent = "Your location";
          tempEl.innerHTML = "<span class='weather-temp-strong'>" + t.toFixed(1) + "°C</span>";
        } catch (e) {
          console.warn("[Weather] failed:", e);
          setError("Weather unavailable");
        }
      }, () => {
        setError("Enable location to see weather");
      }, { timeout: 8000 });
    }
    loadWeather();
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
        .replace("__MARKET_HTML__", market_html)
    )


def build_magazine(max_reports: int = 7) -> None:
    raw_reports = _find_reports()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    reports_for_docs = _copy_last_reports_to_docs(raw_reports, max_reports=max_reports)
    index_path = DOCS_DIR / "index.html"

    index_content = _build_index_content(reports_for_docs)
    index_path.write_text(index_content, encoding="utf-8")
    print(f"[MAG] MaxBits magazine index generated at: {index_path}")


if __name__ == "__main__":
    build_magazine()
