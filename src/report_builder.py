# src/report_builder.py

from __future__ import annotations
from html import escape
from typing import List, Dict


# ------------------------------
# HEADER
# ------------------------------

def _render_header(date_str: str) -> str:
    return f"""
<header class="mb-24">
  <h1 class="title">MaxBits · Daily Tech Watch</h1>
  <p class="subtitle">High-quality technology news from around the world.</p>
  <p class="dateline">Daily brief · {escape(date_str)}</p>

  <div class="weekly-bar">
    <button id="open-weekly-btn" class="btn-primary">
      Open Weekly view (local)
    </button>
    <span class="weekly-hint">
      Weekly = articles you select with “Add to Weekly”, stored only in your browser.
    </span>
  </div>

  <section id="history-box" class="history-box">
    <strong>Last 7 daily reports</strong>
    <ul id="history-list" class="history-list">
      <!-- Filled by JS (window.MAXBITS_HISTORY) -->
    </ul>
  </section>
</header>
"""


# ------------------------------
# DEEP DIVES
# ------------------------------

def _render_deep_dives(deep_dives: List[Dict]) -> str:
    """
    deep_dives: lista di dict con chiavi:
      - id
      - title  (COPIATO 1:1 da RawArticle.title, solo escape HTML)
      - url, source, topic
      - what_it_is, who, what_it_does, why_it_matters, strategic_view
    """
    if not deep_dives:
        return "<p>No deep-dives today.</p>"

    blocks: List[str] = []

    for idx, item in enumerate(deep_dives):
        art_id = escape(item.get("id") or f"deep_{idx+1}")

        # 👉 NESSUNA “pulizia intelligente”: solo escape HTML
        raw_title = item.get("title", "") or ""
        title = escape(raw_title)

        url = item.get("url") or "#"
        source = escape(item.get("source", ""))
        topic = escape(item.get("topic", "General"))

        what_it_is = escape(item.get("what_it_is", ""))
        who = escape(item.get("who", ""))
        what_it_does = escape(item.get("what_it_does", ""))
        why_it_matters = escape(item.get("why_it_matters", ""))
        strategic_view = escape(item.get("strategic_view", ""))

        block = f"""
<article class="deep-dive">
  <h2 class="deep-title">
    <a href="{url}" class="link-article">{title}</a>
  </h2>
  <p class="deep-meta">
    {source} · Topic: <strong>{topic}</strong>
  </p>

  <ul class="deep-list">
    <li><strong>What it is:</strong> {what_it_is}</li>
    <li><strong>Who:</strong> {who}</li>
    <li><strong>What it does:</strong> {what_it_does}</li>
    <li><strong>Why it matters:</strong> {why_it_matters}</li>
    <li><strong>Strategic view:</strong> {strategic_view}</li>
  </ul>

  <label class="weekly-label">
    <input type="checkbox"
           class="weekly-checkbox"
           data-id="{art_id}"
           data-title="{title}"
           data-url="{url}"
           data-source="{source}">
    Add to Weekly
  </label>
</article>
"""
        blocks.append(block)

    return "\n".join(blocks)


# ------------------------------
# WATCHLIST
# ------------------------------

def _render_watchlist_section(title: str, items: List[Dict]) -> str:
    if not items:
        return ""

    rows: List[str] = []
    for i, art in enumerate(items):
        aid = escape(art.get("id") or f"wl_{title}_{i}")

        raw_title = art.get("title", "") or ""
        t = escape(raw_title)   # anche qui: zero manipolazioni, solo escape

        u = art.get("url") or "#"
        s = escape(art.get("source", ""))

        rows.append(f"""
<li class="watch-item">
  <a href="{u}" class="link-article">{t}</a>
  <span class="watch-source">({s})</span>
  <label class="weekly-label small">
    <input type="checkbox"
           class="weekly-checkbox"
           data-id="{aid}"
           data-title="{t}"
           data-url="{u}"
           data-source="{s}">
    Add to Weekly
  </label>
</li>
""")

    return f"""
<section class="watch-section">
  <h3 class="watch-title">{escape(title)}</h3>
  <ul class="watch-list">
    {''.join(rows)}
  </ul>
</section>
"""


def _render_watchlist(watchlist: Dict[str, List[Dict]]) -> str:
    order = [
        "TV/Streaming",
        "Telco/5G",
        "Media/Platforms",
        "AI/Cloud/Quantum",
        "Space/Infra",
        "Robotics/Automation",
        "Broadcast/Video",
        "Satellite/Satcom",
    ]

    sections: List[str] = []

    for topic in order:
        items = watchlist.get(topic, [])
        if not items:
            continue

        pretty = topic.replace("/", " / ").replace("Infra", "Infrastructure")
        sections.append(_render_watchlist_section(pretty, items))

    if not sections:
        return "<p>No watchlist items today.</p>"

    return "\n".join(sections)


# ------------------------------
# MAIN HTML
# ------------------------------

def build_html_report(*, deep_dives, watchlist, date_str: str) -> str:
    header = _render_header(date_str)
    deep_html = _render_deep_dives(deep_dives)
    wl_html = _render_watchlist(watchlist)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="report-date" content="{escape(date_str)}" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>

  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      font-size: 14px;
      color: #111;
      background: #f5f5f7;
      margin: 0;
      padding: 24px;
    }}
    .page {{
      max-width: 900px;
      margin: 0 auto;
      background: #ffffff;
      padding: 24px 32px 32px;
      border-radius: 8px;
      box-shadow: 0 0 12px rgba(0, 0, 0, 0.05);
    }}

    .title {{
      margin: 0;
      font-size: 26px;
      letter-spacing: 0.02em;
    }}
    .subtitle {{
      margin: 2px 0 0 0;
      font-size: 13px;
      color: #666;
    }}
    .dateline {{
      margin: 4px 0 0 0;
      font-size: 13px;
      color: #555;
    }}

    h2 {{
      font-size: 20px;
      margin: 0 0 10px 0;
    }}
    h3 {{
      font-size: 16px;
      margin: 0 0 6px 0;
    }}

    .mb-24 {{ margin-bottom: 24px; }}

    .weekly-bar {{
      margin-top: 12px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .btn-primary {{
      background: #0052cc;
      color: #fff;
      border: none;
      padding: 7px 14px;
      border-radius: 6px;
      font-size: 13px;
      cursor: pointer;
    }}
    .btn-primary:hover {{
      background: #003f9e;
    }}
    .weekly-hint {{
      font-size: 12px;
      color: #777;
    }}

    .history-box {{
      margin-top: 14px;
      padding: 10px 12px;
      border-radius: 6px;
      background: #f3f4f6;
    }}
    .history-list {{
      margin: 6px 0 0 16px;
      padding: 0;
      list-style: disc;
      font-size: 12px;
      color: #333;
    }}

    .deep-dive {{
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #eee;
      page-break-inside: avoid;
    }}
    .deep-title {{
      margin: 0 0 4px 0;
      font-size: 19px;
    }}
    .deep-meta {{
      margin: 0;
      font-size: 12px;
      color: #777;
    }}
    .deep-list {{
      margin: 10px 0 0 20px;
      padding: 0;
      font-size: 14px;
    }}
    .deep-list li {{
      margin-bottom: 4px;
    }}
    .weekly-label {{
      margin-top: 8px;
      display: inline-flex;
      gap: 6px;
      align-items: center;
      font-size: 12px;
      color: #333;
    }}
    .weekly-label.small {{
      font-size: 11px;
    }}

    .watch-section {{
      margin-top: 18px;
      page-break-inside: avoid;
    }}
    .watch-title {{
      margin: 0 0 4px 0;
      font-size: 15px;
    }}
    .watch-list {{
      margin: 2px 0 0 18px;
      padding: 0;
      list-style: disc;
      font-size: 14px;
    }}
    .watch-item {{
      margin-bottom: 4px;
    }}
    .watch-source {{
      font-size: 12px;
      color: #777;
      margin-left: 4px;
    }}

    .link-article {{
      color: #0052cc;
      text-decoration: none;
    }}
    .link-article:hover {{
      text-decoration: underline;
    }}

    @page {{
      margin: 16mm 14mm;
    }}
  </style>
</head>

<body>
  <div class="page">
    {header}

    <section style="margin-top: 28px;">
      <h2>3 deep-dives you should really read</h2>
      {deep_html}
    </section>

    <section style="margin-top: 28px;">
      <h2>Curated watchlist · 3–5 links per topic</h2>
      {wl_html}
    </section>
  </div>

  <script>
  (function() {{
    const KEY = "maxbits_weekly_selections_v1";

    function loadSelections() {{
      try {{
        const raw = localStorage.getItem(KEY);
        return raw ? JSON.parse(raw) : {{}};
      }} catch (e) {{
        console.warn("[Weekly] Cannot parse selections:", e);
        return {{}};
      }}
    }}

    function saveSelections(data) {{
      try {{
        localStorage.setItem(KEY, JSON.stringify(data));
      }} catch (e) {{
        console.warn("[Weekly] Cannot save selections:", e);
      }}
    }}

    function setupCheckboxes() {{
      const meta = document.querySelector("meta[name='report-date']");
      if (!meta) return;
      const dateStr = meta.content;
      const data = loadSelections();
      const todayList = data[dateStr] || [];

      document.querySelectorAll(".weekly-checkbox").forEach(cb => {{
        const id = cb.dataset.id;
        if (!id) return;

        if (todayList.some(x => x.id === id)) {{
          cb.checked = true;
        }}

        cb.addEventListener("change", () => {{
          const entry = {{
            id: cb.dataset.id,
            title: cb.dataset.title,
            url: cb.dataset.url,
            source: cb.dataset.source
          }};

          const list = data[dateStr] || [];
          const idx = list.findIndex(x => x.id === entry.id);

          if (cb.checked) {{
            if (idx === -1) list.push(entry);
          }} else {{
            if (idx !== -1) list.splice(idx, 1);
          }}

          data[dateStr] = list;
          saveSelections(data);
        }});
      }});
    }}

    function openWeeklyView() {{
      const data = loadSelections();
      const dates = Object.keys(data).sort().reverse();
      const win = window.open("", "_blank");
      if (!win) {{
        alert("Popup blocked. Allow pop-ups for this site to see the weekly view.");
        return;
      }}

      let html = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>MaxBits · Weekly Selection</title>";
      html += "<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:14px;background:#f5f5f7;margin:0;padding:24px;}}";
      html += ".page{{max-width:900px;margin:0 auto;background:#fff;padding:24px 32px;border-radius:8px;box-shadow:0 0 12px rgba(0,0,0,0.05);}}";
      html += "h1{{font-size:22px;margin:0 0 10px 0;}} h2{{font-size:16px;margin:18px 0 6px 0;}} ul{{margin:4px 0 0 18px;}}</style></head><body>";
      html += "<div class='page'><h1>MaxBits · Weekly Selection (local)</h1>";
      html += "<p style='color:#555;font-size:13px;'>This page is generated locally from your selections. It is not stored on the server.</p>";

      if (!dates.length) {{
        html += "<p>No weekly selections yet.</p>";
      }} else {{
        dates.forEach(d => {{
          const items = data[d] || [];
          if (!items.length) return;
          html += "<h2>Day " + d + "</h2><ul>";
          items.forEach(it => {{
            const t = it.title || "";
            const u = it.url || "#";
            const s = it.source || "";
            html += "<li><a href='" + u + "' target='_blank' rel='noopener'>" + t + "</a> ";
            html += "<span style='color:#777;font-size:12px;'>(" + s + ")</span></li>";
          }});
          html += "</ul>";
        }});
      }}

      html += "</div></body></html>";
      win.document.open();
      win.document.write(html);
      win.document.close();
    }}

    function initWeeklyButton() {{
      const btn = document.getElementById("open-weekly-btn");
      if (!btn) return;
      btn.addEventListener("click", openWeeklyView);
    }}

    function initHistoryBox() {{
      const history = window.MAXBITS_HISTORY || [];
      const ul = document.getElementById("history-list");
      if (!ul || !history.length) return;

      ul.innerHTML = history.slice(0, 7).map(item => (
        "<li><strong>" + item.date + "</strong> – " +
        "<a href='" + item.html + "' target='_blank' rel='noopener'>HTML</a> · " +
        "<a href='" + item.pdf + "' target='_blank' rel='noopener'>PDF</a></li>"
      )).join("");
    }}

    document.addEventListener("DOMContentLoaded", () => {{
      setupCheckboxes();
      initWeeklyButton();
      initHistoryBox();
    }});
  }})();
  </script>
</body>
</html>
"""
