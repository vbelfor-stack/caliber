"""L-4c — pins on the fundamental_series coverage-expansion writer.

WHAT THIS FILE PROTECTS. `tools/expand_fcf_series.py` is the first surface that writes
`fundamental_series` WITHOUT running an evaluation. That is exactly the capability the
L-4c order needed and exactly the capability that could quietly re-create the 2026-08-17
contamination shape if it ever grew a second destination or a second table.

Four properties, each of which the order names as non-negotiable:

  1. FAIL-CLOSED. A ticker whose filings do not support FCF writes ZERO rows and carries a
     TYPED REASON. Never a synthetic series, never a partial one. Test 1 and test 2.
  2. TABLE ISOLATION. fundamental_series and nothing else. Test 3 asserts this
     BEHAVIOURALLY (every other table still empty after a commit run) and test 6 asserts
     it STRUCTURALLY over the AST, so the behavioural pin cannot be satisfied by a writer
     that merely happens not to fire on this fixture.
  3. DESTINATION ROUTING. One resolved destination, `db_path or _DEFAULT_DB`, per
     evaluate.py:259. Test 4 proves a named destination takes the rows AND that production
     is untouched — the half the L-2a/micro-order pair both turned on.
  4. EXPECTED-DELTA SEMANTICS. Test 5. A NEW ticker is held to an exact row count; a
     ticker already stored is a re-observation where 0 new rows is the CORRECT idempotent
     outcome. This is pinned because the first cut of the tool asserted `+N` unconditionally
     and reported correct idempotent behaviour as a MISMATCH — a reconciliation that cries
     wolf is one a later session learns to wave through.

Offline by construction: `build_one` is monkeypatched, so no test here touches FMP, EDGAR
or the network. The live build path is already covered by tests/test_fundamental_series.py.
"""
from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.fundamental_series import (                          # noqa: E402
    METRIC_FCF, PERIOD_FY, PERIOD_TTM_Q, SeriesPoint,
)
from tools import expand_fcf_series as X                       # noqa: E402

_TOOL_SRC = Path(X.__file__)


def _point(ticker: str, period_end: str, value: float,
           period_type: str = PERIOD_FY) -> SeriesPoint:
    return SeriesPoint(ticker=ticker, metric=METRIC_FCF, period_end=period_end,
                       period_type=period_type, value=value, unit="USD")


def _covered(ticker: str, n: int = 4) -> X.Build:
    b = X.Build(ticker)
    b.basis = "not_applicable"
    b.points = [_point(ticker, f"202{i}-12-31", 1000.0 + i) for i in range(n)]
    return b


# L-4d deleted WITHHELD_NO_CAPEX (a constant that asserted "no tag" regardless
# of cause). This test only ever needed SOME typed reason, so it now carries the
# real post-L-4d shape for a genuine data limit rather than importing a constant.
_UNCOVERED_REASON = "capex:no_tag"


def _uncovered(ticker: str) -> X.Build:
    """A build the FILINGS could not support — the builder withheld the whole family."""
    b = X.Build(ticker)
    b.basis = "not_applicable"
    b.withheld = {METRIC_FCF: _UNCOVERED_REASON}
    b.reason = f"withheld:{METRIC_FCF}={_UNCOVERED_REASON}"
    return b


def _run(monkeypatch, capsys, builds, argv):
    """Drive the CLI with `build_one` stubbed to return `builds` in order."""
    it = iter(builds)
    monkeypatch.setattr(X, "build_one", lambda t: next(it))
    monkeypatch.setattr(sys, "argv", ["expand_fcf_series", *argv])
    X.main()
    return capsys.readouterr().out


def _counts(db: Path) -> dict:
    if not Path(db).exists():
        return {}                       # never created — see the fail-closed test
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")]
        return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
    finally:
        conn.close()


# ── 1/2. FAIL-CLOSED ─────────────────────────────────────────────────────────

def test_an_uncovered_ticker_writes_nothing_and_carries_a_typed_reason(
        monkeypatch, capsys, tmp_path):
    """The order's hard constraint: never manufacture FCF the filings do not support.

    The failure this forbids is not a wrong number — it is a PLAUSIBLE one. A zero row, a
    carried-forward value or a partial family would all be indistinguishable downstream
    from a real series, and step 4 would then block a name on fabricated evidence.
    """
    db = tmp_path / "fc.db"
    out = _run(monkeypatch, capsys, [_uncovered("JPM")],
               ["JPM", "--db-path", str(db), "--commit"])

    assert "UNCOVERED" in out and _UNCOVERED_REASON in out, (
        "the reason must be TYPED and visible, not a silent skip")
    assert "SKIPPED (fail-closed)" in out
    assert _counts(db).get("fundamental_series", 0) == 0, "an uncovered name wrote rows"
    # STRONGER THAN ZERO ROWS, and worth pinning as such: with no covered ticker in the
    # run, no writer is reached at all, so the destination is never even created. The
    # fail-closed path does not open a database to decline to write to it.
    assert not db.exists(), "the fail-closed path still created its destination"


def test_a_build_that_raises_becomes_a_typed_reason_and_never_a_series(monkeypatch):
    """LOUD FAILURE BEATS SILENT DEGRADATION — but a measurement failure must not crash
    the run either, or one unreachable name would deny coverage to the other 23."""
    def boom(_t):
        raise RuntimeError("EDGAR 403")
    monkeypatch.setattr(X, "fetch_fmp", lambda *a, **k: boom(None))

    b = X.build_one("ARM")
    assert b.covered is False
    assert b.points == []
    assert b.reason.startswith("build_failed:RuntimeError"), b.reason


# ── 3. TABLE ISOLATION ───────────────────────────────────────────────────────

def test_the_tool_writes_fundamental_series_and_no_other_table(
        monkeypatch, capsys, tmp_path):
    """L-4c is forbidden from touching evaluations, lifecycle_stage or anything else.

    Asserted over EVERY table the schema declares rather than a named list, so a table
    added later is covered by this pin on the day it appears.
    """
    db = tmp_path / "iso.db"
    _run(monkeypatch, capsys, [_covered("BE"), _covered("QBTS", 3)],
         ["BE", "QBTS", "--db-path", str(db), "--commit"])

    counts = _counts(db)
    assert counts["fundamental_series"] == 7
    others = {k: v for k, v in counts.items() if k != "fundamental_series"}
    assert others and all(v == 0 for v in others.values()), (
        f"a table outside fundamental_series was written: {others}")


# ── 4. DESTINATION ROUTING ───────────────────────────────────────────────────

def test_the_named_destination_takes_the_rows_and_production_is_untouched(
        monkeypatch, capsys, tmp_path):
    """The half that both destination-routing defects turned on: it is not enough that
    the scratch db receives the rows — PRODUCTION MUST NOT."""
    prod = tmp_path / "prod.db"
    scratch = tmp_path / "scratch.db"
    monkeypatch.setattr("store.models._DEFAULT_DB", prod)

    _run(monkeypatch, capsys, [_covered("BE")],
         ["BE", "--db-path", str(scratch), "--commit"])

    assert _counts(scratch)["fundamental_series"] == 4
    assert not prod.exists(), "the run created/opened production despite --db-path"


def test_a_dry_run_writes_nothing_and_creates_no_database(monkeypatch, capsys, tmp_path):
    """Without --commit this is a MEASUREMENT. A measurement that leaves an empty database
    behind is how a read-only tool stops being read-only."""
    db = tmp_path / "dry.db"
    out = _run(monkeypatch, capsys, [_covered("BE")], ["BE", "--db-path", str(db)])

    assert "DRY RUN" in out and "EXPECTED DELTA: +4" in out
    assert not db.exists(), "a dry run created its destination"


# ── 5. EXPECTED-DELTA SEMANTICS ──────────────────────────────────────────────

def test_a_new_ticker_is_held_to_an_exact_count_but_a_re_observation_is_not(
        monkeypatch, capsys, tmp_path):
    """Idempotent re-observation is CORRECT and must not be reported as a mismatch.

    First run: BE is unknown to the destination, so +4 is asserted exactly. Second run:
    the same points are already stored, the append-only writer correctly adds nothing,
    and the reconciliation must read MATCH. The first cut of this tool failed here — it
    asserted +4 both times and cried MISMATCH on correct behaviour.
    """
    db = tmp_path / "delta.db"

    first = _run(monkeypatch, capsys, [_covered("BE")],
                 ["BE", "--db-path", str(db), "--commit"])
    assert "EXPECTED DELTA: +4 rows" in first
    assert "wrote +  4" in first and "MATCH" in first
    assert "MISMATCH" not in first

    second = _run(monkeypatch, capsys, [_covered("BE")],
                  ["BE", "--db-path", str(db), "--commit"])
    assert "re-obs" in second, "a stored ticker must be reported as a re-observation"
    assert "wrote +  0" in second
    assert "MISMATCH" not in second, (
        "correct idempotent behaviour was reported as a mismatch")
    assert _counts(db)["fundamental_series"] == 4, "the re-run duplicated rows"


def test_a_short_count_is_reported_as_a_mismatch_and_exits_nonzero(
        monkeypatch, capsys, tmp_path):
    """POSITIVE CONTROL for the pin above. If the reconciliation could never fail, the
    'no MISMATCH' assertions would be vacuous. Half the points collide on one storage key
    (same ticker/metric/period_end/period_type/basis), so 4 built points can only ever
    become 2 stored rows — and that gap must be caught, not absorbed."""
    db = tmp_path / "short.db"
    b = X.Build("BE")
    b.basis = "not_applicable"
    b.points = [_point("BE", "2024-12-31", 1.0), _point("BE", "2024-12-31", 1.0),
                _point("BE", "2023-12-31", 2.0), _point("BE", "2023-12-31", 2.0)]

    monkeypatch.setattr(X, "build_one", lambda t: b)
    monkeypatch.setattr(sys, "argv",
                        ["expand_fcf_series", "BE", "--db-path", str(db), "--commit"])
    with pytest.raises(SystemExit) as e:
        X.main()
    assert e.value.code == 3
    assert "MISMATCH" in capsys.readouterr().out


# ── 6. STRUCTURAL PIN ────────────────────────────────────────────────────────

def test_save_fundamental_series_is_the_only_writer_reachable_from_this_tool():
    """CLASS PIN, over the AST rather than the text.

    Test 3 shows this run wrote no other table. This shows it CANNOT — the module imports
    exactly one persistence function from `store.models`, and every store import is named
    so a later session adding `save_evaluation` here has to delete a test that says why
    not. Taken over the AST because a prose mention of `save_evaluation` in a docstring
    must not be able to trip it, and a pin that prose can break is one a later session
    weakens instead of heeding.
    """
    tree = ast.parse(_TOOL_SRC.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("store")
        for alias in node.names
    }
    assert imported == {"_DEFAULT_DB", "save_fundamental_series"}, (
        f"the tool reached a second store surface: {imported}")
