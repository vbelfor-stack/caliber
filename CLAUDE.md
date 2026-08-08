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
- Python / SQLite on Replit. Feed reality (2026-08-07): FMP IS THE SOLE LIVE FEED — now TRUE.
  The yfinance teardown is complete (Phases 1–3, commits 7e154cf, 369ad8d, 64f57e5).
  - FMP — the only live data feed, for both batch (batch/runner._fetch, FMP-only, fail loud,
    no failover) and interactive (evaluate.py imports fetch_fmp directly). Also the grader's
    price feed. AlphaVantage cross-check removed 2026-07-19; single-source, medium confidence.
  - yfinance — GONE. Package pin dropped from requirements.txt; adapters/yfinance_adapter.py
    deleted; no live yfinance code or import remains in the runtime.
  - TickerData (core/datatypes.py) is the pipeline's canonical data type (renamed from
    YFinanceData, rehomed out of the adapter in Phase 1). Populated by fmp_adapter (live) or
    fixture_adapter (recorded fixtures, offline/tests).
  - Fixtures: recorded ticker data lives in tests/fixtures/ticker/ (renamed from yfinance/),
    loaded by adapters/fixture_adapter.fetch_fixture. The data is in the historical yfinance
    info-dict shape, so its Prov source stamps read "yfinance" — accurate for recorded data.
  - TRACKED FOLLOW-UP (provenance relabel): live Prov source strings in core/technicals.py,
    core/pillars.py, and the shared trajectory builders in core/datatypes.py still read
    "yfinance*" while stamping FMP-sourced fields. Cosmetic mislabel, no behavioral/grade
    impact; needs source-threading + test updates. Also probe.py (Phase-0 fixture recorder)
    still imports yfinance and is now dead — archive/remove when convenient.
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
- Teardown (yfinance) — DONE 2026-08-07 (Phases 1–3, commits 7e154cf/369ad8d/64f57e5). FMP is
  the sole live feed; TickerData rehomed to core/datatypes; yfinance package + adapter removed.
  See feed-reality section above (incl. the tracked provenance-relabel follow-up).
- EDGAR — IN PROGRESS (unblocked by teardown). SEC filings integration; unlocks "high"
  confidence (the wired secondary source that makes the anti-launder NOTE reachable again).
  E-1 DONE (XBRL extraction, commit 6977a72). E-2 DONE (field resolution, commit 25b40c5;
  see EDGAR section below). E-3 BUILT AND DARK (0df4e6d + basis alignment 8d9bd07);
  threshold LOCKED, second dark run done — AWAITING ARM. See EDGAR section below.
- Phase D — after EDGAR. # TODO Vic: scope
- Phase G — corporate-actions integrity: split-adjustment, zero-with-coverage sentinels,
  >5x adjacent-year EPS jump flagging. Non-urgent — FMP price integrity exonerated by the MU
  investigation (the ~$881 price was correct). Stays behind EDGAR.
- Provenance relabel — cosmetic: retire the "yfinance*" Prov source strings on live
  FMP-sourced fields (core/technicals, core/pillars, core/datatypes trajectory builders).

## EDGAR — E-1/E-2 DONE, E-3 BUILT AND DARK (2026-08-08), awaiting arm
Purpose: EDGAR is the wired SECOND source. It makes "high" confidence reachable again and
restores the anti-launder NOTE, which has been unfirable since the AV teardown.
- E-1 (6977a72): XBRL companyfacts extraction — raw us-gaap/dei concept facts, form-filtered
  (10-K/10-Q family), numeric-coerced, most-recent-first. Fixtures for MU/GOOG/V.
- E-2 (25b40c5): canonical field resolution — 16 fields in adapters/edgar_adapter.py.
  - Extraction depth 40, DE-DUPLICATED FIRST. companyfacts repeats an unchanged fact in
    every filing referencing it (~half of records); identical (start,end,unit,value) tuples
    collapse (newest accession wins) BEFORE the cap, else duplicates crowd out the older
    periods TTM needs. 15 de-duped records cover 10 distinct period-ends worst-case → 40 is
    ~2.5x margin.
  - Synonym table (FIELD_SPECS): explicit ordered chains, NO heuristics. Issuers migrate tags
    and abandon the old one; no golden CIK files two competing tags concurrently. Mapped
    migrations: equity (V uses ...IncludingNoncontrollingInterest; its StockholdersEquity
    stopped 2011), current debt (GOOG/V LongTermDebtCurrent vs MU DebtCurrent), long-term debt
    (GOOG/V LongTermDebtNoncurrent vs MU LongTermDebt), shares (dei absent for GOOG / frozen
    2010 for V, both multi-class → us-gaap CommonStockSharesOutstanding fallback), revenue
    (Revenues <-> RevenueFromContractWithCustomerExcludingAssessedTax), gross profit (GOOG/V
    untagged → derived revenue - cost_of_revenue, same period + same method only).
  - STALE GATE 450d (one fiscal year + a quarter): a concept whose newest period-end lags the
    entity's latest filed period is skipped and the chain falls through; an all-stale chain
    WITHHOLDS the value. Rationale — a stale figure passed downstream wearing a fresh label
    could land inside cross-check tolerance and launder to high. Caught live: V equity
    2011→2026-03-31, GOOG current-debt 2018→2026-06-30, V current-debt 2017→2026-03-31.
  - TTM, three methods, each STAMPED on the field: ttm_annual (newest fact already spans a
    full FY — exact), ttm_summed (4 contiguous QTD ~365d), ttm_reconstructed (prior FY +
    current YTD − prior-year YTD; required by all three golden CIKs, none report Q4
    standalone). Never a partial sum → REASON_TTM_UNAVAILABLE. ttm_summed has SYNTHETIC-ONLY
    coverage; no golden CIK exercises it live.
  - Typed reasons on every withheld field (no_tag, stale_tag, synonym_conflict,
    ambiguous_period, ttm_unavailable, derive_incomplete) + per-synonym trail. These are the
    queryable tag-migration map for onboarding new tickers.
  - Coverage: MU 16/16, GOOG 16/16, V 12/16. V's 4 gaps are ACCEPTED DATA LIMITS: no
    cost-of-revenue or capex concept filed (no_tag x2), gross profit therefore underivable
    (derive_incomplete), share count stale with no fallback (stale_tag). Consequence: V gets
    no gross-margin and no FCF cross-check. Zero synonym conflicts on the golden CIKs.
- E-3 FRESHNESS RULING (locked 2026-08-08, before build): freshness is PER-FIELD, from that
  field's OWN period-end — never per-ticker. MU long_term_debt lags 182d while its siblings
  sit at the latest quarter; it stays capped at medium while they may upgrade. The dark-launch
  delta table must surface that case explicitly so the per-field gate is visibly working.
  CONFIRMED in the second dark run: MU total_debt/debt_to_equity age from 2025-11-27 (254d)
  while its income-statement siblings age from 2026-05-28 (72d), in the same report.
- E-3 STALENESS RULING (locked 2026-08-08, post-dark-run): the 150d day-count is the
  BACKSTOP; the lag-aware submissions cross-reference is the PRIMARY signal, with the
  XBRL-LAG / MISSING-EXPECTED-10Q split as built. Day-count alone is provably insufficient —
  V sits at 130d (inside any sane gate) while a full quarter behind.
- Fixture coverage: all five golden tickers (MU/GOOG/V/NOW/WU) have EDGAR fixtures as of
  d99e8b8. Re-record with `python -m tools.record_edgar_fixture TICKER` — deliberate manual
  step, it moves the regression baseline. NOW 17/17 fields, WU 13/17.
  WU accepted data limits (same class as V's): UNCLASSIFIED balance sheet, so no
  AssetsCurrent/LiabilitiesCurrent exist at all (SettlementAssetsCurrent is float, NOT
  working capital — deliberately not chained in) → no current_ratio; no fresh current-debt
  tag → no total_debt; no ST-investment tag since 2015 → cash-only advisory.
- SECOND DARK RUN (2026-08-08, live, golden five). would-change: MU 7/12, GOOG 7/12,
  NOW 7/12, WU 6/12, V 1/12. Upgrades 6/7/7/5/0; downgrades-to-low 1/0/0/1/1.
  - total_cash measure identity PROVEN: EDGAR cash+ST-investments equals FMP's
    cashAndShortTermInvestments to 0.0% at the matching FY-end (GOOG 126.84B, MU 10.307B,
    NOW 6.284B). Rows still read basis_mismatch because the comparison carries an
    unconditional annual-vs-MRQ basis note — advisory by design, never an agree.
  - Average-equity ROE landed: GOOG 25.0% -> 4.3% (agree). MU 29.0% -> 5.5%, which is just
    OVER the 5.0% tolerance and therefore still a CONFLICT (would downgrade MU roe to low).
  - OPEN, blocks arming: a conflict-derived 'low' BYPASSES the staleness/lag cap, because
    apply_staleness_penalty only caps 'high'. V's current_ratio (10.4%) would be downgraded
    to low on data the same run flags XBRL-LAG as a full quarter stale. Downgrades on
    known-stale data need a ruling before arm.

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
