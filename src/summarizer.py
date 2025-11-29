from datetime import datetime
from jinja2 import Template
from html import escape

TOPICS = {
    "Media, TV & Streaming": [
        "advanced television", "fierce video", "marketing dive", "adweek",
        "wired – business", "techcrunch mobility", "ieee spectrum – robotics"
    ],

    "Telco & 5G": [
        "fierce telecom", "fierce wireless", "telecoms.com",
        "light reading", "capacity media"
    ],

    "AI · Cloud · Tech": [
        "techcrunch ai", "ars technica", "the verge", "wired – tech",
        "data center knowledge", "data center dynamics",
        "the hacker news", "robotics 247"
    ],

    "Space & Infrastructure": [
        "space news", "satnews", "varda", "space.com"
    ],
}


def classify_topic(article):
    source = article["source"].lower()
    for topic, keywords in TOPICS.items():
        for kw in keywords:
            if kw in source:
                return topic
    return "Other"


def build_html_report(deep_dive_articles, watchlist_articles, date_str):
    """
    deep_dive_articles: primi 3 articoli con analisi LLM
    watchlist_articles: tutti gli altri articoli (senza analisi)
    """

    # Classifica le notizie nella watchlist
    grouped = {topic: [] for topic in TOPICS.keys()}
    grouped["Other"] = []

    for a in watchlist_articles:
        topic = classify_topic(a)
        grouped[topic].append(a)

    # Prendi 3–5 per topic
    final_groups = {
        topic: items[:5]
        for topic, items in grouped.items()
    }

    template_str = """
    <html>
    <head>
        <style>
            body { font-family: Arial; margin: 35px; }
            h1 { color: #003366; }
            h2 { color: #005599; margin-top: 35px; }
            h3 { color: #0088cc; }
            .box { margin-bottom: 25px; padding: 15px; border: 1px solid #ccc; border-radius: 8px; }
            a { color: #0088cc; text-decoration: none; }
        </style>
    </head>
    <body>

        <h1>MaxBits Daily Tech Report</h1>
        <p><b>Date:</b> {{ date_str }} |
           <b>Focus:</b> Telco · Media · Streaming · AI · Cloud · Space</p>

        <h2>1. Deep Dive – Executive Summary (3 key stories)</h2>

        {% for a in deep_dive %}
            <div class="box">
                <h3>{{ a.title_clean }}</h3>
                <p><b>Source:</b> {{ a.source }} |
                   <b>Published:</b> {{ a.published_at }} |
                   <a href="{{ a.url }}">Open article</a></p>

                <p><b>WHAT IT IS</b><br>{{ a.what_it_is }}</p>
                <p><b>WHO</b><br>{{ a.who }}</p>
                <p><b>WHAT IT DOES</b><br>{{ a.what_it_does }}</p>
                <p><b>WHY IT MATTERS</b><br>{{ a.why_it_matters }}</p>
                <p><b>STRATEGIC VIEW</b><br>{{ a.strategic_view }}</p>
            </div>
        {% endfor %}

        <h2>2. Watchlist by Topic (3–5 per category)</h2>

        {% for topic, items in groups.items() %}
            <h3>{{ topic }}</h3>
            <ul>
            {% for a in items %}
                <li><a href="{{ a.url }}">{{ a.title_clean }}</a> — {{ a.source }}</li>
            {% endfor %}
            </ul>
        {% endfor %}

    </body>
    </html>
    """

    template = Template(template_str)
    return template.render(
        date_str=date_str,
        deep_dive=deep_dive_articles,
        groups=final_groups
    )
