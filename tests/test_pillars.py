"""
Pillar scorer tests — using fixture data for MU, GOOG, V.
Validates anti-launder, lens-dispatch, and MU golden test (cycle-peak valuation).
"""
import json
from pathlib import Path
import pytest

from adapters.base import Prov, min_conf, missing_prov
from adapters.yfinance_adapter import fetch_yfinance
from adapters.edgar_adapter import fetch_edgar
from adapters.fred_adapter import fetch_fred
from core.lens_select import select_lens
from core.pillars import (
    score_business_quality,
    score_financial_health,
    score_management,
    score_growth,
    score_valuation,
    score_all,
    _valuation_compounder,
)

FIXTURE_ROOT = Path("tests/fixtures")
YF_FIXTURES = FIXTURE_ROOT / "yfinance"
EDGAR_FIXTURES = FIXTURE_ROOT / "edgar"
FRED_FIXTURE = FIXTURE_ROOT / "fred" / "DGS10.json"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mu_yf():
    return fetch_yfinance("MU", fixture_path=YF_FIXTURES / "MU.json")

@pytest.fixture(scope="module")
def mu_edgar():
    return fetch_edgar("MU", fixture_path=EDGAR_FIXTURES / "MU.json")

@pytest.fixture(scope="module")
def goog_yf():
    return fetch_yfinance("GOOG", fixture_path=YF_FIXTURES / "GOOG.json")

@pytest.fixture(scope="module")
def v_yf():
    return fetch_yfinance("V", fixture_path=YF_FIXTURES / "V.json")

@pytest.fixture(scope="module")
def fred():
    return fetch_fred(fixture_path=FRED_FIXTURE)

@pytest.fixture(scope="module")
def mu_lens(mu_yf, mu_edgar):
    return select_lens(mu_yf.sector, mu_yf.industry, mu_edgar.sic)

@pytest.fixture(scope="module")
def goog_lens(goog_yf):
    return select_lens(goog_yf.sector, goog_yf.industry)

@pytest.fixture(scope="module")
def v_lens(v_yf):
    return select_lens(v_yf.sector, v_yf.industry)


# ── Adapter loading sanity ────────────────────────────────────────────────────

def test_mu_yf_loads(mu_yf):
    assert mu_yf.ticker == "MU"
    assert mu_yf.sector == "Technology"
    assert not mu_yf.gross_margin.is_missing()

def test_mu_yf_gross_margin_value(mu_yf):
    """MU gross margin must be the high value seen in Phase 0 fixtures (cycle peak)."""
    gm = mu_yf.gross_margin.value
    assert gm is not None
    assert 0.5 < gm < 1.0, f"Expected MU gross margin >50%, got {gm:.2%}"

def test_mu_yf_forward_pe_low(mu_yf):
    """MU forward PE should be much lower than trailing (cycle peak pattern)."""
    if mu_yf.forward_pe.is_missing() or mu_yf.trailing_pe.is_missing():
        pytest.skip("PE data missing from fixture")
    assert mu_yf.forward_pe.value < mu_yf.trailing_pe.value, (
        "Forward PE should be lower than trailing for MU at cycle peak"
    )

def test_v_industry(v_yf):
    assert v_yf.industry == "Credit Services"

def test_goog_sector(goog_yf):
    assert goog_yf.sector == "Communication Services"


# ── Lens assertions (golden) ──────────────────────────────────────────────────

def test_mu_lens_is_cyclical(mu_lens):
    assert mu_lens == "cyclical", f"MU must be cyclical, got {mu_lens}"

def test_goog_lens_is_compounder(goog_lens):
    assert goog_lens == "compounder", (
        f"GOOG must be quality-compounder (asset-light ad platform), got {goog_lens}"
    )
    assert goog_lens != "growth", "GOOG must never be growth/Rule-of-40 — hard assertion"

def test_v_lens_is_compounder(v_lens):
    assert v_lens == "compounder", f"V must be compounder, got {v_lens}"

def test_v_lens_is_not_bank(v_lens):
    assert v_lens != "bank", "V must never be bank lens — hard assertion"


# ── Anti-launder ──────────────────────────────────────────────────────────────

def test_pillar_confidence_never_exceeds_inputs(mu_yf, mu_edgar, fred, mu_lens):
    """Anti-launder: if any material input is low-confidence, pillar confidence must be ≤ that."""
    # Inject a low-confidence override into a field
    original = mu_yf.gross_margin
    mu_yf.gross_margin = Prov(value=original.value, source="test", as_of=None, confidence="low")
    try:
        result = score_business_quality(mu_yf, mu_lens)
        # Pillar confidence must not be higher than the low-confidence input
        assert result.confidence in ("low",), (
            f"Anti-launder violated: pillar confidence={result.confidence} "
            f"but gross_margin was low"
        )
    finally:
        mu_yf.gross_margin = original


def test_all_medium_inputs_give_medium_pillar(mu_yf, mu_edgar, fred, mu_lens):
    """Single-source (yfinance only, no Tiingo) → all fields are medium → pillar must be medium."""
    result = score_business_quality(mu_yf, mu_lens)
    # All yfinance fields are medium (single source, no Tiingo cross-check)
    assert result.confidence in ("medium", "low"), (
        f"Single-source pillar must be medium or lower, got {result.confidence}"
    )


# ── MU golden: cycle-peak valuation ──────────────────────────────────────────

def test_mu_valuation_not_scored_cheap(mu_yf, fred, mu_lens):
    """
    Golden test (MU): low forward PE at peak margins must NOT score as cheap.
    Score must be ≤ 3 when cycle-peak margins are present.
    """
    assert mu_lens == "cyclical"
    result = score_valuation(mu_yf, fred, mu_lens)
    assert result.score <= 3, (
        f"MU valuation at cycle peak must NOT score cheap (≤3). Got score={result.score}. "
        f"Flags: {result.flags}. Rationale: {result.rationale}"
    )


def test_mu_valuation_has_peak_earnings_flag(mu_yf, fred, mu_lens):
    """Valuation flags must contain cycle-peak warning for MU."""
    result = score_valuation(mu_yf, fred, mu_lens)
    peak_flags = [f for f in result.flags if "CYCLE" in f or "PEAK" in f]
    assert peak_flags, (
        f"MU valuation must flag cycle-peak condition. Got flags: {result.flags}"
    )


def test_mu_valuation_rationale_mentions_peak(mu_yf, fred, mu_lens):
    """Golden assertion: valuation rationale must contain peak-earnings warning."""
    result = score_valuation(mu_yf, fred, mu_lens)
    rationale_lower = result.rationale.lower()
    assert "peak" in rationale_lower or "cycle" in rationale_lower, (
        f"MU valuation rationale must mention peak/cycle. Got: {result.rationale}"
    )


# ── Growth pillar load-bearing check ─────────────────────────────────────────

def test_mu_growth_pillar_has_recovery_flag(mu_yf, mu_edgar, mu_lens):
    """MU revenueGrowth=3.46 (346%) is cyclical recovery from trough, must be flagged."""
    if mu_yf.revenue_growth.is_missing():
        pytest.skip("Revenue growth missing from fixture")
    result = score_growth(mu_yf, mu_edgar, mu_lens)
    # Should note cyclical recovery
    if mu_yf.revenue_growth.value > 1.0:
        assert "CYCLICAL-RECOVERY-GROWTH" in result.flags, (
            f"MU 346% growth should flag as cyclical recovery. Flags: {result.flags}"
        )


def test_growth_pillar_scores_high_growth_well(mu_yf, mu_edgar, mu_lens):
    """High revenue growth should score ≥3 on Growth pillar."""
    if mu_yf.revenue_growth.is_missing():
        pytest.skip("Revenue growth missing from fixture")
    result = score_growth(mu_yf, mu_edgar, mu_lens)
    assert result.score >= 3, f"High revenue growth should score ≥3, got {result.score}"


# ── Trajectory assertions (MU fixture expectations) ──────────────────────────

def test_mu_has_gross_margin_trajectory(mu_yf):
    assert mu_yf.gross_margin_trajectory is not None, (
        "MU fixture must have gross_margin_trajectory — re-probe if missing"
    )


def test_mu_gross_margin_trajectory_ttm_value(mu_yf):
    t = mu_yf.gross_margin_trajectory
    if t is None:
        pytest.skip("No trajectory in fixture")
    assert not t.ttm.is_missing()
    assert 0.5 < t.ttm.value < 1.0, f"TTM gross margin out of expected range: {t.ttm.value}"


def test_mu_gross_margin_trajectory_mrq_above_ttm(mu_yf):
    """MU MRQ gross margin should be materially above TTM — margins still accelerating."""
    t = mu_yf.gross_margin_trajectory
    if t is None or t.mrq.is_missing():
        pytest.skip("No MRQ trajectory in fixture")
    assert t.mrq.value > t.ttm.value, (
        f"MU MRQ gross margin ({t.mrq.value:.2%}) should exceed TTM ({t.ttm.value:.2%}) "
        "— margins still accelerating at Q3 FY2026"
    )


def test_mu_gross_margin_trajectory_tag_accelerating(mu_yf):
    """MU gross margin trajectory: MRQ >> TTM → accelerating."""
    t = mu_yf.gross_margin_trajectory
    if t is None or t.mrq.is_missing():
        pytest.skip("No MRQ trajectory in fixture")
    delta = t.mrq.value - t.ttm.value
    if delta > 0.03:  # only assert if we'd expect accelerating
        assert t.tag == "accelerating", (
            f"MU MRQ ({t.mrq.value:.2%}) >> TTM ({t.ttm.value:.2%}) "
            f"must be 'accelerating', got '{t.tag}'"
        )


def test_mu_has_revenue_growth_trajectory(mu_yf):
    assert mu_yf.revenue_growth_trajectory is not None, (
        "MU fixture must have revenue_growth_trajectory"
    )


def test_mu_revenue_growth_trajectory_ttm(mu_yf):
    t = mu_yf.revenue_growth_trajectory
    if t is None:
        pytest.skip("No trajectory")
    assert not t.ttm.is_missing()
    assert t.ttm.value > 0.5, f"MU TTM revenue growth should be very high: {t.ttm.value}"


def test_mu_trajectory_cycle_position_text_not_trough(mu_yf, fred, mu_lens):
    """Cycle position rationale must not say 'trough' for MU at near-peak margins."""
    result = score_valuation(mu_yf, fred, mu_lens)
    assert "trough" not in result.rationale.lower(), (
        f"MU cycle position must not show 'trough'. Rationale: {result.rationale}"
    )


def test_mu_trajectory_cycle_position_references_trajectory(mu_yf, fred, mu_lens):
    """Rationale must reference the trajectory-derived position, not just 'near-peak'."""
    result = score_valuation(mu_yf, fred, mu_lens)
    # The cycle_pos will be from trajectory: accelerating-toward-peak or near-peak
    pos_keywords = ["accelerating", "peak", "cycle"]
    assert any(kw in result.rationale.lower() for kw in pos_keywords), (
        f"Valuation rationale must reference trajectory-based cycle position. "
        f"Got: {result.rationale}"
    )


# ── Compounder secular-decline language conditionality ───────────────────────

_TODAY_STR = __import__("datetime").date.today().isoformat()


def _make_minimal_yf(revenue_growth_val=None, fcf_yield_val=None) -> "YFinanceData":
    """Build a minimal YFinanceData for isolated _valuation_compounder tests."""
    from adapters.yfinance_adapter import YFinanceData
    m = missing_prov("test", _TODAY_STR)
    rg = (Prov(value=revenue_growth_val, source="test", as_of=_TODAY_STR, confidence="medium")
          if revenue_growth_val is not None else m)
    fy = (Prov(value=fcf_yield_val, source="test", as_of=_TODAY_STR, confidence="medium")
          if fcf_yield_val is not None else m)
    return YFinanceData(
        ticker="TEST", name="Test Co", sector="Financial Services",
        industry="Credit Services", sic=None,
        gross_margin=m, operating_margin=m, profit_margin=m, roe=m, roa=m,
        current_ratio=m, debt_to_equity=m, total_debt=m, total_cash=m,
        free_cashflow=m, operating_cashflow=m,
        revenue_growth=rg,
        trailing_pe=m, forward_pe=m, analyst_count=m, target_mean_price=m,
        price_to_book=m, ev_to_ebitda=m, ev_to_revenue=m, market_cap=m,
        current_price=m, enterprise_value=m,
        fcf_yield=fy,
        shares_outstanding=m, beta=m,
        earnings_history=[], insider_transactions=[], price_history=[],
        gross_margin_trajectory=None, revenue_growth_trajectory=None,
    )


def _make_fred(rate: float) -> "FredData":
    from adapters.fred_adapter import FredData
    return FredData(rate_10y=Prov(value=rate, source="test", as_of=_TODAY_STR, confidence="medium"))


def test_compounder_secular_decline_flag_when_growth_negative():
    """When compounder lens + negative revenue growth + high FCF yield → SECULAR-DECLINE-FCF-YIELD flag."""
    yf = _make_minimal_yf(revenue_growth_val=-0.03, fcf_yield_val=0.10)  # -3% growth, 10% FCF yield
    fred = _make_fred(4.5)  # 10Y at 4.5%; spread = 5.5% → high
    result = _valuation_compounder(yf, fred)
    assert "SECULAR-DECLINE-FCF-YIELD" in result.flags, (
        f"Compounder + negative growth must flag SECULAR-DECLINE-FCF-YIELD. "
        f"Flags: {result.flags}"
    )


def test_compounder_secular_decline_text_in_rationale():
    """Rationale must explicitly state secular-decline pricing, not cheapness."""
    yf = _make_minimal_yf(revenue_growth_val=-0.03, fcf_yield_val=0.10)
    fred = _make_fred(4.5)
    result = _valuation_compounder(yf, fred)
    assert "secular-decline" in result.rationale.lower(), (
        f"Compounder + negative growth rationale must say 'secular-decline'. "
        f"Got: {result.rationale}"
    )
    assert "not cheapness" in result.rationale.lower(), (
        f"Rationale must explicitly say 'not cheapness'. Got: {result.rationale}"
    )


def test_compounder_growing_company_no_secular_decline_flag():
    """When revenue growth is strong, NO secular-decline flag — WU pattern must not fire for healthy compounders."""
    yf = _make_minimal_yf(revenue_growth_val=0.15, fcf_yield_val=0.10)  # 15% growth
    fred = _make_fred(4.5)
    result = _valuation_compounder(yf, fred)
    assert "SECULAR-DECLINE-FCF-YIELD" not in result.flags, (
        f"Healthy compounder (15% growth) must NOT get secular-decline flag. "
        f"Flags: {result.flags}"
    )
    assert "secular-decline" not in result.rationale.lower(), (
        f"Healthy compounder rationale must NOT mention secular-decline. "
        f"Got: {result.rationale}"
    )


def test_compounder_flat_growth_no_secular_decline_without_fcf_spread():
    """Secular-decline text only fires when BOTH growth is weak AND FCF yield spread is material (>=1%)."""
    yf = _make_minimal_yf(revenue_growth_val=-0.03, fcf_yield_val=0.04)  # -3% growth but yield < rate
    fred = _make_fred(4.5)  # rate 4.5%; fcf yield 4% → spread -0.5% (no positive spread)
    result = _valuation_compounder(yf, fred)
    assert "SECULAR-DECLINE-FCF-YIELD" not in result.flags, (
        "Negative growth + low FCF yield spread must NOT trigger secular-decline flag "
        "(the high-yield-looks-cheap logic doesn't apply here)"
    )


def test_compounder_secular_decline_rationale_within_220_chars():
    """Rationale must stay within the 220-char synthesis prompt limit even with secular-decline text."""
    yf = _make_minimal_yf(revenue_growth_val=-0.03, fcf_yield_val=0.10)
    fred = _make_fred(4.5)
    result = _valuation_compounder(yf, fred)
    assert len(result.rationale) <= 220, (
        f"Compounder secular-decline rationale exceeds 220 chars: {len(result.rationale)} chars. "
        f"Text: {result.rationale}"
    )


# ── Full pipeline smoke test ──────────────────────────────────────────────────

def test_score_all_returns_five_pillars(mu_yf, mu_edgar, fred, mu_lens):
    results = score_all(mu_yf, mu_edgar, fred, mu_lens)
    assert len(results) == 5
    names = [r.name for r in results]
    assert "Business Quality" in names
    assert "Financial Health" in names
    assert "Management & Capital Allocation" in names
    assert "Growth / Forward" in names
    assert "Valuation" in names


def test_all_pillar_scores_in_range(mu_yf, mu_edgar, fred, mu_lens):
    results = score_all(mu_yf, mu_edgar, fred, mu_lens)
    for r in results:
        assert 1 <= r.score <= 5, f"Pillar {r.name} score {r.score} out of range"


def test_all_pillar_confidences_valid(mu_yf, mu_edgar, fred, mu_lens):
    results = score_all(mu_yf, mu_edgar, fred, mu_lens)
    valid = {"high", "medium", "low"}
    for r in results:
        assert r.confidence in valid, f"Invalid confidence {r.confidence} in {r.name}"


def test_all_pillar_rationales_within_limit(mu_yf, mu_edgar, fred, mu_lens):
    results = score_all(mu_yf, mu_edgar, fred, mu_lens)
    for r in results:
        assert len(r.rationale) <= 220, (
            f"Pillar {r.name} rationale exceeds 220 chars: {len(r.rationale)}"
        )
