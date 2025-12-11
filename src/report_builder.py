# src/report_builder.py

from __future__ import annotations

from html import escape
from typing import List, Dict


# -------------------------------------------------------
# HEADER + STORICO 7 GIORNI + WEEKLY + TODAY EDITION
# -------------------------------------------------------

def _render_header(date_str: str) -> str:
    return f"""
<header style="margin-bottom: 24px;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">
    <div>
      <h1 style="margin:0; font-size:26px;">MaxBits · Daily Tech Watch</h1>
      <p style="margin:2px 0 0 0; color:#666; font-size:13px;">
        High-quality technology news from around the world.
      </p>
      <p style="margin:4px 0 0 0; color:#555;">Daily brief · {escape(date_str)}</p>
    </div>

    <!-- PILL "Today's edition" usata come back button verso la home MaxBits -->
    <button id="today-edition-btn"
            type="button"
            style="margin-top:4px; padding:6px 12px; border-radius:999px;
                   border:1px solid #e5e7eb; background:#0f172a; color:#e5e7eb;
                   font-size:12px; cursor:pointer; white-space:nowrap;">
      Today’s edition
    </button>
  </div>

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
    sections = []
    for topic in WATCHLIST_TOPICS_ORDER:
        items = watchlist.get(topic, []) or []
        sections.append(_render_watchlist_section(topic, items))

    return "\n".join(sections)


# -------------------------------------------------------
# CEO POV
# -------------------------------------------------------

def _render_ceo_pov(ceo_pov: List[Dict]) -> str:
    if not ceo_pov:
        return """
<section style="margin-top:32px;">
  <h2 style="margin:0 0 10px 0; font-size:20px;">CEO POV · AI & Space Economy</h2>
  <p style="margin:0; font-size:13px; color:#777;">
    No CEO statements collected today.
  </p>
</section>
"""

    rows = []
    for item in ceo_pov:
        ceo = escape(item.get("ceo") or "")
        role = escape(item.get("role") or "")
        company = escape(item.get("company") or "")
        date = escape(item.get("date") or "")
        quote = escape(item.get("quote") or "")
        topic = escape(item.get("topic") or "")
        src = escape(item.get("source") or "")
        url = item.get("url") or "#"

        meta = " · ".join(x for x in [company, topic, date] if x)

        rows.append(f"""
<article style="margin-bottom:14px; padding-bottom:10px; border-bottom:1px solid #eee;">
  <p style="margin:0; font-size:13px; color:#555;">
    <strong>{ceo}</strong> – {role}
  </p>
  <p style="margin:4px 0 0 0; font-size:14px; color:#111;">
    “{quote}”
  </p>
  <p style="margin:4px 0 0 0; font-size:12px; color:#777;">
    {meta}
    {' · ' if meta and src else ''}<a href="{url}" style="color:#0052CC; text-decoration:none;" target="_blank" rel="noopener">{src}</a>
  </p>
</article>
""")

    return f"""
<section style="margin-top:32px;">
  <h2 style="margin:0 0 10px 0; font-size:20px;">CEO POV · AI &amp; Space Economy</h2>
  {''.join(rows)}
</section>
"""


# -------------------------------------------------------
# PATENTS (Compute / Cloud / Video / Data)
# -------------------------------------------------------

def _patent_area_slug(area: str) -> str:
    a = (area or "").lower()
    if "compute" in a or "cpu" in a or "gpu" in a:
        return "compute"
    if "cloud" in a or "saas" in a or "iaas" in a:
        return "cloud"
    if "video" in a or "codec" in a or "stream" in a:
        return "video"
    if "data" in a or "database" in a or "analytics" in a:
        return "data"
    return "other"


def _render_patents(patents: List[Dict]) -> str:
    if not patents:
        return """
<section style="margin-top:32px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">Patents · Compute / Cloud / Video / Data</h2>
  <p style="margin:0; font-size:13px; color:#777;">
    No patent publications collected today.
  </p>
</section>
"""

    legend = """
<div style="margin:4px 0 10px 0; font-size:11px; color:#555;">
  <span class="patent-pill patent-pill-compute">Compute</span>
  <span class="patent-pill patent-pill-cloud">Cloud</span>
  <span class="patent-pill patent-pill-video">Video</span>
  <span class="patent-pill patent-pill-data">Data</span>
  <span class="patent-pill patent-pill-other">Other</span>
</div>
"""

    rows = []
    for p in patents:
        title = escape(p.get("title") or "")
        url = p.get("url") or "#"
        office = escape(p.get("office") or "")
        pub_date = escape(p.get("publication_date") or "")
        area = escape(p.get("area") or "")
        slug = _patent_area_slug(p.get("area") or "")
        assignee = escape(p.get("assignee") or p.get("applicant") or "")
        src = escape(p.get("source") or "")
        abstract = escape(p.get("abstract") or "")

        meta_parts = [office, pub_date]
        meta = " · ".join(x for x in meta_parts if x)

        rows.append(f"""
<li class="patent-item">
  <div class="patent-header">
    <a href="{url}" target="_blank" rel="noopener" class="patent-title">{title}</a>
    <span class="patent-pill patent-pill-{slug}">{area or 'Other'}</span>
  </div>
  <div class="patent-meta">
    <span>{meta}</span>
    {f'<span>Assignee: {assignee}</span>' if assignee else ''}
    {f'<span>Source: {src}</span>' if src else ''}
  </div>
  {f'<p class="patent-abstract">{abstract}</p>' if abstract else ''}
</li>
""")

    return f"""
<section style="margin-top:32px;">
  <h2 style="margin:0 0 6px 0; font-size:20px;">Patents · Compute / Cloud / Video / Data</h2>
  {legend}
  <ul class="patent-list">
    {''.join(rows)}
  </ul>
</section>
"""


# -------------------------------------------------------
# HTML GENERATION
# -------------------------------------------------------

def build_html_report(
    *,
    deep_dives: List[Dict],
    watchlist: Dict[str, List[Dict]],
    ceo_pov: List[Dict],
    patents: List[Dict],
    date_str: str,
) -> str:
    header = _render_header(date_str)
    deep_html = _render_deep_dives(deep_dives)
    wl_html = _render_watchlist(watchlist)
    ceo_html = _render_ceo_pov(ceo_pov)
    pat_html = _render_patents(patents)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="report-date" content="{escape(date_str)}" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>

  <style>
    body {{
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
      background:#fafafa;
      margin:0;
      padding:24px;
      color:#111;
    }}

    .patent-list {{
      list-style:none;
      margin:8px 0 0 0;
      padding:0;
      font-size:13px;
    }}
    .patent-item {{
      padding:8px 10px;
      border-radius:6px;
      border:1px solid #e5e7eb;
      background:#fff;
      margin-bottom:6px;
    }}
    .patent-header {{
      display:flex;
      justify-content:space-between;
      align-items:flex-start;
      gap:8px;
    }}
    .patent-title {{
      color:#0052CC;
      text-decoration:none;
      font-weight:600;
      font-size:13px;
    }}
    .patent-meta {{
      margin-top:4px;
      font-size:11px;
      color:#6b7280;
      display:flex;
      gap:8px;
      flex-wrap:wrap;
    }}
    .patent-abstract {{
      margin:4px 0 0 0;
      font-size:12px;
      color:#374151;
    }}
    .patent-pill {{
      display:inline-block;
      padding:2px 8px;
      border-radius:999px;
      font-size:10px;
      border:1px solid transparent;
      white-space:nowrap;
    }}
    .patent-pill-compute {{
      background:rgba(59,130,246,0.1);
      border-color:rgba(59,130,246,0.5);
      color:#1d4ed8;
    }}
    .patent-pill-cloud {{
      background:rgba(56,189,248,0.1);
      border-color:rgba(56,189,248,0.5);
      color:#0284c7;
    }}
    .patent-pill-video {{
      background:rgba(251,191,36,0.1);
      border-color:rgba(251,191,36,0.5);
      color:#b45309;
    }}
    .patent-pill-data {{
      background:rgba(34,197,94,0.1);
      border-color:rgba(34,197,94,0.5);
      color:#15803d;
    }}
    .patent-pill-other {{
      background:rgba(148,163,184,0.1);
      border-color:rgba(148,163,184,0.5);
      color:#4b5563;
    }}

    /* Bottone fisso per tornare a MaxBits */
    #maxbits-back-btn {{
      position:fixed;
      bottom:12px;
      left:12px;
      z-index:9999;
      padding:7px 12px;
      border-radius:999px;
      border:1px solid #e5e7eb;
      background:rgba(15,23,42,0.96);
      color:#e5e7eb;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
      font-size:12px;
      display:inline-flex;
      align-items:center;
      gap:6px;
      cursor:pointer;
      box-shadow:0 6px 18px rgba(15,23,42,0.45);
    }}
    #maxbits-back-btn span.icon {{
      font-size:14px;
    }}
    #maxbits-back-btn:hover {{
      background:#0b1120;
    }}
    @media (max-width:640px) {{
      #maxbits-back-btn {{
        bottom:8px;
        left:8px;
        font-size:11px;
        padding:6px 10px;
      }}
    }}
  </style>
</head>

<body>

<button id="maxbits-back-btn" type="button">
  <span class="icon">←</span>
  <span>Back to MaxBits</span>
</button>

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

  {ceo_html}

  {pat_html}

</div>

<script>
(function() {{
  const KEY = "maxbits_weekly_selections_v1";

  function loadSel() {{
    try {{
      return JSON.parse(localStorage.getItem(KEY) || "{{}}");
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

    ul.innerHTML = hist.slice(0,7).map(it =>
      "<li><strong>" + it.date + "</strong> – " +
      "<a href='" + it.html + "' target='_blank' rel='noopener'>HTML</a> · " +
      "<a href='" + it.pdf + "' target='_blank' rel='noopener'>PDF</a></li>"
    ).join("");
  }}

  // back verso la home MaxBits (usato da bottone flottante + Today’s edition)
  function initBackButton() {{
    const HOME = "https://maxbertolo.github.io/MaxBits/";

    function goHome() {{
      try {{
        if (window.history.length > 1) {{
          window.history.back();
        }} else if (window.top && window.top !== window) {{
          window.top.location.href = HOME;
        }} else {{
          window.location.href = HOME;
        }}
      }} catch (e) {{
        window.location.href = HOME;
      }}
    }}

    const btnFloating = document.getElementById("maxbits-back-btn");
    if (btnFloating) {{
      btnFloating.addEventListener("click", goHome);
    }}

    const pillToday = document.getElementById("today-edition-btn");
    if (pillToday) {{
      pillToday.addEventListener("click", goHome);
    }}
  }}

  document.addEventListener("DOMContentLoaded", () => {{
    setupCheckboxes();
    initWeeklyBtn();
    initHistory();
    initBackButton();
  }});
}})();
</script>

</body>
</html>
"""
