"""
Phase D-0 measurement probe — READ-ONLY. Produces the calibration evidence behind
docs/d0-panel.md and nothing else.

    python -m tools.probe_valuation_panel MU GOOG V NOW WU --json /tmp/d0.json

WHY THIS EXISTS RATHER THAN A BATCH RUN. The dark panel is already wired at both
evaluation boundaries, but reaching it through batch/runner.py means reaching
save_evaluation (runner.py:224), which fires UNCONDITIONALLY — even under
--no-synthesis. A measurement pass that writes no_synthesis rows into caliber.db would
recontaminate the distribution the 2026-08-07 purge established. D-0 applies nothing, so
its probe must also PERSIST nothing.

The guard is STRUCTURAL, not a flag. This module imports the adapters directly, exactly
as evaluate.py does, and never imports batch.runner or store.models — so no writer is
reachable from here even by accident. tests/test_d0_probe_readonly.py asserts that in a
clean subprocess: importing this module must not pull a persistence module into
sys.modules. If someone later adds a convenience import from batch.runner, that test
fails rather than the probe quietly gaining a write path.

Live-only by design: the FRED fixture records no value, so an offline run is rate-blind
and the mandatory anchor would be missing for reasons that say nothing about the market
(fixing that fixture is D-2).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date
from typing import Any, Dict, List, Optional

from adapters.edgar_adapter import fetch_edgar, instant_series
from adapters.fmp_adapter import fetch_fmp, fetch_sector_pe
from adapters.fred_adapter import fetch_fred
from core.lens_select import select_lens
from core.valuation_anchors import (
    ANCHOR_OWN_HISTORY,
    ANCHOR_RISK_FREE,
    ANCHOR_SECTOR,
    METRIC_EARNINGS_YIELD,
    METRIC_EBITDA_YIELD,
    METRIC_FCF_YIELD,
    METRIC_FORWARD_EARNINGS_YIELD,
    ValuationPanel,
    compute_panel,
    own_history_earnings_yields,
    render_panel,
)

METRICS = [METRIC_EARNINGS_YIELD, METRIC_FORWARD_EARNINGS_YIELD,
           METRIC_FCF_YIELD, METRIC_EBITDA_YIELD]
ANCHORS = [ANCHOR_RISK_FREE, ANCHOR_SECTOR, ANCHOR_OWN_HISTORY]


def _own_history_diagnosis(edgar, price_history) -> Dict[str, Any]:
    """Why the own-history anchor is or is not available, in terms of its INPUTS.

    The panel's own reason string reports the symptom ("only N points"); D-0 has to
    report the cause, because the causes are different in kind — V has no share series
    to build from at all, while NOW has one that a 5:1 split makes discontinuous. One is
    an accepted data limit, the other is a Phase-G dependency.
    """
    shares = [r for r in instant_series(edgar.financials, "shares_outstanding")
              if r.period_end and r.value]
    series = own_history_earnings_yields(edgar, price_history)
    return {
        "share_points": len(shares),
        "usable_quarters": len(series),
        "loss_periods_excluded": series[0].get("loss_periods_excluded", 0) if series else 0,
        "span": (f"{series[-1]['period_end']}→{series[0]['period_end']}"
                 if series else None),
        "median_yield": (statistics.median(h["earnings_yield"] for h in series)
                         if series else None),
    }


def probe_ticker(ticker: str, fred: Any, log) -> Dict[str, Any]:
    """One ticker, live. Returns the panel plus the D-0 diagnostics around it."""
    log(f"\n{'=' * 78}\n{ticker}\n{'=' * 78}")
    yf = fetch_fmp(ticker)
    log(f"  FMP    exchange={yf.exchange}  sector={yf.sector}")
    edgar = fetch_edgar(ticker)
    log(f"  EDGAR  CIK={edgar.cik}  SIC={edgar.sic}")
    yf.sic = edgar.sic

    sector_pe = fetch_sector_pe(yf.exchange or "NASDAQ")
    lens = select_lens(yf.sector, yf.industry, edgar.sic)
    log(f"  lens={lens}  sector_pe_snapshot={len(sector_pe)} sectors")

    panel = compute_panel(yf, fred, edgar, sector_pe, lens)
    log(render_panel(panel))

    return {
        "ticker": ticker,
        "lens": lens,
        "sector": yf.sector,
        "exchange": yf.exchange,
        "as_of": panel.as_of,
        "own_history": _own_history_diagnosis(edgar, yf.price_history),
        "sector_pe": sector_pe.get(yf.sector) if yf.sector else None,
        "readings": [
            {"metric": r.metric, "anchor": r.anchor, "ticker_yield": r.ticker_yield,
             "anchor_yield": r.anchor_yield, "spread": r.spread,
             "available": r.available, "reason": r.reason, "note": r.note}
            for r in panel.readings
        ],
        "per_metric": {
            m: {
                "least_flattering": (panel.least_flattering(m).anchor
                                     if panel.least_flattering(m) else None),
                "least_flattering_spread": (panel.least_flattering(m).spread
                                            if panel.least_flattering(m) else None),
                "anchor_range_pp": panel.anchor_range(m),
                "verdict_split": panel.verdict_split(m),
                "available_anchors": [r.anchor for r in panel.by_metric(m)],
            }
            for m in METRICS
        },
        "notes": list(panel.notes),
        "rendered": render_panel(panel),
    }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cross-ticker distributions. Aggregates the MEASUREMENTS, never the verdicts."""
    dist: Dict[str, Any] = {}
    for metric in METRICS:
        per_anchor = {}
        for anchor in ANCHORS:
            spreads = [
                (r["ticker"], rd["spread"])
                for r in results for rd in r["readings"]
                if rd["metric"] == metric and rd["anchor"] == anchor
                and rd["available"] and rd["spread"] is not None
            ]
            if spreads:
                vals = [s for _, s in spreads]
                per_anchor[anchor] = {
                    "n": len(vals),
                    "min": min(vals), "median": statistics.median(vals), "max": max(vals),
                    "by_ticker": {t: s for t, s in spreads},
                }
            else:
                per_anchor[anchor] = {"n": 0}
        splits = {r["ticker"]: r["per_metric"][metric]["verdict_split"]
                  for r in results if r["per_metric"][metric]["verdict_split"]}
        ranges = [r["per_metric"][metric]["anchor_range_pp"] for r in results
                  if r["per_metric"][metric]["anchor_range_pp"] is not None]
        dist[metric] = {
            "per_anchor": per_anchor,
            "verdict_splits": splits,
            "dispersion_pp": {"n": len(ranges),
                              "min": min(ranges) if ranges else None,
                              "median": statistics.median(ranges) if ranges else None,
                              "max": max(ranges) if ranges else None},
            "least_flattering_counts": _count(
                [r["per_metric"][metric]["least_flattering"] for r in results
                 if r["per_metric"][metric]["least_flattering"]]),
        }
    return dist


def _count(items: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Phase D-0 valuation-anchor probe (read-only; writes no DB rows)")
    ap.add_argument("tickers", nargs="*", default=["MU", "GOOG", "V", "NOW", "WU"],
                    help="tickers to measure (default: the golden five)")
    ap.add_argument("--json", help="write the full measurement record here")
    args = ap.parse_args()
    tickers = [t.upper() for t in (args.tickers or ["MU", "GOOG", "V", "NOW", "WU"])]

    def log(msg):
        print(msg, flush=True)

    log(f"[D-0 PROBE] live measurement  {date.today().isoformat()}  "
        f"tickers={','.join(tickers)}  APPLIED=NOTHING  PERSISTED=NOTHING")

    fred = fetch_fred()
    rate = fred.rate_10y
    log(f"[D-0 PROBE] FRED 10Y = "
        f"{'unavailable' if rate.is_missing() else f'{rate.value:.2f}%'}  "
        f"conf={rate.confidence}")

    results, failures = [], []
    for t in tickers:
        try:
            results.append(probe_ticker(t, fred, log))
        except Exception as e:                       # loud, per-ticker, never silent
            log(f"  [D-0 PROBE] FAILED {t}: {type(e).__name__}: {e}")
            failures.append({"ticker": t, "error": f"{type(e).__name__}: {e}"})

    record = {
        "as_of": date.today().isoformat(),
        "rate_10y": None if rate.is_missing() else rate.value,
        "tickers": tickers,
        "results": results,
        "failures": failures,
        "distributions": summarize(results) if results else {},
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, default=str)
        log(f"\n[D-0 PROBE] measurement record → {args.json}")
    if failures:
        log(f"[D-0 PROBE] {len(failures)} ticker(s) failed: "
            f"{', '.join(f['ticker'] for f in failures)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
