# src/summarizer.py
#
# Gemini summarizer con:
# - 3 tentativi max (1 base + 2 repair)
# - validazione forte dei 5 campi
# - fallback pulito se il modello sbaglia
# - TITOLO SEMPRE COPIATO dall'articolo di partenza

from __future__ import annotations

import os
import re
import json
import html
import textwrap
from typing import List, Dict, Any

import google.generativeai as genai

from .models import RawArticle

# ---------------------------------
# CONFIG
# ---------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_LLM_CALLS = 3  # nel tuo flusso: 3 deep-dives

FIELDS = ["what_it_is", "who", "what_it_does", "why_it_matters", "strategic_view"]

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[LLM] WARNING: GEMINI_API_KEY not set – using only fallback.")


# ---------------------------------
# HELPERS BASE
# ---------------------------------

def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _clean_sentence(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip(" \n\r\t-–—")
    if s and s[-1] not in ".!?":
        s += "."
    return s


def _safe_field(s: str) -> str:
    """Pulisce e butta via stringhe chiaramente sporche."""
    if not s:
        return ""
    s = s.strip()
    # rimuovi label interne nel testo
    if re.search(r"WHAT IT IS|WHAT IT DOES|WHY IT MATTERS|STRATEGIC VIEW|WHO:", s.upper()):
        return ""
    # limita lunghezza
    if len(s) > 350:
        s = s[:350]
    return _clean_sentence(s)


def _fallback_fields(article: RawArticle) -> Dict[str, str]:
    """Fallback deterministico ma leggibile."""
    title = _strip_html(article.title)
    source = article.source or "the company"

    return {
        "what_it_is": _clean_sentence(f"This news concerns a development related to {title}."),
        "who": _clean_sentence(f"The main actors involved include {source} and ecosystem partners."),
        "what_it_does": _clean_sentence(
            "It introduces or describes concrete changes in products, services or capabilities in the technology stack."
        ),
        "why_it_matters": _clean_sentence(
            "It may influence strategy, infrastructure, partnerships or competition for Telco, Media and Tech players."
        ),
        "strategic_view": _clean_sentence(
            "Over the next 6–24 months, this move could reshape positioning, ecosystem relationships and investment priorities."
        ),
    }


# ---------------------------------
# PROMPT PRINCIPALE (JSON)
# ---------------------------------

def _build_json_prompt(article: RawArticle) -> str:
    title = _strip_html(article.title)
    content = (article.content or "").replace("\n", " ")
    if len(content) > 8000:
        content = content[:8000] + " [...]"

    instructions = """
You are a senior technology analyst writing for C-level executives in Telco, Media and Tech.

TASK:
1. Understand the STRATEGIC meaning of this news.
2. Output a CLEAN JSON object with EXACTLY these 5 keys:
   - "what_it_is"
   - "who"
   - "what_it_does"
   - "why_it_matters"
   - "strategic_view"

Each field:
- MUST be ONE English sentence (~20–35 words).
- MUST NOT contain label words ("WHAT IT IS", "WHO", etc.).
- MUST NOT contain line breaks.
- MUST NOT be empty.

STRICT FORMAT:
- Output MUST be valid JSON only (no markdown, no commentary).
"""

    return f"""{textwrap.dedent(instructions).strip()}

Title: {title}
Source: {article.source}
URL: {article.url}

Content:
{content}
"""


# ---------------------------------
# PROMPT DI REPAIR
# ---------------------------------

def _build_repair_prompt(article: RawArticle, draft: Dict[str, Any]) -> str:
    title = _strip_html(article.title)
    draft_json = json.dumps(draft or {}, ensure_ascii=False, indent=2)

    instructions = """
You previously attempted to summarize this news but the result had errors.

Now FIX and REWRITE the summary as a PERFECT JSON object.

Required keys:
- "what_it_is"
- "who"
- "what_it_does"
- "why_it_matters"
- "strategic_view"

For each key:
- ONE clear English sentence (~20–35 words).
- NO labels inside values.
- NO line breaks.
- NO extra keys.
- NO empty strings.

Output MUST be valid JSON only, no extra text.
"""

    return f"""{textwrap.dedent(instructions).strip()}

Title: {title}

Previous draft (may be wrong or incomplete):
{draft_json}
"""


# ---------------------------------
# LLM CALL + JSON PARSING
# ---------------------------------

def _call_gemini(prompt: str, model_name: str | None = None) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    model = genai.GenerativeModel(model_name or GEMINI_MODEL)
    resp = model.generate_content(prompt)
    txt = (getattr(resp, "text", "") or "").strip()
    if not txt:
        raise RuntimeError("Empty response from Gemini")
    return txt


def _extract_json_block(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON block not found")
    return text[start : end + 1]


def _parse_json_summary(text: str) -> Dict[str, Any]:
    block = _extract_json_block(text)
    data = json.loads(block)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be object")
    return data


# ---------------------------------
# VALIDAZIONE + COMPLETAMENTO
# ---------------------------------

def _validate_fields(raw: Dict[str, Any]) -> Dict[str, str]:
    """
    - tiene solo i 5 campi noti
    - filtra spazzatura
    - richiede almeno 3 campi decenti
    """
    cleaned: Dict[str, str] = {}
    ok = 0

    for key in FIELDS:
        val = raw.get(key, "")
        if not isinstance(val, str):
            val = str(val)
        val = _safe_field(val)
        cleaned[key] = val
        if len(val) > 10:
            ok += 1

    if ok < 3:
        raise ValueError(f"Weak summary: only {ok}/5 fields valid")
    return cleaned


def _complete_missing(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    base = _fallback_fields(article)
    for k in FIELDS:
        if not fields.get(k):
            fields[k] = base[k]
        else:
            fields[k] = _clean_sentence(fields[k])
    return fields


# ---------------------------------
# SINGLE ARTICLE SUMMARY (MAX 3 TENTATIVI)
# ---------------------------------

def summarize_article(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Dict[str, str]:
    """
    Pipeline:
      - fino a 3 tentativi:
          1) prompt base (JSON)
          2-3) prompt di repair se serve
      - se tutti falliscono → fallback deterministico

    Il titolo è SEMPRE quello originale dell'articolo.
    """
    title = _strip_html(article.title)

    if not GEMINI_API_KEY:
        print("[LLM] No GEMINI_API_KEY → using fallback.")
        fields = _fallback_fields(article)
        return {
            "title": title,
            "url": article.url,
            "source": article.source,
            "published_at": article.published_at.isoformat(),
            **fields,
        }

    last_draft: Dict[str, Any] = {}
    last_error: Exception | None = None

    for attempt in range(3):
        mode = "base" if attempt == 0 else "repair"
        print(f"[LLM] Article '{title[:60]}' – attempt {attempt+1}/3 ({mode})")

        try:
            if mode == "base":
                prompt = _build_json_prompt(article)
            else:
                prompt = _build_repair_prompt(article, last_draft)

            raw_text = _call_gemini(prompt, model or GEMINI_MODEL)
            draft = _parse_json_summary(raw_text)
            last_draft = draft  # per eventuale tentativo successivo

            fields = _validate_fields(draft)
            fields = _complete_missing(article, fields)

            print("[LLM] Summary OK on attempt", attempt + 1)
            return {
                "title": title,  # COPIATO 1:1
                "url": article.url,
                "source": article.source,
                "published_at": article.published_at.isoformat(),
                **fields,
            }

        except Exception as e:
            last_error = e
            print(f"[LLM] Attempt {attempt+1} failed:", repr(e))
            continue

    # Se arriviamo qui, tutti i tentativi sono falliti
    print("[LLM] All attempts failed, using deterministic fallback.")
    fields = _fallback_fields(article)
    return {
        "title": title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        **fields,
    }


# ---------------------------------
# MULTI-ARTICLE
# ---------------------------------

def summarize_articles(
    articles: List[RawArticle],
    model: str,
    temperature: float,
    max_tokens: int,
) -> List[Dict]:
    results: List[Dict] = []

    for idx, art in enumerate(articles):
        use_llm = bool(GEMINI_API_KEY) and idx < MAX_LLM_CALLS
        print(f"[LLM] Summarizing article {idx+1}/{len(articles)} – use_llm={use_llm}")
        if use_llm:
            res = summarize_article(art, model=model, temperature=temperature, max_tokens=max_tokens)
        else:
            # fallback deterministic for extra articles, in caso di future estensioni
            fields = _fallback_fields(art)
            res = {
                "title": _strip_html(art.title),
                "url": art.url,
                "source": art.source,
                "published_at": art.published_at.isoformat(),
                **fields,
            }
        results.append(res)

    return results
