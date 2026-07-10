"""
Phase 3 batch runner + scheduler tests.
All tests use fixture mode — no live network calls.
Isolation guarantee: one failing ticker must not abort others.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from batch.runner import run_batch, run_single_ticker, read_universe, TickerResult
from batch.scheduler import dry_run


FIXTURE_TICKERS = ["MU", "GOOG", "V"]   # fixtures exist for these three


# ── Universe file ─────────────────────────────────────────────────────────────

class TestReadUniverse:
    def test_reads_tickers(self, tmp_path):
        f = tmp_path / "tickers.txt"
        f.write_text("MU\nGOOG\n# comment\n\nV\n")
        tickers = read_universe(f)
        assert tickers == ["MU", "GOOG", "V"]

    def test_strips_comments_and_blanks(self, tmp_path):
        f = tmp_path / "tickers.txt"
        f.write_text("# header\nMU  # inline comment\n\n  GOOG\n")
        tickers = read_universe(f)
        assert tickers == ["MU", "GOOG"]

    def test_uppercases(self, tmp_path):
        f = tmp_path / "tickers.txt"
        f.write_text("mu\ngoog\n")
        tickers = read_universe(f)
        assert tickers == ["MU", "GOOG"]

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            read_universe(Path("nonexistent_universe.txt"))


# ── Single ticker isolation ───────────────────────────────────────────────────

class TestRunSingleTicker:
    def test_mu_fixture_mode_succeeds(self):
        result = run_single_ticker("MU", fixture_mode=True, run_synthesis=False, verbose=False)
        assert isinstance(result, TickerResult)
        assert result.status == "ok"
        assert result.eval_id is not None
        assert result.avg_score is not None
        assert 1.0 <= result.avg_score <= 5.0
        assert result.lens is not None

    def test_goog_fixture_mode_succeeds(self):
        result = run_single_ticker("GOOG", fixture_mode=True, run_synthesis=False, verbose=False)
        assert result.status == "ok"
        assert result.avg_score is not None
        assert result.lens == "compounder", f"GOOG must be compounder, got {result.lens}"

    def test_v_fixture_mode_succeeds(self):
        result = run_single_ticker("V", fixture_mode=True, run_synthesis=False, verbose=False)
        assert result.status == "ok"
        assert result.lens == "compounder"  # golden-ticker: V must be compounder

    def test_bad_ticker_returns_failed_not_raises(self):
        """Core isolation guarantee: a bad ticker must NOT raise — status='failed'."""
        result = run_single_ticker(
            "XXXXNOTREAL9999", fixture_mode=False, run_synthesis=False, verbose=False
        )
        assert result.status == "failed"
        assert result.error is not None
        assert result.eval_id is not None   # stored as failed-with-diagnosis

    def test_failed_ticker_has_eval_id(self):
        """Failures must be persisted to the store so they're auditable."""
        result = run_single_ticker(
            "BADFIXTURE999", fixture_mode=True, run_synthesis=False, verbose=False
        )
        assert result.status == "failed"
        assert result.eval_id is not None

    def test_duration_recorded(self):
        result = run_single_ticker("MU", fixture_mode=True, run_synthesis=False, verbose=False)
        assert result.duration_s >= 0.0

    def test_mu_lens_is_cyclical(self):
        result = run_single_ticker("MU", fixture_mode=True, run_synthesis=False, verbose=False)
        assert result.lens == "cyclical"


# ── Batch isolation ───────────────────────────────────────────────────────────

class TestRunBatch:
    def test_all_fixture_tickers_complete(self, capsys):
        results = run_batch(
            FIXTURE_TICKERS, fixture_mode=True, run_synthesis=False, verbose=False
        )
        assert len(results) == 3
        statuses = [r.status for r in results]
        assert all(s == "ok" for s in statuses), f"Some failed: {statuses}"

    def test_one_bad_ticker_does_not_abort_batch(self, capsys):
        """Core isolation: BADFIXTURE fails, but MU and GOOG still complete."""
        tickers = ["MU", "BADFIXTURE9999", "GOOG"]
        results = run_batch(tickers, fixture_mode=True, run_synthesis=False, verbose=False)
        assert len(results) == 3

        mu = next(r for r in results if r.ticker == "MU")
        bad = next(r for r in results if r.ticker == "BADFIXTURE9999")
        goog = next(r for r in results if r.ticker == "GOOG")

        assert mu.status == "ok", "MU must succeed despite bad ticker in batch"
        assert goog.status == "ok", "GOOG must succeed despite bad ticker in batch"
        assert bad.status == "failed", "Bad ticker must be failed, not raise"
        assert bad.eval_id is not None, "Failed ticker must persist to store"

    def test_results_in_input_order(self, capsys):
        tickers = ["V", "MU", "GOOG"]
        results = run_batch(tickers, fixture_mode=True, run_synthesis=False, verbose=False)
        assert [r.ticker for r in results] == tickers

    def test_all_eval_ids_distinct(self, capsys):
        results = run_batch(
            FIXTURE_TICKERS, fixture_mode=True, run_synthesis=False, verbose=False
        )
        ids = [r.eval_id for r in results if r.eval_id is not None]
        assert len(ids) == len(set(ids)), "eval_ids must be distinct"

    def test_empty_ticker_list_returns_empty(self, capsys):
        results = run_batch([], fixture_mode=True, run_synthesis=False, verbose=False)
        assert results == []


# ── Scheduler dry-run ─────────────────────────────────────────────────────────

class TestSchedulerDryRun:
    def test_dry_run_returns_tickers(self, tmp_path):
        f = tmp_path / "tickers.txt"
        f.write_text("MU\nGOOG\nV\n")
        tickers = dry_run(f, verbose=False)
        assert tickers == ["MU", "GOOG", "V"]

    def test_dry_run_makes_no_api_calls(self, tmp_path, monkeypatch):
        """dry_run must not touch any live adapter."""
        import adapters.yfinance_adapter as yf_mod
        called = []
        monkeypatch.setattr(yf_mod, "fetch_yfinance", lambda *a, **kw: called.append(1))
        f = tmp_path / "tickers.txt"
        f.write_text("MU\n")
        dry_run(f, verbose=False)
        assert called == [], "dry_run must not call fetch_yfinance"

    def test_dry_run_logs_all_tickers(self, tmp_path, capsys):
        f = tmp_path / "tickers.txt"
        f.write_text("MU\nGOOG\nV\n")
        dry_run(f, verbose=True)
        out = capsys.readouterr().out
        for ticker in ["MU", "GOOG", "V"]:
            assert ticker in out

    def test_dry_run_mentions_isolation(self, tmp_path, capsys):
        f = tmp_path / "tickers.txt"
        f.write_text("MU\n")
        dry_run(f, verbose=True)
        out = capsys.readouterr().out
        assert "isolation" in out.lower() or "failed-with-diagnosis" in out


# ── Store persistence checks ──────────────────────────────────────────────────

class TestBatchStorePersistence:
    def test_ok_runs_appear_in_store(self):
        from store.models import list_evaluations
        results = run_batch(["MU"], fixture_mode=True, run_synthesis=False, verbose=False)
        assert results[0].status == "ok"
        rows = list_evaluations("MU")
        assert any(r["id"] == results[0].eval_id for r in rows)

    def test_failed_runs_appear_in_store_with_status_failed(self):
        from store.models import get_evaluation
        result = run_single_ticker(
            "BADFAIL888", fixture_mode=True, run_synthesis=False, verbose=False
        )
        assert result.status == "failed"
        row = get_evaluation(result.eval_id)
        assert row is not None
        assert row["status"] == "failed"
        assert row["error_msg"] is not None
