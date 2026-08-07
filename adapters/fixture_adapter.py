"""Recorded-fixture loader → TickerData (offline path).

Builds a TickerData from a recorded JSON fixture. Used by the test suite, smoke.py,
and batch fixture mode. The live pipeline is FMP-only (yfinance teardown 2026-08-07);
this module contains NO live network code.

The recorded fixtures are in the historical yfinance info-dict shape
(info_sample / earnings_shape / price_shape / quarterly_financials_shape), so the
Prov `source` stamps here read "yfinance" — an accurate descriptor of where the
RECORDED data originally came from, not a live dependency.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from adapters.base import Confidence, Prov, coerce, missing_prov
from core.datatypes import (
    TickerData, _build_gross_margin_trajectory, _build_revenue_growth_trajectory,
)

TODAY = date.today().isoformat()
SOURCE = "yfinance"   # accurate label for the recorded fixture data (see module docstring)
_DEFAULT_CONF: Confidence = "medium"


def _p(val: Any, as_of: str = TODAY, conf: Confidence = _DEFAULT_CONF) -> Prov:
    """Wrap a recorded value in a Prov. NaN → None → confidence drops to low."""
    v = coerce(val)
    if v is None:
        conf = "low"
    return Prov(value=v, source=SOURCE, as_of=as_of, confidence=conf)


def _compute_fcf_yield(fcf: Prov, mktcap: Prov) -> Prov:
    if fcf.is_missing() or mktcap.is_missing() or mktcap.value == 0:
        return missing_prov(SOURCE, TODAY)
    try:
        val = fcf.value / mktcap.value
        conf: Confidence = "low" if (fcf.confidence == "low" or mktcap.confidence == "low") else "medium"
        return Prov(value=val, source=SOURCE, as_of=TODAY, confidence=conf)
    except Exception:
        return missing_prov(SOURCE, TODAY)


def fetch_fixture(ticker: str, fixture_path: Path) -> TickerData:
    """Load a recorded ticker fixture (JSON) and build TickerData. Fails loud."""
    if not fixture_path.exists():
        raise RuntimeError(
            f"[fixture] fixture not found: {fixture_path}. Run probe.py to record fixtures."
        )
    try:
        with open(fixture_path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"[fixture] corrupt fixture {fixture_path}: {e}") from e

    info = raw.get("info_sample", {})
    if not info:
        raise RuntimeError(f"[fixture] {fixture_path} has no info_sample key.")

    earnings = raw.get("earnings_shape", {}).get("sample", [])
    insiders = raw.get("insider_shape", {}).get("sample", [])
    prices = raw.get("price_shape", {}).get("sample", [])
    quarterly_data = raw.get("quarterly_financials_shape", {}).get("data", {})

    return _build(ticker, info, earnings, insiders, prices, quarterly_data)


def _build(ticker: str, info: Dict, earnings: List[Dict],
           insiders: List[Dict], prices: List[Dict],
           quarterly_data: Optional[Dict] = None) -> TickerData:
    """Construct TickerData from a recorded info dict + supplemental lists."""
    if quarterly_data is None:
        quarterly_data = {}

    def get(key: str) -> Prov:
        return _p(info.get(key))

    fcf = get("freeCashflow")
    mktcap = get("marketCap")
    fcf_yield = _compute_fcf_yield(fcf, mktcap)

    # Build trajectory points from quarterly data
    ttm_gm = coerce(info.get("grossMargins"))
    ttm_rg = coerce(info.get("revenueGrowth"))
    gm_traj = _build_gross_margin_trajectory(ttm_gm, quarterly_data)
    rg_traj = _build_revenue_growth_trajectory(ttm_rg, quarterly_data)

    return TickerData(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        sic=None,  # populated by EDGAR adapter or lens selector

        # Business Quality
        gross_margin=get("grossMargins"),
        operating_margin=get("operatingMargins"),
        profit_margin=get("profitMargins"),
        roe=get("returnOnEquity"),
        roa=get("returnOnAssets"),

        # Financial Health
        current_ratio=get("currentRatio"),
        debt_to_equity=get("debtToEquity"),
        total_debt=get("totalDebt"),
        total_cash=get("totalCash"),
        free_cashflow=fcf,
        operating_cashflow=get("operatingCashflow"),

        # Growth / Forward
        revenue_growth=get("revenueGrowth"),
        trailing_pe=get("trailingPE"),
        forward_pe=get("forwardPE"),
        analyst_count=get("numberOfAnalystOpinions"),
        target_mean_price=get("targetMeanPrice"),

        # Valuation
        price_to_book=get("priceToBook"),
        ev_to_ebitda=get("enterpriseToEbitda"),
        ev_to_revenue=get("enterpriseToRevenue"),
        market_cap=mktcap,
        current_price=get("currentPrice"),
        enterprise_value=get("enterpriseValue"),
        fcf_yield=fcf_yield,

        # Management
        shares_outstanding=get("sharesOutstanding"),
        beta=get("beta"),

        # Raw sequences
        earnings_history=earnings,
        insider_transactions=insiders,
        price_history=prices,

        # Temporal trajectory
        gross_margin_trajectory=gm_traj,
        revenue_growth_trajectory=rg_traj,
    )
