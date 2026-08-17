"""
Held universe vs calibration universe (ruled 2026-08-17).

THE RULING IN ONE LINE: calibration instruments ARE graded, because a bank E(R) is evidence
about the bank lens — the newest and least-proven one — and excluding the only four names
that exercise it would leave D-6 permanently ungradeable. What they may never do is appear
in anything that ranks or recommends holdings.

So there are two separate properties to hold, and they pull in opposite directions:
  1. GRADING ADMITS EVERYTHING. run_grading must not learn to skip these rows.
  2. THE RECOMMENDATION LAYER ADMITS NOTHING FLAGGED. The firewall sits there, not in
     grading, and the flag is what makes the two populations sliceable — a blended accuracy
     number would mislead in both directions.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adapters.base import PillarResult
from core.universe import DEFAULT_UNIVERSE, held_universe, is_calibration_instrument
from store.models import _EVALUATIONS_ADDED_COLUMNS, init_db, save_evaluation

CALIBRATION_BANKS = ("JPM", "BK", "USB", "C")


def _pillars():
    return [PillarResult(name="Valuation", score=3, confidence="medium",
                         rationale="test", flags=[], method="test", key_inputs=[])]


# ── membership resolution ─────────────────────────────────────────────────────

def test_the_held_universe_is_read_from_tickers_txt():
    names = held_universe()
    assert names, "the universe file resolved empty — everything would read calibration"
    assert all(n == n.upper() for n in names)


def test_the_four_calibration_banks_are_not_in_the_held_universe():
    """The D-5/D-6 pin, restated at the membership layer: absent from tickers.txt on
    purpose, so the flag catches them without anyone maintaining a second list."""
    held = set(held_universe())
    for bank in CALIBRATION_BANKS:
        assert bank not in held, f"{bank} is a calibration instrument, never a holding"
        assert is_calibration_instrument(bank)


def test_a_held_name_is_not_flagged():
    for t in held_universe():
        assert not is_calibration_instrument(t)


def test_membership_comes_from_ONE_list_not_a_hardcoded_bank_set():
    """If the flag were a hardcoded list of banks it would silently mis-file the next
    calibration name added. Anything absent from the file is calibration."""
    assert is_calibration_instrument("SOME-NEW-CALIBRATION-NAME")


def test_an_unreadable_universe_fails_toward_calibration(tmp_path):
    """FAIL DIRECTION IS PROTECTIVE. The consequence of the flag is exclusion from
    recommendations, so a missing file must mark everything calibration — withholding a
    recommendation rather than manufacturing one."""
    missing = tmp_path / "nope.txt"
    assert held_universe(missing) == []
    assert is_calibration_instrument("MU", missing)


def test_comments_and_blanks_in_the_universe_file_are_ignored(tmp_path):
    f = tmp_path / "tickers.txt"
    f.write_text("# a comment\n\nMU\n  GOOG  # trailing comment\n\n", encoding="utf-8")
    assert held_universe(f) == ["MU", "GOOG"]


# ── the column, and what NULL means ───────────────────────────────────────────

def test_the_column_is_additive_and_existing_rows_read_NULL(tmp_path):
    """Rows written before the column read NULL = MEMBERSHIP UNRECORDED, which is
    deliberately NOT the same as 0 (=held). A rollup that treats NULL as held would file
    every pre-ruling bank row into the held population."""
    assert "calibration_instrument" in _EVALUATIONS_ADDED_COLUMNS
    db = tmp_path / "t.db"
    init_db(db)
    eid = save_evaluation("MU", "cyclical", _pillars(), None, db_path=db)
    conn = sqlite3.connect(db)
    got = conn.execute("SELECT calibration_instrument FROM evaluations WHERE id=?",
                       (eid,)).fetchone()[0]
    conn.close()
    assert got is None, "an unspecified write must record NULL, not a guess"


@pytest.mark.parametrize("ticker,expected", [("JPM", 1), ("MU", 0)])
def test_the_flag_is_stored_at_write_time(tmp_path, ticker, expected):
    db = tmp_path / "t.db"
    init_db(db)
    eid = save_evaluation(ticker, "bank", _pillars(), None, db_path=db,
                          calibration_instrument=is_calibration_instrument(ticker))
    conn = sqlite3.connect(db)
    got = conn.execute("SELECT calibration_instrument FROM evaluations WHERE id=?",
                       (eid,)).fetchone()[0]
    conn.close()
    assert got == expected


def test_membership_is_stored_not_re_derived_at_read_time(tmp_path, monkeypatch):
    """A grade rollup six months out must know what the name was WHEN IT WAS EVALUATED, not
    what tickers.txt says when the query runs. Stored beats derived."""
    db = tmp_path / "t.db"
    init_db(db)
    eid = save_evaluation("JPM", "bank", _pillars(), None, db_path=db,
                         calibration_instrument=True)
    # JPM is later promoted to a holding; the historical row must not change its story.
    later = tmp_path / "tickers.txt"
    later.write_text("MU\nJPM\n", encoding="utf-8")
    assert not is_calibration_instrument("JPM", later)          # true of TODAY
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT calibration_instrument FROM evaluations WHERE id=?",
                        (eid,)).fetchone()[0] == 1              # unchanged history
    conn.close()


# ── property 1: grading admits everything ─────────────────────────────────────

def test_grading_eligibility_does_NOT_filter_calibration_rows():
    """Ruled: run_grading grades them normally. If someone later adds a
    calibration_instrument filter to the eligibility query, D-6 becomes ungradeable and
    this test is how we find out."""
    src = Path("core/grading.py").read_text(encoding="utf-8")
    assert "calibration_instrument" not in src, (
        "grading learned to skip calibration rows — the firewall belongs at the "
        "recommendation layer, not here")


# ── property 2: the recommendation-layer firewall ─────────────────────────────

def test_no_output_surface_ranks_or_recommends_HOLDINGS_yet():
    """THE FIREWALL PIN, and it is a pin that is EXPECTED TO FLIP.

    Ruled: no calibration-flagged name may appear in any output that ranks or recommends
    holdings. Today CALIBER has no such surface — evaluate.py prints one ticker at a time,
    batch prints a per-ticker summary table, and the web app shows single evaluations. There
    is therefore nothing to filter, and asserting a filter exists would be theatre.

    So this pins the PRECONDITION instead: the moment a ranking or recommendation surface is
    built, this test fails, and the fix is to add the calibration filter to it rather than to
    delete this test. The failure IS the reminder.
    """
    forbidden = ("def rank_holdings", "def recommend", "def top_picks", "def shortlist",
                 "ORDER BY expected_return", "order_by(expected_return")
    for path in ("evaluate.py", "batch/runner.py", "web/app.py", "core/grading.py",
                 "store/models.py"):
        src = Path(path).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in src, (
                f"{path} contains {token!r} — a holdings-ranking surface now exists and it "
                f"MUST exclude rows with calibration_instrument=1 before this test is "
                f"changed")


def test_the_two_populations_are_sliceable(tmp_path):
    """The whole point of the flag: held vs calibration accuracy queried apart. A blended
    number would let a calibration miss discredit the held universe and let held hits
    flatter an unproven lens."""
    db = tmp_path / "t.db"
    init_db(db)
    for t in ("MU", "GOOG"):
        save_evaluation(t, "compounder", _pillars(), None, db_path=db,
                        calibration_instrument=False)
    for t in CALIBRATION_BANKS:
        save_evaluation(t, "bank", _pillars(), None, db_path=db,
                        calibration_instrument=True)
    conn = sqlite3.connect(db)
    held = conn.execute("SELECT COUNT(*) FROM evaluations "
                        "WHERE calibration_instrument=0").fetchone()[0]
    calib = conn.execute("SELECT COUNT(*) FROM evaluations "
                         "WHERE calibration_instrument=1").fetchone()[0]
    unrecorded = conn.execute("SELECT COUNT(*) FROM evaluations "
                              "WHERE calibration_instrument IS NULL").fetchone()[0]
    conn.close()
    assert (held, calib, unrecorded) == (2, 4, 0)
