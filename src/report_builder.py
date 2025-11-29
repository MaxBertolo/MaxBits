from typing import List, Dict
import html


def _escape(text: str) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def build_html_report(
    deep_dives: List[Dict],
    watchlist_grouped: Dict[str, List[Dict]],
    date_str: str,
) -> str:
    """
    Costruisce l'HTML del report MaxBits.

    deep_dives: lista di articoli con riassunto LLM (3 articoli max)
    watchlist_grouped: dict topic -> lista di {title, url, source}
    date_str: data in formato stringa (YYYY-MM-DD)
    """

    # -------------------------
    # HEADER / STILI
    # -------------------------
    html_parts: List[str] = []

    html_parts.append(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits Daily Tech Report - {html.escape(date_str)}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #f4f4f7;
      color: #222;
    }}
    .page {{
      max-width: 1000px;
      margin: 0 auto;
      padding: 24px 32px 40px 32px;
      background-color: #ffffff;
    }}
    h1, h2, h3, h4 {{
      font-weight: 600;
      margin-top: 0;
    }}
    h1 {{
      font-size: 26px;
      margin-bottom: 4px;
    }}
    h2 {{
      font-size: 20px;
      margin-top: 28px;
      margin-bottom: 12px;
    }}
    h3 {{
      font-size: 16px;
      margin-bottom: 8px;
    }}
    p {{
      line-height: 1.4;
      margin: 4px 0;
      font-size: 13px;
    }}
    .subtitle {{
      font-size: 13px;
      color: #666;
      margin-bottom: 16px;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 100px;
      font-size: 11px;
      background-color: #e4ecff;
      color: #1f4fbf;
      margin-right: 6px;
    }}
    .deep-dive-card {{
      border-radius: 8px;
      border: 1px solid #e0e0e5;
      padding: 12px 14px;
      margin-bottom: 14px;
      background-color: #fafbff;
    }}
    .deep-dive-title {{
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 4px;
    }}
    .meta {{
      font-size: 11px;
      color: #777;
      margin-bottom: 6px;
    }}
    .section-label {{
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #555;
      margin-top: 6px;
      margin-bottom: 2px;
    }}
    a {{
      color: #1f4fbf;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .watchlist-topic {{
      margin-top: 10px;
      margin-bottom: 4px;
      font-size: 14px;
      font-weight: 600;
      color: #333;
    }}
    .watchlist-list {{
      margin: 0;
      padding-left: 18px;
    }}
    .watchlist-item {{
      font-size: 12px;
      margin-bottom: 2px;
    }}
    .small-note {{
      font-size: 11px;
      color: #777;
      margin-top: 6px;
    }}
    hr {{
      border: none;
      border-top: 1px solid #e2e2e7;
      margin: 24px 0 18px 0;
    }}
  </style>
</head>
<body>
  <div class="page">
"""
    )

    # -------------------------
    # TITOLO PRINCIPALE
    # -------------------------
    html_parts.append(
        f"""
    <h1>MaxBits Daily Tech Report</h1>
    <div class="subtitle">
      Date: {html.escape(date_str)} &nbsp;&nbsp;|&nbsp;&nbsp;
      Focus: Telco · Media · Streaming · AI · Cloud · Space · Infrastructure
    </div>
"""
    )

    # =========================
    # 1) DEEP DIVE SECTION
    # =========================
    html_parts.append(
        """
    <h2>1. Deep Dive & Executive Summary (3 key stories)</h2>
    <p class="small-note">
      Curated selection of a few high-impact stories with structured analysis for Telco / Media / Tech decision-making.
    </p>
"""
    )

    if not deep_dives:
        html_parts.append(
            "<p>No deep-dive stories available for today.</p>"
        )
    else:
        for idx, art in enumerate(deep_dives, start=1):
            title = _escape(art.get("title", ""))
            url = _escape(art.get("url", ""))
            source = _escape(art.get("source", ""))
            published = _escape(art.get("published_at", ""))

            cos_e = _escape(art.get("cos_e", ""))
            chi = _escape(art.get("chi", ""))
            cosa_fa = _escape(art.get("cosa_fa", ""))
            perche = _escape(art.get("perche_interessante", ""))
            pov = _escape(art.get("pov", ""))

            html_parts.append(
                f"""
    <div class="deep-dive-card">
      <div class="deep-dive-title">
        {idx}. {title}
      </div>
      <div class="meta">
        Source: {source}
"""
            )
            if published:
                html_parts.append(f" &nbsp;|&nbsp; Published: {published}")
            if url:
                html_parts.append(
                    f' &nbsp;|&nbsp; <a href="{url}" target="_blank">Open article</a>'
                )
            html_parts.append("</div>")

            # Cos'è
            if cos_e:
                html_parts.append(
                    f"""
      <div class="section-label">WHAT IT IS</div>
      <p>{cos_e}</p>
"""
                )

            # Chi
            if chi:
                html_parts.append(
                    f"""
      <div class="section-label">WHO</div>
      <p>{chi}</p>
"""
                )

            # Cosa fa
            if cosa_fa:
                html_parts.append(
                    f"""
      <div class="section-label">WHAT IT DOES</div>
      <p>{cosa_fa}</p>
"""
                )

            # Perché è interessante
            if perche:
                html_parts.append(
                    f"""
      <div class="section-label">WHY IT MATTERS</div>
      <p>{perche}</p>
"""
                )

            # Punto di vista strategico
            if pov:
                html_parts.append(
                    f"""
      <div class="section-label">STRATEGIC VIEW</div>
      <p>{pov}</p>
"""
                )

            html_parts.append("</div>")  # fine card

    # Separatore
    html_parts.append("<hr />")

    # =========================
    # 2) WATCHLIST SECTION
    # =========================
    html_parts.append(
        """
    <h2>2. Watchlist by Topic (up to 15 headlines)</h2>
    <p class="small-note">
      Headlines worth monitoring in the next days. For details, use the links and, if needed,
      request deeper AI analysis for selected stories.
    </p>
"""
    )

    if not watchlist_grouped:
        html_parts.append("<p>No additional headlines in the watchlist today.</p>")
    else:
        # Ordiniamo i topic per stabilità
        for topic in sorted(watchlist_grouped.keys()):
            items = watchlist_grouped[topic]
            if not items:
                continue

            html_parts.append(
                f'<div class="watchlist-topic">{_escape(topic)}</div>\n'
            )
            html_parts.append('<ul class="watchlist-list">')

            for it in items:
                t_title = _escape(it.get("title", ""))
                t_url = _escape(it.get("url", ""))
                t_source = _escape(it.get("source", ""))

                html_parts.append("<li class=\"watchlist-item\">")
                if t_url:
                    html_parts.append(
                        f'<a href="{t_url}" target="_blank">{t_title}</a>'
                    )
                else:
                    html_parts.append(t_title)

                if t_source:
                    html_parts.append(f" &nbsp;<span style='color:#777'>[{t_source}]</span>")
                html_parts.append("</li>")

            html_parts.append("</ul>")

    # FOOTER
    html_parts.append(
        """
    <hr />
    <p class="small-note">
      MaxBits · Experimental daily tech intelligence. This report is automatically generated from public news feeds
      and AI summarization. Please verify critical information against the original sources.
    </p>
  </div> <!-- page -->
</body>
</html>
"""
    )

    return "".join(html_parts)
