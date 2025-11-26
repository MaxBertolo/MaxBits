from typing import List, Dict
import os

from groq import Groq
from .models import RawArticle

# Client Groq (legge GROQ_API_KEY dall'ambiente)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# Modello Groq da usare (ha free tier)
GROQ_MODEL = "llama-3.1-8b-instant"


def build_prompt(article: RawArticle) -> str:
    return f"""
Sei un analista tecnologico che scrive per un manager italiano.

Leggi questa notizia (titolo, fonte, contenuto) e produci ESATTAMENTE 5 FRASI in italiano.
Ogni frase MAX 30 parole.

Scrivi nel formato seguente (usa queste etichette):

COS'E: ...
CHI: ...
COSA FA: ...
PERCHE E' INTERESSANTE: ...
PROSPETTIVE FUTURE: ...

Linee guida:
- COS'E: tipo di novità (prodotto, partnership, acquisizione, trend, regolazione, ecc.)
- CHI: aziende, enti o team principali coinvolti
- COSA FA: cosa abilita, introduce o cambia in pratica
- PERCHE E' INTERESSANTE: impatto per Telco/Media/Tech/AI e per un manager
- PROSPETTIVE FUTURE: cosa potrebbe succedere nei prossimi 6-24 mesi se la notizia si consolida

Titolo: {article.title}
Fonte: {article.source}
URL: {article.url}

Contenuto:
{article.content}
"""


def _fallback_summary(article: RawArticle, reason: str) -> Dict[str, str]:
    """
    Se Groq non risponde, creiamo un riassunto di emergenza.
    """
    msg = f"Riassunto non disponibile ({reason}). Leggere l'articolo completo dal link."
    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "cos_e": msg,
        "chi": "—",
        "cosa_fa": "—",
        "perche_interessante": "—",
        "pov": "—",
    }


def summarize_with_groq(article: RawArticle) -> Dict[str, str]:
    if not GROQ_API_KEY:
        # Nessuna API key configurata
        return _fallback_summary(article, "GROQ_API_KEY mancante")

    prompt = build_prompt(article)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.2,
            max_tokens=512,
            messages=[
                {
                    "role": "system",
                    "content": "Sei un analista esperto di tecnologia, telecomunicazioni e media.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
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
            if upper.startswith("COS'E:") or upper.startswith("COS’È:") or upper.startswith("COSA E':"):
                result["cos_e"] = line.split(":", 1)[1].strip()
            elif upper.startswith("CHI:"):
                result["chi"] = line.split(":", 1)[1].strip()
            elif upper.startswith("COSA FA:"):
                result["cosa_fa"] = line.split(":", 1)[1].strip()
            elif upper.startswith("PERCHE E' INTERESSANTE:") or upper.startswith("PERCHÉ È INTERESSANTE:"):
                result["perche_interessante"] = line.split(":", 1)[1].strip()
            elif upper.startswith("PROSPETTIVE FUTURE:"):
                result["pov"] = line.split(":", 1)[1].strip()

        # Se qualcosa è rimasto vuoto, mettiamo un fallback minimale
        if not any(result.values()):
            return _fallback_summary(article, "risposta Groq non parsabile")

        return {
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "published_at": article.published_at.isoformat(),
            **result,
        }

    except Exception as e:
        print("[WARN] Groq summarization failed:", repr(e))
        return _fallback_summary(article, "errore Groq")


def summarize_article(article: RawArticle, model: str, temperature: float, max_tokens: int) -> Dict[str, str]:
    """
    Entry point usato da main.py.
    Ignora model/temperature/max_tokens del config e usa Groq.
    """
    return summarize_with_groq(article)


def summarize_articles(articles: List[RawArticle], model: str, temperature: float, max_tokens: int) -> List[Dict]:
    summarized = []
    for a in articles:
        summarized.append(summarize_article(a, model=model, temperature=temperature, max_tokens=max_tokens))
    return summarized
