from typing import List, Dict
from html import escape


def _render_header(date_str: str) -> str:
    return f"""
    <header style="margin-bottom: 24px;">
      <h1 style="margin:0; font-size:28px;">MaxBits · Daily Tech Watch</h1>
      <p style="margin:4px 0 0 0; color:#555;">Daily brief · {escape(date_str)}</p>
    </header>
    """


def _render_deep_dives(deep_dives: List[Dict]) -> str:
    if not deep_dives:
        return "<p>No deep–dive articles for today.</p>"

    blocks = []
    for item in deep_dives:
        title = escape(item.get("title", ""))
        url = item.get("url") or "#"
        source = escape(item.get("source", ""))
        topic = escape(item.get("topic", "General"))
        what = escape(item.get("what_it_is", ""))
        who = escape(item.get("who", ""))
        impact = escape(item.get("impact", ""))
        future = escape(item.get("future_outlook", ""))
        key_points = escape(item.get("key_points", ""))

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
            <li><strong>Impact:</strong> {impact}</li>
            <li><strong>Future outlook:</strong> {future}</li>
            <li><strong>Key points:</strong> {key_points}</li>
          </ul>
        </article>
        """
        blocks.append(block)

    return "\n".join(blocks)


def _render_watchlist_section(title: str, items: List[Dict]) -> str:
    if not items:
        return ""

    lis = []
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
      <h3 style="margin:0 0 4px 0; font-size:16px;">{escape(title)}</h3>
      <ul style="margin:4px 0 0 18px; padding:0; font-size:14px; list-style:disc;">
        {''.join(lis)}
      </ul>
    </section>
    """


def _render_watchlist(watchlist: Dict[str, List[Dict]]) -> str:
    if not watchlist:
        return "<p>No additional watchlist items today.</p>"

    sections_html = []

    tv_items = watchlist.get("TV/Streaming", [])
    if tv_items:
        sections_html.append(_render_watchlist_section("TV & Streaming", tv_items))

    telco_items = watchlist.get("Telco/5G", [])
    media_items = watchlist.get("Media/Platforms", [])
    ai_items = watchlist.get("AI/Cloud/Quantum", [])
    infra_items = watchlist.get("Space/Infra", [])

    merged_telco = telco_items
    merged_media = media_items
    merged_ai = ai_items
    merged_infra = infra_items

    if merged_telco:
        sections_html.append(_render_watchlist_section("Telco · 5G · Networks", merged_telco))
    if merged_media:
        sections_html.append(_render_watchlist_section("Media · Platforms · Social", merged_media))
    if merged_ai:
        sections_html.append(_render_watchlist_section("AI · Cloud · Quantum", merged_ai))
    if merged_infra:
        sections_html.append(_render_watchlist_section("Space · Infrastructure", merged_infra))

    return "\n".join(sections_html)


def build_html_report(*, deep_dives, watchlist, date_str: str) -> str:
    """
    Costruisce l'HTML completo.

    Parametri (devono combaciare con main.py):
      - deep_dives: lista di 3 articoli "full" (già arricchiti dal summarizer)
      - watchlist: dict categoria -> lista articoli (solo titolo+url+source)
      - date_str: 'YYYY-MM-DD'
    """
    header = _render_header(date_str)
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

 
