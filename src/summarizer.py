from typing import List, Dict
import os
import re
import textwrap
import html

import google.generativeai as genai

from .models import RawArticle


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

MAX_LLM_CALLS = 3

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[LLM] Warning: GEMINI_API_KEY non impostata – verrà usato SOLO il fallback locale.")


def strip_html_title(raw_title: str) -> str:
    if not raw_title:
        return ""
    text = re.sub(r"<[^>]+>", "", raw_title)
    text = html.unescape(text)
    return text.strip()


def build_prompt(article: RawArticle, language: str = "en") -> str:
    content = (article.content or "").replace("\n", " ")
    if len(content) > 8000:
        content = content[:8000] + " [...]"

    title_clean = strip_html_title(article.title)

    instructions = """
You are a senior technology strategist writing for a C-level in Telco / Media / Tech.

Read the following news (title, source, content) and produce EXACTLY 5 lines in English.

Each line MUST:
- start with the exact label below
- then a colon
- then a single sentence (max ~35 words)
- NEVER leave any line empty.

1) WHAT IT IS: type of news (product, partnership, acquisition, trend, regulation, etc.).
2) WHO: main companies / actors involved.
3) WHAT IT DOES: what is introduced or enabled, at functional level.
4) WHY IT MATTERS: impact and business / strategic relevance for Telco / Media / Tech.
5) STRATEGIC VIEW: your point of view on underlying strategy, positioning and 6–24 month opportunities.

Output format (exactly 5 lines, in this order, no extra text):

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
    title_clean = strip_html_title(article.title)
    source = article.source or ""

    what_it_is = f"This news discusses \"{title_clean}\" as a relevant development in connectivity, cloud or digital services."
    who = f"The main actor is {source} together with its partners and ecosystem players."
    what_it_does = (
        "It introduces or describes a concrete initiative, product or deployment that changes how networks, platforms or media services are designed, delivered or consumed."
    )
    why_it_matters = (
        "It may affect revenue mix, infrastructure investment priorities, partner ecosystems and competitive differentiation for Telco / Media / Tech players."
    )
    strategic_view = (
        "In a 6–24 month horizon it should be monitored for scale, customer adoption and regulatory feedback, as it could open new positioning and monetisation options."
    )

    return {
        "what_it_is": what_it_is,
        "who": who,
        "what_it_does": what_it_does,
        "why_it_matters": why_it_matters,
        "strategic_view": strategic_view,
    }


def _to_final_dict(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
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
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = {
        "what_it_is": "",
        "who": "",
        "what_it_does": "",
        "why_it_matters": "",
        "strategic_view": "",
    }

    for line in lines:
        upper = line.upper()
        if upper.startswith("WHAT IT IS:"):
            out["what_it_is"] = line.split(":", 1)[1].strip()
        elif upper.startswith("WHO:"):
            out["who"] = line.split(":", 1)[1].strip()
        elif upper.startswith("WHAT IT DOES:"):
            out["what_it_does"] = line.split(":", 1)[1].strip()
        elif upper.startswith("WHY IT MATTERS:"):
            out["why_it_matters"] = line.split(":", 1)[1].strip()
        elif upper.startswith("STRATEGIC VIEW:"):
            out["strategic_view"] = line.split(":", 1)[1].strip()

    return out


def _ensure_all_fields(article: RawArticle, fields: Dict[str, str]) -> Dict[str, str]:
    """
    Se Gemini ha lasciato vuoto WHY IT MATTERS o STRATEGIC VIEW,
    li ricostruiamo localmente con una frase generica ma sensata.
    """
    title_clean = strip_html_title(article.title)
    source = article.source or "the company"

    if not fields.get("what_it_is"):
        fields["what_it_is"] = (
            f"This news describes \"{title_clean}\" as a relevant development for connectivity, media or data-driven services."
        )
    if not fields.get("who"):
        fields["who"] = f"The main players involved are {source} and ecosystem partners."
    if not fields.get("what_it_does"):
        fields["what_it_does"] = (
            "It introduces a concrete technology, product or initiative that changes how services are built, delivered or monetised."
        )
    if not fields.get("why_it_matters"):
        fields["why_it_matters"] = (
            "It matters because it can reshape investment priorities, cost structure, service quality or go-to-market options for Telco / Media / Tech operators."
        )
    if not fields.get("strategic_view"):
        fields["strategic_view"] = (
            "Strategically, this move signals where the market is heading in the next 6–24 months, "
            "and opens opportunities around partnerships, differentiated offers and new revenue streams."
        )

    return fields


def summarize_article(
    article: RawArticle,
    model: str,
    temperature: float,
    max_tokens: int,
    language: str = "en",
) -> Dict[str, str]:
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
        else:
            fields = _ensure_all_fields(article, fields)

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
