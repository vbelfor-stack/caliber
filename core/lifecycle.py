"""Phase L — lifecycle stage classification (order docs/orders/2026-08-16-phase-l-*.md).

A SECOND CLASSIFICATION AXIS, orthogonal to the Phase D valuation lens. Stage is
classified from FUNDAMENTALS ONLY — never from age-since-IPO and never from market cap.

    YOUNG | HIGROWTH | MATURE | DECLINE

Four stages, a collapse of Damodaran's six (Start-Up + Young Growth merged; Mature Growth
+ Mature Stable merged). Damodaran's model informed the rule STRUCTURE; the thresholds are
ours and live in core/lifecycle_config.

DARK IN THIS PHASE. Nothing here is consumed by a score, a confidence label, a lens or an
E(R). The stage-conditioned behaviours (§5) arm separately, one at a time.

────────────────────────────────────────────────────────────────────────────────
THE TWO IDEAS THAT DECIDE EVERY EDGE CASE IN THIS FILE
────────────────────────────────────────────────────────────────────────────────
1. ASSERTED-ABSENT (R1). A missing input is never a zero, never a False and never a
   default. It is stamped absent WITH A REASON, it never satisfies a rule condition, and
   any classification made with a leg absent carries `inputs_incomplete` naming which legs
   were missing. Absence is visible in the stage table, never silent.

2. AND-PRECEDENCE (R7), AND ITS ONE DOCUMENTED ASYMMETRY.
   R7: "a leg that is asserted-absent means the rule CANNOT fire — a classification as
   consequential as DECLINE is never awarded on partial evidence."
   R7 also: "R1's remaining-legs mechanics apply only to inputs with no compliant source
   after R4/R5/R7 (currently: FCF for V/banks, reinvestment for NOW, dividends if the
   endpoint fails)."
   R6, explicitly: "NOW's single-point series -> reinvestment asserted-absent per R1;
   rule 3 evaluates on CAGR + capital-returns legs."

   Those pull in opposite directions for an AND-rule with a structurally-absent leg, so
   the reconciliation is stated here rather than left to the reader:

     DECLINE (rule 1)  — STRICT. Any absent leg and the rule cannot fire. This is the
                         reading R7 justifies by name, on consequence.
     HIGROWTH (rule 3) — REMAINING-LEGS, but ONLY for the three inputs R7 names as
                         structurally sourceless. R6 states this outcome directly and it
                         is what makes NOW classify HIGROWTH.

   Every remaining-legs classification is stamped `inputs_incomplete`, so the weaker
   evidential basis travels with the row instead of being inferred from it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.lifecycle_config import (
    BANK_LENS,
    BANK_NET_REVENUE_CROSSCHECK_TOL,
    BANK_NET_REVENUE_FORMULA,
    BUYBACK_DE_MINIMIS_NET_REDUCTION,
    CAGR_WINDOW_YEARS,
    CYCLICAL_MIN_FY,
    DECLINE_MIN_STREAK_YEARS,
    DECLINE_MIN_STREAK_YEARS_CYCLICAL,
    HIGROWTH_MIN_CAGR,
    LIFECYCLE_CONFIG_VERSION,
    MARGIN_FLAT_BAND_BP,
    MIN_FY_FOR_CLASSIFICATION,
    REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL,
    TREND_WINDOW_YEARS,
)

STAGE_YOUNG = "YOUNG"
STAGE_HIGROWTH = "HIGROWTH"
STAGE_MATURE = "MATURE"
STAGE_DECLINE = "DECLINE"
STAGES = (STAGE_YOUNG, STAGE_HIGROWTH, STAGE_MATURE, STAGE_DECLINE)

# Flags
FLAG_INPUTS_INCOMPLETE = "INPUTS-INCOMPLETE"
FLAG_INSUFFICIENT_HISTORY = "INSUFFICIENT-HISTORY"
FLAG_CYCLICAL_GUARD_HELD = "CYCLICAL-GUARD-HELD-OUT-OF-DECLINE"
FLAG_CYCLICAL_GUARD_HELD_YOUNG = "CYCLICAL-GUARD-HELD-OUT-OF-YOUNG"
FLAG_GUARD_TOLERANCE_UNCALIBRATED = "GUARD-TOLERANCE-UNCALIBRATED"
FLAG_CYCLICAL_GUARD_BLIND = "CYCLICAL-GUARD-BLIND-WINDOW-TOO-SHORT"
FLAG_REINVEST_UNCALIBRATED = "REINVESTMENT-THRESHOLD-UNCALIBRATED"
FLAG_YOUNG_UNCALIBRATED = "YOUNG-UNCALIBRATED"
FLAG_LENS_INCOMPAT = "LENS-STAGE-INCOMPATIBLE"


# ── Inputs ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Leg:
    """One classifier input. `present=False` means ASSERTED-ABSENT, never False-y data."""
    name: str
    value: Any = None
    present: bool = True
    reason: Optional[str] = None      # set IFF present is False
    detail: Optional[str] = None      # human-readable measurement, always populated

    def __post_init__(self) -> None:
        if self.present and self.reason is not None:
            raise ValueError(f"{self.name}: reason is for absent legs only")
        if not self.present and not self.reason:
            raise ValueError(f"{self.name}: an absent leg MUST carry a reason")

    @staticmethod
    def absent(name: str, reason: str) -> "Leg":
        return Leg(name=name, value=None, present=False, reason=reason,
                   detail=f"asserted-absent ({reason})")


@dataclass
class Assertion:
    """Per-point audit record: which input, which value, which rule, what it decided."""
    rule: str
    leg: str
    outcome: str          # 'satisfied' | 'not_satisfied' | 'absent'
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "leg": self.leg,
                "outcome": self.outcome, "detail": self.detail}


@dataclass
class StageResult:
    ticker: str
    stage: str
    rule_fired: str
    lens: Optional[str]
    assertions: List[Assertion] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    absent_legs: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    config_version: str = LIFECYCLE_CONFIG_VERSION

    @property
    def inputs_incomplete(self) -> bool:
        return bool(self.absent_legs)


# ── Input assembly ───────────────────────────────────────────────────────────

def _revenue_on_basis(row: Dict, lens: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """(revenue_on_the_basis_this_lens_requires, refusal_reason).

    NON-BANK: the filed `revenue`, as before.

    BANK (L-1c ruling): NET revenue, `revenue - interestExpense`. FMP's bank `revenue` is
    gross of interest expense and therefore tracks the rate cycle rather than the
    business — see core/lifecycle_config for the measured case. The published
    netInterestIncome identity is CHECKED, not assumed, and a disagreement REFUSES the row
    instead of picking a side. **There is no gross fallback**: refusing is the ruling.
    """
    rev = row.get("revenue")
    try:
        rev = None if rev in (None, 0) else float(rev)
    except (TypeError, ValueError):
        rev = None
    if rev is None:
        return None, "no_revenue"
    if lens != BANK_LENS:
        return rev, None

    ie = row.get("interestExpense")
    try:
        ie = None if ie is None else float(ie)
    except (TypeError, ValueError):
        ie = None
    if ie is None:
        return None, "bank_net_revenue_components_missing"
    net = rev - ie

    ii, nii = row.get("interestIncome"), row.get("netInterestIncome")
    if ii is not None and nii is not None:
        try:
            alt = float(nii) + (rev - float(ii))
        except (TypeError, ValueError):
            alt = None
        if alt is not None and abs(alt - net) > BANK_NET_REVENUE_CROSSCHECK_TOL * max(
                abs(net), 1.0):
            return None, "bank_net_revenue_formulas_disagree"
    if net <= 0:
        return None, "non_positive_net_revenue"
    return net, None


def _fy_series(income_annual: Sequence[Dict], lens: Optional[str] = None
               ) -> Tuple[List[Tuple[str, float, Optional[float]]], List[str]]:
    """([(fy_label, revenue, operating_margin_pct)] OLDEST FIRST, [refused_row_notes]).

    Rows lacking a usable revenue are DROPPED, not zero-filled — a zero revenue would
    manufacture a 100% decline. A dropped row leaves a HOLE, and holes break streaks
    rather than spanning them (R4).

    THE MARGIN SHARES THE BASIS. For a bank the denominator is net revenue, because an
    operating margin struck on gross interest income is not a margin anyone uses and would
    drift with rates exactly as the revenue leg did.
    """
    out: List[Tuple[str, float, Optional[float]]] = []
    refused: List[str] = []
    for row in income_annual or []:
        date = str(row.get("date", ""))[:10]
        rev, reason = _revenue_on_basis(row, lens)
        if not date:
            continue
        if rev is None:
            refused.append(f"{date[:4]}:{reason}")
            continue
        oi = row.get("operatingIncome")
        margin = None
        if oi is not None:
            try:
                margin = float(oi) / rev * 100.0
            except (TypeError, ValueError, ZeroDivisionError):
                margin = None
        out.append((date, rev, margin))
    out.sort(key=lambda r: r[0])
    return out, refused


def _fy_year(label: str) -> int:
    return int(label[:4])


def _decline_streak(series: Sequence[Tuple[str, float, Optional[float]]]) -> int:
    """Consecutive declining fiscal years ENDING AT THE MOST RECENT one.

    Anchored at the latest FY on purpose: DECLINE is a current-state classification (R11).
    A company that fell for five years and has grown for three is not in decline, and a
    max-streak-anywhere reading would say it was.

    A CALENDAR GAP BREAKS THE STREAK (R4): consecutive means consecutive in fiscal years,
    not merely adjacent in a list with a hole in it. A gap never extends or manufactures a
    decline.
    """
    if len(series) < 2:
        return 0
    streak = 0
    for i in range(len(series) - 1, 0, -1):
        cur_label, cur_rev, _ = series[i]
        prev_label, prev_rev, _ = series[i - 1]
        if _fy_year(cur_label) - _fy_year(prev_label) != 1:
            break                       # hole — stop, do not span it
        if cur_rev < prev_rev:
            streak += 1
        else:
            break
    return streak


def _local_peaks(series: Sequence[Tuple[str, float, Optional[float]]]
                 ) -> List[Tuple[str, float]]:
    """[(fy_label, revenue)] of LOCAL PEAKS, oldest first (L-1d ruled definition).

    A local peak is an FY whose revenue exceeds BOTH adjacent FYs. Window ENDPOINTS may
    qualify against their single interior neighbour — EXCEPT THE LATEST FY, WHICH CAN NEVER
    BE A PEAK: its right-hand neighbour does not exist yet, so calling it a peak would be
    asserting the cycle has topped when the next reading is what decides that.

    DOCUMENTED LIMITATION: adjacency here is adjacency IN THE MEASURED SERIES. If a fiscal
    year is missing, the neighbour used is the nearest measured one, which is not a
    year-adjacent FY. No gap exists in FMP `income_annual` for any of the nine tickers
    (FY2016-2025 contiguous, measured at L-1a), so this is latent — recorded rather than
    resolved, because inventing gap semantics for peak detection is a ruling, not a detail.
    """
    peaks: List[Tuple[str, float]] = []
    n = len(series)
    for i in range(n - 1):                      # the latest FY is never a peak
        rev = series[i][1]
        right = series[i + 1][1]
        left = series[i - 1][1] if i > 0 else None
        if rev > right and (left is None or rev > left):
            peaks.append((series[i][0], rev))
    return peaks


def _window(series: Sequence[Tuple[str, float, Optional[float]]], years: int):
    """(earliest_row, latest_row) spanning exactly `years` fiscal years, or None.

    Requires BOTH ENDPOINTS PRESENT and exactly `years` apart (R9). A window whose
    earliest endpoint is missing is asserted-absent, never silently shortened — a 2y CAGR
    reported as a 3y CAGR is a wrong number wearing a right label.
    """
    if not series:
        return None
    latest = series[-1]
    target = _fy_year(latest[0]) - years
    for row in series:
        if _fy_year(row[0]) == target:
            return row, latest
    return None


def _cagr(earliest_rev: float, latest_rev: float, years: int) -> Optional[float]:
    if earliest_rev <= 0 or latest_rev <= 0 or years <= 0:
        return None
    return (latest_rev / earliest_rev) ** (1.0 / years) - 1.0


def build_legs(
    ticker: str,
    income_annual: Sequence[Dict],
    lens: Optional[str],
    *,
    dividends: Optional[Sequence[Dict]],
    shares_series: Optional[Sequence[Tuple[str, float]]],
    fcf_fy: Optional[Sequence[Tuple[str, Optional[float]]]],
    sales_to_capital_fy: Optional[Sequence[Tuple[str, Optional[float]]]],
) -> Dict[str, Leg]:
    """Assemble every classifier leg, each either measured or asserted-absent with a reason.

    `dividends` and `shares_series` follow the G-4 contract: None means UNKNOWN, an empty
    sequence means the real answer is "none".
    """
    legs: Dict[str, Leg] = {}
    series, refused = _fy_series(income_annual, lens)
    n = len(series)

    legs["fy_count"] = Leg("fy_count", n, detail=f"{n} usable fiscal years")

    # ── which revenue basis this classification stands on (L-1c) ──────────────
    # Recorded as a leg so the basis travels with the row. A bank classified on net
    # revenue and one classified on gross are not the same measurement, and after the
    # L-1c ruling the gross one is not a permitted measurement at all.
    if lens == BANK_LENS:
        if refused:
            legs["revenue_basis"] = Leg.absent(
                "revenue_basis",
                f"bank_net_revenue_uncomputable[{';'.join(refused)}]")
        else:
            legs["revenue_basis"] = Leg(
                "revenue_basis", "net_revenue",
                detail=f"net_revenue ({BANK_NET_REVENUE_FORMULA}) — bank lens, "
                       f"{n} FY on basis")
    else:
        legs["revenue_basis"] = Leg(
            "revenue_basis", "gross_revenue",
            detail=f"gross_revenue (as filed) — lens={lens}"
                   + (f"; {len(refused)} row(s) unusable: {';'.join(refused)}"
                      if refused else ""))

    # ── revenue trend ────────────────────────────────────────────────────────
    if n < 2:
        legs["decline_streak"] = Leg.absent("decline_streak", "history_under_2_fy")
    else:
        streak = _decline_streak(series)
        legs["decline_streak"] = Leg(
            "decline_streak", streak,
            detail=f"{streak} consecutive declining FY ending {series[-1][0]}")

    # ── 3y revenue CAGR ──────────────────────────────────────────────────────
    win = _window(series, CAGR_WINDOW_YEARS)
    if win is None:
        legs["revenue_cagr"] = Leg.absent(
            "revenue_cagr", f"no_fy_exactly_{CAGR_WINDOW_YEARS}y_before_latest")
    else:
        (e_label, e_rev, _), (l_label, l_rev, _) = win
        c = _cagr(e_rev, l_rev, CAGR_WINDOW_YEARS)
        if c is None:
            legs["revenue_cagr"] = Leg.absent("revenue_cagr", "non_positive_revenue")
        else:
            legs["revenue_cagr"] = Leg(
                "revenue_cagr", c,
                detail=f"{c*100:.2f}%/y {e_label}->{l_label} "
                       f"({e_rev:,.0f} -> {l_rev:,.0f})")

    # ── operating-margin trend and sign (R7) ─────────────────────────────────
    twin = _window(series, TREND_WINDOW_YEARS)
    if twin is None:
        legs["margin_trend_bp"] = Leg.absent(
            "margin_trend_bp", f"no_fy_exactly_{TREND_WINDOW_YEARS}y_before_latest")
    elif twin[0][2] is None or twin[1][2] is None:
        legs["margin_trend_bp"] = Leg.absent("margin_trend_bp", "no_operating_income_tag")
    else:
        (e_label, _, e_m), (l_label, _, l_m) = twin
        bp = (l_m - e_m) * 100.0
        legs["margin_trend_bp"] = Leg(
            "margin_trend_bp", bp,
            detail=f"{bp:+.0f}bp {e_label}->{l_label} ({e_m:.2f}% -> {l_m:.2f}%)")

    latest_margin = series[-1][2] if n else None
    if latest_margin is None:
        legs["margin_sign"] = Leg.absent("margin_sign", "no_operating_income_tag")
    else:
        legs["margin_sign"] = Leg(
            "margin_sign", latest_margin,
            detail=f"latest FY operating margin {latest_margin:.2f}% "
                   f"({'negative' if latest_margin < 0 else 'positive'})")

    # ── cyclical through-cycle guard — RULED DEFINITION (L-1c, 2026-08-17) ────
    # PRIOR PEAK = max(FY revenue) over all FYs strictly BEFORE the decline-streak START
    # year. The guard permits DECLINE only if the latest revenue is BELOW that prior peak.
    #
    # WHAT THIS REPLACES AND WHY. The first implementation compared the latest revenue to
    # the peak of everything except the latest year. That is vacuous: a declining latest
    # year is BY CONSTRUCTION below the prior peak, so it returned LOWER for every cyclical
    # name with a streak — it could not refuse in the only situation it exists for.
    # Anchoring the peak BEFORE the streak begins makes it a real comparison: it asks
    # whether this downcycle has taken revenue below where the LAST cycle topped out.
    streak_val = legs["decline_streak"].value if legs["decline_streak"].present else None

    # PEAKS ARE LOGGED FOR EVERY CYCLICAL EVALUATION, not only the ones where the guard
    # reaches a comparison. The ruling asks for the peak pair so a tolerance can be
    # calibrated later; MU is the only cyclical name in the universe and its guard does not
    # fire (streak 0), so logging only on comparison would leave the calibration set EMPTY —
    # which is the opposite of what the instruction was for.
    if lens == "cyclical":
        _peaks = _local_peaks(series)
        legs["cyclical_peaks"] = Leg(
            "cyclical_peaks", [f"{lbl[:4]}:{rev:,.0f}" for lbl, rev in _peaks],
            detail=(f"{len(_peaks)} local peak(s): "
                    + "; ".join(f"{lbl[:4]} {rev:,.0f}" for lbl, rev in _peaks)
                    + (f" — two most recent delta "
                       f"{(_peaks[-1][1] - _peaks[-2][1]) / _peaks[-2][1] * 100:+.2f}%"
                       if len(_peaks) >= 2 else "")) if _peaks else "no local peak in window")
    else:
        _peaks = []

    if lens != "cyclical":
        legs["cyclical_peak_to_peak"] = Leg(
            "cyclical_peak_to_peak", None,
            detail=f"not applicable (lens={lens})")
    elif n < CYCLICAL_MIN_FY:
        legs["cyclical_peak_to_peak"] = Leg.absent(
            "cyclical_peak_to_peak", f"under_{CYCLICAL_MIN_FY}_fy_cannot_see_a_cycle")
    elif not streak_val:
        # No decline to gate. The guard does not fire, and it is NOT absent — nothing is
        # missing. DECLINE is already unreachable on the streak leg alone.
        legs["cyclical_peak_to_peak"] = Leg(
            "cyclical_peak_to_peak", None,
            detail="does not fire — no decline streak to gate (streak 0)")
    elif streak_val >= n - 1:
        # The streak covers the whole measured window, so no PRIOR PEAK was ever observed
        # — the earliest reading is the left edge of the window, not a cycle top. Say so
        # rather than treat the edge as a peak.
        legs["cyclical_peak_to_peak"] = Leg.absent(
            "cyclical_peak_to_peak",
            f"streak_{streak_val}_spans_measured_window_no_prior_peak")
    else:
        # PEAK-TO-PEAK (L-1d ruling). The two most recent local peaks in the measured
        # window; the guard permits DECLINE only if the LATER peak is BELOW the EARLIER one.
        # Strict comparison, no tolerance.
        #
        # WHY PEAK-TO-PEAK AND NOT A MAGNITUDE BAR (ruled, recorded because it is the whole
        # argument): a magnitude bar tests TROUGH DEPTH, and deep troughs are what cyclicals
        # DO — MU's revenue halved in FY2023 while the business was secularly fine, so a
        # depth test would permit DECLINE in precisely the false-positive case. §3 rule 1's
        # intent is SECULAR decline, and the only measurement of that is peak against peak.
        peaks = _peaks
        if len(peaks) < 2:
            # THE GATE FAILS CLOSED — permit REFUSED, and deliberately NOT asserted-absent.
            # This refuses ONE RULE'S GATE, it does not void the classification: with fewer
            # than two measurable cycle tops there is no secular-decline evidence, so the
            # name simply falls through to the remaining rules and is classified normally.
            # (Contrast the streak-spanning-window case above, which is verdict-level and
            # DOES stamp INPUTS-INCOMPLETE.)
            legs["cyclical_peak_to_peak"] = Leg(
                "cyclical_peak_to_peak", False,
                detail=f"permit REFUSED — only {len(peaks)} local peak(s) in {n} measured "
                       f"FY; two cycle tops are needed to measure secular decline")
        else:
            (e_lbl, e_rev), (l_lbl, l_rev) = peaks[-2], peaks[-1]
            lower = l_rev < e_rev
            legs["cyclical_peak_to_peak"] = Leg(
                "cyclical_peak_to_peak", lower,
                detail=f"peak {l_lbl[:4]} {l_rev:,.0f} vs prior peak {e_lbl[:4]} "
                       f"{e_rev:,.0f} — peak-to-peak "
                       f"{'LOWER (permit)' if lower else 'NOT lower (refuse)'} "
                       f"(streak {streak_val}, {n} FY measured)")

    # ── FCF sign, 2 of last 3 (R2) ───────────────────────────────────────────
    if fcf_fy is None:
        legs["fcf_negative_2of3"] = Leg.absent("fcf_negative_2of3", "no_fcf_series")
    else:
        usable = [(p, v) for p, v in fcf_fy if v is not None]
        if len(usable) < 3:
            legs["fcf_negative_2of3"] = Leg.absent(
                "fcf_negative_2of3", f"only_{len(usable)}_fy_fcf_points")
        else:
            last3 = usable[-3:]
            negs = sum(1 for _, v in last3 if v < 0)
            legs["fcf_negative_2of3"] = Leg(
                "fcf_negative_2of3", negs >= 2,
                detail=f"{negs} of last 3 FY FCF negative "
                       f"({', '.join(p[:4] for p, _ in last3)})")

    # ── rule 2's cyclical guard (L-1d ruling) ────────────────────────────────
    # Rule 2's semantic is PRE-EARNINGS. A cyclical name that has demonstrably EARNED
    # inside the measured window is not pre-earnings — it is in a trough. So for a
    # cyclical-lens name, YOUNG is BLOCKED if the window contains at least one FY with
    # positive operating margin AND positive FCF.
    #
    # "THE WINDOW" IS READ AS THE RECENT MEASURED WINDOW (TREND_WINDOW_YEARS + 1 points),
    # the same span every DECLINE leg uses. The alternative reading — the entire measured
    # series — gives the SAME answer on both cases the ruling pins (MU FY2023 blocked, a
    # never-profitable synthetic still YOUNG), so the choice is not load-bearing today; it
    # is stated here because it would matter for a name that earned a decade ago and has
    # not since, and that case should be ruled rather than inherited.
    if lens != "cyclical":
        legs["cyclical_has_earned"] = Leg(
            "cyclical_has_earned", None, detail=f"not applicable (lens={lens})")
    elif fcf_fy is None:
        # Cannot establish that it ever earned, so the block cannot be established either.
        # A missing input never satisfies a condition — including a condition that would
        # BLOCK a classification (R1, applied in the direction that does not invent
        # evidence). YOUNG stays reachable and the absence is on the record.
        legs["cyclical_has_earned"] = Leg.absent(
            "cyclical_has_earned", "no_fcf_series_cannot_establish_earnings")
    else:
        fcf_by_year = {str(p)[:4]: v for p, v in fcf_fy if v is not None}
        window_rows = series[-(TREND_WINDOW_YEARS + 1):]
        earned_years = [
            lbl[:4] for lbl, _rev, margin in window_rows
            if margin is not None and margin > 0
            and fcf_by_year.get(lbl[:4]) is not None and fcf_by_year[lbl[:4]] > 0
        ]
        legs["cyclical_has_earned"] = Leg(
            "cyclical_has_earned", bool(earned_years),
            detail=(f"earned in {', '.join(earned_years)} "
                    f"(positive operating margin AND positive FCF) — not pre-earnings"
                    if earned_years else
                    f"no FY in the last {len(window_rows)} measured has both a positive "
                    f"operating margin and positive FCF"))

    # ── capital returns (R5) ─────────────────────────────────────────────────
    if dividends is None:
        div_leg = Leg.absent("pays_dividend", "dividend_fetch_unknown")
    else:
        pays = len(dividends) > 0
        div_leg = Leg("pays_dividend", pays,
                      detail=f"{len(dividends)} dividend record(s) — "
                             f"{'pays a dividend' if pays else 'pays none'}")
    legs["pays_dividend"] = div_leg

    if shares_series is None or len(shares_series) < 2:
        buyback_leg = Leg.absent("net_buyback", "insufficient_share_series")
    else:
        ordered = sorted(shares_series, key=lambda r: r[0])
        first, last = ordered[0][1], ordered[-1][1]
        reduction = (first - last) / first if first else 0.0
        buyback_leg = Leg(
            "net_buyback", reduction >= BUYBACK_DE_MINIMIS_NET_REDUCTION,
            detail=f"net share change {reduction*100:+.2f}% "
                   f"({ordered[0][0][:10]} -> {ordered[-1][0][:10]}); "
                   f"de-minimis bar {BUYBACK_DE_MINIMIS_NET_REDUCTION*100:.0f}%")
    legs["net_buyback"] = buyback_leg

    if not div_leg.present and not buyback_leg.present:
        legs["capital_returns"] = Leg.absent(
            "capital_returns", "both_dividend_and_buyback_absent")
    else:
        present_bits = [(l.name, bool(l.value)) for l in (div_leg, buyback_leg) if l.present]
        any_return = any(v for _, v in present_bits)
        legs["capital_returns"] = Leg(
            "capital_returns", any_return,
            detail="; ".join(f"{k}={v}" for k, v in present_bits))

    # ── reinvestment (R6) ────────────────────────────────────────────────────
    if sales_to_capital_fy is None:
        legs["reinvestment_heavy"] = Leg.absent("reinvestment_heavy", "no_series")
    else:
        pts = [(p, v) for p, v in sales_to_capital_fy if v is not None]
        if len(pts) < 2:
            legs["reinvestment_heavy"] = Leg.absent(
                "reinvestment_heavy", f"only_{len(pts)}_point_series")
        else:
            latest_stc = pts[-1][1]
            heavy = latest_stc <= REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL
            legs["reinvestment_heavy"] = Leg(
                "reinvestment_heavy", heavy,
                detail=f"sales/capital {latest_stc:.3f} @ {pts[-1][0][:10]} vs bar "
                       f"{REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL:.2f} — "
                       f"{'HEAVY' if heavy else 'light'} reinvestment")
    return legs


# ── Rule engine ──────────────────────────────────────────────────────────────

def _uniq(flags: Sequence[str]) -> List[str]:
    """Order-preserving dedupe. INPUTS-INCOMPLETE can now be raised by the basis check AND
    by a rule's own absent legs; a flag list that repeats itself reads like two findings."""
    out: List[str] = []
    for f in flags:
        if f not in out:
            out.append(f)
    return out


def _record(assertions: List[Assertion], rule: str, leg: Leg,
            satisfied: Optional[bool]) -> None:
    outcome = "absent" if not leg.present else ("satisfied" if satisfied
                                                else "not_satisfied")
    assertions.append(Assertion(rule=rule, leg=leg.name, outcome=outcome,
                                detail=leg.detail or ""))


def classify(
    ticker: str,
    legs: Dict[str, Leg],
    lens: Optional[str] = None,
) -> StageResult:
    """Evaluate rules 1-4 top-down, first match wins. Pure — no I/O, no persistence."""
    assertions: List[Assertion] = []
    flags: List[str] = []
    absent: List[str] = []

    def note_absent(leg: Leg) -> None:
        # Dedupe on the FORMATTED entry, which is what the list actually holds. Comparing
        # the bare name against a list of "name(reason)" strings never matched, so a leg
        # consulted by two rules would have been listed twice in `absent_legs` — and that
        # column is read by Phase M, not just by a human.
        if leg.present:
            return
        entry = f"{leg.name}({leg.reason})"
        if entry not in absent:
            absent.append(entry)

    fy_count = legs["fy_count"].value or 0

    # ── the revenue basis must be established before any revenue leg is read (L-1c) ──
    # A bank whose net-revenue basis is uncomputable is stamped INPUTS-INCOMPLETE here,
    # loudly, rather than quietly classified on whatever rows survived. Never gross.
    basis_leg = legs.get("revenue_basis")
    if basis_leg is not None and not basis_leg.present:
        note_absent(basis_leg)
        flags.append(FLAG_INPUTS_INCOMPLETE)
        assertions.append(Assertion("basis", basis_leg.name, "absent",
                                    basis_leg.detail or ""))

    # ── Rule 2 pre-empted: insufficient history (order §2) ───────────────────
    # Ordered FIRST because it is a statement about whether the OTHER rules can be
    # evaluated at all, not a competing classification.
    if fy_count < MIN_FY_FOR_CLASSIFICATION:
        assertions.append(Assertion(
            "rule2_young", "fy_count", "satisfied",
            f"{fy_count} usable FY < {MIN_FY_FOR_CLASSIFICATION} required"))
        return StageResult(
            ticker=ticker, stage=STAGE_YOUNG, rule_fired="rule2_young_insufficient_history",
            lens=lens, assertions=assertions,
            flags=_uniq(flags + [FLAG_INSUFFICIENT_HISTORY, FLAG_YOUNG_UNCALIBRATED]),
            # Same "name(reason)" shape every other path writes. This return used bare
            # names, so the one row where absence is the WHOLE story was the one row whose
            # absent_legs did not say why.
            absent_legs=[f"{l.name}({l.reason})"
                         for l in legs.values() if not l.present],
            inputs={k: v.value for k, v in legs.items()})

    # ── Rule 1 — DECLINE (STRICT AND, R7) ────────────────────────────────────
    cyclical = lens == "cyclical"
    min_streak = DECLINE_MIN_STREAK_YEARS_CYCLICAL if cyclical else DECLINE_MIN_STREAK_YEARS
    streak_leg = legs["decline_streak"]
    margin_leg = legs["margin_trend_bp"]
    returns_leg = legs["capital_returns"]
    guard_leg = legs["cyclical_peak_to_peak"]

    decline_legs = [streak_leg, margin_leg, returns_leg]
    if cyclical:
        decline_legs.append(guard_leg)

    streak_ok = streak_leg.present and streak_leg.value >= min_streak
    margin_ok = margin_leg.present and margin_leg.value <= MARGIN_FLAT_BAND_BP
    returns_ok = returns_leg.present and bool(returns_leg.value)
    guard_ok = (not cyclical) or (guard_leg.present and bool(guard_leg.value))

    _record(assertions, "rule1_decline", streak_leg, streak_ok)
    _record(assertions, "rule1_decline", margin_leg, margin_ok)
    _record(assertions, "rule1_decline", returns_leg, returns_ok)
    if cyclical:
        _record(assertions, "rule1_decline", guard_leg, guard_ok)
        if not guard_leg.present:
            flags.append(FLAG_CYCLICAL_GUARD_BLIND)
        peaks_leg = legs.get("cyclical_peaks")
        if peaks_leg is not None:
            # The peak pair is logged on every evaluation that produced one, so a tolerance
            # can be calibrated later against REAL refusals instead of chosen in advance.
            _record(assertions, "rule1_decline", peaks_leg, None)
            if isinstance(peaks_leg.value, list) and len(peaks_leg.value) == 2:
                flags.append(FLAG_GUARD_TOLERANCE_UNCALIBRATED)

    for leg in decline_legs:
        note_absent(leg)

    all_present = all(l.present for l in decline_legs)
    if all_present and streak_ok and margin_ok and returns_ok and guard_ok:
        return StageResult(
            ticker=ticker, stage=STAGE_DECLINE, rule_fired="rule1_decline", lens=lens,
            assertions=assertions, flags=_uniq(flags), absent_legs=absent,
            inputs={k: v.value for k, v in legs.items()})

    # The guard EARNED its keep whenever a cyclical name cleared the non-cyclical bar and
    # was held back by the raised one or by through-cycle evidence. Worth its own flag —
    # this is the MU case the guard exists for.
    if cyclical and streak_leg.present and streak_leg.value >= DECLINE_MIN_STREAK_YEARS \
            and not (streak_ok and guard_ok):
        flags.append(FLAG_CYCLICAL_GUARD_HELD)

    # ── Rule 2 — YOUNG (OR; an absent leg simply cannot satisfy, R1) ─────────
    margin_sign_leg = legs["margin_sign"]
    fcf_leg = legs["fcf_negative_2of3"]
    margin_neg = margin_sign_leg.present and margin_sign_leg.value < 0
    fcf_neg = fcf_leg.present and bool(fcf_leg.value)
    _record(assertions, "rule2_young", margin_sign_leg, margin_neg)
    _record(assertions, "rule2_young", fcf_leg, fcf_neg)
    note_absent(margin_sign_leg)
    note_absent(fcf_leg)

    # ── rule 2's CYCLICAL GUARD (L-1d) ───────────────────────────────────────
    # A cyclical name that has earned inside the window is in a TROUGH, not pre-earnings.
    # Blocked -> fall through to the remaining rules. YOUNG-UNCALIBRATED keeps firing
    # wherever YOUNG is still reached, so R10's net stays live.
    earned_leg = legs.get("cyclical_has_earned")
    young_blocked = bool(cyclical and earned_leg is not None
                         and earned_leg.present and earned_leg.value)
    if cyclical and earned_leg is not None:
        _record(assertions, "rule2_young", earned_leg, young_blocked)
        note_absent(earned_leg)
    if young_blocked and (margin_neg or fcf_neg):
        flags.append(FLAG_CYCLICAL_GUARD_HELD_YOUNG)

    if (margin_neg or fcf_neg) and not young_blocked:
        return StageResult(
            ticker=ticker, stage=STAGE_YOUNG, rule_fired="rule2_young", lens=lens,
            assertions=assertions, flags=_uniq(flags + [FLAG_YOUNG_UNCALIBRATED]),
            absent_legs=absent, inputs={k: v.value for k, v in legs.items()})

    # ── Rule 3 — HIGROWTH (AND, remaining-legs for R7's named absences) ──────
    cagr_leg = legs["revenue_cagr"]
    reinvest_leg = legs["reinvestment_heavy"]
    cagr_ok = cagr_leg.present and cagr_leg.value >= HIGROWTH_MIN_CAGR
    reinvest_ok = reinvest_leg.present and bool(reinvest_leg.value)
    returns_absent_ok = returns_leg.present and not bool(returns_leg.value)

    _record(assertions, "rule3_higrowth", cagr_leg, cagr_ok)
    _record(assertions, "rule3_higrowth", reinvest_leg, reinvest_ok)
    _record(assertions, "rule3_higrowth", returns_leg, returns_absent_ok)
    note_absent(cagr_leg)
    note_absent(reinvest_leg)
    if reinvest_leg.present:
        flags.append(FLAG_REINVEST_UNCALIBRATED)

    # Remaining-legs (R6/R7): a structurally sourceless leg does not veto rule 3 the way
    # it vetoes rule 1. Present legs must all pass; absent ones are stamped, not assumed.
    higrowth_legs = [cagr_leg, reinvest_leg, returns_leg]
    present_checks = []
    if cagr_leg.present:
        present_checks.append(cagr_ok)
    if reinvest_leg.present:
        present_checks.append(reinvest_ok)
    if returns_leg.present:
        present_checks.append(returns_absent_ok)
    if present_checks and all(present_checks) and cagr_leg.present:
        # CAGR is NON-NEGOTIABLE: "high growth" with no measured growth is not a
        # classification, it is a guess. The other two legs may be absent; this one may not.
        return StageResult(
            ticker=ticker, stage=STAGE_HIGROWTH, rule_fired="rule3_higrowth", lens=lens,
            assertions=assertions,
            flags=_uniq(flags + ([FLAG_INPUTS_INCOMPLETE]
                                 if any(not l.present for l in higrowth_legs) else [])),
            absent_legs=absent, inputs={k: v.value for k, v in legs.items()})

    # ── Rule 4 — MATURE (residual) ───────────────────────────────────────────
    assertions.append(Assertion(
        "rule4_mature", "residual", "satisfied",
        "no earlier rule fired — positive earnings, moderate growth, "
        "capital returns present or reinvestment moderate"))
    return StageResult(
        ticker=ticker, stage=STAGE_MATURE, rule_fired="rule4_mature", lens=lens,
        assertions=assertions,
        flags=_uniq(flags + ([FLAG_INPUTS_INCOMPLETE] if absent else [])),
        absent_legs=absent, inputs={k: v.value for k, v in legs.items()})


# ── §5.2 lens-compatibility integrity check (NON-BLOCKING FLAGS) ──────────────

_INCOMPATIBLE = {
    (STAGE_YOUNG, "compounder"): "YOUNG+compounder",
    (STAGE_DECLINE, "growth"): "DECLINE+growth",
    (STAGE_MATURE, "growth"): "MATURE+growth (soft)",
}


def lens_compatibility_flags(stage: str, lens: Optional[str]) -> List[str]:
    """Flags only — NEVER reassigns a lens (order §8).

    The bank lens is EXEMPT from every stage check: banks are classified normally, but
    the bank lens always wins, so a stage/lens disagreement there is not a finding.
    """
    if lens == "bank":
        return []
    hit = _INCOMPATIBLE.get((stage, lens or ""))
    return [f"{FLAG_LENS_INCOMPAT}:{hit}"] if hit else []
