"""DOCTRINE PIN — FMP IS THE SOURCE, EDGAR IS THE ARBITER (ruled 2026-08-21, applied 08-22).

Order: docs/orders/2026-08-22-doctrine-fmp-source-edgar-arbiter.md

The doctrine demotes the EDGAR machinery to an AUDIT LAYER and says, in the same breath,
that it is **NOT unwound and NOT deleted — deleting EDGAR-path code requires a Vic ruling.**

That sentence is the whole reason this file exists. A demotion is exactly the kind of
ruling a later session reads as permission to tidy up: the code is off the critical path,
nothing fails when it goes, and the deletion looks like housekeeping rather than a change
of doctrine. Per the standing rule — **a rule recorded without naming its enforcement
point is a belief, not a guard** — the no-delete clause gets an enforcement point here.

WHAT THIS FILE IS NOT. It does not claim any of this code ought to live forever, and it is
not an argument against ever removing it. It is a TRIPWIRE: removal must be a ruled act
that arrives with an order, not a side effect of a cleanup pass. Every assertion below
fails LOUDLY with the name of the ruling it would be overturning, so the next session is
forced to go and read that ruling rather than delete a line and move on.

Structure over prose, throughout: the call-site checks run over the AST, not the text.
That choice is inherited from L-4b, where a substring count was tripped by a COMMENT
mentioning the symbol — and a pin that prose can break is one a later session weakens
instead of heeding.
"""
import ast
from pathlib import Path

import pytest

import core.fundamental_series as FS
from adapters.edgar_adapter import FIELD_SPECS


def _spec(name):
    for s in FIELD_SPECS:
        if s.name == name:
            return s
    raise AssertionError(f"FIELD_SPECS has no spec named {name!r}")


def _calls_to(path, func_name):
    """ast.Call nodes calling a bare NAME. Comments and docstrings are invisible here."""
    src = Path(path).read_text(encoding="utf-8")
    return [n for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == func_name]


# ── 1. the capex chain: L-4d.1's arming survives the demotion ────────────────────────

def test_the_capex_chain_still_carries_all_THREE_ruled_tags():
    """The three-tag chain armed at L-4d.1 is audit-layer now, and stays intact.

    Each tag cost its own ruling: the generic tag at L-4d (NVDA/V/LRCX), the
    Other-PP&E tag at L-4d.1 (LLY), the latter over a COMMITTED PIN that asserted the
    opposite. Demotion to the audit layer does not retire any of that — an arbiter with a
    truncated chain arbitrates wrongly, and silently.
    """
    chain = [c for c, _ns in _spec("capex").synonyms]
    assert chain == [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    ], (
        "the capex chain changed. ORDER IS LOAD-BEARING (generic tag first) and each entry "
        "was armed by a named ruling: L-4d (docs/l4d-capex-synonym.md) for entry 2, L-4d.1 "
        "(docs/l4d1-lly-capex-basis.md) for entry 3. The 2026-08-22 doctrine DEMOTED this "
        "machinery to an audit layer; it did NOT authorise shortening it.")


def test_the_capex_chain_is_not_silently_shortened_to_the_pre_L4d_single_tag():
    """A positive control on the pin above: the pre-L-4d shape must not pass.

    Written as its own assertion because 'the chain is a list of three' and 'the chain is
    not the single-tag spec we started from' fail for different edits, and only the second
    one names the regression a later session is most likely to introduce.
    """
    assert len(_spec("capex").synonyms) >= 3, (
        "capex is back to a short chain — this is the silent-expiry shape L-4d was raised "
        "to kill (an issuer migrates tags, the bare spec goes quiet, coverage drops with no "
        "error). Re-arming needs a ruling.")


# ── 2. the typed reasons: the deletion that WAS the fix stays done ───────────────────

def test_the_typed_reason_machinery_survives_the_demotion():
    """`withheld_reason()` is the L-4d step-3 fix and it is still the reporting path."""
    assert hasattr(FS, "withheld_reason"), (
        "core.fundamental_series.withheld_reason is gone. It is the structural fix from "
        "L-4d step 3 — the resolver reports its OWN reason instead of a caller guessing "
        "one. Removing it re-opens the mislabel as a CLASS, not as instances.")
    for const in ("REASON_FIELD_UNKNOWN", "REASON_SERIES_EMPTY", "REASON_FORM_EXCLUDED"):
        assert hasattr(FS, const), f"typed reason {const} was removed"


def test_the_deleted_withholding_constants_stay_deleted():
    """L-4d deleted WITHHELD_NO_CAPEX / WITHHELD_NO_OCF, and THE DELETION WAS THE FIX.

    Restated here rather than left only in tests/test_l4d_typed_reasons.py because the
    doctrine's 'demoted, not unwound' language could be misread as an invitation to restore
    retired EDGAR-path symbols. It is not. A constant asserting 'no tag' cannot know which
    of four causes occurred, so any code holding one is FORCED to guess.
    """
    assert not hasattr(FS, "WITHHELD_NO_CAPEX")
    assert not hasattr(FS, "WITHHELD_NO_OCF")


# ── 3. field_provenance: still written ───────────────────────────────────────────────

def test_field_provenance_is_still_written():
    """The audit layer is only an audit layer while it still records anything."""
    src = Path("store/models.py").read_text(encoding="utf-8")
    assert "INSERT INTO field_provenance" in src, (
        "the field_provenance writer is gone. The doctrine names field_provenance as part "
        "of the demoted-but-retained audit layer; an audit layer that writes nothing "
        "cannot arbitrate anything later.")


# ── 4. THE TRIPWIRE — EDGAR's four score-bearing call sites ──────────────────────────

@pytest.mark.parametrize("path,line_hint", [("evaluate.py", 300), ("batch/runner.py", 254)])
def test_EDGAR_is_still_score_bearing_on_both_write_paths(path, line_hint):
    """★ THE STOP-CONDITION TRIPWIRE. See §5 of the doctrine order.

    The doctrine says EDGAR is invoked in EXACTLY THREE CASES — arbitration, filed-tag
    provenance, rulings. **The code contradicts that today**, and the contradiction is
    ruled and recorded (docs/phase-archive.md:307-314, 2026-08-15): EDGAR SELECTS THE LENS
    AND THE LENS MOVES SCORES. It is also a hard gate — evaluate.py exits 1 on an EDGAR
    failure, and batch/runner.py deliberately does not wrap it, so a mid-batch 403
    persists a `failed` row per ticker.

    That contradiction is REPORTED FOR RULING, not resolved by this order. This pin holds
    the disputed state still while Vic rules. If a later session removes these call sites,
    this fails — which is the point: migrating EDGAR off the scoring path is precisely the
    change §5 is asking to be ruled on, so it must not happen by accident, and it must not
    happen as a quiet consequence of 'EDGAR is only an arbiter now'.

    THIS PIN IS EXPECTED TO BE RETIRED BY NAME when §5 is ruled. Retiring it is correct;
    deleting the call sites without retiring it is the thing being prevented.
    """
    assert _calls_to(path, "select_lens"), (
        f"{path} no longer calls select_lens(). EDGAR's SIC feeds lens selection and the "
        "lens moves scores — removing this is a scoring-path change under an open ruling "
        "(doctrine order §5). It needs its own order.")
    assert _calls_to(path, "fetch_edgar"), (
        f"{path} no longer calls fetch_edgar(). Under the current architecture EDGAR is a "
        "MANDATORY every-run input, not an optional enrichment; that is exactly what §5 of "
        "the doctrine order asks Vic to rule on. Do not settle it by deletion.")
    assert _calls_to(path, "build_panel"), (
        f"{path} no longer calls build_panel(), which takes EDGAR as a panel input")

    src = Path(path).read_text(encoding="utf-8")
    assert "edgar.sic" in src, f"{path} no longer propagates EDGAR's SIC"


def test_the_growth_pillar_still_takes_EDGAR():
    """The fourth score-bearing path, and the least visible of the four.

    score_growth(yf, edgar, lens) is reached through score_five_pillars, so nothing at the
    call sites above names it. A migration that tidied the three obvious paths and missed
    this one would leave EDGAR score-bearing while the record said otherwise — which is the
    failure mode the whole §5 report is about.
    """
    src = Path("core/pillars.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "score_growth"), None)
    assert fn is not None, "core.pillars.score_growth is gone"
    assert "edgar" in [a.arg for a in fn.args.args], (
        "score_growth no longer takes EDGAR. That is a scoring-path change to a pillar, "
        "under the open §5 ruling of the 2026-08-22 doctrine order.")


# ── 5. the doctrine's own record ─────────────────────────────────────────────────────

def test_the_doctrine_order_document_exists_and_is_reachable():
    """The pins above cite an order by path; a pin citing a missing document is a dead pin."""
    p = Path("docs/orders/2026-08-22-doctrine-fmp-source-edgar-arbiter.md")
    assert p.exists(), "the doctrine order document these pins cite is missing"
    text = p.read_text(encoding="utf-8")
    # The two clauses every assertion in this file ultimately rests on.
    assert "NOT unwound" in text and "requires a Vic ruling" in text
    assert "STOP-CONDITION REPORT" in text
