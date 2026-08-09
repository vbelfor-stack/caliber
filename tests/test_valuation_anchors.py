"""
Phase D-0 — valuation anchor panel. Measurement only; nothing here may be applied.

The load-bearing tests are test_applies_nothing (D-0 is dark) and the ones covering
withheld anchors: an anchor that cannot be computed must be RECORDED as unavailable with
a reason, never silently dropped or defaulted, because a missing denominator that reads
as agreement is exactly the false corroboration the peer anchor was rejected for.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from adapters.base import Prov
from adapters.edgar_adapter import fetch_edgar
from adapters.fmp_adapter import fetch_fmp
from adapters.fred_adapter import FredData
from core.valuation_anchors import (
    ANCHOR_OWN_HISTORY, ANCHOR_RISK_FREE, ANCHOR_SECTOR, METRIC_EARNINGS_YIELD,
    METRIC_FCF_YIELD, METRIC_FORWARD_EARNINGS_YIELD, MIN_HISTORY_POINTS,
    _yield_from_multiple, compute_panel, own_history_earnings_yields, render_panel,
    run_dark_panel,
)

FIXTURES = Path("tests/fixtures")
AS_OF = "2026-08-09"
SECTOR_PE = {"Technology": 48.1, "Financial Services": 21.0}


def _load(ticker: str):
    return (fetch_fmp(ticker, fixture_path=FIXTURES / "fmp" / f"{ticker}.json"),
            fetch_edgar(ticker, fixture_path=FIXTURES / "edgar" / f"{ticker}.json"))


def _fred(rate=4.69):
    return FredData(rate_10y=Prov(value=rate, source="FRED", as_of=AS_OF,
                                  confidence="high"))


def _panel(ticker, fred=None, sector_pe=None, lens="cyclical"):
    yf, edgar = _load(ticker)
    return compute_panel(yf, fred or _fred(), edgar,
                         SECTOR_PE if sector_pe is None else sector_pe, lens, today=AS_OF)


class TestDarkInvariant:
    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "V", "NOW", "WU"])
    def test_applies_nothing(self, ticker):
        yf, edgar = _load(ticker)
        before = {n: (p.value, p.source, p.as_of, p.confidence)
                  for n, p in vars(yf).items() if isinstance(p, Prov)}
        edgar_before = deepcopy(edgar.financials.fields)
        compute_panel(yf, _fred(), edgar, SECTOR_PE, "cyclical", today=AS_OF)
        assert {n: (p.value, p.source, p.as_of, p.confidence)
                for n, p in vars(yf).items() if isinstance(p, Prov)} == before
        assert edgar.financials.fields == edgar_before

    def test_runner_contains_its_own_failures(self):
        """D-0 has no reach into any score, so a bug in it must not kill an evaluation."""
        class Exploding:
            ticker = "BOOM"

            def __getattr__(self, name):
                raise ValueError(f"boom on {name}")

        lines = []
        assert run_dark_panel(Exploding(), None, None, {}, "cyclical",
                              log=lines.append) is None
        assert lines and "FAILED" in lines[0] and "evaluation unaffected" in lines[0]

    def test_table_says_nothing_is_applied(self):
        assert "APPLIED=NOTHING" in render_panel(_panel("MU"))


class TestYieldConversion:
    def test_negative_multiples_have_no_yield(self):
        """A company losing money is not offering a negative earnings yield to be ranked
        against the 10Y — it is unscoreable on that metric. Mirrors the negative
        forward-EPS hard stop."""
        assert _yield_from_multiple(-12.0) is None
        assert _yield_from_multiple(0.0) is None
        assert _yield_from_multiple(None) is None
        assert _yield_from_multiple(20.0) == pytest.approx(5.0)


class TestAnchorAvailability:
    def test_missing_rate_is_recorded_not_assumed(self):
        panel = _panel("MU", fred=FredData(
            rate_10y=Prov(None, "FRED", None, "low")))
        rf = [r for r in panel.readings if r.anchor == ANCHOR_RISK_FREE]
        assert rf and not any(r.available for r in rf)
        assert all("no FRED 10Y rate" in r.reason for r in rf)

    def test_missing_sector_snapshot_is_recorded_not_assumed(self):
        panel = _panel("MU", sector_pe={})
        sec = [r for r in panel.readings if r.anchor == ANCHOR_SECTOR]
        assert sec and not any(r.available for r in sec)
        assert all("no sector P/E snapshot" in r.reason for r in sec)

    def test_unknown_sector_names_itself(self):
        panel = _panel("MU", sector_pe={"Healthcare": 30.0})
        sec = next(r for r in panel.readings if r.anchor == ANCHOR_SECTOR)
        assert not sec.available and "Technology" in sec.reason

    def test_every_metric_gets_every_anchor_recorded(self):
        """No anchor is ever silently dropped — three anchors x four metrics, always."""
        panel = _panel("MU")
        assert len(panel.readings) == 12
        for metric in (METRIC_EARNINGS_YIELD, METRIC_FORWARD_EARNINGS_YIELD):
            anchors = {r.anchor for r in panel.readings if r.metric == metric}
            assert anchors == {ANCHOR_RISK_FREE, ANCHOR_SECTOR, ANCHOR_OWN_HISTORY}

    def test_cross_basis_comparisons_are_flagged(self):
        """The sector snapshot is an EARNINGS multiple; facing an FCF yield to it is a
        basis mismatch that must be visible, not buried."""
        panel = _panel("MU")
        fcf_sector = next(r for r in panel.readings
                          if r.metric == METRIC_FCF_YIELD and r.anchor == ANCHOR_SECTOR)
        assert fcf_sector.available and "basis:" in fcf_sector.note


class TestOwnHistoryAnchor:
    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "NOW", "WU"])
    def test_series_is_built_from_the_price_actually_paid(self, ticker):
        yf, edgar = _load(ticker)
        history = own_history_earnings_yields(edgar, yf.price_history)
        assert len(history) >= MIN_HISTORY_POINTS
        for h in history:
            assert h["earnings_yield"] == pytest.approx(
                h["net_income_ttm"] / (h["price"] * h["shares"]) * 100.0)

    def test_share_counts_are_matched_as_of_not_exactly(self):
        """MU resolves its share count from the dei cover-page tag, whose dates are
        filing cover dates and never coincide with a fiscal period-end. An exact join
        produced an empty series for it while GOOG, on a us-gaap tag, joined cleanly."""
        yf, edgar = _load("MU")
        share_ends = {r["end"] for recs in [edgar.financials.concepts[
            edgar.financials.fields["shares_outstanding"].concept]] for r in recs}
        history = own_history_earnings_yields(edgar, yf.price_history)
        assert history
        assert not any(h["period_end"] in share_ends for h in history)

    def test_v_has_no_own_history_and_says_so(self):
        """V's share count is withheld (stale multi-class tags), so the anchor cannot be
        built. The panel narrows and records why — it does not fall back to a guess."""
        panel = _panel("V", lens="compounder")
        own = next(r for r in panel.readings if r.anchor == ANCHOR_OWN_HISTORY)
        assert not own.available
        assert any("own-history anchor unavailable" in n for n in panel.notes)

    def test_thin_history_is_refused(self):
        yf, edgar = _load("GOOG")
        trimmed = deepcopy(edgar)
        concept = trimmed.financials.fields["net_income"].concept
        trimmed.financials.concepts[concept] = \
            trimmed.financials.concepts[concept][:4]
        panel = compute_panel(yf, _fred(), trimmed, SECTOR_PE, "compounder", today=AS_OF)
        own = next(r for r in panel.readings if r.anchor == ANCHOR_OWN_HISTORY)
        assert not own.available and "historical points" in own.reason


class TestDisagreement:
    def test_split_verdicts_are_surfaced(self):
        """The panel's reason for existing: MU is cheap against its sector and dear
        against both the risk-free rate and its own history."""
        panel = _panel("MU")
        split = panel.verdict_split(METRIC_EARNINGS_YIELD)
        assert split == {"cheap_vs": [ANCHOR_SECTOR],
                         "rich_vs": [ANCHOR_RISK_FREE, ANCHOR_OWN_HISTORY]}
        assert "SPLIT" in render_panel(panel)

    def test_agreement_is_reported_as_agreement(self):
        panel = _panel("V", lens="compounder")
        assert panel.verdict_split(METRIC_EARNINGS_YIELD) is None
        assert "all anchors agree" in render_panel(panel)

    def test_least_flattering_is_the_provisional_aggregate(self):
        """Never look cheaper than your least flattering defensible denominator."""
        panel = _panel("MU")
        worst = panel.least_flattering(METRIC_EARNINGS_YIELD)
        spreads = [r.spread for r in panel.by_metric(METRIC_EARNINGS_YIELD)]
        assert worst.spread == min(spreads)

    @pytest.mark.parametrize("metric", [METRIC_EARNINGS_YIELD, METRIC_FCF_YIELD])
    def test_anchor_range_equals_the_spread_range(self, metric):
        """Within one metric the ticker's own yield cancels, so how far apart the anchors
        sit IS how far apart their verdicts sit. (It still differs BETWEEN metrics,
        because own-history is available only for trailing earnings.)"""
        panel = _panel("MU")
        spreads = [r.spread for r in panel.by_metric(metric) if r.spread is not None]
        assert panel.anchor_range(metric) == pytest.approx(max(spreads) - min(spreads))
