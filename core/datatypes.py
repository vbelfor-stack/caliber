"""Core data types shared across the CALIBER pipeline.

TickerData is the canonical per-ticker data container. It was formerly
YFinanceData in adapters/yfinance_adapter.py; rehomed here 2026-08-07 (Phase 1 of
the yfinance teardown) so the pipeline's central type no longer lives inside a
source-specific adapter. It is feed-neutral — populated by whichever adapter runs
(FMP is primary). This module also hosts the trajectory builders the feed adapters
share.

Import direction: core.datatypes -> adapters.base only (no adapter imports it back),
so no cycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from adapters.base import (
    Confidence, Prov, TrajectoryPoint, derive_trajectory_tag, min_conf, missing_prov,
)

TODAY = date.today().isoformat()


@dataclass
class TickerData:
    ticker: str
    name: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    sic: Optional[str]           # from EDGAR lookup, may be None here

    # Business Quality
    gross_margin: Prov
    operating_margin: Prov
    profit_margin: Prov
    roe: Prov                    # returnOnEquity — ROIC proxy
    roa: Prov

    # Financial Health
    current_ratio: Prov
    debt_to_equity: Prov
    total_debt: Prov
    total_cash: Prov
    free_cashflow: Prov
    operating_cashflow: Prov

    # Growth / Forward
    revenue_growth: Prov         # YoY decimal; >1.0 is valid (e.g. 3.46 = 346%)
    trailing_pe: Prov
    forward_pe: Prov
    analyst_count: Prov
    target_mean_price: Prov

    # Valuation
    price_to_book: Prov
    ev_to_ebitda: Prov
    ev_to_revenue: Prov
    market_cap: Prov
    current_price: Prov
    enterprise_value: Prov
    fcf_yield: Prov              # computed: free_cashflow / market_cap

    # Management
    shares_outstanding: Prov
    beta: Prov

    # Raw sequences (used by Management + Growth pillars, not individually Prov-wrapped)
    earnings_history: List[Dict]     # [{epsActual, epsEstimate, epsDifference, surprisePercent}, ...]
    insider_transactions: List[Dict] # [{Transaction, Insider, Shares, Value, Text, ...}, ...]
    price_history: List[Dict]        # [{Open, High, Low, Close, Volume, date}, ...] for technicals

    # Temporal trajectory — {ttm, mrq, guided_next_q (nullable), tag}
    gross_margin_trajectory: Optional[TrajectoryPoint]     # accelerating|peaking|rolling_over|troughing|stable
    revenue_growth_trajectory: Optional[TrajectoryPoint]

    # Feed that populated this record ("fmp" live, or the fixture label). Stamped
    # into derived-Prov sources (technicals, pillar earnings/insider, trajectories)
    # so provenance reflects the true feed — EDGAR cross-check will key off this.
    feed_source: str = "unknown"

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _build_gross_margin_trajectory(
    ttm_gm: Optional[float],
    quarterly_data: Dict,
    source: str,
    as_of: str = TODAY,
) -> Optional[TrajectoryPoint]:
    """
    Build gross margin trajectory from TTM info field + quarterly_financials.
    MRQ gross margin = Gross Profit(Q0) / Total Revenue(Q0).
    """
    rev = quarterly_data.get("Total Revenue", {})
    gp = quarterly_data.get("Gross Profit", {})
    if not rev or not gp:
        return None

    cols = sorted(rev.keys(), reverse=True)  # most-recent first
    if not cols:
        return None

    # MRQ values (most recent quarter)
    col0 = cols[0]
    rev_q0 = rev.get(col0)
    gp_q0 = gp.get(col0)
    mrq_gm_val: Optional[float] = None
    mrq_as_of = col0[:10]  # trim timestamp to date

    if rev_q0 and gp_q0 and rev_q0 > 0:
        mrq_gm_val = gp_q0 / rev_q0

    ttm_prov = Prov(
        value=ttm_gm, source=source, as_of=as_of,
        confidence="medium" if ttm_gm is not None else "low",
    )
    mrq_prov = Prov(
        value=mrq_gm_val, source=f"{source}/quarterly_financials",
        as_of=mrq_as_of, confidence="medium" if mrq_gm_val is not None else "low",
    )
    guided_prov = missing_prov(f"{source}/guidance", None)

    tag = derive_trajectory_tag(
        ttm_val=ttm_gm,
        mrq_val=mrq_gm_val,
        guided_val=None,
        threshold=0.03,          # 3 percentage-points
        low_level_threshold=0.20,
    )
    tag_conf = min_conf(ttm_prov, mrq_prov)

    return TrajectoryPoint(
        ttm=ttm_prov,
        mrq=mrq_prov,
        guided_next_q=guided_prov,
        tag=tag,
        tag_confidence=tag_conf,
    )


def _build_revenue_growth_trajectory(
    ttm_growth: Optional[float],
    quarterly_data: Dict,
    source: str,
    as_of: str = TODAY,
) -> Optional[TrajectoryPoint]:
    """
    Build revenue growth trajectory.
    MRQ revenue growth = (Revenue Q0 - Revenue Q4) / |Revenue Q4| (same quarter YoY).
    """
    rev = quarterly_data.get("Total Revenue", {})
    if not rev:
        return None

    cols = sorted(rev.keys(), reverse=True)
    if len(cols) < 5:
        # Insufficient history for YoY MRQ; return TTM-only point
        ttm_prov = Prov(
            value=ttm_growth, source=source, as_of=as_of,
            confidence="medium" if ttm_growth is not None else "low",
        )
        return TrajectoryPoint(
            ttm=ttm_prov,
            mrq=missing_prov(f"{source}/quarterly_financials", None),
            guided_next_q=missing_prov(f"{source}/guidance", None),
            tag="stable",
            tag_confidence="low",
        )

    col0 = cols[0]
    col4 = cols[4]
    rev_q0 = rev.get(col0)
    rev_q4 = rev.get(col4)
    mrq_growth_val: Optional[float] = None
    mrq_as_of = col0[:10]

    if rev_q0 is not None and rev_q4 is not None and rev_q4 != 0:
        mrq_growth_val = (rev_q0 - rev_q4) / abs(rev_q4)

    ttm_prov = Prov(
        value=ttm_growth, source=source, as_of=as_of,
        confidence="medium" if ttm_growth is not None else "low",
    )
    mrq_prov = Prov(
        value=mrq_growth_val, source=f"{source}/quarterly_financials",
        as_of=mrq_as_of, confidence="medium" if mrq_growth_val is not None else "low",
    )
    guided_prov = missing_prov(f"{source}/guidance", None)

    tag = derive_trajectory_tag(
        ttm_val=ttm_growth,
        mrq_val=mrq_growth_val,
        guided_val=None,
        threshold=0.05,          # 5 percentage-points
        low_level_threshold=0.0,
    )
    tag_conf = min_conf(ttm_prov, mrq_prov)

    return TrajectoryPoint(
        ttm=ttm_prov,
        mrq=mrq_prov,
        guided_next_q=guided_prov,
        tag=tag,
        tag_confidence=tag_conf,
    )
