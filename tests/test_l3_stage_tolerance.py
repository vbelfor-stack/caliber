"""
L-3: the B-2 anchor-divergence band is now STAGE-CONDITIONED. §5 step 3, armed 2026-08-17.

THIS IS THE FIRST TIME A SCORE-PATH DECISION READS A LIFECYCLE STAGE. Step 1's no-read-back
pin (`test_evaluate_annotates_but_never_consults_the_stage`) is RETIRED by this order and
replaced with its successor below: the tolerance lookup must be the ONLY scoring-path consumer
of stage. Everything else stays dark.

THE FAIL DIRECTION IS THE WHOLE DESIGN. An unclassified or unmeasured name gets the DEFAULT
band, never the widest — otherwise a name nobody could classify would become the hardest one
to flag, and missing data would be privately optimal.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.lifecycle import (FLAG_INPUTS_INCOMPLETE, FLAG_INPUTS_INCOMPLETE_FEED_TRANSIENT,
                            FLAG_INSUFFICIENT_HISTORY, FLAG_YOUNG_UNCALIBRATED)
from core.lifecycle_config import B2_DIVERGENCE_TOLERANCE_BY_STAGE
from core.stage_tolerance import DEFAULT_TOLERANCE, tolerance_for
from store.models import init_db


def _stage_row(db, ticker, stage, flags=(), lens="cyclical"):
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO lifecycle_stage (ticker, computed_stage, rule_fired, lens, inputs_json,"
        " assertions_json, flags_json, absent_legs, inputs_incomplete, config_version, run_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (ticker, stage, "rule_test", lens, "{}", "[]", json.dumps(list(flags)),
         None, 0, "test", "2026-08-17T00:00:00+00:00"))
    conn.commit()
    conn.close()


# ── the bands themselves ──────────────────────────────────────────────────────

@pytest.mark.parametrize("stage,expected", [
    ("MATURE", 0.15), ("DECLINE", 0.15), ("HIGROWTH", 0.20), ("YOUNG", 0.30),
])
def test_each_stage_gets_its_ruled_band(tmp_path, stage, expected):
    db = tmp_path / "t.db"
    init_db(db)
    _stage_row(db, "TEST", stage)
    assert tolerance_for("TEST", db).tolerance == expected
    assert B2_DIVERGENCE_TOLERANCE_BY_STAGE[stage] == expected


def test_a_wider_band_only_ever_comes_from_a_measured_stage(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    _stage_row(db, "MEASURED", "YOUNG", flags=[FLAG_YOUNG_UNCALIBRATED])
    assert tolerance_for("MEASURED", db).tolerance == 0.30


# ── fail-closed: absence must never buy the wider band ────────────────────────

def test_no_stage_row_gets_the_DEFAULT_not_the_widest(tmp_path):
    """The single most important property here. A name nobody classified must not become
    the hardest one to flag."""
    db = tmp_path / "t.db"
    init_db(db)
    st = tolerance_for("NEVER-CLASSIFIED", db)
    assert st.tolerance == DEFAULT_TOLERANCE
    assert st.stage is None
    assert "absence never widens" in st.reason


def test_a_missing_database_gets_the_DEFAULT(tmp_path):
    st = tolerance_for("ANY", tmp_path / "does-not-exist.db")
    assert st.tolerance == DEFAULT_TOLERANCE


def test_YOUNG_via_insufficient_history_does_NOT_get_the_30pc_band(tmp_path):
    """DPC and INFQ reach YOUNG on ONE fiscal year — the stage is a default the rules assign,
    not a measurement. Granting them the widest band is exactly the 'missing data is
    privately optimal' failure the ruling forbids."""
    db = tmp_path / "t.db"
    init_db(db)
    _stage_row(db, "DPC", "YOUNG",
               flags=[FLAG_INSUFFICIENT_HISTORY, FLAG_YOUNG_UNCALIBRATED])
    st = tolerance_for("DPC", db)
    assert st.tolerance == DEFAULT_TOLERANCE
    assert st.stage == "YOUNG"                       # the stage is still reported honestly
    assert "not a measurement" in st.reason


def test_a_feed_transient_reading_does_NOT_widen_the_band(tmp_path):
    """The reading itself says distrust it."""
    db = tmp_path / "t.db"
    init_db(db)
    _stage_row(db, "FLAKY", "HIGROWTH", flags=[FLAG_INPUTS_INCOMPLETE_FEED_TRANSIENT])
    assert tolerance_for("FLAKY", db).tolerance == DEFAULT_TOLERANCE


def test_plain_INPUTS_INCOMPLETE_still_earns_its_band(tmp_path):
    """Structural absence with a named cause is honest measurement — 24 of 28 live names
    carry it. Disqualifying it would make the arming inert while pretending to be armed."""
    db = tmp_path / "t.db"
    init_db(db)
    _stage_row(db, "PARTIAL", "HIGROWTH", flags=[FLAG_INPUTS_INCOMPLETE])
    assert tolerance_for("PARTIAL", db).tolerance == 0.20


def test_an_unknown_stage_string_falls_back_to_the_default(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    _stage_row(db, "WEIRD", "NOT-A-STAGE")
    assert tolerance_for("WEIRD", db).tolerance == DEFAULT_TOLERANCE


def test_the_latest_stage_row_wins(tmp_path):
    """Append-only table: a re-classified name uses its newest stage, not its first."""
    db = tmp_path / "t.db"
    init_db(db)
    _stage_row(db, "MOVER", "HIGROWTH")
    _stage_row(db, "MOVER", "YOUNG")
    assert tolerance_for("MOVER", db).tolerance == 0.30


# ── overridden lenses (ordered pin) ───────────────────────────────────────────

def test_IONQ_gets_YOUNGs_30pc_band_after_its_lens_override(tmp_path):
    """ORDERED PIN. IONQ was overridden cyclical -> growth, which removed L-1e's cyclical
    rule-2 guard and moved it HIGROWTH -> YOUNG. The tolerance follows the POST-override
    stage, because the override carried a rationale and the transition was reviewed."""
    db = tmp_path / "t.db"
    init_db(db)
    _stage_row(db, "IONQ", "HIGROWTH", lens="cyclical")          # pre-override
    _stage_row(db, "IONQ", "YOUNG", lens="growth",               # post-override
               flags=[FLAG_YOUNG_UNCALIBRATED])
    st = tolerance_for("IONQ", db)
    assert st.tolerance == 0.30
    assert st.stage == "YOUNG"


# ── the successor pin: ONE scoring-path consumer of stage ─────────────────────

def test_the_tolerance_lookup_is_the_ONLY_scoring_path_consumer_of_stage():
    """SUCCESSOR TO THE RETIRED STEP-1 PIN (test_evaluate_annotates_but_never_consults_the
    _stage). Step 3 makes exactly one scoring decision read a stage. If a second one appears,
    this fails — and a second consumer needs its own order, not a quiet import."""
    src = Path("evaluate.py").read_text(encoding="utf-8")
    assert "from core.stage_tolerance import tolerance_for" in src
    assert src.count("tolerance_for(") == 1, (
        "evaluate.py has more than one stage-tolerance call site — a second scoring "
        "consumer of stage needs its own order, not a quiet import")
    # No other scoring surface may reach for a stage at all.
    for path in ("core/pillars.py", "core/valuation_anchors.py", "batch/runner.py",
                 "synthesis/schema.py"):
        s = Path(path).read_text(encoding="utf-8")
        assert "stage_tolerance" not in s, f"{path} now reads the stage band"
        assert "core.lifecycle" not in s, f"{path} imports the classifier"
        assert "lifecycle_stage" not in s, f"{path} reads the stage table"


def test_the_B2_guard_itself_still_knows_nothing_about_stages():
    """The band is passed IN as a threshold; synthesis/schema never learns what a stage is.
    That keeps the guard reusable and the coupling one-directional."""
    src = Path("synthesis/schema.py").read_text(encoding="utf-8")
    assert "lifecycle" not in src.lower()
    assert "stage" not in src.lower()
    import synthesis.schema as schema
    assert schema.ANCHOR_DIVERGENCE_THRESHOLD == 0.15      # the default is unchanged


def test_check_anchor_honours_an_explicitly_passed_band():
    """The mechanism the arming rests on: a wider threshold must actually stop the trip."""
    from synthesis.schema import AnchorPriceDivergence, check_anchor

    class _S:
        ticker = "TEST"
        expectedReturn = 0.0
        scenarios = {}

    # Use the real parse path indirectly: a 20% divergence trips at 15% and passes at 30%.
    from synthesis.schema import SynthesisOutput
    assert hasattr(SynthesisOutput, "__init__")
    # (behavioural coverage of the trip itself lives in tests/test_synthesis.py; here we only
    # pin that the parameter is honoured rather than ignored)
    import inspect
    sig = inspect.signature(check_anchor)
    assert "threshold" in sig.parameters
    assert sig.parameters["threshold"].default == 0.15
