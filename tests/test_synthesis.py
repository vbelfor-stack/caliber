"""
Phase 2 synthesis tests.

Covers:
  - JSON repair pipeline (truncation, fences, thousands separators)
  - parse_synthesis happy path
  - Anti-launder enforcement: low-confidence pillar → verdictConfidence=low
  - Truncated payload: repairs or raises loudly (never half-parses silently)
  - Value-trap emergent detection (WU pattern: cheap + solvent + no growth)
  - Value-trap false-positive guard (NOW pattern: growth present → no value trap label)
  - Store: save_evaluation + list_evaluations round-trip
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure caliber root is on path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from adapters.base import PillarResult, Prov
from synthesis.schema import (
    repair_json,
    parse_synthesis,
    enforced_verdict_confidence,
    SynthesisOutput,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_pillar(name: str, score: int, confidence: str, flags=None) -> PillarResult:
    return PillarResult(
        name=name, score=score, confidence=confidence,
        rationale="test rationale", flags=flags or [], method="standard",
    )


def _high_pillars():
    return [_make_pillar(n, 4, "high") for n in
            ("Business Quality", "Financial Health", "Management", "Growth", "Valuation")]


def _low_pillars():
    """At least one pillar with low confidence → anti-launder fires."""
    pillars = _high_pillars()
    pillars[2] = _make_pillar("Management", 3, "low")
    return pillars


def _valid_synthesis_json(
    verdict_confidence="high",
    bear_thesis="Secular decline continues.",
    red_flags=None,
) -> str:
    data = {
        "company": "Test Corp",
        "verdictConfidence": verdict_confidence,
        "verdictReason": "Balanced risk/reward.",
        "expectedReturn": 8.5,
        "redFlags": red_flags or [],
        "scenarios": {
            "bull": {"thesis": "Upside", "points": ["a"], "probability": 30, "priceTarget": 120},
            "base": {"thesis": "Flat",   "points": ["b"], "probability": 50, "priceTarget": 100},
            "bear": {"thesis": bear_thesis, "points": ["c"], "probability": 20, "priceTarget": 70},
        },
        "research": [{"source": "Morningstar", "tier": "independent", "view": "hold", "conflicted": False}],
        "technicals": {"trend": "up", "above_ma50": True, "above_ma200": True,
                       "rsi_14": 55.0, "volume_confirmation": True, "notes": "clean"},
        "dataGaps": [],
    }
    return json.dumps(data)


# ── JSON repair tests ──────────────────────────────────────────────────────────

class TestRepairJson:
    def test_strip_markdown_fences(self):
        raw = "```json\n" + _valid_synthesis_json() + "\n```"
        data = repair_json(raw)
        assert data["company"] == "Test Corp"

    def test_strip_trailing_junk(self):
        raw = _valid_synthesis_json() + "\n\nSome extra text after."
        data = repair_json(raw)
        assert "company" in data

    def test_fix_thousands_separators(self):
        raw = '{"priceTarget": 1,234, "other": 56,789}'
        # Should parse after stripping separators
        data = repair_json(raw)
        assert data["priceTarget"] == 1234

    def test_close_truncated_missing_braces(self):
        # Simulate truncation: missing closing braces
        raw = '{"company": "X", "scenarios": {"bull": {"thesis": "up"'
        data = repair_json(raw)
        assert data["company"] == "X"

    def test_unrecoverable_raises_value_error(self):
        with pytest.raises(ValueError, match="JSON repair failed"):
            repair_json("this is not json at all }{{{")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            repair_json("")

    def test_plain_valid_json(self):
        data = repair_json(_valid_synthesis_json())
        assert data["verdictConfidence"] == "high"


# ── Anti-launder enforcement ──────────────────────────────────────────────────

class TestEnforcedVerdictConfidence:
    def test_all_high_pillars_allows_high(self):
        result = enforced_verdict_confidence(_high_pillars(), "high")
        assert result == "high"

    def test_one_low_pillar_forces_low(self):
        result = enforced_verdict_confidence(_low_pillars(), "high")
        assert result == "low"

    def test_medium_pillar_caps_at_medium(self):
        pillars = _high_pillars()
        pillars[0] = _make_pillar("Business Quality", 4, "medium")
        result = enforced_verdict_confidence(pillars, "high")
        assert result == "medium"

    def test_llm_low_stays_low_regardless(self):
        result = enforced_verdict_confidence(_high_pillars(), "low")
        assert result == "low"

    def test_empty_pillars_returns_low(self):
        result = enforced_verdict_confidence([], "high")
        assert result == "low"


# ── parse_synthesis happy path ────────────────────────────────────────────────

class TestParseSynthesis:
    def test_happy_path(self):
        raw = _valid_synthesis_json()
        out = parse_synthesis(raw, _high_pillars(), "TEST")
        assert isinstance(out, SynthesisOutput)
        assert out.ticker == "TEST"
        assert out.verdictConfidence == "high"
        assert out.bull.probability == 30
        assert out.base.probability == 50
        assert out.bear.probability == 20
        assert out.bull.priceTarget == 120
        assert len(out.research) == 1
        assert out.research[0].tier == "independent"

    def test_anti_launder_fires_in_parse(self):
        raw = _valid_synthesis_json(verdict_confidence="high")
        out = parse_synthesis(raw, _low_pillars(), "TEST")
        assert out.verdictConfidence == "low", (
            "Anti-launder must downgrade verdictConfidence when a pillar is low"
        )

    def test_missing_scenarios_raises(self):
        data = json.loads(_valid_synthesis_json())
        del data["scenarios"]
        with pytest.raises(ValueError, match="scenarios"):
            parse_synthesis(json.dumps(data), _high_pillars(), "TEST")

    def test_missing_bear_scenario_raises(self):
        data = json.loads(_valid_synthesis_json())
        del data["scenarios"]["bear"]
        with pytest.raises(ValueError, match="bear"):
            parse_synthesis(json.dumps(data), _high_pillars(), "TEST")

    def test_probability_sum_out_of_range_raises(self):
        data = json.loads(_valid_synthesis_json())
        data["scenarios"]["bull"]["probability"] = 10
        data["scenarios"]["base"]["probability"] = 10
        data["scenarios"]["bear"]["probability"] = 10
        with pytest.raises(ValueError, match="probabilit"):
            parse_synthesis(json.dumps(data), _high_pillars(), "TEST")

    def test_truncated_payload_repairs_or_raises_loudly(self):
        """
        A truncated payload must either repair successfully OR raise ValueError.
        It must NEVER silently return an incomplete/half-parsed object.
        """
        raw = _valid_synthesis_json()
        # Truncate aggressively — cut off mid-field
        truncated = raw[:len(raw) // 2]
        try:
            out = parse_synthesis(truncated, _high_pillars(), "TEST")
            # If it parses, it must have at least the required fields
            assert out.bull is not None
            assert out.bear is not None
            assert out.base is not None
        except ValueError:
            pass  # Loud failure is acceptable — silent half-parse is not

    def test_fenced_response_parses(self):
        raw = "```json\n" + _valid_synthesis_json() + "\n```"
        out = parse_synthesis(raw, _high_pillars(), "TEST")
        assert out.company == "Test Corp"

    def test_null_price_target_accepted(self):
        data = json.loads(_valid_synthesis_json())
        data["scenarios"]["bull"]["priceTarget"] = None
        out = parse_synthesis(json.dumps(data), _high_pillars(), "TEST")
        assert out.bull.priceTarget is None


# ── Value-trap emergence tests ────────────────────────────────────────────────

class TestValueTrapLogic:
    """
    Value trap is emergent — the synthesis constructs it only when the pillar data
    shows cheap + solvent + no growth. These tests assert on the raw JSON bear
    thesis content, mirroring what the Phase 2 gate checks against real LLM output.
    We validate the schema allows this and that our parser preserves bear thesis text.
    """

    def test_wu_pattern_bear_thesis_preserved(self):
        """WU: cheap + solvent + no growth → bear.thesis contains value-trap language."""
        bear_thesis = "Value trap: cheap on statics but secular revenue decline is structural."
        raw = _valid_synthesis_json(bear_thesis=bear_thesis)
        out = parse_synthesis(raw, _high_pillars(), "WU")
        assert "value trap" in out.bear.thesis.lower() or "value-trap" in out.bear.thesis.lower()

    def test_now_pattern_no_value_trap_in_flags(self):
        """NOW: growth present → 'value trap' must not appear in redFlags."""
        raw = _valid_synthesis_json(
            bear_thesis="Multiple derating if AI commoditizes seat-based SaaS pricing.",
            red_flags=["HIGH-MULTIPLE", "AI-DISRUPTION-RISK"],
        )
        out = parse_synthesis(raw, _high_pillars(), "NOW")
        flag_text = " ".join(out.redFlags).lower()
        assert "value trap" not in flag_text, (
            "NOW pattern must NOT carry value-trap label in redFlags when growth is present"
        )

    def test_bear_thesis_survives_round_trip(self):
        thesis = "Secular decline continues; payout unsustainable."
        raw = _valid_synthesis_json(bear_thesis=thesis)
        out = parse_synthesis(raw, _high_pillars(), "WU")
        assert out.bear.thesis == thesis


# ── Store round-trip tests ────────────────────────────────────────────────────

class TestStore:
    def test_save_and_retrieve_evaluation(self, tmp_path):
        from store.models import save_evaluation, list_evaluations, get_evaluation, init_db
        db = tmp_path / "test.db"
        init_db(db)

        pillars = _high_pillars()
        raw = _valid_synthesis_json()
        synthesis = parse_synthesis(raw, pillars, "TEST")

        eval_id = save_evaluation("TEST", "standard", pillars, synthesis, db_path=db)
        assert isinstance(eval_id, int) and eval_id > 0

        rows = list_evaluations(db_path=db)
        assert len(rows) == 1
        assert rows[0]["ticker"] == "TEST"
        assert rows[0]["status"] == "ok"
        assert rows[0]["avg_score"] == pytest.approx(4.0)
        assert rows[0]["verdict_conf"] == "high"

        row = get_evaluation(eval_id, db_path=db)
        assert row is not None
        assert row["lens"] == "standard"

    def test_save_no_synthesis(self, tmp_path):
        from store.models import save_evaluation, list_evaluations
        db = tmp_path / "test2.db"
        eval_id = save_evaluation("NOSYNTH", "cyclical", _high_pillars(), None, db_path=db)
        rows = list_evaluations(db_path=db)
        assert rows[0]["synthesis_json"] is None
        # status='ok' must mean a COMPLETE eval: a missing synthesis is degraded,
        # recorded honestly as 'no_synthesis', never masked as 'ok'.
        assert rows[0]["status"] == "no_synthesis"
        assert rows[0]["expected_return"] is None

    def test_save_failed_evaluation(self, tmp_path):
        from store.models import save_failed_evaluation, list_evaluations
        db = tmp_path / "test3.db"
        eid = save_failed_evaluation("BAD", "Something went wrong", db_path=db)
        rows = list_evaluations(db_path=db)
        assert rows[0]["status"] == "failed"
        assert "Something went wrong" in rows[0]["error_msg"]

    def test_filter_by_ticker(self, tmp_path):
        from store.models import save_evaluation, list_evaluations
        db = tmp_path / "test4.db"
        save_evaluation("AAPL", "standard", _high_pillars(), None, db_path=db)
        save_evaluation("GOOG", "compounder", _high_pillars(), None, db_path=db)
        aapl_rows = list_evaluations("AAPL", db_path=db)
        assert len(aapl_rows) == 1
        assert aapl_rows[0]["ticker"] == "AAPL"

    def test_multiple_runs_ordered_desc(self, tmp_path):
        from store.models import save_evaluation, list_evaluations
        db = tmp_path / "test5.db"
        save_evaluation("MU", "cyclical", _high_pillars(), None, db_path=db)
        save_evaluation("MU", "cyclical", _low_pillars(), None, db_path=db)
        rows = list_evaluations("MU", db_path=db)
        assert len(rows) == 2
        # Most recent first
        assert rows[0]["run_at"] >= rows[1]["run_at"]


class TestNoSynthesisBackfill:
    """B-1 migration: relabel legacy status='ok'-without-synthesis rows."""

    def _seed_legacy_false_complete(self, db, ticker="LEGACY", run_at="2020-01-01T00:00:00+00:00"):
        """Insert a row mimicking the pre-fix bug: status='ok' but synthesis NULL.

        Uses raw SQL because save_evaluation can no longer produce this state.
        """
        import sqlite3
        from store.models import init_db
        init_db(db)
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO evaluations (ticker, run_at, lens, status, pillars_json, "
                "synthesis_json, avg_score, overall_conf, verdict_conf, expected_return) "
                "VALUES (?, ?, 'standard', 'ok', '[]', NULL, 3.0, 'medium', NULL, NULL)",
                (ticker, run_at),
            )

    def test_backfill_relabels_only_legacy_rows(self, tmp_path):
        from store.models import (
            save_evaluation, list_evaluations, backfill_no_synthesis_status,
        )
        db = tmp_path / "bf.db"
        # 1 legacy false-complete row, 1 honest ok row (synthesis present), 1 honest degraded.
        self._seed_legacy_false_complete(db, "LEGACY")
        synthesis = parse_synthesis(_valid_synthesis_json(), _high_pillars(), "GOODOK")
        save_evaluation("GOODOK", "standard", _high_pillars(), synthesis, db_path=db)
        save_evaluation("DEGRADED", "standard", _high_pillars(), None, db_path=db)

        n = backfill_no_synthesis_status(db_path=db)
        assert n == 1, "only the legacy false-complete row should be relabeled"

        by_ticker = {r["ticker"]: r["status"] for r in list_evaluations(db_path=db)}
        assert by_ticker["LEGACY"] == "no_synthesis"
        assert by_ticker["GOODOK"] == "ok"
        assert by_ticker["DEGRADED"] == "no_synthesis"

    def test_backfill_idempotent(self, tmp_path):
        from store.models import backfill_no_synthesis_status
        db = tmp_path / "bf2.db"
        self._seed_legacy_false_complete(db)
        assert backfill_no_synthesis_status(db_path=db) == 1
        assert backfill_no_synthesis_status(db_path=db) == 0, "re-run must be a no-op"

    def test_backfill_does_not_change_grading_eligibility(self, tmp_path):
        """The relabeled rows were already excluded (NULL E(R)); eligibility is invariant."""
        from store.models import (
            save_evaluation, get_ungradeable_evals, backfill_no_synthesis_status,
        )
        db = tmp_path / "bf3.db"
        # An old legacy false-complete row (NULL E(R)) — excluded by the E(R) clause either way.
        self._seed_legacy_false_complete(db, "LEGACY", run_at="2020-01-01T00:00:00+00:00")
        # An old, complete, gradeable eval — must remain eligible across the backfill.
        synthesis = parse_synthesis(_valid_synthesis_json(), _high_pillars(), "GRADEME")
        save_evaluation("GRADEME", "standard", _high_pillars(), synthesis,
                        expected_return=12.0, db_path=db)
        import sqlite3
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE evaluations SET run_at='2020-01-01T00:00:00+00:00' "
                         "WHERE ticker='GRADEME'")

        before = {r["ticker"] for r in get_ungradeable_evals(min_age_days=90, db_path=db)}
        n = backfill_no_synthesis_status(db_path=db)
        after = {r["ticker"] for r in get_ungradeable_evals(min_age_days=90, db_path=db)}

        assert n == 1
        assert before == after, "backfill must not change the grading-eligible set"
        assert "GRADEME" in after
        assert "LEGACY" not in after


def _synth_for_anchor(model_er, bull_t, base_t, bear_t,
                      pb=30, pn=40, pr=30, ticker="TST"):
    """Build a SynthesisOutput with controlled targets + model E(R) for anchor tests."""
    from synthesis.schema import SynthesisOutput, Scenario, TechnicalsOut
    return SynthesisOutput(
        company="C", ticker=ticker, verdictConfidence="medium", verdictReason="",
        expectedReturn=model_er, redFlags=[],
        bull=Scenario("", [], pb, bull_t),
        base=Scenario("", [], pn, base_t),
        bear=Scenario("", [], pr, bear_t),
        research=[],
        technicals=TechnicalsOut(trend="unknown", above_ma50=None, above_ma200=None,
                                 rsi_14=None, volume_confirmation=None),
        dataGaps=[],
    )


class TestAnchorGuard:
    """B-2: anchor-divergence guard. Ships DISARMED (dark-launch)."""

    def test_default_threshold_disarmed(self):
        import synthesis.schema as s
        assert s.ANCHOR_DIVERGENCE_THRESHOLD is None, "guard must ship disarmed"

    def test_consistent_anchor_is_ok(self):
        from synthesis.schema import check_anchor
        # targets all 110, model E(R)=+10% → implied anchor 100 == live 100.
        syn = _synth_for_anchor(10.0, 110, 110, 110)
        ac = check_anchor(syn, live_price=100.0)
        assert ac.status == "ok"
        assert ac.computed_er == pytest.approx(10.0)
        assert ac.divergence == pytest.approx(0.0, abs=1e-9)

    def test_stale_anchor_dark_launch_does_not_trip(self):
        from synthesis.schema import check_anchor
        # Model anchored to ~100 (targets 110 @ +10%) but live is 60 (MU-like).
        syn = _synth_for_anchor(10.0, 110, 110, 110)
        ac = check_anchor(syn, live_price=60.0)   # threshold defaults to None (disarmed)
        assert ac.status == "ok", "dark-launch must NOT trip"
        assert ac.divergence == pytest.approx(100.0 / 60.0 - 1.0, rel=1e-6)
        # E(R) is still computed (and 'laundered') during dark-launch — that's the
        # point: observe without changing behavior until the threshold is locked.
        assert ac.computed_er == pytest.approx((110.0 / 60.0 - 1.0) * 100.0)

    def test_stale_anchor_trips_when_armed(self):
        from synthesis.schema import check_anchor, AnchorPriceDivergence
        syn = _synth_for_anchor(10.0, 110, 110, 110)
        with pytest.raises(AnchorPriceDivergence):
            check_anchor(syn, live_price=60.0, threshold=0.15)

    def test_within_threshold_when_armed_is_ok(self):
        from synthesis.schema import check_anchor
        # implied anchor 100 vs live 95 → ~5.3% divergence < 15% → ok.
        syn = _synth_for_anchor(10.0, 110, 110, 110)
        ac = check_anchor(syn, live_price=95.0, threshold=0.15)
        assert ac.status == "ok"
        assert ac.computed_er is not None

    def test_missing_model_er_is_unverified_not_bypass(self):
        from synthesis.schema import check_anchor
        # Ruling 4: null model E(R) must NOT fall through — withhold + unverified.
        syn = _synth_for_anchor(None, 110, 110, 110)
        ac = check_anchor(syn, live_price=100.0, threshold=0.15)
        assert ac.status == "anchor_unverified"
        assert ac.computed_er is None

    def test_no_targets_is_unverified(self):
        from synthesis.schema import check_anchor
        syn = _synth_for_anchor(10.0, None, None, None)
        ac = check_anchor(syn, live_price=100.0)
        assert ac.status == "anchor_unverified"
        assert ac.computed_er is None

    def test_no_live_price_is_unverified(self):
        from synthesis.schema import check_anchor
        syn = _synth_for_anchor(10.0, 110, 110, 110)
        ac = check_anchor(syn, live_price=None)
        assert ac.status == "anchor_unverified"
        assert ac.computed_er is None

    def test_degenerate_model_er_is_unverified(self):
        from synthesis.schema import check_anchor
        # model E(R) = -100% → implied anchor denominator 0 → not derivable.
        syn = _synth_for_anchor(-100.0, 110, 110, 110)
        ac = check_anchor(syn, live_price=100.0, threshold=0.15)
        assert ac.status == "anchor_unverified"
        assert ac.computed_er is None


class TestStatusOverride:
    """save_evaluation must honor the anchor-guard status and withhold E(R)."""

    def test_anchor_unverified_persists_null_er(self, tmp_path):
        from store.models import save_evaluation, list_evaluations
        db = tmp_path / "ov.db"
        synthesis = parse_synthesis(_valid_synthesis_json(), _high_pillars(), "OVR")
        # E(R) withheld by the guard; status override supplied.
        save_evaluation("OVR", "standard", _high_pillars(), synthesis,
                        expected_return=None, status="anchor_unverified", db_path=db)
        row = list_evaluations(db_path=db)[0]
        assert row["status"] == "anchor_unverified"
        assert row["synthesis_json"] is not None, "synthesis is still persisted for audit"
        assert row["expected_return"] is None, "withheld E(R) must NOT be reinstated from the LLM"

    def test_no_override_falls_back_to_b1_semantics(self, tmp_path):
        from store.models import save_evaluation, list_evaluations
        db = tmp_path / "ov2.db"
        save_evaluation("NOOV", "standard", _high_pillars(), None, db_path=db)
        assert list_evaluations(db_path=db)[0]["status"] == "no_synthesis"
