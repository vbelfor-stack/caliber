"""
Lens selector tests — encode the golden-ticker lens assertions.
These must pass at every phase boundary from Phase 1 onward.
"""
import pytest
from core.lens_select import select_lens


# ── Golden-ticker assertions ──────────────────────────────────────────────────

def test_mu_lens_is_cyclical():
    """MU: Micron Technology. SIC 3674, industry 'Semiconductors'. Must be cyclical."""
    lens = select_lens("Technology", "Semiconductors", sic="3674")
    assert lens == "cyclical", f"Expected cyclical, got {lens}"


def test_goog_lens_is_compounder():
    """GOOG: Alphabet. Must be compounder — asset-light ad platform.
    Must NOT get growth/Rule-of-40 (wrong for mature mega-cap) and NOT standard."""
    lens = select_lens("Communication Services", "Internet Content & Information", sic="7370")
    assert lens == "compounder", (
        f"GOOG must be quality-compounder lens, got {lens}. "
        "Alphabet is an asset-light ad platform with massive FCF — compounder framing, not Rule-of-40."
    )
    assert lens != "growth", "GOOG must never get growth/Rule-of-40 lens — hard assertion."


def test_v_lens_is_compounder_not_bank():
    """V: Visa. HARD ASSERTION — lens must be compounder, never bank.
    Even though sector='Financial Services', Visa is asset-light; P/TBV is meaningless."""
    lens = select_lens("Financial Services", "Credit Services", sic="7389")
    assert lens == "compounder", (
        f"Visa must use compounder lens, got {lens}. "
        "Asset-light payment network; P/TBV is irrelevant."
    )
    assert lens != "bank", "Visa must NEVER get bank lens — hard assertion."


# ── Additional lens coverage ──────────────────────────────────────────────────

def test_now_lens_is_growth():
    """NOW: ServiceNow. HARD ASSERTION — growth lens (Rule-of-40 framing).
    yfinance returns 'Software - Application' (regular dash, spaces)."""
    lens = select_lens("Technology", "Software - Application", sic="7372")
    assert lens == "growth", (
        f"ServiceNow must get growth lens, got {lens}. "
        "yfinance industry='Software - Application' (space-dash-space, not em-dash)."
    )


def test_saas_gets_growth_lens():
    """ServiceNow-like profile: Technology + Software—Application → growth."""
    lens = select_lens("Technology", "Software—Application", sic="7372")
    assert lens == "growth", f"Expected growth, got {lens}"


def test_software_infrastructure_gets_growth():
    lens = select_lens("Technology", "Software—Infrastructure", sic="7372")
    assert lens == "growth", f"Expected growth, got {lens}"


def test_bank_gets_bank_lens():
    lens = select_lens("Financial Services", "Banking", sic="6022")
    assert lens == "bank", f"Expected bank, got {lens}"


def test_insurer_gets_bank_lens():
    lens = select_lens("Financial Services", "Life Insurance", sic="6311")
    assert lens == "bank", f"Expected bank, got {lens}"


def test_reit_gets_bank_lens():
    lens = select_lens("Real Estate", "REIT—Retail", sic="6512")
    assert lens == "bank", f"Expected bank, got {lens}"


def test_semiconductor_by_sic_is_cyclical():
    """SIC 3674 alone should classify as cyclical even without industry keyword."""
    lens = select_lens("Technology", "Electronic Components", sic="3674")
    assert lens == "cyclical", f"Expected cyclical by SIC, got {lens}"


def test_materials_company_is_cyclical():
    lens = select_lens("Basic Materials", "Aluminum", sic="3350")
    assert lens == "cyclical", f"Expected cyclical, got {lens}"


def test_standard_is_fallback():
    """Generic industrial company with no specific lens signals → standard."""
    lens = select_lens("Industrials", "Aerospace & Defense", sic="3812")
    assert lens == "standard", f"Expected standard fallback, got {lens}"


def test_none_sector_does_not_crash():
    """Adapter may return None for sector — must not raise."""
    lens = select_lens(None, "Semiconductors", sic="3674")
    assert lens == "cyclical"


def test_none_industry_does_not_crash():
    """SIC alone should still classify."""
    lens = select_lens("Technology", None, sic="3674")
    assert lens == "cyclical"


def test_communication_services_not_growth():
    """Communication Services sector is excluded from growth lens.
    Internet-content/internet-software industries map to compounder, never growth."""
    lens = select_lens("Communication Services", "Internet Software & Services", sic="7370")
    assert lens != "growth", f"Communication Services sector must not get growth lens, got {lens}"
    # Internet Software & Services is now compounder (asset-light ad/platform)
    assert lens == "compounder", f"Internet Software & Services should be compounder, got {lens}"
