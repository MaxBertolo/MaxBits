# src/report_builder.py

from __future__ import annotations
from html import escape
from typing import List, Dict


# -------------------------------------------------------
# HEADER + STORICO 7 GIORNI + PULSANTE WEEKLY
# -------------------------------------------------------

def _render_header(date_str: str) -> str:
    return f"""
<header class="mb-header">
  <h1 class="mb-title">MaxBits · Daily Tech Watch</h1>
  <p class="mb-subtitle">High-quality technology news from around the world.</p>
  <p class="mb-date">Daily brief · {escape(date_str)}</p>

  <div class="mb-weekly-bar">
    <button id="open-weekly-btn" class="mb-btn-primary">
      Open Weekly view (local)
    </button>
    <span class="mb-weekly-help">
      Weekly = articoli selezionati con “Add to Weekly”, salvati solo nel tuo browser.
    </span>
  </div>

  <section id="history-box" class="mb-history-box">
    <strong class="mb-history-title">Last 7 daily reports</strong>
    <ul id="history-list" class="mb-history-list">
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
        # TITOLO = esattamente quello dell’articolo sorgente
        title = escape((item.get("title") or "").strip())
        url = item.get("url") or "#"
        source = escape(item.get("source", "") or "")
        topic = escape(item.get("topic", "General") or "")

        what_it_is = escape(item.get("what_it_is", "") or "")
        who = escape(item.get("who", "") or "")
        what_it_does = escape(item.get("what_it_does", "") or "")
        why_it_matters = escape(item.get("why_it_matters", "") or "")
        strategic_view = escape(item.get("strategic_view", "") or "")

        block = f"""
<article class="mb-article">
  <h2 class="mb-article-title">
    <a href="{url}" class="mb-article-link">{title}</a>
  </h2>
  <p class="mb-article-meta">
    {source} · Topic: <strong>{topic}</strong>
  </p>

  <ul class="mb-bullets">
    <li><strong>What it is:</strong> {what_it_is}</li>
    <li><strong>Who:</strong> {who}</li>
    <li><strong>What it does:</strong> {what_it_does}</li>
    <li><strong>Why it matters:</strong> {why_it_matters}</li>
    <li><strong>Strategic view:</strong> {strategic_view}</li>
  </ul>

  <label class="mb-weekly-label">
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

    rows: List[str] = []
    for i, art in enumerate(items):
        aid = escape(art.get("id") or f"wl_{title}_{i}")
        t = escape((art.get("title") or "").strip())
        u = art.get("url") or "#"
        s = escape(art.get("source", "") or "")

        rows.append(f"""
<li class="mb-watch-item">
  <span class="mb-watch-link-wrap">
    <a href="{u}" class="mb-watch-link">{t}</a>
    <span class="mb-watch-source">({s})</span>
  </span>
  <label class="mb-watch-weekly">
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
<section class="mb-watch-section">
  <h3 class="mb-watch-title">{escape(title)}</h3>
  <ul class="mb-watch-list">
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

        pretty = (
            topic.replace("/", " / ")
                 .replace("Infra", "Infrastructure")
        )
        sections.append(_render_watchlist_section(pretty, items))

    if not sections:
        return "<p>No watchlist items today.</p>"

    return "\n".join(sections)


# -------------------------------------------------------
# HTML GENERATION
# -------------------------------------------------------

def build_html_report(*, deep_dives, watchlist, date_str: str) -> str:
    header = _render_header(date_str)
    deep_html = _render_deep_dives(deep_dives)
    wl_html = _render_watchlist(watchlist)

    # HEAD senza CSS/JS (niente {{}})
    head_open = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="report-date" content="{escape(date_str)}" />
  <title>MaxBits · Daily Tech Watch · {escape(date_str)}</title>
"""

    # CSS come stringa normale (non f-string → { } liberi)
    style_block = """
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: #111;
      background: #fafafa;
      margin: 0;
      padding: 24px;
    }
    .mb-container {
      max-width: 900px;
      margin: 0 auto;
      background: #fff;
      padding: 24px 32px;
      border-radius: 8px;
      box-shadow: 0 0 12px rgba(0,0,0,0.05);
    }
    .mb-header { margin-bottom: 24px; }
    .mb-title { margin: 0; font-size: 26px; }
    .mb-subtitle { margin: 4px 0 0 0; color: #444; font-size: 13px; }
    .mb-date { margin: 4px 0 0 0; color: #555; font-size: 13px; }

    .mb-weekly-bar {
      margin-top: 10px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .mb-btn-primary {
      background: #0052cc;
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
    }
    .mb-btn-primary:hover { background: #003f9e; }
    .mb-weekly-help { font-size: 12px; color: #777; }

    .mb-history-box {
      margin-top: 14px;
      padding: 10px 12px;
      border-radius: 6px;
      background: #f5f5f5;
    }
    .mb-history-title { font-size: 13px; }
    .mb-history-list {
      margin: 6px 0 0 16px;
      padding: 0;
      font-size: 12px;
    }
    .mb-history-list li { margin-bottom: 2px; }

    .mb-section-title { margin: 0 0 12px 0; font-size: 22px; }

    .mb-article {
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #eee;
      page-break-inside: avoid;
    }
    .mb-article-title { margin: 0 0 4px 0; font-size: 20px; }
    .mb-article-link { color: #0052cc; text-decoration: none; }
    .mb-article-link:hover { text-decoration: underline; }
    .mb-article-meta { margin: 0; color: #777; font-size: 13px; }

    .mb-bullets {
      margin: 10px 0 0 20px;
      padding: 0;
      font-size: 14px;
      list-style: disc;
    }
    .mb-bullets li { margin-bottom: 4px; }

    .mb-weekly-label {
      margin-top: 10px;
      display: inline-flex;
      gap: 6px;
      font-size: 13px;
      color: #333;
    }

    .mb-watch-section { margin-top: 18px; page-break-inside: avoid; }
    .mb-watch-title { margin: 0 0 6px 0; font-size: 16px; }
    .mb-watch-list {
      margin: 0 0 0 18px;
      padding: 0;
      list-style: disc;
      font-size: 14px;
    }
    .mb-watch-item { margin-bottom: 4px; }
    .mb-watch-link { color: #0052cc; text-decoration: none; }
    .mb-watch-link:hover { text-decoration: underline; }
    .mb-watch-source { color: #777; font-size: 12px; margin-left: 2px; }
    .mb-watch-weekly { margin-left: 8px; font-size: 12px; color: #333; }

    a { word-wrap: break-word; }
    @page { margin: 15mm; }
  </style>
</head>
<body>
  <div class="mb-container">
"""

    body_content = f"""
    {header}

    <section style="margin-top: 30px;">
      <h2 class="mb-section-title">3 deep-dives you should really read</h2>
      {deep_html}
    </section>

    <section style="margin-top: 30px;">
      <h2 style="margin:0 0 12px 0; font-size:20px;">
        Curated watchlist · 3–5 links per topic
      </h2>
      {wl_html}
    </section>
  </div>
"""

    # JS blocco normale (non f-string → { } liberi)
    script_block = """
<script>
(function() {
  const KEY = "maxbits_weekly_selections_v1";

  function loadSel() {
    try {
      const raw = localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function saveSel(x) {
    try {
      localStorage.setItem(KEY, JSON.stringify(x));
    } catch (e) {}
  }

  function setupCheckboxes() {
    const meta = document.querySelector("meta[name='report-date']");
    if (!meta) return;
    const date = meta.content || "";
    const data = loadSel();
    const todays = data[date] || [];

    document.querySelectorAll(".weekly-checkbox").forEach(cb => {
      const id = cb.dataset.id;
      if (!id) return;

      if (todays.some(a => a.id === id)) {
        cb.checked = true;
      }

      cb.addEventListener("change", () => {
        const entry = {
          id: cb.dataset.id,
          title: cb.dataset.title,
          url: cb.dataset.url,
          source: cb.dataset.source
        };
        const arr = data[date] || [];
        const i = arr.findIndex(a => a.id === entry.id);

        if (cb.checked && i === -1) arr.push(entry);
        if (!cb.checked && i !== -1) arr.splice(i, 1);

        data[date] = arr;
        saveSel(data);
      });
    });
  }

  function openWeekly() {
    const data = loadSel();
    const dates = Object.keys(data).sort().reverse();
    const win = window.open("", "_blank");
    if (!win) {
      alert("Popup blocked – allow popups to see the weekly view.");
      return;
    }

    let html = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>MaxBits · Weekly Selection</title></head>";
    html += "<body style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;font-size:14px;color:#111;background:#fafafa;margin:0;padding:24px;'>";
    html += "<div style='max-width:900px;margin:0 auto;background:#fff;padding:24px 32px;border-radius:8px;box-shadow:0 0 12px rgba(0,0,0,0.04);'>";
    html += "<h1 style='margin:0 0 8px 0;font-size:22px;'>MaxBits · Weekly Selection (local)</h1>";
    html += "<p style='margin:0 0 16px 0;color:#555;font-size:13px;'>Questa pagina è generata solo dal tuo browser (localStorage), non viene salvata sul server.</p>";

    if (!dates.length) {
      html += "<p>No weekly selections saved yet.</p>";
    } else {
      dates.forEach(d => {
        const items = data[d] || [];
        if (!items.length) return;
        html += "<section style='margin-top:16px;'><h2 style=\"font-size:18px;margin:0 0 6px 0;\">Day " + d + "</h2><ul style='margin:4px 0 0 18px;font-size:14px;'>";
        items.forEach(it => {
          const t = it.title || "";
          const u = it.url || "#";
          const s = it.source || "";
          html += "<li style='margin-bottom:4px;'><a href='" + u + "' target='_blank' rel='noopener' style='color:#0052cc;'>" +
                  t + "</a><span style='color:#777;font-size:12px;margin-left:4px;'>(" + s + ")</span></li>";
        });
        html += "</ul></section>";
      });
    }

    html += "</div></body></html>";
    win.document.open();
    win.document.write(html);
    win.document.close();
  }

  function initWeeklyBtn() {
    const btn = document.getElementById("open-weekly-btn");
    if (btn) btn.addEventListener("click", openWeekly);
  }

  function initHistory() {
    const hist = window.MAXBITS_HISTORY || [];
    const ul = document.getElementById("history-list");
    if (!ul || !hist.length) return;

    ul.innerHTML = hist.slice(0, 7).map(it =>
      "<li><strong>" + it.date + "</strong> – " +
      "<a href='" + it.html + "' target='_blank' rel='noopener'>HTML</a> · " +
      "<a href='" + it.pdf + "' target='_blank' rel='noopener'>PDF</a></li>"
    ).join("");
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupCheckboxes();
    initWeeklyBtn();
    initHistory();
  });
})();
</script>
</body>
</html>
"""

    return head_open + style_block + body_content + script_block
