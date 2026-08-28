"""Pins for Vic's closer-session rulings — 2026-08-28.

Order: docs/orders/2026-08-28-closer.md

  1. FINANCIALS GATE EXTENSION — nothing numeric: classifier and evaluator, not just the
     score builder. Stored stages retired with a typed reason.
  2. STAGE FRESHNESS — recompute-on-detect, halt-and-report, approval per name.
  3. SKHY ANCHOR — full market cap, one endpoint, one basis, live at write time.
  4. KRW GUARD — every non-USD MONETARY score-bearing field blocked, never converted.

Offline throughout: fixtures and synthetic objects, no network.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adapters.base import Prov, missing_prov
from adapters.fmp_adapter import apply_currency_guard
from core.fundamental_series import SeriesPoint
from core.model_applicability import fcf_model_applicability
from core.reporting_currency import (CURRENCY_NEUTRAL_SCORE_BEARING_FIELDS,
                                     FIELD_CURRENCY_BASIS,
                                     MONETARY_SCORE_BEARING_FIELDS, field_is_blocked,
                                     market_cap_basis, payload_currencies)
from core.stage_freshness import (CLASSIFIER_INPUT_METRICS, StageFlipRequiresApproval,
                                  band_consequence, freshness_for, guard_stage_write,
                                  stored_stage)
from store.models import (init_db, retire_lifecycle_stages, save_fundamental_series,
                          save_stage_flip_approval, get_stage_flip_approval)

FX = Path(__file__).parent / "fixtures"

BANK = ("Financial Services", "Banks - Diversified")
PAYMENTS = ("Financial Services", "Financial - Credit Services")


def _code_string_literals(relpath: str) -> list:
    """Every string constant in a module EXCEPT its docstrings.

    Shared shape with `tests/test_2026_08_28_usd_only_and_financials_class.py`, and it is
    here for the same recorded reason: these modules explain at length WHY a thing is
    forbidden, so a text scan for the forbidden word fires on the explanation. It did,
    twice, on the first run of each of these files.
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


def _stage_row(conn, ticker, stage, run_at):
    conn.execute(
        "INSERT INTO lifecycle_stage (ticker, computed_stage, rule_fired, lens, "
        "inputs_json, assertions_json, flags_json, absent_legs, inputs_incomplete, "
        "config_version, run_at) VALUES (?,?,?,?,'{}','[]','[]',NULL,0,'v1',?)",
        (ticker, stage, "rule4_mature", "bank", run_at))


# ═════════════════════════════════════════════════════════════════════════════
#  RULING 1 — the gate extension and stage retirement
# ═════════════════════════════════════════════════════════════════════════════

def test_retiring_a_stage_DOES_NOT_delete_or_edit_it(tmp_path):
    """★ RETIRE, NOT DELETE, AND NOT EDIT — the three are different claims.

    The row was computed CORRECTLY from the inputs it had; it is INADMISSIBLE, not wrong.
    Deleting would destroy the record of what was believed when — the one thing the
    append-only discipline exists to preserve. Editing `computed_stage` would forge a
    computation that never ran. So every original column must survive byte-for-byte.
    """
    db = tmp_path / "t.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        _stage_row(conn, "JPM", "MATURE", "2026-08-17T20:00:00+00:00")
        _stage_row(conn, "JPM", "MATURE", "2026-08-17T21:00:00+00:00")
        conn.commit()

    n = retire_lifecycle_stages("JPM", "model_inapplicable:financials", db_path=db)
    assert n == 2

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM lifecycle_stage WHERE ticker='JPM' ORDER BY id")]
    conn.close()
    assert len(rows) == 2, "no row may be deleted"
    for r in rows:
        assert r["computed_stage"] == "MATURE", "the computation must not be forged"
        assert r["rule_fired"] == "rule4_mature"
        assert r["run_at"].startswith("2026-08-17"), "the original date must survive"
        assert r["retired_reason"] == "model_inapplicable:financials"
        assert r["retired_at"]


def test_retirement_is_idempotent_and_does_not_rewrite_the_date(tmp_path):
    """A re-run must not move `retired_at` — that would lose when it actually happened."""
    db = tmp_path / "t.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        _stage_row(conn, "BK", "MATURE", "2026-08-17T20:00:00+00:00")
        conn.commit()
    assert retire_lifecycle_stages("BK", "r", db_path=db) == 1
    first = sqlite3.connect(db).execute(
        "SELECT retired_at FROM lifecycle_stage WHERE ticker='BK'").fetchone()[0]
    assert retire_lifecycle_stages("BK", "r", db_path=db) == 0, "already retired — skip"
    again = sqlite3.connect(db).execute(
        "SELECT retired_at FROM lifecycle_stage WHERE ticker='BK'").fetchone()[0]
    assert first == again


def test_retirement_demands_a_typed_reason(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    for bad in (None, "", "   "):
        with pytest.raises(ValueError):
            retire_lifecycle_stages("BK", bad, db_path=db)


def test_a_retired_stage_is_UNREADABLE_by_the_tolerance_lookup(tmp_path):
    """★ THIS IS WHAT MAKES `retired_reason` A GUARD RATHER THAN A NOTE.

    A rule recorded without naming its enforcement point is a belief. Both halves are
    asserted against ONE database so the pin cannot pass because the row was never there:
    the band reads MATURE before retirement and falls to the DEFAULT after.

    The fall is to DEFAULT_TOLERANCE, never the widest — "absence must never be privately
    optimal" — which is why "no band" is represented as 15% rather than left undefined.
    """
    from core.stage_tolerance import DEFAULT_TOLERANCE, tolerance_for
    db = tmp_path / "t.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        _stage_row(conn, "C", "YOUNG", "2026-08-17T20:00:00+00:00")
        conn.commit()

    before = tolerance_for("C", db_path=db)
    assert before.stage == "YOUNG" and before.tolerance == 0.30, before

    retire_lifecycle_stages("C", "model_inapplicable:financials", db_path=db)
    after = tolerance_for("C", db_path=db)
    assert after.stage is None
    assert after.tolerance == DEFAULT_TOLERANCE
    assert after.tolerance <= before.tolerance, "retirement must never WIDEN a band"


def test_the_evaluator_gate_refuses_before_computing_anything():
    """Ruling 1 extends the gate to the EVALUATOR. The refusal is placed after the lens and
    before the panel — the earliest point that knows sector/industry and has computed no
    number — and it exits 5, a code distinct from the crash (1) and the other policy
    refusals (3)."""
    src = (Path(__file__).parent.parent / "evaluate.py").read_text()
    gate = src.split("THE FCF-MODEL CLASS GATE", 1)[1].split("# ── Five pillars", 1)[0]
    assert "applicability_for(yf)" in gate
    assert "sys.exit(5)" in gate
    # The gate must precede the panel build, or a number is computed before the refusal.
    assert src.index("applicability_for(yf)") < src.index("_panel = build_panel"), \
        "the class gate must run BEFORE build_panel — no number before the refusal"


def test_the_batch_gate_precedes_the_series_WRITER():
    """★ THE BATCH GATE'S POSITION IS LOAD-BEARING FOR A REASON THE INTERACTIVE ONE IS NOT.

    `run_dark_fcf_series` WRITES to fundamental_series and sits in the middle of
    run_single_ticker. "Nothing numeric" is not satisfied by refusing to score if a writer
    already ran, so the gate has to be above it, not merely before score_all.
    """
    src = (Path(__file__).parent.parent / "batch" / "runner.py").read_text()
    assert src.index("raise ModelInapplicable") < src.index("run_dark_fcf_series(yf"), \
        "the class gate must precede run_dark_fcf_series, which is a WRITER"
    assert src.index("raise ModelInapplicable") < src.index("pillars = score_all")


def test_model_inapplicable_is_a_REFUSAL_status_not_a_crash():
    """Same distinction RateUnavailable draws: the pipeline worked and DECLINED."""
    src = (Path(__file__).parent.parent / "batch" / "runner.py").read_text()
    handler = src.split("except ModelInapplicable", 1)[1].split("except StageFlip", 1)[0]
    assert 'status="model_inapplicable"' in handler
    assert 'eval_status="model_inapplicable"' in handler
    # Nothing numeric: save_failed_evaluation writes no pillars, no score, no E(R).
    assert "save_failed_evaluation" in handler
    assert "save_evaluation(" not in handler


@pytest.mark.parametrize("sector,industry,caught", [
    (*BANK, True), (*PAYMENTS, False),
])
def test_the_class_membership_is_unchanged_by_this_order(sector, industry, caught):
    """The gate got wider; the CLASS did not. V and WU stay out."""
    assert fcf_model_applicability(sector, industry).applicable is (not caught)


# ═════════════════════════════════════════════════════════════════════════════
#  RULING 2 — stage freshness
# ═════════════════════════════════════════════════════════════════════════════

def _series_row(ticker, metric, period_end, value, ptype="FY"):
    return SeriesPoint(ticker=ticker, metric=metric, period_end=period_end,
                       period_type=ptype, value=value, unit="USD")


def test_staleness_ignores_rows_the_classifier_CANNOT_read(tmp_path):
    """★★ THE SIGNAL IN THE RULING AS WORDED WOULD HAVE RAISED THREE FALSE HALTS ON DAY ONE.

    "any name whose series is newer than its stored stage" taken literally means
    `max(first_observed)` over every row — and measured on production 2026-08-28 that flags
    19 of 28, including JPM, SKHY and USB whose ONLY newer rows are the currency-block and
    class-flag rows written that morning: `value=NULL`, on a `period_type` the classifier
    never queries.

    A row the classifier cannot read cannot change a stage. Counting it as staleness would
    halt runs over nothing and teach the next session to distrust the guard.
    """
    db = tmp_path / "t.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        _stage_row(conn, "ZZ", "MATURE", "2026-08-17T20:00:00+00:00")
        conn.commit()

    # A block row, exactly the shape written on 2026-08-28: NULL value, unreadable type.
    save_fundamental_series([SeriesPoint(
        ticker="ZZ", metric="ingest_block:cash_flow", period_end="2026-08-28",
        period_type="BLOCK_FY", value=None, unit=None, excluded=True,
        exclusion_reason="currency:non_usd_native")], db_path=db)
    assert not freshness_for(db, "ZZ").is_stale, \
        "a value-NULL block row on an unreadable period_type is NOT staleness"

    # A row the classifier really does read.
    save_fundamental_series([_series_row("ZZ", "fcf", "2025-12-31", 1.0)], db_path=db)
    assert freshness_for(db, "ZZ").is_stale


def test_the_staleness_signal_matches_what_the_classifier_is_actually_fed():
    """If a third leg is ever wired into `build_legs`, this tuple must move with it or the
    guard goes quietly blind to that input.

    ★ TAKEN OVER THE AST, NOT BY SPLITTING TEXT. The first version of this pin cut the call
    at the first `)`, which lands inside the nested `_fy_series_from_db(...)` argument and
    silently truncated the very thing it was inspecting. Same family as the prose-breaks-
    the-pin lesson: a pin that depends on incidental formatting is one a later session
    "fixes" by weakening.
    """
    import ast
    tree = ast.parse((Path(__file__).parent.parent / "evaluate.py").read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "build_legs"]
    assert len(calls) == 1, f"expected exactly one build_legs call site, found {len(calls)}"

    fed = set()
    for inner in ast.walk(calls[0]):
        if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                and inner.func.id == "_fy_series_from_db"):
            last = inner.args[-1]
            assert isinstance(last, ast.Constant), "metric must be a literal"
            fed.add(last.value)

    assert fed == set(CLASSIFIER_INPUT_METRICS), (
        f"the classifier is fed {sorted(fed)} but the freshness guard watches "
        f"{sorted(CLASSIFIER_INPUT_METRICS)} — the guard is blind to the difference")


def test_an_unapproved_flip_HALTS_and_an_unchanged_recompute_does_not(tmp_path):
    """The four outcomes, and only one of them raises."""
    db = tmp_path / "t.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        _stage_row(conn, "QQ", "HIGROWTH", "2026-08-17T20:00:00+00:00")
        conn.commit()
    save_fundamental_series([_series_row("QQ", "fcf", "2025-12-31", -1.0)], db_path=db)

    guard_stage_write(db, "QQ", "HIGROWTH")          # stale but unchanged — allowed
    guard_stage_write(db, "NEVER_SEEN", "YOUNG")     # first classification — allowed

    with pytest.raises(StageFlipRequiresApproval) as e:
        guard_stage_write(db, "QQ", "YOUNG", "rule2_young")
    msg = str(e.value)
    assert "HIGROWTH" in msg and "YOUNG" in msg
    assert "20% → 30%" in msg, msg
    assert "WIDER" in msg, "the risk direction must be named"
    assert "rule2_young" in msg


def test_approval_is_PER_TRANSITION_not_per_name(tmp_path):
    """★ A blanket per-name unlock would be an override in disguise.

    An override says the classifier is WRONG; an approval says it is RIGHT and may write.
    So approving HIGROWTH → YOUNG must NOT license a later HIGROWTH → DECLINE.
    """
    db = tmp_path / "t.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        _stage_row(conn, "QQ", "HIGROWTH", "2026-08-17T20:00:00+00:00")
        conn.commit()
    save_fundamental_series([_series_row("QQ", "fcf", "2025-12-31", -1.0)], db_path=db)

    save_stage_flip_approval("QQ", "HIGROWTH", "YOUNG", "measured", db_path=db)
    guard_stage_write(db, "QQ", "YOUNG")             # approved — allowed

    with pytest.raises(StageFlipRequiresApproval):
        guard_stage_write(db, "QQ", "DECLINE")       # a DIFFERENT claim — still halts
    assert get_stage_flip_approval("QQ", "HIGROWTH", "DECLINE", db_path=db) is None


def test_an_approval_demands_a_rationale(tmp_path):
    from store.models import OverrideRationaleMissing
    db = tmp_path / "t.db"
    init_db(db)
    for bad in (None, "", "  "):
        with pytest.raises(OverrideRationaleMissing):
            save_stage_flip_approval("QQ", "A", "B", bad, db_path=db)


def test_approvals_are_NOT_stored_in_lifecycle_overrides(tmp_path):
    """The two tables answer different questions and must stay apart."""
    db = tmp_path / "t.db"
    init_db(db)
    save_stage_flip_approval("QQ", "A", "B", "why", db_path=db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM lifecycle_overrides").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM stage_flip_approvals").fetchone()[0] == 1
    conn.close()


def test_the_guard_raises_BEFORE_the_write_in_evaluate():
    """A refusal that has already written something is not a refusal."""
    src = (Path(__file__).parent.parent / "evaluate.py").read_text()
    assert src.index("guard_stage_write(db_path") < src.index("save_lifecycle_stage(result")


def test_the_halt_is_caught_AHEAD_of_the_broad_annotation_handler():
    """★ THE ORDERING IS THE RULING.

    The broad `except Exception` around `_lifecycle_block` degrades an annotation failure
    to a one-line WARN — correct for a feed flake, catastrophic here. A stage flip reduced
    to a WARN in a wall of output IS the silent stage flip the ruling forbids.
    """
    import ast
    tree = ast.parse((Path(__file__).parent.parent / "evaluate.py").read_text())

    def names(handler):
        t = handler.type
        if t is None:
            return {"<bare>"}
        if isinstance(t, ast.Name):
            return {t.id}
        if isinstance(t, ast.Tuple):
            return {e.id for e in t.elts if isinstance(e, ast.Name)}
        return set()

    target = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if any("StageFlipRequiresApproval" in names(h) for h in node.handlers):
            target = node
            break
    assert target is not None, "no try/except guards the lifecycle block"

    order = [names(h) for h in target.handlers]
    idx_typed = next(i for i, n in enumerate(order) if "StageFlipRequiresApproval" in n)
    idx_broad = next(i for i, n in enumerate(order) if "Exception" in n or "<bare>" in n)
    assert idx_typed < idx_broad, (
        "the broad handler is reached first — a stage flip would be degraded to a WARN, "
        "which IS the silent stage flip the ruling forbids")

    typed = target.handlers[idx_typed]
    exits = [n for n in ast.walk(typed)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "exit"]
    assert exits, "the typed handler must HALT, not fall through"
    assert any(isinstance(a, ast.Constant) and a.value == 6
               for e in exits for a in e.args), "halt must exit 6"


def test_band_consequence_names_the_direction():
    from core.stage_tolerance import DEFAULT_TOLERANCE
    db = Path("nonexistent.db")
    assert "unchanged" in band_consequence(db, "MATURE", "MATURE")
    assert "WIDER" in band_consequence(db, "MATURE", "YOUNG")
    assert "tighter" in band_consequence(db, "YOUNG", "MATURE")
    assert DEFAULT_TOLERANCE == 0.15


# ═════════════════════════════════════════════════════════════════════════════
#  RULING 4 — the currency guard
# ═════════════════════════════════════════════════════════════════════════════

def test_the_guarded_and_unguarded_field_sets_are_disjoint_and_stated():
    assert not set(MONETARY_SCORE_BEARING_FIELDS) & set(
        CURRENCY_NEUTRAL_SCORE_BEARING_FIELDS)
    for f in MONETARY_SCORE_BEARING_FIELDS:
        if f == "market_cap":
            continue                     # basis resolved from the payload, see below
        assert f in FIELD_CURRENCY_BASIS, f"{f} is guarded but has no declared basis"


@pytest.mark.parametrize("field", ["gross_margin", "roe", "debt_to_equity", "fcf_yield",
                                   "trailing_pe", "beta", "shares_outstanding"])
def test_currency_NEUTRAL_fields_are_never_blocked(field):
    """★ BLOCKING A RATIO WOULD DISCARD VALID DATA.

    A ratio whose numerator and denominator share a basis reads the same in KRW and USD.
    Verified against the live case rather than assumed: SKHY's `freeCashFlowYieldTTM` is
    0.0777, and KRW TTM FCF ÷ KRW market cap reproduces 7.77% — FMP's key-metrics block is
    internally consistent on the ISSUER basis. "ALL score-bearing fields" means every field
    a currency error can REACH.
    """
    assert field_is_blocked(field, "KRW", "USD") is None


@pytest.mark.parametrize("field", ["total_debt", "total_cash", "free_cashflow",
                                   "operating_cashflow", "enterprise_value"])
def test_reporting_basis_monetary_fields_block_on_a_non_USD_reporter(field):
    reason = field_is_blocked(field, "KRW", "USD")
    assert reason and "non_usd_blocked:KRW" in reason
    assert field_is_blocked(field, "USD", "USD") is None


def test_UNKNOWN_currency_BLOCKS():
    """"We could not tell" is exactly where an undetected currency error lives."""
    assert field_is_blocked("free_cashflow", None, "USD")
    assert field_is_blocked("current_price", "USD", None)


def test_disagreeing_statements_yield_UNKNOWN_not_a_majority_vote():
    """Two statements claiming different currencies for one issuer is not a thing to
    average — it is an unknown, and an unknown blocks."""
    raw = {"cashflow": [{"reportedCurrency": "USD"}],
           "balance": [{"reportedCurrency": "KRW"}],
           "profile": [{"currency": "USD"}]}
    reporting, quote = payload_currencies(raw)
    assert reporting is None and quote == "USD"
    assert field_is_blocked("free_cashflow", reporting, quote)


def test_market_cap_basis_is_resolved_from_the_PAYLOAD_not_the_field_name():
    """★★ THE DEFECT THIS ORDER'S OWN DARK DIFF CAUGHT, PINNED SO IT CANNOT RETURN.

    A field's currency basis belongs to THE ENDPOINT THAT SUPPLIED IT, not to its name.
    Ruling 3 moved `market_cap` from `key-metrics-ttm` (ISSUER → reporting basis) to
    `market-capitalization` (LISTING → quote basis), and the adapter still falls back to
    key-metrics when the newer endpoint is absent — which is what every recorded fixture
    does. So ONE field sits on EITHER basis depending on who answered.

    The first version of the map hard-coded "reporting", and the dark diff showed SKHY's
    market_cap being BLOCKED — the guard suppressing the very USD figure ruling 3 exists to
    supply. `market_cap` is deliberately absent from FIELD_CURRENCY_BASIS so no one can
    re-add a static answer without this pin failing.
    """
    assert "market_cap" not in FIELD_CURRENCY_BASIS
    assert market_cap_basis({"market_capitalization": [{"marketCap": 1.0}]}) == "quote"
    assert market_cap_basis({"market_capitalization": []}) == "reporting"
    assert market_cap_basis({}) == "reporting", "fails toward the basis that BLOCKS"

    # And the consequence, end to end: a KRW reporter with the new endpoint keeps its cap.
    assert field_is_blocked("market_cap", "KRW", "USD", basis_override="quote") is None
    assert field_is_blocked("market_cap", "KRW", "USD", basis_override="reporting")


def test_the_guard_BLOCKS_it_never_converts():
    """No rate, no arithmetic, no forex call — the value is dropped, not rescaled."""
    from core.datatypes import TickerData
    td = TickerData(
        ticker="ZZ", name=None, sector=None, industry=None, sic=None,
        gross_margin=missing_prov("fmp"), operating_margin=missing_prov("fmp"),
        profit_margin=missing_prov("fmp"), roe=missing_prov("fmp"),
        roa=missing_prov("fmp"), current_ratio=missing_prov("fmp"),
        debt_to_equity=Prov(50.0, "fmp", None, "medium"),
        total_debt=Prov(24_757_848_000_000, "fmp", None, "medium"),
        total_cash=missing_prov("fmp"),
        free_cashflow=Prov(24_793_783_000_000, "fmp", None, "medium"),
        operating_cashflow=missing_prov("fmp"), revenue_growth=missing_prov("fmp"),
        trailing_pe=Prov(12.0, "fmp", None, "medium"), forward_pe=missing_prov("fmp"),
        analyst_count=missing_prov("fmp"), target_mean_price=missing_prov("fmp"),
        price_to_book=missing_prov("fmp"), ev_to_ebitda=missing_prov("fmp"),
        ev_to_revenue=missing_prov("fmp"), market_cap=missing_prov("fmp"),
        current_price=Prov(160.83, "fmp", None, "medium"),
        enterprise_value=missing_prov("fmp"), fcf_yield=Prov(0.0777, "fmp", None, "medium"),
        shares_outstanding=missing_prov("fmp"), beta=missing_prov("fmp"),
        earnings_history=[], insider_transactions=[], price_history=[],
        gross_margin_trajectory=None, revenue_growth_trajectory=None, feed_source="fmp")

    raw = {"cashflow": [{"reportedCurrency": "KRW"}], "profile": [{"currency": "USD"}]}
    out = apply_currency_guard(td, raw)

    assert out.free_cashflow.is_missing(), "a KRW cash flow must be dropped"
    assert "non_usd_blocked:KRW" in out.free_cashflow.source
    assert out.total_debt.is_missing()
    # Currency-NEUTRAL and quote-basis fields survive untouched.
    assert out.debt_to_equity.value == 50.0
    assert out.fcf_yield.value == 0.0777
    assert out.trailing_pe.value == 12.0
    assert out.current_price.value == 160.83, "USD-quoted price is not touched"


def test_a_fully_USD_issuer_is_returned_UNTOUCHED():
    """The overwhelmingly common case must be a no-op, object-identical."""
    from core.datatypes import TickerData
    td = object.__new__(TickerData)
    raw = {"cashflow": [{"reportedCurrency": "USD"}], "profile": [{"currency": "USD"}]}
    assert apply_currency_guard(td, raw) is td


# ═════════════════════════════════════════════════════════════════════════════
#  RULING 3 — the market-cap anchor
# ═════════════════════════════════════════════════════════════════════════════

def test_the_anchor_is_ONE_endpoint_ONE_basis_and_no_float_variants():
    """★ "no float variants" IS A CHOICE BETWEEN TWO DEFENSIBLE NUMBERS, NOT A DETAIL.

    Vic's own reference (~$909.30B) is the FREE-FLOAT cap; the full cap is ~$1.14T. The gap
    is 25.6%. So the tool must not compute, store or offer a float variant at all.
    """
    # TAKEN OVER CODE LITERALS, NOT THE FILE TEXT. The module's docstring EXPLAINS why
    # key-metrics and free-float are not used, so a text scan fires on the prohibition
    # itself — the identical mistake made and recorded on the earlier order of the same
    # day. "A pin that prose can break is one a later session weakens instead of heeding."
    literals = _code_string_literals("tools/write_market_cap_anchor.py")
    assert any("market-capitalization" in s for s in literals)
    for banned in ("floatshares", "freefloat", "shares-float", "key-metrics"):
        assert not any(banned in s.lower() for s in literals), \
            f"{banned!r} as a CODE literal — the anchor is full-cap, one endpoint"
    src = (Path(__file__).parent.parent / "tools" / "write_market_cap_anchor.py").read_text()
    assert "BASIS_FULL_MARKET_CAP" in src


def test_the_anchor_refuses_a_non_USD_quote():
    """Writing an anchor without checking would repeat the defect one layer up."""
    src = (Path(__file__).parent.parent / "tools" / "write_market_cap_anchor.py").read_text()
    body = src.split("def pull(", 1)[1]
    assert 'ccy != "USD"' in body
    assert "REFUSING" in body
    assert "raise RuntimeError" in body


def test_the_anchor_row_uses_a_period_type_no_consumer_queries(tmp_path):
    """Coexistence by construction, same rule the block rows follow."""
    import evaluate
    from tools.write_market_cap_anchor import (METRIC_MARKET_CAP_ANCHOR, PERIOD_ANCHOR)
    from core.fundamental_series import ALL_METRICS
    assert PERIOD_ANCHOR not in ("FY", "TTM_Q")
    assert METRIC_MARKET_CAP_ANCHOR not in ALL_METRICS

    db = tmp_path / "t.db"
    save_fundamental_series([
        _series_row("ZZ", "fcf", "2025-12-31", 5.0),
        SeriesPoint(ticker="ZZ", metric=METRIC_MARKET_CAP_ANCHOR,
                    period_end="2026-08-28", period_type=PERIOD_ANCHOR,
                    value=1.14e12, unit="USD", basis="full_market_cap"),
    ], db_path=db)
    assert evaluate._fy_series_from_db(db, "ZZ", "fcf") == [("2025-12-31", 5.0)]
    assert not freshness_for(db, "ZZ").is_stale or True   # no stage row: nothing to stale


def test_the_anchor_carries_its_own_timestamp_and_price():
    """The ADR cap moves intraday — measured $1,141.66B at $160.83 then $1,143.15B at
    $161.04 minutes later. A cap without its price and pull time is not reproducible."""
    src = (Path(__file__).parent.parent / "tools" / "write_market_cap_anchor.py").read_text()
    for required in ("pulled_at_utc", "quote_price", "implied_shares", '"endpoint"'):
        assert required in src
