# src/patent_collector.py

from __future__ import annotations

from typing import List, Dict
from datetime import datetime, timedelta


def _yesterday_from_str(today_date_str: str) -> str:
    """
    today_date_str: "YYYY-MM-DD" (report date, Europe/Rome)
    ritorna "YYYY-MM-DD" del giorno precedente (per la pubblicazione brevetti).
    """
    d = datetime.strptime(today_date_str, "%Y-%m-%d").date()
    y = d - timedelta(days=1)
    return y.isoformat()


def _tag_patent(title: str, abstract: str, cpc: List[str]) -> List[str]:
    text = f"{title} {abstract}".lower()
    tags: List[str] = []

    if any(code.startswith(("G06F", "G06N", "G11")) for code in cpc) or \
       any(k in text for k in ["compute", "processor", "gpu", "accelerator", "cpu"]):
        tags.append("compute")

    if any(code.startswith(("G06Q", "H04L")) for code in cpc) or \
       any(k in text for k in ["data", "database", "analytics", "storage"]):
        tags.append("data")

    if any(code.startswith(("H04N", "H04S")) for code in cpc) or \
       any(k in text for k in ["video", "codec", "encoding", "transcoding", "streaming"]):
        tags.append("video")

    if any(k in text for k in ["cloud", "saas", "paas", "iaas", "data center", "datacenter"]):
        tags.append("cloud")

    # dedup
    return sorted(set(tags))


def _normalize_cpc(codes: List[str]) -> List[str]:
    out = []
    for c in codes or []:
        c = c.strip().upper()
        if c and c not in out:
            out.append(c)
    return out


# --------- TODO: da implementare con chiamate reali a EPO / USPTO ----------

def _fetch_epo_patents(publication_date: str) -> List[Dict]:
    """
    QUI dentro inserirai le chiamate reali a EPO OPS / Publication Server.

    Deve ritornare una lista di dict come:
    {
      "office": "EPO",
      "publication_number": "EP 3 123 456 A1",
      "title": "...",
      "abstract": "...",
      "applicants": ["..."],
      "cpc_main": ["G06F 9/50", "H04N 21/234"],
      "publication_date": "YYYY-MM-DD",
      "source_url": "https://...",
      "family_id": "optional"
    }
    """
    # Per ora ritorna lista vuota così il resto della pipeline non rompe.
    return []


def _fetch_uspto_patents(publication_date: str) -> List[Dict]:
    """
    QUI dentro inserirai le chiamate reali a USPTO Open Data / Search API.

    Deve ritornare una lista di dict con campi analoghi a quelli EPO.
    """
    return []


# ---------------------------------------------------------------------------

def collect_patent_publications(
    today_date_str: str,
    max_items: int = 20,
) -> List[Dict]:
    """
    - Calcola 'yesterday' a partire da today_date_str (report date).
    - Chiede a EPO + USPTO i brevetti pubblicati ieri.
    - Applica tagging per compute/video/data/cloud.
    - Deduplica e limita il numero finale.
    """
    target_date = _yesterday_from_str(today_date_str)
    print(f"[PATENTS] Collecting patents for previous day: {target_date}")

    epo_raw = _fetch_epo_patents(target_date)
    us_raw = _fetch_uspto_patents(target_date)

    all_raw = []
    for row in epo_raw:
        row = dict(row)
        row.setdefault("office", "EPO")
        all_raw.append(row)

    for row in us_raw:
        row = dict(row)
        row.setdefault("office", "USPTO")
        all_raw.append(row)

    # Normalizza CPC e tagging
    normalized: List[Dict] = []
    seen_keys = set()

    for p in all_raw:
        office = p.get("office", "")
        pub = p.get("publication_number", "")
        key = (office.upper(), pub.replace(" ", "").upper())
        if not pub or key in seen_keys:
            continue
        seen_keys.add(key)

        title = p.get("title", "") or ""
        abstract = p.get("abstract", "") or ""
        cpc = _normalize_cpc(p.get("cpc_main", []))
        tags = _tag_patent(title, abstract, cpc)

        if not tags:
            # se non rientra in compute/video/data/cloud, lo scartiamo
            continue

        normalized.append(
            {
                "office": office,
                "publication_number": pub,
                "title": title,
                "abstract": abstract,
                "applicants": p.get("applicants", []),
                "assignee": p.get("assignee", ""),
                "cpc_main": cpc,
                "tags": tags,
                "publication_date": p.get("publication_date", target_date),
                "source_url": p.get("source_url", ""),
                "family_id": p.get("family_id"),
            }
        )

    # per ora semplice: tronca ai primi N
    return normalized[:max_items]
