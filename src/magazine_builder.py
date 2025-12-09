from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import List, Dict


BASE_DIR = Path(__file__).resolve().parent.parent

# Sorgente report (generati da main.py)
HTML_SRC_DIR = BASE_DIR / "reports" / "html"
PDF_SRC_DIR = BASE_DIR / "reports" / "pdf"

# Cartella pubblica per GitHub Pages
DOCS_DIR = BASE_DIR / "docs"
HTML_DST_DIR = DOCS_DIR / "reports" / "html"
PDF_DST_DIR = DOCS_DIR / "reports" / "pdf"


def _find_reports() -> List[Dict]:
    """
    Cerca tutti i report HTML in reports/html, estrae la data dal nome file,
    e costruisce una lista ordinata per data (desc).

    Ritorna una lista di dict:
      {
        "date": "YYYY-MM-DD",
        "html_file": Path(...),
        "pdf_file": Path(...) or None,
      }
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
        src_html = r["html_file"]
        dst_html = HTML_DST_DIR / src_html.name
        shutil.copy2(src_html, dst_html)
        print(f"[MAG] Copied HTML for {date} -> {dst_html}")

        dst_pdf = None
        if r["pdf_file"] is not None:
            src_pdf = r["pdf_file"]
            dst_pdf = PDF_DST_DIR / src_pdf.name
            shutil.copy2(src_pdf, dst_pdf)
            print(f"[MAG] Copied PDF for {date} -> {dst_pdf}")
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


def _build_index_content(reports_for_docs: List[Dict]) -> str:
    """
    Genera docs/index.html con:
      - header con logo immagine + toggle light/dark
      - main hero (gradient, stile moderno) con iframe ultimo report
      - sidebar con clock, previous 6 reports, market snapshot
    """
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

    # Template HTML con logo immagine, hero moderno, theme toggle, sidebar
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
      gap: 14px;
    }

    .brand-logo img {
      height: 40px;
      width: auto;
      display: block;
    }

    .brand-text {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .brand-title {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      letter-spacing: 0.02em;
    }

    .brand-subtitle {
      margin: 0;
      font-size: 12px;
      color: var(--text-muted);
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

    /* Clock */
    .clock-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }

    .clock {
      position: relative;
      width: 120px;
      height: 120px;
      border-radius: 999px;
      border: 4px solid #e5e7eb;
      background: radial-gradient(circle at 30% 20%, #ffffff, #f3f4f6);
      box-shadow: 0 6px 14px rgba(15,23,42,0.15) inset;
    }

    body[data-theme="dark"] .clock {
      border-color: #111827;
      background: radial-gradient(circle at 30% 20%, #020617, #020617);
      box-shadow: 0 6px 16px rgba(0,0,0,0.8) inset;
    }

    .clock-center {
      position: absolute;
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: #111827;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      z-index: 10;
    }

    body[data-theme="dark"] .clock-center {
      background: #e5e7eb;
    }

    .hand {
      position: absolute;
      width: 2px;
      background: #111827;
      left: 50%;
      top: 50%;
      transform-origin: bottom center;
      transform: translateX(-50%) rotate(0deg);
    }

    body[data-theme="dark"] .hand {
      background: #e5e7eb;
    }

    .hand.hour { height: 32px; border-radius: 999px; }
    .hand.minute { height: 44px; border-radius: 999px; }
    .hand.second {
      height: 52px;
      border-radius: 999px;
      background: var(--accent-dark);
    }

    body[data-theme="dark"] .hand.second {
      background: #38bdf8;
    }

    .clock-label {
      margin: 0;
      font-size: 12px;
      color: var(--text-muted);
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
        <div class="brand-logo">
          <img src="assets/maxbits-logo.png" alt="MaxBits logo">
        </div>
        <div class="brand-text">
          <p class="brand-title">Daily Tech Intelligence</p>
          <p class="brand-subtitle">Telco · Media · AI · Cloud · Space · Patents</p>
        </div>
      </div>

      <div style="display:flex; align-items:center; gap:10px;">
        <div class="tagline">Daily briefing</div>
        <div class="theme-toggle" id="theme-toggle">
          <div class="theme-thumb"></div>
        </div>
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
          <span class="badge-today">Today’s edition</span>
        </div>

        <div class="iframe-wrapper">
          <iframe src="__LATEST_HTML__" loading="lazy"></iframe>
        </div>
      </main>

      <!-- SIDEBAR -->
      <aside class="sidebar">

        <!-- CLOCK -->
        <section class="side-card">
          <h2 class="side-title">Local time</h2>
          <div class="clock-container">
            <div class="clock" id="analog-clock">
              <div class="hand hour" id="clock-hour"></div>
              <div class="hand minute" id="clock-minute"></div>
              <div class="hand second" id="clock-second"></div>
              <div class="clock-center"></div>
            </div>
            <p class="clock-label" id="clock-label-text"></p>
          </div>
        </section>

        <!-- PREVIOUS REPORTS -->
        <section class="side-card">
          <h2 class="side-title">Previous 6 reports</h2>
          <ul class="side-report-list">
__PREVIOUS_LIST__
          </ul>
        </section>

        <!-- MARKET SNAPSHOT -->
        <section class="side-card">
          <h2 class="side-title">Market snapshot*</h2>
          <ul class="market-list" id="market-list">
            <li class="market-item" data-symbol="GOOGL">
              <div class="market-left">Google<span class="market-symbol">GOOGL</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
            <li class="market-item" data-symbol="TSLA">
              <div class="market-left">Tesla<span class="market-symbol">TSLA</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
            <li class="market-item" data-symbol="AAPL">
              <div class="market-left">Apple<span class="market-symbol">AAPL</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
            <li class="market-item" data-symbol="NVDA">
              <div class="market-left">NVIDIA<span class="market-symbol">NVDA</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
            <li class="market-item" data-symbol="META">
              <div class="market-left">Meta<span class="market-symbol">META</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
            <li class="market-item" data-symbol="MSFT">
              <div class="market-left">Microsoft<span class="market-symbol">MSFT</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
            <li class="market-item" data-symbol="AMZN">
              <div class="market-left">Amazon<span class="market-symbol">AMZN</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
            <li class="market-item" data-symbol="BTC-USD">
              <div class="market-left">Bitcoin<span class="market-symbol">BTC</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
            <li class="market-item" data-symbol="ETH-USD">
              <div class="market-left">Ethereum<span class="market-symbol">ETH</span></div>
              <div>
                <span class="market-price">—</span>
                <span class="market-change">…</span>
              </div>
            </li>
          </ul>
          <p style="margin:6px 0 0; font-size:10px; color:#9ca3af;">
            *Prices loaded client-side from a public API. Values are indicative only.
          </p>
        </section>

      </aside>
    </div>

    <footer>
      MaxBits is generated automatically from curated RSS sources, CEO statements and patent feeds.
      Reports are published as static HTML &amp; PDF via GitHub Pages.
    </footer>
  </div>

  <script>
    // THEME TOGGLE (light / dark)
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

    // Analog clock
    function updateClock() {
      const now = new Date();
      const sec = now.getSeconds();
      const min = now.getMinutes();
      const hr  = now.getHours();

      const secDeg = sec * 6;
      const minDeg = min * 6 + sec * 0.1;
      const hrDeg  = ((hr % 12) / 12) * 360 + min * 0.5;

      const h = document.getElementById('clock-hour');
      const m = document.getElementById('clock-minute');
      const s = document.getElementById('clock-second');

      if (h && m && s) {
        h.style.transform = 'translateX(-50%) rotate(' + hrDeg + 'deg)';
        m.style.transform = 'translateX(-50%) rotate(' + minDeg + 'deg)';
        s.style.transform = 'translateX(-50%) rotate(' + secDeg + 'deg)';
      }

      const label = document.getElementById('clock-label-text');
      if (label) {
        label.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      }
    }
    setInterval(updateClock, 1000);
    updateClock();

    // Market data (best effort – potrebbe avere limiti CORS)
    async function loadMarketData() {
      const items = document.querySelectorAll('#market-list .market-item');
      if (!items.length) return;

      const symbols = Array.from(items).map(li => li.dataset.symbol).join(',');
      const url = 'https://query1.finance.yahoo.com/v7/finance/quote?symbols=' + encodeURIComponent(symbols);

      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        const quotes = (data.quoteResponse && data.quoteResponse.result) || [];

        const map = {};
        quotes.forEach(q => {
          if (q.symbol) map[q.symbol] = q;
        });

        items.forEach(li => {
          const sym = li.dataset.symbol;
          const q = map[sym];
          const priceEl = li.querySelector('.market-price');
          const changeEl = li.querySelector('.market-change');
          if (!priceEl || !changeEl) return;

          if (!q || typeof q.regularMarketPrice === 'undefined') {
            priceEl.textContent = 'n/a';
            changeEl.textContent = '';
            return;
          }

          const price = q.regularMarketPrice;
          const pct = q.regularMarketChangePercent;

          priceEl.textContent = price.toFixed(2);

          let cls = 'market-change';
          let txt = '';
          if (typeof pct === 'number') {
            if (pct > 0) {
              cls += ' up';
              txt = '+' + pct.toFixed(2) + '%';
            } else if (pct < 0) {
              cls += ' down';
              txt = pct.toFixed(2) + '%';
            } else {
              txt = '0.00%';
            }
          }
          changeEl.className = cls;
          changeEl.textContent = txt;
        });

      } catch (e) {
        console.warn('[Market] failed to load prices:', e);
      }
    }

    loadMarketData();
  </script>

</body>
</html>
"""

    return (
        template
        .replace("__LATEST_DATE__", latest_date)
        .replace("__LATEST_HTML__", latest_html_rel)
        .replace("__PREVIOUS_LIST__", previous_list_html)
    )


def build_magazine(max_reports: int = 7) -> None:
    """
    Entry point:
      - legge i report sorgente
      - copia gli ultimi N in docs/reports
      - genera docs/index.html con layout moderno + sidebar + theme toggle
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
