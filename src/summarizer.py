# src/summarizer.py
from __future__ import annotations

import os
import re
import json
import html
import textwrap
from typing import List, Dict, Any

import google.generativeai as genai

from .models import RawArticle


# ==============================
#  CONFIG LLM (GEMINI)
# ==============================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_LLM_CALLS = 3  # nel tuo flusso: 3 deep-dive al giorno

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[LLM] WARNING: GEMINI_API_KEY not set – using ONLY local fallback.")


# ==============================
#  HELPERS DI BASE
# ==============================

FIELDS = [
    "what_it_is",
    "who",
    "what_it_does",
    "why_it_matters",
    "strategic_view",
]


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _clean_sentence(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip(" -–—\n\t")
    if s and s[-1] not in ".!?":
        s += "."
    return s


def _basic_fallback(article: RawArticle) -> Dict[str, str]:
    title = _strip_html(article.title)
    source = article.source or "the company"

    return {
        "what_it_is": f"This news concerns an update related to {title}.",
        "who": f"The main actors involved include {source}.",
        "what_it_does": (
            "It introduces or describes a concrete development, product, service or initiative "
            "that affects how technology and services are delivered."
        ),
        "why_it_matters": (
            "It may change strategy, infrastructure, partnerships or customer experience for "
            "Telco, Media and Tech players."
        ),
        "strategic_view": (
            "Over the next 6–24 months, it could open new opportunities or risks in competition, "
            "ecosystem positioning and innovation speed."
        ),
    }


# ==============================
#  PROMPT BUILDER (JSON ONLY)
# ==============================

def _build_json_prompt(article: RawArticle) -> str:
    content = (article.content or "").replace("\n", " ")
    if len(content) > 8000:
        content = content[:8000] + " [...]"

    title = _strip_html(article.title)

    instructions = """
You are a senior technology analyst writing for C-level executives in Telco, Media and Tech.

Your task:
- Read the news (title, source, content).
- Think deeply about the strategic meaning.
- Then produce a CLEAN JSON object with exactly 5 string fields.

The JSON MUST have exactly these keys:
- "what_it_is": one clear sentence (max 35 words) describing the type of news
  (product, partnership, acquisition, regulation, funding, trend, etc.).
- "who": one clear sentence naming the main companies / organizations / actors involved.
- "what_it_does": one clear sentence describing concretely what is introduced or enabled
  (features, capabilities, architecture, use cases).
- "why_it_matters": one clear sentence explaining the impact for Telco / Media / Tech
  (in terms of business, technology, customers, regulation or competition).
- "strategic_view": one clear sentence giving a strategic view over the next 6–24 months,
  including potential opportunities, risks and ecosystem implications.

STRICT RULES:
- Output MUST be VALID JSON, no surrounding text, no markdown.
- Do NOT include line breaks inside values.
- Do NOT include the labels ("WHAT IT IS", etc.) inside the strings.
- Do NOT add keys other than the 5 required keys.
"""

    prompt = f"""{textwrap.dedent(instructions).strip()}

Title: {title}
Source: {article.source}
URL: {article.url}

Content:
{content}
"""
    return prompt.strip()


def _build_repair_prompt(article: RawArticle, draft_fields: Dict[str, str]) -> str:
    """
    Seconda passata: prendo il draft (anche se sporco) e chiedo al modello
    di ripulirlo completamente e riscriverlo in JSON perfetto.
    """
    title = _strip_html(article.title)
    content = (article.content or "")[:2000]

    instructions = """
You previously tried to summarize this news into structured fields for a C-level audience.
The draft you produced was noisy or incomplete.

Now you must FIX and REWRITE the summary into a PERFECT JSON object.

The JSON MUST have EXACTLY these 5 keys, all non-empty strings:
- "what_it_is"
- "who"
- "what_it_does"
- "why_it_matters"
- "strategic_view"

Constraints:
- One sentence per field, max ~35 words, in clear English.
- Do NOT include any label words like "WHAT IT IS" inside the values.
- Do NOT add extra keys.
- Output MUST be valid JSON, no extra text before or after.
"""

    prompt = f"""{textwrap.dedent(instructions).strip()}

Title: {title}
Source: {article.source}

Original draft fields (may be noisy or wrong):
{json.dumps(draft_fields, ensure_ascii=False, indent=2)}

Article excerpt:
{content}
"""
    return prompt.strip()


# ==============================
#  LLM CALL + JSON PARSING
# ==============================

def _call_gemini(prompt: str, model_name: str | None = None) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    model = genai.GenerativeModel(model_name or GEMINI_MODEL_DEFAULT)
    resp = model.generate_content(prompt)
    txt = getattr(resp, "text", "") or ""
    txt = txt.strip()
    if not txt:
        raise RuntimeError("Empty response from Gemini")
    return txt


def _extract_json_block(text: str) -> str:
    """
    Se il modello, nonostante tutto, aggiunge testo prima/dopo il JSON,
    troviamo il blocco compreso fra la prima '{' e l'ultima '}'.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in text")
    return text[start : end + 1]


def _parse_json_summary(text: str) -> Dict[str, Any]:
    """
    Prova a parsare il JSON in modo robusto.
    """
    raw = _extract_json_block(text)
    data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError("JSON summary is not an object")

    return data


# ==============================
#  VALIDAZIONE + NORMALIZZAZIONE
# ==============================

def _validate_and_normalise_fields(data: Dict[str, Any]) -> Dict[str, str]:
    """
    - Tiene solo le 5 chiavi note
    - Pulisce le stringhe
    - Scarta roba assurda
    - Valuta qualità minima
    """
    cleaned: Dict[str, str] = {}
    for key in FIELDS:
        val = data.get(key, "")
        if not isinstance(val, str):
            val = str(val)
        val = val.strip()

        # niente label ripetute dentro
        if re.search(r"WHAT IT|WHY IT MATTERS|STRATEGIC VIEW|WHO:", val.upper()):
            val = ""

        # niente stringhe lunghissime
        if len(val) > 350:
            val = val[:350]

        val = _clean_sentence(val)
        cleaned[key] = val

    # scoring qualità
    score = 0
    for key in FIELDS:
        v = cleaned[key]
        if 15 <= len(v) <= 350:
            score += 1

    # se meno di 3 campi ok → consideriamo l'output scarso
    if score < 3:
        raise ValueError(f"Summary too weak (score={score})")

    return cleaned


def _reconstruct_if_missing(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    """
    Se qualche campo è vuoto dopo la validazione,
    lo ricostruiamo via regole.
    """
    title = _strip_html(article.title)
    source = article.source or "the company"

    if not fields["what_it_is"]:
        fields["what_it_is"] = f"This news concerns an update related to {title}."
    if not fields["who"]:
        fields["who"] = f"The main actors involved include {source}."
    if not fields["what_it_does"]:
        fields["what_it_does"] = (
            "It introduces new or enhanced capabilities, services or initiatives that may affect technology or customer propositions."
        )
    if not fields["why_it_matters"]:
        fields["why_it_matters"] = (
            "It can impact Telco, Media or Tech players in terms of strategy, infrastructure, competition or regulation."
        )
    if not fields["strategic_view"]:
        fields["strategic_view"] = (
            "Over the next 6–24 months, this move may reshape the ecosystem, partnerships and competitive positioning."
        )

    # pulizia finale
    for k in FIELDS:
        fields[k] = _clean_sentence(fields[k])

    return fields


# ==============================
#  API PUBBLICHE
# ==============================

def summarize_article(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Dict[str, str]:
    """
    Pipelines:
      1) Primo tentativo Gemini → JSON
      2) Validazione
      3) Se fail → prompt di repair + nuova chiamata
      4) Se ancora fail → fallback locale
    """
    if not GEMINI_API_KEY:
        print("[LLM] No GEMINI_API_KEY → using basic fallback.")
        fields = _basic_fallback(article)
        return {
            "title": _strip_html(article.title),
            "url": article.url,
            "source": article.source,
            "published_at": article.published_at.isoformat(),
            **fields,
        }

    # -------- PRIMO TENTATIVO --------
    try:
        prompt = _build_json_prompt(article)
        raw_text = _call_gemini(prompt, model or GEMINI_MODEL_DEFAULT)
        data = _parse_json_summary(raw_text)
        fields = _validate_and_normalise_fields(data)
        fields = _reconstruct_if_missing(article, fields)
        print("[LLM] First-pass summary OK.")
    except Exception as e1:
        print("[LLM] First-pass failed:", repr(e1))

        # -------- SECONDO TENTATIVO (REPAIR) --------
        try:
            # se abbiamo qualche data parziale la passiamo,
            # altrimenti passiamo dict vuoto
            try:
                partial = data  # type: ignore[name-defined]
            except Exception:
                partial = {}

            repair_prompt = _build_repair_prompt(article, partial)
            raw_text2 = _call_gemini(repair_prompt, model or GEMINI_MODEL_DEFAULT)
            data2 = _parse_json_summary(raw_text2)
            fields = _validate_and_normalise_fields(data2)
            fields = _reconstruct_if_missing(article, fields)
            print("[LLM] Repair-pass summary OK.")
        except Exception as e2:
            print("[LLM] Repair-pass failed:", repr(e2))
            fields = _basic_fallback(article)

    return {
        "title": _strip_html(article.title),
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        **fields,
    }


def summarize_articles(
    articles: List[RawArticle],
    model: str,
    temperature: float,
    max_tokens: int,
) -> List[Dict]:
    """
    Nel tuo flusso deep-dive: in pratica 3 articoli.
    Facciamo comunque un limite di sicurezza (MAX_LLM_CALLS).
    """
    results: List[Dict] = []

    for idx, article in enumerate(articles):
        use_llm = GEMINI_API_KEY and idx < MAX_LLM_CALLS

        print(f"[LLM] Article {idx + 1}/{len(articles)} – use_llm={bool(use_llm)}")

        if use_llm:
            res = summarize_article(article, model=model, temperature=temperature, max_tokens=max_tokens)
        else:
            fields = _basic_fallback(article)
            res = {
                "title": _strip_html(article.title),
                "url": article.url,
                "source": article.source,
                "published_at": article.published_at.isoformat(),
                **fields,
            }
        results.append(res)

    return results
