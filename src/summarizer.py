# src/summarizer.py

from typing import List, Dict
import os
import re
import textwrap
import html
import json

import google.generativeai as genai

from .models import RawArticle


# ================= CONFIG GLOBALE =================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[LLM] Warning: GEMINI_API_KEY not set – ONLY local fallback will be used.")


# ================= HELPERS DI BASE =================

def strip_html_title(raw_title: str) -> str:
    """Rimuove eventuali tag HTML dal titolo RSS."""
    if not raw_title:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_title)
    text = html.unescape(text)
    return text.strip()


def _short_content_snippet(article: RawArticle, max_chars: int = 600) -> str:
    """Piccolo snippet di contenuto per arricchire i fallback strategici."""
    txt = (article.content or "").replace("\n", " ").strip()
    if len(txt) <= max_chars:
        return txt
    return txt[:max_chars].rsplit(" ", 1)[0] + " [...]"


# ================= PROMPT (JSON-ONLY) =================

def build_prompt_json(article: RawArticle, language: str = "en") -> str:
    """
    Prompt strutturato: chiediamo ESCLUSIVAMENTE JSON con 5 campi.
    Questo massimizza la robustezza nel parsing.
    """
    content = (article.content or "").replace("\n", " ")
    if len(content) > 10000:
        content = content[:10000] + " [...]"

    title_clean = strip_html_title(article.title)

    instructions = """
You are a senior technology strategist for Telco / Media / Tech.

Read the following news (title, source, content) and generate a deep, executive-level analysis.

You MUST return ONLY valid JSON (no markdown, no backticks, no comments), 
with EXACTLY these keys and values as single-line strings:

{
  "what_it_is": "...",
  "who": "...",
  "what_it_does": "...",
  "why_it_matters": "...",
  "strategic_view": "..."
}

Each field MUST be:
- in English
- one sentence (max ~40 words)
- non-empty and informative

Semantics:
- "what_it_is": short definition of the news: type (product, deal, regulation, trend, etc.) + domain (AI, cloud, 5G, media, satellite...).
- "who": main companies / actors / institutions involved.
- "what_it_does": what concretely changes: capabilities, architecture, business model, go-to-market, user experience, etc.
- "why_it_matters": business / strategic impact for Telco / Media / Tech (revenue, cost, time-to-market, risk, regulation, ecosystem).
- "strategic_view": your strategic POV: how this move fits broader trends, where it could go in 6–24 months, what opportunities or risks it opens.

Return ONLY the JSON object, with all 5 keys present.
"""

    prompt = f"""{instructions}

Title: {title_clean}
Source: {article.source}
URL: {article.url}

Content:
{content}
"""
    return textwrap.dedent(prompt).strip()


# ================= FALLBACK LOCALE "INTELLIGENTE" =================

def _simple_local_summary(article: RawArticle) -> Dict[str, str]:
    """
    Fallback completamente locale ma pensato per restare leggibile,
    con un minimo di "pensiero strategico" generico.
    """
    title_clean = strip_html_title(article.title)
    source = article.source or "the company"
    snippet = _short_content_snippet(article)

    what_it_is = (
        f"This news covers \"{title_clean}\" as a relevant development in connectivity, media "
        f"or data-driven services coming from {source}."
    )
    who = (
        f"The main actor is {source}, potentially together with ecosystem partners, "
        f"vendors and platform providers."
    )
    what_it_does = (
        "It introduces or describes a concrete initiative, product or deployment that changes how "
        "networks, platforms or services are designed, delivered or consumed."
    )
    why_it_matters = (
        "It may influence CAPEX priorities, service roadmap, competitive differentiation and how "
        "value is shared across operators, hyperscalers and content/tech players."
    )
    strategic_view = (
        "Strategically, it should be monitored over the next 6–24 months for real adoption, "
        "regulatory response and ecosystem reactions, as it might open new positioning and "
        "monetisation options or accelerate existing shifts."
    )

    # Piccola aggiunta con snippet se disponibile
    if snippet:
        strategic_view += f" The announcement is framed around themes such as: {snippet[:180]}"

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
        "what_it_is": fields.get("what_it_is", ""),
        "who": fields.get("who", ""),
        "what_it_does": fields.get("what_it_does", ""),
        "why_it_matters": fields.get("why_it_matters", ""),
        "strategic_view": fields.get("strategic_view", ""),
    }


# ================= CHIAMATA GEMINI (JSON) =================

def _call_gemini(prompt: str, model_name: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    model = genai.GenerativeModel(model_name=model_name)
    resp = model.generate_content(prompt)
    text = (getattr(resp, "text", "") or "").strip()
    if not text:
        raise RuntimeError("Empty response from Gemini")
    return text


def _parse_json_response(text: str) -> Dict[str, str]:
    """
    Prova a fare il parsing del JSON.
    Se ci sono caratteri extra prima/dopo, prova a ripulire in modo conservativo.
    """
    # Prova diretta
    try:
        data = json.loads(text)
    except Exception:
        # Prova a isolare la prima { ... } grossa
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise
        cleaned = m.group(0)
        data = json.loads(cleaned)

    if not isinstance(data, dict):
        raise ValueError("Gemini JSON is not an object")

    # Normalizza stringhe e chiavi attese
    out: Dict[str, str] = {}
    for key in ["what_it_is", "who", "what_it_does", "why_it_matters", "strategic_view"]:
        val = data.get(key, "")
        if not isinstance(val, str):
            val = str(val)
        out[key] = val.strip()

    return out


def _ensure_all_fields(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    """
    Se Gemini lascia stringhe vuote / troppo corte, le arricchiamo con un fallback locale
    che prova a “capire il contesto” a partire da titolo + snippet.
    """
    base_fallback = _simple_local_summary(article)

    def _fix(key: str, min_len: int = 20) -> None:
        val = fields.get(key, "") or ""
        if len(val.strip()) < min_len:
            fields[key] = base_fallback[key]

    _fix("what_it_is")
    _fix("who")
    _fix("what_it_does")
    _fix("why_it_matters", min_len=40)
    _fix("strategic_view", min_len=60)

    return fields


# ================= API PRINCIPALI =================

def summarize_article(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
    language: str = "en",
) -> Dict[str, str]:
    """
    Riassume un articolo con la massima robustezza possibile:
    - 1) tenta Gemini in JSON
    - 2) se fallisce parsing / risposta, usa fallback locale "intelligente"
    - 3) in ogni caso garantisce tutti i campi non vuoti.
    """
    if not GEMINI_API_KEY:
        print("[LLM] No GEMINI_API_KEY → using local fallback only.")
        fields = _simple_local_summary(article)
        return _to_final_dict(article, fields)

    prompt = build_prompt_json(article, language=language)

    try:
        model_name = model or GEMINI_MODEL_DEFAULT
        print(f"[LLM] Using Gemini model: {model_name}")
        raw_text = _call_gemini(prompt, model_name=model_name)
        fields = _parse_json_response(raw_text)
        fields = _ensure_all_fields(article, fields)

    except Exception as e:
        print("[LLM] Error or invalid JSON from Gemini, using local fallback:", repr(e))
        fields = _simple_local_summary(article)

    return _to_final_dict(article, fields)


def summarize_articles(
    articles: List[RawArticle],
    model: str,
    temperature: float,
    max_tokens: int,
) -> List[Dict]:
    """
    Riassume tutti gli articoli passati.
    Nel tuo flusso attuale: sono solo i 3 deep-dives → possiamo permetterci
    di usare SEMPRE il modello esterno per massima qualità.
    """
    results: List[Dict] = []

    for idx, article in enumerate(articles):
        print(f"[LLM] Summarizing article {idx + 1}/{len(articles)}: {strip_html_title(article.title)}")
        res = summarize_article(
            article,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        results.append(res)

    return results
