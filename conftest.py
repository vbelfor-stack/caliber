"""Global pytest configuration for CALIBER.

Test-isolation guard (R-1): historically, fixture-mode tests that called
run_single_ticker / run_batch / save_evaluation without an explicit db_path
wrote straight into the production caliber.db, because `db_path: Path =
_DEFAULT_DB` binds the real path at import time. This autouse fixture redirects
that default to a per-test temp DB so NOTHING in the suite can touch production
data — regardless of whether a given test remembers to pass db_path.

Mechanism: `db_path=_DEFAULT_DB` stores the *same* Path object (by identity) in
each function's __defaults__. We scan the DB-owning modules, and for every
default that IS that object, rebind it to the temp path. monkeypatch restores
everything after the test. Self-maintaining: new functions with the same default
are covered automatically, no hardcoded list.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable (mirrors the sys.path dance in test files).
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import store.models as _models       # noqa: E402
import core.grading as _grading      # noqa: E402

# Modules whose functions carry a `db_path=_DEFAULT_DB` default.
_DB_MODULES = (_models, _grading)


@pytest.fixture(autouse=True)
def _isolate_default_db(tmp_path, monkeypatch):
    """Point the default caliber.db at a per-test temp file for every test."""
    real = _models._DEFAULT_DB
    test_db = tmp_path / "test_caliber.db"

    monkeypatch.setattr(_models, "_DEFAULT_DB", test_db, raising=False)

    for module in _DB_MODULES:
        for _name, fn in list(vars(module).items()):
            if not inspect.isfunction(fn) or not fn.__defaults__:
                continue
            rebound = tuple(test_db if d is real else d for d in fn.__defaults__)
            if rebound != fn.__defaults__:
                monkeypatch.setattr(fn, "__defaults__", rebound)

    yield
