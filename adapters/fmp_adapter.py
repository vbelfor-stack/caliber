"""
FMP (Financial Modeling Prep) adapter — primary data feed.
Returns TickerData populated from FMP stable API.
Source tag: "fmp". Default confidence: medium.

Endpoints used (all under https://financialmodelingprep.com/stable/):
  profile               → price, marketCap, beta, sector, industry, name
  ratios-ttm            → margins, current_ratio, D/E, trailing PE, P/B
  key-metrics-ttm       → ROE, ROA, EV metrics, FCF yield
  income-statement      → revenue growth, quarterly trajectory
  balance-sheet         → total_debt, total_cash
  cash-flow-statement   → freeCashFlow, operatingCashFlow
  historical-price-eod  → OHLCV for technicals (1Y)
  earnings              → EPS actual vs estimated (beat rate)
  analyst-estimates     → forward EPS → forward PE; analyst count
  price-target-summary  → target mean price, analyst count
  shares-float          → shares outstanding

FMP schema notes:
  - All values are Python native types (int/float/str/None) — no string sentinels
  - debtToEquityRatioTTM differs from the old yfinance field in TWO INDEPENDENT WAYS.
    Both must be held in mind; fixing one does not touch the other.
      (a) DEFINITION — FMP's is *net* D/E (netDebt/equity), yfinance's was gross
          (totalDebt/equity). May trigger CONFLICT in cross-check; expected. This is
          the same mismatch E-4 records against EDGAR (FMP-NET vs EDGAR-GROSS), and
          no period matching can fix it.
      (b) SCALE — FMP publishes a RATIO (0.672), yfinance published a PERCENT (67.2).
          The pillar ladder is in PERCENT, so the raw ratio scored as near-zero
          leverage for every issuer between 2026-08-07 and 2026-08-15. NORMALISED AT
          THIS BOUNDARY by _ratio_to_percent — see that function for the full defect
          history. Consumers receive PERCENT.
  - grossProfitMarginTTM is decimal: 0.726 = 72.6%
  - price_history list is sorted newest→oldest by FMP; we keep that order
  - earnings list: epsActual=None for future quarters (not yet reported)
  - forward_pe computed as: quote_price / next_year_epsAvg from analyst-estimates
  - income-statement annual: index 0 = most recent completed fiscal year
"""
from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from adapters.base import (
    Confidence, Prov, TrajectoryPoint, coerce, min_conf, missing_prov,
    derive_trajectory_tag,
)
from core.datatypes import TickerData

TODAY_STR: str  # set at import from caller; module-level default below
from datetime import date as _date, timedelta
TODAY_STR = _date.today().isoformat()

SOURCE = "fmp"
FMP_BASE = "https://financialmodelingprep.com/stable"
_TIMEOUT = 15
_DEFAULT_CONF: Confidence = "medium"


def _p(val: Any, as_of: str = TODAY_STR, conf: Confidence = _DEFAULT_CONF) -> Prov:
    v = coerce(val)
    if v is None:
        conf = "low"
    return Prov(value=v, source=SOURCE, as_of=as_of, confidence=conf)


def _ratio_to_percent(val: Any) -> Optional[float]:
    """FMP's D/E is a RATIO; score_financial_health's ladder is in PERCENT. Convert here.

    THE DEFECT THIS EXISTS TO CLOSE (production, 2026-08-07 -> 2026-08-15). The leverage
    ladder in core/pillars.py reads `de <= 30 -> 3 pts` and renders `f"{de:.0f}%"` — it was
    calibrated when yfinance was the feed, and yfinance published D/E as a PERCENT (V:
    67.233). FMP publishes the RATIO (V: 0.672331). When the yfinance teardown made FMP the
    sole feed the raw ratio started flowing into the percent ladder unchanged, so NOTHING
    REALISTIC EVER EXCEEDED 30 and every issuer collected the full 3 of 3 leverage points.
    The whole component was inert for a week, and the recorded evidence is in the live
    armed pass of 2026-08-09: V's real ~67% leverage is filed as "debt/equity 1%".

    NORMALISE AT THE ADAPTER BOUNDARY, not in the ladder (ruled 2026-08-15): the percent
    convention is also what the rationale string prints and what the E-4 net-vs-gross note
    is written in, so the units belong to the field, not to one consumer of it.

    NOTE this is a SCALE fix only. The SEPARATE, KNOWN definitional difference stands:
    FMP's debtToEquityRatioTTM is NET of cash while yfinance's was gross, so a converted
    FMP figure still will not equal the old yfinance one (GOOG ~17.6% net vs ~20.0% gross).
    Two different discrepancies on one field; this closes the units one.
    """
    v = coerce(val)
    return None if v is None else v * 100.0


def _get(endpoint: str, key: str) -> Any:
    import requests as _req
    sep = "&" if "?" in endpoint else "?"
    url = f"{FMP_BASE}/{endpoint}{sep}apikey={key}"
    r = _req.get(url, timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "Error Message" in data:
        raise RuntimeError(f"[fmp] API error: {data['Error Message']}")
    return data


def _safe_get(endpoint: str, key: str, default: Any = None) -> Any:
    try:
        return _get(endpoint, key)
    except Exception:
        return default


# ── Sector P/E snapshot (Phase D, market anchor) ──────────────────────────────
# One call serves every ticker on an exchange for a day, so it is cached per
# (date, exchange) rather than fetched per evaluation. The snapshot is published per
# TRADING day — a weekend date returns an empty list, so the request walks back to the
# most recent weekday rather than reporting "no sector data" on a Sunday run.
_SECTOR_PE_CACHE: Dict[Tuple[str, str], Dict[str, float]] = {}
_SECTOR_PE_MAX_LOOKBACK_DAYS = 5


def fetch_sector_pe(exchange: str, as_of: Optional[str] = None) -> Dict[str, float]:
    """{sector_name: pe} for one exchange, or {} when unavailable.

    Advisory data for a dark measurement phase: it returns empty rather than raising, and
    the caller records the anchor as unavailable. It is not a pipeline input yet.
    """
    as_of = as_of or TODAY_STR
    cache_key = (as_of, exchange.upper())
    if cache_key in _SECTOR_PE_CACHE:
        return _SECTOR_PE_CACHE[cache_key]

    key = os.environ.get("FMP_API_KEY", "")
    out: Dict[str, float] = {}
    if key:
        day = _date.fromisoformat(as_of[:10])
        for back in range(_SECTOR_PE_MAX_LOOKBACK_DAYS + 1):
            probe = (day - timedelta(days=back)).isoformat()
            rows = _safe_get(
                f"sector-pe-snapshot?date={probe}&exchange={exchange}", key, [])
            if rows:
                out = {
                    r["sector"]: float(r["pe"]) for r in rows
                    if r.get("sector") and r.get("pe") is not None
                }
                break
    _SECTOR_PE_CACHE[cache_key] = out
    return out


_SPLITS_CACHE: Dict[str, Optional[List[Dict[str, Any]]]] = {}


def _splits_from_rows(rows: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        num, den = coerce(row.get("numerator")), coerce(row.get("denominator"))
        ex = str(row.get("date", ""))[:10]
        if not ex or not num or not den:
            continue
        out.append({"ex_date": ex, "ratio": num / den,
                    "numerator": num, "denominator": den})
    out.sort(key=lambda r: r["ex_date"], reverse=True)
    return out


def fetch_splits(ticker: str,
                 fixture_path: Optional[Path] = None) -> Optional[List[Dict[str, Any]]]:
    """[{ex_date, ratio}, ...] newest first. **None means UNKNOWN, [] means none exist.**

    That distinction is the whole contract. The restated own-history series has no
    truncation to fall back on, so an empty list read as "this issuer never split" when it
    really meant "we could not find out" reintroduces the artifact Phase G removes (GOOG
    2022-03-31 at 81.02%). Callers pass None straight through to a refusal.

    A fixture recorded BEFORE splits joined the payload has no `splits` key and therefore
    returns None — genuinely no split data, so the offline run refuses and keeps the
    truncated series. A re-recorded fixture carries the key and behaves exactly as live.

    THE EX-DATE IS WHY THIS CALL EXISTS AT ALL. EDGAR corroborates the RATIO better than
    FMP does (see core/corporate_actions), but it dates a split to a declaration or record
    date, and the only date that matches the basis FMP adjusted its OWN price series on is
    FMP's ex-date. Pairing an EDGAR date with an FMP-adjusted price would reintroduce the
    basis mismatch Phase G exists to remove.

    Never raises: a lookup failure degrades to None, i.e. to the truncation behaviour
    (flagged), rather than taking down an evaluation.
    """
    t = ticker.upper()
    if fixture_path is not None:
        if not fixture_path.exists():
            raise RuntimeError(f"[fmp] fixture not found: {fixture_path}")
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        if "splits" not in raw:
            return None            # fixture predates the splits capture — UNKNOWN
        return _splits_from_rows(raw["splits"])
    if t in _SPLITS_CACHE:
        return _SPLITS_CACHE[t]
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        return None
    out = _splits_from_rows(_safe_get(f"splits?symbol={t}", key, []))
    _SPLITS_CACHE[t] = out
    return out


def _first(lst: Any, default: Optional[Dict] = None) -> Dict:
    if isinstance(lst, list) and lst:
        return lst[0]
    return default or {}


def _quarterly_to_map(income_q: List[Dict]) -> Dict[str, Dict[str, Optional[float]]]:
    """Convert FMP quarterly income list to the map format trajectory helpers expect."""
    rev: Dict[str, Optional[float]] = {}
    gp: Dict[str, Optional[float]] = {}
    for row in income_q:
        d = str(row.get("date", ""))[:10]
        if not d:
            continue
        rev[d] = coerce(row.get("revenue"))
        gp[d] = coerce(row.get("grossProfit"))
    return {"Total Revenue": rev, "Gross Profit": gp}


def _build_gm_trajectory(ttm_gm: Optional[float], income_q: List[Dict]) -> Optional[TrajectoryPoint]:
    from core.datatypes import _build_gross_margin_trajectory
    qdata = _quarterly_to_map(income_q)
    return _build_gross_margin_trajectory(ttm_gm, qdata, "fmp")


def _build_rg_trajectory(ttm_rg: Optional[float], income_q: List[Dict]) -> Optional[TrajectoryPoint]:
    from core.datatypes import _build_revenue_growth_trajectory
    qdata = _quarterly_to_map(income_q)
    return _build_revenue_growth_trajectory(ttm_rg, qdata, "fmp")


def _compute_revenue_growth(income_annual: List[Dict]) -> Optional[float]:
    if len(income_annual) < 2:
        return None
    r0 = coerce(income_annual[0].get("revenue"))
    r1 = coerce(income_annual[1].get("revenue"))
    if r0 is None or r1 is None or r1 == 0:
        return None
    return (r0 - r1) / abs(r1)


def _earnings_to_history(earnings: List[Dict]) -> List[Dict]:
    """Convert FMP earnings to the format CALIBER's Management pillar expects."""
    result = []
    for row in earnings:
        actual = coerce(row.get("epsActual"))
        est = coerce(row.get("epsEstimated"))
        if actual is None or est is None:
            continue  # skip future quarters
        diff = actual - est
        surprise = (diff / abs(est) * 100) if est != 0 else 0.0
        result.append({
            "epsActual": actual,
            "epsEstimate": est,
            "epsDifference": diff,
            "surprisePercent": surprise,
        })
    return result


def _price_history_to_records(hist: List[Dict]) -> List[Dict]:
    """Normalise FMP OHLCV records to the format technicals expects."""
    records = []
    for row in hist:
        records.append({
            "Open": coerce(row.get("open")),
            "High": coerce(row.get("high")),
            "Low": coerce(row.get("low")),
            "Close": coerce(row.get("close")),
            "Volume": coerce(row.get("volume")),
            "date": str(row.get("date", ""))[:10],
        })
    return records


def _build(
    ticker: str,
    profile: Dict,
    ratios: Dict,
    metrics: Dict,
    income_annual: List[Dict],
    income_q: List[Dict],
    balance: Dict,
    cashflow: Dict,
    price_history: List[Dict],
    earnings: List[Dict],
    analyst_est: List[Dict],
    price_target: Dict,
    shares_float: Dict,
) -> TickerData:

    as_of = TODAY_STR

    # ── Identity ──────────────────────────────────────────────────────────
    current_price_val = coerce(profile.get("price"))
    income0 = _first(income_annual)
    income0_date = str(income0.get("date", as_of))[:10]

    # ── Business Quality ──────────────────────────────────────────────────
    gross_margin = _p(ratios.get("grossProfitMarginTTM"))
    operating_margin = _p(ratios.get("operatingProfitMarginTTM"))
    profit_margin = _p(ratios.get("netProfitMarginTTM"))
    roe = _p(metrics.get("returnOnEquityTTM"))
    roa = _p(metrics.get("returnOnAssetsTTM"))

    # ── Financial Health ──────────────────────────────────────────────────
    current_ratio = _p(ratios.get("currentRatioTTM"))
    debt_to_equity = _p(_ratio_to_percent(ratios.get("debtToEquityRatioTTM")))
    total_debt = _p(balance.get("totalDebt"), as_of=income0_date)
    total_cash = _p(balance.get("cashAndShortTermInvestments"), as_of=income0_date)
    free_cashflow = _p(cashflow.get("freeCashFlow"), as_of=income0_date)
    operating_cashflow = _p(cashflow.get("netCashProvidedByOperatingActivities"), as_of=income0_date)

    # ── Growth / Forward ──────────────────────────────────────────────────
    revenue_growth_val = _compute_revenue_growth(income_annual)
    revenue_growth = _p(revenue_growth_val)

    trailing_pe = _p(ratios.get("priceToEarningsRatioTTM"))

    # Forward PE: price / next-year EPS estimate
    forward_pe_val: Optional[float] = None
    ana0 = _first(analyst_est)
    eps_avg = coerce(ana0.get("epsAvg"))
    if current_price_val and eps_avg and eps_avg > 0:
        forward_pe_val = current_price_val / eps_avg
    forward_pe = _p(forward_pe_val)

    # Analyst count + target price from price-target-summary
    analyst_count_val = coerce(price_target.get("lastMonthCount"))
    target_mean_val = coerce(price_target.get("lastMonthAvgPriceTarget"))
    analyst_count = _p(analyst_count_val)
    target_mean_price = _p(target_mean_val)

    # ── Valuation ────────────────────────────────────────────────────────
    price_to_book = _p(ratios.get("priceToBookRatioTTM"))
    ev_to_ebitda = _p(metrics.get("evToEBITDATTM"))
    ev_to_revenue = _p(metrics.get("evToSalesTTM"))
    market_cap = _p(metrics.get("marketCap"))
    current_price = _p(current_price_val)
    enterprise_value = _p(metrics.get("enterpriseValueTTM"))
    fcf_yield = _p(metrics.get("freeCashFlowYieldTTM"))

    # ── Management ───────────────────────────────────────────────────────
    shares_outstanding = _p(shares_float.get("outstandingShares"))
    beta = _p(profile.get("beta"))

    # ── Raw sequences ────────────────────────────────────────────────────
    earnings_history = _earnings_to_history(earnings)
    insider_transactions: List[Dict] = []  # FMP stable has no free insider endpoint
    price_hist_records = _price_history_to_records(price_history)

    # ── Trajectories ─────────────────────────────────────────────────────
    gm_traj = _build_gm_trajectory(gross_margin.value, income_q)
    rg_traj = _build_rg_trajectory(revenue_growth_val, income_q)

    return TickerData(
        ticker=ticker,
        name=profile.get("companyName"),
        sector=profile.get("sector"),
        industry=profile.get("industry"),
        exchange=profile.get("exchange"),
        sic=None,  # populated by EDGAR adapter
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        profit_margin=profit_margin,
        roe=roe,
        roa=roa,
        current_ratio=current_ratio,
        debt_to_equity=debt_to_equity,
        total_debt=total_debt,
        total_cash=total_cash,
        free_cashflow=free_cashflow,
        operating_cashflow=operating_cashflow,
        revenue_growth=revenue_growth,
        trailing_pe=trailing_pe,
        forward_pe=forward_pe,
        analyst_count=analyst_count,
        target_mean_price=target_mean_price,
        price_to_book=price_to_book,
        ev_to_ebitda=ev_to_ebitda,
        ev_to_revenue=ev_to_revenue,
        market_cap=market_cap,
        current_price=current_price,
        enterprise_value=enterprise_value,
        fcf_yield=fcf_yield,
        shares_outstanding=shares_outstanding,
        beta=beta,
        earnings_history=earnings_history,
        insider_transactions=insider_transactions,
        price_history=price_hist_records,
        gross_margin_trajectory=gm_traj,
        revenue_growth_trajectory=rg_traj,
        feed_source="fmp",
    )


def fetch_fmp(ticker: str, fixture_path: Optional[Path] = None) -> TickerData:
    """
    Fetch FMP data for ticker.
    fixture_path → offline unit-test mode (loads from JSON file).
    Otherwise calls live FMP stable API.
    """
    if fixture_path is not None:
        return _from_fixture(ticker, fixture_path)
    return _from_live(ticker)


def fetch_payload(ticker: str) -> Dict[str, Any]:
    """Every live FMP response for one ticker, keyed as the fixture format stores them.

    Single source of truth for the endpoint set: the live path, the fixture path and the
    fixture RECORDER all go through this shape, so a recorded fixture cannot drift from
    what the live adapter actually requests.
    """
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        raise RuntimeError(f"[fmp] FMP_API_KEY not set — cannot fetch {ticker}")

    warnings.filterwarnings("ignore", category=FutureWarning)

    try:
        profile_raw = _get(f"profile?symbol={ticker}", key)
        if not profile_raw:
            raise RuntimeError(f"[fmp] empty profile for {ticker} — ticker may be invalid")

        return {
            "profile": profile_raw,
            "ratios_ttm": _safe_get(f"ratios-ttm?symbol={ticker}", key, []),
            "key_metrics_ttm": _safe_get(f"key-metrics-ttm?symbol={ticker}", key, []),
            "income_annual": _safe_get(
                f"income-statement?symbol={ticker}&period=annual&limit=4", key, []),
            "income_q": _safe_get(
                f"income-statement?symbol={ticker}&period=quarter&limit=8", key, []),
            "balance": _safe_get(
                f"balance-sheet-statement?symbol={ticker}&period=annual&limit=1", key, []),
            "cashflow": _safe_get(
                f"cash-flow-statement?symbol={ticker}&period=annual&limit=1", key, []),
            "price_history": _safe_get(
                f"historical-price-eod/full?symbol={ticker}&limit=365", key, []),
            "earnings": _safe_get(f"earnings?symbol={ticker}&limit=8", key, []),
            "analyst_est": _safe_get(
                f"analyst-estimates?symbol={ticker}&limit=3&period=annual", key, []),
            "price_target": _safe_get(f"price-target-summary?symbol={ticker}", key, []),
            "shares_float": _safe_get(f"shares-float?symbol={ticker}", key, []),
            # Phase G: part of the ONE payload production requests, so the recorder
            # captures it and an offline run cannot drift from what live asks for.
            "splits": _safe_get(f"splits?symbol={ticker}", key, []),
        }
    except Exception as e:
        raise RuntimeError(
            f"[fmp] fetch failed for ticker={ticker}. "
            f"Error: {type(e).__name__}: {e}"
        ) from e


def _from_payload(ticker: str, raw: Dict[str, Any]) -> TickerData:
    """Build TickerData from a payload, live or recorded — one code path for both."""
    return _build(
        ticker,
        _first(raw.get("profile") or []),
        _first(raw.get("ratios_ttm") or []),
        _first(raw.get("key_metrics_ttm") or []),
        raw.get("income_annual") or [],
        raw.get("income_q") or [],
        _first(raw.get("balance") or []),
        _first(raw.get("cashflow") or []),
        raw.get("price_history") or [],
        raw.get("earnings") or [],
        raw.get("analyst_est") or [],
        _first(raw.get("price_target") or []),
        _first(raw.get("shares_float") or []),
    )


def _from_live(ticker: str) -> TickerData:
    return _from_payload(ticker, fetch_payload(ticker))


def _from_fixture(ticker: str, path: Path) -> TickerData:
    if not path.exists():
        raise RuntimeError(f"[fmp] fixture not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"[fmp] corrupt fixture {path}: {e}") from e
    return _from_payload(ticker, raw)
