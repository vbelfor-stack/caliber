"""
CALIBER v3 — CLI evaluator.
Usage: python evaluate.py <TICKER> [--fixture]

  --fixture   Load from tests/fixtures/ instead of live feeds (offline mode).

Prints full five-pillar readout with provenance stamps and technical overlay.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure caliber root is on sys.path when run directly
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env before any adapter or synthesis import reads os.environ
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on shell environment

from adapters.fmp_adapter import fetch_fmp, fetch_sector_pe, fetch_splits
from core.valuation_anchors import build_panel, run_dark_lens
from adapters.edgar_adapter import fetch_edgar
from core.edgar_cross_check import run_cross_check
from adapters.fred_adapter import fetch_fred
from adapters.base import PillarResult, Prov
from core.lens_select import select_lens, lens_label
from core.lens_overrides import lens_override
from core.universe import is_calibration_instrument
from core.pillars import score_all, RateUnavailable, _cycle_position_from_trajectory
from core.technicals import analyze_technicals, TechnicalOverlay
from synthesis.client import run_synthesis
from synthesis.schema import (
    SynthesisOutput, compute_er, per_scenario_returns,
    check_anchor, AnchorPriceDivergence, ANCHOR_DIVERGENCE_THRESHOLD,
)
from batch.runner import DegradedRunWriteRefused
from store.models import init_db, save_evaluation, save_failed_evaluation


# ── formatting helpers ────────────────────────────────────────────────────────

_CONF_MARK = {"high": "[HI]", "medium": "[MED]", "low": "[LOW]"}
_SCORE_BAR = {1: "[ ][ ][ ][ ][ ]", 2: "[=][ ][ ][ ][ ]", 3: "[=][=][ ][ ][ ]",
              4: "[=][=][=][ ][ ]", 5: "[=][=][=][=][=]"}


def _conf(conf: str) -> str:
    return _CONF_MARK.get(conf, f"[{conf}]")


def _prov_line(label: str, p: Prov, indent: int = 4) -> str:
    pad = " " * indent
    if p.is_missing():
        return f"{pad}{label}: n/a  {_conf('low')}"
    val = p.value
    if isinstance(val, float):
        if abs(val) < 1 and val != 0:
            val_str = f"{val:.4f}"
        else:
            val_str = f"{val:.2f}"
    else:
        val_str = str(val)
    as_of = f" as_of={p.as_of}" if p.as_of else ""
    return f"{pad}{label}: {val_str}  {_conf(p.confidence)} src={p.source}{as_of}"


def _divider(char: str = "-", width: int = 72) -> str:
    return char * width


def _print_pillar(result: PillarResult) -> None:
    bar = _SCORE_BAR.get(result.score, "?")
    print(f"\n  {result.name}")
    print(f"  Score: {result.score}/5  {bar}  {_conf(result.confidence)}")
    print(f"  Lens: {result.method}")
    print(f"  Rationale: {result.rationale}")
    if result.flags:
        print(f"  Flags: {', '.join(result.flags)}")
    if result.key_inputs:
        print("  Key inputs:")
        for p in result.key_inputs:
            if not p.is_missing():
                val = p.value
                if isinstance(val, float):
                    val_str = f"{val:.4f}" if abs(val) < 1 else f"{val:.2f}"
                else:
                    val_str = str(val)[:60]
                as_of = f" as_of={p.as_of}" if p.as_of else ""
                print(f"    {val_str}  {_conf(p.confidence)} src={p.source}{as_of}")


def _fy_series_from_db(db_path: Path, ticker: str, metric: str):
    """FY points for one metric from `fundamental_series`, oldest first, READ-ONLY.

    None means UNKNOWN — the table or the ticker's rows do not exist — which the classifier
    reads as asserted-absent. An empty list would claim "this issuer has no such history",
    which is a different and unearned statement.
    """
    import sqlite3
    if not Path(db_path).exists():
        return None
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
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
    return [(r["period_end"], r["value"]) for r in rows] or None


def _lifecycle_block(ticker: str, yf, edgar, lens: str, fixture_mode: bool,
                     db_path: Path, fmp_fx: Optional[Path]):
    """§5 STEP 1 — ANNOTATE AND PERSIST. Ruled 2026-08-17.

    READ-BACK IS THE THING THAT IS NOT HAPPENING HERE. The stage is computed AFTER every
    pillar is scored and it is written to its own append-only tables; no score, confidence
    label, tolerance, lens or E(R) consults it. Persistence without consultation, so the
    calibration set accrues while the scoring path stays exactly as it was.

    A PRODUCTION WRITE, STATED PLAINLY: one `lifecycle_stage` row per run, plus one
    `lifecycle_transitions` row when the computed stage moves. The destination is named by
    the caller — this writer has no default (L-2a step 0).
    """
    from adapters.edgar_adapter import instant_series
    from adapters.fmp_adapter import fetch_dividends, fetch_income_annual
    from core.lifecycle import (FLAG_INPUTS_INCOMPLETE_FEED_TRANSIENT, build_legs,
                                classify, lens_compatibility_flags)
    from store.models import save_lifecycle_stage

    # The annual rows come from the adapter's own accessor, not from TickerData (which
    # keeps derived point values, not the rows). None means UNKNOWN, and an unknown income
    # series is NOT classified: an empty series would reach the insufficient-history path
    # and emit YOUNG, so a feed flake would manufacture a pre-earnings verdict on a mature
    # issuer. Skipping is the only honest option and it is said out loud.
    income_annual = fetch_income_annual(ticker, fixture_path=fmp_fx)
    if income_annual is None:
        print(f"\n{_divider()}")
        print("LIFECYCLE STAGE  (Phase L — annotation only)")
        print(_divider())
        print("  SKIPPED — annual income rows unavailable (UNKNOWN, not empty). No stage "
              "row written: an empty series would emit YOUNG via insufficient history, "
              "which would be a feed flake wearing a verdict.")
        return None

    transient: dict = {}

    # Dividends: the one genuinely silent flake vector on this path. fetch_dividends
    # degrades a failed lookup to None (UNKNOWN, never []), which is correct but
    # indistinguishable from "no dividend key in an old fixture" — so classify the cause
    # HERE, where the calling context is known, and label it.
    dividends = fetch_dividends(ticker, fixture_path=fmp_fx)
    if dividends is None and not fixture_mode and os.environ.get("FMP_API_KEY"):
        transient["pays_dividend"] = "fmp_dividends_lookup_failed"

    shares = None
    pts = [(r.period_end, r.value)
           for r in instant_series(edgar.financials, "shares_outstanding")
           if r.period_end and r.value]
    shares = sorted(pts) or None

    legs = build_legs(
        ticker, income_annual, lens,
        dividends=dividends,
        shares_series=shares,
        fcf_fy=_fy_series_from_db(db_path, ticker, "fcf"),
        sales_to_capital_fy=_fy_series_from_db(db_path, ticker, "sales_to_capital"),
        transient_absences=transient,
    )
    result = classify(ticker, legs, lens)
    result.flags.extend(lens_compatibility_flags(result.stage, lens))

    print(f"\n{_divider()}")
    print("LIFECYCLE STAGE  (Phase L — annotation only, reads into NO score)")
    print(_divider())
    print(f"  Stage: {result.stage}   (rule: {result.rule_fired}, lens: {lens})")
    if result.flags:
        print(f"  Flags: {', '.join(result.flags)}")
    if result.absent_legs:
        print(f"  Absent legs: {', '.join(result.absent_legs)}")
    if FLAG_INPUTS_INCOMPLETE_FEED_TRANSIENT in result.flags:
        print("  NOTE: at least one absence is a TRANSIENT FEED FAILURE, not missing data —"
              " distrust this reading rather than acting on it.")
    for a in result.assertions:
        mark = {"satisfied": "OK ", "not_satisfied": "no ", "absent": "ABS"}[a.outcome]
        print(f"    {mark} {a.rule:16} {a.leg:22} {a.detail}")

    stage_id, transition_id = save_lifecycle_stage(result, db_path=db_path)
    # EXPECTED-DELTA REPORTING (ruled): every run states what it wrote, so a production md5
    # change is logged rather than silent.
    print(f"\n  PRODUCTION WRITE: lifecycle_stage +1 row (id={stage_id}, {ticker})"
          + (f"; lifecycle_transitions +1 row (id={transition_id})" if transition_id
             else "; lifecycle_transitions +0")
          + f"  -> {db_path}")
    return result


def _print_technicals(tech: TechnicalOverlay) -> None:
    print(_divider())
    print("TECHNICAL OVERLAY  (timing only - NOT a pillar, NOT scored)")
    print(_divider())
    print(f"  Trend:         {tech.trend.upper()}")
    print(f"  Above MA50:    {tech.above_ma50}")
    print(f"  Above MA200:   {tech.above_ma200}")
    rsi_str = f"{tech.rsi_14:.1f}" if tech.rsi_14 is not None else "n/a"
    print(f"  RSI-14:        {rsi_str}")
    print(f"  Vol confirm:   {tech.volume_confirmation}  (>=1.5x 30d avg = conviction)")
    if not tech.price_vs_ma50_pct.is_missing():
        print(_prov_line("vs MA50 %", tech.price_vs_ma50_pct))
    if not tech.price_vs_ma200_pct.is_missing():
        print(_prov_line("vs MA200 %", tech.price_vs_ma200_pct))
    print(f"  Note: {tech.notes}")
    print(f"  Data rows: {tech.data_rows}")


# ── main ──────────────────────────────────────────────────────────────────────

def evaluate(ticker: str, fixture_mode: bool = False,
             db_path: Optional[Path] = None,
             supersedes_id: Optional[int] = None,
             supersede_reason: Optional[str] = None) -> None:
    ticker = ticker.upper().strip()
    fx_root = Path("tests/fixtures")

    # ── DEGRADED-RUN WRITE GUARD (ruled L-2a after the 2026-08-17 contamination) ──
    # A --fixture run REPLAYS RECORDED DATA; its output is a measurement, not an
    # evaluation. Until now this path wrote to production regardless, which is how three
    # fixture-pillar MU rows landed in caliber.db wearing status='ok'. The batch path has
    # refused this since D-2; the interactive path did not, and the standing rule was
    # recorded as though it covered both. Raised BEFORE any fetch, and the SAME exception
    # class as batch so the rule reads once.
    #
    # ONE RESOLVED DESTINATION FOR EVERY WRITE IN THIS FUNCTION. The incident's mechanism
    # was PARTIAL ROUTING: --db-path covered the lifecycle write while save_evaluation kept
    # its production default. Nothing here may re-derive a destination.
    if fixture_mode and db_path is None:
        raise DegradedRunWriteRefused(
            f"{ticker}: --fixture is a DEGRADED run (recorded data replayed) and must NAME "
            f"ITS DESTINATION. Pass --db-path /path/to/scratch.db. Refusing before any "
            f"work so nothing is written to production caliber.db."
        )
    from store.models import _DEFAULT_DB as _PROD_DB
    write_db: Path = Path(db_path) if db_path is not None else _PROD_DB
    init_db(write_db)

    print(_divider("="))
    print(f"  CALIBER v3  --  {ticker}")
    print(_divider("="))

    # ── Load adapters ─────────────────────────────────────────────────────────
    # FMP-only (yfinance teardown Phase 2): no failover — fail loud on FMP error.
    fmp_fx = fx_root / "fmp" / f"{ticker}.json" if fixture_mode else None
    ed_fx = fx_root / "edgar" / f"{ticker}.json" if fixture_mode else None
    fr_fx = fx_root / "fred" / "DGS10.json" if fixture_mode else None

    print(f"\n[1/3] Fetching FMP data ({'fixture' if fixture_mode else 'live'})...")
    try:
        yf = fetch_fmp(ticker, fixture_path=fmp_fx)
        print(f"      OK  name={yf.name}  sector={yf.sector}  industry={yf.industry}")
    except RuntimeError as e:
        print(f"      FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[2/3] Fetching EDGAR data ({'fixture' if fixture_mode else 'live'})...")
    try:
        edgar = fetch_edgar(ticker, fixture_path=ed_fx)
        print(f"      OK  CIK={edgar.cik}  SIC={edgar.sic}  ({edgar.sic_description})")
    except RuntimeError as e:
        print(f"      FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[3/3] Fetching FRED rate ({'fixture' if fixture_mode else 'live'})...")
    try:
        fred = fetch_fred(fixture_path=fr_fx)
        rate_str = f"{fred.rate_10y.value:.2f}%" if not fred.rate_10y.is_missing() else "unavailable"
        print(f"      OK  10Y rate={rate_str}  conf={fred.rate_10y.confidence}")
    except RuntimeError as e:
        print(f"      WARN: {e} (continuing)", file=sys.stderr)
        from adapters.fred_adapter import FredData
        from adapters.base import missing_prov
        fred = FredData(rate_10y=missing_prov("FRED", None))

    # Propagate SIC to the ticker data for lens selection
    yf.sic = edgar.sic

    # E-3 ARMED (2026-08-08): EDGAR is the wired second source. Agreement raises a field
    # to high, conflict drops it to low; stale/lagged data moves nothing either way.
    # Confidence labels + source strings only — values, scores, E(R) and grades untouched.
    xcheck = run_cross_check(edgar, yf)
    if xcheck and xcheck.watch:
        print(f"\n  {xcheck.watch}")

    # ── Lens selection ────────────────────────────────────────────────────────
    lens = select_lens(yf.sector, yf.industry, edgar.sic, ticker=ticker)
    print(f"\n  Valuation lens: {lens_label(lens)} ({lens})")
    _ov = lens_override(ticker)
    if _ov is not None:
        print(f"  LENS OVERRIDDEN (explicit, hand-curated): {_ov[1]}")

    # Phase D-0 DARK: measure the three valuation anchors and log the spreads.
    # Applies nothing — no Prov, score, E(R) or grade can move.
    # Phase G-4 ARMED: the split record selects the own-history basis. None means
    # UNKNOWN (never "no splits"), and the panel falls back to the truncated series.
    _panel = build_panel(yf, fred, edgar,
                            fetch_sector_pe(yf.exchange or "NASDAQ") if not fixture_mode else {},
                            lens,
                            splits=fetch_splits(ticker, fixture_path=fmp_fx))

    # ── Five pillars ──────────────────────────────────────────────────────────
    print(f"\n{_divider('=')}")
    print("  FIVE-PILLAR SCORECARD")
    print(_divider("="))

    try:
        pillars = score_all(yf, edgar, fred, lens, panel=_panel)
    except RateUnavailable as e:
        # Mandatory-rate ruling: refuse loudly rather than print a rate-blind scorecard.
        # Distinct exit code (3) so a caller can tell a policy REFUSAL from a crash (1).
        print(f"\n{_divider('=')}", file=sys.stderr)
        print("  REFUSED TO SCORE — NO RISK-FREE ANCHOR", file=sys.stderr)
        print(_divider("="), file=sys.stderr)
        print(f"\n{e}\n", file=sys.stderr)
        print("The valuation pillar will not score without a 10Y rate. Fix the feed:",
              file=sys.stderr)
        print("  - live:    set FRED_API_KEY (see .env.example)", file=sys.stderr)
        print("  - offline: python -m tools.record_fred_fixture", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"\nFATAL: pillar scoring failed: {e}", file=sys.stderr)
        raise

    # Phase D-3 DARK: what the valuation score WOULD be under panel anchoring, logged
    # beside the live fixed-ladder score. Applies nothing — D-4 arms per lens on ruling.
    _val = next((p for p in pillars if p.name == "Valuation"), None)
    run_dark_lens(_panel, lens, _val.score if _val else None,
                  peak_warning=_cycle_position_from_trajectory(yf)[1])

    for pillar in pillars:
        _print_pillar(pillar)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{_divider()}")
    scores = [p.score for p in pillars]
    confs = [p.confidence for p in pillars]

    avg_score = sum(scores) / len(scores)
    from adapters.base import _RANK, _LEVEL
    min_conf_val = _LEVEL[min(_RANK[c] for c in confs)]

    print(f"  Composite avg score: {avg_score:.1f}/5.0")
    print(f"  Overall confidence:  {min_conf_val}  (min of pillar confidences)")
    print(f"  All flags: {', '.join(f for p in pillars for f in p.flags) or 'none'}")
    print(_divider())

    # ── Technical overlay ─────────────────────────────────────────────────────
    tech = analyze_technicals(yf.price_history, feed_source=yf.feed_source)
    _print_technicals(tech)

    # ── Synthesis ─────────────────────────────────────────────────────────────
    print(f"\n{_divider('=')}")
    print("  SYNTHESIS  (Anthropic API)")
    print(_divider("="))

    synthesis: Optional[SynthesisOutput] = None
    current_price: Optional[float] = (
        yf.current_price.value if not yf.current_price.is_missing() else None
    )

    expected_return: Optional[float] = None
    anchor_status: Optional[str] = None
    try:
        print("  Calling synthesis engine...")
        synthesis = run_synthesis(
            ticker=ticker,
            company_name=yf.name or ticker,
            sector=yf.sector or "",
            industry=yf.industry or "",
            lens=lens,
            pillars=pillars,
            tech=tech,
            current_price=current_price,
        )

        # ── E(R) via anchor-divergence guard (B-2) — never delegated to LLM ──
        price_as_of = yf.current_price.as_of if not yf.current_price.is_missing() else "?"
        price_str = f"${current_price:.2f} (as-of {price_as_of})" if current_price else "n/a"

        scenario_rets = per_scenario_returns(synthesis, current_price) if current_price else {}
        try:
            _ac = check_anchor(synthesis, current_price)   # armed guard (threshold in synthesis.schema)
            expected_return = _ac.computed_er
            anchor_status = _ac.status
            if _ac.divergence is not None:
                _thr_str = (f"armed @ {ANCHOR_DIVERGENCE_THRESHOLD * 100:.0f}%"
                            if ANCHOR_DIVERGENCE_THRESHOLD is not None else "DISARMED")
                print(f"  [anchor] implied=${_ac.implied_anchor:.2f} live=${current_price:.2f} "
                      f"divergence={_ac.divergence * 100:.1f}%  ({_thr_str}, no trip)")
            elif anchor_status == "anchor_unverified":
                print("  [anchor] model E(R) missing / non-derivable — E(R) withheld, "
                      "status=anchor_unverified")
        except AnchorPriceDivergence as e:
            print(f"  ANCHOR DIVERGENCE — {e}", file=sys.stderr)
            expected_return = None
            anchor_status = "anchor_divergence"

        print(f"\n  Current price: {price_str}")
        print(f"  {'Scenario':<8}  {'Prob':>5}  {'Target':>10}  {'Return':>8}")
        print(f"  {'-'*40}")
        for name, sc in [("Bull", synthesis.bull), ("Base", synthesis.base), ("Bear", synthesis.bear)]:
            tgt = f"${sc.priceTarget:.0f}" if sc.priceTarget else "n/a"
            ret = scenario_rets.get(name.lower())
            ret_str = f"{ret:+.1f}%" if ret is not None else "n/a"
            print(f"  {name:<8}  {sc.probability:>4}%  {tgt:>10}  {ret_str:>8}")
        if expected_return is not None:
            print(f"  {'-'*40}")
            print(f"  E(R) probability-weighted: {expected_return:+.1f}%")

        print(f"\n  Verdict confidence: {synthesis.verdictConfidence}")
        print(f"  Reason: {synthesis.verdictReason}")
        if synthesis.redFlags:
            print(f"\n  Red flags:")
            for flag in synthesis.redFlags:
                print(f"    - {flag}")
        if synthesis.bear.thesis:
            print(f"\n  Bear thesis: {synthesis.bear.thesis}")
        if synthesis.dataGaps:
            print(f"\n  Data gaps ({len(synthesis.dataGaps)}):")
            for gap in synthesis.dataGaps:
                print(f"    - {gap}")

    except RuntimeError as e:
        print(f"  WARN: Synthesis skipped — {e}", file=sys.stderr)
    except ValueError as e:
        print(f"  WARN: Synthesis schema error — {e}", file=sys.stderr)

    # ── §5 step 1: lifecycle stage — ANNOTATE AND PERSIST, after all scoring ──
    # Placed here deliberately: every pillar is already scored, so nothing downstream can
    # consult the stage even by accident.
    try:
        _lifecycle_block(ticker, yf, edgar, lens, fixture_mode, write_db, fmp_fx)
    except Exception as e:
        # An annotation must never take down an evaluation. Loud on stderr, never silent.
        print(f"  WARN: lifecycle stage annotation failed — {e}", file=sys.stderr)

    # ── Persist ───────────────────────────────────────────────────────────────
    print(f"\n{_divider()}")
    try:
        eval_id = save_evaluation(ticker, lens, pillars, synthesis,
                                  expected_return=expected_return, status=anchor_status,
                                  db_path=write_db,
                                  calibration_instrument=is_calibration_instrument(ticker),
                                  supersedes_id=supersedes_id,
                                  supersede_reason=supersede_reason)
        print(f"  Evaluation saved  (id={eval_id})")
    except Exception as e:
        print(f"  WARN: Could not persist evaluation — {e}", file=sys.stderr)

    print(_divider("="))
    print("  Readout complete.")
    print(_divider("="))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CALIBER v3 — Reliability-aware equity evaluator"
    )
    parser.add_argument("ticker", help="Stock ticker symbol (e.g. MU, GOOG, V)")
    parser.add_argument(
        "--fixture", action="store_true",
        help="Load from tests/fixtures/ (offline mode, no live network calls)"
    )
    parser.add_argument(
        "--db-path", type=Path, default=None,
        help="Destination for the lifecycle stage write (default: production caliber.db)"
    )
    parser.add_argument("--supersedes", type=int, default=None,
                        help="Evaluation id this run supersedes (requires --supersede-reason)")
    parser.add_argument("--supersede-reason", default=None,
                        help="Why the superseded evaluation is being replaced")
    args = parser.parse_args()
    evaluate(args.ticker, fixture_mode=args.fixture, db_path=args.db_path,
             supersedes_id=args.supersedes, supersede_reason=args.supersede_reason)


if __name__ == "__main__":
    main()
