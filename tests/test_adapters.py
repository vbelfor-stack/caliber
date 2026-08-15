"""
Adapter fixture-loading tests.
All tests run against recorded fixtures — no live network calls.
"""
from pathlib import Path
import pytest

from adapters.fmp_adapter import fetch_fmp
from core.datatypes import TickerData
from adapters.edgar_adapter import (
    fetch_edgar, EdgarData, FIELD_SPECS, resolve_financials,
    REASON_NO_TAG, REASON_STALE_TAG, REASON_SYNONYM_CONFLICT,
    REASON_AMBIGUOUS_PERIOD, REASON_TTM_UNAVAILABLE, REASON_DERIVE_INCOMPLETE,
)
from adapters.fred_adapter import fetch_fred, FredData
from adapters.fmp_adapter import fetch_fmp

FIXTURE_ROOT = Path("tests/fixtures")
YF = FIXTURE_ROOT / "fmp"
EDGAR = FIXTURE_ROOT / "edgar"
FRED_FX = FIXTURE_ROOT / "fred" / "DGS10.json"
FMP = FIXTURE_ROOT / "fmp"


# ── fixture adapter ──────────────────────────────────────────────────────────

class TestRecordedFmpPayload:
    def test_mu_loads_from_fixture(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf, TickerData)
        assert yf.ticker == "MU"

    def test_mu_sector_is_technology(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert yf.sector == "Technology"

    def test_mu_industry_semiconductors(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert yf.industry == "Semiconductors"

    def test_mu_gross_margin_is_prov(self):
        from adapters.base import Prov
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.gross_margin, Prov)
        assert not yf.gross_margin.is_missing()

    def test_mu_gross_margin_source(self):
        """The recorded payload is FMP's, so the stamp reads "fmp" — and it is the LIVE
        label, not a recording artifact. The retired ticker/ fixtures stamped "yfinance",
        which was accurate for their contents but meant offline provenance never matched
        what production writes."""
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert yf.gross_margin.source == "fmp"

    def test_mu_gross_margin_confidence_medium(self):
        """Single source → medium (no secondary cross-check feed wired in)."""
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert yf.gross_margin.confidence == "medium"

    def test_mu_gross_margin_range(self):
        """MU gross margin is high at cycle peak (>50%)."""
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        gm = yf.gross_margin.value
        assert gm is not None
        assert 0.5 < gm < 1.0, f"Expected >50%, got {gm:.2%}"

    def test_mu_forward_pe_positive(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        if not yf.forward_pe.is_missing():
            assert yf.forward_pe.value > 0

    def test_mu_revenue_growth_positive(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        if not yf.revenue_growth.is_missing():
            # MU had massive recovery; value should be positive
            assert yf.revenue_growth.value > 0

    def test_mu_fcf_yield_computed(self):
        """FCF yield is derived: free_cashflow / market_cap."""
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        if not yf.free_cashflow.is_missing() and not yf.market_cap.is_missing():
            if yf.market_cap.value and yf.market_cap.value > 0:
                assert not yf.fcf_yield.is_missing()

    def test_goog_loads(self):
        yf = fetch_fmp("GOOG", fixture_path=YF / "GOOG.json")
        assert yf.ticker == "GOOG"
        assert yf.sector == "Communication Services"

    def test_goog_industry(self):
        yf = fetch_fmp("GOOG", fixture_path=YF / "GOOG.json")
        assert yf.industry == "Internet Content & Information"

    def test_v_loads(self):
        yf = fetch_fmp("V", fixture_path=YF / "V.json")
        assert yf.ticker == "V"
        assert yf.sector == "Financial Services"

    def test_v_industry_credit_services(self):
        # FMP's vocabulary is "Financial - Credit Services"; lens_select keys on the
        # substring, so that is what is pinned.
        yf = fetch_fmp("V", fixture_path=YF / "V.json")
        assert "Credit Services" in yf.industry

    def test_nan_coerced_to_none(self):
        """NaN fields must become None Provs (not crash)."""
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        # Any field that happens to be None must still be a Prov
        from adapters.base import Prov
        assert isinstance(yf.beta, Prov)

    def test_missing_fixture_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="fixture not found"):
            fetch_fmp("FAKE", fixture_path=Path("nonexistent.json"))

    def test_earnings_history_is_list(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.earnings_history, list)

    def test_insider_transactions_is_list(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.insider_transactions, list)

    def test_price_history_is_list(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.price_history, list)


# ── EDGAR adapter ─────────────────────────────────────────────────────────────

class TestEdgarAdapter:
    def test_mu_loads_from_fixture(self):
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        assert isinstance(ed, EdgarData)
        assert ed.ticker == "MU"

    def test_mu_cik_is_micron(self):
        """Critical: MU CIK must be Micron (0000723125), not Cintas."""
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        assert "723125" in ed.cik, (
            f"MU CIK should contain 723125 (Micron). Got: {ed.cik}. "
            "This is the CIK-lookup correctness sentinel."
        )

    def test_mu_sic_semiconductors(self):
        """SIC 3674 = Semiconductors & Related Devices."""
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        assert ed.sic == "3674", f"Expected SIC 3674, got {ed.sic}"

    def test_mu_recent_10k_list(self):
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        assert isinstance(ed.recent_10k, list)

    def test_mu_recent_10q_list(self):
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        assert isinstance(ed.recent_10q, list)

    def test_mu_risk_factors_is_prov(self):
        from adapters.base import Prov
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        assert isinstance(ed.risk_factors_excerpt, Prov)

    def test_mu_risk_factors_source_is_edgar(self):
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        assert ed.risk_factors_excerpt.source == "EDGAR"

    def test_goog_cik_is_alphabet(self):
        ed = fetch_edgar("GOOG", fixture_path=EDGAR / "GOOG.json")
        assert "1652044" in ed.cik, f"GOOG CIK should be Alphabet (1652044). Got: {ed.cik}"

    def test_v_cik_is_visa(self):
        ed = fetch_edgar("V", fixture_path=EDGAR / "V.json")
        assert "1403161" in ed.cik, f"V CIK should be Visa (1403161). Got: {ed.cik}"

    def test_v_sic_business_services(self):
        """Visa SIC is 7389 (Business Services NEC), not 6022 (banking)."""
        ed = fetch_edgar("V", fixture_path=EDGAR / "V.json")
        assert ed.sic is not None
        assert ed.sic != "6022", "Visa must NOT have a banking SIC code"

    def test_missing_fixture_raises(self):
        with pytest.raises(RuntimeError, match="fixture not found"):
            fetch_edgar("FAKE", fixture_path=Path("nonexistent.json"))


# ── FRED adapter ──────────────────────────────────────────────────────────────

class TestFredAdapter:
    def test_loads_from_fixture(self):
        fred = fetch_fred(fixture_path=FRED_FX)
        assert isinstance(fred, FredData)

    def test_rate_10y_is_prov(self):
        from adapters.base import Prov
        fred = fetch_fred(fixture_path=FRED_FX)
        assert isinstance(fred.rate_10y, Prov)

    def test_rate_10y_source_is_fred(self):
        fred = fetch_fred(fixture_path=FRED_FX)
        assert fred.rate_10y.source == "FRED"

    def test_rate_missing_does_not_crash(self):
        """Without key fixture has no rate data — must not raise."""
        fred = fetch_fred(fixture_path=FRED_FX)
        # Either has a value or is missing — both are acceptable
        assert fred.rate_10y.value is None or isinstance(fred.rate_10y.value, (int, float))

    def test_rate_confidence_valid(self):
        fred = fetch_fred(fixture_path=FRED_FX)
        assert fred.rate_10y.confidence in ("high", "medium", "low")

    def test_missing_fixture_raises(self):
        with pytest.raises(RuntimeError, match="fixture not found"):
            fetch_fred(fixture_path=Path("nonexistent.json"))


# ── FMP adapter ───────────────────────────────────────────────────────────────

class TestFmpAdapter:
    def test_mu_loads_from_fixture(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert isinstance(yf, TickerData)
        assert yf.ticker == "MU"

    def test_mu_name_is_micron(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert "Micron" in (yf.name or "")

    def test_mu_sector_is_technology(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert yf.sector == "Technology"

    def test_mu_industry_semiconductors(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert yf.industry == "Semiconductors"

    def test_mu_current_price_realistic(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert not yf.current_price.is_missing()
        assert 100 < yf.current_price.value < 5000

    def test_mu_gross_margin_is_prov(self):
        from adapters.base import Prov
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert isinstance(yf.gross_margin, Prov)

    def test_mu_gross_margin_source_is_fmp(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert yf.gross_margin.source == "fmp"

    def test_mu_gross_margin_confidence_medium(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert yf.gross_margin.confidence == "medium"

    def test_mu_gross_margin_range(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert not yf.gross_margin.is_missing()
        assert 0.5 < yf.gross_margin.value < 1.0

    def test_mu_roe_positive(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert not yf.roe.is_missing()
        assert yf.roe.value > 0

    def test_mu_revenue_growth_positive(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert not yf.revenue_growth.is_missing()
        assert yf.revenue_growth.value > 0

    def test_mu_market_cap_large(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert not yf.market_cap.is_missing()
        assert yf.market_cap.value > 1e11  # > $100B

    def test_mu_earnings_history_is_list(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert isinstance(yf.earnings_history, list)

    def test_mu_earnings_history_has_actual_and_estimate(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        if yf.earnings_history:
            row = yf.earnings_history[0]
            assert "epsActual" in row
            assert "epsEstimate" in row
            assert "epsDifference" in row
            assert "surprisePercent" in row

    def test_mu_price_history_is_list(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert isinstance(yf.price_history, list)

    def test_mu_price_history_has_ohlcv(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        if yf.price_history:
            row = yf.price_history[0]
            assert "Open" in row
            assert "Close" in row
            assert "Volume" in row
            assert "date" in row

    def test_mu_insider_transactions_is_empty_list(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        assert yf.insider_transactions == []

    def test_goog_loads(self):
        yf = fetch_fmp("GOOG", fixture_path=FMP / "GOOG.json")
        assert yf.ticker == "GOOG"

    def test_v_loads(self):
        yf = fetch_fmp("V", fixture_path=FMP / "V.json")
        assert yf.ticker == "V"

    def test_missing_fixture_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="fixture not found"):
            fetch_fmp("FAKE", fixture_path=Path("nonexistent.json"))

    def test_trailing_pe_positive(self):
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        if not yf.trailing_pe.is_missing():
            assert yf.trailing_pe.value > 0

    def test_all_prov_fields_have_fmp_source(self):
        from adapters.base import Prov
        yf = fetch_fmp("MU", fixture_path=FMP / "MU.json")
        prov_fields = [
            yf.gross_margin, yf.operating_margin, yf.profit_margin,
            yf.roe, yf.roa, yf.current_ratio, yf.debt_to_equity,
            yf.total_debt, yf.total_cash, yf.free_cashflow,
            yf.operating_cashflow, yf.revenue_growth, yf.trailing_pe,
            yf.forward_pe, yf.analyst_count, yf.target_mean_price,
            yf.price_to_book, yf.ev_to_ebitda, yf.ev_to_revenue,
            yf.market_cap, yf.current_price, yf.enterprise_value,
            yf.fcf_yield, yf.shares_outstanding, yf.beta,
        ]
        for p in prov_fields:
            assert p.source == "fmp", f"Expected source=fmp, got {p.source}"


class TestFmpOnlyFetch:
    """Live fetch is FMP-only (yfinance teardown 2026-08-07) — fail loud, no fallback."""

    def test_fmp_success_returns_data(self):
        from unittest.mock import patch
        from batch.runner import _fetch

        fake = fetch_fmp("MU", fixture_path=YF / "MU.json")
        with patch("adapters.fmp_adapter.fetch_fmp", return_value=fake):
            result = _fetch("MU", log=lambda msg: None)

        assert isinstance(result, TickerData)
        assert result.ticker == "MU"

    def test_fmp_failure_raises_loud(self):
        """No fallback: an FMP error surfaces as a reason-stamped RuntimeError."""
        from unittest.mock import patch
        from batch.runner import _fetch

        with pytest.raises(RuntimeError, match="FMP failed"):
            with patch("adapters.fmp_adapter.fetch_fmp",
                       side_effect=RuntimeError("FMP down")):
                _fetch("MU", log=lambda msg: None)


class TestProvenanceFeedSource:
    """Derived Prov sources reflect the actual feed (feed_source), never a hardcoded
    label — the prerequisite for EDGAR's cross-check to see real source diversity."""

    def test_fixture_feed_source_and_derived_labels(self):
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        assert yf.feed_source == "fmp"
        assert yf.gross_margin_trajectory.ttm.source == "fmp"
        assert yf.gross_margin_trajectory.mrq.source == "fmp/quarterly_financials"

    def test_derived_sources_follow_feed_source(self):
        from core.technicals import analyze_technicals
        from core.pillars import score_management
        yf = fetch_fmp("MU", fixture_path=YF / "MU.json")
        yf.feed_source = "fmp"    # simulate the live FMP feed
        tech = analyze_technicals(yf.price_history, feed_source=yf.feed_source)
        assert tech.price_vs_ma50_pct.source == "fmp/price_history"
        mgmt = score_management(yf, "cyclical")
        earn = [p for p in mgmt.key_inputs if p.source and "earnings" in p.source]
        assert earn and earn[0].source == "fmp/earnings_history"


class TestEdgarXbrlExtraction:
    """E-1: EDGAR extracts XBRL financial concepts (for the FMP cross-check, E-3)."""

    def test_core_concepts_extracted(self):
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        fin = ed.financials
        assert fin.concepts, "no XBRL concepts extracted"
        assert "NetIncomeLoss" in fin.concepts
        assert "Assets" in fin.concepts
        assert any(c in fin.concepts for c in
                   ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"))

    def test_facts_numeric_dated_and_form_filtered(self):
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        rec = ed.financials.concepts["NetIncomeLoss"][0]
        assert isinstance(rec["value"], float)
        assert rec["end"]
        assert rec["form"] in ("10-K", "10-Q", "10-K/A", "10-Q/A")

    def test_records_most_recent_first(self):
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        ends = [r["end"] for r in ed.financials.concepts["Assets"]]
        assert ends == sorted(ends, reverse=True)

    def test_latest_period_end_is_usgaap_not_cover_date(self):
        """Staleness clock uses us-gaap fiscal period-end, not the dei cover date."""
        ed = fetch_edgar("V", fixture_path=EDGAR / "V.json")
        fin = ed.financials
        usgaap_ends = [r["end"] for name, recs in fin.concepts.items()
                       if name != "EntityCommonStockSharesOutstanding" for r in recs]
        assert fin.latest_period_end == max(usgaap_ends)

    def test_duplicate_facts_deduped(self):
        """Companyfacts repeats unchanged facts across filings; extraction collapses them
        so duplicates cannot crowd out the older periods TTM reconstruction needs."""
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        for concept, recs in ed.financials.concepts.items():
            keys = [(r["start"], r["end"], r["unit"], r["value"]) for r in recs]
            assert len(keys) == len(set(keys)), f"duplicate facts kept for {concept}"


# ── E-2: canonical field resolution ──────────────────────────────────────────

GOLDEN_CIKS = ("MU", "GOOG", "V", "NOW", "WU")

# JPM — sixth golden ticker, added 2026-08-09 by ruling as the BANK-LENS CALIBRATION
# INSTRUMENT. Explicitly NOT a holding: it is absent from tickers.txt (the batch universe)
# on purpose, and exists so the bank lens has a real bank to calibrate against instead of
# the counterfactual forced-lens cells D-3 had to argue from.
#
# It is held to the resolved-xor-reason invariant like every other golden name, but NOT to
# test_core_fields_resolve, because its `cash` is withheld — see the E-2 onboarding
# findings in docs/d4-arming.md. That is an OPEN FINDING awaiting a ruling on the synonym
# chain, deliberately not patched here: adding a bank-specific tag changes EDGAR field
# resolution for every ticker, which is E-2 work, not D-4 work.
# Bank calibration universe RULED 2026-08-09: JPM (money-center), BK (trust/custody,
# high quality), USB (quality regional), C (the below-book discriminator case). All four
# are CALIBRATION INSTRUMENTS, never holdings — pinned absent from tickers.txt.
CALIBRATION_CIKS = ("JPM", "BK", "USB", "C")
ALL_EDGAR_CIKS = GOLDEN_CIKS + CALIBRATION_CIKS
_REASONS = {
    REASON_NO_TAG, REASON_STALE_TAG, REASON_SYNONYM_CONFLICT,
    REASON_AMBIGUOUS_PERIOD, REASON_TTM_UNAVAILABLE, REASON_DERIVE_INCOMPLETE,
}


def _fields(ticker: str):
    return fetch_edgar(ticker, fixture_path=EDGAR / f"{ticker}.json").financials.fields


def _fact(end, value, start=None, unit="USD", accn="0000000000-26-000001", form="10-Q"):
    return {"value": float(value), "unit": unit, "start": start, "end": end,
            "fy": None, "fp": None, "form": form, "accession": accn}


class TestEdgarFieldResolution:
    """E-2: explicit synonym table, per-concept staleness gate, TTM assembly."""

    def test_every_spec_yields_a_field(self):
        fields = _fields("MU")
        assert set(fields) == {s.name for s in FIELD_SPECS}

    @pytest.mark.parametrize("ticker", ALL_EDGAR_CIKS)
    def test_resolved_xor_reason(self, ticker):
        """The core invariant: a field carries a value or a typed reason, never both,
        never neither. A withheld field is never a partial or fabricated figure."""
        for name, rf in _fields(ticker).items():
            if rf.is_resolved():
                assert rf.reason is None and rf.value is not None
                assert rf.period_end and rf.method, f"{ticker}/{name} missing stamps"
            else:
                assert rf.value is None, f"{ticker}/{name} withheld but carries a value"
                assert rf.reason in _REASONS, f"{ticker}/{name} untyped reason {rf.reason}"

    @pytest.mark.parametrize("ticker", GOLDEN_CIKS)
    def test_core_fields_resolve(self, ticker):
        fields = _fields(ticker)
        for name in ("revenue", "net_income", "equity", "total_assets", "cash"):
            assert fields[name].is_resolved(), f"{ticker}/{name}: {fields[name].reason}"

    # ── staleness gate ───────────────────────────────────────────────────────

    def test_v_equity_skips_abandoned_tag(self):
        """V stopped tagging StockholdersEquity in 2011. The gate must skip it and take
        the including-NCI variant — the pre-E-2 extractor returned the 2011 figure."""
        eq = _fields("V")["equity"]
        assert eq.is_resolved()
        assert eq.concept == (
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")
        assert eq.period_end >= "2026-01-01"
        assert any("StockholdersEquity:stale(" in t for t in eq.trail)

    def test_stale_only_chain_withholds_value(self):
        """V's dei share count froze in 2010 and it files no us-gaap fallback."""
        shares = _fields("V")["shares_outstanding"]
        assert shares.value is None
        assert shares.reason == REASON_STALE_TAG

    def test_stale_gate_threshold(self):
        """A concept lagging the entity's latest period by > STALE_TAG_DAYS is withheld."""
        concepts = {"Assets": [_fact("2024-12-31", 1_000)]}
        fresh = resolve_financials(concepts, "2026-01-31")   # 396d lag
        stale = resolve_financials(concepts, "2026-06-30")   # 546d lag
        assert fresh.fields["total_assets"].value == 1_000
        assert stale.fields["total_assets"].value is None
        assert stale.fields["total_assets"].reason == REASON_STALE_TAG

    def test_debt_tags_differ_by_issuer(self):
        """MU and GOOG migrated in opposite directions; the table handles both."""
        assert _fields("MU")["current_debt"].concept == "DebtCurrent"
        assert _fields("GOOG")["current_debt"].concept == "LongTermDebtCurrent"
        assert _fields("MU")["long_term_debt"].concept == "LongTermDebt"
        assert _fields("GOOG")["long_term_debt"].concept == "LongTermDebtNoncurrent"

    def test_shares_falls_back_to_usgaap(self):
        """GOOG files no dei cover-page count (multi-class); fallback supplies it."""
        shares = _fields("GOOG")["shares_outstanding"]
        assert shares.is_resolved()
        assert shares.concept == "CommonStockSharesOutstanding"

    # ── conflicts ────────────────────────────────────────────────────────────

    def test_synonym_conflict_withholds(self):
        """Two fresh tags disagreeing for one period is non-comparable, not arbitrable."""
        fin = resolve_financials({
            "StockholdersEquity": [_fact("2026-03-31", 100)],
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest":
                [_fact("2026-03-31", 140)],
        }, "2026-03-31")
        eq = fin.fields["equity"]
        assert eq.value is None
        assert eq.reason == REASON_SYNONYM_CONFLICT

    def test_synonym_agreement_uses_priority_tag(self):
        fin = resolve_financials({
            "StockholdersEquity": [_fact("2026-03-31", 100.0)],
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest":
                [_fact("2026-03-31", 100.2)],
        }, "2026-03-31")
        assert fin.fields["equity"].value == 100.0
        assert fin.fields["equity"].concept == "StockholdersEquity"

    def test_distinct_measures_skip_the_conflict_gate(self):
        """Revenues (total) and the ASC 606 contract-revenue tag legitimately differ for
        issuers with non-contract income. WU files both for the same period (H1-26:
        1,995.9M vs 1,920.6M), so priority order must decide — withholding here would
        cascade into gross profit and every margin built on revenue."""
        fields = _fields("WU")
        rev = fields["revenue"]
        assert rev.is_resolved(), f"withheld: {rev.reason}"
        assert rev.concept == "Revenues"
        assert any("RevenueFromContractWithCustomer" in t for t in rev.trail)
        # the un-cascade: the fields downstream of revenue survive with it
        assert fields["gross_profit"].is_resolved()
        assert fields["gross_profit"].concept == "derived:revenue-cost_of_revenue"

    def test_conflict_gate_still_armed_for_ambiguous_chains(self):
        """Disabling the gate for distinct measures must not disable it everywhere."""
        fin = resolve_financials({
            "StockholdersEquity": [_fact("2026-03-31", 100)],
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest":
                [_fact("2026-03-31", 140)],
        }, "2026-03-31")
        assert fin.fields["equity"].reason == REASON_SYNONYM_CONFLICT

    def test_current_debt_falls_through_to_short_term_borrowings(self):
        """NOW abandoned LongTermDebtCurrent in 2022 and files ShortTermBorrowings
        (2,082M) alongside its CommercialPaper component (2,100M). The stale leading tag
        is skipped and the aggregate wins over the component."""
        cd = _fields("NOW")["current_debt"]
        assert cd.is_resolved()
        assert cd.concept == "ShortTermBorrowings"
        assert cd.value == pytest.approx(2_082_000_000)
        assert any("LongTermDebtCurrent:stale(" in t for t in cd.trail)

    def test_reported_debt_total_resolves_where_components_cannot(self):
        """R3(a): WU files no fresh current-portion tag, so long_term + current is
        unassemblable for it — DebtAndCapitalLeaseObligations is the only route to the
        measure FMP's totalDebt means."""
        fields = _fields("WU")
        assert fields["current_debt"].reason == REASON_STALE_TAG
        reported = fields["total_debt_reported"]
        assert reported.is_resolved()
        assert reported.concept == "DebtAndCapitalLeaseObligations"
        assert reported.value == pytest.approx(2_697_200_000)

    @pytest.mark.parametrize("ticker,reason", (
        # GOOG DOES file LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities,
        # but abandoned it in 2024 — the 450d gate withholds it, so stale_tag is the
        # accurate code. It read no_tag only until the D-5 chain extension; the fixture
        # caught up at the G-4 re-record. The field is DARK either way.
        ("GOOG", REASON_STALE_TAG),
        ("NOW", REASON_NO_TAG),
    ))
    def test_reported_debt_total_absent_is_typed(self, ticker, reason):
        """Most issuers file only the components; withheld, never zero-filled.

        The DISTINCTION is the point: no_tag means never filed, stale_tag means filed and
        abandoned. Both withhold; conflating them would lose the tag-migration signal that
        makes onboarding a new ticker diagnosable."""
        field = _fields(ticker)["total_debt_reported"]
        assert not field.is_resolved()
        assert field.reason == reason

    def test_unclassified_balance_sheet_is_typed_not_zero_filled(self):
        """WU files no classified current section (its balance sheet is unclassified —
        only SettlementAssetsCurrent, which is float, not working capital). An absent
        section must read as no_tag, never as zero."""
        fields = _fields("WU")
        for name in ("current_assets", "current_liabilities"):
            assert fields[name].value is None
            assert fields[name].reason == REASON_NO_TAG

    @pytest.mark.parametrize("ticker,concept", [
        ("MU", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"),
        ("GOOG", "MarketableSecuritiesCurrent"),
        ("NOW", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"),
    ])
    def test_short_term_investments_resolve(self, ticker, concept):
        sti = _fields(ticker)["short_term_investments"]
        assert sti.is_resolved()
        assert sti.concept == concept

    @pytest.mark.parametrize("ticker", ("V", "WU"))
    def test_short_term_investments_absent_is_typed(self, ticker):
        """V stopped filing an ST-investment tag in 2020, WU in 2015 — withheld, not
        zero-filled. Both fall to the cash-only advisory path in the cross-check."""
        sti = _fields(ticker)["short_term_investments"]
        assert sti.value is None
        assert sti.reason == REASON_STALE_TAG

    def test_ambiguous_period_withholds(self):
        """One filing reporting two values for a period (dimensions stripped by the
        companyfacts API) cannot be disambiguated here."""
        fin = resolve_financials({"Assets": [
            _fact("2026-03-31", 100, accn="0000000000-26-000009"),
            _fact("2026-03-31", 250, accn="0000000000-26-000009"),
        ]}, "2026-03-31")
        assert fin.fields["total_assets"].value is None
        assert fin.fields["total_assets"].reason == REASON_AMBIGUOUS_PERIOD

    def test_restatement_prefers_newest_accession(self):
        fin = resolve_financials({"Assets": [
            _fact("2026-03-31", 250, accn="0000000000-26-000042"),
            _fact("2026-03-31", 100, accn="0000000000-26-000009"),
        ]}, "2026-03-31")
        assert fin.fields["total_assets"].value == 250

    # ── TTM assembly ─────────────────────────────────────────────────────────

    @pytest.mark.parametrize("ticker", GOLDEN_CIKS)
    def test_flows_are_ttm_stamped(self, ticker):
        for name in ("revenue", "net_income", "operating_income"):
            rf = _fields(ticker)[name]
            if rf.is_resolved():
                assert rf.method.startswith("ttm_"), f"{ticker}/{name} method={rf.method}"

    def test_reconstruction_arithmetic(self):
        """MU never reports Q4 standalone, so TTM = prior FY + YTD - prior-year YTD."""
        ed = fetch_edgar("MU", fixture_path=EDGAR / "MU.json")
        rev = ed.financials.fields["revenue"]
        assert rev.method == "ttm_reconstructed"
        facts = {(r["start"], r["end"]): r["value"]
                 for r in ed.financials.concepts[rev.concept] if r.get("start")}
        fy = facts[("2024-08-30", "2025-08-28")]
        ytd = facts[("2025-08-29", "2026-05-28")]
        prior_ytd = facts[("2024-08-30", "2025-05-29")]
        assert rev.value == pytest.approx(fy + ytd - prior_ytd)
        assert rev.period_end == "2026-05-28"

    def test_four_contiguous_quarters_sum(self):
        fin = resolve_financials({"NetIncomeLoss": [
            _fact("2026-06-30", 40, start="2026-04-01"),
            _fact("2026-03-31", 30, start="2026-01-01"),
            _fact("2025-12-31", 20, start="2025-10-01"),
            _fact("2025-09-30", 10, start="2025-07-01"),
        ]}, "2026-06-30")
        ni = fin.fields["net_income"]
        assert ni.value == 100
        assert ni.method == "ttm_summed"
        assert ni.period_start == "2025-07-01" and ni.period_end == "2026-06-30"

    def test_quarter_gap_is_not_summed(self):
        """A missing quarter must never be summed as if the window were complete."""
        fin = resolve_financials({"NetIncomeLoss": [
            _fact("2026-06-30", 40, start="2026-04-01"),
            _fact("2026-03-31", 30, start="2026-01-01"),
            _fact("2025-09-30", 10, start="2025-07-01"),
            _fact("2025-06-30", 10, start="2025-04-01"),
        ]}, "2026-06-30")
        ni = fin.fields["net_income"]
        assert ni.value is None
        assert ni.reason == REASON_TTM_UNAVAILABLE

    def test_full_year_fact_is_ttm_annual(self):
        fin = resolve_financials({"NetIncomeLoss": [
            _fact("2025-12-31", 500, start="2025-01-01", form="10-K"),
        ]}, "2025-12-31")
        assert fin.fields["net_income"].value == 500
        assert fin.fields["net_income"].method == "ttm_annual"

    def test_ttm_unavailable_when_prior_year_missing(self):
        fin = resolve_financials({"NetIncomeLoss": [
            _fact("2026-06-30", 90, start="2026-01-01"),
            _fact("2025-12-31", 200, start="2025-01-01", form="10-K"),
        ]}, "2026-06-30")
        ni = fin.fields["net_income"]
        assert ni.value is None
        assert ni.reason == REASON_TTM_UNAVAILABLE

    # ── derivation ───────────────────────────────────────────────────────────

    def test_gross_profit_derived_when_untagged(self):
        """GOOG does not tag GrossProfit; it is derived from revenue - cost_of_revenue."""
        fields = _fields("GOOG")
        gp = fields["gross_profit"]
        assert gp.is_resolved()
        assert gp.concept == "derived:revenue-cost_of_revenue"
        assert gp.value == pytest.approx(
            fields["revenue"].value - fields["cost_of_revenue"].value)

    def test_tagged_gross_profit_matches_derivation(self):
        """MU tags GrossProfit AND both components — they agree, which independently
        validates the TTM assembly."""
        fields = _fields("MU")
        assert fields["gross_profit"].concept == "GrossProfit"
        assert fields["gross_profit"].value == pytest.approx(
            fields["revenue"].value - fields["cost_of_revenue"].value, rel=1e-6)

    def test_no_derivation_guessing(self):
        """V tags neither GrossProfit nor any cost concept — withheld, not guessed."""
        fields = _fields("V")
        assert fields["cost_of_revenue"].reason == REASON_NO_TAG
        gp = fields["gross_profit"]
        assert gp.value is None
        assert gp.reason == REASON_DERIVE_INCOMPLETE
        assert "cost_of_revenue" in (gp.detail or "")

    def test_derivation_requires_matching_periods(self):
        fin = resolve_financials({
            "Revenues": [_fact("2026-06-30", 900, start="2025-07-01")],
            "CostOfRevenue": [_fact("2025-12-31", 400, start="2025-01-01", form="10-K")],
        }, "2026-06-30")
        gp = fin.fields["gross_profit"]
        assert gp.value is None
        assert gp.reason == REASON_DERIVE_INCOMPLETE

    # ── diagnostics ──────────────────────────────────────────────────────────

    @pytest.mark.parametrize("ticker", GOLDEN_CIKS)
    def test_trail_records_every_synonym(self, ticker):
        """The trail is the tag-migration map used when onboarding new tickers."""
        fields = _fields(ticker)
        for spec in FIELD_SPECS:
            rf = fields[spec.name]
            if spec.derive and rf.concept and rf.concept.startswith("derived:"):
                continue
            assert len(rf.trail) == len(spec.synonyms), f"{ticker}/{spec.name}"


# ── JPM onboarding (D-4): the bank-lens calibration instrument ───────────────

class TestJpmOnboarding:
    @pytest.mark.parametrize("ticker", CALIBRATION_CIKS)
    def test_calibration_tickers_select_the_bank_lens(self, ticker):
        """The whole point of adding them — the bank lens had no real bank before."""
        from core.lens_select import select_lens
        from adapters.fmp_adapter import fetch_fmp
        yf = fetch_fmp(ticker, fixture_path=FMP / f"{ticker}.json")
        edgar = fetch_edgar(ticker, fixture_path=EDGAR / f"{ticker}.json")
        assert edgar.sic.startswith("602"), f"{ticker} SIC {edgar.sic} is not a bank SIC"
        assert select_lens(yf.sector, yf.industry, edgar.sic) == "bank"

    def test_bk_resolves_through_the_sec_ticker_alias(self):
        """BNY Mellon trades as BK and FMP serves it that way, but SEC lists it as BNY.
        The alias is EXPLICIT per-issuer — a fuzzy name match could pair the wrong CIK,
        crossing one issuer's fundamentals with another's price."""
        from adapters.edgar_adapter import SEC_TICKER_ALIASES
        assert SEC_TICKER_ALIASES["BK"] == "BNY"
        assert fetch_edgar("BK", fixture_path=EDGAR / "BK.json").cik == "0001390777"

    @pytest.mark.parametrize("ticker", CALIBRATION_CIKS)
    def test_calibration_tickers_are_not_in_the_batch_universe(self, ticker):
        """Calibration instruments, NOT holdings — ruled 2026-08-09. If one ever appears
        in tickers.txt it starts consuming synthesis budget and producing E(R) for a
        position nobody holds."""
        universe = Path("tickers.txt").read_text(encoding="utf-8")
        lines = [l.split("#")[0].strip().upper()
                 for l in universe.splitlines() if l.split("#")[0].strip()]
        assert ticker not in lines

    def test_jpm_cash_resolves_through_the_bank_tag(self):
        """FLIPPED 2026-08-09: the expected-fail pin fired and the chain was extended.

        Was: cash withheld (stale_tag) because JPM abandoned
        CashAndCashEquivalentsAtCarryingValue in 2018. Now: the chain falls through to
        the bank-specific CashAndDueFromBanks and resolves at the current period. The
        generic tag stays FIRST in the chain, so no non-bank resolution moved — verified
        live across the golden five at the time of the change."""
        cash = _fields("JPM")["cash"]
        assert cash.is_resolved(), f"JPM cash should resolve via CashAndDueFromBanks: {cash.reason}"
        assert cash.value and cash.value > 0
        assert cash.period_end >= "2026-01-01", (
            f"must be a CURRENT period, not the abandoned 2018 tag: {cash.period_end}")

    def test_jpm_long_term_debt_stays_withheld(self):
        """DELIBERATE, not an oversight. JPM's migration target,
        LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities, INCLUDES
        current maturities, so it is a debt TOTAL and is chained on total_debt_reported.
        Chaining it here would conflate two bases and double-count the current portion
        against current_debt. JPM files no non-current-only debt tag, so this is withheld
        and that is the honest answer."""
        ltd = _fields("JPM")["long_term_debt"]
        assert not ltd.is_resolved()
        assert _fields("JPM")["total_debt_reported"].is_resolved(), (
            "the migration target belongs on total_debt_reported and must resolve there")

    def test_jpm_unclassified_balance_sheet_yields_no_current_ratio(self):
        """Same accepted data limit as WU: banks do not file AssetsCurrent /
        LiabilitiesCurrent, so there is no working-capital view to compute."""
        fields = _fields("JPM")
        for name in ("current_assets", "current_liabilities"):
            assert not fields[name].is_resolved()
            assert fields[name].reason == REASON_NO_TAG

    def test_jpm_core_earnings_fields_still_resolve(self):
        """The bank instrument needs ROE and equity; those must be present even though
        the balance-sheet and cash chains are not."""
        fields = _fields("JPM")
        for name in ("revenue", "net_income", "equity", "total_assets"):
            assert fields[name].is_resolved(), f"JPM/{name}: {fields[name].reason}"
