from __future__ import annotations
from html import escape
from typing import List, Dict


def _safe(value: str | None, default: str = "—") -> str:
    v = (value or "").strip()
    if not v:
        return default
    return escape(v)


# -------------------------------------------------------
# HEADER + STORICO 7 GIORNI + PULSANTE WEEKLY
# -------------------------------------------------------

def _render_header(date_str: str) -> str:
    return f"""
<header style="margin-bottom: 20px;">
  <h1 style="margin:0; font-size:24px;">MaxBits · Daily Tech Watch</h1>
  <p style="margin:4px 0 0 0; color:#555; font-size:13px;">
    Daily brief · {escape(date_str)}
  </p>
  <p style="margin:4px 0 0 0; color:#777; font-size:12px;">
    High-quality technology news from around the world.
  </p>

  <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
    <button id="open-weekly-btn"
            style="background:#0052CC; color:#fff; border:none; padding:6px 12px;
                   border-radius:6px; cursor:pointer; font-size:12px;">
      Open Weekly view (local)
    </button>
    <span style="font-size:11px; color:#777;">
      Weekly = articoli selezionati con “Add to Weekly”, salvati in locale nel tuo browser.
    </span>
  </div>

  <section id="history-box"
           style="margin-top:12px; padding:8px 10px; border-radius:6px; background:#f5f5f5;">
    <strong style="font-size:12px;">Last 7 daily reports</strong>
    <ul id="history-list"
        style="margin:4px 0 0 16px; padding:0; font-size:11px; color:#333;">
    </ul>
  </section>
</header>
"""


# -------------------------------------------------------
# DEEP DIVES
# -------------------------------------------------------

def _render_deep_dives(deep_dives: List[Dict]) -> str:
    if not deep_dives:
        return "<p>No deep-dives today.</p>"

    blocks: List[str] = []

    for idx, item in enumerate(deep_dives):
        art_id = escape(item.get("id") or f"deep_{idx+1}")
        title = _safe(item.get("title"))
        url = item.get("url") or "#"
        source = _safe(item.get("source"), "Unknown source")
        topic = _safe(item.get("topic"), "General")

        what_it_is = _safe(item.get("what_it_is"))
        who = _safe(item.get("who"))
        what_it_does = _safe(item.get("what_it_does"))
        why_it_matters = _safe(item.get("why_it_matters"))
        strategic_view = _safe(item.get("strategic_view"))

        blocks.append(f"""
<article style="margin-bottom:18px; padding-bottom:10px; border-bottom:1px solid #eee; page-break-inside:avoid;">
  <h2 style="margin:0 0 4px 0; font-size:18px;">
    <a href="{url}" style="color:#0052CC; text-decoration:none;">{title}</a>
  </h2>
  <p style="margin:0; color:#777; font-size:11px;">
    {source} · Topic: <strong>{topic}</strong>
  </p>

  <ul style="margin:6px 0 0 18px; padding:0; font-size:12px;">
    <li><strong>What it is:</strong> {what_it_is}</li>
    <li><strong>Who:</strong> {who}</li>
    <li><strong>What it does:</strong> {what_it_does}</li>
    <li><strong>Why it matters:</strong> {why_it_matters}</li>
    <li><strong>Strategic view:</strong> {strategic_view}</li>
  </ul>

  <label style="margin-top:6px; display:inline-flex; gap:6px; font-size:11px; color:#333;">
    <input type="checkbox"
           class="weekly-checkbox"
           data-id="{art_id}"
           data-title="{title}"
           data-url="{url}"
           data-source="{source}">
    Add to Weekly
  </label>
</article>
""")

    return "\n".join(blocks)


# -------------------------------------------------------
# WATCHLIST
# -------------------------------------------------------

def _render_watchlist_topic_block(title: str, items: List[Dict]) -> str:
    pretty = title.replace("/", " / ").replace("Infra", "Infrastructure")

    if not items:
        return f"""
<section style="margin-top:10px;">
  <h3 style="margin:0 0 2px 0; font-size:14px;">{escape(pretty)}</h3>
  <p style="margin:0; font-size:11px; color:#999;">No relevant links today.</p>
</section>
"""

    rows: List[str] = []
    for i, art in enumerate(items):
        aid = escape(art.get("id") or f"wl_{title}_{i}")
        t = _safe(art.get("title"))
        u = art.get("url") or "#"
        s = _safe(art.get("source"), "Unknown source")

        rows.append(f"""
<li style="margin-bottom:3px;">
  <a href="{u}" style="color:#0052CC; text-decoration:none;">{t}</a>
  <span style="color:#777; font-size:11px;">({s})</span>
  <label style="margin-left:8px; font-size:11px;">
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
<section style="margin-top:10px;">
  <h3 style="margin:0 0 2px 0; font-size:14px;">{escape(pretty)}</h3>
  <ul style="margin:0 0 0 16px; padding:0; font-size:12px; list-style:disc;">
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
        items = watchlist.get(topic, []) or []
        sections.append(_render_watchlist_topic_block(topic, items))

    return "\n".join(sections)


# -------------------------------------------------------
# HTML GENERATION
# -------------------------------------------------------

def build_html_report(*, deep_dives, watchlist, date_str: str) -> str:
    header = _render_header(date_str)
    deep_html = _render_deep_dives(deep_dives or [])
    wl_html = _render_watchlist(watchlist or {})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="report-date" content="{escape(date_str)}" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>
  <style>
    @page {{
      size: A4;
      margin: 12mm;
    }}
    body {{
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
      font-size:12px;
      color:#111;
      background:#ffffff;
      margin:0;
      line-height:1.4;
    }}
    a {{ color:#0052CC; }}
    article {{ page-break-inside: avoid; }}
  </style>
</head>

<body>
<div style="max-width:900px; margin:0 auto;">

  {header}

  <section style="margin-top:18px;">
    <h2 style="margin:0 0 6px 0; font-size:16px;">3 deep-dives you should really read</h2>
    {deep_html}
  </section>

  <section style="margin-top:18px;">
    <h2 style="margin:0 0 6px 0; font-size:15px;">Curated watchlist · 3–5 links per topic</h2>
    {wl_html}
  </section>

</div>

<script>
(function() {{
  const KEY = "maxbits_weekly_selections_v1";

  function loadSel() {{
    try {{ return JSON.parse(localStorage.getItem(KEY) || "{{}}" ); }}
    catch {{ return {{}}; }}
  }}

  function saveSel(x) {{
    localStorage.setItem(KEY, JSON.stringify(x));
  }}

  function setupCheckboxes() {{
    const meta = document.querySelector("meta[name='report-date']");
    if (!meta) return;
    const date = meta.content;
    const data = loadSel();
    const todays = data[date] || [];

    document.querySelectorAll(".weekly-checkbox").forEach(cb => {{
      const id = cb.dataset.id;
      if (!id) return;

      if (todays.some(a => a.id === id)) cb.checked = true;

      cb.addEventListener("change", () => {{
        const entry = {{
          id: cb.dataset.id,
          title: cb.dataset.title,
          url: cb.dataset.url,
          source: cb.dataset.source
        }};
        const arr = data[date] || [];
        const i = arr.findIndex(a => a.id === entry.id);

        if (cb.checked && i === -1) arr.push(entry);
        if (!cb.checked && i !== -1) arr.splice(i,1);

        data[date] = arr;
        saveSel(data);
      }});
    }});
  }}

  function openWeekly() {{
    const data = loadSel();
    const dates = Object.keys(data).sort().reverse();
    const win = window.open("", "_blank");
    if (!win) {{
      alert("Popup blocked: allow popups to see weekly view.");
      return;
    }}
    win.document.open();
    win.document.write("<h1>MaxBits Weekly (local)</h1>");
    dates.forEach(d => {{
      win.document.write("<h2>" + d + "</h2><ul>");
      (data[d] || []).forEach(it => {{
        win.document.write(
          "<li><a href='" + it.url + "' target='_blank'>" +
          it.title + "</a> (" + (it.source || "") + ")</li>"
        );
      }});
      win.document.write("</ul>");
    }});
    win.document.close();
  }}

  function initWeeklyBtn() {{
    const btn = document.getElementById("open-weekly-btn");
    if (btn) btn.addEventListener("click", openWeekly);
  }}

  function initHistory() {{
    const hist = window.MAXBITS_HISTORY || [];
    const ul = document.getElementById("history-list");
    if (!ul || !hist.length) return;
    ul.innerHTML = hist.slice(0,7).map(it =>
      "<li><strong>" + it.date + "</strong> – " +
      "<a href='" + it.html + "' target='_blank'>HTML</a> · " +
      "<a href='" + it.pdf + "' target='_blank'>PDF</a></li>"
    ).join("");
  }}

  document.addEventListener("DOMContentLoaded", () => {{
    setupCheckboxes();
    initWeeklyBtn();
    initHistory();
  }});
}})();
</script>

</body>
</html>
"""
