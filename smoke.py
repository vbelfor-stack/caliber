"""
CALIBER v3 — smoke.py

Prints PASS/FAIL per subsystem. Exit 0 = all green. No live API calls.

Run from the caliber/ directory:
    python smoke.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

_FX = _ROOT / "tests" / "fixtures"
_WIDTH = 56
_results: list[tuple[str, str, str | None]] = []


def _check(name: str, fn) -> None:
    try:
        fn()
        _results.append((name, "PASS", None))
        print(f"  {name:<44} PASS")
    except Exception as exc:
        _results.append((name, "FAIL", str(exc)))
        print(f"  {name:<44} FAIL")
        print(f"    {exc}")


# ── 1. Store ──────────────────────────────────────────────────────────────────

def _chk_store() -> None:
    from store.models import (
        init_db, save_failed_evaluation, list_evaluations,
        save_grade, list_grades,
    )
    tmp = Path(tempfile.mkdtemp()) / "smoke.db"
    init_db(tmp)

    # save + retrieve a failed eval
    eid = save_failed_evaluation("SMKE", "smoke test sentinel", db_path=tmp)
    assert eid and eid > 0
    rows = list_evaluations(db_path=tmp)
    assert any(r["ticker"] == "SMKE" for r in rows)

    # insert a minimal ok eval row via raw SQL so save_grade has a FK target
    conn = sqlite3.connect(tmp)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.execute(
        """INSERT INTO evaluations
           (ticker, run_at, lens, status, pillars_json, synthesis_json,
            avg_score, overall_conf, verdict_conf, expected_return)
           VALUES ('SMKG','2025-01-01T00:00:00','standard','ok','[]',
                   '{"current_price":100}',3.5,'medium','medium',12.0)"""
    )
    conn.commit()
    eval_id = cur.lastrowid
    conn.close()

    gid = save_grade(
        evaluation_id=eval_id, ticker="SMKG", eval_date="2025-01-01",
        er_published=12.0, verdict_conf="medium",
        price_at_eval=100.0, price_at_90d=115.0,
        actual_return=15.0, grade="A", note="", db_path=tmp,
    )
    assert gid and gid > 0
    grades = list_grades(db_path=tmp)
    assert len(grades) == 1 and grades[0]["grade"] == "A"


# ── 2. Adapters (fixture) ─────────────────────────────────────────────────────

def _chk_adapters() -> None:
    from adapters.yfinance_adapter import fetch_yfinance
    from adapters.edgar_adapter import fetch_edgar
    from adapters.fred_adapter import fetch_fred

    yf = fetch_yfinance("MU", fixture_path=_FX / "yfinance" / "MU.json")
    assert yf.ticker == "MU"
    assert not yf.current_price.is_missing(), "MU current_price missing from fixture"

    ed = fetch_edgar("MU", fixture_path=_FX / "edgar" / "MU.json")
    assert ed.cik, "MU CIK missing from edgar fixture"
    assert str(ed.sic) == "3674", f"MU SIC expected 3674, got {ed.sic!r}"

    # FRED is optional — fixture captured without key; just verify load doesn't crash
    fr = fetch_fred(fixture_path=_FX / "fred" / "DGS10.json")
    assert isinstance(fr.rate_10y.confidence, str), "FRED returned unexpected type"


# ── 3. Cross-check ────────────────────────────────────────────────────────────

def _chk_cross_check() -> None:
    from adapters.base import Prov
    from core.cross_check import apply_cross_check

    primary = Prov(value=100.0, source="yfinance", as_of="2025-01-01", confidence="medium")

    # Agree within tolerance -> high
    upgraded = apply_cross_check(primary, 101.0, "AV", "2025-01-01")
    assert upgraded.confidence == "high", f"Expected high, got {upgraded.confidence}"

    # Conflict outside tolerance -> low
    downgraded = apply_cross_check(primary, 200.0, "AV", "2025-01-01")
    assert downgraded.confidence == "low", f"Expected low, got {downgraded.confidence}"


# ── 4. Lens selector ──────────────────────────────────────────────────────────

def _chk_lens() -> None:
    from core.lens_select import select_lens

    # SIC may be stored as int or str; lens_select handles both
    assert select_lens("Technology", "Semiconductors", "3674") == "cyclical" or \
           select_lens("Technology", "Semiconductors", 3674) == "cyclical", "MU must be cyclical"
    assert select_lens("Financial Services", "Credit Services", None) == "compounder", "V must be compounder"
    assert select_lens("Communication Services", "Internet Content & Information", None) == "compounder", \
        "GOOG must be compounder (not growth/standard)"


# ── 5. Pillars (fixture data, no network) ────────────────────────────────────

def _chk_pillars() -> None:
    from adapters.yfinance_adapter import fetch_yfinance
    from adapters.edgar_adapter import fetch_edgar
    from adapters.fred_adapter import fetch_fred
    from core.lens_select import select_lens
    from core.pillars import score_all

    yf = fetch_yfinance("MU", fixture_path=_FX / "yfinance" / "MU.json")
    ed = fetch_edgar("MU", fixture_path=_FX / "edgar" / "MU.json")
    fr = fetch_fred(fixture_path=_FX / "fred" / "DGS10.json")
    yf.sic = ed.sic

    lens = select_lens(yf.sector, yf.industry, ed.sic)
    assert lens == "cyclical", f"MU lens: expected cyclical, got {lens}"

    pillars = score_all(yf, ed, fr, lens)
    assert len(pillars) == 5, f"Expected 5 pillars, got {len(pillars)}"
    for p in pillars:
        assert 1 <= p.score <= 5, f"Pillar '{p.name}' score {p.score} out of range"
        assert p.confidence in ("high", "medium", "low"), f"Bad confidence: {p.confidence}"


# ── 6. Synthesis schema ───────────────────────────────────────────────────────

def _chk_synthesis_schema() -> None:
    from synthesis.schema import repair_json, parse_synthesis, compute_er
    from adapters.base import PillarResult, Prov

    _MISSING = Prov(value=None, source="?", as_of=None, confidence="low")

    # Valid JSON round-trips
    raw = json.dumps({
        "company": "Acme", "verdictReason": "solid",
        "verdictConfidence": "high",
        "scenarios": {
            "bull": {"thesis": "up", "points": [], "probability": 30, "priceTarget": 130},
            "base": {"thesis": "flat", "points": [], "probability": 50, "priceTarget": 110},
            "bear": {"thesis": "down", "points": [], "probability": 20, "priceTarget": 90},
        },
        "redFlags": [], "research": [], "technicals": {"trend": "up"},
        "dataGaps": [], "expectedReturn": None,
    })
    data = repair_json(raw)
    assert data["company"] == "Acme"

    # Markdown fence stripping
    fenced = f"```json\n{raw}\n```"
    data2 = repair_json(fenced)
    assert data2["company"] == "Acme"

    # Thousands separator fix
    ts_raw = '{"company":"X","verdictConfidence":"medium","verdictReason":"ok",' \
             '"scenarios":{"bull":{"thesis":"up","points":[],"probability":30,' \
             '"priceTarget":1234},"base":{"thesis":"flat","points":[],' \
             '"probability":50,"priceTarget":1100},"bear":{"thesis":"dn",' \
             '"points":[],"probability":20,"priceTarget":900}},' \
             '"redFlags":[],"research":[],"technicals":{"trend":"up"},' \
             '"dataGaps":[],"expectedReturn":null}'
    ts_fixed = repair_json(ts_raw.replace("1234", "1,234"))
    assert ts_fixed["scenarios"]["bull"]["priceTarget"] == 1234

    # Anti-launder: low-conf pillar forces verdict to low even if LLM says high
    low_pillar = PillarResult(
        name="Financials", score=2, confidence="low",
        rationale="weak", flags=[], method="standard", key_inputs=[],
    )
    result = parse_synthesis(raw, pillars=[low_pillar], ticker="ACME")
    assert result.verdictConfidence == "low", \
        f"Anti-launder failed: expected low, got {result.verdictConfidence}"

    # compute_er with known targets
    med_pillar = PillarResult(
        name="Financials", score=3, confidence="medium",
        rationale="ok", flags=[], method="standard", key_inputs=[],
    )
    ok_result = parse_synthesis(raw, pillars=[med_pillar], ticker="ACME")
    er = compute_er(ok_result, current_price=100.0)
    assert er is not None
    # bull=30@130, base=50@110, bear=20@90 -> E(R) = (30*30 + 50*10 + 20*-10)/100 = (900+500-200)/100 = 12
    assert abs(er - 12.0) < 0.01, f"compute_er={er:.2f}, expected 12.0"


# ── 7. Grading ────────────────────────────────────────────────────────────────

def _chk_grading() -> None:
    from core.grading import assign_grade, grade_evaluation
    from store.models import init_db, list_grades

    # Rubric spot-checks
    assert assign_grade(10.0, 10.0) == "A"
    assert assign_grade(20.0, 5.0) == "B"
    assert assign_grade(20.0, 2.0) == "C"
    assert assign_grade(10.0, -5.0) == "D"
    assert assign_grade(10.0, -20.0) == "F"
    assert assign_grade(None, 10.0) == "N/A"

    # grade_evaluation with synthetic DB + injected price (no live call)
    tmp = Path(tempfile.mkdtemp()) / "grade.db"
    init_db(tmp)
    conn = sqlite3.connect(tmp)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.execute(
        """INSERT INTO evaluations
           (ticker, run_at, lens, status, pillars_json, synthesis_json,
            avg_score, overall_conf, verdict_conf, expected_return)
           VALUES ('TST','2025-01-01T00:00:00','standard','ok','[]',
                   '{"current_price":100.0}',3.5,'medium','high',15.0)"""
    )
    conn.commit()
    eval_id = cur.lastrowid
    conn.close()

    row = {"id": eval_id, "ticker": "TST", "run_at": "2025-01-01T00:00:00",
           "expected_return": 15.0, "verdict_conf": "high",
           "synthesis_json": json.dumps({"current_price": 100.0})}

    # F grade with high conf -> anti-launder note
    result = grade_evaluation(row, price_at_90d=78.0, db_path=tmp)
    assert result["grade"] == "F", f"Expected F, got {result['grade']}"
    assert "ANTI-LAUNDER" in result["note"], "Anti-launder note missing on high-conf F"

    grades = list_grades(db_path=tmp)
    assert len(grades) == 1 and grades[0]["grade"] == "F"


# ── 8. Web routes ─────────────────────────────────────────────────────────────

def _chk_web() -> None:
    import importlib
    web_app = importlib.import_module("web.app")

    app = web_app.app
    paths = {r.path for r in app.routes}

    required = {"/library", "/compare", "/batch", "/grading", "/login", "/logout"}
    missing = required - paths
    assert not missing, f"Missing routes: {missing}"

    # Deep view uses a path parameter
    has_deep = any("/eval/{" in (getattr(r, "path", "") or "") for r in app.routes)
    assert has_deep, "Missing /eval/{eval_id} route"


# ── 9. Security ───────────────────────────────────────────────────────────────

def _chk_security() -> None:
    # .env must be in .gitignore
    gitignore = _ROOT / ".gitignore"
    assert gitignore.exists(), ".gitignore not found"
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    assert any(l.strip() == ".env" for l in lines), ".env not in .gitignore"

    # ANTHROPIC_API_KEY must never be echoed in synthesis/client.py
    client_src = (_ROOT / "synthesis" / "client.py").read_text(encoding="utf-8")
    bad_patterns = ["print(api_key", "print(ANTHROPIC_API_KEY", 'log("ANTHROPIC']
    for pat in bad_patterns:
        assert pat not in client_src, f"Potential key leak in synthesis/client.py: {pat!r}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * _WIDTH)
    print("  CALIBER v3 — smoke test")
    print("=" * _WIDTH)

    _check("1/9  Store: init / save / list / grades", _chk_store)
    _check("2/9  Adapters: fixture load (yfinance/edgar/fred)", _chk_adapters)
    _check("3/9  Cross-check: agree->high / conflict->low", _chk_cross_check)
    _check("4/9  Lens selector: MU cyclical / V compounder / GOOG compounder", _chk_lens)
    _check("5/9  Pillars: score_all on MU fixture (no network)", _chk_pillars)
    _check("6/9  Synthesis schema: repair / anti-launder / compute_er", _chk_synthesis_schema)
    _check("7/9  Grading: rubric + grade_evaluation anti-launder", _chk_grading)
    _check("8/9  Web: routes registered (/library /compare /batch /grading)", _chk_web)
    _check("9/9  Security: .env gitignored / key not echoed", _chk_security)

    total = len(_results)
    passed = sum(1 for _, s, _ in _results if s == "PASS")
    failed = total - passed

    print("=" * _WIDTH)
    if failed == 0:
        print(f"  All {total} checks PASSED.")
    else:
        print(f"  {passed}/{total} passed — {failed} FAILED:")
        for name, status, err in _results:
            if status == "FAIL":
                print(f"    FAIL  {name}")
                if err:
                    for line in str(err).splitlines()[:4]:
                        print(f"           {line}")
    print("=" * _WIDTH)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
