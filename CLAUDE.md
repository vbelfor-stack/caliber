# CLAUDE.md — CALIBER (operational context; auto-loads every session)
# Detailed build spec lives in Claude.md (Jul 10). This file is the living operational memory.

## ▶ SESSION PICKUP — READ THIS FIRST (rewritten at L-1b, 2026-08-17)
Opening a session with **"resume — execute the next order in CLAUDE.md"** is enough. This
section is the cold-start record; everything below it is the durable detail.

### STATE AT L-2a 2026-08-17
**PHASE L IS IN FLIGHT.** Order: `docs/orders/2026-08-16-phase-l-lifecycle-classifier.md`
(COMPLETE, rulings R1–R11, amended by the L-1c ruling 2026-08-17).
**ARMING ORDER RULED 2026-08-17:** step 0 housekeeping → step 1 tags in evaluate.py
(ANNOTATE-AND-PERSIST, a sanctioned production write) → step 2 full-universe dark run →
step 3 B-2 stage-conditioned tolerances → step 4 YOUNG supply block. ONE STEP PER WORK
ORDER, dark-verified before the next arms. **NEXT: L-2a commit 2 = step 1.**
**STANDING: NO SYNTHETIC CALIBRATION, EVER** — `GUARD-TOLERANCE-UNCALIBRATED` and
`REINVESTMENT-THRESHOLD-UNCALIBRATED` stay until REAL data calibrates them. A tolerance
tuned on generated series is worse than no tolerance.
Nothing in §5 is armed. The classifier is not wired into `batch/` or `evaluate.py`.
**STANDING RULE ADDED 2026-08-17: any commit closing a ruled work order PUSHES IMMEDIATELY
— no per-commit approval. Unpushed-at-close is the exception, not the norm.**

| | |
|---|---|
| HEAD | L-2a on master, pushed |
| Suite | **769** (682 + 87 in tests/test_lifecycle.py) |
| caliber.db md5 | **e13cbee6f204da1f117beca193e5b7df** — UNCHANGED by all Phase L work so far |
| evaluations | 36 rows, max id **225** |
| Backup | `caliber.db.pre-rerun-2026-08-15.bak` @ 54aa42e5 (pre-write, local only) |

- **L-1a (8ebacd2, pushed):** `income_annual` limit 4 → 10 per R9. Depth MEASURED at 10 on
  the adapter's own path for all nine tickers, FY2016–2025 contiguous. Fixture baseline
  moved by SPLICE ONLY (ruled 2026-08-16) — a full re-record was REJECTED for this phase
  because it dragged in fresh vendor data (4 pillar cells moved, recorded in the order file
  as observed drift, deferred).
- **L-1b (this commit):** `core/lifecycle.py` + `core/lifecycle_config.py` +
  `tools/probe_lifecycle.py` + `fetch_dividends` + three `lifecycle_*` tables, and the §7
  test gates. **TWO LATENT DEFECTS FIXED** in the adopted build — see the commit message.
- **L-1c (2026-08-17):** cyclical-guard definition ruled and implemented (prior peak =
  max FY revenue strictly BEFORE the streak start year); **bank-lens names now classify on
  NET REVENUE** (`revenue - interestExpense`), never gross; R6 default 1.50 ratified with
  the flag kept on every reading.
- **L-1d (2026-08-17) — BOTH CYCLICAL FINDINGS CLOSED BY RULING.**
  **THE GUARD IS NOW PEAK-TO-PEAK** (two most recent local peaks; permit iff later < earlier;
  strict, no tolerance; both peaks logged, flagged `GUARD-TOLERANCE-UNCALIBRATED`). A
  magnitude bar was REJECTED — it tests trough depth, and deep troughs are what cyclicals do
  (MU fell ~50% in FY2023 while secularly fine). Fewer than two local peaks REFUSES the
  permit as a GATE (no `INPUTS-INCOMPLETE`; other rules still classify) — distinct from the
  streak-spans-window case, which is verdict-level.
  Peaks are logged for EVERY cyclical evaluation (not only on comparison) — MU's guard does
  not fire, so comparison-only logging left the calibration set EMPTY; fixed in c87815a.
  **NOTE THE LIVE TABLE HAS NEVER EXERCISED THE GUARD:** MU is the only cyclical name and
  its streak is 0. The evidence the guard works is the harness + synthetics, not the table.
  **HARNESS, ordered re-run, same seed:** 9,966 evaluable → **46.6% permit / 53.4% refuse**
  (L-1c was 100%/0%). The guard is two-sided at last;
  `test_the_guard_can_both_permit_and_refuse_so_it_is_not_vacuous` exists to catch a fourth
  one-sided definition, since one-sidedness survived two rulings unnoticed.
  **RULE 2 NOW HAS A CYCLICAL GUARD:** for cyclical names YOUNG is blocked if the window
  holds an FY with positive operating margin AND positive FCF (earned ⇒ trough, not
  pre-earnings). MU FY2023 now reads **MATURE**, measured. `YOUNG-UNCALIBRATED` still fires
  wherever YOUNG is reached; a block emits `CYCLICAL-GUARD-HELD-OUT-OF-YOUNG`.
- **L-1e (2026-08-17) — BOTH GUARD PRECONDITIONS FAIL CLOSED. THE SYMMETRY IS THE POINT:
  the peak gate denies DECLINE when it cannot measure, the FCF gate denies YOUNG when it
  cannot measure.** Neither grants a tag on evidence it could not gather.
  (1) Cyclical name with NO FCF series → YOUNG BLOCKED, `CYCLICAL-GUARD-UNEVALUABLE-FCF-
  ABSENT`. **This departs from R1's usual direction on purpose** (a missing input now DENIES
  a tag rather than permitting one) because the exposure is trough-reads-YOUNG; a
  pre-earnings cyclical with no FCF series is a feed problem, not a guess.
  (2) Any missing FY in the measured window → peak guard REFUSES, `PEAK-GUARD-SERIES-GAP`;
  peaks are not even computed on a gapped series, so fabricated structure cannot reach the
  calibration set. Contiguity is a PRECONDITION — "adjacent across a hole" is deliberately
  undefined. A real hit is a feed-repair ticket and the reason says so.
  **BOTH ARE PROVABLY INERT LIVE, measured not assumed:** all nine names are contiguous
  FY2016–2025, and MU (the only cyclical lens) has 6 FY FCF points. No dark run was ordered
  or needed.
- **PHASE L PUNCH LIST (ruled, deferred):** calibrate
  `REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL` on the FULL UNIVERSE after §5 arms. 1.50 stands
  until then and every reading that consults it stays flagged
  `REINVESTMENT-THRESHOLD-UNCALIBRATED`. No tuning on a four-name sample.
- **PHASE H CLOSED EXCEPT H-4** (deferred; blocker is the missing D&A spec). **PHASE M
  still parked**, and L blocks it.

- **PHASE H IS FULLY CLOSED EXCEPT H-4.** H-1 built+dark, H-2 ruled, H-3 armed.
- **H-4 (EBITDA leg) REMAINS DEFERRED behind EDGAR expansion** — no D&A spec exists among
  the 19, the same blocker that makes reinvestment NULL. **NOTE: EDGAR is now
  FLAKY-AVAILABLE rather than blocked (see the re-ruling below). That MAY unblock H-4
  sooner than expected. IT DOES NOT UNBLOCK IT TODAY** — the blocker is the missing D&A
  spec, not reachability, and reachability is intermittent besides.
- **PHASES L AND M ARE PARKED, AWAITING VIC'S CALL.** Not scoped, not started.
- **ids 216-220 — OPEN RULING RESOLVED 2026-08-15.** The armed pass was re-run;
  **ids 221-225 SUPERSEDE 216-220** via the new `supersedes_id`/`supersede_reason` trail.
  Both effects verified, WU's HIGH-LEVERAGE flag confirmed correct, attribution clean
  (lens class empty). 216-220 remain byte-identical — appended and linked, never edited.
  Order + full terms: `docs/orders/2026-08-15-rerun-armed-pass.md`. Detail below.
- **EDGAR RE-RULED: INTERMITTENT, NOT BLOCKED.** 403s observed AND cleared within one
  session; a plain `curl` probe disagreed with the adapter path seconds later. Standing
  discipline added: pre-flight ALL required endpoints ON THE ADAPTER'S OWN FETCH PATH
  immediately before any live-EDGAR run — a stale probe is not a pre-flight.
- **CORRECTION ON RECORD: EDGAR IS SCORE-BEARING.** It selects the lens via SIC
  (`batch/runner.py`: `yf.sic = edgar.sic; lens = select_lens(...)`). The long-standing
  "EDGAR can only move a confidence label" framing was WRONG and is corrected throughout.

**WHERE WE ARE — PHASE D IS CLOSED (2026-08-09).** All five valuation lenses are rate-aware
and ARMED, on THREE DIFFERENT MECHANISMS. Ethos rule 10 is fully built.

| Mechanism | Lenses | Shape |
|---|---|---|
| panel-anchored | compounder, cyclical, standard | MIN across available anchors (RULED permanent) |
| rate-shifted thresholds | growth | EV/Rev thresholds x k=(R0+ERP)/(R+ERP); R0=4.0, clamp [0.60,1.80] |
| cost-of-equity | bank | P/B vs justified P/B = ROE/CoE; RATIO ladder + excess-ROE gate |

- growth: R0=4.0 is PROVISIONAL — **revisit if the 10Y exits 3–6%**. Clamp locked.
- cyclical: TRAILING basis + peak/rollover HARD GATE capping at 2.
- bank: ladder is on the RATIO, never the difference (scale-dependence ruling).
- ARMED_LENSES != ARMED_PANEL_LENSES, deliberately. "Armed" does not mean "panel-scored".
- Last live proof: the value trap was caught on C — 1.08x book, screen-cheap, ROE under CoE,
  scored 4 -> 3 by the armed instrument.

**OPEN TRIPWIRES — each REPORTS TO VIC before its result is treated as validated:**
1. **First production STANDARD-lens eval** — report the full panel readout. No golden ticker
   is natively standard-lens, so that first live case is the only real evidence the mapping
   will ever have had.
2. **First live BANK eval landing in rung 4 or 5** — flagged `BANK-RUNG-UNCALIBRATED`. Those
   rungs are PROVISIONAL-UNCALIBRATED: no calibration bank (JPM/BK/USB/C) trades below
   justified book, so they are reasoned, not measured.
3. **β SINGLE-SOURCE CAP** on the bank pillar (`_cap_beta_confidence`) — β is FMP-only, has no
   cross-check, and moves CoE directly. SELF-RETIRES the day a corroborated second β source
   lands; no code change needed.

**PHASE G SCOPING — DONE 2026-08-11. Report: docs/g-scoping.md. NOTHING IMPLEMENTED.**
Root cause confirmed and the fix is exact, but TWO MEASURED FINDINGS CUT AGAINST THE
PREMISE THAT MOVED G UP THE ROADMAP — both need a ruling before any G build starts:
- **G'S ENTIRE REACH IS ONE CELL: own-history goes 3/20 -> 4/20 readings.** Of the 17
  missing, 15 are missing BY CONSTRUCTION (own-history is trailing-earnings-only) and 1
  is V (no share series at any basis; measured 0 -> 0 under the fix). Only NOW's cell is
  a split defect. The 15-cell trailing-only restriction is the REAL coverage constraint
  and is a DIFFERENT piece of work, deliberately not scoped.
- **ZERO SCORES MOVE** across the golden five + four banks, even with the cyclical lens
  FORCED. Own-history feeds METRIC_EARNINGS_YIELD only, and cyclical is the only armed
  panel lens on it — so own-history can move a score through cyclical AND NOWHERE ELSE.
  NOW is a GROWTH ticker (rate-shifted, no panel), so its restored anchor is INERT; and
  NOW reads +0.51pp CHEAP vs its own history, so under MIN it would never bind anyway.
  MU is the only cyclical name and it has no truncation. Per-ticker: NOW 2 -> 19 quarters
  (anchor restored), GOOG 17 -> 20 (accuracy, median 4.43% -> 4.34%), all others unchanged.
G IS STILL WORTH DOING — as LATENT-TRAP REMOVAL AND ACCURACY, not coverage recovery.
KEY TECHNICAL FINDINGS (all measured, see the report):
- The share series is MIXED-BASIS, not pre/post-split: post-split filings restate SOME
  prior period-ends (annual comparatives) and not others (original 10-Q cover pages), and
  instant_series dedupes by period-end keeping whichever sorts first. A naive adjacent-
  ratio detector fires 3x on GOOG (20:1, 1:20, 20:1) and poisons 2 of 20 quarters — while
  THE MEDIAN BARELY MOVES (4.43 -> 4.26). **A G validation that compares medians will pass
  a broken implementation. Per-point assertions are mandatory.**
- THE WELL-POSED RULE (no discontinuity inference): a fact is on the basis in effect at its
  FILING date. adjusted = raw x prod{ratio : split.ex_date > fact.filed}. Verified exactly
  on live SEC data — GOOG's two 2021-12-31 rows reconcile to 0.003%.
- **BLOCKER: _extract_xbrl_facts DROPS `filed`** (keeps start/end/fy/fp/form/accession).
  Accession YEAR is not a substitute — it separates GOOG's two 2021-12-31 rows but NOT
  2022-03-31 from 2022-06-30, which straddle the split and are both `-22-`.
- SINGLE-SOURCE RISK IS REAL BUT MITIGABLE — three witnesses, all measured, all agreeing:
  FMP /stable/splits (GOOG 20:1 ex-2022-07-18, NOW 5:1 ex-2025-12-18); the EDGAR
  RESTATEMENT RATIO, already in the fetched payload at zero cost (GOOG 19.99937, NOW
  5.00001); and the EDGAR TAGGED RATIO StockholdersEquityNoteStockSplitConversionRatio1
  (GOOG 20, NOW 5), one concept away. Two of three are INDEPENDENT OF FMP.
  Take the RATIO corroborated, the DATE from FMP — the EDGAR date is a declaration/record
  date, not an ex-date (GOOG 07-15 vs 07-18). Disagreement -> WITHHOLD, never pick a side.
- NEW RISK RECORDED: price-history depth is an UNDOCUMENTED DEPENDENCY. fetch_payload asks
  for `limit=365` but FMP returns 1,255 rows (~5y) and own-history's whole depth rests on
  that. If FMP ever honours the limit, EVERY own-history series silently goes to 0/20.

**G RULINGS ISSUED 2026-08-11 (all accepted, permanent unless re-ruled):**
- G PROCEEDS, scoped small. Fix = MIXED-BASIS RULE (basis in effect at FILING date).
  NAIVE ADJACENT-RATIO DETECTION REJECTED PERMANENTLY (GOOG: 3 false fires, 2/20 poisoned,
  median-invisible). The `filed`-field blocker is in scope.
- PER-POINT ASSERTIONS MANDATORY in G validation; median checks proven insufficient.
- Split ratio: 2-OF-3 WITNESS CORROBORATION REQUIRED; DATE FROM FMP; declaration-vs-ex-date
  distinction documented. PRECEDENT: first corroborated-by-design input, TEMPLATE FOR THE
  FUTURE BETA CROSS-CHECK.
- Pin the limit=365 risk immediately. DONE.
- Trailing-only expansion = PHASE H CANDIDATE, not scoped. Cost/value paragraph delivered
  in docs/g-build.md §6.
- CLAUDE.md per-phase maintenance RATIFIED as a standing rule.

**G-1/G-2/G-3 BUILT AND DARK 2026-08-11 — report docs/g-build.md. NOTHING ARMED.**
Suite 577 -> 612. caliber.db md5 unchanged 54aa42e5.
- G-1 GATE PASSED: `first_filed` captured, EARLIEST-WINS across the accession tie-break
  (a later filing repeating a value verbatim did not restate it). Resolution diff EMPTY —
  171 fields (9 tickers x 19 specs) on identical cached companyfacts, 0 diffs.
- G-2 GATE PASSED: GOOG 3/3, NOW 3/3, C 2/3 corroborated; V 1/3 REFUSED AND FLAGGED.
  Agreement is exact — GOOG 20 vs 19.99937, NOW 5 vs 5.00001.
  NEW DESIGN ELEMENT — SCOPE HORIZON: EDGAR XBRL starts ~2009, so pre-XBRL splits can
  NEVER earn a second witness (MU 1994-2000, JPM 1982-2000, USB 1979-2001). Splits
  predating the oldest share filing are OUT-OF-SCOPE, not uncorroborated, and are silent.
  Without it the report emitted 33 alarming NOTEs across nine tickers and would have
  desensitised the one warning that matters.
- G-3 GATE PASSED PER QUARTER: GOOG 17 -> 20 (all 17 existing IDENTICAL, recovered points
  3.97/4.05/3.99 vs a ~4% norm — the naive rule's 0.25%/0.20% signature ABSENT),
  NOW 2 -> 19, all seven others identical point-for-point. ZERO existing quarters moved
  anywhere. Dark surface wired at BOTH boundaries, live-only (fixtures predate G-1).
- **TRAP FOUND AND CLOSED BY THE DARK PASS — the build's own headline.** The restated
  series has NO truncation to fall back on, so an EMPTY split list is not a safe default:
  run on GOOG with events=[] it emits 2022-03-31 at 81.02% — the exact artifact G exists
  to remove. An empty list is ambiguous between "never split" and "could not find out".
  `restatement_blocked` refuses unless the split state is ESTABLISHED; `own_history_restated`
  takes the REPORT, not a list, so it cannot be called ambiguously. On refusal the
  truncated series stands. THE FIX WAS CORRECT ON BOTH TICKERS IT WAS BUILT FOR AND WOULD
  STILL HAVE REGRESSED THE PIPELINE ON THE THIRD.

**G-4 ARMED 2026-08-11 — PHASE G IS CLOSED.** Report docs/g-build.md (G-4 section).
Ruled ARM on CORRECTNESS, not score movement: GOOG's series was known-wrong and feeds the
binding anchor class. restatement_blocked RATIFIED (empty list != safe default). Scope
horizon RATIFIED (alarm desensitization is a correctness problem; V's warning must stay the
only one). Suite 613. caliber.db md5 unchanged 54aa42e5.
- ARMED DIFF, live, all nine: **ZERO SCORES MOVED** — exactly the scoping prediction.
  Per-quarter reviewed: GOOG all 17 pre-existing +0.00 and 3 recovered (4.05/3.97/3.99);
  NOW both pre-existing +0.00 and 17 recovered (0.18-1.10). IDENTICAL TO THE DARK DIFF.
- own_history_series() picks the basis AND RETURNS IT; the basis is stamped on the anchor
  reading (basis=split_restated | truncated (<reason>)). A panel anchor on a truncated
  series is a DIFFERENT MEASUREMENT from one on a restated series and provenance says so.
- fetch_splits returns None for UNKNOWN, [] for "none exist" — the distinction is the whole
  contract. `splits` joined fetch_payload so the recorder captures it through the one path
  production requests.
- FIXTURE RE-RECORD (ruled: recorder discipline beats recorded divergence): GOOG + NOW
  re-recorded, offline now reproduces live EXACTLY (GOOG 20q @4.34, NOW 19q @0.78).
  Resolution diff REVIEWED, 1 field of 38 moved: GOOG total_debt_reported no_tag ->
  stale_tag — withheld either way, field is DARK, and it is the same movement already
  recorded live at D-5 (the fixture predated that chain extension). NOW: zero movement.
  MU/V/WU/banks deliberately NOT re-recorded: no split data -> None -> refused ->
  truncated, which already equals their restated series. No drift to close.
- V STAYS REFUSED (1/3 witnesses), flag retained.
- Tests flipped: test_the_truncating_series_is_now_the_FALLBACK_and_still_truncates (the
  truncating function is unchanged and still pinned — it is the only thing between an
  unknown split and GOOG's ~81% quarters) and test_a_recent_split_no_longer_costs_the_anchor.
  Added test_without_a_split_report_the_panel_keeps_the_truncated_basis.

**H-FCF SCOPED 2026-08-11 — docs/h-fcf-scoping.md. NOTHING IMPLEMENTED. BOTH CLAIMS FAIL
AS STATED; THE CEILING ARGUMENT DOES NOT SURVIVE.**
- **CLAIM 1 (free_cashflow advisory -> armed): OPPORTUNITY SURVIVES, ATTRIBUTION DOES NOT.**
  The basis mismatch IS resolvable and the advisory is doing real work (MU diverges 1469%
  unmatched). Re-read at FY-END: MU/GOOG/NOW/BK/C all **0.0%**, WU **28.6% CONFLICT**
  (a genuine disagreement that survives period matching — arming would DOWNGRADE WU),
  V/JPM/USB no capex tag. BUT the mechanism is extending period_basis='annual_fy' to FLOW
  inputs — `_instant_at` requires `not rec.get('start')`, so it is INSTANTS-ONLY today and
  cash-flow rows fall through. The TTM-at-a-target-period helper ALREADY EXISTS
  (_assemble_ttm(as_of_end=)/ttm_series). **A historical series is neither necessary nor
  sufficient for it.** Split out as H-X, a SEPARATE order (see below).
- **CLAIM 1 SECOND FAILURE: arming free_cashflow does NOT unblock Financial Health.**
  Measured, not reasoned: FH's five inputs are current_ratio (high), total_cash (high),
  free_cashflow (fixable), total_debt (total_debt@FY is DARK — MU agrees 0.5%, GOOG
  CONFLICTS 8.8%), and **debt_to_equity, which is FMP-NET vs EDGAR-GROSS — a DEFINITIONAL
  mismatch no period matching can fix**. Forcing all five high does give FH=high, so the
  pillar is reachable in principle; debt_to_equity is the binding constraint.
- **CLAIM 2 (fcf_yield corroborant): FAILS, on principle not on data.** fcf_yield =
  FCF_TTM / market cap, and market cap = PRICE x shares — the E-4 uncorroborable class.
  FMP publishes NO plain TTM FCF (only price-denominated ratios + FCFF/FCFE), so the TTM
  level is reachable only by multiplying a ratio back out by market cap, i.e. by injecting
  the price term. An EDGAR fcf_yield would share an IDENTICAL denominator with FMP's, so
  comparing them carries exactly the free_cashflow row's information and adds none;
  stamping that agreement on fcf_yield would let the uncorroborated price term inherit
  corroboration it never received. LAUNDERING — the peer-anchor rejection rationale.
- **CEILING: H-FCF closes blockers in ZERO of four pillars, not two.**
  test_verdict_high_is_still_blocked STAYS PASSING — do not touch it (ruling R-D).
  Shortest remaining path to verdict-high is NOT this one: it runs through debt_to_equity,
  Management's hardcoded medium, and a second source for price/estimate-derived fields.
- **NEW FINDING — TRANSCRIPTION vs INDEPENDENCE.** EDGAR TTM FCF equals FMP's implied TTM
  FCF **to 0.000% — exact to the dollar — on MU/GOOG/NOW/BK**. Four unrelated issuers
  agreeing to the dollar is not two independent sources; FMP's cash-flow fundamentals are
  evidently SEC-derived. The whole E-3 armed set rests on this same footing. It does NOT
  invalidate the cross-check (WU diverges 40% and that is where it earns its keep), but
  for FILED FUNDAMENTALS it is a TRANSCRIPTION check, not an independent measurement —
  recorded because 'high confidence' is being asked to mean something specific.
- **H-FCF'S REAL VALUE (survives, and is worth doing):** own-history coverage 4/20 -> 8/20;
  INDEPENDENCE-NARROWED 16/20 -> 12/20 (directly attacks D-3 ruling 6's 85%). Compounder
  lens gains its first issuer-referenced denominator.
- **BLAST RADIUS MEASURED (load-bearing — the universe IS the golden five):** own-history
  feeds METRIC_FCF_YIELD -> COMPOUNDER ONLY = GOOG, V, WU = 3 OF 5. **Zero scores move**,
  but **WU's BINDING ANCHOR CHANGES sector -> own_history**, narrowing its read by 8.37pp
  (+12.67 -> +4.30); it survives at 5 only because +4.30 still clears the +3.0 top rung.
  A ticker nearer a rung boundary would move.
- **CORRECTIONS TO MY OWN g-build.md §6:** (a) the useful ceiling is **12/20, not 16/20** —
  16 counts forward-earnings cells NO LENS CONSUMES; (b) **V gains NOTHING — no capex tag**
  (its recorded cross-check limit, which I wrongly carried into the lens claim). The
  compounder beneficiaries are **GOOG and WU**, not GOOG/V/WU.
- **OPEN RULING FOR H-2 — NEGATIVE-FCF EXCLUSION / SURVIVORSHIP.** MU: 10 of 24 quarters
  (42%) have negative FCF and are excluded, so its "own FCF history" is the median of the
  quarters when FCF was POSITIVE, not its typical FCF yield. C: 14 of 21 -> withheld.
  Bias direction is SAFE (higher median -> looks richer -> MIN takes the worst), but the
  magnitude wants a ruling, not a default. Options: exclude-and-flag (trailing precedent),
  withhold above an exclusion threshold, or require positive TTM FCF in a majority.

**H-1 BUILT, DARK, COMMITTED 2026-08-15 (7a8bbf1). H-2 IS RULED. H-3 IS NEXT.**
Report docs/h1-series.md. Suite 613 -> 644. caliber.db md5 unchanged 54aa42e5; the
`fundamental_series` table does NOT exist in production (only a full live batch run creates
it — a fixture/no-synthesis run must name its own destination).
**SUPERSEDED 2026-08-15 (later session): `fundamental_series` NOW EXISTS in production,
557 rows, created by the ids 221-225 re-run — the first full live batch run since H-1
landed. It behaved exactly as designed: 153/121/…/152 new rows per ticker, 0 restatements.**

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
- Degraded runs (`--fixture` / `--no-synthesis`) must NAME THEIR DESTINATION (`--db-path`).
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

WHY THIS EXISTS (2026-08-15, real incident): an orphaned peer session shared this checkout
and wrote the entire H-1 build into it WHILE a fresh session was re-orienting after an
interrupt — the tree changed between two `git status` calls minutes apart. The successor
session then asserted from context that it was PID 243; it was in fact PID 3070, and 243
was the peer. Acting on that inverted belief would have killed the verifying session and
LEFT THE WRITER RUNNING. A PPID read settled it in one command. Two sessions on one
checkout is a data-loss hazard; an unverified kill target is a worse one.

## SESSION-CLOSE PROTOCOL (standing rule, 2026-08-09)
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
  three-conventions note in the EDGAR section). 654 tests were green throughout; the live
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
  E-1 DONE (XBRL extraction, 6977a72). E-2 DONE (field resolution, 25b40c5).
  E-3 ARMED 2026-08-09 (031506f) — live at both boundaries. E-4 DONE (verdict-high
  reachability): the note is NOT revived, see the E-4 finding below. See EDGAR section.
- Phase D — VALUATION PANEL: **CLOSED 2026-08-09. ALL FIVE LENSES ARMED.** Ethos rule 10
  is fully built — every lens is rate-aware, on THREE DIFFERENT MECHANISMS:
    panel-anchored (MIN across anchors) : compounder, cyclical, standard
    rate-shifted thresholds             : growth
    cost-of-equity                      : bank
  ARMED_LENSES and ARMED_PANEL_LENSES are deliberately DIFFERENT SETS — 'armed' does
  not mean 'panel-scored'. See Phase D section + docs/d5-banks.md.
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
  cannot corroborate (see the E-4 ceiling finding). Wiring it lifts tripwire 3 above.
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
