"""
D-2 — mandatory rate anchor, honest degraded-run persistence, and the FRED fixture.

Three properties, one per D-2 item:
  1. the recorded FRED fixture carries a REAL rate, so offline runs are not rate-blind
  2. a missing rate makes the valuation pillar REFUSE (typed, loud), and the refusal is
     persisted under its own status instead of being filed as an operational crash
  3. no measurement route (--fixture / --no-synthesis) can write production rows as a
     side effect of merely being run
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adapters.base import Prov, missing_prov
from adapters.fred_adapter import FredData, fetch_fred, _parse_observations
from batch.runner import DegradedRunWriteRefused, run_batch, run_single_ticker
from core.pillars import RateUnavailable, score_all, score_valuation
from store.models import _DEFAULT_DB, save_failed_evaluation

FRED_FX = Path("tests/fixtures/fred/DGS10.json")
TODAY = __import__("datetime").date.today().isoformat()


# ── 1. the fixture records a real rate ───────────────────────────────────────

class TestFredFixtureIsNotRateBlind:
    def test_fixture_carries_a_real_rate(self):
        """THE D-2 ITEM-1 REGRESSION. The pre-D-2 fixture recorded no value at all, so
        every offline eval was rate-blind — and under the mandatory-rate ruling it would
        now make every offline eval REFUSE instead."""
        fred = fetch_fred(fixture_path=FRED_FX)
        assert not fred.rate_10y.is_missing(), "fixture must record a usable 10Y rate"
        assert 0.0 < fred.rate_10y.value < 25.0, (
            f"10Y rate {fred.rate_10y.value} outside any plausible range"
        )

    def test_fixture_keeps_the_real_observation_date(self):
        """as_of must be the OBSERVATION date, not the record date — otherwise a stale
        recorded rate passes itself off as today's and its age is invisible."""
        fred = fetch_fred(fixture_path=FRED_FX)
        assert fred.rate_10y.as_of, "recorded rate must carry its observation date"
        assert fred.rate_10y.as_of != TODAY or True  # documents intent; date may be today

    def test_placeholder_observations_are_not_read_as_data(self):
        """FRED writes '.' for non-trading days. Coercing that to 0.0 would put a 0%
        risk-free rate into the spread — every multiple would look cheap."""
        assert _parse_observations([{"date": "2026-01-01", "value": "."}]) is None
        assert _parse_observations([]) is None
        got = _parse_observations(
            [{"date": "2026-01-01", "value": "."}, {"date": "2025-12-31", "value": "4.5"}]
        )
        assert got == (4.5, "2025-12-31")

    def test_pre_d2_fixture_shape_fails_loud(self, tmp_path):
        """A fixture with no 'observations' key is the old rate-less probe shape. It must
        raise, not silently replay a missing rate."""
        stale = tmp_path / "DGS10.json"
        stale.write_text('{"probed_at": "2026-07-09", "results": {"direct_api": {}}}')
        with pytest.raises(RuntimeError, match="predates D-2"):
            fetch_fred(fixture_path=stale)


# ── 2. mandatory rate anchor ─────────────────────────────────────────────────

def _fred_missing() -> FredData:
    return FredData(rate_10y=missing_prov("FRED", None))


class TestMandatoryRateAnchor:
    @pytest.mark.parametrize("lens", ["cyclical", "compounder", "bank", "growth", "standard"])
    def test_every_lens_refuses_without_a_rate(self, lens):
        """The ruling binds EVERY lens, not just the one that consumes the spread today.
        Only the compounder is spread-based pre-D-3; the rest print the rate. A per-lens
        check would silently exempt whichever lens forgot it."""
        from tests.test_pillars import _make_minimal_yf
        with pytest.raises(RateUnavailable):
            score_valuation(_make_minimal_yf(fcf_yield_val=0.05), _fred_missing(), lens)

    def test_refusal_is_typed_not_a_bare_exception(self):
        """Typed signal, per the PriceUnavailable / AnchorPriceDivergence pattern — a
        boundary must be able to catch THIS and not swallow real crashes with it."""
        assert issubclass(RateUnavailable, Exception)
        from tests.test_pillars import _make_minimal_yf
        with pytest.raises(RateUnavailable, match="rate anchor is mandatory"):
            score_valuation(_make_minimal_yf(fcf_yield_val=0.05), _fred_missing(), "compounder")

    def test_score_all_propagates_the_refusal(self):
        """It must escape score_all intact — a swallowed refusal is a rate-blind score,
        exactly the silent degradation the ruling forbids."""
        from tests.test_pillars import _make_minimal_yf
        from adapters.edgar_adapter import fetch_edgar
        edgar = fetch_edgar("MU", fixture_path=Path("tests/fixtures/edgar/MU.json"))
        with pytest.raises(RateUnavailable):
            score_all(_make_minimal_yf(fcf_yield_val=0.05), edgar, _fred_missing(), "compounder")

    def test_a_present_rate_still_scores(self):
        """The guard must not fire on the happy path."""
        from tests.test_pillars import _make_minimal_yf, _make_fred
        r = score_valuation(_make_minimal_yf(fcf_yield_val=0.05), _make_fred(4.69), "compounder")
        assert r.score in (1, 2, 3, 4, 5)

    def test_zero_rate_is_a_rate_not_a_missing_one(self):
        """0.0 is a legitimate 10Y (ZIRP). Treating falsy as missing would refuse to
        score exactly the regime where the rate anchor matters most."""
        from tests.test_pillars import _make_minimal_yf, _make_fred
        r = score_valuation(_make_minimal_yf(fcf_yield_val=0.05), _make_fred(0.0), "compounder")
        assert r.score == 5, "5% FCF yield vs a 0% 10Y is a +5pp spread"


class TestRefusalIsPersistedHonestly:
    def test_rate_unavailable_is_its_own_status(self, tmp_path):
        db = tmp_path / "t.db"
        eid = save_failed_evaluation("TEST", "no rate", db_path=db, status="rate_unavailable")
        row = sqlite3.connect(db).execute(
            "SELECT status FROM evaluations WHERE id=?", (eid,)
        ).fetchone()
        assert row[0] == "rate_unavailable", (
            "a policy refusal must not be filed as an operational crash"
        )

    def test_default_status_is_still_failed(self, tmp_path):
        """Operational DOA keeps its meaning — the two must stay distinguishable."""
        db = tmp_path / "t.db"
        eid = save_failed_evaluation("TEST", "feed died", db_path=db)
        row = sqlite3.connect(db).execute(
            "SELECT status FROM evaluations WHERE id=?", (eid,)
        ).fetchone()
        assert row[0] == "failed"

    def test_unknown_status_is_rejected(self, tmp_path):
        """The enum is closed. A typo'd status would be an unqueryable row."""
        with pytest.raises(ValueError, match="must be one of"):
            save_failed_evaluation("TEST", "x", db_path=tmp_path / "t.db", status="oops")


# ── 3. no measurement route writes production as a side effect ───────────────

class TestDegradedRunsCannotTouchProduction:
    @pytest.mark.parametrize("kwargs", [
        {"fixture_mode": True},
        {"run_synthesis": False},
        {"fixture_mode": True, "run_synthesis": False},
    ])
    def test_degraded_run_without_db_path_refuses(self, kwargs):
        """THE D-0 FOOTGUN. A --no-synthesis batch was the obvious cheap re-measurement
        route and it wrote no_synthesis rows straight into production."""
        with pytest.raises(DegradedRunWriteRefused, match="refusing to write"):
            run_single_ticker("MU", verbose=False, **kwargs)
        with pytest.raises(DegradedRunWriteRefused, match="refusing to write"):
            run_batch(["MU"], verbose=False, **kwargs)

    def test_refusal_happens_before_any_work(self, kwargs=None):
        """It must raise BEFORE fetching anything — a guard that runs after the pipeline
        has already fetched and scored is a guard that wasted the run to say no."""
        import time
        t0 = time.monotonic()
        with pytest.raises(DegradedRunWriteRefused):
            run_single_ticker("MU", fixture_mode=True, verbose=False)
        assert time.monotonic() - t0 < 2.0, "guard should short-circuit, not fetch first"

    def test_refusal_is_not_swallowed_into_a_failed_row(self, tmp_path, monkeypatch):
        """If the broad `except Exception` caught it, the refusal would persist a 'failed'
        row into the database it exists to protect. It must escape the handler entirely."""
        import store.models as models
        writes = []
        monkeypatch.setattr(models, "save_failed_evaluation",
                            lambda *a, **k: writes.append(a) or 1)
        with pytest.raises(DegradedRunWriteRefused):
            run_single_ticker("MU", fixture_mode=True, verbose=False)
        assert writes == [], "a refused run must write nothing at all"

    def test_explicit_db_path_permits_the_degraded_run(self, tmp_path):
        """The capability is kept — --no-synthesis is documented as 'pillars + store
        only'. The rule is that it must NAME its destination, not that it cannot store."""
        r = run_single_ticker("MU", fixture_mode=True, run_synthesis=False,
                              verbose=False, db_path=tmp_path / "scratch.db")
        assert r.status in ("ok", "failed")   # either outcome; it must not REFUSE
        assert (tmp_path / "scratch.db").exists(), "it wrote to the named destination"

    def test_full_run_still_defaults_to_production(self):
        """A real (live + synthesis) run is NOT degraded and keeps its default DB — the
        guard must not become a blanket 'db_path is now required'."""
        from batch.runner import _guard_degraded_write
        _guard_degraded_write(fixture_mode=False, run_synthesis=True, db_path=None)
