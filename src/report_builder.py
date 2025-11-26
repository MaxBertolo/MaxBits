from typing import List, Dict
from datetime import datetime


def build_html_report(summaries: List[Dict], date_str: str | None = None) -> str:
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    parts = []
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append(f"<title>MaxBits Tech Daily {date_str}</title></head><body>")
    parts.append(f"<h1>MaxBits – Daily Tech Briefing – {date_str}</h1>")
    parts.append("<p>Selezione automatica di notizie su tecnologia / AI / media.</p>")
    parts.append("<hr>")

    for item in summaries:
        parts.append("<div style='margin-bottom: 20px;'>")
        parts.append(f"<h3>{item['title']}</h3>")
        parts.append(f"<p><b>Fonte:</b> {item['source']} – <a href='{item['url']}'>link</a></p>")
        parts.append("<ul>")
        parts.append(f"<li><b>COS'È:</b> {item['cos_e']}</li>")
        parts.append(f"<li><b>CHI LA FA:</b> {item['chi']}</li>")
        parts.append(f"<li><b>COSA FA:</b> {item['cosa_fa']}</li>")
        parts.append(f"<li><b>PERCHE È INTERESSANTE:</b> {item['perche_interessante']}</li>")
        parts.append(f"<li><b>PUNTO DI VISTA:</b> {item['pov']}</li>")
        parts.append("</ul>")
        parts.append("</div><hr>")

    parts.append("</body></html>")
    return "\n".join(parts)
