"""L-4d.1 — `PaymentsToAcquireOtherPropertyPlantAndEquipment` armed as the THIRD capex tag.

Order: docs/orders/2026-08-22-l4d1-lly-capex-basis.md. Ruling of 2026-08-21, executed
2026-08-22 after the predecessor session died mid-order.

WHAT THIS PINS AND WHY IT EXISTS. LLY migrated its capex tag THREE times and abandoned
`PaymentsToAcquireProductiveAssets` at 2022-09-30 — a 1369-day lag, far past the 450-day
staleness gate — so its whole FCF family was withheld with a truthful `capex:stale_tag`.
Its current tag is `PaymentsToAcquireOtherPropertyPlantAndEquipment`, which L-4d
DELIBERATELY EXCLUDED and L-4d.1 re-ruled IN on the L-4f ARM precedent.

THE REVERSAL IS THE INTERESTING PART, so it is pinned rather than merely done: see
`tests/test_l4d_capex_synonym.py::TestCapexChainShape::test_LLY_third_tag_is_ARMED`, which
carries the superseded pin's rationale verbatim.

Everything here runs offline. The LLY and FN shapes are synthetic (`resolve_financials`
over hand-built facts) because neither has a recorded fixture — and shape pins outlive the
issuer that motivated them anyway.
"""
from pathlib import Path

import pytest

from adapters.edgar_adapter import (
    FIELD_SPECS,
    REASON_STALE_TAG,
    STALE_TAG_DAYS,
    XBRL_CONCEPTS,
    FieldSpec,
    _resolve_one,
    fetch_edgar,
    resolve_financials,
)

EDGAR = Path("tests/fixtures/edgar")
FIXTURE_TICKERS = ("MU", "GOOG", "NOW", "JPM", "BK", "C", "V", "WU", "USB")

PPE = "PaymentsToAcquirePropertyPlantAndEquipment"
PRD = "PaymentsToAcquireProductiveAssets"
OTHER_PPE = "PaymentsToAcquireOtherPropertyPlantAndEquipment"


def _capex_spec():
    return next(s for s in FIELD_SPECS if s.name == "capex")


def _flow(end, start, value, form="10-K", fp="FY"):
    return {"value": float(value), "unit": "USD", "start": start, "end": end,
            "fy": None, "fp": fp, "form": form, "accession": "0000000000-26-000001"}


# ── the chain, after the arm ─────────────────────────────────────────────────

class TestThreeTagChain:

    def test_the_chain_is_exactly_three_tags_in_this_order(self):
        """Order IS the safety argument. The two armed tags keep priority; the new tag is
        reachable only when both are absent or stale — which is exactly the LLY case."""
        assert [c for c, _ns in _capex_spec().synonyms] == [PPE, PRD, OTHER_PPE]

    def test_the_new_tag_is_LAST_behind_both_armed_tags(self):
        """'Behind the two armed tags' is the ruling's own wording. Pinned as a position,
        not as a list, so it survives a future fourth entry."""
        names = [c for c, _ns in _capex_spec().synonyms]
        assert names.index(OTHER_PPE) > names.index(PPE)
        assert names.index(OTHER_PPE) > names.index(PRD)

    def test_the_new_tag_is_actually_fetched_from_companyfacts(self):
        """XBRL_CONCEPTS is derived from the spec table. If that derivation ever breaks,
        the spec would name a concept nobody downloads and the arm would be inert."""
        assert OTHER_PPE in {c for c, _ns in XBRL_CONCEPTS}

    def test_conflict_check_stays_off_and_L4d1_did_not_touch_it(self):
        """L-4d.1 changed the chain, NOT the conflict policy. Recorded so a later session
        does not read the third entry as a re-opening of that ruling."""
        assert _capex_spec().conflict_check is False


# ── the LLY shape: why the tag was needed ────────────────────────────────────

class TestLlyShapeResolves:

    def test_the_LLY_shape_resolves_on_the_third_tag(self):
        """THE WHOLE POINT. Generic tag never filed, ProductiveAssets abandoned 1369d ago,
        OtherPP&E current. Before L-4d.1 this withheld the entire FCF family."""
        fin = resolve_financials({
            PRD: [_flow("2022-09-30", "2021-10-01", 2_000)],        # 1369d — stale
            OTHER_PPE: [_flow("2026-06-30", "2025-07-01", 9_893)],  # fresh
        }, "2026-06-30")
        capex = fin.fields["capex"]
        assert capex.value == 9_893
        assert capex.concept == OTHER_PPE
        assert capex.reason is None
        assert any(f"{PRD}:stale(" in t for t in capex.trail), capex.trail

    def test_POSITIVE_CONTROL_the_two_tag_spec_goes_QUIET_on_the_same_facts(self):
        """THE PIN THAT MAKES THE OTHERS MEAN SOMETHING. Resolves identical facts against
        the pre-L-4d.1 two-tag spec and asserts it withholds — silently, with a typed
        reason on one field of nineteen. Without this, the test above cannot distinguish
        'the third tag works' from 'the input was easy'."""
        facts = {
            PRD: [_flow("2022-09-30", "2021-10-01", 2_000)],
            OTHER_PPE: [_flow("2026-06-30", "2025-07-01", 9_893)],
        }
        old = _resolve_one(
            FieldSpec("capex", "flow", ((PPE, "us-gaap"), (PRD, "us-gaap")),
                      conflict_check=False),
            facts, "2026-06-30", STALE_TAG_DAYS)
        assert old.value is None
        assert old.reason == REASON_STALE_TAG

        new = _resolve_one(_capex_spec(), facts, "2026-06-30", STALE_TAG_DAYS)
        assert new.value == 9_893
        assert new.concept == OTHER_PPE

    def test_the_LLY_shape_feeds_the_series_builder_end_to_end(self):
        """Value-level, per the L-4a finding that this suite asserted provenance strings
        where it should have asserted numbers. OCF and capex on DIFFERENT tags still
        produce an FCF point."""
        from core.fundamental_series import METRIC_FCF, build_fcf_series

        fin = resolve_financials({
            "NetCashProvidedByUsedInOperatingActivities": [
                _flow("2026-06-30", "2025-07-01", 18_190)],
            PRD: [_flow("2022-09-30", "2021-10-01", 2_000)],        # stale, skipped
            OTHER_PPE: [_flow("2026-06-30", "2025-07-01", 9_893)],  # fresh, used
            "Revenues": [_flow("2026-06-30", "2025-07-01", 60_000)],
        }, "2026-06-30")

        class _Edgar:
            financials = fin

        result = build_fcf_series("TEST", _Edgar(), None, None)
        assert not result.withheld, f"FCF still withheld: {result.withheld}"
        fcf = result.by_metric(METRIC_FCF)
        assert len(fcf) == 1
        assert fcf[0].value == 18_190 - 9_893
        assert fcf[0].components["capex"] == 9_893


# ── no regression: the two armed tags keep winning ───────────────────────────

class TestNoRegression:

    def test_a_fresh_generic_tag_beats_a_fresh_new_tag(self):
        """No name already resolving on PP&E may be moved onto the broader measure."""
        fin = resolve_financials({
            PPE: [_flow("2026-06-30", "2025-07-01", 100)],
            OTHER_PPE: [_flow("2026-06-30", "2025-07-01", 175)],
        }, "2026-06-30")
        assert fin.fields["capex"].value == 100
        assert fin.fields["capex"].concept == PPE

    def test_a_fresh_productive_assets_beats_a_fresh_new_tag(self):
        """The L-4d recoveries (NVDA / V / LRCX) must not be re-based by L-4d.1."""
        fin = resolve_financials({
            PRD: [_flow("2026-06-30", "2025-07-01", 1_571)],
            OTHER_PPE: [_flow("2026-06-30", "2025-07-01", 4_000)],
        }, "2026-06-30")
        assert fin.fields["capex"].value == 1_571
        assert fin.fields["capex"].concept == PRD

    def test_THE_FN_SHAPE_a_5110_day_stale_new_tag_changes_nothing(self):
        """FN is the ONLY other name in the universe that files the new tag, and its copy
        ended 2012-06-29 — 5110 days stale, behind a fresh generic tag. Measured in the
        dark diff; pinned so FN cannot be silently re-based by a future gate change."""
        fin = resolve_financials({
            PPE: [_flow("2026-06-26", "2025-06-27", 2_871)],
            OTHER_PPE: [_flow("2012-06-29", "2011-07-01", 9_999)],
        }, "2026-06-26")
        assert STALE_TAG_DAYS < 5110
        assert fin.fields["capex"].value == 2_871
        assert fin.fields["capex"].concept == PPE

    @pytest.mark.parametrize("ticker", FIXTURE_TICKERS)
    def test_no_recorded_fixture_moves(self, ticker):
        """The dark diff measured 27 of 28 names bit-identical and ZERO non-capex field
        changes. These are the names with recorded fixtures, so it stays checkable
        offline forever."""
        capex = fetch_edgar(ticker, fixture_path=EDGAR / f"{ticker}.json").financials.fields["capex"]
        assert capex.concept != OTHER_PPE, (
            f"{ticker} was re-based onto the L-4d.1 tag — the arm was meant to reach LLY only")

    def test_THE_ARM_IS_MONOTONE_it_can_only_ADD_resolutions(self):
        """The safety property, same shape as L-4b's monotone-widening and L-4f's monotone
        form admission. A strict superset of the chain can only resolve MORE fields, never
        fewer — so no name that resolved before can stop resolving.

        Stated over the spec rather than over the universe, because a universe sweep only
        proves it for today's 28 names.
        """
        names = [c for c, _ns in _capex_spec().synonyms]
        assert names[:2] == [PPE, PRD], (
            "the pre-L-4d.1 chain must remain an ordered PREFIX of the new chain — "
            "if it is not, the addition is no longer monotone and this pin is the wrong pin")
        assert len(names) == 3


# ── the fixture-aging hazard does NOT recur here ─────────────────────────────

def test_NO_fixture_holds_the_new_tag_so_no_fixture_AGES():
    """★ THE L-4d HAZARD, CHECKED AND ABSENT — and that is a measurement, not luck.

    L-4d recorded that adding a synonym silently AGES every recorded fixture, because
    fixtures store the POST-EXTRACTION concepts dict pulled from XBRL_CONCEPTS at record
    time (see test_the_V_fixture_predates_the_L4d_synonym_and_UNDERSTATES_production).
    That hazard is real and general. It does NOT bite here, for one measurable reason:
    no recorded EDGAR fixture contains OTHER_PPE at all, so there is nothing to age.

    Pinned so the conclusion is re-derived rather than assumed if a fixture is ever
    re-recorded — at which point this test fails and forces the question to be re-asked.
    """
    holders = []
    for path in sorted(EDGAR.glob("*.json")):
        if OTHER_PPE in path.read_text():
            holders.append(path.name)
    assert holders == [], (
        f"{holders} now contain {OTHER_PPE}; the L-4d fixture-aging hazard is live again "
        "and offline/live divergence must be re-reasoned before this pin is relaxed")


# ── the cross-check movement is ADVISORY ONLY ────────────────────────────────

def test_basis_mismatch_is_structurally_incapable_of_moving_confidence():
    """LLY's free_cashflow cross-check verdict moves `no_edgar` → `basis_mismatch` when the
    tag arms (EDGAR TTM 18.190B vs FMP annual 8.972B). The ruling calls that ADVISORY, and
    this pins that it is advisory STRUCTURALLY rather than by observation: a basis_mismatch
    delta carries no would_be_confidence, so `would_change` cannot be True.

    This is why arming the tag moves no score, E(R), grade or confidence label anywhere —
    the dark run's would-change list was byte-identical before and after.
    """
    from core.edgar_cross_check import VERDICT_BASIS_MISMATCH, FieldDelta

    delta = FieldDelta(fmp_field="free_cashflow", verdict=VERDICT_BASIS_MISMATCH,
                       edgar_value=18_190_000_000.0, fmp_value=8_972_000_000.0,
                       note="FMP cash-flow is annual; EDGAR is TTM")
    assert delta.would_be_confidence is None
    assert delta.would_change is False
