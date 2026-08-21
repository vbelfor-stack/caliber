"""L-4d step 3 — typed withholding reasons must be EVIDENCE-BACKED. Armed 2026-08-21.

THE DEFECT THIS CLOSES. `core/fundamental_series.py` recorded `no_operating_cashflow_tag`
or `no_capex_tag` — assertions about the ISSUER'S FILINGS — on a condition that only
measured whether OUR reader returned points. It was wrong for 9 of the 13 names it fired
on. In every one of those the tag WAS filed, and the real causes were TTM assembly with no
prior-year leg, a taxonomy migration past the staleness gate, and the 20-F form filter.

The fix is structural, not a better string: the reason is now taken from the resolver's own
`ResolvedField.reason`/`.detail`, and the two constants that could assert absence without
evidence were DELETED. These tests pin the guarantee so the class cannot come back.

Everything here is offline — synthetic companyfacts through the real extractor, plus the
recorded fixtures.
"""
from pathlib import Path

import pytest

from adapters.edgar_adapter import (
    FIELD_SPECS,
    XBRL_CONCEPTS,
    _extract_xbrl_facts,
    fetch_edgar,
    resolve_financials,
)
from core import fundamental_series as FS

FIXTURE_TICKERS = ("MU", "GOOG", "NOW", "JPM", "BK", "C", "V", "WU", "USB")
OCF = "NetCashProvidedByUsedInOperatingActivities"
PPE = "PaymentsToAcquirePropertyPlantAndEquipment"

# Reason codes that assert the issuer does not file the tag. These are the only ones that
# can be contradicted by observed facts, which is what makes them the ones worth policing.
ABSENCE_CLAIMS = {"no_tag"}


def _facts(concept, form, start, end, val, ns="us-gaap"):
    return {"facts": {ns: {concept: {"units": {"USD": [
        {"val": val, "start": start, "end": end, "fy": 2026, "fp": "FY",
         "form": form, "accn": "0000000000-26-000001", "filed": "2026-03-01"}]}}}}}


def _merge(*payloads):
    out = {"facts": {"us-gaap": {}}}
    for p in payloads:
        out["facts"]["us-gaap"].update(p["facts"]["us-gaap"])
    return out


class _Edgar:
    def __init__(self, fin):
        self.financials = fin


# ── THE INVARIANT ────────────────────────────────────────────────────────────

def _absence_claims_contradicted_by_evidence(fin):
    """Every (field, concept) where we claim 'no tag' while HOLDING facts for that tag.

    This is the contradiction the whole order exists to make impossible: a recorded reason
    that the evidence we ourselves collected already refutes.
    """
    bad = []
    excluded = getattr(fin, "form_excluded", {}) or {}
    for spec in FIELD_SPECS:
        rf = fin.fields.get(spec.name)
        if rf is None or rf.reason not in ABSENCE_CLAIMS:
            continue
        for concept, _ns in spec.synonyms:
            observed = len(fin.concepts.get(concept, []))
            dropped = sum((excluded.get(concept) or {}).values())
            if observed or dropped:
                bad.append((spec.name, concept, observed, dropped))
    return bad


@pytest.mark.parametrize("ticker", FIXTURE_TICKERS)
def test_no_absence_claim_is_contradicted_by_observed_facts(ticker):
    """THE PERMANENT GUARANTEE, over every recorded fixture.

    A field may say "no tag filed" ONLY when we hold no facts for any concept in its
    chain — neither kept nor form-dropped. Any other combination is a reason refuted by
    our own evidence.
    """
    fin = fetch_edgar(ticker, fixture_path=Path(f"tests/fixtures/edgar/{ticker}.json")).financials
    bad = _absence_claims_contradicted_by_evidence(fin)
    assert not bad, f"{ticker}: reason claims absence but facts were observed: {bad}"


def test_the_invariant_BITES_positive_control():
    """POSITIVE CONTROL. The test above passes trivially if the checker can never fire, so
    construct the shape — a concept present in companyfacts but filed only on a form we do
    not read — and assert the checker WOULD flag it if the reason stayed `no_tag`. Without
    this, the fixture sweep proves nothing.

    ★ EXEMPLAR FORM CHANGED AT L-4f (2026-08-21), DELIBERATELY. This was written with 20-F,
    which WAS the live ARM case. L-4f ADMITTED 20-F/6-K, so ARM now resolves and 20-F can no
    longer stand for "a form we do not read". The mechanism this pins is unchanged and still
    load-bearing — it is what will surface the NEXT form gap — so the test keeps its job and
    swaps to S-1, a registration statement that remains outside `_XBRL_VALID_FORMS`.
    Rewriting the exemplar is the honest move; deleting the test would retire a live guard
    because one issuer stopped needing it.
    """
    payload = _merge(_facts(OCF, "S-1", "2025-04-01", "2026-03-31", 1_524_000_000),
                     _facts(PPE, "S-1", "2025-04-01", "2026-03-31", 545_000_000))
    fin = _extract_xbrl_facts(payload)

    # Extraction dropped everything, so the resolver honestly sees nothing...
    assert fin.concepts == {}
    assert fin.fields["operating_cashflow"].reason == "no_tag"
    # ...but we RECORDED what we discarded, so the contradiction is detectable.
    assert fin.form_excluded[OCF] == {"S-1": 1}
    flagged = _absence_claims_contradicted_by_evidence(fin)
    assert ("operating_cashflow", OCF, 0, 1) in flagged, flagged


def test_the_builder_reports_form_excluded_NOT_no_tag():
    """End to end. The reason a consumer sees must say the facts exist and we did not read
    them — the opposite of 'the issuer does not file it'.

    ★ Exemplar changed 20-F → S-1 at L-4f for the reason in the positive control above.
    """
    payload = _merge(_facts(OCF, "S-1", "2025-04-01", "2026-03-31", 1_524_000_000),
                     _facts(PPE, "S-1/A", "2025-04-01", "2026-03-31", 545_000_000))
    result = FS.build_fcf_series("REGONLY", _Edgar(_extract_xbrl_facts(payload)), None, None)
    reason = result.withheld[FS.METRIC_FCF]
    assert "form_excluded" in reason
    assert "no_tag" not in reason
    detail = result.withheld_detail[FS.METRIC_FCF]
    assert "NOT absent from the filings" in detail
    assert "S-1" in detail


# ── the reason IS the resolver's reason ──────────────────────────────────────

def test_reason_is_the_resolvers_own_code_not_a_restatement():
    """TTM unassemblable (the CBRS/DPC/SPCX/XE shape): a single YTD fact, no prior FY."""
    payload = _merge(
        _facts(OCF, "10-Q", "2026-01-01", "2026-06-30", -47_488_000),
        _facts(PPE, "10-Q", "2026-01-01", "2026-06-30", 548_873_000))
    fin = _extract_xbrl_facts(payload)
    assert fin.fields["operating_cashflow"].reason == "ttm_unavailable"

    result = FS.build_fcf_series("YTDONLY", _Edgar(fin), None, None)
    assert result.withheld[FS.METRIC_FCF] == (
        "operating_cashflow:ttm_unavailable; capex:ttm_unavailable")
    # The evidence travels with the reason, not just the code.
    assert "prior FY missing" in result.withheld_detail[FS.METRIC_FCF]


def test_a_stale_chain_reports_stale_not_absent():
    """THE LLY SHAPE. Abandoning a tag is not the same fact as never filing it, and the
    reason must not conflate them — that conflation is what mis-filed LLY as Class 1."""
    fin = resolve_financials({
        OCF: [{"value": 1.0, "unit": "USD", "start": "2025-07-01", "end": "2026-06-30",
               "fy": None, "fp": "FY", "form": "10-K", "accession": "a"}],
        "PaymentsToAcquireProductiveAssets": [
            {"value": 2.0, "unit": "USD", "start": "2021-10-01", "end": "2022-09-30",
             "fy": None, "fp": "FY", "form": "10-K", "accession": "a"}],
    }, "2026-06-30")
    reason, _detail = FS.withheld_reason(fin, "capex")
    assert reason == "capex:stale_tag"


def test_every_blocked_input_is_reported_not_just_the_first():
    """THE XE LESSON. Two sequential `if not X: return` reported only the earlier leg, so
    XE was recorded as an OCF problem for a whole order while ALSO carrying a capex spec
    gap that nothing surfaced. A short-circuit on the first withholding hides every later
    one, and the hidden ones then look absent."""
    payload = _merge(
        _facts(OCF, "10-Q", "2026-01-01", "2026-06-30", 100),      # ttm_unavailable
        _facts("Revenues", "10-K", "2025-07-01", "2026-06-30", 900))  # capex: no tag at all
    result = FS.build_fcf_series("BOTH", _Edgar(_extract_xbrl_facts(payload)), None, None)
    reason = result.withheld[FS.METRIC_FCF]
    assert "operating_cashflow:" in reason and "capex:" in reason, reason


def test_a_resolved_field_with_no_series_is_its_own_named_code():
    """Not folded into another reason. No name in the universe does this today, so if it
    ever fires it must be visibly NEW rather than quietly wearing an existing label."""
    assert FS.REASON_SERIES_EMPTY == "series_empty_despite_live_value"
    assert FS.REASON_SERIES_EMPTY not in (FS.WITHHELD_NO_DA_SPEC, FS.REASON_FORM_EXCLUDED)


# ── the deleted constants must stay deleted ──────────────────────────────────

def test_the_tag_absence_constants_are_GONE_and_must_not_return():
    """RETIRED BY NAME (L-4d): WITHHELD_NO_CAPEX = "no_capex_tag" and WITHHELD_NO_OCF =
    "no_operating_cashflow_tag".

    Both asserted a fact about the filings that this module cannot know. Re-adding either
    re-creates the defect wholesale, because a constant cannot consult the resolver. The
    replacement is `withheld_reason()`, which asks.

    WITHHELD_NO_DA_SPEC deliberately survives: it is a claim about OUR SPEC TABLE, which
    is knowable here and true, and it is the only one of the three ever persisted.
    """
    assert not hasattr(FS, "WITHHELD_NO_CAPEX")
    assert not hasattr(FS, "WITHHELD_NO_OCF")
    assert FS.WITHHELD_NO_DA_SPEC == "no_da_spec"

    source = open("core/fundamental_series.py", encoding="utf-8").read()
    body = "\n".join(line for line in source.splitlines()
                     if not line.lstrip().startswith("#"))
    for banned in ('= "no_capex_tag"', '= "no_operating_cashflow_tag"'):
        assert banned not in body, (
            f"a tag-absence constant was re-introduced ({banned}) — see this test's "
            f"docstring before doing that")


def test_form_excluded_is_a_diagnostic_and_moves_no_resolution():
    """The record of dropped facts must not become an input. Resolution with and without
    the diagnostic populated is identical — it exists to explain a reason, never to
    change one.

    ★ Exemplar changed 20-F → S-1 at L-4f (2026-08-21) — see the positive control above.
    """
    payload = _merge(_facts(OCF, "S-1", "2025-04-01", "2026-03-31", 1_524_000_000))
    fin = _extract_xbrl_facts(payload)
    assert fin.form_excluded                      # populated
    baseline = resolve_financials(fin.concepts, fin.latest_period_end)
    assert {k: (v.value, v.reason) for k, v in fin.fields.items()} == \
           {k: (v.value, v.reason) for k, v in baseline.fields.items()}


def test_every_spec_concept_is_watched_for_form_exclusion():
    """The diagnostic keys off XBRL_CONCEPTS, which is derived from the spec table — so a
    concept added to a chain is watched automatically and cannot be silently unmonitored.
    """
    watched = {c for c, _ns in XBRL_CONCEPTS}
    for spec in FIELD_SPECS:
        for concept, _ns in spec.synonyms:
            assert concept in watched, f"{spec.name}/{concept} is not pulled at extraction"
