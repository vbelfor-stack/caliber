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
  python -m batch.runner --no-synthesis --db-path /tmp/x.db   # pillars + store, no LLM

Degraded runs (--fixture / --no-synthesis) REQUIRE --db-path: they are measurement
routes, and defaulting them into production caliber.db is how the 2026-08-07
contamination happened. See DegradedRunWriteRefused.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Ensure caliber root on path when run as __main__
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass


from core.datatypes import TickerData
from adapters.fmp_adapter import fetch_fmp
from adapters.edgar_adapter import fetch_edgar
from core.edgar_cross_check import run_cross_check
from core.fundamental_series import run_dark_fcf_series
from core.valuation_anchors import build_panel, run_dark_lens
from adapters.fred_adapter import fetch_fred, FredData
from adapters.base import missing_prov
from core.lens_select import select_lens
from core.pillars import score_all, RateUnavailable, _cycle_position_from_trajectory
from core.technicals import analyze_technicals
from store.models import (save_evaluation, save_failed_evaluation, get_cached_synthesis,
                          save_synthesis_cache, _DEFAULT_DB, _validate_supersede_link,
                          SupersedeLinkInvalid)
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
    # Carried ONLY to feed the batch-level leverage uniformity tripwire below. Not scored
    # here and not persisted from here — the pillar owns the scoring.
    debt_to_equity: Optional[float] = None


class DegradedRunWriteRefused(Exception):
    """A degraded run tried to write to the DEFAULT (production) database.

    A degraded run is one whose output is not a real evaluation: --fixture replays
    recorded data, --no-synthesis produces an eval with no synthesis. Both are
    MEASUREMENT routes, and both used to land in production caliber.db as a side effect
    of merely being run — that is how 189 rows of test contamination got in (see the
    2026-08-07 purge), and a --no-synthesis batch is the obvious cheap re-measurement
    route that would do it again.

    The rule is not "degraded runs may not persist" — `--no-synthesis` is documented as
    "pillars + store only" and that capability is kept. The rule is that a degraded run
    must NAME ITS DESTINATION: pass db_path (CLI: --db-path). Writing to production then
    requires saying so out loud, which makes it a decision instead of an accident.
    """


def _guard_degraded_write(fixture_mode: bool, run_synthesis: bool, db_path: Optional[Path]) -> None:
    """Refuse a degraded run that would write to the default production DB.

    Raised BEFORE any work and deliberately OUTSIDE run_single_ticker's try/except: if
    the broad handler caught it, the refusal would itself be persisted to production as
    a 'failed' row — writing to the very database it exists to protect.
    """
    if db_path is not None:
        return
    degraded = []
    if fixture_mode:
        degraded.append("--fixture (replays recorded data, not a real evaluation)")
    if not run_synthesis:
        degraded.append("--no-synthesis (produces an eval with no synthesis)")
    if not degraded:
        return
    raise DegradedRunWriteRefused(
        "refusing to write a degraded run to the production database.\n"
        "  Degraded because: " + "; ".join(degraded) + "\n"
        f"  Default DB would be: {_DEFAULT_DB}\n"
        "  Name a destination explicitly: --db-path /tmp/scratch.db\n"
        "  (Pass the production path deliberately if that is genuinely what you want.)"
    )


def run_single_ticker(
    ticker: str,
    fixture_mode: bool = False,
    run_synthesis: bool = True,
    verbose: bool = True,
    force_refresh: bool = False,
    db_path: Optional[Path] = None,
    supersedes_id: Optional[int] = None,
    supersede_reason: Optional[str] = None,
) -> TickerResult:
    """
    Run the full CALIBER pipeline for one ticker.
    Never raises — failures are caught and returned as TickerResult(status='failed').

    supersedes_id / supersede_reason: stamp the persisted row as REPLACING an earlier
    evaluation. Only a COMPLETING run carries the link — a 'failed' or
    'rate_unavailable' row supersedes nothing, because it replaced nothing.

    EXCEPT DegradedRunWriteRefused, which is raised before any work: a degraded run
    (fixture_mode or run_synthesis=False) must pass db_path explicitly rather than
    defaulting into production caliber.db. See _guard_degraded_write.
    """
    _guard_degraded_write(fixture_mode, run_synthesis, db_path)
    # Validated HERE, outside the try/except, for the same reason the degraded-write
    # guard is: the broad handler below persists a 'failed' row, so a malformed
    # supersede link caught in there would write a junk row into the very database
    # the check protects — and then report the refusal as an operational failure.
    _validate_supersede_link(supersedes_id, supersede_reason, db_path or _DEFAULT_DB)

    t0 = time.monotonic()
    _log = (lambda msg: print(f"  [{ticker}] {msg}")) if verbose else (lambda msg: None)

    try:
        ed_fx = FX_ROOT / "edgar" / f"{ticker}.json" if fixture_mode else None
        fr_fx = FX_ROOT / "fred" / "DGS10.json" if fixture_mode else None
        # Split records live in the FMP fixture, which is now also where fixture mode gets
        # its TickerData — one recorded payload, one source, no cross-set pairing. Absent
        # file -> None -> UNKNOWN -> the panel keeps the truncated own-history basis.
        _fmp_fx = FX_ROOT / "fmp" / f"{ticker}.json"
        fmp_fx = _fmp_fx if (fixture_mode and _fmp_fx.exists()) else None

        # ── Primary data feed ─────────────────────────────────────────────────
        if fixture_mode:
            _log("loading recorded fixture...")
            # Fixture mode replays the FMP fixture — THE SAME PAYLOAD PRODUCTION FETCHES,
            # through the same adapter. The retired tests/fixtures/ticker set was a
            # yfinance-shaped recording whose loader had no live counterpart, so an
            # offline run exercised a code path production no longer had. It also carried
            # only 3 undated price rows, which is why the H-1 yield leg could never
            # produce a point offline.
            yf = fetch_fmp(ticker, fixture_path=FX_ROOT / "fmp" / f"{ticker}.json")
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

        # Phase D-0 DARK: measure the three valuation anchors; applies nothing.
        if fixture_mode:
            sector_pe = {}
        else:
            from adapters.fmp_adapter import fetch_sector_pe
            sector_pe = fetch_sector_pe(yf.exchange or "NASDAQ")
        # Phase G-4 ARMED: the split record selects the own-history basis. None means
        # UNKNOWN (never "no splits"), and the panel falls back to the truncated series.
        from adapters.fmp_adapter import fetch_splits
        _splits = (fetch_splits(ticker, fixture_path=fmp_fx)
                   if (fmp_fx is not None or not fixture_mode) else None)
        _panel = build_panel(yf, fred, edgar, sector_pe, lens, log=_log, splits=_splits)

        # Phase H-1 DARK: build and PERSIST the FCF component series for Phase M.
        # Applies nothing — no score, E(R), grade or confidence label reads it. The
        # destination is named explicitly because H-1 makes this surface a writer; the
        # degraded-run guard at the top of this function has already validated it.
        run_dark_fcf_series(yf, edgar, splits=_splits, log=_log,
                            db_path=db_path or _DEFAULT_DB)

        # RateUnavailable is deliberately NOT caught here — it must reach the dedicated
        # handler below, not the broad `except Exception` that reports operational DOA.
        # A policy refusal filed as a crash is exactly the conflation D-2 removes.
        pillars = score_all(yf, edgar, fred, lens, panel=_panel)
        tech = analyze_technicals(yf.price_history, feed_source=yf.feed_source)

        # Phase D-3 DARK: log the would-be panel score beside the live one.
        _val = next((p for p in pillars if p.name == "Valuation"), None)
        run_dark_lens(_panel, lens, _val.score if _val else None,
                      peak_warning=_cycle_position_from_trajectory(yf)[1], log=_log)

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
                        db_path=db_path or _DEFAULT_DB,
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
            db_path=db_path or _DEFAULT_DB,
            supersedes_id=supersedes_id, supersede_reason=supersede_reason,
        )
        if supersedes_id is not None:
            _log(f"supersedes id={supersedes_id}")
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
            debt_to_equity=(None if yf.debt_to_equity.is_missing()
                            else yf.debt_to_equity.value),
        )

    except RateUnavailable as exc:
        # Mandatory-rate ruling: a refusal is not a crash. Persisted under its own status
        # so the audit trail shows the pipeline worked and DECLINED, and record-and-
        # continue keeps one rate-less ticker from aborting the batch.
        err = f"RateUnavailable: {exc}"
        _log(f"REFUSED TO SCORE — no risk-free anchor. {exc}")
        try:
            eval_id = save_failed_evaluation(
                ticker, err, db_path=db_path or _DEFAULT_DB, status="rate_unavailable",
            )
        except Exception:
            eval_id = None
        return TickerResult(
            ticker=ticker,
            status="failed",       # not 'ok': no pillars were produced, nothing is usable
            eval_id=eval_id,
            error=err,
            duration_s=time.monotonic() - t0,
            eval_status="rate_unavailable",
        )

    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        _log(f"FAILED — {err}")
        try:
            eval_id = save_failed_evaluation(ticker, err, db_path=db_path or _DEFAULT_DB)
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


# The leverage ladder's top rung (core/pillars.score_financial_health: de <= 30 -> 3 pts).
# Mirrored, not imported, on purpose: the tripwire must keep firing if someone edits the
# ladder without thinking about units, which importing the live threshold would mask.
_DE_TOP_RUNG_PCT = 30.0
_DE_UNIFORMITY_MIN_TICKERS = 3


def _leverage_uniformity_alarm(results: List[TickerResult]) -> Optional[str]:
    """Warn when EVERY name in a batch collects maximum leverage points.

    THE SYMPTOM THIS WATCHES FOR IS THE ONE WE MISSED. For a week after the yfinance
    teardown, FMP's D/E RATIO was scored against a PERCENT ladder, so every issuer landed
    under the top rung and the leverage component contributed nothing to any score. It was
    visible the whole time — GOOG "debt/equity 0%", V "1%" for a name levered ~67% — and
    nothing in the system remarked on it.

    A real universe does not agree like that. The golden five alone span ~6% to ~295%, so
    a whole batch under the top rung is far more likely to be a units regression than a
    portfolio of debt-free issuers.

    ADVISORY ONLY — it prints, it never changes a score or blocks a run. A tripwire that
    can withhold an evaluation would be a new failure mode; this one only makes the
    silence audible.
    """
    seen = [r.debt_to_equity for r in results if r.debt_to_equity is not None]
    if len(seen) < _DE_UNIFORMITY_MIN_TICKERS:
        return None                       # too few to call uniformity
    if any(de > _DE_TOP_RUNG_PCT for de in seen):
        return None                       # the ladder is discriminating; nothing to say
    return (
        f"  [!] LEVERAGE UNIFORMITY — all {len(seen)} ticker(s) with a debt/equity "
        f"reading are at or under the ladder's top rung ({_DE_TOP_RUNG_PCT:.0f}%), so "
        f"EVERY ONE scored maximum leverage points.\n"
        f"      max seen {max(seen):.2f}%. This is the signature of a UNITS REGRESSION "
        f"(a ratio reaching a percent ladder), which is exactly how the 2026-08-07 "
        f"debt/equity defect hid for a week.\n"
        f"      Advisory only — no score was changed. Verify the adapter's D/E scale "
        f"before trusting this batch's Financial Health readings."
    )


def run_batch(
    tickers: List[str],
    fixture_mode: bool = False,
    run_synthesis: bool = True,
    verbose: bool = True,
    db_path: Optional[Path] = None,
    supersedes: Optional[Dict[str, int]] = None,
    supersede_reason: Optional[str] = None,
) -> List[TickerResult]:
    """
    Run the full pipeline for every ticker with per-name isolation.
    Returns results in input order. Failures do not abort remaining tickers.

    Raises DegradedRunWriteRefused up front (before any ticker runs) if this is a
    degraded run with no explicit db_path — refusing the whole batch is right here, as
    the destination is a property of the run, not of any one ticker.

    supersedes: {ticker -> superseded evaluation id}. A ticker absent from the map
    runs normally and supersedes nothing. Every link is validated UP FRONT, before
    any ticker runs, for the same reason as the degraded-write guard: a re-run that
    would leave the trail half-written on ticker 4 of 5 should not start.
    """
    _guard_degraded_write(fixture_mode, run_synthesis, db_path)

    supersedes = supersedes or {}
    unknown = sorted(set(supersedes) - set(tickers))
    if unknown:
        raise SupersedeLinkInvalid(
            f"supersedes names ticker(s) not in this batch: {', '.join(unknown)}. "
            "A link that never runs would be silently dropped."
        )
    for _tkr, _sid in supersedes.items():
        _validate_supersede_link(_sid, supersede_reason, db_path or _DEFAULT_DB)

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
            db_path=db_path,
            supersedes_id=supersedes.get(ticker),
            supersede_reason=supersede_reason if ticker in supersedes else None,
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
    leverage_alarm = _leverage_uniformity_alarm(results)
    if leverage_alarm:
        print()
        print(leverage_alarm)

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
    parser.add_argument("--db-path", default=None,
                        help="Destination DB. REQUIRED for degraded runs (--fixture / "
                             "--no-synthesis) so a measurement run cannot land in production.")
    parser.add_argument("--supersedes", default=None,
                        help="Mark this run as REPLACING earlier evaluations. "
                             "Format: TICKER=ID[,TICKER=ID...]. Requires --supersede-reason. "
                             "The earlier rows are never modified.")
    parser.add_argument("--supersede-reason", default=None,
                        help="Why the earlier evaluations are superseded. Mandatory "
                             "whenever --supersedes is given.")
    args = parser.parse_args()

    supersedes = None
    if args.supersedes:
        supersedes = {}
        for pair in args.supersedes.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                print(f"\nREFUSED: --supersedes entry {pair!r} is not TICKER=ID\n", file=sys.stderr)
                sys.exit(3)
            tkr, _, sid = pair.partition("=")
            if not sid.strip().isdigit():
                print(f"\nREFUSED: --supersedes entry {pair!r} has a non-numeric id\n", file=sys.stderr)
                sys.exit(3)
            supersedes[tkr.strip().upper()] = int(sid)

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = read_universe(Path(args.universe))

    if not tickers:
        print("No tickers to process.", file=sys.stderr)
        sys.exit(1)

    try:
        results = run_batch(
            tickers,
            fixture_mode=args.fixture,
            run_synthesis=not args.no_synthesis,
            db_path=Path(args.db_path) if args.db_path else None,
            supersedes=supersedes,
            supersede_reason=args.supersede_reason,
        )
    except (DegradedRunWriteRefused, SupersedeLinkInvalid) as e:
        # Loud, but a refusal is an expected operator outcome, not a crash — print it
        # readably and exit 3 (matching evaluate.py's refusal code) rather than dumping
        # a traceback that reads like a bug.
        print(f"\nREFUSED: {e}\n", file=sys.stderr)
        sys.exit(3)

    failed = [r for r in results if r.status == "failed"]
    sys.exit(1 if len(failed) == len(results) else 0)


if __name__ == "__main__":
    main()
