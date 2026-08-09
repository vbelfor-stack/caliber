"""
Phase D — valuation anchor panel. D-0: MEASUREMENT ONLY, applied to nothing.

"Cheap" needs a denominator and there is no single safe one, so three independent
anchors are measured and none is allowed to speak for the others:

    risk-free   (FRED 10Y)        should I own equities at all?   blind to market re-rating
    sector      (FMP sector P/E)  is this the better equity?      blind to market bubbles
    own history (this issuer's)   cheap vs its usual multiple?    blind to re-ratings

The justification for a panel rather than a pick is CALIBER's own golden test: MU at the
2018 cycle peak was cheap on trailing P/E, cheap versus its own history AND cheap versus
semis. Three readings said buy; only the margin trajectory caught that the E was about to
halve. DISAGREEMENT BETWEEN ANCHORS IS THE SIGNAL, so this module reports dispersion and
never averages it away.

Everything is expressed as a YIELD IN PERCENTAGE POINTS so the three anchors share one
currency and a spread means the same thing everywhere:

    spread = ticker_yield - anchor_yield      positive ⇒ cheaper than that anchor

D-0 applies nothing. No Prov is touched, no score, E(R) or grade can move. The output is
a table for calibration, exactly as the anchor guard and the EDGAR cross-check were run
before either was armed.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from adapters.edgar_adapter import EdgarData, instant_series, ttm_series

ANCHOR_RISK_FREE = "risk_free"
ANCHOR_SECTOR = "sector"
ANCHOR_OWN_HISTORY = "own_history"

# Metrics measured for every ticker regardless of lens. D-3 decides which ones each lens
# scores on; D-0's job is to show what the numbers look like first.
METRIC_EARNINGS_YIELD = "earnings_yield_trailing"
METRIC_FORWARD_EARNINGS_YIELD = "earnings_yield_forward"
METRIC_FCF_YIELD = "fcf_yield"
METRIC_EBITDA_YIELD = "ebitda_yield"

# An own-history series needs enough points to have a shape; below this the median is
# noise dressed as a baseline and the anchor is withheld instead.
MIN_HISTORY_POINTS = 8

# Adjacent-quarter share-count ratio beyond which a corporate action, not issuance or
# buyback, is the only explanation. Real buybacks and issuance move a share count by low
# single-digit percents a quarter; GOOG's 2022 split moved it 20x.
_SPLIT_RATIO_TOLERANCE = 1.5


@dataclass
class AnchorReading:
    """One (metric, anchor) pair. Unavailable readings are recorded, never dropped."""
    metric: str
    anchor: str
    ticker_yield: Optional[float] = None     # percentage points
    anchor_yield: Optional[float] = None     # percentage points
    available: bool = False
    reason: str = ""                         # why unavailable
    note: str = ""

    @property
    def spread(self) -> Optional[float]:
        if self.ticker_yield is None or self.anchor_yield is None:
            return None
        return self.ticker_yield - self.anchor_yield


@dataclass
class ValuationPanel:
    ticker: str
    lens: str
    as_of: str
    readings: List[AnchorReading] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def by_metric(self, metric: str) -> List[AnchorReading]:
        return [r for r in self.readings if r.metric == metric and r.available]

    def anchor_range(self, metric: str) -> Optional[float]:
        """How far apart the available anchors sit, in percentage points.

        Every anchor faces the same ticker yield, so for one metric this equals the range
        of the SPREADS — the ticker's own yield cancels. It still varies BETWEEN metrics,
        because which anchors are available does (own-history is trailing-earnings only).
        """
        ys = [r.anchor_yield for r in self.by_metric(metric) if r.anchor_yield is not None]
        return max(ys) - min(ys) if len(ys) > 1 else None

    def verdict_split(self, metric: str) -> Optional[Dict[str, List[str]]]:
        """Anchors that disagree about the DIRECTION of cheapness.

        This is what the panel exists to surface. A stock cheap against one denominator
        and dear against another is not an averaging problem — it is the finding. MU in
        2018 was cheap on three denominators at once and still a sell; the inverse case,
        where they split, is the one a single-anchor rule silently resolves.
        """
        cheap = [r.anchor for r in self.by_metric(metric)
                 if r.spread is not None and r.spread > 0]
        rich = [r.anchor for r in self.by_metric(metric)
                if r.spread is not None and r.spread <= 0]
        return {"cheap_vs": cheap, "rich_vs": rich} if cheap and rich else None

    def least_flattering(self, metric: str) -> Optional[AnchorReading]:
        """The anchor a stock looks WORST against — the provisional aggregation rule:
        never look cheaper than your least flattering defensible denominator."""
        rated = [r for r in self.by_metric(metric) if r.spread is not None]
        return min(rated, key=lambda r: r.spread) if rated else None


# ── shared rate-anchoring helper (D-1) ───────────────────────────────────────
# One spread→score ladder, used by the live valuation lenses. Extracted from
# _valuation_compounder unchanged; D-3 adds the remaining lenses and the per-lens
# ladders on top of this, so there is exactly one place the mapping lives.

# Ordered high→low; the FIRST threshold a spread clears wins. Percentage points.
# A None threshold is the floor and always matches, so the ladder is total.
RATE_SPREAD_LADDER = (
    (3.0, 5, None),
    (1.0, 4, None),
    (-1.0, 3, None),
    (-3.0, 2, "RICH"),
    (None, 1, "VERY-RICH"),
)


@dataclass
class SpreadScore:
    """One anchor's verdict on one metric: the spread it implies and the score it earns.

    Shaped for the D-3 aggregation rule (MIN across available anchors, RULED
    2026-08-09 permanent): `min(readings, key=lambda s: s.spread)` picks the least
    flattering denominator directly, matching ValuationPanel.least_flattering.
    Carrying `anchor` on the reading is what makes a narrowed panel detectable —
    the anchor COUNT is a binding condition of the ruling, so a caller must be able
    to see WHICH anchors produced a score, not just the winning number.
    """
    spread: float
    score: int
    anchor: str = ANCHOR_RISK_FREE
    flags: List[str] = field(default_factory=list)


def score_yield_spread(
    ticker_yield_pct: Optional[float],
    anchor_yield_pct: Optional[float],
    *,
    anchor: str = ANCHOR_RISK_FREE,
    ladder: tuple = RATE_SPREAD_LADDER,
    flag_scope: str = "RISK-FREE",
) -> Optional[SpreadScore]:
    """Score a yield against one anchor. None if either side is unavailable.

    Both yields are in PERCENTAGE POINTS, not fractions — the caller converts. That
    asymmetry is inherited: FMP serves fcf_yield as a fraction while FRED serves the
    10Y as percent, and the existing lenses already multiply by 100 at the call site.
    """
    if ticker_yield_pct is None or anchor_yield_pct is None:
        return None
    spread = ticker_yield_pct - anchor_yield_pct
    for threshold, score, flag in ladder:
        if threshold is None or spread >= threshold:
            return SpreadScore(
                spread=spread,
                score=score,
                anchor=anchor,
                flags=[f"{flag}-VS-{flag_scope}"] if flag else [],
            )
    raise AssertionError(f"ladder has no floor rung — spread {spread} unmatched")


def _yield_from_multiple(multiple: Optional[float]) -> Optional[float]:
    """1/x as a percentage. A NEGATIVE multiple has no yield interpretation — a company
    losing money is not offering a negative earnings yield to be ranked against the 10Y,
    it is unscoreable on this metric. Mirrors the negative-forward-EPS hard stop."""
    if multiple is None or multiple <= 0:
        return None
    return 100.0 / multiple


def _price_on_or_before(price_history: List[Dict], target: str) -> Optional[float]:
    """Closing price at the last session on or before a period-end.

    Period-ends land on weekends and holidays, and the filing's own date is not a trading
    day in general, so an exact-date lookup silently loses a third of the series.
    """
    best_date, best_close = None, None
    for row in price_history:
        d = str(row.get("date", ""))[:10]
        close = row.get("Close")
        if not d or close is None or d > target:
            continue
        if best_date is None or d > best_date:
            best_date, best_close = d, float(close)
    return best_close


def own_history_earnings_yields(
    edgar: EdgarData, price_history: List[Dict]
) -> List[Dict[str, Any]]:
    """This issuer's own trailing earnings yield at each historical period-end.

    Built from EDGAR's TTM net-income series and share count against the FMP price on
    that date — the multiple the market ACTUALLY paid then, not a reconstruction from
    today's share count applied backwards.
    """
    ni_points = {r.period_end: r.value for r in ttm_series(edgar.financials, "net_income")}
    # Share counts are matched AS-OF, not exactly. MU resolves its count from the dei
    # cover-page tag, whose dates are filing cover dates (2026-06-17) and never coincide
    # with a fiscal period-end (2026-05-28) — an exact join silently produced an empty
    # series for it while GOOG, on a us-gaap tag, joined cleanly.
    share_points = sorted(
        ((r.period_end, r.value)
         for r in instant_series(edgar.financials, "shares_outstanding")
         if r.period_end and r.value),
        reverse=True,
    )

    def shares_as_of(target: str) -> Optional[float]:
        return next((v for d, v in share_points if d <= target), None)

    out: List[Dict[str, Any]] = []
    dropped_loss = 0
    prev_shares: Optional[float] = None
    for period_end, ni in sorted(ni_points.items(), reverse=True):
        shares = shares_as_of(period_end)
        price = _price_on_or_before(price_history, period_end)
        if not shares or not price or ni is None:
            continue

        # SPLIT BOUNDARY (Phase G dependency). FMP prices are split-adjusted back to
        # today's basis; EDGAR share counts are AS FILED and are not restated. Across a
        # split the two disagree by the split ratio, which put GOOG's pre-2022 quarters
        # at an 81% earnings yield against a ~4% norm — a 20x artifact, not a valuation.
        # The series is only self-consistent back to the most recent discontinuity, so it
        # is truncated there rather than silently averaging the artifact into the median.
        if prev_shares is not None:
            ratio = shares / prev_shares if prev_shares else 1.0
            if ratio > _SPLIT_RATIO_TOLERANCE or ratio < 1 / _SPLIT_RATIO_TOLERANCE:
                break
        prev_shares = shares

        mkt_cap = price * shares
        if mkt_cap <= 0:
            continue
        # A loss-making period has no earnings yield to rank against the 10Y, exactly as
        # a negative P/E has none today. Excluded from the series, and counted so the
        # exclusion is visible rather than a silently shorter history.
        if ni <= 0:
            dropped_loss += 1
            continue
        out.append({"period_end": period_end, "earnings_yield": ni / mkt_cap * 100.0,
                    "price": price, "net_income_ttm": ni, "shares": shares,
                    "loss_periods_excluded": dropped_loss})
    if out:
        out[0]["loss_periods_excluded"] = dropped_loss
    return out


def _risk_free_reading(metric: str, ticker_yield: Optional[float],
                       fred: Any) -> AnchorReading:
    rate = getattr(fred, "rate_10y", None)
    if rate is None or rate.is_missing():
        return AnchorReading(metric, ANCHOR_RISK_FREE, ticker_yield,
                             reason="no FRED 10Y rate")
    if ticker_yield is None:
        return AnchorReading(metric, ANCHOR_RISK_FREE, anchor_yield=float(rate.value),
                             reason=f"{metric} unavailable or non-positive")
    return AnchorReading(metric, ANCHOR_RISK_FREE, ticker_yield, float(rate.value),
                         available=True)


def _sector_reading(metric: str, ticker_yield: Optional[float], sector: Optional[str],
                    sector_pe: Dict[str, float]) -> AnchorReading:
    if not sector_pe:
        return AnchorReading(metric, ANCHOR_SECTOR, ticker_yield,
                             reason="no sector P/E snapshot")
    if not sector or sector not in sector_pe:
        return AnchorReading(metric, ANCHOR_SECTOR, ticker_yield,
                             reason=f"sector {sector!r} not in snapshot")
    anchor = _yield_from_multiple(sector_pe[sector])
    if anchor is None or ticker_yield is None:
        return AnchorReading(metric, ANCHOR_SECTOR, ticker_yield, anchor,
                             reason="metric or sector yield unavailable")
    # The sector snapshot is an EARNINGS multiple; comparing an FCF or EBITDA yield to it
    # is a basis mismatch, recorded rather than hidden.
    note = ("" if metric in (METRIC_EARNINGS_YIELD, METRIC_FORWARD_EARNINGS_YIELD)
            else f"basis: {metric} vs sector EARNINGS yield")
    return AnchorReading(metric, ANCHOR_SECTOR, ticker_yield, anchor,
                         available=True, note=note)


def _own_history_reading(metric: str, ticker_yield: Optional[float],
                         history: List[Dict[str, Any]]) -> AnchorReading:
    if metric != METRIC_EARNINGS_YIELD:
        return AnchorReading(metric, ANCHOR_OWN_HISTORY, ticker_yield,
                             reason="own-history series is trailing-earnings only")
    if len(history) < MIN_HISTORY_POINTS:
        return AnchorReading(
            metric, ANCHOR_OWN_HISTORY, ticker_yield,
            reason=f"only {len(history)} historical points (<{MIN_HISTORY_POINTS})")
    median = statistics.median(h["earnings_yield"] for h in history)
    losses = history[0].get("loss_periods_excluded", 0)
    note = (f"median of {len(history)} quarters, "
            f"{history[-1]['period_end']}→{history[0]['period_end']}"
            + (f"; {losses} loss period(s) excluded" if losses else ""))
    if ticker_yield is None:
        return AnchorReading(metric, ANCHOR_OWN_HISTORY, anchor_yield=median,
                             reason=f"{metric} unavailable or non-positive")
    return AnchorReading(metric, ANCHOR_OWN_HISTORY, ticker_yield, median,
                         available=True, note=note)


def compute_panel(
    ticker_data: Any,
    fred: Any,
    edgar: Optional[EdgarData],
    sector_pe: Dict[str, float],
    lens: str,
    today: Optional[str] = None,
) -> ValuationPanel:
    """Measure every anchor against every yield metric. Pure — mutates nothing."""
    today = today or date.today().isoformat()
    panel = ValuationPanel(ticker=getattr(ticker_data, "ticker", "?"), lens=lens,
                           as_of=today)

    def val(name):
        p = getattr(ticker_data, name, None)
        return None if p is None or p.is_missing() else p.value

    metrics = {
        METRIC_EARNINGS_YIELD: _yield_from_multiple(val("trailing_pe")),
        METRIC_FORWARD_EARNINGS_YIELD: _yield_from_multiple(val("forward_pe")),
        METRIC_FCF_YIELD: (None if val("fcf_yield") is None
                           else float(val("fcf_yield")) * 100.0),
        METRIC_EBITDA_YIELD: _yield_from_multiple(val("ev_to_ebitda")),
    }

    history = (own_history_earnings_yields(edgar, ticker_data.price_history)
               if edgar is not None else [])
    if edgar is not None and not history:
        panel.notes.append(
            "own-history anchor unavailable: no overlapping TTM earnings, share count "
            "and price series")

    for metric, ticker_yield in metrics.items():
        panel.readings.append(_risk_free_reading(metric, ticker_yield, fred))
        panel.readings.append(
            _sector_reading(metric, ticker_yield, getattr(ticker_data, "sector", None),
                            sector_pe))
        panel.readings.append(_own_history_reading(metric, ticker_yield, history))

    return panel


def render_panel(panel: ValuationPanel) -> str:
    """The D-0 calibration table. Nothing here is applied."""
    lines = [
        f"[VAL-PANEL D-0] {panel.ticker}  lens={panel.lens}  as_of={panel.as_of}  "
        f"APPLIED=NOTHING",
        f"  {'metric':26s} {'anchor':12s} {'ticker%':>8s} {'anchor%':>8s} {'spread':>8s}  note",
    ]
    for r in panel.readings:
        ty = f"{r.ticker_yield:.2f}" if r.ticker_yield is not None else "—"
        ay = f"{r.anchor_yield:.2f}" if r.anchor_yield is not None else "—"
        sp = f"{r.spread:+.2f}" if r.spread is not None else "—"
        tail = r.note if r.available else f"UNAVAILABLE: {r.reason}"
        lines.append(f"  {r.metric:26s} {r.anchor:12s} {ty:>8s} {ay:>8s} {sp:>8s}  {tail}")
    for metric in (METRIC_EARNINGS_YIELD, METRIC_FORWARD_EARNINGS_YIELD,
                   METRIC_FCF_YIELD, METRIC_EBITDA_YIELD):
        worst = panel.least_flattering(metric)
        if worst is None or worst.spread is None:
            continue
        split = panel.verdict_split(metric)
        verdict = (f"SPLIT — cheap vs {'+'.join(split['cheap_vs'])}, "
                   f"rich vs {'+'.join(split['rich_vs'])}" if split
                   else "all anchors agree")
        rng = panel.anchor_range(metric)
        rng_s = f", anchors {rng:.2f}pp apart" if rng is not None else ""
        lines.append(f"  {metric:26s} least-flattering={worst.anchor} "
                     f"({worst.spread:+.2f}pp){rng_s}  {verdict}")
    for n in panel.notes:
        lines.append(f"  NOTE {n}")
    return "\n".join(lines)


def run_dark_panel(
    ticker_data: Any, fred: Any, edgar: Optional[EdgarData],
    sector_pe: Dict[str, float], lens: str,
    log: Optional[Any] = None,
) -> Optional[ValuationPanel]:
    """Compute and log the panel. Applies nothing, and cannot fail an evaluation.

    D-0 is measurement: it has no reach into any score, so a bug in it must not be able
    to take down an evaluation it cannot influence. It reports its own failure loudly.
    """
    emit = log or print
    try:
        panel = compute_panel(ticker_data, fred, edgar, sector_pe, lens)
        emit(render_panel(panel))
        return panel
    except Exception as e:                              # noqa: BLE001 — see docstring
        emit(f"[VAL-PANEL D-0] FAILED for {getattr(ticker_data, 'ticker', '?')}: "
             f"{type(e).__name__}: {e} (measurement only; evaluation unaffected)")
        return None


# ── D-3 DARK: per-lens panel application (APPLIES NOTHING) ───────────────────
# Everything below computes what a panel-anchored score WOULD be, alongside the live
# fixed-ladder score. Nothing here is wired into score_valuation; D-4 arms per lens on
# Vic's rulings. The point of the dark pass is to make the deltas arguable from data
# rather than from the shape of the code.

# Which yield metric each lens would be anchored on, and why that basis.
#   cyclical  — TRAILING, deliberately. MU's forward yield reads 30.16% (+25.47pp cheap,
#               all anchors agreeing) at a cycle peak; forward is the number that lies
#               exactly when the cyclical lens matters most. See D-0 §6.1.
#   compounder— FCF, unchanged: the prototype, already live and already spread-based.
#   standard  — EBITDA yield, matching the lens's own primary input (EV/EBITDA).
#   growth    — EBITDA yield, but see GROWTH_SPREAD_LADDER: the mechanism is a SHIFTED
#               ladder, not a spread verdict, because a SaaS multiple is a duration asset.
#   bank      — none. P/B is not a yield; see bank_instrument_reading().
LENS_METRIC = {
    "compounder": METRIC_FCF_YIELD,
    "cyclical": METRIC_EARNINGS_YIELD,
    "standard": METRIC_EBITDA_YIELD,
    "growth": METRIC_EBITDA_YIELD,
    "bank": None,
}

# Growth lens: same rung geometry, shifted DOWN one notch of generosity. A high-growth
# name is bought for duration, so it can carry a negative current yield spread and still
# be correctly priced; demanding a positive spread would score every SaaS name 1-2 and
# make the lens useless. This is the "shifted ladder" option, measured.
GROWTH_SPREAD_LADDER = (
    (1.0, 5, None),
    (-1.0, 4, None),
    (-3.0, 3, None),
    (-5.0, 2, "RICH"),
    (None, 1, "VERY-RICH"),
)

LENS_LADDER = {
    "compounder": RATE_SPREAD_LADDER,
    "cyclical": RATE_SPREAD_LADDER,
    "standard": RATE_SPREAD_LADDER,
    "growth": GROWTH_SPREAD_LADDER,
}

# Anchors that reference the MARKET rather than the issuer's own past. When own-history
# is absent the surviving pair is both of these — two views of the same market, not two
# independent checks (binding condition 1 of the aggregation ruling).
_MARKET_REFERENCED = (ANCHOR_RISK_FREE, ANCHOR_SECTOR)


@dataclass
class DarkLensScore:
    """What a panel-anchored valuation score WOULD be. Applied to nothing."""
    lens: str
    metric: Optional[str]
    live_score: Optional[int] = None
    panel_score: Optional[int] = None
    binding_anchor: Optional[str] = None
    binding_spread: Optional[float] = None
    anchor_count: int = 0
    narrowed: bool = False              # <3 anchors
    independence_narrowed: bool = False  # surviving anchors are all market-referenced
    haircut_score: Optional[int] = None  # panel_score under the one-rung narrowed haircut
    gate_applied: Optional[str] = None
    flags: List[str] = field(default_factory=list)
    reason: str = ""

    @property
    def delta(self) -> Optional[int]:
        if self.live_score is None or self.panel_score is None:
            return None
        return self.panel_score - self.live_score


def dark_lens_score(
    panel: ValuationPanel,
    lens: str,
    live_score: Optional[int] = None,
    peak_warning: Optional[str] = None,
) -> DarkLensScore:
    """The would-be panel score for one lens. PURE — applies nothing, persists nothing.

    peak_warning ('peak' | 'rollover' | None) comes from the cyclical lens's existing
    trajectory read. It is passed in rather than recomputed so the dark score gates on
    exactly the same signal the live lens already trusts.
    """
    metric = LENS_METRIC.get(lens)
    out = DarkLensScore(lens=lens, metric=metric, live_score=live_score)

    if metric is None:
        out.reason = "lens has no yield metric — see bank_instrument_reading()"
        return out

    readings = panel.by_metric(metric)
    rated = [
        score_yield_spread(r.ticker_yield, r.anchor_yield, anchor=r.anchor,
                           ladder=LENS_LADDER.get(lens, RATE_SPREAD_LADDER),
                           flag_scope=r.anchor.upper().replace("_", "-"))
        for r in readings if r.spread is not None
    ]
    rated = [r for r in rated if r is not None]
    out.anchor_count = len(rated)

    if not rated:
        out.reason = f"no available anchor for {metric}"
        return out

    # AGGREGATION: MIN across available anchors (RULED 2026-08-09, permanent).
    worst = min(rated, key=lambda s: s.spread)
    out.panel_score = worst.score
    out.binding_anchor = worst.anchor
    out.binding_spread = worst.spread
    out.flags = list(worst.flags)

    out.narrowed = out.anchor_count < 3
    present = {r.anchor for r in rated}
    out.independence_narrowed = out.narrowed and present.issubset(set(_MARKET_REFERENCED))
    if out.independence_narrowed:
        out.flags.append("PANEL-NARROWED-MARKET-ONLY")
    elif out.narrowed:
        out.flags.append("PANEL-NARROWED")

    # Independence haircut, MEASURED not applied: one rung off a cheap verdict when the
    # only surviving anchors are market-referenced. Never makes a stock look cheaper.
    out.haircut_score = out.panel_score
    if out.independence_narrowed and out.panel_score is not None and out.panel_score > 1:
        out.haircut_score = out.panel_score - 1

    # CYCLICAL HARD GATE: at peak/rollover margins a cheap multiple is a sell signal, not
    # a discount. The gate CAPS; it never raises. This is the MU-2018 guard, kept as a
    # gate rather than folded into the ladder because peak earnings break the yield's
    # meaning outright — no rung geometry can express "this E is about to halve".
    if lens == "cyclical" and peak_warning in ("peak", "rollover"):
        out.gate_applied = peak_warning
        if out.panel_score is not None and out.panel_score > 2:
            out.panel_score = 2
            out.flags.append(f"CYCLE-GATE-CAP-{peak_warning.upper()}")
        if out.haircut_score is not None and out.haircut_score > 2:
            out.haircut_score = 2

    return out


def bank_instrument_reading(ticker_data: Any, fred: Any) -> Dict[str, Any]:
    """The bank lens's ALTERNATIVE instrument, measured dark: P/B against excess ROE.

    A yield spread does not fit a bank. Book value IS the asset base, so the question is
    not "what does this earn against the risk-free rate" but "does it earn more on its
    book than shareholders require" — and P/B is the market's answer to exactly that.
    Excess ROE = ROE - cost of equity, with CoE = 10Y + beta x ERP (ERP fixed at 4.5pp).

    Returns the measurement only; no score, no ladder. The mechanism question goes to Vic.
    """
    def val(name):
        p = getattr(ticker_data, name, None)
        return None if p is None or p.is_missing() else p.value

    roe, beta, ptb = val("roe"), val("beta"), val("price_to_book")
    rate = None if fred.rate_10y.is_missing() else fred.rate_10y.value
    coe = None if (rate is None or beta is None) else rate + beta * 4.5
    excess = None if (roe is None or coe is None) else roe * 100.0 - coe
    return {
        "price_to_book": ptb,
        "roe_pct": None if roe is None else roe * 100.0,
        "beta": beta,
        "rate_10y": rate,
        "cost_of_equity_pct": coe,
        "excess_roe_pp": excess,
        # Justified P/B under the Gordon identity: (ROE - g) / (CoE - g), g = 0 for the
        # measurement. Reduces to ROE/CoE, which is the whole point — a bank earning its
        # cost of equity is worth book, and the ratio says how far off that it trades.
        "justified_pb": None if (roe is None or not coe) else (roe * 100.0) / coe,
        "pb_vs_justified": (None if (ptb is None or roe is None or not coe)
                            else ptb - (roe * 100.0) / coe),
    }


def render_dark_lens(scores: List[DarkLensScore], ticker: str) -> str:
    """The D-3 delta table for one ticker. Nothing here is applied."""
    lines = [f"[VAL-LENS D-3 DARK] {ticker} — live vs would-be panel score (APPLIES NOTHING)"]
    lines.append(f"  {'lens':<11} {'metric':<24} {'live':>4} {'panel':>5} {'cut':>4} "
                 f"{'Δ':>3}  {'binding':<12} {'spread':>8}  flags")
    for s in scores:
        if s.panel_score is None:
            lines.append(f"  {s.lens:<11} {'—':<24} {'—':>4} {'—':>5} {'—':>4} {'—':>3}  "
                         f"{'—':<12} {'—':>8}  {s.reason}")
            continue
        d = s.delta
        lines.append(
            f"  {s.lens:<11} {(s.metric or '—'):<24} "
            f"{(s.live_score if s.live_score is not None else '—'):>4} "
            f"{s.panel_score:>5} {s.haircut_score:>4} "
            f"{(f'{d:+d}' if d is not None else '—'):>3}  "
            f"{(s.binding_anchor or '—'):<12} "
            f"{(f'{s.binding_spread:+.2f}pp' if s.binding_spread is not None else '—'):>8}  "
            f"{','.join(s.flags) if s.flags else '—'}"
        )
    return "\n".join(lines)


def run_dark_lens(
    panel: Optional[ValuationPanel],
    lens: str,
    live_score: Optional[int],
    peak_warning: Optional[str] = None,
    log: Optional[Any] = None,
) -> Optional[DarkLensScore]:
    """Compute and log the would-be panel score for the ACTIVE lens. Applies nothing.

    Same containment contract as run_dark_panel: D-3 has no reach into any score, so a
    bug here must not be able to take down an evaluation it cannot influence.
    """
    emit = log or print
    if panel is None:
        return None
    try:
        dark = dark_lens_score(panel, lens, live_score=live_score,
                               peak_warning=peak_warning)
        emit(render_dark_lens([dark], panel.ticker))
        return dark
    except Exception as e:                              # noqa: BLE001 — see docstring
        emit(f"[VAL-LENS D-3] FAILED for {panel.ticker}: {type(e).__name__}: {e} "
             f"(measurement only; evaluation unaffected)")
        return None
