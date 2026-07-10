"""
FRED adapter — 10-Year Treasury rate (DGS10) for rate-aware valuation.
FRED_API_KEY via env (optional). Without key: confidence degrades to low.
Ethos rule 10: pull current 10Y; judge multiples relative to risk-free regime.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from adapters.base import Confidence, Prov, missing_prov

TODAY = date.today().isoformat()
SOURCE = "FRED"
SERIES = "DGS10"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


@dataclass
class FredData:
    rate_10y: Prov          # DGS10 value in percent (e.g. 4.32)
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def fetch_fred(fixture_path: Optional[Path] = None) -> FredData:
    if fixture_path is not None:
        return _from_fixture(fixture_path)
    return _from_live()


def _from_live() -> FredData:
    api_key = os.environ.get("FRED_API_KEY", "")

    # Strategy A: fredapi library
    if api_key:
        try:
            from fredapi import Fred
            fred = Fred(api_key=api_key)
            series = fred.get_series(SERIES, observation_start="2024-01-01")
            valid = series.dropna()
            if not valid.empty:
                val = float(valid.iloc[-1])
                as_of = str(valid.index[-1].date())
                return FredData(rate_10y=Prov(
                    value=val, source=SOURCE, as_of=as_of, confidence="high"
                ))
        except Exception as e:
            pass  # fall through to direct API

    # Strategy B: direct REST API
    if api_key:
        try:
            r = requests.get(FRED_BASE, params={
                "series_id": SERIES,
                "sort_order": "desc",
                "limit": 10,
                "file_type": "json",
                "api_key": api_key,
            }, timeout=15)
            r.raise_for_status()
            obs = r.json().get("observations", [])
            valid = [(o["date"], o["value"]) for o in obs if o.get("value") != "."]
            if valid:
                val = float(valid[0][1])
                return FredData(rate_10y=Prov(
                    value=val, source=SOURCE, as_of=valid[0][0], confidence="high"
                ))
        except Exception as e:
            pass

    # No key or all attempts failed — degrade gracefully
    conf: Confidence = "low"
    note = "FRED_API_KEY not set" if not api_key else "FRED fetch failed"
    return FredData(rate_10y=Prov(value=None, source=SOURCE, as_of=None, confidence=conf))


def _from_fixture(path: Path) -> FredData:
    if not path.exists():
        raise RuntimeError(f"[FRED] fixture not found: {path}. Run probe.py first.")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    results = raw.get("results", {})

    # Try fredapi result first
    fa = results.get("fredapi", {})
    if "latest_value" in fa:
        return FredData(rate_10y=Prov(
            value=fa["latest_value"],
            source=SOURCE,
            as_of=fa.get("latest_date", TODAY),
            confidence="high",
        ))

    # Try direct API result
    da = results.get("direct_api", {})
    obs = da.get("sample_observations", [])
    valid = [(o["date"], o["value"]) for o in obs if o.get("value") != "."]
    if valid:
        return FredData(rate_10y=Prov(
            value=float(valid[0][1]),
            source=SOURCE,
            as_of=valid[0][0],
            confidence="high" if raw.get("fred_api_key_present") else "medium",
        ))

    # No data available in fixture
    return FredData(rate_10y=missing_prov(SOURCE, TODAY))
