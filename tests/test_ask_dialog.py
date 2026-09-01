"""The read-only Claude dialog on the deep view (built 2026-09-01, Vic's order).

WHAT WAS ORDERED. A dialog box on the evaluation screen that answers questions,
aware of both the numbers on that page and the mechanics of CALIBER. Vic ruled
its scope explicitly: "it only needs to answer my questions... it doesn't need
to do anything other than research. it doesn't need to save anything."

WHY THE PINS BELOW ARE STRUCTURAL RATHER THAN BEHAVIOURAL. "Read-only" is the
entire safety argument for putting a model on a production screen, and a
behavioural test can only show that the path did not write ON THE INPUTS TRIED.
The standing rule here is that a rule recorded without naming its enforcement
point is a belief, not a guard — so read-only is enforced over the AST of both
the module and the route handler, where a later session adding a save_* call
trips it on any input.

TEST 5 IS THE POSITIVE CONTROL AND IT IS NOT OPTIONAL. It asserts the same
detector FIRES on `override_post`, which really does write. Without it, tests
3 and 4 would pass just as happily if the detector were broken and matched
nothing at all — the recorded "a sweep that cannot fire proves nothing"
discipline, same shape as L-4a's shuffled-input test.

NOTE, MEASURED NOT ASSUMED: importing `web.app` runs `init_db()` at module
scope (web/app.py:48) against production caliber.db. That is pre-existing and
was measured md5-neutral at this build (69dc2328… before and after), because
the tables already exist and init_db is idempotent. It is NOT introduced by
this order and is not fixed here — changing it is a restructuring of working
code and needs a ruling.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from web.ask import AskUnavailable, CALIBER_PRIMER, build_context  # noqa: E402


# Names that mutate the store. Kept deliberately broad: the point is that the
# ask path touches NONE of them, so a false positive here is cheap and a false
# negative is the whole defect.
_WRITE_NAMES = {
    "save_evaluation", "save_grade", "save_override", "save_synthesis_cache",
    "save_lifecycle_stage", "save_field_provenance", "init_db",
    "commit", "executescript",
}


def _calls_in(node: ast.AST) -> set:
    """Every called name in a subtree, by bare name and by attribute tail."""
    found = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                found.add(f.id)
            elif isinstance(f, ast.Attribute):
                found.add(f.attr)
    return found


def _func_named(tree: ast.AST, name: str):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError(f"function {name!r} not found")


# ── 1-2. The context is the page, not a re-fetch ──────────────────────────────

def _sample_eval():
    return {
        "id": 22,
        "ticker": "GOOG",
        "status": "ok",
        "lens": "compounder",
        "expected_return": 7.25,
        "avg_score": 3.8,
        "overall_conf": "medium",
        "verdict_conf": "medium",
        "calibration_instrument": 1,
        "run_at": "2026-09-01 10:00:00",
        "pillars": [{
            "name": "valuation",
            "score": 3,
            "confidence": "medium",
            "rationale": "Trades above the panel anchor.",
            "fields": [{"name": "pe_forward", "value": 24.1,
                        "source": "fmp", "confidence": "medium"}],
        }],
        "synthesis": {"verdict": "hold", "priceTargets": {"base": 215}},
    }


def test_context_carries_the_numbers_on_screen():
    """The model must see the evaluation the user is looking at."""
    ctx = build_context(
        _sample_eval(),
        conflicts=[{"field_key": "capex", "src_a": "fmp", "val_a": 8.4,
                    "src_b": "edgar", "val_b": 5.05, "override": None}],
        overrides=[{"field_name": "beta", "override_value": 1.02,
                    "override_at": "2026-08-30", "note": "manual"}],
    )
    for needle in ("GOOG", "compounder", "valuation", "pe_forward",
                   "capex", "unresolved", "beta", "priceTargets"):
        assert needle in ctx, f"context is missing {needle!r}"


def test_a_defect_tagged_row_announces_itself_in_the_context():
    """A TECHNICALS-REVERSED row must not be discussed as if it were clean.

    68 stored evaluations carry defect_tags. If the dialog reads one without
    being told, it will explain poisoned 2021 technicals as though they were
    current — the exact laundering the tag exists to prevent.
    """
    ev = _sample_eval()
    ev["defect_tags"] = "TECHNICALS-REVERSED-AT-SYNTHESIS"
    ctx = build_context(ev)
    assert "TECHNICALS-REVERSED-AT-SYNTHESIS" in ctx
    assert "TAGGED" in ctx


# ── 3-5. Read-only, enforced structurally, with a positive control ────────────

def test_the_ask_module_contains_no_write_call():
    tree = ast.parse((_ROOT / "web" / "ask.py").read_text(encoding="utf-8"))
    hits = _calls_in(tree) & _WRITE_NAMES
    assert not hits, f"web/ask.py must not write; found {sorted(hits)}"


def test_the_ask_route_handler_contains_no_write_call():
    tree = ast.parse((_ROOT / "web" / "app.py").read_text(encoding="utf-8"))
    hits = _calls_in(_func_named(tree, "deep_ask")) & _WRITE_NAMES
    assert not hits, f"deep_ask must not write; found {sorted(hits)}"


def test_POSITIVE_CONTROL_the_detector_fires_on_a_handler_that_does_write():
    """Without this, the two tests above pass vacuously if the detector breaks."""
    tree = ast.parse((_ROOT / "web" / "app.py").read_text(encoding="utf-8"))
    hits = _calls_in(_func_named(tree, "override_save")) & _WRITE_NAMES
    assert "save_override" in hits, (
        "the write detector no longer fires on a known writer — the read-only "
        "pins above are now vacuous"
    )


# ── 6. Fails loud, never silently ─────────────────────────────────────────────

def test_a_missing_api_key_raises_rather_than_returning_an_empty_answer(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(AskUnavailable) as exc:
        build_ctx = build_context(_sample_eval())
        from web.ask import answer
        answer("why compounder?", build_ctx)
    assert "ANTHROPIC_API_KEY" in str(exc.value)


def test_an_empty_question_is_refused_before_any_api_call(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    from web.ask import answer
    with pytest.raises(AskUnavailable):
        answer("   ", build_context(_sample_eval()))


# ── 7. The primer states the limits the answers depend on ─────────────────────

def test_the_primer_declares_the_dialog_read_only_and_non_scoring():
    """The model is told what it may not claim to be. Substantive, not cosmetic.

    Checked as whole phrases on the primer CONSTANT — not a text scan over the
    module — because two pins on 2026-08-28 fired on the prose explaining a
    prohibition rather than on the prohibition. This reads the value the API
    actually receives.
    """
    p = CALIBER_PRIMER
    assert "READ-ONLY" in p
    assert "Nothing you say is an input to any score." in p
    assert "NEVER resolve a contradiction by picking a side." in p
    assert "Absence is not zero." in p


def test_the_primer_carries_the_grading_rubric_in_its_ruled_order():
    """The rubric is order-sensitive; a mis-ordered copy would answer wrongly."""
    p = CALIBER_PRIMER
    i_noconv = p.index("no-conviction")
    i_flat = p.index("flat outcome")
    i_a = p.index("-> A")
    assert i_noconv < i_flat < i_a, "rubric is out of its ruled evaluation order"
    assert "90 days" in p


def test_the_context_asks_only_for_columns_that_EXIST_on_evaluations():
    """A defect found in this order's own first draft, by the live model.

    build_context originally read company_name / sector / industry /
    current_price. None is a column on `evaluations`. Every invented field
    rendered as an em-dash, and the answer then reported four fields "blank"
    as though the evaluation were incomplete. A context builder that silently
    renders absence for a field that was never stored MANUFACTURES A DATA GAP
    THAT DOES NOT EXIST — worse than omitting the line, because the model
    reasons about the fabricated absence.

    READ OVER THE AST, NOT THE TEXT. The first version of this pin scanned the
    module source for the phantom names and failed on the COMMENT that explains
    why they are forbidden — the third time in this repo that a text-scan pin
    has fired on the prose describing its own prohibition (two on 2026-08-28,
    both rewritten over the AST for the same reason). A pin that prose can
    break is one a later session weakens instead of heeding.
    """
    tree = ast.parse((_ROOT / "web" / "ask.py").read_text(encoding="utf-8"))
    fn = _func_named(tree, "build_context")

    # Every literal key fetched off the evaluation row inside build_context.
    keys = set()
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get"
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "ev"
                and n.args and isinstance(n.args[0], ast.Constant)):
            keys.add(n.args[0].value)
    for n in ast.walk(fn):
        if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                and n.value.id == "ev" and isinstance(n.slice, ast.Constant)):
            keys.add(n.slice.value)

    assert keys, "found no ev lookups — this pin has gone blind"

    real = {
        "id", "ticker", "run_at", "lens", "status", "error_msg",
        "pillars_json", "synthesis_json", "avg_score", "overall_conf",
        "verdict_conf", "expected_return", "supersedes_id",
        "supersede_reason", "calibration_instrument", "defect_tags",
    }
    # Added by _prep_eval, not columns: parsed blobs and a display helper.
    derived = {"pillars", "synthesis", "run_at_short"}

    phantom = keys - real - derived
    assert not phantom, (
        f"build_context reads {sorted(phantom)}, which are not columns on "
        "evaluations and not added by _prep_eval — they render as em-dashes "
        "and fabricate data gaps"
    )


def test_a_calibration_row_says_so():
    """GOOG is the calibration line and GOOGL is the held one (same CIK).

    Reading a calibration row as a held position is the share-class
    double-count hazard in conversational form.
    """
    ev = _sample_eval()
    ev["calibration_instrument"] = 1
    assert "CALIBRATION INSTRUMENT" in build_context(ev)
