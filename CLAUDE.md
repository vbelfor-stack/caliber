# CLAUDE.md — CALIBER (operational context; auto-loads every session)
# Detailed build spec lives in Claude.md (Jul 10). This file is the living operational memory.

## ▶ SESSION PICKUP — READ THIS FIRST (rewritten at close, 2026-08-21, after L-4f)
Opening a session with **"resume — execute the next order in CLAUDE.md"** is enough. This
section is the cold-start record; everything below it is the durable detail.

**TOMORROW'S FIRST ACTION: run the session-open protocol, then execute L-4d.1 — the LLY
capex-basis rider. THE RULING ALREADY EXISTS AND THE WORK IS HALF-MEASURED; see the ★
`.scratch_lly/` entry below before doing anything else.**
**L-4f CLOSED COMPLETE 2026-08-21: 20-F/6-K admitted, the `_fy_ends` FY gate fixed, ARM
recovered 0 → 16 of 19 fields, coverage 18 → 19 of 28, +72 rows, one write point,
reconciled exactly.** Tree clean, pushed.
**★ THE ONE THING MOST LIKELY TO MISLEAD A LATER SESSION: `.scratch_lly/` IS UNTRACKED BUT
GITIGNORED AND MUST NOT BE DELETED.** It holds the ONLY surviving record of the LLY ruling
of 2026-08-21 — two read-only dark-diff scripts and 28 raw-facts dumps from a session that
**died mid-order after the L-4d close commit**. Verified harmless (no write verbs, no
production db reference, md5 was bit-identical across it). **A session was ruled, started,
and vanished; the tree reads clean and hides that.** Its ruling: add
`PaymentsToAcquireOtherPropertyPlantAndEquipment` as the THIRD capex chain entry. **The dark
diff's RESULTS were never written down — only the scripts survive, so L-4d.1 must re-run
them.** Cleaned in L-4d.1's close, not before.
**SECOND MOST LIKELY TO MISLEAD: `tests/fixtures/edgar/V.json`
PREDATES THE L-4d SYNONYM, so OFFLINE V withholds while LIVE V resolves $1.571B.** Adding
a synonym silently ages every recorded fixture, because fixtures store POST-EXTRACTION
concepts pulled from `XBRL_CONCEPTS` at record time. Pinned by name; the pin FAILS if V is
re-recorded, which is deliberate. Do not "fix" the offline result by re-recording without
a ruling — that moves the regression baseline for every valuation score.
**NOTE THE ASYMMETRY L-4f ESTABLISHED: a FORM admission ages NO fixture, a SYNONYM addition
ages every one.** Fixtures store post-extraction facts that already passed the form filter,
so admitting a form adds nothing to a recorded dict. The corollary is worse than the
non-problem it replaces — **the fixture replay path (`edgar_adapter.py:952`) calls
`resolve_financials` DIRECTLY and never runs the form filter at all**, so that filter has
ZERO offline coverage and `form_excluded` is never populated offline. Pins touching it must
be synthetic-fact pins.
**★ CARRY THIS FORWARD: the `B2-WIDENING-SUPPRESSED-TRIP` tripwire is LIVE and unfired.** If
any batch run emits it, that is a REPORT-TO-VIC event before the E(R) is trusted — see ARMED
STATE below. It is the one thing L-4b left deliberately observable rather than settled.
**THE B-2 BAND RULING IS SETTLED (2026-08-20): arm on the existing 15/20/30 set, no
re-derivation. L-4b is DONE.**

### STATE AT CLOSE 2026-08-21 (L-4f) — every value below was MEASURED at close, not remembered

| | |
|---|---|
| HEAD | the **L-4f close commit** — verify with `git log -1`. A block cannot contain its own hash. Previous session's last commit was **`c68d0ca`** (L-4d step 3). |
| This session's commits | ONE: the L-4f arm + write + close. |
| Pushed | **YES — `git rev-list --count origin/master..master` reads 0**, tree clean apart from gitignored `.scratch_lly/` and `.scratch_l4f/` |
| Suite | **953 passed** (was 922; +31 `test_l4f_foreign_forms.py`). No pre-existing test broke. **Three `test_l4d_typed_reasons.py` tests were UPDATED DELIBERATELY** — they used 20-F as the exemplar of "a form we do not read", which L-4f made false; each swaps to S-1 and carries a `★ EXEMPLAR FORM CHANGED AT L-4f` note. |
| caliber.db md5 | **e3fe5ff9868fcb05fc60106521779769** — **CHANGED THIS SESSION** (was `c0bae791…`). WAL checkpointed (returned `(0,0,0)`) before each reading; the empty wal/shm pair read connections create was removed and the md5 re-verified after. |
| **PRODUCTION WRITES THIS SESSION** | **ONE WRITE POINT: +72 rows in `fundamental_series` for ONE new ticker, ARM. Expected delta stated before the write, reconciled exactly: expected +72, actual +72, restatements 0, superseded 0 — MATCH.** EVERY other table re-counted after, all +0. |
| md5 trail this session | `c0bae791` (open; unchanged across step 1, the step-2 dark diff, AND the full 953-test suite) → **`e3fe5ff9`** (the single production write). Backup before the write: **`caliber.db.pre-l4f-c0bae791.bak`**, md5 verified equal to the pre-write db. |
| evaluations | **80** rows, max id **272** · unchanged this session |
| **defect-tagged** | **68 rows carry `defect_tags='TECHNICALS-REVERSED-AT-SYNTHESIS'`** — every row that ever carried a synthesis EXCEPT the post-fix STX id 272. The 11 untagged others are `failed` no-synthesis rows from 2026-07-10. |
| lifecycle_stage | **44** rows (unchanged) |
| lifecycle_transitions | **1** row (IONQ HIGROWTH → YOUNG) |
| field_provenance | **1437** rows (unchanged) |
| fundamental_series | **2374 rows, 19 tickers** (was 2302 / 18). Added ARM. · grades 0 · overrides 0 · lifecycle_overrides 0 · synthesis_cache 16 (evaluate.py never writes the cache) |
| **step-4 evaluable** | **19 of 28**, read through the production reader `evaluate._fy_series_from_db` (documented and confirmed **oldest-first**, `ORDER BY period_end`, so the R2 signal reads `s[-3:]`, NOT `s[:3]`). ARM has 5 FY points, NVDA 5, the other 17 six. All-negative last-3 FY FCF (the R2 YOUNG signal): **IONQ, QBTS, RKLB, C — UNCHANGED by L-4f** (re-measured through the production reader; ARM's last three are `[998M, 178M, 979M]`). Near the boundary: LITE (n/n/p), BE (n/p/p). |
| **ARM's rows** | fcf 14 (5 FY) · fcf_margin 14 (5) · reinvestment 14 (5) · fcf_growth 10 (4) · fcf_yield 10 (3) · revenue_growth 10 (4). **`sales_to_capital` 0 — ARM files no debt tag of any kind, so invested capital is uncomputable. NOT disqualifying: BE/BK/C/FN/IONQ already carry zero and count as evaluable; step-4 evaluability is the `fcf` FY series.** |
| **the 9 still uncovered, and WHY** | Correctly fail-closed with an accurate reason: **JPM, USB, INFQ** (`capex:no_tag`) and **SKHY** (`operating_cashflow:no_tag; capex:no_tag` — **no us-gaap namespace at all**; see the ★ punch-list entry). Blocked by OUR limits, each saying so precisely: **CBRS/DPC/SPCX/XE** `ttm_unavailable`, **LLY** `capex:stale_tag` (ruled — L-4d.1). **ARM is no longer among them.** |
| **V's share basis** | `truncated`, NOT `split_restated` — its 2015-03-19 split is uncorroborated (G-4 2-of-3 witnesses). Affects **`fcf_yield` only**; FCF is share-independent so the FY FCF step 4 reads is unaffected. Stamped per point. |
| **L-4b band assignment** | 18 of 28 names at the default 15%; **10 widen** — ARM/BE/CBRS/LITE/NOW/QBTS/SKHY @20%, IONQ/RKLB/SPCX @30%. DPC and INFQ read YOUNG but are correctly DENIED 30% (`INSUFFICIENT-HISTORY`). INFQ sits **0.37pp** from tripping at its 15%. |

### ARMED STATE — what reads what, precisely

- **★ 20-F/6-K ARE ADMITTED, AND THE ANNUAL/INTERIM SPLIT IS NOW LOAD-BEARING (L-4f,
  2026-08-21).** `_XBRL_VALID_FORMS = _XBRL_ANNUAL_FORMS | _XBRL_INTERIM_FORMS`, with
  ANNUAL = `{10-K, 10-K/A, 20-F, 20-F/A}` and INTERIM = `{10-Q, 10-Q/A, 6-K, 6-K/A}`.
  **The split exists because TWO different decisions read this set** — extraction asks "may
  I keep this fact", `_fy_ends` asks "is this a FISCAL YEAR end" — and they were the same
  question only by coincidence, since every admitted annual form began "10-K".
  **`_fy_ends` now tests MEMBERSHIP in `_XBRL_ANNUAL_FORMS`, not the string prefix
  `startswith("10-K")`.** ARM broke the coincidence: it tags `fp='FY'` correctly, on 20-F.
  - **THE ADMISSION IS MONOTONE, AND THAT IS ITS SAFETY PROPERTY** — a strict superset can
    only KEEP more facts, so no name that resolved before can stop resolving. Same shape as
    L-4b's monotone-widening argument; pinned by
    `test_the_admission_is_MONOTONE_it_can_only_add_facts`.
  - **The gate rewrite is EQUIVALENT on domestic filers, not merely close.** `_fy_ends`
    reads POST-extraction concepts, so it only ever sees admitted forms; over the OLD
    admitted set, `startswith("10-K")` IS membership in `{10-K, 10-K/A}`. Measured across
    the universe: the only `10-K*`/`20-F*` strings that exist anywhere are `10-K`, `10-K/A`
    and `20-F` — **no `10-KT`, no `10-K405`.** Pinned.
  - **F-1 AND 40-F ARE DELIBERATELY STILL EXCLUDED and pinned as such.** F-1 is SKHY's only
    form and is a REGISTRATION STATEMENT; 40-F is unmeasured because no universe name files
    one. Each is its own ruling.
  - **DARK DIFF BEFORE ARM: 16 of 532 cells moved, all ARM; 27 of 28 names bit-identical;
    ZERO domestic movement — which is STRUCTURAL, not lucky, because no domestic name files
    a single 20-F or 6-K fact.**
- **§5 step 3 IS ARMED ON BOTH WRITE PATHS (batch armed at L-4b, 2026-08-20).** The B-2
  anchor-divergence band is stage-conditioned: **YOUNG 30% · HIGROWTH 20% · MATURE 15% ·
  DECLINE 15%**, read from the PERSISTED `lifecycle_stage` table via
  `core/stage_tolerance.tolerance_for()`.
- **THE PER-PATH TOLERANCE DIVERGENCE IS CLOSED (L-4b, 2026-08-20).** `batch/runner.py` used
  to call the guard on the flat 15% while evaluate.py used the stage band, so the same name
  could get a different verdict by entry point. Both paths now call `tolerance_for()` once,
  **against the DESTINATION db (`db_path or _DEFAULT_DB`), never unconditionally production** —
  a scratch run finds no stage rows and falls to the DEFAULT band. `batch/runner.py` no longer
  imports `ANCHOR_DIVERGENCE_THRESHOLD` at all, and the removal is pinned.
- **THE ARM IS MONOTONE-WIDENING, AND THAT IS THE SAFETY PROPERTY IT RESTS ON.** No stage band
  is tighter than the flat default (`min(bands) == DEFAULT_TOLERANCE == 0.15`), so it can only
  ever SUPPRESS a trip, never create one. Pinned by `test_the_arm_is_monotone_widening`, which
  fails loudly if a future band ever drops below 15%.
- **★ LIVE TRIPWIRE — `B2-WIDENING-SUPPRESSED-TRIP` (codicil to the L-4b ruling).** 10 of 28
  names widen (ARM/BE/CBRS/LITE/NOW/QBTS/SKHY @20%, IONQ/RKLB/SPCX @30%) and **9 of those 10
  were UNVERIFIED at arm time** — no eval-date price exists for them, so their bands are
  reasoned, not measured. The widened band IS THE RISK DIRECTION. The first divergence landing
  in `(15%, stage band]` — one flat-15 would have tripped — emits a grep-able full readout and
  **REPORTS TO VIC BEFORE THAT E(R) IS TREATED AS TRUSTED.** Same pattern as the D-5 bank
  cheap-rungs tripwire. It ADVISES, it does not withhold: E(R) is still computed and persisted,
  because the codicil ordered a report and withholding would be a second unruled guard.
- **`core/technicals.py` NOW OWNS ITS ORDERING CONTRACT (armed 2026-08-19, `cd6b70f`).** It
  sorts by date internally and REFUSES (fail-closed) when order cannot be established. It no
  longer trusts caller order, so the adapter's newest-first contract and this module can no
  longer silently disagree. Pinned by `tests/test_l4a_technicals_ordering.py` (28 tests),
  including the suite's FIRST value-level assertions on an MA and a boolean.
- **THE TOLERANCE LOOKUP IS THE ONLY SCORING-PATH CONSUMER OF LIFECYCLE STAGE.** Pinned by
  `test_the_tolerance_lookup_is_the_ONLY_scoring_path_consumer_of_stage`, **widened at L-4b**
  to admit `batch/runner.py` as the second WRITE PATH making THE SAME ONE decision — one real
  call site per write path, still zero anywhere else. `core/pillars.py`,
  `core/valuation_anchors.py` and `synthesis/schema.py` contain no reference to the classifier
  or the stage table. The band is passed INTO `check_anchor` as its existing `threshold`, so
  the guard never learns what a stage is.
  Two properties of that pin worth knowing before editing it: **(a)** the classifier/table
  prohibition is ASYMMETRIC on purpose — `evaluate.py` is the ANNOTATOR (§5 step 1) and must
  import both; batch annotates nothing and may learn only the band. **(b)** the call-site count
  is taken over the **AST, not the text** — the old substring count was tripped by a COMMENT
  mentioning `tolerance_for()`, and a pin that prose can break is one a later session weakens
  instead of heeding.
- **RETIRED BY NAME AT L-4b: `test_batch_runner_does_not_read_the_classifier`.** Its surviving
  half (batch may never touch the classifier or the raw stage table, only the derived band) is
  re-asserted by `test_batch_reads_the_band_and_never_the_classifier` + the widened successor
  pin above. A retirement comment naming that handoff sits where the test was.
- **§5 STEPS 4+ ARE UNARMED.** Step 4 (YOUNG supply-layer block) is blocked behind
  `fundamental_series` coverage expansion by standing ruling. L-4c took coverage 4 → 15;
  **L-4d (2026-08-21) armed the capex synonym and took it 15 → 18 of 28.** The ruling is
  still NOT discharged: of the 10 remaining, only JPM/USB/INFQ/SKHY are correctly
  fail-closed. The other 6 (CBRS/DPC/SPCX/XE + ARM + LLY) are OUR limits — YTD-only TTM
  assembly, the 20-F form filter, and LLY's unruled capex definition. **Sequence from
  here: correct the typed reasons → rule LLY → THEN rule step 4.** ARM's 20-F admission
  and YTD TTM assembly are ruled OUT of that path (separate orders).
  **L-4d added NO name to the R2 YOUNG signal and removed none** — NVDA/V/LRCX are all
  firmly FCF-positive on their newest three FY points, so all-negative-last-3 remains
  IONQ/QBTS/RKLB/C.
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
  **DONE 2026-08-19 — docs/l4a-stx-diagnosis.md. ANSWER: NEITHER. It is a THIRD cause and it is
  OURS — the `core/technicals.py` newest-first/oldest-first defect (see punch-list TOP ITEM).
  FMP exonerated; the model anchored to a stale price WE PUT IN THE PROMPT. Diagnosis only, zero
  writes, caliber.db md5 unchanged. FIX NOT APPLIED — awaiting ruling, and it must land BEFORE
  L-4b arms a divergence band.**
- **L-4b — BATCH TOLERANCE ARMING. ✅ DONE 2026-08-20 — docs/l4b-batch-tolerance.md.**
  Vic ruled "arm now" on the existing 15/20/30 set with two codicils (coverage limit on record;
  the `B2-WIDENING-SUPPRESSED-TRIP` tripwire — both in the ARMED STATE section above). The
  band values were NOT re-derived: the contaminated-calibration concern bears on whether
  30/20/15 are the RIGHT numbers, which is already-shipped state on the interactive path, and
  L-4b changed no number — it removed an inconsistency. **Rationale for arming over clamping
  batch to flat 15, in Vic's words: clamping "creates per-path tolerance divergence (same name,
  different verdict by entry point), which is its own defect class. Monotone-widening + empty
  dark diff + path consistency carries it."** Zero production writes; caliber.db md5 unchanged.
  Suite 853 → 871.
- **L-4c — COVERAGE EXPANSION. ✅ DONE 2026-08-21 — docs/l4c-coverage-expansion.md.**
  `fundamental_series` 557 rows / 4 tickers → **1917 rows / 15 tickers**; step-4 evaluable
  4 → **15 of 28**. One write point, expected delta reconciled exactly (+1360, 0
  restatements, 0 superseded), no other table touched. New surface
  `tools/expand_fcf_series.py` — the first writer of this table that does NOT run an
  evaluation, which is what let the order stay inside its "no writes outside
  fundamental_series" constraint. Suite 876 → 884.
  **THE FAIL-CLOSED CONSTRAINT HELD ON ITS FIRST HALF AND FAILED ON ITS SECOND, AND THAT IS
  THE FINDING.** Nothing synthetic, partial or placeholder was written for the 13 uncovered
  names — but the TYPED REASON is wrong or misdescribes the cause for **9 of those 13**. See
  the ★ punch-list entry. **STEP 4 IS THEREFORE STILL NOT RULEABLE** — arming it now would
  block names on which XBRL concept their accountants chose, which is precisely the
  feed-coverage-as-business-reality failure the standing ruling forbids. The ruling is
  better evidenced, not discharged.

- **L-4d — CAPEX SYNONYM + TYPED-REASON CORRECTIONS. ✅ ALL THREE STEPS DONE 2026-08-21 —
  docs/l4d-capex-synonym.md.**
  Ordered by Vic as "a FIELD_SPECS change, not a coverage order", with the raw-facts sweep
  amended in after step 1 proved the builder's short-circuit hides downstream gaps.
  Step 1 diagnosed three distinct mechanisms behind the mis-typed reasons (none of them the
  capex gap). Step 2 armed the synonym on a dark diff: **0 non-capex field changes across
  all 28 names, 0 movement on all 15 already-covered names, and the armed cross-check moves
  only `no_edgar` → `basis_mismatch`, which is ADVISORY ONLY** — so no value, score, E(R),
  grade or confidence label moved anywhere. Coverage **15 → 18**, one write point, expected
  delta +385 reconciled exactly. LLY failed its conditional gate (branch B) and is open.
  Step 3 then killed the typed-reason mislabel structurally — see the ✅ punch-list entry.
  **Sequence from here: rule LLY (18 → 19) → then rule step 4.**

- **L-4f — 20-F/6-K FORM ADMISSION. ✅ DONE 2026-08-21 — docs/l4f-form-admission.md.**
  Ordered as "foreign-filer support; motivating case ARM, primary payload SKHY and any
  other ADR". **MEASUREMENT INVERTED THE PAYLOAD AND THAT IS THE FINDING OF STEP 1: ARM is
  the ONLY name in the universe admission moves, SKHY gains NOTHING and cannot, and there
  is no other ADR.** No 40-F anywhere. LYTE/FLTW measured live: **no SEC CIK at all**.
  **Step 1 also found a SECOND GATE the order did not know about** — `_fy_ends` matched
  `form.startswith("10-K")`, so admission ALONE would have delivered `+0` step-4
  evaluability while writing five rows labelled `TTM_Q` about periods ARM itself tagged
  `FY`. Vic ruled the gate into the order (option a) rather than accept a known-false
  label. **Result: ARM 0 → 16 of 19 fields, coverage 18 → 19 of 28, +72 rows, one write
  point, reconciled exactly.** Suite 922 → 953, pins fail 11 of 31 pre-fix.
  **The three fields ARM still withholds are truthful `no_tag` — it files no debt concept
  of any kind.**

**WHAT THE B-2 BAND RULING NEEDS TO DECIDE (carried forward from L-4a ruling 5, all numbers in
docs/l4a-stx-diagnosis.md §9):** (a) whether to re-synthesise any of the 68 defect-tagged rows
to obtain a clean calibration population — **ruled NO for now**, so the band may have to be set
on tagged data with that stated; (b) **the method must be pinned to the eval date** — L-3's
"stored anchor vs live price" comparison is only meaningful same-day, and re-run two days later
it showed 8 flags at flat 15% against ZERO at eval time, the gap being pure price drift
(STX itself -16.3% in two days); (c) INFQ still sits **0.37pp** from tripping (14.63% vs its
fail-closed 15%), which is the live held name that makes the band decision non-theoretical.

### PUNCH LIST — current at close

- **★★ TOP PRIORITY, DO NOT FOLD INTO A SPEC ORDER — SKHY IS EDGAR-UNEVALUABLE, AND IT IS A
  DATA-SOURCE ARCHITECTURE DECISION, NOT A SPEC FIX (ruled 2026-08-21, L-4f).** SKHY was
  named as L-4f's primary payload and gains nothing from any form admission. **Its ENTIRE
  companyfacts is 1,863 bytes with NO `us-gaap` namespace at all** — everything in it is
  `ffd` SEC **filing-fee** data (`NetFeeAmt`, `TtlFeeAmt`, `TtlOfferingAmt`) from SK hynix's
  $1B **F-1 IPO registration statement** filed 2026-06-24 / amended 2026-07-06. F-1 is a
  registration statement, NOT a periodic report; an F-1 registrant becomes a 20-F filer only
  after its first fiscal year-end post-effectiveness. **No spec, synonym or form change can
  reach it — there is no financial XBRL to read.** Admitting F-1 would be admitting a fee
  table as a financial statement; pinned excluded. The open question is whether a NON-EDGAR
  fundamentals source is wired for issuers EDGAR structurally cannot serve. Its current
  fail-closed reason is accurate and stays. **LYTE/FLTW are a DIFFERENT case and the L-4f
  ruling text mis-stated it: they are NOT domestic filers — they have NO SEC CIK AT ALL and
  file nothing under those tickers** (ETFs file under their trust's CIK). Already absent
  from `tickers.txt`; unaffected either way.
- **★ THE ARMED CROSS-CHECK COMPARES THE LATEST PERIOD ONLY — A HISTORY-DEPTH BLIND SPOT
  AFFECTING EVERY NAME (found by L-4f, candidate for L-4e scope).** ARM's capex reconciles
  to FMP **to the dollar in FY25/FY26 and diverges 4.5–10.7% in FY22–FY24**; the
  cross-check saw none of it, because it only ever inspects the live value, which agrees
  exactly. **Those three years were found BY HAND and would otherwise have shipped
  silently.** This is general: **every historical point in `fundamental_series` is written
  on ONE source's word, with no corroboration at any depth.** The strongest argument yet for
  reading the per-point `first_filed` basis stamp G-1 already captures. Measured, not fixed.
- **ARM GAINS `high` CONFIDENCE ON 8 FIELDS (L-4f, noted NOT defective).** The armed
  cross-check moves ARM from 15 × `no_edgar` to 8 × `agree` (gross_margin, operating_margin,
  profit_margin, roe, roa, current_ratio, shares_outstanding, total_cash@FY), lifting
  `medium → high` with source `fmp+EDGAR`; 3 × `basis_mismatch` (advisory: EDGAR TTM vs FMP
  annual) and 4 × `no_edgar` (the debt fields). **This is a scoring-path change** — it makes
  the `[ANTI-LAUNDER: high-conf miss]` NOTE reachable on ARM — and it is the system working
  as designed, recorded here so a later session does not read it as a regression.

- **✅ CLOSED 2026-08-21 (L-4d) — THE SINGLE-TAG `capex` SPEC IS NOW A TWO-TAG CHAIN.
  ARMED. Full report docs/l4d-capex-synonym.md.** `PaymentsToAcquireProductiveAssets`
  added, generic tag FIRST, `conflict_check=False`. **NVDA, V and LRCX recovered;
  `fundamental_series` 15 → 18 of 28 (+385 rows, expected delta reconciled exactly).**
  Suite 884 → 903, pins verified to FAIL 8 of 19 against the pre-fix spec before landing.
  `core/fundamental_series.py:261`'s wrong comment is corrected (V was a SPEC GAP, not a
  data limit; JPM/USB remain a real limit).
  - **★ LLY IS NOW ORDER L-4d.1 (LLY capex-basis rider) — RULED 2026-08-21, NOT YET LANDED.
    THIS IS THE NEXT ORDER.** Named L-4d.1 by ruling because it is a follow-on from L-4d's
    step-2 findings, not a new phase (L-4e stays reserved for the synonym census, L-4f was
    form admission). **The ruling: add `PaymentsToAcquireOtherPropertyPlantAndEquipment` as
    the THIRD capex chain entry, behind the two armed tags.** A session began executing it
    and DIED mid-order; its read-only scratch survives in **`.scratch_lly/`** (gitignored,
    do NOT delete — see the pickup block). **The dark-diff RESULTS were never recorded, so
    L-4d.1 must re-run `.scratch_lly/dark_diff.py` and `dark_series.py`.** Takes coverage
    19 → 20. **The L-4f ruling on ARM is the governing precedent and settles the principle:
    intangible/IPR&D-class acquisitions are NOT capital intensity, so where FMP bundles them
    and the issuer's own tag is definitionally consistent, the EDGAR tag stands and the
    disagreement is an advisory basis note.** LLY's FMP series bundles
    `PaymentsToAcquireInProcessResearchAndDevelopment`; ARM's bundles
    `PaymentsToAcquireIntangibleAssets`. Same question, answered once. Original diagnosis
    retained: L-4c had it in Class 1;
    that was wrong. LLY migrated **THREE times** and abandoned
    `PaymentsToAcquireProductiveAssets` at 2022-09-30 (1369d lag, past the 450d gate). Its
    current tag is `PaymentsToAcquireOtherPropertyPlantAndEquipment`, which **FAILED the
    ruled FMP reconciliation: 53.4% off in FY2023, 39.8% in FY2024, exact in FY2025.**
    Cause identified exactly — **FMP's `capitalExpenditure` bundles
    `PaymentsToAcquireInProcessResearchAndDevelopment` in FY23/FY24 (to the dollar) and
    drops it in FY25, so FMP is not self-consistent across years while the EDGAR tag is.**
    The ruling needed: whose capex definition governs when the two disagree DEFINITIONALLY
    and the feed is internally inconsistent. Not arbitrated in the resolver — that would be
    the "never fix a contradiction by teaching the model to ignore it" violation.
  - **★ THE SWEEP FOUND THE NEXT ONE: `net_income` IS A SINGLE-TAG SPEC AND
    `NetIncomeLoss` IS ALREADY STALE ON BE AND CAT.** A core field on a bare tag with the
    same silent-expiry shape. **9 of 19 specs have no synonym chain** (gross_profit,
    operating_income, net_income, capex, total_assets, current_assets, total_liabilities,
    current_liabilities, operating_lease_liability); `operating_lease_liability` is also
    stale on LLY. Feeds L-4e scope. Measured, not fixed.
- **✅ CLOSED 2026-08-21 (L-4d step 3) — THE TYPED-REASON MISLABEL IS KILLED AS A CLASS,
  NOT AS FIVE INSTANCES. docs/l4d-capex-synonym.md §4.** The reason is now taken from the
  resolver's own `ResolvedField.reason`/`.detail` via `withheld_reason()`, and
  **`WITHHELD_NO_CAPEX`/`WITHHELD_NO_OCF` WERE DELETED, NOT RENAMED — the deletion IS the
  fix.** A constant asserting "no tag" cannot know which of four causes occurred, so any
  code holding one is forced to guess. **ZERO PRODUCTION WRITES** (measured: no row has
  ever carried a withholding reason — a withheld ticker writes no rows at all), md5
  unchanged. Suite 903 → 922, pins fail 6 of 18 pre-fix.
  Three things fell out of doing it structurally:
  - **EVERY blocked input is now reported, not the first.** The old two-`return`
    short-circuit is exactly how XE was misfiled for a whole order.
  - **Extraction records what it discards** (`EdgarFinancials.form_excluded`). Necessary,
    not incidental: the resolver STRUCTURALLY CANNOT report the ARM cause because the facts
    are already gone by the time it runs. **The form filter is UNCHANGED and the record
    feeds no resolution — pinned.**
  - **The permanent invariant** (`tests/test_l4d_typed_reasons.py`): a tag-absence reason is
    legal ONLY when we hold no facts for any concept in the chain, kept or form-dropped.
    Swept over all 9 fixtures WITH a positive control, because a sweep that cannot fire
    proves nothing.
  Mechanisms, for the record — none of them was the capex gap:
  - **CBRS/DPC/SPCX/XE — `ttm_unavailable`, not a missing tag.** 10-Q-only filers whose
    cash-flow facts are YTD cumulative (89d/178d/180d), defeating all three `_assemble_ttm`
    paths: no 350–380d fact, no four contiguous QTD quarters, no prior-FY leg. Outcome
    correct, label wrong. **Fail-closed is correct here — TTM assembly for YTD-only filers
    is ruled OUT of scope, punch-listed as a capability question.**
  - **✅ ARM — the FORM FILTER, not the data. CLOSED 2026-08-21 BY L-4f.** `_XBRL_VALID_FORMS`
    admitted only the 10-K/10-Q family, so **0 of ARM's 4,373 facts survived extraction**.
    Now admitted; ARM resolves 16 of 19. **One correction to the L-4d prediction, on
    measurement: it said ARM "would resolve on `ttm_annual` untouched". That is the 20-F-ONLY
    reading. With 6-K also admitted ARM resolves on `ttm_reconstructed` at 2026-06-30 —
    a quarter fresher — because its cash-flow 6-K facts are YTD-cumulative (90/182/274d) with
    no standalone Q2/Q3 and no Q4 QTD at all, which defeats `ttm_summed` even on the income
    statement. Path 3 needs BOTH forms: the 20-F supplies `prior_fy`, the 6-Ks supply
    `current` and `prior_ytd`.**
  - **XE is Class 1 AND Class 2.** It files `PaymentsToAcquireProductiveAssets` and not the
    generic tag, so its capex reason was also wrong — undercounted because the builder
    checks OCF first and `return`s. **A short-circuit on the first withholding hides every
    later one**; sweep raw facts, never builder output.
  - Only **JPM, USB, INFQ** (no PP&E-purchase concept anywhere in their facts) and **SKHY**
    (no XBRL facts at all) are correctly fail-closed with an accurate reason. **BK and C
    are banks and DO resolve capex** — "banks file no capex" is not a rule.
- **★ NEW, FOUND BY L-4d AND PINNED — ADDING A SYNONYM SILENTLY AGES EVERY RECORDED
  FIXTURE.** EDGAR fixtures store the POST-EXTRACTION concepts dict, and extraction pulls
  exactly the concepts in `XBRL_CONCEPTS` **at record time**. `tests/fixtures/edgar/V.json`
  holds 23 concepts and no `Payments*` one, so **OFFLINE V withholds while LIVE V resolves
  $1.571B with 6 FY FCF points.** This is the recorded "a baseline that agrees with the bug
  shows nothing" hazard in a new form. **NOT fixed by re-recording** — that moves the
  regression baseline for every valuation score and is a deliberate ruled step. Pinned by
  `test_the_V_fixture_predates_the_L4d_synonym_and_UNDERSTATES_production`, which **FAILS
  if V is re-recorded**, forcing the divergence to be re-reasoned rather than forgotten.
  Applies to any future synonym addition, not just this one.
- **LATENT COUPLING, MEASURED NOT LOAD-BEARING (L-4d, recorded not fixed).** `_resolve_one`
  drops `concept` on its unresolved return, and `ttm_series` bails on `not rf.concept` — so
  the HISTORICAL series reader is gated on the LIVE TTM resolving. Forcing the concept back
  on for all four affected names yielded **forced=0 everywhere**, so no name in the universe
  demonstrates it today. Not fixed: changing it would move series content on the armed path
  with nothing to validate against.
- **GOOG AND GOOGL NOW BOTH CARRY A FULL SERIES ON ONE CIK (`0001652044`)** — as the
  share-class dedup entry below predicted. This is CORRECT for step 4, which reads per ticker
  and needs GOOGL (the held line) evaluable at all; it is a double-count hazard **only for
  grade rollups, which do not exist yet.** Dedup by CIK before any aggregate.

- **★ CLOSED 2026-08-19 — `core/technicals.py` READ THE PRICE HISTORY FROM THE WRONG END.
  FOUND, DIAGNOSED, RULED AND FIXED IN ONE SESSION. Fix `cd6b70f`; report + execution record
  docs/l4a-stx-diagnosis.md (§9 carries the rulings-1-5 outcomes).** Kept in full because the
  blast-radius facts below still govern how the 68 tagged rows may be read.
  **WHAT LANDED:** ascending sort inside core/technicals.py (adapter untouched) + fail-closed
  refusal when rows carry no `date` + 28 pins including both-orders-identical, a shuffled-input
  test so a reverse-only fix cannot pass, and the suite's FIRST value-level assertions on an MA
  and a boolean. Suite 825 -> 853, no pre-existing test broke. STX re-synthesised as id 272
  superseding 258: **divergence 90.08% -> 1.73%, E(R) restored from WITHHELD to -6.61%.**
  All 68 affected rows carry `evaluations.defect_tags='TECHNICALS-REVERSED-AT-SYNTHESIS'`
  (ruled: TAG, do NOT re-run). **STILL OPEN: the B-2 band ruling — Vic rules next session;
  L-4b STAYS BLOCKED.** Original diagnosis retained:
  FMP serves `price_history` **newest-first** (documented at
  `adapters/fmp_adapter.py:33`); `analyze_technicals` assumes oldest-first (`closes[-1]`,
  `closes[-period:]`), so **every MA, RSI, boolean and volume reading describes AUGUST 2021,
  not today** — and RSI is computed on a time-reversed series. Aggravated by the known quirk
  that FMP ignores `limit` (asks 365, returns 1254), making the stale end ~5y old, not ~1y.
  - **THIS IS THE STX CAUSE (id 258) AND THE MU id 209 CAUSE.** Both anchor_divergence rows
    are this defect. FMP is EXONERATED: price verified to the cent against a second source
    ($832.56), no splits, series continuous, the 9.31x is real appreciation.
  - **BLAST RADIUS — pillar scores UNAFFECTED (structural: no pillar/lens/anchor reads
    technicals; only evaluate.py, batch/runner.py and the prompt do). Grades: 0 rows.
    `_price_on_or_before` is order-agnostic so own-history/G-4/H-3 are immune.** What IS hit:
    **all 68 evaluations carrying a synthesis** (FMP became the feed 2026-07-11; first ok eval
    2026-07-12 — there is NO clean pre-defect population), via prompt → trend/redFlags/
    narrative/verdictConfidence → and on the 2 caught rows → priceTargets → E(R).
  - **THE B-2 HEALTHY BAND IS CONTAMINATED CALIBRATION** — "0.6-8.2%, 15% with ~6x margin" was
    measured entirely on poisoned prompts, and six 2026-08-17 rows already read 9.9-14.6%.
    **RECALIBRATE ON CLEAN PROMPTS BEFORE L-4b ARMS A BAND** — L-4b arms a divergence
    tolerance, so arming first would bake this defect into the guard.
  - **DO NOT RE-SYNTHESIZE STX YET.** The prompt still carries 2021 technicals, so a re-run
    today would reproduce the poisoning or (worse, given the B-2 prompt fix) mask it into a
    healthy-looking divergence. Fix first, THEN supersede-link `supersedes_id=258`.
  - **RECOMMENDED SEQUENCE FOR THE RULING:** technicals fix (sort ascending INSIDE
    core/technicals.py, leaving the adapter contract alone) + a both-orders-identical-output
    pin + the first-ever value-level assertion on an MA/boolean → re-synthesize STX
    supersede-linked → recalibrate B-2 → then L-4b. Fix flips **8 of 18** boolean cells on
    the fixtures (WU both True→False, NOW both False→True, BK/JPM/USB/C one each; GOOG/MU/V
    unmoved — right by luck, because strong trends sit above both MAs at either end).
  - **WHY 825 GREEN TESTS AND THE GOLDEN HARNESS MISSED IT:** all nine FMP fixtures are
    newest-first (recorders reuse the adapter's live path, correctly), so **the baseline agrees
    with the bug**; the retired yfinance fixtures were ascending, under which the code was
    CORRECT — the feed migration introduced the defect and the fixture migration hid it, which
    is the already-recorded "migrating a baseline onto the source it checks retires the check"
    warning coming true, with the thing given up never named. And the ONE test touching
    `analyze_technicals` asserts a **provenance source string**, not a single numeric value.

- **WHAT OPENED A BACKUP AS A LIVE DATABASE AT 19:52 ON 2026-08-17? DIAGNOSIS QUESTION, ruled
  onto the punch list 2026-08-19 (L-4a ruling 6), NOT this session's work.**
  `caliber.db.pre-rerun-2026-08-15.bak-shm` (32 KB) and `-wal` (0 bytes) exist, timestamped
  19:52 on 2026-08-17 — **inside the contamination window** (the fixture runs were 19:50-19:52).
  The WAL is EMPTY so nothing was pending and the `.bak` itself is intact, but a `-shm`/`-wal`
  pair only appears when something OPENS a file as a SQLite database. A backup is evidence; a
  process that can open it read-write is a hazard to the evidence. Question to answer: which
  call opened it — a stray `--db-path` pointing at the `.bak`, an `init_db`, or a manual probe?
- **✅ CLOSED 2026-08-20 (micro-order) — `batch/runner.py` READ THE SYNTHESIS CACHE FROM
  PRODUCTION EVEN UNDER `--db-path`.** `get_cached_synthesis(ticker, today_str)` took no
  destination, so the READ always resolved to production while the `save_synthesis_cache`
  twelve lines below honoured `db_path or _DEFAULT_DB` — a scratch or fixture run could REUSE
  a production synthesis it would never write back. Third instance of one shape (a destination
  flag whose real scope is narrower than a human reads it; the others are the ids-226-228
  contamination and the L-2a save-side half of this same pair). **Fix: the read now resolves
  `db_path or _DEFAULT_DB`, identical to the save.** Zero production writes, md5 unchanged.
  Suite 871 → 876, `tests/test_cache_read_routing.py`.
  - **THE SAVE SIDE WAS CLOSED BY DELETING THE DEFAULT; THE READ SIDE COULD NOT BE** —
    `get_cached_synthesis` is also called legitimately without one — so the enforcement point
    is at the CALL SITE, written as a class pin, not an instance pin.
  - **SWEEP RESULT (AST over every non-test `.py`, positional AND keyword routing counted):
    NO FOURTH INSTANCE.** `batch/runner.py:309` was the only unrouted store accessor on either
    `--db-path`-honouring path. The other candidates all route POSITIONALLY, and a
    keyword-only sweep reports them falsely — `_validate_supersede_link` (runner :211/:507),
    `init_db` (evaluate.py :260, smoke.py :51/:234, tools/probe_lifecycle.py :70). **A sweep
    that only counts keywords will re-raise all five; count positionals.**
  - **`web/app.py` IS OUT OF SCOPE BY DESIGN, not by oversight** — 14 unrouted reads and one
    unrouted write (`save_override` :451) against production. It is the production dashboard
    and has NO destination flag to understate, so it is not this shape. Stated in the pin's
    docstring so a later session does not read the exclusion as a miss.
  - Pinned four ways: the behavioural guarantee; a POSITIVE CONTROL (same run, row moved to
    its own destination, must hit) so the pin cannot pass vacuously if the cache branch ever
    goes dead in fixture mode; the write-side twin restated beside it; and the AST class pin
    above. Verified to FAIL 4 of 5 against the pre-fix line before landing.
- **✅ CLOSED 2026-08-20 (L-4c step-0 rider) — `evaluate.py --db-path`'s HELP STRING NOW STATES
  WHAT IT ROUTES.** It read "Destination for the lifecycle stage write" — true before L-2a,
  false since: the flag routes EVERY write (see the `write_db` resolution at evaluate.py:259 and
  the routing comment at :249-251). Same shape as the 2026-08-17 contamination — a flag whose
  stated scope was narrower than its real one, read by a human as covering the run. Fix is a
  help-string only: now reads "Destination for every write this run makes (evaluation, lifecycle
  stage, provenance, cache)". No test pinned the old string; docs/help-text change, zero
  production writes, caliber.db md5 unchanged.
- **`field_provenance.field_name` is NULL on all 1,437 rows** (re-measured at close 2026-08-19;
  was 1,416 before the STX re-synthesis added 21) — provenance is unqueryable by
  field, only by `(evaluation_id, pillar)`. **DIAGNOSIS QUESTION, not yet a fix order:** is
  the writer dropping the name, or was it never populated?
- **RECORD `price_snapshot` ON EVERY COMPLETING EVAL (roadmap item, ruled 2026-08-20 as NOT
  part of L-4b).** Today only `synthesis_cache` carries an eval-date price, only batch writes
  it, and it holds 16 rows across 5 tickers — which is why 9 of the 10 L-4b widened names could
  not be replay-verified. Per the L-4a ruling 5(b) an eval-date price is the ONLY thing that
  makes a divergence recomputable later; without it, a re-run measures price drift instead.
  Extending capture (batch and/or evaluate.py) closes the L-4b verification gap **BY
  OPERATION** on the next real evals — no dedicated capture order needed.
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
- **NEVER FIX A CONTRADICTION BY TEACHING THE MODEL TO IGNORE IT — REMOVE IT AT SOURCE.**
  (Ruled 2026-08-19, L-4a ruling 4.) A prompt instruction that tells the model which of two
  disagreeing inputs to trust **MASKS the defect that made them disagree**: the bad input keeps
  flowing, and the one symptom that would have exposed it disappears. ORIGIN, and it is exact:
  B-2's 2026-08-07 prompt fix ("anchor to the provided current_price, never remembered levels")
  was filed as the MU **root cause**. It was not. The real cause was `core/technicals.py`
  handing the model a 2021 price in the same prompt as a 2026 one. The instruction made the
  model prefer the right number, divergence fell 90.8% -> 1.1%, everyone read that as fixed —
  **and the poisoned technicals then ran for 12 more days across 5 batch sessions with nothing
  objecting.** A contradiction between two inputs is EVIDENCE; suppressing it destroys the
  evidence. If two inputs disagree, fix the producer or fail loudly — never arbitrate in the
  prompt. Corollary: when a guard's symptom disappears after a fix, verify the CAUSE is gone
  and not merely the symptom.

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

- **STEP 4 (YOUNG SUPPLY BLOCK) IS BLOCKED BEHIND FEED COVERAGE (ruled 2026-08-17; STILL
  BLOCKED after L-4f, 2026-08-21).** `fundamental_series` now covers **19 of 28** (was 4,
  then 15, then 18). Of the 9 remaining, **only 4 are correctly fail-closed**
  (JPM/USB/INFQ/SKHY); the other 5 are OUR limits — CBRS/DPC/SPCX/XE (`ttm_unavailable`,
  YTD-only filers, ruled OUT of scope) and LLY (ruled, pending L-4d.1). The
  YOUNG/blocked boundary therefore still reflects **which names happen to have FCF data**,
  not business reality, and a hard block driven by feed coverage would be arbitrary in
  exactly the way this system exists to avoid.
  **Sequence from here: land L-4d.1 (LLY → 20 of 28) → THEN rule step 4 on its evidence.**
  ARM's admission is done; the two feed-repair tickets below join that work.
  **NOTE FOR THE STEP-4 RULING: `fundamental_series` coverage and step-4 evaluability are
  no longer guaranteed to be the same number.** L-4f nearly separated them (ARM would have
  had 72 rows and 0 FY-labelled points) and only the `_fy_ends` fix kept them equal. Count
  evaluability through `evaluate._fy_series_from_db`, never by `SELECT DISTINCT ticker`.
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
  **★ OBSERVED 2026-08-21 (L-4f close) — RUN `gh auth setup-git` IMMEDIATELY BEFORE THE
  PUSH, NOT ONCE AT SESSION OPEN.** It WAS run at session open and reported OK, with the
  helpers visible in `git config`. The close push then still failed with the documented
  "Password authentication is not supported", and by then `git config --list | grep
  credential` returned **NOTHING** — the helper entries had gone. Re-running
  `gh auth setup-git` restored them and the push succeeded on the retry, same token, no
  `gh auth login` needed. So the helper config **can disappear mid-session** on this
  container. Note also that everything else looked healthy throughout: `gh auth status`
  read logged in, `gh api user` returned the login, and `gh repo view` reported ADMIN —
  **none of which proves git can push.** Cheap fix, run it every time.
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
- ~~MU root cause RESOLVED: it was a genuine stale LLM anchor, NOT a feed bug. Model anchored
  to ~$81 (stale training data)~~ **← THIS ATTRIBUTION IS WRONG. OVERTURNED 2026-08-19 BY L-4a
  ON id 209's OWN STORED DATA (docs/l4a-stx-diagnosis.md §4).** The $81 was NOT recalled from
  training data — it was **IN THE PROMPT**, put there by the `core/technicals.py` ordering
  defect (§ punch list). id 209's stored technicals notes read "Price $80.21 above MA50 $72.12
  and MA200 $78.10" — MU's **2021** prices — and its implied anchor $80.88 matches that
  injected price to within 0.8%. **The model anchored to a price we handed it, which is correct
  behaviour.** MU really trades ~$881 (~$1T mkt cap, May-2026 HBM-cycle 10x re-rate, no split)
  — **FMP was CORRECT, that half stands.** The guard caught its motivating Phase-B case on
  first live outing (also stands — it caught a REAL defect, just not the one recorded).
  Canonical positive preserved as eval id=209 (retroactively set anchor_divergence, E(R) NULL).
  Do NOT delete id=209.
- Prompt fix (~~root cause~~ **MASK, not root cause — see L-4a**): synthesis/prompt.py now
  instructs the model to anchor ALL targets to the provided current_price and never use
  remembered price levels. Verified: MU re-eval (id=214, force_refresh) re-anchored targets to
  $525/$800/$1225, divergence 90.8% -> 1.1%, status ok. **THE FIX IS STILL WORTH KEEPING — it is
  correct guidance on its own terms — BUT IT SUPPRESSED THE ONLY VISIBLE SYMPTOM OF A LIVE
  DEFECT.** id 214's stored notes STILL carry the poisoned 2021 values ("Price above both MA50
  (72.12) and MA200 (78.10)") on a stock at $885: the model was made to IGNORE the contradiction
  rather than the contradiction being removed, and the defect then ran unnoticed for 12 days
  across 5 further batch sessions. **"Loud failure beats silent degradation", inverted by
  accident.**
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
