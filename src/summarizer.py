import os
from typing import List, Dict
from openai import OpenAI
from .models import RawArticle

# il client usa OPENAI_API_KEY dall'ambiente (GitHub Actions secret)
client = OpenAI()


def build_prompt(article: RawArticle) -> str:
    return f"""
Sei un analista tecnologico che scrive per un manager italiano.

Leggi questa notizia (titolo, fonte, contenuto) e produci ESATTAMENTE 5 frasi in italiano.
Ogni frase MAX 25 parole.

1) COS'È: tipo di novità (prodotto, partnership, acquisizione, trend, regolazione, ecc.).
2) CHI LA FA: aziende/enti principali coinvolti.
3) COSA FA: cosa introduce, abilita o cambia.
4) PERCHÉ È INTERESSANTE: impatto per Telco/Media/Tech.
5) PUNTO DI VISTA: mini commento strategico, neutro ma con insight.

Rispetta il formato:

COS'E: ...
CHI LA FA: ...
COSA FA: ...
PERCHE E' INTERESSANTE: ...
PUNTO DI VISTA: ...

Titolo: {article.title}
Fonte: {article.source}
URL: {article.url}

Contenuto:
{article.content}
"""


def summarize_article(article: RawArticle, model: str, temperature: float, max_tokens: int) -> Dict[str, str]:
    prompt = build_prompt(article)

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": "Sei un assistente esperto di tecnologia, telco e media."},
            {"role": "user", "content": prompt},
        ],
    )

    text = response.choices[0].message.content.strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "cos_e": "",
        "chi": "",
        "cosa_fa": "",
        "perche_interessante": "",
        "pov": "",
    }

    for line in lines:
        upper = line.upper()
        if upper.startswith("COS'E:") or upper.startswith("COS'È:") or upper.startswith("COSA E':"):
            result["cos_e"] = line.split(":", 1)[1].strip()
        elif upper.startswith("CHI LA FA:"):
            result["chi"] = line.split(":", 1)[1].strip()
        elif upper.startswith("COSA FA:"):
            result["cosa_fa"] = line.split(":", 1)[1].strip()
        elif upper.startswith("PERCHE E' INTERESSANTE:") or upper.startswith("PERCHÉ È INTERESSANTE:"):
            result["perche_interessante"] = line.split(":", 1)[1].strip()
        elif upper.startswith("PUNTO DI VISTA:"):
            result["pov"] = line.split(":", 1)[1].strip()

    return result


def summarize_articles(articles: List[RawArticle], model: str, temperature: float, max_tokens: int) -> List[Dict]:
    summarized = []
    for a in articles:
        fields = summarize_article(a, model=model, temperature=temperature, max_tokens=max_tokens)
        summarized.append({
            "title": a.title,
            "url": a.url,
            "source": a.source,
            "published_at": a.published_at.isoformat(),
            **fields,
        })
    return summarized
