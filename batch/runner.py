"""
CALIBER v3 — batch runner.

Runs the full evaluation pipeline for a list of tickers with per-name isolation:
  - One ticker failing never kills the batch.
  - Failures are persisted to SQLite as status='failed' with diagnosis.
  - Live API calls: FMP, EDGAR, FRED, Anthropic (synthesis).

Usage:
  python -m batch.runner                      # reads tickers.txt
  python -m batch.runner --tickers MU,GOOG,V  # explicit list
  python -m batch.runner --fixture            # fixture mode (no live calls)
  python -m batch.runner --no-synthesis       # skip LLM (pillars + store only)
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Ensure caliber root on path when run as __main__
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

from adapters.fixture_adapter import fetch_fixture
from core.datatypes import TickerData
from adapters.edgar_adapter import fetch_edgar
from core.edgar_cross_check import run_cross_check
from adapters.fred_adapter import fetch_fred, FredData
from adapters.base import missing_prov
from core.lens_select import select_lens
from core.pillars import score_all
from core.technicals import analyze_technicals
from store.models import save_evaluation, save_failed_evaluation, get_cached_synthesis, save_synthesis_cache
from synthesis.schema import check_anchor, AnchorPriceDivergence, ANCHOR_DIVERGENCE_THRESHOLD

DEFAULT_UNIVERSE = _ROOT / "tickers.txt"
FX_ROOT = _ROOT / "tests" / "fixtures"


def _fetch(ticker: str, log) -> TickerData:
    """
    Live data feed: FMP only (yfinance teardown 2026-08-07 — no failover leg).
    Fails loud with a reason-stamped RuntimeError on any FMP error.
    """
    try:
        from adapters.fmp_adapter import fetch_fmp
        data = fetch_fmp(ticker)
        log("data via FMP")
        return data
    except Exception as e:
        raise RuntimeError(f"[fetch] FMP failed for {ticker}: {type(e).__name__}: {e}") from e


def read_universe(path: Path = DEFAULT_UNIVERSE) -> List[str]:
    """Read tickers from universe file. Strips comments and blank lines."""
    if not path.exists():
        raise FileNotFoundError(f"Universe file not found: {path}")
    tickers = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            tickers.append(line.upper())
    return tickers


@dataclass
class TickerResult:
    ticker: str
    status: str                       # runner outcome: "ok" | "failed"
    eval_id: Optional[int] = None
    error: Optional[str] = None
    duration_s: float = 0.0
    avg_score: Optional[float] = None
    verdict_confidence: Optional[str] = None
    expected_return: Optional[float] = None
    lens: Optional[str] = None
    # Persisted DB eval status, mirroring the evaluations.status enum
    # (ok | no_synthesis | anchor_unverified | anchor_divergence | failed).
    # Distinct from `status` above, which stays the binary runner outcome so the
    # batch summary buckets are unchanged.
    eval_status: Optional[str] = None
    # Informational EDGAR staleness notice + predicted next-data date; no confidence
    # effect. Surfaced in the batch summary so a stale run says when it self-heals.
    freshness_watch: Optional[str] = None


def run_single_ticker(
    ticker: str,
    fixture_mode: bool = False,
    run_synthesis: bool = True,
    verbose: bool = True,
    force_refresh: bool = False,
) -> TickerResult:
    """
    Run the full CALIBER pipeline for one ticker.
    Never raises — failures are caught and returned as TickerResult(status='failed').
    """
    t0 = time.monotonic()
    _log = (lambda msg: print(f"  [{ticker}] {msg}")) if verbose else (lambda msg: None)

    try:
        ed_fx = FX_ROOT / "edgar" / f"{ticker}.json" if fixture_mode else None
        fr_fx = FX_ROOT / "fred" / "DGS10.json" if fixture_mode else None

        # ── Primary data feed ─────────────────────────────────────────────────
        if fixture_mode:
            _log("loading recorded fixture...")
            yf = fetch_fixture(ticker, fixture_path=FX_ROOT / "ticker" / f"{ticker}.json")
        else:
            yf = _fetch(ticker, log=_log)

        _log("fetching EDGAR...")
        edgar = fetch_edgar(ticker, fixture_path=ed_fx)

        _log("fetching FRED...")
        try:
            fred = fetch_fred(fixture_path=fr_fx)
        except Exception as e:
            _log(f"FRED unavailable ({e}), continuing with missing rate")
            fred = FredData(rate_10y=missing_prov("FRED", None))

        # E-3 ARMED (2026-08-08): apply EDGAR corroboration to field confidence.
        # Labels + source strings only; no value, score, E(R) or grade can move.
        xcheck = run_cross_check(edgar, yf, log=_log)
        freshness = xcheck.watch if xcheck else None

        # ── Scoring ───────────────────────────────────────────────────────────
        yf.sic = edgar.sic
        lens = select_lens(yf.sector, yf.industry, edgar.sic)
        pillars = score_all(yf, edgar, fred, lens)
        tech = analyze_technicals(yf.price_history, feed_source=yf.feed_source)

        avg_score = sum(p.score for p in pillars) / len(pillars)
        from adapters.base import _RANK, _LEVEL
        overall_conf = _LEVEL[min(_RANK[p.confidence] for p in pillars)]

        _log(f"pillars scored  avg={avg_score:.1f}  conf={overall_conf}  lens={lens}")

        # ── Synthesis (cache-first, deterministic) ────────────────────────────
        synthesis = None
        expected_return = None
        anchor_status = None
        price_for_er = None
        if run_synthesis:
            try:
                from synthesis.client import run_synthesis as _synth
                from synthesis.schema import parse_synthesis
                import json as _json
                from datetime import date as _date

                current_price = yf.current_price.value if not yf.current_price.is_missing() else None
                today_str = _date.today().isoformat()

                cached = None if force_refresh else get_cached_synthesis(ticker, today_str)
                if cached:
                    _log("synthesis cache hit — reusing today's scenario set")
                    synthesis = parse_synthesis(cached["synthesis_json"], pillars, ticker)
                    price_for_er = cached["price_snapshot"] or current_price
                else:
                    synthesis = _synth(
                        ticker=ticker,
                        company_name=yf.name or ticker,
                        sector=yf.sector or "",
                        industry=yf.industry or "",
                        lens=lens,
                        pillars=pillars,
                        tech=tech,
                        current_price=current_price,
                    )
                    save_synthesis_cache(
                        ticker, today_str,
                        _json.dumps(synthesis.rawJson),
                        current_price,
                    )
                    price_for_er = current_price
                    _log("synthesis generated and cached")
                _log(f"synthesis ok  verdict={synthesis.verdictConfidence}")
            except Exception as e:
                _log(f"synthesis skipped ({type(e).__name__}: {e})")

            # ── E(R) via anchor-divergence guard (B-2) ────────────────────────
            # Kept OUT of the generation try above so an armed divergence trip is
            # never misreported as "synthesis skipped" by the broad except.
            if synthesis is not None:
                try:
                    _ac = check_anchor(synthesis, price_for_er)   # armed guard (threshold in synthesis.schema)
                    expected_return = _ac.computed_er
                    anchor_status = _ac.status
                    if _ac.divergence is not None:
                        _thr_str = (f"armed @ {ANCHOR_DIVERGENCE_THRESHOLD * 100:.0f}%"
                                    if ANCHOR_DIVERGENCE_THRESHOLD is not None else "DISARMED")
                        _er_str = f"  E(R)={expected_return:+.1f}%" if expected_return is not None else ""
                        _log(f"[anchor] divergence={_ac.divergence * 100:.1f}%{_er_str}  ({_thr_str}, no trip)")
                    elif anchor_status == "anchor_unverified":
                        _log("[anchor] model E(R) missing / non-derivable — E(R) withheld, anchor_unverified")
                except AnchorPriceDivergence as e:
                    _log(f"ANCHOR DIVERGENCE — {e}")
                    expected_return = None
                    anchor_status = "anchor_divergence"

        # ── Persist ───────────────────────────────────────────────────────────
        eval_id = save_evaluation(
            ticker, lens, pillars, synthesis,
            expected_return=expected_return, status=anchor_status,
        )
        # Mirror the status save_evaluation actually persisted (anchor verdict
        # wins; else B-1 derivation from synthesis presence).
        eval_status = anchor_status or ("ok" if synthesis is not None else "no_synthesis")
        _log(f"saved  id={eval_id}")

        return TickerResult(
            ticker=ticker,
            status="ok",
            eval_id=eval_id,
            duration_s=time.monotonic() - t0,
            avg_score=avg_score,
            verdict_confidence=synthesis.verdictConfidence if synthesis else overall_conf,
            expected_return=expected_return,
            lens=lens,
            eval_status=eval_status,
            freshness_watch=freshness,
        )

    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        _log(f"FAILED — {err}")
        try:
            eval_id = save_failed_evaluation(ticker, err)
        except Exception:
            eval_id = None
        return TickerResult(
            ticker=ticker,
            status="failed",
            eval_id=eval_id,
            error=err,
            duration_s=time.monotonic() - t0,
            eval_status="failed",
        )


def run_batch(
    tickers: List[str],
    fixture_mode: bool = False,
    run_synthesis: bool = True,
    verbose: bool = True,
) -> List[TickerResult]:
    """
    Run the full pipeline for every ticker with per-name isolation.
    Returns results in input order. Failures do not abort remaining tickers.
    """
    total = len(tickers)
    results: List[TickerResult] = []

    print(f"\n{'='*72}")
    print(f"  CALIBER BATCH  —  {total} ticker(s)  {'[fixture]' if fixture_mode else '[live]'}")
    print(f"{'='*72}")

    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{total}] {ticker}")
        result = run_single_ticker(
            ticker,
            fixture_mode=fixture_mode,
            run_synthesis=run_synthesis,
            verbose=verbose,
        )
        results.append(result)

    # ── Summary ───────────────────────────────────────────────────────────────
    ok = [r for r in results if r.status == "ok"]
    failed = [r for r in results if r.status == "failed"]
    total_s = sum(r.duration_s for r in results)

    print(f"\n{'='*72}")
    print(f"  BATCH SUMMARY")
    print(f"{'='*72}")
    print(f"  {'Ticker':<8}  {'Status':<8}  {'Score':>6}  {'Conf':<8}  {'E(R)':>8}  {'ID':>6}")
    print(f"  {'-'*56}")
    for r in results:
        score_s = f"{r.avg_score:.1f}" if r.avg_score else "n/a"
        conf_s = r.verdict_confidence or "n/a"
        er_s = f"{r.expected_return:+.1f}%" if r.expected_return is not None else "n/a"
        id_s = str(r.eval_id) if r.eval_id else "-"
        status_s = r.status.upper()
        print(f"  {r.ticker:<8}  {status_s:<8}  {score_s:>6}  {conf_s:<8}  {er_s:>8}  {id_s:>6}")
    print(f"  {'-'*56}")
    print(f"  {len(ok)} succeeded  {len(failed)} failed  {total_s:.1f}s total")
    watches = [r.freshness_watch for r in results if r.freshness_watch]
    if watches:
        print()
        for w in watches:
            print(f"  {w}")
    if failed:
        print(f"\n  Failed tickers (stored as failed-with-diagnosis):")
        for r in failed:
            print(f"    {r.ticker}: {r.error}")
    print(f"{'='*72}\n")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="CALIBER v3 — batch evaluator")
    parser.add_argument("--tickers", help="Comma-separated tickers (default: read tickers.txt)")
    parser.add_argument("--fixture", action="store_true", help="Use fixture mode (no live calls)")
    parser.add_argument("--no-synthesis", action="store_true", help="Skip LLM synthesis")
    parser.add_argument("--universe", default=str(DEFAULT_UNIVERSE), help="Path to universe file")
    args = parser.parse_args()

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = read_universe(Path(args.universe))

    if not tickers:
        print("No tickers to process.", file=sys.stderr)
        sys.exit(1)

    results = run_batch(
        tickers,
        fixture_mode=args.fixture,
        run_synthesis=not args.no_synthesis,
    )

    failed = [r for r in results if r.status == "failed"]
    sys.exit(1 if len(failed) == len(results) else 0)


if __name__ == "__main__":
    main()
