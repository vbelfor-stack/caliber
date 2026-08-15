"""
Phase H-1 measurement probe — READ-ONLY. Produces the gate evidence behind
docs/h1-series.md and nothing else.

    python -m tools.probe_fcf_series MU GOOG V NOW WU JPM BK USB C --json /tmp/h1.json

READ-ONLY BY CONSTRUCTION, on the D-0 precedent. H-1 makes the production series surface
a WRITER, which makes it more important, not less, that the measurement pass persists
nothing: this module imports the adapters directly and never imports batch.runner or
store.models, so no writer is reachable from here even by accident. Persistence is proven
separately by tests and by a batch run that NAMES ITS DESTINATION.

PER POINT, NEVER MEDIANS. Standing ruling from Phase G: a median comparison provably
passes a broken implementation — a naive split detector poisoned 2 of GOOG's 20 quarters
while moving the median only 4.43% -> 4.26%. Every quarter is printed.

Live-only by design: the FCF yield leg needs the FMP price history, and the split basis
needs the live split record.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from adapters.edgar_adapter import fetch_edgar
from adapters.fmp_adapter import fetch_fmp, fetch_splits
from core.corporate_actions import build_split_report
from core.fundamental_series import (
    ALL_METRICS,
    METRIC_FCF,
    METRIC_FCF_YIELD,
    PERIOD_FY,
    build_fcf_series,
)


def probe(ticker: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ticker": ticker}
    yf = fetch_fmp(ticker)
    edgar = fetch_edgar(ticker)
    splits = fetch_splits(ticker)
    # `splits is None` means UNKNOWN and must never be read as "never split" — the
    # restatement refuses and the truncated basis stands. Passed through as-is.
    report = (build_split_report(ticker, splits, edgar.financials)
              if splits is not None else None)

    result = build_fcf_series(ticker, edgar, yf.price_history, report)
    out["basis"] = result.basis
    out["withheld"] = result.withheld
    out["diagnostics"] = result.diagnostics

    metrics: Dict[str, Any] = {}
    for metric in ALL_METRICS:
        pts = result.by_metric(metric)
        if not pts:
            continue
        metrics[metric] = {
            "stored": len(pts),
            "fy_rows": sum(1 for p in pts if p.period_type == PERIOD_FY),
            "anchor_usable": len(result.anchor_usable(metric)),
            "excluded": result.excluded_count(metric),
            "points": [
                {"period_end": p.period_end, "period_type": p.period_type,
                 "value": p.value, "unit": p.unit, "basis": p.basis,
                 "excluded": p.excluded, "exclusion_reason": p.exclusion_reason,
                 "null_reason": p.null_reason, "components": p.components}
                for p in pts
            ],
        }
    out["metrics"] = metrics
    return out


def render(rec: Dict[str, Any]) -> str:
    lines = [f"\n=== {rec['ticker']}  basis={rec.get('basis')} ==="]
    if rec.get("withheld"):
        for k, v in rec["withheld"].items():
            lines.append(f"  WITHHELD {k}: {v}")
        return "\n".join(lines)
    for metric, m in rec["metrics"].items():
        lines.append(f"  {metric}  stored={m['stored']} (FY={m['fy_rows']})  "
                     f"anchor_usable={m['anchor_usable']}  excluded={m['excluded']}")
    # Per-point for the two legs the rulings bear on: FCF (the addendum's series) and
    # FCF yield (what H-3 would arm).
    for metric in (METRIC_FCF, METRIC_FCF_YIELD):
        m = rec["metrics"].get(metric)
        if not m:
            continue
        lines.append(f"  --- {metric} per point ---")
        for p in m["points"]:
            v = "—" if p["value"] is None else f"{p['value']:,.4f}"
            if p["excluded"]:
                tag = f"  EXCLUDED:{p['exclusion_reason']}"
            elif p.get("null_reason"):
                tag = f"  NULL:{p['null_reason']}"
            else:
                tag = ""
            lines.append(f"    {p['period_end']}  {p['period_type']:5s} {v:>22s}"
                         f"  {p['unit']}{tag}")
    lines.append(f"  diagnostics: {rec.get('diagnostics')}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="H-1 FCF series probe (READ-ONLY)")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()

    records: List[Dict[str, Any]] = []
    for t in args.tickers:
        try:
            rec = probe(t.upper())
        except Exception as e:                          # noqa: BLE001
            # LOUD FAILURE BEATS SILENT DEGRADATION: a ticker that could not be measured
            # is reported as such and never rendered as an empty series.
            rec = {"ticker": t.upper(), "error": f"{type(e).__name__}: {e}"}
            print(f"\n=== {t.upper()} === PROBE FAILED: {rec['error']}", file=sys.stderr)
            records.append(rec)
            continue
        records.append(rec)
        print(render(rec))

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(records, f, indent=2)
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
