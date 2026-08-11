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
from adapters.fmp_adapter import fetch_fmp, fetch_splits
from core.corporate_actions import build_split_report
from adapters.fred_adapter import FredData
from core.valuation_anchors import (
    ANCHOR_OWN_HISTORY, ANCHOR_RISK_FREE, ANCHOR_SECTOR, METRIC_EARNINGS_YIELD,
    METRIC_FCF_YIELD, METRIC_FORWARD_EARNINGS_YIELD, MIN_HISTORY_POINTS,
    METRIC_EBITDA_YIELD,
    _yield_from_multiple, compute_panel, own_history_earnings_yields, render_panel,
    build_panel, score_yield_spread,
)

FIXTURES = Path("tests/fixtures")
AS_OF = "2026-08-09"
SECTOR_PE = {"Technology": 48.1, "Financial Services": 21.0}


def _FMP_FX(ticker: str) -> Path:
    return FIXTURES / "fmp" / f"{ticker}.json"


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
        """D-4: build_panel is load-bearing, so a failure must degrade to the risk-free-
        only fallback (flagged PANEL-NARROWED) rather than kill the evaluation."""
        class Exploding:
            ticker = "BOOM"

            def __getattr__(self, name):
                raise ValueError(f"boom on {name}")

        lines = []
        assert build_panel(Exploding(), None, None, {}, "cyclical",
                           log=lines.append) is None
        assert lines and "FAILED" in lines[0] and "risk-free-only" in lines[0]

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
    @pytest.mark.parametrize("ticker", ["MU", "GOOG", "WU"])
    def test_series_is_built_from_the_price_actually_paid(self, ticker):
        yf, edgar = _load(ticker)
        history = own_history_earnings_yields(edgar, yf.price_history)
        assert len(history) >= MIN_HISTORY_POINTS
        for h in history:
            assert h["earnings_yield"] == pytest.approx(
                h["net_income_ttm"] / (h["price"] * h["shares"]) * 100.0)

    def test_the_truncating_series_is_now_the_FALLBACK_and_still_truncates(self):
        """FLIPPED AT G-4 (was test_series_truncates_at_a_split_boundary).

        own_history_earnings_yields is unchanged and still truncates — it is what the
        panel falls back to when the split state is not established. Pinned because the
        fallback has to keep working: it is the only thing standing between an unknown
        split and GOOG's pre-2022 quarters at an ~81% yield against a ~4% norm.
        """
        yf, edgar = _load("GOOG")
        history = own_history_earnings_yields(edgar, yf.price_history)
        assert history[-1]["period_end"] >= "2022-06-30"
        assert max(h["earnings_yield"] for h in history) < 10.0

    def test_a_recent_split_no_longer_costs_the_anchor(self):
        """FLIPPED AT G-4 (was test_a_recent_split_can_cost_the_anchor_entirely).

        NOW's 5:1 split used to leave 2 consistent quarters and cost the anchor outright.
        Armed, the series is restated onto today's basis instead of truncated, and the
        anchor is AVAILABLE. This is the whole point of Phase G.
        """
        yf, edgar = _load("NOW")
        report = build_split_report("NOW", fetch_splits("NOW", fixture_path=_FMP_FX("NOW")),
                                    edgar.financials)
        assert [e.ratio for e in report.usable] == [5.0]
        panel = compute_panel(yf, _fred(), edgar, SECTOR_PE, "growth", today=AS_OF,
                              split_report=report)
        own = next(r for r in panel.readings
                   if r.anchor == ANCHOR_OWN_HISTORY
                   and r.metric == METRIC_EARNINGS_YIELD)
        assert own.available and "split_restated" in own.note
        # ...and the truncated series it replaced was below the withholding floor
        assert len(own_history_earnings_yields(edgar, yf.price_history)) < MIN_HISTORY_POINTS

    def test_without_a_split_report_the_panel_keeps_the_truncated_basis(self):
        """None means UNKNOWN, never "no splits". An unknown split state must not reach
        the restated series, which has no truncation to protect it."""
        yf, edgar = _load("NOW")
        panel = compute_panel(yf, _fred(), edgar, SECTOR_PE, "growth", today=AS_OF)
        own = next(r for r in panel.readings
                   if r.anchor == ANCHOR_OWN_HISTORY
                   and r.metric == METRIC_EARNINGS_YIELD)
        assert not own.available and "historical points" in own.reason

    def test_loss_periods_are_excluded_and_counted(self):
        """A loss-making period has no earnings yield to rank against the 10Y, exactly
        as a negative P/E has none today. MU's FY2023 losses are excluded, not folded
        into the median as negative yields."""
        yf, edgar = _load("MU")
        history = own_history_earnings_yields(edgar, yf.price_history)
        assert all(h["earnings_yield"] > 0 for h in history)
        assert history[0]["loss_periods_excluded"] > 0
        panel = compute_panel(yf, _fred(), edgar, SECTOR_PE, "cyclical", today=AS_OF)
        own = next(r for r in panel.readings if r.anchor == ANCHOR_OWN_HISTORY)
        assert "loss period(s) excluded" in own.note

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


# ── D-1: shared rate-anchoring helper ────────────────────────────────────────
# These pin the EXTRACTED ladder against the inline one it replaced in
# _valuation_compounder. D-1 is a pure refactor: if any expectation below has to be
# edited to make the suite pass, the extraction changed behaviour and is wrong.

class TestSharedSpreadHelper:
    # (spread, expected_score, expected_flags) — transcribed from the pre-extraction
    # inline ladder, boundaries included on the >= side exactly as it read.
    LADDER_CASES = [
        (10.0, 5, []), (3.01, 5, []), (3.0, 5, []),
        (2.99, 4, []), (1.0, 4, []),
        (0.99, 3, []), (0.0, 3, []), (-1.0, 3, []),
        (-1.01, 2, ["RICH-VS-RISK-FREE"]), (-3.0, 2, ["RICH-VS-RISK-FREE"]),
        (-3.01, 1, ["VERY-RICH-VS-RISK-FREE"]), (-50.0, 1, ["VERY-RICH-VS-RISK-FREE"]),
    ]

    @pytest.mark.parametrize("spread,score,flags", LADDER_CASES)
    def test_ladder_matches_pre_extraction_behavior(self, spread, score, flags):
        r = score_yield_spread(4.0 + spread, 4.0)
        assert r.score == score, f"spread {spread:+} must score {score}, got {r.score}"
        assert r.flags == flags
        assert r.spread == pytest.approx(spread)

    def test_ladder_is_total_every_spread_scores(self):
        """No spread may fall through — a None score would reach the pillar as a crash."""
        for hundredths in range(-2000, 2001):
            assert score_yield_spread(hundredths / 100.0, 0.0) is not None

    def test_missing_either_side_returns_none_not_a_default(self):
        """A missing denominator must NOT score. Defaulting it to 0 would read as a
        4-5pp spread against a 4% yield — false cheapness, the peer-anchor failure."""
        assert score_yield_spread(None, 4.0) is None
        assert score_yield_spread(4.0, None) is None
        assert score_yield_spread(None, None) is None

    def test_default_anchor_is_risk_free(self):
        assert score_yield_spread(5.0, 4.0).anchor == ANCHOR_RISK_FREE

    def test_flag_scope_is_parameterised_for_d3(self):
        """D-3 scores the same spread against sector and own-history; the flag must name
        WHICH denominator it is rich against, or the panel's disagreement is unreadable."""
        r = score_yield_spread(2.0, 4.0, anchor=ANCHOR_SECTOR, flag_scope="SECTOR")
        assert r.flags == ["RICH-VS-SECTOR"] and r.anchor == ANCHOR_SECTOR
        deep = score_yield_spread(0.0, 4.0, anchor=ANCHOR_SECTOR, flag_scope="SECTOR")
        assert deep.flags == ["VERY-RICH-VS-SECTOR"], "both rungs must carry the scope"

    def test_shaped_for_min_aggregation(self):
        """AGGREGATION RULED 2026-08-09: MIN across available anchors, permanent.
        The reading must support it directly — least flattering wins, and stays
        attributable to its anchor so a narrowed panel is detectable."""
        readings = [
            score_yield_spread(8.0, 4.0, anchor=ANCHOR_RISK_FREE),
            score_yield_spread(8.0, 6.0, anchor=ANCHOR_SECTOR),
            score_yield_spread(8.0, 9.0, anchor=ANCHOR_OWN_HISTORY),
        ]
        worst = min(readings, key=lambda s: s.spread)
        assert worst.anchor == ANCHOR_OWN_HISTORY, "MIN must pick the dissenting anchor"
        assert worst.spread == pytest.approx(-1.0) and worst.score == 3
        assert worst.score < max(r.score for r in readings), (
            "MIN must not look cheaper than the least flattering denominator"
        )

    def test_min_is_not_median_on_the_wu_shape(self):
        """Median was REJECTED on D-0 evidence: it discards own-history exactly when it
        dissents, and that dissent is the discriminator. Pins the rejected behaviour."""
        readings = [
            score_yield_spread(12.0, 4.0, anchor=ANCHOR_RISK_FREE),
            score_yield_spread(12.0, 5.0, anchor=ANCHOR_SECTOR),
            score_yield_spread(12.0, 11.0, anchor=ANCHOR_OWN_HISTORY),
        ]
        spreads = sorted(r.spread for r in readings)
        assert min(spreads) == pytest.approx(1.0), "MIN keeps the own-history dissent"
        assert spreads[1] == pytest.approx(7.0), "median would discard it — rejected"
