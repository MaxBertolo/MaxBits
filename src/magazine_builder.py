# src/magazine_builder.py

from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import List, Dict


# Cartelle nel workspace del workflow
BASE_DIR = Path(__file__).resolve().parent.parent

# Qui il daily genera i report
HTML_SRC_DIR = BASE_DIR / "reports" / "html"
PDF_SRC_DIR = BASE_DIR / "reports" / "pdf"

# Qui vive il sito GitHub Pages
DOCS_DIR = BASE_DIR / "docs"
HTML_DST_DIR = DOCS_DIR / "reports" / "html"
PDF_DST_DIR = DOCS_DIR / "reports" / "pdf"


def _find_reports() -> List[Dict]:
    """
    Trova tutti i report_*.html in reports/html, e se esiste
    anche il PDF associato in reports/pdf.

    Ritorna: lista di dict con chiavi:
      - date (YYYY-MM-DD)
      - html_file (Path)
      - pdf_file (Path | None)
    Ordinata per data decrescente.
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


def _copy_last_reports_to_docs(reports: List[Dict]) -> List[Dict]:
    """
    Copia negli /docs/reports/html|pdf gli ultimi 7 report.
    Ritorna una nuova lista con i path di destinazione, usati per i link.
    """
    HTML_DST_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DST_DIR.mkdir(parents=True, exist_ok=True)

    selected = reports[:7]
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


def _build_history_list(reports: List[Dict]) -> str:
    """
    Costruisce l'HTML della lista "Last 7 daily reports".

    ATTENZIONE: a questo punto 'reports' contiene i path
    dentro /docs/reports/... perché è il risultato di
    _copy_last_reports_to_docs().
    I link sono quindi relativi a docs/index.html:
      reports/html/...
      reports/pdf/...
    """
    if not reports:
        return "<li>No reports available yet.</li>"

    items_html: List[str] = []
    for r in reports:
        date = r["date"]
        html_rel = f"reports/html/{r['html_file'].name}"
        if r["pdf_file"] is not None:
            pdf_rel = f"reports/pdf/{r['pdf_file'].name}"
        else:
            pdf_rel = None

        row = (
            f"<li><strong>{date}</strong> – "
            f"<a href=\"{html_rel}\" target=\"_blank\" rel=\"noopener\">HTML</a>"
        )
        if pdf_rel:
            row += f" · <a href=\"{pdf_rel}\" target=\"_blank\" rel=\"noopener\">PDF</a>"
        row += "</li>"

        items_html.append(row)

    return "\n".join(items_html)


def _build_latest_embed(reports: List[Dict]) -> str:
    """
    Embed dell'ultimo report disponibile (il più recente).
    Anche qui usiamo i path già copiati in /docs/reports.
    """
    if not reports:
        return "<p>No latest report to display.</p>"

    latest = reports[0]
    date = latest["date"]
    html_rel = f"reports/html/{latest['html_file'].name}"

    return f"""
<h2 style="margin:16px 0 8px 0; font-size:18px;">Latest report · {date}</h2>
<iframe
  src="{html_rel}"
  loading="lazy"
  style="
    width: 100%;
    height: 80vh;
    border: 1px solid #ddd;
    border-radius: 8px;
    box-shadow: 0 0 8px rgba(0,0,0,0.04);
  ">
</iframe>
"""


def build_magazine() -> None:
    """
    Genera /docs/index.html con:
      - copia degli ultimi 7 report dentro /docs/reports/html|pdf
      - lista "Last 7 daily reports"
      - embed dell'ultimo daily
    """
    raw_reports = _find_reports()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Copia gli ultimi 7 dentro docs/
    reports_for_docs = _copy_last_reports_to_docs(raw_reports)

    history_html = _build_history_list(reports_for_docs)
    latest_html = _build_latest_embed(reports_for_docs)

    index_path = DOCS_DIR / "index.html"

    index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits Mag · Daily Tech Reports</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             font-size:14px; color:#111; background:#fafafa; margin:0; padding:24px;">

  <div style="max-width:900px; margin:0 auto; background:white;
              padding:24px 32px; border-radius:8px;
              box-shadow:0 0 12px rgba(0,0,0,0.06);">

    <header style="margin-bottom:16px;">
      <h1 style="margin:0; font-size:24px;">MaxBits Mag</h1>
      <p style="margin:4px 0 0 0; color:#555; font-size:13px;">
        Below you find the last daily reports (max 7 days).
      </p>
    </header>

    <section style="margin-bottom:16px;">
      <ul style="margin:0 0 0 18px; padding:0; font-size:13px; color:#333;">
        {history_html}
      </ul>
    </section>

    <section>
      {latest_html}
    </section>

  </div>
</body>
</html>
"""

    index_path.write_text(index_content, encoding="utf-8")
    print(f"[MAG] MaxBits magazine index generated at: {index_path}")


if __name__ == "__main__":
    build_magazine()
