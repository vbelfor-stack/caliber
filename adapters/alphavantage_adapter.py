"""
AlphaVantage adapter — secondary feed for cross-check confidence upgrades.

Endpoint used:
  OVERVIEW — fundamentals (margins, PE, P/B, EV ratios, beta, market cap, price)

AlphaVantage quirks:
  - Missing values returned as the string "None", "-", or "" — NOT JSON null.
  - All numeric values returned as strings — must float() every field.
  - Rate limit: 25 req/day free tier; use sparingly in batch.

Key: ALPHAVANTAGE_API_KEY env var. If absent, fetch_alphavantage() returns None
and cross-check degrades silently (single-source stays medium).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

TODAY = date.today().isoformat()
SOURCE = "alphavantage"
_OVERVIEW_URL = "https://www.alphavantage.co/query"
_TIMEOUT = 15  # seconds


def _av_float(val: Any) -> Optional[float]:
    """Convert an AV string value to float. Returns None for 'None', '-', '', 'N/A'."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("None", "-", "", "N/A", "0"):
        # "0" is a valid numeric value but AV sometimes returns it for missing ratios;
        # keep it as a real zero only for fields where 0 is meaningful — callers decide.
        pass
    if s in ("None", "-", "", "N/A"):
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


@dataclass
class AlphaVantageData:
    """Secondary fundamentals from AlphaVantage OVERVIEW endpoint."""
    ticker: str
    gross_margin: Optional[float]       # GrossProfitTTM / RevenueTTM
    operating_margin: Optional[float]   # OperatingMarginTTM
    roe: Optional[float]                # ReturnOnEquityTTM
    roa: Optional[float]                # ReturnOnAssetsTTM
    trailing_pe: Optional[float]        # TrailingPE
    forward_pe: Optional[float]         # ForwardPE
    price_to_book: Optional[float]      # PriceToBookRatio
    ev_to_ebitda: Optional[float]       # EVToEBITDA
    ev_to_revenue: Optional[float]      # EVToRevenue
    beta: Optional[float]               # Beta
    market_cap: Optional[float]         # MarketCapitalization
    shares_outstanding: Optional[float] # SharesOutstanding
    as_of: str = TODAY


def _parse_overview(ticker: str, overview: dict) -> AlphaVantageData:
    """Parse an AV OVERVIEW response dict into AlphaVantageData."""
    revenue = _av_float(overview.get("RevenueTTM"))
    gross_profit = _av_float(overview.get("GrossProfitTTM"))
    gross_margin: Optional[float] = None
    if revenue and gross_profit and revenue > 0:
        gross_margin = gross_profit / revenue

    return AlphaVantageData(
        ticker=ticker,
        gross_margin=gross_margin,
        operating_margin=_av_float(overview.get("OperatingMarginTTM")),
        roe=_av_float(overview.get("ReturnOnEquityTTM")),
        roa=_av_float(overview.get("ReturnOnAssetsTTM")),
        trailing_pe=_av_float(overview.get("TrailingPE")),
        forward_pe=_av_float(overview.get("ForwardPE")),
        price_to_book=_av_float(overview.get("PriceToBookRatio")),
        ev_to_ebitda=_av_float(overview.get("EVToEBITDA")),
        ev_to_revenue=_av_float(overview.get("EVToRevenue")),
        beta=_av_float(overview.get("Beta")),
        market_cap=_av_float(overview.get("MarketCapitalization")),
        shares_outstanding=_av_float(overview.get("SharesOutstanding")),
    )


def fetch_alphavantage(
    ticker: str,
    fixture_path: Optional[Path] = None,
) -> Optional[AlphaVantageData]:
    """
    Fetch AlphaVantage OVERVIEW for ticker.
    Returns None (not an error) if the API key is absent — callers degrade gracefully.
    Raises RuntimeError on network failure or malformed response.
    fixture_path: load from recorded JSON instead of live call (unit-test mode).
    """
    if fixture_path is not None:
        return _from_fixture(ticker, fixture_path)
    return _from_live(ticker)


def _from_live(ticker: str) -> Optional[AlphaVantageData]:
    api_key = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
    if not api_key:
        return None  # graceful degrade — single-source stays medium

    try:
        import requests as _requests
    except ImportError as exc:
        raise RuntimeError(
            "[alphavantage] requests package not installed — cannot fetch."
        ) from exc

    try:
        resp = _requests.get(
            _OVERVIEW_URL,
            params={"function": "OVERVIEW", "symbol": ticker, "apikey": api_key},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"[alphavantage] OVERVIEW fetch failed for ticker={ticker}. "
            f"Error: {type(exc).__name__}: {exc}"
        ) from exc

    if not data or "Symbol" not in data:
        # AV returns {"Note": "..."} when rate-limited, {"Information": "..."} for bad key
        note = data.get("Note") or data.get("Information") or "empty response"
        raise RuntimeError(
            f"[alphavantage] OVERVIEW returned no usable data for {ticker}. "
            f"Response: {str(note)[:200]}"
        )

    return _parse_overview(ticker, data)


def _from_fixture(ticker: str, path: Path) -> AlphaVantageData:
    if not path.exists():
        raise RuntimeError(
            f"[alphavantage] fixture not found: {path}. "
            f"Run probe_mu_edgar.py or record manually."
        )
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"[alphavantage] corrupt fixture {path}: {exc}"
        ) from exc

    overview = raw.get("overview", {})
    if not overview:
        raise RuntimeError(
            f"[alphavantage] fixture {path} has no 'overview' key."
        )
    return _parse_overview(ticker, overview)
