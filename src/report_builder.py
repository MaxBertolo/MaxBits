# src/report_builder.py

from __future__ import annotations

from typing import List, Dict
from html import escape


# -----------------------------
# HEADER
# -----------------------------

def _render_header(date_str: str) -> str:
    return f"""
<header style="margin-bottom: 24px;">
  <h1 style="margin:0; font-size:26px; letter-spacing:0.03em;">MaxBits · Daily Tech Watch</h1>
  <p style="margin:4px 0 0 0; color:#555; font-size:13px;">
    High-quality technology news from around the world · <strong>{escape(date_str)}</strong>
  </p>

  <div style="margin-top:12px; display:flex; flex-wrap:wrap; gap:8px; align-items:center;">
    <button id="open-weekly-btn"
            style="background:#0052CC; color:#fff; border:none; padding:8px 14px;
                   border-radius:6px; cursor:pointer; font-size:13px;">
      Open Weekly view (local)
    </button>
    <span style="font-size:12px; color:#777;">
      Weekly = articoli selezionati con “Add to Weekly”, salvati in locale nel browser.
    </span>
  </div>

  <section id="history-box"
           style="margin-top:16px; padding:10px 12px; border-radius:6px; background:#f5f5f5;">
    <strong style="font-size:13px;">Last 7 daily reports</strong>
    <ul id="history-list"
        style="margin:6px 0 0 16px; padding:0; font-size:12px; color:#333;">
    </ul>
  </section>
</header>
"""


# -----------------------------
# DEEP DIVES
# -----------------------------

def _render_deep_dives(deep_dives: List[Dict]) -> str:
    if not deep_dives:
        return "<p>No deep-dives today.</p>"

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
<article style="margin-bottom:24px; padding:16px 18px; border-radius:8px;
                border:1px solid #e2e2e2; background:#fafafa;">
  <h2 style="margin:0 0 4px 0; font-size:19px;">
    <a href="{url}" style="color:#0052CC; text-decoration:none;">{title}</a>
  </h2>
  <p style="margin:0 0 10px 0; color:#777; font-size:13px;">
    {source} · Topic: <strong>{topic}</strong>
  </p>

  <table style="width:100%; border-collapse:collapse; font-size:14px;">
    <tbody>
      <tr>
        <td style="width:140px; vertical-align:top; padding:2px 6px; font-weight:bold;">What it is</td>
        <td style="vertical-align:top; padding:2px 6px;">{what_it_is}</td>
      </tr>
      <tr>
        <td style="vertical-align:top; padding:2px 6px; font-weight:bold;">Who</td>
        <td style="vertical-align:top; padding:2px 6px;">{who}</td>
      </tr>
      <tr>
        <td style="vertical-align:top; padding:2px 6px; font-weight:bold;">What it does</td>
        <td style="vertical-align:top; padding:2px 6px;">{what_it_does}</td>
      </tr>
      <tr>
        <td style="vertical-align:top; padding:2px 6px; font-weight:bold;">Why it matters</td>
        <td style="vertical-align:top; padding:2px 6px;">{why_it_matters}</td>
      </tr>
      <tr>
        <td style="vertical-align:top; padding:2px 6px; font-weight:bold;">Strategic view</td>
        <td style="vertical-align:top; padding:2px 6px;">{strategic_view}</td>
      </tr>
    </tbody>
  </table>

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


# -----------------------------
# WATCHLIST
# -----------------------------

def _render_watchlist_section(title: str, items: List[Dict]) -> str:
    if not items:
        return ""

    rows: List[str] = []
    for i, art in enumerate(items):
        aid = escape(art.get("id") or f"wl_{title}_{i}")
        t = escape(art.get("title", ""))
        u = art.get("url") or "#"
        s = escape(art.get("source", ""))

        rows.append(f"""
<li style="margin-bottom:4px;">
  <a href="{u}" style="color:#0052CC; text-decoration:none;">{t}</a>
  <span style="color:#777; font-size:12px;">({s})</span>
  <label style="margin-left:8px; font-size:12px; color:#333;">
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
<section style="margin-top:16px;">
  <h3 style="margin:0 0 6px 0; font-size:16px;">{escape(title)}</h3>
  <ul style="margin:0 0 0 18px; padding:0; font-size:14px; list-style:disc;">
    {''.join(rows)}
  </ul>
</section>
"""


def _render_watchlist(watchlist: Dict[str, List[Dict]]) -> str:
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

    sections: List[str] = []
    for topic in ordered_topics:
        items = watchlist.get(topic, [])
        if not items:
            continue
        pretty = topic.replace("/", " / ").replace("Infra", "Infrastructure")
        sections.append(_render_watchlist_section(pretty, items))

    if not sections:
        return "<p>No watchlist items today.</p>"

    return "\n".join(sections)


# -----------------------------
# HTML COMPLETO
# -----------------------------

def build_html_report(*, deep_dives, watchlist, date_str: str) -> str:
    header = _render_header(date_str)
    deep_html = _render_deep_dives(deep_dives)
    wl_html = _render_watchlist(watchlist)

    # JS separato per evitare problemi con le { } dentro l'f-string
    script = """
<script>
(function() {
  const STORAGE_KEY = "maxbits_weekly_selections_v1";

  function loadSelections() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return {};
      return JSON.parse(raw);
    } catch (e) {
      console.warn("[Weekly] Cannot parse selections:", e);
      return {};
    }
  }

  function saveSelections(data) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
      console.warn("[Weekly] Cannot save selections:", e);
    }
  }

  function setupCheckboxes() {
    const dateMeta = document.querySelector("meta[name='report-date']");
    const dateStr = dateMeta ? dateMeta.content : "";
    const data = loadSelections();
    const todays = data[dateStr] || [];

    document.querySelectorAll(".weekly-checkbox").forEach(cb => {
      const id = cb.dataset.id;
      if (!id) return;

      if (todays.some(x => x.id === id)) {
        cb.checked = true;
      }

      cb.addEventListener("change", () => {
        const entry = {
          id: cb.dataset.id,
          title: cb.dataset.title,
          url: cb.dataset.url,
          source: cb.dataset.source
        };

        const list = data[dateStr] || [];
        const idx = list.findIndex(x => x.id === entry.id);

        if (cb.checked) {
          if (idx === -1) list.push(entry);
        } else {
          if (idx !== -1) list.splice(idx, 1);
        }

        data[dateStr] = list;
        saveSelections(data);
      });
    });
  }

  function openWeeklyView() {
    const data = loadSelections();
    const dates = Object.keys(data).sort().reverse();

    const win = window.open("", "_blank");
    if (!win) {
      alert("Popup blocked: allow popups to see weekly view.");
      return;
    }

    let html = "<!DOCTYPE html><html><head><meta charset='utf-8'>" +
               "<title>MaxBits · Weekly Selection (local)</title></head>" +
               "<body style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;" +
               "font-size:14px; background:#fafafa; margin:0; padding:24px;'>" +
               "<div style='max-width:900px; margin:0 auto; background:#fff; padding:24px 32px;" +
               "border-radius:8px; box-shadow:0 0 12px rgba(0,0,0,0.05);'>" +
               "<h1 style='margin-top:0;'>MaxBits · Weekly Selection (local)</h1>" +
               "<p style='color:#555;font-size:13px;'>This page is generated locally from your selections. " +
               "Nothing is stored on the server.</p>";

    if (!dates.length) {
      html += "<p>No weekly selections yet.</p>";
    } else {
      dates.forEach(function(d) {
        const items = data[d] || [];
        if (!items.length) return;
        html += "<section style='margin-top:16px;'>" +
                "<h2 style='font-size:16px; margin:0 0 4px 0;'>Day " + d + "</h2>" +
                "<ul style='margin:4px 0 0 18px; padding:0; font-size:14px;'>";
        items.forEach(function(it) {
          const t = it.title || "";
          const u = it.url || "#";
          const s = it.source || "";
          html += "<li style='margin-bottom:4px;'>" +
                  "<a href='" + u + "' target='_blank' rel='noopener' style='color:#0052CC;'>" +
                  t + "</a> <span style='color:#777; font-size:12px;'>(" + s + ")</span>" +
                  "</li>";
        });
        html += "</ul></section>";
      });
    }

    html += "</div></body></html>";
    win.document.open();
    win.document.write(html);
    win.document.close();
  }

  function initWeeklyButton() {
    const btn = document.getElementById("open-weekly-btn");
    if (!btn) return;
    btn.addEventListener("click", openWeeklyView);
  }

  function initHistoryBox() {
    const history = window.MAXBITS_HISTORY || [];
    const ul = document.getElementById("history-list");
    if (!ul || !history.length) return;

    ul.innerHTML = history.slice(0, 7).map(function(item) {
      var h = "<li><strong>" + item.date + "</strong> – ";
      h += "<a href='" + item.html + "' target='_blank' rel='noopener'>HTML</a>";
      if (item.pdf) {
        h += " · <a href='" + item.pdf + "' target='_blank' rel='noopener'>PDF</a>";
      }
      h += "</li>";
      return h;
    }).join("");
  }

  document.addEventListener("DOMContentLoaded", function() {
    setupCheckboxes();
    initWeeklyButton();
    initHistoryBox();
  });
})();
</script>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="report-date" content="{escape(date_str)}" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             font-size:14px; color:#111; background:#f0f0f0; margin:0; padding:24px;">

  <div style="max-width:900px; margin:0 auto; background:white;
              padding:24px 32px; border-radius:8px;
              box-shadow:0 0 14px rgba(0,0,0,0.06);">

    {header}

    <section style="margin-top:28px;">
      <h2 style="margin:0 0 10px 0; font-size:20px;">3 deep-dives you should really read</h2>
      {deep_html}
    </section>

    <section style="margin-top:28px;">
      <h2 style="margin:0 0 10px 0; font-size:19px;">Curated watchlist · 3–5 links per topic</h2>
      {wl_html}
    </section>

  </div>

  {script}
</body>
</html>
"""
