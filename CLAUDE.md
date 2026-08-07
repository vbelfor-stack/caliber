# CLAUDE.md — CALIBER (operational context; auto-loads every session)
# Detailed build spec lives in Claude.md (Jul 10). This file is the living operational memory.

## How we work (relay / architect model)
- Vic is architect and gatekeeper; Code executes work orders. Report as you go, in plain English.
- STOP and ask before: changing grading/scoring logic, restructuring working code, deleting or
  overwriting data, or any change beyond what the order specifies.
- Never add duplicate logic. If existing behavior already satisfies the order, leave it and say so.
- Manual mode (per-action approval) is the default.

## Core disciplines (non-negotiable)
- LOUD FAILURE BEATS SILENT DEGRADATION. Failures raise a typed signal — never swallowed,
  never masked as success. (yfinance fallback was removed for this reason.)
- Hard stops — must raise typed signals, never pass silently:
  - anchor_price divergence
  - PE basis computed on negative forward EPS  (LCID is the negative-forward-PE test fixture)
- status='ok' must mean a COMPLETE eval (see open thread #2).
- Golden-ticker regression harness: MU, GOOG, V, NOW, WU. Behavior on these must not change
  silently across sessions.   (confirmed current 2026-08-07)

## Stack & repo map
- Python / SQLite / FMP API on Replit. FMP is the sole source (AlphaVantage cross-check
  removed 2026-07-19; single-source, no confidence upgrades — see teardown note below).
- core/grading.py — assign_grade(), grade_evaluation(), run_grading(), _fetch_price_at_date(), PriceUnavailable
- store/models.py — save_grade(), list_grades(), get_ungradeable_evals(), init_db
- tests/test_grading.py
- caliber.db — tables: evaluations, grades, synthesis_cache, field_provenance, overrides

## Grading rubric (authoritative — mirrors assign_grade(), evaluated in THIS order)
1. |E(R)| < 5%   -> C  [no-conviction E(R)]   (conviction floor; wins ties)
2. |actual| < 5% -> C  [flat outcome]
3. dir correct AND |actual| >= |E(R)|*0.75 -> A   (one-sided floor, NO upper bound)
4. dir correct, smaller move -> B
5. dir wrong AND |actual| >= 15% -> F
6. dir wrong, |actual| < 15% -> D
When both C-triggers fire, [no-conviction E(R)] wins (locked decision, tested).

## Grader status — DONE (2026-07-17)
Code-complete, suite green (268 passed). Live A–F path validated synthetically; confirms on
real data ~Oct 2026 when the 8 Visa evals mature.
- run_grading() admits only evals >=90d old. At default min_age_days=90, PENDING is unreachable
  via run_grading() (query admits >=90d; PENDING branch requires <90d — mutually exclusive).

## Open threads (parked, not urgent)
1. 51 ok-evals have NULL E(R) — correct by design (synthesis never ran; nothing hidden in
   synthesis_json). Grader correctly excludes them.
2. Those 51 were written status='ok' despite NO synthesis. status='ok' should mean a complete
   eval — latent schema question in the evaluate/synthesis path.
3. "0 eligible / nothing graded" exits clean — make it distinguishable from "something broke."

## Roadmap
- Phase A — NTM forward PE fix. DONE.
- Phase B — synthesis engine schema overhaul (fix stale price-target anchoring, e.g. MU). # TODO Vic: current status?
- Phase C — KILLED. AlphaVantage cross-check torn out 2026-07-19 (see teardown note below).
- Phase D — # TODO Vic: scope
- Phase G — corporate-actions integrity: split-adjustment, zero-with-coverage sentinels,
  >5x adjacent-year EPS jump flagging.
- EDGAR — # TODO Vic: scope (SEC filings integration?)

## AlphaVantage teardown (2026-07-19)
AV cross-check removed; FMP is sole source, no re-adding a cross-check (decision closed).
- Deleted: adapters/alphavantage_adapter.py, its fixture, apply_av_cross_checks() in
  core/cross_check.py, AV tests, AV call sites in evaluate.py + batch/runner.py.
- Verdict at the behavioral gate: ADVISORY ONLY. The cross-check only ever set the
  confidence LABEL + source string on yfinance fields (value was always preserved); it
  never touched an FMP value and never altered a score, E(R), or grade. Confidence's only
  reach into output is the "[ANTI-LAUNDER: high-conf miss]" NOTE in reason_for_grade().
- Consequence to know: AV was the ONLY wired secondary source. apply_cross_check() (the
  generic engine) + apply_staleness_penalty() are KEPT, but with no secondary feed every
  field now stays 'medium'. "high" confidence is therefore unreachable, so the anti-launder
  NOTE can no longer fire on new evals. Grades themselves are unchanged (assign_grade is
  pure over E(R)/actual). No alpha_vantage pip dep existed (adapter used raw requests).
- Replit: delete the ALPHAVANTAGE_API_KEY secret manually.

## Persistence (Replit) — why this file exists
Code sessions do NOT persist: ~/.claude is wiped between containers. Repo files DO persist, and
CLAUDE.md auto-loads at session start. This file is the durable memory — keep it current.
Note: the existing Claude.md (capital C only) did NOT auto-load (wrong casing + it's the build spec).
