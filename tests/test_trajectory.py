"""
Trajectory tag derivation tests.
Encodes the two canonical failure cases the spec requires.
"""
import pytest
from adapters.base import derive_trajectory_tag

M = 0.03   # margin threshold (3pp)
G = 0.05   # growth threshold (5pp decimal)


# ── Canonical failure cases ───────────────────────────────────────────────────

def test_mrq_ripping_ttm_lags_is_accelerating():
    """
    FAILURE CASE 1 — Early recovery: MRQ ripping while TTM lags.
    Must be 'accelerating'. Must NEVER be 'peaking'.
    MU-style: TTM 30% (recovery still baking in), MRQ 55% (latest quarter breakout).
    """
    tag = derive_trajectory_tag(ttm_val=0.30, mrq_val=0.55, guided_val=None, threshold=M)
    assert tag == "accelerating", f"Early-recovery rip must be 'accelerating', got '{tag}'"
    assert tag != "peaking", "MRQ > TTM by large margin must NEVER be tagged 'peaking'"


def test_mrq_cracking_ttm_still_high_is_rolling_over():
    """
    FAILURE CASE 2 — Rollover: MRQ cracking while TTM still high.
    Must be 'rolling_over'. Must NEVER be 'peaking'.
    Cyclical top: TTM=72%, MRQ=58% (margins contracting from cycle peak).
    """
    tag = derive_trajectory_tag(ttm_val=0.72, mrq_val=0.58, guided_val=None, threshold=M)
    assert tag == "rolling_over", f"Contraction from high TTM must be 'rolling_over', got '{tag}'"
    assert tag != "peaking", (
        "MRQ cracking below TTM must be 'rolling_over', NEVER 'peaking'. "
        "'Peaking' implies the metric is still at its apex."
    )


# ── Peaking (valid trigger paths) ────────────────────────────────────────────

def test_peaking_stable_zone_guide_retreats():
    """Peaking: MRQ ≈ TTM (within threshold), guided pulling back."""
    tag = derive_trajectory_tag(ttm_val=0.70, mrq_val=0.72, guided_val=0.65, threshold=M)
    assert tag == "peaking", f"Stable zone + guide retreating should be 'peaking', got '{tag}'"


def test_peaking_mrq_accelerating_but_guide_reverses():
    """MRQ slightly above TTM but guide signals immediate reversal → peaking."""
    tag = derive_trajectory_tag(ttm_val=0.68, mrq_val=0.73, guided_val=0.65, threshold=M)
    assert tag == "peaking", f"Expected 'peaking' (MRQ high, guide retreating), got '{tag}'"


def test_peaking_requires_guide_data():
    """Peaking without guide data and no large delta → defaults to stable, not peaking."""
    tag = derive_trajectory_tag(ttm_val=0.70, mrq_val=0.72, guided_val=None, threshold=M)
    assert tag != "peaking", "Cannot be peaking without guide confirmation in stable zone"
    assert tag == "stable"


# ── Accelerating ─────────────────────────────────────────────────────────────

def test_accelerating_no_guide():
    tag = derive_trajectory_tag(ttm_val=0.40, mrq_val=0.50, guided_val=None, threshold=M)
    assert tag == "accelerating"


def test_accelerating_guide_confirms():
    tag = derive_trajectory_tag(ttm_val=0.40, mrq_val=0.50, guided_val=0.55, threshold=M)
    assert tag == "accelerating"


def test_accelerating_at_extreme_level():
    """MU case: TTM=72.6%, MRQ=84.6% → still accelerating despite extreme absolute level."""
    tag = derive_trajectory_tag(ttm_val=0.726, mrq_val=0.846, guided_val=None, threshold=M)
    assert tag == "accelerating"


def test_accelerating_large_revenue_growth():
    """346% MRQ revenue growth vs 300% TTM → accelerating."""
    tag = derive_trajectory_tag(ttm_val=3.00, mrq_val=3.46, guided_val=None, threshold=G)
    assert tag == "accelerating"


def test_accelerating_from_trough():
    """Early-recovery signature: large positive delta from low base."""
    tag = derive_trajectory_tag(ttm_val=-0.20, mrq_val=0.10, guided_val=None, threshold=M)
    assert tag == "accelerating"


# ── Rolling over ─────────────────────────────────────────────────────────────

def test_rolling_over_no_guide():
    tag = derive_trajectory_tag(ttm_val=0.72, mrq_val=0.60, guided_val=None, threshold=M)
    assert tag == "rolling_over"


def test_rolling_over_guide_also_down():
    tag = derive_trajectory_tag(ttm_val=0.72, mrq_val=0.60, guided_val=0.50, threshold=M)
    assert tag == "rolling_over"


def test_rolling_over_exhaustive_mrq_range():
    """Core invariant: for ALL mrq values meaningfully below ttm=0.72, must be rolling_over."""
    for mrq in [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68]:
        tag = derive_trajectory_tag(ttm_val=0.72, mrq_val=mrq, guided_val=None, threshold=M)
        assert tag == "rolling_over", (
            f"mrq={mrq:.2f} < ttm=0.72 by >threshold → must be 'rolling_over', got '{tag}'"
        )
        assert tag != "peaking", f"mrq={mrq:.2f} < ttm=0.72 must NEVER be 'peaking'"


# ── Stable ────────────────────────────────────────────────────────────────────

def test_stable_negligible_delta():
    tag = derive_trajectory_tag(ttm_val=0.50, mrq_val=0.51, guided_val=None, threshold=M)
    assert tag == "stable"


def test_stable_exact_zero_delta():
    tag = derive_trajectory_tag(ttm_val=0.50, mrq_val=0.50, guided_val=None, threshold=M)
    assert tag == "stable"


def test_stable_guide_neutral():
    tag = derive_trajectory_tag(ttm_val=0.50, mrq_val=0.50, guided_val=0.51, threshold=M)
    assert tag == "stable"


def test_below_threshold_is_stable_not_accelerating():
    """delta < threshold must be stable. Uses 2pp delta vs 3pp threshold to avoid float edge."""
    tag = derive_trajectory_tag(ttm_val=0.50, mrq_val=0.52, guided_val=None, threshold=M)
    assert tag == "stable", f"delta=2pp < threshold=3pp must be 'stable', got '{tag}'"


def test_just_above_threshold_is_accelerating():
    tag = derive_trajectory_tag(ttm_val=0.50, mrq_val=0.531, guided_val=None, threshold=M)
    assert tag == "accelerating"


# ── Troughing ─────────────────────────────────────────────────────────────────

def test_troughing_stable_at_low_level():
    """Low absolute level + no strong delta → troughing (bouncing along bottom)."""
    tag = derive_trajectory_tag(
        ttm_val=0.12, mrq_val=0.13, guided_val=None,
        threshold=M, low_level_threshold=0.20,
    )
    assert tag == "troughing"


def test_troughing_negative_revenue_growth():
    tag = derive_trajectory_tag(
        ttm_val=-0.04, mrq_val=-0.03, guided_val=None,
        threshold=G, low_level_threshold=0.0,
    )
    assert tag == "troughing"


def test_troughing_not_triggered_at_high_level():
    """High absolute level with flat delta should be stable, not troughing."""
    tag = derive_trajectory_tag(
        ttm_val=0.65, mrq_val=0.66, guided_val=None,
        threshold=M, low_level_threshold=0.20,
    )
    assert tag != "troughing"
    assert tag == "stable"


# ── Guide-driven accelerating/peaking in stable zone ─────────────────────────

def test_guide_up_in_stable_zone_gives_accelerating():
    tag = derive_trajectory_tag(ttm_val=0.50, mrq_val=0.50, guided_val=0.56, threshold=M)
    assert tag == "accelerating"


def test_guide_down_in_stable_zone_gives_peaking():
    tag = derive_trajectory_tag(ttm_val=0.50, mrq_val=0.50, guided_val=0.44, threshold=M)
    assert tag == "peaking"


# ── None inputs ───────────────────────────────────────────────────────────────

def test_none_ttm_returns_stable():
    assert derive_trajectory_tag(None, 0.50, None, M) == "stable"


def test_none_mrq_returns_stable():
    assert derive_trajectory_tag(0.50, None, None, M) == "stable"


def test_none_both_returns_stable():
    assert derive_trajectory_tag(None, None, None, M) == "stable"
