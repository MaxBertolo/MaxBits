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


def _build_recent_reports_list(reports_for_docs: List[Dict]) -> str:
    """
    Costruisce l'HTML della lista "Recent reports" (gli ultimi N).
    """
    if not reports_for_docs:
        return """
      <p style="font-size:13px; color:#6b7280;">
        No reports available yet. Once the first report is generated, it will appear here.
      </p>
"""

    rows: List[str] = []
    for r in reports_for_docs:
        date = r["date"]
        html_rel = f"reports/html/{r['html_file'].name}"
        pdf_rel = f"reports/pdf/{r['pdf_file'].name}" if r["pdf_file"] else None

        if pdf_rel:
            links_html = (
                f"<a href=\"{html_rel}\">HTML</a>"
                f"<span class=\"dot\">·</span>"
                f"<a href=\"{pdf_rel}\">PDF</a>"
            )
        else:
            links_html = f"<a href=\"{html_rel}\">HTML</a>"

        row = f"""
        <li class="reports-item">
          <div class="reports-item-main">
            <span class="reports-date">{date}</span>
            <span class="reports-meta">MaxBits · Daily Tech Watch</span>
          </div>
          <div class="reports-links">
            {links_html}
          </div>
        </li>"""
        rows.append(row)

    return "\n".join(rows)


def _build_index_content(reports_for_docs: List[Dict]) -> str:
    """
    Costruisce il contenuto completo di docs/index.html usando lo stile
    minimal & clean, popolato automaticamente con:
      - Latest report (hero)
      - Recent reports (lista ultimi N)
    """
    # Caso: nessun report disponibile
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
    <p>No reports available yet. Once the first daily report is generated, this page will show the latest report and the last 7 days.</p>
  </div>
</body>
</html>
"""

    latest = reports_for_docs[0]
    latest_date = latest["date"]
    latest_html_rel = f"reports/html/{latest['html_file'].name}"
    latest_pdf_rel = f"reports/pdf/{latest['pdf_file'].name}" if latest["pdf_file"] else None

    # Sezione hero (latest report)
    if latest_pdf_rel:
        hero_actions_html = f"""
      <div class="hero-actions">
        <a class="btn-primary" href="{latest_html_rel}">
          Open today’s report
        </a>
        <a class="btn-secondary" href="{latest_pdf_rel}">
          Download PDF
          <span class="badge">Daily</span>
        </a>
      </div>
"""
    else:
        hero_actions_html = f"""
      <div class="hero-actions">
        <a class="btn-primary" href="{latest_html_rel}">
          Open today’s report
        </a>
      </div>
"""

    # Lista recent reports
    recent_list_html = _build_recent_reports_list(reports_for_docs)

    # CSS + struttura statica (uguale al template che ti avevo dato)
    head_and_style = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Daily Tech Intelligence</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <style>
    :root {
      --bg: #f5f5f7;
      --card-bg: #ffffff;
      --accent: #0052cc;
      --accent-soft: #e6efff;
      --text-main: #111827;
      --text-muted: #6b7280;
      --border: #e5e7eb;
      --radius-lg: 14px;
      --shadow-soft: 0 14px 30px rgba(15, 23, 42, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      padding: 32px 16px 40px;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
                   system-ui, -system-ui, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text-main);
    }

    .page {
      max-width: 960px;
      margin: 0 auto;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 24px;
    }

    .brand {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .brand-title {
      margin: 0;
      font-size: 24px;
      letter-spacing: 0.03em;
    }

    .brand-subtitle {
      margin: 0;
      font-size: 13px;
      color: var(--text-muted);
    }

    .tag {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      padding: 4px 8px;
      border-radius: 999px;
      background: #eef2ff;
      color: #4f46e5;
      border: 1px solid #e0e7ff;
      white-space: nowrap;
    }

    .hero {
      background: radial-gradient(circle at top left, #eef2ff, #f9fafb);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-soft);
      padding: 20px 20px 18px;
      margin-bottom: 20px;
      border: 1px solid #e5e7f0;
    }

    .hero-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 10px;
    }

    .hero-title {
      margin: 0;
      font-size: 20px;
    }

    .hero-text {
      margin: 4px 0 0;
      font-size: 13px;
      color: var(--text-muted);
    }

    .hero-pill {
      font-size: 12px;
      padding: 4px 9px;
      border-radius: 999px;
      background: #ecfdf3;
      color: #047857;
      border: 1px solid #bbf7d0;
      white-space: nowrap;
    }

    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 4px;
    }

    .btn-primary {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 8px 14px;
      font-size: 13px;
      border-radius: 999px;
      border: none;
      cursor: pointer;
      background: var(--accent);
      color: #fff;
      text-decoration: none;
      font-weight: 500;
    }

    .btn-secondary {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 8px 12px;
      font-size: 12px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.9);
      color: var(--text-muted);
      text-decoration: none;
      gap: 6px;
    }

    .btn-secondary span.badge {
      padding: 2px 6px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 10px;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .section {
      margin-top: 22px;
    }

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 6px;
    }

    .section-title {
      margin: 0;
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--text-muted);
    }

    .section-subtitle {
      margin: 0;
      font-size: 12px;
      color: var(--text-muted);
    }

    .reports-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      grid-template-columns: minmax(0,1fr);
      gap: 8px;
    }

    .reports-item {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 10px;
      padding: 8px 10px;
      border-radius: 10px;
      background: var(--card-bg);
      border: 1px solid var(--border);
    }

    .reports-item-main {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .reports-date {
      font-size: 13px;
      font-weight: 500;
    }

    .reports-meta {
      font-size: 11px;
      color: var(--text-muted);
    }

    .reports-links {
      display: flex;
      gap: 8px;
      font-size: 11px;
      white-space: nowrap;
    }

    .reports-links a {
      text-decoration: none;
      color: var(--accent);
      font-weight: 500;
    }

    .reports-links span.dot {
      color: #d1d5db;
    }

    footer {
      margin-top: 26px;
      font-size: 11px;
      color: var(--text-muted);
      text-align: left;
    }

    footer a {
      color: var(--accent);
      text-decoration: none;
    }

    @media (min-width: 720px) {
      body {
        padding-top: 40px;
      }
      .hero-top {
        align-items: center;
      }
    }
  </style>
</head>

<body>
  <div class="page">

    <!-- HEADER -->
    <header>
      <div class="brand">
        <h1 class="brand-title">MaxBits Mag</h1>
        <p class="brand-subtitle">
          Daily tech intelligence across Telco · Media · AI · Data · Space.
        </p>
      </div>
      <span class="tag">Daily Briefing</span>
    </header>
"""

    hero_section = f"""
    <!-- HERO / LATEST REPORT -->
    <section class="hero">
      <div class="hero-top">
        <div>
          <h2 class="hero-title">Latest report · {latest_date}</h2>
          <p class="hero-text">
            Curated news + deep-dives designed for busy tech leaders. Updated every morning.
          </p>
        </div>
        <div class="hero-pill">
          HTML &amp; PDF · 3 deep-dives · Watchlist
        </div>
      </div>
{hero_actions_html.strip()}
    </section>
"""

    recent_section = f"""
    <!-- RECENT REPORTS -->
    <section class="section">
      <div class="section-header">
        <h3 class="section-title">Recent reports</h3>
        <p class="section-subtitle">Last {len(reports_for_docs)} days · HTML &amp; PDF</p>
      </div>

      <ul class="reports-list">
{recent_list_html}
      </ul>
    </section>
"""

    footer = """
    <footer>
      MaxBits is generated automatically from curated RSS sources and AI summaries.
      Reports are published as static HTML &amp; PDF via GitHub Pages.
    </footer>
  </div>
</body>
</html>
"""

    return head_and_style + hero_section + recent_section + footer


def build_magazine(max_reports: int = 7) -> None:
    """
    Entry point:
      - legge i report sorgente
      - copia gli ultimi N in docs/reports
      - genera docs/index.html con template minimal & clean
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
