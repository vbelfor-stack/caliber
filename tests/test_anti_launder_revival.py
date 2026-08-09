"""
E-4 — verdict-high reachability and the anti-launder NOTE.

Background. reason_for_grade() emits "[ANTI-LAUNDER: high-conf miss]" when an evaluation
that claimed HIGH verdict confidence lands a D or F. Since the AlphaVantage teardown that
note has been UNFIRABLE on real evaluations: with a single feed every field stayed
'medium', so no pillar could be high, so enforced_verdict_confidence could never return
high. The note's own logic stayed unit-tested (test_grading), but nothing could reach it.

These tests walk the chain link by link and pin down exactly how far EDGAR carries it:

    EDGAR agreement → field 'high' → pillar 'high' → verdict 'high' → NOTE fires
    ✓                 ✓              ✓ (one pillar)  ✗ BLOCKED       (ready, untriggered)

The chain is restored up to pillar level and is still blocked at the verdict, because
enforced_verdict_confidence takes the MINIMUM across all five pillars and four of them
carry material inputs EDGAR structurally cannot corroborate (price- and estimate-derived
fields, the FRED rate). test_verdict_high_is_still_blocked documents that gap and names
the blockers; it is EXPECTED TO FAIL when coverage expands, which is the point — the day
verdict-high becomes reachable, this suite says so loudly instead of silently.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from adapters.base import PillarResult, Prov, min_conf
from adapters.edgar_adapter import fetch_edgar
from adapters.fixture_adapter import fetch_fixture
from adapters.fred_adapter import fetch_fred
from core.edgar_cross_check import apply_report, compute_cross_check
from core.grading import reason_for_grade
from core.lens_select import select_lens
from core.pillars import score_all
from synthesis.schema import enforced_verdict_confidence

FIXTURES = Path("tests/fixtures")
AS_OF = "2026-08-08"


def _load(ticker: str):
    edgar = fetch_edgar(ticker, fixture_path=FIXTURES / "edgar" / f"{ticker}.json")
    yf = fetch_fixture(ticker, fixture_path=FIXTURES / "ticker" / f"{ticker}.json")
    yf.sic = edgar.sic
    fred = fetch_fred(fixture_path=FIXTURES / "fred" / "DGS10.json")
    return edgar, yf, fred


def _align_to_edgar(edgar, yf):
    """Set every comparable FMP value to what EDGAR reports for it.

    The recorded ticker fixtures pre-date the EDGAR ones and disagree in places, which
    exercises the conflict path but cannot exercise the upgrade path. Aligning the values
    models the best case the feed can present — full corroboration — so the ceiling this
    file measures is a property of the PIPELINE, not of fixture drift.
    """
    for d in compute_cross_check(edgar, yf, today=AS_OF).deltas:
        if d.dark or d.edgar_value is None:
            continue
        prov = getattr(yf, d.fmp_field, None)
        if prov is not None and not prov.is_missing():
            prov.value = d.edgar_value
    return yf


def _corroborated_pillars(ticker="GOOG"):
    edgar, yf, fred = _load(ticker)
    _align_to_edgar(edgar, yf)
    apply_report(compute_cross_check(edgar, yf, today=AS_OF), yf)
    return score_all(yf, edgar, fred, select_lens(yf.sector, yf.industry, edgar.sic))


def _pillars_at(*confidences):
    return [PillarResult(name=f"P{i}", score=3, confidence=c, method="test",
                         rationale="", key_inputs=[], flags=[])
            for i, c in enumerate(confidences)]


class TestChainLink1FieldHigh:
    def test_edgar_agreement_raises_a_field_to_high(self):
        """The link that was severed: with one feed, nothing could exceed medium."""
        edgar, yf, _ = _load("MU")
        assert getattr(yf, "gross_margin").confidence == "medium"
        apply_report(compute_cross_check(edgar, yf, today=AS_OF), yf)
        assert getattr(yf, "gross_margin").confidence == "high"


class TestChainLink2PillarHigh:
    def test_pillar_reaches_high_when_every_material_input_is_corroborated(self):
        by_name = {p.name: p for p in _corroborated_pillars()}
        assert by_name["Business Quality"].confidence == "high"
        assert all(i.confidence == "high" for i in by_name["Business Quality"].key_inputs)

    def test_no_pillar_could_reach_high_before_edgar(self):
        """Same data, cross-check withheld — the pre-EDGAR state, and the reason the
        note went dead rather than merely unused."""
        edgar, yf, fred = _load("GOOG")
        _align_to_edgar(edgar, yf)
        compute_cross_check(edgar, yf, today=AS_OF)          # computed, not applied
        pillars = score_all(yf, edgar, fred,
                            select_lens(yf.sector, yf.industry, edgar.sic))
        assert all(p.confidence != "high" for p in pillars)

    def test_pillar_confidence_is_the_minimum_of_its_inputs(self):
        """The anti-launder rule itself: one uncorroborated input caps the pillar."""
        high, medium = Prov(1.0, "s", AS_OF, "high"), Prov(1.0, "s", AS_OF, "medium")
        assert min_conf(high, high) == "high"
        assert min_conf(high, medium) == "medium"


class TestChainLink3VerdictHigh:
    def test_verdict_high_requires_every_pillar_high(self):
        assert enforced_verdict_confidence(_pillars_at(*["high"] * 5), "high") == "high"
        assert enforced_verdict_confidence(
            _pillars_at("high", "high", "high", "high", "medium"), "high") == "medium"

    def test_llm_cannot_claim_more_than_the_pillars_support(self):
        assert enforced_verdict_confidence(_pillars_at(*["medium"] * 5), "high") == "medium"
        assert enforced_verdict_confidence(_pillars_at(*["low"] * 5), "high") == "low"

    def test_verdict_high_is_still_blocked(self):
        """THE E-4 FINDING. Even with every EDGAR-comparable field corroborated, the
        verdict cannot reach high: four pillars carry material inputs EDGAR structurally
        cannot corroborate.

        EXPECTED TO FAIL when that changes — arming R3(b) would corroborate total_cash
        and total_debt, and closing the rest would make the note firable for the first
        time. Update this test then, deliberately.
        """
        pillars = _corroborated_pillars()
        assert enforced_verdict_confidence(pillars, "high") == "medium"
        blocked = {p.name for p in pillars if p.confidence != "high"}
        assert blocked == {"Financial Health", "Management & Capital Allocation",
                           "Growth / Forward", "Valuation"}


class TestChainLink4NoteFires:
    def test_note_fires_end_to_end_from_pillars_to_grade(self):
        """The revival path, exercised whole: once every pillar is corroborated the
        verdict is high, and a high-confidence miss is called out."""
        verdict = enforced_verdict_confidence(_pillars_at(*["high"] * 5), "high")
        assert verdict == "high"
        assert reason_for_grade("F", 15.0, -22.0, verdict) == \
            "[ANTI-LAUNDER: high-conf miss]"
        assert reason_for_grade("D", 10.0, -8.0, verdict) == \
            "[ANTI-LAUNDER: high-conf miss]"

    def test_note_stays_silent_at_the_confidence_the_pipeline_can_reach(self):
        """Today's ceiling is medium, and a medium-confidence miss is not laundering."""
        verdict = enforced_verdict_confidence(_corroborated_pillars(), "high")
        assert reason_for_grade("F", 15.0, -22.0, verdict) == ""

    def test_note_is_for_misses_only(self):
        assert reason_for_grade("A", 15.0, 20.0, "high") == ""
        assert reason_for_grade("B", 15.0, 8.0, "high") == ""


class TestConflictDirection:
    def test_an_edgar_conflict_pins_the_pillar_and_the_verdict_low(self):
        """The other half of arming: EDGAR can also REMOVE confidence. A single
        contradicted field drags its pillar — and so the verdict — to low."""
        edgar, yf, fred = _load("GOOG")
        pillars = score_all(yf, edgar, fred,
                            select_lens(yf.sector, yf.industry, edgar.sic))
        assert enforced_verdict_confidence(pillars, "high") == "medium"

        apply_report(compute_cross_check(edgar, yf, today=AS_OF), yf)
        after = score_all(yf, edgar, fred,
                          select_lens(yf.sector, yf.industry, edgar.sic))
        assert any(d.verdict == "conflict" for d in
                   compute_cross_check(edgar, yf, today=AS_OF).deltas)
        assert any(p.confidence == "low" for p in after)
        assert enforced_verdict_confidence(after, "high") == "low"
