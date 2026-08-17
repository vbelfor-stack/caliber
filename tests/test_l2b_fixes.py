"""
L-2b: the negative-multiple sign gate, and the lens map rewritten at SEC granularity.

BOTH DEFECTS WERE FOUND BY THE STEP-2 FULL-UNIVERSE RUN, on held names, in production.
Neither was found by the suite, because until that run the universe was five golden tickers
and none of them is loss-making or pharma or heavy machinery. That is the whole argument for
running the real universe before arming anything on top of it.
"""
from __future__ import annotations

import pytest

from adapters.base import Prov, missing_prov
from core.lens_overrides import LENS_OVERRIDES, lens_override
from core.lens_select import select_lens
from core.pillars import FLAG_NEGATIVE_MULTIPLE, _valuation_standard


class _Fred:
    rate_10y = Prov(value=4.68, source="FRED", as_of="2026-08-14", confidence="high")


def _YF(ev=None, pe=None, fcf=None):
    """A real TickerData with only the standard lens's inputs populated.

    Deliberately the REAL type, not a stub: the lens reaches through _panel_score into the
    D-4 panel builder, and a hand-rolled stub silently diverges from what production passes.
    """
    import dataclasses

    from core.datatypes import TickerData

    def prov(v):
        return (Prov(value=v, source="fmp", as_of="2026-08-17", confidence="medium")
                if v is not None else missing_prov("fmp", None))

    kwargs = {}
    for f in dataclasses.fields(TickerData):
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            kwargs[f.name] = prov(None)
    kwargs.update(ticker="TEST", name="TEST", sector=None, industry=None, sic=None,
                  price_history=[], earnings_history=[], insider_transactions=[],
                  gross_margin_trajectory=[], revenue_growth_trajectory=[],
                  ev_to_ebitda=prov(ev), trailing_pe=prov(pe), fcf_yield=prov(fcf))
    return TickerData(**kwargs)


# ── the sign gate ─────────────────────────────────────────────────────────────

def test_RKLB_exact_panel_does_NOT_score_5():
    """THE PINNED CASE, with RKLB's real production numbers.

    Before the gate this scored 5/5 — the maximum, "cheapest" rung — because the no-panel
    fallback ladder's first rung is `ev_eb < 10` and -372.6 satisfies it. The same evaluation
    carried NEGATIVE-OPERATING-MARGIN, NEGATIVE-ROE and NEGATIVE-FCF.
    """
    r = _valuation_standard(_YF(ev=-372.65, pe=-296.42, fcf=-0.0084), _Fred(), panel=None)
    assert r.score != 5, "a loss-maker is scoring as maximally cheap again"
    assert r.score <= 3, "negative multiples must not reach the cheap rungs (4 or 5)"
    assert FLAG_NEGATIVE_MULTIPLE in r.flags


def test_SPCX_control_positive_multiple_still_scores_rich():
    """The control from the same run: a POSITIVE 445.9x is genuinely expensive and the gate
    must not touch it. If this moves, the fix broke the ladder rather than the defect."""
    r = _valuation_standard(_YF(ev=445.87, pe=-94.95, fcf=-0.0149), _Fred(), panel=None)
    assert r.score == 1


@pytest.mark.parametrize("ev,pe,fcf", [
    (-1.0, 20.0, 0.05),      # negative EV/EBITDA alone
    (12.0, -5.0, 0.05),      # negative P/E alone
    (8.0, 10.0, -0.02),      # negative FCF yield alone — would otherwise be rung 5
])
def test_any_single_negative_multiple_withholds_the_cheap_rungs(ev, pe, fcf):
    """Ruled: negative EV/EBITDA, P/E *or* FCF yield makes rungs 4 and 5 ineligible. Applied
    as a CAP after every input, so no ordering of the three can route around it."""
    r = _valuation_standard(_YF(ev=ev, pe=pe, fcf=fcf), _Fred(), panel=None)
    assert r.score <= 3
    assert FLAG_NEGATIVE_MULTIPLE in r.flags


def test_a_genuinely_cheap_positive_name_still_reaches_rung_5():
    """The gate must not make the cheap end unreachable for names that earn."""
    r = _valuation_standard(_YF(ev=8.0, pe=11.0, fcf=0.09), _Fred(), panel=None)
    assert r.score == 5
    assert FLAG_NEGATIVE_MULTIPLE not in r.flags


def test_the_withholding_is_stated_in_the_rationale():
    """A capped score that does not say it was capped is a silent adjustment."""
    r = _valuation_standard(_YF(ev=8.0, pe=11.0, fcf=-0.02), _Fred(), panel=None)
    assert "Cheap rungs withheld" in r.rationale
    assert "FCF yield" in r.rationale


# ── the lens map ──────────────────────────────────────────────────────────────

def test_pharma_is_carved_out_of_the_chemicals_range():
    """SEC major group 28 is 'Chemicals and Allied Products' and CONTAINS pharma. Commodity
    chemicals are cyclical; drugs are not, and a major-group range cannot tell 2834 from
    2860. Found live: LLY read cyclical and would carry a peak/rollover gate."""
    assert select_lens(None, "Drug Manufacturers - General", "2834") == "compounder"
    for sic in ("2833", "2834", "2835", "2836"):
        assert select_lens(None, "Biotech", sic) == "compounder", f"SIC {sic} not carved out"


def test_industrial_chemicals_are_still_cyclical():
    """The carve-out must not empty the range it sits inside."""
    assert select_lens(None, "Specialty Chemicals", "2860") == "cyclical"
    assert select_lens(None, "Specialty Chemicals", "2821") == "cyclical"


def test_heavy_machinery_is_cyclical_and_CAT_is_the_case():
    """3500-3599 previously fell through EVERY range, so the archetypal industrial cyclical
    got the generic lens with no peak gate."""
    assert select_lens(None, "Agricultural - Machinery", "3531") == "cyclical"
    for sic in ("3510", "3523", "3532", "3541", "3559", "3569"):
        assert select_lens(None, "Machinery", sic) == "cyclical", f"SIC {sic} missed"


def test_computers_and_office_equipment_are_NOT_swept_into_heavy_machinery():
    """The range stops at 3570 deliberately — 357x is computers, not heavy machinery."""
    for sic in ("3571", "3572", "3576", "3577"):
        assert select_lens(None, "Computer Systems", sic) != "cyclical", (
            f"SIC {sic} was swept into the heavy-machinery range")


# ── the override mechanism ────────────────────────────────────────────────────

@pytest.mark.parametrize("ticker", ["IONQ", "INFQ", "BE"])
def test_the_ruled_overrides_take_effect(ticker):
    lens, rationale = LENS_OVERRIDES[ticker]
    assert lens == "growth"
    assert select_lens(None, "Computer Hardware", "3620", ticker=ticker) == "growth"
    assert rationale.strip()


def test_every_override_carries_a_rationale():
    """Enforced at import, asserted here too: an unexplained reclassification is the thing
    the record exists to prevent."""
    for t, (lens, rationale) in LENS_OVERRIDES.items():
        assert lens in {"growth", "cyclical", "bank", "compounder", "standard"}
        assert rationale and rationale.strip(), f"{t} has no rationale"
        assert len(rationale) > 40, f"{t}'s rationale is too thin to audit"


def test_an_override_beats_both_sic_and_industry():
    """A human who looked at the business outranks a vendor string and a filing code."""
    assert select_lens(None, "Semiconductors", "3674", ticker="IONQ") == "growth"


def test_names_without_an_override_are_untouched():
    assert lens_override("MU") is None
    assert lens_override(None) is None
    assert select_lens(None, "Semiconductors", "3674", ticker="MU") == "cyclical"


def test_FN_and_SPCX_are_deliberately_NOT_overridden():
    """Recorded decisions, not omissions. FN is defensibly cyclical (optics on the
    hyperscaler capex cycle). SPCX reads standard from SEC's OWN SIC 7370 and is not
    overridden on judgement alone."""
    assert lens_override("FN") is None
    assert select_lens(None, "Hardware, Equipment & Parts", "3661", ticker="FN") == "cyclical"
    assert lens_override("SPCX") is None
    assert select_lens(None, "Aerospace & Defense", "7370", ticker="SPCX") == "standard"


def test_omitting_the_ticker_preserves_the_previous_behaviour():
    """Callers that do not pass a ticker get exactly what they got before the hook existed."""
    assert select_lens(None, "Semiconductors", "3674") == "cyclical"
    assert select_lens(None, "Computer Hardware", "7373") == "cyclical"   # sweep still applies


def test_the_golden_five_lenses_are_unmoved():
    """The whole point of a golden set: this rewrite must not silently move them."""
    assert select_lens("Technology", "Semiconductors", "3674", ticker="MU") == "cyclical"
    assert select_lens(None, "Internet Content & Information", "7370",
                       ticker="GOOGL") == "compounder"
    assert select_lens(None, "Financial - Credit Services", "7389", ticker="V") == "compounder"
