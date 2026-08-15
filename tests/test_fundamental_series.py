"""Phase H-1 — FCF component series + its storage shape.

PER-POINT ASSERTIONS, NOT MEDIANS. Standing ruling from Phase G: a median comparison
provably passes a broken implementation. Every test here pins a specific period-end.

The three 2026-08-15 rulings each have a test that fails if it is quietly undone:
  grain        -> test_fy_rows_are_a_queryable_subset_not_a_separate_build
  negative FCF -> test_negative_fcf_is_STORED_and_only_filtered_at_read_time
  reinvestment -> test_reinvestment_is_null_with_a_reason_and_never_a_proxy
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.edgar_adapter import fetch_edgar
from adapters.fmp_adapter import fetch_fmp, fetch_splits
from core.corporate_actions import build_split_report
from core.fundamental_series import (
    BASIS_NOT_APPLICABLE,
    EXCL_NEGATIVE_FCF,
    EXCL_NON_POSITIVE_BASE,
    METRIC_FCF,
    METRIC_FCF_GROWTH,
    METRIC_FCF_MARGIN,
    METRIC_FCF_YIELD,
    METRIC_REINVESTMENT,
    METRIC_SALES_TO_CAPITAL,
    PERIOD_FY,
    PERIOD_TTM_Q,
    WITHHELD_NO_CAPEX,
    WITHHELD_NO_DA_SPEC,
    build_fcf_series,
    run_dark_fcf_series,
)
from store.models import (
    list_fundamental_series,
    save_fundamental_series,
)

FIXTURES = Path(__file__).parent / "fixtures" / "edgar"
FMP_FIXTURES = Path(__file__).parent / "fixtures" / "fmp"


def _edgar(ticker: str):
    return fetch_edgar(ticker, fixture_path=FIXTURES / f"{ticker}.json")


def _price_history(ticker: str):
    """The REAL recorded price history, THROUGH THE ADAPTER — not the raw fixture rows.

    The yield leg is the only one that touches a price, and F1 found it had never produced
    a value under test because every case passed an empty list. A synthetic flat price
    would satisfy `if shares and price` while proving nothing about the join.

    It has to come through `fetch_fmp` rather than straight off the JSON: the adapter
    renames FMP's `close` to `Close`, and `_price_on_or_before` reads `Close`. Reading the
    raw rows here would hand every lookup a None and reproduce the exact hole F1 found,
    while looking like it had been fixed.
    """
    return fetch_fmp(ticker, fixture_path=FMP_FIXTURES / f"{ticker}.json").price_history


def _split_report(ticker: str):
    """A REAL split report, resolved through the ADAPTER'S OWN fetch path.

    Deliberately not re-normalised here: `fetch_splits` already turns the recorded FMP
    rows into {ex_date, ratio} and already returns None for a fixture with no `splits`
    key. Re-implementing either would be a second copy of the contract that could drift
    from the one production runs.

    `None` means UNKNOWN, and is passed straight through to a refusal — MU/C/BK carry no
    recorded splits and must keep the truncated basis.
    """
    splits = fetch_splits(ticker, fixture_path=FMP_FIXTURES / f"{ticker}.json")
    if splits is None:
        return None
    return build_split_report(ticker, splits, _edgar(ticker).financials)


def _series(ticker: str, price_history=None, split_report=None):
    return build_fcf_series(ticker, _edgar(ticker), price_history or [], split_report)


def _priced_series(ticker: str):
    """The full production shape: real prices AND a real split report."""
    return build_fcf_series(ticker, _edgar(ticker), _price_history(ticker),
                            _split_report(ticker))


def _point(result, metric: str, period_end: str):
    return next((p for p in result.by_metric(metric) if p.period_end == period_end), None)


# ── The measurement itself ───────────────────────────────────────────────────

def test_fcf_is_ocf_minus_capex_at_a_named_period_end():
    """capex is filed as a POSITIVE outflow magnitude, so FCF is a SUBTRACTION.

    Pinned on GOOG's FY2025, which the H-FCF scoping report measured independently at
    73.27B against FMP's annual freeCashFlow (0.0% divergence). If the sign convention
    ever flips, this reads ~256B and fails loudly.
    """
    p = _point(_series("GOOG"), METRIC_FCF, "2025-12-31")
    assert p is not None
    assert p.components["operating_cashflow"] == pytest.approx(164_713_000_000)
    assert p.components["capex"] == pytest.approx(91_447_000_000)
    assert p.value == pytest.approx(73_266_000_000)


def test_the_mrq_point_reproduces_the_scoping_reports_unmatched_reading():
    """GOOG at 2026-06-30 is 53.27B — the number the scoping report showed diverging
    27.3% from FMP's ANNUAL figure before period matching. Pinned so the series and the
    cross-check cannot silently drift apart about what the same quarter is worth."""
    p = _point(_series("GOOG"), METRIC_FCF, "2026-06-30")
    assert p.value == pytest.approx(53_273_000_000)
    assert p.period_type == PERIOD_TTM_Q


def test_a_no_capex_issuer_withholds_the_whole_family_rather_than_guessing():
    """V and JPM file no PaymentsToAcquirePropertyPlantAndEquipment concept at all.

    An accepted data limit, already recorded for the cross-check. The correct behaviour is
    an empty series with a NAMED reason — never FCF defaulted to operating cash flow.
    """
    for ticker in ("V", "JPM"):
        r = _series(ticker)
        assert r.points == []
        assert r.withheld[METRIC_FCF] == WITHHELD_NO_CAPEX


# ── RULING 1 — grain ─────────────────────────────────────────────────────────

def test_fy_rows_are_a_queryable_subset_not_a_separate_build():
    """Per-year is a FILTER over the native quarterly series, not a second series.

    GOOG's 2025-12-31 is a fiscal year end and 2026-06-30 is not, and both are stored.
    """
    r = _series("GOOG")
    fcf = r.by_metric(METRIC_FCF)
    assert _point(r, METRIC_FCF, "2025-12-31").period_type == PERIOD_FY
    assert _point(r, METRIC_FCF, "2026-06-30").period_type == PERIOD_TTM_Q
    fy = [p for p in fcf if p.period_type == PERIOD_FY]
    assert 0 < len(fy) < len(fcf), "FY must be a strict subset of the quarterly series"


def test_fiscal_year_ends_come_from_the_filings_not_from_the_calendar():
    """MU's fiscal year ends in AUGUST. Inferring FY from month-of-year would mislabel
    every one of its rows, so the flag is taken from fp='FY' on a 10-K."""
    fy = {p.period_end for p in _series("MU").by_metric(METRIC_FCF)
          if p.period_type == PERIOD_FY}
    assert fy, "MU must have fiscal year ends"
    assert all(not pe.endswith("-12-31") for pe in fy), sorted(fy)


# ── RULING 2 — negative FCF is stored, filtered only at read time ─────────────

def test_negative_fcf_is_STORED_and_only_filtered_at_read_time():
    """THE LOAD-BEARING TEST OF THE ADDENDUM.

    C has 14 negative-FCF quarters of 21 (the scoping report measured 14 of 21
    independently). All 14 must be PRESENT in storage and flagged, because Phase M
    samples a distribution and dropping them removes exactly the left tail it exists to
    model. The anchor read filters them; the stored series does not.
    """
    r = _series("C")
    stored = r.by_metric(METRIC_FCF)
    excluded = [p for p in stored if p.excluded]
    assert len(stored) == 21
    assert len(excluded) == 14
    assert len(r.anchor_usable(METRIC_FCF)) == 7
    assert all(p.exclusion_reason == EXCL_NEGATIVE_FCF for p in excluded)
    # The values are really there, not nulled out.
    assert all(p.value is not None and p.value <= 0 for p in excluded)
    assert _point(r, METRIC_FCF, "2025-12-31").value == pytest.approx(-74_152_000_000)


def test_the_anchor_read_and_the_phase_m_read_differ_by_exactly_the_exclusions():
    r = _series("MU")
    stored = r.by_metric(METRIC_FCF)
    usable = r.anchor_usable(METRIC_FCF)
    assert len(stored) - len(usable) == r.excluded_count(METRIC_FCF)
    assert r.excluded_count(METRIC_FCF) == 8, "MU: 16 positive of 24 (scoping §4c)"


def test_growth_off_a_non_positive_base_is_stored_but_excluded():
    """-1.1B -> +0.9B is not '+180% growth'. The point is kept for Phase M and flagged
    so the anchor never reads it as a growth rate."""
    bad = [p for p in _series("MU").by_metric(METRIC_FCF_GROWTH) if p.excluded]
    assert bad, "MU swings through negative FCF and must produce excluded growth points"
    assert all(p.exclusion_reason == EXCL_NON_POSITIVE_BASE for p in bad)
    assert all(p.components["base"] <= 0 for p in bad)


def test_a_negative_margin_is_a_reading_not_an_exclusion():
    """A negative FCF margin is economically meaningful, unlike a negative yield. It must
    not inherit the yield exclusion."""
    for p in _series("C").by_metric(METRIC_FCF_MARGIN):
        assert not p.excluded


# ── RULING 3 — reinvestment is null, never a proxy ───────────────────────────

def test_reinvestment_is_null_with_a_reason_and_never_a_proxy():
    """Reinvestment needs capex - D&A + dWC and there is no D&A spec among the 19.

    The column exists so Phase M needs no migration; the value is NULL and says why.
    A silent proxy (capex alone, say) would be a fabricated fundamental.
    """
    pts = _series("GOOG").by_metric(METRIC_REINVESTMENT)
    assert pts, "the column must be populated with rows, not absent"
    assert all(p.value is None for p in pts)
    assert all(p.null_reason == WITHHELD_NO_DA_SPEC for p in pts)


def test_a_null_reason_is_never_an_exclusion_reason(tmp_path):
    """F3 — the two reasons are separate columns and must not leak into each other.

    A structurally-unavailable value is NOT a rejected one. If these ever shared a column,
    `exclusion_reason IS NOT NULL` would silently mean two different things to Phase M.
    """
    r = _series("MU")
    for p in r.by_metric(METRIC_REINVESTMENT):
        assert p.null_reason == WITHHELD_NO_DA_SPEC
        assert p.exclusion_reason is None
        assert p.excluded is False
    for p in r.by_metric(METRIC_FCF):
        assert p.null_reason is None
        assert (p.exclusion_reason is not None) == p.excluded

    # ...and the separation survives the round trip through storage.
    db = tmp_path / "reasons.db"
    save_fundamental_series(r.by_metric(METRIC_REINVESTMENT) + r.by_metric(METRIC_FCF),
                            db_path=db)
    rows = list_fundamental_series(ticker="MU", db_path=db)
    for row in rows:
        if row["value"] is None:
            assert row["null_reason"] and not row["exclusion_reason"]
        elif row["excluded"]:
            assert row["exclusion_reason"] and not row["null_reason"]
        else:
            assert not row["exclusion_reason"] and not row["null_reason"]


def test_sales_to_capital_carries_reinvestment_duty_and_is_really_computed():
    p = next(iter(_series("MU").by_metric(METRIC_SALES_TO_CAPITAL)), None)
    assert p is not None and p.value is not None and p.value > 0
    c = p.components
    assert c["invested_capital"] == pytest.approx(c["equity"] + c["debt"] - c["cash"])


# ── Basis stamping (G-4 carried forward) ─────────────────────────────────────

def test_only_the_yield_leg_carries_a_share_basis():
    """FCF, margin, sales-to-capital and growth divide by no market cap, so a split
    cannot touch them and claiming a split basis for them would be false provenance.

    Run on the PRICED series, where a real basis IS established — otherwise the assertion
    passes for the trivial reason that nothing had a basis to claim.
    """
    r = _priced_series("GOOG")
    assert r.basis == "split_restated", "guard: a basis must exist to be wrongly claimed"
    for metric in (METRIC_FCF, METRIC_FCF_MARGIN, METRIC_SALES_TO_CAPITAL,
                   METRIC_FCF_GROWTH):
        for p in r.by_metric(metric):
            assert p.basis == BASIS_NOT_APPLICABLE, metric


def test_an_unknown_split_record_yields_the_truncated_basis_not_a_silent_restatement():
    """`splits is None` means UNKNOWN, never 'never split' — the G-4 contract. With no
    report the series must fall back and SAY it fell back."""
    r = _series("GOOG", split_report=None)
    assert r.basis.startswith("truncated (")


# ── F5 — the split_restated path, which is the one production took ───────────

def test_a_real_split_report_puts_the_series_on_the_RESTATED_basis():
    """GOOG took this path in the live batch run; it cannot stay untested.

    With the recorded 20:1 of 2022-07-18 established, the restatement is no longer blocked
    and the series must say `split_restated` — not the truncated fallback.
    """
    assert _priced_series("GOOG").basis == "split_restated"


def test_the_restated_and_truncated_bases_are_DIFFERENT_measurements():
    """The whole reason the basis is RETURNED rather than hidden — pinned PER POINT.

    The two bases yield the same NUMBER OF points (the truncated path drops nothing here),
    so a count comparison would pass a broken implementation. Exactly two of GOOG's 20
    quarters move, and they move by the 20:1 split factor:

        2022-03-31   restated  3.7493%   truncated  74.9867%
        2021-09-30   restated  3.7061%   truncated  74.1221%

    That ~20x is the artifact G-4 exists to remove. Only two quarters move — not every
    pre-split one — because the share series is MIXED-BASIS: most pre-split period-ends
    were restated by later filings, so their `first_filed` is already post-split and the
    factor is 1. These two were not.
    """
    restated = _priced_series("GOOG")
    truncated = build_fcf_series("GOOG", _edgar("GOOG"), _price_history("GOOG"), None)
    assert restated.basis == "split_restated"
    assert truncated.basis.startswith("truncated (")

    r = {p.period_end: p.value for p in restated.by_metric(METRIC_FCF_YIELD)}
    t = {p.period_end: p.value for p in truncated.by_metric(METRIC_FCF_YIELD)}
    assert set(r) == set(t), "the bases must cover the same period-ends here"

    moved = {pe for pe in r if abs(r[pe] - t[pe]) > 1e-9}
    assert moved == {"2022-03-31", "2021-09-30"}, sorted(moved)
    for pe in moved:
        assert t[pe] / r[pe] == pytest.approx(20.0, rel=0.01), \
            f"{pe}: the truncated basis must be wrong by exactly the split ratio"
    assert r["2022-03-31"] == pytest.approx(3.7493, abs=1e-4)
    assert t["2022-03-31"] == pytest.approx(74.9867, abs=1e-4)


# ── F1 — the yield leg actually produces values ──────────────────────────────

def test_the_yield_leg_really_produces_values():
    """THE LEG H-3 ARMS. Before this test it had never produced a single point anywhere —
    every case passed an empty price history, so `if shares and price` never fired."""
    pts = _priced_series("GOOG").by_metric(METRIC_FCF_YIELD)
    assert pts, "the yield leg must produce points when prices and shares are present"
    assert all(p.value is not None for p in pts)
    assert all(p.unit == "pct" for p in pts)
    # A large-cap FCF yield is a low single-digit percentage. This is a SANITY BAND, not a
    # pinned value: a share basis wrong by the 20:1 split would land ~20x outside it.
    assert all(0.0 < p.value < 15.0 for p in pts), \
        [(p.period_end, p.value) for p in pts]


def test_the_yield_leg_carries_the_split_basis_ON_EVERY_POINT():
    """F1's other half — the G-4 basis assertion must actually FIRE, not vacuously pass
    over an empty list. A yield computed on a truncated share series is a different
    measurement, and the stamp is per point because a single series can only ever be read
    with the basis that produced it."""
    pts = _priced_series("GOOG").by_metric(METRIC_FCF_YIELD)
    assert pts, "guard: this assertion is worthless over an empty series"
    assert all(p.basis == "split_restated" for p in pts)


def test_the_yield_components_reconstruct_the_market_cap():
    """The stored components must let a later reader re-derive the value rather than take
    it on trust — the same reason G-1 stamped `first_filed` on every share fact."""
    p = next(iter(_priced_series("GOOG").by_metric(METRIC_FCF_YIELD)))
    c = p.components
    assert c["market_cap"] == pytest.approx(c["price"] * c["shares"])
    assert p.value == pytest.approx(
        (c["operating_cashflow"] - c["capex"]) / c["market_cap"] * 100.0)


def test_a_negative_yield_is_excluded_on_the_priced_series():
    """Ruling 2 must hold on the leg that consumes it. MU swings negative, and those
    quarters must be STORED on the yield series and flagged — not dropped."""
    pts = _priced_series("MU").by_metric(METRIC_FCF_YIELD)
    excluded = [p for p in pts if p.excluded]
    assert pts and excluded, "MU must produce negative-FCF yield points"
    assert all(p.exclusion_reason == EXCL_NEGATIVE_FCF for p in excluded)
    assert all(p.value is not None and p.value <= 0 for p in excluded)
    assert len(pts) - len(excluded) == len(
        [p for p in pts if not p.excluded])


# ── Storage: append, never overwrite ─────────────────────────────────────────

def test_re_observing_an_identical_value_adds_no_row_and_refreshes_confirmation(tmp_path):
    db = tmp_path / "series.db"
    pts = _series("GOOG").by_metric(METRIC_FCF)
    written, restated = save_fundamental_series(pts, db_path=db)
    assert written == len(pts) and restated == 0

    again_written, again_restated = save_fundamental_series(pts, db_path=db)
    assert again_written == 0 and again_restated == 0
    rows = list_fundamental_series(ticker="GOOG", metric=METRIC_FCF, db_path=db)
    assert len(rows) == len(pts)
    assert all(r["last_confirmed"] >= r["first_observed"] for r in rows)


def test_a_changed_value_is_APPENDED_and_the_old_figure_stays_readable(tmp_path):
    """A restatement must not delete the number it replaced — that evidence is the whole
    point of Phase G's basis work."""
    db = tmp_path / "series.db"
    pts = _series("GOOG").by_metric(METRIC_FCF)[:1]
    save_fundamental_series(pts, db_path=db)
    original = pts[0].value

    pts[0].value = original + 1_000_000_000
    written, restated = save_fundamental_series(pts, db_path=db)
    assert written == 1 and restated == 1

    live = list_fundamental_series(ticker="GOOG", metric=METRIC_FCF, db_path=db)
    assert len(live) == 1
    assert live[0]["value"] == pytest.approx(original + 1_000_000_000)

    full = list_fundamental_series(ticker="GOOG", metric=METRIC_FCF,
                                   include_superseded=True, db_path=db)
    assert len(full) == 2
    assert any(r["value"] == pytest.approx(original) and r["superseded"] == 1
               for r in full), "the superseded figure must remain readable"


def test_a_method_change_at_an_identical_value_still_supersedes(tmp_path):
    """F4 — the comparison covers everything DESCRIBING the measurement, not the value.

    A TTM assembly moving ttm_reconstructed -> ttm_summed at the same number is a
    different measurement that happens to agree. Silence would hide exactly the change a
    later reader needs to explain a divergence.
    """
    db = tmp_path / "method.db"
    pts = _series("GOOG").by_metric(METRIC_FCF)[:1]
    save_fundamental_series(pts, db_path=db)

    pts[0].method = "ttm_summed_probe_variant"
    written, restated = save_fundamental_series(pts, db_path=db)
    assert written == 1, "a method change must append a row"
    assert restated == 0, "but it is NOT a restatement — the value did not move"

    full = list_fundamental_series(ticker="GOOG", metric=METRIC_FCF,
                                   include_superseded=True, db_path=db)
    assert len(full) == 2
    assert {r["method"] for r in full} == {pts[0].method,
                                           _series("GOOG").by_metric(METRIC_FCF)[0].method}


def test_a_components_change_at_an_identical_value_still_supersedes(tmp_path):
    """Two legs moving in opposite directions can cancel. The cancellation is evidence,
    not a no-op."""
    db = tmp_path / "components.db"
    pts = _series("GOOG").by_metric(METRIC_FCF)[:1]
    save_fundamental_series(pts, db_path=db)

    pts[0].components = dict(pts[0].components,
                             operating_cashflow=pts[0].components["operating_cashflow"] + 1,
                             capex=pts[0].components["capex"] + 1)
    written, restated = save_fundamental_series(pts, db_path=db)
    assert written == 1 and restated == 0


def test_the_anchor_read_excludes_and_the_phase_m_read_does_not(tmp_path):
    """The two consumers of one table, pinned at the storage boundary."""
    db = tmp_path / "series.db"
    save_fundamental_series(_series("C").by_metric(METRIC_FCF), db_path=db)

    phase_m = list_fundamental_series(ticker="C", metric=METRIC_FCF, db_path=db)
    anchor = list_fundamental_series(ticker="C", metric=METRIC_FCF,
                                     include_excluded=False, db_path=db)
    assert len(phase_m) == 21
    assert len(anchor) == 7
    assert any(r["value"] < 0 for r in phase_m)
    assert all(r["value"] > 0 for r in anchor)


def test_per_year_is_a_query_over_the_same_table(tmp_path):
    db = tmp_path / "series.db"
    save_fundamental_series(_series("GOOG").by_metric(METRIC_FCF), db_path=db)
    fy = list_fundamental_series(ticker="GOOG", metric=METRIC_FCF,
                                 period_type=PERIOD_FY, db_path=db)
    allrows = list_fundamental_series(ticker="GOOG", metric=METRIC_FCF, db_path=db)
    assert 0 < len(fy) < len(allrows)
    assert all(r["period_type"] == PERIOD_FY for r in fy)


def test_a_null_valued_reinvestment_row_round_trips(tmp_path):
    """NULL is a legal stored value and must not be confused with 'absent' on re-save."""
    db = tmp_path / "series.db"
    pts = _series("GOOG").by_metric(METRIC_REINVESTMENT)
    written, _ = save_fundamental_series(pts, db_path=db)
    assert written == len(pts)
    again, _ = save_fundamental_series(pts, db_path=db)
    assert again == 0, "a NULL value must compare equal to itself, not append forever"
    rows = list_fundamental_series(ticker="GOOG", metric=METRIC_REINVESTMENT, db_path=db)
    assert rows and all(r["value"] is None for r in rows)


# ── The dark surface applies and persists nothing by default ─────────────────

class _TD:
    ticker = "GOOG"
    price_history: list = []


def test_the_dark_surface_writes_nothing_when_no_destination_is_named(tmp_path):
    """H-1 made this surface a writer, so 'no db_path' must mean NO WRITE — not a
    default into production."""
    db = tmp_path / "unused.db"
    logs: list = []
    result = run_dark_fcf_series(_TD(), _edgar("GOOG"), splits=None, log=logs.append)
    assert result is not None and result.points
    assert not db.exists()
    assert any("APPLIED=NOTHING" in line for line in logs)


def test_the_dark_surface_persists_only_to_the_named_destination(tmp_path):
    db = tmp_path / "named.db"
    run_dark_fcf_series(_TD(), _edgar("GOOG"), splits=None, log=lambda _m: None,
                        db_path=db)
    assert list_fundamental_series(ticker="GOOG", db_path=db)


def test_a_failure_in_the_dark_surface_cannot_break_the_evaluation():
    """Contained like every other dark surface."""
    class Boom:
        ticker = "GOOG"

        @property
        def price_history(self):
            raise RuntimeError("boom")

    logs: list = []
    assert run_dark_fcf_series(Boom(), _edgar("GOOG"), log=logs.append) is None
    assert any("FAILED" in line for line in logs)


def test_no_score_reads_the_series_yet():
    """H-1 is DARK. If a scorer starts reading this module, H-3 has happened and this
    test is the thing that should have been flipped deliberately."""
    import core.pillars as pillars
    src = Path(pillars.__file__).read_text()
    assert "fundamental_series" not in src
