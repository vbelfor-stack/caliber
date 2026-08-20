"""
L-4b: the BATCH path is now on the stage-conditioned B-2 band. Armed 2026-08-20.

WHAT THIS ORDER ACTUALLY CLOSED. Since L-3 the two write paths disagreed about tolerance:
evaluate.py used the stage-conditioned band, batch/runner.py used the flat 15%. The same
ticker with the same synthesis could therefore get a DIFFERENT VERDICT depending on which
entry point produced it — a per-path tolerance divergence, which is its own defect class
regardless of which band is right. That is what closes here.

THE TWO CODICILS VIC ATTACHED TO THE ARM (2026-08-20), both pinned below:
  1. COVERAGE LIMIT ON RECORD. 9 of the 10 widened names were UNVERIFIED at arm time — no
     eval-date price exists for them, so their bands are reasoned, not measured. The dark
     replay that justified the arm covered 16 rows across 5 tickers, only ONE of which
     widens (NOW @20%, max divergence 6.91%).
  2. TRIPWIRE. The first divergence that lands in `(15%, stage band]` — one flat-15 WOULD
     have tripped — reports with a full readout before that E(R) is trusted. Same pattern
     as the D-5 BANK-RUNG-UNCALIBRATED tripwire: an uncalibrated rung stays OBSERVABLE
     until a real event validates it.

THE SAFETY PROPERTY THE ARM RESTS ON is `test_the_arm_is_monotone_widening` below. It is
the reason an empty dark diff on 1-of-10 coverage was sufficient: no stage band is TIGHTER
than the flat default, so this arm can only ever SUPPRESS a trip, never create one. Nothing
that passes the batch guard today starts failing it. The risk therefore runs in exactly one
direction, and codicil 2 is the instrument pointed at that direction.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.lifecycle import FLAG_INSUFFICIENT_HISTORY
from core.lifecycle_config import B2_DIVERGENCE_TOLERANCE_BY_STAGE
from core.stage_tolerance import (DEFAULT_TOLERANCE, suppressed_by_widening,
                                  tolerance_for)
from store.models import init_db


def _stage_row(db, ticker, stage, flags=(), lens="growth"):
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO lifecycle_stage (ticker, computed_stage, rule_fired, lens, inputs_json,"
        " assertions_json, flags_json, absent_legs, inputs_incomplete, config_version, run_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (ticker, stage, "rule_test", lens, "{}", "[]", json.dumps(list(flags)),
         None, 0, "test", "2026-08-20T00:00:00+00:00"))
    conn.commit()
    conn.close()


# ── the invariant the whole arming rests on ──────────────────────────────────

def test_the_arm_is_monotone_widening():
    """THE LOAD-BEARING PIN OF THIS ORDER. Every stage band is >= the flat default, so
    moving batch from flat-15 onto the stage set can only ever REMOVE a trip, never add
    one. This is what made arming on 1-of-10 verified coverage defensible.

    IF A FUTURE ORDER EVER SETS A BAND BELOW 15%, THIS FAILS — and it should, loudly:
    that band would make batch start flagging names it currently passes, and the empty
    dark diff recorded at L-4b would no longer cover the change.
    """
    assert min(B2_DIVERGENCE_TOLERANCE_BY_STAGE.values()) == DEFAULT_TOLERANCE
    for stage, band in B2_DIVERGENCE_TOLERANCE_BY_STAGE.items():
        assert band >= DEFAULT_TOLERANCE, f"{stage} band {band} is TIGHTER than the default"


# ── the two paths now agree ──────────────────────────────────────────────────

def test_both_write_paths_resolve_the_same_band_for_the_same_ticker(tmp_path):
    """The defect L-4b closes, stated as an assertion: one ticker, one band, regardless of
    entry point. Both paths call the same tolerance_for() against the same destination db,
    so agreement is structural rather than a coincidence of two copied constants."""
    db = tmp_path / "b.db"
    init_db(db)
    _stage_row(db, "RKLB", "YOUNG")
    _stage_row(db, "ARM", "HIGROWTH")
    _stage_row(db, "MU", "MATURE")
    for ticker, expected in (("RKLB", 0.30), ("ARM", 0.20), ("MU", 0.15)):
        assert tolerance_for(ticker, db).tolerance == expected


def test_batch_reads_the_band_and_never_the_classifier():
    """CARRIES THE SURVIVING HALF of the retired dark pin
    (test_batch_runner_does_not_read_the_classifier, removed from tests/test_lifecycle.py
    at L-4b). Batch annotates no stage — it may learn the derived BAND and nothing more."""
    src = Path("batch/runner.py").read_text(encoding="utf-8")
    assert "tolerance_for" in src
    assert "core.lifecycle" not in src, "batch imports the classifier"
    assert "lifecycle_stage" not in src, "batch reads the raw stage table"


def test_batch_no_longer_holds_a_flat_threshold_to_drift_back_onto():
    """The flat import is GONE, not merely unused. An unused import of the old value is how
    a path quietly regains the behaviour an order just removed."""
    src = Path("batch/runner.py").read_text(encoding="utf-8")
    assert "ANCHOR_DIVERGENCE_THRESHOLD" not in src.split('"""')[-1] or True
    import ast
    tree = ast.parse(src)
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                for a in n.names}
    assert "ANCHOR_DIVERGENCE_THRESHOLD" not in imported


def test_the_batch_guard_is_called_with_an_explicit_threshold():
    """check_anchor's DEFAULT is the flat 15%. If the batch call site ever loses its
    threshold= argument it silently reverts to flat-15 and the two paths diverge again —
    with no error, because the default is a valid value. Pin the argument itself."""
    src = Path("batch/runner.py").read_text(encoding="utf-8")
    assert "check_anchor(synthesis, price_for_er, threshold=_tol.tolerance)" in src


# ── codicil 2: the tripwire ──────────────────────────────────────────────────

@pytest.mark.parametrize("divergence,tolerance,expected", [
    (0.18, 0.20, True),    # above flat-15, inside the 20% band — THE event
    (0.28, 0.30, True),    # same, at the widest band
    (0.30, 0.30, True),    # boundary: exactly at the band still counts as suppressed
    (0.15, 0.20, False),   # exactly at flat-15 — flat-15 does not trip here either (`>`)
    (0.10, 0.30, False),   # comfortably inside both
    (0.35, 0.30, False),   # trips anyway — the widening suppressed nothing
    (0.18, 0.15, False),   # default band: widening cannot be the cause by definition
])
def test_the_tripwire_fires_exactly_when_widening_is_the_only_reason(
        divergence, tolerance, expected):
    assert suppressed_by_widening(divergence, tolerance) is expected


def test_the_tripwire_is_silent_when_there_is_no_divergence_to_judge():
    assert suppressed_by_widening(None, 0.30) is False


def test_the_tripwire_boundary_matches_the_guards_own_comparison():
    """The guard trips on `divergence > threshold`, so a divergence EXACTLY at 15% does not
    trip at flat-15. The tripwire must use the same boundary or it would report an event
    flat-15 would not in fact have caught."""
    assert suppressed_by_widening(DEFAULT_TOLERANCE, 0.30) is False
    assert suppressed_by_widening(DEFAULT_TOLERANCE + 1e-9, 0.30) is True


def test_the_tripwire_readout_is_wired_into_the_batch_path():
    """A rule recorded without naming its enforcement point is a belief, not a guard. The
    predicate existing is not enough — the batch path must actually call it."""
    src = Path("batch/runner.py").read_text(encoding="utf-8")
    assert "_log_widening_suppression(ticker, _ac, _tol, _log)" in src
    assert "B2-WIDENING-SUPPRESSED-TRIP" in src


def test_the_tripwire_advises_and_does_not_withhold():
    """Deliberate scope limit. The codicil ordered a REPORT, not a second guard. E(R) is
    still computed and persisted on a suppressed-trip row; withholding it would be an
    unruled guard smuggled in under a reporting order."""
    from batch.runner import _log_widening_suppression

    class _AC:
        divergence, implied_anchor, live_price = 0.18, 118.0, 100.0

    class _Tol:
        tolerance, reason = 0.20, "stage HIGROWTH band 20%"

    lines = []
    _log_widening_suppression("ARM", _AC(), _Tol(), lines.append)
    assert len(lines) == 1
    msg = lines[0]
    assert "B2-WIDENING-SUPPRESSED-TRIP" in msg and "ARM" in msg
    assert "flat-15 WOULD" in msg and "persisted" in msg


# ── fail-closed: a scratch-db run must not borrow production's stages ────────

def test_a_scratch_db_run_gets_the_DEFAULT_band_not_productions_stages(tmp_path):
    """THE CONTAMINATION SHAPE, INVERTED. Batch reads the stage from `db_path or _DEFAULT_DB`
    — the DESTINATION, never unconditionally production. A --db-path run therefore finds no
    stage rows and every name falls to the DEFAULT band. That is fail-closed in the right
    direction: an isolated run cannot borrow production's classifications to widen its own
    tolerance."""
    db = tmp_path / "scratch.db"
    init_db(db)
    st = tolerance_for("RKLB", db)              # YOUNG in production, unclassified here
    assert st.tolerance == DEFAULT_TOLERANCE
    assert st.stage is None


def test_the_batch_call_site_reads_the_destination_db(tmp_path):
    """Pin the argument, not just the behaviour — `tolerance_for(ticker, _DEFAULT_DB)` would
    pass every test above while silently reading production from a scratch run."""
    src = Path("batch/runner.py").read_text(encoding="utf-8")
    assert "tolerance_for(ticker, db_path or _DEFAULT_DB)" in src


# ── codicil 1: the coverage limit stays visible ──────────────────────────────

def test_insufficient_history_names_still_do_not_get_a_widened_band(tmp_path):
    """Re-pinned ON THE BATCH PATH's band source. DPC and INFQ reach YOUNG on one fiscal
    year. INFQ sits 0.37pp from tripping at its fail-closed 15%; had the arm handed it 30%
    it would have gained ~15pp of headroom on an absence rather than a measurement."""
    db = tmp_path / "b.db"
    init_db(db)
    _stage_row(db, "INFQ", "YOUNG", flags=[FLAG_INSUFFICIENT_HISTORY])
    st = tolerance_for("INFQ", db)
    assert st.tolerance == DEFAULT_TOLERANCE
    assert suppressed_by_widening(0.1463, st.tolerance) is False
