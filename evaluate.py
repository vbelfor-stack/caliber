"""
CALIBER v3 — CLI evaluator.
Usage: python evaluate.py <TICKER> [--fixture]

  --fixture   Load from tests/fixtures/ instead of live feeds (offline mode).

Prints full five-pillar readout with provenance stamps and technical overlay.
"""
from __future__ import annotations

import argparse
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

from adapters.fmp_adapter import fetch_fmp
from adapters.edgar_adapter import fetch_edgar
from core.edgar_cross_check import run_dark_cross_check
from adapters.fred_adapter import fetch_fred
from adapters.base import PillarResult, Prov
from core.lens_select import select_lens, lens_label
from core.pillars import score_all
from core.technicals import analyze_technicals, TechnicalOverlay
from synthesis.client import run_synthesis
from synthesis.schema import (
    SynthesisOutput, compute_er, per_scenario_returns,
    check_anchor, AnchorPriceDivergence, ANCHOR_DIVERGENCE_THRESHOLD,
)
from store.models import save_evaluation, save_failed_evaluation


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

def evaluate(ticker: str, fixture_mode: bool = False) -> None:
    ticker = ticker.upper().strip()
    fx_root = Path("tests/fixtures")

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

    # E-3 DARK LAUNCH: log what an EDGAR cross-check WOULD do to each field's
    # confidence. Applies nothing — no Prov is mutated, no score/E(R)/grade can move.
    xcheck = run_dark_cross_check(edgar, yf)
    if xcheck and xcheck.watch:
        print(f"\n  {xcheck.watch}")

    # ── Lens selection ────────────────────────────────────────────────────────
    lens = select_lens(yf.sector, yf.industry, edgar.sic)
    print(f"\n  Valuation lens: {lens_label(lens)} ({lens})")

    # ── Five pillars ──────────────────────────────────────────────────────────
    print(f"\n{_divider('=')}")
    print("  FIVE-PILLAR SCORECARD")
    print(_divider("="))

    try:
        pillars = score_all(yf, edgar, fred, lens)
    except Exception as e:
        print(f"\nFATAL: pillar scoring failed: {e}", file=sys.stderr)
        raise

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

    # ── Persist ───────────────────────────────────────────────────────────────
    print(f"\n{_divider()}")
    try:
        eval_id = save_evaluation(ticker, lens, pillars, synthesis,
                                  expected_return=expected_return, status=anchor_status)
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
    args = parser.parse_args()
    evaluate(args.ticker, fixture_mode=args.fixture)


if __name__ == "__main__":
    main()
