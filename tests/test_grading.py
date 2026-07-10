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

from core.grading import assign_grade, grade_evaluation
from store.models import init_db, save_grade, list_grades


# ── Pure rubric tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("er,actual,expected_grade", [
    # Direction correct, magnitude ≥75% → A
    (10.0,  10.0, "A"),
    (10.0,   8.0, "A"),   # 80% of er
    (-5.0,  -4.0, "A"),   # short correct, |act|=4 >= |er|*0.75=3.75 → A
    # Direction correct, magnitude <75% → B
    (20.0,   5.0, "B"),
    (-10.0, -6.0, "B"),   # short correct, |act|=6 < |er|*0.75=7.5 → B
    # Flat outcome (|actual| < 3) → C regardless
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
    row = {"id": 99, "ticker": "NOER", "run_at": "2025-01-01T00:00:00",
           "expected_return": None, "verdict_conf": "medium",
           "synthesis_json": json.dumps({"current_price": 100.0})}

    result = grade_evaluation(row, price_at_90d=110.0, db_path=db)

    assert result["grade"] == "N/A"


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
