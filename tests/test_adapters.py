"""
Adapter fixture-loading tests.
All tests run against recorded fixtures — no live network calls.
"""
from pathlib import Path
import pytest

from adapters.fixture_adapter import fetch_fixture
from core.datatypes import TickerData
from adapters.edgar_adapter import fetch_edgar, EdgarData
from adapters.fred_adapter import fetch_fred, FredData
from adapters.fmp_adapter import fetch_fmp

FIXTURE_ROOT = Path("tests/fixtures")
YF = FIXTURE_ROOT / "ticker"
EDGAR = FIXTURE_ROOT / "edgar"
FRED_FX = FIXTURE_ROOT / "fred" / "DGS10.json"
FMP = FIXTURE_ROOT / "fmp"


# ── fixture adapter ──────────────────────────────────────────────────────────

class TestFixtureAdapter:
    def test_mu_loads_from_fixture(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf, TickerData)
        assert yf.ticker == "MU"

    def test_mu_sector_is_technology(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert yf.sector == "Technology"

    def test_mu_industry_semiconductors(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert yf.industry == "Semiconductors"

    def test_mu_gross_margin_is_prov(self):
        from adapters.base import Prov
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.gross_margin, Prov)
        assert not yf.gross_margin.is_missing()

    def test_mu_gross_margin_source(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert yf.gross_margin.source == "yfinance"

    def test_mu_gross_margin_confidence_medium(self):
        """Single source → medium (no secondary cross-check feed wired in)."""
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert yf.gross_margin.confidence == "medium"

    def test_mu_gross_margin_range(self):
        """MU gross margin is high at cycle peak (>50%)."""
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        gm = yf.gross_margin.value
        assert gm is not None
        assert 0.5 < gm < 1.0, f"Expected >50%, got {gm:.2%}"

    def test_mu_forward_pe_positive(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        if not yf.forward_pe.is_missing():
            assert yf.forward_pe.value > 0

    def test_mu_revenue_growth_positive(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        if not yf.revenue_growth.is_missing():
            # MU had massive recovery; value should be positive
            assert yf.revenue_growth.value > 0

    def test_mu_fcf_yield_computed(self):
        """FCF yield is derived: free_cashflow / market_cap."""
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        if not yf.free_cashflow.is_missing() and not yf.market_cap.is_missing():
            if yf.market_cap.value and yf.market_cap.value > 0:
                assert not yf.fcf_yield.is_missing()

    def test_goog_loads(self):
        yf = fetch_fixture("GOOG", fixture_path=YF / "GOOG.json")
        assert yf.ticker == "GOOG"
        assert yf.sector == "Communication Services"

    def test_goog_industry(self):
        yf = fetch_fixture("GOOG", fixture_path=YF / "GOOG.json")
        assert yf.industry == "Internet Content & Information"

    def test_v_loads(self):
        yf = fetch_fixture("V", fixture_path=YF / "V.json")
        assert yf.ticker == "V"
        assert yf.sector == "Financial Services"

    def test_v_industry_credit_services(self):
        yf = fetch_fixture("V", fixture_path=YF / "V.json")
        assert yf.industry == "Credit Services"

    def test_nan_coerced_to_none(self):
        """NaN fields must become None Provs (not crash)."""
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        # Any field that happens to be None must still be a Prov
        from adapters.base import Prov
        assert isinstance(yf.beta, Prov)

    def test_missing_fixture_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="fixture not found"):
            fetch_fixture("FAKE", fixture_path=Path("nonexistent.json"))

    def test_earnings_history_is_list(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.earnings_history, list)

    def test_insider_transactions_is_list(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.insider_transactions, list)

    def test_price_history_is_list(self):
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
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

        fake = fetch_fixture("MU", fixture_path=YF / "MU.json")
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
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        assert yf.feed_source == "yfinance"                       # recorded data — accurate
        assert yf.gross_margin_trajectory.ttm.source == "yfinance"
        assert yf.gross_margin_trajectory.mrq.source == "yfinance/quarterly_financials"

    def test_derived_sources_follow_feed_source(self):
        from core.technicals import analyze_technicals
        from core.pillars import score_management
        yf = fetch_fixture("MU", fixture_path=YF / "MU.json")
        yf.feed_source = "fmp"    # simulate the live FMP feed
        tech = analyze_technicals(yf.price_history, feed_source=yf.feed_source)
        assert tech.price_vs_ma50_pct.source == "fmp/price_history"
        mgmt = score_management(yf, "cyclical")
        earn = [p for p in mgmt.key_inputs if p.source and "earnings" in p.source]
        assert earn and earn[0].source == "fmp/earnings_history"
