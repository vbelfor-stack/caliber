"""
Technicals — timing overlay only, per ethos rule 6.
NOT a pillar. Never lifts a broken company's verdict.
Volume confirmation: breakout on ≥1.5× 30-day avg volume = conviction; thin = noise.
Output is separate from pillar scores; flags contradiction with fundamentals if present.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from adapters.base import Confidence, Prov, missing_prov

SOURCE = "yfinance/price_history"
TODAY_STR = __import__("datetime").date.today().isoformat()


@dataclass
class TechnicalOverlay:
    trend: str                        # "bullish" | "bearish" | "neutral" | "insufficient_data"
    above_ma50: Optional[bool]        # price > 50-day MA
    above_ma200: Optional[bool]       # price > 200-day MA
    rsi_14: Optional[float]           # 14-day RSI
    volume_confirmation: Optional[bool]  # last close volume >= 1.5x 30d avg
    price_vs_ma50_pct: Prov           # % above/below 50-day MA
    price_vs_ma200_pct: Prov          # % above/below 200-day MA
    notes: str
    data_rows: int


def _simple_ma(closes: List[float], period: int) -> Optional[float]:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas[-period:]]
    losses = [max(-d, 0) for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _prov(val: Optional[float], conf: Confidence = "medium") -> Prov:
    if val is None:
        return missing_prov(SOURCE, TODAY_STR)
    return Prov(value=val, source=SOURCE, as_of=TODAY_STR, confidence=conf)


def analyze_technicals(price_history: List[Dict]) -> TechnicalOverlay:
    """
    Compute technical overlay from OHLCV daily price records.
    price_history: list of dicts with keys Open, High, Low, Close, Volume (case-sensitive).
    Returns TechnicalOverlay. Never raises — missing data returns 'insufficient_data'.
    """
    if not price_history or len(price_history) < 5:
        return TechnicalOverlay(
            trend="insufficient_data",
            above_ma50=None,
            above_ma200=None,
            rsi_14=None,
            volume_confirmation=None,
            price_vs_ma50_pct=missing_prov(SOURCE, TODAY_STR),
            price_vs_ma200_pct=missing_prov(SOURCE, TODAY_STR),
            notes="Insufficient price history for technical analysis.",
            data_rows=len(price_history),
        )

    try:
        closes = [float(r["Close"]) for r in price_history
                  if r.get("Close") is not None and not math.isnan(float(r["Close"]))]
        volumes = [float(r["Volume"]) for r in price_history
                   if r.get("Volume") is not None]
    except (KeyError, TypeError, ValueError):
        return TechnicalOverlay(
            trend="insufficient_data",
            above_ma50=None, above_ma200=None, rsi_14=None,
            volume_confirmation=None,
            price_vs_ma50_pct=missing_prov(SOURCE, TODAY_STR),
            price_vs_ma200_pct=missing_prov(SOURCE, TODAY_STR),
            notes="Price history format error.",
            data_rows=len(price_history),
        )

    if not closes:
        return TechnicalOverlay(
            trend="insufficient_data",
            above_ma50=None, above_ma200=None, rsi_14=None,
            volume_confirmation=None,
            price_vs_ma50_pct=missing_prov(SOURCE, TODAY_STR),
            price_vs_ma200_pct=missing_prov(SOURCE, TODAY_STR),
            notes="No valid close prices in history.",
            data_rows=0,
        )

    last_price = closes[-1]
    ma50 = _simple_ma(closes, 50)
    ma200 = _simple_ma(closes, 200)
    rsi = _rsi(closes, 14)

    above_ma50 = (last_price > ma50) if ma50 else None
    above_ma200 = (last_price > ma200) if ma200 else None

    # % vs MAs
    vs_ma50_pct = ((last_price - ma50) / ma50 * 100) if ma50 else None
    vs_ma200_pct = ((last_price - ma200) / ma200 * 100) if ma200 else None

    # Volume confirmation: last volume vs 30-day avg
    volume_confirmation = None
    if volumes and len(volumes) >= 31:
        avg_vol_30d = sum(volumes[-31:-1]) / 30
        last_vol = volumes[-1]
        if avg_vol_30d > 0:
            volume_confirmation = last_vol >= 1.5 * avg_vol_30d

    # Trend assessment
    bullish_signals = sum([
        above_ma50 is True,
        above_ma200 is True,
        rsi is not None and 50 < rsi < 70,
    ])
    bearish_signals = sum([
        above_ma50 is False,
        above_ma200 is False,
        rsi is not None and rsi < 40,
    ])

    if bullish_signals >= 2 and bearish_signals == 0:
        trend = "bullish"
    elif bearish_signals >= 2 and bullish_signals == 0:
        trend = "bearish"
    else:
        trend = "neutral"

    ma50_str = f"{ma50:.2f}" if ma50 else "n/a"
    ma200_str = f"{ma200:.2f}" if ma200 else "n/a"
    rsi_str = f"{rsi:.1f}" if rsi else "n/a"
    notes = (
        f"Price ${last_price:.2f}. MA50={ma50_str} MA200={ma200_str} RSI={rsi_str}."
        f" Volume confirmation: {volume_confirmation}."
    )

    conf: Confidence = "medium" if len(closes) >= 50 else "low"

    return TechnicalOverlay(
        trend=trend,
        above_ma50=above_ma50,
        above_ma200=above_ma200,
        rsi_14=rsi,
        volume_confirmation=volume_confirmation,
        price_vs_ma50_pct=_prov(vs_ma50_pct, conf),
        price_vs_ma200_pct=_prov(vs_ma200_pct, conf),
        notes=notes,
        data_rows=len(closes),
    )
