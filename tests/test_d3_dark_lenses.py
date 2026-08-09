"""
D-3 — per-lens panel anchoring, DARK. The load-bearing test is test_applies_nothing:
D-3 measures, D-4 arms. Everything else pins the mechanisms Vic rules on, so a ruling
that lands later changes these deliberately rather than by accident.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from adapters.edgar_adapter import fetch_edgar
from adapters.fmp_adapter import fetch_fmp
from adapters.fred_adapter import FredData
from adapters.base import Prov
from core.pillars import score_valuation
from core.valuation_anchors import (
    ANCHOR_OWN_HISTORY, ANCHOR_RISK_FREE, ANCHOR_SECTOR, GROWTH_SPREAD_LADDER,
    LENS_LADDER, LENS_METRIC, METRIC_EARNINGS_YIELD, RATE_SPREAD_LADDER,
    AnchorReading, ValuationPanel, bank_instrument_reading, compute_panel,
    dark_lens_score, run_dark_lens, score_yield_spread,
)

FIXTURES = Path("tests/fixtures")
AS_OF = "2026-08-09"


def _panel_with(metric, pairs):
    """A panel holding exactly the (anchor, ticker_yield, anchor_yield) rows given."""
    p = ValuationPanel(ticker="TEST", lens="compounder", as_of=AS_OF)
    for anchor, ty, ay in pairs:
        p.readings.append(AnchorReading(metric=metric, anchor=anchor, ticker_yield=ty,
                                        anchor_yield=ay, available=True))
    return p


class TestAppliesNothing:
    def test_dark_score_does_not_touch_the_live_score(self):
        """THE D-3 INVARIANT. score_valuation must be byte-identical whether or not the
        dark lens score was computed first."""
        yf = fetch_fmp("MU", fixture_path=FIXTURES / "fmp" / "MU.json")
        edgar = fetch_edgar("MU", fixture_path=FIXTURES / "edgar" / "MU.json")
        yf.sic = edgar.sic
        fred = FredData(rate_10y=Prov(4.69, "FRED", AS_OF, "high"))

        before = score_valuation(yf, fred, "cyclical")
        panel = compute_panel(yf, fred, edgar, {"Technology": 48.1}, "cyclical")
        dark = dark_lens_score(panel, "cyclical", live_score=before.score,
                               peak_warning="peak")
        after = score_valuation(yf, fred, "cyclical")

        assert (after.score, sorted(after.flags), after.rationale, after.confidence) == \
               (before.score, sorted(before.flags), before.rationale, before.confidence)
        assert dark.panel_score is not None, "the dark score was actually computed"

    def test_dark_score_mutates_neither_panel_nor_readings(self):
        panel = _panel_with(METRIC_EARNINGS_YIELD,
                            [(ANCHOR_RISK_FREE, 8.0, 4.69), (ANCHOR_SECTOR, 8.0, 2.08)])
        snapshot = [(r.anchor, r.ticker_yield, r.anchor_yield, r.available)
                    for r in panel.readings]
        dark_lens_score(panel, "compounder", live_score=3)
        assert [(r.anchor, r.ticker_yield, r.anchor_yield, r.available)
                for r in panel.readings] == snapshot

    def test_run_dark_lens_survives_a_broken_panel(self):
        """Containment: D-3 has no reach into any score, so a bug in it must not be able
        to take down an evaluation it cannot influence."""
        assert run_dark_lens(None, "compounder", 3, log=lambda m: None) is None


class TestMinAggregation:
    def test_min_binds_the_least_flattering_anchor(self):
        """AGGREGATION RULED permanent: MIN across available anchors."""
        panel = _panel_with(METRIC_EARNINGS_YIELD, [
            (ANCHOR_RISK_FREE, 5.11, 4.69),      # +0.42
            (ANCHOR_SECTOR, 5.11, 2.08),         # +3.03
            (ANCHOR_OWN_HISTORY, 5.11, 5.76),    # -0.65  <- binds
        ])
        d = dark_lens_score(panel, "cyclical", live_score=2)
        assert d.binding_anchor == ANCHOR_OWN_HISTORY
        assert d.binding_spread == pytest.approx(-0.65, abs=0.01)
        assert d.anchor_count == 3 and not d.narrowed

    def test_the_mu_shape_is_not_rescued_by_the_other_two_anchors(self):
        """MU's live configuration: cheap vs risk-free AND sector, rich vs own history.
        MIN must report the dissent, not the majority."""
        panel = _panel_with(METRIC_EARNINGS_YIELD, [
            (ANCHOR_RISK_FREE, 5.11, 4.69), (ANCHOR_SECTOR, 5.11, 2.08),
            (ANCHOR_OWN_HISTORY, 5.11, 5.76),
        ])
        d = dark_lens_score(panel, "cyclical", live_score=2)
        assert d.binding_spread < 0, "the dissenting anchor must bind"


class TestIndependenceNarrowing:
    def test_market_only_pair_is_flagged_independence_narrowed(self):
        """Binding condition 1: risk-free + sector are two MARKET-referenced denominators,
        not two independent checks."""
        panel = _panel_with(METRIC_EARNINGS_YIELD,
                            [(ANCHOR_RISK_FREE, 6.0, 4.69), (ANCHOR_SECTOR, 6.0, 2.08)])
        d = dark_lens_score(panel, "cyclical", live_score=3)
        assert d.narrowed and d.independence_narrowed
        assert "PANEL-NARROWED-MARKET-ONLY" in d.flags

    def test_pair_including_own_history_is_narrowed_but_still_independent(self):
        """Two anchors, but one is the issuer's own past — narrowed, NOT independence-
        narrowed. The distinction is the whole point of the condition."""
        panel = _panel_with(METRIC_EARNINGS_YIELD,
                            [(ANCHOR_RISK_FREE, 6.0, 4.69), (ANCHOR_OWN_HISTORY, 6.0, 5.0)])
        d = dark_lens_score(panel, "cyclical", live_score=3)
        assert d.narrowed and not d.independence_narrowed
        assert "PANEL-NARROWED" in d.flags

    def test_haircut_never_makes_a_stock_look_cheaper(self):
        """Whatever mechanism is ruled, it may only ever be conservative."""
        for ty in (0.0, 2.0, 5.0, 9.0, 20.0):
            panel = _panel_with(METRIC_EARNINGS_YIELD,
                                [(ANCHOR_RISK_FREE, ty, 4.69), (ANCHOR_SECTOR, ty, 2.08)])
            d = dark_lens_score(panel, "cyclical", live_score=3)
            assert d.haircut_score <= d.panel_score

    def test_haircut_has_a_floor_of_one(self):
        panel = _panel_with(METRIC_EARNINGS_YIELD,
                            [(ANCHOR_RISK_FREE, 0.0, 4.69), (ANCHOR_SECTOR, 0.0, 2.08)])
        d = dark_lens_score(panel, "cyclical", live_score=1)
        assert d.panel_score == 1 and d.haircut_score == 1


class TestCyclicalGate:
    @pytest.mark.parametrize("warn", ["peak", "rollover"])
    def test_gate_caps_a_cheap_reading_at_two(self, warn):
        """THE MU-2018 GUARD. At peak margins a cheap multiple is a sell signal. The gate
        CAPS; no rung geometry can express 'this E is about to halve'."""
        panel = _panel_with(METRIC_EARNINGS_YIELD,
                            [(ANCHOR_RISK_FREE, 30.16, 4.69)])   # +25.47pp — MU forward
        ungated = dark_lens_score(panel, "cyclical", live_score=2)
        gated = dark_lens_score(panel, "cyclical", live_score=2, peak_warning=warn)
        assert ungated.panel_score == 5, "unanimously cheap without the gate"
        assert gated.panel_score == 2, "gate must cap the cycle-peak trap"
        assert f"CYCLE-GATE-CAP-{warn.upper()}" in gated.flags

    def test_gate_never_raises_a_score(self):
        panel = _panel_with(METRIC_EARNINGS_YIELD,
                            [(ANCHOR_RISK_FREE, 1.0, 4.69)])     # -3.69pp -> 1
        d = dark_lens_score(panel, "cyclical", live_score=1, peak_warning="peak")
        assert d.panel_score == 1, "a gate may only cap, never lift"

    def test_gate_applies_only_to_the_cyclical_lens(self):
        panel = _panel_with(LENS_METRIC["compounder"],
                            [(ANCHOR_RISK_FREE, 30.0, 4.69)])
        d = dark_lens_score(panel, "compounder", live_score=5, peak_warning="peak")
        assert d.panel_score == 5 and d.gate_applied is None


class TestLensMapping:
    def test_cyclical_is_anchored_on_trailing_not_forward(self):
        """Basis ruling input: MU's forward yield is +25.47pp cheap at a cycle peak while
        trailing is -0.65pp rich. Forward is the number that lies here."""
        assert LENS_METRIC["cyclical"] == METRIC_EARNINGS_YIELD

    def test_growth_ladder_is_shifted_not_the_default(self):
        assert LENS_LADDER["growth"] is GROWTH_SPREAD_LADDER
        assert LENS_LADDER["growth"] != RATE_SPREAD_LADDER

    def test_growth_ladder_is_more_permissive_at_every_rung(self):
        """A duration asset may carry a negative current spread and still be priced
        correctly; the shift must be uniformly more generous, never mixed."""
        for spread in (-6.0, -4.0, -2.0, 0.0, 2.0, 4.0):
            default = score_yield_spread(spread, 0.0, ladder=RATE_SPREAD_LADDER).score
            growth = score_yield_spread(spread, 0.0, ladder=GROWTH_SPREAD_LADDER).score
            assert growth >= default, f"growth ladder must not be harsher at {spread}"

    def test_bank_has_no_yield_metric(self):
        """The honest answer: a yield spread does not fit a bank. See the D-3 report."""
        assert LENS_METRIC["bank"] is None
        panel = _panel_with(METRIC_EARNINGS_YIELD, [(ANCHOR_RISK_FREE, 6.0, 4.69)])
        d = dark_lens_score(panel, "bank", live_score=3)
        assert d.panel_score is None and "bank_instrument_reading" in d.reason


class TestBankInstrument:
    def test_excess_roe_and_justified_pb_are_computed(self):
        yf = fetch_fmp("V", fixture_path=FIXTURES / "fmp" / "V.json")
        fred = FredData(rate_10y=Prov(4.69, "FRED", AS_OF, "high"))
        r = bank_instrument_reading(yf, fred)
        assert r["cost_of_equity_pct"] is not None
        assert r["justified_pb"] is not None
        assert r["excess_roe_pp"] == pytest.approx(
            r["roe_pct"] - r["cost_of_equity_pct"], abs=1e-6)

    def test_missing_inputs_withhold_rather_than_default(self):
        """A missing beta must not silently become 1.0 — that would manufacture a cost
        of equity out of nothing."""
        yf = fetch_fmp("V", fixture_path=FIXTURES / "fmp" / "V.json")
        yf.beta = Prov(None, "test", AS_OF, "low")
        fred = FredData(rate_10y=Prov(4.69, "FRED", AS_OF, "high"))
        r = bank_instrument_reading(yf, fred)
        assert r["cost_of_equity_pct"] is None and r["excess_roe_pp"] is None


# ── D-5 DARK: bank instrument ladder (NOT ARMED) ─────────────────────────────

class TestBankLadderProposal:
    """Calibrated on JPM/BK/USB/C. Applied to nothing — the bank lens is not armed."""

    def test_bank_lens_is_still_not_armed(self):
        """THE INVARIANT. The ladder exists as a proposal; score_valuation must not use
        it until Vic rules."""
        from core.pillars import ARMED_LENSES, ARMED_PANEL_LENSES
        assert "bank" not in ARMED_LENSES and "bank" not in ARMED_PANEL_LENSES

    def test_ratio_discriminates_where_the_difference_does_not(self):
        """THE CALIBRATION FINDING. JPM and BK sit +0.70 and +0.68 on the DIFFERENCE —
        indistinguishable — but 1.36x and 1.45x on the RATIO. The difference is scale-
        dependent in the justified value; the ratio is not."""
        from core.valuation_anchors import score_bank_instrument
        jpm = score_bank_instrument({"price_to_book": 2.66, "justified_pb": 1.96,
                                     "excess_roe_pp": 8.72})
        bk = score_bank_instrument({"price_to_book": 2.20, "justified_pb": 1.51,
                                    "excess_roe_pp": 4.81})
        assert abs(jpm["difference"] - bk["difference"]) < 0.05
        assert bk["ratio"] > jpm["ratio"] + 0.05

    def test_below_book_is_not_automatically_cheap(self):
        """C trades at 1.08x BOOK but 1.24x JUSTIFIED book, because its ROE (8.4%) is
        under its cost of equity (9.65%). The bank-lens value trap."""
        from core.valuation_anchors import score_bank_instrument
        c = score_bank_instrument({"price_to_book": 1.08, "justified_pb": 0.87,
                                   "excess_roe_pp": -1.26})
        assert c["ratio"] > 1.0, "cheap on book, dear on what it earns"
        assert "ROE-BELOW-COST-OF-EQUITY" in c["flags"]

    def test_excess_roe_gate_caps_a_collapsed_bank(self):
        """The gate is written for the case NOT in the calibration set: a sub-book bank
        whose ROE has collapsed, which is when the instrument would otherwise scream buy."""
        from core.valuation_anchors import score_bank_instrument
        s = score_bank_instrument({"price_to_book": 0.50, "justified_pb": 0.80,
                                   "excess_roe_pp": -4.0})
        assert s["raw_score"] == 5, "ratio alone would call it maximally cheap"
        assert s["score"] == 3, "gate must cap a bank not covering its cost of equity"

    def test_gate_never_raises(self):
        from core.valuation_anchors import score_bank_instrument
        s = score_bank_instrument({"price_to_book": 4.0, "justified_pb": 1.0,
                                   "excess_roe_pp": -2.0})
        assert s["score"] == s["raw_score"] == 1

    def test_missing_inputs_withhold(self):
        from core.valuation_anchors import score_bank_instrument
        assert score_bank_instrument({"price_to_book": None, "justified_pb": 1.0}) is None
        assert score_bank_instrument({"price_to_book": 1.0, "justified_pb": None}) is None
