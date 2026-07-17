"""
Phase 5 gate: grading runs correctly against synthetic backdated rows.

Tests cover:
  - assign_grade() rubric (pure function, no DB)
  - grade_evaluation() with injected actual price (no live API)
  - Anti-launder note applied to high-conf D/F grades
  - N/A grade when E(R) is absent
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

import core.grading as grading
from core.grading import (
    PriceUnavailable, assign_grade, grade_evaluation, reason_for_grade, run_grading,
)
from store.models import init_db, save_grade, list_grades


# ── Pure rubric tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("er,actual,expected_grade", [
    # Direction correct, magnitude ≥75% → A
    (10.0,  10.0, "A"),
    (10.0,   8.0, "A"),   # 80% of er
    (-20.0, -16.0, "A"),  # bearish correct, |act|=16 >= |er|*0.75=15 → A
    # Direction correct, magnitude <75% → B
    (20.0,   5.0, "B"),
    (-10.0, -6.0, "B"),   # short correct, |act|=6 < |er|*0.75=7.5 → B
    # Flat outcome (|actual| < 5, and |er| >= 5) → C regardless of direction
    (20.0,   2.0, "C"),
    (-15.0,  1.0, "C"),
    (5.0,   -2.0, "C"),
    # Direction wrong, loss < 15% → D
    (10.0,  -5.0, "D"),
    (-5.0,   8.0, "D"),
    # Direction wrong, loss ≥ 15% → F
    (10.0, -20.0, "F"),
    (-5.0,  20.0, "F"),
    # Missing → N/A
    (None,  10.0, "N/A"),
    (10.0,  None, "N/A"),
    (None,  None, "N/A"),
])
def test_assign_grade_rubric(er, actual, expected_grade):
    assert assign_grade(er, actual) == expected_grade


# ── Flat-outcome C boundary at 5% (with strong conviction, |er| >= 5) ───────────

@pytest.mark.parametrize("er,actual,expected", [
    (10.0,  4.9, "C"),   # just inside flat band → C
    (10.0, -4.9, "C"),   # negative, just inside flat band → C
    (10.0,  5.0, "B"),   # exactly 5% is NOT flat; right dir, 5 < 7.5 → B
    (10.0,  5.1, "B"),   # just outside flat band → graded on magnitude
])
def test_flat_band_boundary_5pct(er, actual, expected):
    assert assign_grade(er, actual) == expected


# ── D/F boundary at 15% (wrong direction) ──────────────────────────────────────

@pytest.mark.parametrize("er,actual,expected", [
    (10.0, -14.9, "D"),   # wrong dir, just under 15% loss → D
    (10.0, -15.0, "F"),   # wrong dir, exactly 15% → F
    (10.0, -15.1, "F"),   # wrong dir, over 15% → F
    (-8.0,  14.9, "D"),   # bearish wrong, +14.9% → D
    (-8.0,  15.0, "F"),   # bearish wrong, +15% → F
])
def test_df_boundary_15pct(er, actual, expected):
    assert assign_grade(er, actual) == expected


# ── Conviction floor: |E(R)| < 5% → C regardless of the actual move ─────────────

@pytest.mark.parametrize("er,actual,expected", [
    (3.0,   50.0, "C"),   # weak conviction, huge move → still C (abstention)
    (-4.9, -30.0, "C"),   # weak bearish conviction, big drop → still C
    (4.99, 100.0, "C"),   # just under 5% conviction → C
    (0.0,   20.0, "C"),   # zero conviction → C
    (5.0,   10.0, "A"),   # exactly 5% conviction is NOT weak; right dir → A
])
def test_conviction_floor(er, actual, expected):
    assert assign_grade(er, actual) == expected


# ── Precedence when BOTH C triggers fire (|E(R)|<5% AND |actual|<5%) ────────────
# Locked decision: conviction floor is checked first, so the no-conviction label
# wins over the flat-outcome label. Assert grade C AND [no-conviction E(R)].

@pytest.mark.parametrize("er,actual", [
    (3.0,   2.0),   # weak conviction, flat outcome — both triggers fire
    (4.9,  -1.0),   # just-under-floor conviction, tiny down move
    (-2.0,  4.0),   # weak bearish conviction, small up move
    (0.0,   0.0),   # zero conviction, zero move
])
def test_both_c_triggers_conviction_wins(er, actual):
    grade = assign_grade(er, actual)
    assert grade == "C"
    note = reason_for_grade(grade, er, actual, "low")
    assert note == "[no-conviction E(R)]"
    assert note != "[flat outcome]"


# ── Negative-E(R) bearish calls grade symmetrically ────────────────────────────

@pytest.mark.parametrize("er,actual,expected", [
    (-20.0, -18.0, "A"),   # correct, |18| >= |20|*0.75=15 → A
    (-20.0, -10.0, "B"),   # correct dir, |10| < 15 → B
    (-20.0,  10.0, "D"),   # wrong dir, |10| < 15 → D
    (-20.0,  20.0, "F"),   # wrong dir, |20| >= 15 → F
])
def test_bearish_negative_er(er, actual, expected):
    assert assign_grade(er, actual) == expected


# ── reason_for_grade: the two C flavours + anti-launder are distinguishable ─────

def test_reason_two_c_flavours_and_antilaunder():
    # Weak conviction → no-conviction C (wins even if the market was also flat)
    assert reason_for_grade("C", 3.0, 1.0, "low") == "[no-conviction E(R)]"
    assert reason_for_grade("C", 3.0, 40.0, "low") == "[no-conviction E(R)]"
    # Strong conviction but flat market → flat-outcome C
    assert reason_for_grade("C", 10.0, 2.0, "medium") == "[flat outcome]"
    # Anti-launder penalty on high-conf misses
    assert reason_for_grade("F", 15.0, -22.0, "high") == "[ANTI-LAUNDER: high-conf miss]"
    assert reason_for_grade("D", 10.0, -8.0, "high") == "[ANTI-LAUNDER: high-conf miss]"
    # No note for a clean A
    assert reason_for_grade("A", 10.0, 12.0, "high") == ""


# ── grade_evaluation persists the correct C note end-to-end ────────────────────

def test_grade_evaluation_no_conviction_C_note():
    db = _make_test_db()
    eval_id = _insert_eval(db, "WEAK", er=3.0, verdict_conf="low", price_at_eval=100.0)
    row = {"id": eval_id, "ticker": "WEAK", "run_at": "2025-01-01T00:00:00",
           "expected_return": 3.0, "verdict_conf": "low",
           "synthesis_json": json.dumps({"current_price": 100.0})}
    # Stock ripped +40%, but the call had no conviction → C (no-conviction)
    result = grade_evaluation(row, price_at_90d=140.0, db_path=db)
    assert result["grade"] == "C"
    assert result["note"] == "[no-conviction E(R)]"
    assert list_grades(db_path=db)[0]["note"] == "[no-conviction E(R)]"


def test_grade_evaluation_flat_C_note():
    db = _make_test_db()
    eval_id = _insert_eval(db, "FLAT", er=15.0, verdict_conf="medium", price_at_eval=100.0)
    row = {"id": eval_id, "ticker": "FLAT", "run_at": "2025-01-01T00:00:00",
           "expected_return": 15.0, "verdict_conf": "medium",
           "synthesis_json": json.dumps({"current_price": 100.0})}
    # Strong conviction, but the stock barely moved (+2%) → C (flat outcome)
    result = grade_evaluation(row, price_at_90d=102.0, db_path=db)
    assert result["grade"] == "C"
    assert result["note"] == "[flat outcome]"


# ── Graded outcome using an FMP-fetched 90-day price (feed mocked, no network) ──

def test_grade_evaluation_fetches_from_fmp(monkeypatch):
    db = _make_test_db()
    eval_id = _insert_eval(db, "FMPX", er=10.0, verdict_conf="medium",
                           price_at_eval=100.0, run_at="2025-01-01T00:00:00+00:00")
    row = {"id": eval_id, "ticker": "FMPX", "run_at": "2025-01-01T00:00:00+00:00",
           "expected_return": 10.0, "verdict_conf": "medium",
           "synthesis_json": json.dumps({"current_price": 100.0})}

    # Stand in for the FMP HTTP layer: EOD rows around the 90-day target.
    def fake_get(endpoint, key):
        assert "historical-price-eod/full" in endpoint
        # 90-day target is 2025-04-01; the exact-date row (112.0) must be chosen
        return [{"date": "2025-03-30", "close": 108.0},
                {"date": "2025-04-01", "close": 112.0}]

    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr("adapters.fmp_adapter._get", fake_get)

    # No price_at_90d passed → must fetch via FMP; +12% vs er 10% → A
    result = grade_evaluation(row, db_path=db)
    assert result["grade"] == "A"
    assert abs(result["actual_return"] - 12.0) < 0.01


# ── Feed down → typed loud failure, batch persists PRICE_UNAVAILABLE + retries ──

def test_price_unavailable_raises_and_batch_persists(monkeypatch):
    db = _make_test_db()
    eval_id = _insert_eval(db, "DOWN", er=10.0, verdict_conf="medium",
                           price_at_eval=100.0, run_at="2025-01-01T00:00:00+00:00")
    row = {"id": eval_id, "ticker": "DOWN", "run_at": "2025-01-01T00:00:00+00:00",
           "expected_return": 10.0, "verdict_conf": "medium",
           "synthesis_json": json.dumps({"current_price": 100.0})}

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    # grade_evaluation is loud: it raises rather than returning a silent None
    with pytest.raises(PriceUnavailable):
        grade_evaluation(row, db_path=db)

    # The batch runner catches it, records a reason-stamped row, and survives
    results = run_grading(min_age_days=90, db_path=db, verbose=False)
    assert any(r.get("grade") == "PRICE_UNAVAILABLE" for r in results)
    grades = list_grades(db_path=db)
    assert grades[0]["grade"] == "PRICE_UNAVAILABLE"
    assert "FMP_API_KEY not set" in grades[0]["note"]


# ── grade_evaluation() with synthetic DB rows ──────────────────────────────────

def _make_test_db() -> Path:
    """Return path to a fresh temp DB with tables created."""
    tmp = Path(tempfile.mkdtemp()) / "test_grading.db"
    init_db(tmp)
    return tmp


def _insert_eval(db_path: Path, ticker: str, er: float, verdict_conf: str,
                 price_at_eval: float, run_at: str = "2025-01-01T00:00:00") -> int:
    """Insert a minimal synthetic evaluation row. Returns eval id."""
    synth_json = json.dumps({"current_price": price_at_eval})
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """INSERT INTO evaluations
           (ticker, run_at, lens, status, pillars_json, synthesis_json,
            avg_score, overall_conf, verdict_conf, expected_return)
           VALUES (?, ?, 'standard', 'ok', '[]', ?, 3.5, 'medium', ?, ?)""",
        (ticker, run_at, synth_json, verdict_conf, er),
    )
    conn.commit()
    eval_id = cur.lastrowid
    conn.close()
    return eval_id


# ── Scenario A: bull thesis pays off ──────────────────────────────────────────

def test_grade_evaluation_A():
    db = _make_test_db()
    eval_id = _insert_eval(db, "TST", er=12.0, verdict_conf="medium",
                           price_at_eval=100.0)
    row = {"id": eval_id, "ticker": "TST", "run_at": "2025-01-01T00:00:00",
           "expected_return": 12.0, "verdict_conf": "medium", "synthesis_json":
           json.dumps({"current_price": 100.0})}

    result = grade_evaluation(row, price_at_90d=115.0, db_path=db)

    assert result["grade"] == "A"
    assert abs(result["actual_return"] - 15.0) < 0.01
    grades = list_grades(db_path=db)
    assert len(grades) == 1
    assert grades[0]["grade"] == "A"
    assert grades[0]["ticker"] == "TST"


# ── Scenario B: direction right but small gain ─────────────────────────────────

def test_grade_evaluation_B():
    db = _make_test_db()
    eval_id = _insert_eval(db, "TST2", er=20.0, verdict_conf="medium",
                           price_at_eval=100.0)
    row = {"id": eval_id, "ticker": "TST2", "run_at": "2025-01-01T00:00:00",
           "expected_return": 20.0, "verdict_conf": "medium",
           "synthesis_json": json.dumps({"current_price": 100.0})}

    result = grade_evaluation(row, price_at_90d=108.0, db_path=db)  # +8%, er=20% → B

    assert result["grade"] == "B"


# ── Scenario F with high-conf anti-launder note ───────────────────────────────

def test_grade_evaluation_F_antilaunder():
    db = _make_test_db()
    eval_id = _insert_eval(db, "WRNG", er=15.0, verdict_conf="high",
                           price_at_eval=100.0)
    row = {"id": eval_id, "ticker": "WRNG", "run_at": "2025-01-01T00:00:00",
           "expected_return": 15.0, "verdict_conf": "high",
           "synthesis_json": json.dumps({"current_price": 100.0})}

    result = grade_evaluation(row, price_at_90d=78.0, db_path=db)  # -22% → F

    assert result["grade"] == "F"
    assert "ANTI-LAUNDER" in result["note"]
    grades = list_grades(db_path=db)
    assert "ANTI-LAUNDER" in grades[0]["note"]


# ── Scenario D: direction wrong, moderate loss ────────────────────────────────

def test_grade_evaluation_D():
    db = _make_test_db()
    eval_id = _insert_eval(db, "TST3", er=10.0, verdict_conf="medium",
                           price_at_eval=50.0)
    row = {"id": eval_id, "ticker": "TST3", "run_at": "2025-01-01T00:00:00",
           "expected_return": 10.0, "verdict_conf": "medium",
           "synthesis_json": json.dumps({"current_price": 50.0})}

    result = grade_evaluation(row, price_at_90d=44.0, db_path=db)  # -12% → D

    assert result["grade"] == "D"
    assert "ANTI-LAUNDER" not in result["note"]  # medium conf, no penalty


# ── N/A when E(R) is missing ──────────────────────────────────────────────────

def test_grade_evaluation_no_er():
    db = _make_test_db()
    eval_id = _insert_eval(db, "NOER", er=None, verdict_conf="medium", price_at_eval=100.0)
    row = {"id": eval_id, "ticker": "NOER", "run_at": "2025-01-01T00:00:00",
           "expected_return": None, "verdict_conf": "medium",
           "synthesis_json": json.dumps({"current_price": 100.0})}

    result = grade_evaluation(row, price_at_90d=110.0, db_path=db)

    assert result["grade"] == "N/A"
    # N/A is now a persisted, queryable outcome (not a silent drop)
    assert list_grades(db_path=db)[0]["grade"] == "N/A"


# ── Multiple grades persist and are retrievable ───────────────────────────────

def test_list_grades_multiple():
    db = _make_test_db()
    for i, (er, p90, expected) in enumerate([
        (10.0, 115.0, "A"),   # +15% vs er 10 → A
        (20.0, 107.0, "B"),   # +7% vs er 20 → B
        (10.0,  82.0, "F"),   # -18% vs er 10 → F
    ]):
        eval_id = _insert_eval(db, f"T{i}", er=er, verdict_conf="medium",
                               price_at_eval=100.0, run_at=f"2025-0{i+1}-01T00:00:00")
        row = {"id": eval_id, "ticker": f"T{i}", "run_at": f"2025-0{i+1}-01T00:00:00",
               "expected_return": er, "verdict_conf": "medium",
               "synthesis_json": json.dumps({"current_price": 100.0})}
        result = grade_evaluation(row, price_at_90d=p90, db_path=db)
        assert result["grade"] == expected, f"T{i}: expected {expected} got {result['grade']}"

    grades = list_grades(db_path=db)
    assert len(grades) == 3
    grade_set = {g["grade"] for g in grades}
    assert grade_set == {"A", "B", "F"}
