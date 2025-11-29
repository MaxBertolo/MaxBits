from typing import List, Dict
import os
import json

from datetime import datetime
import google.generativeai as genai

from .models import RawArticle


# ===============================
# Gemini configuration
# ===============================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Nome modello corretto per la nuova API
GEMINI_MODEL = "gemini-1.5-flash-latest"


def _configure_gemini():
    """
    Inizializza la libreria Gemini con la API key.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY non impostata. "
            "Imposta il secret GEMINI_API_KEY in GitHub Actions."
        )
    genai.configure(api_key=GEMINI_API_KEY)


# ===============================
# Prompt builder
# ===============================

def build_prompt(article: RawArticle) -> str:
    """
    Prompt in inglese, stile approfondito per manager Telco/Media.
    """
    return f"""
You are a senior technology & strategy analyst writing for a C-level executive
in a Telco/Media/Tech company.

Read the NEWS (title + content) and produce a DEEP, STRUCTURED analysis.

### GOAL

Return a JSON object with EXACTLY this schema (no extra fields):

{{
  "what_it_is": "...",
  "who": "...",
  "what_it_does": "...",
  "why_it_matters": "...",
  "strategic_view": "..."
}}

### STYLE & GUIDELINES

- Language: **English**.
- Tone: professional, clear, business-oriented (no marketing fluff).
- Each field should be a short paragraph (2–3 sentences), not bullet points.
- Avoid generic statements like "this is important" without explaining why.
- Do NOT invent companies or facts that are not supported by the text.

FIELD DETAILS:

- "what_it_is":
    2–3 sentences explaining what the news is about:
    e.g. product launch, partnership, acquisition, regulation, standard,
    funding round, infrastructure build-out, technology milestone, etc.

- "who":
    2 sentences describing the main actors (companies, institutions, key roles)
    and their roles in the news.

- "what_it_does":
    2–3 sentences explaining concretely what this initiative/technology enables
    or changes (capabilities, use cases, segments impacted).

- "why_it_matters":
    2–3 sentences about why this matters for Telco/Media/Tech/AI:
    relate, where possible, to networks, cloud, AI, advertising, streaming,
    robotics, data centers, satellite, infrastructure.

- "strategic_view":
    2–3 sentences with a forward-looking point of view (6–24 months):
    risks & opportunities, likely impact on operators, broadcasters,
    OTTs, hyperscalers, or players like Sky.

### OUTPUT FORMAT (VERY IMPORTANT)

- Answer **ONLY** with a valid JSON object.
- No comments, no markdown, no explanations.
- Do NOT wrap it in ```json or any code fences.

### NEWS DATA

Title: {article.title}
Source: {article.source}
URL: {article.url}

Content:
{article.content}
"""


# ===============================
# Fallback handler
# ===============================

def _fallback_summary(article: RawArticle, reason: str) -> Dict[str, str]:
    """
    Fallback se la chiamata a Gemini fallisce o l'output non è parsabile.
    """
    msg = f"Summary not available ({reason}). Please read the full article from the link."
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


# ===============================
# Gemini summarization
# ===============================

def summarize_with_gemini(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Dict[str, str]:
    """
    Chiama Gemini e restituisce un dict con i 5 campi logici.
    """
    try:
        _configure_gemini()
    except Exception as e:
        print("[LLM] Gemini not configured:", repr(e))
        return _fallback_summary(article, "Gemini not configured")

    mdl_name = model or GEMINI_MODEL
    print("[LLM] Using Gemini model:", mdl_name)

    prompt = build_prompt(article)

    try:
        gemini_model = genai.GenerativeModel(mdl_name)
        response = gemini_model.generate_content(
            prompt,
            generation_config={
                "temperature": float(temperature),
                "max_output_tokens": int(max_tokens),
            },
        )
        text = (response.text or "").strip()
    except Exception as e:
        print("[LLM] Error calling Gemini:", repr(e))
        return _fallback_summary(article, "Gemini call error")

    if not text:
        return _fallback_summary(article, "empty response")

    # A volte il modello aggiunge ```json ... ``` → ripuliamo
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
    except Exception as e:
        print("[LLM] JSON parse error:", repr(e))
        print("[LLM] Raw output (first 500 chars):", text[:500])
        return _fallback_summary(article, "unparsable JSON")

    # Normalizziamo i campi (in inglese ma mappati sui campi italiani del report)
    what_it_is = data.get("what_it_is", "").strip()
    who = data.get("who", "").strip()
    what_it_does = data.get("what_it_does", "").strip()
    why_it_matters = data.get("why_it_matters", "").strip()
    strategic_view = data.get("strategic_view", "").strip()

    if not any([what_it_is, who, what_it_does, why_it_matters, strategic_view]):
        return _fallback_summary(article, "all fields empty")

    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "cos_e": what_it_is,
        "chi": who,
        "cosa_fa": what_it_does,
        "perche_interessante": why_it_matters,
        "pov": strategic_view,
    }


# ===============================
# Public API used by main.py
# ===============================

def summarize_article(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Dict[str, str]:
    """
    Entry point usato da main.py per un singolo articolo.
    """
    return summarize_with_gemini(
        article,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def summarize_articles(
    articles: List[RawArticle],
    model: str,
    temperature: float,
    max_tokens: int,
) -> List[Dict]:
    """
    Entry point usato da main.py per una lista di articoli.
    """
    summarized: List[Dict] = []
    for a in articles:
        summarized.append(
            summarize_article(
                a,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
    return summarized
