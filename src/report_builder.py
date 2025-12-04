from typing import List, Dict, Optional
from html import escape


# Chiave interna -> etichetta da mostrare
TOPIC_LABELS = {
    "TV/Streaming": "TV & Streaming",
    "Telco/5G": "Telco & 5G",
    "Media/Platforms": "Media · Platforms · Social",
    "AI/Cloud/Quantum": "AI · Cloud · Quantum",
    "Space/Infra": "Space · Infrastructure",
    "Robotics/Automation": "Robotics & Automation",
    "Broadcast/Video": "Broadcast · Video Tech",
    "Satellite/Satcom": "Satellite & Satcom",
}


def _render_header(date_str: str) -> str:
    return f"""
    <header style="margin-bottom: 24px;">
      <h1 style="margin:0; font-size:28px;">MaxBits · Daily Tech Watch</h1>
      <p style="margin:4px 0 0 0; color:#555;">Daily brief · {escape(date_str)}</p>
    </header>
    """


def _render_history(recent_reports: List[Dict], weekly_pdf: Optional[str]) -> str:
    """
    recent_reports: lista di dict {date: 'YYYY-MM-DD', href: 'path/to/pdf'}
    weekly_pdf: href dell'ultimo weekly report (o None)
    """
    # se non c'è storico né weekly, non mostriamo la sezione
    if not recent_reports and not weekly_pdf:
        return ""

    items_html: List[str] = []
    for item in recent_reports:
        d = escape(item.get("date", ""))
        href = item.get("href") or "#"
        items_html.append(
            f'<li style="margin-bottom:4px;">'
            f'<a href="{href}" style="color:#0052CC; text-decoration:none;">'
            f'Daily report · {d}</a></li>'
        )

    history_list = ""
    if items_html:
        history_list = (
            "<ul style='margin:4px 0 0 18px; padding:0; list-style:disc; font-size:14px;'>"
            + "".join(items_html)
            + "</ul>"
        )
    else:
        history_list = (
            "<p style='margin:4px 0 0 0; font-size:13px; color:#777;'>"
            "No previous daily reports found for the last 6 days."
            "</p>"
        )

    weekly_button = ""
    if weekly_pdf:
        weekly_button = f"""
        <div style="margin-top:12px;">
          <a href="{weekly_pdf}"
             style="display:inline-block; padding:8px 14px; border-radius:4px;
                    background:#0052CC; color:#fff; text-decoration:none;
                    font-size:13px; font-weight:500;">
            Open latest weekly report
          </a>
        </div>
        """

    return f"""
    <section style="margin-bottom:24px;">
      <h2 style="margin:0 0 4px 0; font-size:18px;">Last 7 days · navigation</h2>
      <p style="margin:2px 0 4px 0; font-size:13px; color:#555;">
        Quick links to the last 6 daily PDFs and the most recent weekly summary.
      </p>
      {history_list}
      {weekly_button}
    </section>
    """


def _render_deep_dives(deep_dives: List[Dict]) -> str:
    if not deep_dives:
        return "<p>No deep–dive articles for today.</p>"

    blocks: List[str] = []
    for item in deep_dives:
        title = escape(item.get("title_clean") or item.get("title", ""))
        url = item.get("url") or "#"
        source = escape(item.get("source", ""))
        topic = escape(item.get("topic", "General"))

        what = escape(item.get("what_it_is", ""))
        who = escape(item.get("who", ""))
        what_does = escape(item.get("what_it_does", ""))
        why = escape(item.get("why_it_matters", ""))
        strategic = escape(item.get("strategic_view", ""))

        block = f"""
        <article style="margin-bottom: 24px; padding-bottom:16px; border-bottom:1px solid #eee;">
          <h2 style="margin:0 0 4px 0; font-size:20px;">
            <a href="{url}" style="color:#0052CC; text-decoration:none;">{title}</a>
          </h2>
          <p style="margin:0; color:#777; font-size:13px;">
            {source} · Topic: <strong>{topic}</strong>
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

    return "\n".join(blocks)


def _render_watchlist_section(title: str, items: List[Dict]) -> str:
    safe_title = escape(title)

    if not items:
        return f"""
        <section style="margin-top:16px;">
          <h3 style="margin:0 0 4px 0; font-size:16px;">{safe_title}</h3>
          <p style="margin:2px 0 0 0; font-size:13px; color:#777;">
            No headlines selected today.
          </p>
        </section>
        """

    lis: List[str] = []
    for art in items:
        atitle = escape(art.get("title", ""))
        url = art.get("url") or "#"
        source = escape(art.get("source", ""))
        lis.append(
            f'<li style="margin-bottom:4px;"><a href="{url}" '
            f'style="color:#0052CC; text-decoration:none;">{atitle}</a>'
            f' <span style="color:#777; font-size:12px;">({source})</span></li>'
        )

    return f"""
    <section style="margin-top:16px;">
      <h3 style="margin:0 0 4px 0; font-size:16px;">{safe_title}</h3>
      <ul style="margin:4px 0 0 18px; padding:0; font-size:14px; list-style:disc;">
        {''.join(lis)}
      </ul>
    </section>
    """


def _render_watchlist(watchlist: Dict[str, List[Dict]]) -> str:
    """
    watchlist è un dict: topic_key -> lista articoli.
    Mostriamo SEMPRE le 8 sezioni, anche se vuote.
    """
    sections_html: List[str] = []

    for topic_key, label in TOPIC_LABELS.items():
        items = watchlist.get(topic_key, []) or []
        sections_html.append(_render_watchlist_section(label, items))

    return "\n".join(sections_html)


def build_html_report(
    *,
    deep_dives,
    watchlist,
    date_str: str,
    recent_reports: Optional[List[Dict]] = None,
    weekly_pdf: Optional[str] = None,
) -> str:
    """
    Costruisce l'HTML completo.

    Parametri:
      - deep_dives: lista di 3 articoli "full" (già arricchiti dal summarizer)
      - watchlist: dict categoria -> lista articoli (solo titolo+url+source)
      - date_str: 'YYYY-MM-DD'
      - recent_reports: lista di dict {date, href} per gli ultimi 6 giorni
      - weekly_pdf: href dell'ultimo weekly PDF (o None)
    """
    recent_reports = recent_reports or []

    header = _render_header(date_str)
    history_html = _render_history(recent_reports, weekly_pdf)
    deep_dives_html = _render_deep_dives(deep_dives)
    watchlist_html = _render_watchlist(watchlist)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; font-size:14px; color:#111; background:#fafafa; margin:0; padding:24px;">
  <div style="max-width:900px; margin:0 auto; background:#fff; padding:24px 32px; border-radius:8px; box-shadow:0 0 12px rgba(0,0,0,0.04);">
    {header}

    {history_html}

    <section style="margin-bottom:32px;">
      <h2 style="margin:0 0 12px 0; font-size:22px;">3 deep-dives you should really read</h2>
      {deep_dives_html}
    </section>

    <section>
      <h2 style="margin:0 0 8px 0; font-size:20px;">Curated watchlist · 3–5 links per topic</h2>
      {watchlist_html}
    </section>
  </div>
</body>
</html>
"""
