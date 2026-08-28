# ARMED STATE — what reads what, precisely

**THE LIVE BEHAVIOURAL RECORD OF THE SYSTEM. READ IT BEFORE TOUCHING ANY ARMED SURFACE.**

Migrated out of CLAUDE.md on 2026-08-28 (micro session) under Vic's ruling — "armed state
migrates" — extending ruling 2. **RELOCATION ONLY: not one character below was edited.**

### ★ THIS IS A LIVING FILE, NOT A DATED CLOSE SNAPSHOT, AND THE DISTINCTION IS THE RULING'S
### OWN LOGIC

Close state is a **measurement of one moment** — md5, row counts, a reconciliation — so it
belongs in a dated `docs/closes/` file that is never touched again. ARMED STATE is the
**current answer to "what reads what"**, and it carries forward across every close. Freezing
it into a dated snapshot per close would put N superseding copies on disk, each labelled
"supersedes the one below" — which is **precisely the failure ruling 2 was written to kill**,
relocated rather than removed.

So: **this file is UPDATED IN PLACE when an arm changes, and there is exactly one of it.**
CLAUDE.md points here and carries no armed-state prose.

---

### ARMED STATE — what reads what, precisely

- **★★ THE FINANCIALS GATE IS ARMED ON THREE SURFACES (Vic ruling 1, 2026-08-28).** Not just
  `build_fcf_series` any more: **the EVALUATOR** (`evaluate.py`, refuses after lens selection
  and BEFORE `build_panel`, **exit 5**) and **the BATCH path** (`batch/runner.py` raises
  `ModelInapplicable` → `status='model_inapplicable'` via `save_failed_evaluation`, which
  writes no pillars, no score, no E(R)). The classifier is reached transitively — evaluate.py
  is the sole annotator, so refusing there means no stage is computed.
  - **★ THE BATCH GATE'S POSITION IS LOAD-BEARING IN A WAY THE INTERACTIVE ONE IS NOT: it
    sits ABOVE `run_dark_fcf_series`, WHICH IS A WRITER.** "Nothing numeric" is not satisfied
    by declining to score if a writer already ran. Pinned by line order.
  - **8 `lifecycle_stage` ROWS ARE RETIRED, NOT DELETED AND NOT EDITED** (BK 7/35, C 9/37,
    JPM 6/34, USB 8/36). The rows were computed CORRECTLY from the inputs they had — they are
    **INADMISSIBLE, not wrong**, and that is a different claim. `computed_stage`, `rule_fired`
    and `run_at` all survive byte-for-byte; pinned.
  - **`retired_reason` IS A GUARD, NOT A NOTE:** `core.stage_tolerance._latest_stage_row` and
    `core.stage_freshness` both filter `retired_reason IS NULL`. Measured after the write:
    BK/C/JPM/USB → `tolerance 0.15, stage=None`; V and IONQ untouched. **"No band" is
    represented as the DEFAULT, never undefined and never the widest** — pinned that
    retirement can never WIDEN a band.
  - **THE NAMES ARE NOT HARDCODED** — membership is recomputed live through
    `fcf_model_applicability`. V and WU were passed to the retirement tool explicitly and
    correctly SKIPPED.
- **★★ STAGE FRESHNESS IS ARMED — NO SILENT STAGE FLIPS (Vic ruling 2, 2026-08-28).**
  `core/stage_freshness.guard_stage_write` raises `StageFlipRequiresApproval` **before** the
  write. Four outcomes, one raises: not stale → write; stale but same stage → write; stale +
  flipped + APPROVED → write; stale + flipped + unapproved → **HALT, exit 6, nothing
  persists.**
  - **★★ THE STALENESS SIGNAL IS *NOT* "ANY NEWER ROW", AND THE NAIVE VERSION IS ALREADY
    WRONG.** `max(first_observed)` over all rows flags **19 of 28**, but JPM/SKHY/USB appear
    only because of the `value=NULL` currency-block and class-flag rows written that morning.
    **A row the classifier cannot read cannot change a stage.** The signal is
    `period_type='FY'` AND `value IS NOT NULL` AND `metric IN ('fcf','sales_to_capital')` —
    pinned over the **AST** against the actual `build_legs` call, so a third leg cannot be
    wired in without the guard following it.
  - **THE APPROVAL CHANNEL IS `stage_flip_approvals`, DELIBERATELY *NOT* `lifecycle_overrides`.**
    An override says "the approved stage REPLACES the computed one" — disagreement with the
    classifier. An approval says "the classifier is RIGHT and may write" — consent to persist.
    **Approval is PER-TRANSITION**, keyed `(ticker, from_stage, to_stage)`: approving
    `HIGROWTH → YOUNG` does not license a later `HIGROWTH → DECLINE`. Both pinned.
  - **THE HALT IS CAUGHT AHEAD OF THE BROAD `except Exception` around `_lifecycle_block`** —
    that handler degrades an annotation failure to a one-line WARN, which is right for a feed
    flake and **IS the silent stage flip** here. Pinned over the AST on handler order.
  - **RUN THE SWEEP BEFORE ANY EVALUATION RUN** — `python -m tools.stage_freshness_sweep`,
    read-only. **QBTS `HIGROWTH → YOUNG` was APPROVED 2026-08-28** (`stage_flip_approvals`
    id 1), so the sweep no longer exits 6 on it. **No other flip is approved**, and any NEW
    flip the sweep finds still HALTS.
- **★ THE ETF / FUND REFUSAL IS ARMED ABOVE THE EDGAR FETCH ON BOTH PATHS (Vic ruling 2,
  2026-08-28; REPOSITIONED the same day after the acceptance run).**
  `core/etf_guard.etf_refusal` reads `profile.isEtf` and nothing else — no name matching, no
  exchange rule, no ticker list. **evaluate.py exits 7** (distinct from crash 1, rate 3,
  financials 5, stage-flip halt 6); **batch raises `EtfNotEvaluable` → `status='etf_refused'`**.
  - **★★ POSITION IS THE RULING, AND THE FIRST POSITION WAS WRONG.** It originally sat above
    `select_lens`, which is correct as far as it goes — but `fetch_edgar` is a HARD GATE and
    an ETF has **no ticker-level SEC CIK** (funds file under their trust's CIK), so every real
    fund was refused at the EDGAR gate with "Ticker not found in SEC tickers.json" and NEVER
    REACHED THE GUARD. **Measured: LYTE and FLTW exited 1, not 7.** Safe outcome, WRONG typed
    reason, and a first line of defence that was ACCIDENTAL rather than the guard built for
    it. Now above `fetch_edgar` on both paths; re-measured at **exit 7, `etf:not_a_company`,
    EDGAR never fetched.** Pinned by line index both above `fetch_edgar` AND below the FMP
    fetch it depends on.
  - **UNKNOWN DOES NOT REFUSE** — a stated departure from fail-closed. Refusing on absence
    would refuse every recorded fixture (they predate the field). Cost named: this guard
    cannot catch a fund whose payload omits `isEtf`.
  - **`isEtf` IS PARSED TRI-STATE, NEVER PYTHON TRUTHINESS** — `bool("false")` is `True`, so
    a truthiness guard would refuse the entire universe while looking like it worked.
  - **BLAST RADIUS: ZERO of the 28.** No universe name has `isEtf=true`; LYTE and FLTW are
    the positive controls, and both are held but deliberately outside `tickers.txt`.

- **★ THE USD-ONLY CURRENCY GUARD IS ARMED ON SCORE-BEARING FIELDS (Vic ruling 4,
  2026-08-28).** `adapters.fmp_adapter.apply_currency_guard`, applied at the payload boundary
  so ONE enforcement point covers the live AND fixture paths.
  **GUARDED (8 MONETARY):** `total_debt`, `total_cash`, `free_cashflow`,
  `operating_cashflow`, `market_cap`, `enterprise_value`, `current_price`,
  `target_mean_price`. **NOT GUARDED (currency-neutral), and stated in code:** every margin,
  `roe`, `roa`, `current_ratio`, `debt_to_equity`, `revenue_growth`, `trailing_pe`,
  `forward_pe`, `price_to_book`, `ev_to_ebitda`, `ev_to_revenue`, `fcf_yield`, `beta`,
  `shares_outstanding`, `analyst_count`.
  - **"ALL score-bearing fields" IS READ AS "every field a currency error can REACH."** A
    ratio sharing a basis top and bottom reads the same in KRW and USD — verified live, not
    assumed: SKHY's `freeCashFlowYieldTTM` is 0.0777 and KRW TTM FCF ÷ KRW cap reproduces
    7.77%. Blocking those would DISCARD VALID DATA.
  - **BLOCK = `missing_prov` with a typed source. NOTHING IS CONVERTED** — no rate, no forex
    call, no arithmetic. Pinned behaviourally and over the AST. **UNKNOWN BLOCKS**, including
    two statements disagreeing about the currency (UNKNOWN, never a majority vote).
  - **BLAST RADIUS: ONE NAME.** SKHY is the universe's only non-USD reporter; all 28 are
    USD-quoted.
- **★ MARKET CAP NOW COMES FROM `market-capitalization`, NOT `key-metrics-ttm` (ruling 3).**
  Dark diff over all 28: **26 agree to 1.0000**; **SKHY ratio 0.0010** (key-metrics served
  the KRW cap of `000660.KS`, byte-identical) and **GOOG ratio 0.9921** — key-metrics serves
  GOOG the ISSUER cap (byte-identical to GOOGL) while this endpoint serves the class-specific
  one. **GOOG's −0.79% was NOT anticipated by the ruling; reported, not absorbed.**
  **ZERO PILLAR SCORES MOVED on any of the 28.**
  - **★★ THE GUARD IS WHAT MAKES THIS SAFE, NOT AN INDEPENDENT IMPROVEMENT.**
    `core/pillars.py:237-238` computes `fcf / market_cap`; both legs were KRW for SKHY and
    **accidentally correct**. Making `market_cap` USD without blocking the KRW
    `free_cashflow` would be wrong by ~1,378x. **Rulings 3 and 4 land together or not at all.**
  - **★ `market_cap` IS DELIBERATELY ABSENT FROM `FIELD_CURRENCY_BASIS`.** Its basis belongs
    to **the endpoint that supplied it**, and ruling 3 moved that endpoint; the adapter still
    falls back to key-metrics when the newer endpoint is absent, which is what every recorded
    fixture does. A static answer BLOCKED the very USD figure ruling 3 exists to supply —
    caught by the dark diff. `market_cap_basis()` resolves it per payload and fails toward
    the basis that blocks. Pinned so a static answer cannot be re-added.
  - **FIXTURE AGING, RECORDED NOT FIXED:** recorded FMP fixtures predate the
    `market_capitalization` key, so **offline market_cap keeps the key-metrics value while
    live uses the new endpoint.** Same hazard L-4d pinned for the capex synonym.
- **★ THE SKHY ANCHOR IS WRITTEN** — `fundamental_series` id 2622,
  `metric='market_cap_anchor'`, `period_type='ANCHOR'`, **$1,143,150,316,466 USD**,
  period_end `2026-08-28`, basis `full_market_cap`, method `market-capitalization`.
  **Free float is NOT computed, NOT stored and NOT offered** — Vic's own ~$909.30B reference
  IS the free-float cap and the full cap is ~$1.14T, a 25.6% gap, so "no float variants" is a
  choice between two defensible numbers. The tool **refuses** a non-USD quote. Destination is
  `fundamental_series` and **not `overrides`**, because `overrides` is read only by
  `web/app.py` and by nothing on the pipeline path — a row there would be an anchor nothing
  reads, which is worse than none.

- **★ THE FCF-MODEL FINANCIALS CLASS IS ARMED (2026-08-28, `core/model_applicability.py`).**
  Banks, insurers and diversified financials are **model-inapplicable** to the FCF engine —
  a CLASS, not a per-ticker call. **Caught, measured over all 28: BK, C, JPM, USB.**
  - **IT OWNS NO TAXONOMY.** It delegates to `select_lens(sector, industry, None, None) ==
    "bank"`. **`sic` and `ticker` are pinned OFF**: SIC would make the class EDGAR-score-
    bearing (a fifth unruled path), and a ticker would admit the hand-curated override list,
    which is the per-issuer judgement the ruling removes. `fcf_model_applicability` takes
    exactly two arguments, so there is no third to smuggle.
  - **★ V AND WU ARE FINANCIAL SERVICES SECTOR AND ARE DELIBERATELY *NOT* CAUGHT.** Their
    industry is "Financial - Credit Services" → compounder lens, and both are CURRENTLY
    COVERED in `fundamental_series`. **A sector-level rule would have destroyed working
    coverage on two names.** Vic's wording is "banks/insurers/diversified financials", not
    "the Financial Services sector". Pinned.
  - **ENFORCEMENT POINTS, NAMED:** `build_fcf_series` refuses **FIRST, ahead of every data
    check** (the ordering is the ruling — `capex:no_tag` is accurate and leads nowhere, and
    JPM/USB sat under it for four orders); `own_history_fcf_yields` threads it to the panel.
    **It is OPT-IN — `applicability=None` means NOT ASKED**, so every pre-existing caller is
    unchanged and the arm is visible at the sites that opted in.
  - **MEASURED SCORE MOVEMENT TODAY: ZERO, AND STRUCTURALLY SO.** Every caught name is on the
    BANK lens; `bank` ∉ `ARMED_PANEL_LENSES` and `_valuation_bank` does not take `panel` at
    all. **Pinned by a test that FAILS LOUDLY if the bank lens is ever panel-armed**, which
    is exactly when that claim stops being true.
  - **BK IS THE NAME THAT MAKES THE PINS ABLE TO FIRE** — unlike JPM/USB it DOES file capex
    and DID build a usable series, so a dead gate would show up on BK and nowhere else.
  - **★ IT DOES *NOT* REACH THE LIFECYCLE CLASSIFIER, AND THAT IS THE OPEN RULING** — the
    gate binds the BUILDER; the classifier reads the STORED series. See the C finding.
- **★ THE USD-ONLY REPORTING-CURRENCY GATE IS ARMED (2026-08-28,
  `core/reporting_currency.py`).** Partitions FMP statement rows on `reportedCurrency` and
  **nothing else** — never on magnitude, exchange, country or `profile.currency`. Two typed
  reasons, deliberately NOT collapsed: **`currency:non_usd_native`** (a fact about the
  ISSUER) and **`currency:currency_unstated`** (a fact about the FEED, and the more alarming
  one). **NOTHING IS EVER CONVERTED** — pinned behaviourally (the gate hands back the SAME
  row objects) and over the AST (no forex symbol, endpoint or converter call in either
  module).
- **★ BLOCK/FLAG ROWS USE A `metric` AND `period_type` NO CONSUMER QUERIES —
  `ingest_block:{income|balance_sheet|cash_flow}` on `BLOCK_FY`/`BLOCK_Q`, and
  `model_applicability` on `FLAG`.** This is FORCED BY MEASUREMENT, not taste:
  `evaluate._fy_series_from_db` **does not filter `excluded`** (verified empirically), so a
  block written as `fcf`/`FY` would flip `fcf_fy` from None (UNKNOWN) to a list and relabel
  the leg `only_0_fy_fcf_points` — a claim about the ISSUER for something WE blocked.
  **★★ AND DO NOT "FIX" THAT BY FILTERING THE READER ON `excluded=0`: 30 FY `fcf` rows
  across 8 tickers (BE, BK, C, IONQ, LITE, MU, QBTS, RKLB) are `excluded=1` BECAUSE THEY ARE
  NEGATIVE, AND THOSE NEGATIVE POINTS *ARE* THE R2 ALL-NEGATIVE-LAST-3 SIGNAL.** A warning
  pin fails if a future session adds the filter thinking it is tidying up.
  The class FLAG row is keyed on the **RULING date** (`2026-08-28`), not the run date, so a
  re-run is idempotent and a re-ruling appends beside it rather than overwriting.

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
