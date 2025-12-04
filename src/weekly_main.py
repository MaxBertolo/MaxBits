from pathlib import Path
from datetime import datetime, timedelta
import json
import yaml

from .weekly_report_builder import build_weekly_html_report
from .pdf_export import html_to_pdf
from .email_sender import send_report_email


BASE_DIR = Path(__file__).resolve().parent.parent


def load_config():
    config_path = BASE_DIR / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main():
    cfg = load_config()
    out_cfg = cfg.get("output", {})
    json_dir = Path(out_cfg.get("json_dir", "reports/json"))
    weekly_html_dir = Path(out_cfg.get("weekly_html_dir", "reports/weekly_html"))
    weekly_pdf_dir = Path(out_cfg.get("weekly_dir", "reports/weekly"))

    weekly_html_dir.mkdir(parents=True, exist_ok=True)
    weekly_pdf_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().date()
    # ISO week, esempio "2025-W48"
    iso_year, iso_week, _ = today.isocalendar()
    week_label = f"{iso_year}-W{iso_week:02d}"

    items = []

    # ultimi 7 giorni (escluso oggi)
    for delta in range(1, 8):
        d = today - timedelta(days=delta)
        date_str = d.strftime("%Y-%m-%d")
        json_path = json_dir / f"deep_dives_{date_str}.json"
        if not json_path.exists():
            continue
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                day_items = json.load(jf)
            # aggiungi info data a ciascun item
            for it in day_items:
                it["date"] = date_str
                items.append(it)
        except Exception as e:
            print("[WEEKLY] Error reading", json_path, ":", repr(e))

    if not items:
        print("[WEEKLY] No deep-dive items found for the last 7 days. Exiting.")
        return

    print(f"[WEEKLY] Building weekly report with {len(items)} items for week {week_label}")

    html = build_weekly_html_report(items=items, week_label=week_label)

    html_path = weekly_html_dir / f"weekly_{week_label}.html"
    pdf_path = weekly_pdf_dir / f"weekly_{week_label}.pdf"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("[WEEKLY] Saved weekly HTML to:", html_path)

    html_to_pdf(html, str(pdf_path))
    print("[WEEKLY] Saved weekly PDF to:", pdf_path)

    # opzionale: invia weekly via email
    try:
        send_report_email(
            pdf_path=str(pdf_path),
            date_str=f"Weekly {week_label}",
            html_path=str(html_path),
        )
        print("[WEEKLY][EMAIL] Weekly email sent (if SMTP configured).")
    except Exception as e:
        print("[WEEKLY][EMAIL] Error sending weekly email:", repr(e))


if __name__ == "__main__":
    main()
