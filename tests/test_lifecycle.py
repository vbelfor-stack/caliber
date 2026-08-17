"""
Phase L testing gates (order §7, docs/orders/2026-08-16-phase-l-lifecycle-classifier.md).

WHAT THESE ARE. The classifier is DARK — no score, no confidence label, no lens and no
E(R) reads it. So these are not regression tests protecting a number; they are the gates
§7 names, plus the guards that make the stage table trustworthy to Phase M, which WILL
read it.

THE FOUR THINGS PINNED HARDEST, because each one is a way the table could lie quietly:
  1. RULE ORDER. First match wins. A ticker that satisfies two rules must land on the
     earlier one, deterministically, or the same inputs classify differently by accident.
  2. ASSERTED-ABSENT (R1). A missing input is never a zero, never a False, never a
     default. It cannot satisfy a condition, and its absence travels with the row.
  3. AND-PRECEDENCE ASYMMETRY (R6/R7). DECLINE is strict — any absent leg and it cannot
     fire. HIGROWTH uses remaining-legs, which is what makes NOW classify at all.
  4. THE G-4 CONTRACT ON DIVIDENDS. None means UNKNOWN, [] means PAYS NONE. Collapsing
     them pushes a name toward DECLINE or HIGROWTH on evidence never gathered.

THE CYCLICAL GUARD HAS BEEN DEFINED THREE TIMES AND THE TEST HISTORY IS DELIBERATE:
L-1b compared latest revenue to the prior peak; L-1c compared it to the pre-streak peak;
both were provably ALL-PERMIT, so the guard could not refuse anything. L-1d rules
PEAK-TO-PEAK. `test_the_guard_can_both_permit_and_refuse_so_it_is_not_vacuous` exists
specifically to catch a fourth one-sided definition, because one-sidedness is the failure
mode that survived two rulings unnoticed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.lifecycle import (
    FLAG_CYCLICAL_GUARD_BLIND,
    FLAG_CYCLICAL_GUARD_HELD,
    FLAG_CYCLICAL_GUARD_HELD_YOUNG,
    FLAG_CYCLICAL_GUARD_UNEVALUABLE_FCF,
    FLAG_GUARD_TOLERANCE_UNCALIBRATED,
    FLAG_INPUTS_INCOMPLETE,
    FLAG_INSUFFICIENT_HISTORY,
    FLAG_LENS_INCOMPAT,
    FLAG_REINVEST_UNCALIBRATED,
    FLAG_YOUNG_UNCALIBRATED,
    STAGE_DECLINE,
    STAGE_HIGROWTH,
    STAGE_MATURE,
    STAGE_YOUNG,
    Leg,
    build_legs,
    classify,
    lens_compatibility_flags,
)
from core.lifecycle_config import (
    B2_DIVERGENCE_TOLERANCE_BY_STAGE,
    BUYBACK_DE_MINIMIS_NET_REDUCTION,
    CYCLICAL_MIN_FY,
    DECLINE_MIN_STREAK_YEARS,
    DECLINE_MIN_STREAK_YEARS_CYCLICAL,
    HIGROWTH_MIN_CAGR,
    LIFECYCLE_CONFIG_VERSION,
    M_WIDTH_PRIOR_ORDERING,
    MARGIN_FLAT_BAND_BP,
    REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL,
)
from store.models import (
    OverrideRationaleMissing,
    get_standing_override,
    init_db,
    list_lifecycle_stages,
    list_lifecycle_transitions,
    save_lifecycle_override,
    save_lifecycle_stage,
)

PAYS_DIVIDEND = [{"ex_date": "2025-12-01", "dividend": 0.25, "frequency": "Quarterly"}]


# ── synthetic income_annual builders ─────────────────────────────────────────
# SYNTHETIC ON PURPOSE (§7: "each rule fires on synthetic fixtures"). A live ticker
# exercises one path through the rules; these exercise the paths no live name reaches,
# including the ones we hope never occur.

def _income(pairs, margins=None):
    """pairs = [(fiscal_year, revenue)]; margins = [pct] aligned, or None for untagged."""
    rows = []
    for i, (year, rev) in enumerate(pairs):
        oi = None if margins is None else rev * margins[i] / 100.0
        rows.append({"date": f"{year}-12-31", "revenue": rev, "operatingIncome": oi})
    return rows


def _legs(income, lens=None, *, dividends=None, shares=None, fcf=None, stc=None):
    return build_legs("SYN", income, lens, dividends=dividends, shares_series=shares,
                      fcf_fy=fcf, sales_to_capital_fy=stc)


def _outcomes(result, rule):
    return {a.leg: a.outcome for a in result.assertions if a.rule == rule}


# ── §7: each rule fires ───────────────────────────────────────────────────────

def test_rule1_decline_fires_on_a_non_cyclical_name():
    """Three declining years, margin inside the flat band, a dividend being paid."""
    income = _income([(2022, 1000), (2023, 950), (2024, 900), (2025, 850)],
                     margins=[20.0, 19.5, 19.2, 19.0])
    r = classify("SYN", _legs(income, "compounder", dividends=PAYS_DIVIDEND), "compounder")
    assert r.stage == STAGE_DECLINE
    assert r.rule_fired == "rule1_decline"
    assert _outcomes(r, "rule1_decline") == {
        "decline_streak": "satisfied",
        "margin_trend_bp": "satisfied",
        "capital_returns": "satisfied",
    }
    assert not r.inputs_incomplete


def test_rule2_young_fires_on_a_negative_operating_margin():
    income = _income([(2022, 100), (2023, 200), (2024, 400), (2025, 800)],
                     margins=[-30.0, -20.0, -10.0, -5.0])
    r = classify("SYN", _legs(income, "growth", dividends=[]), "growth")
    assert r.stage == STAGE_YOUNG
    assert r.rule_fired == "rule2_young"
    assert _outcomes(r, "rule2_young")["margin_sign"] == "satisfied"


def test_rule2_young_fires_on_fcf_negative_in_2_of_last_3_years():
    """Margin positive, so the FCF leg is the only thing that can trigger YOUNG."""
    income = _income([(2022, 100), (2023, 200), (2024, 400), (2025, 800)],
                     margins=[5.0, 6.0, 7.0, 8.0])
    fcf = [("2023-12-31", -50.0), ("2024-12-31", -20.0), ("2025-12-31", 10.0)]
    r = classify("SYN", _legs(income, "growth", dividends=[], fcf=fcf), "growth")
    assert r.stage == STAGE_YOUNG
    assert _outcomes(r, "rule2_young") == {"margin_sign": "not_satisfied",
                                           "fcf_negative_2of3": "satisfied"}


def test_rule3_higrowth_fires_on_cagr_plus_heavy_reinvestment_plus_no_returns():
    income = _income([(2022, 1000), (2023, 1200), (2024, 1400), (2025, 1600)],
                     margins=[5.0, 6.0, 7.0, 8.0])
    r = classify("SYN", _legs(income, "growth", dividends=[],
                              shares=[("2022-12-31", 100.0), ("2025-12-31", 105.0)],
                              stc=[("2024-12-31", 1.2), ("2025-12-31", 1.1)]), "growth")
    assert r.stage == STAGE_HIGROWTH
    assert r.rule_fired == "rule3_higrowth"
    assert _outcomes(r, "rule3_higrowth") == {
        "revenue_cagr": "satisfied",
        "reinvestment_heavy": "satisfied",
        "capital_returns": "satisfied",
    }
    # Consulting the uncalibrated bar is always declared (R6: four tickers is not a
    # calibration, so every reading that leans on it says so).
    assert FLAG_REINVEST_UNCALIBRATED in r.flags


def test_rule4_mature_is_the_residual():
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[20.0, 20.5, 21.0, 21.5])
    r = classify("SYN", _legs(income, "compounder", dividends=PAYS_DIVIDEND), "compounder")
    assert r.stage == STAGE_MATURE
    assert r.rule_fired == "rule4_mature"
    assert _outcomes(r, "rule4_mature")["residual"] == "satisfied"


# ── §7: ordering respected ────────────────────────────────────────────────────

def test_decline_wins_over_young_when_both_would_fire():
    """Revenue falling AND margin gone negative. Rule 1 is evaluated first, so DECLINE."""
    income = _income([(2022, 1000), (2023, 950), (2024, 900), (2025, 850)],
                     margins=[5.0, 2.0, 0.5, -1.0])
    r = classify("SYN", _legs(income, "compounder", dividends=PAYS_DIVIDEND), "compounder")
    assert r.stage == STAGE_DECLINE, "rule order broken: YOUNG pre-empted DECLINE"


def test_young_wins_over_higrowth_when_both_would_fire():
    """20%+ CAGR with a negative margin is a YOUNG name, not a HIGROWTH one."""
    income = _income([(2022, 1000), (2023, 1300), (2024, 1600), (2025, 2000)],
                     margins=[-5.0, -4.0, -3.0, -2.0])
    r = classify("SYN", _legs(income, "growth", dividends=[],
                              stc=[("2024-12-31", 1.0), ("2025-12-31", 1.0)]), "growth")
    assert r.stage == STAGE_YOUNG, "rule order broken: HIGROWTH pre-empted YOUNG"


def test_the_four_rules_are_evaluated_in_the_ordered_sequence():
    """Assertion order IS the audit trail of evaluation order; pin it, don't assume it."""
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[20.0, 20.5, 21.0, 21.5])
    r = classify("SYN", _legs(income, "compounder", dividends=PAYS_DIVIDEND), "compounder")
    seen = []
    for a in r.assertions:
        if a.rule not in seen:
            seen.append(a.rule)
    assert seen == ["rule1_decline", "rule2_young", "rule3_higrowth", "rule4_mature"]


# ── §7: insufficient history ──────────────────────────────────────────────────

def test_insufficient_history_yields_young_with_an_assertion():
    r = classify("SYN", _legs(_income([(2025, 500)], margins=[10.0]), "growth"), "growth")
    assert r.stage == STAGE_YOUNG
    assert r.rule_fired == "rule2_young_insufficient_history"
    assert FLAG_INSUFFICIENT_HISTORY in r.flags
    assert FLAG_YOUNG_UNCALIBRATED in r.flags
    assert any(a.leg == "fy_count" and a.outcome == "satisfied" for a in r.assertions)


def test_the_insufficient_history_row_states_WHY_each_leg_is_absent():
    """DEFECT FIX (L-1b). This return wrote bare leg names into absent_legs while every
    other path wrote "name(reason)" — so the one row where absence is the entire story was
    the one row that did not say why."""
    r = classify("SYN", _legs(_income([(2025, 500)], margins=[10.0]), "growth"), "growth")
    assert r.absent_legs, "a one-year history must report absent legs"
    for entry in r.absent_legs:
        assert entry.endswith(")") and "(" in entry, (
            f"absent leg {entry!r} carries no reason — R1 requires one")


def test_no_leg_is_listed_twice_in_absent_legs():
    """DEFECT FIX (L-1b). The dedupe compared a bare name against a list of formatted
    "name(reason)" entries, so it never matched. Phase M reads this column."""
    income = _income([(2022, 1000), (2023, 950), (2024, 900), (2025, 850)], margins=None)
    r = classify("SYN", _legs(income, "compounder", dividends=None), "compounder")
    assert len(r.absent_legs) == len(set(r.absent_legs))


# ── R1 / R7: asserted-absent mechanics ────────────────────────────────────────

def test_an_absent_leg_cannot_satisfy_a_condition():
    assert Leg.absent("x", "because").present is False
    with pytest.raises(ValueError):
        Leg(name="x", value=1, present=False)           # absent with no reason
    with pytest.raises(ValueError):
        Leg(name="x", value=1, present=True, reason="r")  # reason on a present leg


def test_decline_is_STRICT_one_absent_leg_and_it_cannot_fire():
    """R7 by name: 'a classification as consequential as DECLINE is never awarded on
    partial evidence.' Revenue and returns legs both satisfied; margin untagged."""
    income = _income([(2022, 1000), (2023, 950), (2024, 900), (2025, 850)],
                     margins=None)                       # no operatingIncome anywhere
    legs = _legs(income, "compounder", dividends=PAYS_DIVIDEND)
    assert legs["decline_streak"].value >= DECLINE_MIN_STREAK_YEARS
    assert legs["capital_returns"].value is True
    assert legs["margin_trend_bp"].present is False
    r = classify("SYN", legs, "compounder")
    assert r.stage != STAGE_DECLINE
    assert _outcomes(r, "rule1_decline")["margin_trend_bp"] == "absent"
    assert FLAG_INPUTS_INCOMPLETE in r.flags
    assert any("margin_trend_bp" in e for e in r.absent_legs)


def test_higrowth_uses_REMAINING_LEGS_and_stamps_the_gap():
    """R6 names this outcome directly — it is what lets NOW classify with a single-point
    sales-to-capital series."""
    income = _income([(2022, 1000), (2023, 1200), (2024, 1400), (2025, 1600)],
                     margins=[5.0, 6.0, 7.0, 8.0])
    legs = _legs(income, "growth", dividends=[],
                 stc=[("2025-12-31", 1.6)])              # single point -> absent
    assert legs["reinvestment_heavy"].present is False
    r = classify("SYN", legs, "growth")
    assert r.stage == STAGE_HIGROWTH
    assert FLAG_INPUTS_INCOMPLETE in r.flags
    assert r.inputs_incomplete


def test_higrowth_cannot_fire_without_a_MEASURED_cagr():
    """'High growth' with no measured growth is a guess. CAGR is the non-negotiable leg."""
    income = _income([(2023, 1200), (2024, 1400), (2025, 1600)],   # no FY exactly 3y back
                     margins=[6.0, 7.0, 8.0])
    legs = _legs(income, "growth", dividends=[],
                 stc=[("2024-12-31", 1.0), ("2025-12-31", 1.0)])
    assert legs["revenue_cagr"].present is False
    r = classify("SYN", legs, "growth")
    assert r.stage == STAGE_MATURE
    assert _outcomes(r, "rule3_higrowth")["revenue_cagr"] == "absent"


def test_a_window_is_never_silently_shortened():
    """R9: both endpoints present and exactly N years apart, or asserted-absent. A 2y CAGR
    reported as a 3y CAGR is a wrong number wearing a right label."""
    legs = _legs(_income([(2023, 100), (2024, 150), (2025, 200)], margins=[5, 6, 7]),
                 "growth", dividends=[])
    assert legs["revenue_cagr"].present is False
    assert "3y" in legs["revenue_cagr"].reason


# ── R4: gaps break streaks (synthetic — GOOG is explicitly NOT this case) ─────

def test_a_calendar_gap_breaks_a_decline_streak():
    """R4/R9: a gap never extends or manufactures a decline.

    DELIBERATELY SYNTHETIC. R9's parenthetical cited a GOOG 2022-23 gap; the R9-directed
    measurement corrected that — the gap is in the EDGAR-derived series, and FMP
    income_annual carries GOOG 2016-2025 complete. GOOG must NOT be this test's case, so
    the hole here is invented.
    """
    # 2021 absent. Adjacent-in-list would read 4 declining years; consecutive-in-fiscal
    # years reads 3, stopping at the hole.
    income = _income([(2020, 1000), (2022, 900), (2023, 850), (2024, 800), (2025, 750)],
                     margins=[10.0] * 5)
    legs = _legs(income, "compounder", dividends=PAYS_DIVIDEND)
    assert legs["decline_streak"].value == 3, "the streak spanned a hole in the series"


def test_a_gap_at_the_endpoint_makes_the_cagr_absent_rather_than_wrong():
    income = _income([(2021, 1000), (2023, 1200), (2024, 1400), (2025, 1600)],
                     margins=[5.0, 6.0, 7.0, 8.0])       # 2022 absent -> no 3y endpoint
    legs = _legs(income, "growth", dividends=[])
    assert legs["revenue_cagr"].present is False


# ── §3 rule 1: the cyclical guard ─────────────────────────────────────────────

def test_a_cyclical_name_needs_a_longer_streak_than_a_non_cyclical_one():
    """Two declining years: DECLINE for a compounder, held for a cyclical."""
    income = _income([(y, r) for y, r in
                      [(2016, 700), (2017, 800), (2018, 900), (2019, 1000),
                       (2020, 1100), (2021, 1200), (2022, 1300), (2023, 1400),
                       (2024, 1300), (2025, 1200)]],
                     margins=[10.0] * 10)
    cyc = classify("SYN", _legs(income, "cyclical", dividends=PAYS_DIVIDEND), "cyclical")
    non = classify("SYN", _legs(income, "compounder", dividends=PAYS_DIVIDEND),
                   "compounder")
    assert non.stage == STAGE_DECLINE
    assert cyc.stage != STAGE_DECLINE
    assert FLAG_CYCLICAL_GUARD_HELD in cyc.flags
    assert DECLINE_MIN_STREAK_YEARS_CYCLICAL > DECLINE_MIN_STREAK_YEARS


def test_a_cyclical_guard_that_cannot_see_a_cycle_refuses_to_rule_on_one():
    """R9: under CYCLICAL_MIN_FY measured years the guard is asserted-absent, and for a
    cyclical name that means DECLINE cannot fire at all."""
    income = _income([(2022, 1000), (2023, 950), (2024, 900), (2025, 850)],
                     margins=[10.0] * 4)                 # 4 FY < 8
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    assert legs["cyclical_peak_to_peak"].present is False
    assert str(CYCLICAL_MIN_FY) in legs["cyclical_peak_to_peak"].reason
    r = classify("SYN", legs, "cyclical")
    assert r.stage != STAGE_DECLINE
    assert FLAG_CYCLICAL_GUARD_BLIND in r.flags


def test_the_guard_is_not_applied_to_non_cyclical_lenses():
    income = _income([(2022, 1000), (2023, 950), (2024, 900), (2025, 850)],
                     margins=[10.0] * 4)
    legs = _legs(income, "compounder", dividends=PAYS_DIVIDEND)
    leg = legs["cyclical_peak_to_peak"]
    assert leg.present and leg.value is None and "not applicable" in leg.detail


def test_the_guard_PERMITS_when_the_later_cycle_peak_is_below_the_earlier_one():
    """THE RULED DEFINITION (L-1d): peak-to-peak. The two most recent local peaks; the
    guard permits DECLINE only if the later peak is BELOW the earlier one. Strict, no
    tolerance.

    FLIPPED TWICE NOW, and the history is the point: L-1b compared latest-vs-prior-peak
    (vacuous), L-1c compared latest-vs-pre-streak-peak (also vacuous, provably), and only a
    peak-against-peak comparison measures SECULAR decline rather than trough depth.

    Series below: local peaks 1100 @ 2018 and 900 @ 2022. Later peak is LOWER, so each
    cycle is topping out weaker — the guard permits and DECLINE fires.
    """
    income = _income([(2016, 500), (2017, 900), (2018, 1100), (2019, 700), (2020, 600),
                      (2021, 800), (2022, 900), (2023, 800), (2024, 700), (2025, 600)],
                     margins=[10.0] * 10)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    assert legs["decline_streak"].value == 3
    guard = legs["cyclical_peak_to_peak"]
    assert guard.value is True
    assert "peak 2022 900 vs prior peak 2018 1,100" in guard.detail
    assert "LOWER (permit)" in guard.detail
    r = classify("SYN", legs, "cyclical")
    assert r.stage == STAGE_DECLINE
    assert FLAG_GUARD_TOLERANCE_UNCALIBRATED in r.flags


def test_the_guard_REFUSES_when_the_cycle_peaks_are_RISING():
    """The case every earlier definition let through, and the reason peak-to-peak was ruled.

    Rising cycle tops (700 @ 2018 then 1200 @ 2022) mean the business is not secularly
    declining, however deep the current trough. A magnitude bar would PERMIT here — the
    trough is 25% off the peak — which is exactly the MU-shaped false positive.
    """
    income = _income([(2016, 500), (2017, 600), (2018, 700), (2019, 650), (2020, 800),
                      (2021, 1000), (2022, 1200), (2023, 1100), (2024, 1000), (2025, 900)],
                     margins=[10.0] * 10)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    assert legs["decline_streak"].value == 3
    guard = legs["cyclical_peak_to_peak"]
    assert guard.value is False
    assert "NOT lower (refuse)" in guard.detail
    r = classify("SYN", legs, "cyclical")
    assert r.stage != STAGE_DECLINE
    assert FLAG_CYCLICAL_GUARD_HELD in r.flags


def test_both_peak_values_are_logged_on_every_evaluation():
    """Ruled: log both peaks so a tolerance can be calibrated later on REAL refusals."""
    income = _income([(2016, 500), (2017, 900), (2018, 1100), (2019, 700), (2020, 600),
                      (2021, 800), (2022, 900), (2023, 800), (2024, 700), (2025, 600)],
                     margins=[10.0] * 10)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    peaks = legs["cyclical_peaks"]
    assert peaks.value == ["2018:1,100", "2022:900"]
    assert "delta -18.18%" in peaks.detail
    r = classify("SYN", legs, "cyclical")
    assert any(a.leg == "cyclical_peaks" for a in r.assertions)
    assert r.inputs["cyclical_peaks"] == ["2018:1,100", "2022:900"]   # persisted


def test_peaks_are_logged_even_when_the_guard_does_not_fire():
    """The calibration set must not be empty. MU is the only cyclical name in the universe
    and its guard does not fire (streak 0), so logging peaks only on a comparison would
    leave nothing to calibrate a tolerance against — the opposite of the instruction."""
    income = _income([(2016, 500), (2017, 900), (2018, 1100), (2019, 700), (2020, 600),
                      (2021, 800), (2022, 900), (2023, 800), (2024, 700), (2025, 1500)],
                     margins=[10.0] * 10)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    assert legs["decline_streak"].value == 0                  # guard does not fire
    assert legs["cyclical_peak_to_peak"].value is None
    assert legs["cyclical_peaks"].value == ["2018:1,100", "2022:900"]
    r = classify("SYN", legs, "cyclical")
    assert r.inputs["cyclical_peaks"] == ["2018:1,100", "2022:900"]


def test_fewer_than_two_local_peaks_REFUSES_the_permit_without_voiding_the_verdict():
    """Ruled fail-direction: the GATE fails closed, and that is not the same as voiding the
    classification. No two measurable cycle tops means no secular-decline tag on streak
    strength alone — but the name still classifies on the remaining rules, so this must NOT
    stamp INPUTS-INCOMPLETE the way the streak-spans-window case does."""
    # One local peak only (2021), then a long decline.
    income = _income([(2016, 400), (2017, 500), (2018, 600), (2019, 700), (2020, 800),
                      (2021, 900), (2022, 850), (2023, 800), (2024, 750), (2025, 700)],
                     margins=[10.0] * 10)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    guard = legs["cyclical_peak_to_peak"]
    assert legs["decline_streak"].value == 4
    assert guard.present is True and guard.value is False
    assert "only 1 local peak" in guard.detail
    r = classify("SYN", legs, "cyclical")
    assert r.stage != STAGE_DECLINE
    assert not any("cyclical_peak_to_peak" in e for e in r.absent_legs)
    assert FLAG_GUARD_TOLERANCE_UNCALIBRATED not in r.flags      # no pair to calibrate on


def test_the_latest_fy_can_never_be_a_local_peak():
    """Its right-hand neighbour does not exist yet, so calling it a peak would assert the
    cycle has topped when the next reading is what decides that."""
    from core.lifecycle import _fy_series, _local_peaks
    income = _income([(2016, 400), (2017, 500), (2018, 600), (2019, 700), (2020, 800),
                      (2021, 900), (2022, 950), (2023, 980), (2024, 990), (2025, 9999)],
                     margins=[10.0] * 10)
    series, _ = _fy_series(income, None)
    assert [lbl[:4] for lbl, _rev in _local_peaks(series)] == []


def test_an_endpoint_may_be_a_peak_against_its_single_interior_neighbour():
    from core.lifecycle import _fy_series, _local_peaks
    income = _income([(2016, 900), (2017, 500), (2018, 600), (2019, 400)],
                     margins=[10.0] * 4)
    series, _ = _fy_series(income, None)
    # 2016 qualifies against 2017 alone; 2018 qualifies against 2017 and 2019.
    assert [lbl[:4] for lbl, _rev in _local_peaks(series)] == ["2016", "2018"]


def test_the_guard_can_both_permit_and_refuse_so_it_is_not_vacuous():
    """THE PROPERTY EVERY EARLIER DEFINITION LACKED, asserted directly.

    L-1b's and L-1c's definitions were provably all-permit: whatever the data, a decline
    streak forced LOWER=True. This test fails if the guard ever becomes one-sided again,
    which is the failure mode that survived two rulings undetected.
    """
    rising = _income([(2016, 500), (2017, 600), (2018, 700), (2019, 650), (2020, 800),
                      (2021, 1000), (2022, 1200), (2023, 1100), (2024, 1000), (2025, 900)],
                     margins=[10.0] * 10)
    falling = _income([(2016, 500), (2017, 900), (2018, 1100), (2019, 700), (2020, 600),
                       (2021, 800), (2022, 900), (2023, 800), (2024, 700), (2025, 600)],
                      margins=[10.0] * 10)
    verdicts = {
        _legs(rising, "cyclical", dividends=PAYS_DIVIDEND)["cyclical_peak_to_peak"].value,
        _legs(falling, "cyclical", dividends=PAYS_DIVIDEND)["cyclical_peak_to_peak"].value,
    }
    assert verdicts == {True, False}, "the guard is one-sided again"


def test_with_no_decline_streak_the_guard_does_not_fire_and_is_not_absent():
    """Ruled: streak 0 -> the guard does not fire, because there is no decline to gate.
    It must NOT read as asserted-absent — nothing is missing, so nothing is incomplete.
    This is MU's live situation."""
    income = _income([(2016, 500), (2017, 600), (2018, 700), (2019, 650), (2020, 600),
                      (2021, 1000), (2022, 1100), (2023, 1000), (2024, 900), (2025, 1200)],
                     margins=[10.0] * 10)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    assert legs["decline_streak"].value == 0
    guard = legs["cyclical_peak_to_peak"]
    assert guard.present is True and guard.value is None
    assert "no decline streak to gate" in guard.detail
    r = classify("SYN", legs, "cyclical")
    assert r.stage != STAGE_DECLINE
    # The guard specifically must not appear as an absence. (Other legs may be absent here
    # — no share or sales-to-capital series was passed — so the row-level
    # INPUTS-INCOMPLETE flag is not the thing under test.)
    assert not any("cyclical_peak_to_peak" in e for e in r.absent_legs)


def test_a_streak_spanning_the_whole_window_yields_INPUTS_INCOMPLETE_not_a_verdict():
    """Ruled: if the streak covers the measured window there IS no prior peak — the
    earliest reading is the left edge of the window, not a cycle top. Say so, don't guess.
    """
    income = _income([(2016, 1600), (2017, 1500), (2018, 1400), (2019, 1300),
                      (2020, 1200), (2021, 1100), (2022, 1000), (2023, 900),
                      (2024, 800), (2025, 700)],
                     margins=[10.0] * 10)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    assert legs["decline_streak"].value == 9                      # every transition down
    guard = legs["cyclical_peak_to_peak"]
    assert guard.present is False
    assert "spans_measured_window_no_prior_peak" in guard.reason
    r = classify("SYN", legs, "cyclical")
    assert r.stage != STAGE_DECLINE, "DECLINE awarded with no prior peak to compare"
    assert FLAG_INPUTS_INCOMPLETE in r.flags


MU_FY2023_FCF = [("2020-09-03", 83e6), ("2021-09-02", 2438e6), ("2022-09-01", 3114e6),
                 ("2023-08-31", -6117e6)]


def test_MU_mid_downcycle_NO_LONGER_reads_YOUNG_and_reads_MATURE_instead():
    """ORDERED PIN 2a (L-1d). MU's own filed series truncated at FY2023 — the memory
    trough, revenue 30,758M -> 15,540M, operating margin -36.97%, FCF -6,117M.

    BEFORE L-1d this classified YOUNG: rule 2 had no cyclical guard, so a trough looked
    like pre-earnings. Now measured, every step shown rather than assumed:

      - streak 1, under the cyclical bar of 3            -> rule 1 blocked on the streak
      - peak-to-peak 2018 30,391M then 2022 30,758M, RISING -> guard REFUSES the permit too,
        so rule 1 is blocked twice, and this time the guard genuinely performed a check
      - rule 2's cyclical guard: earned in 2020, 2021 and 2022 (positive margin AND positive
        FCF) -> YOUNG BLOCKED, flag CYCLICAL-GUARD-HELD-OUT-OF-YOUNG
      - CAGR 2020->2023 is negative                      -> rule 3 cannot fire
      - therefore MATURE, on the residual.
    """
    rows = json.loads(Path("tests/fixtures/fmp/MU.json").read_text())["income_annual"]
    through_2023 = [r for r in sorted(rows, key=lambda x: x["date"])
                    if r["date"][:4] <= "2023"]
    legs = _legs(through_2023, "cyclical", dividends=PAYS_DIVIDEND, fcf=MU_FY2023_FCF)
    assert legs["fy_count"].value == 8                      # meets CYCLICAL_MIN_FY
    assert legs["decline_streak"].value == 1
    assert legs["cyclical_peak_to_peak"].value is False     # peaks RISING -> refuse
    assert legs["margin_sign"].value < 0                    # -36.97%, would have been YOUNG
    assert legs["cyclical_has_earned"].value is True
    r = classify("MU", legs, "cyclical")
    assert r.stage != STAGE_YOUNG
    assert r.stage == STAGE_MATURE
    assert r.rule_fired == "rule4_mature"
    assert FLAG_CYCLICAL_GUARD_HELD_YOUNG in r.flags


def test_a_genuinely_pre_earnings_cyclical_still_reaches_YOUNG():
    """ORDERED PIN 2b (L-1d). The guard must block troughs, NOT pre-earnings names. No FY
    in the window has both a positive operating margin and positive FCF, so nothing has
    been demonstrably earned and YOUNG is still correct."""
    income = _income([(2016, 10), (2017, 25), (2018, 60), (2019, 40), (2020, 90),
                      (2021, 150), (2022, 220), (2023, 180), (2024, 260), (2025, 300)],
                     margins=[-40.0, -35.0, -30.0, -50.0, -28.0,
                              -22.0, -18.0, -25.0, -12.0, -8.0])
    fcf = [(f"{y}-12-31", -5e6) for y in range(2016, 2026)]
    legs = _legs(income, "cyclical", dividends=[], fcf=fcf)
    assert legs["cyclical_has_earned"].value is False
    r = classify("SYN", legs, "cyclical")
    assert r.stage == STAGE_YOUNG
    assert r.rule_fired == "rule2_young"
    assert FLAG_YOUNG_UNCALIBRATED in r.flags
    assert FLAG_CYCLICAL_GUARD_HELD_YOUNG not in r.flags


def test_an_unevaluable_rule2_guard_FAILS_CLOSED_and_blocks_YOUNG():
    """ORDERED PIN (L-1e). FLIPPED: this previously asserted YOUNG stayed reachable when the
    guard could not evaluate — the R1 "a missing input never satisfies a condition" reading,
    applied to a condition that BLOCKS.

    RULED OTHERWISE, and the rationale is asymmetric on purpose: the exposure is
    trough-reads-YOUNG, so the protective direction WITHHOLDS YOUNG from a cyclical we
    cannot clear rather than granting it. A genuinely pre-earnings cyclical with no FCF
    series is a feed problem to fix, not a classification to guess.

    MU truncated at FY2023 with no FCF series: margin −36.97% would fire rule 2, and the
    guard cannot evaluate. YOUNG must be blocked anyway.
    """
    rows = json.loads(Path("tests/fixtures/fmp/MU.json").read_text())["income_annual"]
    through_2023 = [r for r in sorted(rows, key=lambda x: x["date"])
                    if r["date"][:4] <= "2023"]
    legs = _legs(through_2023, "cyclical", dividends=PAYS_DIVIDEND, fcf=None)
    assert legs["cyclical_has_earned"].present is False
    assert "cannot_establish_earnings" in legs["cyclical_has_earned"].reason
    assert legs["margin_sign"].value < 0
    r = classify("MU", legs, "cyclical")
    assert r.stage != STAGE_YOUNG
    assert FLAG_CYCLICAL_GUARD_HELD_YOUNG in r.flags
    assert FLAG_CYCLICAL_GUARD_UNEVALUABLE_FCF in r.flags


def test_a_cyclical_with_no_fcf_series_and_negative_margins_does_not_read_YOUNG():
    """The ordered pin, stated on synthetic data so it does not depend on MU's history."""
    income = _income([(2016, 100), (2017, 120), (2018, 140), (2019, 120), (2020, 100),
                      (2021, 130), (2022, 160), (2023, 140), (2024, 120), (2025, 100)],
                     margins=[-5.0] * 10)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND, fcf=None)
    r = classify("SYN", legs, "cyclical")
    assert r.stage != STAGE_YOUNG
    assert FLAG_CYCLICAL_GUARD_UNEVALUABLE_FCF in r.flags


def test_a_gap_in_the_revenue_window_REFUSES_the_peak_guard():
    """ORDERED PIN (L-1e). Contiguity is a PRECONDITION, not a semantic to define: a peak
    detected against a phantom neighbour is fabricated structure. A hole anywhere in the
    measured window refuses the permit — the same closed fail as fewer than two peaks — and
    the reason names the remedy as feed repair.

    Peaks are not even computed on a gapped series, so no invented structure reaches the
    calibration set.
    """
    # 2021 missing. Without the precondition, 2020 would read as a peak against 2022.
    income = _income([(2016, 500), (2017, 900), (2018, 1100), (2019, 700), (2020, 1200),
                      (2022, 900), (2023, 800), (2024, 700), (2025, 600)],
                     margins=[10.0] * 9)
    legs = _legs(income, "cyclical", dividends=PAYS_DIVIDEND)
    guard = legs["cyclical_peak_to_peak"]
    assert guard.present is True and guard.value is False
    assert "PEAK-GUARD-SERIES-GAP" in guard.detail
    assert "missing FY 2021" in guard.detail
    assert "repair the feed" in guard.detail
    assert legs["cyclical_peaks"].value == []
    assert "NOT COMPUTED" in legs["cyclical_peaks"].detail
    r = classify("SYN", legs, "cyclical")
    assert r.stage != STAGE_DECLINE
    # Gate-level refusal: the verdict is not voided, so no absence is claimed for the guard.
    assert not any("cyclical_peak_to_peak" in e for e in r.absent_legs)


def test_both_gates_deny_the_tag_they_guard_when_they_cannot_measure():
    """THE SYMMETRY, asserted directly: the peak gate denies DECLINE, the FCF gate denies
    YOUNG. Neither grants a tag it could not measure."""
    gapped = _income([(2016, 500), (2017, 900), (2018, 1100), (2019, 700), (2020, 1200),
                      (2022, 900), (2023, 800), (2024, 700), (2025, 600)],
                     margins=[10.0] * 9)
    assert classify("SYN", _legs(gapped, "cyclical", dividends=PAYS_DIVIDEND),
                    "cyclical").stage != STAGE_DECLINE

    no_fcf = _income([(2016, 100), (2017, 120), (2018, 140), (2019, 120), (2020, 100),
                      (2021, 130), (2022, 160), (2023, 140), (2024, 120), (2025, 100)],
                     margins=[-5.0] * 10)
    assert classify("SYN", _legs(no_fcf, "cyclical", dividends=PAYS_DIVIDEND, fcf=None),
                    "cyclical").stage != STAGE_YOUNG


def test_the_rule2_guard_does_not_apply_to_non_cyclical_lenses():
    """A non-cyclical name with a negative margin is YOUNG on rule 2 as before — the guard
    is scoped to the lens whose troughs motivated it."""
    income = _income([(2022, 100), (2023, 200), (2024, 400), (2025, 800)],
                     margins=[-30.0, -20.0, -10.0, -5.0])
    legs = _legs(income, "growth", dividends=[],
                 fcf=[("2023-12-31", 5e6), ("2024-12-31", 6e6), ("2025-12-31", 7e6)])
    assert legs["cyclical_has_earned"].value is None
    assert classify("SYN", legs, "growth").stage == STAGE_YOUNG


def test_the_streak_is_anchored_at_the_latest_fy_not_the_worst_run_anywhere():
    """R11: DECLINE is a current-state classification. Five down years followed by three
    up years is not a company in decline."""
    income = _income([(2018, 1000), (2019, 900), (2020, 800), (2021, 700), (2022, 600),
                      (2023, 700), (2024, 800), (2025, 900)],
                     margins=[10.0] * 8)
    legs = _legs(income, "compounder", dividends=PAYS_DIVIDEND)
    assert legs["decline_streak"].value == 0
    assert classify("SYN", legs, "compounder").stage != STAGE_DECLINE


# ── L-1c: the bank net-revenue basis ──────────────────────────────────────────

def _bank_rows(pairs, *, int_exp_share=0.35, margin=30.0, drop_interest_expense=False):
    """Bank-shaped FMP income rows: gross revenue plus the interest components.

    `int_exp_share` of gross revenue is interest expense, so net revenue is the remainder —
    the same shape as the real payload, where interestIncome/interestExpense/
    netInterestIncome all reconcile.
    """
    rows = []
    for year, gross in pairs:
        int_exp = gross * int_exp_share
        int_inc = gross * 0.70
        row = {"date": f"{year}-12-31", "revenue": gross,
               "operatingIncome": (gross - int_exp) * margin / 100.0,
               "interestIncome": int_inc,
               "netInterestIncome": int_inc - int_exp,
               "interestExpense": int_exp}
        if drop_interest_expense:
            del row["interestExpense"]
        rows.append(row)
    return rows


def test_a_bank_is_classified_on_net_revenue_never_gross():
    rows = _bank_rows([(2022, 100.0), (2023, 200.0), (2024, 260.0), (2025, 280.0)])
    legs = _legs(rows, "bank", dividends=PAYS_DIVIDEND)
    assert legs["revenue_basis"].value == "net_revenue"
    assert "revenue - interestExpense" in legs["revenue_basis"].detail
    # 65% of gross survives, so the CAGR is struck on 65 -> 182, not 100 -> 280.
    gross_cagr = (280.0 / 100.0) ** (1 / 3) - 1
    assert abs(legs["revenue_cagr"].value - gross_cagr) < 1e-9, (
        "the ratio is basis-invariant here by construction — see the JPM test for the "
        "case where the basis changes the verdict")


def test_a_non_bank_lens_keeps_the_gross_filed_revenue():
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    legs = _legs(income, "compounder", dividends=PAYS_DIVIDEND)
    assert legs["revenue_basis"].value == "gross_revenue"


def test_a_bank_with_missing_components_is_INPUTS_INCOMPLETE_and_never_falls_back():
    """Ruled: 'If the required components aren't all present: INPUTS-INCOMPLETE. Never fall
    back to gross.' The gross figure IS present on every row here — it must not be used."""
    rows = _bank_rows([(2022, 100.0), (2023, 200.0), (2024, 260.0), (2025, 280.0)],
                      drop_interest_expense=True)
    legs = _legs(rows, "bank", dividends=PAYS_DIVIDEND)
    basis = legs["revenue_basis"]
    assert basis.present is False
    assert "bank_net_revenue_uncomputable" in basis.reason
    assert legs["fy_count"].value == 0, "a row was kept on the gross basis"
    r = classify("BANKX", legs, "bank")
    assert FLAG_INPUTS_INCOMPLETE in r.flags
    assert any("revenue_basis" in e for e in r.absent_legs)


def test_a_bank_whose_two_net_revenue_formulas_disagree_refuses_the_row():
    """WITHHOLD, never pick a side (the G-2 corroboration precedent). The identity
    interestIncome - interestExpense == netInterestIncome is checked, not assumed."""
    rows = _bank_rows([(2022, 100.0), (2023, 200.0), (2024, 260.0), (2025, 280.0)])
    rows[-1]["netInterestIncome"] = rows[-1]["netInterestIncome"] * 1.5   # vendor drift
    legs = _legs(rows, "bank", dividends=PAYS_DIVIDEND)
    assert legs["revenue_basis"].present is False
    assert "formulas_disagree" in legs["revenue_basis"].reason


def test_JPM_with_its_dividend_suspended_does_NOT_classify_HIGROWTH():
    """THE POINT OF THE FIX, on JPM's real filed income series.

    On the GROSS basis JPM's 3y revenue CAGR is 22.06% — the rate cycle, not growth — and
    with the dividend suspended (measured [] = pays none) rule 3's legs all passed and JPM
    classified HIGROWTH. A bank cutting its dividend in a crisis, tagged high growth, one
    input away. On the ruled net-revenue basis the CAGR falls under the 15% bar and the
    rule cannot fire.
    """
    rows = json.loads(Path("tests/fixtures/fmp/JPM.json").read_text())["income_annual"]
    legs = _legs(rows, "bank", dividends=[])            # dividend SUSPENDED
    r = classify("JPM", legs, "bank")
    assert legs["revenue_basis"].value == "net_revenue"
    assert legs["revenue_cagr"].value < HIGROWTH_MIN_CAGR, (
        f"net-basis CAGR {legs['revenue_cagr'].value:.4f} still clears the HIGROWTH bar")
    assert r.stage != STAGE_HIGROWTH
    assert r.stage == STAGE_MATURE


def test_every_calibration_bank_reads_under_the_higrowth_bar_on_the_net_basis():
    """All four read 16-27%/y on gross. If any still clears 15% on the net basis, the fix
    is incomplete and this test says which."""
    for t in ("JPM", "BK", "USB", "C"):
        rows = json.loads(Path(f"tests/fixtures/fmp/{t}.json").read_text())["income_annual"]
        legs = _legs(rows, "bank", dividends=PAYS_DIVIDEND)
        assert legs["revenue_basis"].value == "net_revenue"
        assert legs["revenue_cagr"].present
        assert legs["revenue_cagr"].value < HIGROWTH_MIN_CAGR, (
            f"{t}: net-basis CAGR {legs['revenue_cagr'].value*100:.2f}% clears the bar")


def test_the_bank_margin_shares_the_net_basis():
    """An operating margin struck on gross interest income is not a margin anyone uses,
    and it would drift with rates exactly as the revenue leg did."""
    rows = _bank_rows([(2022, 100.0), (2023, 110.0), (2024, 120.0), (2025, 130.0)],
                      margin=30.0)
    legs = _legs(rows, "bank", dividends=PAYS_DIVIDEND)
    assert abs(legs["margin_sign"].value - 30.0) < 1e-6, (
        "margin was struck on gross revenue, not on the net basis")


def test_flags_never_repeat_themselves():
    """INPUTS-INCOMPLETE can now be raised by the basis check AND by a rule's absent legs.
    A duplicated flag reads like two findings."""
    rows = _bank_rows([(2022, 100.0), (2023, 200.0), (2024, 260.0), (2025, 280.0)],
                      drop_interest_expense=True)
    r = classify("BANKX", _legs(rows, "bank", dividends=None), "bank")
    assert len(r.flags) == len(set(r.flags))


# ── R7: the margin flat band ──────────────────────────────────────────────────

def test_the_flat_band_is_inclusive_of_flat_and_down_only():
    """'flat/down' == delta <= +100bp. A rising margin fails the leg."""
    down = _income([(2022, 1000), (2023, 950), (2024, 900), (2025, 850)],
                   margins=[20.0, 20.0, 20.0, 20.5])       # +50bp -> inside the band
    up = _income([(2022, 1000), (2023, 950), (2024, 900), (2025, 850)],
                 margins=[20.0, 20.0, 20.0, 22.0])         # +200bp -> outside
    assert classify("SYN", _legs(down, "compounder", dividends=PAYS_DIVIDEND),
                    "compounder").stage == STAGE_DECLINE
    r_up = classify("SYN", _legs(up, "compounder", dividends=PAYS_DIVIDEND), "compounder")
    assert r_up.stage != STAGE_DECLINE
    assert _outcomes(r_up, "rule1_decline")["margin_trend_bp"] == "not_satisfied"
    assert MARGIN_FLAT_BAND_BP == 100.0


# ── R5 + G-4: the dividend / capital-returns contract ─────────────────────────

def test_dividends_None_is_UNKNOWN_and_empty_is_PAYS_NONE():
    """THE G-4 CONTRACT. Collapsing these pushes a name toward DECLINE (rule 1's returns
    leg) or HIGROWTH (rule 3's 'returns absent') on evidence never gathered."""
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    unknown = _legs(income, "compounder", dividends=None)
    pays_none = _legs(income, "compounder", dividends=[])
    assert unknown["pays_dividend"].present is False
    assert unknown["pays_dividend"].reason == "dividend_fetch_unknown"
    assert pays_none["pays_dividend"].present is True
    assert pays_none["pays_dividend"].value is False


def test_capital_returns_is_absent_only_when_BOTH_witnesses_are_absent():
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    both = _legs(income, "compounder", dividends=None, shares=None)
    assert both["capital_returns"].present is False
    # One witness present is enough to evaluate the leg.
    one = _legs(income, "compounder", dividends=None,
                shares=[("2022-12-31", 100.0), ("2025-12-31", 90.0)])
    assert one["capital_returns"].present is True
    assert one["capital_returns"].value is True             # 10% net reduction


def test_a_de_minimis_share_change_is_not_a_capital_return():
    """Option issuance netting against small repurchases must not read as a buyback."""
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    legs = _legs(income, "compounder", dividends=[],
                 shares=[("2022-12-31", 100.0), ("2025-12-31", 99.7)])   # 0.3%
    assert legs["net_buyback"].value is False
    assert BUYBACK_DE_MINIMIS_NET_REDUCTION == 0.01


def test_fetch_dividends_returns_None_when_the_fixture_predates_the_key(tmp_path):
    from adapters.fmp_adapter import fetch_dividends
    fix = tmp_path / "X.json"
    fix.write_text(json.dumps({"profile": []}), encoding="utf-8")
    assert fetch_dividends("X", fixture_path=fix) is None       # UNKNOWN, never []


def test_fetch_dividends_reads_an_empty_recorded_list_as_pays_none(tmp_path):
    from adapters.fmp_adapter import fetch_dividends
    fix = tmp_path / "X.json"
    fix.write_text(json.dumps({"dividends": []}), encoding="utf-8")
    assert fetch_dividends("X", fixture_path=fix) == []          # PAYS NONE


def test_fetch_dividends_degrades_a_live_failure_to_UNKNOWN_never_to_empty(monkeypatch):
    import adapters.fmp_adapter as fmp

    def boom(*a, **k):
        raise RuntimeError("502 from vendor")

    monkeypatch.setattr(fmp, "_get", boom)
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr(fmp, "_DIVIDENDS_CACHE", {})
    assert fmp.fetch_dividends("ZZZZ") is None


# ── R6: the reinvestment bar ──────────────────────────────────────────────────

def test_lower_sales_to_capital_means_HEAVIER_reinvestment():
    """The direction is inverted relative to naive reading and it decides rule 3."""
    income = _income([(2022, 1000), (2023, 1200), (2024, 1400), (2025, 1600)],
                     margins=[5.0] * 4)
    heavy = _legs(income, "growth", dividends=[],
                  stc=[("2024-12-31", 1.0), ("2025-12-31", 0.6)])
    light = _legs(income, "growth", dividends=[],
                  stc=[("2024-12-31", 3.0), ("2025-12-31", 2.7)])
    assert heavy["reinvestment_heavy"].value is True
    assert light["reinvestment_heavy"].value is False
    assert REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL == 1.50


def test_every_reading_that_consults_the_uncalibrated_bar_declares_it():
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    r = classify("SYN", _legs(income, "compounder", dividends=PAYS_DIVIDEND,
                              stc=[("2024-12-31", 1.0), ("2025-12-31", 1.0)]),
                 "compounder")
    assert FLAG_REINVEST_UNCALIBRATED in r.flags


# ── §5.2 lens compatibility — FLAGS ONLY, never a reassignment ────────────────

@pytest.mark.parametrize("stage,lens", [
    (STAGE_YOUNG, "compounder"),
    (STAGE_DECLINE, "growth"),
    (STAGE_MATURE, "growth"),
])
def test_incompatible_stage_lens_pairs_are_flagged(stage, lens):
    flags = lens_compatibility_flags(stage, lens)
    assert len(flags) == 1 and flags[0].startswith(FLAG_LENS_INCOMPAT)


@pytest.mark.parametrize("stage", [STAGE_YOUNG, STAGE_HIGROWTH, STAGE_MATURE,
                                   STAGE_DECLINE])
def test_the_bank_lens_is_exempt_from_every_stage_check(stage):
    assert lens_compatibility_flags(stage, "bank") == []


def test_compatible_pairs_are_silent():
    assert lens_compatibility_flags(STAGE_HIGROWTH, "growth") == []
    assert lens_compatibility_flags(STAGE_MATURE, "compounder") == []


def test_the_compatibility_check_returns_flags_and_nothing_else():
    """§8: compatibility checks flag, NEVER reassign. The function's only output is a list
    of strings — it has no access to a lens to change."""
    out = lens_compatibility_flags(STAGE_YOUNG, "compounder")
    assert isinstance(out, list) and all(isinstance(f, str) for f in out)


# ── §7: override guards ───────────────────────────────────────────────────────

def test_an_override_without_a_rationale_is_refused(tmp_path):
    db = tmp_path / "l.db"
    init_db(db)
    for bad in (None, "", "   ", "\n\t"):
        with pytest.raises(OverrideRationaleMissing):
            save_lifecycle_override("WU", STAGE_DECLINE, STAGE_MATURE, bad, db_path=db)


def test_a_refused_override_writes_nothing(tmp_path):
    """A refusal that has already written something is not a refusal."""
    db = tmp_path / "l.db"
    init_db(db)
    with pytest.raises(OverrideRationaleMissing):
        save_lifecycle_override("WU", STAGE_DECLINE, STAGE_MATURE, "", db_path=db)
    assert get_standing_override("WU", db_path=db) is None


def test_an_override_with_a_rationale_is_recorded_and_stands(tmp_path):
    db = tmp_path / "l.db"
    init_db(db)
    save_lifecycle_override("WU", STAGE_DECLINE, STAGE_MATURE,
                            "secular decline read is premature; 2025 margin turned up",
                            db_path=db)
    standing = get_standing_override("WU", db_path=db)
    assert standing["approved_stage"] == STAGE_MATURE
    assert standing["rationale_text"].startswith("secular decline")


def test_a_superseding_override_appends_and_leaves_the_trail(tmp_path):
    db = tmp_path / "l.db"
    init_db(db)
    save_lifecycle_override("WU", STAGE_DECLINE, STAGE_MATURE, "first call", db_path=db)
    save_lifecycle_override("WU", STAGE_DECLINE, STAGE_DECLINE, "reversed on new data",
                            db_path=db)
    assert get_standing_override("WU", db_path=db)["rationale_text"] == \
        "reversed on new data"
    import sqlite3
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM lifecycle_overrides").fetchone()[0] == 2
    conn.close()


# ── §4 / §6: persistence, transitions, and no silent reclassification ─────────

def _result(ticker, stage, rule="rule4_mature"):
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    r = classify(ticker, _legs(income, "compounder", dividends=PAYS_DIVIDEND),
                 "compounder")
    r.stage = stage
    r.rule_fired = rule
    return r


def test_a_first_classification_is_not_a_transition(tmp_path):
    db = tmp_path / "l.db"
    init_db(db)
    stage_id, transition_id = save_lifecycle_stage(_result("MU", STAGE_MATURE), db_path=db)
    assert stage_id and transition_id is None
    assert list_lifecycle_transitions(db_path=db) == []


def test_an_unchanged_stage_writes_no_transition(tmp_path):
    db = tmp_path / "l.db"
    init_db(db)
    save_lifecycle_stage(_result("MU", STAGE_MATURE), db_path=db)
    _, transition_id = save_lifecycle_stage(_result("MU", STAGE_MATURE), db_path=db)
    assert transition_id is None
    assert len(list_lifecycle_stages("MU", db_path=db)) == 2       # append-only


def test_a_changed_stage_writes_a_transition_row(tmp_path):
    db = tmp_path / "l.db"
    init_db(db)
    save_lifecycle_stage(_result("WU", STAGE_MATURE), db_path=db)
    _, transition_id = save_lifecycle_stage(_result("WU", STAGE_DECLINE), db_path=db)
    assert transition_id
    t = list_lifecycle_transitions(db_path=db)[0]
    assert (t["from_stage"], t["to_stage"]) == (STAGE_MATURE, STAGE_DECLINE)
    assert t["overridden"] == 0 and t["standing_override"] is None


def test_an_overridden_name_is_NEVER_silently_reclassified(tmp_path):
    """§4. The new computation is still recorded — suppressing it would hide the drift the
    re-review trigger exists to surface — and the transition says the override stands."""
    db = tmp_path / "l.db"
    init_db(db)
    save_lifecycle_stage(_result("WU", STAGE_MATURE), db_path=db)
    save_lifecycle_override("WU", STAGE_MATURE, STAGE_MATURE,
                            "hold MATURE pending a full-cycle read", db_path=db)
    save_lifecycle_stage(_result("WU", STAGE_DECLINE), db_path=db)
    t = list_lifecycle_transitions(db_path=db)[0]
    assert t["overridden"] == 1
    assert t["standing_override"] == STAGE_MATURE
    rows = list_lifecycle_stages("WU", db_path=db)
    assert [r["computed_stage"] for r in rows] == [STAGE_DECLINE, STAGE_MATURE]


def test_the_stage_row_carries_the_absence_record_and_the_config_version(tmp_path):
    db = tmp_path / "l.db"
    init_db(db)
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    r = classify("V", _legs(income, "compounder", dividends=None, shares=None), "compounder")
    save_lifecycle_stage(r, db_path=db)
    row = list_lifecycle_stages("V", latest_only=True, db_path=db)[0]
    assert row["inputs_incomplete"] == 1
    assert "capital_returns" in row["absent_legs"]
    assert row["config_version"] == LIFECYCLE_CONFIG_VERSION
    assert json.loads(row["assertions_json"])                 # per-point trail persisted


def test_a_fully_measured_row_records_no_absence(tmp_path):
    db = tmp_path / "l.db"
    init_db(db)
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    r = classify("MU", _legs(income, "compounder", dividends=PAYS_DIVIDEND,
                             shares=[("2022-12-31", 100.0), ("2025-12-31", 99.9)],
                             fcf=[("2023-12-31", 5.0), ("2024-12-31", 6.0),
                                  ("2025-12-31", 7.0)],
                             stc=[("2024-12-31", 2.0), ("2025-12-31", 2.1)]), "compounder")
    save_lifecycle_stage(r, db_path=db)
    row = list_lifecycle_stages("MU", latest_only=True, db_path=db)[0]
    assert row["inputs_incomplete"] == 0 and row["absent_legs"] is None


# ── §5: everything stage-conditioned is DARK in this phase ───────────────────

def test_the_b2_tolerance_table_covers_every_stage_and_matches_the_ruling():
    assert set(B2_DIVERGENCE_TOLERANCE_BY_STAGE) == {STAGE_YOUNG, STAGE_HIGROWTH,
                                                     STAGE_MATURE, STAGE_DECLINE}
    assert B2_DIVERGENCE_TOLERANCE_BY_STAGE == {"YOUNG": 0.30, "HIGROWTH": 0.20,
                                                "MATURE": 0.15, "DECLINE": 0.15}


def test_the_b2_guard_still_reads_its_own_unconditioned_threshold():
    """§5.1 IS NOT ARMED. The live guard must still be the flat 15%, and it must not have
    grown a dependency on the stage table. This test flips when §5.1 arms."""
    import synthesis.schema as schema
    src = Path("synthesis/schema.py").read_text(encoding="utf-8")
    assert schema.ANCHOR_DIVERGENCE_THRESHOLD == 0.15
    assert "lifecycle" not in src.lower()


def test_mature_is_the_tightest_and_young_the_widest_prior():
    """The ordering is the only claim this phase makes; the multipliers are M's."""
    assert M_WIDTH_PRIOR_ORDERING[0] == STAGE_MATURE
    assert M_WIDTH_PRIOR_ORDERING[-1] == STAGE_YOUNG


# ── DARK-SURFACE PINS — ONE PER FILE, DELIBERATELY (ruled L-2a step 0) ────────
# These were ONE test looping over five files. Arming §5 step 1 touches evaluate.py, which
# would have meant deleting or editing the single pin and RETIRING THE PROTECTION ON THE
# OTHER FOUR IN THE SAME STROKE — the 2026-08-15 eleven-test silent-dependency shape, where
# a check was lost as a side effect of a change that only needed part of it.
# Split, each arming step flips exactly one assertion and the rest keep failing loudly.

def _assert_dark(path: str) -> None:
    src = Path(path).read_text(encoding="utf-8")
    assert "core.lifecycle" not in src, f"{path} imports the classifier — L is DARK here"
    assert "lifecycle_stage" not in src, f"{path} reads the stage table — L is DARK here"


def test_pillars_does_not_read_the_classifier():
    """Scoring must never consult a stage. This pin outlives every §5 step."""
    _assert_dark("core/pillars.py")


def test_valuation_anchors_does_not_read_the_classifier():
    _assert_dark("core/valuation_anchors.py")


def test_batch_runner_does_not_read_the_classifier():
    """The batch path stays dark until its own arming order — step 1 is evaluate.py ONLY."""
    _assert_dark("batch/runner.py")


def test_synthesis_schema_does_not_read_the_classifier():
    """Flips only when §5.1's stage-conditioned B-2 tolerances arm (step 3)."""
    _assert_dark("synthesis/schema.py")


def test_evaluate_does_not_read_the_classifier_yet():
    """THE ONE PIN §5 STEP 1 IS EXPECTED TO FLIP. It is separate from the other four
    precisely so that flipping it costs exactly one assertion."""
    _assert_dark("evaluate.py")


def test_save_lifecycle_stage_refuses_to_default_its_destination():
    """A writer that falls back to production caliber.db when an argument is forgotten is
    the exact failure mode the interactive path creates. db_path is required and
    keyword-only."""
    import inspect
    sig = inspect.signature(save_lifecycle_stage)
    p = sig.parameters["db_path"]
    assert p.default is inspect.Parameter.empty, "db_path grew a default again"
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        save_lifecycle_stage(_result("MU", STAGE_MATURE))       # type: ignore[call-arg]


def test_the_config_version_is_stamped_and_non_empty():
    """A stage read six months from now must answer which thresholds produced it."""
    assert LIFECYCLE_CONFIG_VERSION and LIFECYCLE_CONFIG_VERSION.startswith("L-v")
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    r = classify("SYN", _legs(income, "compounder", dividends=PAYS_DIVIDEND), "compounder")
    assert r.config_version == LIFECYCLE_CONFIG_VERSION


def test_every_consulted_leg_leaves_a_per_point_assertion():
    """Order §2: 'every classification decision carries per-point assertions — which
    input, which value, which rule fired.'"""
    income = _income([(2022, 1000), (2023, 1050), (2024, 1100), (2025, 1150)],
                     margins=[10.0] * 4)
    r = classify("SYN", _legs(income, "compounder", dividends=PAYS_DIVIDEND), "compounder")
    assert r.assertions
    for a in r.assertions:
        assert a.rule and a.leg and a.outcome in {"satisfied", "not_satisfied", "absent"}
        assert a.detail, f"{a.leg} left an assertion with no measurement"


def test_the_classifier_is_pure_and_does_no_io():
    """classify() takes assembled legs and returns a result. No fetches, no writes — the
    probe and the storage layer are the only I/O, and they are separate on purpose."""
    import inspect
    src = inspect.getsource(classify)
    for forbidden in ("requests", "sqlite3", "open(", "fetch_", "save_"):
        assert forbidden not in src
