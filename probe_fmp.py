"""
Phase 0 FMP probe — MU, GOOG, V
Calls live FMP API, records fixtures, prints schema notes.
Usage: cd caliber && python probe_fmp.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass

import requests

FMP_KEY = os.environ.get("FMP_API_KEY", "")
if not FMP_KEY:
    sys.exit("FMP_API_KEY not set — add it to .env")

BASE = "https://financialmodelingprep.com/api/v3"
TICKERS = ["MU", "GOOG", "V"]
OUT_DIR = Path(__file__).parent / "tests" / "fixtures" / "fmp"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS = {
    "profile":         "/profile/{t}",
    "ratios_ttm":      "/ratios-ttm/{t}",
    "key_metrics_ttm": "/key-metrics-ttm/{t}",
    "income":          "/income-statement/{t}?period=annual&limit=4",
    "income_q":        "/income-statement/{t}?period=quarter&limit=8",
    "balance":         "/balance-sheet-statement/{t}?period=annual&limit=4",
    "balance_q":       "/balance-sheet-statement/{t}?period=quarter&limit=8",
    "cashflow":        "/cash-flow-statement/{t}?period=annual&limit=4",
    "cashflow_q":      "/cash-flow-statement/{t}?period=quarter&limit=8",
    "analyst":         "/analyst-estimates/{t}?limit=5",
    "price_history":   "/historical-price-full/{t}?timeseries=365",
}


def _get(endpoint: str, ticker: str) -> Any:
    url = BASE + endpoint.format(t=ticker)
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}apikey={FMP_KEY}"
    r = requests.get(full_url, timeout=20)
    r.raise_for_status()
    return r.json()


def _show_keys(obj: Any, label: str, depth: int = 0) -> None:
    prefix = "  " * depth
    if isinstance(obj, dict):
        print(f"{prefix}{label}: {{dict, {len(obj)} keys}}")
        for k, v in list(obj.items())[:30]:
            val_str = repr(v)[:60] if not isinstance(v, (dict, list)) else ""
            print(f"{prefix}  {k}: {type(v).__name__} {val_str}")
    elif isinstance(obj, list):
        print(f"{prefix}{label}: [list, {len(obj)} items]")
        if obj:
            _show_keys(obj[0], "[0]", depth + 1)
    else:
        print(f"{prefix}{label}: {type(obj).__name__} = {repr(obj)[:60]}")


def probe_ticker(ticker: str) -> Dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"  Probing {ticker}")
    print(f"{'='*60}")

    fixture: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    for name, endpoint in ENDPOINTS.items():
        try:
            data = _get(endpoint, ticker)
            fixture[name] = data
            print(f"\n  [{name}]")
            _show_keys(data, name)
            # Small delay to be polite
            time.sleep(0.3)
        except Exception as e:
            errors[name] = str(e)
            print(f"\n  [{name}] ERROR: {e}")

    if errors:
        fixture["_errors"] = errors

    return fixture


def main() -> None:
    for ticker in TICKERS:
        fixture = probe_ticker(ticker)
        out = OUT_DIR / f"{ticker}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(fixture, f, indent=2, default=str)
        print(f"\n  => Fixture saved: {out}")
        time.sleep(1)  # rate-limit courtesy between tickers

    print("\n\nDone. Fixtures in tests/fixtures/fmp/")


if __name__ == "__main__":
    main()
