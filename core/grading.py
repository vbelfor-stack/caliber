"""
CALIBER v3 — Phase 5 grading.

Grades stored evaluations by comparing published E(R) against actual 90-day
forward return. Fetches actual prices from FMP historical-price-eod/full.
Price gaps raise PriceUnavailable (typed, reason-stamped) — never a silent None.

Grading rubric (applied to direction + magnitude; all comparisons on magnitude,
so the bands are symmetric for bullish (er > 0) and bearish (er < 0) calls):

  C  — conviction floor: |er| < 5%  → C regardless of the actual move
       (a weak-conviction call is an abstention, not a prediction)
       note: "[no-conviction E(R)]"
  C  — flat outcome:    |actual| < 5%  → C regardless of direction
       (only reached when |er| >= 5%; the market simply didn't move)
       note: "[flat outcome]"
  A  — direction correct AND |actual| >= |er| * 0.75
       (actual reached at least 75% of the predicted magnitude; this is a
        one-sided floor, not a +/-25% band — a larger-than-predicted move in
        the right direction also earns A, with no upper bound)
  B  — direction correct AND |actual| <  |er| * 0.75  (right direction, fell short)
  D  — direction wrong AND |actual| <  15%
  F  — direction wrong AND |actual| >= 15%

  The conviction floor is checked first, so it wins when a call is both
  weak-conviction and lands in a flat market; the note records which C it is.

  PENDING           — evaluation not yet 90 days old; no forward price yet
  PRICE_UNAVAILABLE — feed could not supply a price; note carries the reason
  N/A               — E(R) present but actual could not be computed (no eval-date price)

Confidence penalty:
  If verdict_conf == 'high' and grade in (D, F): note = "[ANTI-LAUNDER: high-conf miss]"
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from store.models import (
    _DEFAULT_DB, get_ungradeable_evals, list_evaluations,
    save_grade,
)


class PriceUnavailable(RuntimeError):
    """Raised when the FMP price feed cannot supply a close for (ticker, date).

    Carries a reason stamp; never swallowed into None. The batch runner
    (run_grading) catches this, persists a PRICE_UNAVAILABLE row, and continues.
    """


def assign_grade(
    er_published: Optional[float],
    actual_return: Optional[float],
) -> str:
    """Pure function: assign letter grade from E(R) and actual return (both in %).

    Magnitude-based (abs) comparisons throughout, so bands are symmetric for
    bullish and bearish calls. Both C rules use a 5% threshold; the conviction
    floor is checked first (see reason_for_grade for which C it is).
    """
    if er_published is None or actual_return is None:
        return "N/A"
    er = er_published
    act = actual_return
    # Both positive or both negative = same direction
    same_dir = (er >= 0 and act >= 0) or (er < 0 and act < 0)
    # Conviction floor: |E(R)| < 5% is a no-conviction abstention → C regardless of outcome.
    if abs(er) < 5.0:
        return "C"
    # Flat outcome: negligible actual move (< 5%) → C regardless of direction.
    if abs(act) < 5.0:
        return "C"
    if same_dir:
        if abs(act) >= abs(er) * 0.75:
            return "A"
        return "B"
    else:
        # Wrong direction — magnitude of the bad move drives F vs D
        if abs(act) >= 15.0:
            return "F"
        return "D"


def reason_for_grade(
    grade: str,
    er_published: Optional[float],
    actual_return: Optional[float],
    verdict_conf: Optional[str],
) -> str:
    """Return the note stamp explaining a grade.

    Distinguishes the two C flavours (conviction floor vs flat outcome, in the
    same order assign_grade applies them) and the anti-launder penalty.
    """
    if grade == "C":
        if er_published is not None and abs(er_published) < 5.0:
            return "[no-conviction E(R)]"
        return "[flat outcome]"
    if verdict_conf == "high" and grade in ("D", "F"):
        return "[ANTI-LAUNDER: high-conf miss]"
    return ""


def _fetch_price_at_date(ticker: str, target_date: datetime) -> float:
    """Fetch the FMP EOD close nearest to target_date.

    Raises PriceUnavailable (reason-stamped) on any gap: missing key, HTTP error,
    no rows in the window, or a null close. Never returns None.
    """
    import os
    from adapters.fmp_adapter import _get  # reuse the proven FMP HTTP layer

    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        raise PriceUnavailable(
            f"[grading] FMP_API_KEY not set — cannot price {ticker} @ {target_date:%Y-%m-%d}"
        )
    start = (target_date - timedelta(days=5)).strftime("%Y-%m-%d")
    end = (target_date + timedelta(days=5)).strftime("%Y-%m-%d")
    try:
        rows = _get(f"historical-price-eod/full?symbol={ticker}&from={start}&to={end}", key)
    except Exception as e:
        raise PriceUnavailable(
            f"[grading] FMP fetch failed for {ticker} @ {target_date:%Y-%m-%d}: "
            f"{type(e).__name__}: {e}"
        ) from e
    if not rows:
        raise PriceUnavailable(
            f"[grading] FMP returned no EOD rows for {ticker} in [{start}, {end}]"
        )
    target = target_date.replace(tzinfo=None)

    def _diff(r: dict) -> float:
        return abs((datetime.strptime(str(r["date"])[:10], "%Y-%m-%d") - target).total_seconds())

    closest = min(rows, key=_diff)
    close = closest.get("close")
    if close is None:
        raise PriceUnavailable(
            f"[grading] FMP row for {ticker} @ {closest.get('date')} has null close"
        )
    return float(close)


def grade_evaluation(
    eval_row: dict,
    price_at_90d: Optional[float] = None,
    db_path: Path = _DEFAULT_DB,
) -> dict:
    """
    Grade one evaluation. If price_at_90d is None, try to fetch it live.
    Returns the grade dict (and persists to DB).
    """
    eval_id = eval_row["id"]
    ticker = eval_row["ticker"]
    er = eval_row.get("expected_return")
    verdict_conf = eval_row.get("verdict_conf")
    eval_date_str = eval_row.get("run_at", "")

    # Parse eval date
    try:
        eval_dt = datetime.fromisoformat(eval_date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        eval_dt = None

    # Price at eval from synthesis_json
    price_at_eval: Optional[float] = None
    synth_raw = eval_row.get("synthesis_json")
    if synth_raw:
        try:
            sj = json.loads(synth_raw)
            price_at_eval = sj.get("current_price")
        except Exception:
            pass

    # Fetch price_at_90d if not provided
    if price_at_90d is None and eval_dt is not None:
        target_dt = eval_dt + timedelta(days=90)
        if target_dt > datetime.now(timezone.utc):
            # Not enough time has passed — persist a queryable PENDING row.
            # Retried once old enough (get_ungradeable_evals re-includes PENDING).
            note = "[pending: <90d]"
            save_grade(
                evaluation_id=eval_id, ticker=ticker, eval_date=eval_date_str[:10],
                er_published=er, verdict_conf=verdict_conf,
                price_at_eval=price_at_eval, price_at_90d=None, actual_return=None,
                grade="PENDING", note=note, db_path=db_path,
            )
            return {"evaluation_id": eval_id, "ticker": ticker, "grade": "PENDING",
                    "status": "pending", "note": note}
        # Raises PriceUnavailable on any gap — caught + persisted by run_grading.
        price_at_90d = _fetch_price_at_date(ticker, target_dt)

    # Compute actual return
    actual_return: Optional[float] = None
    if price_at_eval and price_at_90d and price_at_eval > 0:
        actual_return = (price_at_90d / price_at_eval - 1) * 100.0

    grade = assign_grade(er, actual_return)

    if grade == "N/A":
        # Persist a queryable N/A row: E(R) present but actual couldn't be computed
        # (no eval-date price in synthesis). Distinct from PENDING / PRICE_UNAVAILABLE.
        note = "[N/A: no E(R) or no eval-date price]"
        save_grade(
            evaluation_id=eval_id, ticker=ticker, eval_date=eval_date_str[:10],
            er_published=er, verdict_conf=verdict_conf,
            price_at_eval=price_at_eval, price_at_90d=price_at_90d,
            actual_return=actual_return, grade="N/A", note=note, db_path=db_path,
        )
        return {"evaluation_id": eval_id, "ticker": ticker, "grade": "N/A",
                "er_published": er, "actual_return": actual_return, "note": note}

    note = reason_for_grade(grade, er, actual_return, verdict_conf)

    save_grade(
        evaluation_id=eval_id,
        ticker=ticker,
        eval_date=eval_date_str[:10],
        er_published=er,
        verdict_conf=verdict_conf,
        price_at_eval=price_at_eval,
        price_at_90d=price_at_90d,
        actual_return=actual_return,
        grade=grade,
        note=note,
        db_path=db_path,
    )
    return {
        "evaluation_id": eval_id,
        "ticker": ticker,
        "er_published": er,
        "actual_return": actual_return,
        "grade": grade,
        "note": note,
    }


def run_grading(
    min_age_days: int = 90,
    db_path: Path = _DEFAULT_DB,
    verbose: bool = True,
) -> list:
    """Grade all ungraded evaluations that are old enough. Returns list of grade dicts."""
    pending = get_ungradeable_evals(min_age_days=min_age_days, db_path=db_path)
    if verbose:
        print(f"[grading] {len(pending)} evaluation(s) eligible for grading.")
    results = []
    for row in pending:
        try:
            result = grade_evaluation(row, db_path=db_path)
        except PriceUnavailable as e:
            # (ii) loud at the boundary, but the batch survives: persist a
            # reason-stamped PRICE_UNAVAILABLE row (retried next run) and continue.
            reason = str(e)
            save_grade(
                evaluation_id=row["id"], ticker=row["ticker"],
                eval_date=str(row.get("run_at", ""))[:10],
                er_published=row.get("expected_return"), verdict_conf=row.get("verdict_conf"),
                price_at_eval=None, price_at_90d=None, actual_return=None,
                grade="PRICE_UNAVAILABLE", note=reason, db_path=db_path,
            )
            if verbose:
                print(f"  {row['ticker']} #{row['id']}: PRICE_UNAVAILABLE — {reason}")
            results.append({"evaluation_id": row["id"], "ticker": row["ticker"],
                            "grade": "PRICE_UNAVAILABLE", "status": "price_unavailable",
                            "note": reason})
            continue
        if verbose:
            if result.get("status") == "pending":
                print(f"  {row['ticker']} #{row['id']}: PENDING (< {min_age_days}d)")
            else:
                print(f"  {row['ticker']} #{row['id']}: grade={result['grade']} "
                      f"er={result['er_published']} actual={result['actual_return']}")
        results.append(result)
    return results
