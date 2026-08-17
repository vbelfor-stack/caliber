"""Phase L dark run — classify lifecycle stage for a set of tickers and report.

    python -m tools.probe_lifecycle MU GOOG V NOW WU JPM BK USB C \
        --db-path /tmp/l_dark.db

DARK. Nothing here touches a score, a confidence label, a lens or an E(R). It reads
fundamentals, classifies, prints the stage table with every per-point assertion, and
persists to a NAMED database.

THE DESTINATION IS ALWAYS NAMED. This is a degraded run by construction (fixture inputs,
no synthesis), so `--db-path` is mandatory — the same rule that keeps a measurement route
from writing into production as a side effect of merely being run.

DIVIDENDS ARE FETCHED LIVE, DELIBERATELY. `dividends` joined fetch_payload in this phase,
so the recorded fixtures — which Vic ruled are NOT to be re-recorded — predate the key and
return None (UNKNOWN) offline. Under R1 that would assert the capital-returns leg absent
for every ticker and, under R7's strict AND-precedence, make DECLINE unreachable in the
dark run: the run would "pass" while measuring nothing. Fetching the one missing input live
is the honest fix, and the source of every leg is stamped in the readout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from adapters.edgar_adapter import fetch_edgar, instant_series
from adapters.fmp_adapter import fetch_dividends, fetch_fmp
from core.lens_select import select_lens
from core.lifecycle import build_legs, classify, lens_compatibility_flags
from store.models import init_db, save_lifecycle_stage

FMP_FIXTURES = Path("tests/fixtures/fmp")
EDGAR_FIXTURES = Path("tests/fixtures/edgar")


def _series_from_db(db: Path, ticker: str, metric: str
                    ) -> Optional[List[Tuple[str, Optional[float]]]]:
    """FY points for one metric from an EXISTING fundamental_series table, oldest first.

    Returns None — UNKNOWN, hence asserted-absent — when the table or the ticker's rows do
    not exist. An empty list would claim "this issuer has no FCF history", which is a
    different and unearned statement.
    """
    import sqlite3
    if not db.exists():
        return None
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT period_end, value FROM fundamental_series "
            "WHERE ticker=? AND metric=? AND period_type='FY' AND superseded=0 "
            "ORDER BY period_end",
            (ticker.upper(), metric),
        ).fetchall()
    except sqlite3.OperationalError:
        return None                      # table absent — UNKNOWN, not empty
    finally:
        conn.close()
    if not rows:
        return None
    return [(r["period_end"], r["value"]) for r in rows]


def run(tickers: List[str], db_path: Path, series_db: Path,
        live_dividends: bool = True) -> Dict[str, dict]:
    init_db(db_path)
    out: Dict[str, dict] = {}

    for t in tickers:
        fmp_fix = FMP_FIXTURES / f"{t}.json"
        payload = json.loads(fmp_fix.read_text(encoding="utf-8"))
        income_annual = payload.get("income_annual") or []

        yf = fetch_fmp(t, fixture_path=fmp_fix)
        lens = select_lens(yf.sector, yf.industry, yf.sic)

        # shares series (buyback leg) — EDGAR, the same call the own-history anchor makes
        edgar_fix = EDGAR_FIXTURES / f"{t}.json"
        shares: Optional[List[Tuple[str, float]]] = None
        if edgar_fix.exists():
            edgar = fetch_edgar(t, fixture_path=edgar_fix)
            pts = [(r.period_end, r.value)
                   for r in instant_series(edgar.financials, "shares_outstanding")
                   if r.period_end and r.value]
            shares = sorted(pts) or None

        # dividends — live by default; see the module docstring for why
        divs = (fetch_dividends(t) if live_dividends
                else fetch_dividends(t, fixture_path=fmp_fix))

        legs = build_legs(
            t, income_annual, lens,
            dividends=divs,
            shares_series=shares,
            fcf_fy=_series_from_db(series_db, t, "fcf"),
            sales_to_capital_fy=_series_from_db(series_db, t, "sales_to_capital"),
        )
        result = classify(t, legs, lens)
        result.flags.extend(lens_compatibility_flags(result.stage, lens))
        stage_id, transition_id = save_lifecycle_stage(result, db_path=db_path)

        out[t] = {
            "stage": result.stage, "rule": result.rule_fired, "lens": lens,
            "flags": result.flags, "absent": result.absent_legs,
            "stage_id": stage_id, "transition_id": transition_id,
            "assertions": [a.as_dict() for a in result.assertions],
            "dividend_source": ("live" if live_dividends else "fixture"),
            "n_dividends": (None if divs is None else len(divs)),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase L lifecycle classifier — DARK run")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--db-path", required=True, type=Path,
                    help="REQUIRED. Degraded run — the destination is always named.")
    ap.add_argument("--series-db", type=Path, default=Path("caliber.db"),
                    help="Read-only source for fundamental_series (default caliber.db)")
    ap.add_argument("--fixture-dividends", action="store_true",
                    help="Read dividends from the fixture instead of live (they predate "
                         "the payload key, so this asserts them absent)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    res = run([t.upper() for t in args.tickers], args.db_path, args.series_db,
              live_dividends=not args.fixture_dividends)

    print(f"\n{'='*78}\nPHASE L — DARK CLASSIFICATION\n{'='*78}")
    print(f"{'TICKER':7s} {'LENS':11s} {'STAGE':9s} {'RULE':34s} INCOMPLETE")
    print("-" * 78)
    for t, r in res.items():
        inc = ",".join(r["absent"]) if r["absent"] else "-"
        print(f"{t:7s} {r['lens']:11s} {r['stage']:9s} {r['rule']:34s} {inc}")

    print(f"\n{'='*78}\nPER-POINT ASSERTIONS\n{'='*78}")
    for t, r in res.items():
        print(f"\n{t}  [{r['lens']} lens] -> {r['stage']}  (div source: "
              f"{r['dividend_source']}, records: {r['n_dividends']})")
        for a in r["assertions"]:
            mark = {"satisfied": "OK ", "not_satisfied": "no ", "absent": "ABS"}[a["outcome"]]
            print(f"    {mark} {a['rule']:16s} {a['leg']:22s} {a['detail']}")
        if r["flags"]:
            print(f"    FLAGS: {', '.join(r['flags'])}")

    if args.json:
        args.json.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    sys.exit(main())
