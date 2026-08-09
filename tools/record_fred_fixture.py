"""Record the FRED DGS10 fixture, in the shape adapters/fred_adapter reads back.

    python -m tools.record_fred_fixture

Companion to tools/record_fmp_fixture.py and tools/record_edgar_fixture.py. It records
adapters.fred_adapter.fetch_payload verbatim — the same function the live path uses —
so the recorded shape cannot drift from what production requests.

Re-recording moves the golden-ticker regression baseline (the 10Y is an input to every
valuation score), so it is a deliberate manual step. The existing file is backed up to
DGS10.json.bak (gitignored).

Requires FRED_API_KEY. Without it this fails LOUD rather than writing a rate-less
fixture — a fixture that records no rate is what made offline runs rate-blind before
D-2, and under the mandatory-rate ruling it now makes every offline eval refuse.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from adapters.fred_adapter import fetch_payload, fetch_fred

FIXTURE_DIR = Path("tests/fixtures/fred")


def record() -> Path:
    payload = fetch_payload()

    parsed = [o for o in payload["observations"] if o.get("value") not in (".", None)]
    if not parsed:
        raise SystemExit(
            "[FRED] refusing to write a fixture with no usable observation — "
            "every value came back as '.' (non-trading days)."
        )

    path = FIXTURE_DIR / "DGS10.json"
    if path.exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    # Load it straight back through the adapter: a fixture that cannot rebuild a
    # FredData is worse than no fixture, and better to learn that here than in a test.
    data = fetch_fred(fixture_path=path)
    if data.rate_10y.is_missing():
        raise SystemExit(f"[FRED] wrote {path} but it rebuilt as MISSING — aborting.")
    print(
        f"DGS10: rate={data.rate_10y.value}%  as_of={data.rate_10y.as_of}  "
        f"conf={data.rate_10y.confidence}  ({len(payload['observations'])} obs) -> {path}"
    )
    return path


def main(argv: list) -> int:
    if argv:
        print(__doc__)
        return 2
    record()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
