from __future__ import annotations

from html import escape
from typing import List, Dict
import json


# -------------------------------------------------------
# HEADER + STORICO 7 GIORNI + PULSANTE WEEKLY
# -------------------------------------------------------

def _render_header(date_str: str) -> str:
    return f"""
<header style="margin-bottom: 24px;">
  <h1 style="margin:0; font-size:26px;">MaxBits · Daily Tech Watch</h1>
  <p style="margin:2px 0 0 0; color:#666; font-size:13px;">
    High-quality technology news from around the world.
  </p>
  <p style="margin:4px 0 0 0; color:#555;">Daily brief · {escape(date_str)}</p>

  <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
    <button id="open-weekly-btn"
            style="background:#0052CC; color:#fff; border:none; padding:8px 14px;
                   border-radius:6px; cursor:pointer; font-size:13px;">
      Open Weekly view (local)
    </button>
    <span style="font-size:12px; color:#777;">
      Weekly = articoli selezionati con “Add to Weekly”, salvati solo nel tuo browser.
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

WATCHLIST_TOPICS_ORDER = [
    "TV/Streaming",
    "Telco/5G",
    "Media/Platforms",
    "AI/Cloud/Quantum",
    "Space/Infra",
    "Robotics/Automation",
    "Broadcast/Video",
    "Satellite/Satcom",
]


def _pretty_topic_name(topic: str) -> str:
    if topic == "Space/Infra":
        return "Space / Infrastructure"
    if topic == "AI/Cloud/Quantum":
        return "AI / Cloud / Quantum"
    if topic == "Telco/5G":
        return "Telco / 5G"
    if topic == "Media/Platforms":
        return "Media / Platforms"
    if topic == "Robotics/Automation":
        return "Robotics / Automation"
    if topic == "Broadcast/Video":
        return "Broadcast / Video"
    if topic == "Satellite/Satcom":
        return "Satellite / Satcom"
    if topic == "TV/Streaming":
        return "TV / Streaming"
    return topic.replace("/", " / ")


def _render_watchlist_section(topic: str, items: List[Dict]) -> str:
    """
    Se items è vuoto, mostra comunque la sezione con il messaggio:
    "No notable articles for this topic today."
    """
    title = escape(_pretty_topic_name(topic))

    if not items:
        return f"""
<section style="margin-top:18px;">
  <h3 style="margin:0 0 4px 0; font-size:16px;">{title}</h3>
  <p style="margin:2px 0 0 0; font-size:13px; color:#777;">
    No notable articles for this topic today.
  </p>
</section>
"""

    rows = []
    for i, art in enumerate(items):
        aid = escape(art.get("id") or f"wl_{topic}_{i}")
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
  <h3 style="margin:0 0 6px 0; font-size:16px;">{title}</h3>
  <ul style="margin:0 0 0 18px; font-size:14px; padding:0; list-style:disc;">
    {''.join(rows)}
  </ul>
</section>
"""


def _render_watchlist(watchlist: Dict[str, List[Dict]]) -> str:
    """
    Mostra SEMPRE tutte le categorie in WATCHLIST_TOPICS_ORDER.
    Se una categoria non ha articoli, mostra un messaggio esplicito.
    """
    sections = []
    for topic in WATCHLIST_TOPICS_ORDER:
        items = watchlist.get(topic, []) or []
        sections.append(_render_watchlist_section(topic, items))

    return "\n".join(sections)


# -------------------------------------------------------
# CEO POV SECTION
# -------------------------------------------------------

def _render_ceo_pov(ceo_items: List[Dict]) -> str:
    if not ceo_items:
        return """
<section style="margin-top:30px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">CEO POV – AI & Space Economy</h2>
  <p style="margin:0; font-size:13px; color:#777;">
    No relevant CEO quotes detected today.
  </p>
</section>
"""

    cards = []
    for item in ceo_items:
        ceo = escape(item.get("ceo", ""))
        company = escape(item.get("company", ""))
        topic = escape(item.get("topic", ""))
        quote = escape(item.get("quote", ""))
        source = escape(item.get("source", ""))
        url = item.get("source_url") or "#"
        ctx = escape(item.get("context", "") or "")
        published_at = escape(item.get("published_at", "") or "")
        tags = item.get("tags") or []
        tags_str = ", ".join(escape(t) for t in tags)

        cards.append(f"""
<article style="margin-bottom:16px; padding:10px 12px; border-radius:6px; border:1px solid #eee; background:#fafafa;">
  <p style="margin:0 0 4px 0; font-size:13px; color:#555;">
    <strong>{ceo}</strong> · {company} · <span style="color:#006644;">{topic}</span>
  </p>
  <p style="margin:4px 0; font-size:14px; line-height:1.4;">
    “{quote}”
  </p>
  <p style="margin:4px 0 0 0; font-size:12px; color:#777;">
    {ctx if ctx else ""} {("· " + published_at) if published_at else ""}
    {("· Tags: " + tags_str) if tags_str else ""}
  </p>
  <p style="margin:4px 0 0 0; font-size:12px; color:#555;">
    Source: <a href="{url}" target="_blank" rel="noopener" style="color:#0052CC;">{source}</a>
  </p>
</article>
""")

    return f"""
<section style="margin-top:30px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">CEO POV – AI & Space Economy</h2>
  {''.join(cards)}
</section>
"""


# -------------------------------------------------------
# PATENT WATCH SECTION
# -------------------------------------------------------

def _render_patents(patents: List[Dict]) -> str:
    if not patents:
        return """
<section style="margin-top:30px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">Patent Watch – Compute / Video / Data / Cloud (EU/US)</h2>
  <p style="margin:0; font-size:13px; color:#777;">
    No relevant patent publications detected for this day (or collector not yet configured).
  </p>
</section>
"""

    rows = []
    for p in patents:
        office = escape(p.get("office", ""))
        pub_num = escape(p.get("publication_number", ""))
        title = escape(p.get("title", ""))
        url = p.get("source_url") or "#"
        applicant_list = p.get("applicants") or []
        applicant = ", ".join(escape(a) for a in applicant_list) if applicant_list else ""
        if not applicant:
            applicant = escape(p.get("assignee", "") or "")
        tags = ", ".join(escape(t) for t in p.get("tags", []))
        pub_date = escape(p.get("publication_date", "") or "")

        rows.append(f"""
<tr>
  <td style="padding:4px 6px; border-top:1px solid #eee; white-space:nowrap; font-size:12px;">{office}</td>
  <td style="padding:4px 6px; border-top:1px solid #eee; white-space:nowrap; font-size:12px;">{pub_num}</td>
  <td style="padding:4px 6px; border-top:1px solid #eee; font-size:13px;">
    <a href="{url}" target="_blank" rel="noopener" style="color:#0052CC; text-decoration:none;">{title}</a>
  </td>
  <td style="padding:4px 6px; border-top:1px solid #eee; font-size:12px;">{applicant}</td>
  <td style="padding:4px 6px; border-top:1px solid #eee; font-size:12px;">{tags}</td>
  <td style="padding:4px 6px; border-top:1px solid #eee; white-space:nowrap; font-size:12px;">{pub_date}</td>
</tr>
""")

    return f"""
<section style="margin-top:30px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">Patent Watch – Compute / Video / Data / Cloud (EU/US)</h2>
  <div style="overflow-x:auto;">
    <table style="border-collapse:collapse; width:100%; font-size:13px;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="text-align:left; padding:4px 6px; font-size:12px;">Office</th>
          <th style="text-align:left; padding:4px 6px; font-size:12px;">Publication</th>
          <th style="text-align:left; padding:4px 6px; font-size:12px;">Title</th>
          <th style="text-align:left; padding:4px 6px; font-size:12px;">Applicant / Assignee</th>
          <th style="text-align:left; padding:4px 6px; font-size:12px;">Tags</th>
          <th style="text-align:left; padding:4px 6px; font-size:12px;">Pub. date</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
</section>
"""


# -------------------------------------------------------
# HTML GENERATION
# -------------------------------------------------------

def build_html_report(
    *,
    deep_dives,
    watchlist,
    date_str: str,
    ceo_pov: list | None = None,
    patents: list | None = None,
    history: list | None = None,
) -> str:
    header = _render_header(date_str)
    deep_html = _render_deep_dives(deep_dives)
    wl_html = _render_watchlist(watchlist)
    ceo_html = _render_ceo_pov(ceo_pov or [])
    patents_html = _render_patents(patents or [])
    history_js = json.dumps(history or [], ensure_ascii=False)

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

  {ceo_html}

  {patents_html}

  <section style="margin-top:30px;">
    <h2 style="margin:0 0 12px 0; font-size:20px;">Curated watchlist · 3–5 links per topic</h2>
    {wl_html}
  </section>

</div>

<script>
  // History payload injected from backend (last 7 daily reports)
  window.MAXBITS_HISTORY = {history_js};
</script>

<script>
(function() {{
  const KEY = "maxbits_weekly_selections_v1";

  function loadSel() {{
    try {{
      return JSON.parse(localStorage.getItem(KEY) || "{{}}" );
    }} catch (e) {{
      return {{}};
    }}
  }}

  function saveSel(x) {{
    try {{
      localStorage.setItem(KEY, JSON.stringify(x));
    }} catch (e) {{
      console.warn("[Weekly] Cannot save selections", e);
    }}
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
        if (!cb.checked && i !== -1) arr.splice(i, 1);

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
      alert("Popup blocked: allow popups for this site to see the weekly view.");
      return;
    }}

    let html = "<!DOCTYPE html><html><head><meta charset='utf-8' />" +
               "<title>MaxBits · Weekly Selection (local)</title></head>" +
               "<body style=\\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;" +
               "background:#fafafa; margin:0; padding:24px; color:#111;\\">" +
               "<div style=\\"max-width:900px; margin:0 auto; background:white; padding:24px 32px;" +
               "border-radius:8px; box-shadow:0 0 12px rgba(0,0,0,0.05);\\">" +
               "<h1>MaxBits · Weekly Selection (local)</h1>" +
               "<p style='color:#555;font-size:14px;'>This page is generated locally from your browser selections. It is NOT stored on the server.</p>";

    if (!dates.length) {{
      html += "<p>No weekly selections saved yet.</p>";
    }} else {{
      dates.forEach(d => {{
        const items = data[d] || [];
        if (!items.length) return;
        html += "<section style='margin-top:18px;'>" +
                "<h2 style='font-size:18px; margin:0 0 6px 0;'>Day " + d + "</h2>" +
                "<ul style='margin:4px 0 0 18px; font-size:14px;'>";
        items.forEach(it => {{
          const t = it.title || "";
          const u = it.url || "#";
          const s = it.source || "";
          html += "<li style='margin-bottom:4px;'>" +
                  "<a href='" + u + "' target='_blank' rel='noopener' style='color:#0052CC;'>" + t + "</a>" +
                  " <span style='color:#777; font-size:12px;'>(" + s + ")</span>" +
                  "</li>";
        }});
        html += "</ul></section>";
      }});
    }}

    html += "</div></body></html>";
    win.document.open();
    win.document.write(html);
    win.document.close();
  }}

  function initWeeklyBtn() {{
    const btn = document.getElementById("open-weekly-btn");
    if (!btn) return;
    btn.addEventListener("click", openWeekly);
  }}

  function initHistory() {{
    const hist = window.MAXBITS_HISTORY || [];
    const ul = document.getElementById("history-list");
    if (!ul) return;
    if (!hist.length) {{
      ul.innerHTML = "<li>No reports available yet.</li>";
      return;
    }}

    ul.innerHTML = hist.map(it => {{
      const pdfPart = it.pdf
        ? " · <a href='" + it.pdf + "' target='_blank' rel='noopener'>PDF</a>"
        : "";
      return "<li><strong>" + it.date + "</strong> – " +
             "<a href='" + it.html + "' target='_blank' rel='noopener'>HTML</a>" +
             pdfPart + "</li>";
    }}).join("");
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
