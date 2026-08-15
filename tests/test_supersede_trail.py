"""
Guard tests for the evaluations supersede trail (ruled 2026-08-15).

The ruling: two nullable columns, additive, existing rows read NULL, and a row may
not supersede a nonexistent id / supersedes_id requires supersede_reason non-null.

WHY THESE ARE GUARDS AND NOT COVERAGE. The trail is the ONLY thing that will ever
explain why two evaluations of the same ticker on the same day disagree. A link that
points nowhere, or one with no stated reason, is worse than no link: it reads as
provenance to a future consumer while carrying none.
"""
from __future__ import annotations

import sqlite3

import pytest

from adapters.base import PillarResult
from store.models import (
    SupersedeLinkInvalid,
    init_db,
    save_evaluation,
    _EVALUATIONS_ADDED_COLUMNS,
    _ensure_columns,
)


def _pillars():
    return [PillarResult(name="Valuation", score=3, confidence="medium",
                         rationale="test", flags=[], method="test", key_inputs=[])]


def _save(db, **kw):
    return save_evaluation("MU", "cyclical", _pillars(), None, db_path=db, **kw)


def _cols(db):
    with sqlite3.connect(db) as c:
        return [r[1] for r in c.execute("PRAGMA table_info(evaluations)")]


# ── the columns exist, and are additive ──────────────────────────────────────

def test_both_columns_exist_on_a_fresh_db(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    cols = _cols(db)
    assert "supersedes_id" in cols
    assert "supersede_reason" in cols


def test_an_ordinary_evaluation_reads_null_on_both(tmp_path):
    db = tmp_path / "t.db"
    eid = _save(db)
    with sqlite3.connect(db) as c:
        row = c.execute(
            "SELECT supersedes_id, supersede_reason FROM evaluations WHERE id=?", (eid,)
        ).fetchone()
    assert row == (None, None)


def test_the_migration_adds_the_columns_to_a_PREEXISTING_table_without_touching_rows(tmp_path):
    """The production case: a DB whose evaluations table predates the columns.

    Pinned because the ruling is explicitly 'additive, no migration of existing rows'.
    An ALTER that rewrote or dropped a row would be a data-loss event on caliber.db.
    """
    db = tmp_path / "legacy.db"
    with sqlite3.connect(db) as c:
        c.execute("""
            CREATE TABLE evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL, run_at TEXT NOT NULL, lens TEXT,
                status TEXT NOT NULL DEFAULT 'ok', error_msg TEXT,
                pillars_json TEXT, synthesis_json TEXT, avg_score REAL,
                overall_conf TEXT, verdict_conf TEXT, expected_return REAL
            )""")
        c.execute("INSERT INTO evaluations (ticker, run_at, avg_score) VALUES ('MU','x',4.2)")

    init_db(db)

    with sqlite3.connect(db) as c:
        rows = c.execute(
            "SELECT ticker, avg_score, supersedes_id, supersede_reason FROM evaluations"
        ).fetchall()
    assert rows == [("MU", 4.2, None, None)], "pre-existing row must survive verbatim, NULL on the new columns"


def test_the_migration_is_idempotent(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    eid = _save(db, supersedes_id=None)
    init_db(db)   # second call must not raise (duplicate column) or disturb anything
    init_db(db)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 1
        assert c.execute("SELECT id FROM evaluations").fetchone()[0] == eid


def test_ensure_columns_reports_what_it_added_and_then_nothing(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row
        assert _ensure_columns(c, "evaluations", _EVALUATIONS_ADDED_COLUMNS) == []


# ── guard 1: may not supersede a nonexistent id ──────────────────────────────

def test_a_row_may_not_supersede_a_nonexistent_id(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    with pytest.raises(SupersedeLinkInvalid) as e:
        _save(db, supersedes_id=9999, supersede_reason="defect fix")
    assert "9999" in str(e.value)


def test_the_refused_link_writes_NOTHING(tmp_path):
    """A refusal must not leave a partial row behind — the check runs before the insert."""
    db = tmp_path / "t.db"
    init_db(db)
    with pytest.raises(SupersedeLinkInvalid):
        _save(db, supersedes_id=9999, supersede_reason="defect fix")
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0


# ── guard 2: supersedes_id requires supersede_reason ─────────────────────────

def test_supersedes_id_requires_a_reason(tmp_path):
    db = tmp_path / "t.db"
    first = _save(db)
    with pytest.raises(SupersedeLinkInvalid) as e:
        _save(db, supersedes_id=first)
    assert "supersede_reason" in str(e.value)


def test_an_empty_or_whitespace_reason_is_not_a_reason(tmp_path):
    db = tmp_path / "t.db"
    first = _save(db)
    for blank in ("", "   ", "\n"):
        with pytest.raises(SupersedeLinkInvalid):
            _save(db, supersedes_id=first, supersede_reason=blank)


def test_a_reason_with_no_id_is_refused(tmp_path):
    """CODE'S ADDITION, not part of the ruling — disclosed for Vic to strike or keep.

    A reason naming no row is unqueryable noise that still reads as provenance.
    """
    db = tmp_path / "t.db"
    init_db(db)
    with pytest.raises(SupersedeLinkInvalid):
        _save(db, supersede_reason="defect fix")


# ── the happy path ───────────────────────────────────────────────────────────

def test_a_valid_link_persists_and_leaves_the_superseded_row_untouched(tmp_path):
    db = tmp_path / "t.db"
    old = _save(db)
    with sqlite3.connect(db) as c:
        before = c.execute("SELECT * FROM evaluations WHERE id=?", (old,)).fetchone()

    new = _save(db, supersedes_id=old, supersede_reason="debt/equity units defect (8d9aa95)")

    with sqlite3.connect(db) as c:
        after = c.execute("SELECT * FROM evaluations WHERE id=?", (old,)).fetchone()
        link = c.execute(
            "SELECT supersedes_id, supersede_reason FROM evaluations WHERE id=?", (new,)
        ).fetchone()

    assert new != old
    assert after == before, "superseding APPENDS — the superseded row is never edited"
    assert link == (old, "debt/equity units defect (8d9aa95)")


def test_the_foreign_key_is_the_db_level_backstop(tmp_path):
    """Belt and braces: even bypassing _validate_supersede_link, the FK refuses."""
    db = tmp_path / "t.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO evaluations (ticker, run_at, supersedes_id, supersede_reason) "
            "VALUES ('MU','x',9999,'r')"
        )
        conn.commit()
    conn.close()
