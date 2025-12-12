from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, List, Tuple
import time
import requests
from datetime import datetime  # ✅ FIX: era mancante


BASE_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = BASE_DIR / "reports" / "json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()


STOCKS = [
    {"name": "Google",   "symbol": "GOOGL"},
    {"name": "Tesla",    "symbol": "TSLA"},
    {"name": "Apple",    "symbol": "AAPL"},
    {"name": "NVIDIA",   "symbol": "NVDA"},
    {"name": "Meta",     "symbol": "META"},
    {"name": "Microsoft","symbol": "MSFT"},
    {"name": "Amazon",   "symbol": "AMZN"},
]

CRYPTOS = [
    {"name": "Bitcoin",  "symbol": "BTC"},
    {"name": "Ethereum", "symbol": "ETH"},
]


def _alpha_get(params: Dict) -> Dict:
    base_url = "https://www.alphavantage.co/query"
    params = dict(params)
    params["apikey"] = ALPHAVANTAGE_API_KEY
    resp = requests.get(base_url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _extract_last_two_points(ts: Dict[str, Dict]) -> Tuple[float, float] | None:
    """
    Dato un time-series dict {date: {...}}, ritorna (last_close, prev_close).
    """
    if not ts:
        return None
    dates = sorted(ts.keys(), reverse=True)
    if len(dates) < 2:
        return None
    d0, d1 = dates[0], dates[1]
    try:
        close0 = float(ts[d0]["4. close"])
        close1 = float(ts[d1]["4. close"])
    except Exception:
        return None
    return close0, close1


def _fetch_stock(symbol: str) -> Tuple[float, float] | None:
    """
    Usa TIME_SERIES_DAILY_ADJUSTED per avere ultimo close e precedente.
    """
    data = _alpha_get(
        {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact",
        }
    )
    ts = data.get("Time Series (Daily)")
    if not ts:
        return None
    return _extract_last_two_points(ts)


def _fetch_crypto(symbol: str) -> Tuple[float, float] | None:
    """
    Usa DIGITAL_CURRENCY_DAILY per avere ultimo close in USD.
    """
    data = _alpha_get(
        {
            "function": "DIGITAL_CURRENCY_DAILY",
            "symbol": symbol,
            "market": "USD",
        }
    )
    ts = data.get("Time Series (Digital Currency Daily)")
    if not ts:
        return None

    dates = sorted(ts.keys(), reverse=True)
    if len(dates) < 2:
        return None
    d0, d1 = dates[0], dates[1]
    try:
        close0 = float(ts[d0]["4a. close (USD)"])
        close1 = float(ts[d1]["4a. close (USD)"])
    except Exception:
        return None
    return close0, close1


def _pct_change(last_price: float, prev_price: float) -> float:
    if prev_price == 0:
        return 0.0
    return (last_price - prev_price) / prev_price * 100.0


def build_market_snapshot() -> None:
    if not ALPHAVANTAGE_API_KEY:
        print("[MARKET] ERROR: ALPHAVANTAGE_API_KEY not set.")
        return

    items: List[Dict] = []

    # Stocks
    for s in STOCKS:
        sym = s["symbol"]
        name = s["name"]
        print(f"[MARKET] Fetching stock {sym}...")
        try:
            res = _fetch_stock(sym)
        except Exception as e:
            print(f"[MARKET] ERROR stock {sym}: {e!r}")
            res = None

        if res is None:
            items.append({"name": name, "symbol": sym, "price": None, "change_pct": None})
        else:
            last_p, prev_p = res
            pct = _pct_change(last_p, prev_p)
            items.append({"name": name, "symbol": sym, "price": last_p, "change_pct": pct})

        time.sleep(12)  # rate limit safe

    # Cryptos
    for c in CRYPTOS:
        sym = c["symbol"]
        name = c["name"]
        print(f"[MARKET] Fetching crypto {sym}...")
        try:
            res = _fetch_crypto(sym)
        except Exception as e:
            print(f"[MARKET] ERROR crypto {sym}: {e!r}")
            res = None

        if res is None:
            items.append({"name": name, "symbol": sym, "price": None, "change_pct": None})
        else:
            last_p, prev_p = res
            pct = _pct_change(last_p, prev_p)
            items.append({"name": name, "symbol": sym, "price": last_p, "change_pct": pct})

        time.sleep(12)

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M CET")

    payload = {
        "updated_at": updated_at,
        "items": items,
    }

    out_path = JSON_DIR / "market_snapshot_latest.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[MARKET] Snapshot saved to {out_path}")


if __name__ == "__main__":
    build_market_snapshot()
