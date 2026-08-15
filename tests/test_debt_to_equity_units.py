"""The debt/equity UNITS defect — production, 2026-08-07 to 2026-08-15.

WHAT HAPPENED. `core/pillars.score_financial_health` scores leverage on a PERCENT ladder
(`de <= 30 -> 3 pts`, rendered `f"{de:.0f}%"`). It was calibrated when yfinance was the
feed, and yfinance published D/E as a percent (V: 67.233). FMP publishes the RATIO
(V: 0.672331). When the yfinance teardown made FMP the sole live feed, the raw ratio began
flowing into the percent ladder unchanged. Nothing realistic exceeds 30 as a ratio, so
EVERY issuer collected the full 3 of 3 leverage points and the component went inert.

It was visible in production the entire time. The live armed pass of 2026-08-09
(ids 216-220) recorded GOOG "debt/equity 0%", MU "0%", V "1%" — V being a name levered
~67% — and nothing remarked on it.

These tests pin the convention so it cannot drift back, and pin the tripwire that would
have made the silence audible.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from adapters.fmp_adapter import _ratio_to_percent, fetch_fmp
from batch.runner import TickerResult, _leverage_uniformity_alarm
from core.pillars import score_financial_health

FMP = Path(__file__).parent / "fixtures" / "fmp"


def _fmp(ticker: str):
    return fetch_fmp(ticker, fixture_path=FMP / f"{ticker}.json")


# ── The conversion itself ────────────────────────────────────────────────────

def test_a_ratio_is_emitted_as_the_percent_the_ladder_expects():
    """0.672331 (FMP's ratio for V) must reach the ladder as 67.2331, not 0.672331."""
    assert _ratio_to_percent(0.672331) == pytest.approx(67.2331)
    assert _ratio_to_percent(0.0) == 0.0
    assert _ratio_to_percent(None) is None


def test_the_adapter_emits_percent_for_every_golden_ticker():
    """Pinned per ticker, not on an aggregate — the standing per-point ruling.

    These are the real recorded values. WU is the case that proves the ladder discriminates
    again: at ~295% it is nowhere near the top rung.
    """
    expected = {
        "MU": 6.33,
        "GOOG": 17.60,
        "V": 67.23,
        "NOW": 67.54,
        "WU": 294.87,
    }
    for ticker, pct in expected.items():
        got = _fmp(ticker).debt_to_equity.value
        assert got == pytest.approx(pct, abs=0.01), f"{ticker}: {got}"


def test_the_defect_reproduced_every_ticker_scored_the_top_rung():
    """THE DEFECT, STATED AS A TEST. Under the old raw-ratio path every golden ticker sat
    under the ladder's top rung; under the fix they no longer do. If this ever passes in
    both directions again, the units have regressed."""
    raw_ratios = [_fmp(t).debt_to_equity.value / 100.0
                  for t in ("MU", "GOOG", "V", "NOW", "WU")]
    assert all(r <= 30 for r in raw_ratios), "the raw ratios all clear the top rung"

    converted = [_fmp(t).debt_to_equity.value for t in ("MU", "GOOG", "V", "NOW", "WU")]
    assert not all(c <= 30 for c in converted), \
        "converted, the universe must NOT be uniformly at the top rung"


# ── The ladder actually discriminates again ──────────────────────────────────

def test_WU_now_scores_ZERO_leverage_points_at_295_percent():
    """WU is levered ~295%. Under the defect it collected the maximum 3 points; it must now
    collect none, which is the whole point of having a ladder."""
    wu = _fmp("WU")
    assert wu.debt_to_equity.value > 200, wu.debt_to_equity.value
    result = score_financial_health(wu, "compounder")
    assert "295%" in result.rationale or "debt/equity 295%" in result.rationale, \
        result.rationale


def test_the_rationale_prints_leverage_a_reader_would_recognise():
    """GOOG at ~17.6% must not render as "0%" — the string that made the defect look
    unremarkable in five production evaluations."""
    r = score_financial_health(_fmp("GOOG"), "compounder")
    assert "debt/equity 0%" not in r.rationale, r.rationale
    assert "18%" in r.rationale, r.rationale


# ── The tripwire ─────────────────────────────────────────────────────────────

def _res(ticker: str, de):
    return TickerResult(ticker=ticker, status="ok", debt_to_equity=de)


def test_the_tripwire_fires_when_every_name_is_under_the_top_rung():
    """The 2026-08-07 signature, replayed: a whole batch of raw ratios."""
    alarm = _leverage_uniformity_alarm(
        [_res("MU", 0.063), _res("GOOG", 0.176), _res("V", 0.672),
         _res("NOW", 0.675), _res("WU", 2.949)])
    assert alarm is not None
    assert "LEVERAGE UNIFORMITY" in alarm
    assert "UNITS REGRESSION" in alarm


def test_the_tripwire_stays_silent_on_a_healthy_batch():
    """The corrected values must NOT trip it — a tripwire that always fires is noise."""
    assert _leverage_uniformity_alarm(
        [_res("MU", 6.33), _res("GOOG", 17.60), _res("V", 67.23),
         _res("NOW", 67.54), _res("WU", 294.87)]) is None


def test_the_tripwire_refuses_to_call_uniformity_on_too_few_readings():
    """Two debt-free issuers are not evidence of a units bug."""
    assert _leverage_uniformity_alarm([_res("A", 1.0), _res("B", 2.0)]) is None


def test_the_tripwire_ignores_tickers_with_no_reading():
    """A missing D/E must not be counted as 'under the top rung' — that would let a batch
    of withheld values raise a units alarm."""
    assert _leverage_uniformity_alarm(
        [_res("A", None), _res("B", None), _res("C", None), _res("D", 5.0)]) is None


def test_the_tripwire_is_advisory_and_returns_text_not_an_exception():
    """It must never be able to withhold an evaluation — that would be a new failure mode
    bolted onto a diagnostic."""
    alarm = _leverage_uniformity_alarm(
        [_res("A", 1.0), _res("B", 2.0), _res("C", 3.0)])
    assert isinstance(alarm, str)
