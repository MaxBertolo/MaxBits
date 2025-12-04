# ==========================================
#  SUMMARIZER — VERSIONE STABILE / CORRETTA
# ==========================================

from __future__ import annotations
import os
import re
import textwrap
import html
from typing import Dict, List

import google.generativeai as genai

from .models import RawArticle


# -----------------------------------------------------
# LLM INITIALIZATION
# -----------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
MAX_LLM_CALLS = 3

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# -----------------------------------------------------
# TEXT CLEANING & VALIDATION UTILITIES
# -----------------------------------------------------

def clean_sentence(s: str) -> str:
    """Cleanup: remove double spaces, fix punctuation, trim."""
    if not s:
        return ""

    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" -–—\n\t")

    # Fix: ensure sentence ends with punctuation.
    if s and s[-1] not in ".!?":
        s += "."

    return s


def is_messy(s: str) -> bool:
    """Detect garbage: multiple labels inside one field, too long, nonsense."""
    if not s:
        return True
    if len(s) > 300:
        return True
    if re.search(r"WHAT IT|WHY IT|STRATEGIC|WHO:", s.upper()):
        return True
    return False


def sanitize_field(s: str) -> str:
    """Return cleaned field or empty if garbage."""
    s = clean_sentence(s)
    if is_messy(s):
        return ""
    return s


def ensure_english_capitalization(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    return s[0].upper() + s[1:]


# -----------------------------------------------------
# PROMPT GENERATION
# -----------------------------------------------------

def build_prompt(article: RawArticle) -> str:
    content = (article.content or "").replace("\n", " ")
    if len(content) > 6000:
        content = content[:6000] + " [...]"

    title = html.unescape(article.title)

    instructions = """
You are a senior technology analyst writing for C-level executives.

Produce EXACTLY 5 SECTIONS in English.
STRICT RULES:
- Each section must start with the label in UPPERCASE + colon.
- Each section must be ONE sentence (max ~35 words).
- No bullets, no markdown, no extra text.
- No mixing of labels on the same line.

Labels:
WHAT IT IS:
WHO:
WHAT IT DOES:
WHY IT MATTERS:
STRATEGIC VIEW:
"""

    return f"""{textwrap.dedent(instructions).strip()}

Title: {title}
Source: {article.source}
URL: {article.url}

Content:
{content}
"""


# -----------------------------------------------------
# PARSER ROBUSTO
# -----------------------------------------------------

def parse_llm_output(text: str) -> Dict[str, str]:
    """
    Parser ULTRA-Robusto.
    Taglia, separa e pulisce anche output sporchi.
    """

    labels = [
        ("what_it_is", "WHAT IT IS:"),
        ("who", "WHO:"),
        ("what_it_does", "WHAT IT DOES:"),
        ("why_it_matters", "WHY IT MATTERS:"),
        ("strategic_view", "STRATEGIC VIEW:"),
    ]

    out = {k: "" for k, _ in labels}
    upper = text.upper()

    for i, (key, label) in enumerate(labels):
        start = upper.find(label)
        if start == -1:
            continue

        start_val = start + len(label)

        # look ahead for next label
        next_positions = []
        for _, nxt in labels[i+1:]:
            pos = upper.find(nxt, start_val)
            if pos != -1:
                next_positions.append(pos)

        end_val = min(next_positions) if next_positions else len(text)

        segment = text[start_val:end_val].strip()
        out[key] = sanitize_field(segment)

    return out


# -----------------------------------------------------
# RULE-BASED RECONSTRUCTION (if fields missing)
# -----------------------------------------------------

def reconstruct_fields(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    """
    If some fields are empty or garbage, reconstruct them with rules-based logic.
    """

    title = html.unescape(article.title)
    source = article.source or "the company"

    if not fields["what_it_is"]:
        fields["what_it_is"] = f"This news concerns an update related to {title}."

    if not fields["who"]:
        fields["who"] = f"The main actors involved include {source}."

    if not fields["what_it_does"]:
        fields["what_it_does"] = (
            f"It introduces new capabilities or actions connected with {title.lower()}."
        )

    if not fields["why_it_matters"]:
        fields["why_it_matters"] = (
            "It may influence technology, strategy, partnerships, market competition or "
            "infrastructure priorities for Telco, Media or Tech companies."
        )

    if not fields["strategic_view"]:
        fields["strategic_view"] = (
            "Over the next 6–24 months, this could reshape competitive positions, "
            "ecosystem partnerships or long-term investment decisions."
        )

    # final cleanup
    for k in fields:
        fields[k] = ensure_english_capitalization(clean_sentence(fields[k]))

    return fields


# -----------------------------------------------------
# LLM CALL
# -----------------------------------------------------

def call_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing Gemini key")

    model = genai.GenerativeModel(GEMINI_MODEL_DEFAULT)
    resp = model.generate_content(prompt)
    txt = getattr(resp, "text", "").strip()

    if not txt:
        raise RuntimeError("Gemini returned empty response")

    return txt


# -----------------------------------------------------
# SINGLE ARTICLE SUMMARIZATION (ROBUST)
# -----------------------------------------------------

def summarize_article(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Dict[str, str]:
    """
    Nuova pipeline SUPER ROBUSTA:
    1. prompt → Gemini
    2. parsing robusto
    3. validazione + correzione
    4. ricostruzione automatica dei campi mancanti
    """

    if not GEMINI_API_KEY:
        print("[LLM] No Gemini key → fallback local summary.")
        fields = _local_summary(article)
        return _final(article, fields)

    prompt = build_prompt(article)

    try:
        raw = call_gemini(prompt)
        fields = parse_llm_output(raw)

        # If fields are too empty → fix automatically
        empty_count = sum(1 for v in fields.values() if not v)
        if empty_count > 2:
            print("[LLM] Output incomplete → reconstructing fields.")
            fields = reconstruct_fields(article, fields)

    except Exception as e:
        print("[LLM] ERROR:", e)
        fields = reconstruct_fields(article, {"what_it_is": "", "who": "", "what_it_does": "", "why_it_matters": "", "strategic_view": ""})

    return _final(article, fields)


# fallback local
def _local_summary(article: RawArticle) -> Dict[str, str]:
    return {
        "what_it_is": f"This news concerns {article.title}.",
        "who": f"The article involves {article.source}.",
        "what_it_does": "It introduces new development or initiative.",
        "why_it_matters": "It may affect Telco/Media/Tech strategy or operations.",
        "strategic_view": "This could open new opportunities over the next 6–24 months.",
    }


def _final(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    return {
        "title": html.unescape(article.title),
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        **fields
    }


# -----------------------------------------------------
# MULTI-ARTICLE
# -----------------------------------------------------

def summarize_articles(articles: List[RawArticle], model: str, temperature: float, max_tokens: int) -> List[Dict]:
    results = []
    for i, art in enumerate(articles):
        print(f"[LLM] Summarizing article {i+1}/{len(articles)}")
        res = summarize_article(art, model, temperature, max_tokens)
        results.append(res)
    return results
