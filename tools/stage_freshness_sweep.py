"""Stage-freshness sweep + the approval channel — Vic's ruling 2, 2026-08-28.

TWO MODES, AND THE DEFAULT IS READ-ONLY:

  (no flags)   SWEEP. Recompute every name whose classifier inputs are newer than its
               stored stage, and report `old → new` with the band consequence. WRITES
               NOTHING. This is the "run it once across the universe and report" step.

  --approve T  Record Vic's consent for ONE specific flip on ONE name. This is the only
               thing in the system that can unblock `guard_stage_write`, and it demands a
               rationale.

★ THE APPROVAL IS PER-TRANSITION, NOT PER-NAME. `stage_flip_approvals` is keyed on
(ticker, from_stage, to_stage), so approving MATURE → YOUNG does not also license a later
MATURE → DECLINE. A blanket per-name unlock would be an override in disguise, and an
override is a different claim: it says the classifier is WRONG, where an approval says the
classifier is RIGHT and may write.

WHY A SWEEP EXISTS AT ALL RATHER THAN JUST THE IN-RUN GUARD. The guard fires one name at a
time, inside an evaluation, where the operator is thinking about that name. The condition it
guards against is universe-wide and was created by orders that touched no evaluation:
measured 2026-08-28, EVERY stage row in the table predates its own inputs, because all 44
were written on 2026-08-17 and L-4c/L-4d/L-4f/L-4d.1 wrote series on 21–22 August. A guard
that can only be discovered one evaluation at a time would surface that over weeks.
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

from core.stage_freshness import band_consequence, freshness_for, stored_stage


def recompute(ticker: str, db_path: Path) -> Dict[str, Any]:
    """Recompute one name's stage from live inputs. PURE — persists nothing.

    Runs the SAME calls `evaluate._lifecycle_block` runs, in the same order, so a stage
    computed here cannot differ from one the evaluation path would have produced. Anything
    less would make the sweep's answer unfalsifiable.
    """
    import evaluate
    from adapters.edgar_adapter import fetch_edgar, instant_series
    from adapters.fmp_adapter import (fetch_dividends, fetch_fmp, fetch_income_annual)
    from core.lens_select import select_lens
    from core.lifecycle import build_legs, classify, lens_compatibility_flags
    from core.model_applicability import applicability_for

    yf = fetch_fmp(ticker)
    edgar = fetch_edgar(ticker)
    yf.sic = edgar.sic

    app = applicability_for(yf)
    if not app.applicable:
        # RULING 1 OUTRANKS RULING 2. A model-inapplicable name has no stage to be stale
        # about — the classifier does not run for it at all — so it is reported as gated
        # rather than recomputed. Reporting a recomputed stage here would resurrect exactly
        # the number ruling 1 exists to suppress.
        return {"ticker": ticker, "gated": True, "class": app.class_name}

    income = fetch_income_annual(ticker)
    if income is None:
        return {"ticker": ticker, "skipped": "income_annual UNKNOWN"}

    lens = select_lens(yf.sector, yf.industry, edgar.sic, ticker=ticker)
    shares = sorted([(r.period_end, r.value)
                     for r in instant_series(edgar.financials, "shares_outstanding")
                     if r.period_end and r.value]) or None
    legs = build_legs(
        ticker, income, lens,
        dividends=fetch_dividends(ticker),
        shares_series=shares,
        fcf_fy=evaluate._fy_series_from_db(db_path, ticker, "fcf"),
        sales_to_capital_fy=evaluate._fy_series_from_db(db_path, ticker,
                                                        "sales_to_capital"),
    )
    res = classify(ticker, legs, lens)
    res.flags.extend(lens_compatibility_flags(res.stage, lens))
    return {"ticker": ticker, "stage": res.stage, "rule": res.rule_fired,
            "lens": lens, "flags": sorted(res.flags)}


def sweep(tickers: List[str], db_path: Path) -> Dict[str, Any]:
    from store.models import get_stage_flip_approval

    stale, flips, gated, steady, skipped = [], [], [], [], []
    print("")
    print("=" * 92)
    print("  STAGE-FRESHNESS SWEEP — READ-ONLY. NOTHING IS PERSISTED BY THIS MODE.")
    print(f"  db: {db_path}")
    print("=" * 92)
    print(f"\n  {'ticker':8s} {'stored':10s} {'recomputed':11s} {'band':22s} verdict")
    print("  " + "-" * 88)

    for t in tickers:
        fresh = freshness_for(db_path, t)
        if not fresh.is_stale:
            continue
        stale.append(t)
        r = recompute(t, db_path)
        if r.get("gated"):
            gated.append(t)
            print(f"  {t:8s} {'-':10s} {'-':11s} {'-':22s} "
                  f"GATED by ruling 1 ({r['class']}) — no stage computed")
            continue
        if r.get("skipped"):
            skipped.append(t)
            print(f"  {t:8s} {'?':10s} {'?':11s} {'-':22s} SKIPPED — {r['skipped']}")
            continue
        old = stored_stage(db_path, t)
        new = r["stage"]
        band = band_consequence(db_path, old, new)
        if old == new:
            steady.append(t)
            print(f"  {t:8s} {str(old):10s} {new:11s} {band:22s} unchanged — safe to refresh")
        else:
            approved = get_stage_flip_approval(t, old, new, db_path=db_path) is not None
            flips.append({"ticker": t, "old": old, "new": new, "rule": r["rule"],
                          "band": band, "approved": approved, "flags": r["flags"]})
            print(f"  {t:8s} {str(old):10s} {new:11s} {band:22s} "
                  f"** FLIP ** ({r['rule']}) "
                  f"{'APPROVED' if approved else 'NEEDS VIC APPROVAL — HALTS'}")

    print("\n  " + "-" * 88)
    print(f"  stale (classifier inputs newer than stage) : {len(stale)} — {stale}")
    print(f"  gated by ruling 1 (no stage at all)        : {len(gated)} — {gated}")
    print(f"  recomputed to the SAME stage               : {len(steady)} — {steady}")
    print(f"  skipped (input unknown)                    : {len(skipped)} — {skipped}")
    print(f"  ** STAGE FLIPS **                          : {len(flips)}")
    for f in flips:
        print(f"       {f['ticker']}: {f['old']} → {f['new']}  band {f['band']}  "
              f"rule {f['rule']}  {'APPROVED' if f['approved'] else 'UNAPPROVED'}")
    unapproved = [f for f in flips if not f["approved"]]
    if unapproved:
        print("\n  ★★ NOTHING WAS PERSISTED. Each flip above needs Vic's approval, per name:")
        for f in unapproved:
            print(f"       python -m tools.stage_freshness_sweep --approve {f['ticker']} "
                  f"--rationale \"...\"")
    else:
        print("\n  No unapproved flips. Nothing requires a ruling.")
    print("=" * 92 + "\n")

    return {"stale": stale, "gated": gated, "steady": steady, "skipped": skipped,
            "flips": flips}


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Stage-freshness sweep (read-only) and the stage-flip approval channel")
    ap.add_argument("tickers", nargs="*",
                    help="Defaults to every ticker that has a stage row.")
    ap.add_argument("--db-path", dest="db_path", default=None,
                    help="Destination/source. Defaults to production caliber.db.")
    ap.add_argument("--approve", metavar="TICKER", default=None,
                    help="Record Vic's approval for one flip on this name. WRITES.")
    ap.add_argument("--rationale", default=None,
                    help="Mandatory with --approve.")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()

    from store.models import _DEFAULT_DB
    db = Path(args.db_path) if args.db_path is not None else _DEFAULT_DB

    if args.approve:
        t = args.approve.upper()
        old = stored_stage(db, t)
        r = recompute(t, db)
        if r.get("gated") or r.get("skipped"):
            print(f"  {t}: nothing to approve — {r}")
            sys.exit(2)
        new = r["stage"]
        if old == new:
            print(f"  {t}: stored and recomputed agree ({old}) — no flip to approve.")
            sys.exit(0)
        from store.models import save_stage_flip_approval
        rid = save_stage_flip_approval(t, old, new, args.rationale, db_path=db)
        print(f"  APPROVED {t}: {old} → {new}  (stage_flip_approvals id={rid})")
        print(f"  band consequence: {band_consequence(db, old, new)}")
        return

    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        import sqlite3
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        tickers = [r[0] for r in conn.execute(
            "SELECT DISTINCT ticker FROM lifecycle_stage ORDER BY ticker")]
        conn.close()

    out = sweep(tickers, db)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2, default=str))
        print(f"  wrote {args.json_out}")
    if [f for f in out["flips"] if not f["approved"]]:
        sys.exit(6)


if __name__ == "__main__":
    main()
