# src/summarizer.py

from typing import List, Dict
import os
import re
import textwrap
import html
from datetime import datetime

import google.generativeai as genai

from .models import RawArticle


# ================= CONFIG GLOBALE =================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Max articoli per cui usare il modello al giorno (deep-dives)
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
    Prompt per Gemini: chiediamo ESATTAMENTE 5 blocchi etichettati.

    Anche se il modello non va a capo fra le righe, il parser userà
    i label 'WHAT IT IS:', 'WHO:' ecc. per separarli.
    """
    content = (article.content or "").replace("\n", " ")
    if len(content) > 6000:
        content = content[:6000] + " [...]"

    title_clean = strip_html_title(article.title)

    instructions = """
You are a senior technology analyst writing for a C-level manager in Telco / Media / Tech.

Read the following news (title, source, content) and produce EXACTLY 5 labeled sections in English.

Each section MUST start with the label in ALL CAPS, followed by a colon and a short explanation
(max 2 sentences, around 20–35 words total per section).

Required labels (exact spelling):

1) WHAT IT IS:
2) WHO:
3) WHAT IT DOES:
4) WHY IT MATTERS:
5) STRATEGIC VIEW:

Output format (exactly these 5 labels, in this order, no bullets):

WHAT IT IS: ...
WHO: ...
WHAT IT DOES: ...
WHY IT MATTERS: ...
STRATEGIC VIEW: ...
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
    Fallback locale: frasi standard ma leggibili.
    """
    title_clean = strip_html_title(article.title)
    source = article.source or ""

    what_it_is = f"This news is about: {title_clean or 'a recent technology development'}."
    who = f"The main actor is {source or 'the company or organization mentioned in the article'}."
    what_it_does = (
        "It describes a new product, initiative or market move that affects infrastructure, "
        "services or business models in Telco / Media / Tech."
    )
    why_it_matters = (
        "It could change competitive dynamics, customer experience or investment priorities, "
        "impacting how networks, platforms or services are deployed and monetised."
    )
    strategic_view = (
        "It is worth monitoring over the next 6–24 months for ecosystem effects, partnerships, "
        "adoption curves and regulatory or financial signals."
    )

    return {
        "what_it_is": what_it_is,
        "who": who,
        "what_it_does": what_it_does,
        "why_it_matters": why_it_matters,
        "strategic_view": strategic_view,
    }


def _to_final_dict(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    """Costruisce il dizionario finale consumato dal report builder."""
    return {
        "title": article.title,
        "title_clean": strip_html_title(article.title),
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "what_it_is": (fields.get("what_it_is") or "").strip(),
        "who": (fields.get("who") or "").strip(),
        "what_it_does": (fields.get("what_it_does") or "").strip(),
        "why_it_matters": (fields.get("why_it_matters") or "").strip(),
        "strategic_view": (fields.get("strategic_view") or "").strip(),
    }


def _call_gemini(prompt: str, model_name: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    model = genai.GenerativeModel(model_name=model_name)
    resp = model.generate_content(prompt)
    text = (getattr(resp, "text", "") or "").strip()
    if not text:
        raise RuntimeError("Empty response from Gemini")
    return text


# ========= PARSER ROBUSTO PER I 5 LABEL =========

_LABELS = [
    "WHAT IT IS",
    "WHO",
    "WHAT IT DOES",
    "WHY IT MATTERS",
    "STRATEGIC VIEW",
]

_LABEL_MAP = {
    "WHAT IT IS": "what_it_is",
    "WHO": "who",
    "WHAT IT DOES": "what_it_does",
    "WHY IT MATTERS": "why_it_matters",
    "STRATEGIC VIEW": "strategic_view",
}


def _parse_labeled_text(text: str) -> Dict[str, str]:
    """
    Parsing robusto basato su regex.

    Funziona sia se Gemini mette ogni label su una riga separata,
    sia se scrive tutto su UNA riga tipo:
      WHAT IT IS: ... WHO: ... WHAT IT DOES: ...

    Regex: cattura "LABEL: contenuto ... (fino al label successivo o fine testo)".
    """
    out = {v: "" for v in _LABEL_MAP.values()}
    if not text:
        return out

    pattern = (
        r"(WHAT IT IS|WHO|WHAT IT DOES|WHY IT MATTERS|STRATEGIC VIEW)\s*:"
        r"\s*(.*?)\s*(?=(WHAT IT IS|WHO|WHAT IT DOES|WHY IT MATTERS|STRATEGIC VIEW)\s*:|$)"
    )

    for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
        label_raw = match.group(1)  # es. "WHAT IT IS"
        content = match.group(2) or ""
        label_norm = label_raw.upper().strip()

        key = _LABEL_MAP.get(label_norm)
        if not key:
            continue

        # Pulizia minima del contenuto
        content_clean = " ".join(content.split())
        out[key] = content_clean

    return out


def _is_summary_good(fields: Dict[str, str]) -> bool:
    """
    Controlla se il riassunto LLM è 'accettabile':
      - almeno 3 campi non vuoti
      - why_it_matters e strategic_view non troppo corti
    """
    non_empty = sum(1 for v in fields.values() if v and v.strip())
    if non_empty < 3:
        return False
    if len(fields.get("why_it_matters", "").strip()) < 30:
        return False
    if len(fields.get("strategic_view", "").strip()) < 30:
        return False
    return True


# ========= API PRINCIPALI =========

def summarize_article(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
    language: str = "en",
) -> Dict[str, str]:
    """
    Riassume un singolo articolo usando:
      - Gemini (se configurato, con parser robusto)
      - fallback locale in caso di errore o risposta poco utile.
    """
    if not GEMINI_API_KEY:
        fields = _simple_local_summary(article)
        return _to_final_dict(article, fields)

    prompt = build_prompt(article, language=language)
    model_name = model or GEMINI_MODEL_DEFAULT

    fields: Dict[str, str] = {}
    try:
        # Primo tentativo
        print(f"[LLM] Using Gemini model: {model_name}")
        raw_text = _call_gemini(prompt, model_name=model_name)
        fields = _parse_labeled_text(raw_text)

        if not _is_summary_good(fields):
            print("[LLM] First parse not good enough, retrying once with slightly different temperature...")
            # Secondo tentativo leggermente diverso
            alt_model = genai.GenerativeModel(model_name=model_name)
            alt_resp = alt_model.generate_content(
                prompt,
                generation_config={
                    "temperature": min(max(temperature, 0.1), 0.5),
                    "max_output_tokens": max_tokens,
                },
            )
            alt_text = (getattr(alt_resp, "text", "") or "").strip()
            if alt_text:
                fields2 = _parse_labeled_text(alt_text)
                if _is_summary_good(fields2):
                    fields = fields2

        if not _is_summary_good(fields):
            print("[LLM] Parsed too few / weak fields, using local fallback.")
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
    - usa Gemini per i primi MAX_LLM_CALLS articoli
    - per gli altri usa solo il fallback locale
      (nel tuo flusso attuale: 3 deep-dives → tutti serviti da Gemini).
    """
    results: List[Dict] = []

    llm_budget = min(MAX_LLM_CALLS, len(articles))
    print(f"[LLM] Will use Gemini for {llm_budget} article(s), then local fallback if needed.")

    for idx, article in enumerate(articles):
        use_llm = idx < llm_budget and GEMINI_API_KEY

        if use_llm:
            print(f"[LLM] Using Gemini for article {idx + 1}: {strip_html_title(article.title)}")
            res = summarize_article(
                article,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                language="en",
            )
        else:
            print(f"[LLM] Skipping Gemini for article {idx + 1}, using local fallback.")
            fields = _simple_local_summary(article)
            res = _to_final_dict(article, fields)

        results.append(res)

    return results
