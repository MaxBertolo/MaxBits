# src/report_builder.py

from __future__ import annotations

from typing import List, Dict
from html import escape


def _render_header(date_str: str) -> str:
    """
    Header principale del daily + box link storico ultimi 7 giorni.
    Lo storico viene gestito da JS leggendo la lista dei file disponibili.
    """
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
      Weekly = articoli che selezioni con “Add to Weekly” (salvati solo sul tuo browser).
    </span>
  </div>

  <section id="history-box" style="margin-top:14px; padding:10px 12px; border-radius:6px; background:#f5f5f5;">
    <strong style="font-size:13px;">Last 7 daily reports</strong>
    <p style="margin:4px 0 0 0; font-size:12px; color:#555;">
      La lista è gestita dal workflow che pubblica i report. Qui sotto JS inserirà i link
      agli ultimi 7 (HTML + PDF) quando disponibili.
    </p>
    <ul id="history-list"
        style="margin:6px 0 0 16px; padding:0; font-size:12px; color:#333;">
    </ul>
  </section>
</header>
"""


def _render_deep_dives(deep_dives: List[Dict]) -> str:
    """
    deep_dives: lista di dizionari con chiavi:
      - id (string) – opzionale; se non c'è usiamo l'indice
      - title, url, source, topic
      - what_it_is, who, what_it_does, why_it_matters, strategic_view
    """
    if not deep_dives:
        return "<p>No deep-dive articles for today.</p>"

    blocks: List[str] = []

    for idx, item in enumerate(deep_dives):
        art_id = escape(item.get("id") or f"deep_{idx+1}")
        title = escape(item.get("title", ""))
        url = item.get("url") or "#"
        source = escape(item.get("source", ""))
        topic = escape(item.get("topic", "General"))

        what_it_is = escape(item.get("what_it_is", ""))
        who = escape(item.get("who", ""))
        what_it_does = escape(item.get("what_it_does", ""))
        why_it_matters = escape(item.get("why_it_matters", ""))
        strategic_view = escape(item.get("strategic_view", ""))

        block = f"""
<article style="margin-bottom: 24px; padding-bottom:16px; border-bottom:1px solid #eee;">
  <h2 style="margin:0 0 4px 0; font-size:20px;">
    <a href="{url}" style="color:#0052CC; text-decoration:none;">{title}</a>
  </h2>
  <p style="margin:0; color:#777; font-size:13px;">
    {source} · Topic: <strong>{topic}</strong>
  </p>

  <ul style="margin:8px 0 0 18px; padding:0; font-size:14px;">
    <li><strong>What it is:</strong> {what_it_is}</li>
    <li><strong>Who:</strong> {who}</li>
    <li><strong>What it does:</strong> {what_it_does}</li>
    <li><strong>Why it matters:</strong> {why_it_matters}</li>
    <li><strong>Strategic view:</strong> {strategic_view}</li>
  </ul>

  <div style="margin-top:8px;">
    <label style="display:inline-flex; align-items:center; gap:6px; font-size:13px; color:#333;">
      <input type="checkbox"
             class="weekly-checkbox"
             data-id="{art_id}"
             data-title="{title}"
             data-url="{url}"
             data-source="{source}">
      <span>Add to Weekly</span>
    </label>
  </div>
</article>
"""
        blocks.append(block)

    return "\n".join(blocks)


def _render_watchlist_section(title: str, items: List[Dict]) -> str:
    """
    items: lista di dict con almeno title, url, source, id opzionale
    """
    if not items:
        return ""

    lis: List[str] = []

    for idx, art in enumerate(items):
        art_id = escape(art.get("id") or f"wl_{title}_{idx+1}")
        atitle = escape(art.get("title", ""))
        url = art.get("url") or "#"
        source = escape(art.get("source", ""))

        lis.append(
            f"""
<li style="margin-bottom:4px;">
  <a href="{url}" style="color:#0052CC; text-decoration:none;">{atitle}</a>
  <span style="color:#777; font-size:12px;">({source})</span>

  <label style="margin-left:8px; font-size:12px; color:#333;">
    <input type="checkbox"
           class="weekly-checkbox"
           data-id="{art_id}"
           data-title="{atitle}"
           data-url="{url}"
           data-source="{source}">
    Add to Weekly
  </label>
</li>
"""
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
    """
    watchlist: dict topic -> lista articoli (già deduplicati in main)
    Le chiavi attese (anche se alcune possono essere vuote) sono:
      "TV/Streaming",
      "Telco/5G",
      "Media/Platforms",
      "AI/Cloud/Quantum",
      "Space/Infra",
      "Robotics/Automation",
      "Broadcast/Video",
      "Satellite/Satcom"
    """
    if not watchlist:
        return "<p>No additional watchlist items today.</p>"

    sections_html: List[str] = []

    ordered_topics = [
        "TV/Streaming",
        "Telco/5G",
        "Media/Platforms",
        "AI/Cloud/Quantum",
        "Space/Infra",
        "Robotics/Automation",
        "Broadcast/Video",
        "Satellite/Satcom",
    ]

    for topic in ordered_topics:
        items = watchlist.get(topic, [])
        if items:
            pretty_title = topic.replace("/", " / ").replace("Infra", "Infrastructure")
            sections_html.append(_render_watchlist_section(pretty_title, items))

    return "\n".join(sections_html)


def build_html_report(*, deep_dives, watchlist, date_str: str) -> str:
    """
    Costruisce l'HTML completo del daily.

    Parametri:
      - deep_dives: lista di 3 articoli "full" (già arricchiti dal summarizer)
      - watchlist: dict topic -> lista articoli (solo titolo+url+source, NO duplicazioni con deep_dives)
      - date_str: 'YYYY-MM-DD'
    """
    header = _render_header(date_str)
    deep_dives_html = _render_deep_dives(deep_dives)
    watchlist_html = _render_watchlist(watchlist)

    # NB: meta name="report-date" serve al JS per sapere la data del report corrente
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="report-date" content="{escape(date_str)}" />
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
             font-size:14px; color:#111; background:#fafafa; margin:0; padding:24px;">
  <div style="max-width:900px; margin:0 auto; background:#fff; padding:24px 32px;
              border-radius:8px; box-shadow:0 0 12px rgba(0,0,0,0.04);">
    {header}

    <section style="margin-bottom:32px;">
      <h2 style="margin:0 0 12px 0; font-size:22px;">3 deep-dives you should really read</h2>
      {deep_dives_html}
    </section>

    <section>
      <h2 style="margin:0 0 8px 0; font-size:20px;">Curated watchlist · 3–5 links per topic (no duplicates)</h2>
      {watchlist_html}
    </section>
  </div>

  <!-- ========================
       WEEKLY LOCAL SELECTION JS
       ======================== -->
  <script>
  (function() {{
    const STORAGE_KEY = "maxbits_weekly_selections_v1";

    function loadSelections() {{
      try {{
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (!raw) return {{}};
        return JSON.parse(raw);
      }} catch (e) {{
        console.warn("[Weekly] Cannot parse selections from localStorage:", e);
        return {{}};
      }}
    }}

    function saveSelections(data) {{
      try {{
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      }} catch (e) {{
        console.warn("[Weekly] Cannot save selections:", e);
      }}
    }}

    function onCheckboxChange(dateStr, cb) {{
      const data = loadSelections();
      if (!data[dateStr]) data[dateStr] = [];

      const entry = {{
        id: cb.dataset.id,
        title: cb.dataset.title,
        url: cb.dataset.url,
        source: cb.dataset.source
      }};

      const list = data[dateStr];
      const idx = list.findIndex(x => x.id === entry.id);

      if (cb.checked) {{
        if (idx === -1) list.push(entry);
      }} else {{
        if (idx !== -1) list.splice(idx, 1);
      }}

      saveSelections(data);
    }}

    function initialiseCheckboxes() {{
      const meta = document.querySelector('meta[name="report-date"]');
      if (!meta) return;
      const dateStr = meta.content;

      const data = loadSelections();
      const todayList = data[dateStr] || [];

      document.querySelectorAll(".weekly-checkbox").forEach(cb => {{
        const id = cb.dataset.id;
        if (!id) return;

        // pre-seleziona se già presente
        if (todayList.some(x => x.id === id)) {{
          cb.checked = true;
        }}

        cb.addEventListener("change", () => onCheckboxChange(dateStr, cb));
      }});
    }}

    function buildWeeklyHtml(selected) {{
      // selected: dict date -> [articles]
      const dates = Object.keys(selected).sort().reverse();
      if (!dates.length) {{
        return "<p>No weekly selections saved yet.</p>";
      }}

      let html = "<h1>MaxBits · Weekly Selection (local)</h1>";
      html += "<p style='color:#555;font-size:14px;'>This page is generated locally from your browser selections. It is NOT stored on the server.</p>";

      dates.forEach(d => {{
        const items = selected[d];
        if (!items || !items.length) return;

        html += `<section style="margin-top:18px;">
          <h2 style="font-size:18px; margin:0 0 6px 0;">Day ${d}</h2>
          <ul style="margin:4px 0 0 18px; font-size:14px;">`;

        items.forEach(it => {{
          const t = it.title || "";
          const u = it.url || "#";
          const s = it.source || "";
          html += `<li style="margin-bottom:4px;">
                     <a href="${{u}}" target="_blank" rel="noopener" style="color:#0052CC;">${{t}}</a>
                     <span style="color:#777; font-size:12px;">(${{s}})</span>
                   </li>`;
        }});

        html += "</ul></section>";
      }});

      return html;
    }}

    function openWeeklyView() {{
      const data = loadSelections();
      const win = window.open("", "_blank");
      if (!win) {{
        alert("Popup blocked: allow popups for this site to see the weekly view.");
        return;
      }}

      const weeklyHtml = buildWeeklyHtml(data);

      win.document.open();
      win.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MaxBits · Weekly Selection (local)</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             font-size:14px; color:#111; background:#fafafa; margin:0; padding:24px;">
  <div style="max-width:900px; margin:0 auto; background:#fff; padding:24px 32px;
              border-radius:8px; box-shadow:0 0 12px rgba(0,0,0,0.04);">
    ${weeklyHtml}
  </div>
</body>
</html>`);
      win.document.close();
    }}

    function initWeeklyButton() {{
      const btn = document.getElementById("open-weekly-btn");
      if (!btn) return;
      btn.addEventListener("click", openWeeklyView);
    }}

    // Storico ultimi 7 giorni – qui JS può riempire #history-list se hai una API
    // o una lista generata dal workflow (es. via window.MAXBITS_HISTORY inserito dallo stesso).
    function initHistoryBox() {{
      // Per ora lasciamo vuoto: il workflow può iniettare script con la lista.
      // Esempio:
      //   window.MAXBITS_HISTORY = [
      //     {{ date: "2025-12-04", html: "reports/html/report_2025-12-04.html",
      //        pdf: "reports/pdf/report_2025-12-04.pdf" }},
      //   ];
      const history = window.MAXBITS_HISTORY || [];
      const ul = document.getElementById("history-list");
      if (!ul || !history.length) return;

      ul.innerHTML = history.slice(0, 7).map(item => `
        <li>
          <strong>${{item.date}}</strong> –
          <a href="${{item.html}}" target="_blank" rel="noopener">HTML</a>
          ·
          <a href="${{item.pdf}}" target="_blank" rel="noopener">PDF</a>
        </li>
      `).join("");
    }}

    document.addEventListener("DOMContentLoaded", function() {{
      initialiseCheckboxes();
      initWeeklyButton();
      initHistoryBox();
    }});
  }})();
  </script>
</body>
</html>
"""
