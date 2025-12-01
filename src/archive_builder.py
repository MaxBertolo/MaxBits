from pathlib import Path
from datetime import datetime
import shutil
from typing import List, Dict


BASE_DIR = Path(__file__).resolve().parent.parent

REPORT_HTML_DIR = BASE_DIR / "reports" / "html"
REPORT_PDF_DIR = BASE_DIR / "reports" / "pdf"

DOCS_ROOT = BASE_DIR / "docs"
DOCS_DAILY = DOCS_ROOT / "daily"

MAX_DAYS = 7  # quanti report tenere nel mini-sito


def _parse_date_from_name(name: str) -> str | None:
    """
    Da 'report_2025-12-01.html' estrae '2025-12-01'.
    Ritorna None se il formato non torna.
    """
    if not name.startswith("report_"):
        return None
    if "." not in name:
        return None
    core = name.split(".", 1)[0]  # report_2025-12-01
    parts = core.split("_", 1)
    if len(parts) != 2:
        return None
    date_str = parts[1]
    # quick sanity check
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    return date_str


def _collect_reports() -> List[Dict]:
    """
    Legge tutti gli HTML in reports/html e costruisce
    una lista di {date_str, html_src, pdf_src}.
    """
    reports: List[Dict] = []

    if not REPORT_HTML_DIR.exists():
        return reports

    for html_file in REPORT_HTML_DIR.glob("report_*.html"):
        date_str = _parse_date_from_name(html_file.name)
        if not date_str:
            continue

        pdf_file = REPORT_PDF_DIR / f"report_{date_str}.pdf"
        reports.append(
            {
                "date": date_str,
                "html_src": html_file,
                "pdf_src": pdf_file if pdf_file.exists() else None,
            }
        )

    # Ordiniamo per data desc (più recente prima)
    reports.sort(key=lambda x: x["date"], reverse=True)
    return reports


def _copy_reports_to_docs(reports: List[Dict]) -> List[Dict]:
    """
    Copia gli ultimi MAX_DAYS report in docs/daily/.
    Ritorna la lista effettiva dei report copiati.
    """
    DOCS_ROOT.mkdir(exist_ok=True)
    DOCS_DAILY.mkdir(parents=True, exist_ok=True)

    selected = reports[:MAX_DAYS]

    keep_filenames = set()

    for r in selected:
        date_str = r["date"]
        html_src = r["html_src"]
        pdf_src = r["pdf_src"]

        html_dst = DOCS_DAILY / html_src.name
        shutil.copy2(html_src, html_dst)

        keep_filenames.add(html_dst.name)

        if pdf_src is not None:
            pdf_dst = DOCS_DAILY / pdf_src.name
            shutil.copy2(pdf_src, pdf_dst)
            keep_filenames.add(pdf_dst.name)

        # aggiungiamo le path di destinazione
        r["html_dst"] = html_dst
        if pdf_src is not None:
            r["pdf_dst"] = DOCS_DAILY / pdf_src.name
        else:
            r["pdf_dst"] = None

    # pulizia: rimuovi file vecchi in docs/daily
    for f in DOCS_DAILY.glob("*"):
        if f.name not in keep_filenames:
            f.unlink()

    return selected


def _build_index_html(reports: List[Dict]) -> str:
    """
    Crea la homepage del mini-sito (docs/index.html)
    con elenco ultimi report e embed del più recente.
    """
    if not reports:
        body = """
        <p>No reports available yet. Come back tomorrow 👀</p>
        """
        latest_embed = ""
    else:
        # lista dei report
        items_html: List[str] = []
        for r in reports:
            date_str = r["date"]
            html_rel = f"daily/{r['html_dst'].name}"
            if r["pdf_dst"] is not None:
                pdf_rel = f"daily/{r['pdf_dst'].name}"
                pdf_link = f' · <a href="{pdf_rel}" target="_blank">PDF</a>'
            else:
                pdf_link = ""

            items_html.append(
                f'<li><strong>{date_str}</strong>: '
                f'<a href="{html_rel}" target="_blank">HTML</a>{pdf_link}</li>'
            )

        body = f"""
        <p>Below you find the last {len(reports)} daily reports (max {MAX_DAYS} days).</p>
        <ul>
          {''.join(items_html)}
        </ul>
        """

        # embed dell'ultimo (il più recente)
        latest = reports[0]
        latest_rel = f"daily/{latest['html_dst'].name}"
        latest_embed = f"""
        <h2 style="margin-top:32px;">Latest report · {latest['date']}</h2>
        <iframe src="{latest_rel}" 
                style="width:100%; height:70vh; border:1px solid #ddd; border-radius:8px;"
                loading="lazy">
        </iframe>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Max Bits Magazine · Daily Tech Watch</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
             background:#f5f5f5; margin:0; padding:16px;">
  <div style="max-width:960px; margin:0 auto; background:#fff; padding:24px 28px;
              border-radius:10px; box-shadow:0 0 16px rgba(0,0,0,0.04);">

    <header style="margin-bottom:24px;">
      <h1 style="margin:0 0 4px 0;">Max Bits Magazine</h1>
      <p style="margin:0; color:#666;">Curated daily tech & telco intelligence · last {MAX_DAYS} days</p>
    </header>

    {body}

    {latest_embed}
  </div>
</body>
</html>
"""
    return html


def main():
    print("[ARCHIVE] Collecting reports...")
    reports = _collect_reports()
    if not reports:
        print("[ARCHIVE] No reports found in reports/html. Nothing to do.")
        return

    print(f"[ARCHIVE] Found {len(reports)} reports, keeping last {MAX_DAYS}...")
    selected = _copy_reports_to_docs(reports)

    print(f"[ARCHIVE] Selected {len(selected)} reports for docs/daily")

    index_html = _build_index_html(selected)
    index_path = DOCS_ROOT / "index.html"
    index_path.write_text(index_html, encoding="utf-8")

    print(f"[ARCHIVE] Home page written to {index_path}")


if __name__ == "__main__":
    main()

