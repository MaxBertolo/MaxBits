from pathlib import Path
from datetime import datetime
import re


# Root del repo (cartella padre di src/)
BASE_DIR = Path(__file__).resolve().parent.parent


def _collect_last_reports(max_days: int = 7):
    """
    Cerca i file reports/html/report_YYYY-MM-DD.html,
    li ordina per data (più recente prima) e ne ritorna al massimo max_days.
    """
    reports_dir = BASE_DIR / "reports" / "html"
    if not reports_dir.exists():
        print("[ARCHIVE] reports/html directory does not exist.")
        return []

    files = sorted(reports_dir.glob("report_*.html"))
    items = []

    for f in files:
        m = re.match(r"report_(\d{4}-\d{2}-\d{2})\.html", f.name)
        if not m:
            continue
        date_str = m.group(1)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        items.append((dt, date_str, f))

    # Ordina per data decrescente (più recente per primo)
    items.sort(key=lambda x: x[0], reverse=True)

    # Ne teniamo solo max_days
    return items[:max_days]


def build_archive(max_days: int = 7):
    """
    Costruisce il "mini-sito" Max Bits Magazine:

      - Copia gli ultimi N report HTML in docs/daily/report_YYYY-MM-DD.html
      - Cancella gli HTML più vecchi di N giorni in docs/daily/
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

    # 1) Copia i report selezionati in docs/daily/
    keep_filenames = set()

    for dt, date_str, src in items:
        dest = daily_dir / f"report_{date_str}.html"
        html_text = src.read_text(encoding="utf-8")
        dest.write_text(html_text, encoding="utf-8")
        keep_filenames.add(dest.name)

    # 2) Rimuovi gli HTML più vecchi in docs/daily (oltre la finestra dei N giorni)
    for f in daily_dir.glob("report_*.html"):
        if f.name not in keep_filenames:
            print(f"[ARCHIVE] Removing old report from docs/daily: {f.name}")
            f.unlink()

    # 3) Costruisci docs/index.html (mini-sito)
    cards = []
    for dt, date_str, _src in items:
        # Mostriamo la data in formato YYYY-MM-DD (pulito e stabile)
        cards.append(
            f"""
        <article style="border-radius:8px; border:1px solid #eee; padding:16px 20px; margin-bottom:16px; background:#fff;">
          <h2 style="margin:0 0 4px 0; font-size:18px;">{date_str}</h2>
          <p style="margin:0 0 8px 0; color:#777; font-size:13px;">Daily Tech Intelligence</p>
          <a href="daily/report_{date_str}.html"
             style="font-size:14px; text-decoration:none; color:#0052CC;">
            Open full report →
          </a>
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
        Daily tech intelligence · last 7 days · newest first
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
