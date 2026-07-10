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
