from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = BASE_DIR / "reports" / "json"
DOCS_DIR = BASE_DIR / "docs"
WEEKLY_DIR = DOCS_DIR / "weekly"


@dataclass
class WeeklyItem:
    date: str
    title: str
    url: str
    source: Optional[str] = None
    topic: Optional[str] = None
    why: Optional[str] = None


def _parse_deep_dives_json(path: Path, date_str: str) -> List[WeeklyItem]:
    """Parsa un singolo JSON di deep-dives in modo super robusto."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WEEKLY] Cannot parse JSON {path}: {e!r}")
        return []

    # flessibile: list diretta, o dizionari con chiavi diverse
    if isinstance(raw, list):
        articles = raw
    elif isinstance(raw, dict):
        articles = (
            raw.get("deep_dives")
            or raw.get("items")
            or raw.get("articles")
            or []
        )
    else:
        print(f"[WEEKLY] Unexpected JSON structure in {path}")
        return []

    if not isinstance(articles, list):
        print(f"[WEEKLY] 'articles' in {path} is not a list, skipping")
        return []

    out: List[WeeklyItem] = []
    for a in articles:
        if not isinstance(a, dict):
            continue

        title = str(a.get("title") or "").strip()
        url = (
            a.get("url")
            or a.get("link")
            or a.get("source_url")
            or ""
        )
        url = str(url).strip()

        if not title or not url:
            continue

        source = str(a.get("source") or a.get("site") or "").strip() or None
        topic = (
            a.get("topic")
            or a.get("category")
            or a.get("section")
        )
        topic = str(topic).strip() if topic else None

        why = (
            a.get("why_it_matters")
            or a.get("why")
            or a.get("summary")
        )
        why = str(why).strip() if why else None

        out.append(
            WeeklyItem(
                date=date_str,
                title=title,
                url=url,
                source=source,
                topic=topic,
                why=why,
            )
        )

    print(f"[WEEKLY] Parsed {len(out)} items from {path.name}")
    return out


def _load_last_7_days_deep_dives() -> List[WeeklyItem]:
    """Carica i deep-dives degli ultimi 7 giorni (se presenti)."""
    if not JSON_DIR.exists():
        print(f"[WEEKLY] JSON directory not found: {JSON_DIR}")
        return []

    pattern = re.compile(r"deep_dives_(\d{4}-\d{2}-\d{2})\.json$")
    files: List[tuple[str, Path]] = []

    for f in JSON_DIR.glob("deep_dives_*.json"):
        m = pattern.match(f.name)
        if not m:
            continue
        date_str = m.group(1)
        files.append((date_str, f))

    if not files:
        print("[WEEKLY] No deep_dives_*.json files found.")
        return []

    # ordino per data discendente
    files.sort(key=lambda x: x[0], reverse=True)

    today = datetime.utcnow().date()
    cutoff = today - timedelta(days=7)

    all_items: List[WeeklyItem] = []
    for date_str, path in files:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue

        if d < cutoff:
            # fermiamoci quando usciamo dalla finestra 7 giorni
            continue

        items = _parse_deep_dives_json(path, date_str)
        all_items.extend(items)

    if not all_items:
        print("[WEEKLY] No deep-dive items collected.")
        return []

    # dedup per URL (mantieni il più recente)
    dedup: Dict[str, WeeklyItem] = {}
    for item in sorted(all_items, key=lambda i: i.date, reverse=True):
        if item.url not in dedup:
            dedup[item.url] = item

    final_list = list(dedup.values())
    print(f"[WEEKLY] Total unique items for weekly: {len(final_list)}")
    return final_list


def _group_by_topic(items: List[WeeklyItem]) -> Dict[str, List[WeeklyItem]]:
    groups: Dict[str, List[WeeklyItem]] = {}
    for it in items:
        topic = it.topic or "General"
        groups.setdefault(topic, []).append(it)

    # ordino gli articoli per data decrescente dentro ogni topic
    for topic in groups:
        groups[topic].sort(key=lambda i: i.date, reverse=True)

    return dict(sorted(groups.items(), key=lambda kv: kv[0].lower()))


def _build_html(items: List[WeeklyItem]) -> str:
    today = datetime.utcnow().date().isoformat()

    if not items:
        body_html = """
        <p style="font-size:14px; color:#6b7280;">
          No deep-dive articles collected in the last 7 days.
        </p>
        """
    else:
        groups = _group_by_topic(items)
        blocks: List[str] = []
        for topic, group_items in groups.items():
            rows: List[str] = []
            for it in group_items:
                badge = (
                    f'<span class="tag">{it.source}</span>'
                    if it.source
                    else ""
                )
                why_html = (
                    f'<p class="why">{it.why}</p>'
                    if it.why
                    else ""
                )
                rows.append(
                    f"""
            <article class="item">
              <h3>
                <a href="{it.url}" target="_blank" rel="noopener">
                  {it.title}
                </a>
              </h3>
              <div class="meta">
                <span class="date">{it.date}</span>
                {badge}
              </div>
              {why_html}
            </article>
            """
                )

            blocks.append(
                f"""
        <section class="topic">
          <h2>{topic}</h2>
          {''.join(rows)}
        </section>
        """
            )

        body_html = "\n".join(blocks)

    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MaxBits · Weekly Selection</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      --bg: #020617;
      --card-bg: #020617;
      --accent: #25A7FF;
      --accent-soft: rgba(37,167,255,0.12);
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
      --border: #1f2937;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 24px 16px 40px;
      background: radial-gradient(circle at top left, #020617, #020617);
      font-family: -apple-system, BlinkMacSystemFont, system-ui, "Segoe UI", sans-serif;
      color: var(--text-main);
    }}
    .page {{
      max-width: 900px;
      margin: 0 auto;
    }}
    header {{
      display:flex;
      justify-content: space-between;
      align-items: center;
      gap:16px;
      margin-bottom: 18px;
    }}
    .title-block h1 {{
      margin: 0;
      font-size: 22px;
      letter-spacing: 0.02em;
    }}
    .subtitle {{
      margin: 3px 0 0;
      font-size: 13px;
      color: var(--text-muted);
    }}
    .badge-date {{
      font-size: 11px;
      padding: 4px 9px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--text-muted);
    }}
    .back-btn {{
      border-radius: 999px;
      padding: 6px 14px;
      border: 1px solid var(--border);
      background: var(--accent-soft);
      color: #e5f2ff;
      font-size: 12px;
      cursor: pointer;
    }}
    .back-btn:hover {{
      background: rgba(37,167,255,0.25);
    }}
    main {{
      background: radial-gradient(circle at top left, rgba(37,167,255,0.12), #020617);
      border-radius: 18px;
      padding: 20px 18px 24px;
      border: 1px solid var(--border);
      box-shadow: 0 20px 40px rgba(0,0,0,0.8);
    }}
    .topic {{
      margin-bottom: 20px;
    }}
    .topic h2 {{
      margin: 0 0 8px;
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--text-muted);
    }}
    .item {{
      padding: 10px 0;
      border-top: 1px solid rgba(148,163,184,0.35);
    }}
    .item:first-of-type {{
      border-top: none;
    }}
    .item h3 {{
      margin: 0 0 4px;
      font-size: 15px;
    }}
    .item a {{
      color: #bfdbfe;
      text-decoration: none;
    }}
    .item a:hover {{
      text-decoration: underline;
    }}
    .meta {{
      font-size: 11px;
      color: var(--text-muted);
      display:flex;
      align-items:center;
      gap:8px;
      margin-bottom: 4px;
    }}
    .tag {{
      padding: 1px 7px;
      border-radius: 999px;
      border: 1px solid rgba(148,163,184,0.7);
      font-size: 10px;
    }}
    .why {{
      margin: 0;
      font-size: 13px;
      color: #e5e7eb;
    }}
    footer {{
      margin-top: 18px;
      font-size: 11px;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <div class="title-block">
        <h1>MaxBits · Weekly Selection</h1>
        <p class="subtitle">
          A curated view of the key deep-dives from the last 7 days. Updated weekly.
        </p>
      </div>
      <div style="display:flex; flex-direction:column; align-items:flex-end; gap:6px;">
        <span class="badge-date">Week ending {today}</span>
        <button class="back-btn" type="button" onclick="window.location.href='../index.html'">
          ⬅ Back to today’s report
        </button>
      </div>
    </header>

    <main>
      {body_html}
    </main>

    <footer>
      Weekly report is generated automatically from the same curated sources used
      for the daily MaxBits report.
    </footer>
  </div>
</body>
</html>
"""
    return template


def build_weekly() -> None:
    print("[WEEKLY] Building weekly report...")
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

    items = _load_last_7_days_deep_dives()
    html = _build_html(items)

    out_path = WEEKLY_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[WEEKLY] Weekly HTML written to: {out_path}")


if __name__ == "__main__":
    build_weekly()
