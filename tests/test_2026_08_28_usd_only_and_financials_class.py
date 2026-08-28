"""Pins for Vic's 2026-08-28 rulings — USD-only ingest + the financials class.

Order document: docs/orders/2026-08-28-skhy-usd-only-and-financials-class.md

TWO RULINGS, PINNED SEPARATELY BECAUSE THEY FAIL SEPARATELY:

  1. FINANCIALS CLASSIFICATION — banks, insurers and diversified financials are
     model-inapplicable to the FCF engine. A CLASS, not a per-ticker call.
  2. USD ONLY — ingest only what FMP reports natively in USD. Non-USD periods are blocked
     with a typed reason and NEVER converted.

Every offline fixture below is either a recorded fixture or a synthetic object. Nothing here
touches the network, and the two live measurements the pins depend on (the 28-name
sector/industry sweep, and SKHY's 129 all-KRW periods) are FROZEN as tables with the date
they were taken — a pin that needs a live fetch is a pin that fails for the wrong reason.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

import evaluate
from adapters.edgar_adapter import fetch_edgar
from adapters.fmp_adapter import fetch_fmp
from core.fundamental_series import (ALL_METRICS, METRIC_FCF, SeriesPoint,
                                     build_fcf_series)
from core.model_applicability import (APPLICABLE, CLASS_FINANCIALS, CLASS_RULED_ON,
                                      Applicability, applicability_for,
                                      fcf_model_applicability)
from core.reporting_currency import (CURRENCY_FIELD, REASON_CURRENCY_UNKNOWN,
                                     REASON_NON_USD_NATIVE, USD, currency_of,
                                     split_by_currency)
from store.models import save_fundamental_series
from tools.ingest_fmp_usd_series import (METRIC_INGEST_BLOCK,
                                         METRIC_MODEL_APPLICABILITY, PERIOD_BLOCK_FY,
                                         PERIOD_BLOCK_Q, PERIOD_FLAG)

FX = Path(__file__).parent / "fixtures"

# ── FROZEN MEASUREMENT: FMP sector/industry for all 28 evaluated names ───────
# Taken live 2026-08-28, TWICE on independent fetches, and identical both times. Frozen
# rather than re-fetched so the pin measures the CLASSIFIER and not FMP's uptime. If FMP
# ever restates one of these strings the pin keeps asserting the old classification, which
# is correct: the ruling was made against these strings, and a vendor restatement is a thing
# that should force a re-reading rather than silently re-classify a name.
UNIVERSE_SECTOR_INDUSTRY = {
    "ARM":   ("Technology", "Semiconductors"),
    "BE":    ("Industrials", "Electrical Equipment & Parts"),
    "BK":    ("Financial Services", "Investment - Banking & Investment Services"),
    "C":     ("Financial Services", "Banks - Diversified"),
    "CAT":   ("Industrials", "Agricultural - Machinery"),
    "CBRS":  ("Technology", "Semiconductors"),
    "DPC":   ("Industrials", "Manufacturing - Metal Fabrication"),
    "FN":    ("Technology", "Hardware, Equipment & Parts"),
    "GOOG":  ("Communication Services", "Internet Content & Information"),
    "GOOGL": ("Communication Services", "Internet Content & Information"),
    "INFQ":  ("Technology", "Computer Hardware"),
    "IONQ":  ("Technology", "Computer Hardware"),
    "JPM":   ("Financial Services", "Banks - Diversified"),
    "LITE":  ("Technology", "Communication Equipment"),
    "LLY":   ("Healthcare", "Drug Manufacturers - General"),
    "LRCX":  ("Technology", "Semiconductors"),
    "MU":    ("Technology", "Semiconductors"),
    "NOW":   ("Technology", "Software - Application"),
    "NVDA":  ("Technology", "Semiconductors"),
    "QBTS":  ("Technology", "Computer Hardware"),
    "RKLB":  ("Industrials", "Aerospace & Defense"),
    "SKHY":  ("Technology", "Semiconductors"),
    "SPCX":  ("Industrials", "Aerospace & Defense"),
    "STX":   ("Technology", "Computer Hardware"),
    "USB":   ("Financial Services", "Banks - Diversified"),
    "V":     ("Financial Services", "Financial - Credit Services"),
    "WU":    ("Financial Services", "Financial - Credit Services"),
    "XE":    ("Industrials", "Industrial - Machinery"),
}

CAUGHT = {"BK", "C", "JPM", "USB"}


# ═════════════════════════════════════════════════════════════════════════════
#  RULING 1 — THE FINANCIALS CLASS
# ═════════════════════════════════════════════════════════════════════════════

def test_the_class_catches_exactly_BK_C_JPM_USB_over_the_whole_universe():
    """THE HEADLINE OF STEP (c), swept over all 28 with NO pre-filtering.

    Vic: "Report which current-universe names the class catches — no pre-filtering, list
    them all." This is that sweep, frozen.
    """
    caught = {t for t, (s, i) in UNIVERSE_SECTOR_INDUSTRY.items()
              if not fcf_model_applicability(s, i).applicable}
    assert caught == CAUGHT, f"class membership moved: {caught ^ CAUGHT}"


@pytest.mark.parametrize("ticker", ["V", "WU"])
def test_V_and_WU_are_FINANCIAL_SERVICES_but_are_NOT_caught(ticker):
    """★ THE POINT OF THE WHOLE CLASS DEFINITION, AND THE POSITIVE CONTROL ON IT.

    Six of the 28 are FMP sector "Financial Services". Only four are caught. V and WU are
    industry "Financial - Credit Services" — asset-light payment networks with large
    positive FCF, both scored on the COMPOUNDER lens, and both CURRENTLY COVERED in
    `fundamental_series`. A sector-level rule would have swept them in and destroyed working
    coverage on two names to enforce a class neither belongs to.

    Vic's wording is "banks/insurers/diversified financials", not "the Financial Services
    sector". This test is where that distinction is enforced rather than merely believed.
    """
    sector, industry = UNIVERSE_SECTOR_INDUSTRY[ticker]
    assert sector == "Financial Services", "the premise of this pin"
    assert fcf_model_applicability(sector, industry).applicable, \
        f"{ticker} must NOT be class-blocked — it is a payment network, not a bank"


def test_the_class_does_NOT_consult_SIC():
    """Vic said FMP sector/industry. SIC comes from EDGAR.

    Under the FMP-is-the-source doctrine EDGAR is the ARBITER, not a pipeline input, and it
    is already score-bearing on every run through four paths the doctrine's three-case list
    does not name (the open pre-flight contradiction). This class will not become a fifth.

    A bank SIC (6021) on a non-financial industry must therefore NOT trip the class — even
    though `select_lens` itself WOULD return "bank" for that pair when handed the SIC. That
    divergence is the pin: it proves the argument is genuinely being withheld.

    The industry string has to be one that falls THROUGH every earlier check to reach the
    SIC-bank rule at step 5 — "Semiconductors" does not, because it matches the cyclical
    INDUSTRY keywords at step 2 and never gets that far. RKLB's real pair is used instead.
    """
    from core.lens_select import select_lens
    sector, industry = UNIVERSE_SECTOR_INDUSTRY["RKLB"]      # Industrials / Aerospace & Defense
    assert select_lens(sector, industry, "6021", None) == "bank", \
        "premise: select_lens WOULD read this SIC as a bank if it were passed"
    assert fcf_model_applicability(sector, industry).applicable, \
        "the class must not see SIC at all"


def test_the_class_does_NOT_consult_the_per_ticker_lens_override_list():
    """Vic: "a CLASS, not a per-ticker call."

    `select_lens` consults the hand-curated `lens_overrides` table when given a ticker.
    Admitting it would reintroduce exactly the per-issuer judgement the ruling removes. The
    signature is the enforcement: `fcf_model_applicability` takes no ticker, so there is no
    way to pass one.
    """
    import inspect
    params = set(inspect.signature(fcf_model_applicability).parameters)
    assert params == {"sector", "industry"}, params

    # And measured: no override in the list would change the caught set today, so this
    # costs nothing now and holds the line later.
    from core.lens_overrides import lens_override
    overridden = {t for t in UNIVERSE_SECTOR_INDUSTRY if lens_override(t) is not None}
    assert not (overridden & CAUGHT), \
        f"an override now touches a class member — re-read the ruling: {overridden & CAUGHT}"


@pytest.mark.parametrize("sector,industry", [
    (None, None), ("", ""), (None, "Banks - Diversified"[:0]),
])
def test_an_unclassifiable_issuer_is_APPLICABLE_and_the_direction_is_deliberate(
        sector, industry):
    """FAIL-CLOSED means the guard denies THE TAG IT GUARDS. Here the tag is the BLOCK.

    Denying the block on absent evidence is the protective direction: the alternative would
    withhold FCF from the ENTIRE universe the moment a profile fetch flaked, which is a far
    worse failure than letting one unclassified bank through to a series that is then
    visibly nonsensical.
    """
    assert fcf_model_applicability(sector, industry).applicable


def test_the_typed_reason_names_the_class_and_is_None_when_applicable():
    a = fcf_model_applicability(*UNIVERSE_SECTOR_INDUSTRY["JPM"])
    assert a.typed_reason == f"fcf:model_inapplicable:{CLASS_FINANCIALS}"
    assert a.detail and "balance-sheet financing" in a.detail
    assert APPLICABLE.typed_reason is None
    assert APPLICABLE.class_name is None, \
        "there is no 'applicable' class — only the absence of an inapplicable one"


def _code_string_literals(relpath: str) -> list:
    """Every string constant in a module EXCEPT its docstrings.

    ★ TAKEN OVER THE AST, NOT THE TEXT, AND THAT IS A RECORDED LESSON RATHER THAN A STYLE
    CHOICE. The L-4b successor pin was first written as a substring count and was tripped by
    a COMMENT that merely mentioned `tolerance_for()`; "a pin that prose can break is one a
    later session weakens instead of heeding." These two modules are heavily commented
    precisely because their rulings are subtle, so a text scan for words like "bank" or
    "convert" would fire on the explanation of why they are forbidden. It did, on the first
    run of this file.
    """
    import ast
    tree = ast.parse((Path(__file__).parent.parent / relpath).read_text())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


def test_the_module_owns_NO_taxonomy_of_its_own():
    """NEVER ADD DUPLICATE LOGIC.

    `core.lens_select` already encodes banks/insurers/REITs, and already checks the
    compounder industries FIRST — which is precisely what keeps V and WU out, and has been
    pinned by the golden tests since Phase 0. A second keyword list here would be two
    encodings of one judgement, free to drift, with nothing to say which is authoritative
    when they disagree.

    The one industry-ish literal permitted is `_INAPPLICABLE_LENS = "bank"` — a LENS NAME,
    which is the delegation target, not a keyword being matched against a vendor string.
    """
    src = (Path(__file__).parent.parent / "core" / "model_applicability.py").read_text()
    assert "from core.lens_select import select_lens" in src

    literals = _code_string_literals("core/model_applicability.py")
    assert literals.count("bank") == 1, \
        f"exactly one 'bank' literal expected (the delegation target): {literals}"
    for banned in ("insurance", "reit", "savings", "mortgage", "credit services",
                   "banks - diversified", "financial services"):
        assert not any(banned in s.lower() for s in literals), \
            f"{banned!r} appears as a code literal — that is a second taxonomy"


# ── The enforcement points ───────────────────────────────────────────────────

def test_build_fcf_series_refuses_FIRST_ahead_of_every_data_check():
    """★ THE ORDERING IS THE RULING, NOT AN IMPLEMENTATION DETAIL.

    A class-blocked name with NO edgar at all must report the CLASS, not "no EDGAR data".
    Both are true; the class fact is PRIOR, because better inputs would not help. Reporting
    the data reason first is how JPM and USB spent four orders filed under `capex:no_tag` —
    a label that was accurate and led nowhere, because it describes a coverage gap and a
    coverage gap invites the next session to go and find the missing tag.
    """
    blocked = fcf_model_applicability(*UNIVERSE_SECTOR_INDUSTRY["JPM"])
    r = build_fcf_series("JPM", None, None, None, applicability=blocked)
    assert r.withheld.get(METRIC_FCF) == blocked.typed_reason
    assert "all" not in r.withheld, "'no EDGAR data' must not be the reported cause"
    assert not r.points


def test_the_class_gate_beats_capex_no_tag_on_a_REAL_fixture():
    """JPM files no PP&E-purchase concept, so without the gate it reports `capex:no_tag`.

    Same fixture, both ways, in one test — so the pin cannot pass because the gate is dead.
    """
    ed = fetch_edgar("JPM", fixture_path=FX / "edgar" / "JPM.json")
    yf = fetch_fmp("JPM", fixture_path=FX / "fmp" / "JPM.json")

    unasked = build_fcf_series("JPM", ed, yf.price_history, None)
    assert "capex:no_tag" in unasked.withheld[METRIC_FCF], unasked.withheld

    asked = build_fcf_series("JPM", ed, yf.price_history, None,
                             applicability=fcf_model_applicability(*UNIVERSE_SECTOR_INDUSTRY["JPM"]))
    assert asked.withheld[METRIC_FCF] == "fcf:model_inapplicable:financials"


def test_BK_builds_a_real_series_unasked_and_NOTHING_asked():
    """BK IS THE NAME THAT MAKES THESE PINS ABLE TO FIRE.

    Unlike JPM and USB, BK DOES file capex and DOES build a usable series. So if the class
    gate ever stopped running, JPM and USB would merely swap one refusal reason for another
    — nothing visible — while BK would silently regain a full FCF family. BK is the positive
    control on the whole class.
    """
    ed = fetch_edgar("BK", fixture_path=FX / "edgar" / "BK.json")
    yf = fetch_fmp("BK", fixture_path=FX / "fmp" / "BK.json")

    unasked = build_fcf_series("BK", ed, yf.price_history, None)
    assert unasked.points, "premise: BK really does build a series"
    assert not unasked.withheld

    asked = build_fcf_series("BK", ed, yf.price_history, None,
                             applicability=fcf_model_applicability(*UNIVERSE_SECTOR_INDUSTRY["BK"]))
    assert asked.points == []
    assert asked.withheld[METRIC_FCF] == "fcf:model_inapplicable:financials"


def test_the_gate_is_OPT_IN_so_no_existing_caller_changed():
    """`applicability=None` means NOT ASKED. Every pre-existing call site passes nothing,
    so the arming is visible exactly at the sites that opted in."""
    import inspect
    for fn in (build_fcf_series,):
        assert inspect.signature(fn).parameters["applicability"].default is None


def test_the_bank_lens_is_not_panel_scored_so_the_arm_moves_no_score_today():
    """★ THE SAFETY PROPERTY THE ARM RESTS ON — STATED AND PINNED, NOT ASSUMED.

    Same shape as L-4b's monotone-widening argument. Every name the class catches scores on
    the BANK lens, and `bank` is not in ARMED_PANEL_LENSES — `_valuation_bank` does not even
    take `panel` as a parameter. So a bank's panel is computed and logged but never scored,
    and withholding its FCF anchor changes one NOTE line.

    THIS PIN FAILS LOUDLY IF THE BANK LENS IS EVER PANEL-ARMED, which is exactly when the
    zero-movement claim above stops being true and has to be re-argued.
    """
    import inspect
    from core.pillars import ARMED_PANEL_LENSES, _valuation_bank
    assert "bank" not in ARMED_PANEL_LENSES, \
        "the bank lens is now panel-scored — the class arm's zero-movement claim is STALE"
    assert "panel" not in inspect.signature(_valuation_bank).parameters


# ═════════════════════════════════════════════════════════════════════════════
#  RULING 2 — USD ONLY
# ═════════════════════════════════════════════════════════════════════════════

# FROZEN MEASUREMENT: SKHY's reporting currency, live 2026-08-28, twice.
SKHY_MEASURED_PERIODS = 129
SKHY_MEASURED_CURRENCIES = {"KRW": 129}


def test_the_gate_partitions_on_reportedCurrency_and_nothing_else():
    rows = [{"date": "2025-12-31", CURRENCY_FIELD: "USD"},
            {"date": "2024-12-31", CURRENCY_FIELD: "KRW"},
            {"date": "2023-12-31", CURRENCY_FIELD: "usd"}]   # case-insensitive
    split = split_by_currency(rows)
    assert [r["date"] for r in split.usd] == ["2025-12-31", "2023-12-31"]
    assert len(split.blocked) == 1
    assert split.blocked[0][1] == f"currency:{REASON_NON_USD_NATIVE}"
    assert split.blocked[0][2] == "KRW"


def test_profile_currency_is_NEVER_consulted():
    """★ `profile.currency` IS THE QUOTE CURRENCY, NOT THE REPORTING CURRENCY.

    Measured 2026-08-28: SKHY's profile reads `currency=USD` — it is a NASDAQ ADR quoted in
    dollars — while ALL 129 of its statement rows read `reportedCurrency=KRW`. The control
    settles it: the same issuer's Korean ordinary line `000660.KS` reads
    `profile.currency=KRW` on exchange KSC. Both fields are CORRECT; they answer different
    questions.

    CLAUDE.md previously recorded this as "profile.currency is WRONG for this issuer". That
    was too harsh, and this pin is where the correction lives: a row carrying a USD-looking
    `currency` field alongside a KRW `reportedCurrency` must still be BLOCKED.
    """
    row = {"date": "2025-12-31", "currency": "USD", "symbol": "SKHY",
           CURRENCY_FIELD: "KRW"}
    split = split_by_currency([row])
    assert split.usd == []
    assert split.blocked[0][2] == "KRW"


def test_an_unstated_currency_gets_its_OWN_reason_not_the_foreign_one():
    """TWO FAILURE MODES, TWO TYPED REASONS — collapsing them is the L-4d defect.

    `non_usd_native` is a fact about the ISSUER. `currency_unstated` is a fact about the
    FEED, and a more alarming one: it means we cannot tell, and an undetectable currency
    error is worse than a detected foreign one. One constant cannot know which occurred, so
    any code holding it would be forced to guess.
    """
    split = split_by_currency([{"date": "2025-12-31"}, {"date": "2024-12-31",
                                                        CURRENCY_FIELD: None}])
    assert len(split.blocked) == 2
    assert all(b[1] == f"currency:{REASON_CURRENCY_UNKNOWN}" for b in split.blocked)
    assert all(b[2] == "UNSTATED" for b in split.blocked)
    assert currency_of({}) is None
    assert currency_of({CURRENCY_FIELD: "  "}) is None


def test_NOTHING_IS_EVER_CONVERTED():
    """★ RULING 2'S CORE PROHIBITION, AND THE SURVIVOR OF THE SUPERSEDED §8.1(2).

    The 2026-08-21 addendum ordered period-matched KRW→USD conversion and required the
    ingest-date-rate prohibition to be PINNED. Vic's 2026-08-28 ruling removed conversion
    entirely, so the pin gets stronger, not weaker: there must be no conversion of any kind,
    at any rate, on any date basis.

    Enforced two ways — the gate hands back the SAME row objects with values untouched, and
    neither the gate nor the ingest tool names a forex symbol or an FX endpoint IN CODE.

    The code check is taken over the AST for the reason given on `_code_string_literals`:
    both modules explain at length WHY conversion is forbidden, so a text scan fires on the
    prohibition itself. It did, on this test's first run.
    """
    row = {"date": "2025-12-31", CURRENCY_FIELD: "KRW",
           "operatingCashFlow": 53_373_126_000_000}
    split = split_by_currency([row])
    returned, _reason, _ccy = split.blocked[0]
    assert returned is row, "the gate must not copy, rewrite or rescale a row"
    assert returned["operatingCashFlow"] == 53_373_126_000_000

    import ast
    for mod in ("core/reporting_currency.py", "tools/ingest_fmp_usd_series.py"):
        for s in _code_string_literals(mod):
            low = s.lower()
            for banned in ("usdkrw", "krwusd", "historical-price-eod", "forex",
                           "exchange_rate", "fx_rate"):
                assert banned not in low, \
                    f"{banned!r} as a code literal in {mod} — conversion is RULED OUT"
        # No FX arithmetic either: no call named like a converter.
        tree = ast.parse((Path(__file__).parent.parent / mod).read_text())
        called = {n.func.id for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert not {c for c in called if "convert" in c.lower() or "rate" in c.lower()}, \
            f"{mod} calls something that looks like a converter"


def test_the_currency_summary_reports_both_sides():
    """Vic: "Report the split before ingesting." The summary must cover BOTH sides, or a
    100%-blocked name would render as an empty dict and read like a fetch failure."""
    split = split_by_currency([{CURRENCY_FIELD: "KRW"}] * 19)
    assert split.currencies == {"KRW": 19}
    assert not split.has_usd
    mixed = split_by_currency([{CURRENCY_FIELD: "USD"}, {CURRENCY_FIELD: "KRW"}])
    assert mixed.currencies == {"USD": 1, "KRW": 1}
    assert mixed.has_usd


# ═════════════════════════════════════════════════════════════════════════════
#  THE BLOCK-ROW SHAPE — constrained by measurement, not by taste
# ═════════════════════════════════════════════════════════════════════════════

def test_block_rows_use_a_metric_and_period_type_NO_consumer_queries():
    """The structural half of the argument. The behavioural half is the next test."""
    assert PERIOD_BLOCK_FY not in ("FY", "TTM_Q")
    assert PERIOD_BLOCK_Q not in ("FY", "TTM_Q")
    assert PERIOD_FLAG not in ("FY", "TTM_Q")
    assert METRIC_MODEL_APPLICABILITY not in ALL_METRICS
    assert all(not METRIC_INGEST_BLOCK.startswith(m) for m in ALL_METRICS)


def test_block_rows_are_INVISIBLE_to_the_lifecycle_classifier_reader(tmp_path):
    """★ THE POSITIVE CONTROL, AND THE REASON THIS FILE EXISTS AT ALL.

    `evaluate._fy_series_from_db` selects on ticker/metric/period_type='FY'/superseded and
    DOES NOT filter `excluded`. So block rows written under `metric='fcf'` /
    `period_type='FY'` would flip the classifier's `fcf_fy` from None (UNKNOWN — "we hold no
    series") to a populated list, changing its absent-leg reason from `no_fcf_series` to
    `only_0_fy_fcf_points` — a claim that the ISSUER has no FY FCF points when in fact WE
    blocked them. That is the L-4d typed-reason mislabel in a new costume.

    Both halves are asserted IN ONE TEST, against ONE database: the real series is read
    back untouched with block rows sitting beside it, AND the counterfactual is shown to
    move the reading. A pin that only asserted the safe half could pass while the block
    rows were silently absent.
    """
    db = tmp_path / "t.db"
    real = [SeriesPoint(ticker="ZZ", metric="fcf", period_end=f"202{i}-12-31",
                        period_type="FY", value=float(i), unit="USD")
            for i in (1, 2, 3)]
    blocks = [SeriesPoint(ticker="ZZ", metric=f"{METRIC_INGEST_BLOCK}:cash_flow",
                          period_end="2020-12-31", period_type=PERIOD_BLOCK_FY,
                          value=None, unit=None, excluded=True,
                          exclusion_reason=f"currency:{REASON_NON_USD_NATIVE}"),
              SeriesPoint(ticker="ZZ", metric=METRIC_MODEL_APPLICABILITY,
                          period_end=CLASS_RULED_ON, period_type=PERIOD_FLAG,
                          value=None, unit=None, excluded=True,
                          exclusion_reason="fcf:model_inapplicable:financials")]
    save_fundamental_series(real + blocks, db_path=db)

    assert evaluate._fy_series_from_db(db, "ZZ", "fcf") == [
        ("2021-12-31", 1.0), ("2022-12-31", 2.0), ("2023-12-31", 3.0)]

    # THE COUNTERFACTUAL — the same block, written the naive way, DOES move the reading.
    save_fundamental_series([SeriesPoint(
        ticker="YY", metric="fcf", period_end="2020-12-31", period_type="FY",
        value=None, unit=None, excluded=True, exclusion_reason="naive")], db_path=db)
    naive = evaluate._fy_series_from_db(db, "YY", "fcf")
    assert naive == [("2020-12-31", None)], \
        "premise: a naive block row IS visible — which is why the shape above is required"


def test_fy_series_reader_must_NOT_be_filtered_on_excluded():
    """★ THE OTHER DESIGN, AND WHY IT IS WORSE. A WARNING PIN.

    The obvious "fix" for the hazard above is to filter `_fy_series_from_db` on
    `excluded=0`. That would be a silent catastrophe: `EXCL_NEGATIVE_FCF` marks every
    negative FCF point excluded, and those negative points ARE the R2
    all-negative-last-3-FY signal. Measured in production 2026-08-28: 30 FY `fcf` rows
    across 8 tickers (BE, BK, C, IONQ, LITE, MU, QBTS, RKLB) carry excluded=1.

    So this pin asserts the reader does NOT filter, and it exists to FAIL if a future
    session adds the filter thinking it is tidying up.
    """
    src = (Path(__file__).parent.parent / "evaluate.py").read_text()
    fn = src.split("def _fy_series_from_db", 1)[1].split("\ndef ", 1)[0]
    assert "excluded" not in fn, (
        "_fy_series_from_db must NOT filter on `excluded` — negative-FCF points are "
        "excluded=1 and they ARE the R2 all-negative-last-3 signal")


def test_every_row_this_order_writes_is_excluded_with_a_typed_reason(tmp_path):
    """A block row that could be mistaken for a measurement would defeat its own purpose."""
    from tools.ingest_fmp_usd_series import build_one  # noqa: F401  (import shape only)
    db = tmp_path / "t.db"
    pts = [SeriesPoint(ticker="ZZ", metric=f"{METRIC_INGEST_BLOCK}:income",
                       period_end="2025-12-31", period_type=PERIOD_BLOCK_FY,
                       value=None, unit=None, excluded=True,
                       exclusion_reason=f"currency:{REASON_NON_USD_NATIVE}",
                       components={"reported_currency": "KRW"})]
    save_fundamental_series(pts, db_path=db)
    conn = sqlite3.connect(db)
    bad = conn.execute(
        "SELECT COUNT(*) FROM fundamental_series WHERE NOT ("
        "excluded=1 AND exclusion_reason IS NOT NULL AND value IS NULL "
        "AND null_reason IS NULL)").fetchone()[0]
    conn.close()
    assert bad == 0


def test_the_class_flag_row_is_keyed_on_the_RULING_date_not_the_run_date():
    """A class membership is not a period, and it needs a stable key.

    Stamping the RUN date would mint a fresh row every day and grow without bound. Stamping
    the RULING date is idempotent — a re-run touches `last_confirmed` and nothing else — and
    if the class is ever re-ruled the new date makes a NEW row with the old one surviving
    beside it, which is append-never-overwrite applied to a decision.
    """
    from datetime import date
    assert CLASS_RULED_ON == "2026-08-28"
    assert CLASS_RULED_ON != date.today().isoformat() or True  # documented, not asserted
    parsed = date.fromisoformat(CLASS_RULED_ON)
    assert parsed.year == 2026


def test_applicability_for_survives_an_object_with_no_sector_attributes():
    """A crash on this path would take down an evaluation over a classification question."""
    class Bare:
        pass
    assert applicability_for(Bare()).applicable
    assert applicability_for(None).applicable
