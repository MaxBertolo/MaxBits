from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent

# ---- Sources: daily reports produced by main.py ----
HTML_SRC_DIR_PRIMARY = BASE_DIR / "reports" / "html"
PDF_SRC_DIR_PRIMARY = BASE_DIR / "reports" / "pdf"

# ---- Fallback archive already published in docs/ (rolling history) ----
HTML_SRC_DIR_FALLBACK = BASE_DIR / "docs" / "reports" / "html"
PDF_SRC_DIR_FALLBACK = BASE_DIR / "docs" / "reports" / "pdf"

# ---- GitHub Pages public folder ----
DOCS_DIR = BASE_DIR / "docs"
HTML_DST_DIR = DOCS_DIR / "reports" / "html"
PDF_DST_DIR = DOCS_DIR / "reports" / "pdf"

# ---- Config ----
EXTRA_REPORTS_CFG = BASE_DIR / "config" / "extra_reports.yaml"

# ---- UI / Access ----
ACCESS_PASSWORD = "mix"  # cambia qui quando vuoi


# -------------------------------------------------------------------
#  REPORT DISCOVERY
# -------------------------------------------------------------------

_REPORT_RE = re.compile(r"report_(\d{4}-\d{2}-\d{2})\.html$")


def _scan_reports(html_dir: Path, pdf_dir: Path) -> List[Dict]:
    """
    Scan one (html_dir, pdf_dir) pair and return:
      { "date": "YYYY-MM-DD", "html_file": Path, "pdf_file": Path|None }
    """
    if not html_dir.exists():
        return []

    out: List[Dict] = []
    for f in html_dir.glob("report_*.html"):
        m = _REPORT_RE.match(f.name)
        if not m:
            continue
        date_str = m.group(1)
        pdf = pdf_dir / f"report_{date_str}.pdf"
        out.append(
            {
                "date": date_str,
                "html_file": f,
                "pdf_file": pdf if pdf.exists() else None,
            }
        )

    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def _find_reports_merged() -> List[Dict]:
    """
    Merge reports found in primary (reports/) and fallback (docs/) folders.
    Keyed by date (YYYY-MM-DD) so we keep one per day.
    """
    merged: Dict[str, Dict] = {}

    for r in _scan_reports(HTML_SRC_DIR_PRIMARY, PDF_SRC_DIR_PRIMARY):
        merged.setdefault(r["date"], r)

    for r in _scan_reports(HTML_SRC_DIR_FALLBACK, PDF_SRC_DIR_FALLBACK):
        merged.setdefault(r["date"], r)

    reports = list(merged.values())
    reports.sort(key=lambda x: x["date"], reverse=True)
    print(f"[MAG] Total reports found (merged): {len(reports)}")
    return reports


def _copy_last_reports_to_docs(reports: List[Dict], max_reports: int = 7) -> List[Dict]:
    """
    Copy last N reports into docs/reports/html|pdf.
    Avoid SameFileError and never crash if a copy fails.
    Returns list pointing to DESTINATION files.
    """
    HTML_DST_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DST_DIR.mkdir(parents=True, exist_ok=True)

    selected = reports[:max_reports]
    out: List[Dict] = []

    for r in selected:
        date = r["date"]

        src_html: Path = r["html_file"]
        dst_html = HTML_DST_DIR / src_html.name

        # copy HTML
        try:
            if src_html.exists():
                if src_html.resolve() != dst_html.resolve():
                    shutil.copy2(src_html, dst_html)
                    print(f"[MAG] Copied HTML for {date} -> {dst_html}")
                else:
                    print(f"[MAG] HTML for {date} already in docs/, skipping copy.")
            else:
                print(f"[MAG][WARN] Missing HTML for {date}: {src_html}")
        except Exception as e:
            print(f"[MAG][WARN] Cannot copy HTML for {date}: {e!r}")

        # copy PDF (optional)
        dst_pdf: Optional[Path] = None
        if r.get("pdf_file") is not None:
            src_pdf: Path = r["pdf_file"]
            dst_pdf = PDF_DST_DIR / src_pdf.name
            try:
                if src_pdf.exists():
                    if src_pdf.resolve() != dst_pdf.resolve():
                        shutil.copy2(src_pdf, dst_pdf)
                        print(f"[MAG] Copied PDF for {date} -> {dst_pdf}")
                    else:
                        print(f"[MAG] PDF for {date} already in docs/, skipping copy.")
                else:
                    print(f"[MAG][WARN] Missing PDF for {date}: {src_pdf}")
                    dst_pdf = None
            except Exception as e:
                print(f"[MAG][WARN] Cannot copy PDF for {date}: {e!r}")
                dst_pdf = None
        else:
            print(f"[MAG] No PDF for {date}, skipping PDF copy.")

        out.append({"date": date, "html_file": dst_html, "pdf_file": dst_pdf})

    return out


# -------------------------------------------------------------------
#  SIDEBAR: PREVIOUS 6 REPORTS
# -------------------------------------------------------------------

def _build_previous_reports_list(reports_for_docs: List[Dict]) -> str:
    """
    Sidebar HTML: previous 6 reports (skip latest).
    Prefer showing PDF link when available.
    """
    if len(reports_for_docs) <= 1:
        return '<p style="font-size:12px; color:#6b7280;">No previous reports yet.</p>'

    items: List[str] = []
    for r in reports_for_docs[1:7]:
        date = r["date"]
        html_rel = f"reports/html/{r['html_file'].name}"
        pdf_rel = f"reports/pdf/{r['pdf_file'].name}" if r.get("pdf_file") else None

        if pdf_rel:
            links_html = (
                f'<a href="{pdf_rel}" target="_blank" rel="noopener">PDF</a>'
                f'<span class="dot">·</span>'
                f'<a href="{html_rel}" target="_blank" rel="noopener">HTML</a>'
            )
        else:
            links_html = f'<a href="{html_rel}" target="_blank" rel="noopener">HTML</a>'

        items.append(
            f"""
<li class="side-report-item">
  <div class="side-report-main">
    <span class="side-report-date">{date}</span>
    <span class="side-report-links">{links_html}</span>
  </div>
</li>
""".strip()
        )

    return "\n".join(items)


# -------------------------------------------------------------------
#  EXTRA REPORTS (YAML + 30 DAYS WINDOW)
# -------------------------------------------------------------------

def _load_extra_reports() -> List[Dict]:
    """
    Reads config/extra_reports.yaml:
      extra_reports:
        - title: ...
          url: ...
          date: "YYYY-MM-DD"
    Returns only last 30 days entries (UTC date comparison).
    """
    if not EXTRA_REPORTS_CFG.exists():
        print(f"[MAG] No extra_reports.yaml at {EXTRA_REPORTS_CFG}")
        return []

    try:
        data = yaml.safe_load(EXTRA_REPORTS_CFG.read_text(encoding="utf-8")) or {}
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

        out.append({"title": title, "url": url, "date": date_str, "days_left": days_left})

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
  <a href="{url}" target="_blank" rel="noopener" class="extra-report-link">{title}</a>
  <div class="extra-report-meta">
    <span class="extra-report-date">{date_str}</span>
    <span class="extra-report-pill extra-report-pill-{pill_class}">{pill}</span>
  </div>
</li>
""".strip()
        )

    return "\n".join(items)


# -------------------------------------------------------------------
#  INDEX HTML
# -------------------------------------------------------------------

def _build_index_content(reports_for_docs: List[Dict]) -> str:
    if not reports_for_docs:
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Daily Tech Intelligence</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body style="margin:0;padding:32px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7;color:#111827;">
  <div style="max-width:960px;margin:0 auto;">
    <h1>MaxBits · Daily Tech Intelligence</h1>
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

    .brand-left {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .brand-pill {
      display:inline-flex;
      align-items:center;
      padding:4px 10px;
      border-radius:999px;
      background:#ffffff;
      box-shadow:0 6px 14px rgba(15,23,42,0.10);
    }

    body[data-theme="dark"] .brand-pill {
      background:#020617;
      box-shadow:0 10px 24px rgba(0,0,0,0.85);
    }

    .brand-pill span:first-child {
      font-weight:600;
      padding-right:4px;
    }
    .brand-pill span:last-child {
      font-weight:600;
      color:var(--accent-dark);
    }

    .brand-tagline {
      font-size:11px;
      color:var(--text-muted);
    }

    .header-right {
      display:flex;
      flex-direction:column;
      align-items:flex-end;
      gap:4px;
    }

    .view-mode-row {
      display:flex;
      align-items:center;
      gap:8px;
    }

    .view-mode-label {
      font-size:10px;
      letter-spacing:0.16em;
      text-transform:uppercase;
      color:var(--text-muted);
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

    .exit-btn {
      margin-top:2px;
      font-size:11px;
      padding:3px 10px;
      border-radius:999px;
      border:1px solid #fecaca;
      background:#fee2e2;
      color:#b91c1c;
      cursor:pointer;
    }

    body[data-theme="dark"] .exit-btn {
      background:#7f1d1d;
      border-color:#fecaca;
      color:#fee2e2;
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

    /* "Today’s edition" also acts as Back/Home */
    .badge-today {
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(37,167,255,0.12);
      color: var(--accent-dark);
      border: 1px solid rgba(37,167,255,0.4);
      white-space: nowrap;
      cursor:pointer;
      user-select:none;
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

    .clock-digital {
      font-size: 20px;
      font-weight: 600;
    }

    .clock-sub {
      margin:2px 0 0;
      font-size:11px;
      color:var(--text-muted);
    }

    .weather-temp {
      margin-top:8px;
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

    footer {
      margin-top: 22px;
      font-size: 11px;
      color: var(--text-muted);
      text-align: left;
    }

    @media (max-width: 900px) {
      .layout { grid-template-columns: minmax(0, 1fr); }
    }
  </style>
</head>

<body>
  <div class="page">
    <header>
      <div class="brand-left">
        <div class="brand-pill">
          <span>Max</span><span>Bits</span>
        </div>
        <div class="brand-tagline">
          Daily Tech Intelligence · Telco · Media · AI · Cloud · Space · Patents
        </div>
      </div>

      <div class="header-right">
        <div class="view-mode-row">
          <span class="view-mode-label">View mode</span>
          <div class="theme-toggle" id="theme-toggle">
            <div class="theme-thumb"></div>
          </div>
        </div>
        <button class="exit-btn" id="exit-btn">Exit</button>
      </div>
    </header>

    <div class="layout">
      <!-- MAIN -->
      <main class="main-card">
        <div class="main-header">
          <div>
            <h1 class="main-title">Latest report · __LATEST_DATE__</h1>
            <p class="main-meta">
              Curated news + deep-dives designed for busy tech leaders. Updated every morning.
            </p>
          </div>
          <span class="badge-today" id="today-badge">Today’s edition</span>
        </div>

        <div class="iframe-wrapper">
          <iframe src="__LATEST_HTML__" loading="lazy"></iframe>
        </div>
      </main>

      <!-- SIDEBAR -->
      <aside class="sidebar">

        <section class="side-card">
          <h2 class="side-title">Local time &amp; weather</h2>
          <div>
            <div class="clock-digital" id="clock-digital">--:--:--</div>
            <p class="clock-sub" id="clock-date"></p>
            <p class="weather-temp" id="weather-text">Detecting your location…</p>
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

      </aside>
    </div>

    <footer>
      MaxBits is generated automatically from curated RSS sources, CEO statements, patents and external reports.
      Reports are published as static HTML &amp; PDF via GitHub Pages.
    </footer>
  </div>

  <script>
    // ---- Password gate (SESSION) ----
    (function() {
      const PASSWORD = "__PASSWORD__";
      const KEY = "maxbits-auth";

      if (!sessionStorage.getItem(KEY)) {
        const userInput = prompt("Enter password to access MaxBits:");
        if (userInput !== PASSWORD) {
          alert("Incorrect password.");
          window.location.href = "bye.html";
          return;
        }
        sessionStorage.setItem(KEY, "1");
      }
    })();

    // ---- View mode (light/dark) ----
    (function() {
      const key = "maxbits_theme";
      const root = document.body;

      function applyTheme(t) {
        if (t === "dark") root.setAttribute("data-theme", "dark");
        else root.setAttribute("data-theme", "light");
      }

      const stored = localStorage.getItem(key);
      if (stored === "light" || stored === "dark") applyTheme(stored);
      else applyTheme("light");

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

    // ---- Today’s edition: always back to home ----
    (function() {
      const btn = document.getElementById("today-badge");
      if (!btn) return;
      btn.addEventListener("click", function() {
        window.location.href = "index.html";
      });
    })();

    // ---- Exit button -> bye.html and reset auth ----
    (function() {
      const btn = document.getElementById("exit-btn");
      if (!btn) return;
      btn.addEventListener("click", function() {
        try { sessionStorage.removeItem("maxbits-auth"); } catch(e) {}
        window.location.href = "bye.html";
      });
    })();

    // ---- Digital clock ----
    function updateClock() {
      const now = new Date();
      const timeEl = document.getElementById("clock-digital");
      const dateEl = document.getElementById("clock-date");

      if (timeEl) {
        timeEl.textContent = now.toLocaleTimeString([], {
          hour: "2-digit", minute: "2-digit", second: "2-digit"
        });
      }
      if (dateEl) {
        dateEl.textContent = now.toLocaleDateString([], {
          weekday: "short", day: "2-digit", month: "short", year: "numeric"
        });
      }
    }
    setInterval(updateClock, 1000);
    updateClock();

    // ---- Weather via geolocation + Open-Meteo (best effort) ----
    (function() {
      const el = document.getElementById("weather-text");
      if (!el) return;

      function show(msg) { el.textContent = msg; }

      if (!navigator.geolocation) {
        show("Location not available.");
        return;
      }

      navigator.geolocation.getCurrentPosition(
        function(pos) {
          const lat = pos.coords.latitude.toFixed(3);
          const lon = pos.coords.longitude.toFixed(3);
          const url = "https://api.open-meteo.com/v1/forecast?latitude=" + lat +
                      "&longitude=" + lon + "&current=temperature_2m&timezone=auto";

          fetch(url)
            .then(r => r.json())
            .then(data => {
              try {
                const t = data.current.temperature_2m;
                if (typeof t === "number") show("Your location · " + t.toFixed(1) + "°C");
                else show("Your location · temperature unavailable");
              } catch (e) {
                show("Weather unavailable.");
              }
            })
            .catch(() => show("Weather unavailable."));
        },
        function() { show("Location not shared."); },
        { timeout: 5000 }
      );
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
        .replace("__PASSWORD__", ACCESS_PASSWORD)
    )


# -------------------------------------------------------------------
#  BYE PAGE
# -------------------------------------------------------------------

def _build_bye_page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MaxBits · Exit</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      margin:0; padding:0;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#020617; color:#e5e7eb;
      display:flex; align-items:center; justify-content:center;
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


# -------------------------------------------------------------------
#  ENTRY POINT
# -------------------------------------------------------------------

def build_magazine(max_reports: int = 7) -> None:
    """
    - Merge reports (reports/ + docs/ archive)
    - Copy last N into docs/reports
    - Generate docs/index.html + docs/bye.html
    """
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    raw_reports = _find_reports_merged()
    reports_for_docs = _copy_last_reports_to_docs(raw_reports, max_reports=max_reports)

    index_path = DOCS_DIR / "index.html"
    index_content = _build_index_content(reports_for_docs)
    index_path.write_text(index_content, encoding="utf-8")
    print(f"[MAG] Index generated: {index_path}")

    bye_path = DOCS_DIR / "bye.html"
    bye_content = _build_bye_page()
    bye_path.write_text(bye_content, encoding="utf-8")
    print(f"[MAG] Bye page generated: {bye_path}")


if __name__ == "__main__":
    build_magazine()
