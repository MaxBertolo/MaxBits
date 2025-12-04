# src/summarizer.py

from __future__ import annotations

from typing import List, Dict
import os
import re
import textwrap
import html

import google.generativeai as genai

from .models import RawArticle


# =========================
#   GLOBAL LLM CONFIG
# =========================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Max articoli per cui usare il modello al giorno (gli altri vanno in fallback locale)
MAX_LLM_CALLS = 3

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[LLM] Warning: GEMINI_API_KEY non impostata – verrà usato SOLO il fallback locale.")


# =========================
#   HELPERS
# =========================

def strip_html_title(raw_title: str) -> str:
    """Rimuove eventuali tag HTML dal titolo RSS (es. <a href=...>Title</a>)."""
    if not raw_title:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_title)
    text = html.unescape(text)
    return text.strip()


def build_prompt(article: RawArticle, language: str = "en") -> str:
    """
    Prompt per Gemini: chiediamo ESATTAMENTE 5 sezioni etichettate.
    Ogni sezione deve iniziare con il label seguito da ':'.

    È pensato per massimizzare la qualità su:
      - WHY IT MATTERS (impatto)
      - STRATEGIC VIEW (contesto + opportunità 6–24 mesi)
    """
    content = (article.content or "").replace("\n", " ")
    # tagliamo se l'articolo è enorme, per non sprecare token
    if len(content) > 6000:
        content = content[:6000] + " [...]"

    title_clean = strip_html_title(article.title)

    instructions = """
You are a senior technology analyst writing for C-level executives in Telco, Media and Tech.
Your goal is to understand the strategic meaning of the news, not just rewrite it.

Read the news (title, source, content) and produce EXACTLY 5 SECTIONS in English.

CRITICAL RULES (STRICT):
- Each section MUST start with the label below, in UPPERCASE, followed by a colon.
- After the colon, write ONE clear sentence (max ~35 words).
- Keep the labels in this exact order.
- Do NOT repeat the label names inside the sentences.
- Do NOT use bullets, markdown or extra commentary.
- Do NOT add any text before the first label or after the last one.

Labels and what they MUST contain:
1) WHAT IT IS: classify the type of news (product, partnership, acquisition, funding, regulation, trend, etc.).
2) WHO: name the main companies / organizations / stakeholders involved.
3) WHAT IT DOES: describe concretely what is introduced or enabled (features, capabilities, use cases).
4) WHY IT MATTERS: explain the impact for Telco / Media / Tech players (business, technology, customers, or regulation).
5) STRATEGIC VIEW: give a strategic viewpoint over the next 6–24 months: opportunities, risks, competitive moves,
   and why this could matter in a broader ecosystem perspective.

Output format (exactly 5 labeled sections, nothing else):

WHAT IT IS: ...
WHO: ...
WHAT IT DOES: ...
WHY IT MATTERS: ...
STRATEGIC VIEW: ...
"""

    prompt = f"""{textwrap.dedent(instructions).strip()}

Title: {title_clean}
Source: {article.source}
URL: {article.url}

Content:
{content}
"""
    return prompt.strip()


def _simple_local_summary(article: RawArticle) -> Dict[str, str]:
    """
    Fallback completamente locale se Gemini non è disponibile o fallisce.
    Non è “intelligente”, ma produce qualcosa di leggibile e coerente.
    """
    title_clean = strip_html_title(article.title)
    source = article.source or "the company"

    what_it_is = (
        f"This news covers an update or initiative related to {title_clean or 'a technology topic'}."
    )
    who = (
        f"The main actor is {source}, possibly together with partners, suppliers or ecosystem players."
    )
    what_it_does = (
        "It introduces new capabilities, products or services, or reports on a move that can affect "
        "technology, operations or the market position of the companies involved."
    )
    why_it_matters = (
        "It may influence how Telco, Media and Tech players design infrastructure, services, go-to-market "
        "strategies or customer experience in the near future."
    )
    strategic_view = (
        "This is worth monitoring over the next 6–24 months for potential opportunities in partnerships, "
        "investments, new business models or competitive differentiation."
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
        "what_it_is": fields.get("what_it_is", ""),
        "who": fields.get("who", ""),
        "what_it_does": fields.get("what_it_does", ""),
        "why_it_matters": fields.get("why_it_matters", ""),
        "strategic_view": fields.get("strategic_view", ""),
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


def _parse_labeled_text(text: str) -> Dict[str, str]:
    """
    Parsing robusto delle 5 sezioni etichettate.

    Funziona anche se il modello:
      - non manda a capo le sezioni
      - inserisce testo extra fra una sezione e l'altra

    Strategia:
      - normalizziamo a maiuscolo per cercare i marker (WHAT IT IS:, WHO:, ecc.)
      - per ogni marker prendiamo il testo fino al marker successivo.
    """

    labels = [
        ("what_it_is", "WHAT IT IS"),
        ("who", "WHO"),
        ("what_it_does", "WHAT IT DOES"),
        ("why_it_matters", "WHY IT MATTERS"),
        ("strategic_view", "STRATEGIC VIEW"),
    ]

    # Versione maiuscola per cercare i marker, ma usiamo il testo originale per estrarre.
    upper = text.upper()
    out = {k: "" for k, _ in labels}

    for i, (field, label) in enumerate(labels):
        marker = label + ":"
        start = upper.find(marker)
        if start == -1:
            continue  # marker non trovato

        start_val = start + len(marker)

        # Cerca il prossimo marker tra quelli successivi
        next_positions = []
        for _, next_label in labels[i + 1 :]:
            pos = upper.find(next_label + ":", start_val)
            if pos != -1:
                next_positions.append(pos)

        end_val = min(next_positions) if next_positions else len(text)

        value = text[start_val:end_val].strip(" \n\r\t-•·:")
        out[field] = value

    return out


# =========================
#   PUBLIC API
# =========================

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
      - fallback locale in caso di errore o risposta incompleta.
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

        # Controllo robustezza: almeno 3 campi devono essere non vuoti.
        non_empty = sum(1 for v in fields.values() if v)
        if non_empty < 3:
            print("[LLM] Parsed too few fields – using local fallback.")
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
    - usa Gemini per i primi MAX_LLM_CALLS articoli (se API key presente)
    - per gli altri usa solo il fallback locale

    Nel tuo flusso attuale i deep-dives sono 3, quindi verranno
    tutti serviti da Gemini (salvo errori).
    """
    results: List[Dict] = []

    llm_budget = min(MAX_LLM_CALLS, len(articles))
    print(f"[LLM] Will use Gemini for {llm_budget} article(s), then local fallback if needed.")

    for idx, article in enumerate(articles):
        use_llm = idx < llm_budget and bool(GEMINI_API_KEY)

        if use_llm:
            title_preview = strip_html_title(article.title)[:80]
            print(f"[LLM] Summarizing article {idx + 1}: {title_preview!r}")
            res = summarize_article(
                article,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            print(f"[LLM] Skipping Gemini for article {idx + 1}, using local fallback.")
            fields = _simple_local_summary(article)
            res = _to_final_dict(article, fields)

        results.append(res)

    return results
