"""Market-cap anchor writer — Vic's ruling 3, 2026-08-28.

    "SKHY ANCHOR: full market cap basis, from the same endpoint as the (d) measurement
     (market-capitalization?symbol=SKHY, USD), pulled live at write time (~$1.14T basis).
     One basis, one endpoint, no float variants. Write it."   — Vic, 2026-08-28

FOUR CONSTRAINTS, ALL FROM THE RULING, ALL ENFORCED HERE:

  ONE ENDPOINT      `market-capitalization?symbol=X`, and nothing else is consulted. It is
                    also the only one of the four cap-publishing endpoints that carries its
                    own `date`, which is exactly what an anchor needs — `profile`, `quote`
                    and `key-metrics-ttm` all return a bare number.
  ONE BASIS         FULL market cap. Free-float is NOT computed, NOT stored and NOT offered.
                    Vic's own reference figure (~$909.30B) IS the free-float cap and the
                    full cap is ~$1.14T — a 25.6% gap — so "no float variants" is the
                    difference between two defensible numbers, not a rounding preference.
  LIVE AT WRITE     No cached value, no re-use of the (d) measurement. The ADR cap moves
                    intraday (measured: $1,141,659,621,195 at $160.83, then
                    $1,143,150,316,466 at $161.04 minutes later), so the row stores the
                    price and the timestamp it was taken at, or it is not reproducible.
  USD               Refuses outright if the endpoint's issuer is not USD-quoted. The whole
                    reason this anchor exists is that `key-metrics-ttm` silently served
                    SKHY a KRW figure; writing an anchor without checking would repeat the
                    defect one layer up.

WHY `fundamental_series` AND NOT `overrides`. Measured 2026-08-28: the `overrides` table is
read ONLY by `web/app.py` and by nothing on the pipeline path. A row there would be an
anchor that nothing reads — which is worse than no anchor, because it would look like the
question had been settled.

The row uses `period_type='ANCHOR'`, a value no existing consumer queries — the same
coexistence-by-construction rule the currency-block rows follow.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

from core.fundamental_series import SeriesPoint

METRIC_MARKET_CAP_ANCHOR = "market_cap_anchor"
PERIOD_ANCHOR = "ANCHOR"
BASIS_FULL_MARKET_CAP = "full_market_cap"
ENDPOINT = "market-capitalization"


def existing_anchors(db: Path, ticker: str) -> list:
    if not db.exists():
        return []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, ticker, period_end, value, unit, basis, method, superseded "
            "FROM fundamental_series WHERE ticker=? AND metric=? ORDER BY id",
            (ticker.upper(), METRIC_MARKET_CAP_ANCHOR)).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [dict(r) for r in rows]


def pull(ticker: str) -> dict:
    """LIVE pull. One endpoint. Raises rather than degrading."""
    from adapters.fmp_adapter import _get, _safe_get
    key = os.environ.get("FMP_API_KEY")
    if not key:
        raise RuntimeError("no FMP_API_KEY — refusing to write an anchor without a source")

    rows = _get(f"{ENDPOINT}?symbol={ticker}", key)
    row = rows[0] if isinstance(rows, list) and rows else {}
    cap, when = row.get("marketCap"), row.get("date")
    if cap is None or not when:
        raise RuntimeError(
            f"{ticker}: {ENDPOINT} returned no marketCap/date — refusing. "
            f"An anchor without its own timestamp is not reproducible. got={row!r}")

    # The quote currency, checked against the SAME defect this anchor exists to fix.
    prof = (_safe_get(f"profile?symbol={ticker}", key, []) or [{}])[0]
    ccy = str(prof.get("currency") or "").strip().upper()
    if ccy != "USD":
        raise RuntimeError(
            f"{ticker}: quote currency is {ccy or 'UNSTATED'}, not USD — REFUSING to write "
            f"an anchor. Ruled USD-only 2026-08-28; never converted.")

    return {"market_cap": float(cap), "date": str(when)[:10],
            "price": prof.get("price"), "currency": ccy,
            "shares_implied": (float(cap) / prof["price"]) if prof.get("price") else None}


def main() -> None:
    ap = argparse.ArgumentParser(description="Write the full-market-cap anchor (ruling 3)")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--db-path", dest="db_path", default=None)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    from store.models import _DEFAULT_DB
    db = Path(args.db_path) if args.db_path is not None else _DEFAULT_DB
    from datetime import datetime, timezone
    pulled_at = datetime.now(timezone.utc).isoformat()

    print("")
    print("=" * 88)
    print(f"  MARKET-CAP ANCHOR — {'COMMIT' if args.commit else 'DRY RUN'}")
    print(f"  db: {db}   endpoint: {ENDPOINT}?symbol=<T>   basis: {BASIS_FULL_MARKET_CAP}")
    print("=" * 88)

    points = []
    for t in (x.upper() for x in args.tickers):
        before = existing_anchors(db, t)
        print(f"\n  {t}")
        print(f"    ANCHOR ROWS BEFORE : {len(before)}"
              + (f" -> {before}" if before else " (none)"))
        d = pull(t)
        print(f"    endpoint           : {ENDPOINT}?symbol={t}")
        print(f"    field              : marketCap")
        print(f"    value              : {d['market_cap']:,.0f} {d['currency']}")
        print(f"    endpoint date      : {d['date']}")
        print(f"    pulled at (UTC)    : {pulled_at}")
        print(f"    quote price        : {d['price']}")
        print(f"    implied shares     : "
              f"{d['shares_implied']:,.0f}" if d["shares_implied"] else "    implied shares     : n/a")
        points.append(SeriesPoint(
            ticker=t, metric=METRIC_MARKET_CAP_ANCHOR,
            period_end=d["date"], period_type=PERIOD_ANCHOR,
            value=d["market_cap"], unit=d["currency"],
            basis=BASIS_FULL_MARKET_CAP, method=ENDPOINT,
            components={
                "endpoint": f"{ENDPOINT}?symbol={t}", "field": "marketCap",
                "quote_price": d["price"], "quote_currency": d["currency"],
                "implied_shares": d["shares_implied"],
                "pulled_at_utc": pulled_at,
                "basis": "FULL market cap — free float deliberately NOT used",
                "ruled_by": "Vic", "ruled_on": "2026-08-28",
            }))

    print(f"\n  " + "-" * 84)
    print(f"  EXPECTED DELTA: +{len(points)} row(s) in fundamental_series "
          f"(metric={METRIC_MARKET_CAP_ANCHOR}, period_type={PERIOD_ANCHOR}).")
    print( "  NO OTHER TABLE IS WRITTEN BY THIS TOOL.\n")

    if not args.commit:
        return

    from store.models import save_fundamental_series
    written, restated = save_fundamental_series(points, db_path=db)
    print(f"  --- writing ---")
    print(f"  expected +{len(points)}  wrote +{written}  restatements {restated} — "
          f"{'MATCH' if written == len(points) and restated == 0 else 'MISMATCH — STOP'}")
    for t in (x.upper() for x in args.tickers):
        after = existing_anchors(db, t)
        print(f"    {t} ANCHOR ROWS AFTER : {len(after)} -> "
              f"{[{k: r[k] for k in ('id', 'period_end', 'value', 'unit', 'basis')} for r in after]}")
    if written != len(points) or restated:
        sys.exit(3)


if __name__ == "__main__":
    main()
