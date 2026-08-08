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
    APPLICABLE_VERDICTS, COMPARISONS, DIVERGENCE_TOLERANCE_PCT,
    FRESHNESS_THRESHOLD_DAYS, VERDICT_AGREE, VERDICT_BASIS_MISMATCH,
    VERDICT_CONFLICT, VERDICT_NO_EDGAR, VERDICT_STALE_CAPPED,
    apply_report, compute_cross_check, run_cross_check,
    filing_freshness_flags, freshness_watch, issuer_filing_lag, issuer_period_cadence,
    newest_filed_period, render_report, run_dark_cross_check,
)

FIXTURES = Path("tests/fixtures")
EDGAR = FIXTURES / "edgar"
TICKER = FIXTURES / "ticker"


def _pair(ticker: str):
    return (fetch_edgar(ticker, fixture_path=EDGAR / f"{ticker}.json"),
            fetch_fixture(ticker, fixture_path=TICKER / f"{ticker}.json"))


class TestComputeIsPure:
    """Computation and application are separate, and only apply_report writes.

    This was the dark-launch invariant; after arming it is what keeps arming HONEST —
    the table you read is produced without side effects, and every write is one explicit
    call that can be withheld (replays, calibration) without touching this code path.
    """

    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "V"])
    def test_applies_nothing(self, ticker):
        """No Prov on the ticker data may be touched — value, source, as_of or
        confidence — by computing the report."""
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
        """It moves a confidence label, never a value, score, E(R) or grade — so a bug in
        it must not kill an evaluation. It fails loudly and applies nothing."""
        lines = []
        assert run_cross_check("not-an-EdgarData", None, log=lines.append) is None
        assert lines and "FAILED" in lines[0] and "NOTHING APPLIED" in lines[0]

    def test_report_states_nothing_applied(self):
        edgar, yf = _pair("MU")
        assert "APPLIED=NOTHING" in render_report(compute_cross_check(edgar, yf))


class TestArmedApplication:
    """E-3 ARMED: agree→high, conflict→low, everything else leaves the field alone."""

    def _armed(self, ticker):
        edgar, yf = _pair(ticker)
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        applied = apply_report(report, yf)
        return edgar, yf, report, applied

    def test_agreement_upgrades_and_conflict_downgrades(self):
        _, yf, report, applied = self._armed("MU")
        by_field = {d.fmp_field: d for d in report.deltas}
        assert by_field["gross_margin"].verdict == VERDICT_AGREE
        assert getattr(yf, "gross_margin").confidence == "high"
        assert by_field["operating_margin"].verdict == VERDICT_CONFLICT
        assert getattr(yf, "operating_margin").confidence == "low"
        assert "gross_margin→high" in applied and "operating_margin→low" in applied

    def test_source_string_records_corroboration_and_conflict(self):
        """A field that moved must say why on inspection, not just carry a new label."""
        _, yf, _, _ = self._armed("MU")
        assert getattr(yf, "gross_margin").source.endswith("+EDGAR")
        assert "CONFLICT" in getattr(yf, "operating_margin").source

    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "V"])
    def test_values_are_never_touched(self, ticker):
        """A cross-check adjudicates confidence, never data. Applying it must not move a
        single value or as_of — that is the line between corroboration and rewriting."""
        edgar, yf = _pair(ticker)
        before = {name: (p.value, p.as_of) for name, p in vars(yf).items()
                  if isinstance(p, Prov)}
        apply_report(compute_cross_check(edgar, yf, today="2026-08-08"), yf)
        after = {name: (p.value, p.as_of) for name, p in vars(yf).items()
                 if isinstance(p, Prov)}
        assert before == after

    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "V"])
    def test_only_applicable_verdicts_move_anything(self, ticker):
        """basis_mismatch, stale_capped, no_edgar and no_fmp are logged, never applied."""
        edgar, yf = _pair(ticker)
        before = {name: p.confidence for name, p in vars(yf).items()
                  if isinstance(p, Prov)}
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        apply_report(report, yf)
        for d in report.deltas:
            now = getattr(yf, d.fmp_field).confidence
            if d.verdict in APPLICABLE_VERDICTS:
                assert now == d.would_be_confidence
            else:
                assert now == before[d.fmp_field], f"{d.fmp_field} moved on {d.verdict}"

    def test_symmetric_gate_survives_arming(self):
        """R1 is not merely a reporting nicety: with everything stale, arming writes
        nothing at all."""
        edgar, yf = _pair("MU")
        before = {name: (p.confidence, p.source) for name, p in vars(yf).items()
                  if isinstance(p, Prov)}
        report = compute_cross_check(edgar, yf, today="2026-08-08", threshold_days=10)
        assert apply_report(report, yf) == []
        after = {name: (p.confidence, p.source) for name, p in vars(yf).items()
                 if isinstance(p, Prov)}
        assert before == after

    def test_run_cross_check_applies_and_reports_what_it_applied(self):
        lines = []
        edgar, yf = _pair("MU")
        run_cross_check(edgar, yf, log=lines.append)
        assert "[EDGAR-XCHECK ARMED]" in lines[0]
        assert "APPLIED=" in lines[0] and "APPLIED=NOTHING" not in lines[0]
        assert getattr(yf, "gross_margin").confidence == "high"

    def test_apply_can_be_withheld_for_replays(self):
        lines = []
        edgar, yf = _pair("MU")
        run_cross_check(edgar, yf, log=lines.append, apply=False)
        assert "APPLIED=NOTHING" in lines[0]
        assert getattr(yf, "gross_margin").confidence == "medium"


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

    def test_total_cash_includes_short_term_investments(self):
        """FMP's total_cash is cashAndShortTermInvestments; the EDGAR side must measure
        the same thing rather than cash alone."""
        edgar, yf = _pair("MU")
        by_field = {d.fmp_field: d for d in compute_cross_check(edgar, yf).deltas}
        fields = edgar.financials.fields
        assert by_field["total_cash"].edgar_value == pytest.approx(
            fields["cash"].value + fields["short_term_investments"].value)

    def test_missing_optional_input_downgrades_to_advisory(self):
        """V files no ST-investment tag, so its cash-only value faces a broader FMP
        measure — advisory, never a conflict."""
        edgar, yf = _pair("V")
        delta = {d.fmp_field: d for d in compute_cross_check(edgar, yf).deltas}["total_cash"]
        assert delta.verdict == VERDICT_BASIS_MISMATCH
        assert not delta.would_change
        assert "short_term_investments" in delta.note

    def test_roe_uses_average_equity(self):
        """FMP computes ROE on average equity; against period-end equity the gap tracks
        equity growth (MU 29%, GOOG 25%). Averaging aligns the basis."""
        edgar, yf = _pair("MU")
        delta = {d.fmp_field: d for d in compute_cross_check(edgar, yf).deltas}["roe"]
        assert "avg w/ prior yr" in delta.edgar_inputs
        fields = edgar.financials.fields
        end_only = fields["net_income"].value / fields["equity"].value
        assert delta.edgar_value != pytest.approx(end_only)
        assert delta.divergence_pct < 10.0   # was 29.0 on the period-end basis

    def test_average_equity_follows_the_migrated_tag(self):
        """V's equity resolves via the incl-NCI variant; the prior-year lookup must use
        that same tag, not the abandoned one."""
        edgar, yf = _pair("V")
        delta = {d.fmp_field: d for d in compute_cross_check(edgar, yf).deltas}["roe"]
        assert "IncludingPortionAttributableToNoncontrollingInterest" in delta.edgar_inputs
        assert "avg w/ prior yr" in delta.edgar_inputs

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


class TestSymmetricStaleGating:
    """R1 (ruling 2026-08-08): a source too stale to upgrade is too stale to downgrade.

    The staleness engine caps only 'high', so before R1 a conflict measured on stale or
    lagged data still downgraded the field to low — confidence moving on data the same
    report declared untrustworthy.
    """

    def test_stale_data_moves_nothing_in_either_direction(self):
        """The property, asserted directly: with everything stale, no delta moves."""
        edgar, yf = _pair("MU")
        report = compute_cross_check(edgar, yf, today="2026-08-08", threshold_days=10)
        assert any(d.divergence_pct and d.divergence_pct > 5.0 for d in report.deltas), \
            "fixture must contain a conflict-sized divergence for this to prove anything"
        for d in report.deltas:
            assert not d.would_change, f"{d.fmp_field} moved while stale"
            assert d.would_be_confidence == d.current_confidence

    def test_conflict_on_stale_data_renders_stale_capped_with_divergence_kept(self):
        edgar, yf = _pair("MU")
        by_field = {d.fmp_field: d for d in
                    compute_cross_check(edgar, yf, today="2026-08-08",
                                        threshold_days=10).deltas}
        om = by_field["operating_margin"]          # 18.3% — a conflict when fresh
        assert om.verdict == VERDICT_STALE_CAPPED
        assert om.would_be_confidence == om.current_confidence
        assert om.divergence_pct > DIVERGENCE_TOLERANCE_PCT   # measured, not discarded
        assert "conflict suppressed" in om.note

    def test_the_gate_is_what_suppressed_it_not_the_tolerance(self):
        """Same field, same data, fresh: it does downgrade. Proves the test above is
        exercising the gate rather than a comparison that never conflicted."""
        edgar, yf = _pair("MU")
        by_field = {d.fmp_field: d for d in
                    compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        assert by_field["operating_margin"].verdict == VERDICT_CONFLICT
        assert by_field["operating_margin"].would_be_confidence == "low"

    def test_lagged_conflict_is_suppressed_too(self):
        """The lag half of the gate, on the ticker that prompted the ruling: V's
        companyfacts is a full quarter behind its own filings. (Live it was
        current_ratio at 10.4%; against the recorded FMP fixture the conflicting field
        is operating_margin — the gate is field-agnostic.)"""
        edgar, yf = _pair("V")
        edgar.recent_10q = [FilingRef(form="10-Q", date="2026-07-29", accession="x",
                                      primary_doc="d.htm", report_date="2026-06-30")]
        by_field = {d.fmp_field: d for d in
                    compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        om = by_field["operating_margin"]
        assert om.verdict == VERDICT_STALE_CAPPED
        assert om.would_be_confidence == om.current_confidence
        assert "conflict suppressed" in om.note and "XBRL behind submissions" in om.note

    def test_lag_suppression_needs_the_lag(self):
        """Without the submissions cross-reference V is only 130d old — inside the 150d
        backstop — so the same conflict is live. The lag is doing the work."""
        edgar, yf = _pair("V")
        by_field = {d.fmp_field: d for d in
                    compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        assert by_field["operating_margin"].verdict == VERDICT_CONFLICT


class TestFreshnessWatch:
    """R-NEW: informational staleness notice with a predicted next-data date."""

    def test_fires_past_sixty_days_with_a_prediction(self):
        edgar, _ = _pair("MU")                       # 72d at the pinned date
        line = freshness_watch(edgar, edgar.financials.latest_period_end, "2026-08-08")
        assert line.startswith("[FRESHNESS-WATCH] MU: EDGAR data 72d old")
        assert "expected ~2026-" in line

    def test_silent_inside_the_window(self):
        edgar, _ = _pair("GOOG")                     # 39d
        assert freshness_watch(edgar, edgar.financials.latest_period_end,
                               "2026-08-08") is None

    @pytest.mark.parametrize("today,fires", [("2026-07-27", False), ("2026-07-29", True)])
    def test_threshold_boundary(self, today, fires):
        """60d exactly is inside the window; 61d trips it."""
        edgar, _ = _pair("MU")                       # period-end 2026-05-28
        line = freshness_watch(edgar, edgar.financials.latest_period_end, today)
        assert (line is not None) == fires

    def test_xbrl_lag_reports_extraction_pending_not_a_prediction(self):
        """The filing already landed. Predicting a filing date here would be predicting
        something that has already happened."""
        edgar, _ = _pair("V")
        edgar.recent_10q = [FilingRef(form="10-Q", date="2026-07-29", accession="x",
                                      primary_doc="d.htm", report_date="2026-06-30")]
        line = freshness_watch(edgar, "2026-03-31", "2026-08-08")
        assert line == ("[FRESHNESS-WATCH] V: EDGAR data 130d old; June-Q filed "
                        "2026-07-29, extraction pending (XBRL-LAG); fresher data "
                        "expected imminently")
        assert "expected ~" not in line

    def test_cadence_is_anchored_to_a_core_concept(self):
        """Pooling every concept's instants poisons the median with dei cover-page
        dates, which sit between period-ends — that read MU's quarters as 77d."""
        edgar, _ = _pair("MU")
        assert issuer_period_cadence(edgar) == 91

    def test_prediction_uses_issuer_history_and_says_when_it_cannot(self):
        """Fixtures record filings without a report_date, so the issuer's own lag is
        unknowable there and the line must admit the fallback rather than imply
        issuer-specific precision."""
        edgar, _ = _pair("MU")
        assert issuer_filing_lag(edgar) is None
        assert "p90 lag — issuer filing history unavailable" in freshness_watch(
            edgar, edgar.financials.latest_period_end, "2026-08-08")

        edgar.recent_10q = [
            FilingRef("10-Q", "2026-06-25", "a", "d.htm", report_date="2026-05-28"),
            FilingRef("10-Q", "2026-04-02", "b", "d.htm", report_date="2026-02-26"),
        ]
        assert issuer_filing_lag(edgar) == 31       # even count: mean of 28 and 35
        assert "p90 lag" not in freshness_watch(
            edgar, edgar.financials.latest_period_end, "2026-08-08")

    def test_watch_is_informational_only(self):
        """It must not gate anything: MU is past the 60d watch but inside the 150d
        backstop, so its agreements still upgrade."""
        edgar, yf = _pair("MU")
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        assert report.watch
        assert any(d.verdict == VERDICT_AGREE and d.would_be_confidence == "high"
                   for d in report.deltas)

    def test_report_carries_and_renders_the_watch(self):
        edgar, yf = _pair("MU")
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        assert report.watch in render_report(report)


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
