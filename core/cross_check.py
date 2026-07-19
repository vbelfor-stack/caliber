"""
Cross-check + confidence engine.
Compares a primary value against a secondary value from an independent source and
upgrades or downgrades confidence according to ethos rule 1:
  - Two independent sources agree and fresh → high
  - Single source → medium (default from adapter)
  - Sources conflict → low

Note: no secondary feed is currently wired in (the AlphaVantage cross-check was
removed). apply_cross_check remains the generic engine; with a single source every
field stays at medium confidence.
"""
from __future__ import annotations

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
