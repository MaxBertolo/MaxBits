from typing import List, Dict
import os
import re
import textwrap
import html

import google.generativeai as genai

from .models import RawArticle


# ================= CONFIG GLOBALE =================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Max articoli per cui usare il modello al giorno (gli altri vanno in fallback locale)
MAX_LLM_CALLS = 3

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[LLM] Warning: GEMINI_API_KEY non impostata – verrà usato SOLO il fallback locale.")


# ================= HELPERS =================

def strip_html_title(raw_title: str) -> str:
    """Rimuove eventuali tag HTML dal titolo RSS (es. <a href=...>Title</a>)."""
    if not raw_title:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_title)
    text = html.unescape(text)
    return text.strip()


def build_prompt(article: RawArticle, language: str = "en") -> str:
    """
    Prompt per Gemini: chiediamo ESATTAMENTE 5 righe etichettate,
    così il parsing è robusto e i campi combaciano con il report.
    """
    content = (article.content or "").replace("\n", " ")
    if len(content) > 4000:
        content = content[:4000] + " [...]"

    title_clean = strip_html_title(article.title)

    instructions = """
You are a senior technology analyst writing for a C-level manager in Telco / Media / Tech.
Read the following news (title, source, content) and produce EXACTLY 5 lines in English.

Each line MUST start with the exact label, followed by a colon and a short sentence (max ~35 words).

1) WHAT IT IS: type of news (product, partnership, acquisition, trend, regulation, etc.).
2) WHO: main companies / actors involved.
3) WHAT IT DOES: what is introduced or enabled.
4) IMPACT: why this matters for Telco / Media / Tech.
5) FUTURE OUTLOOK: key points on how this might evolve in the next 6–24 months.

Output format (exactly 5 lines, no bullets, no extra text):

WHAT IT IS: ...
WHO: ...
WHAT IT DOES: ...
IMPACT: ...
FUTURE OUTLOOK: ...
"""

    prompt = f"""{instructions}

Title: {title_clean}
Source: {article.source}
URL: {article.url}

Content:
{content}
"""
    return textwrap.dedent(prompt).strip()


def _simple_local_summary(article: RawArticle) -> Dict[str, str]:
    """
    Fallback completamente locale: frasi standard ma leggibili.
    """
    title_clean = strip_html_title(article.title)
    source = article.source or "the company"

    return {
        "what_it_is": f"This news is about: {title_clean}.",
        "who": f"The main actor is {source} and its partners.",
        "what_it_does": (
            f"It describes a new development, product or initiative related to "
            f"{title_clean.lower() if title_clean else 'the tech ecosystem'}."
        ),
        "impact": (
            "It may affect Telco / Media / Tech in terms of infrastructure, services, "
            "innovation speed or competitive positioning."
        ),
        "future_outlook": (
            "Worth monitoring during the next 6–24 months for ecosystem effects, "
            "customer adoption and possible regulatory or market reactions."
        ),
    }


def _to_final_dict(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    """Costruisce il dizionario finale consumato dal report builder."""
    return {
        "title": article.title,
        "title_clean": strip_html_title(article.title),
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "what_it_is": fields.get("what_it_is", ""),
        "who": fields.get("who", ""),
        "what_it_does": fields.get("what_it_does", ""),
        "impact": fields.get("impact", ""),
        "future_outlook": fields.get("future_outlook", ""),
    }


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

    Accetta righe extra (le ignora) e varianti di maiuscole/spazi.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = {
        "what_it_is": "",
        "who": "",
        "what_it_does": "",
        "impact": "",
        "future_outlook": "",
    }

    for line in lines:
        upper = line.upper()
        if upper.startswith("WHAT IT IS:"):
            out["what_it_is"] = line.split(":", 1)[1].strip()
        elif upper.startswith("WHO:"):
            out["who"] = line.split(":", 1)[1].strip()
        elif upper.startswith("WHAT IT DOES:"):
            out["what_it_does"] = line.split(":", 1)[1].strip()
        elif upper.startswith("IMPACT:"):
            out["impact"] = line.split(":", 1)[1].strip()
        elif upper.startswith("FUTURE OUTLOOK:"):
            out["future_outlook"] = line.split(":", 1)[1].strip()

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
    - Gemini (se configurato)
    - fallback locale in caso di errore o risposta vuota.
    """
    if not GEMINI_API_KEY:
        fields = _simple_local_summary(article)
        return _to_final_dict(article, fields)

    prompt = build_prompt(article, language=language)

    try:
        model_name = model or GEMINI_MODEL_DEFAULT
        print(f"[LLM] Using Gemini model: {model_name}")
        raw_text = _call_gemini(prompt, model_name=model_name)
        fields = _parse_labeled_text(raw_text)

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
    - usa Gemini per i primi MAX_LLM_CALLS articoli (deep-dives)
    - per gli altri usa solo il fallback locale
    """
    results: List[Dict] = []

    llm_budget = min(MAX_LLM_CALLS, len(articles))
    print(f"[LLM] Will use Gemini for {llm_budget} article(s), then local fallback if needed.")

    for idx, article in enumerate(articles):
        use_llm = idx < llm_budget and GEMINI_API_KEY

        if use_llm:
            print(f"[LLM] Using Gemini for article {idx + 1}: {strip_html_title(article.title)}")
            res = summarize_article(article, model=model, temperature=temperature, max_tokens=max_tokens)
        else:
            print(f"[LLM] Skipping Gemini for article {idx + 1}, using local fallback.")
            fields = _simple_local_summary(article)
            res = _to_final_dict(article, fields)

        results.append(res)

    return results
