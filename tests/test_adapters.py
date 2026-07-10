"""
Adapter fixture-loading tests.
All tests run against recorded fixtures — no live network calls.
"""
from pathlib import Path
import pytest

from adapters.yfinance_adapter import fetch_yfinance, YFinanceData
from adapters.edgar_adapter import fetch_edgar, EdgarData
from adapters.fred_adapter import fetch_fred, FredData
from adapters.alphavantage_adapter import fetch_alphavantage, AlphaVantageData

FIXTURE_ROOT = Path("tests/fixtures")
YF = FIXTURE_ROOT / "yfinance"
EDGAR = FIXTURE_ROOT / "edgar"
FRED_FX = FIXTURE_ROOT / "fred" / "DGS10.json"
AV = FIXTURE_ROOT / "alphavantage"


# ── yfinance adapter ──────────────────────────────────────────────────────────

class TestYFinanceAdapter:
    def test_mu_loads_from_fixture(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf, YFinanceData)
        assert yf.ticker == "MU"

    def test_mu_sector_is_technology(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        assert yf.sector == "Technology"

    def test_mu_industry_semiconductors(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        assert yf.industry == "Semiconductors"

    def test_mu_gross_margin_is_prov(self):
        from adapters.base import Prov
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.gross_margin, Prov)
        assert not yf.gross_margin.is_missing()

    def test_mu_gross_margin_source(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        assert yf.gross_margin.source == "yfinance"

    def test_mu_gross_margin_confidence_medium(self):
        """Single source → medium (AlphaVantage cross-check not applied in isolation)."""
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        assert yf.gross_margin.confidence == "medium"

    def test_mu_gross_margin_range(self):
        """MU gross margin is high at cycle peak (>50%)."""
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        gm = yf.gross_margin.value
        assert gm is not None
        assert 0.5 < gm < 1.0, f"Expected >50%, got {gm:.2%}"

    def test_mu_forward_pe_positive(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        if not yf.forward_pe.is_missing():
            assert yf.forward_pe.value > 0

    def test_mu_revenue_growth_positive(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        if not yf.revenue_growth.is_missing():
            # MU had massive recovery; value should be positive
            assert yf.revenue_growth.value > 0

    def test_mu_fcf_yield_computed(self):
        """FCF yield is derived: free_cashflow / market_cap."""
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        if not yf.free_cashflow.is_missing() and not yf.market_cap.is_missing():
            if yf.market_cap.value and yf.market_cap.value > 0:
                assert not yf.fcf_yield.is_missing()

    def test_goog_loads(self):
        yf = fetch_yfinance("GOOG", fixture_path=YF / "GOOG.json")
        assert yf.ticker == "GOOG"
        assert yf.sector == "Communication Services"

    def test_goog_industry(self):
        yf = fetch_yfinance("GOOG", fixture_path=YF / "GOOG.json")
        assert yf.industry == "Internet Content & Information"

    def test_v_loads(self):
        yf = fetch_yfinance("V", fixture_path=YF / "V.json")
        assert yf.ticker == "V"
        assert yf.sector == "Financial Services"

    def test_v_industry_credit_services(self):
        yf = fetch_yfinance("V", fixture_path=YF / "V.json")
        assert yf.industry == "Credit Services"

    def test_nan_coerced_to_none(self):
        """NaN fields must become None Provs (not crash)."""
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        # Any field that happens to be None must still be a Prov
        from adapters.base import Prov
        assert isinstance(yf.beta, Prov)

    def test_missing_fixture_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="fixture not found"):
            fetch_yfinance("FAKE", fixture_path=Path("nonexistent.json"))

    def test_earnings_history_is_list(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.earnings_history, list)

    def test_insider_transactions_is_list(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        assert isinstance(yf.insider_transactions, list)

    def test_price_history_is_list(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
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


# ── AlphaVantage adapter ──────────────────────────────────────────────────────

class TestAlphaVantageAdapter:
    def test_mu_loads_from_fixture(self):
        av = fetch_alphavantage("MU", fixture_path=AV / "MU.json")
        assert isinstance(av, AlphaVantageData)
        assert av.ticker == "MU"

    def test_gross_margin_computed_from_revenue_and_profit(self):
        """gross_margin = GrossProfitTTM / RevenueTTM — derived, not a raw field."""
        av = fetch_alphavantage("MU", fixture_path=AV / "MU.json")
        assert av.gross_margin is not None
        assert 0.5 < av.gross_margin < 1.0, f"Expected >50%, got {av.gross_margin:.2%}"

    def test_operating_margin_present(self):
        av = fetch_alphavantage("MU", fixture_path=AV / "MU.json")
        assert av.operating_margin is not None
        assert 0.0 < av.operating_margin < 1.0

    def test_roe_present(self):
        av = fetch_alphavantage("MU", fixture_path=AV / "MU.json")
        assert av.roe is not None

    def test_trailing_pe_positive(self):
        av = fetch_alphavantage("MU", fixture_path=AV / "MU.json")
        assert av.trailing_pe is not None
        assert av.trailing_pe > 0

    def test_forward_pe_positive(self):
        av = fetch_alphavantage("MU", fixture_path=AV / "MU.json")
        assert av.forward_pe is not None
        assert av.forward_pe > 0

    def test_market_cap_large(self):
        av = fetch_alphavantage("MU", fixture_path=AV / "MU.json")
        assert av.market_cap is not None
        assert av.market_cap > 1e11  # > $100B

    def test_missing_fixture_raises(self):
        with pytest.raises(RuntimeError, match="fixture not found"):
            fetch_alphavantage("FAKE", fixture_path=Path("nonexistent.json"))

    def test_none_string_parsed_as_none(self):
        """AV returns 'None' string for missing values — must parse to Python None."""
        from adapters.alphavantage_adapter import _av_float
        assert _av_float("None") is None
        assert _av_float("-") is None
        assert _av_float("") is None
        assert _av_float("N/A") is None
        assert _av_float("42.5") == pytest.approx(42.5)
        assert _av_float("1234567890") == pytest.approx(1234567890.0)


# ── AlphaVantage cross-check integration ─────────────────────────────────────

class TestAlphaVantangeCrossCheck:
    """Tests that apply_av_cross_checks correctly upgrades/downgrades yfinance fields."""

    def _load(self):
        yf = fetch_yfinance("MU", fixture_path=YF / "MU.json")
        av = fetch_alphavantage("MU", fixture_path=AV / "MU.json")
        return yf, av

    def test_agreeing_fields_upgrade_to_high(self):
        from core.cross_check import apply_av_cross_checks
        yf, av = self._load()
        result = apply_av_cross_checks(yf, av)
        # Gross margin should agree (fixture values calibrated within 5%)
        assert result.gross_margin.confidence == "high", (
            f"Expected high after AV agreement, got {result.gross_margin.confidence}. "
            f"yf={yf.gross_margin.value:.4f} av={av.gross_margin:.4f}"
        )

    def test_operating_margin_upgrades(self):
        from core.cross_check import apply_av_cross_checks
        yf, av = self._load()
        result = apply_av_cross_checks(yf, av)
        assert result.operating_margin.confidence == "high"

    def test_roe_upgrades(self):
        from core.cross_check import apply_av_cross_checks
        yf, av = self._load()
        result = apply_av_cross_checks(yf, av)
        assert result.roe.confidence == "high"

    def test_source_attribution_includes_alphavantage(self):
        from core.cross_check import apply_av_cross_checks
        yf, av = self._load()
        result = apply_av_cross_checks(yf, av)
        assert "alphavantage" in result.gross_margin.source

    def test_conflict_degrades_to_low(self):
        """Deliberately conflicting AV value → confidence drops to low."""
        from core.cross_check import apply_av_cross_checks
        from adapters.alphavantage_adapter import AlphaVantageData
        yf, av = self._load()
        # Replace gross_margin with a wildly different value (50% relative diff)
        bad_av = AlphaVantageData(
            ticker="MU",
            gross_margin=0.20,   # yfinance says ~0.726 — far outside tolerance
            operating_margin=av.operating_margin,
            roe=av.roe, roa=av.roa,
            trailing_pe=av.trailing_pe, forward_pe=av.forward_pe,
            price_to_book=av.price_to_book,
            ev_to_ebitda=av.ev_to_ebitda, ev_to_revenue=av.ev_to_revenue,
            beta=av.beta, market_cap=av.market_cap,
            shares_outstanding=av.shares_outstanding,
        )
        result = apply_av_cross_checks(yf, bad_av)
        assert result.gross_margin.confidence == "low", (
            "Conflicting AV value must downgrade confidence to low"
        )

    def test_none_av_field_leaves_primary_unchanged(self):
        """If AV has no value for a field, primary confidence is not changed."""
        from core.cross_check import apply_av_cross_checks
        from adapters.alphavantage_adapter import AlphaVantageData
        yf, av = self._load()
        no_beta_av = AlphaVantageData(
            ticker="MU",
            gross_margin=av.gross_margin,
            operating_margin=av.operating_margin,
            roe=av.roe, roa=av.roa,
            trailing_pe=av.trailing_pe, forward_pe=av.forward_pe,
            price_to_book=av.price_to_book,
            ev_to_ebitda=av.ev_to_ebitda, ev_to_revenue=av.ev_to_revenue,
            beta=None,   # ← no AV beta
            market_cap=av.market_cap,
            shares_outstanding=av.shares_outstanding,
        )
        result = apply_av_cross_checks(yf, no_beta_av)
        assert result.beta.confidence == yf.beta.confidence  # unchanged
