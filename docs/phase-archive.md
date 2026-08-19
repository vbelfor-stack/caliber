# CALIBER — PHASE ARCHIVE (finished history, relocated out of CLAUDE.md)

**PURE RELOCATION, 2026-08-19, under Vic's archive-trim order. Nothing here was deleted,
summarised, reworded or reordered — every section below is BYTE-IDENTICAL to the text that
stood in CLAUDE.md at commit 570da51, and appears in the order it stood there.** CLAUDE.md
keeps the session pickup block, the standing rules, the punch lists and the live work order.
This file keeps the history behind them.

**THIS IS NOT ALL NARRATIVE — IT CARRIES LIVE-BEHAVIOUR FACTS THAT NO LONGER AUTO-LOAD.**
Read the relevant section before touching the surface it covers. Specifically: the EDGAR
ARMED SET (which fields move confidence), the permanent-advisory and dark row lists, the
`debt_to_equity` three-conventions note, the FIELD_SPECS synonym/TTM/stale-gate rulings, the
R-A alignment preconditions (re-checked every evaluation), and every Phase D ladder, gate and
withholding rule for all five lenses.

## CONTENTS (in the order they stood in CLAUDE.md)
1. PHASE H CLOSED EXCEPT H-4 — first session of 2026-08-15
2. SESSION-CLOSE NOTES — 2026-08-15 (second session), incl. the two superseded H-FCF order blocks
3. INCIDENT — 2026-08-17: production contamination from a fixture run (closed)
4. Data integrity — test-contamination purge (2026-08-07) (closed)
5. EDGAR — E-1→E-4 ALL DONE, cross-check ARMED and live
6. EDGAR — alignment semantic (R-A)
7. Phase D — VALUATION PANEL (scoped + rulings)

---

## ▶ PHASE H CLOSED EXCEPT H-4 — first session of 2026-08-15 (SUPERSEDED BY THE PICKUP BLOCK ABOVE)
Commits this session: 7a8bbf1 (H-1) · 6bdd4e8 · 8d9aa95 (D/E scale defect) · 15ab835 ·
365bc6c (fixture migration) · 3a05a4f (H-3 armed). Suite 613 -> 670. caliber.db md5
UNCHANGED 54aa42e5 throughout — no session work touched production data.
- **H-1 BUILT+DARK, H-2 RULED (by ruling 2), H-3 ARMED.** H-4 (EBITDA leg) REMAINS
  DEFERRED BEHIND EDGAR EXPANSION — no D&A spec exists among the 19, which is the same
  blocker that makes reinvestment NULL.
- **H-3 ARMED — compounder lens on the fundamental_series own-history anchor.**
  ZERO of 25 golden pillar cells moved (measured twice: offline, and against a LIVE FMP
  sector snapshot, because the fixtures carry none and WU's transition is invisible
  without one). No score -> no avg_score -> no E(R) -> no grade.
  **THE ARMING IS VISIBLE IN THE BINDING ANCHOR, NOT THE SCORE:** WU moves
  sector (+12.62pp) -> own_history (+4.22pp), an **8.40pp narrowing against a predicted
  8.37pp**. It survives at 5 only because +4.22 still clears the +3.0 top rung; a ticker
  nearer a boundary WOULD have moved. GOOG gains the anchor (-2.41) but risk-free still
  binds. V/JPM/USB have NO FCF series (no capex concept) — panel narrows to the
  market-referenced pair, nothing substituted, missing anchor NEVER scored as 0%, and the
  reading names the cause (`basis=unavailable (no_capex_tag)`).
  Pre-arm state in H3_BINDING_ANCHOR_DELTAS + an intentionally EMPTY H3_SCORE_DELTAS.
- **PRODUCTION SCORING DEFECT FOUND AND FIXED — debt/equity units (8d9aa95).** FMP
  publishes a RATIO, `score_financial_health` scores a PERCENT ladder. From the yfinance
  teardown (2026-08-07) to 2026-08-15 every issuer collected maximum leverage points and
  the component was INERT. Fixed at the adapter boundary (`_ratio_to_percent`).
  Golden diff: V and WU Financial Health 5 -> 4. WU is the validating case — ~295%
  leverage now scores ZERO where it scored maximum. ids 216-220 were scored under the
  defect and are NOT modified (points lost: MU 0, GOOG 0, V -1, NOW -1, WU -3);
  **RE-RUN ORDERED AND EXECUTED 2026-08-15 — ids 221-225 SUPERSEDE 216-220.** Terms in
  docs/orders/2026-08-15-rerun-armed-pass.md. ids 216-220 remain BYTE-IDENTICAL (verified
  against the pre-write backup); the correction is APPENDED AND LINKED, never edited in.

**RE-RUN OF THE ARMED PASS — DONE 2026-08-15. ids 221-225. Order: docs/orders/2026-08-15-rerun-armed-pass.md.**
First production write since 2026-08-09. caliber.db md5 54aa42e5 -> e13cbee6.
- **SUPERSEDE TRAIL ADDED TO `evaluations`** (ruled): `supersedes_id` INTEGER REFERENCES
  evaluations(id) + `supersede_reason` TEXT, both nullable, ADDITIVE — 31 pre-existing rows
  verified byte-identical after migration, all reading NULL. Guards raise the typed
  `SupersedeLinkInvalid` BEFORE any write: no superseding a nonexistent id, and
  `supersedes_id` requires a non-empty reason. Validated in run_single_ticker OUTSIDE the
  try/except, for the same reason DegradedRunWriteRefused is — the broad handler persists a
  'failed' row, so a link error caught in there would write junk into the DB it protects.
  run_batch validates EVERY link up front, before ticker 1. CLI: `--supersedes TICKER=ID,...`
  + `--supersede-reason`. Tests: tests/test_supersede_trail.py (12).
- **THREE EFFECT CLASSES, ruled — a re-run diff is never lumped:**
  (a) units fix, (b) H-3 armed own-history anchor, (c) EDGAR-derived LENS SELECTION.
  **CLASS (c) WAS EMPTY** — all five lenses identical then vs now (MU cyclical, GOOG/V/WU
  compounder, NOW growth), so no ticker's pillar diff is confounded and (a)/(b) attribution
  is clean. A lens change would have CONFOUNDED that ticker's whole panel; the check is
  mandatory in any future re-run.
- **ONE PILLAR CELL MOVED IN ALL 25: WU Financial Health 5 -> 4** (avg 3.6 -> 3.4), on
  class (a). D/E as scored: MU 0%->6%, GOOG 0%->18%, V 1%->68%, NOW 1%->68%, WU 3%->295%.
  Only WU crossed a rung and it now carries HIGH-LEVERAGE. **The live diff is NARROWER than
  the fixture golden diff, which showed V AND WU moving 5 -> 4 — live V was ALREADY 4 (held
  by CURRENT-RATIO-BELOW-1) and its restored -1 leverage point did not cross a boundary.**
- **CLASS (b) IS VISIBLE IN THE BINDING ANCHOR, NOT THE SCORE — as predicted.** WU's
  compounder fcf_yield binds **own_history at +3.32pp** vs sector +11.71 and risk_free
  +12.70 — an 8.39pp narrowing (predicted 8.37/8.40). **It survives at 5 with 0.32pp of
  margin over the +3.0 top rung.** WU's Valuation 5 is now the single most boundary-exposed
  cell in the golden set — a small move in FCF, price or the 10Y drops it. GOOG gains the
  anchor (-2.41pp) but risk_free still binds (-3.36pp). MU binds own_history (-1.14pp).
  **V's own-history is UNAVAILABLE FOR TWO INDEPENDENT REASONS** — earnings leg
  `basis=truncated` (2015-03-19 4:1 split, 1/3 witnesses, still REFUSED) and FCF leg
  `basis=unavailable (no_capex_tag)`. Both stated in the reading; nothing substituted.
- **DELTA AUDIT — THREE DELTAS BEYOND THE THREE THE ORDER NAMED.** Named and expected:
  evaluations +5 rows + 2 columns, `fundamental_series` created (557 rows). ALSO CHANGED,
  reported rather than absorbed: **field_provenance +105** (21/eval, a dependent of the new
  rows — save_evaluation writes them), **synthesis_cache +5** (fresh synthesis cached; NOT
  in the order's stated set), **sqlite_sequence +1** (AUTOINCREMENT bookkeeping for the new
  table). Nothing was dropped or rewritten.
- **E(R) MOVED ON ALL FIVE AND IS NOT ATTRIBUTABLE TO (a), (b) OR (c).** MU -17.56->-14.58,
  GOOG +6.09->+3.99, V +5.86->+4.01, NOW +1.62->-2.18, WU -9.60->-14.09; NOW's verdict_conf
  medium -> low. Six days of price movement plus a fresh LLM synthesis on fresh prices —
  inherent to re-running, not evidence about the fixes. **A re-run cannot produce a clean
  E(R) diff and should never be read as one.** Anchor divergence stayed healthy on all five
  (MU 0.4%, GOOG 3.9%), no trip.
- Grades table still 0 rows. Suite 670 -> 682.

## ▶ SESSION-CLOSE NOTES — 2026-08-15 (second session). NEXT ORDER: AWAITING VIC.
Commits: **1f538b9** (re-run + supersede trail + EDGAR re-ruling) + this close.
Suite 670 -> 682. **caliber.db md5 54aa42e5 -> e13cbee6 — the FIRST production write since
2026-08-09, and it was ORDERED.** Backup at the pre-write md5 kept locally.
- **THE SESSION'S ONE ORDER WAS EXECUTED IN FULL.** ids 221-225 supersede 216-220. Open
  ruling on 216-220 RESOLVED by Vic on the report.
- **PRECEDENT SET — ORDERS ARE RECORDED VERBATIM BEFORE EXECUTION.**
  `docs/orders/2026-08-15-rerun-armed-pass.md` was written BEFORE the first write, so the
  terms survive a session death mid-order. **The order text arrived TRUNCATED mid-sentence
  and was recorded truncation-and-all, with the reading Code acted under stated separately
  rather than silently completing it.** Do this again: never quietly finish a cut-off order.
- **THE SESSION-OPEN PROTOCOL PAID OFF AGAIN, cheaply.** Empirical PPID read settled
  identity in one command (PID 246, no peers) before anything touched the tree.
- **STATE-DETERMINATION BEFORE ACTION WORKED.** The wake-up prompt asked which of three
  states the tree was in; md5 + max(eval id) + suite count answered it in three commands
  (state A, never started). Cheap, and it is what made the production write safe to start.
- **TWO FINDINGS SURFACED BY PRE-FLIGHTING RATHER THAN TRUSTING RECORDED STATE:**
  1. The EDGAR 403 is INTERMITTENT, not cleared — and a `curl` probe DISAGREED with the
     adapter path seconds later. Recorded state was stale in BOTH directions within one
     session. New standing discipline: pre-flight on the adapter's own path, immediately.
  2. EDGAR IS SCORE-BEARING via SIC -> lens. Code's own order-file reasoning had asserted
     "confidence labels only"; it was wrong, was caught before the write, and the wrong
     claim is struck through IN PLACE rather than deleted. Had EDGAR 403'd mid-batch,
     `fetch_edgar` (unwrapped) would have written FIVE `failed` rows into production.
- **THE GENERAL LESSON, and it is the same shape as the last session's:** RECORDED STATE IS
  A CLAIM, NOT A MEASUREMENT. Last session it was a baseline silently doing unadvertised
  work; this session it was an environment flag that had changed underneath the note, and
  an attribution sentence in this very file that had been wrong the whole time. **Re-measure
  what a write depends on, immediately before the write, on the path production uses.**
- STANDING RULES ADDED THIS SESSION (all in the session protocol above): live-EDGAR
  pre-flight · EDGAR is score-bearing · expected-delta sets name their dependents.
- PHASE H FULLY CLOSED EXCEPT H-4 (deferred behind EDGAR expansion; the blocker is the
  MISSING D&A SPEC, not reachability). **PHASES L AND M PARKED AWAITING VIC'S CALL.**
  New tripwire `_leverage_uniformity_alarm` — advisory, warns when a whole batch sits
  under the ladder's top rung, which was the visible symptom nobody noticed for 8 days.
- **FIXTURE MODE MIGRATED TO THE FMP FIXTURES (365bc6c); yfinance remnants deleted**
  (tests/fixtures/ticker/, adapters/fixture_adapter.py, probe_fmp.py). Offline now calls
  `fetch_fmp(fixture_path=...)` — the same call production makes. The H-1 yield leg went
  0 -> 118 points across six tickers, and NOW/WU became runnable in fixture mode at all.
  Golden re-baseline, measured: GOOG compounder @10Y=0.0 valuation 3 -> 4 (source's own
  numbers: ev_to_ebitda 26.75 -> 12.91). PRE_D4_SCORES LEFT AS RECORDED; the moved cell
  lives in SOURCE_MIGRATION_DELTAS. Prov stamps now read "fmp" offline, retiring most of
  the tracked provenance-relabel follow-up.
- **LEDGER — THE ELEVEN-TEST SILENT DEPENDENCY (the session's most transferable finding).**
  The migration broke ELEVEN tests, and the breakage was the only reason a hidden
  dependency surfaced: **the legacy fixtures were a SECOND, DISAGREEING SOURCE**, and the
  EDGAR cross-check's entire conflict/downgrade path was covered ONLY because the
  yfinance-shaped recordings pre-dated the EDGAR ones and happened to diverge. Against the
  FMP payload those fields AGREE. Had the migration been done without a full-suite diff,
  the downgrade path would have gone untested SILENTLY — green suite, no signal.
  REPLACED WITH A DELIBERATE MECHANISM: `_pair_with_forced_conflict(ticker, field)` pushes
  ONE NAMED field 1.5x out of tolerance, so each test states which field conflicts and by
  how much instead of inheriting it from a stale recording. Same for the anti-launder
  downgrade test. Strictly better coverage than the accident it replaces.
  RELATED: four tests asserted alignment-gated rows are capped by absolute age. They are
  EXEMPT BY DESIGN (R-A); that was invisible only because MU's legacy fixture served
  total_cash as MRQ, revoking alignment. The FMP payload serves the FY figure.
  **THE GENERAL LESSON, twice over this session:** a baseline that disagrees with the feed
  is doing unadvertised work. Migrating a baseline onto the source it checks retires the
  check — name what is being given up before doing it.
- THREE SCHEMA-ADDENDUM RULINGS, all encoded: (1) GRAIN — native quarterly TTM + FY rows in
  ONE ISSUER-KEYED table (never evaluation-keyed), append-never-overwrite with a supersede
  trail, G-4 basis stamped; per-year is a QUERY, not a second build. (2) NEGATIVE FCF —
  persisted unfiltered with excluded=1; exclusion is a READ-TIME FILTER for the
  MIN-of-medians anchor ONLY, storage always carries the full series so Phase M keeps its
  left tail. **THIS RULES H-2.** (3) REINVESTMENT — column stored, value NULL until the D&A
  spec lands behind H-4, NO PROXY.
- **PROVENANCE — ADOPTED, NOT AUTHORED.** The build landed from an orphaned PEER SESSION
  (c2) sharing this checkout; see the SESSION-OPEN PROTOCOL below for the incident. It was
  terminated, then the build was audited line-by-line and adopted. FOUR FINDINGS FIXED
  BEFORE COMMIT:
  - F3 `exclusion_reason` was carrying BOTH "value rejected" and "value structurally
    unavailable". SPLIT: `exclusion_reason` IFF excluded=1, new `null_reason` IFF value IS
    NULL and excluded=0. Verified over 234 rows: 16/16, 48/48, ZERO carrying both.
  - F4 restatement detector ignored method/unit/components — a TTM method change at an
    identical value recorded NOTHING. Now compared; a method-only change supersedes without
    counting as a restated FIGURE.
  - F5 the `split_restated` path — the one production took — was untested. Pinned.
  - F1 **the `fcf_yield` leg, WHICH H-3 ARMS, had never produced a value anywhere** (every
    test passed price_history=[]). Now measured: GOOG 20 points, all basis=split_restated.
    THE TRAP: raw FMP fixture rows use `close`, `_price_on_or_before` reads `Close` —
    reading them raw hands every lookup a None and reproduces the hole WHILE LOOKING FIXED.
    Always go through the adapter's own fetch path.
  - **G-4's ARTIFACT IS NOW PINNED PER POINT** — GOOG 2022-03-31 restated 3.7493% vs
    truncated 74.9867%, exactly 20x. Both bases emit THE SAME COUNT of points, so a count
    comparison would have passed a broken implementation. Only 2 of 20 quarters move,
    because the share series is MIXED-BASIS (most pre-split period-ends were restated by
    later filings, so first_filed is already post-split and the factor is 1).
- **EDGAR ENVIRONMENT FLAG (accepted 2026-08-15, NOT to be worked around):** sec.gov and
  data.sec.gov return **HTTP 403 from this host** — with and without a declared User-Agent,
  sandboxed and unsandboxed, via adapter and plain curl. FMP is unaffected. Suspected
  egress-IP block. FMP is the sole live feed by standing discipline and EDGAR is the
  cross-check, so an offline fixture-recorded delivery is honest, not degraded.
  **INVESTIGATE AS A SEPARATE ENVIRONMENT TASK.** Consequence: H-1's per-ticker figures are
  fixture-recorded, and the live probe has never run.
- SECOND FIXTURE LIMITATION — **RESOLVED 2026-08-15 by the fixture migration.** Fixture
  mode now loads TickerData from tests/fixtures/fmp (the payload production fetches);
  tests/fixtures/ticker, adapters/fixture_adapter.py and the dead probe_fmp.py recorder
  are DELETED. The yield leg produces 118 points across six tickers offline, and NOW/WU
  are runnable in fixture mode for the first time. See docs/h1-series.md §9b.
- OFFLINE COVERAGE, fcf metric: MU 24 pts (8 neg, 33%), GOOG 24 (0), NOW 24 (0), WU 24 (0),
  BK 24 (4, 17%), C 21 (14, 67%); V/JPM/USB withheld `no_capex_tag` (no capex concept
  filed). Counts reconcile exactly with scoping §4c's `quarters − positive`.
- **H-3 DONE — ARMED 2026-08-15 (3a05a4f).** See the Phase-H close block above.
  NOTE `test_no_score_reads_the_series_yet` STILL PASSES and was NOT flipped: H-3 wired the
  anchor through core/valuation_anchors, not core/pillars, so the pin it makes (pillars.py
  never imports the series module directly) remains true and remains worth holding.

**(superseded) NEXT ORDER: AWAITING VIC ON THE H-FCF REPORT.** Phased plan with per-phase blast radius
in docs/h-fcf-scoping.md §5: H-1 series builder DARK (blast radius NONE) -> H-2 exclusion
ruling (NONE) -> H-3 ARM on the compounder lens (**REAL: 3 of 5 universe tickers; first H
phase that can move a score -> E(R) -> grade**) -> H-4 EBITDA leg DEFERRED behind EDGAR.
**H-X, RECOMMENDED AS A SEPARATE ORDER:** extend annual_fy to FLOW inputs and arm
free_cashflow. Blast radius CONFIDENCE LABELS ONLY, but it can DOWNGRADE (WU 28.6%).
Kept out of H deliberately — bundling would mix a confidence-only blast radius with a
score-moving one in a single arm.

**(superseded order, kept for the record) SCOPE PHASE H-FCF — REPORT ONLY. Ruled 2026-08-11.**
H-FCF = extend the own-history anchor from trailing-earnings-only to an FCF yield series.
- WHY IT IS NEXT: own-history reaches a score ONLY through the cyclical lens today (MU
  alone of the nine). An FCF own-history series gives the COMPOUNDER lens — GOOG, V, WU,
  the MAJORITY LENS — its first issuer-referenced denominator, turning MIN from a
  two-market-anchor rule into a genuine three-anchor one for most of the universe.
- CEILING NOTE (Vic, ruled): H-FCF is the MOST DIRECT PATH TO VERDICT-HIGH REACHABILITY.
  The E-4 finding pins the medium ceiling on four structural blockers; free_cashflow is
  one of them, currently PERMANENT ADVISORY on an FMP-annual-vs-EDGAR-TTM basis mismatch.
  A proper EDGAR TTM FCF series is exactly the missing basis. **VERIFY THIS AT SCOPING —
  it is the reasoning, not yet a measurement**: does an EDGAR TTM FCF resolve the basis
  mismatch enough to move free_cashflow from advisory to ARMED, and does it give the
  Valuation pillar's fcf_yield a corroborant? If yes, H-FCF closes blockers in TWO of the
  four pillars and test_verdict_high_is_still_blocked (ruling R-D, LEFT PINNED
  DELIBERATELY) becomes the signal that fires.
- FEASIBILITY ALREADY MEASURED: operating_cashflow and capex are BOTH already flow specs,
  so ttm_series works on them today — 24 overlapping quarters for MU/GOOG/NOW/WU. V has no
  capex tag (its existing accepted limit), so V gains nothing and stays 0.
- SCOPE BOUNDARY, BIAS AGAINST CREEP: the EBITDA leg is DEFERRED BEHIND EDGAR EXPANSION
  (no D&A spec, EV build-out needed, EBITDA tagging varies far more than cash-flow
  tagging). Forward-earnings own-history is worth NOTHING (no lens is anchored on it).
  H is TWO legs, and this order is the FIRST ONE ONLY.
- The report MUST state expected own-history coverage after H-FCF (today 4/20) and which
  lenses gain a discriminator, and MUST carry a blast-radius audit — unlike G, this one
  CAN move compounder scores, which is three of the golden five.
- DARK BEFORE ARM. Per-point validation, not medians (standing ruling from G).
AFTER H-FCF: G-5 (zero-with-coverage sentinels, >5x adjacent-year EPS jump) under its own
ruling — DIFFERENT DEFECT CLASS, ruled not to ride along with G. Then EDGAR expansion.

**STANDING SEQUENCE AFTER G:** EDGAR expansion resumes ONLY after G. Then the recorded
roadmap items: β cross-check, ttm_summed synthetic-only coverage, dark total_debt variants,
provenance relabel.

**SESSION PROTOCOL — non-negotiable:**
- Every close = commit + push + `git rev-list --count origin/master..master` reads 0 +
  `gh auth setup-git` re-check (the credential helper has vanished mid-session twice).
- **DEGRADED RUNS MUST NAME THEIR DESTINATION (`--db-path`) ON *BOTH* PATHS.** ~~(was
  recorded as a single rule without naming where it was enforced)~~ **CORRECTED 2026-08-17
  after a live contamination: the guard existed in `batch/runner.py` ONLY, and
  `evaluate.py --fixture` wrote to production caliber.db the whole time.** Guard locations,
  both raising `batch.runner.DegradedRunWriteRefused`:
    `batch/runner.py`  — run_batch up front, run_single_ticker OUTSIDE its try/except
    `evaluate.py`      — top of `evaluate()`, before any fetch (added L-2a)
  **AND `--db-path` MUST ROUTE EVERY WRITE, not most of them.** Partial routing is the
  mechanism that caused the incident. Enforced structurally: `save_evaluation`,
  `save_failed_evaluation`, `save_synthesis_cache` and `save_lifecycle_stage` all take
  `db_path` as a REQUIRED KEYWORD-ONLY argument — no production default to fall back to.
  Pinned by `test_the_writers_in_the_evaluate_path_have_no_production_default` and by
  `test_db_path_leaves_production_BYTE_IDENTICAL_across_a_whole_evaluate_run`.
  STILL DEFAULTED, DELIBERATELY — **each with its reason, because a list of exceptions
  without reasons decays into a list nobody dares shrink** (ruled 2026-08-17). Changing any
  of these is its own order:
    `init_db`               web/app.py:48 calls it argument-less at import to guarantee the
                            UI's tables exist; there is no request context to name a path.
    `save_override`         web/app.py:451 — a human accepting a field override in the UI IS
                            a production act; the UI has exactly one database by design.
    `save_grade`            core/grading.py (4 sites) — grading reads production evaluations
                            and writes production grades; a grade about a production row
                            belongs nowhere else.
    `save_lifecycle_override` written only by Vic, deliberately, one ticker at a time. No
                            automated path reaches it, so a forgotten argument cannot happen
                            in a loop. **Carries the identical exposure and is the first
                            candidate if the class is closed further.**
- DARK BEFORE ARM on any new comparison surface.
- Golden diffs are REVIEWED, never asserted.
- **EXPECTED-DELTA SETS NAME THEIR DEPENDENTS (standing, ruled 2026-08-15).** A
  production-write order states the FULL expected-delta set, INCLUDING dependent tables, so
  the post-write confirmation can distinguish an EXPECTED-DEPENDENT delta from a SURPRISE.
  **Expected companions of ANY live evaluation write** — never a finding on their own:
    `field_provenance`   +N rows per eval (save_evaluation writes them with the row)
    `synthesis_cache`    +1 per ticker synthesised (save_synthesis_cache)
    `sqlite_sequence`    +1 per NEW AUTOINCREMENT table created that run
  Anything OUTSIDE the stated set plus these three is REPORTED, NEVER ABSORBED. Origin: the
  2026-08-15 re-run order named three deltas and the write produced six; all three extras
  were benign dependents, but "benign" was a judgement made AFTER the fact, which is exactly
  the judgement an expected-delta set exists to make BEFOREHAND.
- **LIVE-EDGAR PRE-FLIGHT (standing discipline, ruled 2026-08-15).** Any run that will hit
  live EDGAR PRE-FLIGHTS ALL REQUIRED ENDPOINTS ON THE ADAPTER'S OWN FETCH PATH IMMEDIATELY
  BEFORE THE RUN. **A STALE PROBE IS NOT A PRE-FLIGHT.** EDGAR reachability is INTERMITTENT,
  measured within a single session: both endpoints 200 at open, `www.sec.gov` 403 ~20min
  later while `data.sec.gov` stayed 200, then all five golden CIKs and all five
  `fetch_edgar` calls clean on the adapter path. A plain `curl` probe DISAGREED with the
  adapter path seconds later — which is why the pre-flight must use the adapter, not curl.
  Hard-fail semantics are UNCHANGED and deliberately so: `fetch_edgar` is NOT wrapped in
  `run_single_ticker`, so a mid-batch 403 raises into the broad handler and persists a
  `failed` row PER TICKER. Five failed rows in production is exactly what loud-failure
  discipline exists to prevent; the pre-flight is the mechanism that prevents it.
  See docs/h1-series.md §9a (which supersedes the flat "EDGAR unreachable" flag).
- **EDGAR IS SCORE-BEARING, NOT CONFIDENCE-ONLY (correction, ruled 2026-08-15).** The
  cross-check `apply_report` touches confidence labels and source strings only — but
  batch/runner.py separately does `yf.sic = edgar.sic; lens = select_lens(...)`. **EDGAR
  SELECTS THE LENS AND THE LENS MOVES SCORES.** Any claim that an EDGAR failure can only
  move a confidence label is WRONG. Blast radius of an EDGAR outage is a REFUSED
  evaluation, not a degraded one. Consequence for any re-run diff: lens-selection is its
  own effect class, and a ticker whose lens changed between passes has a CONFOUNDED pillar
  diff that must not be attributed to any other cause.

## ▶ INCIDENT — 2026-08-17: PRODUCTION CONTAMINATION FROM A FIXTURE RUN (closed)
**3 evaluations + 63 field_provenance rows written to production caliber.db, then purged
under ruling.** Recorded here because the cause was a rule that looked enforced and wasn't.
- **What:** ids **226, 227, 228** — three MU rows, `status='ok'`, `avg_score` 4.2, with
  `expected_return` values, from three `python evaluate.py MU --fixture --db-path
  /tmp/step1.db` debugging runs at 19:50–19:52. Fixture pillars stapled to a synthesis
  pulled from the 2026-08-15 MU `synthesis_cache` row — **chimeras that would have become
  GRADEABLE in 90 days** and entered the grading set as real evaluations.
- **Cause:** `--db-path` was newly added to `evaluate.py` for §5 step 1 and routed **only
  the lifecycle write**; `save_evaluation` kept its production default. The flag read as
  "this run writes here" and did not cover the run's main write. Code ran it believing it
  was sandboxed without verifying what the flag covered. Compounding it: `evaluate.py` had
  **never** had a degraded-run guard — the D-2 work was batch-only.
- **Resolution:** purged in a single transaction with an exact blast-radius assertion
  (3 ids + 63 provenance rows, else ROLLBACK) — the 2026-08-07 precedent. Verified after:
  evaluations 36, max id 225, field_provenance 525, nothing in 226–228, grading-set query
  clean. Backup of the contaminated state kept at `caliber.db.contaminated-2026-08-17-
  195e6687.bak` until step 1's sanctioned run is verified, **then deleted** (a contaminated
  backup outliving its purpose is its own hazard).
- **md5 trail:** `e13cbee6` (pre-incident) → `195e6687` (contaminated) → **`e5f337b8`**
  (post-purge). It does NOT return to `e13cbee6`: the three `lifecycle_*` tables created by
  `init_db` at 19:50 were **unsanctioned but are RETAINED BY RULING** at 0 rows, because
  step 1 creates them sanctioned within the hour and dropping them would add a destructive
  step for cosmetic md5 purity.
- **SECOND LEAK FOUND WHILE FIXING, never triggered:** `batch/runner.py` called
  `save_synthesis_cache` **without `db_path`**, so a `--fixture --db-path scratch.db` batch
  run would have routed its evaluation to the scratch DB and its synthesis cache to
  PRODUCTION. It was never caught because the one live verification of that flag
  (2026-08-09) used `--no-synthesis`, which writes no cache row. Fixed in L-2a.
- **THE LESSON, and it is a new one:** the standing rules said degraded runs must name their
  destination, and that sentence was true of the batch path and false of the interactive
  one. **A rule recorded without naming its enforcement point is a belief, not a guard.**
  Every guard entry in this file now names the file it lives in.
- **AND THE SECOND LESSON, from the batch leak (ruled worth recording 2026-08-17):**
  **A FLAG VERIFICATION ONLY COVERS THE WRITES THE VERIFYING RUN ACTUALLY PERFORMS.** The
  2026-08-09 `--db-path` verification passed honestly and proved nothing about
  `save_synthesis_cache`, because `--no-synthesis` meant the leaking write never executed.
  When verifying a routing flag, enumerate every write the path CAN make and make the
  verifying run perform all of them.
- **AUDIT, 2026-08-17 — NO CONTAMINATED `synthesis_cache` ROWS EXIST. Closed.** Question
  asked: did any batch run between 2026-08-09 and today execute `--fixture` WITH synthesis?
  **Answer: no**, on three independent measurements. (a) ORPHAN TEST: all 16 cache rows have
  a matching production evaluation for the same ticker+date — a `--fixture --db-path` run
  would by construction leave a cache row with its evaluation in the scratch DB, i.e. an
  orphan; there are none. (b) The only post-08-09 cache rows are the five from the sanctioned
  live re-run of 2026-08-15, and every price is a LIVE value differing from the fixture value
  (GOOG 343.54 vs 343, MU 971.66 vs 979.3, NOW 124.0 vs 127.54, V 364.15 vs 348.97,
  WU 7.45 vs 7.08). (c) The only `--fixture` batch invocation in the repo record is
  `--fixture --no-synthesis --db-path /tmp/h1_scratch.db` (docs/h1-series.md:191), which
  writes no cache row. **RED HERRING, named so nobody re-opens it:** cache row
  `V 2026-07-12 price=348.97` matches V's fixture price EXACTLY — but it predates both the
  window and D-2's `--db-path` (before which everything went to production by design), it has
  a matching production evaluation from the documented genuine live session, and V's fixture
  was recorded in that era. Coincidence, explained.

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

## EDGAR — E-1→E-4 ALL DONE (2026-08-08/09). Cross-check ARMED and live.
Purpose: EDGAR is the wired SECOND source. It makes "high" confidence reachable again.
It did NOT revive the anti-launder NOTE — see the E-4 ceiling finding.
- E-1 6977a72 · E-2 25b40c5 · E-3 built 0df4e6d, basis-aligned 8d9bd07, ARMED 031506f
  · E-4 5f62e96. Rulings: R1 e2d53f2 · R-NEW 8e657a9 · R3 dark 539c998 · R-A 36ad838
  · R-C 3a4ec18 · R-B dark b2dcc30.
- ARMED SET (moves confidence): gross_margin, operating_margin, profit_margin, roe, roa,
  current_ratio, shares_outstanding, total_cash@FY. agree→high, conflict→low.
- **debt_to_equity CARRIES THREE CONVENTIONS — they live here together deliberately:**
  (a) DEFINITION: FMP is NET of cash, EDGAR/yfinance gross. No period matching fixes it;
      this is the permanent-advisory reason below.
  (b) SCALE: FMP publishes a RATIO, the pillar ladder is PERCENT. (b) WAS A LIVE SCORING
      DEFECT 2026-08-07 -> 2026-08-15, FIXED at the adapter boundary (`_ratio_to_percent`,
      commit 8d9aa95). Fixing (b) does NOT resolve (a).
  (c) CROSS-CHECK UNITS: core/edgar_cross_check's debt_to_equity comparison computes the
      EDGAR side x100 so BOTH SIDES SPEAK PERCENT. RULED KEEP 2026-08-15. Without it the
      row reported a units artifact on every ticker (~99% everywhere); with it the row
      shows only the genuine net-vs-gross gap — MU 47.8%, GOOG 21.9%, **V 0.0% (exact
      agreement)**. That is the advisory row doing its job. Row stays permanent-advisory:
      it moves no confidence and no score either way.
- PERMANENT ADVISORY (measured, logged, never applied — declared basis mismatch):
  total_cash (MRQ), total_debt (MRQ), debt_to_equity (FMP is NET of cash, EDGAR gross),
  operating_cashflow and free_cashflow (FMP annual, EDGAR TTM).
- DARK (computed and logged, applied to nothing): total_debt@FY, total_debt(reported).
- Rows are keyed by LABEL, not field: one FMP field may carry several rows. If two ARMED
  rows disagree about a field, apply_report applies NEITHER and logs "!CONTRADICTION" —
  resolving by row order would be silent degradation.
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
  - Coverage now 19 specs (E-2 shipped 16; +short_term_investments, +total_debt_reported,
    +operating_lease_liability): MU 19/19, GOOG 18/19, NOW 18/19, WU 15/19, V 14/19.
    V's gaps are ACCEPTED DATA LIMITS: no cost-of-revenue or capex concept filed
    (no_tag x2), gross profit therefore underivable (derive_incomplete), share count and
    ST-investments stale with no fallback. Consequence: V gets no gross-margin and no FCF
    cross-check. Zero synonym conflicts on the golden CIKs.
  - conflict_check=False marks chains holding DISTINCT-but-substitutable measures, where
    priority order decides and disagreement is expected rather than ambiguous: revenue
    (total Revenues vs the ASC 606 subset — WU files both), current_debt
    (ShortTermBorrowings vs its CommercialPaper component — NOW files both),
    short_term_investments, total_debt_reported. The gate stays ARMED for genuinely
    ambiguous chains (equity), tested directly.
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
  - RESOLVED by R1 (symmetric gating, e2d53f2).
- R1 SYMMETRIC GATING (ruling 2026-08-08, DONE): a source too stale to RAISE confidence is
  too stale to LOWER it. Stale/lagged data renders stale_capped and moves nothing either
  way; the divergence is still logged with the suppressed direction named. The staleness
  engine is reused, PROBED with a synthetic 'high' since it only caps that level.
- R-NEW FRESHNESS-WATCH (DONE, 8e657a9): informational line past 60d with the predicted
  next-data date from the ISSUER'S OWN cadence + median filing lag (golden five: MU 32d,
  GOOG 30d, V 33d, NOW 27d, WU 40d). Under XBRL-LAG it says extraction-pending instead of
  predicting a filing that already happened. No confidence effect. Cadence is measured on
  ONE core balance-sheet concept — pooling all instants poisons it with dei cover-page
  dates (read MU's quarters as 77d, not 91d).
- E-3 ARMED 2026-08-09 (031506f). agree→high, conflict→low (both under R1's gate);
  basis_mismatch/stale_capped/no_edgar/no_fmp move nothing. compute_cross_check stays PURE;
  apply_report is the only writer, and it touches the confidence LABEL and source string
  only — values and as_of are asserted unchanged. Exception containment kept: a failure
  degrades to the pre-EDGAR state (everything 'medium', the safe direction) and says so.
- LIVE ARMED PASS 2026-08-09, ids 216-220 (MU/GOOG/V/NOW/WU, all status=ok). Fields applied
  MU 7, GOOG 7, NOW 7, WU 6, V 0 (V fully suppressed by XBRL-LAG — R1 working live).
  'high' persisted in field_provenance for the first time since the AV teardown.
  Controlled A/B on the same live data (armed vs unarmed): pillar SCORES identical on all
  five, so E(R) and grades are provably untouched; grades table still 0 rows.
- E-4 FINDING (2026-08-09): the anti-launder NOTE is STILL UNFIRABLE. The chain is
  EDGAR agreement → field high → pillar high → verdict high → NOTE. EDGAR restored it to
  PILLAR level (Business Quality reaches high under full corroboration) but the verdict is
  min-across-five-pillars, and four pillars carry material inputs EDGAR structurally cannot
  corroborate: Financial Health (debt_to_equity NET-vs-gross, free_cashflow annual-vs-TTM,
  total_cash/total_debt annual-vs-MRQ), Management (earnings_history, insider_transactions
  — hardcoded medium), Growth (revenue_growth, trailing/forward PE, analyst_count — price
  and estimate derived), Valuation (fcf_yield, ev_to_ebitda, revenue_growth). NOTE the
  FRED rate was never a real blocker — it read LOW only in the offline fixture, which
  recorded no value. D-2 FIXED THAT: the fixture now carries 4.69 at HIGH, matching live,
  so the artifact is gone. Confirmed by re-running the chain after D-2 — the verdict is
  still blocked, by the FOUR STRUCTURAL blockers above and nothing else.
  tests/test_anti_launder_revival.py walks the chain and pins the blockers; its
  test_verdict_high_is_still_blocked is EXPECTED TO FAIL when coverage expands — that
  failure is the signal the note has become firable. LEAVE IT PINNED (ruling R-D).
  Arming total_cash@FY closed 1 of Financial Health's 4 blockers.
  THE MEDIUM CEILING IS THE HEADLINE: verdict_conf tops out at medium on every real eval,
  so a high-confidence miss cannot be flagged. Closing it needs a second source for
  price/estimate-derived fields, which EDGAR is not.

## EDGAR — alignment semantic (R-A, approved 2026-08-09, SCOPED)
A matched-period row is aged on ALIGNMENT (gap between the two sides' periods, zero by
construction) instead of absolute age: a correctly-labelled annual figure corroborating an
annual FMP field launders nothing. Without it, every matched row would render stale_capped
(an annual period is up to a year old by definition) and could never be a real test.
Valid ONLY while all three hold — and the third is RE-CHECKED EVERY EVALUATION, not trusted:
  1. periods matched         — period_basis == 'annual_fy'
  2. bases proven identical  — a missing aligning input makes the row advisory BEFORE the
                               gate is reached (V and WU: no ST-investment tag → cash-only)
  3. the primary's IN-USE value is still the matched-period figure — _tracks_matched_period
     asks which of two EDGAR PERIODS the FMP value tracks (not whether it agrees, which
     would be circular). Fails CLOSED when the two periods are indistinguishable.
XBRL-LAG still applies, scoped to what can invalidate a matched pair: a 10-K covering a
LATER fiscal year caps the row; a quarterly lag does not.
Caught in practice twice already: MU's recorded ticker fixture serves total_cash as MRQ
(alignment revoked, row capped), and V's lease-inclusive debt drifted away from FMP under
R-B (alignment revoked rather than reporting a false disagreement).

## Phase D — VALUATION PANEL (scoped + rulings 2026-08-09)
Ethos rule 10 ("judge multiples relative to the risk-free regime") is one-fifth built:
_valuation_compounder scores an FCF-yield-vs-10Y spread; cyclical, bank, growth and
standard use FIXED ABSOLUTE ladders and only PRINT the rate. A 22x multiple scores the
same at a 1% and a 7% 10Y.
- FRAMING RULING: not a "floor" — a PANEL. "Cheap" needs a denominator and there is no
  single safe one. THREE anchors, each answering a different question:
    risk-free (FRED 10Y)   — should I own equities at all?      blind to market-wide re-rating
    sector P/E (FMP)       — is this the better equity?          blind to whole-market bubbles
    own history            — cheap vs what it usually trades at? blind to structural re-ratings
- WHY A PANEL, not a pick: MU at the 2018 cycle peak was cheap on trailing P/E, cheap vs
  its own history AND cheap vs semis. Three anchors said buy; only the margin-trajectory
  read caught that the E was about to halve. The anchors are independent checks and their
  DISAGREEMENT IS THE SIGNAL.
- AGGREGATION — RULED 2026-08-09, LOCKED PERMANENT: MIN across available anchors.
  PRINCIPLE ON RECORD: never look cheaper than your least flattering defensible
  denominator.
  MEDIAN REJECTED on D-0 evidence: both times median would flip a verdict (WU, and MU on
  trailing), it does so by discarding own-history exactly when it DISSENTS — and that
  dissent is the discriminator. Own history is structurally the minority anchor, so a
  median throws it away precisely when it is carrying the signal.
  BINDING CONDITIONS (both mandatory):
  1. ANCHOR COUNT is recorded per reading; a 2-anchor panel is flagged NARROWED. When the
     missing anchor is own-history, the surviving pair (risk-free + sector) is TWO
     MARKET-REFERENCED denominators — not two independent checks. D-3 ladder proposals
     MUST include a mechanism treating independence-narrowed panels more conservatively.
     Propose at D-3; VIC RULES. (Own history is trailing-only, so forward/FCF/EBITDA are
     2-anchor everywhere — this is the common case, not the exception.)
  2. DISPERSION stays a REPORTED FLAG, never an aggregation input. On 3 of 4 metrics it is
     currently just |risk_free - sector| and therefore metric-invariant; "dispersion is the
     signal" holds on trailing earnings only.
- MISSING ANCHORS: the panel narrows and provenance says so — EXCEPT the rate anchor,
  which is MANDATORY. No FRED rate → the valuation pillar REFUSES TO SCORE, loudly. No
  rate-blind scoring (that is silent degradation).
- PEER ANCHOR — REJECTED 2026-08-09, on evidence. FMP `stock-peers` resolves, 8-10 names,
  but the competitive sets are WRONG: V -> ALLY/AXP/BAC/JPM/MA/PYPL/SEZL/SLM (one true
  comp, the rest are LENDERS — V takes no credit risk); WU -> BFH/BHF/ENVA/NMIH/TBBK/WSBC
  (subprime lenders and insurers, not money transfer); MU -> AMAT/ARM/CRM/CSCO/IBM/KLAC/
  LRCX/QCOM/SAP/TXN (equipment and enterprise software; the real comps, Samsung and SK
  Hynix, are foreign filers and absent). A wrong-competitive-set anchor MANUFACTURES FALSE
  CORROBORATION, which is worse than no anchor. Cost compounds it: peers return price and
  market cap only, so peer multiples would need 8-10 extra ratios-ttm calls per eval.
  Peers re-enter ONLY with hand-curated per-ticker lists — Vic's call later, never an
  adapter's inference.
- PHASES (STOP between each; dark before arm):
  D-0 DONE 2026-08-09 (e963a01). Report: docs/d0-panel.md, re-runnable via
      `python -m tools.probe_valuation_panel MU GOOG V NOW WU --json OUT`. The probe is
      READ-ONLY BY CONSTRUCTION — it never imports batch.runner or store.models, pinned
      three ways in tests/test_d0_probe_readonly.py (subprocess import closure, AST
      imports, AST calls). Live run left caliber.db byte-identical.
      HEADLINES: MU reproduced the founding case on first measurement — the set's only
      three-anchor split, cheap vs 10Y (+0.42pp) and sector (+3.03pp), RICH vs own history
      (-0.65pp), while its FORWARD yield of 30.16% reads +25/+28pp cheap with all anchors
      agreeing (at a cycle peak the forward E is the number that lies). WU is the decisive
      case: +12.97/+12.03/+13.54/+18.82pp cheap on every market-referenced denominator and
      +1.38pp vs its own ~6x history — own-history strips 11.6pp off a screening buy.
      Own-history covers 3 of 5 and for DIFFERENT reasons: V has no share series at all
      (accepted data limit), NOW is split-truncated (Phase G dependency). Since MIN's value
      concentrates in the worst-covered anchor, Phase G is worth more than its current
      placement behind EDGAR suggests.
  D-1 DONE 2026-08-09. Shared rate-anchoring helper extracted to core/valuation_anchors:
      RATE_SPREAD_LADDER + score_yield_spread() -> SpreadScore(spread, score, anchor,
      flags). _valuation_compounder consumes it; the inline ladder is GONE (asserted by
      test_d1_no_duplicate_ladder_left_in_pillars, which fails if a copy reappears).
      Shaped for MIN: min(readings, key=lambda s: s.spread), and each reading carries its
      ANCHOR so a NARROWED panel stays detectable per binding condition 1.
      flag_scope is parameterised so D-3's sector/own-history rungs name their own
      denominator (RICH-VS-SECTOR etc.) instead of all reading RISK-FREE.
      ZERO BEHAVIOUR CHANGE, MEASURED not assumed: 180-row sweep across every ladder rung
      and both growth branches + the golden fixtures captured BEFORE the edit and replayed
      after — score, flags, rationale, confidence and method identical on all 186. Golden
      values pinned permanently in test_pillars.GOLDEN_VALUATION (MU 2/2, GOOG 3@0% and
      1@4.69%, V 5@0% and 2@4.69%). Suite 496 passed. caliber.db md5 unchanged.
      NOT DONE HERE (deliberate, D-3's job): the other four lenses still use FIXED
      ABSOLUTE ladders and only PRINT the rate. Only the compounder was ever spread-based;
      extracting one helper does not make the others rate-aware.
  D-2 DONE 2026-08-09. Three items:
      (1) FRED FIXTURE RE-RECORDED with a real rate — 4.69% as_of 2026-08-06, conf high.
          Offline runs are no longer rate-blind. New recorder tools/record_fred_fixture.py
          follows the FMP/EDGAR discipline: fred_adapter.fetch_payload() is now the shared
          production fetch path (REST/Strategy B), the recorder captures it verbatim, and
          _from_fixture parses it back through the same _parse_observations the live path
          uses — so a fixture cannot drift from what production requests. The pre-D-2
          probe shape (no 'observations' key) now raises a LOUD "predates D-2" error
          instead of silently replaying a missing rate. FRED writes '.' for non-trading
          days; that is never coerced to 0.0 (a 0% risk-free makes everything look cheap).
      (2) MANDATORY RATE ARMED — see the hard-stop entry above. NEW STATUS
          'rate_unavailable' added to the evaluations enum. It does NOT compose with an
          existing one: 'failed' means operational DOA (something raised), while this is a
          POLICY REFUSAL where the pipeline worked and declined. Filing a refusal as a
          crash would hide the policy from the audit trail. Persisted via
          save_failed_evaluation(status=...), whose statuses are now a closed set
          (_NON_COMPLETING_STATUSES) — an unknown status raises rather than writing an
          unqueryable row. TickerResult.status stays 'failed' (no pillars were produced,
          nothing is usable); eval_status carries 'rate_unavailable'.
      (3) save_evaluation UNCONDITIONAL WRITE — FIXED. See the DEGRADED-RUN rule below.
      Test movement 496 -> 519 (+23, all in tests/test_d2_mandatory_rate.py). No test was
      removed; 15 in test_batch.py were MODIFIED to name a db_path, because they were
      exercising the exact route the new guard blocks — that file was the original
      contamination source, so it relying on conftest's backstop was the smell.
  D-3 DONE 2026-08-09 + ALL SEVEN RULINGS ISSUED. Report docs/d3-lenses.md (+ .json).
      RULINGS (permanent unless re-ruled):
      1. COMPOUNDER — confirmed as-is. ARMED at D-4.
      2. CYCLICAL — TRAILING basis + hard gate as a CAP AT 2. ARMED at D-4. Rationale on
         record: forward unanimity at a cycle peak is the 2018 signature; the gate sets
         the FAILURE MODE because peak-margin denominators invalidate rung geometry.
      3. GROWTH — panel mapping REJECTED PERMANENTLY. PRINCIPLE ON RECORD: LENSES KEEP
         THEIR INSTRUMENTS, THE RATE SHIFTS THRESHOLDS, NOT MEASURES. Growth does NOT
         arm at D-4. Rate-shifted EV/Rev dark pass APPROVED and DONE — see D-4 below.
      4. STANDARD — ARMED at D-4 WITH A TRIPWIRE: the FIRST production eval scoring
         through the standard lens is reported to Vic with its full panel readout before
         its result is treated as validated. No golden ticker is natively standard-lens,
         so that first live case is the only real evidence the mapping will have had.
      5. BANK — mechanism RULED: P/B vs justified P/B = ROE/CoE, CoE = 10Y + beta x ERP.
         NOT ARMED. JPM added as sixth golden ticker (see D-4). Bank arms only after a
         calibration report and a further ruling.
      6. INDEPENDENCE-NARROWED — FLAG ONLY, no score effect. Rationale: 17 of 20 readings
         (85%) were independence-narrowed, so a haircut would be a global ladder
         recalibration through a side door, not a degraded-case adjustment.
      7. EXCHANGE-SCOPED SECTOR P/E — PRIMARY-LISTING CONVENTION, documented.
         REVISIT TRIGGER ON RECORD: any golden spread landing within 0.33pp of a rung
         boundary. (Today none does; the artifact flips zero scores.)
  D-4 DONE 2026-08-09 — ARMED compounder + cyclical + standard. Report docs/d4-arming.md,
      records docs/d4-diff.json (before/after, 25 cells) + docs/d4-arming.json.
      REVIEWED DIFF: 3 of 25 cells moved, and ALL FIVE NATIVE CELLS ARE UNCHANGED. Every
      move is a counterfactual forced-lens cell (NOW cyclical 2->1, NOW standard 1->2,
      WU cyclical 5->4). NO E(R) AND NO GRADE MOVES FROM THIS ARMING.
      What changed without crossing a rung: MU cyclical now BINDS ON OWN_HISTORY
      (-0.65pp) — the founding case, with the peak gate capping at 2 on top; V and WU
      compounder bind on SECTOR (were risk-free-only); WU compounder now carries
      SECULAR-DECLINE-FCF-YIELD at a sector-bound +12.61pp.
      Offline fixture baseline: scores unchanged, gained PANEL-NARROWED-MARKET-ONLY
      (fixture calls have no sector snapshot / no EDGAR, so armed lenses fall back to a
      risk-free-only panel and the flag is that fallback declaring itself). PRE_D4_SCORES
      kept in tests/test_pillars.py so the diff stays auditable from the test file.
      BUG FOUND AND FIXED WHILE ARMING: threading the panel from the boundaries left
      panel=None for DIRECT callers of a lens function, and the compounder then skipped
      its whole FCF branch and silently dropped SECULAR-DECLINE-FCF-YIELD. The
      risk-free-only fallback now lives inside _panel_score, so a lens behaves the same
      whether entered through the dispatcher or called directly.
      RENAME: run_dark_panel -> build_panel. It is load-bearing now (armed lenses score
      off it) and its broad except no longer claims "evaluation unaffected" — it says it
      degrades to risk-free-only, which is flagged, never rate-blind.
      GROWTH DARK PASS (ruling 3) — NOT ARMED, awaiting Vic. Mechanism: EV/Rev thresholds
      multiplied by k = (R0 + ERP) / (R + ERP), R0=4.0, ERP=4.5, clamped [0.60, 1.80].
      Delta ZERO on all five at the live 4.69% (k=0.925), but genuinely rate-sensitive:
      at ZIRP every name gains a rung; above 6% NOW falls to the floor; WU invariant
      (0.88x EV/Rev is cheap in any regime). OPEN QUESTION FOR THE RULING: R0=4.0 is a
      JUDGEMENT, not a measurement — it sets where k=1.
  D-5 (2026-08-09) — GROWTH ARMED + JPM CHAIN MIGRATION + BANK CALIBRATION.
      Report docs/d5-banks.md, record docs/d5-bank-calibration.json.
      GROWTH ARMED on the rate-shifted EV/Rev mechanism. R0 = 4.0 RATIFIED PROVISIONALLY
      (the fixed ladder was implicitly calibrated in a ~4% regime, so 4.0 as the k=1 point
      preserves its meaning). CLAMP [0.60, 1.80] LOCKED. REVISIT TRIGGER: 10Y OUTSIDE 3-6%.
      Golden-five growth diff re-measured: DELTA 0 on all five at k=0.925. A
      RATE-SHIFT-CLAMPED flag fires if the clamp ever binds — past that point the shift is
      no longer a smooth function of the rate and that must be visible.
      NOTE ARMED_LENSES vs ARMED_PANEL_LENSES are DELIBERATELY DIFFERENT SETS: growth is
      armed but RATE-anchored, not PANEL-anchored.
      JPM CHAIN MIGRATION EXECUTED. cash: +CashAndDueFromBanks (appended SECOND so the
      generic tag still wins for every non-bank). The other migration target,
      LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities, was chained on
      total_debt_reported and NOT on long_term_debt — it INCLUDES CURRENT MATURITIES, so
      it is a debt TOTAL; putting it on long_term_debt would conflate two bases and then
      double-count the current portion against current_debt. CONSEQUENCE: JPM's
      long_term_debt stays WITHHELD (it files no non-current-only tag). Pinned by test.
      GOLDEN-FIVE VERIFIED UNCHANGED — LIVE, not by fixture. The fixture check was
      MISLEADING (golden fixtures predate the new tags so they cannot contain them). Live:
      MU 19/19, GOOG 18/19, V 14/19, NOW 18/19, WU 15/19 — no resolution changed. GOOG
      does file the new debt tag but its newest fact is 2024-09-30 (~639d), so the 450d
      stale gate withholds it; its REASON moves no_tag -> stale_tag, which is strictly
      more accurate. total_debt_reported is DARK anyway. JPM 9/19 -> 11/19.
      The expected-fail pin fired and was FLIPPED to test_jpm_cash_resolves_through_the_
      bank_tag.
  D-6 (2026-08-09) — BANK ARMED. PHASE D CLOSED. Report docs/d5-banks.md.
      LADDER RULED ON THE RATIO (P/B / justified P/B), NOT the difference —
      scale-dependence rationale adopted: JPM +0.70 and BK +0.68 are indistinguishable on
      the difference but sit at 1.36x and 1.45x on the ratio, and +0.70 is 36% of JPM's
      justified 1.96 but would be 80% of C's 0.87.
      Rungs: <0.85 -> 5, <1.05 -> 4, <1.25 -> 3, <1.50 -> 2, else 1.
      EXCESS-ROE GATE ADOPTED (excess ROE < 0 -> CAP AT 3), mirroring the cyclical peak
      gate: a low P/B on a bank not covering its cost of equity is cheap FOR A REASON, and
      no rung geometry over the price can say the denominator is impaired.
      ARMED FOUR-BANK DIFF, reviewed: JPM 2->2, BK 2->2, USB 3->3, C 4->3. ONE CELL MOVED
      AND IT IS THE VALIDATING CASE — C screened 4 (cheap) on the old raw P/B ladder at
      1.08x book; armed it scores 3 with ROE-BELOW-COST-OF-EQUITY. The bank value trap,
      caught by the instrument that was built for it.
      WITHHOLDING RULE: if ROE or beta is missing there is no justified P/B, so the lens
      reports P/B and REFUSES to score off it (BANK-INSTRUMENT-UNAVAILABLE). Falling back
      to a raw P/B ladder would be the exact screen this work replaced.
      CODICIL 3 (recorded, nothing to implement): C's period-end lags two quarters; R1
      symmetric gating applies normally on a live C run — acceptable for rung-setting,
      stale-capped live.
      SEC_TICKER_ALIASES DESIGN RATIFIED: explicit per-issuer, never a name match, because
      pairing a wrong CIK crosses one issuer's fundamentals with another's price.
      EQUITY-CONFLICT GATE firing on 3 of 4 banks is THE GATE WORKING — on record.
  BANK CALIBRATION UNIVERSE (ruled 2026-08-09): JPM + BK + USB + C. ALL FOUR ARE
      CALIBRATION INSTRUMENTS, NEVER HOLDINGS — CALIBRATION_CIKS, pinned absent from
      tickers.txt for every one of them. All four select the bank lens (SIC 602x).
      NEW INTEGRATION FINDING — SEC_TICKER_ALIASES: BK could not be onboarded at all.
      BNY Mellon trades as BK and FMP serves it that way, but SEC's company_tickers.json
      lists BNY (CIK 1390777) after the 2024 rebrand. The alias map is EXPLICIT per-issuer
      — never a fuzzy name match, which could pair the wrong CIK and cross one issuer's
      fundamentals with another's price.
      E-2 COVERAGE: JPM 11/19, BK 11/19, USB 10/19, C 11/19.
      SYSTEMATIC FINDING — the equity conflict gate fires on 3 of 4 banks (BK 1.3%, USB
      0.7%, C 0.7% between StockholdersEquity and the including-NCI variant). Banks carry
      minority interests routinely, so both tags are fresh and genuinely disagree. The
      gate is deliberately ARMED on equity, so this is it WORKING. It does not block the
      bank instrument, which takes ROE from FMP. JPM files only one tag.
      C's latest period-end is 2025-12-31, TWO QUARTERS behind the others — R1 symmetric
      gating would treat it as lagged on a live run.
      BANK INSTRUMENT CALIBRATED on four points. RECOMMENDATION AWAITING RULING: put the
      ladder on the RATIO (P/B / justified P/B), NOT the ruled DIFFERENCE. Evidence: JPM
      +0.70 and BK +0.68 are indistinguishable on the difference but sit at 1.36x and
      1.45x of justified; the difference is scale-dependent in the justified value (+0.70
      is 36% on JPM's 1.96 but would be 80% on C's 0.87). Proposed rungs on r:
      <0.85 -> 5, <1.05 -> 4, <1.25 -> 3, <1.50 -> 2, else 1, PLUS an EXCESS-ROE GATE
      (excess ROE < 0 -> cap 3), same shape as the cyclical peak gate.
      HEADLINE: C trades at 1.08x BOOK but 1.24x JUSTIFIED book because its ROE (8.39%)
      does not cover its CoE (9.65%) — cheap on book, dear on what it earns. The bank
      value trap, caught.
      LIMITS ON RECORD: the gate does not bite on today's four (C is already 3 on ratio
      alone) — it is tested synthetically only; NO bank in the set trades below justified
      book, so the 5 and 4 RUNGS ARE UNCALIBRATED; four points cannot validate five rungs;
      beta is FMP single-source and moves CoE directly with no cross-check.
      BANK REMAINS UNARMED, pinned by test_bank_lens_is_still_not_armed.
  JPM — SIXTH GOLDEN TICKER, BANK-LENS CALIBRATION INSTRUMENT (ruled 2026-08-09).
      CIK 0000019617, SIC 6021, NYSE. Lens confirmed 'bank'. EXPLICITLY NOT A HOLDING:
      absent from tickers.txt on purpose and PINNED so by
      test_jpm_is_not_in_the_batch_universe. Lives in CALIBRATION_CIKS, held to
      resolved-xor-reason but NOT to test_core_fields_resolve.
      E-2 ONBOARDING: 9/19 resolved. TWO TAG MIGRATIONS FOUND (actionable, NOT fixed —
      extending a chain changes EDGAR resolution for every ticker and feeds the armed
      cross-check, so it is E-2 work under its own ruling):
        - cash: CashAndCashEquivalentsAtCarryingValue ABANDONED 2018-12-31 (stale 2738d);
          JPM now files the bank-specific CashAndDueFromBanks, current to 2026-06-30.
        - long_term_debt: LongTermDebt abandoned ~12y ago (stale 4383d); now
          LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities.
      test_jpm_cash_is_withheld_by_the_stale_gate is EXPECTED TO FAIL when the chain is
      extended — that failure is the signal the fix landed.
      Accepted limits (structural, like WU's): unclassified balance sheet so no
      current_assets/current_liabilities and no current_ratio; no cost_of_revenue or
      gross_profit (a bank has none); no OperatingIncomeLoss.
      BANK INSTRUMENT CALIBRATED: P/B 2.66, ROE 17.81%, beta 0.977, CoE 9.09%,
      justified P/B 1.96, P/B-justified +0.70 (~36% premium; excess ROE +8.7pp). Every
      input present — unlike the golden five, where beta on a cyclical (MU 2.19) inflated
      CoE into nonsense. STILL MISSING FOR ARMING: a LADDER. One calibration point cannot
      set rungs; would want several banks spanning the quality range (high-ROE trust bank,
      low-ROE regional, ideally one below book). Universe decision — Vic's.
- BLAST RADIUS, why this is not EDGAR: this is the first change that can move a SCORE.
  score -> avg_score -> synthesis prompt -> E(R) -> grade. EDGAR could only ever move a
  confidence label and a failure there degraded to 'medium'. A failure here moves grades.
  Touches the MU golden test (cyclical peak-earnings warning) directly.
