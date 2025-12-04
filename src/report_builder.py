# src/report_builder.py

from __future__ import annotations
from html import escape
from typing import List, Dict


# -------------------------------------------------------
# HEADER + STORICO 7 GIORNI + PULSANTE WEEKLY
# -------------------------------------------------------

def _render_header(date_str: str) -> str:
    return f"""
<header style="margin-bottom: 24px;">
  <h1 style="margin:0; font-size:26px;">MaxBits · Daily Tech Watch</h1>
  <p style="margin:4px 0 0 0; color:#555;">Daily brief · {escape(date_str)}</p>

  <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
    <button id="open-weekly-btn"
            style="background:#0052CC; color:#fff; border:none; padding:8px 14px;
                   border-radius:6px; cursor:pointer; font-size:13px;">
      Open Weekly view (local)
    </button>
    <span style="font-size:12px; color:#777;">
      Weekly = articoli selezionati con “Add to Weekly”, salvati in locale.
    </span>
  </div>

  <section id="history-box"
           style="margin-top:14px; padding:10px 12px; border-radius:6px; background:#f5f5f5;">
    <strong style="font-size:13px;">Last 7 daily reports</strong>
    <ul id="history-list"
        style="margin:6px 0 0 16px; padding:0; font-size:12px; color:#333;">
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

    blocks = []

    for idx, item in enumerate(deep_dives):
        art_id = escape(item.get("id") or f"deep_{idx+1}")
        title = escape(item.get("title", ""))
        url = item.get("url") or "#"
        source = escape(item.get("source", ""))
        topic = escape(item.get("topic", "General"))

        block = f"""
<article style="margin-bottom:24px; padding-bottom:16px; border-bottom:1px solid #eee;">
  <h2 style="margin:0 0 4px 0; font-size:20px;">
    <a href="{url}" style="color:#0052CC; text-decoration:none;">{title}</a>
  </h2>
  <p style="margin:0; color:#777; font-size:13px;">
    {source} · Topic: <strong>{topic}</strong>
  </p>

  <ul style="margin:10px 0 0 20px; padding:0; font-size:14px;">
    <li><strong>What it is:</strong> {escape(item.get("what_it_is",""))}</li>
    <li><strong>Who:</strong> {escape(item.get("who",""))}</li>
    <li><strong>What it does:</strong> {escape(item.get("what_it_does",""))}</li>
    <li><strong>Why it matters:</strong> {escape(item.get("why_it_matters",""))}</li>
    <li><strong>Strategic view:</strong> {escape(item.get("strategic_view",""))}</li>
  </ul>

  <label style="margin-top:10px; display:inline-flex; gap:6px; font-size:13px; color:#333;">
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


# -------------------------------------------------------
# WATCHLIST
# -------------------------------------------------------

def _render_watchlist_section(title: str, items: List[Dict]) -> str:
    if not items:
        return ""

    rows = []
    for i, art in enumerate(items):
        aid = escape(art.get("id") or f"wl_{title}_{i}")
        t = escape(art.get("title",""))
        u = art.get("url") or "#"
        s = escape(art.get("source",""))

        rows.append(f"""
<li style="margin-bottom:4px;">
  <a href="{u}" style="color:#0052CC; text-decoration:none;">{t}</a>
  <span style="color:#777; font-size:12px;">({s})</span>

  <label style="margin-left:8px; font-size:12px;">
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
<section style="margin-top:18px;">
  <h3 style="margin:0 0 6px 0; font-size:16px;">{escape(title)}</h3>
  <ul style="margin:0 0 0 18px; font-size:14px; padding:0; list-style:disc;">
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

    sections = []
    for topic in order:
        items = watchlist.get(topic, [])
        if items:
            pretty = topic.replace("/", " / ") \
                           .replace("Infra","Infrastructure")
            sections.append(_render_watchlist_section(pretty, items))

    return "\n".join(sections) if sections else "<p>No watchlist items today.</p>"


# -------------------------------------------------------
# HTML GENERATION
# -------------------------------------------------------

def build_html_report(*, deep_dives, watchlist, date_str: str) -> str:
    header = _render_header(date_str)
    deep_html = _render_deep_dives(deep_dives)
    wl_html = _render_watchlist(watchlist)

    # !!! IMPORTANTE: nessuna doppia { in JS o Python crasha. Versione pulita qui sotto.
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="report-date" content="{escape(date_str)}" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>
</head>

<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             background:#fafafa; margin:0; padding:24px; color:#111;">

<div style="max-width:900px; margin:0 auto; background:white;
            padding:24px 32px; border-radius:8px; box-shadow:0 0 12px rgba(0,0,0,0.05);">

  {header}

  <section style="margin-top:30px;">
    <h2 style="margin:0 0 12px 0; font-size:22px;">3 deep-dives you should really read</h2>
    {deep_html}
  </section>

  <section style="margin-top:30px;">
    <h2 style="margin:0 0 12px 0; font-size:20px;">Curated watchlist · 3–5 links per topic</h2>
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

  function saveSel(x) {{ localStorage.setItem(KEY, JSON.stringify(x)); }}

  function setupCheckboxes() {{
    const date = document.querySelector("meta[name='report-date']").content;
    const data = loadSel();
    const todays = data[date] || [];

    document.querySelectorAll(".weekly-checkbox").forEach(cb => {{
      const id = cb.dataset.id;

      if (todays.some(a => a.id === id)) cb.checked = true;

      cb.onchange = () => {{
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
      }};
    }});
  }}

  function openWeekly() {{
    const data = loadSel();
    const dates = Object.keys(data).sort().reverse();
    const win = window.open("", "_blank");
    win.document.write("<h1>MaxBits Weekly (local)</h1>");

    dates.forEach(d => {{
      win.document.write("<h2>" + d + "</h2><ul>");
      data[d].forEach(it => {{
        win.document.write("<li><a href='" + it.url + "'>" + it.title + "</a></li>");
      }});
      win.document.write("</ul>");
    }});
  }}

  function initWeeklyBtn() {{
    document.getElementById("open-weekly-btn")
            .addEventListener("click", openWeekly);
  }}

  function initHistory() {{
    const hist = window.MAXBITS_HISTORY || [];
    const ul = document.getElementById("history-list");
    if (!ul) return;
    ul.innerHTML = hist.slice(0,7).map(it =>
      "<li><strong>" + it.date + "</strong> – " +
      "<a href='" + it.html + "'>HTML</a> · " +
      "<a href='" + it.pdf + "'>PDF</a></li>"
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


