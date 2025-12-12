# src/magazine_builder.py
from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent

# Fresh reports created by main/report builder
HTML_SRC_DIR = BASE_DIR / "reports" / "html"
PDF_SRC_DIR = BASE_DIR / "reports" / "pdf"

# Published archive (so previous 6 remain visible even if today's run fails)
DOCS_DIR = BASE_DIR / "docs"
HTML_ARCHIVE_DIR = DOCS_DIR / "reports" / "html"
PDF_ARCHIVE_DIR = DOCS_DIR / "reports" / "pdf"

# Public destinations
HTML_DST_DIR = DOCS_DIR / "reports" / "html"
PDF_DST_DIR = DOCS_DIR / "reports" / "pdf"

# Market snapshot JSON
JSON_DIR = BASE_DIR / "reports" / "json"

# Cartella JSON pubblica per GitHub Pages
JSON_DST_DIR = DOCS_DIR / "reports" / "json"
JSON_DST_DIR.mkdir(parents=True, exist_ok=True)

MARKET_LATEST = JSON_DIR / "market_snapshot_latest.json"

def _copy_market_snapshot():
    src = JSON_REPORTS_DIR / "market_snapshot_latest.json"
    if src.exists():
        shutil.copy2(src, JSON_DST_DIR / src.name)


def _safe_copy(src: Path, dst: Path) -> None:
    try:
        if src.resolve() == dst.resolve():
            return
    except Exception:
        pass
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dst)
    except Exception as e:
        print(f"[MAG][WARN] Copy failed {src} -> {dst}: {e!r}")


def _scan_reports(html_dir: Path, pdf_dir: Path) -> List[Dict]:
    reports: List[Dict] = []
    if not html_dir.exists():
        return reports

    pattern = re.compile(r"report_(\d{4}-\d{2}-\d{2})\.html$")

    for f in html_dir.glob("report_*.html"):
        m = pattern.match(f.name)
        if not m:
            continue
        date_str = m.group(1)
        pdf_file = pdf_dir / f"report_{date_str}.pdf"
        reports.append(
            {
                "date": date_str,
                "html_file": f,
                "pdf_file": pdf_file if pdf_file.exists() else None,
            }
        )

    reports.sort(key=lambda x: x["date"], reverse=True)
    return reports


def _find_reports_merged() -> List[Dict]:
    """
    Merge archive (docs/) + fresh (reports/).
    Fresh wins on same date.
    """
    by_date: Dict[str, Dict] = {}

    # archive first
    for r in _scan_reports(HTML_ARCHIVE_DIR, PDF_ARCHIVE_DIR):
        by_date[r["date"]] = r

    # fresh overrides
    for r in _scan_reports(HTML_SRC_DIR, PDF_SRC_DIR):
        by_date[r["date"]] = r

    reports = list(by_date.values())
    reports.sort(key=lambda x: x["date"], reverse=True)
    print(f"[MAG] Total reports found (merged): {len(reports)}")
    return reports


def _copy_last_reports_to_docs(reports: List[Dict], max_reports: int = 7) -> List[Dict]:
    HTML_DST_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DST_DIR.mkdir(parents=True, exist_ok=True)

    selected = reports[:max_reports]
    out: List[Dict] = []

    for r in selected:
        date = r["date"]
        src_html = r["html_file"]
        dst_html = HTML_DST_DIR / src_html.name
        _safe_copy(src_html, dst_html)

        dst_pdf = None
        if r.get("pdf_file"):
            src_pdf: Path = r["pdf_file"]
            dst_pdf = PDF_DST_DIR / src_pdf.name
            if src_pdf.exists():
                _safe_copy(src_pdf, dst_pdf)
            else:
                dst_pdf = None

        out.append({"date": date, "html_file": dst_html, "pdf_file": dst_pdf})

    return out


def _build_previous_reports_list(reports_for_docs: List[Dict]) -> str:
    if len(reports_for_docs) <= 1:
        return '<p style="font-size:12px; color:#6b7280;">No previous reports yet.</p>'

    items: List[str] = []
    for r in reports_for_docs[1:7]:
        date = r["date"]
        html_rel = f"reports/html/{Path(r['html_file']).name}"
        pdf_rel = f"reports/pdf/{Path(r['pdf_file']).name}" if r.get("pdf_file") else None

        if pdf_rel:
            links = (
                f'<a href="{html_rel}" target="_blank" rel="noopener">HTML</a>'
                f'<span class="dot">·</span>'
                f'<a href="{pdf_rel}" target="_blank" rel="noopener">PDF</a>'
            )
        else:
            links = f'<a href="{html_rel}" target="_blank" rel="noopener">HTML</a>'

        items.append(
            f"""
<li class="side-report-item">
  <div class="side-report-main">
    <span class="side-report-date">{date}</span>
    <span class="side-report-links">{links}</span>
  </div>
</li>
""".strip()
        )

    return "\n".join(items)


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

    raw = data.get("extra_reports") or []
    if not isinstance(raw, list):
        return []

    today = datetime.utcnow().date()
    cutoff = today - timedelta(days=30)

    out: List[Dict] = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip()
        url = str(it.get("url") or "").strip()
        date_str = str(it.get("date") or "").strip()
        if not (title and url and date_str):
            continue
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if d < cutoff or d > today:
            continue

        age = (today - d).days
        out.append(
            {
                "title": title,
                "url": url,
                "date": date_str,
                "days_left": max(0, 30 - age),
            }
        )

    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def _build_extra_reports_sidebar_html(extra_reports: List[Dict]) -> str:
    if not extra_reports:
        return '<p style="font-size:12px; color:#6b7280;">No extra reports (last 30 days).</p>'

    items: List[str] = []
    for rep in extra_reports:
        days_left = int(rep.get("days_left", 0))
        if days_left <= 0:
            pill = "expires today"
            pill_class = "expiring"
        elif days_left == 1:
            pill = "1 day left"
            pill_class = "expiring"
        else:
            pill = f"{days_left} days left"
            pill_class = "ok"

        items.append(
            f"""
<li class="extra-report-item">
  <a href="{rep["url"]}" target="_blank" rel="noopener" class="extra-report-link">{rep["title"]}</a>
  <div class="extra-report-meta">
    <span class="extra-report-date">{rep["date"]}</span>
    <span class="extra-report-pill extra-report-pill-{pill_class}">{pill}</span>
  </div>
</li>
""".strip()
        )

    return "\n".join(items)


def _load_market_snapshot() -> Optional[Dict]:
    if not MARKET_LATEST.exists():
        print(f"[MAG] Market snapshot missing: {MARKET_LATEST}")
        return None
    try:
        data = json.loads(MARKET_LATEST.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"[MAG] Market snapshot parse error: {e!r}")
        return None


def _build_market_snapshot_html(snapshot: Optional[Dict]) -> Tuple[str, str]:
    """
    Returns (items_html, updated_at_label)
    """
    if not snapshot:
        return (
            "\n".join(
                [
                    _market_li("Google", "GOOGL", None, None),
                    _market_li("Tesla", "TSLA", None, None),
                    _market_li("Apple", "AAPL", None, None),
                    _market_li("NVIDIA", "NVDA", None, None),
                    _market_li("Meta", "META", None, None),
                    _market_li("Microsoft", "MSFT", None, None),
                    _market_li("Amazon", "AMZN", None, None),
                    _market_li("Bitcoin", "BTC", None, None),
                    _market_li("Ethereum", "ETH", None, None),
                ]
            ),
            "not available",
        )

    updated = str(snapshot.get("updated_at") or "n/a")
    items = snapshot.get("items") or []
    if not isinstance(items, list):
        items = []

    desired = ["GOOGL", "TSLA", "AAPL", "NVDA", "META", "MSFT", "AMZN", "BTC", "ETH"]
    lookup = {str(i.get("symbol")): i for i in items if isinstance(i, dict)}

    html_items: List[str] = []
    for sym in desired:
        it = lookup.get(sym) or {}
        html_items.append(
            _market_li(
                str(it.get("name") or it.get("label") or sym),
                sym,
                it.get("price"),
                it.get("change_pct"),
            )
        )

    return "\n".join(html_items), updated


def _market_li(name: str, symbol: str, price, change_pct) -> str:
    price_str = "—"
    if isinstance(price, (int, float)):
        price_str = f"{price:.2f}"

    cls = "market-change"
    pct_str = ""
    if isinstance(change_pct, (int, float)):
        if change_pct > 0:
            cls += " up"
            pct_str = f"+{change_pct:.2f}%"
        elif change_pct < 0:
            cls += " down"
            pct_str = f"{change_pct:.2f}%"
        else:
            pct_str = "0.00%"

    return f"""
<li class="market-item">
  <div class="market-left">{name}<span class="market-symbol">{symbol}</span></div>
  <div>
    <span class="market-price">{price_str}</span>
    <span class="{cls}">{pct_str}</span>
  </div>
</li>
""".strip()


def _build_bye_page() -> str:
    # This is the courtesy page you asked for: re-enter requires password again.
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MaxBits · Exit</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      margin:0;
      padding:0;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#020617;
      color:#e5e7eb;
      display:flex;
      align-items:center;
      justify-content:center;
      min-height:100vh;
    }
    .box {
      max-width:360px;
      padding:24px 28px;
      border-radius:16px;
      background:rgba(15,23,42,0.9);
      box-shadow:0 18px 40px rgba(0,0,0,0.9);
      text-align:center;
    }
    h1 { margin:0 0 8px; font-size:20px; }
    p { margin:4px 0; font-size:13px; color:#9ca3af; }
    button {
      margin-top:12px;
      padding:8px 16px;
      border-radius:999px;
      border:none;
      background:#25A7FF;
      color:#0b1120;
      font-weight:500;
      cursor:pointer;
    }
  </style>
</head>
<body>
  <div class="box">
    <h1>MaxBits closed</h1>
    <p>You exited the MaxBits daily view.</p>
    <p>To re-enter, you will be asked again for the access password.</p>
    <button id="back-btn">Back to MaxBits</button>
  </div>

  <script>
    document.getElementById("back-btn").addEventListener("click", function() {
      try { sessionStorage.removeItem("maxbits-auth"); } catch(e) {}
      window.location.href = "index.html";
    });
  </script>
</body>
</html>
"""


def _build_index_content(reports_for_docs: List[Dict]) -> str:
    if not reports_for_docs:
        return """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MaxBits</title></head><body style="font-family:system-ui;padding:24px">No reports yet.</body></html>"""

    latest = reports_for_docs[0]
    latest_date = latest["date"]
    latest_html_rel = f"reports/html/{Path(latest['html_file']).name}"

    previous_html = _build_previous_reports_list(reports_for_docs)
    extra_html = _build_extra_reports_sidebar_html(_load_extra_reports())

    market_snapshot = _load_market_snapshot()
    market_items_html, market_updated = _build_market_snapshot_html(market_snapshot)

    # NOTE: password is here (easy to change)
    PASSWORD = "mix"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MaxBits · Daily Tech Intelligence</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #f5f7fa;
      --card-bg: #ffffff;
      --accent: #25A7FF;
      --accent-dark: #006fd6;
      --text-main: #111111;
      --text-muted: #6b7280;
      --border: #e5e7eb;
      --radius-lg: 16px;
      --shadow-soft: 0 18px 40px rgba(15, 23, 42, 0.18);
    }}

    body[data-theme="dark"] {{
      --bg: #020617;
      --card-bg: #020617;
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
      --border: #1f2937;
      --shadow-soft: 0 18px 40px rgba(0, 0, 0, 0.8);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      padding: 0;
      background: radial-gradient(circle at top left, #e5f3ff, #f5f7fa);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      transition: background 0.35s ease, color 0.25s ease;
    }}

    body[data-theme="dark"] {{
      background: radial-gradient(circle at top left, #020617, #020617);
    }}

    .page {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px 16px 40px;
    }}

    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 8px 4px 22px;
    }}

    .brand-left {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}

    .brand-pill {{
      display:inline-flex;
      align-items:center;
      padding:4px 10px;
      border-radius:999px;
      background:#ffffff;
      box-shadow:0 6px 14px rgba(15,23,42,0.10);
    }}

    body[data-theme="dark"] .brand-pill {{
      background:#020617;
      box-shadow:0 10px 24px rgba(0,0,0,0.85);
    }}

    .brand-pill span:first-child {{
      font-weight:600;
      padding-right:4px;
    }}
    .brand-pill span:last-child {{
      font-weight:600;
      color:var(--accent-dark);
    }}

    .brand-tagline {{
      font-size:11px;
      color:var(--text-muted);
    }}

    .header-right {{
      display:flex;
      flex-direction:column;
      align-items:flex-end;
      gap:4px;
    }}

    .view-mode-label {{
      font-size:10px;
      letter-spacing:0.16em;
      text-transform:uppercase;
      color:var(--text-muted);
    }}

    .view-mode-row {{
      display:flex;
      align-items:center;
      gap:8px;
    }}

    .theme-toggle {{
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
    }}

    body[data-theme="dark"] .theme-toggle {{
      background: #020617;
    }}

    .theme-thumb {{
      width: 16px;
      height: 16px;
      border-radius: 999px;
      background: #020617;
      transform: translateX(0);
      transition: transform 0.22s ease, background 0.22s ease;
    }}

    body[data-theme="dark"] .theme-thumb {{
      transform: translateX(16px);
      background: #facc15;
    }}

    .exit-btn {{
      margin-top:2px;
      font-size:11px;
      padding:3px 10px;
      border-radius:999px;
      border:1px solid #fecaca;
      background:#fee2e2;
      color:#b91c1c;
      cursor:pointer;
    }}

    body[data-theme="dark"] .exit-btn {{
      background:#7f1d1d;
      border-color:#fecaca;
      color:#fee2e2;
    }}

    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 2.7fr) minmax(270px, 1fr);
      gap: 20px;
    }}

    .main-card {{
      background: radial-gradient(circle at top left, rgba(37,167,255,0.12), rgba(255,255,255,0.96));
      padding: 20px 20px 18px;
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-soft);
      border: 1px solid rgba(255,255,255,0.4);
      backdrop-filter: blur(10px);
    }}

    body[data-theme="dark"] .main-card {{
      background: radial-gradient(circle at top left, rgba(15,118,255,0.35), #020617);
      border-color: #1f2937;
    }}

    .main-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 12px;
    }}

    .main-title {{
      margin: 0;
      font-size: 20px;
      letter-spacing: 0.02em;
    }}

    .main-meta {{
      margin: 3px 0 0;
      font-size: 12px;
      color: var(--text-muted);
    }}

    .badge-today {{
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(37,167,255,0.12);
      color: var(--accent-dark);
      border: 1px solid rgba(37,167,255,0.4);
      white-space: nowrap;
      cursor:pointer;
    }}

    body[data-theme="dark"] .badge-today {{
      background: rgba(37,167,255,0.15);
      color: #e0f2fe;
      border-color: rgba(59,130,246,0.6);
    }}

    .iframe-wrapper {{
      margin-top: 10px;
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid rgba(148,163,184,0.5);
      background: #ffffff;
    }}

    body[data-theme="dark"] .iframe-wrapper {{
      background: #020617;
      border-color: #1f2937;
    }}

    .iframe-wrapper iframe {{
      width: 100%;
      height: 78vh;
      border: none;
    }}

    .sidebar {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}

    .side-card {{
      background: var(--card-bg);
      border-radius: 14px;
      padding: 14px 14px 12px;
      border: 1px solid var(--border);
      box-shadow: 0 10px 26px rgba(15,23,42,0.08);
    }}

    body[data-theme="dark"] .side-card {{
      box-shadow: 0 16px 40px rgba(0,0,0,0.85);
    }}

    .side-title {{
      margin: 0 0 6px 0;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--text-muted);
    }}

    .clock-digital {{
      font-size: 20px;
      font-weight: 600;
    }}

    .clock-sub {{
      margin:2px 0 0;
      font-size:11px;
      color:var(--text-muted);
    }}

    .side-report-list, .extra-report-list, .market-list {{
      list-style: none;
      padding-left: 0;
      margin: 6px 0 0 0;
    }}

    .side-report-item + .side-report-item {{
      margin-top: 4px;
    }}

    .side-report-date {{
      font-size: 12px;
      font-weight: 500;
    }}

    .side-report-links {{
      font-size: 11px;
      color: var(--text-muted);
    }}

    .side-report-links a {{
      color: var(--accent-dark);
      text-decoration: none;
      font-weight: 500;
    }}

    body[data-theme="dark"] .side-report-links a {{
      color: #60a5fa;
    }}

    .side-report-links .dot {{
      color: #d1d5db;
      margin: 0 4px;
    }}

    .extra-report-item {{ margin-bottom: 8px; }}
    .extra-report-link {{
      font-size: 12px;
      font-weight: 500;
      color: var(--accent-dark);
      text-decoration: none;
    }}
    body[data-theme="dark"] .extra-report-link {{ color: #60a5fa; }}
    .extra-report-meta {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 6px;
      margin-top: 2px;
      font-size: 10px;
      color: var(--text-muted);
    }}

    .extra-report-pill {{
      padding: 1px 6px;
      border-radius: 999px;
      border: 1px solid #e5e7eb;
      font-size: 10px;
      white-space: nowrap;
    }}
    .extra-report-pill-ok {{
      background: rgba(22, 163, 74, 0.08);
      border-color: rgba(22, 163, 74, 0.35);
      color: #166534;
    }}
    .extra-report-pill-expiring {{
      background: rgba(234, 179, 8, 0.1);
      border-color: rgba(234, 179, 8, 0.45);
      color: #92400e;
    }}

    body[data-theme="dark"] .extra-report-pill-ok {{
      background: rgba(34,197,94,0.15);
      border-color: rgba(34,197,94,0.6);
      color: #bbf7d0;
    }}
    body[data-theme="dark"] .extra-report-pill-expiring {{
      background: rgba(250,204,21,0.1);
      border-color: rgba(250,204,21,0.6);
      color: #facc15;
    }}

    .market-item {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 6px;
      font-size: 12px;
      padding: 2px 0;
    }}
    .market-left {{ font-weight: 500; color: var(--text-main); }}
    .market-symbol {{
      font-size: 10px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-left: 4px;
    }}
    .market-price {{ font-weight: 500; color: var(--text-main); }}
    .market-change {{ font-size: 11px; }}
    .market-change.up {{ color: #16a34a; }}
    .market-change.down {{ color: #dc2626; }}
    body[data-theme="dark"] .market-change.up {{ color: #4ade80; }}
    body[data-theme="dark"] .market-change.down {{ color: #f97373; }}

    footer {{
      margin-top: 22px;
      font-size: 11px;
      color: var(--text-muted);
      text-align: left;
    }}

    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: minmax(0, 1fr); }}
    }}
  </style>
</head>

<body>
  <div class="page">

    <header>
      <div class="brand-left">
        <div class="brand-pill"><span>Max</span><span>Bits</span></div>
        <div class="brand-tagline">Daily Tech Intelligence · Telco · Media · AI · Cloud · Space · Patents</div>
      </div>

      <div class="header-right">
        <div class="view-mode-row">
          <span class="view-mode-label">View mode</span>
          <div class="theme-toggle" id="theme-toggle"><div class="theme-thumb"></div></div>
        </div>
        <button class="exit-btn" id="exit-btn">Exit</button>
      </div>
    </header>

    <div class="layout">
      <main class="main-card">
        <div class="main-header">
          <div>
            <h1 class="main-title">Latest report · {latest_date}</h1>
            <p class="main-meta">Curated news + deep-dives designed for busy tech leaders. Updated every morning.</p>
          </div>
          <span class="badge-today" id="today-badge">Today’s edition</span>
        </div>

        <div class="iframe-wrapper">
          <iframe src="{latest_html_rel}" loading="lazy"></iframe>
        </div>
      </main>

      <aside class="sidebar">

        <section class="side-card">
          <h2 class="side-title">Local time</h2>
          <div>
            <div class="clock-digital" id="clock-digital">--:--:--</div>
            <p class="clock-sub" id="clock-date"></p>
          </div>
        </section>

        <section class="side-card">
          <h2 class="side-title">Previous 6 reports</h2>
          <ul class="side-report-list">
            {previous_html}
          </ul>
        </section>

        <section class="side-card">
          <h2 class="side-title">Extra reports (30 days)</h2>
          <ul class="extra-report-list">
            {extra_html}
          </ul>
        </section>

        <section class="side-card">
          <h2 class="side-title">Market snapshot*</h2>
          <ul class="market-list">
            {market_items_html}
          </ul>
          <p style="margin:6px 0 0; font-size:10px; color:#9ca3af;">
            *Static snapshot updated at {market_updated}. Values are indicative only.
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
    // ---- Password gate (SESSION): asked once, then remembered until Exit ----
    (function() {{
      const PASSWORD = "{PASSWORD}";
      const KEY = "maxbits-auth";
      if (!sessionStorage.getItem(KEY)) {{
        const userInput = prompt("Enter password to access MaxBits:");
        if (userInput !== PASSWORD) {{
          alert("Incorrect password.");
          window.location.href = "bye.html";
          return;
        }}
        sessionStorage.setItem(KEY, "1");
      }}
    }})();

    // ---- View mode (light/dark) ----
    (function() {{
      const key = "maxbits_theme";
      const root = document.body;

      function applyTheme(t) {{
        root.setAttribute("data-theme", (t === "dark") ? "dark" : "light");
      }}

      const stored = localStorage.getItem(key);
      applyTheme((stored === "dark" || stored === "light") ? stored : "light");

      const btn = document.getElementById("theme-toggle");
      if (btn) {{
        btn.addEventListener("click", () => {{
          const current = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
          const next = current === "dark" ? "light" : "dark";
          applyTheme(next);
          try {{ localStorage.setItem(key, next); }} catch(e) {{}}
        }});
      }}
    }})();

    // ---- Today’s edition = back to home ----
    (function() {{
      const btn = document.getElementById("today-badge");
      if (!btn) return;
      btn.addEventListener("click", function() {{
        window.location.href = "index.html";
      }});
    }})();

    // ---- Exit button -> courtesy page + clears session auth ----
    (function() {{
      const btn = document.getElementById("exit-btn");
      if (!btn) return;
      btn.addEventListener("click", function() {{
        try {{ sessionStorage.removeItem("maxbits-auth"); }} catch(e) {{}}
        window.location.href = "bye.html";
      }});
    }})();

    // ---- Digital clock ----
    function updateClock() {{
      const now = new Date();
      const timeEl = document.getElementById("clock-digital");
      const dateEl = document.getElementById("clock-date");
      if (timeEl) {{
        timeEl.textContent = now.toLocaleTimeString([], {{ hour: "2-digit", minute: "2-digit", second: "2-digit" }});
      }}
      if (dateEl) {{
        dateEl.textContent = now.toLocaleDateString([], {{ weekday: "short", day: "2-digit", month: "short", year: "numeric" }});
      }}
    }}
    setInterval(updateClock, 1000);
    updateClock();
  </script>
</body>
</html>
"""


def build_magazine(max_reports: int = 7) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    reports = _find_reports_merged()
    reports_for_docs = _copy_last_reports_to_docs(reports, max_reports=max_reports)

    (DOCS_DIR / "index.html").write_text(_build_index_content(reports_for_docs), encoding="utf-8")
    (DOCS_DIR / "bye.html").write_text(_build_bye_page(), encoding="utf-8")

    print("[MAG] Generated docs/index.html and docs/bye.html")


if __name__ == "__main__":
    build_magazine()
