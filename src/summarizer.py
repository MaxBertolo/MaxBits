from typing import List, Dict
import os

import google.generativeai as genai

from .models import RawArticle


# ===============================
# Gemini configuration
# ===============================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_FALLBACK = "gemini-2.5-flash"

# Numero massimo di articoli da riassumere con l'LLM
# (per stare nei limiti della free tier)
MAX_LLM_CALLS = 5


def _configure_gemini():
    """
    Inizializza la libreria Gemini con la API key.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY not set. "
            "Set the secret GEMINI_API_KEY in GitHub Actions."
        )
    genai.configure(api_key=GEMINI_API_KEY)


# ===============================
# Prompt builder
# ===============================

def build_prompt(article: RawArticle) -> str:
    """
    Prompt in inglese, stile approfondito per manager Telco/Media.
    Il formato di output è TESTUALE con etichette, non JSON.
    """
    return f"""
You are a senior technology & strategy analyst writing for a C-level executive
in a Telco/Media/Tech company.

Read the NEWS (title + content) and produce a DEEP, STRUCTURED analysis.

### GOAL

Produce EXACTLY 5 labelled sections, in this order:

WHAT IT IS: ...
WHO: ...
WHAT IT DOES: ...
WHY IT MATTERS: ...
STRATEGIC VIEW: ...

### STYLE & GUIDELINES

- Language: English.
- Tone: professional, clear, business-oriented (no marketing fluff).
- Each section should be a short paragraph (2–3 sentences).
- Avoid generic statements like "this is important" without explaining why.
- Do NOT invent companies or facts that are not supported by the text.

FIELD DETAILS:

- WHAT IT IS:
    2–3 sentences explaining what the news is about:
    product launch, partnership, acquisition, regulation, funding round,
    infrastructure build-out, technology milestone, etc.

- WHO:
    2 sentences describing the main actors (companies, institutions, key roles)
    and their roles in the news.

- WHAT IT DOES:
    2–3 sentences explaining concretely what this initiative/technology enables
    or changes (capabilities, use cases, segments impacted).

- WHY IT MATTERS:
    2–3 sentences about why this matters for Telco/Media/Tech/AI:
    networks, cloud, AI, advertising, streaming, robotics,
    data centers, satellite, infrastructure.

- STRATEGIC VIEW:
    2–3 sentences with a forward-looking point of view (6–24 months):
    risks & opportunities, likely impact on operators, broadcasters,
    OTTs, hyperscalers, or players like Sky.

### OUTPUT FORMAT (VERY IMPORTANT)

- Answer ONLY with plain text.
- Use EXACTLY these 5 labels in uppercase English:
  - WHAT IT IS:
  - WHO:
  - WHAT IT DOES:
  - WHY IT MATTERS:
  - STRATEGIC VIEW:
- Each label must start a new line.

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
    Fallback se la chiamata a Gemini fallisce o non vogliamo usare l'LLM
    (es. per risparmiare quota free).
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
# Helpers
# ===============================

def _extract_text_from_response(response) -> str:
    """
    Prova a estrarre testo dalla risposta Gemini in modo robusto.
    """
    # Caso standard: risposta con .text
    try:
        txt = getattr(response, "text", None)
        if txt:
            return txt.strip()
    except Exception:
        pass

    # Caso: usiamo parts del primo candidato
    try:
        if response.candidates:
            parts = response.candidates[0].content.parts
            texts = []
            for p in parts:
                t = getattr(p, "text", None)
                if t:
                    texts.append(t)
            joined = " ".join(texts).strip()
            if joined:
                return joined
    except Exception:
        pass

    return ""


def _parse_labelled_text(text: str) -> Dict[str, str]:
    """
    Parsiamo il testo con etichette tipo:

    WHAT IT IS: ...
    WHO: ...
    WHAT IT DOES: ...
    WHY IT MATTERS: ...
    STRATEGIC VIEW: ...

    Restituiamo un dict con chiavi logiche.
    """
    sections = {
        "WHAT IT IS:": "",
        "WHO:": "",
        "WHAT IT DOES:": "",
        "WHY IT MATTERS:": "",
        "STRATEGIC VIEW:": "",
    }

    current_label = None
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for line in lines:
        upper = line.upper()
        # Se la linea inizia con una delle etichette, cambiamo contesto
        matched_label = None
        for label in sections.keys():
            if upper.startswith(label):
                matched_label = label
                break

        if matched_label:
            current_label = matched_label
            content = line[len(matched_label):].strip()
            if content:
                sections[current_label] = content
        else:
            # linea successiva: la aggiungiamo alla sezione corrente
            if current_label:
                if sections[current_label]:
                    sections[current_label] += " " + line
                else:
                    sections[current_label] = line

    return {
        "what_it_is": sections["WHAT IT IS:"].strip(),
        "who": sections["WHO:"].strip(),
        "what_it_does": sections["WHAT IT DOES:"].strip(),
        "why_it_matters": sections["WHY IT MATTERS:"].strip(),
        "strategic_view": sections["STRATEGIC VIEW:"].strip(),
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

    mdl_name = model or GEMINI_MODEL_FALLBACK
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
        text = _extract_text_from_response(response)
    except Exception as e:
        print("[LLM] Error calling Gemini:", repr(e))
        return _fallback_summary(article, "Gemini call error")

    if not text:
        return _fallback_summary(article, "empty response")

    sections = _parse_labelled_text(text)

    if not any(sections.values()):
        return _fallback_summary(article, "no labelled sections found")

    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "cos_e": sections["what_it_is"],
        "chi": sections["who"],
        "cosa_fa": sections["what_it_does"],
        "perche_interessante": sections["why_it_matters"],
        "pov": sections["strategic_view"],
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

    Per rimanere nei limiti della free tier:
    - usiamo Gemini solo per i primi MAX_LLM_CALLS articoli
    - per gli altri usiamo il fallback.
    """
    summarized: List[Dict] = []

    for idx, a in enumerate(articles):
        if idx < MAX_LLM_CALLS:
            summarized.append(
                summarize_article(
                    a,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )
        else:
            print(
                f"[LLM] Skipping Gemini for article {idx+1}, using fallback "
                f"to preserve free-tier quota."
            )
            summarized.append(
                _fallback_summary(
                    a,
                    "LLM quota reserved for top articles (free tier limit)",
                )
            )

    return summarized
