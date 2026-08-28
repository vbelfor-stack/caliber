# CLAUDE.md — CALIBER (operational context; auto-loads every session)
# Detailed build spec lives in Claude.md (Jul 10). This file is the living operational memory.

## ▶▶ DOCTRINE (ratified 2026-08-21, applied 2026-08-22) — READ BEFORE THE PICKUP BLOCK
# **FMP IS THE SOURCE. EDGAR IS THE ARBITER.**
Order + full measurement: **`docs/orders/2026-08-22-doctrine-fmp-source-edgar-arbiter.md`**.
Pin: `tests/test_doctrine_edgar_arbiter.py`. Rationale, in Vic's terms: paid/normalized beats
free for pipeline reliability; EDGAR remains ground truth of record, invoked for arbitration,
not pipeline. **This reverses the direction of travel of every order from E-1 through L-4d.1**,
so read it before acting on any EDGAR-coverage language further down — much of that text now
describes the AUDIT LAYER, not the pipeline.

- **FMP feeds ALL pipeline runs** — series building, TTM, scoring.
- **EDGAR is invoked in exactly three cases:** (a) **divergence arbitration** — FMP diverges
  **>25%** from an EDGAR-visible figure; (b) **filed-tag provenance** on a challenged
  verdict; (c) **rulings**.
  - **★ AMENDED 2026-08-28 (Vic ruling 6, doc-level) — "THE SANITY GATE" IS *DEFINED AS* THE
    EXISTING 25% DIVERGENCE CHECK. IT IS NOT A SECOND, SEPARATE TRIGGER, AND NO NEW MACHINERY
    IS TO BE BUILT.** The original §1.2(a) read "FMP fails a sanity gate **or** diverges
    >25%", which a reader can only take as naming TWO triggers — and the first one had no
    referent anywhere in the runtime, so it was permanently unreachable. That is worse than a
    missing feature: it is a doctrine clause that looks armed and is not, and the standing
    response to an unreachable guard is to remove the claim, not to leave it standing as a
    belief. **The "or" is therefore struck and the two are collapsed into one:** the sanity
    gate IS the >25% divergence check, which does exist and is measurable.
    **DO NOT "IMPLEMENT THE SANITY GATE" — there is nothing left to implement.** A future
    session reading this must not build a second checker; if a genuinely different sanity
    condition is ever wanted, that is a NEW ruling with its own name, not this clause.
    Closes census item 9.
- **EDGAR MACHINERY IS DEMOTED TO AN AUDIT LAYER — NOT UNWOUND, NOT DELETED.** The capex
  chains (including the three-tag chain armed at L-4d.1), the typed withholding reasons and
  `field_provenance` all stay exactly as they are. **DELETING EDGAR-PATH CODE REQUIRES A VIC
  RULING.** Pinned — a demotion is precisely the ruling a later session misreads as licence
  to tidy up, so the no-delete clause has an enforcement point rather than being a belief.
- **COEXISTENCE IS BY DESIGN, NOT A DEFECT.** EDGAR-chain capex and FMP `capitalExpenditure`
  both live in the db with distinct provenance and are PERMITTED TO DISAGREE. **The worked
  example is LLY FY2024: EDGAR $5.058B vs FMP $8.4036B — $3.3456B apart (39.8%). MEASURED,
  not remembered. DO NOT "FIX" IT.** Cause was already ruled at L-4d.1: FMP bundles
  `PaymentsToAcquireInProcessResearchAndDevelopment`, the EDGAR tag does not; IPR&D is not
  capital intensity. Both sides are internally coherent, so this is a BASIS difference.
- **All other standing disciplines are UNCHANGED.**

### ★ ONE CLAUSE IS RULED BUT **NOT OPERATIVE** — PRE-FLIGHT. AWAITING VIC.
The doctrine rescopes the live-EDGAR pre-flight to **arbitration runs only**. **DO NOT ACT ON
THAT YET — THE PRE-FLIGHT REMAINS MANDATORY ON EVERY LIVE RUN.** Reported at the doctrine
close (order §5) rather than improvised past, because the code contradicts the doctrine's
premise and the contradiction is itself already ruled:

> **EDGAR IS SCORE-BEARING ON EVERY RUN TODAY**, via four paths the three-case list does not
> name: `yf.sic = edgar.sic` (evaluate.py:300, batch/runner.py:254) → `select_lens(...)`
> (:310 / :255) — **the lens moves scores**; `build_panel(yf, fred, edgar, …)` (:320 / :268);
> and `score_growth(yf, edgar, lens)` (core/pillars.py:988). `fetch_edgar` is a **hard gate** —
> evaluate.py exits 1, and batch/runner.py deliberately does not wrap it, so a mid-batch 403
> persists a **`failed` row per ticker**. Already on record at docs/phase-archive.md:307-314.

Rescoping the pre-flight while that is true would remove the one mechanism standing between an
intermittent SEC 403 and **28 `failed` rows in production** — the exact incident the pre-flight
was ruled into existence for. Two resolutions are on the table in order §5 — **(a)** sequence
it (hold the arming until EDGAR is genuinely off the pipeline path), or **(b)** widen the
doctrine to a fourth case ("classification + panel inputs") and withdraw the rescope. **Not
chosen here. Vic rules.**
**~~Also noted, not blocking: §1.2(a) invokes EDGAR when "FMP fails a sanity gate" — NO
SANITY GATE EXISTS anywhere in the runtime, so that trigger is currently unreachable.~~
✅ CLOSED 2026-08-28 BY RULING 6 — the clause is AMENDED, not implemented: the sanity gate is
DEFINED as the existing 25% divergence check, the misleading "or" is struck, and no new
machinery is built. See the amendment under §1.2 above.**

## ▶ SESSION PICKUP — READ THIS FIRST (rewritten at close, 2026-08-28)
Opening a session with **"resume — execute the next order in CLAUDE.md"** is enough. This
section is the cold-start record; everything below it is the durable detail.

### ▶▶▶ 2026-08-28 SECOND CLOSE (the "closer" order) — READ THIS BEFORE THE BLOCK BELOW IT.
Order `docs/orders/2026-08-28-closer.md`, report `docs/2026-08-28-closer.md`.
Suite **1011 → 1051**. caliber.db **`70be9730` → `19d615fe`**.

**✅ RULED AND PERSISTED 2026-08-28 (micro session) — `QBTS HIGROWTH → YOUNG` IS APPROVED**,
band `20% → 30%` (the WIDER direction), `rule2_young`. `stage_flip_approvals` id 1.
**★ AN APPROVAL IS CONSENT, NOT PERSISTENCE — QBTS's `lifecycle_stage` row (id 28) STILL
READS `HIGROWTH` AND WAS NOT TOUCHED.** The flip lands when the next evaluation of QBTS
recomputes and writes; until then the stored stage, and therefore the live band, is
unchanged at 20%. Verified live: `QBTS → YOUNG` PERMITTED, `QBTS → DECLINE` still HALTS,
`IONQ → MATURE` still HALTS — the approval is per-transition, exactly as built.
**Vic expected the sweep to find zero after the financials gate; it found one, and the
reason is structural: EVERY stage row in the table predates its own inputs** (all 44 written
2026-08-17; L-4c/L-4d/L-4f/L-4d.1 wrote series 21–22 August). **C was never the only case —
it was the first one anyone looked at.** 13 names recomputed to the SAME stage; QBTS is the
only flip.

**WHAT LANDED.** (a) The financials gate now binds the **evaluator** (exit 5) and the
**batch path** (`status='model_inapplicable'`), not just the score builder — and **8
`lifecycle_stage` rows for BK/C/JPM/USB are RETIRED**, not deleted or edited, with
`tolerance_for()` now filtering `retired_reason IS NULL`. (b) `core/stage_freshness.py` +
`tools/stage_freshness_sweep.py`, with a NEW approval table `stage_flip_approvals`. (c) The
currency guard on 8 MONETARY score-bearing fields (`core/reporting_currency.py`) — ratios
deliberately NOT guarded, because KRW/KRW reads the same as USD/USD. (d) The SKHY anchor
**written**: `market-capitalization?symbol=SKHY` → **$1,143,150,316,466 USD, 2026-08-28**,
`metric='market_cap_anchor'`, `period_type='ANCHOR'`, full-cap basis. (e) Pre-flight rescope
doc-level only. (f) A 32-item punch-list census — **that census in the report is now the
authoritative "what's left" list; this file is the narrative.**

**★★ MAJOR FLAG — FINANCIALS ARE UNSCOREABLE. Router + gate SHIPPED; ENGINE NOT BUILT;
scoping order QUEUED behind the open items.** BK/C/JPM/USB get no stage, no score, no band.
**Consequence Vic priced in: they are the only four bank-lens names, so D-5/D-6 bank-lens
calibration has NO POPULATION until a dedicated financials leg exists.**

**★ TWO DEFECTS WERE CAUGHT IN MY OWN WORK THIS SESSION AND BOTH ARE WORTH THE READ.**
**(1)** `tools/retire_financial_stages.py` reported "0 live rows" for four names holding
eight — an `except OperationalError: return []` masking an unmigrated column. **A `--commit`
on that output would have retired nothing and RECONCILED TO MATCH**, because expected and
actual would both have been zero. **(2)** The currency guard's first version declared
`market_cap`'s basis STATICALLY, and the dark diff showed it BLOCKING the very USD figure
ruling 3 exists to supply — **a field's currency basis belongs to the ENDPOINT THAT SUPPLIED
IT, not to its name**, and ruling 3 had just moved that endpoint.

**★ AND A THIRD, IN THE PINS, FOR THE SECOND TIME IN ONE DAY:** two new pins scanned module
TEXT for a forbidden word and fired on the prose explaining the prohibition. Both rewritten
over the AST. *A pin that prose can break is one a later session weakens instead of heeding.*

### ▶▶ 2026-08-28 FIRST CLOSE — SKHY USD-ONLY + THE FINANCIALS CLASS. READ THE C FINDING.
Order `docs/orders/2026-08-28-skhy-usd-only-and-financials-class.md`, report
`docs/2026-08-28-skhy-usd-only-and-financials-class.md`. Suite **984 → 1011**. One write
point, **+133 rows in `fundamental_series`**, reconciled exactly, every other table +0.
caliber.db md5 **`eec96270…` → `70be9730…`**.

**★★ TOMORROW'S FIRST ACTION — RULE THIS. CITIGROUP CLASSIFIES AS *YOUNG* ON A LIVE RUN
TODAY, AND IT HAS BEEN ARMED FOR SEVEN DAYS.** Measured on production 2026-08-28:
`C → YOUNG, rule2_young, fcf_negative_2of3=True ("3 of last 3 FY FCF negative")` on FY FCF
of −$80.0B / −$26.2B / −$74.2B. **C's STORED stage rows are dated 2026-08-17 and read
MATURE; its `fundamental_series` rows were first observed 2026-08-21 (L-4c). The stored
stage PREDATES the series that flips it, and C has not been re-evaluated since.** This is
not annotation-only: stage drives the B-2 band via `tolerance_for()`, and `rule2_young`
fired on a MEASURED leg (not an absence), so C is NOT denied the wider band the way
DPC/INFQ are. **The next eval persists YOUNG; the one after scores a ~$200B bank at a 30%
divergence tolerance instead of 15%.** The financials class does NOT stop it — the class
gate binds `build_fcf_series`, and the classifier reads the STORED series. **Fixing it is a
scoring-path change and needs a ruling: see report §8 item 1.**
**GENERALISE IT BEFORE RULING (report §8 item 5): C is not special. ANY name whose
`fundamental_series` arrived after its last evaluation carries a stage row computed without
it, and NOTHING re-computes stages when the series changes. C is just the one where it
flips a rule. That was found, not designed for.**

**WHAT LANDED.** (a) SKHY serves **129 statement periods across six FMP endpoints and 0 are
USD** — the USD set is EMPTY, so (b) wrote **zero numeric rows** and 129 typed block rows
(`currency:non_usd_native`). (c) The financials class catches **exactly BK, C, JPM, USB**;
**V and WU are Financial Services sector but are correctly NOT caught** (Credit Services
industry → compounder lens, and both are currently covered — a sector-level rule would have
destroyed working coverage on two names). (d) Anchor re-measured read-only, **no anchor
write**. (e) Dark before/after: **NOTHING MOVED**; SKHY stays HIGROWTH/rule3.

**CARRIED OPEN FROM THE DOCTRINE ORDER (2026-08-22), STILL UNRULED —**
**(1) the pre-flight / EDGAR-score-bearing contradiction above (order §5);**
**(2) step 4 on FMP basis, given the feasibility measurement came back MUCH WEAKER than the
ruling assumed — 5 of the 8 names FAIL on FMP basis (★ step-4 entry below);**
**(3) ~~the SKHY FX verification band~~ — ✅ CLOSED 2026-08-28. THE BAND HAS NO SUBJECT ANY
MORE. Vic's USD-ONLY ruling removed the conversion the band existed to verify, so it is
MOOT rather than "still failing by 1.0%". Its five ordered pins are moot for the same
reason and are recorded superseded, not written. See the 2026-08-28 report §5.**
**DOCTRINE ORDER CLOSED COMPLETE 2026-08-22: docs + CLAUDE.md + one pin, ZERO production
writes, ZERO code-behaviour changes, caliber.db md5 unchanged. Suite 975 → 984. The SKHY
currency ruling addendum was FOLDED IN (order §8), not held — the order had not closed and
performs no writes, so there was nothing in flight to interrupt.**
**L-4d.1 CLOSED COMPLETE 2026-08-22: the third capex tag armed, LLY recovered, coverage
19 → 20 of 28, +114 rows, one write point, reconciled exactly. Suite 953 → 975.** Tree
clean, pushed. Order `docs/orders/2026-08-22-l4d1-lly-capex-basis.md`, report
`docs/l4d1-lly-capex-basis.md`.
**L-4f CLOSED COMPLETE 2026-08-21: 20-F/6-K admitted, the `_fy_ends` FY gate fixed, ARM
recovered 0 → 16 of 19 fields, coverage 18 → 19 of 28, +72 rows, one write point,
reconciled exactly.** Tree clean, pushed.
**★ `.scratch_lly/` IS GONE — RETIRED AT THE L-4d.1 CLOSE, NOT LOST.** Archived to
**`.snapshots/l4d1-lly-2026-08-21/`** (gitignored: 28 raw-facts dumps / 93 MB + both
scripts + a README). **Committed copies of the scripts are at `tools/l4d1_dark_diff.py`
and `tools/l4d1_dark_series.py`**, so the method is in git even if the snapshot is lost.
**DO NOT RE-FETCH `facts/` TO REPRODUCE** — it is a DATED 2026-08-21 snapshot, and that is
the point; `dark_diff.py` reads the cache when present, so it reproduces the original
measurement exactly. A live re-fetch measures today and will not.
**★ CORRECTION THIS BLOCK USED TO CARRY: it called `.scratch_lly/` "the ONLY surviving
record of the LLY ruling." THAT WAS LOOSE, and the loose version is what nearly got the
snapshot deleted as redundant.** The ruling TEXT was always here in CLAUDE.md; `facts/`
contains no ruling text at all, only raw payloads. What the residue uniquely held is
**reproducibility of the measurement** — a different and much better reason to keep it.
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

### ▶ STATE POINTER — FULL STATE LIVES IN `docs/closes/`, NOT HERE (Vic ruling 2, 2026-08-28)

| | |
|---|---|
| HEAD | the **2026-08-28 ACCEPTANCE close commit** — verify with `git log -1`. A block cannot contain its own hash. |
| Suite | **1091 passed** |
| caliber.db md5 | **`69dc2328ee3af8a43d506b64665da39b`** (was `8752e75e…`; the full-universe acceptance run) |
| Backup | `caliber.db.pre-acceptance-8752e75e.bak` |
| Full state this close | `docs/closes/2026-08-28-acceptance.md` |
| **★★ ACCEPTANCE** | **PASSED 2026-08-28.** 28/28 accounted for: 24 SCORED, 4 REFUSED (financials), 0 silent. Zero unexplained anomalies. **CALIBER IS IN GRADING LIFE — next sessions are grading reads, NOT construction.** First gradeable cohort ~**2026-11-26** (90d). |
| Prior closes | `docs/closes/` — index at `docs/closes/README.md` |
| Open items | the 32-item census in `docs/2026-08-28-closer.md` §8 is the authoritative "what's left" list |

**★ THE RULE: a close writes FULL state to a dated file in `docs/closes/`; CLAUDE.md carries
ONLY this ~10-line pointer block and NEVER a full state table.** The three tables that used to
sit here (2026-08-28 closer, 2026-08-28 first, 2026-08-22 L-4d.1) were relocated VERBATIM —
relocation only, nothing edited, nothing dropped; all 44 lines verified present in the
destination files before removal.

### ▶ ARMED STATE — what reads what, precisely → **`docs/armed-state.md`**

**READ IT BEFORE TOUCHING ANY ARMED SURFACE.** It is a LIVING file, updated in place, one
copy — not a dated snapshot, because "what reads what" carries forward across closes while a
close measurement does not. Currently armed and recorded there: the **financials gate** (three
surfaces, 8 retired stage rows) · **stage freshness** / `stage_flip_approvals` · the **USD-only
currency guard** (8 monetary fields) · **market cap from `market-capitalization`** · the **SKHY
anchor** · the **FCF-model financials class** · the **USD-only reporting-currency gate** ·
**20-F/6-K admission** · the **B-2 stage-conditioned band** and the `B2-WIDENING-SUPPRESSED-TRIP`
tripwire · `core/technicals.py`'s ordering contract.
**Update it IN PLACE when an arm changes; never fork a dated copy.**


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
  the `B2-WIDENING-SUPPRESSED-TRIP` tripwire — both in `docs/armed-state.md`). The
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

### PUNCH LIST — ★ THE AUTHORITATIVE "WHAT'S LEFT" LIST IS NOW THE 32-ITEM CENSUS IN
### `docs/2026-08-28-closer.md` §8 (read-only census, 2026-08-28). The entries below are the
### NARRATIVE behind those lines — richer, but not the index. Reconcile against §8, not this.

- **★★ MAJOR FLAG — FINANCIALS ARE UNSCOREABLE. ROUTER + GATE SHIPPED; ENGINE NOT BUILT;
  SCOPING ORDER QUEUED behind the current open items (Vic, 2026-08-28).** BK, C, JPM and USB
  produce **no stage, no score, no band** — see the financials gate in `docs/armed-state.md`.
  **CONSEQUENCE VIC PRICED IN AND THAT A LATER SESSION MUST NOT READ AS A REGRESSION: those
  four are the ONLY bank-lens names, so D-5/D-6 BANK-LENS CALIBRATION HAS NO POPULATION until
  a dedicated financials leg exists.** `BANK-RUNG-UNCALIBRATED` is now unreachable for the
  same reason. Do NOT "restore" bank scoring to fix a calibration gap — that is the ruling
  working.
- **✅ QBTS `HIGROWTH → YOUNG` APPROVED 2026-08-28** (band `20% → 30%`, `rule2_young`,
  `stage_flip_approvals` id 1). The stage row itself is UNCHANGED — the flip persists on
  QBTS's next evaluation, not on the approval.
  **THE GENERAL CONDITION BEHIND IT IS STILL FULLY OPEN, and approving one name did not
  touch it: EVERY stage row predates its own inputs** (44 rows written 2026-08-17; series written 21–22 August). 13 names recomputed to
  the SAME stage, so the exposure is bounded and measured — but nothing re-computes a stage
  when its series changes, and the sweep is the only thing that looks.
- **★ TWO DEFECTS FOUND IN THIS SESSION'S OWN WORK — the shapes recur, so read them.**
  **(1) A defensive `except` that manufactured a confident wrong answer.**
  `tools/retire_financial_stages.py` caught `OperationalError` on an unmigrated column and
  returned `[]`, reporting "0 live rows" for four names holding eight. **A `--commit` on that
  output would have retired nothing and RECONCILED TO MATCH**, because expected and actual
  would both have been zero. Same family as the L-4c short-circuit. Fixed: migrate before
  reading, and the query now RAISES.
  **(2) A guard whose static assumption was invalidated by the same order that armed it.**
  The currency guard declared `market_cap`'s basis statically; ruling 3 had just moved that
  field's source endpoint, so the guard BLOCKED the very USD figure ruling 3 exists to
  supply. Caught by the dark diff, not by review.
- **★ AND A THIRD, IN THE PINS, FOR THE SECOND TIME IN ONE DAY:** two new pins scanned module
  TEXT for a forbidden word (`"bank"`, `"convert"`, `"key-metrics"`) and fired on the PROSE
  explaining why the thing is forbidden. Both rewritten over the AST. **These modules are
  heavily commented precisely because their rulings are subtle, so text-scan pins on them are
  structurally unsafe.** *A pin that prose can break is one a later session weakens instead
  of heeding.*

- **★★ TOP PRIORITY, RULE BEFORE ANYTHING ELSE — CITIGROUP READS *YOUNG* ON A LIVE RUN, AND
  THE STALE-STAGE PROBLEM BEHIND IT IS GENERAL (found 2026-08-28).** Full statement in the
  pickup block. Two decisions, and the second is bigger than the first:
  - **(1) Should the financials class reach the LIFECYCLE CLASSIFIER?** If it does, C leaves
    the R2 all-negative-last-3 set and stops reading pre-earnings. If it does not, C persists
    YOUNG on its next eval and gets a **30% B-2 band instead of 15%**. Scoring-path change;
    needs a ruling.
  - **(2) NOTHING RE-COMPUTES A LIFECYCLE STAGE WHEN ITS SERIES CHANGES.** Any name whose
    `fundamental_series` arrived AFTER its last evaluation carries a stage row computed
    without it. **C is merely the one where the gap flips a RULE.** Measured, not designed
    for, and not fixed here. A stage-staleness sweep across all 28 is the obvious next
    measurement and was NOT run this session.
- **★ THE FMP-BASIS *NUMERIC* SERIES BUILDER IS DELIBERATELY NOT BUILT (2026-08-28).** With
  **0 USD periods universe-wide** it would be a production write path nothing exercises, and
  it must clear two recorded traps blind: **(1) SIGN** — FMP files capex NEGATIVE while
  `build_fcf_series` computes `ocf - capex` on EDGAR's positive-outflow convention, so
  reusing it **ADDS** capex (the debt/equity ratio-vs-percent unit defect in a new costume,
  and that one ran eight days behind 654 green tests); **(2)** the R2 boundary population
  must be **re-measured on FMP basis**, never assumed to carry over.
  **`tools/ingest_fmp_usd_series.py` REFUSES LOUDLY and writes nothing if a USD period ever
  appears**, so the day the case becomes real it stops and reports. A separate order.
- **★ THE SKHY ANCHOR BASIS IS UNDECIDED, AND THE THREE CANDIDATES DIFFER BY UP TO 34%
  (2026-08-28, NO ANCHOR WRITTEN).** Free-float **$909.30B** (Vic's reference, matched to
  +0.16%) · full ADR cap **$1,141.66B** (`market-capitalization?symbol=SKHY`, the only
  cap endpoint carrying its own `date`) · Korean ordinary **$851.37B**. Any stored anchor
  must name **which basis and which listing**, and carry its price and timestamp — the ADR
  cap moves intraday.

- **★★ TOP PRIORITY, DO NOT FOLD INTO A SPEC ORDER — SKHY IS EDGAR-UNEVALUABLE, AND IT IS A
  DATA-SOURCE ARCHITECTURE DECISION, NOT A SPEC FIX (ruled 2026-08-21, L-4f).** SKHY was
  named as L-4f's primary payload and gains nothing from any form admission. **Its ENTIRE
  companyfacts is 1,863 bytes with NO `us-gaap` namespace at all** — everything in it is
  `ffd` SEC **filing-fee** data (`NetFeeAmt`, `TtlFeeAmt`, `TtlOfferingAmt`) from SK hynix's
  $1B **F-1 IPO registration statement** filed 2026-06-24 / amended 2026-07-06. F-1 is a
  registration statement, NOT a periodic report; an F-1 registrant becomes a 20-F filer only
  after its first fiscal year-end post-effectiveness. **No spec, synonym or form change can
  reach it — there is no financial XBRL to read.** Admitting F-1 would be admitting a fee
  table as a financial statement; pinned excluded. Its current EDGAR-side fail-closed reason
  is accurate and stays.
  - **✅ THE OPEN QUESTION IS ANSWERED, MEASURED 2026-08-22 (doctrine order §3.3).** It asked
    "whether a NON-EDGAR fundamentals source is wired for issuers EDGAR structurally cannot
    serve." **FMP serves SK hynix IN FULL — 10 FY rows (2016–2025) and 12 quarters, every FCF
    input populated.** The EDGAR finding above is unchanged and still correct; it was a
    statement about EDGAR, never about the issuer. Under the new doctrine the source question
    is settled — but the item does NOT close, because measuring it surfaced a new blocker:
  - **★ CORRECTED 2026-08-28 — THERE ARE *THREE* CURRENCY SURFACES, NOT TWO, AND
    `profile.currency` WAS NOT "WRONG".** This entry used to read: *"KRW is the true
    reporting currency; `profile.currency` is WRONG for this issuer."* **That was too harsh
    and is now falsified by a control.** `profile.currency = USD` is the **QUOTE** currency
    of a NASDAQ-listed ADR and is CORRECT; `reportedCurrency = KRW` is the **REPORTING**
    currency and is also correct. They answer different questions. **Control: the same
    issuer's Korean ordinary line `000660.KS` reads `profile.currency = KRW` on exchange
    KSC.** The magnitude arbitration below still stands and was never the disputed part —
    FY2025 OCF reads 53,373,126,000,000, which is KRW.
    - **★★ THE SURPRISING THIRD SURFACE, AND IT IS A LATENT ~1,028x TRAP ON A SCORE-BEARING
      FIELD. MEASURED 2026-08-28, NOT FIXED.** **`key-metrics-ttm.marketCap` for SKHY is
      served in KRW** — `1,173,390,134,823,000`, **byte-identical to `000660.KS`'s profile
      marketCap, delta exactly 0**, i.e. the HOME LISTING'S cap. That field is what
      `adapters/fmp_adapter.py:457` puts in `TickerData.market_cap` (via `key_metrics_ttm`
      at `:587`), and `core/pillars.py:237-238` divides FCF by it for the FCF-yield bonus.
      **Controls: NVDA and ARM both read `key-metrics ÷ profile = 1.0000`, so SKHY is the
      sole anomaly in the universe.** Today it is ACCIDENTALLY self-consistent (FCF is also
      KRW, so the ratio is KRW/KRW) — **a latent trap, not a live defect.** Fixing it is a
      change to a score-bearing adapter field and needs a ruling.
    - **★ AND THE ADR TRADES AT A +34.1% PREMIUM TO THE KOREAN ORDINARY** (the two caps imply
      USDKRW 1,027.79 against a measured 1,378.24). So **an SKHY market cap is
      basis-dependent by a third**, and any anchor must say WHICH LISTING it measures.
    JPM/USB/INFQ/CBRS/DPC/SPCX/XE/LLY all report USD on both endpoints, so SKHY is the sole
    tripper and there was no existing currency handling to lean on.
  - **★★ THE WHOLE CONVERSION BLOCK BELOW IS SUPERSEDED. RULED 2026-08-28 BY VIC: *USD
    ONLY.*** "Ingest only what FMP supplies natively in USD. KRW-only periods excluded with
    typed block rows — never converted. Short history accepted; YOUNG/coverage rules apply
    to whatever USD depth survives." **MEASURED THE SAME DAY: SKHY serves 129 statement
    periods across six FMP endpoints and 0 ARE USD, so the USD set is EMPTY and SKHY gets
    ZERO numeric rows plus 129 typed block rows.** What survives from the 2026-08-21
    addendum is ONLY term (7), the standing currency gate, now built as
    `core/reporting_currency.py`. **Terms (1)–(6) and the $38–40B verification anchor are
    MOOT — they governed a conversion that no longer exists.** The five ordered pins are
    moot for the same reason and are recorded superseded rather than written.
    **★ AND THE TYPED REASON IS `currency:non_usd_native`, NOT term (7)'s
    `currency:unconverted`** — "unconverted" asserts that conversion is the pending remedy,
    which the ruling removed, so the constant would make a claim the ruling has already
    falsified. Exactly the `WITHHELD_NO_CAPEX`/`WITHHELD_NO_OCF` defect L-4d DELETED rather
    than renamed. Kept below for the record, not for execution:
  - **~~RULED 2026-08-21 (Vic addendum, folded into the doctrine order §8) — SKHY IS
    EVALUATED IN USD, VIA PERIOD-MATCHED CONVERSION.~~ SUPERSEDED 2026-08-28.**
    Vic's book is USD and the decision-relevant fundamentals are USD. Terms:
    **(1)** convert per period at THAT period's rate — flows at **fiscal-period-average**,
    balance-sheet items (if ever ingested) at **period-end**; **(2) NEVER convert history at
    the ingest-date rate** — a today-rate conversion silently rewrites the past on every
    refresh, and the prohibition is to be PINNED; **(3)** FX source is the FMP forex
    endpoints (`historical-price-eod` on the KRW pair) — sole-source doctrine holds through
    the conversion; **(4)** record per row the rate used, its date basis, and provenance tag
    **`currency:krw_converted_usd`**; **(5) preserve the native figure** — conversion must be
    **auditable and reversible, never destructive**; **(6)** the endpoint disagreement stays
    on the record; **(7) STANDING CURRENCY GATE, ALL NAMES** — any row whose
    `reportedCurrency` ≠ USD without a conversion record is **WITHHELD with typed reason
    `currency:unconverted`**. SKHY is the only current tripper; the gate guards every future
    non-USD name.
  - **★★ ~~VIC'S HARD-STOP VERIFICATION ANCHOR FIRED, AND IT IS UNRESOLVED~~ — ✅ CLOSED
    2026-08-28: THE ANCHOR HAS NO SUBJECT. IT IS MOOT, NOT FAILING.** USD-only removed the
    conversion it was verifying. **Separately, the 2026-08-28 order answered what the band
    ACTUALLY MEASURED, which is the part worth carrying: it measured FY2025 OPERATING CASH
    FLOW in USD — a one-year FLOW — and was never a market cap. So the "~24x gap" against
    SKHY's ~$909.30B market cap is not a discrepancy at all: $909.30B ÷ $37.61B = 24.18x,
    a PRICE-TO-OPERATING-CASH-FLOW MULTIPLE.** Nothing was ever inverted or mis-united.
    Original text kept for the record:
    The anchor: FY2025 OCF must land in **$38–40B** at 2025-average USDKRW, and
    *"any other magnitude means the rate plumbing is inverted or mis-united — STOP and report,
    no write."* **MEASURED 2026-08-22, LIVE, READ-ONLY: it lands at $37.61B — 1.0% BELOW the
    band floor, and the miss is ROBUST** (six averaging conventions span only 0.5%:
    $37.43B–$37.61B; none reaches $38B).
    **BUT THE DIAGNOSIS THE ANCHOR NAMES IS FALSIFIED, and that was tested, not assumed:**
    `USDKRW` closes span 1,351.65–1,482.72 (order 10³ — KRW per USD, so **not mis-united**);
    dividing gives $37.6B while multiplying gives $7.6×10¹⁶, absurd on sight (**not
    inverted**); and the independently-served `KRWUSD` symbol corroborates at $37.43B (0.5%).
    **THE CAUSE IS BAND CALIBRATION.** The band came from the ruling's cited ~1,380, which
    yields $38.68B and IS in band — but **1,380 is roughly the MID-YEAR rate**, not the annual
    average (monthly: Q1 1,441–1,455, Jun–Sep 1,365–1,394, Q4 1,423–1,464). **Measured 2025
    average = 1,418.97**, 2.8% weaker. **So the RULE is right and the BAND is off, not the
    reverse** — §8.1(1)'s fiscal-period-average convention is exactly what produces 1,418.97.
    **RECOMMENDED, NOT APPLIED — VIC'S CALL:** re-set the band to **$37.4–37.8B**, or restate
    it as a rate assertion (`2025 avg USDKRW ∈ [1,410, 1,430]`) so it tests plumbing rather
    than a remembered rate. **I did not move the band myself: a verification anchor the
    verifying session may re-fit is not a verification anchor.**
  - **★ FMP's `USDKRW` AND `KRWUSD` ARE NOT EXACT RECIPROCALS** (found while running the
    anchor). Same-day products over 301 common days: mean **0.9944**, range 0.9882–1.0098 —
    independently sourced or rounded, not derived from each other. So there is a **~0.6% noise
    floor** on any FX-derived figure, and **the choice of pair symbol is itself a basis
    decision**: the per-row record required by term (4) must capture **WHICH SYMBOL** was
    used, or the conversion is not reproducible.
  - **THE FIVE ORDERED PINS ARE SPECIFIED BUT NOT WRITTEN — they land with the expansion.**
    ingest-date-rate prohibition · SKHY FY2025 magnitude anchor · gate behaviour on an
    unconverted non-USD row · rate-recorded-per-row · KRW recoverability. **None is
    expressible today** — there is no conversion path, no gate and no `currency:unconverted`
    reason in the runtime, so each would be a vacuous test, and *a sweep that cannot fire
    proves nothing*. **The magnitude anchor is unwritable for a SECOND, independent reason:
    the band it would assert is the one that just failed.** **LYTE/FLTW are a DIFFERENT case and the L-4f
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
  - **✅ CLOSED 2026-08-22 (L-4d.1) — THE THIRD CAPEX TAG IS ARMED AND LLY IS RECOVERED.
    Order `docs/orders/2026-08-22-l4d1-lly-capex-basis.md`, report
    `docs/l4d1-lly-capex-basis.md`.** `PaymentsToAcquireOtherPropertyPlantAndEquipment`
    added as the THIRD chain entry behind the two armed tags; LLY resolves $9.893B with 6
    FY FCF points; `fundamental_series` 2374 → **2488 rows / 20 tickers**, coverage
    **19 → 20 of 28**, +114 rows reconciled exactly (0 restatements, 0 superseded), every
    other table +0. Suite 953 → **975**; 9 of 41 pins verified to FAIL pre-fix.
    **LLY does NOT join the R2 YOUNG all-negative-last-3 set** — that stays IONQ/QBTS/RKLB/C.
    - **★ THIS ORDER OVERTURNED A COMMITTED PIN, AND THE REVERSAL IS THE PART TO READ.**
      `test_LLY_third_tag_is_deliberately_absent` (`c7a3813`) asserted the OPPOSITE and
      opened "RULED OUT, NOT OVERLOOKED". Superseded on TWO grounds: **chronology** (the
      pin is L-4d step-2 era; the governing ruling post-dates it and cites the L-4f ARM
      precedent, which did not yet exist) and **retired predicate** (its rationale was a
      failed FMP reconciliation; the ARM precedent makes that an advisory basis note
      against the FEED, not a disqualification of the tag). **The pin was NOT wrong when
      written** — it recorded a real ruling later re-ruled on new evidence. Renamed
      `test_LLY_third_tag_is_ARMED`, carrying the original rationale verbatim; the matching
      `# DELIBERATELY NOT ADDED` source comment was rewritten, not deleted.
    - **THE FIXTURE-AGING HAZARD DID NOT RECUR, AND THAT IS MEASURED.** Unlike L-4d, **no
      EDGAR fixture contains the new tag** (all 9 read zero), so nothing aged and the
      `V.json` pin is unaffected. Pinned, so a future re-record forces the question again.
    - **THE CONFLICT PATH IS UNREACHABLE.** Only LLY and FN file the tag, both
      `freshtags=1`; FN's copy is **5110d stale** behind a fresh primary. The staleness
      gate does the work, not `conflict_check=False`. Pinned as the FN shape.
    - Original ruling text, retained: **The L-4f ruling on ARM is the governing precedent
      and settles the principle:
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
    same silent-expiry shape. **8 of 19 specs have no synonym chain** (gross_profit,
    operating_income, net_income, total_assets, current_assets, total_liabilities,
    current_liabilities, operating_lease_liability); `operating_lease_liability` is also
    stale on LLY. Feeds L-4e scope. Measured, not fixed.
    **RE-MEASURED AT THE L-4d.1 CLOSE 2026-08-22: was 9, now 8 — `capex` left this list
    when its chain went to three tags.** The count is taken from the spec table, not
    remembered; re-measure it rather than trusting this line.
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
- **★ CLOSE STATE GOES TO `docs/closes/`, NOT INTO THIS FILE (Vic ruling 2, 2026-08-28).**
  Every close writes its FULL measured state — md5 trail, write points, expected-vs-actual
  reconciliation, per-table counts — to a DATED file `docs/closes/YYYY-MM-DD-<slug>.md`.
  **CLAUDE.md carries ONLY the ~10-line STATE POINTER block** (HEAD · suite · md5 · backup
  name · full-state file · open-items pointer) and **NEVER a full state table.** The pointer
  block is REPLACED at each close, not appended to — one pointer, always current.
  **★ ONE CARVE-OUT, RULED 2026-08-28: `docs/armed-state.md` IS A LIVING FILE, UPDATED IN
  PLACE, AND IS NEVER DATED OR FORKED PER CLOSE.** Close state measures a moment; armed
  state is the current answer to "what reads what" and carries forward. Dating it would
  stack superseding copies, which is the failure this rule exists to kill.
  **WHY: state tables accreted three deep here, each labelled "supersedes every table below
  it", and a cold-start session had to read all three to learn one md5.** A pointer that is
  always current is cheaper to trust than a stack that has to be date-ordered by hand.
  **The narrative and the rulings STAY here** — they are not state tables. **ARMED STATE
  ALSO MIGRATED** (Vic, 2026-08-28) to **`docs/armed-state.md`**, but as a **LIVING file
  updated in place, NOT a dated close snapshot**: "what reads what" carries forward across
  closes, so dating it would stack superseding copies — the exact failure this rule kills.
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

- **★★ STEP 4 — RULED 2026-08-21 ONTO FMP BASIS, AND THE READ-ONLY FEASIBILITY MEASUREMENT
  CAME BACK MUCH WEAKER THAN THE RULING ASSUMED. NOT ARMED. NOT EXECUTED.**
  **VIC'S RULING (2026-08-21):** coverage expansion **proceeds on FMP basis**; **EDGAR
  YTD-assembly is NOT to be built** — the limit that parked CBRS/DPC/SPCX/XE "dissolves
  under the new source"; JPM/USB/INFQ/SKHY are re-examined on FMP basis too. Expansion was
  **deliberately NOT executed** in the doctrine order; that order reports feasibility only.
  **MEASURED 2026-08-22, LIVE, READ-ONLY — the premise holds for 1 of 8 outright, partly for
  2 more, and FAILS for 5.** Full table + method in the order doc §3. The YTD-assembly limit
  specifically DOES dissolve (FMP serves annual cash-flow where EDGAR could not assemble it),
  but that is not the same statement as "the 8 become evaluable".

  | Ticker | FMP FY rows | verdict on FMP basis |
  |---|---|---|
  | **JPM** | 10 | **NO — and actively WRONG.** `capitalExpenditure` is 0 on all 10 FY + all 12 qtrs, so FMP publishes `freeCashFlow` **== `operatingCashFlow`** ($100.867B for FY2025). A confident false number where EDGAR correctly refuses. |
  | **USB** | 10 | **NO — identical trap** (capex 0/10 FY, 0/12 qtr). |
  | **INFQ** | 3 | **NO** — capex nonzero only 1/3 FY, revenue only 1/3. |
  | **SKHY** | 10 | **YES** (10 FY + 12 qtrs fully populated). Currency **RULED 2026-08-21** — store USD via period-matched conversion, terms in the punch-list entry. **One open item: Vic's verification band failed by 1.0% and needs re-setting — plumbing verified sound.** |
  | **CBRS** | 4 | **FY yes; QUARTERLY NO — the quarterly rows are MANUFACTURED.** |
  | **DPC** | **1** | **NO** — one FY point cannot feed a 3-FY signal. |
  | **SPCX** | 3 | FY **marginal** (exactly 3); quarterly holed. |
  | **XE** | 3 | **NO — the rows are 2025, 2022, 2021; FY2023 + FY2024 MISSING.** |

  - **★ JPM/USB ARE THE PRESENCE≠POPULATED TRAP IN ITS WORST FORM, AND THE RULING SHOULD
    WEIGH IT: migrating them to FMP basis converts a CORRECT fail-closed refusal into a
    SILENT FALSE POSITIVE.** EDGAR's `capex:no_tag` is the more truthful of the two answers.
    Any FMP-basis builder must read `capitalExpenditure == 0` across a whole series as
    **ABSENCE, NEVER ZERO.**
  - **★ CBRS's QUARTERLY ROWS ARE ALLOCATED, NOT REPORTED.** Within each year Q1 and Q2 are
    **identical to the cent** (2024: both 155,906,500 / −5,894,000; 2023: both −35,092,500 /
    −227,000), the `.5` remainder is the signature of a division by two, and **Q3/Q4 do not
    exist for any year**. They do NOT reconcile to the annual row either (2024 annual OCF
    451,978,000; the pair sums to 311,813,000) — so the "halved annual" reading is WRONG and
    was checked before being written down. **FMP has not dissolved the YTD problem here, it
    has papered over it with values that look complete — a worse failure mode than EDGAR's
    honest `ttm_unavailable`.** CBRS FY data is usable; CBRS quarterly must not feed TTM.
  - **★ XE's FEED-REPAIR TICKET IS CONFIRMED AND WIDENED: the FY2023/FY2024 hole is in the
    CASH-FLOW endpoint too, not just `income_annual`.** It is an issuer-level FMP gap. A
    3-FY window that skips two years is not three consecutive years, and the R2 last-3-FY
    signal would read straight across the hole.
  - **TWO CONVERSION TRAPS ANY FMP-BASIS BUILDER MUST CLEAR, recorded BEFORE the build.**
    **(1) SIGN:** FMP files capex **negative**; EDGAR files it as a **positive outflow
    magnitude**, and `build_fcf_series` computes `fcf = ocf - capex`
    (core/fundamental_series.py:410) — reusing that expression on FMP input **ADDS** capex.
    This is the debt/equity ratio-vs-percent unit defect in a new costume, and that one ran
    eight days behind 654 green tests. **(2) THE STEP-4 SIGNAL MOVES:** LLY's last three FY
    FCF are `[+0.792B, +3.760B, +8.972B]` on EDGAR basis but `[−3.152B, +0.414B, +8.972B]`
    on FMP basis — **two of three flip sign.** LLY still does not join the R2
    all-negative-last-3 set (FY2025 is positive either way, so that set **remains
    IONQ/QBTS/RKLB/C**), but the doctrine switch is **NOT signal-neutral** and the R2
    boundary population must be **re-measured on FMP basis before step 4 arms**, never
    assumed to carry over.
  - **THE PRODUCTION PAYLOAD DOES NOT FETCH ANY OF THIS TODAY.** `fetch_payload`
    (adapters/fmp_adapter.py:556) requests `cash-flow-statement?period=annual&limit=1` — one
    annual row, **no quarterly cash-flow at all.** FMP-basis expansion is an **endpoint-scope
    change**, not a re-pointing of an existing fetch.

- **★ SUPERSEDED CONTEXT BELOW — kept because its reasoning is still the record of WHY the
  EDGAR path stopped, but the conclusion "the next order is step 4 on EDGAR coverage" is
  overtaken by the doctrine above. STEP 4 (YOUNG SUPPLY BLOCK) — THE EDGAR-BASIS BLOCKING
  CONDITION WAS DISCHARGED AS OF L-4d.1 (2026-08-22). IT IS NOT ARMED.**
  `fundamental_series` covers **20 of 28** (was 4, then 15, 18, 19). Of the 8 remaining,
  **4 are correctly fail-closed** (JPM/USB/INFQ/SKHY) and **4 are explicitly ruled OUT of
  scope** (CBRS/DPC/SPCX/XE — `ttm_unavailable`, YTD-only filers). **For the first time
  every uncovered name is either correctly fail-closed or ruled out of scope — no name is
  now uncovered because of an unaddressed limit of ours.** That was the exact condition
  the 2026-08-17 ruling blocked on: the YOUNG/blocked boundary no longer reflects "which
  names happen to have FCF data".
  **CAVEAT THE RULING SHOULD WEIGH, NOT A BLOCKER: "ruled out of scope" is not the same as
  "correctly fail-closed."** The 4 YTD-only filers still lack FCF because of an assembly
  capability we chose not to build. If step 4 hard-blocks them, it blocks on our limit —
  bounded and named now, rather than unexamined.
  ARM's admission and the LLY rider are both done; the two feed-repair tickets below join
  that work.
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

## SESSION-OPEN CHECKLIST — RESCOPED FOR THE DOCTRINE (doc-level, 2026-08-28)
Run in this order at every wake-up. **Steps 1–2 are the peer-process protocol below and are
unchanged.** Steps 3–5 are the doctrine rescope Vic ordered as step (e) of the closer order.

1. **PEER-PROCESS CHECK** — `ps aux | grep claude`, `ListAgents`, verify your OWN pid
   empirically by PPID walk, enumerate orphans by `ppid 1`. Full rules below.
2. **STATE VERIFICATION** — HEAD, suite count, caliber.db md5 (checkpoint WAL first),
   `git status`, `git rev-list --count origin/master..master`. Mismatch against the
   chat-carried pointers ⇒ **STOP, no writes.**
3. **★ THE LIVE-EDGAR PRE-FLIGHT REMAINS MANDATORY ON EVERY LIVE RUN. IT IS *NOT* RESCOPED
   TO ARBITRATION-ONLY, AND THAT IS THE MEASUREMENT, NOT A PARTIAL IMPLEMENTATION.**
   The doctrine says EDGAR is the arbiter, invoked in three cases. **The code disagrees, and
   was re-confirmed by grep on 2026-08-28: EDGAR is SCORE-BEARING ON EVERY RUN** via
   `yf.sic = edgar.sic` → `select_lens(...)` (evaluate.py:300/310, batch/runner.py:254/255),
   `build_panel(yf, fred, edgar, …)`, and `score_growth(yf, edgar, lens)`; and `fetch_edgar`
   is a **hard gate** (evaluate.py exits 1; batch persists a `failed` row per ticker).
   Rescoping the pre-flight while that holds would remove the one mechanism standing between
   an intermittent SEC 403 and **28 `failed` rows in production**. **Vic's option (a) —
   SEQUENCE IT — is what is implemented: the pre-flight stays until EDGAR is genuinely off
   the pipeline path.** Re-read doctrine §5 before touching it.
4. **FMP IS THE SOURCE.** Every pipeline input — series, TTM, scoring, market cap — comes
   from FMP. **EDGAR is invoked only for arbitration (>25% divergence), filed-tag provenance
   on a challenged verdict, and rulings.**
   **"THE SANITY GATE" *IS* THE 25% DIVERGENCE CHECK — one trigger, not two (ruling 6,
   2026-08-28). There is nothing separate to build.**
5. **USD ONLY.** Any non-USD MONETARY score-bearing field is blocked with a typed reason and
   **never converted** (`core/reporting_currency.py`). Any non-USD statement period is
   blocked, never ingested. SKHY is the only current tripper.
6. **BEFORE ANY EVALUATION RUN, run the stage-freshness sweep** —
   `python -m tools.stage_freshness_sweep`. It is read-only. **An unapproved flip HALTS the
   run (exit 6) and persists nothing**, so finding out at sweep time is strictly cheaper.

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
- **★ WRITE `docs/closes/YYYY-MM-DD-<slug>.md` FIRST, THEN UPDATE THE POINTER BLOCK IN
  CLAUDE.md.** Full state to the dated file; the pointer block gets HEAD, suite, md5, backup
  name, the close-file path and the open-items pointer — and nothing else. Ruling 2,
  2026-08-28. Index the new file in `docs/closes/README.md`.
  **If an ARM CHANGED this session, edit `docs/armed-state.md` IN PLACE — do not date it,
  do not copy it into the close file.**
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
  - **✅ CLOSED 2026-08-28 (rulings 3 + 4) — BOTH HALVES WERE ALREADY DONE, AND THAT IS THE
    FINDING. The ticket below was STALE, not outstanding.** Kept in full because "we fixed
    it" and "it was never broken" are different claims and the difference is the record.
    ORIGINAL TEXT: *live Prov source strings in core/technicals.py, core/pillars.py, and the
    shared trajectory builders in core/datatypes.py still read "yfinance*" while stamping
    FMP-sourced fields. Cosmetic mislabel, no behavioral/grade impact; needs source-threading
    + test updates. Also probe.py (Phase-0 fixture recorder) still imports yfinance and is
    now dead — archive/remove when convenient.*
    **MEASURED:** every live Prov source reads `fmp` / `fmp+EDGAR` / `fmp/...` (25 of 25 on
    NVDA); `analyze_technicals` takes `feed_source` as a PARAMETER and both call sites
    (evaluate.py, batch/runner.py) pass `yf.feed_source`, stamping `fmp/price_history`. An
    AST sweep for `yfinance` string literals across all non-test, non-vendor code returns
    **DOCSTRINGS ONLY** — teardown history, the D/E unit-defect explanation, and lens_select's
    industry-string examples. **Those docstrings must NOT be "corrected": they are the record
    of the ratio-vs-percent defect.** **`probe.py` AND `probe_fmp.py` DO NOT EXIST** — both
    deleted at the fixture migration. **45 historical `field_provenance` rows still read
    `yfinance/*` and are LEFT UNTOUCHED per ruling 3** (supersede, never purge).
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
- EDGAR — **NO LONGER "IN PROGRESS". DEMOTED TO THE AUDIT LAYER 2026-08-22 by the
  FMP-SOURCE / EDGAR-ARBITER doctrine** (see the ▶▶ DOCTRINE section at the top of this
  file). SEC filings integration; unlocks "high" confidence (the wired secondary source that
  makes the anti-launder NOTE reachable again).
  E-1 DONE (XBRL extraction, 6977a72). E-2 DONE (field resolution, 25b40c5).
  E-3 ARMED 2026-08-09 (031506f) — live at both boundaries. E-4 DONE (verdict-high
  reachability): the note is NOT revived, see the E-4 finding + EDGAR section, both now in
  docs/phase-archive.md.
  **NOTHING HERE IS UNWOUND OR DELETED — the machinery stays, and DELETING EDGAR-PATH CODE
  REQUIRES A VIC RULING** (pinned, `tests/test_doctrine_edgar_arbiter.py`). Further EDGAR
  COVERAGE expansion is off the roadmap; EDGAR arbitration capability is not.
  **NOTE the unresolved contradiction: EDGAR is still SCORE-BEARING on every run
  (SIC → lens, panel, growth pillar) and `fetch_edgar` is still a HARD GATE. See the ★
  pre-flight entry in the DOCTRINE section — awaiting ruling.**
- **H-4 (EBITDA leg / EDGAR D&A tag spec) — PARKED INDEFINITELY 2026-08-22. DEMOTED FROM
  BLOCKER TO OPTIONAL AUDIT TOOLING** by the doctrine above. It was "DEFERRED behind EDGAR
  expansion" (docs/h-fcf-scoping.md:235) — i.e. a live blocker on the EBITDA leg and on the
  NULL `reinvestment` column (core/fundamental_series.py:435, whose `blocked_on` string still
  reads "no depreciation/amortization spec (H-4)"). **Under FMP-as-source the D&A input comes
  from FMP if it comes from anywhere, so an EDGAR D&A spec is no longer on the critical path
  for anything.** Not deleted, not scheduled. If the EBITDA leg is ever wanted, it is an
  FMP-basis order, not this one.
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
  from what production requests (the Phase-0 probe_fmp.py did drift — it targeted the
  retired v3 API and wrote keys the adapter no longer read). **`probe_fmp.py` NO LONGER
  EXISTS — deleted at the fixture migration; verified absent 2026-08-28.** Retained here as
  the REASON the recorders reuse the adapter's own path.
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
