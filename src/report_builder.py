from pathlib import Path
from datetime import datetime
import re
from typing import List, Tuple


# Root del repo (cartella padre di src/)
BASE_DIR = Path(__file__).resolve().parent.parent


def _collect_last_reports(max_days: int = 7) -> List[Tuple[datetime.date, str, Path, Path | None]]:
    """
    Cerca i file reports/html/report_YYYY-MM-DD.html,
    li ordina per data (più recente prima) e ne ritorna al massimo max_days.

    Ritorna lista di tuple:
      (data, date_str, html_path, pdf_path_or_None)
    """
    html_dir = BASE_DIR / "reports" / "html"
    pdf_dir = BASE_DIR / "reports" / "pdf"

    if not html_dir.exists():
        print("[ARCHIVE] reports/html directory does not exist.")
        return []

    files = sorted(html_dir.glob("report_*.html"))
    items: List[Tuple[datetime.date, str, Path, Path | None]] = []

    for f in files:
        m = re.match(r"report_(\d{4}-\d{2}-\d{2})\.html", f.name)
        if not m:
            continue
        date_str = m.group(1)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        pdf_path = pdf_dir / f"report_{date_str}.pdf"
        if not pdf_path.exists():
            pdf_path = None

        items.append((dt, date_str, f, pdf_path))

    items.sort(key=lambda x: x[0], reverse=True)
    return items[:max_days]


def build_archive(max_days: int = 7) -> None:
    """
    Costruisce il mini-sito Max Bits Magazine:

      - Copia gli ultimi N report HTML in docs/daily/report_YYYY-MM-DD.html
      - Copia gli eventuali PDF corrispondenti in docs/daily/report_YYYY-MM-DD.pdf
      - Cancella HTML/PDF più vecchi di N giorni in docs/daily/
      - Genera docs/index.html con la lista degli ultimi N giorni (più recente per primo)
    """
    docs_dir = BASE_DIR / "docs"
    daily_dir = docs_dir / "daily"

    docs_dir.mkdir(exist_ok=True)
    daily_dir.mkdir(parents=True, exist_ok=True)

    items = _collect_last_reports(max_days=max_days)
    if not items:
        print("[ARCHIVE] No reports found, skipping archive build.")
        return

    keep_filenames: set[str] = set()

    # 1) Copia i report selezionati in docs/daily/
    for dt, date_str, html_src, pdf_src in items:
        html_dest = daily_dir / f"report_{date_str}.html"
        html_text = html_src.read_text(encoding="utf-8")
        html_dest.write_text(html_text, encoding="utf-8")
        keep_filenames.add(html_dest.name)

        if pdf_src is not None and pdf_src.exists():
            pdf_dest = daily_dir / f"report_{date_str}.pdf"
            pdf_dest.write_bytes(pdf_src.read_bytes())
            keep_filenames.add(pdf_dest.name)

    # 2) Rimuovi HTML/PDF più vecchi in docs/daily
    for f in daily_dir.glob("report_*.*"):
        if f.name not in keep_filenames:
            print(f"[ARCHIVE] Removing old file from docs/daily: {f.name}")
            f.unlink()

    # 3) Costruisci docs/index.html
    cards: List[str] = []
    for dt, date_str, _html_src, pdf_src in items:
        pdf_link_html = ""
        if pdf_src is not None:
            pdf_href = f"daily/report_{date_str}.pdf"
            pdf_link_html = (
                f'<a href="{pdf_href}" '
                f'style="font-size:13px; text-decoration:none; color:#444;">'
                f'Download PDF</a>'
            )

        cards.append(
            f"""
        <article style="border-radius:8px; border:1px solid #eee;
                        padding:16px 20px; margin-bottom:16px; background:#fff;">
          <h2 style="margin:0 0 4px 0; font-size:18px;">{date_str}</h2>
          <p style="margin:0 0 8px 0; color:#777; font-size:13px;">
            MaxBits · Daily Tech Intelligence
          </p>
          <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
            <a href="daily/report_{date_str}.html"
               style="font-size:14px; text-decoration:none; color:#0052CC;">
              Open full report →
            </a>
            {pdf_link_html}
          </div>
        </article>
        """
        )

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Max Bits Magazine · Daily Tech Watch</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
             font-size:14px; color:#111; background:#fafafa; margin:0; padding:16px;">

  <div style="max-width:900px; margin:0 auto;">

    <header style="margin:8px 0 16px 0;">
      <h1 style="margin:0 0 4px 0; font-size:26px;">Max Bits Magazine</h1>
      <p style="margin:0; color:#555; font-size:13px;">
        Daily tech intelligence · last {max_days} days · newest first
      </p>
    </header>

    {''.join(cards)}

  </div>
</body>
</html>
"""
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"[ARCHIVE] Updated docs/index.html with last {len(items)} reports.")


if __name__ == "__main__":
    build_archive(max_days=7)
