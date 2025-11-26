from typing import List, Dict
import os
import requests

from .models import RawArticle

# Config HuggingFace
HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_MODEL_ID = "facebook/bart-large-cnn"  # modello di summarization free


def _structured_fallback(article: RawArticle, text: str, reason: str) -> Dict[str, str]:
    """
    Usa un unico riassunto (eventualmente di emergenza) e lo mappa
    nei 5 campi in modo semplice.
    """
    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published_at": article.published_at.isoformat(),
        "cos_e": text,
        "chi": "—",
        "cosa_fa": "—",
        "perche_interessante": f"Generato via fallback ({reason}).",
        "pov": "Per maggiori dettagli, leggere l'articolo completo dal link.",
    }


def summarize_with_huggingface(article: RawArticle) -> Dict[str, str]:
    """
    Summarization SOLO con HuggingFace (niente OpenAI).
    """
    if not HF_API_KEY:
        msg = "Riassunto non disponibile (HF_API_KEY mancante)."
        return _structured_fallback(article, msg, "HuggingFace non configurato")

    endpoint = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": article.content or (article.title + " " + article.url),
        "parameters": {"max_length": 200, "min_length": 60, "do_sample": False},
    }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        # formato tipico: [{"summary_text": "..."}]
        if isinstance(data, list) and len(data) > 0 and "summary_text" in data[0]:
            summary_text = data[0]["summary_text"]
        else:
            summary_text = str(data)
        return _structured_fallback(article, summary_text, "HuggingFace")
    except Exception as e:
        print("[WARN] HuggingFace summarization failed:", repr(e))
        msg = "Riassunto non disponibile (errore HuggingFace)."
        return _structured_fallback(article, msg, "errore HF")


def summarize_article(article: RawArticle, model: str, temperature: float, max_tokens: int) -> Dict[str, str]:
    """
    Entry point usato da main.py: IGNORA OpenAI, usa solo HuggingFace.
    I parametri model/temperature/max_tokens non vengono usati.
    """
    return summarize_with_huggingface(article)


def summarize_articles(articles: List[RawArticle], model: str, temperature: float, max_tokens: int) -> List[Dict]:
    summarized = []
    for a in articles:
        summarized.append(summarize_article(a, model=model, temperature=temperature, max_tokens=max_tokens))
    return summarized
