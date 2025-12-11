# src/market_snapshot.py

from __future__ import annotations

import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

import requests


BASE_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = BASE_DIR / "reports" / "json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

ALPHA_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()

# Titoli che vuoi nel riquadro
INSTRUMENTS = [
    {"label": "Google",   "symbol": "GOOGL",   "type": "equity"},
    {"label": "Tesla",    "symbol": "TSLA",    "type": "equity"},
    {"label": "Apple",    "symbol": "AAPL",    "type": "equity"},
    {"label": "NVIDIA",   "symbol": "NVDA",    "type": "equity"},
    {"label": "Meta",     "symbol": "META",    "type": "equity"},
    {"label": "Microsoft","symbol": "MSFT",    "type": "equity"},
    {"label": "Amazon",   "symbol": "AMZN",    "type": "equity"},
    {"label": "Bitcoin",  "symbol": "BTC",     "type": "crypto"},
    {"label": "Ethereum", "symbol": "ETH",     "type": "crypto"},
]


def _now_cet() -> datetime:
    """
    Rende un orario approssimativo CET = UTC+1 (senza gestire DST).
    Va benissimo per l'etichetta 'updated at ... CET'.
    """
    now_utc = datetime.now(timezone.utc)
    return now_utc + timedelta(hours=1)


def _fetch_equity(symbol: str) -> Dict[str, Any]:
    """
    Usa Alpha Vantage GLOBAL_QUOTE per le azioni.
    """
    if not ALPHA_KEY:
        return {"price": None, "change_pct": None}

    url = (
        "https://www.alphavantage.co/query"
        "?function=GLOBAL_QUOTE"
        f"&symbol={symbol}"
        f"&apikey={ALPHA_KEY}"
    )
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json().get("Global Quote", {})
        price_str = data.get("05. price")
        pct_str = data.get("10. change percent")

        price = float(price_str) if price_str else None
        if pct_str and pct_str.endswith("%"):
            pct = float(pct_str.rstrip("%"))
        else:
            pct = None

        return {"price": price, "change_pct": pct}
    except Exception as e:
        print(f"[MARKET] Equity {symbol} error: {e!r}")
        return {"price": None, "change_pct": None}


def _fetch_crypto(symbol: str) -> Dict[str, Any]:
    """
    Usa DIGITAL_CURRENCY_DAILY per crypto (BTC/ETH vs USD).
    Calcola % change fra ultimo giorno e giorno precedente.
    """
    if not ALPHA_KEY:
        return {"price": None, "change_pct": None}

    url = (
        "https://www.alphavantage.co/query"
        "?function=DIGITAL_CURRENCY_DAILY"
        f"&symbol={symbol}"
        "&market=USD"
        f"&apikey={ALPHA_KEY}"
    )
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        series = resp.json().get("Time Series (Digital Currency Daily)", {})
        if not series:
            return {"price": None, "change_pct": None}

        dates = sorted(series.keys(), reverse=True)
        latest = dates[0]
        latest_data = series[latest]
        price_latest = float(latest_data.get("4a. close (USD)", "0") or "0")

        pct = None
        if len(dates) > 1:
            prev = dates[1]
            prev_data = series[prev]
            price_prev = float(prev_data.get("4a. close (USD)", "0") or "0")
            if price_prev > 0:
                pct = (price_latest / price_prev - 1.0) * 100.0

        return {"price": price_latest, "change_pct": pct}
    except Exception as e:
        print(f"[MARKET] Crypto {symbol} error: {e!r}")
        return {"price": None, "change_pct": None}


def build_market_snapshot() -> None:
    cet_now = _now_cet()
    as_of_label = cet_now.strftime("%Y-%m-%d %H:%M CET")
    print("[MARKET] Building snapshot at", as_of_label)

    items: List[Dict[str, Any]] = []

    for idx, inst in enumerate(INSTRUMENTS):
        label = inst["label"]
        symbol = inst["symbol"]
        t = inst["type"]

        # piccolo delay per rispettare i limiti free di Alpha Vantage
        if idx > 0:
            time.sleep(13)  # circa 5 call/min -> safe

        if t == "equity":
            data = _fetch_equity(symbol)
        else:
            data = _fetch_crypto(symbol)

        item = {
            "label": label,
            "symbol": symbol,
            "type": t,
            "price": data["price"],
            "change_pct": data["change_pct"],
        }
        print(f"[MARKET] {label} ({symbol}) -> {item['price']} / {item['change_pct']}")
        items.append(item)

    snapshot = {
        "as_of_label": as_of_label,
        "items": items,
    }

    # file del giorno+ora (log storico)
    fname = f"market_snapshot_{cet_now.strftime('%Y-%m-%d_%H%M')}.json"
    path_hist = JSON_DIR / fname
    path_hist.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    # file "latest" che il magazine legge
    latest_path = JSON_DIR / "market_snapshot_latest.json"
    latest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[MARKET] Saved latest snapshot to: {latest_path}")


if __name__ == "__main__":
    build_market_snapshot()
