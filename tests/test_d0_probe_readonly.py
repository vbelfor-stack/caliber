"""
The D-0 probe must be structurally incapable of writing to caliber.db.

A flag would not be enough: batch/runner.py imports save_evaluation at module scope and
calls it unconditionally (runner.py:224), so any convenience import from batch.runner
would hand the probe a live write path regardless of how it is invoked. These tests
assert the IMPORT CLOSURE, so that mistake fails here instead of silently persisting
rows during a measurement pass.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "tools" / "probe_valuation_panel.py"
PROBES = {
    "tools.probe_valuation_panel": REPO / "tools" / "probe_valuation_panel.py",
    "tools.probe_d3_lenses": REPO / "tools" / "probe_d3_lenses.py",   # D-3, same rule
}
PERSISTENCE_MODULES = ("store.models", "store", "batch.runner", "batch")


def test_probe_import_closure_reaches_no_persistence_module():
    """Import the probe in a clean interpreter; no writer may come along with it.

    This is the load-bearing check — it catches a writer arriving TRANSITIVELY, through
    a module the probe imports rather than one it names.
    """
    code = (
        "import importlib, sys, json\n"
        "importlib.import_module('tools.probe_valuation_panel')\n"
        f"print(json.dumps([m for m in {PERSISTENCE_MODULES!r} if m in sys.modules]))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    leaked = proc.stdout.strip().splitlines()[-1]
    assert leaked == "[]", (
        f"D-0 probe pulled persistence module(s) into its import closure: {leaked}. "
        "The probe must reach the adapters directly, never through batch.runner."
    )


def test_probe_imports_no_persistence_module_by_name():
    """The same rule read off the AST, so the violation is pinned to a source line.

    Parsed rather than grepped: the module docstring has to be free to EXPLAIN why
    save_evaluation is avoided without tripping its own guard.
    """
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{a.name}" for a in node.names)
    offenders = {m for m in imported
                 if m.split(".")[0] in ("store", "batch") or "save_evaluation" in m}
    assert not offenders, f"probe imports a persistence path: {sorted(offenders)}"


def test_probe_calls_no_writer():
    """No call to a persistence function, however it might have been bound."""
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    called = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not {"save_evaluation", "save_failed_evaluation", "save_grade",
                "save_synthesis_cache", "init_db"} & called


def test_probe_reports_a_failed_ticker_loudly_and_exits_nonzero(monkeypatch, capsys):
    """A dead ticker is named and the run exits 1 — never a silent partial pass.

    Faked at the adapter seam rather than by breaking the environment: the contract
    under test is the probe's own error handling, not requests' behaviour offline.
    """
    from adapters.base import Prov
    from adapters.fred_adapter import FredData
    import tools.probe_valuation_panel as probe

    monkeypatch.setattr(probe, "fetch_fred",
                        lambda *a, **k: FredData(
                            rate_10y=Prov(4.69, "FRED", "2026-08-08", "high")))
    monkeypatch.setattr(probe, "fetch_fmp",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no feed")))
    monkeypatch.setattr(sys, "argv", ["probe", "ZZZZ"])

    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "FAILED ZZZZ" in out and "RuntimeError: no feed" in out


# ── D-3 probe: the same structural guarantee, same reasons ───────────────────
# The D-3 probe scores every ticker on every lens live. It reaches core.pillars (the
# real scorer) as well as the adapters, which is a wider import surface than D-0's —
# so the closure check matters MORE here, not less.

@pytest.mark.parametrize("module,path", sorted(PROBES.items()))
def test_every_probe_import_closure_is_write_free(module, path):
    code = (
        "import importlib, sys, json\n"
        f"importlib.import_module({module!r})\n"
        f"print(json.dumps([m for m in {PERSISTENCE_MODULES!r} if m in sys.modules]))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    leaked = proc.stdout.strip().splitlines()[-1]
    assert leaked == "[]", (
        f"{module} pulled persistence module(s) into its import closure: {leaked}"
    )


@pytest.mark.parametrize("module,path", sorted(PROBES.items()))
def test_every_probe_names_no_persistence_module(module, path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{a.name}" for a in node.names)
    offenders = {m for m in imported
                 if m.split(".")[0] in ("store", "batch") or "save_evaluation" in m}
    assert not offenders, f"{module} imports persistence: {sorted(offenders)}"
