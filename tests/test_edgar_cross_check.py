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
from adapters.fmp_adapter import fetch_fmp
from core.edgar_cross_check import (
    APPLICABLE_VERDICTS, COMPARISONS, DIVERGENCE_TOLERANCE_PCT,
    FRESHNESS_THRESHOLD_DAYS, VERDICT_AGREE, VERDICT_BASIS_MISMATCH,
    VERDICT_CONFLICT, VERDICT_NO_EDGAR, VERDICT_STALE_CAPPED,
    apply_report, compute_cross_check, run_cross_check,
    filing_freshness_flags, freshness_watch, issuer_filing_lag, issuer_period_cadence,
    _tracks_matched_period, latest_fiscal_year_end, newest_filed_period, render_report,
    run_dark_cross_check,
)

FIXTURES = Path("tests/fixtures")
EDGAR = FIXTURES / "edgar"
TICKER = FIXTURES / "fmp"


GOLDEN = ("MU", "GOOG", "V", "NOW", "WU")


def _pair(ticker: str):
    return (fetch_edgar(ticker, fixture_path=EDGAR / f"{ticker}.json"),
            fetch_fmp(ticker, fixture_path=TICKER / f"{ticker}.json"))


def _fmp_pair(ticker: str):
    """EDGAR + the recorded FMP feed — the pairing production actually runs.

    Kept as a distinct name from _pair for readability at the call sites that were
    written to say "this one is the production pairing" (R-C). Since the yfinance-shaped
    tests/fixtures/ticker set was retired, the two are the same source.
    """
    return (fetch_edgar(ticker, fixture_path=EDGAR / f"{ticker}.json"),
            fetch_fmp(ticker, fixture_path=FIXTURES / "fmp" / f"{ticker}.json"))


# Divergence large enough to clear every comparison's tolerance (the widest armed one is
# 5%). Applied to a single named field so a test says WHICH field conflicts.
_FORCED_CONFLICT_FACTOR = 1.5


def _pair_with_forced_conflict(ticker: str, field: str):
    """The production pairing, with ONE named field pushed deliberately out of tolerance.

    WHY THIS EXISTS. The conflict path used to be exercised BY ACCIDENT: the retired
    yfinance-shaped fixtures pre-dated the EDGAR ones, so some field or other happened to
    disagree and the downgrade path got covered as a side effect of fixture drift. That is
    not coverage — it is drift that happened to be useful, and it evaporated the moment
    fixture mode moved to the payload production actually fetches (MU's operating margin
    now agrees with EDGAR to 0.2%).

    Forcing the divergence states which field conflicts and by how much, so the test
    documents its own premise instead of inheriting it from a stale recording. It also
    means these tests keep testing the downgrade path after any future re-record, which
    the accidental version provably did not.
    """
    edgar, yf = _pair(ticker)
    prov = getattr(yf, field)
    assert not prov.is_missing(), f"{ticker}.{field} must have a value to perturb"
    prov.value = prov.value * _FORCED_CONFLICT_FACTOR
    return edgar, yf


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

    def _armed(self, ticker, conflict_field=None):
        edgar, yf = (_pair_with_forced_conflict(ticker, conflict_field)
                     if conflict_field else _pair(ticker))
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        applied = apply_report(report, yf)
        return edgar, yf, report, applied

    def test_agreement_upgrades_and_conflict_downgrades(self):
        # gross_margin agrees on the recorded data; operating_margin is pushed out of
        # tolerance on purpose so BOTH directions are exercised in one report.
        _, yf, report, applied = self._armed("MU", conflict_field="operating_margin")
        by_field = {(d.label or d.fmp_field): d for d in report.deltas}
        assert by_field["gross_margin"].verdict == VERDICT_AGREE
        assert getattr(yf, "gross_margin").confidence == "high"
        assert by_field["operating_margin"].verdict == VERDICT_CONFLICT
        assert getattr(yf, "operating_margin").confidence == "low"
        assert "gross_margin→high" in applied and "operating_margin→low" in applied

    def test_source_string_records_corroboration_and_conflict(self):
        """A field that moved must say why on inspection, not just carry a new label."""
        _, yf, _, _ = self._armed("MU", conflict_field="operating_margin")
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
        armed = [d for d in report.deltas if not d.dark]   # dark: TestDarkComparisons
        for name in {d.fmp_field for d in armed}:
            # A field may carry several armed rows (total_cash has an MRQ advisory and
            # an @FY test); only an applicable one may have moved it.
            movers = [d for d in armed if d.fmp_field == name
                      and d.verdict in APPLICABLE_VERDICTS and d.would_change]
            now = getattr(yf, name).confidence
            if movers:
                assert now == movers[0].would_be_confidence
            else:
                assert now == before[name], f"{name} moved with no applicable verdict"

    def test_symmetric_gate_survives_arming(self):
        """R1 is not merely a reporting nicety: with everything stale, arming writes
        nothing at all.

        total_cash@FY is EXEMPT — it is gated on alignment, not absolute age (R-A), so it
        legitimately still applies. It is dropped from the report here so the assertion
        measures R1 rather than R-A. The exemption used to be invisible because MU's
        retired fixture served total_cash as MRQ, revoking alignment outright.
        """
        edgar, yf = _pair("MU")
        before = {name: (p.confidence, p.source) for name, p in vars(yf).items()
                  if isinstance(p, Prov)}
        report = compute_cross_check(edgar, yf, today="2026-08-08", threshold_days=10)
        report.deltas = [d for d in report.deltas
                         if "gated on alignment" not in (d.note or "")]
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


class TestDarkComparisons:
    """R3: new comparison surface — computed, logged, applied to nothing."""

    def _report(self, ticker):
        edgar, yf = _pair(ticker)
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        return edgar, yf, report, {(d.label or d.fmp_field): d for d in report.deltas}

    # NOW and WU have EDGAR fixtures but no FMP-side ticker fixture, so the comparison
    # layer can only run offline for these three. WU's R3(a) row is covered at the
    # resolution layer in test_adapters instead.
    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "V"])
    def test_dark_rows_never_apply(self, ticker):
        """The whole point of dark-first: these rows can reach an agree/conflict verdict
        and still move nothing."""
        edgar, yf = _pair(ticker)
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        dark = [d for d in report.deltas if d.dark]
        assert dark, "R3 rows missing entirely"
        before = {name: p.confidence for name, p in vars(yf).items()
                  if isinstance(p, Prov)}
        applied = apply_report(report, yf)
        assert not any(d.fmp_field in a for d in dark for a in applied
                       if d.verdict in APPLICABLE_VERDICTS and d.would_change
                       and not any(x.fmp_field == d.fmp_field and not x.dark
                                   and x.would_change for x in report.deltas))
        for name, conf in before.items():
            armed_moved = any(not d.dark and d.would_change and d.fmp_field == name
                              for d in report.deltas)
            if not armed_moved:
                assert getattr(yf, name).confidence == conf

    def test_dark_rows_are_marked_in_the_table(self):
        """A dark row is marked 'd', never '*' — it cannot change anything yet."""
        _, _, report, _ = self._report("MU")
        rows = [ln for ln in render_report(report, applied=[]).splitlines()
                if "total_debt@FY" in ln]
        assert len(rows) == 1 and rows[0].startswith(" d")

    @pytest.mark.parametrize("ticker,fy", [("MU", "2025-08-28"), ("GOOG", "2025-12-31"),
                                           ("V", "2025-09-30")])
    def test_matched_period_reads_the_fiscal_year_end(self, ticker, fy):
        """52/53-week filers drift, so the FY period is matched on proximity to the
        issuer's declared fiscal year-end, not on equality (MU lands 2025-08-28).

        The EDGAR side is asserted against the fixture's own facts at that period. The
        0.0%-vs-FMP identity this comparison exists for is a property of LIVE FMP, which
        serves the annual balance sheet; the recorded ticker fixtures hold MRQ values, so
        it is verified in the live run rather than here."""
        edgar, _, _, by_label = self._report(ticker)
        assert latest_fiscal_year_end(edgar) == fy
        row = by_label["total_cash@FY"]
        assert row.period_end == fy

        def at_fy(concept):
            return next(r["value"] for r in edgar.financials.concepts[concept]
                        if r["end"] == fy and not r.get("start"))
        fields = edgar.financials.fields
        sti = fields["short_term_investments"]
        expected = at_fy(fields["cash"].concept) + (
            at_fy(sti.concept) if sti.is_resolved() else 0.0)
        mrq = fields["cash"].value + (sti.value if sti.is_resolved() else 0.0)
        assert row.edgar_value == pytest.approx(expected)
        assert row.edgar_value != pytest.approx(mrq), \
            "matched row must not be reading the MRQ figures"

    def test_alignment_holds_when_the_primary_tracks_the_matched_period(self):
        """R-A condition 3, satisfied: GOOG's recorded total_cash is its FY figure, so
        the annual-vs-annual premise is live and the row is aged on alignment despite
        being 220d old in absolute terms."""
        _, _, _, by_label = self._report("GOOG")
        row = by_label["total_cash@FY"]
        assert row.age_days > FRESHNESS_THRESHOLD_DAYS
        assert row.verdict == VERDICT_AGREE
        assert "gated on alignment" in row.note

    def test_alignment_revoked_when_the_primary_switches_to_mrq(self):
        """R-A condition 3, violated — and caught at runtime rather than assumed.

        When the primary's in-use value is the MRQ figure rather than the fiscal year-end
        one, the annual-vs-annual premise is false, alignment is revoked, the row ages
        absolutely (345d) and caps. This is the exact failure the scope exists to stop:
        corroborating an annual EDGAR figure against a quarterly FMP one.

        The MRQ value is now set EXPLICITLY. It used to arrive for free because the
        retired yfinance-shaped fixture happened to serve MU's total_cash as MRQ; the FMP
        payload production actually fetches serves the FY figure, so the premise had to
        become part of the test instead of a property of a stale recording."""
        edgar, yf = _pair("MU")
        f = edgar.financials.fields
        yf.total_cash.value = f["cash"].value + f["short_term_investments"].value
        by_label = {(d.label or d.fmp_field): d
                    for d in compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        row = by_label["total_cash@FY"]
        assert row.verdict == VERDICT_STALE_CAPPED
        assert not row.would_change
        assert "alignment revoked" in row.note and "aged absolutely" in row.note

    def test_alignment_needs_the_two_periods_to_be_distinguishable(self):
        """Fails closed: if the FY and MRQ figures are identical there is no evidence
        about which one the primary is serving, so alignment is withheld."""
        assert _tracks_matched_period(100.0, 100.0, 100.0) is False
        assert _tracks_matched_period(100.0, None, 90.0) is False
        assert _tracks_matched_period(100.0, 99.0, 80.0) is True
        assert _tracks_matched_period(100.0, 80.0, 99.0) is False

    def test_newer_fiscal_year_filed_revokes_alignment(self):
        """The XBRL-LAG check still applies to alignment rows: matched periods say
        nothing about whether a fresher matched PAIR already exists."""
        edgar, yf = _pair("GOOG")
        edgar.recent_10k = [FilingRef("10-K", "2027-02-04", "x", "d.htm",
                                      report_date="2026-12-31")]
        by_label = {(d.label or d.fmp_field): d
                    for d in compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        row = by_label["total_cash@FY"]
        assert row.verdict == VERDICT_STALE_CAPPED
        assert "FY 2026-12-31 filed but not yet in companyfacts" in row.note

    def test_quarterly_lag_does_not_revoke_alignment(self):
        """V is a quarter behind, which does NOT make its FY-2025 figures the wrong ones
        to compare against an annual FMP field."""
        edgar, yf = _pair("GOOG")
        edgar.recent_10q = [FilingRef("10-Q", "2026-07-29", "x", "d.htm",
                                      report_date="2026-06-30")]
        by_label = {(d.label or d.fmp_field): d
                    for d in compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        assert by_label["total_cash@FY"].verdict == VERDICT_AGREE

    def test_contradicting_rows_on_one_field_apply_nothing(self):
        """Two armed rows disagreeing about one field has no defensible answer, so it
        takes neither and says so — resolving it by row order would be silent."""
        edgar, yf = _pair("GOOG")
        report = compute_cross_check(edgar, yf, today="2026-08-08")
        by_label = {(d.label or d.fmp_field): d for d in report.deltas}
        before = getattr(yf, "total_cash").confidence
        # force the MRQ row to disagree with the armed @FY row
        mrq = by_label["total_cash"]
        mrq.verdict, mrq.would_be_confidence, mrq.dark = VERDICT_CONFLICT, "low", False
        applied = apply_report(report, yf)
        assert any(a.startswith("!CONTRADICTION total_cash") for a in applied)
        assert getattr(yf, "total_cash").confidence == before

    def test_matched_period_input_not_filed_then_is_withheld(self):
        """Never silently substitute the MRQ figure for a period the issuer skipped."""
        edgar, yf = _pair("MU")
        cash = edgar.financials.fields["cash"]
        edgar.financials.concepts[cash.concept] = [
            r for r in edgar.financials.concepts[cash.concept]
            if r.get("end") != latest_fiscal_year_end(edgar)
        ]
        by_label = {(d.label or d.fmp_field): d
                    for d in compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        row = by_label["total_cash@FY"]
        assert row.verdict == VERDICT_NO_EDGAR
        assert "not filed @" in row.note

    def test_reported_total_row_is_dark_and_separate(self):
        """It sits alongside the armed components row rather than replacing it, so both
        bases stay visible while the reported-total surface is under review."""
        _, _, _, by_label = self._report("MU")
        reported = by_label["total_debt(reported)"]
        assert reported.dark and not by_label["total_debt"].dark
        assert reported.edgar_inputs.startswith("total_debt_reported=")

    def test_armed_total_debt_still_uses_components(self):
        """R3(a) must not silently re-source the armed row: MU files a FRESH reported
        total while its component tags lag a quarter, and the lagging-sibling case has
        to stay visible in the table."""
        edgar, _, _, by_label = self._report("MU")
        fields = edgar.financials.fields
        assert by_label["total_debt"].period_end == min(
            fields["long_term_debt"].period_end, fields["current_debt"].period_end)
        # The reported row is sourced independently — and ages from the oldest of ITS
        # own inputs, which for MU is the lagging operating-lease tag, not the debt one.
        assert by_label["total_debt(reported)"].period_end == min(
            fields["total_debt_reported"].period_end,
            fields["operating_lease_liability"].period_end)
        assert "long_term_debt=" in by_label["total_debt"].edgar_inputs
        assert "total_debt_reported=" in by_label["total_debt(reported)"].edgar_inputs


class TestGoldenFiveOffline:
    """R-C: the comparison layer now runs offline for all five golden tickers, against
    the recorded FMP payload rather than the older yfinance-shaped fixtures.

    These are the invariants that must hold for EVERY ticker, so they are the ones worth
    paying five-ticker coverage for. Ticker-specific behaviour stays in the classes above.
    """

    @pytest.mark.parametrize("ticker", GOLDEN)
    def test_every_comparison_yields_a_delta(self, ticker):
        edgar, yf = _fmp_pair(ticker)
        report = compute_cross_check(edgar, yf, today="2026-08-09")
        assert {(d.label or d.fmp_field) for d in report.deltas} == {
            (c.label or c.fmp_field) for c in COMPARISONS}

    @pytest.mark.parametrize("ticker", GOLDEN)
    def test_withheld_edgar_fields_are_never_compared(self, ticker):
        edgar, yf = _fmp_pair(ticker)
        for d in compute_cross_check(edgar, yf, today="2026-08-09").deltas:
            if d.verdict == VERDICT_NO_EDGAR:
                assert d.edgar_value is None
                assert d.would_be_confidence == d.current_confidence

    @pytest.mark.parametrize("ticker", GOLDEN)
    def test_application_moves_labels_only(self, ticker):
        edgar, yf = _fmp_pair(ticker)
        before = {n: (p.value, p.as_of) for n, p in vars(yf).items()
                  if isinstance(p, Prov)}
        apply_report(compute_cross_check(edgar, yf, today="2026-08-09"), yf)
        assert {n: (p.value, p.as_of) for n, p in vars(yf).items()
                if isinstance(p, Prov)} == before

    @pytest.mark.parametrize("ticker", GOLDEN)
    def test_dark_rows_move_nothing(self, ticker):
        edgar, yf = _fmp_pair(ticker)
        report = compute_cross_check(edgar, yf, today="2026-08-09")
        assert any(d.dark for d in report.deltas)
        applied = apply_report(report, yf)
        dark_only = {d.fmp_field for d in report.deltas if d.dark} - {
            d.fmp_field for d in report.deltas if not d.dark and d.would_change}
        assert not [a for a in applied if a.split("→")[0] in dark_only]

    @pytest.mark.parametrize("ticker", GOLDEN)
    def test_no_contradictions_on_the_golden_five(self, ticker):
        """Two armed rows on one field must not disagree. If this ever fires, the
        comparison set has grown an ambiguity that needs resolving at the table."""
        edgar, yf = _fmp_pair(ticker)
        applied = apply_report(
            compute_cross_check(edgar, yf, today="2026-08-09"), yf)
        assert not [a for a in applied if a.startswith("!CONTRADICTION")]

    def test_wu_total_debt_reaches_a_verdict_only_via_the_reported_total(self):
        """The R-B case, now offline: WU's components are unassemblable, so its armed
        row is no_edgar and only the dark reported-total row produces a value."""
        edgar, yf = _fmp_pair("WU")
        by_label = {(d.label or d.fmp_field): d
                    for d in compute_cross_check(edgar, yf, today="2026-08-09").deltas}
        assert by_label["total_debt"].verdict == VERDICT_NO_EDGAR
        # Lease-inclusive per R-B: reported debt 2,697.2M + operating lease 225.7M.
        assert by_label["total_debt(reported)"].edgar_value == pytest.approx(2_922_900_000)

    @pytest.mark.parametrize("ticker", ("MU", "GOOG", "NOW"))
    def test_matched_period_cash_is_identical_to_fmp(self, ticker):
        """The identity that justified arming total_cash@FY, now pinned offline: read at
        the fiscal year-end, EDGAR cash+ST-investments IS FMP's cashAndShortTermInvestments."""
        edgar, yf = _fmp_pair(ticker)
        by_label = {(d.label or d.fmp_field): d
                    for d in compute_cross_check(edgar, yf, today="2026-08-09").deltas}
        row = by_label["total_cash@FY"]
        assert row.divergence_pct == pytest.approx(0.0, abs=0.05)
        assert row.verdict == VERDICT_AGREE
        assert "gated on alignment" in row.note

    @pytest.mark.parametrize("ticker", ("V", "WU"))
    def test_issuers_without_st_investments_stay_advisory(self, ticker):
        """Scope condition 2: a missing aligning input keeps the row advisory, so it
        never reaches the gate and can never be corroborated on a narrower measure."""
        edgar, yf = _fmp_pair(ticker)
        by_label = {(d.label or d.fmp_field): d
                    for d in compute_cross_check(edgar, yf, today="2026-08-09").deltas}
        row = by_label["total_cash@FY"]
        assert row.verdict == VERDICT_BASIS_MISMATCH
        assert not row.would_change
        assert "short_term_investments" in row.note


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
        by_field = {(d.label or d.fmp_field): d for d in compute_cross_check(edgar, yf).deltas}
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
        by_field = {(d.label or d.fmp_field): d for d in compute_cross_check(edgar, yf).deltas}
        fields = edgar.financials.fields
        assert by_field["total_cash"].edgar_value == pytest.approx(
            fields["cash"].value + fields["short_term_investments"].value)

    def test_missing_optional_input_downgrades_to_advisory(self):
        """V files no ST-investment tag, so its cash-only value faces a broader FMP
        measure — advisory, never a conflict."""
        edgar, yf = _pair("V")
        delta = {(d.label or d.fmp_field): d for d in compute_cross_check(edgar, yf).deltas}["total_cash"]
        assert delta.verdict == VERDICT_BASIS_MISMATCH
        assert not delta.would_change
        assert "short_term_investments" in delta.note

    def test_roe_uses_average_equity(self):
        """FMP computes ROE on average equity; against period-end equity the gap tracks
        equity growth (MU 29%, GOOG 25%). Averaging aligns the basis."""
        edgar, yf = _pair("MU")
        delta = {(d.label or d.fmp_field): d for d in compute_cross_check(edgar, yf).deltas}["roe"]
        assert "avg w/ prior yr" in delta.edgar_inputs
        fields = edgar.financials.fields
        end_only = fields["net_income"].value / fields["equity"].value
        assert delta.edgar_value != pytest.approx(end_only)
        assert delta.divergence_pct < 10.0   # was 29.0 on the period-end basis

    def test_average_equity_follows_the_migrated_tag(self):
        """V's equity resolves via the incl-NCI variant; the prior-year lookup must use
        that same tag, not the abandoned one."""
        edgar, yf = _pair("V")
        delta = {(d.label or d.fmp_field): d for d in compute_cross_check(edgar, yf).deltas}["roe"]
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
        by_field = {(d.label or d.fmp_field): d for d in report.deltas}
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
        by_field = {(d.label or d.fmp_field): d for d in report.deltas}
        assert by_field["total_debt"].age_days > by_field["gross_margin"].age_days
        assert by_field["gross_margin"].would_be_confidence == "high"

    def test_multi_input_field_ages_from_oldest_input(self):
        edgar, yf = _pair("MU")
        by_field = {(d.label or d.fmp_field): d for d in compute_cross_check(edgar, yf).deltas}
        fields = edgar.financials.fields
        assert by_field["total_debt"].period_end == min(
            fields["long_term_debt"].period_end, fields["current_debt"].period_end)

    def test_beyond_threshold_caps_at_medium(self):
        """ALIGNMENT-GATED ROWS ARE EXEMPT BY DESIGN (R-A) and are excluded here.

        A matched-period row is aged on the gap between the two sides' periods — zero by
        construction — not on absolute age, because a correctly-labelled annual figure
        corroborating an annual FMP field launders nothing. The day-count threshold
        therefore does not apply to it, and asserting otherwise would contradict R-A.

        This exclusion used to be unnecessary: MU's retired fixture served total_cash as
        MRQ, so alignment was revoked and no alignment row survived to be exempt.
        """
        edgar, yf = _pair("MU")
        report = compute_cross_check(edgar, yf, today="2026-08-08", threshold_days=10)
        absolute_aged = [d for d in report.deltas
                         if "gated on alignment" not in (d.note or "")]
        for d in absolute_aged:
            assert d.would_be_confidence != "high", f"{d.fmp_field} upgraded while stale"
        assert any(d.verdict == VERDICT_STALE_CAPPED for d in absolute_aged)


class TestSymmetricStaleGating:
    """R1 (ruling 2026-08-08): a source too stale to upgrade is too stale to downgrade.

    The staleness engine caps only 'high', so before R1 a conflict measured on stale or
    lagged data still downgraded the field to low — confidence moving on data the same
    report declared untrustworthy.
    """

    def test_stale_data_moves_nothing_in_either_direction(self):
        """The property, asserted directly: with everything stale, no delta moves.

        Alignment-gated rows are excluded — they are aged on alignment, not absolute age
        (R-A), so "stale" is not a claim that can be made about them.
        """
        edgar, yf = _pair_with_forced_conflict("MU", "operating_margin")
        report = compute_cross_check(edgar, yf, today="2026-08-08", threshold_days=10)
        armed = [d for d in report.deltas
                 if not d.dark and "gated on alignment" not in (d.note or "")]
        assert any(d.divergence_pct and d.divergence_pct > 5.0 for d in armed), \
            "a conflict-sized divergence must be present for this to prove anything"
        for d in armed:
            assert not d.would_change, f"{d.fmp_field} moved while stale"
            assert d.would_be_confidence == d.current_confidence

    def test_conflict_on_stale_data_renders_stale_capped_with_divergence_kept(self):
        edgar, yf = _pair_with_forced_conflict("MU", "operating_margin")
        by_field = {(d.label or d.fmp_field): d for d in
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
        edgar, yf = _pair_with_forced_conflict("MU", "operating_margin")
        by_field = {(d.label or d.fmp_field): d for d in
                    compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        assert by_field["operating_margin"].verdict == VERDICT_CONFLICT
        assert by_field["operating_margin"].would_be_confidence == "low"

    def test_lagged_conflict_is_suppressed_too(self):
        """The lag half of the gate, on the ticker that prompted the ruling: V's
        companyfacts is a full quarter behind its own filings. (Live it was
        current_ratio at 10.4%; against the recorded FMP fixture the conflicting field
        is operating_margin — the gate is field-agnostic.)"""
        edgar, yf = _pair_with_forced_conflict("V", "operating_margin")
        edgar.recent_10q = [FilingRef(form="10-Q", date="2026-07-29", accession="x",
                                      primary_doc="d.htm", report_date="2026-06-30")]
        by_field = {(d.label or d.fmp_field): d for d in
                    compute_cross_check(edgar, yf, today="2026-08-08").deltas}
        om = by_field["operating_margin"]
        assert om.verdict == VERDICT_STALE_CAPPED
        assert om.would_be_confidence == om.current_confidence
        assert "conflict suppressed" in om.note and "XBRL behind submissions" in om.note

    def test_lag_suppression_needs_the_lag(self):
        """Without the submissions cross-reference V is only 130d old — inside the 150d
        backstop — so the same conflict is live. The lag is doing the work."""
        edgar, yf = _pair_with_forced_conflict("V", "operating_margin")
        by_field = {(d.label or d.fmp_field): d for d in
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
        # Armed rows only: matched-period rows are gated on alignment, not the MRQ lag.
        aged_only = [d for d in compute_cross_check(
            edgar, yf, today="2026-08-08", lag_aware=False).deltas if not d.dark]
        lag_aware = [d for d in compute_cross_check(
            edgar, yf, today="2026-08-08", lag_aware=True).deltas if not d.dark]
        assert any(d.would_be_confidence == "high" for d in aged_only)
        assert all(d.would_be_confidence != "high" for d in lag_aware)
        # Every cap here was the lag's doing, not the day-count's: each capped row is
        # comfortably inside the 150d backstop.
        capped = [d for d in lag_aware if d.verdict == VERDICT_STALE_CAPPED]
        assert capped
        assert all(d.age_days < FRESHNESS_THRESHOLD_DAYS
                   for d in capped if d.age_days is not None)
