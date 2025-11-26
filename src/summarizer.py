from typing import List, Dict
import os
import requests

from openai import OpenAI
from .models import RawArticle

# Client OpenAI (usa OPENAI_API_KEY dall'ambiente)
client = OpenAI()

# Config HuggingFace
HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_MODEL_ID = "facebook/bart-large-cnn"  # modello di summarization free


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


def _structured_fallback(article: RawArticle, text: str, reason: str) -> Dict[str, str]:
    """
    Usa un unico riassunto (es. da HuggingFace) e lo mappa
    nei 5 campi in modo semplice.
    """
    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "cos_e": text,
        "chi": "—",
        "cosa_fa": "—",
        "perche_interessante": f"Generato via fallback ({reason}).",
        "pov": "Per maggiori dettagli, leggere l'articolo completo dal link.",
    }


# --------- OPENAI PRIMARIO ---------
def summarize_with_openai(article: RawArticle, model: str, temperature: float, max_tokens: int) -> Dict[str, str]:
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

    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        **result,
    }


# --------- HUGGINGFACE FALLBACK ---------
def summarize_with_huggingface(article: RawArticle) -> Dict[str, str]:
    """
    Fallback gratuito: usa HuggingFace Inference API.
    """
    if not HF_API_KEY:
        # Nessuna chiave → fallback testuale semplice
        msg = "Riassunto non disponibile (HF_API_KEY mancante)."
        return _structured_fallback(article, msg, "HuggingFace non configurato")

    endpoint = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": article.content or (article.title + " " + article.url),
        "parameters": {"max_length": 200, "min_length": 60, "do_sample": False},
    }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        # formato tipico: [{"summary_text": "..."}]
        if isinstance(data, list) and len(data) > 0 and "summary_text" in data[0]:
            summary_text = data[0]["summary_text"]
        else:
            summary_text = str(data)
        return _structured_fallback(article, summary_text, "HuggingFace")
    except Exception as e:
        print("[WARN] HuggingFace fallback failed:", repr(e))
        msg = "Riassunto non disponibile (errore HuggingFace)."
        return _structured_fallback(article, msg, "errore HF")


# --------- ENTRY POINT USATO DA main.py ---------
def summarize_article(article: RawArticle, model: str, temperature: float, max_tokens: int) -> Dict[str, str]:
    """
    1) Prova OpenAI
    2) Se QUALSIASI errore → passa a HuggingFace
    """
    try:
        return summarize_with_openai(article, model=model, temperature=temperature, max_tokens=max_tokens)
    except Exception as e:
        print("[WARN] OpenAI summarization failed, uso HuggingFace:", repr(e))
        return summarize_with_huggingface(article)


def summarize_articles(articles: List[RawArticle], model: str, temperature: float, max_tokens: int) -> List[Dict]:
    summarized = []
    for a in articles:
        summarized.append(summarize_article(a, model=model, temperature=temperature, max_tokens=max_tokens))
    return summarized
