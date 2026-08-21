"""L-4f — 20-F / 6-K FOREIGN-FILER ADMISSION. Armed 2026-08-21.

WHAT THIS CLOSES. `_XBRL_VALID_FORMS` admitted only the 10-K/10-Q family, so a foreign
private issuer filing the identical us-gaap tags on 20-F/6-K reported "no tag filed" for
every one of the 19 fields. ARM was the live case: 4,373 facts, 100% dropped, 0 of 19
resolved. L-4d made the drop VISIBLE (`form_excluded`); L-4f admits the forms.

AND THE SECOND GATE, which admission alone does not clear. `_fy_ends` decided which
period-ends are fiscal year ends with `form.startswith("10-K")`. ARM tags `fp='FY'`
correctly — on 20-F — so `_fy_ends` returned the EMPTY SET and every point, including the
five that ARE fiscal year ends, was labelled `TTM_Q`. Step 4 reads `period_type='FY'` only,
so admitting the forms without this would have written five KNOWN-FALSE labels into
production and still delivered +0 evaluability. Ruled into this order (option a) precisely
because landing (b) is what the L-4d ruling forbids.

WHY THESE PINS ARE SYNTHETIC-FACT PINS AND NOT FIXTURE PINS. The fixture replay path
(`edgar_adapter.py:952`) calls `resolve_financials` DIRECTLY and never runs
`_extract_xbrl_facts`, so the form filter has NO offline coverage from the recorded fixture
set and none can be added without recording a foreign-filer fixture. These drive the
extractor directly, the shape `tests/test_l4d_typed_reasons.py` established.

Verified to FAIL against the pre-fix code before landing.
"""
import pytest

from adapters.edgar_adapter import (
    _XBRL_ANNUAL_FORMS,
    _XBRL_INTERIM_FORMS,
    _XBRL_VALID_FORMS,
    _extract_xbrl_facts,
)
from core import fundamental_series as FS
from core.fundamental_series import _fy_ends

OCF = "NetCashProvidedByUsedInOperatingActivities"
PPE = "PaymentsToAcquirePropertyPlantAndEquipment"
REV = "RevenueFromContractWithCustomerExcludingAssessedTax"

# ARM's real fiscal calendar: FY ends 03-31, 20-F annual, 6-K for Q1/Q2/Q3, no Q4 standalone.
FY26 = ("2025-04-01", "2026-03-31")
Q1_27 = ("2026-04-01", "2026-06-30")
Q1_26 = ("2025-04-01", "2025-06-30")


def _fact(val, start, end, form, fp, accn="0000000000-26-000001"):
    return {"val": val, "start": start, "end": end, "fy": 2026, "fp": fp,
            "form": form, "accn": accn, "filed": "2026-05-26"}


def _payload(**concept_facts):
    return {"facts": {"us-gaap": {
        c: {"units": {"USD": facts}} for c, facts in concept_facts.items()}}}


def _arm_shape(concept, base):
    """The real ARM duration profile for one cash-flow concept: a 20-F full year, a 6-K
    current-quarter YTD and the prior-year 6-K YTD — the three legs ttm_reconstructed needs.
    """
    return [
        _fact(base * 4, *FY26, "20-F", "FY"),
        _fact(base, *Q1_27, "6-K", "Q1"),
        _fact(base // 2, *Q1_26, "6-K", "Q1", accn="0000000000-25-000001"),
    ]


class _Edgar:
    def __init__(self, fin):
        self.financials = fin


# ── THE ADMISSION ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("form", ["20-F", "20-F/A", "6-K", "6-K/A"])
def test_the_foreign_forms_are_admitted(form):
    assert form in _XBRL_VALID_FORMS


@pytest.mark.parametrize("form", ["10-K", "10-K/A", "10-Q", "10-Q/A"])
def test_the_domestic_family_is_untouched(form):
    """Admission ADDS. Nothing that resolved before may stop resolving."""
    assert form in _XBRL_VALID_FORMS


def test_the_admission_is_MONOTONE_it_can_only_add_facts():
    """THE SAFETY PROPERTY THE ARM RESTS ON, pinned the way L-4b pinned monotone-widening.

    The change is a strict superset of the old form set. A superset filter can only KEEP
    more facts, never fewer, so no name that resolved before this order can stop resolving
    because of it. If a future edit ever REMOVES a form, this fails loudly rather than
    silently un-resolving a live name.
    """
    assert {"10-K", "10-Q", "10-K/A", "10-Q/A"} <= _XBRL_VALID_FORMS


def test_annual_and_interim_partition_the_admitted_set():
    assert _XBRL_ANNUAL_FORMS | _XBRL_INTERIM_FORMS == _XBRL_VALID_FORMS
    assert not (_XBRL_ANNUAL_FORMS & _XBRL_INTERIM_FORMS)


@pytest.mark.parametrize("form", ["S-1", "S-1/A", "S-8", "8-K", "DEF 14A", "424B2", "F-1", "F-1/A", "40-F"])
def test_the_admission_is_BOUNDED_other_forms_stay_excluded(form):
    """The order admits two form families, not "everything foreign".

    F-1 is on this list deliberately: it is SKHY's only form and it is a REGISTRATION
    STATEMENT, not a periodic report — SKHY's entire companyfacts is an SEC filing-fee
    table. 40-F is here because no universe name files one today, so admitting it would be
    unmeasured. Both are their own rulings if ever wanted.
    """
    assert form not in _XBRL_VALID_FORMS


def test_a_20F_fact_now_survives_extraction():
    fin = _extract_xbrl_facts(_payload(**{OCF: [_fact(1_524_000_000, *FY26, "20-F", "FY")]}))
    assert fin.concepts.get(OCF), "20-F fact was dropped"
    assert fin.fields["operating_cashflow"].value == 1_524_000_000
    assert fin.fields["operating_cashflow"].reason is None


def test_a_6K_fact_now_survives_extraction():
    fin = _extract_xbrl_facts(_payload(**{OCF: [
        _fact(4_000_000_000, "2025-07-01", "2026-06-30", "6-K", "Q1")]}))
    assert fin.concepts.get(OCF), "6-K fact was dropped"


def test_form_excluded_still_records_genuinely_excluded_forms():
    """L-4d's discard tracking must SURVIVE the admission, or the next form gap goes
    invisible exactly the way this one did."""
    fin = _extract_xbrl_facts(_payload(**{OCF: [_fact(1, *FY26, "S-1", "FY")]}))
    assert fin.concepts == {}
    assert fin.form_excluded[OCF] == {"S-1": 1}


# ── THE FY GATE ──────────────────────────────────────────────────────────────

def test_fy_ends_recognises_a_FY_fact_on_20F():
    """THE SECOND GATE. Without this, admission delivers +0 step-4 evaluability and writes
    five rows asserting TTM_Q about periods the issuer itself tagged FY."""
    fin = _extract_xbrl_facts(_payload(**{OCF: [_fact(1_524_000_000, *FY26, "20-F", "FY")]}))
    assert _fy_ends(fin, [OCF]) == {"2026-03-31"}


def test_fy_ends_still_recognises_a_FY_fact_on_10K():
    fin = _extract_xbrl_facts(_payload(**{OCF: [
        _fact(1_000, "2025-01-01", "2025-12-31", "10-K", "FY")]}))
    assert _fy_ends(fin, [OCF]) == {"2025-12-31"}


@pytest.mark.parametrize("form", ["10-Q", "6-K"])
def test_an_INTERIM_form_never_labels_a_fiscal_year_end(form):
    """Fail-closed direction. An interim filing repeating a full-year comparative must not
    mint an FY label — that is how a TTM point would be read as an annual one."""
    fin = _extract_xbrl_facts(_payload(**{OCF: [
        _fact(1_000, "2025-01-01", "2025-12-31", form, "FY")]}))
    assert _fy_ends(fin, [OCF]) == set()


def test_the_gate_rewrite_is_EQUIVALENT_on_domestic_forms():
    """NO-REGRESSION PIN (passes before AND after — that is the point).

    `_fy_ends` reads POST-extraction concepts, so it only ever sees admitted forms. Over
    the OLD admitted set, `startswith("10-K")` IS membership in {10-K, 10-K/A}. This
    asserts the two rules agree on every domestic form, so the rewrite cannot have moved a
    domestic label. Measured across the universe when this landed: the only 10-K*/20-F*
    strings that exist anywhere are 10-K, 10-K/A and 20-F — no 10-KT, no 10-K405.
    """
    for form in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
        fin = _extract_xbrl_facts(_payload(**{OCF: [
            _fact(1_000, "2025-01-01", "2025-12-31", form, "FY")]}))
        old_rule = form.startswith("10-K")
        assert bool(_fy_ends(fin, [OCF])) == old_rule, form


# ── END TO END, THE REAL ARM SHAPE ───────────────────────────────────────────

def test_the_ARM_shape_resolves_TTM_across_20F_and_6K():
    """Path 3 (ttm_reconstructed) needs BOTH forms: the 20-F supplies prior_fy, the 6-K
    supplies current and prior-year YTD. This is why the ruled scope is 20-F AND 6-K —
    20-F alone resolves only ttm_annual, one quarter staler.
    """
    fin = _extract_xbrl_facts(_payload(**{OCF: _arm_shape(OCF, 1_000_000)}))
    rf = fin.fields["operating_cashflow"]
    assert rf.method == "ttm_reconstructed"
    assert rf.value == 4_000_000 + 1_000_000 - 500_000
    assert rf.period_end == "2026-06-30"


def test_the_ARM_shape_emits_a_series_with_a_TRUTHFUL_FY_LABEL():
    """The whole order in one assertion: a foreign filer's fiscal year end is labelled FY,
    so step 4 (`period_type='FY'`) can see it."""
    fin = _extract_xbrl_facts(_payload(
        **{OCF: _arm_shape(OCF, 1_000_000),
           PPE: _arm_shape(PPE, 100_000),
           REV: _arm_shape(REV, 5_000_000)}))
    result = FS.build_fcf_series("ARMLIKE", _Edgar(fin), None, None)

    assert not result.withheld, result.withheld
    fcf = [p for p in result.points if p.metric == FS.METRIC_FCF]
    by_end = {p.period_end: p.period_type for p in fcf}
    assert by_end.get("2026-03-31") == FS.PERIOD_FY, by_end
    assert by_end.get("2026-06-30") == FS.PERIOD_TTM_Q, by_end


def test_a_foreign_filer_no_longer_reports_form_excluded_for_admitted_forms():
    """The reason L-4d gave ARM was TRUE and is now OBSOLETE — the facts are read, so there
    is nothing to report as discarded. A reason that outlives its cause is the next
    mislabel."""
    fin = _extract_xbrl_facts(_payload(
        **{OCF: _arm_shape(OCF, 1_000_000), PPE: _arm_shape(PPE, 100_000)}))
    assert OCF not in (fin.form_excluded or {})
    result = FS.build_fcf_series("ARMLIKE", _Edgar(fin), None, None)
    assert not result.withheld


def test_the_SKHY_shape_stays_correctly_fail_closed():
    """SKHY was the order's named payload and gains NOTHING — measured, not assumed. Its
    entire companyfacts is an `ffd` filing-fee table from an F-1 IPO registration: no
    us-gaap namespace at all. Admission must not invent coverage for it.
    """
    payload = {"facts": {"ffd": {"TtlOfferingAmt": {"units": {"USD": [
        {"val": 1_000_000_000, "end": "2026-06-22", "fy": None, "fp": None,
         "form": "F-1", "accn": "0001193125-26-280172", "filed": "2026-06-24"}]}}}}}
    fin = _extract_xbrl_facts(payload)
    assert fin.concepts == {}
    result = FS.build_fcf_series("SKHYLIKE", _Edgar(fin), None, None)
    assert "no_tag" in result.withheld[FS.METRIC_FCF]
