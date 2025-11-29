from typing import List, Dict
from jinja2 import Template
import re
import html

from .models import RawArticle


# ================== TOPIC MAPPING ==================

TOPICS = {
    "Media, TV & Streaming": [
        "advanced television",
        "fierce video",
        "marketing dive",
        "adweek",
        "wired – business",
        "wired - business",
        "techcrunch mobility",
    ],
    "Telco & 5G": [
        "fierce telecom",
        "fierce wireless",
        "telecoms.com",
        "light reading",
        "capacity media",
    ],
    "AI · Cloud · Tech": [
        "techcrunch ai",
        "ars technica",
        "the verge",
        "wired – tech",
        "wired - tech",
        "data center knowledge",
        "data center dynamics",
        "the hacker news",
        "robotics 247",
        "robotics247",
    ],
    "Space & Infrastructure": [
        "space news",
        "satnews",
        "spacenews",
        "space.com",
    ],
}


def strip_html_title(raw_title: str) -> str:
    if not raw_title:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_title)
    text = html.unescape(text)
    return text.strip()


def classify_topic(article: RawArticle) -> str:
    source = (article.source or "").lower()
    for topic, keywords in TOPICS.items():
        for kw in keywords:
            if kw in source:
                return topic
    return "Other"


# ================== HTML REPORT ==================


def build_html_report(
    deep_dive_summaries: List[Dict],
    watchlist_articles: List[RawArticle],
    date_str: str,
) -> str:
    """
    deep_dive_summaries: output di summarize_articles (3 articoli)
    watchlist_articles: lista di RawArticle (tutti i candidati interessanti)
    """

    # ---- Normalizza deep-dive (già riassunti dal LLM) ----
    deep_dive = []
    for d in deep_dive_summaries:
        deep_dive.append(
            {
                "title_clean": d.get("title_clean") or strip_html_title(d.get("title", "")),
                "source": d.get("source", ""),
                "published_at": d.get("published_at", ""),
                "url": d.get("url", ""),
                "what_it_is": d.get("what_it_is", ""),
                "who": d.get("who", ""),
                "what_it_does": d.get("what_it_does", ""),
                "why_it_matters": d.get("why_it_matters", ""),
                "strategic_view": d.get("strategic_view", ""),
            }
        )

    # ---- Classifica watchlist per topic ----
    grouped: Dict[str, List[Dict]] = {topic: [] for topic in TOPICS.keys()}
    grouped["Other"] = []

    for art in watchlist_articles:
        topic = classify_topic(art)
        grouped[topic].append(
            {
                "title_clean": strip_html_title(art.title),
                "url": art.url,
                "source": art.source,
            }
        )

    # Limita a 3–5 articoli per topic
    final_groups: Dict[str, List[Dict]] = {}
    for topic, items in grouped.items():
        if not items:
            continue
        final_groups[topic] = items[:5]

    # ---- Template HTML ----
    template_str = """
    <html>
    <head>
        <meta charset="utf-8" />
        <style>
            body { font-family: Arial, sans-serif; margin: 35px; }
            h1 { color: #003366; }
            h2 { color: #005599; margin-top: 32px; }
            h3 { color: #0088cc; margin-top: 24px; }
            .box {
                margin-bottom: 24px;
                padding: 16px;
                border: 1px solid #ccc;
                border-radius: 8px;
                background-color: #fafafa;
            }
            .meta {
                font-size: 0.9em;
                color: #555;
                margin-bottom: 8px;
            }
            a { color: #0088cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>

        <h1>MaxBits Daily Tech Report</h1>
        <p>
            <b>Date:</b> {{ date_str }}<br/>
            <b>Scope:</b> Telco · Media · Streaming · AI · Cloud · Space · Infrastructure
        </p>

        <h2>1. Deep Dive – Executive Summary (3 key stories)</h2>

        {% for a in deep_dive %}
            <div class="box">
                <h3>{{ a.title_clean }}</h3>
                <p class="meta">
                    <b>Source:</b> {{ a.source }}
                    {% if a.published_at %}| <b>Published:</b> {{ a.published_at }}{% endif %}
                    {% if a.url %}| <a href="{{ a.url }}">Open article</a>{% endif %}
                </p>

                <p><b>WHAT IT IS</b><br/>{{ a.what_it_is }}</p>
                <p><b>WHO</b><br/>{{ a.who }}</p>
                <p><b>WHAT IT DOES</b><br/>{{ a.what_it_does }}</p>
                <p><b>WHY IT MATTERS</b><br/>{{ a.why_it_matters }}</p>
                <p><b>STRATEGIC VIEW</b><br/>{{ a.strategic_view }}</p>
            </div>
        {% endfor %}

        <h2>2. Watchlist by Topic (3–5 stories per category)</h2>

        {% for topic, items in groups.items() %}
            <h3>{{ topic }}</h3>
            <ul>
            {% for a in items %}
                <li>
                    <a href="{{ a.url }}">{{ a.title_clean }}</a>
                    – {{ a.source }}
                </li>
            {% endfor %}
            </ul>
        {% endfor %}

    </body>
    </html>
    """

    template = Template(template_str)
    return template.render(
        date_str=date_str,
        deep_dive=deep_dive,
        groups=final_groups,
    )
