"""
Phase G — corporate-actions integrity. DARK: nothing here is applied to a live score.

The load-bearing tests are the ones that pin WHY naive detection was rejected. A split
fix that is validated on medians passes while poisoning individual quarters — measured on
GOOG, where a naive adjacent-ratio detector corrupts 2 of 20 points and moves the median
only 4.43% -> 4.26%. So the restatement is asserted PER POINT here, never in aggregate.

The GOOG fixture below is the real filing pattern, reproduced exactly: one period-end
(2021-12-31) filed on BOTH bases by two different filings, and two neighbouring quarters
that straddle the split with no restatement at all. That interleaving is what makes the
series mixed-basis and what any ratio-based detector reads wrong.
"""
import pytest

from adapters.edgar_adapter import EdgarFinancials, ResolvedField, _extract_xbrl_facts
from core.corporate_actions import (
    MIN_RATIO_DEVIATION, REQUIRED_WITNESSES, WITNESS_FMP, WITNESS_RESTATEMENT,
    WITNESS_TAGGED, build_split_report, earliest_share_filing, render_split_report,
    restatement_blocked, restatement_witnesses, split_factor, tagged_ratio_witnesses,
)

SHARES = "CommonStockSharesOutstanding"
TAGGED = "StockholdersEquityNoteStockSplitConversionRatio1"

# GOOG's actual records around the 2022-07-18 20:1 split.
GOOG_ROWS = [
    ("2022-06-30", 13_078_000_000, "2022-07-27"),   # filed AFTER  -> already post-split
    ("2022-03-31", 658_763_000, "2022-04-27"),      # filed BEFORE -> pre-split basis
    ("2021-12-31", 13_242_000_000, "2022-07-27"),   # RESTATED by a later filing
    ("2021-12-31", 662_121_000, "2022-02-02"),      # ...and the original, still present
    ("2021-09-30", 664_682_000, "2021-10-27"),      # filed BEFORE -> pre-split basis
]


def _fin(rows=GOOG_ROWS, tagged=None):
    concepts = {SHARES: [{"value": v, "unit": "shares", "start": None, "end": e,
                          "fy": None, "fp": None, "form": "10-Q",
                          "accession": f"acc-{f}", "first_filed": f}
                         for e, v, f in rows]}
    if tagged is not None:
        concepts[TAGGED] = [{"value": tagged, "unit": "pure", "start": None,
                             "end": "2022-07-15", "fy": None, "fp": None,
                             "form": "10-K", "accession": "acc-t",
                             "first_filed": "2022-07-27"}]
    return EdgarFinancials(concepts=concepts, latest_period_end="2022-06-30")


def _fmp(ratio=20.0, ex="2022-07-18"):
    return [{"ex_date": ex, "ratio": ratio, "numerator": ratio, "denominator": 1}]


class TestWitnesses:
    def test_restatement_witness_recovers_the_ratio_from_edgar_alone(self):
        """One period-end filed at two values IS the split ratio — at zero fetch cost,
        from the issuer's own filings, independent of FMP."""
        found = restatement_witnesses(_fin())
        assert len(found) == 1
        ratio, detail = found[0]
        assert ratio == pytest.approx(20.0, rel=1e-3)
        assert "2021-12-31" in detail

    def test_rounding_duplicates_are_not_split_witnesses(self):
        """NOW files 2020-12-31 as both 195,844,000 and 195,845,000. Filing precision is
        not a corporate action; a witness must clear MIN_RATIO_DEVIATION."""
        rows = [("2020-12-31", 195_844_000, "2021-02-01"),
                ("2020-12-31", 195_845_000, "2021-04-01")]
        assert restatement_witnesses(_fin(rows)) == []

    def test_tagged_ratio_is_a_third_witness(self):
        assert tagged_ratio_witnesses(_fin(tagged=20))[0][0] == pytest.approx(20.0)

    def test_a_tagged_ratio_of_one_is_ignored(self):
        assert tagged_ratio_witnesses(_fin(tagged=1)) == []


class TestCorroboration:
    def test_three_witnesses_corroborate(self):
        rep = build_split_report("GOOG", _fmp(), _fin(tagged=20))
        assert len(rep.usable) == 1
        ev = rep.usable[0]
        assert ev.witnesses == [WITNESS_FMP, WITNESS_RESTATEMENT, WITNESS_TAGGED]
        assert ev.ex_date == "2022-07-18"      # DATE ALWAYS FROM FMP, never the 07-15 tag

    def test_fmp_alone_is_not_enough_and_says_so(self):
        """The single-source failure mode is a clean 20x that reads as a valuation rather
        than an error, so an uncorroborated split is refused AND announced."""
        rows = [(e, v, f) for e, v, f in GOOG_ROWS if v != 13_242_000_000]
        rep = build_split_report("GOOG", _fmp(), _fin(rows))
        assert rep.events and not rep.events[0].corroborated
        assert rep.usable == []
        assert rep.has_uncorroborated
        assert any("UNCORROBORATED" in n for n in rep.notes)

    def test_required_witnesses_is_two_of_three(self):
        rep = build_split_report("GOOG", _fmp(), _fin())   # fmp + restatement, no tag
        assert len(rep.usable[0].witnesses) == REQUIRED_WITNESSES

    def test_edgar_ratio_with_no_fmp_record_is_unplaceable_not_applied(self):
        """EDGAR can attest a RATIO but only dates it to a declaration date. Without an
        ex-date there is nothing to place it against, so it is reported, never used."""
        rep = build_split_report("GOOG", [], _fin(tagged=20))
        assert rep.usable == []
        assert any("UNPLACEABLE" in n for n in rep.notes)

    def test_a_split_predating_every_share_filing_is_out_of_scope_not_uncorroborated(self):
        """EDGAR's XBRL record starts ~2009, so pre-XBRL splits can NEVER earn a second
        witness. Demanding one would leave MU/JPM/USB permanently uncorroborated over
        splits that provably cannot move a number."""
        # No restatement in the series — MU's splits are all pre-XBRL, so EDGAR holds no
        # witness for them and never will.
        quiet = [("2022-06-30", 1_100_000_000, "2022-07-27"),
                 ("2022-03-31", 1_090_000_000, "2022-04-27")]
        rep = build_split_report("MU", _fmp(2.0, "2000-05-02"), _fin(quiet))
        assert rep.events == [] and rep.usable == []
        assert rep.out_of_scope and not rep.notes
        assert rep.horizon == "2022-04-27"

    def test_horizon_is_the_oldest_share_filing(self):
        assert earliest_share_filing(_fin()) == "2021-10-27"

    def test_render_does_not_raise_on_every_shape(self):
        for fin, fmp in ((_fin(tagged=20), _fmp()), (_fin(), []), (_fin(), _fmp(1.01))):
            assert render_split_report(build_split_report("X", fmp, fin))


class TestSplitFactor:
    def test_a_fact_filed_before_the_split_is_adjusted(self):
        rep = build_split_report("GOOG", _fmp(), _fin(tagged=20))
        assert split_factor("2022-04-27", rep.usable) == pytest.approx(20.0)

    def test_a_fact_filed_after_the_split_is_left_alone(self):
        rep = build_split_report("GOOG", _fmp(), _fin(tagged=20))
        assert split_factor("2022-07-27", rep.usable) == pytest.approx(1.0)

    def test_the_restated_and_original_copies_reconcile(self):
        """The two 2021-12-31 rows are the SAME fact on two bases. Adjusting each by its
        own filing date must land them on the same number — this is what makes the rule
        self-validating and independent of which duplicate a de-dupe happens to keep."""
        rep = build_split_report("GOOG", _fmp(), _fin(tagged=20))
        original = 662_121_000 * split_factor("2022-02-02", rep.usable)
        restated = 13_242_000_000 * split_factor("2022-07-27", rep.usable)
        assert original == pytest.approx(restated, rel=0.001)

    def test_missing_filing_date_adjusts_nothing(self):
        rep = build_split_report("GOOG", _fmp(), _fin(tagged=20))
        assert split_factor(None, rep.usable) == 1.0

    def test_uncorroborated_splits_never_reach_the_factor(self):
        rows = [(e, v, f) for e, v, f in GOOG_ROWS if v != 13_242_000_000]
        rep = build_split_report("GOOG", _fmp(), _fin(rows))
        assert split_factor("2022-04-27", rep.usable) == 1.0


class TestFirstFiledCapture:
    """G-1: the extraction must carry the EARLIEST filing date a value appeared under."""

    def _facts(self, entries):
        return {"facts": {"us-gaap": {SHARES: {"units": {"shares": entries}}}, "dei": {}}}

    def test_earliest_filing_wins_across_the_dedupe(self):
        """A later filing REPEATING a value verbatim did not restate it, so the value
        still carries its original basis. Taking the latest date would read a repeated
        pre-split value as post-split and silently skip its adjustment."""
        fin = _extract_xbrl_facts(self._facts([
            {"val": 662_121_000, "end": "2021-12-31", "form": "10-K",
             "accn": "0001-22-000019", "filed": "2022-02-02"},
            {"val": 662_121_000, "end": "2021-12-31", "form": "10-Q",
             "accn": "0001-22-000029", "filed": "2022-04-27"},
        ]))
        recs = fin.concepts[SHARES]
        assert len(recs) == 1                       # same value, collapsed
        assert recs[0]["accession"] == "0001-22-000029"   # newest accession kept...
        assert recs[0]["first_filed"] == "2022-02-02"     # ...earliest filing preserved

    def test_a_restatement_is_a_separate_record_with_its_own_date(self):
        fin = _extract_xbrl_facts(self._facts([
            {"val": 662_121_000, "end": "2021-12-31", "form": "10-K",
             "accn": "0001-22-000019", "filed": "2022-02-02"},
            {"val": 13_242_000_000, "end": "2021-12-31", "form": "10-Q",
             "accn": "0001-22-000071", "filed": "2022-07-27"},
        ]))
        by_val = {r["value"]: r["first_filed"] for r in fin.concepts[SHARES]}
        assert by_val == {662_121_000: "2022-02-02", 13_242_000_000: "2022-07-27"}

    def test_corporate_action_concepts_do_not_move_the_staleness_clock(self):
        """A split-ratio fact is dated to the split, not to a reporting period. Letting it
        into the clock would let a corporate action move every field's freshness gate."""
        facts = {"facts": {"us-gaap": {
            SHARES: {"units": {"shares": [
                {"val": 100, "end": "2020-01-01", "form": "10-K",
                 "accn": "a", "filed": "2020-02-01"}]}},
            TAGGED: {"units": {"pure": [
                {"val": 20, "end": "2099-01-01", "form": "10-K",
                 "accn": "b", "filed": "2020-02-01"}]}},
        }, "dei": {}}}
        assert _extract_xbrl_facts(facts).latest_period_end == "2020-01-01"


class TestRestatedOwnHistory:
    """G-3: the series with the share counts put on today's basis. DARK — the live anchor
    still comes from own_history_earnings_yields until G-4 arms."""

    NI = 40_000_000_000.0   # flat TTM earnings, so only the SHARE basis can move a yield

    def _edgar(self, rows=GOOG_ROWS):
        from adapters.edgar_adapter import EdgarData
        from adapters.base import Prov
        fin = _fin(rows, tagged=20)
        # net_income as a resolved TTM series over the same period-ends
        from datetime import date, timedelta
        # Full-year spans, so _assemble_ttm resolves each period-end via ttm_annual.
        fin.concepts["NetIncomeLoss"] = [
            {"value": self.NI, "unit": "USD",
             "start": (date.fromisoformat(e) - timedelta(days=364)).isoformat(), "end": e,
             "fy": None, "fp": "FY", "form": "10-K", "accession": f"ni-{e}",
             "first_filed": f}
            for e, _, f in rows
        ]
        fin.fields["net_income"] = ResolvedField(
            name="net_income", value=self.NI, period_end="2022-06-30",
            concept="NetIncomeLoss", method="ttm_annual")
        fin.fields["shares_outstanding"] = ResolvedField(
            name="shares_outstanding", value=13_078_000_000, period_end="2022-06-30",
            concept=SHARES, method="instant")
        p = Prov(value=None, source="edgar", as_of="", confidence="low")
        return EdgarData(ticker="GOOG", cik="", company_name=None, sic=None,
                         sic_description=None, fiscal_year_end=None, recent_10k=[],
                         recent_10q=[], risk_factors_excerpt=p, mda_excerpt=p,
                         xbrl_concept_count=0, financials=fin)

    PRICES = [{"date": d, "Close": 100.0} for d in
              ("2021-09-30", "2021-12-31", "2022-03-31", "2022-06-30")]

    def test_every_quarter_lands_on_one_basis(self):
        """THE POINT OF PHASE G. With earnings and price held flat, any spread in the
        yields is pure share-basis error. A naive detector leaves 20x outliers here;
        the filed-date rule must leave none."""
        from core.valuation_anchors import own_history_restated
        rep = build_split_report("GOOG", _fmp(), self._edgar().financials)
        series = own_history_restated(self._edgar(), self.PRICES, rep)
        assert len(series) == 4
        yields = [h["earnings_yield"] for h in series]
        assert max(yields) / min(yields) < 1.05      # NOT 20x — per-point, not median

    def test_the_split_boundary_quarters_are_adjusted_and_the_others_are_not(self):
        from core.valuation_anchors import own_history_restated
        rep = build_split_report("GOOG", _fmp(), self._edgar().financials)
        by = {h["period_end"]: h for h in
              own_history_restated(self._edgar(), self.PRICES, rep)}
        assert by["2022-06-30"]["split_factor"] == pytest.approx(1.0)
        assert by["2022-03-31"]["split_factor"] == pytest.approx(20.0)
        assert by["2021-09-30"]["split_factor"] == pytest.approx(20.0)
        # the restated copy of 2021-12-31 is already on today's basis
        assert by["2021-12-31"]["split_factor"] == pytest.approx(1.0)

    def test_no_truncation_survives(self):
        """The live series BREAKS at the discontinuity and loses everything older. The
        restated one corrects the split instead of fleeing it."""
        from core.valuation_anchors import (own_history_earnings_yields,
                                            own_history_restated)
        rep = build_split_report("GOOG", _fmp(), self._edgar().financials)
        live = own_history_earnings_yields(self._edgar(), self.PRICES)
        new = own_history_restated(self._edgar(), self.PRICES, rep)
        assert len(live) < len(new) == 4

    def test_a_point_with_no_filing_date_is_dropped_not_guessed(self):
        """Recorded fixtures predate G-1 and carry no filing date. An unknown basis is
        NOT 'assume today's' — that is exactly how a 20x artifact would launder in."""
        from core.valuation_anchors import own_history_restated
        ed = self._edgar()
        for r in ed.financials.concepts[SHARES]:
            r["first_filed"] = None
        rep = build_split_report("GOOG", _fmp(), self._edgar().financials)
        assert own_history_restated(ed, self.PRICES, rep) == []

    def test_with_no_splits_the_two_series_agree_point_for_point(self):
        """Seven of the nine tracked tickers have no in-scope split. G must be a no-op
        for them, asserted per quarter rather than on a median."""
        from core.valuation_anchors import (own_history_earnings_yields,
                                            own_history_restated)
        quiet = [("2022-06-30", 1_100_000_000, "2022-07-27"),
                 ("2022-03-31", 1_090_000_000, "2022-04-27"),
                 ("2021-12-31", 1_080_000_000, "2022-02-02"),
                 ("2021-09-30", 1_070_000_000, "2021-10-27")]
        ed = self._edgar(quiet)
        live = own_history_earnings_yields(ed, self.PRICES)
        new = own_history_restated(ed, self.PRICES,
                                   build_split_report("X", [], ed.financials))
        assert len(live) == len(new) == 4
        for a, b in zip(live, new):
            assert a["period_end"] == b["period_end"]
            assert a["earnings_yield"] == pytest.approx(b["earnings_yield"])


class TestPriceHistoryDepthPin:
    """RULED 2026-08-11: pin the limit=365 risk immediately.

    fetch_payload requests `historical-price-eod/full?limit=365`, but FMP returns ~1,255
    rows (~5 years) — the limit is NOT honoured, and the entire depth of the own-history
    anchor rests on that. If FMP ever starts honouring it, every own-history series drops
    below MIN_HISTORY_POINTS and the anchor silently goes to 0/20 across the board. That
    is a total loss of the only issuer-referenced denominator, and it would look like a
    data gap rather than a regression.

    The recorded FMP fixtures are the tripwire: they are captured through the adapter's
    own live fetch path, so the day a re-record brings back a one-year series this fails
    — at the deliberate baseline-move gate, which is exactly where it should surface.
    """
    import pytest as _pytest

    # 24 quarters is what ttm_series asks for; MIN_HISTORY_POINTS is the withholding floor.
    REQUIRED_YEARS = 4.0

    @_pytest.mark.parametrize("ticker", ["MU", "GOOG", "NOW", "WU", "JPM"])
    def test_recorded_price_history_spans_the_own_history_window(self, ticker):
        import json
        from pathlib import Path
        rows = json.loads(
            Path(f"tests/fixtures/fmp/{ticker}.json").read_text())["price_history"]
        dates = sorted(str(r["date"])[:10] for r in rows)
        span_years = (int(dates[-1][:4]) - int(dates[0][:4])
                      + (int(dates[-1][5:7]) - int(dates[0][5:7])) / 12.0)
        assert span_years >= self.REQUIRED_YEARS, (
            f"{ticker} price history spans only {span_years:.1f}y. If FMP began honouring "
            f"limit=365, the own-history anchor is now silently unavailable for every "
            f"ticker — raise the limit at the fetch_payload call site.")

    def test_the_window_covers_the_withholding_floor(self):
        """A 4-year span is >= MIN_HISTORY_POINTS quarters with margin, so the assertion
        above is pinned to the thing that actually matters and not to a magic number."""
        from core.valuation_anchors import MIN_HISTORY_POINTS
        assert self.REQUIRED_YEARS * 4 >= MIN_HISTORY_POINTS


class TestRestatementRefusal:
    """The guard that turns G from 'strictly better' into 'never strictly worse'.

    The restated series does not truncate, so an unknown split state has nothing holding
    it back: run it on GOOG with no split record and 2022-03-31 reads 81.02% against a
    ~4% norm — the exact artifact Phase G exists to remove, reintroduced by the fix. This
    was found by running the dark surface before arming, and it is pinned here.
    """

    def test_missing_split_record_is_refused(self):
        assert "unavailable" in restatement_blocked(None)

    def test_an_uncorroborated_in_scope_split_is_refused(self):
        rows = [(e, v, f) for e, v, f in GOOG_ROWS if v != 13_242_000_000]
        rep = build_split_report("GOOG", _fmp(), _fin(rows))
        blocked = restatement_blocked(rep)
        assert blocked and "2-of-3" in blocked

    def test_a_corroborated_split_is_not_refused(self):
        assert restatement_blocked(build_split_report("GOOG", _fmp(), _fin(tagged=20))) is None

    def test_no_splits_at_all_is_not_refused(self):
        """'This issuer never split' is a KNOWN state and is safe. Only 'we could not find
        out' is refused — conflating the two is what the report type prevents."""
        quiet = [("2022-06-30", 1_100_000_000, "2022-07-27")]
        assert restatement_blocked(build_split_report("WU", [], _fin(quiet))) is None

    def test_a_refused_restatement_yields_no_series_not_a_raw_one(self):
        """THE MEASURED TRAP: without this the caller receives an untruncated,
        unadjusted series and cannot tell it from a good one."""
        from core.valuation_anchors import own_history_restated
        t = TestRestatedOwnHistory()
        ed = t._edgar()
        rows = [(e, v, f) for e, v, f in GOOG_ROWS if v != 13_242_000_000]
        uncorroborated = build_split_report("GOOG", _fmp(), _fin(rows))
        assert own_history_restated(ed, t.PRICES, uncorroborated) == []
        assert own_history_restated(ed, t.PRICES, None) == []
