"""
L-4a — the technicals ordering contract.

BACKGROUND (docs/l4a-stx-diagnosis.md). FMP serves price_history NEWEST-FIRST and the adapter
preserves that order deliberately (adapters/fmp_adapter.py:33). core/technicals.analyze_technicals
computes oldest-first (closes[-1] is "now"). Between 2026-07-11 and 2026-08-19 nothing reconciled
the two, so every MA, RSI, boolean and volume reading described ~August 2021 instead of today,
and RSI was computed on a time-reversed series. It reached the synthesis prompt on all 68
evaluations and caused both anchor_divergence rows (MU id 209, STX id 258).

WHY THESE TESTS EXIST AND WHAT THEY ARE FOR:
  - the sort inside analyze_technicals is the fix; a sort with no test is a belief, not a guard
  - the suite had 825 passing tests and NEVER asserted a single technicals VALUE — the one test
    touching analyze_technicals asserted a provenance source string. These are the first
    value-level assertions on an MA and on a boolean.
  - all nine FMP fixtures are newest-first, so the offline baseline AGREED with the bug; a
    before/after diff could never have surfaced it. Only a value-level pin can.
"""
from pathlib import Path

import pytest

from adapters.fmp_adapter import fetch_fmp
from core.technicals import analyze_technicals

FMP_FIXTURES = Path("tests/fixtures/fmp")
ALL_FIXTURES = sorted(p.stem for p in FMP_FIXTURES.glob("*.json"))


def _history(ticker: str):
    return fetch_fmp(ticker, fixture_path=FMP_FIXTURES / f"{ticker}.json").price_history


def _comparable(t):
    """Every field an ordering bug could move."""
    return (
        t.trend,
        t.above_ma50,
        t.above_ma200,
        t.rsi_14,
        t.volume_confirmation,
        t.price_vs_ma50_pct.value,
        t.price_vs_ma200_pct.value,
        t.notes,
        t.data_rows,
    )


class TestOrderingIsIrrelevantToTheCaller:
    """The contract: analyze_technicals owns its ordering requirement, so callers cannot
    break it by handing rows over in a different order."""

    @pytest.mark.parametrize("ticker", ALL_FIXTURES)
    def test_output_is_identical_whichever_order_the_rows_arrive_in(self, ticker):
        rows = _history(ticker)
        assert len(rows) > 200, "fixture too short to exercise MA200"

        as_served = analyze_technicals(rows, feed_source="fmp")
        reversed_ = analyze_technicals(list(reversed(rows)), feed_source="fmp")
        ascending = analyze_technicals(
            sorted(rows, key=lambda r: str(r["date"])[:10]), feed_source="fmp")

        assert _comparable(as_served) == _comparable(reversed_), (
            f"{ticker}: reversing the input moved the reading — the ordering defect is back")
        assert _comparable(as_served) == _comparable(ascending), (
            f"{ticker}: explicitly-ascending input disagrees with as-served input")

    @pytest.mark.parametrize("ticker", ["WU", "MU"])
    def test_a_shuffled_series_gives_the_same_answer_so_it_is_a_real_sort(self, ticker):
        """A reverse-only fix would pass the test above. This one fails unless rows are
        genuinely sorted by date."""
        import random
        rows = list(_history(ticker))
        shuffled = list(rows)
        random.Random(4).shuffle(shuffled)
        assert shuffled != rows, "shuffle was a no-op; test proves nothing"
        assert _comparable(analyze_technicals(shuffled, feed_source="fmp")) == \
               _comparable(analyze_technicals(rows, feed_source="fmp"))


class TestTheFixtureContractThatMadeThisPossible:
    """Pin the PREMISE, so that if FMP ever flips to ascending, the reason the sort exists
    is still documented rather than becoming folklore."""

    @pytest.mark.parametrize("ticker", ALL_FIXTURES)
    def test_fmp_really_does_serve_newest_first(self, ticker):
        rows = _history(ticker)
        first, last = str(rows[0]["date"])[:10], str(rows[-1]["date"])[:10]
        assert first > last, (
            f"{ticker}: fixture is no longer newest-first ({first} .. {last}). The sort in "
            "analyze_technicals is still correct, but this test's premise has changed — "
            "re-read docs/l4a-stx-diagnosis.md before touching the module.")


class TestValueLevelPinsOnWuTheValidatingCase:
    """WU is the validating case, ruled so at L-4a.

    WU is a secular decliner at $7.08, BELOW both moving averages. The defect reported it at
    its 2021 price of $22.73, ABOVE both MAs (MA50 21.24, MA200 18.96) — i.e. it described the
    project's canonical secular-decline name as being in an uptrend, and the trend read
    'bullish' instead of 'bearish'.
    """

    def test_the_booleans_describe_the_newest_end(self):
        t = analyze_technicals(_history("WU"), feed_source="fmp")
        assert t.above_ma50 is False
        assert t.above_ma200 is False
        assert t.trend == "bearish"

    def test_the_moving_averages_are_the_trailing_window_not_the_oldest_one(self):
        t = analyze_technicals(_history("WU"), feed_source="fmp")
        # MA values are surfaced through notes and the vs-MA percentages.
        assert "Price $7.08. MA50=7.70 MA200=8.81" in t.notes
        assert t.price_vs_ma50_pct.value == pytest.approx(-8.1068, abs=1e-3)
        assert t.price_vs_ma200_pct.value == pytest.approx(-19.6126, abs=1e-3)

    def test_it_does_not_report_the_2021_window(self):
        """The exact pre-fix numbers, pinned as forbidden so a regression is named on sight."""
        t = analyze_technicals(_history("WU"), feed_source="fmp")
        assert "22.73" not in t.notes, "reading the OLDEST end again (2021 close)"
        assert "MA50=21.24" not in t.notes, "MA50 is the 2021 window again"
        assert "MA200=18.96" not in t.notes, "MA200 is the 2021 window again"
        assert t.above_ma50 is not True, "2021 WU sat above its MA50; today's does not"

    def test_rsi_is_not_computed_on_a_reversed_series(self):
        """Reversal flips the sign of every delta, so RSI is not merely stale but inverted.
        MEASURED, not reasoned: the defect produced RSI 78.42 (overbought) for WU where the
        correct series gives 28.42 (oversold) — near-mirrored about 50, as a sign flip
        implies. A $7 secular decliner was being handed to the model as strong momentum."""
        t = analyze_technicals(_history("WU"), feed_source="fmp")
        assert t.rsi_14 == pytest.approx(28.415, abs=1e-2)
        assert t.rsi_14 < 40, "a secular decliner should not read as strong momentum"


class TestOtherNamesThatMoveOnTheFix:
    """Ruled blast radius: 8 of 18 boolean cells flip. NOW flips both, and is the clearest
    'wrong at the turning point' case — GOOG/MU/V do not move because a strong uptrend sits
    above both MAs at either end of the window, i.e. the booleans were right by luck exactly
    when they carried least information."""

    def test_now_flips_both_booleans_to_true(self):
        t = analyze_technicals(_history("NOW"), feed_source="fmp")
        assert t.above_ma50 is True
        assert t.above_ma200 is True
        assert "Price $127.54. MA50=107.75 MA200=122.74" in t.notes

    def test_mu_is_unchanged_because_a_strong_uptrend_is_above_both_ends(self):
        t = analyze_technicals(_history("MU"), feed_source="fmp")
        assert t.above_ma50 is True
        assert t.above_ma200 is True
        # but the VALUES were nonsense before: MA200 464.48 today vs 78.87 pre-fix
        assert "MA50=899.05 MA200=464.48" in t.notes


class TestFailClosedWhenOrderCannotBeEstablished:
    """FAIL-CLOSED DEFAULTS (standing rule): a guard that cannot measure denies. Technicals
    computed on an unverifiable order is the defect being fixed, so refusing beats guessing."""

    def test_rows_without_a_date_are_refused_not_guessed(self):
        rows = [{"Close": 10.0 + i, "Volume": 1000} for i in range(300)]
        t = analyze_technicals(rows, feed_source="fmp")
        assert t.trend == "insufficient_data"
        assert t.above_ma50 is None and t.above_ma200 is None and t.rsi_14 is None
        assert "REFUSED" in t.notes
        assert t.price_vs_ma50_pct.value is None

    def test_one_missing_date_among_many_still_refuses(self):
        rows = [{"date": f"2026-01-{i % 28 + 1:02d}", "Close": 10.0, "Volume": 1} for i in range(300)]
        rows[17] = {"Close": 10.0, "Volume": 1}
        assert analyze_technicals(rows, feed_source="fmp").trend == "insufficient_data"
