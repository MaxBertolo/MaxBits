from typing import List, Dict
from datetime import datetime
import os
import json

import google.generativeai as genai

from .models import RawArticle


# Config Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-1.5-flash"


def _configure_gemini():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY non impostata nelle variabili d'ambiente.")
    genai.configure(api_key=GEMINI_API_KEY)


def build_prompt(article: RawArticle) -> str:
    """
    Prompt in italiano, stile approfondito per manager Telco/Media.
    """
    return f"""
Sei un analista senior che scrive per il CTO di una Media & Telco company.

Devi leggere la NOTIZIA (titolo + contenuto) ed estrarre un'analisi strutturata e APPROFONDITA.

### OBIETTIVO

Produrre un oggetto JSON con questo schema ESATTO (nessun testo fuori dal JSON):

{{
  "cose": "...",
  "chi": "...",
  "cosa_fa": "...",
  "perche_interessante": "...",
  "pov": "..."
}}

### LINEE GUIDA

- Scrivi in italiano.
- Tono professionale, chiaro, orientato al business, non accademico.
- Ogni campo deve contenere un paragrafo di 2–3 frasi, MA NON romanzi.
- Evita frasi vaghe come "è importante" senza dire perché.
- Non inventare aziende o dati che non sono nel testo.

DETTAGLIO CAMPI:

- "cose":
    2–3 frasi che spiegano COS'È la notizia.
    Es: tipo di novità (prodotto, acquisizione, partnership, standard, regolazione, trend di mercato, dati di ricerca, ecc.).
- "chi":
    2 frasi su chi sono gli attori principali (aziende, enti, ruoli) e che ruolo giocano.
- "cosa_fa":
    2–3 frasi che descrivono cosa abilita o cambia in concreto
    (funzionalità, tecnologia principale, use case, segmenti coinvolti).
- "perche_interessante":
    2–3 frasi su perché è rilevante per Telco, Media, Tech, AI.
    Collega, se possibile, a temi come: reti, cloud, AI, advertising, streaming, robotica, data center, infrastrutture.
- "pov":
    2–3 frasi di punto di vista strategico:
    impatto 6–24 mesi, rischi/opportunità, possibili implicazioni per player come Sky, operatori Telco, broadcaster, OTT.

### FORMATO OBBLIGATORIO

- Rispondi SOLO con un JSON valido.
- Nessun commento, nessun markdown, niente testo prima o dopo.
- Non mandare mai "```json" o simili.

### DATI NOTIZIA

Titolo: {article.title}
Fonte: {article.source}
URL: {article.url}

Contenuto:
{article.content}
"""


def _fallback_summary(article: RawArticle, reason: str) -> Dict[str, str]:
    """
    Fallback se la chiamata a Gemini fallisce o l'output non è parsabile.
    Meglio un messaggio chiaro che un testo confuso.
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


def summarize_with_gemini(article: RawArticle, model: str, temperature: float, max_tokens: int) -> Dict[str, str]:
    """
    Chiama Gemini e restituisce un dizionario strutturato con i 5 campi.
    """
    try:
        _configure_gemini()
    except Exception as e:
        print("[LLM] Gemini non configurato:", repr(e))
        return _fallback_summary(article, "Gemini non configurato")

    mdl_name = model or GEMINI_MODEL
    prompt = build_prompt(article)

    try:
        mdl = genai.GenerativeModel(mdl_name)
        response = mdl.generate_content(
            prompt,
            generation_config={
                "temperature": float(temperature),
                "max_output_tokens": int(max_tokens),
            },
        )
        text = (response.text or "").strip()
    except Exception as e:
        print("[LLM] Errore chiamando Gemini:", repr(e))
        return _fallback_summary(article, "errore chiamata Gemini")

    if not text:
        return _fallback_summary(article, "risposta vuota")

    # A volte i modelli aggiungono ```json ... ```
    cleaned = text
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    try:
        data = json.loads(cleaned)
    except Exception as e:
        print("[LLM] Impossibile fare parse del JSON:", repr(e))
        print("[LLM] Output ricevuto:", text[:500])
        return _fallback_summary(article, "JSON non parsabile")

    # Normalizziamo i campi
    cose = data.get("cose", "").strip()
    chi = data.get("chi", "").strip()
    cosa_fa = data.get("cosa_fa", "").strip()
    perche = data.get("perche_interessante", "").strip()
    pov = data.get("pov", "").strip()

    # Se per qualche motivo i campi sono vuoti → fallback
    if not any([cose, chi, cosa_fa, perche, pov]):
        return _fallback_summary(article, "campi vuoti")

    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "cos_e": cose,
        "chi": chi,
        "cosa_fa": cosa_fa,
        "perche_interessante": perche,
        "pov": pov,
    }


def summarize_article(article: RawArticle, model: str, temperature: float, max_tokens: int) -> Dict[str, str]:
    """
    Entry point usato da main.py.
    """
    return summarize_with_gemini(article, model=model, temperature=temperature, max_tokens=max_tokens)


def summarize_articles(articles: List[RawArticle], model: str, temperature: float, max_tokens: int) -> List[Dict]:
    summarized: List[Dict] = []
    for a in articles:
        summarized.append(summarize_article(a, model=model, temperature=temperature, max_tokens=max_tokens))
    return summarized
