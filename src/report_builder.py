# src/report_builder.py

from __future__ import annotations

from html import escape
from typing import List, Dict, Any


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

  # <section id="history-box"
   #        style="margin-top:14px; padding:10px 12px; border-radius:6px; background:#f5f5f5;">
    #<strong style="font-size:13px;">Last 7 daily reports</strong>
    #<ul id="history-list"
     #   style="margin:6px 0 0 16px; padding:0; font-size:12px; color:#333;">
    #</ul>
  #</section>
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
# CEO POV SECTION
# -------------------------------------------------------

def _render_ceo_pov(ceo_items: List[Dict[str, Any]]) -> str:
    """
    Mostra le dichiarazioni dei CEO su AI / Space / Tech in modo compatto ma leggibile.
    """
    if not ceo_items:
        return """
<section style="margin-top:30px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">CEO POV · AI &amp; Space Economy</h2>
  <p style="margin:4px 0 0 0; font-size:13px; color:#777;">
    No CEO statements collected for today.
  </p>
</section>
"""

    blocks: List[str] = []

    for idx, item in enumerate(ceo_items):
        cid = escape(str(item.get("id") or f"ceo_{idx+1}"))

        name = (
            item.get("ceo_name")
            or item.get("name")
            or item.get("person")
            or "Unnamed executive"
        )
        company = item.get("company") or ""
        role = item.get("role") or ""
        topic = item.get("topic") or ""
        quote = item.get("quote") or ""
        source = item.get("source") or ""
        url = item.get("url") or ""
        date = item.get("date") or ""

        name_html = escape(name)
        company_html = escape(company)
        role_html = escape(role)
        topic_html = escape(topic or "Tech / Strategy")
        source_html = escape(source)
        date_html = escape(date)

        # se quote è lunga, accorcia a ~260 char
        q = quote.strip()
        if len(q) > 260:
            q = q[:257] + "…"
        quote_html = escape(q)

        meta_parts = []
        if company_html:
            meta_parts.append(company_html)
        if role_html:
            meta_parts.append(role_html)
        if date_html:
            meta_parts.append(date_html)
        meta_str = " · ".join(meta_parts)

        link_html = ""
        if url:
            link_html = f"""<a href="{url}" target="_blank" rel="noopener"
                             style="font-size:12px; color:#0052CC; text-decoration:none;">
                             Source</a>"""

        blocks.append(f"""
<article id="{cid}"
         style="margin-bottom:14px; padding:10px 12px;
                border-radius:8px; background:#f9fafb; border:1px solid #e5e7eb;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
    <div style="flex:1;">
      <p style="margin:0; font-size:13px; color:#374151;">
        <span style="font-weight:600;">{name_html}</span>
        <span style="color:#6b7280;"> — {meta_str}</span>
      </p>
      <p style="margin:6px 0 0 0; font-size:13px; color:#111827;">
        “{quote_html}”
      </p>
    </div>
    <div style="padding-left:8px; text-align:right;">
      <span style="display:inline-block; padding:2px 8px; border-radius:999px;
                   background:#e0f2fe; color:#0369a1; font-size:11px;">
        {topic_html}
      </span>
    </div>
  </div>
  <div style="margin-top:6px; display:flex; justify-content:space-between; align-items:center;">
    <span style="font-size:11px; color:#6b7280;">{source_html}</span>
    {link_html}
  </div>
</article>
""")

    return f"""
<section style="margin-top:30px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">CEO POV · AI &amp; Space Economy</h2>
  <p style="margin:2px 0 10px 0; font-size:13px; color:#777;">
    Selected statements from top tech and space CEOs about AI, cloud and orbital infrastructure.
  </p>
  {''.join(blocks)}
</section>
"""


# -------------------------------------------------------
# PATENT WATCH SECTION (COMPUTE / VIDEO / DATA / CLOUD)
# -------------------------------------------------------

def _patent_area(pat: Dict[str, Any]) -> str:
    """
    Classifica un brevetto in una macro area: Compute, Cloud, Video, Data, Other.
    Usa title+abstract in modo euristico.
    """
    text = " ".join(
        [
            str(pat.get("title") or ""),
            str(pat.get("abstract") or ""),
        ]
    ).lower()

    # Semplici euristiche (ordine di priorità)
    if any(k in text for k in ["codec", "encoding", "decoding", "transcoding", "video", "streaming", "abr", "av1", "hevc", "vvc", "h.264", "h.265"]):
        return "Video"

    if any(k in text for k in ["database", "data lake", "data warehouse", "analytics", "big data", "olap", "oltp", "data pipeline", "data processing"]):
        return "Data"

    if any(k in text for k in ["cloud", "saas", "paas", "iaas", "kubernetes", "serverless", "object storage", "block storage", "edge computing"]):
        return "Cloud"

    if any(k in text for k in ["gpu", "accelerator", "cpu", "processor", "asic", "inference", "neural network accelerator", "compute", "computing", "tensor core"]):
        return "Compute"

    return "Other"


def _patent_area_badge(area: str) -> str:
    """
    Badge colorata per l'area.
    """
    area = area or "Other"
    label = area

    bg = "#e5e7eb"
    fg = "#374151"

    if area == "Compute":
        bg, fg = "#dbeafe", "#1d4ed8"   # light indigo
    elif area == "Cloud":
        bg, fg = "#e0f2fe", "#0369a1"   # light sky
    elif area == "Video":
        bg, fg = "#ccfbf1", "#0f766e"   # teal
    elif area == "Data":
        bg, fg = "#fef3c7", "#b45309"   # amber

    return f"""
<span style="display:inline-block; padding:2px 8px; border-radius:999px;
             background:{bg}; color:{fg}; font-size:11px; font-weight:500;">
  {escape(label)}
</span>
"""


def _render_patent_watch(patents: List[Dict[str, Any]]) -> str:
    if not patents:
        return """
<section style="margin-top:30px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">Patent watch · Compute / Video / Data / Cloud</h2>
  <p style="margin:4px 0 0 0; font-size:13px; color:#777;">
    No relevant patent publications detected for today (EPO / USPTO).
  </p>
</section>
"""

    # arricchisci ogni patente con area
    enriched = []
    for p in patents:
        area = _patent_area(p)
        enriched.append((area, p))

    # ordina per area poi per data
    def _sort_key(item):
        area, p = item
        date_str = p.get("publication_date") or ""
        return (area, date_str)

    enriched.sort(key=_sort_key, reverse=True)

    rows: List[str] = []
    for area, p in enriched:
        badge = _patent_area_badge(area)

        title = escape(p.get("title") or "Untitled patent")
        url = p.get("source_url") or ""
        office = escape(p.get("office") or "")
        pubno = escape(p.get("publication_number") or "")
        date = escape(p.get("publication_date") or "")
        applicants = p.get("applicants") or []
        if isinstance(applicants, str):
            applicants_str = applicants
        else:
            applicants_str = ", ".join(str(a) for a in applicants)
        applicants_html = escape(applicants_str)

        assignee_html = escape(p.get("assignee") or "")
        abstract = (p.get("abstract") or "").strip()
        if len(abstract) > 220:
            abstract = abstract[:217] + "…"
        abstract_html = escape(abstract)

        if url:
            title_html = f'<a href="{url}" target="_blank" rel="noopener" style="color:#0052CC; text-decoration:none;">{title}</a>'
        else:
            title_html = title

        meta_line_parts = []
        if office:
            meta_line_parts.append(office)
        if pubno:
            meta_line_parts.append(pubno)
        if date:
            meta_line_parts.append(date)
        meta_line = " · ".join(meta_line_parts)

        applicant_line_parts = []
        if applicants_html:
            applicant_line_parts.append(applicants_html)
        if assignee_html:
            applicant_line_parts.append(assignee_html)
        applicant_line = " — ".join(applicant_line_parts)

        rows.append(f"""
<tr style="border-bottom:1px solid #f3f4f6;">
  <td style="vertical-align:top; padding:8px 8px 8px 0; width:110px;">
    {badge}
    <div style="margin-top:4px; font-size:11px; color:#6b7280;">{meta_line}</div>
  </td>
  <td style="vertical-align:top; padding:8px 0 8px 0;">
    <div style="font-size:13px; font-weight:600; margin-bottom:2px;">
      {title_html}
    </div>
    <div style="font-size:12px; color:#6b7280; margin-bottom:4px;">
      {applicant_line}
    </div>
    <div style="font-size:12px; color:#374151;">
      {abstract_html}
    </div>
  </td>
</tr>
""")

    table_html = f"""
<table style="width:100%; border-collapse:collapse; margin-top:6px;">
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
"""

    return f"""
<section style="margin-top:30px;">
  <h2 style="margin:0 0 8px 0; font-size:20px;">Patent watch · Compute / Video / Data / Cloud</h2>
  <p style="margin:2px 0 6px 0; font-size:13px; color:#777;">
    Selected patent publications from EPO / USPTO relevant to computation, video, data platforms and cloud infrastructure.
  </p>
  {table_html}
</section>
"""


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
# HTML GENERATION
# -------------------------------------------------------

def build_html_report(
    *,
    deep_dives,
    watchlist,
    date_str: str,
    ceo_pov: List[Dict[str, Any]] | None = None,
    patents: List[Dict[str, Any]] | None = None,
) -> str:
    """
    Genera l'HTML del daily report.

    Parametri nuovi (opzionali, backward compatible):
      - ceo_pov: lista di dict con dichiarazioni dei CEO
      - patents: lista di brevetti rilevanti
    """
    header = _render_header(date_str)
    deep_html = _render_deep_dives(deep_dives)
    ceo_html = _render_ceo_pov(ceo_pov or [])
    patent_html = _render_patent_watch(patents or [])
    wl_html = _render_watchlist(watchlist)

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

  {patent_html}

  <section style="margin-top:30px;">
    <h2 style="margin:0 0 12px 0; font-size:20px;">Curated watchlist · 3–5 links per topic</h2>
    {wl_html}
  </section>

</div>

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

    ul.innerHTML = hist.slice(0,7).map(it =>
      "<li><strong>" + it.date + "</strong> – " +
      "<a href='" + it.html + "' target='_blank' rel='noopener'>HTML</a> · " +
      "<a href='" + it.pdf + "' target='_blank' rel='noopener'>PDF</a></li>"
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
