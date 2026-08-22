"""L-4e(LLY) DARK DIFF — measurement only. Nothing here writes, and no source file is
modified: the amended FieldSpec is substituted IN MEMORY so the real resolver is measured
rather than a re-implementation (same method as the L-4d step-2 dark diff).

Adds ("PaymentsToAcquireOtherPropertyPlantAndEquipment", "us-gaap") as the THIRD entry of
the capex chain, behind the two armed tags, per the Vic ruling of 2026-08-21.
"""
from __future__ import annotations

import json
import sys
import time
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

NEW_TAG = ("PaymentsToAcquireOtherPropertyPlantAndEquipment", "us-gaap")

UNIVERSE = ["BE", "CAT", "DPC", "GOOGL", "LLY", "NVDA", "RKLB", "SPCX", "V", "XE", "IONQ",
            "ARM", "CBRS", "FN", "INFQ", "LITE", "LRCX", "MU", "QBTS", "SKHY", "STX",
            "GOOG", "NOW", "WU", "JPM", "BK", "USB", "C"]

CACHE = Path(__file__).parent / "facts"
CACHE.mkdir(exist_ok=True)


def companyfacts(ticker: str):
    p = CACHE / f"{ticker}.json"
    if p.exists():
        return json.loads(p.read_text())
    cik = ea._get_cik(ticker)
    time.sleep(0.35)
    cf = ea._fetch_companyfacts(cik)
    p.write_text(json.dumps(cf) if cf is not None else "null")
    return cf


def amended_specs():
    out = []
    for spec in ea.FIELD_SPECS:
        if spec.name == "capex":
            out.append(ea.FieldSpec("capex", "flow", spec.synonyms + (NEW_TAG,),
                                    conflict_check=spec.conflict_check))
        else:
            out.append(spec)
    return tuple(out)


def extract_under(specs, cf):
    """Run the real extraction+resolution with `specs` installed."""
    orig_specs, orig_concepts = ea.FIELD_SPECS, ea.XBRL_CONCEPTS
    ea.FIELD_SPECS = specs
    ea.XBRL_CONCEPTS = [syn for s in specs for syn in s.synonyms] + ea.CORPORATE_ACTION_CONCEPTS
    try:
        return ea._extract_xbrl_facts(cf) if cf else ea.EdgarFinancials()
    finally:
        ea.FIELD_SPECS, ea.XBRL_CONCEPTS = orig_specs, orig_concepts


def cell(rf):
    if rf is None:
        return ("<absent>", None, None)
    return (rf.reason or "resolved", rf.value, rf.concept)


def main():
    amended = amended_specs()
    names = [s.name for s in ea.FIELD_SPECS]

    print("=" * 96)
    print("  L-4e(LLY) DARK DIFF — +PaymentsToAcquireOtherPropertyPlantAndEquipment (3rd in chain)")
    print("=" * 96)

    moved, noncapex_changes, resolved_counts = [], 0, {}
    for t in UNIVERSE:
        cf = companyfacts(t)
        base = extract_under(ea.FIELD_SPECS, cf)
        amd = extract_under(amended, cf)
        rb = sum(1 for n in names if base.fields.get(n) and base.fields[n].is_resolved())
        ra = sum(1 for n in names if amd.fields.get(n) and amd.fields[n].is_resolved())
        resolved_counts[t] = (rb, ra)
        for n in names:
            b, a = cell(base.fields.get(n)), cell(amd.fields.get(n))
            if b != a:
                if n != "capex":
                    noncapex_changes += 1
                moved.append((t, n, b, a))

    print(f"\n  {'ticker':7s} {'field':10s} {'BEFORE':>46s}   ->  AFTER")
    print("  " + "-" * 94)
    for t, n, b, a in moved:
        fb = f"{b[0]}/{b[1]}/{b[2]}"
        fa = f"{a[0]}/{a[1]}/{a[2]}"
        print(f"  {t:7s} {n:10s} {fb:>46s}   ->  {fa}")
    if not moved:
        print("  (no field on any name moves)")

    print(f"\n  NON-CAPEX FIELD CHANGES ACROSS ALL 28 NAMES: {noncapex_changes}")
    print("  RESOLVED-FIELD COUNT CHANGES:",
          ", ".join(f"{t} {b}->{a}" for t, (b, a) in resolved_counts.items() if b != a) or "none")
    print("  names whose resolved count is unchanged:",
          sum(1 for b, a in resolved_counts.values() if b == a), "of", len(UNIVERSE))

    # ── Q2 regression question: does any name file MORE THAN ONE chain tag fresh? ──
    print("\n  RAW-FACTS SWEEP — who files the new tag, and is the conflict path reachable?")
    chain = [c for c, _ in amended[[s.name for s in amended].index("capex")].synonyms]
    for t in UNIVERSE:
        cf = companyfacts(t)
        fin = extract_under(amended, cf)
        lpe = fin.latest_period_end
        rows = []
        for c in chain:
            recs = fin.concepts.get(c)
            if not recs:
                continue
            newest = max(r["end"] for r in recs if r["end"])
            lag = ea._days_between(newest, lpe)
            rows.append(f"{c[19:39]}…={newest}({lag}d,{'FRESH' if lag is not None and lag <= ea.STALE_TAG_DAYS else 'STALE'})")
        fresh = sum(1 for r in rows if "FRESH" in r)
        if rows and (fresh > 1 or NEW_TAG[0] in fin.concepts):
            print(f"   {t:7s} freshtags={fresh}  " + " | ".join(rows))
    print("\n  (a name is listed only if it files the NEW tag or has >1 fresh chain tag)")


if __name__ == "__main__":
    main()
