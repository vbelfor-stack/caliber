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
  - anchor_price divergence   # ARMED 2026-08-07 at 15% (B-2). Anchor-AGNOSTIC: trips when the
    #   model's implied anchor (from its own E(R)+targets) and the live price disagree >15% —
    #   catches EITHER a stale LLM anchor OR a bad feed price. Raises AnchorPriceDivergence;
    #   E(R) withheld; status='anchor_divergence'. See Anchor guard note below.
  - PE basis computed on negative forward EPS  (LCID is the negative-forward-PE test fixture)
- status='ok' must mean a COMPLETE eval (see open thread #2).
- Golden-ticker regression harness: MU, GOOG, V, NOW, WU. Behavior on these must not change
  silently across sessions.   (confirmed current 2026-08-07)

## Stack & repo map
- Python / SQLite on Replit. Feed reality (corrected 2026-08-07): "FMP sole source" is
  INACCURATE as previously written. Actual state:
  - FMP — batch-primary (batch/runner._fetch_with_failover) and the grader's price feed.
  - yfinance — batch-FALLBACK leg (fires when FMP raises) AND interactive-primary
    (evaluate.py fetches yfinance directly, no FMP). Rate-limited/IP-blocked on Replit,
    so the live yfinance paths are dead-on-arrival here (fail loud, ~6.6s, no hang) — but
    still wired. AlphaVantage cross-check removed 2026-07-19; single-source, no confidence
    upgrades (see teardown note below).
  - YFinanceData (in adapters/yfinance_adapter.py) is the pipeline's CANONICAL data type,
    imported by core/pillars, synthesis/client, synthesis/prompt, batch/runner, AND
    adapters/fmp_adapter itself — FMP cannot run without the yfinance_adapter module.
    A true "sole source" state requires the teardown (Phase 1 = rehome this type to a
    neutral core module). Sequencing: Phase B → teardown Phases 1–3 → EDGAR → Phase D.
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
1. RESOLVED 2026-08-07. The "51 (later 119) ok-evals with NULL E(R)" were NOT real evals —
   they were TEST CONTAMINATION. tests/test_batch.py ran fixture-mode run_single_ticker/
   run_batch without a db_path, writing into production caliber.db. Purged 2026-08-07 (see
   Data integrity note). No real no-synthesis 'ok' eval ever existed.
2. RESOLVED 2026-08-07 by B-1 (producer-side): save_evaluation now derives status from
   synthesis presence ('ok' only if synthesis present, else 'no_synthesis'). The fix is
   correct and stands; its ORIGINAL production-backfill "validation" was retroactively vacuous
   (it operated entirely on the test-contamination rows above). Real-data validation of B-1/B-2
   status semantics lands with R-4's golden-ticker run.
3. "0 eligible / nothing graded" exits clean — make it distinguishable from "something broke."
   DONE 2026-08-07 (run_grading now emits an explicit "CLEAN EMPTY" line + early return).
4. anchor_price divergence hard stop — DONE 2026-08-07 as B-2, ARMED at 15%. See Anchor
   guard note below for the calibration + MU resolution.

## Data integrity — test-contamination purge (2026-08-07)
- Root cause: tests/test_batch.py wrote fixture-mode evals into production caliber.db (no
  db_path). Fixed by conftest.py autouse fixture (R-1) that pins the default DB to a temp path;
  verified no test write reaches production (row count stable across a full suite run).
- Purge (R-2): removed 189 evaluations (153 no_synthesis fixture clusters MU/GOOG/V + 36 failed
  synthetic tickers) and 3,060 linked field_provenance rows, under a transaction with a
  blast-radius assertion (exact 189/3,060 or ROLLBACK). Backup: caliber.db.pre-purge-2026-08-07.bak.
- TRUE post-purge distribution: ok:8, failed:11, no_synthesis:0 (total 19). The 8 ok are the
  REAL Visa synthesis evals (live avg=4.0 != fixture 3.8; synthesis present; genuine 2026-07-12
  session) maturing to the grader's first live grades ~2026-10-10. The 11 failed are real
  yfinance-DOA operational records (kept as the evidence trail). grading-eligible still 0.

## Anchor guard — calibration + MU resolution (2026-08-07, B-2 DONE)
- Guard ARMED at 15% in synthesis/schema.py (ANCHOR_DIVERGENCE_THRESHOLD=0.15). Derived check:
  implied_anchor = weighted_target / (1 + model_E(R)/100), compared to live price. Divergence is
  logged on EVERY eval permanently (ongoing calibration); >15% raises AnchorPriceDivergence,
  caught at both synthesis boundaries → E(R) withheld (NULL), status='anchor_divergence',
  synthesis_json kept, record-and-continue. threshold=None replays disarmed.
- Live golden-ticker calibration (R-4): divergence — GOOG 0.6%, NOW 3.2%, V 6.1%, WU 8.2%,
  MU 90.8%. Healthy band 0.6-8.2%; 15% isolates the pathological case with ~6x margin.
  null-model-E(R) rate 0/5 (and 0/8 historical) → anchor_unverified rarely fires; no prompt fix
  needed for that.
- MU root cause RESOLVED: it was a genuine stale LLM anchor, NOT a feed bug. Model anchored to
  ~$81 (stale training data); MU really trades ~$881 (~$1T mkt cap, May-2026 HBM-cycle 10x
  re-rate, no split) — FMP was CORRECT. The guard caught its motivating Phase-B case on first
  live outing. Canonical positive preserved as eval id=209 (retroactively set anchor_divergence,
  E(R) NULL). Do NOT delete id=209.
- Prompt fix (root cause): synthesis/prompt.py now instructs the model to anchor ALL targets to
  the provided current_price and never use remembered price levels. Verified: MU re-eval (id=214,
  force_refresh) re-anchored targets to $525/$800/$1225, divergence 90.8% -> 1.1%, status ok.
- NOTE the guard is anchor-AGNOSTIC: it flags model-vs-live disagreement regardless of which side
  is wrong (stale LLM anchor OR bad feed price). Withholding a laundered E(R) is correct either way.

## Roadmap
- Phase A — NTM forward PE fix. DONE.
- Phase B — synthesis engine schema overhaul (stale price-target anchoring, e.g. MU). DONE
  2026-08-07: B-1 (status semantics: ok requires synthesis; no_synthesis/anchor_unverified/
  anchor_divergence enum) + B-2 (anchor guard ARMED at 15% + prompt anchoring fix). See Anchor
  guard note above. E(R) computed downstream from targets, never delegated to the LLM.
- Phase C — KILLED. AlphaVantage cross-check torn out 2026-07-19 (see teardown note below).
- Phase D — HOLD until teardown Phase 1 done. # TODO Vic: scope
- Phase G — corporate-actions integrity: split-adjustment, zero-with-coverage sentinels,
  >5x adjacent-year EPS jump flagging. Non-urgent — FMP price integrity exonerated by the MU
  investigation (the ~$881 price was correct). Stays behind teardown + EDGAR, original sequence.
- EDGAR — HOLD until teardown Phase 1 done (no point wiring a 2nd source into a type system
  about to be rehomed). # TODO Vic: scope (SEC filings integration?)
- Teardown (yfinance) — follows Phase B. Phase 1 rehome YFinanceData + trajectory builders
  to neutral core module; Phase 2 migrate evaluate.py to FMP; Phase 3 remove fallback leg +
  requirements pin. Blast radius logged in session 2026-08-07.

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
