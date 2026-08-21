"""Phase H-1 — FCF component series. DARK: applied to nothing.

WHAT THIS IS. A per-period historical series of the FCF family — free cash flow, FCF
margin, sales-to-capital, growth rates and the FCF yield — assembled from EDGAR flows and
instants at each period-end the issuer actually filed. H-3 arms the FCF yield leg as the
compounder lens's own-history anchor. Nothing here is wired into a score yet.

THE SCHEMA ADDENDUM (ruled 2026-08-15). These series are PERSISTED, because Phase M
(Monte Carlo) will derive input distributions from them. Three rulings shape the output
and none of them is an implementation detail:

  1. GRAIN — native quarterly, with `period_type` marking which period-ends are fiscal
     year ends. Per-year is then a QUERY (period_type='FY'), not a second build, so the
     anchor gets its quarterly series and Phase M gets ~4x the points from one table.

  2. NEGATIVE FCF IS PERSISTED, NEVER DROPPED. The H-FCF scoping report argued the
     negative-quarter exclusion was safe because a higher median makes a stock look
     richer and MIN takes the least flattering anchor. THAT ARGUMENT HOLDS ONLY WHILE
     THE CONSUMER IS MIN-OF-MEDIANS. Phase M sampling this series would be handed a
     distribution with its left tail removed — MU loses 10 of 24 quarters (42%), C loses
     14 of 21 — which is precisely the downside Monte Carlo exists to model. So exclusion
     is a READ-TIME FILTER for the anchor (`excluded=True`) and never a storage filter.

  3. REINVESTMENT IS EMITTED NULL. It needs capex - D&A + dWC and there is NO
     depreciation/amortization spec among the 19 EDGAR specs — the same missing spec that
     deferred the EBITDA leg to H-4. The column exists so Phase M needs no migration when
     EDGAR expansion lands it. NO PROXY, silent or otherwise. sales-to-capital carries
     reinvestment duty for Phase M v1.

THREE DISTINCT WAYS A POINT CAN BE ABSENT FROM THE ANCHOR, and conflating them would undo
ruling 2. Each has its OWN field — reason-present must never require a cross-check against
`excluded` to interpret (F3, ruled 2026-08-15):
    not emitted        — UNCOMPUTABLE. An input was missing (no capex tag, no revenue at
                         that period-end, non-positive invested capital). Counted in
                         diagnostics, never silently swallowed.
    emitted excluded=1 — COMPUTABLE, but illegal for the MIN-of-medians anchor. The value
                         is stored in full and `exclusion_reason` says why it is skipped.
                         Phase M reads it; the anchor skips it.
    emitted value=None — STRUCTURALLY UNAVAILABLE, not rejected. `null_reason` says why,
                         `excluded` stays 0, and no consumer reads it because
                         `anchor_usable` already filters on `value is not None`.
                         Reinvestment is the only case today.

SHARE BASIS. FCF, margin, sales-to-capital and the growth rates are share-independent —
no price, no share count, so a split cannot touch them and their basis is
`not_applicable`. Only the FCF YIELD divides by a market cap, so only it carries the G-4
split basis, and it carries it per point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from adapters.edgar_adapter import EdgarData, instant_series, ttm_series

# Metrics. Namespaced to this module deliberately — `fcf_yield` here is a HISTORICAL
# series point built from EDGAR flows, not FMP's live freeCashFlowYieldTTM field.
METRIC_FCF = "fcf"
METRIC_FCF_MARGIN = "fcf_margin"
METRIC_SALES_TO_CAPITAL = "sales_to_capital"
METRIC_REINVESTMENT = "reinvestment"
METRIC_FCF_YIELD = "fcf_yield"
METRIC_FCF_GROWTH = "fcf_growth"
METRIC_REVENUE_GROWTH = "revenue_growth"

ALL_METRICS = (METRIC_FCF, METRIC_FCF_MARGIN, METRIC_SALES_TO_CAPITAL,
               METRIC_REINVESTMENT, METRIC_FCF_YIELD, METRIC_FCF_GROWTH,
               METRIC_REVENUE_GROWTH)

PERIOD_FY = "FY"
PERIOD_TTM_Q = "TTM_Q"

BASIS_NOT_APPLICABLE = "not_applicable"

# Exclusion reasons (ruling 2 — read-time filter only, the row is still stored).
EXCL_NEGATIVE_FCF = "negative_fcf"
EXCL_NON_POSITIVE_BASE = "non_positive_base"

# Withholding reasons (uncomputable — no row is emitted).
WITHHELD_NO_CAPEX = "no_capex_tag"
WITHHELD_NO_OCF = "no_operating_cashflow_tag"
WITHHELD_NO_DA_SPEC = "no_da_spec"

# A year-ago period-end must land this close for a growth rate to be well posed. Matches
# the tolerance _assemble_ttm already uses for its prior-year YTD leg.
_YOY_TOLERANCE_DAYS = 10


@dataclass
class SeriesPoint:
    """One metric, at one period-end, on one basis.

    `components` carries the raw inputs that produced the value. It is stored so that a
    later disagreement can be traced to a leg rather than re-derived from scratch — the
    same reason the split work stamps `first_filed` on every share fact.
    """
    ticker: str
    metric: str
    period_end: str
    period_type: str
    value: Optional[float]
    unit: str
    basis: str = BASIS_NOT_APPLICABLE
    method: Optional[str] = None
    excluded: bool = False
    # SET IFF excluded — the value is real but illegal for the anchor.
    exclusion_reason: Optional[str] = None
    # SET IFF value is None and NOT excluded — the value is structurally unavailable.
    # Deliberately NOT the same column as exclusion_reason: a consumer must never have to
    # cross-check `excluded` to learn which kind of absence a reason describes.
    null_reason: Optional[str] = None
    components: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SeriesResult:
    ticker: str
    points: List[SeriesPoint] = field(default_factory=list)
    basis: str = BASIS_NOT_APPLICABLE          # the share basis available to fcf_yield
    withheld: Dict[str, str] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def by_metric(self, metric: str) -> List[SeriesPoint]:
        """Every stored point for a metric, newest first — INCLUDING excluded ones.

        This is the Phase M read. The anchor read is `anchor_usable`.
        """
        return sorted((p for p in self.points if p.metric == metric),
                      key=lambda p: p.period_end, reverse=True)

    def anchor_usable(self, metric: str) -> List[SeriesPoint]:
        """The MIN-of-medians anchor read — the read-time filter of ruling 2."""
        return [p for p in self.by_metric(metric)
                if not p.excluded and p.value is not None]

    def excluded_count(self, metric: str) -> int:
        return sum(1 for p in self.by_metric(metric) if p.excluded)


def _days_between(a: str, b: str) -> Optional[int]:
    from datetime import date
    try:
        d1 = date.fromisoformat(a[:10])
        d2 = date.fromisoformat(b[:10])
    except (ValueError, TypeError):
        return None
    return (d2 - d1).days


def _flow_points(financials: Any, field_name: str) -> Dict[str, Tuple[float, str]]:
    """{period_end: (ttm_value, method)} for a flow field."""
    return {r.period_end: (r.value, r.method)
            for r in ttm_series(financials, field_name)
            if r.period_end and r.value is not None}


def _instant_as_of(financials: Any, field_name: str) -> Any:
    """A callable giving the newest instant value at or before a target period-end.

    AS-OF, not exact. The precedent is own_history_earnings_yields: MU resolves its share
    count from a dei cover-page tag whose dates are FILING dates and never coincide with a
    fiscal period-end, so an exact join silently produced an empty series for it.
    """
    points = sorted(((r.period_end, r.value)
                     for r in instant_series(financials, field_name)
                     if r.period_end and r.value is not None),
                    reverse=True)

    def as_of(target: str) -> Optional[float]:
        return next((v for d, v in points if d <= target), None)

    return as_of


def _fy_ends(financials: Any, concepts: List[str]) -> set:
    """Period-ends the issuer itself labelled a fiscal year end.

    Taken from the filings (fp == 'FY' on a 10-K), never inferred from month-of-year: a
    52/53-week filer's year end moves, and MU's fiscal year ends in August.
    """
    out = set()
    for concept in concepts:
        for r in financials.concepts.get(concept, []):
            if r.get("fp") == "FY" and str(r.get("form", "")).startswith("10-K"):
                if r.get("end"):
                    out.add(r["end"])
    return out


def _concept_of(financials: Any, field_name: str) -> Optional[str]:
    rf = financials.fields.get(field_name)
    if rf is None or not rf.concept or rf.concept.startswith("derived:"):
        return None
    return rf.concept


def _share_basis(edgar: EdgarData, split_report: Any) -> Tuple[Any, str]:
    """(shares_as_of, basis) on the G-4 split basis where it is established.

    Mirrors own_history_series' contract: the restated basis is preferred, the truncated
    one is the fallback, and the basis is RETURNED rather than hidden because a yield
    computed on a truncated share series is a DIFFERENT MEASUREMENT from one computed on
    a restated series.

    On the truncated fallback this returns as-filed share counts with NO restatement. A
    point built from them can be wrong by exactly the split ratio, so the basis stamp is
    the only thing telling a later reader which it is — which is why it is per point.
    """
    from core.corporate_actions import restatement_blocked, split_factor

    blocked = restatement_blocked(split_report)
    raw = sorted(((r.period_end, r.value, r.first_filed)
                  for r in instant_series(edgar.financials, "shares_outstanding")
                  if r.period_end and r.value),
                 reverse=True)

    if blocked is None:
        events = split_report.usable

        def restated(target: str) -> Optional[float]:
            hit = next(((v, f) for d, v, f in raw if d <= target), None)
            if hit is None:
                return None
            value, first_filed = hit
            # No filing date means the basis is UNKNOWN, not "assume today's". Recorded
            # fixtures predate G-1 and carry none; such a point is dropped rather than
            # silently priced on an unverified basis.
            if first_filed is None and events:
                return None
            return value * split_factor(first_filed, events)

        return restated, "split_restated"

    def as_filed(target: str) -> Optional[float]:
        return next((v for d, v, _ in raw if d <= target), None)

    return as_filed, f"truncated ({blocked})"


def build_fcf_series(
    ticker: str,
    edgar: Optional[EdgarData],
    price_history: Optional[List[Dict]] = None,
    split_report: Any = None,
) -> SeriesResult:
    """Assemble the FCF component series. PURE — mutates nothing, persists nothing."""
    result = SeriesResult(ticker=ticker)
    if edgar is None:
        result.withheld["all"] = "no EDGAR data"
        return result

    fin = edgar.financials
    ocf = _flow_points(fin, "operating_cashflow")
    capex = _flow_points(fin, "capex")
    revenue = _flow_points(fin, "revenue")

    if not ocf:
        result.withheld[METRIC_FCF] = WITHHELD_NO_OCF
        return result
    if not capex:
        # CORRECTED L-4d, 2026-08-21. This comment used to read "V, JPM and USB file no
        # PaymentsToAcquirePropertyPlantAndEquipment concept at all... an ACCEPTED DATA
        # LIMIT". It was right about JPM and USB and WRONG ABOUT V: V files
        # PaymentsToAcquireProductiveAssets, so V was a SPEC GAP wearing a data-limit
        # label, and the label is why nobody looked for six months. V now resolves.
        # JPM and USB remain a real data limit — they file no PP&E-purchase concept of
        # any kind, checked across every us-gaap concept and not just our spec.
        result.withheld[METRIC_FCF] = WITHHELD_NO_CAPEX
        return result

    fy = _fy_ends(fin, [c for c in (_concept_of(fin, "operating_cashflow"),
                                    _concept_of(fin, "revenue"),
                                    _concept_of(fin, "capex")) if c])

    equity_at = _instant_as_of(fin, "equity")
    lt_debt_at = _instant_as_of(fin, "long_term_debt")
    cur_debt_at = _instant_as_of(fin, "current_debt")
    cash_at = _instant_as_of(fin, "cash")
    sti_at = _instant_as_of(fin, "short_term_investments")

    shares_at, basis = _share_basis(edgar, split_report)
    result.basis = basis

    from core.valuation_anchors import _price_on_or_before

    # capex is filed as a POSITIVE outflow magnitude
    # (PaymentsToAcquirePropertyPlantAndEquipment), so FCF is a subtraction, not a sum.
    fcf: Dict[str, float] = {}
    uncomputable = {"fcf_no_capex_at_period": 0, "sales_to_capital_no_inputs": 0,
                    "fcf_yield_no_price_or_shares": 0, "margin_no_revenue": 0}

    for period_end in sorted(ocf, reverse=True):
        if period_end not in capex:
            uncomputable["fcf_no_capex_at_period"] += 1
            continue
        fcf[period_end] = ocf[period_end][0] - capex[period_end][0]

    def ptype(pe: str) -> str:
        return PERIOD_FY if pe in fy else PERIOD_TTM_Q

    for period_end in sorted(fcf, reverse=True):
        value = fcf[period_end]
        negative = value <= 0
        pt = ptype(period_end)
        comp = {"operating_cashflow": ocf[period_end][0],
                "capex": capex[period_end][0]}

        # ── FCF ───────────────────────────────────────────────────────────────
        result.points.append(SeriesPoint(
            ticker=ticker, metric=METRIC_FCF, period_end=period_end, period_type=pt,
            value=value, unit="USD", method=ocf[period_end][1],
            excluded=negative,
            exclusion_reason=EXCL_NEGATIVE_FCF if negative else None,
            components=comp))

        # ── REINVESTMENT — ruled: emitted NULL, no proxy ──────────────────────
        result.points.append(SeriesPoint(
            ticker=ticker, metric=METRIC_REINVESTMENT, period_end=period_end,
            period_type=pt, value=None, unit="USD",
            null_reason=WITHHELD_NO_DA_SPEC,
            components={"blocked_on": "no depreciation/amortization spec (H-4)"}))

        # ── FCF MARGIN — a negative margin is a real reading, not an exclusion ─
        rev = revenue.get(period_end, (None, None))[0]
        if rev and rev > 0:
            result.points.append(SeriesPoint(
                ticker=ticker, metric=METRIC_FCF_MARGIN, period_end=period_end,
                period_type=pt, value=value / rev * 100.0, unit="pct",
                method=revenue[period_end][1],
                components={**comp, "revenue": rev}))
        else:
            uncomputable["margin_no_revenue"] += 1

        # ── SALES TO CAPITAL — reinvestment duty for Phase M v1 ───────────────
        eq = equity_at(period_end)
        debt_legs = [d for d in (lt_debt_at(period_end), cur_debt_at(period_end))
                     if d is not None]
        cash_legs = [c for c in (cash_at(period_end), sti_at(period_end))
                     if c is not None]
        if rev and rev > 0 and eq is not None and debt_legs:
            invested = eq + sum(debt_legs) - sum(cash_legs)
            if invested > 0:
                result.points.append(SeriesPoint(
                    ticker=ticker, metric=METRIC_SALES_TO_CAPITAL,
                    period_end=period_end, period_type=pt, value=rev / invested,
                    unit="ratio",
                    components={"revenue": rev, "equity": eq,
                                "debt": sum(debt_legs), "cash": sum(cash_legs),
                                "invested_capital": invested}))
            else:
                uncomputable["sales_to_capital_no_inputs"] += 1
        else:
            uncomputable["sales_to_capital_no_inputs"] += 1

        # ── FCF YIELD — the only leg that touches price and shares ────────────
        shares = shares_at(period_end)
        price = _price_on_or_before(price_history or [], period_end)
        if shares and price:
            mkt_cap = price * shares
            if mkt_cap > 0:
                result.points.append(SeriesPoint(
                    ticker=ticker, metric=METRIC_FCF_YIELD, period_end=period_end,
                    period_type=pt, value=value / mkt_cap * 100.0, unit="pct",
                    basis=basis, excluded=negative,
                    exclusion_reason=EXCL_NEGATIVE_FCF if negative else None,
                    components={**comp, "price": price, "shares": shares,
                                "market_cap": mkt_cap}))
            else:
                uncomputable["fcf_yield_no_price_or_shares"] += 1
        else:
            uncomputable["fcf_yield_no_price_or_shares"] += 1

    _append_growth(result, ticker, METRIC_FCF_GROWTH, fcf, ptype)
    _append_growth(result, ticker, METRIC_REVENUE_GROWTH,
                   {k: v[0] for k, v in revenue.items()}, ptype)

    result.diagnostics = {
        "ocf_periods": len(ocf), "capex_periods": len(capex),
        "revenue_periods": len(revenue), "fcf_periods": len(fcf),
        "fy_period_ends": len(fy),
        "negative_fcf_periods": sum(1 for v in fcf.values() if v <= 0),
        "uncomputable": uncomputable,
    }
    return result


def _append_growth(result: SeriesResult, ticker: str, metric: str,
                   points: Dict[str, float], ptype: Any) -> None:
    """Year-over-year growth, matched to the period-end ~365 days back.

    A growth rate off a non-positive base is not a growth rate — MU swings through
    negative FCF, and -1.1B -> +0.9B is not "+180% growth". Those points are STORED with
    the value that falls out and flagged EXCLUDED, per ruling 2: the anchor must not read
    them, and Phase M must not be handed a series with the volatile periods quietly gone.
    """
    ends = sorted(points, reverse=True)
    for pe in ends:
        base_end = next(
            (e for e in ends
             if abs((_days_between(e, pe) or 0) - 365) <= _YOY_TOLERANCE_DAYS),
            None)
        if base_end is None:
            continue
        base = points[base_end]
        if base == 0:
            continue
        bad_base = base <= 0
        result.points.append(SeriesPoint(
            ticker=ticker, metric=metric, period_end=pe, period_type=ptype(pe),
            value=(points[pe] - base) / abs(base) * 100.0, unit="pct",
            excluded=bad_base,
            exclusion_reason=EXCL_NON_POSITIVE_BASE if bad_base else None,
            components={"current": points[pe], "base": base,
                        "base_period_end": base_end}))


def render_series(result: SeriesResult) -> str:
    """The H-1 dark readout. Per point, never a median — standing ruling from Phase G."""
    lines = [f"[H-1 FCF-SERIES] {result.ticker}  basis={result.basis}  "
             f"APPLIED=NOTHING"]
    if result.withheld:
        for k, v in result.withheld.items():
            lines.append(f"  WITHHELD {k}: {v}")
        return "\n".join(lines)
    for metric in ALL_METRICS:
        pts = result.by_metric(metric)
        if not pts:
            continue
        usable = result.anchor_usable(metric)
        excl = result.excluded_count(metric)
        fy = sum(1 for p in pts if p.period_type == PERIOD_FY)
        head = (f"  {metric:20s} {len(pts):3d} stored ({fy} FY), "
                f"{len(usable):3d} anchor-usable, {excl:3d} excluded")
        lines.append(head)
    d = result.diagnostics
    if d:
        lines.append(f"  diagnostics: {d}")
    return "\n".join(lines)


def run_dark_fcf_series(
    ticker_data: Any, edgar: Optional[EdgarData],
    splits: Optional[List[Dict]] = None,
    log: Optional[Any] = None,
    db_path: Optional[Any] = None,
) -> Optional[SeriesResult]:
    """H-1 DARK: build the FCF series, log it per metric, and persist it.

    APPLIES NOTHING. No score, E(R), grade or confidence label can move — the series is
    stored for Phase M and, at H-3, read back as the compounder lens's own-history
    anchor. It is not read by anything today.

    PERSISTS ONLY WHEN GIVEN A db_path. H-1 reclassifies this surface from "computes and
    logs" to "writes", so the destination is named by the caller rather than defaulted:
    the batch boundary passes the path its own degraded-run guard already validated, and
    a caller that names nothing gets the computation and the log with no write at all.

    Contained like every other dark surface: a failure here must not touch an evaluation
    it cannot influence.
    """
    emit = log or print
    if edgar is None:
        return None
    try:
        report = None
        if splits is not None:
            from core.corporate_actions import build_split_report
            report = build_split_report(getattr(ticker_data, "ticker", "?"), splits,
                                        edgar.financials)
        result = build_fcf_series(
            getattr(ticker_data, "ticker", "?"), edgar,
            getattr(ticker_data, "price_history", None), report)
        emit(render_series(result))
        if db_path is not None and result.points:
            from store.models import save_fundamental_series
            written, restated = save_fundamental_series(result.points, db_path=db_path)
            emit(f"[H-1 FCF-SERIES] {result.ticker} persisted: {written} new row(s), "
                 f"{restated} restatement(s) — APPLIED=NOTHING")
        return result
    except Exception as e:                              # noqa: BLE001 — see docstring
        emit(f"[H-1 FCF-SERIES] FAILED for {getattr(ticker_data, 'ticker', '?')}: "
             f"{type(e).__name__}: {e} (measurement only; evaluation unaffected)")
        return None
