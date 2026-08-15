"""H-3 — the compounder lens gains its own-history FCF-yield anchor.

WHAT ARMING MEANS HERE. Before H-3, own-history reached exactly ONE metric
(trailing earnings yield) and therefore exactly one armed panel lens (cyclical). Every
compounder reading was scored against two MARKET-REFERENCED denominators — risk-free and
sector — which is a 2-anchor panel that D-3 ruling 6 flags INDEPENDENCE-NARROWED. H-3
gives the majority lens its first issuer-referenced denominator.

THE AGGREGATION RULE IS UNCHANGED: MIN across available anchors, ruled permanent
2026-08-09. Adding an anchor can therefore only ever make a stock look CHEAPER-OR-EQUAL
never richer... in the other direction: MIN takes the least flattering, so a NEW anchor can
only pull a reading DOWN or leave it alone. WU is the case where it pulls.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import core.valuation_anchors as VA
from adapters.edgar_adapter import fetch_edgar
from adapters.fmp_adapter import fetch_fmp, fetch_splits
from adapters.fred_adapter import fetch_fred
from core.corporate_actions import build_split_report
from core.valuation_anchors import (
    ANCHOR_OWN_HISTORY, ANCHOR_RISK_FREE, ANCHOR_SECTOR, METRIC_FCF_YIELD,
    compute_panel, own_history_fcf_yields,
)

FX = Path(__file__).parent / "fixtures"

# Measured 2026-08-15 when H-3 was armed, against a LIVE sector snapshot (the offline
# fixtures carry none, so the sector anchor is absent there and WU's transition cannot be
# reproduced from fixtures alone). Kept as the arming record.
#   {ticker: (binding anchor before, spread before, binding anchor after, spread after)}
H3_BINDING_ANCHOR_DELTAS = {
    "GOOG": (ANCHOR_RISK_FREE, -3.41, ANCHOR_RISK_FREE, -3.41),   # gains an anchor, unbound
    "V":    (ANCHOR_SECTOR,    -2.45, ANCHOR_SECTOR,    -2.45),   # no FCF series at all
    "WU":   (ANCHOR_SECTOR,   +12.62, ANCHOR_OWN_HISTORY, +4.22),  # THE MOVER
}

# ZERO pillar cells moved on the golden five when H-3 was armed — measured, both with and
# without a live sector snapshot. Recorded in its own map so the D-4 trail in
# tests/test_pillars.py stays exactly as written (append-never-overwrite).
H3_SCORE_DELTAS: dict = {}


def _panel(ticker: str, sector_pe=None, lens: str = "compounder"):
    yf = fetch_fmp(ticker, fixture_path=FX / "fmp" / f"{ticker}.json")
    ed = fetch_edgar(ticker, fixture_path=FX / "edgar" / f"{ticker}.json")
    sp = fetch_splits(ticker, fixture_path=FX / "fmp" / f"{ticker}.json")
    report = build_split_report(ticker, sp, ed.financials) if sp is not None else None
    fred = fetch_fred(fixture_path=FX / "fred" / "DGS10.json")
    return compute_panel(yf, fred, ed, sector_pe or {}, lens, split_report=report)


def _own_history_fcf(panel):
    return next(r for r in panel.readings
                if r.metric == METRIC_FCF_YIELD and r.anchor == ANCHOR_OWN_HISTORY)


# ── The anchor exists at all ─────────────────────────────────────────────────

@pytest.mark.parametrize("ticker", ["GOOG", "NOW", "WU", "MU", "BK"])
def test_the_compounder_metric_now_has_an_own_history_anchor(ticker):
    """Before H-3 this reading was always unavailable with 'trailing-earnings only'."""
    r = _own_history_fcf(_panel(ticker))
    assert r.available, r.reason
    assert r.anchor_yield is not None
    assert "median of" in r.note


def test_the_series_comes_through_the_anchor_filter_not_raw_storage():
    """RULING 2: negative-FCF quarters are STORED but must never reach the anchor.

    C has 14 negative quarters of 21. The anchor must see only the usable ones, while the
    stored series keeps all of them for Phase M.
    """
    from core.fundamental_series import METRIC_FCF_YIELD as M, build_fcf_series
    ed = fetch_edgar("C", fixture_path=FX / "edgar" / "C.json")
    yf = fetch_fmp("C", fixture_path=FX / "fmp" / "C.json")
    stored = build_fcf_series("C", ed, yf.price_history, None).by_metric(M)
    series, _ = own_history_fcf_yields("C", ed, yf.price_history, None)
    assert len(stored) > len(series), "the anchor must see fewer points than storage"
    assert all(p["fcf_yield"] > 0 for p in series), "no negative yield may reach the anchor"


def test_the_anchor_carries_its_split_basis():
    """G-4 provenance rides through H-3: a yield built on a truncated share series is a
    different measurement from one built on a restated series, and the reading says so."""
    assert "basis=split_restated" in _own_history_fcf(_panel("GOOG")).note


# ── V: the degraded path, ASSERTED not silent ────────────────────────────────

@pytest.mark.parametrize("ticker", ["V", "JPM", "USB"])
def test_an_issuer_with_no_capex_concept_gets_NO_anchor_and_says_why(ticker):
    """V, JPM and USB file no PaymentsToAcquirePropertyPlantAndEquipment concept, so the
    whole FCF family is withheld and there is no own-history anchor to build.

    THE POINT OF THIS TEST IS THE REASON STRING. '0 historical points' is true both for a
    withheld family and for a series that existed and was entirely excluded, and those are
    different facts about the issuer. The reading must name the cause, so a later reader
    does not conclude V has a short history when it has none at all.
    """
    r = _own_history_fcf(_panel(ticker))
    assert not r.available
    assert "no_capex_tag" in r.reason, r.reason


def test_V_falls_back_to_the_market_referenced_pair_and_the_panel_notes_it():
    """The degraded path is a NARROWED PANEL, never a substituted anchor. V keeps
    risk-free + sector — two market-referenced denominators, which D-3 ruling 6 flags as
    independence-narrowed — and nothing stands in for the missing third."""
    panel = _panel("V", sector_pe={"Financial Services": 21.09})
    available = {r.anchor for r in panel.by_metric(METRIC_FCF_YIELD)}
    assert ANCHOR_OWN_HISTORY not in available
    assert available == {ANCHOR_RISK_FREE, ANCHOR_SECTOR}
    assert any("FCF anchor unavailable" in n for n in panel.notes), panel.notes


def test_the_missing_anchor_never_becomes_a_zero():
    """A withheld anchor must not be scored as a 0% baseline — that would read as
    'infinitely cheap vs its own history' and is exactly the silent degradation the panel
    exists to prevent."""
    r = _own_history_fcf(_panel("V"))
    assert r.anchor_yield is None


# ── WU: the mover ────────────────────────────────────────────────────────────

def test_WU_binding_anchor_moves_from_sector_to_own_history():
    """THE ARMING'S HEADLINE, and the case H-FCF scoping predicted.

    WU screens cheap on every market-referenced denominator (+13.54 vs risk-free, +12.62
    vs sector) and merely cheap-ish against its own history (+4.22). Under MIN the new
    anchor binds and strips ~8.4pp off the read — the same shape as D-0's finding that
    own-history stripped 11.6pp off WU's trailing-earnings screening buy.

    Scoping predicted sector -> own_history and an 8.37pp narrowing; measured 8.40pp.
    """
    panel = _panel("WU", sector_pe={"Financial Services": 17.81})
    readings = {r.anchor: r for r in panel.by_metric(METRIC_FCF_YIELD)}
    assert ANCHOR_OWN_HISTORY in readings

    binding = min(readings.values(), key=lambda r: r.spread)
    assert binding.anchor == ANCHOR_OWN_HISTORY, \
        {a: round(r.spread, 2) for a, r in readings.items()}
    narrowing = readings[ANCHOR_SECTOR].spread - binding.spread
    assert narrowing == pytest.approx(8.4, abs=0.3), narrowing


def test_WU_survives_at_the_top_rung_because_4pp_still_clears_it():
    """Scoping's other prediction: the binding anchor moves but the SCORE does not,
    because +4.22pp still clears the ladder's +3.0 top rung. A ticker nearer a boundary
    would have moved — that is why this arming is a real blast radius and not a no-op."""
    from core.valuation_anchors import RATE_SPREAD_LADDER
    top_threshold = RATE_SPREAD_LADDER[0][0]
    panel = _panel("WU", sector_pe={"Financial Services": 17.81})
    binding = min(panel.by_metric(METRIC_FCF_YIELD), key=lambda r: r.spread)
    assert binding.spread > top_threshold


# ── The recorded arming diff ─────────────────────────────────────────────────

def test_no_golden_score_moved_when_H3_was_armed():
    """H3_SCORE_DELTAS is EMPTY and that is the measurement, not an omission.

    If a future change makes H-3 move a golden score, this test is where it surfaces, and
    the delta gets recorded in the map rather than absorbed.
    """
    assert H3_SCORE_DELTAS == {}, (
        "a score delta was recorded for H-3; re-measure the golden five and update the "
        "arming report before accepting it")


def test_the_binding_anchor_record_matches_what_the_panel_does_now():
    """Pins the recorded arming deltas against live behaviour for the anchors that do not
    need a sector snapshot to be reproducible."""
    goog = {r.anchor: r for r in _panel("GOOG").by_metric(METRIC_FCF_YIELD)}
    assert ANCHOR_OWN_HISTORY in goog
    # GOOG gains the anchor but risk-free still binds — MIN keeps the least flattering.
    assert min(goog.values(), key=lambda r: r.spread).anchor == ANCHOR_RISK_FREE
