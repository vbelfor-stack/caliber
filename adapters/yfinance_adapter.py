"""
yfinance adapter — primary data feed.
Returns YFinanceData with Prov-wrapped fields.
Single source → medium confidence (upgrades to high if Tiingo agrees in cross_check).

Schema quirks (from schema-notes.md):
  - DataFrame column headers are pd.Timestamp objects; must str() them.
  - NaN → None at ingestion via coerce().
  - revenueGrowth is YoY decimal: 0.218 = 21.8%, 3.46 = 346%.
  - earnings_history columns: epsActual, epsEstimate, epsDifference, surprisePercent.
  - insider_transactions columns: Shares, Value, URL, Text, Insider, Position,
      Transaction, Start Date, Ownership.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from adapters.base import (
    Confidence, Prov, TrajectoryPoint, coerce, derive_trajectory_tag, min_conf, missing_prov,
)

TODAY = date.today().isoformat()
SOURCE = "yfinance"
# Single-source confidence per closed-decision: Tiingo absent → medium
_DEFAULT_CONF: Confidence = "medium"


@dataclass
class YFinanceData:
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

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _p(val: Any, as_of: str = TODAY, conf: Confidence = _DEFAULT_CONF) -> Prov:
    """Wrap a value in a yfinance Prov. NaN → None → confidence stays but value is None."""
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


def _extract_quarterly_data(qf: Any) -> Dict:
    """
    Extract {row: {col_str: float}} from a quarterly_financials DataFrame.
    Returns empty dict if unavailable.
    """
    try:
        if qf is None or (hasattr(qf, "empty") and qf.empty):
            return {}
        rows = ["Total Revenue", "Gross Profit", "Operating Income"]
        result = {}
        for row in rows:
            if row in qf.index:
                row_vals = qf.loc[row].to_dict()
                result[row] = {
                    str(k): (float(v) if isinstance(v, (int, float)) and v == v else None)
                    for k, v in row_vals.items()
                }
        return result
    except Exception:
        return {}


def _build_gross_margin_trajectory(
    ttm_gm: Optional[float],
    quarterly_data: Dict,
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
        value=ttm_gm, source=SOURCE, as_of=as_of,
        confidence="medium" if ttm_gm is not None else "low",
    )
    mrq_prov = Prov(
        value=mrq_gm_val, source=f"{SOURCE}/quarterly_financials",
        as_of=mrq_as_of, confidence="medium" if mrq_gm_val is not None else "low",
    )
    guided_prov = missing_prov(f"{SOURCE}/guidance", None)

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
            value=ttm_growth, source=SOURCE, as_of=as_of,
            confidence="medium" if ttm_growth is not None else "low",
        )
        return TrajectoryPoint(
            ttm=ttm_prov,
            mrq=missing_prov(f"{SOURCE}/quarterly_financials", None),
            guided_next_q=missing_prov(f"{SOURCE}/guidance", None),
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
        value=ttm_growth, source=SOURCE, as_of=as_of,
        confidence="medium" if ttm_growth is not None else "low",
    )
    mrq_prov = Prov(
        value=mrq_growth_val, source=f"{SOURCE}/quarterly_financials",
        as_of=mrq_as_of, confidence="medium" if mrq_growth_val is not None else "low",
    )
    guided_prov = missing_prov(f"{SOURCE}/guidance", None)

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


def _df_to_records(df: Any) -> List[Dict]:
    """Convert a pandas DataFrame to a list of dicts, handling Timestamp keys."""
    try:
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        records = df.reset_index().to_dict(orient="records")
        clean = []
        for rec in records:
            clean.append({str(k): (None if (isinstance(v, float) and __import__("math").isnan(v)) else v)
                          for k, v in rec.items()})
        return clean
    except Exception:
        return []


def fetch_yfinance(ticker: str, fixture_path: Optional[Path] = None) -> YFinanceData:
    """
    Fetch yfinance data for ticker.
    If fixture_path is provided, loads from recorded JSON (unit-test mode).
    Otherwise calls live yfinance (integration mode).
    Fails loudly with full context on any error.
    """
    if fixture_path is not None:
        return _from_fixture(ticker, fixture_path)
    return _from_live(ticker)


def _from_live(ticker: str) -> YFinanceData:
    try:
        import yfinance as yf
        import requests as _requests
    except ImportError as e:
        raise RuntimeError(f"[yfinance] package not installed — cannot fetch {ticker}. Error: {e}") from e

    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    # Custom session bypasses Yahoo Finance cloud-IP blocking (Replit, AWS, etc.)
    _session = _requests.Session()
    _session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    import time as _time
    last_exc = None
    for _attempt in range(3):
        try:
            tk = yf.Ticker(ticker, session=_session)
            info = tk.info or {}
            break
        except Exception as e:
            last_exc = e
            if _attempt < 2:
                _time.sleep(2 ** _attempt)
    else:
        raise RuntimeError(
            f"[yfinance] fetch failed for ticker={ticker}. "
            f"Error: {type(last_exc).__name__}: {last_exc}"
        ) from last_exc

    if not info or len(info) < 5:
        raise RuntimeError(
            f"[yfinance] empty or near-empty info for ticker={ticker}. "
            f"Got {len(info)} keys. Ticker may be delisted or invalid."
        )

    # Earnings history
    try:
        eh = tk.earnings_history
        earnings = _df_to_records(eh)
    except Exception:
        earnings = []

    # Insider transactions
    try:
        it = tk.insider_transactions
        insiders = _df_to_records(it)
    except Exception:
        insiders = []

    # Price history (1Y daily for technicals)
    try:
        hist = tk.history(period="1y", interval="1d")
        prices = _df_to_records(hist)
    except Exception:
        prices = []

    # Quarterly financials for trajectory computation
    try:
        qf_raw = tk.quarterly_financials
        quarterly_data = _extract_quarterly_data(qf_raw)
    except Exception:
        quarterly_data = {}

    return _build(ticker, info, earnings, insiders, prices, quarterly_data)


def _from_fixture(ticker: str, path: Path) -> YFinanceData:
    if not path.exists():
        raise RuntimeError(
            f"[yfinance] fixture not found: {path}. "
            f"Run probe.py first to record fixtures."
        )
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"[yfinance] corrupt fixture {path}: {e}") from e

    info = raw.get("info_sample", {})
    if not info:
        raise RuntimeError(f"[yfinance] fixture {path} has no info_sample key.")

    earnings = raw.get("earnings_shape", {}).get("sample", [])
    insiders = raw.get("insider_shape", {}).get("sample", [])
    prices = raw.get("price_shape", {}).get("sample", [])
    quarterly_data = raw.get("quarterly_financials_shape", {}).get("data", {})

    return _build(ticker, info, earnings, insiders, prices, quarterly_data)


def _build(ticker: str, info: Dict, earnings: List[Dict],
           insiders: List[Dict], prices: List[Dict],
           quarterly_data: Optional[Dict] = None) -> YFinanceData:
    """Construct YFinanceData from a raw info dict + supplemental lists."""
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

    return YFinanceData(
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
