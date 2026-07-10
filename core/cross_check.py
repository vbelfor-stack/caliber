"""
Cross-check + confidence engine.
Compares primary (yfinance) vs secondary (AlphaVantage) values and upgrades or
downgrades confidence according to ethos rule 1:
  - Two independent sources agree and fresh → high
  - Single source → medium (default from adapter)
  - Sources conflict → low
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

from adapters.base import Confidence, Prov

_DEFAULT_TOLERANCE_PCT = 5.0  # values within 5% are "agree"


def apply_cross_check(
    primary: Prov,
    secondary_value: Any,
    secondary_source: str,
    secondary_as_of: Optional[str],
    tolerance_pct: float = _DEFAULT_TOLERANCE_PCT,
    same_day_tol_pct: Optional[float] = None,
) -> Prov:
    """
    Given a primary Prov and a secondary value from an independent source:
      - If they agree within tolerance: upgrade confidence to high.
      - If they conflict: downgrade to low, logging both values + as-of stamps.
      - If secondary_value is None: leave primary unchanged (single-source stays medium).

    same_day_tol_pct: when both sources share the same as_of date, use this tighter
      tolerance instead of tolerance_pct. Intended for price-derived fields (market_cap,
      trailing_pe) where intraday movements are small but inter-day gaps are not.
      Genuine conflict beyond either tolerance still degrades to LOW.
    """
    if primary.is_missing():
        return primary
    if secondary_value is None:
        return primary

    # Resolve effective tolerance: tighten for same-day price-derived fields
    effective_tol = tolerance_pct
    if same_day_tol_pct is not None and primary.as_of and secondary_as_of:
        if primary.as_of[:10] == secondary_as_of[:10]:
            effective_tol = same_day_tol_pct

    try:
        p = float(primary.value)
        s = float(secondary_value)
    except (TypeError, ValueError):
        # Non-numeric: string equality check
        agree = str(primary.value).strip().lower() == str(secondary_value).strip().lower()
        conf: Confidence = "high" if agree else "low"
        src = (
            f"{primary.source}+{secondary_source}" if agree
            else f"{primary.source}[{primary.value}@{primary.as_of or '?'}]"
                 f" vs {secondary_source}[{secondary_value}@{secondary_as_of or '?'}] CONFLICT"
        )
        return Prov(value=primary.value, source=src, as_of=primary.as_of, confidence=conf)

    if p == 0:
        pct_diff = 0.0 if s == 0 else 100.0
    else:
        pct_diff = abs(p - s) / abs(p) * 100.0

    if pct_diff <= effective_tol:
        conf = "high"
        src = f"{primary.source}+{secondary_source}"
    else:
        conf = "low"
        src = (
            f"{primary.source}[{p:.4g}@{primary.as_of or '?'}]"
            f" vs {secondary_source}[{s:.4g}@{secondary_as_of or '?'}] CONFLICT"
        )

    return Prov(value=primary.value, source=src, as_of=primary.as_of, confidence=conf)


def apply_av_cross_checks(yf: "YFinanceData", av: "AlphaVantageData") -> "YFinanceData":
    """
    Apply AlphaVantage secondary values to yfinance fields via apply_cross_check.
    Returns a new YFinanceData with updated confidences (high on agreement, low on conflict).
    Fields with no AV equivalent are left unchanged (single-source stays medium).

    Tolerance notes:
      - margins / ratios: 5% relative (default)
      - market_cap: 10% — share price can drift between fetch times
    """
    # Import here to avoid circular at module load (core imports adapters.base only)
    from adapters.alphavantage_adapter import AlphaVantageData  # noqa: F401
    from adapters.yfinance_adapter import YFinanceData           # noqa: F401

    src = "alphavantage"
    as_of = av.as_of

    _SAME_DAY_TOL = 3.0   # price-derived fields: ±3% when both sources share same as-of

    def _cc(
        prov: Prov,
        av_val: Optional[float],
        tol: float = _DEFAULT_TOLERANCE_PCT,
        same_day_tol: Optional[float] = None,
    ) -> Prov:
        return apply_cross_check(
            prov, av_val, src, as_of,
            tolerance_pct=tol,
            same_day_tol_pct=same_day_tol,
        )

    return replace(
        yf,
        # Fundamental ratios: standard 5% tolerance
        gross_margin=_cc(yf.gross_margin, av.gross_margin),
        operating_margin=_cc(yf.operating_margin, av.operating_margin),
        roe=_cc(yf.roe, av.roe),
        roa=_cc(yf.roa, av.roa),
        forward_pe=_cc(yf.forward_pe, av.forward_pe),
        price_to_book=_cc(yf.price_to_book, av.price_to_book),
        ev_to_ebitda=_cc(yf.ev_to_ebitda, av.ev_to_ebitda),
        ev_to_revenue=_cc(yf.ev_to_revenue, av.ev_to_revenue),
        shares_outstanding=_cc(yf.shares_outstanding, av.shares_outstanding),
        # Price-derived fields: same-day ±3%, wider inter-day fallback
        trailing_pe=_cc(yf.trailing_pe, av.trailing_pe, same_day_tol=_SAME_DAY_TOL),
        market_cap=_cc(yf.market_cap, av.market_cap, tol=10.0, same_day_tol=_SAME_DAY_TOL),
        beta=_cc(yf.beta, av.beta, tol=10.0, same_day_tol=_SAME_DAY_TOL),
    )


def apply_staleness_penalty(prov: Prov, days_old: int, stale_threshold: int = 90) -> Prov:
    """
    If data is older than stale_threshold days, cap confidence at medium.
    Undated data (as_of=None) is always medium at best.
    """
    if prov.as_of is None:
        if prov.confidence == "high":
            return Prov(value=prov.value, source=prov.source,
                        as_of=prov.as_of, confidence="medium")
        return prov
    if days_old > stale_threshold and prov.confidence == "high":
        return Prov(value=prov.value, source=prov.source,
                    as_of=prov.as_of, confidence="medium")
    return prov
