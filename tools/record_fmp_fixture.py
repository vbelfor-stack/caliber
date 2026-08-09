"""Record an FMP fixture for one ticker, in the shape adapters/fmp_adapter reads back.

    python -m tools.record_fmp_fixture NOW WU

Companion to tools/record_edgar_fixture.py. It records adapters.fmp_adapter.fetch_payload
verbatim — the same function the live path uses — so the endpoint set cannot drift
between what is recorded and what production requests.

Re-recording moves the golden-ticker regression baseline, so it is a deliberate manual
step. Existing files are backed up to <name>.json.bak (gitignored).
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

from adapters.fmp_adapter import fetch_payload, fetch_fmp

FIXTURE_DIR = Path("tests/fixtures/fmp")


def record(ticker: str) -> Path:
    payload = fetch_payload(ticker)

    path = FIXTURE_DIR / f"{ticker}.json"
    if path.exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    # Load it straight back through the adapter: a fixture that cannot rebuild a
    # TickerData is worse than no fixture, and better to learn that here than in a test.
    data = fetch_fmp(ticker, fixture_path=path)
    counts = {k: len(v) if isinstance(v, list) else 1 for k, v in payload.items()}
    print(f"{ticker}: {data.name} — rebuilt OK, price={data.current_price.value} "
          f"-> {path}")
    print(f"    rows: {counts}")
    return path


if __name__ == "__main__":
    tickers = sys.argv[1:]
    if not tickers:
        raise SystemExit("usage: python -m tools.record_fmp_fixture TICKER [TICKER ...]")
    for t in tickers:
        record(t.upper())
        time.sleep(0.5)
