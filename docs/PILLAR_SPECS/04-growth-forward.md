# GROWTH PILLAR — WHAT IT ACTUALLY COMPUTES
**Read-only census, 2026-08-29. Zero writes, zero code changes, engine frozen.**
Measured against HEAD `ff02e21`, suite **1091 passed**, caliber.db md5
`69dc2328ee3af8a43d506b64665da39b` (unchanged before and after this read).

Sole implementation: **`core/pillars.py:347-430`, `score_growth(yf, edgar, lens)`**.
Single call site: `core/pillars.py:988` (`score_all_pillars`). There is no second growth
scorer. `core/valuation_anchors.py:939 score_growth_shifted` is the **growth-LENS
VALUATION** mechanism and is a different pillar — do not confuse the two.

---

## ★★ THE HEADLINE, BEFORE THE DETAIL

**THE GROWTH PILLAR READS NO SERIES AT ALL.** It is not a trajectory computation. It is a
**four-leg point-in-time scorecard** over three TTM/annual scalars plus an
earnings-surprise trend. Specifically:

- **NO FCF.** `fundamental_series` — the table L-4c/L-4d/L-4f/L-4d.1 spent four orders
  populating to 20 of 28 tickers — is **never read by this pillar**.
- **NO operating income.** No leg touches it.
- **NO EPS growth.** The line the rationale prints as `EPS trend:` is **not EPS growth** —
  it is the trend in **earnings SURPRISE versus analyst estimate**. See §3.
- **NO revenue series.** One YoY point, `income_annual[0]` vs `income_annual[1]`.
- **`edgar` IS ACCEPTED AND NEVER READ.** `EdgarData` is in the signature at line 347 and
  appears **nowhere in the body** (verified by grep over lines 347-430: one hit, the `def`
  line). This is one of the four paths the DOCTRINE pre-flight entry names as
  "EDGAR is score-bearing on every run" — **for the growth pillar specifically, it is not.**
  The parameter is inert here.
- **`lens` IS ACCEPTED AND USED ONLY AS A LABEL** — `method=lens` on the returned
  `PillarResult`. It moves no threshold and selects no branch.

---

## 1. SOURCE FIELDS — FMP NAMES AND GRAIN

All four legs come from **FMP only**. Every `Prov.source` on this pillar reads `fmp` or
`fmp/earnings_history` (confirmed on the three production evals in §5).

| Leg | `TickerData` field | FMP endpoint | FMP key | Grain | Built at |
|---|---|---|---|---|---|
| 1 | `revenue_growth` | `income-statement?period=annual&limit=10` | `revenue` | **ANNUAL FY, 2 points** | `adapters/fmp_adapter.py:352 _compute_revenue_growth`, called :437 |
| 2a | `trailing_pe` | `ratios-ttm` | `priceToEarningsRatioTTM` | **TTM** | `fmp_adapter.py:440` |
| 2b | `forward_pe` | `analyst-estimates?limit=3&period=annual` + quote | `epsAvg` (next-yr) ÷ price | **NTM ANNUAL estimate** | `fmp_adapter.py:443-448` |
| 3 | `analyst_count` | `price-target-summary` | `lastMonthCount` | point-in-time | `fmp_adapter.py:451-453` |
| 4 | `earnings_history` | `earnings?limit=8` | `epsActual`, `epsEstimated` | **QUARTERLY, ≤8 rows** | `fmp_adapter.py:362 _earnings_to_history`, called :507 |

**GRAIN IS MIXED AND THE MIX IS LOAD-BEARING.** Leg 1 is annual-FY. Leg 2a is TTM. Leg 2b
is a forward ANNUAL estimate. Leg 4 is quarterly. Leg 2's "discount" therefore compares a
**TTM realised** multiple against an **NTM estimated** one — that is the intended earnings-
growth signal, but it means the leg is partly an analyst-expectation reading, not a
measured one.

**`analyst_count` (leg 3) SCORES NOTHING.** `core/pillars.py:392-393` appends it to
`inputs` only. It reaches the output solely through `min_conf(...)` at :409 — it can
lower the pillar's **confidence label**, never its score.

**DEAD INPUT, RECORDED NOT FIXED:** `revenue_growth_trajectory` is built by
`fmp_adapter.py:513` and carried on `TickerData` (`core/datatypes.py:76`), and **no
scorer in the runtime reads it** (grep over all non-test code: definition and
construction sites only). The quarterly revenue-growth shape is fetched, computed,
carried, and discarded.

**CURRENCY:** every growth input is in `CURRENCY_NEUTRAL_SCORE_BEARING_FIELDS`
(`core/reporting_currency.py:188-198`) — `revenue_growth` is a percent change,
`trailing_pe`/`forward_pe` are price ÷ per-share, `analyst_count` is a count. The
USD-only guard does **not** bind this pillar, correctly: a KRW/KRW ratio reads the same as
USD/USD. Growth is the one pillar SKHY's currency problem cannot reach through.

---

## 2. ROUTING — ONE FORMULA FOR EVERY STAGE AND EVERY LENS

**THE COMPUTATION IS NOT STAGE-DEPENDENT. AT ALL.**

- **Lifecycle stage (YOUNG / HIGROWTH / MATURE / DECLINE) never enters this function.**
  `score_growth` receives `(yf, edgar, lens)`. There is no stage argument, no
  `tolerance_for()` call, no `lifecycle_stage` read. Stage reaches production through
  `tolerance_for()` at `evaluate.py:487` and `batch/runner.py:408` — the **B-2 divergence
  band**, which is downstream of synthesis and has nothing to do with pillar scoring.
- **Lens does not branch either.** Unlike `score_valuation` (`core/pillars.py:514-522`,
  which dispatches five ways), `score_growth` has **no lens branch**. `lens` is written to
  `method=` at line 428 and is otherwise unused.
- **No weights vary.** The point budget is fixed: 3 (revenue) + 2 (PE discount) + 1 (trend).

**CONSEQUENCE WORTH STATING PLAINLY:** a pre-revenue YOUNG name and a MATURE compounder
are scored on **identical thresholds** — 20%/10%/0% revenue growth, 25%/0% PE discount.
The 20%-is-full-marks ceiling that reads as demanding for V is trivially cleared by any
early-stage name off a small base, and there is no upper bound or trough adjustment
beyond the advisory `CYCLICAL-RECOVERY-GROWTH` flag.

---

## 3. NEGATIVE / ZERO HANDLING — THE LEG DISAPPEARS, IT DOES NOT SCORE ZERO

This is the section that matters most, because **the denominator is dynamic**.
`max_pts` is accumulated per leg *only when that leg's inputs are present and usable*
(`core/pillars.py:355, 361, 381, 402, 405`), and the score is
`_score_from_points(pts, max_pts)` at :408 — `round(1 + clamp(pts/max_pts) * 4)`.

**So a skipped leg shrinks the denominator rather than costing points.**

### 3.1 EPS growth — there is none, and the substitute is a surprise trend

**THERE IS NO EPS-GROWTH COMPUTATION ANYWHERE IN THIS PILLAR.** The rationale string at
:418 prints `EPS trend: {trend}`, and `trend` comes from `_analyze_earnings`
(`core/pillars.py:51-86`), which computes over **`surprisePercent` — actual EPS versus
ANALYST ESTIMATE**, not versus a prior period.

`trend` is derived at :72-84: with `n ≥ 4` usable quarters, split `half = n // 2`,
compare `mean(surprises[:half])` (recent) against `mean(surprises[half:])` (older);
`improving` if recent exceeds older by **more than 2 percentage points**, `deteriorating`
if it falls short by more than 2, else `stable`. Fewer than 4 → `insufficient`.
No records or no surprises → `no_data`.

- **ORDERING IS CORRECT AND WAS CHECKED**, given the `core/technicals.py` precedent. FMP
  serves `earnings` **newest-first** (verified in `tests/fixtures/fmp/MU.json`:
  2026-09-22, 2026-06-24, 2026-03-18, …), so `surprises[:half]` genuinely is the recent
  half. **This pillar does not carry the L-4a reversal defect.**
- **ODD-n SPLIT IS ASYMMETRIC.** `_earnings_to_history` drops future quarters
  (`epsActual is None`), so 8 fetched rows commonly yield 7 usable. `half = 3` compares
  **3 recent against 4 older** — a real but small asymmetry, recorded not fixed.
- **★ A ZERO ESTIMATE MANUFACTURES A DATA POINT.** `fmp_adapter.py:371`:
  `surprise = (diff / abs(est) * 100) if est != 0 else 0.0`. An estimate of exactly zero
  yields **a confident 0.0% surprise**, which then enters `beat_rate` and both trend means
  as if it were measured. It should be an absence. Same family as the
  `except OperationalError: return []` defect caught 2026-08-28.
- **★ A NEAR-ZERO ESTIMATE IS AN UNBOUNDED OUTLIER.** `est = 0.01, actual = 0.05` gives
  **+400%**, which dominates a 3- or 4-point unweighted mean and can single-handedly set
  `improving`. **This is the pre-earnings/YOUNG population exactly** — IONQ, QBTS, RKLB.
  No clamp, no median, no winsorisation. Measured as a structural exposure; **not
  demonstrated to have fired on a production row, and not fixed.**

### 3.2 Negative or absent PE — the whole earnings leg vanishes

`core/pillars.py:377-380` requires `not trailing_pe.is_missing() and not
forward_pe.is_missing()` **and then** `tpe > 0 and fpe > 0`. Any of: missing trailing PE,
missing forward PE, negative trailing PE (loss-making), negative forward PE
(negative forward EPS) → `max_pts += 2` **is never reached** and the leg is silently
dropped.

Note `forward_pe` is additionally guarded upstream at `fmp_adapter.py:446`
(`eps_avg > 0`), so a negative forward EPS estimate yields `forward_pe = None` rather
than a negative multiple. That is the documented negative-forward-PE discipline (LCID is
the named fixture) working — but its effect *here* is leg deletion, not a penalty.

**★ ABSENCE IS PRIVATELY OPTIMAL, AND QBTS IS THE LIVE PROOF.** The standing rule is
"FAIL-CLOSED DEFAULTS — a guard that cannot measure DENIES the tag or band it guards;
absence must never be privately optimal." **This pillar inverts it.** QBTS (eval 289)
carries `trailing_pe = -23.95` and no forward PE, so the earnings leg is dropped and it
scores **4/4 → 5**. Had the leg been present and scored the minimum, QBTS would be
**4/6 → round(1 + 0.667×4) = 4**. *A loss-making pre-profit issuer scores a point HIGHER
on growth than it would if its profitability were measurable at all.*
**Measured, reconciled, and NOT FIXED — this is a scoring-path change and needs a ruling.**

### 3.3 Zero / negative base revenue

`_compute_revenue_growth` (`fmp_adapter.py:352-359`):
- fewer than 2 annual rows → `None` (leg dropped, `max_pts` unchanged)
- `revenue` missing on either row → `None`
- **`r1 == 0` → `None`** — division by zero is refused outright, correctly. A
  **revenue_zero** prior year yields no growth reading rather than an infinity.
- denominator is **`abs(r1)`**, so a negative prior-year revenue (rare; possible on
  contra-revenue restatements) produces a **sign-correct** growth figure rather than an
  inverted one. Deliberate and right.
- **Pre-revenue names** (both years zero or absent) therefore lose the 3-point leg
  entirely, leaving the pillar on the PE leg (likely also absent — see 3.2) and the trend
  leg. In the limit a pre-revenue, loss-making name is scored on **the surprise trend
  alone**: `improving` → 1/1 → **score 5**; `deteriorating` → 0/1 → score 1.
- Negative growth adds **0 points against a max of 3** and flags
  `NEGATIVE-REVENUE-GROWTH` — this leg *is* fail-closed, unlike leg 2.
- `rg > 1.0` (>100%) adds the advisory `CYCLICAL-RECOVERY-GROWTH` flag. **Flag only —
  it costs nothing and caps nothing.**

### 3.4 Total absence

`core/pillars.py:408`: `score = _score_from_points(pts, max_pts) if max_pts > 0 else 3`.
**With every leg absent the pillar returns a NEUTRAL 3, not a refusal and not a 1.**
`_score_from_points` would itself have returned `lo = 1` on `max_pts == 0`; the `else 3`
overrides that. Contrast `score_valuation`, which raises `RateUnavailable` rather than
score without its anchor. **The growth pillar has no refusal path.** Recorded, not fixed.

---

## 4. LOOKBACK — POINT-TO-POINT, NOT CAGR, NOT REGRESSION

**NO CAGR. NO REGRESSION. NO MULTI-YEAR WINDOW.**

| Leg | Lookback | Method |
|---|---|---|
| Revenue growth | **2 annual points** (`income_annual[0]`, `[1]`) | **point-to-point YoY**, `(r0 − r1) / abs(r1)` |
| PE discount | **1 point each side** (TTM now vs NTM estimate) | point-to-point ratio |
| Surprise trend | **≤8 quarters fetched, ≤7 usable** | split-half **mean** comparison, ±2pp deadband |

`INCOME_ANNUAL_LIMIT = 10` (`fmp_adapter.py:124`) — **ten annual rows are fetched and
eight are discarded** by this pillar. The depth is paid for and unused. The trend leg is
the only leg with any history at all, and it is a two-bucket mean, not a fitted slope.

---

## 5. WORKED EXAMPLES — LAST PRODUCTION EVALUATION, ALL THREE RECONCILE EXACTLY

Source: `caliber.db`, latest `evaluations` row per ticker, with the matching
`field_provenance` rows (`pillar = 'Growth / Forward'`). All three are from the
**2026-08-28 full-universe acceptance run**, `status='ok'`, `defect_tags=NULL`.

`field_provenance.field_name` is **NULL on every row** (the standing open diagnosis
question), so field identity below is recovered from the `inputs` list order at
`core/pillars.py:356, 393, 399` — `[revenue_growth, trailing_pe, forward_pe]`, then
`analyst_count` if present, then the trend. Values are verbatim from the DB.

### QBTS — eval id 289, run_at `2026-08-28T22:30:30`, lens `cyclical`

**★ STAGE NOTE, AND IT CORRECTS A STALE LINE IN CLAUDE.md.** QBTS's stored
`lifecycle_stage` now reads **`YOUNG` / `rule2_young`**, written `22:30:30.425633` — i.e.
**by this very evaluation**, 18ms before the eval row. The CLAUDE.md pickup block still
says the row "STILL READS `HIGROWTH` AND WAS NOT TOUCHED"; that was true at the micro
session, and the acceptance run then persisted the flip exactly as the approval predicted.
The prior row (`2026-08-17`) reads `HIGROWTH` / `rule3_higrowth`. **The narrative line is
now stale — flagged, not edited (read-only order).**

| Input | Value |
|---|---|
| `revenue_growth` | **1.7854310637815793** → 178.54% |
| `trailing_pe` | **−23.950704225352112** (loss-making) |
| `forward_pe` | **ABSENT** — only 4 growth provenance rows persisted |
| `analyst_count` | 4 |
| surprise trend | `improving` |

| Leg | pts | max_pts |
|---|---|---|
| Revenue 178.54% ≥ 20 | +3 | 3 |
| PE discount — **SKIPPED**, `forward_pe` missing (and `tpe < 0`) | — | — |
| Trend `improving` | +1 | 1 |
| **TOTAL** | **4** | **4** |

`round(1 + (4/4)×4)` = **5**. Stored score: **5** ✓
Flags: `CYCLICAL-RECOVERY-GROWTH` (because `rg > 1.0`) ✓ — no `EARNINGS-GROWTH-EXPECTED`,
the leg never ran. Confidence `medium`.
Rationale: *"Revenue growth 178.5% YoY. Forward PE n/a. EPS trend: improving. Cyclical
recovery from trough inflates growth rate."*

**This row is §3.2's worked case: max marks on a two-of-four scorecard.**

### MU — eval id 286, run_at `2026-08-28T22:28:33`, lens `cyclical`, stage `MATURE`/`rule4_mature`

| Input | Value |
|---|---|
| `revenue_growth` | **0.48851101111066864** → 48.85% |
| `trailing_pe` | **20.81812095514394** |
| `forward_pe` | **3.5246155589979975** |
| `analyst_count` | 3 |
| surprise trend | `improving` |

discount = (20.81812095514394 − 3.5246155589979975) / 20.81812095514394 = **0.83070** (83.07%)

| Leg | pts | max_pts |
|---|---|---|
| Revenue 48.85% ≥ 20 | +3 | 3 |
| Discount 83.07% ≥ 0.25 | +2 | 2 |
| Trend `improving` | +1 | 1 |
| **TOTAL** | **6** | **6** |

`round(1 + (6/6)×4)` = **5**. Stored score: **5** ✓
Flags: `EARNINGS-GROWTH-EXPECTED` ✓. **No `CYCLICAL-RECOVERY-GROWTH`** — 0.4885 is not
> 1.0, so the flag that fired on the historic 346% trough rebound correctly does not fire
here. Confidence `medium`.

**MU is the pillar's cleanest reading: all four legs present, full marks.** Note the 83%
"discount" is a **cyclical-peak-earnings artefact**, not durable earnings growth — a
forward PE of 3.5x on a semiconductor at cycle peak is the market pricing an earnings
*decline*. The pillar reads it as maximum growth. **The lens knows MU is cyclical
(`method='cyclical'`) and does nothing with that knowledge** — §2's finding, with a number
attached.

### V — eval id 294, run_at `2026-08-28T22:33:33`, lens `compounder`, stage `MATURE`/`rule4_mature`

| Input | Value |
|---|---|
| `revenue_growth` | **0.1133997661860491** → 11.34% |
| `trailing_pe` | **32.4214103653356** |
| `forward_pe` | **19.916492693110648** |
| `analyst_count` | 14 |
| surprise trend | `stable` |

discount = (32.4214103653356 − 19.916492693110648) / 32.4214103653356 = **0.38570** (38.57%)

| Leg | pts | max_pts |
|---|---|---|
| Revenue 11.34% — in [10, 20) | +2 | 3 |
| Discount 38.57% ≥ 0.25 | +2 | 2 |
| Trend `stable` — **neither pts NOR max_pts moves** | — | — |
| **TOTAL** | **4** | **5** |

`round(1 + (4/5)×4)` = `round(4.2)` = **4**. Stored score: **4** ✓
Flags: `EARNINGS-GROWTH-EXPECTED` ✓. Confidence `medium`.

**V is the worked case for the `stable` asymmetry** (`core/pillars.py:401-406`):
`improving` adds `+1/1`, `deteriorating` adds `+0/1`, and **`stable`/`insufficient`/
`no_data` add nothing to either side**. So a genuinely steady issuer is scored on a
**5-point** denominator while a deteriorating one is scored on **6** — the deteriorating
name is penalised twice (no point, larger denominator) and the stable name's steadiness is
neither rewarded nor recorded in the divisor.

---

## 6. WHAT THIS CENSUS FOUND, RANKED — ALL MEASURED, NONE FIXED

Every item below is **recorded, not repaired.** This was a read-only order.

1. **★★ ABSENCE IS PRIVATELY OPTIMAL ON THE EARNINGS LEG** (§3.2). A negative or missing
   PE deletes a 2-point leg instead of scoring it, raising the score. QBTS eval 289 is the
   live instance: **5 with the leg absent, 4 with it present at minimum.** Directly
   contradicts the standing FAIL-CLOSED rule. **Scoring-path change — needs a ruling.**
2. **★★ "EPS trend" IS NOT EPS GROWTH** (§3.1). It is analyst-surprise trend. The
   rationale string ships that label to the synthesis prompt and to Vic's reading of every
   evaluation. This is a **naming defect on a score-bearing output**, the same family as
   `WITHHELD_NO_CAPEX` — a label asserting something the computation does not do.
3. **★ THE PILLAR HAS NO REFUSAL PATH** (§3.4). Total input absence returns a neutral
   **3**, not a refusal, while `score_valuation` raises `RateUnavailable` on its missing
   anchor. A middling growth score built from nothing is indistinguishable in the output
   from one built from four measured legs.
4. **★ A ZERO ANALYST ESTIMATE FABRICATES A 0.0% SURPRISE**; a near-zero one produces an
   unbounded outlier into an unweighted 3-or-4-point mean (§3.1). The exposed population
   is precisely the YOUNG/pre-earnings names.
5. **NO STAGE ROUTING WHATSOEVER** (§2). Pre-revenue YOUNG and MATURE compounder share one
   threshold set. Whether that is correct is a design question, but it should be a **ruled**
   one rather than an unexamined one — nothing in the code records it as a decision.
6. **`edgar` IS ACCEPTED AND UNUSED** (headline). Relevant to the open pre-flight /
   EDGAR-score-bearing contradiction in the DOCTRINE section: of the four named
   score-bearing EDGAR paths, `score_growth(yf, edgar, lens)` is listed as one — and **this
   pillar does not in fact read it.** The other three paths (SIC → `select_lens`,
   `build_panel`, and `fetch_edgar` as a hard gate) are **not** re-examined here and remain
   as recorded. *This narrows the contradiction by one path; it does not dissolve it.*
7. **`revenue_growth_trajectory` IS BUILT AND NEVER READ** (§1). Dead input.
8. **TEN ANNUAL ROWS ARE FETCHED AND TWO ARE USED** (§4). If a CAGR or regression leg is
   ever wanted, the data is already in the payload — no endpoint-scope change needed.
   Contrast the FMP-basis series work, which *is* an endpoint-scope change.
9. **THE ODD-n SPLIT-HALF IS ASYMMETRIC** — 3 recent vs 4 older on the common 7-usable
   case (§3.1). Small, real, recorded.
10. **THE `stable` DENOMINATOR ASYMMETRY** (§5, V). `stable` moves neither numerator nor
    denominator; `deteriorating` moves only the denominator.

## 7. WHAT WAS *NOT* FOUND — STATED SO IT IS NOT RE-INVESTIGATED

- **NO ordering defect.** FMP serves `earnings` newest-first and `_analyze_earnings`
  reads it newest-first. Verified against `tests/fixtures/fmp/MU.json`. The
  `core/technicals.py` reversal does **not** have a sibling here.
- **NO currency exposure.** Every growth input is currency-neutral by construction and is
  explicitly listed as such in `core/reporting_currency.py:188-198`.
- **NO division-by-zero.** `_compute_revenue_growth` refuses `r1 == 0`;
  `_earnings_to_history` guards `est != 0`; `_score_from_points` guards `max_pts == 0`.
  The refusals are present — it is what they *return* (§3.4) that is the finding.
- **NO drift between the three worked examples and the code.** All three reconcile to the
  stored score exactly, from stored inputs, by hand.
