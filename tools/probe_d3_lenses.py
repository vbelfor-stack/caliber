"""
Phase D-3 measurement probe — READ-ONLY. Live fixed-ladder score vs would-be
panel-anchored score, per lens per ticker. APPLIES NOTHING, PERSISTS NOTHING.

    python -m tools.probe_d3_lenses MU GOOG V NOW WU --json /tmp/d3.json

Read-only by CONSTRUCTION, not by flag — same discipline as the D-0 probe: it imports
the adapters and core.pillars directly, exactly as evaluate.py does, and never imports
batch.runner or store.models, so no writer is reachable from here even by accident.
tests/test_d0_probe_readonly.py pins that property for both probes.

WHY EVERY TICKER IS SCORED ON EVERY LENS. The golden five only exercise three of the
five lenses natively (MU cyclical, GOOG/V/WU compounder, NOW growth) — there is NO
golden bank and NO golden standard name. Scoring each ticker under every lens gives the
bank and standard proposals some live evidence instead of none. Forced-lens cells are
COUNTERFATUAL and marked as such; only the native cell describes what CALIBER would
actually do to that ticker.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Dict, List

from adapters.edgar_adapter import fetch_edgar
from adapters.fmp_adapter import fetch_fmp, fetch_sector_pe
from adapters.fred_adapter import fetch_fred
from core.lens_select import select_lens
from core.pillars import _cycle_position_from_trajectory, score_valuation
from core.valuation_anchors import (
    LENS_METRIC, bank_instrument_reading, compute_panel, dark_lens_score,
    render_dark_lens,
)

LENSES = ["cyclical", "compounder", "growth", "standard", "bank"]


def probe_ticker(ticker: str, fred: Any, log) -> Dict[str, Any]:
    log(f"\n{'=' * 78}\n{ticker}\n{'=' * 78}")
    yf = fetch_fmp(ticker)
    edgar = fetch_edgar(ticker)
    yf.sic = edgar.sic
    sector_pe = fetch_sector_pe(yf.exchange or "NASDAQ")
    native = select_lens(yf.sector, yf.industry, edgar.sic)
    log(f"  native lens={native}  sector={yf.sector}  exchange={yf.exchange}")

    panel = compute_panel(yf, fred, edgar, sector_pe, native)
    _, peak_warning = _cycle_position_from_trajectory(yf)
    log(f"  cycle warning={peak_warning or 'none'}")

    scores, rows = [], []
    for lens in LENSES:
        live = score_valuation(yf, fred, lens)          # the REAL live scorer
        dark = dark_lens_score(panel, lens, live_score=live.score,
                               peak_warning=peak_warning)
        scores.append(dark)
        rows.append({
            "lens": lens,
            "is_native": lens == native,
            "metric": dark.metric,
            "live_score": live.score,
            "live_flags": sorted(live.flags),
            "panel_score": dark.panel_score,
            "haircut_score": dark.haircut_score,
            "delta": dark.delta,
            "binding_anchor": dark.binding_anchor,
            "binding_spread": dark.binding_spread,
            "anchor_count": dark.anchor_count,
            "narrowed": dark.narrowed,
            "independence_narrowed": dark.independence_narrowed,
            "gate_applied": dark.gate_applied,
            "panel_flags": dark.flags,
            "reason": dark.reason,
        })
    log(render_dark_lens(scores, ticker))

    bank = bank_instrument_reading(yf, fred)
    log(f"  [BANK-INSTRUMENT] P/B={bank['price_to_book']}  ROE={bank['roe_pct']}  "
        f"beta={bank['beta']}  CoE={bank['cost_of_equity_pct']}  "
        f"excess_ROE={bank['excess_roe_pp']}  justified_PB={bank['justified_pb']}")

    return {
        "ticker": ticker, "native_lens": native, "sector": yf.sector,
        "exchange": yf.exchange, "peak_warning": peak_warning,
        "rows": rows, "bank_instrument": bank,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase D-3 dark lens probe (read-only)")
    ap.add_argument("tickers", nargs="*", default=["MU", "GOOG", "V", "NOW", "WU"])
    ap.add_argument("--json")
    args = ap.parse_args()
    tickers = [t.upper() for t in (args.tickers or ["MU", "GOOG", "V", "NOW", "WU"])]

    def log(msg):
        print(msg, flush=True)

    log(f"[D-3 PROBE] live  {date.today().isoformat()}  tickers={','.join(tickers)}  "
        f"APPLIED=NOTHING  PERSISTED=NOTHING")
    fred = fetch_fred()
    r = fred.rate_10y
    log(f"[D-3 PROBE] FRED 10Y = {'unavailable' if r.is_missing() else f'{r.value:.2f}%'}"
        f"  conf={r.confidence}")

    results, failures = [], []
    for t in tickers:
        try:
            results.append(probe_ticker(t, fred, log))
        except Exception as e:
            log(f"  [D-3 PROBE] FAILED {t}: {type(e).__name__}: {e}")
            failures.append({"ticker": t, "error": f"{type(e).__name__}: {e}"})

    record = {
        "as_of": date.today().isoformat(),
        "rate_10y": None if r.is_missing() else r.value,
        "lens_metric_map": LENS_METRIC,
        "results": results, "failures": failures,
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, default=str)
        log(f"\n[D-3 PROBE] record → {args.json}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
