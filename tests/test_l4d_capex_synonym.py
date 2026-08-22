"""L-4d — the `capex` synonym chain, armed 2026-08-21.

WHAT THIS PINS AND WHY IT EXISTS. `FIELD_SPECS` gave `capex` exactly one concept,
`PaymentsToAcquirePropertyPlantAndEquipment`. NVDA abandoned it at 2020-07-26, and V and
LRCX never filed it at all — all three file `PaymentsToAcquireProductiveAssets`. Because a
single-tag spec goes QUIET rather than LOUD when an issuer restates its taxonomy, all three
withheld the entire FCF family while still resolving 14-16 of the other 19 fields, and
nothing objected for as long as the condition existed. These tests are the loudness that
was missing.

Everything here runs offline: the migration shapes are synthetic (`resolve_financials` over
hand-built facts), and the no-regression pins run against the recorded EDGAR fixtures. The
three recovering issuers have no fixtures, so their behaviour is pinned by SHAPE rather
than by name — which is the stronger pin anyway, since the next migration will be a
different issuer.

Evidence and the full dark diff: docs/l4d-capex-synonym.md.
"""
from pathlib import Path

import pytest

from adapters.edgar_adapter import (
    FIELD_SPECS,
    REASON_NO_TAG,
    REASON_STALE_TAG,
    STALE_TAG_DAYS,
    XBRL_CONCEPTS,
    fetch_edgar,
    resolve_financials,
)

EDGAR = Path("tests/fixtures/edgar")
FIXTURE_TICKERS = ("MU", "GOOG", "NOW", "JPM", "BK", "C")

PPE = "PaymentsToAcquirePropertyPlantAndEquipment"
PRD = "PaymentsToAcquireProductiveAssets"
OTHER_PPE = "PaymentsToAcquireOtherPropertyPlantAndEquipment"


def _capex_spec():
    return next(s for s in FIELD_SPECS if s.name == "capex")


def _flow(end, start, value, form="10-K", fp="FY"):
    """One duration fact spanning a full fiscal year — the ttm_annual path."""
    return {"value": float(value), "unit": "USD", "start": start, "end": end,
            "fy": None, "fp": fp, "form": form, "accession": "0000000000-26-000001"}


def _fields(ticker):
    return fetch_edgar(ticker, fixture_path=EDGAR / f"{ticker}.json").financials.fields


# ── the chain itself ─────────────────────────────────────────────────────────

class TestCapexChainShape:

    def test_both_concepts_are_in_the_chain(self):
        """★ SUPERSEDED AT L-4d.1 (2026-08-22) — docs/orders/2026-08-22-l4d1-lly-capex-basis.md.

        Was `== [PPE, PRD]`. L-4d.1 armed OTHER_PPE as the THIRD entry, so the two-tag
        assertion became false. The pin is WIDENED, not weakened: it still asserts the
        chain EXACTLY and in order, so a fourth tag cannot arrive unnoticed either.
        """
        assert [c for c, _ns in _capex_spec().synonyms] == [PPE, PRD, OTHER_PPE]

    def test_the_generic_tag_stays_first(self):
        """Priority order is the whole no-regression argument: an issuer already
        resolving on the generic tag must keep resolving on it, unchanged."""
        assert _capex_spec().synonyms[0][0] == PPE

    def test_both_concepts_are_pulled_from_companyfacts(self):
        """XBRL_CONCEPTS is derived from the spec table — one place to add a tag. If that
        derivation ever breaks, the spec would list a concept nobody fetches."""
        names = {c for c, _ns in XBRL_CONCEPTS}
        assert PPE in names and PRD in names

    def test_conflict_check_is_off_and_that_is_deliberate(self):
        """Productive assets is the BROADER class and PP&E is a subset of it, so the two
        are distinct measures that are merely substitutable — the revenue / current_debt
        pattern, not the ambiguous-synonym pattern. Ruled 2026-08-21."""
        assert _capex_spec().conflict_check is False

    def test_LLY_third_tag_is_ARMED(self):
        """★ SUPERSEDED AT L-4d.1 (2026-08-22) — RENAMED FROM
        `test_LLY_third_tag_is_deliberately_absent`, WHICH ASSERTED THE OPPOSITE.
        Order: docs/orders/2026-08-22-l4d1-lly-capex-basis.md §3.

        THE REVERSAL IS RECORDED HERE, NOT HIDDEN. The old pin read "RULED OUT, NOT
        OVERLOOKED (2026-08-21)" and its rationale was that OTHER_PPE failed the FMP
        reconciliation the other three tags passed — FMP's capitalExpenditure for LLY
        bundles PaymentsToAcquireInProcessResearchAndDevelopment in FY2023 (+$3.944B, to
        the dollar) and FY2024 (+$3.346B), then drops it in FY2025.

        Superseded on two ruled grounds, neither of which is "the old pin was wrong":
          1. CHRONOLOGY. The old pin is L-4d step-2 era (c7a3813). The governing ruling
             post-dates it and cites the L-4f ARM precedent, which did not yet exist.
          2. RETIRED PREDICATE. The ARM precedent settles the principle: intangible /
             IPR&D-class acquisitions are NOT capital intensity, so where FMP bundles them
             and the issuer's own tag is definitionally consistent, THE EDGAR TAG STANDS
             and the disagreement is an advisory basis note. The old pin's own text
             concedes FMP "is not self-consistent year to year" — under the precedent that
             is a finding against the FEED, not a disqualification of the tag.

        The measurement that decided it: FY2025 reconciles to the dollar (EDGAR-derived
        8.972B vs FMP 8972000000). See tests/test_l4d1_lly_capex_basis.py for the rest.
        """
        assert OTHER_PPE in {c for c, _ns in _capex_spec().synonyms}


# ── the migration shape (the NVDA case), synthetic ───────────────────────────

class TestTagMigrationResolves:

    def test_stale_primary_falls_through_to_the_fresh_synonym(self):
        """THE NVDA SHAPE. Primary abandoned years ago, successor current. Before L-4d
        this resolved to None and withheld the whole FCF family."""
        fin = resolve_financials({
            PPE: [_flow("2020-07-26", "2019-07-29", 1_000)],
            PRD: [_flow("2026-04-26", "2025-04-28", 6_572)],
        }, "2026-04-26")
        capex = fin.fields["capex"]
        assert capex.value == 6_572
        assert capex.concept == PRD
        assert capex.reason is None
        assert any(f"{PPE}:stale(" in t for t in capex.trail)

    def test_synonym_only_resolves(self):
        """THE V / LRCX SHAPE — the generic tag was never filed at all."""
        fin = resolve_financials({
            PRD: [_flow("2026-03-31", "2025-04-01", 1_571)],
        }, "2026-03-31")
        assert fin.fields["capex"].value == 1_571
        assert fin.fields["capex"].concept == PRD

    def test_a_single_tag_spec_goes_QUIET_on_this_input_POSITIVE_CONTROL(self):
        """THE POSITIVE CONTROL, and the reason the defect survived so long.

        Resolves the SAME facts twice — once against a one-synonym spec (what shipped
        until 2026-08-21) and once against the real chain — and asserts the one-tag
        result is a silent None rather than a loud failure. Without this the passing
        tests above could not distinguish "the chain works" from "the input was easy".
        """
        from adapters.edgar_adapter import FieldSpec, _resolve_one

        facts = {
            PPE: [_flow("2020-07-26", "2019-07-29", 1_000)],
            PRD: [_flow("2026-04-26", "2025-04-28", 6_572)],
        }
        old = _resolve_one(
            FieldSpec("capex", "flow", ((PPE, "us-gaap"),)),
            facts, "2026-04-26", STALE_TAG_DAYS)
        # QUIET: no value, no exception, just a typed reason on one field of nineteen.
        assert old.value is None
        assert old.reason == REASON_STALE_TAG

        new = _resolve_one(_capex_spec(), facts, "2026-04-26", STALE_TAG_DAYS)
        assert new.value == 6_572
        assert new.reason is None

    def test_neither_tag_filed_is_still_a_clean_no_tag(self):
        """JPM / USB / INFQ file no PP&E-purchase concept of any kind — checked across
        every us-gaap concept, not just our spec. Fail-closed must stay fail-closed."""
        fin = resolve_financials({"Assets": [
            {"value": 1.0, "unit": "USD", "start": None, "end": "2026-06-30",
             "fy": None, "fp": None, "form": "10-K", "accession": "a"}]}, "2026-06-30")
        assert fin.fields["capex"].value is None
        assert fin.fields["capex"].reason == REASON_NO_TAG

    def test_both_stale_withholds_rather_than_using_an_expired_tag(self):
        """THE LLY SHAPE. A chain whose every entry is abandoned must withhold — a stale
        figure passed downstream wearing a fresh label could agree with FMP inside the
        cross-check tolerance and launder to high confidence."""
        fin = resolve_financials({
            PRD: [_flow("2022-09-30", "2021-10-01", 2_000)],
        }, "2026-06-30")                                   # 1369d lag >> STALE_TAG_DAYS
        assert STALE_TAG_DAYS < 1369
        assert fin.fields["capex"].value is None
        assert fin.fields["capex"].reason == REASON_STALE_TAG


# ── no regression on anything already resolving ──────────────────────────────

class TestNoRegression:

    @pytest.mark.parametrize("ticker", FIXTURE_TICKERS)
    def test_fixture_capex_is_unchanged_by_the_added_synonym(self, ticker):
        """The dark diff measured ZERO capex movement on all 15 covered names. These are
        the six with recorded fixtures, so the property is checkable offline forever."""
        capex = _fields(ticker)["capex"]
        if ticker in ("JPM",):
            assert capex.value is None          # real data limit, files no such concept
        else:
            assert capex.is_resolved(), f"{ticker} capex regressed: {capex.reason}"
            assert capex.concept == PPE, (
                f"{ticker} capex moved off the generic tag to {capex.concept}")

    def test_a_fresh_primary_wins_over_a_stale_synonym(self):
        """THE CAT / WU SHAPE — both hold a stale ProductiveAssets copy behind a fresh
        generic tag. The staleness gate skips the stale entry BEFORE the conflict check is
        reached, so no covered name can be withheld by the new chain."""
        fin = resolve_financials({
            PPE: [_flow("2026-06-30", "2025-07-01", 2_871)],
            PRD: [_flow("2019-12-31", "2019-01-01", 9_999)],
        }, "2026-06-30")
        assert fin.fields["capex"].value == 2_871
        assert fin.fields["capex"].concept == PPE

    def test_two_fresh_tags_do_NOT_withhold_under_conflict_check_False(self):
        """The behavioural consequence of conflict_check=False, stated as a value rather
        than as a flag. No issuer files both fresh TODAY — measured across all 28 — so
        this pins what a FUTURE dual-filer gets: priority order decides, nothing is
        withheld, and the broader measure never silently displaces PP&E."""
        fin = resolve_financials({
            PPE: [_flow("2026-06-30", "2025-07-01", 100)],
            PRD: [_flow("2026-06-30", "2025-07-01", 175)],     # 75% apart
        }, "2026-06-30")
        capex = fin.fields["capex"]
        assert capex.value == 100
        assert capex.concept == PPE
        assert capex.reason is None
        # NON-VACUITY: prove BOTH tags were walked. Against the pre-L-4d single-tag spec
        # the assertions above pass for the wrong reason — PRD was simply never consulted.
        assert any(t.startswith(PRD) for t in capex.trail), capex.trail


# ── the FCF family is what this unblocks ─────────────────────────────────────

class TestFcfFamilyUnblocks:

    def test_capex_on_the_migrated_tag_feeds_the_series_builder(self):
        """END TO END, the point of the change: OCF and capex on DIFFERENT tags still
        produce an FCF point. Value-level, per the L-4a finding that this suite asserted
        provenance strings where it should have asserted numbers."""
        from core.fundamental_series import METRIC_FCF, build_fcf_series

        fin = resolve_financials({
            "NetCashProvidedByUsedInOperatingActivities": [
                _flow("2026-04-26", "2025-04-28", 10_000)],
            PPE: [_flow("2020-07-26", "2019-07-29", 1_000)],       # stale, skipped
            PRD: [_flow("2026-04-26", "2025-04-28", 6_572)],       # fresh, used
            "Revenues": [_flow("2026-04-26", "2025-04-28", 50_000)],
        }, "2026-04-26")

        class _Edgar:
            financials = fin

        result = build_fcf_series("TEST", _Edgar(), None, None)
        assert not result.withheld, f"FCF still withheld: {result.withheld}"
        fcf = result.by_metric(METRIC_FCF)
        assert len(fcf) == 1
        assert fcf[0].value == 10_000 - 6_572
        assert fcf[0].components["capex"] == 6_572
