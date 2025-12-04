# src/weekly_report_builder.py

from __future__ import annotations
from typing import List, Dict
from html import escape


def _render_header(week_label: str) -> str:
    return f"""
<header style="margin-bottom: 20px;">
  <h1 style="margin:0; font-size:26px;">MaxBits · Weekly Tech Brief</h1>
  <p style="margin:4px 0 0 0; color:#555; font-size:13px;">
    Top 15 user–selected stories · {escape(week_label)}
  </p>
  <p style="margin:8px 0 0 0; color:#777; font-size:12px;">
    Ranked by number of selections (votes) across the week. Each item includes a structured view:
    <em>What it is · Who · What it does · Why it matters · Strategic view</em>.
  </p>
</header>
"""


def _render_article_block(idx: int, art: Dict) -> str:
    title = escape(art.get("title", ""))
    url = art.get("url") or "#"
    source = escape(art.get("source", ""))
    topic = escape(art.get("topic", ""))
    votes = art.get("votes", 0)

    what_it_is = escape(art.get("what_it_is", ""))
    who = escape(art.get("who", ""))
    what_it_does = escape(art.get("what_it_does", ""))
    why_it_matters = escape(art.get("why_it_matters", ""))
    strategic_view = escape(art.get("strategic_view", ""))

    topic_str = f" · Topic: {escape(topic)}" if topic else ""
    votes_str = f"{votes} vote{'s' if votes != 1 else ''}"

    return f"""
<article style="margin-bottom:20px; padding-bottom:14px; border-bottom:1px solid #eee; page-break-inside:avoid;">
  <h2 style="margin:0 0 4px 0; font-size:18px;">
    {idx}. <a href="{url}" style="color:#0052CC; text-decoration:none;">{title}</a>
  </h2>
  <p style="margin:0; color:#777; font-size:12px;">
    {source}{topic_str} · <strong>{votes_str}</strong>
  </p>

  <ul style="margin:8px 0 0 20px; padding:0; font-size:13px;">
    <li><strong>What it is:</strong> {what_it_is}</li>
    <li><strong>Who:</strong> {who}</li>
    <li><strong>What it does:</strong> {what_it_does}</li>
    <li><strong>Why it matters:</strong> {why_it_matters}</li>
    <li><strong>Strategic view:</strong> {strategic_view}</li>
  </ul>
</article>
"""


def build_weekly_html_report(*, articles: List[Dict], week_label: str) -> str:
    """
    Costruisce l'HTML del weekly report.
    'articles' deve essere già:
      - limitato a max 15
      - ordinato per votes decrescente
      - con tutti i 5 campi riempiti
    """
    header = _render_header(week_label)
    blocks = []

    if not articles:
        blocks.append("<p>No weekly selections available for this week.</p>")
    else:
        for idx, art in enumerate(articles, start=1):
            blocks.append(_render_article_block(idx, art))

    body = "\n".join(blocks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Weekly Tech Brief · {escape(week_label)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
      font-size:13px;
      color:#111;
      background:#ffffff;
      margin:12mm;
      line-height:1.4;
    }}
    h1, h2 {{ page-break-after: avoid; }}
    article {{ page-break-inside: avoid; }}
    a {{ color:#0052CC; }}
    ul {{ margin-top:4px; }}
    li {{ margin-bottom:3px; }}
  </style>
</head>
<body>
  <div style="max-width:900px; margin:0 auto;">
    {header}
    {body}
  </div>
</body>
</html>
"""
