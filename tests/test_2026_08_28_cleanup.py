"""Cleanup session, 2026-08-28 — Vic rulings 1-6.

Pins for: the zero-vs-absent typed reason (ruling 1), the ETF guard (ruling 2), the
provenance relabel being ALREADY DONE (ruling 3), the dead surfaces being ALREADY GONE
(ruling 4), the BANK-RUNG-UNCALIBRATED successor condition (ruling 5), and the doctrine
sanity-gate amendment (ruling 6).
"""
from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


# ══════════════════════════════════════════════════════════════════════════════
# RULING 1 — zero revenue is a VALUE, not an absence. The drop stays; the LABEL changes.
# ══════════════════════════════════════════════════════════════════════════════

class TestZeroRevenueIsNotAbsence:

    def test_a_filed_zero_revenue_reports_revenue_zero_not_no_revenue(self):
        """The feed-repair ticket said "IONQ missing FY2020". It was never missing: FMP
        serves it with `revenue: 0` and WE dropped it while claiming the issuer filed
        nothing. Same mislabel class as WITHHELD_NO_CAPEX, which L-4d deleted."""
        from core.lifecycle import _revenue_on_basis
        rev, reason = _revenue_on_basis({"revenue": 0}, "growth")
        assert rev is None, "a zero revenue is still DROPPED — the guard is unchanged"
        assert reason == "revenue_zero"

    def test_a_genuinely_absent_revenue_still_reports_no_revenue(self):
        """The two causes must stay distinguishable in BOTH directions, or the split is
        decorative. A sweep that cannot tell them apart proves nothing."""
        from core.lifecycle import _revenue_on_basis
        for row in ({}, {"revenue": None}, {"revenue": "not-a-number"}):
            rev, reason = _revenue_on_basis(row, "growth")
            assert rev is None
            assert reason == "no_revenue", row

    def test_the_DROP_BEHAVIOUR_is_unchanged_by_the_relabel(self):
        """★ THE POINT OF THE PIN. Ruling 1 authorised a feed repair, not a scoring change.
        A zero row must still be excluded from the classifier's series."""
        from core.lifecycle import _fy_series
        rows = [{"date": "2021-12-31", "revenue": 100, "operatingIncome": -10},
                {"date": "2020-12-31", "revenue": 0, "operatingIncome": -5},
                {"date": "2019-12-31", "revenue": 50, "operatingIncome": -5}]
        series, refused = _fy_series(rows, "growth")
        assert [s[0][:4] for s in series] == ["2019", "2021"], "the zero row is still dropped"
        assert refused == ["2020:revenue_zero"]

    def test_admitting_zeros_is_NOT_safe_and_the_guard_is_load_bearing(self):
        """★★ THE MEASURED REASON THE DROP SURVIVED THE RULING, kept as a permanent record.

        Dark-run over the universe on 2026-08-28: exactly two names carry a zero-revenue
        FY. IONQ's is interior (FY2020) and moves nothing. INFQ's are its two MOST RECENT
        fiscal years, and admitting them flips it
        `YOUNG/rule2_young_insufficient_history -> MATURE/rule4_mature`.

        That is the "a zero revenue would manufacture a 100% decline" hazard the guard was
        written for, firing on a live name. This test pins the ARITHMETIC of that hazard so
        the reasoning cannot be lost: a series ending in zeros reads as a total collapse."""
        from core.lifecycle import _fy_series
        rows = [{"date": "2025-12-31", "revenue": 0}, {"date": "2024-12-31", "revenue": 0},
                {"date": "2023-12-31", "revenue": 900}]
        series, refused = _fy_series(rows, "growth")
        assert [s[0][:4] for s in series] == ["2023"], \
            "the two most recent FY are dropped, leaving one usable year"
        assert refused == ["2025:revenue_zero", "2024:revenue_zero"]
        # Had they been admitted, the latest FY would read 0 against a prior 900 — a 100%
        # decline manufactured entirely out of a placeholder-shaped value.


# ══════════════════════════════════════════════════════════════════════════════
# RULING 2 — the ETF guard
# ══════════════════════════════════════════════════════════════════════════════

class TestEtfGuard:

    def _yf(self, is_etf, name="Some Fund"):
        class _F:
            pass
        f = _F()
        f.is_etf = is_etf
        f.name = name
        f.ticker = "XXXX"
        return f

    def test_a_true_isEtf_refuses_with_a_typed_reason(self):
        from core.etf_guard import ETF_TYPED_REASON, etf_refusal
        r = etf_refusal(self._yf(True))
        assert r.refused is True
        assert r.typed_reason == ETF_TYPED_REASON == "etf:not_a_company"
        assert r.detail

    def test_a_false_isEtf_proceeds(self):
        from core.etf_guard import etf_refusal
        assert etf_refusal(self._yf(False)).refused is False

    def test_UNKNOWN_does_not_refuse_and_that_is_deliberate(self):
        """A departure from fail-closed, ruled and stated. Refusing on absence would refuse
        every recorded fixture (they predate the field) and every live name the moment FMP
        drops the key. Vic's ruling is "any TRUE value refuses"; absence is not true."""
        from core.etf_guard import etf_refusal
        assert etf_refusal(self._yf(None)).refused is False

    @pytest.mark.parametrize("raw,expected", [
        (True, True), (False, False),
        ("true", True), ("TRUE", True), ("True", True),
        ("false", False), ("False", False), ("FALSE", False),
        (1, True), (0, False), ("1", True), ("0", False),
        (None, None), ("maybe", None), (2, None), ([], None),
    ])
    def test_isEtf_is_PARSED_never_taken_as_python_truthiness(self, raw, expected):
        """★ `bool("false")` is True. A guard that used truthiness would refuse every name
        whose feed serves the STRING "false" — i.e. it would refuse the whole universe while
        looking like it was working."""
        from core.etf_guard import parse_is_etf
        assert parse_is_etf(raw) is expected

    def test_the_guard_owns_no_taxonomy_no_name_or_ticker_matching(self):
        """It reads `is_etf` and nothing else. A name-substring rule would catch "Trust" in
        a REIT and "Fund" in an operating company — the `_CYCLICAL_INDUSTRY` keyword-sweep
        defect that put IONQ and INFQ on the wrong lens. Checked over the AST so the module's
        own prose explaining the prohibition cannot trip it."""
        src = (ROOT / "core" / "etf_guard.py").read_text()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "etf_refusal")
        attrs = {n.args[1].value for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "getattr"
                 and len(n.args) > 1 and isinstance(n.args[1], ast.Constant)}
        assert "is_etf" in attrs
        assert not {"sector", "industry", "exchange"} & attrs, \
            "the guard must not reach for a taxonomy field"

    def test_the_refusal_sits_ABOVE_lens_selection_on_BOTH_paths(self):
        """★ THE ORDERING IS THE RULING. A fund carries a sector and an industry like
        anything else, so `select_lens` will route one to a company lens and everything
        downstream looks well-formed. Pinned by line index on both write paths."""
        for mod in ("evaluate.py", "batch/runner.py"):
            src = (ROOT / mod).read_text()
            assert src.index("_etf = etf_refusal") < src.index("lens = select_lens"), mod

    def test_the_refusal_sits_ABOVE_the_EDGAR_FETCH_on_BOTH_paths(self):
        """★★ THE PIN THE ACCEPTANCE RUN BOUGHT. Vic ruled the guard above `fetch_edgar`
        on 2026-08-28 after an end-to-end control showed it was UNREACHABLE for every real
        fund.

        `fetch_edgar` is a HARD GATE (exit 1 interactively; a `failed` row per ticker in
        batch), and an ETF has NO ticker-level SEC CIK — funds file under their trust's
        CIK. So LYTE and FLTW were refused with "Ticker not found in SEC tickers.json" and
        never reached the guard built for them: measured, both exited 1 rather than 7.

        THE OUTCOME WAS SAFE AND THE REASON WAS WRONG, which is the whole defect class this
        project keeps killing. It also meant the first line of defence was ACCIDENTAL — it
        rested on funds happening to lack a CIK, not on the guard. A fund whose CIK did
        resolve would have gone straight past it.

        `etf_refusal` reads only `yf`, so it has no reason to wait behind a network call it
        does not use. Pinned by line index on both paths so it cannot drift back down."""
        for mod in ("evaluate.py", "batch/runner.py"):
            src = (ROOT / mod).read_text()
            assert src.index("_etf = etf_refusal") < src.index("edgar = fetch_edgar"), (
                f"{mod}: the ETF guard has fallen back below the EDGAR hard gate — every "
                f"real fund will be refused with the WRONG typed reason again")

    def test_the_refusal_still_sits_BELOW_the_fmp_fetch_it_depends_on(self):
        """The guard reads `yf`. Moving it above the fetch that produces `yf` would be a
        NameError on the refusal path — the one path that must never crash."""
        for mod, fetch in (("evaluate.py", "yf = fetch_fmp"),
                           ("batch/runner.py", "yf = _fetch")):
            src = (ROOT / mod).read_text()
            assert src.index(fetch) < src.index("_etf = etf_refusal"), mod

    def test_the_batch_refusal_sits_ABOVE_the_dark_series_WRITER(self):
        """"Nothing numeric" is not satisfied by declining to score if a writer already ran.
        Same clause that makes the financials gate's position load-bearing."""
        src = (ROOT / "batch" / "runner.py").read_text()
        assert src.index("_etf = etf_refusal") < src.index("run_dark_fcf_series(yf")

    def test_the_interactive_refusal_exits_7_not_1(self):
        """A policy refusal filed as a crash is the conflation D-2 removed. 7 is distinct
        from crash(1), rate(3), financials(5) and the stage-flip halt(6)."""
        src = (ROOT / "evaluate.py").read_text()
        # Slice the REFUSAL BLOCK ITSELF, not "everything up to lens selection". The guard
        # was moved above `fetch_edgar` on 2026-08-28, so the old wider slice now contains
        # the EDGAR hard gate's own `sys.exit(1)` — which belongs to a different refusal.
        # A pin whose boundary is "the next unrelated landmark" breaks whenever code moves
        # between them and says nothing about the thing it was written to protect.
        block = src.split("_etf = etf_refusal", 1)[1].split("[2/3] Fetching EDGAR", 1)[0]
        assert "sys.exit(7)" in block
        for taken in ("sys.exit(1)", "sys.exit(3)", "sys.exit(5)", "sys.exit(6)"):
            assert taken not in block, f"{taken} would conflate the ETF refusal"

    def test_the_adapter_populates_is_etf_from_the_profile(self):
        src = (ROOT / "adapters" / "fmp_adapter.py").read_text()
        assert 'is_etf=parse_is_etf(profile.get("isEtf"))' in src


# ══════════════════════════════════════════════════════════════════════════════
# RULING 3 — the provenance relabel was ALREADY DONE. Pin it so it cannot regress.
# ══════════════════════════════════════════════════════════════════════════════

class TestProvenanceNamesTheRealFeed:

    def test_technicals_takes_its_source_from_the_caller_never_a_literal(self):
        """`analyze_technicals` must not hardcode a feed name. Both call sites pass
        `yf.feed_source`, so the stamp follows the feed that actually supplied the rows."""
        src = (ROOT / "core" / "technicals.py").read_text()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "analyze_technicals")
        assert any(a.arg == "feed_source" for a in fn.args.args)
        lits = [n.value for n in ast.walk(fn)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        assert not any("yfinance" in v.lower() for v in lits)

    def test_both_call_sites_thread_the_real_feed_source(self):
        for mod in ("evaluate.py", "batch/runner.py"):
            src = (ROOT / mod).read_text()
            assert "analyze_technicals(yf.price_history, feed_source=yf.feed_source)" in src, mod

    def test_no_live_code_STAMPS_yfinance_docstrings_excepted(self):
        """★ AST, NOT TEXT, AND THE EXEMPTION IS THE WHOLE POINT. These modules document the
        yfinance teardown and the ratio-vs-percent D/E unit defect at length. A text scan
        fires on the prose explaining the history and would push a later session to DELETE
        the record of a production defect. Only non-docstring string literals count."""
        offenders = []
        for f in sorted(ROOT.rglob("*.py")):
            s = str(f)
            if ".pythonlibs" in s or "/tests/" in s or f.name.startswith("test_"):
                continue
            try:
                tree = ast.parse(f.read_text())
            except SyntaxError:
                continue
            docs = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                    d = ast.get_docstring(node, clean=False)
                    if d:
                        docs.add(d)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and "yfinance" in node.value.lower()
                        and node.value not in docs):
                    offenders.append(f"{f.relative_to(ROOT)}:{node.lineno}")
        assert not offenders, f"live yfinance provenance strings reappeared: {offenders}"


# ══════════════════════════════════════════════════════════════════════════════
# RULING 4 — the dead surfaces are already gone; the operator guidance was the residue
# ══════════════════════════════════════════════════════════════════════════════

class TestDeadSurfaces:

    def test_probe_and_probe_fmp_do_not_exist(self):
        for name in ("probe.py", "probe_fmp.py", "tools/probe_fmp.py", "tools/probe.py"):
            assert not (ROOT / name).exists(), name

    def test_no_error_message_tells_the_operator_to_run_a_deleted_tool(self):
        """★ THE ONLY REAL RESIDUE RULING 4 HAD LEFT TO FIX. `edgar_adapter` told the
        operator to "Run probe.py first" — guidance pointing at a file deleted a phase
        earlier, which costs whoever follows it a debugging session."""
        src = (ROOT / "adapters" / "edgar_adapter.py").read_text()
        assert "Run probe.py first" not in src
        assert "tools.record_edgar_fixture" in src


# ══════════════════════════════════════════════════════════════════════════════
# RULING 5 — the successor condition. This is the enforcement point of the retirement.
# ══════════════════════════════════════════════════════════════════════════════

class TestBankRungTripwireRetirement:

    def test_the_BANK_RUNG_tripwire_REARMS_if_the_financials_leg_ships(self):
        """★★ THE SUCCESSOR CONDITION FOR THE RETIRED `BANK-RUNG-UNCALIBRATED` TRIPWIRE.

        The tripwire was retired for ONE reason: the financials gate refuses BK/C/JPM/USB
        before any pillar is scored, and those four are the entire bank-lens population, so
        the flag is structurally unreachable in production.

        THIS TEST FAILS THE MOMENT THAT STOPS BEING TRUE. If a financials leg ever ships and
        any of the four becomes evaluable, the uncalibrated cheap rungs (5 and 4) are
        reachable again and the calibration question is live again. A retirement whose
        premise can quietly expire is exactly the kind a later session weakens instead of
        heeding, so the premise is asserted rather than believed.

        Membership is recomputed live through the real classifier — never hardcoded."""
        from core.datatypes import Prov
        from core.model_applicability import fcf_model_applicability
        still_gated = []
        for tkr, sector, industry in (
                ("JPM", "Financial Services", "Banks - Diversified"),
                ("BK", "Financial Services", "Banks - Diversified"),
                ("USB", "Financial Services", "Banks - Regional"),
                ("C", "Financial Services", "Banks - Diversified")):
            app = fcf_model_applicability(sector, industry)
            still_gated.append((tkr, app.applicable))
        assert all(not applicable for _, applicable in still_gated), (
            "A BANK-LENS NAME IS EVALUABLE AGAIN. The BANK-RUNG-UNCALIBRATED tripwire was "
            "retired ONLY because its population was empty. That premise has expired: "
            f"{still_gated}. Re-arm the tripwire or re-rule the retirement — do not delete "
            "this test.")

    def test_the_production_flag_is_NOT_deleted(self):
        """Retiring a tripwire retires its STANDING, not the code. Deleting the flag would
        be unwinding a demoted path, which needs its own ruling."""
        src = (ROOT / "core" / "pillars.py").read_text()
        assert 'flags.append("BANK-RUNG-UNCALIBRATED")' in src

    def test_the_retirement_names_its_successor_where_the_pin_lives(self):
        """A retirement that does not name its handoff is a deletion with a comment."""
        src = (ROOT / "tests" / "test_d3_dark_lenses.py").read_text()
        assert "RETIRED BY NAME" in src
        assert "test_the_BANK_RUNG_tripwire_REARMS_if_the_financials_leg_ships" in src


# ══════════════════════════════════════════════════════════════════════════════
# RULING 6 — the doctrine amendment
# ══════════════════════════════════════════════════════════════════════════════

class TestDoctrineSanityGateAmendment:

    def test_the_doctrine_no_longer_names_a_second_unreachable_trigger(self):
        """§1.2(a) used to read "fails a sanity gate OR diverges >25%", naming two triggers
        where only one existed. The "or" is struck: the sanity gate IS the 25% check."""
        doc = (ROOT / "CLAUDE.md").read_text()
        assert "sanity gate or diverges" not in doc
        assert "NO SANITY\nGATE EXISTS" not in doc

    def test_the_amendment_forbids_building_new_machinery(self):
        doc = (ROOT / "CLAUDE.md").read_text()
        assert 'DO NOT "IMPLEMENT THE SANITY GATE"' in doc
