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
from adapters.yfinance_adapter import YFinanceData

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

def score_business_quality(yf: YFinanceData, lens: str) -> PillarResult:
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

def score_financial_health(yf: YFinanceData, lens: str) -> PillarResult:
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

def score_management(yf: YFinanceData, lens: str) -> PillarResult:
    flags: List[str] = []
    pts = 0
    max_pts = 0

    beat_rate, avg_surprise, trend = _analyze_earnings(yf.earnings_history)
    insider_signal = _analyze_insiders(yf.insider_transactions)

    # Beat/miss history
    beat_prov = Prov(
        value=beat_rate, source="yfinance/earnings_history",
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
        value=insider_signal, source="yfinance/insider_transactions",
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

def score_growth(yf: YFinanceData, edgar: EdgarData, lens: str) -> PillarResult:
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
    trend_prov = Prov(value=trend, source="yfinance/earnings_history",
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

def score_valuation(yf: YFinanceData, fred: FredData, lens: str) -> PillarResult:
    """Dispatch to lens-specific valuation scorer."""
    if lens == "cyclical":
        return _valuation_cyclical(yf, fred)
    if lens == "compounder":
        return _valuation_compounder(yf, fred)
    if lens == "bank":
        return _valuation_bank(yf, fred)
    if lens == "growth":
        return _valuation_growth(yf, fred)
    return _valuation_standard(yf, fred)


def _rate_note(fred: FredData) -> str:
    if fred.rate_10y.is_missing():
        return "Rate: unavailable."
    return f"10Y rate {fred.rate_10y.value:.2f}%."


def _cycle_position_from_trajectory(yf: YFinanceData) -> tuple:
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


def _valuation_cyclical(yf: YFinanceData, fred: FredData) -> PillarResult:
    """
    Cyclical lens: normalize to mid-cycle earnings.
    Cycle position derived from trajectory tag, NOT TTM level alone (per spec).
    Golden test (MU): low forward PE at extreme margins = SELL signal, not cheap.
    """
    flags: List[str] = []
    inputs: List[Prov] = [yf.trailing_pe, yf.forward_pe, yf.gross_margin, fred.rate_10y]

    cycle_pos, warn_type = _cycle_position_from_trajectory(yf)

    # Propagate the gross margin flag if trajectory shows peak conditions
    if warn_type in ("peak", "rollover") and not yf.gross_margin.is_missing():
        if yf.gross_margin.value > 0.55:
            flags.append("CYCLE-PEAK-MARGINS")

    score = 3
    rationale_parts = [f"Cyclical/mid-cycle. Cycle position: {cycle_pos}."]

    if not yf.forward_pe.is_missing():
        fpe = yf.forward_pe.value
        if warn_type == "peak":
            flags.append("LOW-PE-AT-CYCLE-PEAK-NOT-CHEAP")
            score = 2
            rationale_parts.append(
                f"Forward PE {fpe:.1f}x reflects peak-cycle earnings estimates; "
                f"mid-cycle normalized multiple is materially higher. "
                f"Low multiple is a sell signal, not cheap."
            )
        elif warn_type == "rollover":
            flags.append("MARGINS-CONTRACTING-EARNINGS-DECLINING")
            score = 2
            rationale_parts.append(
                f"Forward PE {fpe:.1f}x at contracting margins; "
                f"declining earnings make low multiple misleading."
            )
        else:
            if fpe < 12:
                score = 5
            elif fpe < 17:
                score = 4
            elif fpe < 25:
                score = 3
            elif fpe < 35:
                score = 2
            else:
                score = 1
            rationale_parts.append(f"Forward PE {fpe:.1f}x at {cycle_pos} cycle.")
    else:
        rationale_parts.append("Forward PE unavailable.")

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


def _valuation_compounder(yf: YFinanceData, fred: FredData) -> PillarResult:
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

    # FCF yield vs 10Y rate (equity risk premium proxy)
    if not yf.fcf_yield.is_missing() and not fred.rate_10y.is_missing():
        fy = yf.fcf_yield.value * 100
        r = fred.rate_10y.value
        spread = fy - r

        if _growth_weak and spread >= 1:
            # High FCF yield + no growth = market pricing secular decline, not a bargain
            flags.append("SECULAR-DECLINE-FCF-YIELD")
            parts.append(
                f"FCF yield {fy:.1f}% vs 10Y {r:.2f}% ({spread:+.1f}% spread). "
                f"Elevated yield reflects secular-decline pricing, not cheapness — "
                f"revenue growth is flat/negative."
            )
        else:
            parts.append(f"FCF yield {fy:.1f}% vs 10Y {r:.2f}% (spread {spread:+.1f}%).")

        if spread >= 3:
            score = 5
        elif spread >= 1:
            score = 4
        elif spread >= -1:
            score = 3
        elif spread >= -3:
            score = 2
            flags.append("RICH-VS-RISK-FREE")
        else:
            score = 1
            flags.append("VERY-RICH-VS-RISK-FREE")
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


def _valuation_bank(yf: YFinanceData, fred: FredData) -> PillarResult:
    """Bank / insurer / REIT lens: P/TBV, P/FFO."""
    flags: List[str] = []
    inputs: List[Prov] = [yf.price_to_book, fred.rate_10y]
    score = 3
    parts = ["Bank/insurer/REIT lens."]

    if not yf.price_to_book.is_missing():
        ptb = yf.price_to_book.value
        parts.append(f"P/TBV {ptb:.2f}x.")
        if ptb < 0.8:
            score = 5
        elif ptb < 1.2:
            score = 4
        elif ptb < 2.0:
            score = 3
        elif ptb < 3.0:
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
        method="bank",
        key_inputs=inputs,
    )


def _valuation_growth(yf: YFinanceData, fred: FredData) -> PillarResult:
    """Growth / SaaS lens: EV/Revenue vs growth, Rule of 40."""
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
        parts.append(f"EV/Revenue {evr:.1f}x.")
        base = 3
        if rule40 is not None:
            if rule40 >= 60:
                base = 5 if evr < 10 else 4 if evr < 20 else 3
            elif rule40 >= 40:
                base = 4 if evr < 8 else 3 if evr < 15 else 2
            else:
                base = 3 if evr < 6 else 2 if evr < 10 else 1
        score = base

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


def _valuation_standard(yf: YFinanceData, fred: FredData) -> PillarResult:
    """Standard lens: EV/EBITDA, P/E, FCF yield."""
    flags: List[str] = []
    inputs: List[Prov] = [yf.ev_to_ebitda, yf.trailing_pe, yf.fcf_yield, fred.rate_10y]
    score = 3
    parts = ["Standard valuation lens."]
    scored = False

    if not yf.ev_to_ebitda.is_missing():
        ev_eb = yf.ev_to_ebitda.value
        parts.append(f"EV/EBITDA {ev_eb:.1f}x.")
        if ev_eb < 10:
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
            if pe < 12:
                score = 5
            elif pe < 18:
                score = 4
            elif pe < 25:
                score = 3
            elif pe < 35:
                score = 2
            else:
                score = 1

    if not yf.fcf_yield.is_missing():
        fy = yf.fcf_yield.value * 100
        parts.append(f"FCF yield {fy:.1f}%.")

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
    yf: YFinanceData,
    edgar: EdgarData,
    fred: FredData,
    lens: str,
) -> List[PillarResult]:
    """Score all five pillars. Returns list in canonical order."""
    return [
        score_business_quality(yf, lens),
        score_financial_health(yf, lens),
        score_management(yf, lens),
        score_growth(yf, edgar, lens),
        score_valuation(yf, fred, lens),
    ]
