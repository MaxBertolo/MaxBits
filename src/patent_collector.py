# src/patent_collector.py

from __future__ import annotations

from typing import List, Dict
from datetime import datetime, timedelta
import os
import base64
import json

import requests
from xml.etree import ElementTree as ET


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


# ---------------------------------------------------------------------------
#   EPO OPS HELPERS
# ---------------------------------------------------------------------------

def _get_epo_access_token() -> str | None:
    """
    Ottiene un access token EPO OPS via OAuth2 client_credentials.

    Richiede:
      - EPO_OPS_KEY
      - EPO_OPS_SECRET

    Ritorna il token (string) o None se non configurato o errore.
    """
    key = os.getenv("EPO_OPS_KEY", "").strip()
    secret = os.getenv("EPO_OPS_SECRET", "").strip()
    if not key or not secret:
        print("[PATENTS][EPO] EPO_OPS_KEY / EPO_OPS_SECRET not set – skipping EPO.")
        return None

    token_url = "https://ops.epo.org/3.2/auth/accesstoken"
    auth_bytes = f"{key}:{secret}".encode("utf-8")
    auth_header = "Basic " + base64.b64encode(auth_bytes).decode("ascii")

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}

    try:
        resp = requests.post(token_url, headers=headers, data=data, timeout=10)
        if resp.status_code != 200:
            print(f"[PATENTS][EPO] Token request failed: {resp.status_code} {resp.text[:200]}")
            return None
        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            print("[PATENTS][EPO] Token missing in response.")
            return None
        return token
    except Exception as e:
        print("[PATENTS][EPO] Exception while requesting token:", repr(e))
        return None


def _fetch_epo_patents(publication_date: str) -> List[Dict]:
    """
    Richiama OPS 'published-data/search' (biblio) per trovare brevetti EP
    pubblicati in una certa data con CPC nell'area compute/video/data/cloud.

    Per semplificare, limitiamo la ricerca a un range piccolo e al primo batch.
    """
    token = _get_epo_access_token()
    if not token:
        return []

    # Esempio CQL:
    #  pd=2025.12.06 and (cpc=G06F or cpc=G06N or cpc=G06Q or cpc=H04N or cpc=H04L)
    d = datetime.strptime(publication_date, "%Y-%m-%d")
    pd_str = d.strftime("%Y.%m.%d")
    cql = f"pd={pd_str} and (cpc=G06F or cpc=G06N or cpc=G06Q or cpc=H04N or cpc=H04L)"

    url = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/xml",
        "X-OPS-Range": "1-50",  # primi 50 documenti della query
    }
    params = {"q": cql}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"[PATENTS][EPO] Search failed: {resp.status_code} {resp.text[:200]}")
            return []

        xml_root = ET.fromstring(resp.text)
        ns = {
            "ops": "http://ops.epo.org",
            "exchange-doc": "http://www.epo.org/exchange",
            "dc": "http://purl.org/dc/elements/1.1/",
        }

        results: List[Dict] = []

        # Struttura semplificata: cerchiamo 'exchange-doc:exchange-document'
        for doc in xml_root.findall(".//exchange-doc:exchange-document", ns):
            pub_ref = doc.find(".//exchange-doc:publication-reference", ns)
            pub_number = ""
            if pub_ref is not None:
                doc_id = pub_ref.find(".//exchange-doc:doc-number", ns)
                kind = pub_ref.find(".//exchange-doc:kind", ns)
                if doc_id is not None:
                    pub_number = doc_id.text or ""
                    if kind is not None and kind.text:
                        pub_number = f"{pub_number} {kind.text}"

            title_el = doc.find(".//exchange-doc:invention-title", ns)
            title = title_el.text if title_el is not None else ""

            abs_el = doc.find(".//exchange-doc:abstract/exchange-doc:p", ns)
            abstract = abs_el.text if abs_el is not None else ""

            applicants: List[str] = []
            for app in doc.findall(".//exchange-doc:applicants/exchange-doc:applicant", ns):
                name_el = app.find(".//exchange-doc:applicant-name", ns)
                if name_el is not None and name_el.text:
                    applicants.append(name_el.text)

            cpc_codes: List[str] = []
            for c in doc.findall(".//exchange-doc:classification-cpc", ns):
                sec = c.find(".//exchange-doc:section", ns)
                cla = c.find(".//exchange-doc:class", ns)
                sub = c.find(".//exchange-doc:subclass", ns)
                main = c.find(".//exchange-doc:main-group", ns)
                subg = c.find(".//exchange-doc:subgroup", ns)
                parts = [x.text for x in (sec, cla, sub, main, subg) if x is not None and x.text]
                if parts:
                    cpc_codes.append("".join(parts))

            results.append(
                {
                    "office": "EPO",
                    "publication_number": pub_number.strip(),
                    "title": title or "",
                    "abstract": abstract or "",
                    "applicants": applicants,
                    "cpc_main": cpc_codes,
                    "publication_date": publication_date,
                    "source_url": "",  # opzionale: potresti costruire link Espacenet qui
                    "family_id": None,
                }
            )

        return results

    except Exception as e:
        print("[PATENTS][EPO] Exception while fetching patents:", repr(e))
        return []


# ---------------------------------------------------------------------------
#   USPTO IBD API
# ---------------------------------------------------------------------------

def _fetch_uspto_patents(publication_date: str) -> List[Dict]:
    """
    Usa USPTO Bulk Search & Download API (IBD API) per cercare
    tutte le application/grant con data di pubblicazione == publication_date.

    Endpoint:
      https://developer.uspto.gov/ibd-api/v1/patent/application

    La risposta è in JSON con struttura:
      { "response": { "docs": [ ... ] } }

    Per semplicità:
      - non filtriamo per CPC a livello di query
      - ci affidiamo al tagging successivo su titolo/abstract
    """
    base_url = "https://developer.uspto.gov/ibd-api/v1/patent/application"
    params = {
        "publicationFromDate": publication_date,
        "publicationToDate": publication_date,
        "rows": 100,
        "start": 0,
    }

    try:
        resp = requests.get(base_url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"[PATENTS][USPTO] Search failed: {resp.status_code} {resp.text[:200]}")
            return []

        # La risposta è JSON: {"response": {"numFound":..., "docs":[...]}}
        payload = resp.json()
        response = payload.get("response", {})
        docs = response.get("docs", [])
        results: List[Dict] = []

        for d in docs:
            title = d.get("title", "")
            abstract = d.get("abstract", "")
            # classificazioni: dipende dal dataset, non sempre c'è CPC
            # proviamo a leggere qualche campo tipico, altrimenti lista vuota
            cpc_fields = []
            for k in ("cpcSubgroup", "cpc_subgroup", "cpc", "cpcClassification"):
                v = d.get(k)
                if isinstance(v, list):
                    cpc_fields.extend(v)
                elif isinstance(v, str):
                    cpc_fields.append(v)

            applicants = []
            for k in ("assignee", "applicant"):
                v = d.get(k)
                if isinstance(v, list):
                    applicants.extend(v)
                elif isinstance(v, str):
                    applicants.append(v)

            pub_number = d.get("documentId") or d.get("patentNumber") or ""

            results.append(
                {
                    "office": "USPTO",
                    "publication_number": pub_number,
                    "title": title or "",
                    "abstract": abstract or "",
                    "applicants": applicants,
                    "assignee": d.get("assignee", ""),
                    "cpc_main": cpc_fields,
                    "publication_date": publication_date,
                    # un link base all'invenzione (non perfetto ma utile)
                    "source_url": "",  # puoi costruire link a patentcenter se vuoi
                    "family_id": None,
                }
            )

        return results

    except Exception as e:
        print("[PATENTS][USPTO] Exception while fetching patents:", repr(e))
        return []


# ---------------------------------------------------------------------------
#   ENTRY POINT USATO DA main.py
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
