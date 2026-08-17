"""
Five-pillar scorer — deterministic, lens-aware.

Pillars:
  1. Business Quality   — margins, ROIC proxy, durability
  2. Financial Health   — leverage, liquidity, FCF generation
  3. Management & Capital Allocation — beat/miss, insider, dilution, buybacks
  4. Growth / Forward   — revenue/EPS trajectory, estimate direction (load-bearing for value-trap)
  5. Valuation          — lens-specific; anti-launder rate-aware

Anti-launder rule: pillar.confidence = min(material input confidences).
Scores: 1 (very weak) → 5 (very strong).
Rationale: capped at 220 chars per synthesis prompt spec.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from adapters.base import Confidence, Prov, PillarResult, min_conf, missing_prov
from adapters.edgar_adapter import EdgarData
from adapters.fred_adapter import FredData
from core.datatypes import TickerData
from core.valuation_anchors import (GROWTH_SHIFT_BOUNDS, ValuationPanel,
                                    bank_instrument_reading, compute_panel,
                                    dark_lens_score, score_bank_instrument,
                                    score_growth_shifted, score_yield_spread)

TODAY_STR = __import__("datetime").date.today().isoformat()

# ── helpers ──────────────────────────────────────────────────────────────────

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _score_from_points(pts: int, max_pts: int, lo: int = 1, hi: int = 5) -> int:
    """Map raw points [0, max_pts] onto score [lo, hi]."""
    if max_pts == 0:
        return lo
    frac = _clamp(pts / max_pts, 0.0, 1.0)
    return round(lo + frac * (hi - lo))


def _flag(condition: bool, label: str) -> List[str]:
    return [label] if condition else []


# ── Earnings history helpers ──────────────────────────────────────────────────

def _analyze_earnings(records: List[Dict]) -> Tuple[Optional[float], Optional[float], str]:
    """
    Returns (beat_rate 0-1, avg_surprise_pct, trend).
    beat_rate: fraction of quarters with surprisePercent > 0.
    avg_surprise_pct: mean surprisePercent.
    trend: "improving" | "stable" | "deteriorating" | "insufficient".
    """
    if not records:
        return None, None, "no_data"

    surprises = [
        r.get("surprisePercent")
        for r in records
        if r.get("surprisePercent") is not None
    ]
    if not surprises:
        return None, None, "no_data"

    beat_rate = sum(1 for s in surprises if s > 0) / len(surprises)
    avg_surprise = sum(surprises) / len(surprises)

    n = len(surprises)
    if n >= 4:
        half = n // 2
        recent_avg = sum(surprises[:half]) / half
        older_avg = sum(surprises[half:]) / (n - half)
        if recent_avg > older_avg + 2:
            trend = "improving"
        elif recent_avg < older_avg - 2:
            trend = "deteriorating"
        else:
            trend = "stable"
    else:
        trend = "insufficient"

    return beat_rate, avg_surprise, trend


def _analyze_insiders(transactions: List[Dict]) -> str:
    """
    Returns "cluster_buy" | "cluster_sell" | "routine_sell" | "neutral" | "no_data".
    Cluster: 3+ distinct insiders buying in recent transactions.
    Routine sell: dominated by option exercises and plan sales.
    """
    if not transactions:
        return "no_data"

    recent = transactions[:24]
    purchases = [t for t in recent
                 if "purchase" in str(t.get("Transaction", "")).lower()
                 or "buy" in str(t.get("Transaction", "")).lower()]
    sales = [t for t in recent
             if "sale" in str(t.get("Transaction", "")).lower()
             or "sell" in str(t.get("Transaction", "")).lower()]
    exercises = [t for t in recent
                 if "exercise" in str(t.get("Transaction", "")).lower()
                 or "option" in str(t.get("Transaction", "")).lower()]

    # Cluster buy: 3+ distinct insiders buying
    buying_insiders = {t.get("Insider") for t in purchases if t.get("Insider")}
    if len(buying_insiders) >= 3:
        return "cluster_buy"

    # If mostly options/exercises: routine (noise per ethos rule 4)
    if len(exercises) > len(sales) * 0.7:
        return "routine_sell"

    # Many sellers with purchases rare → cluster sell flag
    if len(sales) >= 5 and len(purchases) == 0:
        return "cluster_sell"

    return "neutral"


# ── Pillar 1: Business Quality ────────────────────────────────────────────────

def score_business_quality(yf: TickerData, lens: str) -> PillarResult:
    flags: List[str] = []
    pts = 0
    max_pts = 0
    inputs: List[Prov] = [yf.gross_margin, yf.operating_margin, yf.roe, yf.roa]

    # Gross margin
    if not yf.gross_margin.is_missing():
        gm = yf.gross_margin.value
        max_pts += 3
        if gm >= 0.65:
            pts += 3
        elif gm >= 0.45:
            pts += 2
        elif gm >= 0.25:
            pts += 1
        if lens == "cyclical" and gm > 0.55:
            flags.append("CYCLE-PEAK-MARGINS")

    # Operating margin
    if not yf.operating_margin.is_missing():
        om = yf.operating_margin.value
        max_pts += 3
        if om >= 0.25:
            pts += 3
        elif om >= 0.15:
            pts += 2
        elif om >= 0.05:
            pts += 1
        if om < 0:
            flags.append("NEGATIVE-OPERATING-MARGIN")

    # ROE (ROIC proxy)
    if not yf.roe.is_missing():
        roe = yf.roe.value
        max_pts += 3
        if roe >= 0.25:
            pts += 3
        elif roe >= 0.15:
            pts += 2
        elif roe >= 0.05:
            pts += 1
        if roe < 0:
            flags.append("NEGATIVE-ROE")

    score = _score_from_points(pts, max_pts) if max_pts > 0 else 3
    confidence = min_conf(*[p for p in inputs if not p.is_missing()])

    gm_str = f"{yf.gross_margin.value:.1%}" if not yf.gross_margin.is_missing() else "n/a"
    om_str = f"{yf.operating_margin.value:.1%}" if not yf.operating_margin.is_missing() else "n/a"
    roe_str = f"{yf.roe.value:.1%}" if not yf.roe.is_missing() else "n/a"

    rationale = (
        f"Gross margin {gm_str}, operating margin {om_str}, ROE {roe_str}."
        + (" Peak-cycle margins inflate quality score." if "CYCLE-PEAK-MARGINS" in flags else "")
    )

    return PillarResult(
        name="Business Quality",
        score=score,
        confidence=confidence,
        rationale=rationale,
        flags=flags,
        method=lens,
        key_inputs=inputs,
    )


# ── Pillar 2: Financial Health ─────────────────────────────────────────────────

def score_financial_health(yf: TickerData, lens: str) -> PillarResult:
    flags: List[str] = []
    pts = 0
    max_pts = 0
    inputs: List[Prov] = [
        yf.current_ratio, yf.debt_to_equity, yf.free_cashflow,
        yf.total_debt, yf.total_cash,
    ]

    # Current ratio
    if not yf.current_ratio.is_missing():
        cr = yf.current_ratio.value
        max_pts += 2
        if cr >= 2.0:
            pts += 2
        elif cr >= 1.0:
            pts += 1
        else:
            flags.append("CURRENT-RATIO-BELOW-1")

    # Debt/equity
    if not yf.debt_to_equity.is_missing():
        de = yf.debt_to_equity.value
        max_pts += 3
        if de <= 30:
            pts += 3
        elif de <= 100:
            pts += 2
        elif de <= 200:
            pts += 1
        else:
            flags.append("HIGH-LEVERAGE")

    # FCF positivity
    if not yf.free_cashflow.is_missing():
        fcf = yf.free_cashflow.value
        max_pts += 2
        if fcf > 0:
            pts += 2
            # FCF yield bonus check
            if not yf.market_cap.is_missing() and yf.market_cap.value > 0:
                yield_pct = fcf / yf.market_cap.value * 100
                if yield_pct >= 3:
                    pts = min(pts + 1, max_pts)
        else:
            flags.append("NEGATIVE-FCF")

    # Net cash position
    if not yf.total_cash.is_missing() and not yf.total_debt.is_missing():
        net_cash = yf.total_cash.value - yf.total_debt.value
        if net_cash > 0:
            flags.append("NET-CASH-POSITIVE")

    score = _score_from_points(pts, max_pts) if max_pts > 0 else 3
    confidence = min_conf(*[p for p in inputs if not p.is_missing()])

    cr_str = f"{yf.current_ratio.value:.2f}" if not yf.current_ratio.is_missing() else "n/a"
    de_str = f"{yf.debt_to_equity.value:.0f}%" if not yf.debt_to_equity.is_missing() else "n/a"
    fcf_str = (f"${yf.free_cashflow.value/1e9:.1f}B" if not yf.free_cashflow.is_missing() else "n/a")

    rationale = f"Current ratio {cr_str}, debt/equity {de_str}, FCF {fcf_str}."

    return PillarResult(
        name="Financial Health",
        score=score,
        confidence=confidence,
        rationale=rationale,
        flags=flags,
        method=lens,
        key_inputs=inputs,
    )


# ── Pillar 3: Management & Capital Allocation ──────────────────────────────────

def score_management(yf: TickerData, lens: str) -> PillarResult:
    flags: List[str] = []
    pts = 0
    max_pts = 0

    beat_rate, avg_surprise, trend = _analyze_earnings(yf.earnings_history)
    insider_signal = _analyze_insiders(yf.insider_transactions)

    # Beat/miss history
    beat_prov = Prov(
        value=beat_rate, source=f"{yf.feed_source}/earnings_history",
        as_of=TODAY_STR, confidence="medium" if beat_rate is not None else "low",
    )
    if beat_rate is not None:
        max_pts += 2
        if beat_rate >= 0.75:
            pts += 2
        elif beat_rate >= 0.50:
            pts += 1
        if trend == "improving":
            pts = min(pts + 1, max_pts)
            flags.append("BEAT-TREND-IMPROVING")
        elif trend == "deteriorating":
            flags.append("BEAT-TREND-DETERIORATING")

    # Average surprise magnitude
    if avg_surprise is not None:
        max_pts += 2
        if avg_surprise >= 5:
            pts += 2
        elif avg_surprise >= 0:
            pts += 1
        else:
            flags.append("AVERAGE-EARNINGS-MISS")

    # Insider activity
    insider_prov = Prov(
        value=insider_signal, source=f"{yf.feed_source}/insider_transactions",
        as_of=TODAY_STR, confidence="medium",
    )
    max_pts += 2
    if insider_signal == "cluster_buy":
        pts += 2
        flags.append("INSIDER-CLUSTER-BUY")
    elif insider_signal in ("neutral", "routine_sell", "no_data"):
        pts += 1  # neutral / noise
    elif insider_signal == "cluster_sell":
        flags.append("INSIDER-CLUSTER-SELL")
        # no points added

    inputs: List[Prov] = [beat_prov, insider_prov, yf.shares_outstanding]
    confidence = min_conf(*[p for p in inputs if not p.is_missing()])

    br_str = f"{beat_rate:.0%}" if beat_rate is not None else "n/a"
    avg_str = f"{avg_surprise:+.1f}%" if avg_surprise is not None else "n/a"
    rationale = (
        f"EPS beat rate {br_str}, avg surprise {avg_str}, trend {trend}. "
        f"Insider signal: {insider_signal}."
    )

    score = _score_from_points(pts, max_pts) if max_pts > 0 else 3

    return PillarResult(
        name="Management & Capital Allocation",
        score=score,
        confidence=confidence,
        rationale=rationale,
        flags=flags,
        method=lens,
        key_inputs=inputs,
    )


# ── Pillar 4: Growth / Forward ────────────────────────────────────────────────

def score_growth(yf: TickerData, edgar: EdgarData, lens: str) -> PillarResult:
    """
    Load-bearing for value-trap logic in synthesis:
      - Low growth here + cheap valuation + solvent health → synthesis should construct value-trap thesis.
      - High growth here → synthesis should NOT flag value trap.
    """
    flags: List[str] = []
    pts = 0
    max_pts = 0
    inputs: List[Prov] = [yf.revenue_growth, yf.trailing_pe, yf.forward_pe]

    # Revenue growth
    if not yf.revenue_growth.is_missing():
        rg = yf.revenue_growth.value  # decimal; 0.218 = 21.8%, 3.46 = 346%
        max_pts += 3
        # Classify growth rate (normalise: values >1 are unusual, flag
        pct = rg * 100
        if pct >= 20:
            pts += 3
        elif pct >= 10:
            pts += 2
        elif pct >= 0:
            pts += 1
        else:
            flags.append("NEGATIVE-REVENUE-GROWTH")

        if rg > 1.0:
            flags.append("CYCLICAL-RECOVERY-GROWTH")  # MU 346% = trough rebound

    # Forward PE discount to trailing (earnings growth signal)
    if not yf.trailing_pe.is_missing() and not yf.forward_pe.is_missing():
        tpe = yf.trailing_pe.value
        fpe = yf.forward_pe.value
        if tpe > 0 and fpe > 0:
            max_pts += 2
            discount = (tpe - fpe) / tpe  # positive = forward cheaper = earnings growth
            if discount >= 0.25:
                pts += 2
                flags.append("EARNINGS-GROWTH-EXPECTED")
            elif discount >= 0.0:
                pts += 1
            else:
                flags.append("EARNINGS-DECELERATION-EXPECTED")

    # Analyst coverage depth
    if not yf.analyst_count.is_missing() and yf.analyst_count.value is not None:
        inputs.append(yf.analyst_count)

    # EPS trajectory from earnings history
    _, _, trend = _analyze_earnings(yf.earnings_history)
    trend_prov = Prov(value=trend, source=f"{yf.feed_source}/earnings_history",
                      as_of=TODAY_STR, confidence="medium")
    inputs.append(trend_prov)

    if trend == "improving":
        max_pts += 1
        pts += 1
    elif trend == "deteriorating":
        max_pts += 1
        flags.append("EPS-TREND-DETERIORATING")

    score = _score_from_points(pts, max_pts) if max_pts > 0 else 3
    confidence = min_conf(*[p for p in inputs if not p.is_missing()])

    rg_str = (f"{yf.revenue_growth.value*100:.1f}%"
              if not yf.revenue_growth.is_missing() else "n/a")
    fpe_str = (f"{yf.forward_pe.value:.1f}x"
               if not yf.forward_pe.is_missing() else "n/a")

    rationale = (
        f"Revenue growth {rg_str} YoY. Forward PE {fpe_str}. "
        f"EPS trend: {trend}."
        + (" Cyclical recovery from trough inflates growth rate." if "CYCLICAL-RECOVERY-GROWTH" in flags else "")
    )

    return PillarResult(
        name="Growth / Forward",
        score=score,
        confidence=confidence,
        rationale=rationale,
        flags=flags,
        method=lens,
        key_inputs=inputs,
    )


# ── Pillar 5: Valuation ───────────────────────────────────────────────────────

class RateUnavailable(Exception):
    """The risk-free anchor is missing, so the valuation pillar REFUSES to score.

    Phase D ruling (mandatory rate anchor): every other anchor may go missing and the
    panel merely narrows, with provenance saying so. The RATE anchor may not. Scoring a
    multiple with no risk-free denominator is not a degraded answer, it is a different
    question — ethos rule 10 exists because a 22x multiple means opposite things at a 1%
    and a 7% 10Y. Returning a score anyway would be silent degradation, so this raises.

    Typed-signal siblings: PriceUnavailable (core.grading),
    AnchorPriceDivergence (synthesis.schema). Same contract — raised loud at the point
    of detection, converted to an honest persisted status at the boundary, and
    record-and-continue at batch level so one refusing ticker cannot abort the run.
    """


# D-4 ARMED 2026-08-09 on Vic's D-3 rulings. These three lenses derive their score from
# the valuation panel (MIN across available anchors) instead of a fixed absolute ladder.
#   growth — panel mapping REJECTED PERMANENTLY. Ruling principle: LENSES KEEP THEIR
#            INSTRUMENTS, THE RATE SHIFTS THRESHOLDS, NOT MEASURES. Its rate-shifted
#            EV/Revenue mechanism is on a separate dark pass and is NOT armed.
#   bank   — mechanism ruled (P/B vs justified P/B) but NOT armed: no calibration exists
#            until JPM is onboarded and dark-calibrated.
ARMED_PANEL_LENSES = ("compounder", "cyclical", "standard")
# Growth is ARMED too, but on the RATE-SHIFTED THRESHOLD mechanism, not the panel —
# it is rate-anchored, not panel-anchored. Kept separate so the distinction stays
# visible: "armed" and "panel-scored" are not the same set.
ARMED_LENSES = ARMED_PANEL_LENSES + ("growth", "bank")
# All five lenses are armed as of 2026-08-09 (Phase D closed), on three DIFFERENT
# mechanisms — keeping them as distinct sets is what stops "armed" being read as
# "panel-scored":
#   panel-anchored : compounder, cyclical, standard   (MIN across anchors)
#   rate-shifted   : growth                            (thresholds move with the 10Y)
#   cost-of-equity : bank                              (P/B vs ROE/CoE)


def _cap_beta_confidence(conf: "Confidence", yf: TickerData) -> "Confidence":
    """CODICIL 2 (ruled 2026-08-09): beta is SINGLE-SOURCE (FMP, no cross-check) and moves
    the cost of equity directly, so the bank pillar may not exceed MEDIUM while it is in
    use. A high-confidence bank score resting on an uncorroborated beta would be exactly
    the laundering the anti-launder rule exists to prevent.

    Lifts automatically the day a second beta source is wired — no code change needed,
    because it caps only when beta is present AND itself uncorroborated.
    """
    if yf.beta is None or yf.beta.is_missing():
        return conf
    if yf.beta.confidence == "high":
        return conf                      # a corroborated beta needs no cap
    return "medium" if conf == "high" else conf


def score_valuation(
    yf: TickerData,
    fred: FredData,
    lens: str,
    panel: "Optional[ValuationPanel]" = None,
) -> PillarResult:
    """Dispatch to lens-specific valuation scorer.

    Refuses outright without a risk-free rate — see RateUnavailable. The check is HERE,
    ahead of the dispatch, because it binds every lens.

    `panel` carries the sector and own-history anchors, which need EDGAR and the FMP
    sector snapshot — neither of which this module may fetch (pillars must stay pure and
    offline). The evaluation boundaries build it and pass it down. When it is absent the
    armed lenses fall back to a RISK-FREE-ONLY panel built from `fred` alone: still
    correct, but a 1-anchor panel, and it says so via the PANEL-NARROWED flag rather than
    pretending to a breadth it does not have. For the compounder that fallback is exactly
    the pre-D-4 behaviour, which is why the D-1 golden values are unchanged by arming.
    """
    if fred.rate_10y.is_missing():
        raise RateUnavailable(
            f"no FRED 10Y rate available — the valuation pillar refuses to score "
            f"{yf.ticker} on the '{lens}' lens. The rate anchor is mandatory: a multiple "
            f"judged against no risk-free regime is not a degraded score, it is "
            f"meaningless. (rate source={fred.rate_10y.source}, "
            f"confidence={fred.rate_10y.confidence})"
        )
    if lens == "cyclical":
        return _valuation_cyclical(yf, fred, panel)
    if lens == "compounder":
        return _valuation_compounder(yf, fred, panel)
    if lens == "bank":
        return _valuation_bank(yf, fred)
    if lens == "growth":
        return _valuation_growth(yf, fred)
    return _valuation_standard(yf, fred, panel)


def _panel_score(yf, fred, panel, lens: str, peak_warning: Optional[str] = None):
    """The armed panel verdict for one lens: (DarkLensScore | None).

    Thin wrapper so every armed lens reaches the aggregation the same way — MIN across
    available anchors, RULED permanent — and so the narrowing flags are emitted from one
    place rather than re-derived per lens.

    THE FALLBACK LIVES HERE, not in score_valuation, so a lens function called DIRECTLY
    behaves identically to one reached through the dispatcher. When it lived upstream, a
    direct call left panel=None and the lens silently lost its whole scoring path — the
    compounder fell through to EV/EBITDA and stopped emitting SECULAR-DECLINE-FCF-YIELD.
    A guard that only works when entered by the front door is not a guard.
    """
    if panel is None:
        panel = compute_panel(yf, fred, None, {}, lens)   # risk-free-only fallback
    return dark_lens_score(panel, lens, peak_warning=peak_warning)


def _panel_flags(ps) -> List[str]:
    """Narrowing flags, FLAG-ONLY per the independence-narrowed ruling (2026-08-09).

    17 of 20 measured readings were independence-narrowed, so a score haircut would have
    been a global ladder recalibration through a side door. These flags change no score;
    they record that the panel was thinner than three independent anchors.
    """
    if ps is None:
        return []
    return [f for f in ps.flags if f.startswith("PANEL-NARROWED")]


def _rate_note(fred: FredData) -> str:
    if fred.rate_10y.is_missing():
        return "Rate: unavailable."
    return f"10Y rate {fred.rate_10y.value:.2f}%."


def _cycle_position_from_trajectory(yf: TickerData) -> tuple:
    """
    Derive (cycle_pos: str, warn_type: str|None) from gross margin trajectory tag.
    Falls back to TTM absolute level if trajectory unavailable.
    warn_type:
      "peak"    → low PE at peak earnings = sell signal
      "rollover" → margins contracting; declining earnings; low PE not cheap either
      None       → no warning
    """
    traj = yf.gross_margin_trajectory
    tag = traj.tag if traj is not None else "stable"
    mrq_val = traj.mrq.value if (traj and not traj.mrq.is_missing()) else None

    HIGH_ABS = 0.65  # gross margin above this = high-absolute-level warning even while accelerating

    if tag == "rolling_over":
        return ("contracting/late-cycle", "rollover")
    elif tag == "peaking":
        return ("near-peak", "peak")
    elif tag == "accelerating":
        # Accelerating is positive — but if absolute MRQ level is extreme, warn approaching peak
        if mrq_val is not None and mrq_val > HIGH_ABS:
            return ("accelerating-toward-peak", "peak")
        return ("mid-cycle recovery", None)
    elif tag == "troughing":
        return ("trough/early-recovery", None)
    else:
        # stable or unknown: fall back to TTM absolute level
        if not yf.gross_margin.is_missing():
            gm = yf.gross_margin.value
            if gm > 0.55:
                return ("near-peak (TTM)", "peak")
            elif gm > 0.35:
                return ("mid-cycle (TTM)", None)
            else:
                return ("trough (TTM)", None)
        return ("unknown", None)


def _valuation_cyclical(yf: TickerData, fred: FredData, panel=None) -> PillarResult:
    """
    Cyclical lens — D-4 ARMED: TRAILING earnings yield vs the panel, plus a HARD GATE.

    BASIS RULED TRAILING (2026-08-09). On a forward basis MU scores 5 — maximally cheap,
    every anchor agreeing — at a cycle peak; that unanimity IS the 2018 signature. On
    trailing the same name scores 3 raw with own-history already dissenting. Both end at
    2 once the gate fires, so the basis choice is really about the FAILURE MODE: with no
    trajectory read available, forward hands the model a 5 and trailing a 3.

    GATE, NOT LADDER (ruled): at peak/rollover margins the denominator itself is about to
    change, so no rung geometry over the current E is meaningful. The gate CAPS at 2 and
    can never lift a score.
    """
    flags: List[str] = []
    inputs: List[Prov] = [yf.trailing_pe, yf.forward_pe, yf.gross_margin, fred.rate_10y]

    cycle_pos, warn_type = _cycle_position_from_trajectory(yf)

    # Propagate the gross margin flag if trajectory shows peak conditions
    if warn_type in ("peak", "rollover") and not yf.gross_margin.is_missing():
        if yf.gross_margin.value > 0.55:
            flags.append("CYCLE-PEAK-MARGINS")

    score = 3
    rationale_parts = [f"Cyclical. Cycle: {cycle_pos}."]

    ps = _panel_score(yf, fred, panel, "cyclical", peak_warning=warn_type)
    if ps is not None and ps.panel_score is not None:
        score = ps.panel_score
        flags.extend(f for f in ps.flags if f.startswith(("RICH", "VERY-RICH")))
        flags.extend(_panel_flags(ps))
        rationale_parts.append(
            f"Trailing earnings yield vs {ps.binding_anchor} "
            f"({ps.binding_spread:+.1f}pp)."
        )
        if warn_type == "peak":
            flags.append("LOW-PE-AT-CYCLE-PEAK-NOT-CHEAP")
            rationale_parts.append(
                "Peak-cycle earnings: low multiple is a sell signal, not cheap.")
        elif warn_type == "rollover":
            flags.append("MARGINS-CONTRACTING-EARNINGS-DECLINING")
            rationale_parts.append(
                "Margins contracting; declining earnings make a low multiple misleading.")
    else:
        rationale_parts.append("Trailing earnings yield unavailable.")
        if warn_type == "peak":
            flags.append("LOW-PE-AT-CYCLE-PEAK-NOT-CHEAP")
            score = 2
        elif warn_type == "rollover":
            flags.append("MARGINS-CONTRACTING-EARNINGS-DECLINING")
            score = 2

    rationale_parts.append(_rate_note(fred))
    confidence = min_conf(*[p for p in inputs if not p.is_missing()])

    return PillarResult(
        name="Valuation",
        score=score,
        confidence=confidence,
        rationale=" ".join(rationale_parts),
        flags=flags,
        method="cyclical/mid-cycle",
        key_inputs=inputs,
    )


def _valuation_compounder(yf: TickerData, fred: FredData, panel=None) -> PillarResult:
    """
    Quality compounder lens (Visa, payments, exchanges, GOOG).
    NOT P/TBV — book value is meaningless for asset-light networks.
    Focus: FCF yield vs risk-free, EV/EBITDA, growth durability.

    Secular-decline guard: if revenue growth is flat/negative, a high FCF yield
    reflects secular-decline pricing, NOT cheapness. Must state this explicitly.
    """
    flags: List[str] = []
    inputs: List[Prov] = [yf.fcf_yield, yf.ev_to_ebitda, yf.revenue_growth, fred.rate_10y]
    score = 3
    parts = ["Quality compounder (asset-light network) lens."]

    # Detect weak/declining growth — changes interpretation of FCF yield spread
    _growth_weak = (
        not yf.revenue_growth.is_missing()
        and yf.revenue_growth.value is not None
        and yf.revenue_growth.value < 0.03   # <3% trailing YoY = not meaningfully growing
    )

    # D-4 ARMED: FCF yield vs the PANEL (MIN across available anchors) rather than the
    # risk-free rate alone. The rungs are unchanged — measured delta-0 on all five golden
    # tickers — but the binding denominator may now be sector or own history, and the
    # rationale names which one it was.
    ps = _panel_score(yf, fred, panel, "compounder")
    if ps is not None and ps.panel_score is not None:
        spread = ps.binding_spread

        if _growth_weak and spread >= 1:
            # High FCF yield + no growth = market pricing secular decline, not a bargain
            flags.append("SECULAR-DECLINE-FCF-YIELD")
            parts.append(
                f"FCF yield vs {ps.binding_anchor} ({spread:+.1f}pp). Elevated yield "
                f"reflects secular-decline pricing, not cheapness — growth flat/negative."
            )
        else:
            parts.append(f"FCF yield vs {ps.binding_anchor} ({spread:+.1f}pp).")

        score = ps.panel_score
        flags.extend(f for f in ps.flags if f.startswith(("RICH", "VERY-RICH")))
        flags.extend(_panel_flags(ps))
    elif not yf.ev_to_ebitda.is_missing():
        ev_eb = yf.ev_to_ebitda.value
        parts.append(f"EV/EBITDA {ev_eb:.1f}x.")
        if ev_eb < 15:
            score = 5
        elif ev_eb < 20:
            score = 4
        elif ev_eb < 28:
            score = 3
        elif ev_eb < 35:
            score = 2
        else:
            score = 1

    parts.append(_rate_note(fred))
    confidence = min_conf(*[p for p in inputs if not p.is_missing()])

    return PillarResult(
        name="Valuation",
        score=score,
        confidence=confidence,
        rationale=" ".join(parts),
        flags=flags,
        method="compounder",
        key_inputs=inputs,
    )


def _valuation_bank(yf: TickerData, fred: FredData) -> PillarResult:
    """Bank / insurer / REIT lens — ARMED 2026-08-09: P/B vs JUSTIFIED P/B.

    RULED: a yield spread does not fit a bank. Book value IS the asset base, so the
    question is not what it earns against the risk-free rate but whether it earns more on
    its book than shareholders require. justified P/B = ROE / CoE, CoE = 10Y + beta x ERP
    — still rate-anchored, through the cost of equity rather than a spread.

    LADDER ON THE RATIO, NOT THE DIFFERENCE (ruled on the four-bank calibration): JPM
    (+0.70) and BK (+0.68) are indistinguishable on the difference but sit at 1.36x and
    1.45x of justified, and the difference is scale-dependent in the justified value.

    EXCESS-ROE GATE: excess ROE < 0 caps the score at 3. Same shape as the cyclical peak
    gate — a low P/B on a bank that does not cover its cost of equity is cheap FOR A
    REASON, and no rung geometry over the price can say the denominator is impaired. C is
    the validating case: 1.08x book, screen-cheap, ROE under CoE.
    """
    flags: List[str] = []
    # CODICIL 2: beta is FMP single-source with no cross-check and moves CoE directly, so
    # it is a KEY INPUT here and its confidence caps the pillar. See _cap_beta_confidence.
    inputs: List[Prov] = [yf.price_to_book, yf.roe, yf.beta, fred.rate_10y]
    score = 3
    parts = ["Bank lens."]

    reading = bank_instrument_reading(yf, fred)
    scored = score_bank_instrument(reading)
    if scored is not None:
        score = scored["score"]
        flags.extend(scored["flags"])
        parts.append(
            f"P/B {reading['price_to_book']:.2f}x vs justified "
            f"{reading['justified_pb']:.2f}x ({scored['ratio']:.2f}x); "
            f"ROE {reading['roe_pct']:.1f}% vs CoE {reading['cost_of_equity_pct']:.1f}%."
        )
        # CODICIL 1: rungs 5 and 4 are PROVISIONAL-UNCALIBRATED — no bank in the
        # calibration set traded below justified book, so those rungs are reasoned, not
        # measured. Flagged so the first live eval landing there is reportable.
        if score >= 4:
            flags.append("BANK-RUNG-UNCALIBRATED")
    elif not yf.price_to_book.is_missing():
        # Instrument unavailable (no ROE or no beta): report P/B, do NOT score off it.
        # A raw P/B ladder is the screen the justified-P/B work exists to replace.
        parts.append(f"P/B {yf.price_to_book.value:.2f}x; justified P/B unavailable.")
        flags.append("BANK-INSTRUMENT-UNAVAILABLE")

    parts.append(_rate_note(fred))
    confidence = _cap_beta_confidence(min_conf(*[p for p in inputs if not p.is_missing()]), yf)

    return PillarResult(
        name="Valuation",
        score=score,
        confidence=confidence,
        rationale=" ".join(parts),
        flags=flags,
        method="bank",
        key_inputs=inputs,
    )


def _valuation_growth(yf: TickerData, fred: FredData) -> PillarResult:
    """Growth / SaaS lens — D-4 ARMED: Rule-of-40 x EV/Revenue, RATE-SHIFTED thresholds.

    STANDING RULING: lenses keep their instruments, the rate shifts thresholds, not
    measures. The panel mapping was REJECTED PERMANENTLY — scoring an EBITDA yield here
    would swap a growth-QUALITY instrument for a PROFITABILITY one. So the instrument,
    the Rule-of-40 gate and the rung ordering are all untouched; only the EV/Revenue
    thresholds move, by k = (R0 + ERP) / (R + ERP).

    R0 = 4.0 RATIFIED PROVISIONALLY (2026-08-09): the fixed ladder was implicitly
    calibrated in a ~4% regime, so 4.0 as the k=1 point preserves its meaning.
    REVISIT TRIGGER: 10Y outside 3-6%. Clamp [0.60, 1.80] locked.

    This lens takes no panel — deliberately. It is rate-anchored, not panel-anchored.
    """
    flags: List[str] = []
    inputs: List[Prov] = [yf.ev_to_revenue, yf.revenue_growth, yf.operating_margin, fred.rate_10y]
    score = 3
    parts = ["Growth/SaaS lens."]

    # Rule of 40 (growth% + FCF/operating margin%)
    rule40 = None
    if not yf.revenue_growth.is_missing() and not yf.operating_margin.is_missing():
        rg_pct = yf.revenue_growth.value * 100
        om_pct = yf.operating_margin.value * 100
        rule40 = rg_pct + om_pct
        parts.append(f"Rule-of-40 score: {rule40:.0f} ({rg_pct:.0f}% growth + {om_pct:.0f}% margin).")
        flags.append(f"RULE40={rule40:.0f}")

    if not yf.ev_to_revenue.is_missing():
        evr = yf.ev_to_revenue.value
        rate = None if fred.rate_10y.is_missing() else fred.rate_10y.value
        shifted = score_growth_shifted(evr, rule40, rate)
        if shifted is not None:
            score = shifted["score"]
            parts.append(
                f"EV/Revenue {evr:.1f}x vs rate-shifted thresholds "
                f"{shifted['shifted_thresholds']} (k={shifted['shift_k']:.2f})."
            )
            if abs(shifted["shift_k"] - 1.0) > 0.001:
                flags.append(f"RATE-SHIFT-K={shifted['shift_k']:.2f}")
            if shifted["shift_k"] in GROWTH_SHIFT_BOUNDS:
                # The clamp is a guard against a rate shock producing an absurd multiple.
                # If it BINDS, the shift is no longer a smooth function of the rate and
                # that must be visible rather than silently flattened.
                flags.append("RATE-SHIFT-CLAMPED")
        else:
            parts.append(f"EV/Revenue {evr:.1f}x.")

    if not yf.ev_to_revenue.is_missing() and yf.ev_to_revenue.value > 20:
        flags.append("HIGH-EV-REVENUE-MULTIPLE")

    parts.append(_rate_note(fred))
    confidence = min_conf(*[p for p in inputs if not p.is_missing()])

    return PillarResult(
        name="Valuation",
        score=score,
        confidence=confidence,
        rationale=" ".join(parts),
        flags=flags,
        method="growth",
        key_inputs=inputs,
    )


# A negative multiple is an UNDEFINED one, not a cheap one. Ruled L-2b 2026-08-17 after
# RKLB scored 5/5 on EV/EBITDA -372.6x in production.
FLAG_NEGATIVE_MULTIPLE = "NEGATIVE-MULTIPLE-CHEAP-RUNGS-WITHHELD"


def _valuation_standard(yf: TickerData, fred: FredData, panel=None) -> PillarResult:
    """Standard lens: EV/EBITDA, P/E, FCF yield."""
    flags: List[str] = []
    inputs: List[Prov] = [yf.ev_to_ebitda, yf.trailing_pe, yf.fcf_yield, fred.rate_10y]
    score = 3
    parts = ["Standard valuation lens."]
    scored = False

    # D-4 ARMED: EBITDA yield vs the PANEL. The mapping is an IDENTITY, not a swap —
    # EV/EBITDA is this lens's own primary input and ebitda_yield is its reciprocal — which
    # is why arming it was ruled safe on counterfactual evidence alone.
    ps = _panel_score(yf, fred, panel, "standard")
    if ps is not None and ps.panel_score is not None:
        if not yf.ev_to_ebitda.is_missing():
            parts.append(f"EV/EBITDA {yf.ev_to_ebitda.value:.1f}x.")
        parts.append(f"EBITDA yield vs {ps.binding_anchor} ({ps.binding_spread:+.1f}pp).")
        score = ps.panel_score
        flags.extend(f for f in ps.flags if f.startswith(("RICH", "VERY-RICH")))
        flags.extend(_panel_flags(ps))
        scored = True
    elif not yf.ev_to_ebitda.is_missing():
        ev_eb = yf.ev_to_ebitda.value
        parts.append(f"EV/EBITDA {ev_eb:.1f}x.")
        if ev_eb < 0:
            # SIGN GATE (ruled 2026-08-17, L-2b). A NEGATIVE multiple is not a cheap one,
            # it is an UNDEFINED one: negative EV/EBITDA means negative EBITDA, so there
            # are no earnings to be cheap against. Without this the ladder's first rung
            # (`< 10`) admitted -372.6x and scored RKLB 5/5 — the maximum, "cheapest" rung
            # — on an evaluation that simultaneously carried NEGATIVE-OPERATING-MARGIN,
            # NEGATIVE-ROE and NEGATIVE-FCF. Same principle as the negative-forward-PE hard
            # stop; found live by tripwire 1's first firing.
            score = 1
            flags.append(FLAG_NEGATIVE_MULTIPLE)
        elif ev_eb < 10:
            score = 5
        elif ev_eb < 15:
            score = 4
        elif ev_eb < 22:
            score = 3
        elif ev_eb < 30:
            score = 2
        else:
            score = 1
        scored = True

    if not yf.trailing_pe.is_missing():
        pe = yf.trailing_pe.value
        parts.append(f"P/E {pe:.1f}x.")
        if not scored:
            if pe < 0:
                score = 1          # same gate: no earnings to be cheap against
                flags.append(FLAG_NEGATIVE_MULTIPLE)
            elif pe < 12:
                score = 5
            elif pe < 18:
                score = 4
            elif pe < 25:
                score = 3
            elif pe < 35:
                score = 2
            else:
                score = 1
            scored = True

    if not yf.fcf_yield.is_missing():
        fy = yf.fcf_yield.value * 100
        parts.append(f"FCF yield {fy:.1f}%.")

    # THE GATE IS A CAP, NOT ONLY A LADDER RUNG (ruled: "ineligible for rungs 4 and 5").
    # Whichever input awarded the score, a negative EV/EBITDA, P/E or FCF yield means the
    # cheap end of the ladder is unreachable BY CONSTRUCTION. Applied last so no ordering of
    # the three inputs can route around it.
    negatives = [
        f"EV/EBITDA {yf.ev_to_ebitda.value:.1f}x"
        if not yf.ev_to_ebitda.is_missing() and yf.ev_to_ebitda.value < 0 else None,
        f"P/E {yf.trailing_pe.value:.1f}x"
        if not yf.trailing_pe.is_missing() and yf.trailing_pe.value < 0 else None,
        f"FCF yield {yf.fcf_yield.value * 100:.1f}%"
        if not yf.fcf_yield.is_missing() and yf.fcf_yield.value < 0 else None,
    ]
    negatives = [n for n in negatives if n]
    if negatives and score >= 4:
        score = 3
        parts.append(f"Cheap rungs withheld — negative {', '.join(negatives)}.")
        if FLAG_NEGATIVE_MULTIPLE not in flags:
            flags.append(FLAG_NEGATIVE_MULTIPLE)

    parts.append(_rate_note(fred))
    confidence = min_conf(*[p for p in inputs if not p.is_missing()])

    return PillarResult(
        name="Valuation",
        score=score,
        confidence=confidence,
        rationale=" ".join(parts),
        flags=flags,
        method="standard",
        key_inputs=inputs,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def score_all(
    yf: TickerData,
    edgar: EdgarData,
    fred: FredData,
    lens: str,
    panel=None,
) -> List[PillarResult]:
    """Score all five pillars. Returns list in canonical order.

    `panel` is the D-4 valuation panel, built at the evaluation boundary (it needs the
    FMP sector snapshot, which this module may not fetch). Omitting it does not break
    scoring — the armed lenses fall back to a risk-free-only panel and flag the
    narrowing — but a full-breadth score requires it.
    """
    return [
        score_business_quality(yf, lens),
        score_financial_health(yf, lens),
        score_management(yf, lens),
        score_growth(yf, edgar, lens),
        score_valuation(yf, fred, lens, panel=panel),
    ]
