from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
import os

import requests


logger = logging.getLogger(__name__)

# -------------------------------
#  TOPIC KEYWORDS (Compute/Video/Data/Cloud)
# -------------------------------

TOPIC_KEYWORDS = [
    # compute / infra
    "compute", "computing", "processor", "cpu", "gpu", "accelerator", "asic",
    "neural network accelerator", "tensor core", "inference engine",
    "data center", "datacenter", "edge computing", "cloud computing",
    "distributed computing", "virtualization", "kubernetes",

    # video
    "video", "codec", "encoding", "decoding", "transcoding",
    "streaming", "adaptive bitrate", "abr", "h.264", "avc", "h.265",
    "hevc", "vvc", "av1", "vp9", "vrt", "immersive video",

    # data
    "data storage", "database", "datastore", "data pipeline",
    "data processing", "analytics", "big data", "olap", "oltp",

    # cloud
    "cloud service", "cloud platform", "saas", "paas", "iaas",
    "object storage", "block storage", "cloud-native", "serverless",

    # ai tie-in (spesso compute/cloud related)
    "machine learning", "deep learning", "neural network",
    "llm", "large language model", "transformer", "inference",
]

# -------------------------------
#  APPLICANT / ASSIGNEE WATCHLIST
# -------------------------------

WATCHLIST_APPLICANTS = [
    "v-nova",
    "vnova",
    "nvidia",
    "apple",
    "microsoft",
    "tesla",
    "x corp",
    "x corp.",
    "twitter",          # per vecchio naming
    "spacex",
    "space x",
    "oneweb",
    "one web",
    "google",
    "alphabet",
    "youtube",
    "meta",
    "facebook",
    "the thinking machine lab",
    "openai",
    "mistral ai",
    "mistral",
    "samsung",
    "LG"
    "Sony"
    "Amdocs"
    "Netflix"
    "Comcast"
    "Cujo"
    "Leonardo"
    "British Telecom"
]


def _norm(s: str) -> str:
    if not s:
        return ""
    return " ".join(s.lower().split())


def _matches_topic_keywords(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in TOPIC_KEYWORDS)


def _matches_watchlist_applicant(pat: Dict[str, Any]) -> bool:
    """
    Ritorna True se uno degli applicants / assignee contiene
    un nome in WATCHLIST_APPLICANTS (case-insensitive, substring).
    """
    names: List[str] = []

    applicants = pat.get("applicants") or []
    if isinstance(applicants, str):
        names.append(applicants)
    else:
        names.extend(str(a) for a in applicants if a)

    assignee = pat.get("assignee")
    if assignee:
        names.append(str(assignee))

    if not names:
        return False

    norm_watch = [ _norm(w) for w in WATCHLIST_APPLICANTS ]

    for raw in names:
        n = _norm(raw)
        if not n:
            continue
        for w in norm_watch:
            if w and w in n:
                return True
    return False


# -------------------------------
#  FETCHERS (EPO / USPTO) – ESEMPI
# -------------------------------

def _fetch_epo_patents(publication_date: str, max_items: int = 50) -> List[Dict]:
    """
    Placeholder per fetch da EPO (Open Patent Services).

    publication_date: stringa 'YYYY-MM-DD' (giorno di pubblicazione).
    Ritorna una lista di dict con chiavi standardizzate:
      - office: "EPO"
      - publication_number
      - title
      - abstract
      - publication_date
      - applicants: List[str]
      - assignee: str (opzionale)
      - source_url
      - tags: List[str]
    """
    logger.info("[PATENTS][EPO] Fetching patents for date=%s", publication_date)

    # QUI devi integrare la tua logica reale verso OPS / EPO.
    # Per ora mettiamo uno stub vuoto.
    results: List[Dict] = []

    # Esempio di record (da usare per test locale):
    # results.append(
    #     {
    #         "office": "EPO",
    #         "publication_number": "EP1234567A1",
    #         "title": "Cloud-native video encoding system",
    #         "abstract": "A system for distributed cloud-native video encoding...",
    #         "publication_date": publication_date,
    #         "applicants": ["v-Nova International Ltd."],
    #         "assignee": "",
    #         "source_url": "https://register.epo.org/application?number=EP1234567",
    #         "tags": [],
    #     }
    # )

    return results[:max_items]


def _fetch_uspto_patents(publication_date: str, max_items: int = 50) -> List[Dict]:
    """
    Placeholder per fetch da USPTO (es. Patent Public Search / PatentsView / API interne).

    publication_date: stringa 'YYYY-MM-DD'.
    Ritorna la stessa struttura di _fetch_epo_patents.
    """
    logger.info("[PATENTS][USPTO] Fetching patents for date=%s", publication_date)

    # Anche qui: integra la tua logica reale verso l'API USPTO che preferisci.
    results: List[Dict] = []

    # Esempio fittizio:
    # results.append(
    #     {
    #         "office": "USPTO",
    #         "publication_number": "US2025XXXXXXA1",
    #         "title": "GPU-accelerated cloud inference platform",
    #         "abstract": "Techniques for deploying GPU-accelerated inference workloads in a cloud environment...",
    #         "publication_date": publication_date,
    #         "applicants": ["NVIDIA Corporation"],
    #         "assignee": "NVIDIA Corporation",
    #         "source_url": "https://patents.google.com/patent/US2025XXXXXXA1/en",
    #         "tags": [],
    #     }
    # )

    return results[:max_items]


# -------------------------------
#  COLLECTOR PRINCIPALE
# -------------------------------

def _enrich_tags(pat: Dict[str, Any]) -> None:
    """
    - Aggiunge tag 'topic-compute-video-data-cloud' se matcha le keyword.
    - Aggiunge tag 'watchlist-applicant' se appartiene alla watchlist.
    """
    tags = list(pat.get("tags") or [])
    text = " ".join(
        [
            pat.get("title") or "",
            pat.get("abstract") or "",
        ]
    )
    if _matches_topic_keywords(text):
        tags.append("topic-compute-video-data-cloud")

    if _matches_watchlist_applicant(pat):
        tags.append("watchlist-applicant")

    # de-duplicate
    dedup = []
    for t in tags:
        if t and t not in dedup:
            dedup.append(t)
    pat["tags"] = dedup


def collect_patent_publications(
    today_date_str: str,
    max_items: int = 20,
) -> List[Dict]:
    """
    Raccoglie i brevetti pubblicati nel **giorno precedente** (EPO + USPTO)
    e filtra su:

      1. Topic = Compute / Video / Data / Cloud (keywords)
      2. OPPURE applicant/assignee in WATCHLIST_APPLICANTS

    In output torna una lista di dict pronti per il `report_builder`,
    già etichettati con tag:
      - "topic-compute-video-data-cloud"
      - "watchlist-applicant" (se applicable)
    """
    try:
        today = datetime.strptime(today_date_str, "%Y-%m-%d").date()
    except ValueError:
        # fallback: se la stringa non è valida, usiamo la data di oggi del sistema
        today = datetime.utcnow().date()

    prev_day = today - timedelta(days=1)
    prev_str = prev_day.strftime("%Y-%m-%d")

    logger.info("[PATENTS] Collecting publications for previous day: %s", prev_str)

    epo = _fetch_epo_patents(prev_str, max_items=max_items * 2)
    us = _fetch_uspto_patents(prev_str, max_items=max_items * 2)

    all_raw: List[Dict] = epo + us
    logger.info("[PATENTS] Raw collected: EPO=%d, US=%d", len(epo), len(us))

    filtered: List[Dict] = []

    for pat in all_raw:
        # Enrich tags based on title/abstract + watchlist
        _enrich_tags(pat)

        text = " ".join(
            [
                pat.get("title") or "",
                pat.get("abstract") or "",
            ]
        )

        topic_match = _matches_topic_keywords(text)
        watchlist_match = _matches_watchlist_applicant(pat)

        # FILTRO PRINCIPALE:
        # - tieni se è on-topic
        #   OPPURE
        # - appartiene alla watchlist dei big player che ti interessano.
        if not (topic_match or watchlist_match):
            continue

        # Normalizza campi minimi richiesti dal report_builder
        pat.setdefault("office", "UNKNOWN")
        pat.setdefault("publication_number", "")
        pat.setdefault("title", "")
        pat.setdefault("publication_date", prev_str)
        pat.setdefault("applicants", [])
        pat.setdefault("assignee", "")
        pat.setdefault("source_url", "")

        filtered.append(pat)

    # Ordiniamo: prima per data (disc), poi per office, poi per pub number
    def _sort_key(p: Dict[str, Any]):
        d_str = p.get("publication_date") or prev_str
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except Exception:
            d = prev_day
        return (d, p.get("office", ""), p.get("publication_number", ""))

    filtered_sorted = sorted(filtered, key=_sort_key, reverse=True)

    if len(filtered_sorted) > max_items:
        filtered_sorted = filtered_sorted[:max_items]

    logger.info("[PATENTS] Filtered relevant publications: %d", len(filtered_sorted))
    return filtered_sorted
