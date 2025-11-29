from typing import List, Dict
import os
import textwrap

import google.generativeai as genai

from .models import RawArticle


# ============= CONFIG GLOBALE =============

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # può essere sovrascritto da config.yaml

# massimo numero di articoli per cui chiamare il modello al giorno
MAX_LLM_CALLS = 3

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[LLM] Warning: GEMINI_API_KEY non impostata, userò SOLO il fallback locale.")


# ============= PROMPT =============

def build_prompt(article: RawArticle, language: str = "en") -> str:
    """
    Prompt testuale: chiediamo esattamente 5 righe con etichette fisse.
    Così possiamo fare un parsing semplice e robusto.
    """

    # limitiamo il contenuto per non superare i token gratuiti
    content = article.content or ""
    content = content.replace("\n", " ")
    if len(content) > 4000:
        content = content[:4000] + " [...]"

    if language.lower().startswith("it"):
        # versione italiana (se un domani vuoi tornare a IT)
        instructions = """
You are a senior technology analyst writing for a C-level manager in Telco / Media / Tech.
Read the following news (title, source, content) and produce EXACTLY 5 lines in Italian.

Each line MUST start with the exact label, followed by a colon and a short sentence (max 35 words).

1) WHAT IT IS: type of news (product, partnership, acquisition, trend, regulation, etc.).
2) WHO: main companies / actors involved.
3) WHAT IT DOES: what is introduced or enabled.
4) WHY IT MATTERS: short impact for Telco / Media / Tech.
5) STRATEGIC VIEW: mini strategic comment with 6–24 months perspective.

Output format (exactly 5 lines, no bullets, no extra text):

WHAT IT IS: ...
WHO: ...
WHAT IT DOES: ...
WHY IT MATTERS: ...
STRATEGIC VIEW: ...
"""
    else:
        # versione inglese
        instructions = """
You are a senior technology analyst writing for a C-level manager in Telco / Media / Tech.
Read the following news (title, source, content) and produce EXACTLY 5 lines in English.

Each line MUST start with the exact label, followed by a colon and a short sentence (max 35 words).

1) WHAT IT IS: type of news (product, partnership, acquisition, trend, regulation, etc.).
2) WHO: main companies / actors involved.
3) WHAT IT DOES: what is introduced or enabled.
4) WHY IT MATTERS: short impact for Telco / Media / Tech.
5) STRATEGIC VIEW: mini strategic comment with 6–24 months perspective.

Output format (exactly 5 lines, no bullets, no extra text):

WHAT IT IS: ...
WHO: ...
WHAT IT DOES: ...
WHY IT MATTERS: ...
STRATEGIC VIEW: ...
"""

    prompt = f"""{instructions}

Title: {article.title}
Source: {article.source}
URL: {article.url}

Content:
{content}
"""
    return textwrap.dedent(prompt).strip()


# ============= FALLBACK LOCALE =============

def _simple_local_summary(article: RawArticle) -> Dict[str, str]:
    """
    Fallback completamente locale: usa solo title + content
    per costruire frasi brevi e comunque leggibili.
    """

    title = article.title or ""
    source = article.source or ""
    text = (article.content or "").replace("\n", " ")

    # prendiamo le prime frasi o tronchiamo
    short = text[:400].strip()
    if not short:
        short = title

    cos_e = f"This news is about: {title}."
    chi = f"The main actor is {source} or partners mentioned in the article."
    cosa_fa = f"It describes a new development or initiative related to {title.lower()}."
    perche = "It may affect Telco / Media / Tech in terms of infrastructure, services or competitive positioning."
    pov = "Worth monitoring: potential impact depends on execution, ecosystem adoption and regulatory or market reactions."

    return {
        "cos_e": cos_e,
        "chi": chi,
        "cosa_fa": cosa_fa,
        "perche_interessante": perche,
        "pov": pov,
    }


def _to_final_dict(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    """Costruisce il dizionario finale per il report."""
    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "cos_e": fields.get("cos_e", ""),
        "chi": fields.get("chi", ""),
        "cosa_fa": fields.get("cosa_fa", ""),
        "perche_interessante": fields.get("perche_interessante", ""),
        "pov": fields.get("pov", ""),
    }


# ============= CHIAMATA A GEMINI =============

def _call_gemini(prompt: str, model_name: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    model = genai.GenerativeModel(model_name=model_name)
    resp = model.generate_content(prompt)
    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("Empty response from Gemini")
    return text


def _parse_labeled_text(text: str) -> Dict[str, str]:
    """
    Parsing delle 5 righe etichettate.
    Accetta anche eventuali righe extra (le ignora).
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = {
        "cos_e": "",
        "chi": "",
        "cosa_fa": "",
        "perche_interessante": "",
        "pov": "",
    }

    for line in lines:
        upper = line.upper()
        if upper.startswith("WHAT IT IS:"):
            out["cos_e"] = line.split(":", 1)[1].strip()
        elif upper.startswith("WHO:"):
            out["chi"] = line.split(":", 1)[1].strip()
        elif upper.startswith("WHAT IT DOES:"):
            out["cosa_fa"] = line.split(":", 1)[1].strip()
        elif upper.startswith("WHY IT MATTERS:"):
            out["perche_interessante"] = line.split(":", 1)[1].strip()
        elif upper.startswith("STRATEGIC VIEW:"):
            out["pov"] = line.split(":", 1)[1].strip()

    return out


def summarize_article(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
    language: str = "en",
) -> Dict[str, str]:
    """
    Riassume un singolo articolo usando:
    - Gemini (se configurato e finché non superiamo MAX_LLM_CALLS)
    - fallback locale in caso di errore o risposta vuota.
    """

    # se non c'è chiave → direttamente fallback
    if not GEMINI_API_KEY:
        fields = _simple_local_summary(article)
        return _to_final_dict(article, fields)

    prompt = build_prompt(article, language=language)

    try:
        raw_text = _call_gemini(prompt, model_name=model or GEMINI_MODEL)
        fields = _parse_labeled_text(raw_text)

        # se per qualche motivo mancano quasi tutti i campi → fallback
        non_empty = sum(1 for v in fields.values() if v)
        if non_empty < 3:
            print("[LLM] Parsed too few fields, using local fallback.")
            fields = _simple_local_summary(article)

    except Exception as e:
        print("[LLM] Error calling Gemini, using local fallback:", repr(e))
        fields = _simple_local_summary(article)

    return _to_final_dict(article, fields)


def summarize_articles(
    articles: List[RawArticle],
    model: str,
    temperature: float,
    max_tokens: int,
) -> List[Dict]:
    """
    Riassume una lista di articoli.
    - Usa Gemini solo per i primi MAX_LLM_CALLS articoli.
    - Per gli altri usa il fallback locale (così non consumi quota).
    """
    results: List[Dict] = []

    # usiamo al massimo 3 chiamate al giorno a Gemini
    llm_budget = min(MAX_LLM_CALLS, len(articles))
    print(f"[LLM] Will use Gemini for {llm_budget} article(s), then local fallback.")

    for idx, article in enumerate(articles):
        use_llm = idx < llm_budget and GEMINI_API_KEY

        if use_llm:
            print(f"[LLM] Using Gemini for article {idx + 1}: {article.title}")
            res = summarize_article(article, model=model, temperature=temperature, max_tokens=max_tokens)
        else:
            print(f"[LLM] Skipping Gemini for article {idx + 1}, using local fallback.")
            fields = _simple_local_summary(article)
            res = _to_final_dict(article, fields)

        results.append(res)

    return results
