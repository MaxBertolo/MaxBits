from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

import requests


BASE_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = BASE_DIR / "reports" / "json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()

STOCKS = [
    {"name": "Google",    "symbol": "GOOGL"},
    {"name": "Tesla",     "symbol": "TSLA"},
    {"name": "Apple",     "symbol": "AAPL"},
    {"name": "NVIDIA",    "symbol": "NVDA"},
    {"name": "Meta",      "symbol": "META"},
    {"name": "Microsoft", "symbol": "MSFT"},
    {"name": "Amazon",    "symbol": "AMZN"},
]

CRYPTOS = [
    {"name": "Bitcoin",   "symbol": "BTC"},
    {"name": "Ethereum",  "symbol": "ETH"},
]


# ---- Alpha Vantage helper (robust) ----

def _alpha_get(params: Dict[str, Any], *, max_retries: int = 5) -> Dict[str, Any]:
    """
    Calls Alpha Vantage and handles:
    - transient network issues
    - throttling JSON (Note / Information)
    - error message JSON
    """
    if not ALPHAVANTAGE_API_KEY:
        return {"_error": "ALPHAVANTAGE_API_KEY not set"}

    base_url = "https://www.alphavantage.co/query"
    p = dict(params)
    p["apikey"] = ALPHAVANTAGE_API_KEY

    backoff_seconds = 20
    last_err: str | None = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(base_url, params=p, timeout=25)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}

            # throttling / informational responses
            if isinstance(data, dict):
                if "Note" in data or "Information" in data:
                    msg = data.get("Note") or data.get("Information") or "Throttled"
                    print(f"[MARKET] Throttled by AlphaVantage (attempt {attempt}/{max_retries}): {msg}")
                    time.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2, 120)
                    continue

                if "Error Message" in data:
                    last_err = str(data.get("Error Message"))
                    print(f"[MARKET] AlphaVantage error (attempt {attempt}/{max_retries}): {last_err}")
                    break

            return data if isinstance(data, dict) else {}

        except Exception as e:
            last_err = repr(e)
            print(f"[MARKET] Request error (attempt {attempt}/{max_retries}): {last_err}")
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 120)

    return {"_error": last_err or "unknown error"}


def _extract_last_two_points_daily(ts: Dict[str, Dict[str, str]]) -> Optional[Tuple[float, float]]:
    """
    AlphaVantage daily TS: {date: {"4. close": "..."}}
    returns (last_close, prev_close)
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


def _fetch_stock(symbol: str) -> Optional[Tuple[float, float]]:
    """
    TIME_SERIES_DAILY_ADJUSTED -> Time Series (Daily) -> 4. close
    """
    data = _alpha_get(
        {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact",
        }
    )
    if "_error" in data:
        return None

    ts = data.get("Time Series (Daily)")
    if not isinstance(ts, dict):
        return None

    return _extract_last_two_points_daily(ts)


def _fetch_crypto(symbol: str) -> Optional[Tuple[float, float]]:
    """
    DIGITAL_CURRENCY_DAILY -> Time Series (Digital Currency Daily) -> 4a. close (USD)
    """
    data = _alpha_get(
        {
            "function": "DIGITAL_CURRENCY_DAILY",
            "symbol": symbol,
            "market": "USD",
        }
    )
    if "_error" in data:
        return None

    ts = data.get("Time Series (Digital Currency Daily)")
    if not isinstance(ts, dict) or not ts:
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
        print("[MARKET] ERROR: ALPHAVANTAGE_API_KEY not set (GitHub Secret).")
        # still write a file so the UI doesn't break
        payload = {"updated_at": "n/a", "items": []}
        (JSON_DIR / "market_snapshot_latest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return

    items: List[Dict[str, Any]] = []

    def add_item(name: str, sym: str, res: Optional[Tuple[float, float]]) -> None:
        if res is None:
            items.append({"name": name, "symbol": sym, "price": None, "change_pct": None})
        else:
            last_p, prev_p = res
            items.append(
                {"name": name, "symbol": sym, "price": last_p, "change_pct": _pct_change(last_p, prev_p)}
            )

    # NOTE: free tier is strict; keep spacing wide
    spacing_seconds = 15

    for i, s in enumerate(STOCKS):
        sym = s["symbol"]
        name = s["name"]
        print(f"[MARKET] Fetching stock {sym}...")
        try:
            res = _fetch_stock(sym)
        except Exception as e:
            print(f"[MARKET] ERROR stock {sym}: {e!r}")
            res = None
        add_item(name, sym, res)
        if i != len(STOCKS) - 1:
            time.sleep(spacing_seconds)

    for j, c in enumerate(CRYPTOS):
        sym = c["symbol"]
        name = c["name"]
        print(f"[MARKET] Fetching crypto {sym}...")
        try:
            res = _fetch_crypto(sym)
        except Exception as e:
            print(f"[MARKET] ERROR crypto {sym}: {e!r}")
            res = None
        add_item(name, sym, res)
        if j != len(CRYPTOS) - 1:
            time.sleep(spacing_seconds)

    updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    payload = {
        "updated_at": updated_at,
        "items": items,
    }

    out_path = JSON_DIR / "market_snapshot_latest.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[MARKET] Snapshot saved to {out_path}")


if __name__ == "__main__":
    build_market_snapshot()
