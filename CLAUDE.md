# CLAUDE.md — CALIBER (operational context; auto-loads every session)
# Detailed build spec lives in Claude.md (Jul 10). This file is the living operational memory.

## ▶ SESSION PICKUP — READ THIS FIRST (rewritten at close, 2026-08-17)
Opening a session with **"resume — execute the next order in CLAUDE.md"** is enough. This
section is the cold-start record; everything below it is the durable detail.

**TOMORROW'S FIRST ACTION: run the session-open protocol, then execute L-4a (STX diagnosis).
Do not start coverage expansion before L-4a and L-4b land.**

### STATE AT CLOSE 2026-08-17 — every value below was MEASURED at close, not remembered

| | |
|---|---|
| HEAD | the **session-close commit carrying this block** — verify with `git log -1`. **Last WORK commit: `633d300a5717a662fdd8f98c394a755f913f3998`** ("L-3 report: consumer census, dark table, zero flips"). A block cannot contain its own hash; this was caught by the close verification pass rather than left as a false claim. |
| Pushed | **YES — `git rev-list --count origin/master..master` reads 0**, tree clean, no uncommitted state |
| Suite | **825 passed** |
| caliber.db md5 | **24df814597b6bab52b979e7fee6ca034** (WAL checkpointed at close) |
| evaluations | **79** rows, max id **271** · held 50 / calibration 29 / NULL 0 |
| lifecycle_stage | **43** rows |
| lifecycle_transitions | **1** row (IONQ HIGROWTH → YOUNG) |
| field_provenance | **1416** rows |
| fundamental_series | 557 rows (4 tickers only — MU/GOOG/NOW/WU) · grades 0 · synthesis_cache 16 |

### ARMED STATE — what reads what, precisely

- **§5 step 3 IS ARMED, IN `evaluate.py` ONLY.** The B-2 anchor-divergence band is
  stage-conditioned: **YOUNG 30% · HIGROWTH 20% · MATURE 15% · DECLINE 15%**, read from the
  PERSISTED `lifecycle_stage` table via `core/stage_tolerance.tolerance_for()`.
- **KNOWN DIVERGENCE, FIX RULED FOR L-4a:** `batch/runner.py` still calls the guard on the
  **flat 15%**. The two write paths currently disagree about tolerance. Bounded and legible,
  but it must not persist.
- **THE TOLERANCE LOOKUP IS THE ONLY SCORING-PATH CONSUMER OF LIFECYCLE STAGE.** Pinned by
  `test_the_tolerance_lookup_is_the_ONLY_scoring_path_consumer_of_stage`. `core/pillars.py`,
  `core/valuation_anchors.py`, `batch/runner.py` and `synthesis/schema.py` contain no
  reference to the classifier or the stage table. The band is passed INTO `check_anchor` as
  its existing `threshold`, so the guard never learns what a stage is.
- **§5 STEPS 4+ ARE UNARMED.** Step 4 (YOUNG supply-layer block) is BLOCKED behind
  `fundamental_series` coverage expansion by standing ruling — 24 of 28 names have no FCF
  history, so the YOUNG/blocked boundary currently reflects FEED COVERAGE, not business
  reality, and a hard block on that basis would be arbitrary.
- Step 1's no-read-back pin was **RETIRED BY NAME** at L-3 and replaced by the successor pin
  above. Its surviving half is still checked: the annotation runs AFTER scoring, so a run's
  own stage row cannot feed that run's own pillars.

### THE L-4 WORK ORDER — as issued by Vic in the 2026-08-17 close order

Transcribed verbatim from the close order's own words; it was not delivered as a separate
order document, and that is recorded here rather than silently smoothed over.

> **STX diagnosis first — price-feed vs stale-anchor question; batch tolerance arming; then
> coverage expansion capped at one order, step 4 ruled on its evidence.**

Code's reading, stated separately and NOT part of the order:

- **L-4a — STX DIAGNOSIS, FIRST.** STX carries a **90.08% anchor divergence** and
  `status='anchor_divergence'`: its synthesis anchored near **$94** while STX trades near
  **$995**, a ~10x gap. The question to answer is **price-feed vs stale-anchor** — i.e. is
  FMP serving a wrong/split-unadjusted price, or did the model anchor to a stale remembered
  level (the MU 2026-08-07 shape, which turned out to be a stale LLM anchor while the feed
  was correct)? Both are ~10x-shaped, and the MU precedent says do not assume which.
  E(R) is currently withheld on STX, which is the guard working.
- **L-4b — BATCH TOLERANCE ARMING.** Bring `batch/runner.py` onto the same stage-conditioned
  band so the two write paths stop disagreeing. Flips the batch dark pin — expect to retire
  it by name and replace it, exactly as L-3 did for evaluate.py.
- **L-4c — COVERAGE EXPANSION, CAPPED AT ONE ORDER.** Extend `fundamental_series` beyond the
  four names it covers. **Step 4 is then ruled on that evidence**, not before.

### PUNCH LIST — current at close

- **`field_provenance.field_name` is NULL on all 1,416 rows** — provenance is unqueryable by
  field, only by `(evaluation_id, pillar)`. **DIAGNOSIS QUESTION, not yet a fix order:** is
  the writer dropping the name, or was it never populated?
- **SHARE-CLASS DEDUP AT CIK LEVEL.** GOOG and GOOGL are ONE issuer on ONE CIK
  (`0001652044`) and both are evaluated. Two rows with near-identical fundamentals would
  DOUBLE-WEIGHT one forecast in any grade rollup. GOOGL is canonical (held); GOOG is
  calibration. Dedup by CIK before grading aggregates, not by ticker.
- **REPLACE THE `_CYCLICAL_INDUSTRY` KEYWORD SWEEP with explicit SIC entries** as names
  accumulate. Matching keywords against a vendor's free-text industry string is what put
  IONQ/INFQ on the cyclical lens and forced the L-2b overrides.
- **FEED-REPAIR TICKETS:** `income_annual` series gaps — **IONQ missing FY2020**, **XE missing
  FY2023 and FY2024**. Both had peak detection REFUSED rather than inferred across the hole.
- **NO ETF/FUND REFUSAL GUARD.** Pointing `evaluate.py` at an ETF yields a garbage
  classification instead of a refusal. The signal is already in the payload FMP returns
  (`isEtf: true`, verified live on LYTE). LYTE and FLTW are held but deliberately absent from
  `tickers.txt` for this reason.
- **THRESHOLD CALIBRATIONS — BOTH FLAGS STAY INDEFINITELY.**
  `GUARD-TOLERANCE-UNCALIBRATED` (no cyclical name has carried a decline streak, so ZERO real
  peak comparisons have occurred) and `REINVESTMENT-THRESHOLD-UNCALIBRATED` (only GOOG 1.195
  and MU 0.668 measured). **NO SYNTHETIC CALIBRATION, EVER** — a tolerance tuned on generated
  series is worse than no tolerance.

### STANDING RULES THAT SURVIVE SESSIONS

- **PUSH ON LANDING.** Any commit that closes a ruled work order pushes immediately — no
  per-commit approval. Unpushed-at-close is the exception, not the norm.
- **EXPECTED-DELTA ON EVERY WRITE.** State the full expected delta set INCLUDING dependents
  before writing; report anything outside it rather than absorbing it. Standing companions of
  any evaluation write: `field_provenance` +N per eval, `synthesis_cache` +1 per ticker
  synthesised **by batch only** (`evaluate.py` never writes the cache), `sqlite_sequence` +1
  per new AUTOINCREMENT table.
- **SUPERSEDE, NEVER PURGE, for a sanctioned run with a defect.** A corrected run lands as a
  NEW ROW with `supersedes_id` + a stated reason. Purge is reserved for CONTAMINATION (rows
  that should never have existed), under a transaction with an exact blast-radius assertion.
- **FAIL-CLOSED DEFAULTS.** A guard that cannot measure DENIES the tag or band it guards:
  the peak gate denies DECLINE, the FCF gate denies YOUNG, an unclassified name gets the
  DEFAULT tolerance and never the widest. Absence must never be privately optimal.
- **NO SAME-DAY DUPLICATE E(R)s.** Re-run only names whose state actually changes; unflipped
  names do not re-run.
- **STOP AND REPORT BETWEEN ORDERS.** One step per work order, dark-verified before the next
  arms. Nothing arms without a ruling.
- **ALWAYS `PRAGMA wal_checkpoint(TRUNCATE)` BEFORE RECORDING AN md5**, or a later checkpoint
  moves bytes with no logical write behind it.
- **A RULE RECORDED WITHOUT NAMING ITS ENFORCEMENT POINT IS A BELIEF, NOT A GUARD** — and a
  flag verification only covers the writes the verifying run actually performs.

## ▶ ARCHIVE — FINISHED HISTORY NOW LIVES IN docs/phase-archive.md (trimmed 2026-08-19)
Pure relocation under ruling; nothing deleted. **READ THE ARCHIVE BEFORE TOUCHING A SURFACE IT
COVERS — it carries live-behaviour facts, not just narrative** (EDGAR ARMED SET, the
permanent-advisory rows, the R-A alignment preconditions, every Phase D ladder and gate).
- **Phase D — VALUATION PANEL, D-0→D-6 rulings** — all five lenses, ladders, gates, bank calibration, MIN-across-anchors, peer rejection → docs/phase-archive.md
- **EDGAR E-1→E-4 detail** — ARMED SET, permanent-advisory + dark rows, `debt_to_equity` three conventions, FIELD_SPECS synonyms, TTM methods, stale gate, R1/R-NEW, E-4 ceiling finding → docs/phase-archive.md
- **EDGAR alignment semantic R-A** — the three preconditions, the third re-checked every evaluation → docs/phase-archive.md
- **2026-08-15 close notes, first session** — Phase H close, the D/E units scoring defect, H-3 arming, fixture migration, the eleven-test silent dependency → docs/phase-archive.md
- **2026-08-15 close notes, second session** — re-run ids 221-225, supersede trail, the three effect classes + the two superseded H-FCF order blocks → docs/phase-archive.md
- **INCIDENT 2026-08-17 — production contamination from a fixture run (closed)** — cause, purge, md5 trail, the second leak, the two lessons → docs/phase-archive.md
- **Data integrity — test-contamination purge 2026-08-07 (closed)** — root cause, 189/3,060 blast-radius purge, true post-purge distribution → docs/phase-archive.md

## ▶ PHASE L PUNCH LIST (deferred, ruled)
<!-- promoted ### -> ## by the 2026-08-19 archive trim: its parent section (the 2026-08-17
     incident record) moved to docs/phase-archive.md. Text below is unchanged. -->

- **STEP 4 (YOUNG SUPPLY BLOCK) IS BLOCKED BEHIND FEED COVERAGE (ruled 2026-08-17).**
  `fundamental_series` covers 4 of 28 names, so the YOUNG population (4, with 4 more blocked
  by L-1e's fail-closed guard) currently reflects **which names happen to have FCF data**,
  not business reality. A hard block driven by feed coverage would be arbitrary in exactly
  the way this system exists to avoid. **Sequence: fundamental_series coverage expansion →
  then step 4.** The two feed-repair tickets below join that work.
  **STEP 3 (B-2 stage-conditioned tolerances) MAY PROCEED after L-2b** — tolerances are
  bounded and inspectable; blocks are not.
- **FEED-REPAIR TICKETS (from the step-2 run):** `income_annual` series gaps —
  **IONQ missing FY2020**, **XE missing FY2023 and FY2024**. Both had peak detection REFUSED
  rather than inferred across the hole (L-1e contiguity precondition, which fired on live
  data despite being recorded as latent).
- **SHARE-CLASS DEDUP AT CIK LEVEL (ruled 2026-08-17, not built).** GOOG and GOOGL are ONE
  issuer on ONE CIK (0001652044) and both are now evaluated. Two rows with near-identical
  fundamentals would DOUBLE-WEIGHT one forecast in any grade rollup. GOOGL is canonical
  (held); GOOG is calibration. Dedup by CIK before grading aggregates, not by ticker.
- **REPLACE THE `_CYCLICAL_INDUSTRY` KEYWORD SWEEP with explicit SIC entries** as names
  accumulate. Matching keywords against a vendor's free-text industry string is what put
  IONQ/INFQ on the cyclical lens and forced the L-2b overrides.
- Calibrate `REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL` on the FULL UNIVERSE after §5 arms.
- **NO ETF/FUND REFUSAL GUARD EXISTS (found 2026-08-17, recorded not built).** Pointing
  `evaluate.py` at an ETF today produces a garbage classification rather than a refusal. The
  signal is ALREADY in the payload production fetches — FMP `profile` returns
  `isEtf: true` (verified live on LYTE, "Roundhill Photonics & Optics ETF"). A guard is one
  check at the adapter boundary. LYTE and FLTW are held but deliberately absent from
  `tickers.txt` for this reason.
- **NO SYNTHETIC CALIBRATION, EVER** — `GUARD-TOLERANCE-UNCALIBRATED` and
  `REINVESTMENT-THRESHOLD-UNCALIBRATED` stay until REAL data calibrates them.

## How we work (relay / architect model)
- Vic is architect and gatekeeper; Code executes work orders. Report as you go, in plain English.
- STOP and ask before: changing grading/scoring logic, restructuring working code, deleting or
  overwriting data, or any change beyond what the order specifies.
- Never add duplicate logic. If existing behavior already satisfies the order, leave it and say so.
- Manual mode (per-action approval) is the default.

## SESSION-OPEN PROTOCOL (standing rule, 2026-08-15) — PEER-PROCESS CHECK
On every wake-up: run `ps aux | grep claude` and `ListAgents`. Verify your OWN pid
EMPIRICALLY (spawn a bash child, read its PPID) — never assert identity from memory or
prior session notes. If any peer process exists: STOP, report the full ps with self/peer
labeled, and await ruling before touching the tree. Never execute a kill against a PID not
verified this session.

ALSO CHECK FOR ORPHANED CHILDREN OF A DEAD SESSION (added 2026-08-17): processes with
`ppid 1` running python / evaluate.py / batch.runner. A session died mid-order on 2026-08-16,
and anything of its that can still WRITE TO caliber.db is a data hazard, not just clutter.
Enumerate by ppid, per the close protocol — do not pattern-match for them.

WHY THIS EXISTS (2026-08-15, real incident): an orphaned peer session shared this checkout
and wrote the entire H-1 build into it WHILE a fresh session was re-orienting after an
interrupt — the tree changed between two `git status` calls minutes apart. The successor
session then asserted from context that it was PID 243; it was in fact PID 3070, and 243
was the peer. Acting on that inverted belief would have killed the verifying session and
LEFT THE WRITER RUNNING. A PPID read settled it in one command. Two sessions on one
checkout is a data-loss hazard; an unverified kill target is a worse one.

## SESSION-CLOSE PROTOCOL (standing rule, 2026-08-09)
- **ENUMERATE CHILD PROCESSES BY PPID AND STOP THEM. A PATTERN GREP IS NOT A PROCESS CHECK.**
  `ps -eo pid,ppid,etime,cmd --no-headers | awk '$2==<own pid>'` — the parent/child link is
  STRUCTURAL; a grep pattern is a guess about what you happened to name things. Stop harness
  tasks with **TaskStop** (keeps its bookkeeping straight), not a bare kill.
  ORIGIN 2026-08-17: the close reported "zero processes" after grepping
  `python|evaluate.py|pytest` — a pattern that CANNOT match a bash `until ... sleep` loop —
  while two wait-loops had been spinning for 2h27m and 55m. Vic caught it, not the check.
- **`pgrep -f "X"` MATCHES THE WATCHER'S OWN COMMAND LINE.** Both leaked loops used
  `until ! pgrep -f "evaluate.py"`, and their own `bash -c` contained that literal string, so
  the exit condition was UNREACHABLE FROM THE FIRST SECOND. Self-exclude (`| grep -v $$`),
  match on something the watcher does not contain, or wait on the harness task instead.
- EVERY session ends with a PUSH TO ORIGIN after the session-close commit. Unpushed local
  commits are a single-container-failure loss — committing is NOT backing up. The close is
  not done until `git rev-list --count origin/master..master` reads 0.
- DATABASE FILES NEVER GO TO THE REMOTE (ruling 2026-08-09). caliber.db, *.bak and any DB
  artifact stay local. Verified already covered by .gitignore (`*.db`, `caliber.db.*`,
  `*.bak`) and never committed in any branch's history — no remediation was needed.
- Before a push, run the secrets pass: no hardcoded keys (all creds must be os.environ.get),
  .env.example placeholders empty, no fixture embedding a keyed URL. Public SEC/FMP fixture
  payloads are fine to push.
- CONTAINER-WIPE AUTH (2026-08-09, RESOLVED — expect it again every new container): origin
  push fails with "Password authentication is not supported". The wipe takes GitHub
  credentials with it; ~/.claude is not the only thing that does not persist.
  TWO steps, and the second is the one that gets missed:
    1. `gh auth login`      — MANUAL VIC STEP (interactive; Code cannot do it)
    2. `gh auth setup-git`  — wires gh as git's credential helper. WITHOUT THIS, gh reads
       "logged in" and `git push` STILL FAILS: gh's token does not reach git on its own.
  Do NOT read a successful `git ls-remote origin` as proof push will work — the repo is
  public, so reads succeed anonymously while pushes reject. Only a real push proves auth.
- The `gitsafe-backup` remote is NOT a usable fallback: its pre-receive hook allows pushes to
  `main` ONLY, and its `main` (88cd9fd) is an UNRELATED history line. Reaching it would mean
  force-pushing over unrelated commits — destructive, never done unattended.

## Core disciplines (non-negotiable)
- LOUD FAILURE BEATS SILENT DEGRADATION. Failures raise a typed signal — never swallowed,
  never masked as success. (yfinance fallback was removed for this reason.)
- Hard stops — must raise typed signals, never pass silently:
  - anchor_price divergence   # ARMED 2026-08-07 at 15% (B-2). Anchor-AGNOSTIC: trips when the
    #   model's implied anchor (from its own E(R)+targets) and the live price disagree >15% —
    #   catches EITHER a stale LLM anchor OR a bad feed price. Raises AnchorPriceDivergence;
    #   E(R) withheld; status='anchor_divergence'. See Anchor guard note below.
  - PE basis computed on negative forward EPS  (LCID is the negative-forward-PE test fixture)
  - MISSING RISK-FREE RATE   # ARMED 2026-08-09 (D-2). The rate anchor is MANDATORY: no
    #   FRED 10Y -> score_valuation raises RateUnavailable (core/pillars.py) and the
    #   valuation pillar REFUSES to score. Checked ahead of the lens dispatch, so it binds
    #   ALL FIVE lenses, not just the spread-based compounder. Boundaries: evaluate.py
    #   exits 3 with a loud readout; batch/runner.py persists status='rate_unavailable'
    #   and continues to the next ticker. 0.0 is a RATE (ZIRP), not a missing one.
- status='ok' must mean a COMPLETE eval (see open thread #2).
- Golden-ticker regression harness: MU, GOOG, V, NOW, WU. Behavior on these must not change
  silently across sessions.   (confirmed current 2026-08-07)
  **THE HARNESS PAID FOR ITSELF 2026-08-15 — LEDGER ENTRY, PRODUCTION DATA.** It caught a
  UNIT-CONVENTION PRODUCTION DEFECT that the suite, the grader and a full live armed pass
  ALL MISSED: FMP's debt/equity RATIO scored against a PERCENT ladder for eight days, so
  every issuer collected maximum leverage points and the component was inert (see the
  three-conventions note in the EDGAR section, now in docs/phase-archive.md). 654 tests were
  green throughout; the live
  armed pass of 2026-08-09 filed V — levered ~67% — as "debt/equity 1%" and nothing
  objected. **THE ONLY REASON THE DEFECT SURFACED IS THAT THE LEGACY FIXTURES PRESERVED
  THE OLD UNIT CONVENTION**, so a routine before/after diff put percent beside ratio and
  the 100x gap became visible. A harness whose baseline had already been migrated to the
  new feed would have agreed with the bug and shown nothing. THE ARGUMENT FOR KEEPING AN
  INDEPENDENT BASELINE IS NOW WRITTEN IN PRODUCTION DATA, not in principle.
  COROLLARY, and the reason the migration below was ordered only AFTER the fix landed:
  migrating a baseline onto the same source it is meant to check RETIRES THE CHECK. When
  that is done deliberately, the thing being given up must be named.

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
  - Fixtures: recorded ticker data lives in tests/fixtures/fmp/, loaded by
    adapters/fmp_adapter.fetch_fmp(fixture_path=...) — THE SAME CALL PRODUCTION MAKES, so
    an offline run cannot exercise a code path production no longer has. The yfinance-shaped
    tests/fixtures/ticker set and its fixture_adapter loader were DELETED 2026-08-15; their
    Prov stamps read "yfinance" and offline provenance never matched what production writes.
    That also retires most of the tracked provenance-relabel follow-up below.
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
   Data integrity note, now in docs/phase-archive.md). No real no-synthesis 'ok' eval ever
   existed.
2. RESOLVED 2026-08-07 by B-1 (producer-side): save_evaluation now derives status from
   synthesis presence ('ok' only if synthesis present, else 'no_synthesis'). The fix is
   correct and stands; its ORIGINAL production-backfill "validation" was retroactively vacuous
   (it operated entirely on the test-contamination rows above). Real-data validation of B-1/B-2
   status semantics lands with R-4's golden-ticker run.
3. "0 eligible / nothing graded" exits clean — make it distinguishable from "something broke."
   DONE 2026-08-07 (run_grading now emits an explicit "CLEAN EMPTY" line + early return).
4. anchor_price divergence hard stop — DONE 2026-08-07 as B-2, ARMED at 15%. See Anchor
   guard note below for the calibration + MU resolution.

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
  E-1 DONE (XBRL extraction, 6977a72). E-2 DONE (field resolution, 25b40c5).
  E-3 ARMED 2026-08-09 (031506f) — live at both boundaries. E-4 DONE (verdict-high
  reachability): the note is NOT revived, see the E-4 finding + EDGAR section, both now in
  docs/phase-archive.md.
- Phase D — VALUATION PANEL: **CLOSED 2026-08-09. ALL FIVE LENSES ARMED.** Ethos rule 10
  is fully built — every lens is rate-aware, on THREE DIFFERENT MECHANISMS:
    panel-anchored (MIN across anchors) : compounder, cyclical, standard
    rate-shifted thresholds             : growth
    cost-of-equity                      : bank
  ARMED_LENSES and ARMED_PANEL_LENSES are deliberately DIFFERENT SETS — 'armed' does
  not mean 'panel-scored'. See the Phase D section (now in docs/phase-archive.md) +
  docs/d5-banks.md.
- OPEN TRIPWIRES (Phase D leftovers, each reports to Vic before its result is trusted):
  1. STANDARD-LENS FIRST EVAL — no golden ticker is natively standard-lens, so the first
     production eval scoring through it reports with its full panel readout.
  2. BANK CHEAP RUNGS (5 and 4) ARE PROVISIONAL-UNCALIBRATED — no bank in the JPM/BK/
     USB/C set trades below justified book, so those rungs are reasoned, not measured.
     Flagged BANK-RUNG-UNCALIBRATED; first live eval landing there reports with the full
     readout.
  3. BETA IS SINGLE-SOURCE (FMP, no cross-check) and moves CoE directly, so the bank
     pillar is CAPPED AT MEDIUM while beta is uncorroborated (_cap_beta_confidence).
     The cap LIFTS AUTOMATICALLY when a second beta source is wired — no code change.
- Phase G — corporate-actions integrity: split-adjustment, zero-with-coverage sentinels,
  >5x adjacent-year EPS jump flagging. MOVED UP (ruling 2026-08-09): scope it IMMEDIATELY
  AFTER D-4 ARMS, BEFORE any further EDGAR expansion. No longer "stays behind EDGAR".
  SCOPED 2026-08-11 — docs/g-scoping.md, NOTHING IMPLEMENTED, awaiting rulings. See the
  pickup section for the findings. THE ORIGINAL RATIONALE IS PARTLY REFUTED ON EVIDENCE:
  "own-history is absent 17 of 20 readings" is true but is NOT evidence for G — 15 of
  those 17 are absent by construction (trailing-earnings-only) and 1 is V's accepted data
  limit. G reaches EXACTLY ONE CELL (3/20 -> 4/20) and moves ZERO scores on all nine
  tracked tickers. It remains worth doing as latent-trap removal and accuracy. FMP price
  integrity stays exonerated by the MU investigation (~$881 was correct); this is about
  series BASIS consistency, not price correctness.
  Phased plan on record: G-1 capture `filed` (additive, resolution diff must be empty) ->
  G-2 split acquisition + three-witness corroboration DARK -> G-3 filed-date restatement
  DARK, validated PER-POINT not on medians -> G-4 arm on ruling -> G-5 (separate ruling)
  sentinels + EPS-jump flagging. Two tests flip when G lands, the JPM-cash-tag pattern:
  test_series_truncates_at_a_split_boundary, test_a_recent_split_can_cost_the_anchor_entirely.
  **CLOSED 2026-08-11 — G-4 ARMED on a zero-score-movement diff** (docs/g-build.md).
  Delivered: mixed-basis rule (basis at FILING date) · 2-of-3 witness corroboration with
  the DATE FROM FMP · scope horizon for pre-XBRL splits · restatement_blocked · the
  limit=365 pin. Own-history coverage 3/20 -> 4/20 readings, 7/9 -> 8/9 tickers. No score,
  E(R) or grade moved. PRECEDENT SET: first corroborated-by-design input, and the ruled
  TEMPLATE FOR THE BETA CROSS-CHECK (which lifts D's tripwire 3).
  G-1/G-2/G-3 built dark first; the arm diff matched the dark diff exactly.
  New surfaces: core/corporate_actions.py (witnesses, corroboration, scope horizon,
  split_factor, restatement_blocked); adapters/fmp_adapter.fetch_splits; EDGAR gained
  `first_filed` on every fact + the tagged-ratio concept, the latter kept OUT of
  FIELD_SPECS (so the 19-spec counts and the cross-check are unmoved) and out of the
  staleness clock (a corporate action must not move every field's freshness gate).
  own_history_restated takes the REPORT, never a bare event list — see the trap above.
- Provenance relabel — cosmetic: retire the "yfinance*" Prov source strings on live
  FMP-sourced fields (core/technicals, core/pillars, core/datatypes trajectory builders).
- BETA CROSS-CHECK — single-source gap, now load-bearing (it moves the bank lens's cost
  of equity). Sits alongside the other price/estimate-derived fields EDGAR structurally
  cannot corroborate (see the E-4 ceiling finding, now in docs/phase-archive.md). Wiring it
  lifts tripwire 3 above.
- DEGRADED-RUN WRITE GUARD (was "save_evaluation UNCONDITIONAL WRITE", FIXED in D-2
  2026-08-09): a DEGRADED run is one whose output is not a real evaluation — --fixture
  (replays recorded data) or --no-synthesis (eval with no synthesis). Both are MEASUREMENT
  routes and both used to land in production caliber.db as a side effect of merely being
  run; that is how the 189 contamination rows got in.
  THE RULE IS NOT "degraded runs may not persist" — --no-synthesis is documented as
  "pillars + store only" and that capability is KEPT. The rule is that a degraded run must
  NAME ITS DESTINATION: pass db_path (CLI --db-path), else DegradedRunWriteRefused.
  Raised BEFORE any work and deliberately OUTSIDE run_single_ticker's try/except — if the
  broad handler caught it, the refusal would persist a 'failed' row into the very database
  it protects. run_batch guards the whole batch up front. CLI exits 3 (matching
  evaluate.py's refusal code), not a traceback.
  A full live+synthesis run is NOT degraded and still defaults to production — the guard
  is not a blanket "db_path is now required".
  VERIFIED LIVE: `--fixture --no-synthesis --db-path /tmp/scratch.db` put its no_synthesis
  row in the scratch DB; caliber.db md5 unchanged at 54aa42e5.
- SECTOR ANCHOR IS EXCHANGE-SCOPED — now a D-3 AGENDA ITEM (ruling 2026-08-09): the FMP
  snapshot is published per exchange, so the same sector carries two anchors by listing
  venue — Technology/NASDAQ 48.1x (MU) vs Technology/NYSE 41.4x (NOW). ~0.33pp of yield;
  small, but an economically arbitrary term inside an anchor that would be armed. Bring
  primary-listing-convention vs cap-weighted-blend, BIAS TO SIMPLEST DEFENSIBLE; Vic rules.
- GOOG FCF yield 1.24% vs its 5.68% earnings yield (D-0, UNVERIFIED): plausible on current
  datacenter capex, but it drives GOOG's least-flattering FCF reading — one confirmation
  pass before FCF is armed. Low priority.

## FRESHNESS-WATCH — standing operational feature
Per-ticker informational line, no confidence effect, emitted on every eval past 60d from
the governing period-end. Surfaces in evaluate.py output and under the batch summary table.
Two shapes: under XBRL-LAG it says extraction-pending; otherwise it predicts the next data
date from the ISSUER'S OWN cadence + median filing lag. Degrades honestly — fixtures record
no report_date, so offline it says "(p90 lag — issuer filing history unavailable)".
Known imprecision: 53-week fiscal years add a catch-up quarter a median cadence cannot
predict, so MU's estimate lands ~7d early.

## EDGAR — recorders and fixtures
- `python -m tools.record_edgar_fixture TICKER...`, `python -m tools.record_fmp_fixture
  TICKER...`, and `python -m tools.record_fred_fixture` (no args — DGS10 is the only
  series). All three reuse the ADAPTER's own live fetch path, so a fixture cannot drift
  from what production requests (the Phase-0 probe_fmp.py did drift — it still targets the
  retired v3 API and writes keys the adapter no longer reads; treat it as dead).
  record_fred_fixture requires FRED_API_KEY and fails LOUD without it rather than writing
  a rate-less fixture — under the mandatory-rate ruling that would make every offline eval
  refuse. Re-recording the FRED fixture MOVES THE BASELINE for every valuation score, since
  the 10Y is an input to all of them.
- Re-recording MOVES THE REGRESSION BASELINE — deliberate manual step, never incidental.
  Prior files are backed up to *.json.bak (gitignored).
- Three fixture sets: tests/fixtures/edgar (all five), tests/fixtures/fmp (all five, the
  pairing production runs, and now the ONLY ticker-data fixture set), (retired: ticker/
  for the historical pipeline). Golden-five invariants run against edgar+fmp.

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
