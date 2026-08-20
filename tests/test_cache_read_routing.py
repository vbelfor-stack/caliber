"""Read-side twin of the write-side destination guard (micro-order, 2026-08-20).

THE DEFECT THIS PINS. `batch/runner.py` called `get_cached_synthesis(ticker, today_str)`
with no destination, so the synthesis-cache READ always resolved to production
`caliber.db` — while the `save_synthesis_cache` twelve lines below it honoured
`db_path or _DEFAULT_DB`. A `--db-path scratch.db` run could therefore REUSE A
PRODUCTION SYNTHESIS it would never write back.

It is the third instance of one shape: a destination flag whose real scope is narrower
than a human reads it. The first was the ids-226-228 contamination; the second was the
L-2a save-side half of this very pair, fixed by making `db_path` required there. The
save side could be closed by removing the default; the read side cannot, because
`get_cached_synthesis` is also called legitimately without one. So the guard here is at
the CALL SITE, and it is written as a class pin (test 3) rather than an instance pin, per
the standing "remove the class, not the instance" ruling.

Test 2 is the positive control and it is not optional: without it, test 1 would pass just
as happily if the cache branch were unreachable in fixture mode, which would make the
whole file vacuous. Same discipline as L-4a's shuffled-input test — a fix that only
appears to work must not be able to pass.
"""
from __future__ import annotations

import ast
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from batch.runner import run_single_ticker          # noqa: E402
from store.models import init_db, get_cached_synthesis, save_synthesis_cache  # noqa: E402

_CACHE_HIT_LOG = "synthesis cache hit"
_TICKER = "MU"


def _seed_cache(db: Path, ticker: str = _TICKER) -> None:
    """Put a today-dated cache row in `db` so a read against it MUST hit.

    The payload is deliberately unparseable: we are measuring WHICH DATABASE WAS READ,
    not what came back. The cache-hit log line is emitted before the parse, so a junk
    payload still proves the read landed, and the broad handler swallows the parse.
    """
    init_db(db)
    save_synthesis_cache(
        ticker, date.today().isoformat(),
        json.dumps({"poisoned": "this row lives in the OTHER database"}),
        123.45, db_path=db,
    )
    assert get_cached_synthesis(ticker, date.today().isoformat(), db) is not None, (
        "seed failed — the rest of this test would be measuring nothing")


def _no_live_synthesis(monkeypatch):
    """Make generation observable and offline.

    Raising is enough: the broad `except` around generation logs 'synthesis skipped' and
    the run continues, so the discriminator stays the cache-hit line.
    """
    import synthesis.client as _client
    calls = []

    def _boom(*a, **kw):
        calls.append(kw.get("ticker") or (a[0] if a else "?"))
        raise RuntimeError("no live synthesis in tests")

    monkeypatch.setattr(_client, "run_synthesis", _boom)
    return calls


# ── 1. The pin ────────────────────────────────────────────────────────────────

def test_a_db_path_run_never_reads_the_production_synthesis_cache(tmp_path, monkeypatch,
                                                                  capsys):
    """The ordered guarantee. conftest's R-1 fixture rebinds the `db_path=_DEFAULT_DB`
    defaults to tmp_path/test_caliber.db, so THAT file is the stand-in production here —
    it is exactly where the unrouted read used to land."""
    stand_in_production = tmp_path / "test_caliber.db"
    scratch = tmp_path / "scratch.db"
    _seed_cache(stand_in_production)
    generated = _no_live_synthesis(monkeypatch)

    run_single_ticker(_TICKER, fixture_mode=True, run_synthesis=True,
                      verbose=True, db_path=scratch)

    out = capsys.readouterr().out
    assert _CACHE_HIT_LOG not in out, (
        "the run reused a synthesis from production while writing to a scratch DB — "
        "this is the partial-routing defect the fix closed")
    assert generated, (
        "generation was never reached, so the cache read cannot have missed for the "
        "right reason — check this test still exercises the cache branch")


# ── 2. Positive control — the read path is genuinely live ─────────────────────

def test_the_same_run_DOES_hit_a_cache_row_in_its_own_destination(tmp_path, monkeypatch,
                                                                  capsys):
    """Without this, test 1 passes for free if the cache branch is dead in fixture mode.
    Identical setup, row moved to the destination the run names."""
    scratch = tmp_path / "scratch.db"
    _seed_cache(scratch)
    generated = _no_live_synthesis(monkeypatch)

    run_single_ticker(_TICKER, fixture_mode=True, run_synthesis=True,
                      verbose=True, db_path=scratch)

    out = capsys.readouterr().out
    assert _CACHE_HIT_LOG in out, (
        "a cache row in the run's OWN destination was not read — the read is now routed "
        "somewhere else entirely, which is a new defect, not the old one")
    assert not generated, "cache hit should have short-circuited generation"


def test_the_production_stand_in_is_not_written_either(tmp_path, monkeypatch):
    """The write-side guarantee restated beside its read-side twin, so the pair reads as
    one rule: under --db-path, production is untouched in BOTH directions."""
    stand_in_production = tmp_path / "test_caliber.db"
    scratch = tmp_path / "scratch.db"
    init_db(stand_in_production)
    _no_live_synthesis(monkeypatch)

    run_single_ticker(_TICKER, fixture_mode=True, run_synthesis=True,
                      verbose=False, db_path=scratch)

    conn = sqlite3.connect(stand_in_production)
    try:
        assert conn.execute("SELECT COUNT(*) FROM synthesis_cache").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0
    finally:
        conn.close()


# ── 3. Class pin — no FOURTH instance of the shape ────────────────────────────

_ROUTED_PATHS = ("batch/runner.py", "evaluate.py")


def _store_fns_taking_a_destination() -> dict:
    """Name -> positional index of db_path (None when keyword-only), read off the source
    so a signature change cannot quietly drop a function out of this pin's scope."""
    tree = ast.parse((_ROOT / "store" / "models.py").read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        pos = [a.arg for a in node.args.args]
        kwonly = [a.arg for a in node.args.kwonlyargs]
        if "db_path" in pos:
            out[node.name] = pos.index("db_path")
        elif "db_path" in kwonly:
            out[node.name] = None
    return out


def test_no_store_accessor_on_a_routed_path_defaults_to_production():
    """REMOVE THE CLASS, NOT THE INSTANCE. Both `--db-path`-honouring entry points must
    name a destination at EVERY store call site — reads included. The save side of this
    pair was closed in L-2a by deleting the default; the read side cannot be, so the
    enforcement point has to be here.

    Taken over the AST, not the text, for the reason the L-4b call-site pin records: a
    substring count is trippable by a comment, and a pin that prose can break is one a
    later session weakens instead of heeding.

    NOT IN SCOPE: web/app.py, which reads and writes production unrouted BY DESIGN — it
    is the production dashboard and has no destination flag to understate. That is a
    deliberate exclusion, stated so it is not mistaken for an oversight.
    """
    sigs = _store_fns_taking_a_destination()
    assert "get_cached_synthesis" in sigs, "the pin lost sight of the function it exists for"

    unrouted = []
    for rel in _ROUTED_PATHS:
        tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if fn not in sigs:
                continue
            idx = sigs[fn]
            routed = ("db_path" in [k.arg for k in node.keywords]
                      or (idx is not None and len(node.args) > idx))
            if not routed:
                unrouted.append(f"{rel}:{node.lineno} {fn}()")

    assert not unrouted, (
        "store accessor(s) called with no destination on a --db-path path: "
        + ", ".join(unrouted)
        + " — this is the partial-routing shape that produced the ids-226-228 "
          "contamination and the batch cache-read defect")


def test_the_cache_read_and_the_cache_write_resolve_the_SAME_destination():
    """The defect was not a missing argument in the abstract — it was ASYMMETRY between
    two adjacent calls on one table. Pin the symmetry, not just the presence."""
    tree = ast.parse((_ROOT / "batch" / "runner.py").read_text(encoding="utf-8"))
    dests = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if fn not in ("get_cached_synthesis", "save_synthesis_cache"):
            continue
        expr = next((k.value for k in node.keywords if k.arg == "db_path"), None)
        if expr is None and len(node.args) > 2:
            expr = node.args[2]
        assert expr is not None, f"{fn} at line {node.lineno} names no destination"
        dests[fn] = ast.unparse(expr)

    assert set(dests) == {"get_cached_synthesis", "save_synthesis_cache"}, (
        f"expected one read and one write call site, found {sorted(dests)}")
    assert dests["get_cached_synthesis"] == dests["save_synthesis_cache"], (
        f"read routes to {dests['get_cached_synthesis']!r} but write routes to "
        f"{dests['save_synthesis_cache']!r} — an asymmetry here is the whole defect")
