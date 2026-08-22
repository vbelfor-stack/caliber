"""L-4e(LLY) DARK DIFF part 2 — the FCF SERIES and the ARMED CROSS-CHECK surface.

Same in-memory spec substitution. Builds LLY's series through the SAME calls the writer
(tools/expand_fcf_series.build_one) makes, and computes the cross-check report both ways.
Nothing is written; compute_cross_check is pure and apply_report is never called.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

import adapters.edgar_adapter as ea
from adapters.fmp_adapter import fetch_fmp, fetch_splits
from core.corporate_actions import build_split_report
from core.fundamental_series import METRIC_FCF, PERIOD_FY, build_fcf_series
from core.edgar_cross_check import compute_cross_check

NEW_TAG = ("PaymentsToAcquireOtherPropertyPlantAndEquipment", "us-gaap")
TICKERS = sys.argv[1:] or ["LLY", "MU", "GOOGL", "C"]


def install_amended():
    specs = tuple(
        ea.FieldSpec("capex", "flow", s.synonyms + (NEW_TAG,), conflict_check=s.conflict_check)
        if s.name == "capex" else s
        for s in ea.FIELD_SPECS)
    ea.FIELD_SPECS = specs
    ea.XBRL_CONCEPTS = [syn for s in specs for syn in s.synonyms] + ea.CORPORATE_ACTION_CONCEPTS


def run(ticker, amended):
    yf = fetch_fmp(ticker)
    edgar = ea.fetch_edgar(ticker)
    splits = fetch_splits(ticker)
    report = (build_split_report(ticker, splits, edgar.financials)
              if splits is not None else None)
    res = build_fcf_series(ticker, edgar, yf.price_history, report)
    cc = compute_cross_check(edgar, yf)
    fy = sorted([p for p in res.points
                 if p.metric == METRIC_FCF and p.period_type == PERIOD_FY and p.value is not None],
                key=lambda p: p.period_end)
    verdicts = {c.label or c.fmp_field: c.verdict for c in cc.deltas}
    return {
        "rows": len(res.points), "basis": res.basis, "withheld": dict(res.withheld or {}),
        "fy_fcf": [(p.period_end, p.value) for p in fy],
        "verdicts": verdicts,
        "would_change": [(c.label or c.fmp_field) for c in cc.deltas if c.would_change],
        "fcf_note": next((f"{c.note} | edgar={c.edgar_value} fmp={c.fmp_value} div={c.divergence_pct}"
                          for c in cc.deltas
                          if (c.label or c.fmp_field) == "free_cashflow"), None),
    }


def main():
    print("=" * 96)
    print(f"  DARK SERIES BUILD — {'AMENDED (+OtherPP&E)' if AMEND else 'CURRENT'} spec")
    print("=" * 96)
    for t in TICKERS:
        try:
            r = run(t, AMEND)
        except Exception as e:                                   # noqa: BLE001
            print(f"  {t}: build_failed {type(e).__name__}: {e}")
            continue
        print(f"\n  {t}: rows={r['rows']} basis={r['basis']} withheld={r['withheld']}")
        print(f"      FY FCF points ({len(r['fy_fcf'])}): "
              + ", ".join(f"{d}={v/1e9:.3f}B" for d, v in r["fy_fcf"]))
        print(f"      step-4 gate (>=3 FY FCF pts): "
              f"{'PASS' if len(r['fy_fcf']) >= 3 else 'FAIL'}")
        print(f"      cross-check verdicts: "
              + ", ".join(f"{k}={v}" for k, v in sorted(r["verdicts"].items())))
        print(f"      free_cashflow note: {r['fcf_note']}")
        print(f"      comparisons that WOULD CHANGE confidence: {r['would_change'] or 'none'}")


if __name__ == "__main__":
    import os
    AMEND = os.environ.get("AMEND") == "1"
    if AMEND:
        install_amended()
    main()
