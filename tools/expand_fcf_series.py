"""L-4c — fundamental_series COVERAGE EXPANSION writer.

WHAT THIS IS. The one surface that persists an FCF family series for a ticker WITHOUT
running an evaluation. `fundamental_series` has only ever been written from inside
`batch/runner.run_single_ticker`, which means the only way to give a name FCF history was
to also write it an evaluation, a lifecycle_stage row, provenance and a synthesis. L-4c
needs the series for 24 names and is explicitly forbidden from touching any other table,
so the series build gets its own named entry point.

IT BUILDS THROUGH THE SAME CALLS THE PRODUCTION PATH USES — `fetch_fmp`, `fetch_edgar`,
`fetch_splits`, `build_split_report`, `build_fcf_series` — in the same order, so a series
written here cannot differ from one the batch path would have written. This module is the
probe (`tools/probe_fcf_series.py`) plus a destination; it deliberately adds no
computation of its own.

FAIL-CLOSED, AND THAT IS THE POINT OF THE ORDER. "Coverage expansion must not manufacture
FCF where the filings do not support it — a name that cannot be covered gets a TYPED
REASON, never a synthetic series." So:

  * the builder's own withholdings are honoured verbatim and NOTHING is written for that
    ticker — no partial series, no placeholder row, no zero;
  * a ticker whose fetch or build RAISES is recorded with the exception type as its typed
    reason and is skipped, never retried onto a different source;
  * FMP is the only price/split feed and EDGAR the only filings feed, exactly as
    production. There is no fallback and none may be added.

WRITES ARE OPT-IN. Without `--commit` this computes, reports the full expected delta and
persists NOTHING — that readout IS the expected-delta statement the standing rule requires
before a production write. `--commit` then writes from THE SAME IN-MEMORY BUILD that was
reported, so there is no fetch between the statement and the write for reality to drift
through, and the reconciliation at the end compares actual rows against that same build.

DESTINATION. `--db-path` resolves exactly as evaluate.py does (`db_path or _DEFAULT_DB`),
one resolved destination for every write this run makes. There is no hardcoded path here
and `save_fundamental_series` is the only writer reachable from this module.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

from adapters.edgar_adapter import fetch_edgar
from adapters.fmp_adapter import fetch_fmp, fetch_splits
from core.corporate_actions import build_split_report
from core.fundamental_series import (
    METRIC_FCF,
    PERIOD_FY,
    build_fcf_series,
)

# The step-4 (YOUNG supply block) gate reads FY FCF points and refuses below three
# (core/lifecycle.py, `only_N_fy_fcf_points`). Reported per ticker so this run's output
# says which names it actually made evaluable, rather than only how many rows it wrote.
STEP4_MIN_FY_FCF_POINTS = 3


class Build:
    """One ticker's built series, or the typed reason there isn't one."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.points: List[Any] = []
        self.basis: Optional[str] = None
        self.withheld: Dict[str, str] = {}
        self.diagnostics: Any = None
        self.reason: Optional[str] = None      # set IFF nothing may be written
        self.written: Optional[int] = None
        self.restated: Optional[int] = None
        # Live rows already in the DESTINATION for this ticker, read before the write.
        # The expected delta is only `len(points)` for a ticker the destination has never
        # seen; for one it has, the writer's append-never-overwrite contract means the
        # honest expectation is a RE-OBSERVATION of unknown size, and asserting +N there
        # would report correct idempotent behaviour as a mismatch.
        self.pre_existing: Optional[int] = None

    @property
    def is_new_ticker(self) -> bool:
        return self.pre_existing == 0

    @property
    def expected_delta(self) -> Optional[int]:
        """Rows this write should add, or None when it cannot be asserted ahead of time."""
        if not self.covered:
            return 0
        return len(self.points) if self.is_new_ticker else None

    @property
    def covered(self) -> bool:
        return self.reason is None

    @property
    def fy_fcf_usable(self) -> int:
        return sum(1 for p in self.points
                   if p.metric == METRIC_FCF and p.period_type == PERIOD_FY
                   and p.value is not None)

    @property
    def meets_step4_gate(self) -> bool:
        return self.fy_fcf_usable >= STEP4_MIN_FY_FCF_POINTS


def build_one(ticker: str) -> Build:
    """Fetch and build. Never writes. Never raises — a failure becomes a typed reason."""
    b = Build(ticker)
    try:
        yf = fetch_fmp(ticker)
        edgar = fetch_edgar(ticker)
        splits = fetch_splits(ticker)
        # `splits is None` means UNKNOWN and must never be read as "never split" — the
        # restatement refuses and the truncated basis stands. Passed through as-is.
        report = (build_split_report(ticker, splits, edgar.financials)
                  if splits is not None else None)
        result = build_fcf_series(ticker, edgar, yf.price_history, report)
    except Exception as e:                              # noqa: BLE001
        # LOUD FAILURE BEATS SILENT DEGRADATION. The exception TYPE is the typed reason;
        # this name is reported uncovered and no row is written for it.
        b.reason = f"build_failed:{type(e).__name__}: {e}"
        return b

    b.basis = result.basis
    b.withheld = dict(result.withheld or {})
    b.diagnostics = result.diagnostics
    b.points = list(result.points)

    if b.withheld:
        # The builder itself refused. Honour it verbatim — writing the metrics that DID
        # compute would be a partial series wearing the same shape as a complete one.
        b.reason = "withheld:" + ";".join(f"{k}={v}" for k, v in sorted(b.withheld.items()))
    elif not b.points:
        b.reason = "no_points_emitted"
    return b


def count_existing(destination: Path, ticker: str) -> int:
    """Live (non-superseded) rows already stored for `ticker`. READ-ONLY.

    Opened read-only against the resolved destination so that merely PLANNING a write
    cannot create the database it is planning to write to — a dry run must leave no trace,
    including no empty file.
    """
    import sqlite3
    if not Path(destination).exists():
        return 0
    conn = sqlite3.connect(f"file:{destination}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM fundamental_series WHERE ticker=? AND superseded=0",
            (ticker.upper(),),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return 0                                 # table absent — nothing stored yet
    finally:
        conn.close()


def render_plan(builds: List[Build], destination: Path, committing: bool) -> str:
    lines = [
        "",
        "=" * 78,
        f"  L-4c FCF-SERIES COVERAGE EXPANSION — {'COMMIT' if committing else 'DRY RUN'}",
        f"  destination: {destination}",
        "=" * 78,
        "",
        f"  {'ticker':8s} {'built':>6s} {'stored':>7s} {'expect':>7s} {'FY fcf':>7s} "
        f"{'gate':>5s}  basis / typed reason",
        "  " + "-" * 88,
    ]
    for b in builds:
        pre = "-" if b.pre_existing is None else str(b.pre_existing)
        if not b.covered:
            lines.append(f"  {b.ticker:8s} {'0':>6s} {pre:>7s} {'+0':>7s} {'-':>7s} "
                         f"{'-':>5s}  UNCOVERED {b.reason}")
        else:
            exp = "re-obs" if b.expected_delta is None else f"+{b.expected_delta}"
            gate = "PASS" if b.meets_step4_gate else "under"
            lines.append(f"  {b.ticker:8s} {len(b.points):6d} {pre:>7s} {exp:>7s} "
                         f"{b.fy_fcf_usable:7d} {gate:>5s}  {b.basis}")
    cov = [b for b in builds if b.covered]
    unc = [b for b in builds if not b.covered]
    new = [b for b in cov if b.is_new_ticker]
    reobs = [b for b in cov if not b.is_new_ticker]
    lines += [
        "  " + "-" * 88,
        f"  EXPECTED DELTA: +{sum(len(b.points) for b in new)} rows in fundamental_series "
        f"across {len(new)} NEW ticker(s).",
        f"  RE-OBSERVED (already stored; append-only, delta not assertable in advance): "
        f"{len(reobs)} — {', '.join(b.ticker for b in reobs) or 'none'}",
        f"  UNCOVERED (fail-closed, zero rows, typed reason recorded): {len(unc)} — "
        f"{', '.join(b.ticker for b in unc) or 'none'}",
        f"  step-4 gate (>= {STEP4_MIN_FY_FCF_POINTS} FY fcf points): "
        f"{sum(1 for b in cov if b.meets_step4_gate)} of {len(builds)} name(s) would pass.",
        "  NO OTHER TABLE IS WRITTEN BY THIS TOOL.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="L-4c fundamental_series coverage expansion (writes only with --commit)")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--db-path", dest="db_path", default=None,
                    help="Destination for every write this run makes (fundamental_series "
                         "only). Defaults to production caliber.db.")
    ap.add_argument("--commit", action="store_true",
                    help="Actually persist. Without it this is a read-only measurement.")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()

    from store.models import _DEFAULT_DB
    destination = Path(args.db_path) if args.db_path is not None else _DEFAULT_DB

    builds = [build_one(t.upper()) for t in args.tickers]
    for b in builds:
        b.pre_existing = count_existing(destination, b.ticker)

    # The expected delta is STATED BEFORE THE WRITE, from the same build the write uses.
    print(render_plan(builds, destination, args.commit))

    if args.commit:
        from store.models import save_fundamental_series
        print("  --- writing ---")
        mismatches = 0
        for b in builds:
            if not b.covered:
                print(f"  {b.ticker:8s} SKIPPED (fail-closed): {b.reason}")
                continue
            written, restated = save_fundamental_series(b.points, db_path=destination)
            b.written, b.restated = written, restated
            exp = b.expected_delta
            # A NEW ticker is held to the exact count. A ticker already stored is a
            # re-observation, where 0 new rows is the CORRECT idempotent outcome — there
            # the reportable event is a RESTATEMENT, not a row count.
            bad = (written != exp) if exp is not None else (restated != 0)
            mismatches += bool(bad)
            exp_s = f"+{exp}" if exp is not None else "re-obs"
            print(f"  {b.ticker:8s} expected {exp_s:>7s}  wrote +{written:3d}  "
                  f"restatements {restated}{'   <-- MISMATCH' if bad else ''}")
        act = sum(b.written or 0 for b in builds if b.covered)
        res = sum(b.restated or 0 for b in builds if b.covered)
        exp_total = sum(len(b.points) for b in builds if b.covered and b.is_new_ticker)
        print(f"\n  RECONCILIATION: expected +{exp_total} (new tickers), actual +{act}, "
              f"restatements {res} — "
              f"{'MATCH' if mismatches == 0 else f'{mismatches} MISMATCH(ES) — STOP'}")
        if mismatches:
            sys.exit(3)

    if args.json_out:
        payload = [{
            "ticker": b.ticker, "covered": b.covered, "reason": b.reason,
            "basis": b.basis, "withheld": b.withheld, "diagnostics": b.diagnostics,
            "rows": len(b.points), "fy_fcf_usable": b.fy_fcf_usable,
            "meets_step4_gate": b.meets_step4_gate,
            "pre_existing": b.pre_existing, "expected_delta": b.expected_delta,
            "written": b.written, "restated": b.restated,
        } for b in builds]
        Path(args.json_out).write_text(json.dumps(payload, indent=2, default=str))
        print(f"\n  wrote {args.json_out}")


if __name__ == "__main__":
    main()
