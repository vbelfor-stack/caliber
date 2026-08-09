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


def fetch_payload() -> dict:
    """The raw FRED observations response — THE production fetch path (Strategy B).

    tools/record_fred_fixture records exactly this, and _from_fixture parses it back
    through the same _parse_observations the live path uses, so a recorded fixture
    cannot drift from what production requests. Mirrors fmp_adapter.fetch_payload.
    """
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        raise RuntimeError("[FRED] FRED_API_KEY not set — cannot fetch DGS10")
    r = requests.get(FRED_BASE, params={
        "series_id": SERIES,
        "sort_order": "desc",
        "limit": 10,
        "file_type": "json",
        "api_key": api_key,
    }, timeout=15)
    r.raise_for_status()
    payload = r.json()
    return {
        "series": SERIES,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "observations": payload.get("observations", []),
    }


def _parse_observations(obs: list) -> Optional[tuple]:
    """Newest non-placeholder observation as (value, date). FRED writes '.' for a
    non-trading day; treating that as data would put a 0.0 rate into the spread."""
    valid = [(o.get("date"), o.get("value")) for o in obs if o.get("value") not in (".", None)]
    if not valid:
        return None
    return float(valid[0][1]), valid[0][0]


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
        except Exception:
            pass  # fall through to direct API

    # Strategy B: direct REST API — the shape the recorder captures
    if api_key:
        try:
            parsed = _parse_observations(fetch_payload()["observations"])
            if parsed is not None:
                val, as_of = parsed
                return FredData(rate_10y=Prov(
                    value=val, source=SOURCE, as_of=as_of, confidence="high"
                ))
        except Exception:
            pass

    # No key or all attempts failed. The rate anchor is MANDATORY (Phase D ruling), so
    # this missing value is not a soft degrade any more — score_valuation REFUSES to
    # score on it and raises RateUnavailable. Returning it missing is still correct
    # here: the adapter reports what it has, the pillar rules on what that means.
    conf: Confidence = "low"
    return FredData(rate_10y=Prov(value=None, source=SOURCE, as_of=None, confidence=conf))


def _from_fixture(path: Path) -> FredData:
    if not path.exists():
        raise RuntimeError(
            f"[FRED] fixture not found: {path}. "
            f"Record it with: python -m tools.record_fred_fixture"
        )
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    if "observations" not in raw:
        # The pre-D-2 probe shape recorded no rate at all, which made every offline run
        # rate-blind. Fail LOUD rather than silently replaying a missing rate.
        raise RuntimeError(
            f"[FRED] fixture {path} predates D-2 (no 'observations' key) — it records no "
            f"rate, so offline runs would be rate-blind. Re-record: "
            f"python -m tools.record_fred_fixture"
        )

    parsed = _parse_observations(raw["observations"])
    if parsed is None:
        return FredData(rate_10y=missing_prov(SOURCE, TODAY))
    val, as_of = parsed
    # Recorded, but a real observation with its real observation date — the as_of keeps
    # its age visible rather than passing a stale rate off as today's.
    return FredData(rate_10y=Prov(value=val, source=SOURCE, as_of=as_of, confidence="high"))
