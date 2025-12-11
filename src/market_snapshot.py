from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import os
import json
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = BASE_DIR / "reports" / "json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

# Puoi lasciare la chiave hard-coded oppure usare la variabile d'ambiente ALPHA_VANTAGE_KEY
ALPHA_API_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "72K5S53NMAU4X0HM")

SYMBOLS = [
    ("GOOGL", "Google"),
    ("TSLA", "Tesla"),
    ("AAPL", "Apple"),
    ("NVDA", "NVIDIA"),
    ("META", "Meta"),
    ("MSFT", "Microsoft"),
    ("AMZN", "Amazon"),
    ("BTC-USD", "Bitcoin"),
    ("ETH-USD", "Ethereum"),
]


def _fetch_quote(symbol: str) -> tuple[float | None, float | None]:
    """
    Ritorna (prezzo, variazione_percentuale) usando Alpha Vantage GLOBAL_QUOTE.
    Se qualcosa va storto => (None, None).
    """
    url = (
        "https://www.alphavantage.co/query"
        f"?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_API_KEY}"
    )
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        data = r.json().get("Global Quote", {})
        price_str = data.get("05. price")
        prev_str = data.get("08. previous close")
        if not price_str or not prev_str:
            return None, None

        price = float(price_str)
        prev = float(prev_str)
        pct = ((price - prev) / prev * 100.0) if prev else 0.0
        return price, pct
    except Exception as e:
        print(f"[MARKET] Error fetching {symbol}: {e!r}")
        return None, None


def build_snapshot() -> Path:
    items = []
    for sym, name in SYMBOLS:
        price, pct = _fetch_quote(sym)
        items.append(
            {
                "symbol": sym,
                "name": name,
                "price": price,
                "change_pct": pct,
            }
        )

    # Timestamp (UTC) – il builder lo mostra così com'è
    now_utc = datetime.now(timezone.utc)
    updated_at = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    payload = {
        "updated_at": updated_at,
        "items": items,
    }

    filename = f"market_snapshot_{now_utc.strftime('%Y-%m-%d_%H-%M')}.json"
    out_path = JSON_DIR / filename
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[MARKET] Snapshot saved to {out_path}")
    return out_path


if __name__ == "__main__":
    build_snapshot()
