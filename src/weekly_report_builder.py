from typing import List, Dict
from html import escape


def build_weekly_html_report(*, items: List[Dict], week_label: str) -> str:
    """
    items: lista di dict con campi:
      - date (YYYY-MM-DD)
      - title, url, source
      - what_it_is, who, what_it_does, why_it_matters, strategic_view
    """
    header = f"""
    <header style="margin-bottom: 24px;">
      <h1 style="margin:0; font-size:28px;">MaxBits · Weekly Tech Highlights</h1>
      <p style="margin:4px 0 0 0; color:#555;">Week {escape(week_label)}</p>
    </header>
    """

    if not items:
        body = "<p>No deep-dive articles found for the last 7 days.</p>"
    else:
        blocks = []
        # ordina per data decrescente
        items_sorted = sorted(items, key=lambda x: x.get("date", ""), reverse=True)

        for it in items_sorted:
            date_str = escape(it.get("date", ""))
            title = escape(it.get("title_clean") or it.get("title", ""))
            url = it.get("url") or "#"
            source = escape(it.get("source", ""))

            what = escape(it.get("what_it_is", ""))
            who = escape(it.get("who", ""))
            what_does = escape(it.get("what_it_does", ""))
            why = escape(it.get("why_it_matters", ""))
            strategic = escape(it.get("strategic_view", ""))

            block = f"""
            <article style="margin-bottom: 24px; padding-bottom:16px; border-bottom:1px solid #eee;">
              <h2 style="margin:0 0 4px 0; font-size:20px;">
                <a href="{url}" style="color:#0052CC; text-decoration:none;">{title}</a>
              </h2>
              <p style="margin:0; color:#777; font-size:13px;">
                {source} · {date_str}
              </p>
              <ul style="margin:8px 0 0 18px; padding:0; font-size:14px;">
                <li><strong>What it is:</strong> {what}</li>
                <li><strong>Who:</strong> {who}</li>
                <li><strong>What it does:</strong> {what_does}</li>
                <li><strong>Why it matters:</strong> {why}</li>
                <li><strong>Strategic view:</strong> {strategic}</li>
              </ul>
            </article>
            """
            blocks.append(block)

        body = "\n".join(blocks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Weekly Tech Highlights · Week {escape(week_label)}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; font-size:14px; color:#111; background:#fafafa; margin:0; padding:24px;">
  <div style="max-width:900px; margin:0 auto; background:#fff; padding:24px 32px; border-radius:8px; box-shadow:0 0 12px rgba(0,0,0,0.04);">
    {header}
    {body}
  </div>
</body>
</html>
"""
