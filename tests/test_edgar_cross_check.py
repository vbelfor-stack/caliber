"""
E-3 EDGAR × FMP cross-check tests — all against recorded fixtures, no live calls.

The load-bearing test in this file is test_applies_nothing: while the cross-check is dark
it must be impossible for it to move a single value or confidence anywhere downstream.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from adapters.base import Prov
from adapters.edgar_adapter import FilingRef, fetch_edgar
from adapters.fixture_adapter import fetch_fixture
from core.edgar_cross_check import (
    COMPARISONS, FRESHNESS_THRESHOLD_DAYS, VERDICT_AGREE, VERDICT_BASIS_MISMATCH,
    VERDICT_CONFLICT, VERDICT_NO_EDGAR, VERDICT_STALE_CAPPED, compute_cross_check,
    filing_freshness_flags, newest_filed_period, render_report, run_dark_cross_check,
)

FIXTURES = Path("tests/fixtures")
EDGAR = FIXTURES / "edgar"
TICKER = FIXTURES / "ticker"


def _pair(ticker: str):
    return (fetch_edgar(ticker, fixture_path=EDGAR / f"{ticker}.json"),
            fetch_fixture(ticker, fixture_path=TICKER / f"{ticker}.json"))


class TestDarkLaunchInvariant:
    """Dark means dark."""

    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "V"])
    def test_applies_nothing(self, ticker):
        """No Prov on the ticker data may be touched — value, source, as_of or
        confidence. If this fails the cross-check has stopped being dark."""
        edgar, yf = _pair(ticker)
        before = {
            name: (p.value, p.source, p.as_of, p.confidence)
            for name, p in vars(yf).items() if isinstance(p, Prov)
        }
        compute_cross_check(edgar, yf)
        after = {
            name: (p.value, p.source, p.as_of, p.confidence)
            for name, p in vars(yf).items() if isinstance(p, Prov)
        }
        assert before == after

    def test_edgar_data_not_mutated(self):
        edgar, yf = _pair("MU")
        snapshot = deepcopy(edgar.financials.fields)
        compute_cross_check(edgar, yf)
        assert edgar.financials.fields == snapshot

    def test_runner_never_raises(self):
        """A dark component gates nothing, so a bug in it must not kill an evaluation."""
        lines = []
        assert run_dark_cross_check("not-an-EdgarData", None, log=lines.append) is None
        assert lines and "FAILED" in lines[0]

    def test_report_states_nothing_applied(self):
        edgar, yf = _pair("MU")
        assert "APPLIED=NOTHING" in render_report(compute_cross_check(edgar, yf))


class TestComparisons:
    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "V"])
    def test_every_comparison_yields_a_delta(self, ticker):
        edgar, yf = _pair(ticker)
        report = compute_cross_check(edgar, yf)
        assert {d.fmp_field for d in report.deltas} == {c.fmp_field for c in COMPARISONS}

    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "V"])
    def test_unresolved_edgar_fields_never_compared(self, ticker):
        """A field EDGAR withheld must not acquire a value here by another route."""
        edgar, yf = _pair(ticker)
        for d in compute_cross_check(edgar, yf).deltas:
            if d.verdict == VERDICT_NO_EDGAR:
                assert d.edgar_value is None
                assert d.would_be_confidence == d.current_confidence

    def test_v_gaps_surface_as_no_edgar(self):
        """V files no capex or cost-of-revenue concept, so those comparisons cannot run."""
        edgar, yf = _pair("V")
        by_field = {d.fmp_field: d for d in compute_cross_check(edgar, yf).deltas}
        assert by_field["free_cashflow"].verdict == VERDICT_NO_EDGAR
        assert "capex" in by_field["free_cashflow"].note
        assert by_field["gross_margin"].verdict == VERDICT_NO_EDGAR

    def test_known_basis_mismatch_never_moves_confidence(self):
        """Advisory only: divergence is measured and shown, confidence is left alone."""
        edgar, yf = _pair("MU")
        mismatched = [d for d in compute_cross_check(edgar, yf).deltas
                      if d.verdict == VERDICT_BASIS_MISMATCH]
        assert mismatched
        for d in mismatched:
            assert d.would_be_confidence == d.current_confidence
            assert not d.would_change
            assert d.note

    def test_agreement_and_conflict_both_occur(self):
        edgar, yf = _pair("MU")
        verdicts = {d.verdict for d in compute_cross_check(edgar, yf).deltas}
        assert VERDICT_AGREE in verdicts and VERDICT_CONFLICT in verdicts


class TestPerFieldFreshness:
    """Freshness is per-field from that field's own period-end, never per-ticker."""

    def test_field_ages_from_its_own_period_end(self):
        edgar, yf = _pair("MU")
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        by_field = {d.fmp_field: d for d in report.deltas}
        gm = by_field["gross_margin"]
        assert gm.period_end == "2026-05-28"
        assert gm.age_days == 72

    def test_lagging_sibling_ages_separately(self):
        """MU's debt tags lag its income statement by a quarter, so the two age
        independently in one report — fresh siblings reach high while the lagging field
        carries its own, much older age. (Its confidence is additionally pinned by a
        basis note, so the age cap itself is exercised in test_beyond_threshold.)"""
        edgar, yf = _pair("MU")
        fields = edgar.financials.fields
        assert fields["long_term_debt"].period_end < fields["revenue"].period_end
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        by_field = {d.fmp_field: d for d in report.deltas}
        assert by_field["total_debt"].age_days > by_field["gross_margin"].age_days
        assert by_field["gross_margin"].would_be_confidence == "high"

    def test_multi_input_field_ages_from_oldest_input(self):
        edgar, yf = _pair("MU")
        by_field = {d.fmp_field: d for d in compute_cross_check(edgar, yf).deltas}
        fields = edgar.financials.fields
        assert by_field["total_debt"].period_end == min(
            fields["long_term_debt"].period_end, fields["current_debt"].period_end)

    def test_beyond_threshold_caps_at_medium(self):
        edgar, yf = _pair("MU")
        report = compute_cross_check(edgar, yf, today="2026-08-08", threshold_days=10)
        for d in report.deltas:
            assert d.would_be_confidence != "high", f"{d.fmp_field} upgraded while stale"
        assert any(d.verdict == VERDICT_STALE_CAPPED for d in report.deltas)


class TestFilingFreshnessFlags:
    def test_xbrl_lag_distinguished_from_missing_filing(self):
        """V filed its June quarter on time; companyfacts had not published it. That is
        an API lag, not a delinquent issuer, and must not be reported as one."""
        edgar, _ = _pair("V")
        edgar.recent_10q = [FilingRef(form="10-Q", date="2026-07-29",
                                      accession="x", primary_doc="d.htm",
                                      report_date="2026-06-30")]
        flags = filing_freshness_flags(edgar, "2026-03-31", "2026-08-08")
        assert len(flags) == 1
        assert flags[0].startswith("XBRL-LAG")
        assert "MISSING" not in flags[0]

    def test_missing_expected_10q_when_nothing_newer_filed(self):
        edgar, _ = _pair("V")
        edgar.recent_10k, edgar.recent_10q = [], []
        flags = filing_freshness_flags(edgar, "2026-03-31", "2026-08-08")
        assert len(flags) == 1 and flags[0].startswith("MISSING-EXPECTED-10Q")

    def test_no_flag_when_current(self):
        edgar, _ = _pair("GOOG")
        edgar.recent_10k, edgar.recent_10q = [], []
        assert filing_freshness_flags(edgar, "2026-06-30", "2026-08-08") == []

    def test_newest_filed_period_ignores_undated_refs(self):
        edgar, _ = _pair("MU")
        assert newest_filed_period(edgar) is None   # fixtures carry no report_date

    def test_lag_aware_caps_fields_behind_submissions(self):
        """A day-count gate cannot see this: V is 130d old, inside any sane threshold,
        yet a full quarter behind what the issuer has filed."""
        edgar, yf = _pair("V")
        edgar.recent_10q = [FilingRef(form="10-Q", date="2026-07-29", accession="x",
                                      primary_doc="d.htm", report_date="2026-06-30")]
        aged_only = compute_cross_check(edgar, yf, today="2026-08-08", lag_aware=False)
        lag_aware = compute_cross_check(edgar, yf, today="2026-08-08", lag_aware=True)
        assert any(d.would_be_confidence == "high" for d in aged_only.deltas)
        assert all(d.would_be_confidence != "high" for d in lag_aware.deltas)
        assert all(d.age_days is None or d.age_days < FRESHNESS_THRESHOLD_DAYS
                   for d in lag_aware.deltas if d.age_days is not None)
