"""
CALIBER v3 — Phase 5 grading.

Grades stored evaluations by comparing published E(R) against actual 90-day
forward return. Fetches actual prices from yfinance history where available.

Grading rubric (applied to direction + magnitude):
  A  — direction correct AND actual >= er * 0.75  (within 25% of magnitude)
  B  — direction correct AND actual < er * 0.75   (right direction, lower magnitude)
  C  — flat outcome: |actual| < 5% regardless of er
  D  — direction wrong, loss < 15%
  F  — direction wrong, loss >= 15%

  PENDING — evaluation < 90 days old; no price data yet
  N/A     — evaluation has no E(R); cannot grade

Confidence penalty:
  If verdict_conf == 'high' and grade in (D, F): note += ' [ANTI-LAUNDER: high-conf miss]'
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


def assign_grade(
    er_published: Optional[float],
    actual_return: Optional[float],
) -> str:
    """Pure function: assign letter grade from E(R) and actual return (both in %)."""
    if er_published is None or actual_return is None:
        return "N/A"
    er = er_published
    act = actual_return
    # Both positive or both negative = same direction
    same_dir = (er >= 0 and act >= 0) or (er < 0 and act < 0)
    # Flat: truly negligible move (< 3%) — call it C regardless of direction
    if abs(act) < 3.0:
        return "C"
    if same_dir:
        if er != 0 and abs(act) >= abs(er) * 0.75:
            return "A"
        return "B"
    else:
        # Wrong direction — magnitude of the bad move drives F vs D
        if abs(act) >= 15.0:
            return "F"
        return "D"


def _fetch_price_at_date(ticker: str, target_date: datetime) -> Optional[float]:
    """Fetch the closing price nearest to target_date from yfinance."""
    try:
        import yfinance as yf
        start = (target_date - timedelta(days=5)).strftime("%Y-%m-%d")
        end = (target_date + timedelta(days=5)).strftime("%Y-%m-%d")
        hist = yf.Ticker(ticker).history(start=start, end=end)
        if hist.empty:
            return None
        # Pick the row closest to target_date
        target_ts = target_date.replace(tzinfo=None)
        hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
        diffs = [(abs((idx.to_pydatetime() - target_ts).total_seconds()), idx) for idx in hist.index]
        closest = min(diffs, key=lambda x: x[0])[1]
        return float(hist.loc[closest, "Close"])
    except Exception:
        return None


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
            # Not enough time has passed
            return {"status": "pending", "evaluation_id": eval_id}
        price_at_90d = _fetch_price_at_date(ticker, target_dt)

    # Compute actual return
    actual_return: Optional[float] = None
    if price_at_eval and price_at_90d and price_at_eval > 0:
        actual_return = (price_at_90d / price_at_eval - 1) * 100.0

    grade = assign_grade(er, actual_return)

    if grade == "N/A":
        return {"evaluation_id": eval_id, "ticker": ticker, "grade": "N/A",
                "er_published": er, "actual_return": actual_return, "note": ""}

    note = ""
    if verdict_conf == "high" and grade in ("D", "F"):
        note = "[ANTI-LAUNDER: high-conf miss]"

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
        result = grade_evaluation(row, db_path=db_path)
        if verbose:
            if result.get("status") == "pending":
                print(f"  {row['ticker']} #{row['id']}: PENDING (< {min_age_days}d)")
            else:
                print(f"  {row['ticker']} #{row['id']}: grade={result['grade']} "
                      f"er={result['er_published']} actual={result['actual_return']}")
        results.append(result)
    return results
