"""
Cross-check + confidence engine tests.
Validates ethos rule 1 (provenance) and rule 2 (anti-launder).
"""
import pytest
from adapters.base import Prov, min_conf, missing_prov
from core.cross_check import apply_cross_check, apply_staleness_penalty


# ── Prov basics ───────────────────────────────────────────────────────────────

def test_prov_is_missing_none():
    p = Prov(value=None, source="test", as_of="2026-01-01", confidence="medium")
    assert p.is_missing()


def test_prov_is_missing_nan():
    import math
    p = Prov(value=float("nan"), source="test", as_of="2026-01-01", confidence="medium")
    assert p.is_missing()


def test_prov_not_missing_zero():
    p = Prov(value=0.0, source="test", as_of="2026-01-01", confidence="high")
    assert not p.is_missing()


# ── min_conf (anti-launder) ───────────────────────────────────────────────────

def test_min_conf_single_high():
    p = Prov(value=1.0, source="a", as_of="2026-01-01", confidence="high")
    assert min_conf(p) == "high"


def test_min_conf_high_and_low_gives_low():
    p1 = Prov(value=1.0, source="a", as_of="2026-01-01", confidence="high")
    p2 = Prov(value=2.0, source="b", as_of="2026-01-01", confidence="low")
    assert min_conf(p1, p2) == "low"


def test_min_conf_high_and_medium_gives_medium():
    p1 = Prov(value=1.0, source="a", as_of="2026-01-01", confidence="high")
    p2 = Prov(value=2.0, source="b", as_of="2026-01-01", confidence="medium")
    assert min_conf(p1, p2) == "medium"


def test_min_conf_all_medium():
    provs = [Prov(value=i, source="a", as_of="2026-01-01", confidence="medium") for i in range(5)]
    assert min_conf(*provs) == "medium"


def test_min_conf_none_inputs_returns_low():
    assert min_conf() == "low"


def test_min_conf_skips_missing_values():
    """Missing Provs should be excluded from min_conf computation, not drag it to low."""
    p1 = Prov(value=1.0, source="a", as_of="2026-01-01", confidence="high")
    p_missing = Prov(value=None, source="b", as_of=None, confidence="low")
    # missing prov should be skipped; result from p1 alone = high
    assert min_conf(p1, p_missing) == "high"


def test_min_conf_all_missing_returns_low():
    p = Prov(value=None, source="a", as_of=None, confidence="low")
    assert min_conf(p) == "low"


# ── cross_check ───────────────────────────────────────────────────────────────

def test_cross_check_agree_gives_high():
    primary = Prov(value=100.0, source="yfinance", as_of="2026-07-09", confidence="medium")
    result = apply_cross_check(primary, 100.5, "tiingo", "2026-07-09", tolerance_pct=2.0)
    assert result.confidence == "high"


def test_cross_check_agree_within_tolerance():
    primary = Prov(value=100.0, source="yfinance", as_of="2026-07-09", confidence="medium")
    result = apply_cross_check(primary, 101.9, "tiingo", "2026-07-09", tolerance_pct=2.0)
    assert result.confidence == "high"


def test_cross_check_exact_match_gives_high():
    primary = Prov(value=50.0, source="yfinance", as_of="2026-07-09", confidence="medium")
    result = apply_cross_check(primary, 50.0, "tiingo", "2026-07-09")
    assert result.confidence == "high"


def test_cross_check_conflict_gives_low():
    primary = Prov(value=100.0, source="yfinance", as_of="2026-07-09", confidence="medium")
    result = apply_cross_check(primary, 120.0, "tiingo", "2026-07-09", tolerance_pct=2.0)
    assert result.confidence == "low"


def test_cross_check_secondary_none_unchanged():
    """If no secondary value, primary confidence is unchanged."""
    primary = Prov(value=100.0, source="yfinance", as_of="2026-07-09", confidence="medium")
    result = apply_cross_check(primary, None, "tiingo", "2026-07-09")
    assert result.confidence == "medium"
    assert result.value == 100.0


def test_cross_check_missing_primary_unchanged():
    primary = missing_prov("yfinance", "2026-07-09")
    result = apply_cross_check(primary, 100.0, "tiingo", "2026-07-09")
    assert result.is_missing()


def test_cross_check_source_attribution():
    primary = Prov(value=100.0, source="yfinance", as_of="2026-07-09", confidence="medium")
    result = apply_cross_check(primary, 100.0, "tiingo", "2026-07-09")
    assert "tiingo" in result.source


# ── staleness ─────────────────────────────────────────────────────────────────

def test_staleness_caps_high_to_medium():
    p = Prov(value=1.0, source="a", as_of="2025-01-01", confidence="high")
    result = apply_staleness_penalty(p, days_old=100, stale_threshold=90)
    assert result.confidence == "medium"


def test_staleness_leaves_medium_unchanged():
    p = Prov(value=1.0, source="a", as_of="2025-01-01", confidence="medium")
    result = apply_staleness_penalty(p, days_old=100, stale_threshold=90)
    assert result.confidence == "medium"


def test_staleness_fresh_data_unchanged():
    p = Prov(value=1.0, source="a", as_of="2026-07-01", confidence="high")
    result = apply_staleness_penalty(p, days_old=8, stale_threshold=90)
    assert result.confidence == "high"


def test_staleness_undated_caps_high():
    p = Prov(value=1.0, source="a", as_of=None, confidence="high")
    result = apply_staleness_penalty(p, days_old=0)
    assert result.confidence == "medium"
