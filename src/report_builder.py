from typing import List, Dict
from html import escape

# Etichette leggibili per i topic
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
    """Intestazione del report."""
    return f"""
    <header style="margin-bottom: 24px;">
      <h1 style="margin:0; font-size:28px;">MaxBits · Daily Tech Watch</h1>
      <p style="margin:4px 0 0 0; color:#555;">Daily brief · {escape(date_str)}</p>
    </header>
    """


def _render_deep_dives(deep_dives: List[Dict]) -> str:
    """Rendering dei 3 articoli deep-dive."""

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
    """Una sezione della watchlist (es. Telco & 5G)."""

    safe_title = escape(title)

    # Nessun articolo per questo topic
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
            f"""
            <li style="margin-bottom:6px; list-style:none;">
              <strong>
                <a href="{url}" style="color:#0052CC; text-decoration:none;">
                  {atitle}
                </a>
              </strong><br/>
              <span style="color:#777; font-size:12px;">
                {source}
              </span>
            </li>
            """
        )

    return f"""
    <section style="margin-top:16px;">
      <h3 style="margin:0 0 4px 0; font-size:16px;">{safe_title}</h3>
      <ul style="margin:4px 0 0 18px; padding:0; font-size:14px;">
        {''.join(lis)}
      </ul>
    </section>
    """


def _render_watchlist(watchlist: Dict[str, List[Dict]]) -> str:
    """
    watchlist = dict(topic_key -> lista articoli)

    Qui garantiamo che *tutti i topic* definiti compaiano nel report,
    anche se vuoti.
    """

    sections: List[str] = []
    for topic_key, label in TOPIC_LABELS.items():
        items = watchlist.get(topic_key, []) or []
        sections.append(_render_watchlist_section(label, items))

    return "\n".join(sections)


def build_html_report(*, deep_dives, watchlist, date_str: str) -> str:
    """Costruisce l’intero HTML del report."""

    header = _render_header(date_str)
    deep_dives_html = _render_deep_dives(deep_dives)
    watchlist_html = _render_watchlist(watchlist)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>
</head>

<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
             font-size:14px; color:#111; background:#fafafa; margin:0; padding:24px;">

  <div style="max-width:900px; margin:0 auto; background:#fff;
              padding:24px 32px; border-radius:8px;
              box-shadow:0 0 12px rgba(0,0,0,0.04);">

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
