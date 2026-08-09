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

    out = []
    for period_end, ni in sorted(ni_points.items(), reverse=True):
        shares = shares_as_of(period_end)
        price = _price_on_or_before(price_history, period_end)
        if not shares or not price or ni is None:
            continue
        mkt_cap = price * shares
        if mkt_cap <= 0:
            continue
        out.append({"period_end": period_end, "earnings_yield": ni / mkt_cap * 100.0,
                    "price": price, "net_income_ttm": ni, "shares": shares})
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
    if ticker_yield is None:
        return AnchorReading(metric, ANCHOR_OWN_HISTORY, anchor_yield=median,
                             reason=f"{metric} unavailable or non-positive")
    return AnchorReading(
        metric, ANCHOR_OWN_HISTORY, ticker_yield, median, available=True,
        note=(f"median of {len(history)} quarters, "
              f"{history[-1]['period_end']}→{history[0]['period_end']}"))


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
