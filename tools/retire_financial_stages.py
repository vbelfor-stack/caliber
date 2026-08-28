"""Retire stored lifecycle stages for model-inapplicable issuers — Vic's ruling 1.

    "BK, C, JPM, USB get no stage, no score, no band — typed flag rows only. Existing
     stored stages for these names are retired with a typed reason, not left to be read."
                                                                    — Vic, 2026-08-28

RETIRE, NOT DELETE, AND NOT EDIT. A stage row for one of these names is not WRONG — it was
computed correctly from the inputs it had on 2026-08-17. It is INADMISSIBLE, which is a
different claim and needs its own representation:

  * DELETING destroys the record of what was believed when, which is the one thing the
    append-only discipline exists to preserve;
  * EDITING `computed_stage` forges a computation that never ran.

So the row is left byte-for-byte as written and stamped `retired_reason` + `retired_at`.
`core.stage_tolerance._latest_stage_row` and `core.stage_freshness` both filter
`retired_reason IS NULL`, which is what makes the label a GUARD rather than a note — a rule
recorded without naming its enforcement point is a belief.

THE NAMES ARE NOT HARDCODED. Membership is recomputed live from FMP sector/industry through
`fcf_model_applicability`, so this tool retires whatever the CLASS currently catches. Vic's
four are the answer today, not the definition.

WRITES ARE OPT-IN: without `--commit` this reports the exact expected delta and persists
nothing.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

from core.model_applicability import fcf_model_applicability

RETIREMENT_REASON = "model_inapplicable:financials (Vic ruling 1, 2026-08-28)"


def live_stage_rows(db: Path, ticker: str) -> List[Dict]:
    """Every stage row for `ticker`, with its retirement state. READ-ONLY.

    ★ THE `OperationalError` CATCH THAT USED TO BE HERE WAS A SILENT-DEGRADATION BUG, AND
    IT FIRED ON THE FIRST DRY RUN. `retired_reason` is an added column; against a database
    that has not been migrated yet, the SELECT raises and the old code returned `[]` — so
    the tool cheerfully reported "0 live rows" for four names holding eight, and an
    unsuspecting `--commit` would have retired nothing and reconciled to MATCH. A catch
    that turns "I could not read the table" into "the table is empty" is the exact shape of
    failure this project forbids.

    Now: the caller migrates first, and a query error RAISES. Loud failure beats silent
    degradation.
    """
    if not db.exists():
        return []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, ticker, computed_stage, rule_fired, run_at, retired_reason "
            "FROM lifecycle_stage WHERE ticker=? ORDER BY id",
            (ticker.upper(),)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(description="Retire stages for model-inapplicable issuers")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--db-path", dest="db_path", default=None)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    from adapters.fmp_adapter import _safe_get
    from store.models import _DEFAULT_DB
    import os
    key = os.environ.get("FMP_API_KEY")
    db = Path(args.db_path) if args.db_path is not None else _DEFAULT_DB

    # MIGRATE BEFORE READING. `retired_reason`/`retired_at` are added columns, and a DRY RUN
    # against an unmigrated database cannot see them — which is how the first run of this
    # tool reported "0 live rows" for four names holding eight. `init_db` is idempotent and
    # additive (`_ensure_columns` never redefines or backfills), so this is safe to run
    # against production before a read.
    if db.exists():
        from store.models import init_db
        init_db(db)

    print("")
    print("=" * 88)
    print(f"  RETIRE STAGES FOR MODEL-INAPPLICABLE ISSUERS — "
          f"{'COMMIT' if args.commit else 'DRY RUN'}")
    print(f"  db: {db}")
    print("=" * 88)
    print(f"\n  {'ticker':8s} {'class':13s} {'live rows':>10s} {'already ret':>12s}  detail")
    print("  " + "-" * 84)

    plan = {}
    total = 0
    for t in (x.upper() for x in args.tickers):
        p = (_safe_get(f"profile?symbol={t}", key, []) or [{}])[0]
        app = fcf_model_applicability(p.get("sector"), p.get("industry"))
        rows = live_stage_rows(db, t)
        live = [r for r in rows if r["retired_reason"] is None]
        ret = [r for r in rows if r["retired_reason"] is not None]
        if app.applicable:
            print(f"  {t:8s} {'APPLICABLE':13s} {len(live):10d} {len(ret):12d}  "
                  f"SKIPPED — the class does not catch this name; nothing retired")
            continue
        plan[t] = live
        total += len(live)
        print(f"  {t:8s} {str(app.class_name):13s} {len(live):10d} {len(ret):12d}  "
              f"ids {[r['id'] for r in live]} stages "
              f"{sorted({r['computed_stage'] for r in live})}")

    print("\n  " + "-" * 84)
    print(f"  EXPECTED DELTA: {total} lifecycle_stage row(s) stamped retired_reason + "
          f"retired_at.")
    print( "  NO ROW IS DELETED. NO ROW'S computed_stage, rule_fired OR run_at IS TOUCHED.")
    print( "  NO OTHER TABLE IS WRITTEN BY THIS TOOL.")
    print(f"  reason: {RETIREMENT_REASON}\n")

    if not args.commit:
        return

    from store.models import retire_lifecycle_stages
    print("  --- writing ---")
    actual = 0
    mismatches = 0
    for t, live in plan.items():
        n = retire_lifecycle_stages(t, RETIREMENT_REASON, db_path=db)
        actual += n
        bad = n != len(live)
        mismatches += bad
        print(f"  {t:8s} expected {len(live):3d}  stamped {n:3d}"
              f"{'   <-- MISMATCH' if bad else ''}")
    print(f"\n  RECONCILIATION: expected {total}, actual {actual} — "
          f"{'MATCH' if mismatches == 0 else f'{mismatches} MISMATCH(ES) — STOP'}")
    if mismatches:
        sys.exit(3)


if __name__ == "__main__":
    main()
