"""USD-only FMP ingest + typed block rows — Vic's rulings 1 and 2, 2026-08-28.

WHAT THIS IS. The writer for the 2026-08-28 order. It fetches an issuer's FMP statements,
applies two gates in a FIXED ORDER, and persists what survives plus a typed row for what did
not. It writes `fundamental_series` and NO OTHER TABLE, exactly as `tools/expand_fcf_series`
does; the difference is the basis and the gates.

    GATE 1 — THE FCF-MODEL CLASS (ruling 1). Banks, insurers and diversified financials
             are model-inapplicable. Runs FIRST, and the ordering is the point: a bank's
             currency split is a true fact that does not matter, and reporting it would
             suggest that fixing the currency would help. It would not.

    GATE 2 — THE REPORTING CURRENCY (ruling 2). USD only. Non-USD periods are blocked with
             a typed reason and NEVER converted.

★ THE USD SET IS EMPTY TODAY, AND THIS TOOL IS DELIBERATELY NOT BUILT TO WRITE ONE.
Measured live 2026-08-28 across all six FMP statement endpoints: SKHY serves 129 periods and
**0 of them are USD**. SKHY is the universe's only non-USD reporter, so there is no name
anywhere for which a numeric FMP-basis series could be built today.

Writing that builder anyway would put a production write path into the tree that nothing
exercises — and it would have to clear two traps recorded BEFORE the build, neither of which
could be tested against real data: FMP files capex NEGATIVE while `build_fcf_series` computes
`ocf - capex` on EDGAR's positive-outflow convention (reusing that expression on FMP input
ADDS capex — the debt/equity ratio-vs-percent unit defect in a new costume, and that one ran
eight days behind 654 green tests), and the R2 boundary population would have to be
re-measured on FMP basis rather than assumed to carry over. Those are not things to get right
blind.

So instead: **if a USD period is ever served, this tool REFUSES LOUDLY and writes nothing
for that ticker.** The day the case becomes real it stops and reports, rather than silently
writing down an unbuilt path. Building it is a separate order and the order document says so.

WRITES ARE OPT-IN. Without `--commit` this computes, prints the full expected delta and
persists NOTHING — that readout IS the expected-delta statement the standing rule requires.
`--commit` writes from THE SAME IN-MEMORY BUILD that was reported, so no fetch sits between
the statement and the write for reality to drift through.

DESTINATION resolves exactly as evaluate.py does (`db_path or _DEFAULT_DB`).
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

from core.fundamental_series import BASIS_NOT_APPLICABLE, SeriesPoint
from core.model_applicability import CLASS_RULED_ON, fcf_model_applicability
from core.reporting_currency import split_by_currency

# ── The block-row shape ──────────────────────────────────────────────────────
#
# ★ THIS SHAPE IS CONSTRAINED BY MEASUREMENT, NOT BY TASTE, AND THE TWO OBVIOUS DESIGNS ARE
# BOTH RULED OUT. `evaluate._fy_series_from_db` selects
# `WHERE ticker=? AND metric=? AND period_type='FY' AND superseded=0` and DOES NOT filter
# `excluded` — verified empirically against a scratch db, where an excluded row came back
# and a NULL-valued row came back as `(period_end, None)`.
#
#   Writing blocks as metric='fcf'/period_type='FY' would flip the classifier's `fcf_fy`
#   from None (UNKNOWN — "we hold no series") to a populated list, changing its absent-leg
#   reason from `no_fcf_series` to `only_0_fy_fcf_points` — a claim that the ISSUER has no
#   FY FCF points when in fact WE blocked them. That is the L-4d typed-reason mislabel in a
#   new costume.
#
#   Filtering `_fy_series_from_db` to `excluded=0` to fix that is WORSE: 30 FY `fcf` rows
#   across 8 tickers (BE, BK, C, IONQ, LITE, MU, QBTS, RKLB) carry excluded=1 because
#   EXCL_NEGATIVE_FCF marks every negative point — and those negative points ARE the R2
#   all-negative-last-3 signal. Filtering would silently delete it on four names.
#
# So block rows take a metric and a period_type that NO existing consumer queries.
# Coexistence by construction: nothing downstream can pick them up by accident.
METRIC_INGEST_BLOCK = "ingest_block"
METRIC_MODEL_APPLICABILITY = "model_applicability"
PERIOD_BLOCK_FY = "BLOCK_FY"          # deliberately != "FY"
PERIOD_BLOCK_Q = "BLOCK_Q"            # deliberately != "TTM_Q"
PERIOD_FLAG = "FLAG"

# The six statement endpoints, and the granularity each block row inherits.
STATEMENTS = [
    ("income", "income-statement", "annual", PERIOD_BLOCK_FY),
    ("income", "income-statement", "quarter", PERIOD_BLOCK_Q),
    ("balance_sheet", "balance-sheet-statement", "annual", PERIOD_BLOCK_FY),
    ("balance_sheet", "balance-sheet-statement", "quarter", PERIOD_BLOCK_Q),
    ("cash_flow", "cash-flow-statement", "annual", PERIOD_BLOCK_FY),
    ("cash_flow", "cash-flow-statement", "quarter", PERIOD_BLOCK_Q),
]

_ANNUAL_LIMIT = 20
_QUARTER_LIMIT = 24


class Result:
    """One ticker's outcome — the rows to write, or the typed reason there are none."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.sector: Optional[str] = None
        self.industry: Optional[str] = None
        self.applicability: Any = None
        self.points: List[SeriesPoint] = []
        self.currency_summary: Dict[str, Dict[str, int]] = {}
        self.usd_periods = 0
        self.blocked_periods = 0
        self.reason: Optional[str] = None       # set IFF the run REFUSED for this ticker
        self.written: Optional[int] = None
        self.restated: Optional[int] = None
        self.pre_existing_blocks: Optional[int] = None

    @property
    def expected_delta(self) -> int:
        return len(self.points)


def _fetch(endpoint: str, key: str) -> List[Dict]:
    from adapters.fmp_adapter import _safe_get
    rows = _safe_get(endpoint, key, [])
    return rows if isinstance(rows, list) else []


def build_one(ticker: str) -> Result:
    """Fetch, gate, and assemble the rows. NEVER WRITES. Never raises."""
    import os
    r = Result(ticker)
    key = os.environ.get("FMP_API_KEY")
    if not key:
        r.reason = "no FMP_API_KEY — refusing rather than reporting an empty universe"
        return r

    try:
        profile = _fetch(f"profile?symbol={ticker}", key)
        p = profile[0] if profile else {}
        r.sector, r.industry = p.get("sector"), p.get("industry")

        # ── GATE 1 — THE CLASS. Runs before anything is measured about the data. ──
        r.applicability = fcf_model_applicability(r.sector, r.industry)
        if not r.applicability.applicable:
            r.points = [SeriesPoint(
                ticker=ticker,
                metric=METRIC_MODEL_APPLICABILITY,
                period_end=CLASS_RULED_ON,
                period_type=PERIOD_FLAG,
                value=None,
                unit=None,
                basis=BASIS_NOT_APPLICABLE,
                excluded=True,
                exclusion_reason=r.applicability.typed_reason,
                components={
                    "class": r.applicability.class_name,
                    "fmp_sector": r.sector,
                    "fmp_industry": r.industry,
                    "detail": r.applicability.detail,
                    "ruled_by": "Vic",
                    "ruled_on": CLASS_RULED_ON,
                    "enforcement_points": [
                        "core.fundamental_series.build_fcf_series (refuses first)",
                        "core.valuation_anchors.own_history_fcf_yields (panel anchor)",
                    ],
                },
            )]
            # NO CURRENCY WORK FOR A CLASS-BLOCKED NAME. Its currency split is a true fact
            # that does not matter, and recording it would imply that fixing the currency
            # would help. It would not — see the gate ordering in the module docstring.
            return r

        # ── GATE 2 — THE REPORTING CURRENCY. USD only, never converted. ──
        for stmt, endpoint, period, ptype in STATEMENTS:
            limit = _ANNUAL_LIMIT if period == "annual" else _QUARTER_LIMIT
            rows = _fetch(f"{endpoint}?symbol={ticker}&period={period}&limit={limit}", key)
            split = split_by_currency(rows)
            r.currency_summary[f"{stmt}_{period}"] = split.currencies
            r.usd_periods += len(split.usd)

            for row, typed_reason, ccy in split.blocked:
                r.points.append(SeriesPoint(
                    ticker=ticker,
                    metric=f"{METRIC_INGEST_BLOCK}:{stmt}",
                    period_end=str(row.get("date") or row.get("fiscalYear") or "unknown"),
                    period_type=ptype,
                    value=None,
                    unit=None,
                    basis=BASIS_NOT_APPLICABLE,
                    excluded=True,
                    exclusion_reason=typed_reason,
                    components={
                        # THE EVIDENCE, NOT JUST THE CODE. A reason a later reader cannot
                        # check is the thing L-4d existed to remove. Re-fetching to find out
                        # would measure a different day.
                        "reported_currency": ccy,
                        "statement": stmt,
                        "endpoint": f"{endpoint}?symbol={ticker}&period={period}",
                        "fiscal_year": row.get("fiscalYear"),
                        "period": row.get("period"),
                        "filing_date": row.get("filingDate"),
                        "ruled_by": "Vic",
                        "ruled_on": "2026-08-28",
                        "rule": "USD only — non-USD periods are blocked, NEVER converted",
                    },
                ))
                r.blocked_periods += 1

        # ── THE REFUSAL. See the module docstring. ──
        if r.usd_periods:
            r.reason = (
                f"REFUSED — {r.usd_periods} natively-USD period(s) served, and the "
                f"FMP-basis NUMERIC series builder IS NOT BUILT. Writing them would need "
                f"the capex SIGN conversion (FMP files capex negative; build_fcf_series "
                f"computes ocf - capex on EDGAR's positive-outflow convention, so reusing "
                f"it ADDS capex) and a re-measurement of the R2 boundary population on FMP "
                f"basis. Both are ruled into a SEPARATE order. Nothing written for "
                f"{ticker}."
            )
            r.points = []
            return r

    except Exception as e:                                  # noqa: BLE001
        # LOUD FAILURE BEATS SILENT DEGRADATION — the exception TYPE is the typed reason.
        r.reason = f"build_failed:{type(e).__name__}: {e}"
        r.points = []
    return r


def count_existing_blocks(destination: Path, ticker: str) -> int:
    """Live block/flag rows already stored for `ticker`. READ-ONLY.

    Opened read-only so that merely PLANNING a write cannot create the database it is
    planning to write to — a dry run must leave no trace, including no empty file.
    """
    import sqlite3
    if not Path(destination).exists():
        return 0
    conn = sqlite3.connect(f"file:{destination}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM fundamental_series "
            "WHERE ticker=? AND superseded=0 AND period_type IN (?,?,?)",
            (ticker.upper(), PERIOD_BLOCK_FY, PERIOD_BLOCK_Q, PERIOD_FLAG),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def render_plan(results: List[Result], destination: Path, committing: bool) -> str:
    lines = [
        "",
        "=" * 84,
        f"  USD-ONLY FMP INGEST + TYPED BLOCK ROWS — {'COMMIT' if committing else 'DRY RUN'}",
        f"  destination: {destination}",
        "=" * 84,
        "",
        f"  {'ticker':8s} {'class':14s} {'USD':>4s} {'blocked':>8s} {'stored':>7s} "
        f"{'expect':>7s}  outcome",
        "  " + "-" * 82,
    ]
    for r in results:
        cls = "-" if r.applicability is None or r.applicability.applicable \
            else r.applicability.class_name
        pre = "-" if r.pre_existing_blocks is None else str(r.pre_existing_blocks)
        if r.reason:
            outcome = f"REFUSED {r.reason[:60]}"
        elif not r.applicability.applicable:
            outcome = "model-inapplicable -> 1 typed FLAG row, no numeric ingest"
        else:
            outcome = f"{r.blocked_periods} period(s) blocked, 0 ingested"
        lines.append(f"  {r.ticker:8s} {cls:14s} {r.usd_periods:4d} "
                     f"{r.blocked_periods:8d} {pre:>7s} {'+'+str(r.expected_delta):>7s}  "
                     f"{outcome}")
    for r in results:
        if r.currency_summary:
            lines.append("")
            lines.append(f"  {r.ticker} reporting-currency split, per endpoint:")
            for ep, ccy in r.currency_summary.items():
                lines.append(f"      {ep:26s} {ccy}")
    total = sum(r.expected_delta for r in results)
    lines += [
        "",
        "  " + "-" * 82,
        f"  EXPECTED DELTA: +{total} rows in fundamental_series.",
        f"     block rows (non-USD periods): "
        f"+{sum(r.blocked_periods for r in results)}",
        f"     class FLAG rows: "
        f"+{sum(1 for r in results if r.applicability is not None and not r.applicability.applicable and not r.reason)}",
        f"     NUMERIC series rows: +0  (the USD set is empty; see the module docstring)",
        "  NO OTHER TABLE IS WRITTEN BY THIS TOOL.",
        "  Every row written is excluded=1 with a typed exclusion_reason, and carries a",
        "  metric/period_type that no existing consumer queries.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="USD-only FMP ingest + typed block rows (writes only with --commit)")
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

    results = [build_one(t.upper()) for t in args.tickers]
    for r in results:
        r.pre_existing_blocks = count_existing_blocks(destination, r.ticker)

    print(render_plan(results, destination, args.commit))

    exit_code = 0
    if args.commit:
        from store.models import save_fundamental_series
        print("  --- writing ---")
        mismatches = 0
        for r in results:
            if r.reason:
                print(f"  {r.ticker:8s} SKIPPED: {r.reason}")
                continue
            written, restated = save_fundamental_series(r.points, db_path=destination)
            r.written, r.restated = written, restated
            # A ticker the destination has never seen is held to the exact count. One it
            # HAS seen is a re-observation, where 0 new rows is the CORRECT idempotent
            # outcome and the reportable event is a RESTATEMENT, not a row count.
            first_time = (r.pre_existing_blocks == 0)
            bad = (written != r.expected_delta) if first_time else (restated != 0)
            mismatches += bool(bad)
            exp = f"+{r.expected_delta}" if first_time else "re-obs"
            print(f"  {r.ticker:8s} expected {exp:>7s}  wrote +{written:3d}  "
                  f"restatements {restated}{'   <-- MISMATCH' if bad else ''}")
        act = sum(r.written or 0 for r in results if not r.reason)
        res = sum(r.restated or 0 for r in results if not r.reason)
        exp_total = sum(r.expected_delta for r in results
                        if not r.reason and r.pre_existing_blocks == 0)
        print(f"\n  RECONCILIATION: expected +{exp_total} (first-time tickers), "
              f"actual +{act}, restatements {res} — "
              f"{'MATCH' if mismatches == 0 else f'{mismatches} MISMATCH(ES) — STOP'}")
        if mismatches:
            exit_code = 3

    if any(r.reason and r.reason.startswith("REFUSED") for r in results):
        exit_code = exit_code or 4

    if args.json_out:
        Path(args.json_out).write_text(json.dumps([{
            "ticker": r.ticker, "sector": r.sector, "industry": r.industry,
            "applicable": None if r.applicability is None else r.applicability.applicable,
            "class": None if r.applicability is None else r.applicability.class_name,
            "usd_periods": r.usd_periods, "blocked_periods": r.blocked_periods,
            "currency_summary": r.currency_summary, "reason": r.reason,
            "expected_delta": r.expected_delta, "pre_existing_blocks": r.pre_existing_blocks,
            "written": r.written, "restated": r.restated,
        } for r in results], indent=2, default=str))
        print(f"\n  wrote {args.json_out}")

    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
