# THE STAGE CLASSIFIER — LIFECYCLE (YOUNG / HIGROWTH / MATURE / DECLINE)
**Glass-box audit, 2026-08-29. Read-only. No fixes applied.**
HEAD `ff02e21` · suite 1091 · caliber.db md5 `69dc2328ee3af8a43d506b64665da39b` (unchanged).
Implementation: **`core/lifecycle.py`** — `build_legs` (`:319-638`), `classify` (`:657-848`).
Thresholds: **`core/lifecycle_config.py`**, version **`L-v1-2026-08-16`**, stamped on every row.

**This is not a scorecard.** It is a **top-down rule cascade, first match wins**, over legs
that are each either *measured* or *asserted-absent with a reason*. It writes a
`lifecycle_stage` row per run and is the most rigorously fail-closed component audited.

---

## 1. EXACT COMPUTATION

### 1.1 Inputs and their sources — **two different origins, and that matters**

| Leg | Built from | Source | Grain |
|---|---|---|---|
| `fy_count` | usable FY rows | `income-statement?period=annual&limit=10` | **ANNUAL** |
| `revenue_basis` | gross, or **net for bank lens** | `revenue`, `interestExpense` | ANNUAL |
| `decline_streak` | consecutive declining FY revenue | `revenue` | ANNUAL |
| `revenue_cagr` | 3y CAGR | `revenue` | ANNUAL |
| `margin_trend_bp` | latest FY vs FY−3 operating margin, in bp | `operatingIncome`/`revenue` | ANNUAL |
| `margin_sign` | latest FY operating margin | same | ANNUAL |
| `cyclical_peaks`, `cyclical_peak_to_peak` | local revenue peaks | `revenue` | ANNUAL, needs **≥8 FY** |
| **`fcf_negative_2of3`** | 2 of last 3 FY FCF negative | **`fundamental_series` TABLE (DB)** | ANNUAL |
| **`cyclical_has_earned`** | any of last 4 FY with +op margin AND +FCF | **`fundamental_series` (DB)** | ANNUAL |
| **`reinvestment_heavy`** | latest sales-to-capital ≤ 1.50 | **`fundamental_series` (DB)** | ANNUAL |
| `pays_dividend` | any dividend | `dividends?limit=8` | event |
| `net_buyback` | share count shrinking | `shares-float` series | event |
| `capital_returns` | `pays_dividend OR net_buyback` | — | — |

**★ THREE LEGS COME FROM THE `fundamental_series` DATABASE TABLE, NOT FROM THE LIVE FEED**
(`evaluate.py:185-186`, `_fy_series_from_db`). That table is written by a *different* process
(`tools/expand_fcf_series.py`, the L-4c/d/f orders) on its own schedule. **This is the exact
coupling behind the stale-stage problem already on the CLAUDE.md punch list**, and QBTS in §6
is the worked instance.

### 1.2 The cascade — first match wins

**Pre-empt: `fy_count < 2`** → `YOUNG` / `rule2_young_insufficient_history` +
`INSUFFICIENT-HISTORY` + `YOUNG-UNCALIBRATED`. *Ordered first because it is a statement about
whether the other rules can be evaluated at all.*

**Rule 1 — DECLINE (STRICT AND; every leg must be PRESENT and pass):**
`decline_streak ≥ 2` (**≥3 on the cyclical lens**) **AND** `margin_trend_bp ≤ +100`
**AND** `capital_returns` true **AND** (non-cyclical **OR** `cyclical_peak_to_peak` present
and true).

**Rule 2 — YOUNG (OR):** `margin_sign < 0` **OR** `fcf_negative_2of3` — **unless blocked by
the cyclical guard** (`cyclical_has_earned` true **OR** unevaluable).

**Rule 3 — HIGROWTH (AND over PRESENT legs):** `revenue_cagr ≥ 0.15` **AND**
`reinvestment_heavy` **AND** `capital_returns` **false**. **`revenue_cagr` is
NON-NEGOTIABLE** — it may not be absent (`:830-831`: *"'high growth' with no measured growth
is not a classification, it is a guess"*).

**Rule 4 — MATURE:** residual. Nothing is measured; it is what is left.

### 1.3 Thresholds (`core/lifecycle_config.py`, `L-v1-2026-08-16`)

`TREND_WINDOW_YEARS=3` · `CAGR_WINDOW_YEARS=3` · `CYCLICAL_MIN_FY=8` ·
`MIN_FY_FOR_CLASSIFICATION=2` · `MARGIN_FLAT_BAND_BP=100.0` · `DECLINE_MIN_STREAK_YEARS=2` ·
`DECLINE_MIN_STREAK_YEARS_CYCLICAL=3` · `HIGROWTH_MIN_CAGR=0.15` ·
**`REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL=1.50`** (uncalibrated — see §4 Finding B).

## 2. ★★ ANALYST / ESTIMATE-DERIVED INPUTS

**NONE. ZERO.** Every leg is a filed annual statement figure, a dividend/share event, or a
value computed from them. **The stage classifier is the cleanest component in the engine on
this question** — no estimate, no target, no consensus, no LLM output anywhere in the path.

## 3. STAGE HANDLING — this component *produces* stage

- It **consumes `lens`**, load-bearingly and in three distinct places: the **bank net-revenue
  basis** (never gross), the **raised cyclical DECLINE streak bar** (3 vs 2), and the
  **cyclical YOUNG guard**. Nothing in the signature is unread.
- `lens_compatibility_flags` (`:857-871`) records `YOUNG+compounder`, `DECLINE+growth`,
  `MATURE+growth` — **flags only, NEVER reassigns a lens.** Bank lens exempt by design.
- **Downstream, the stage it writes reaches exactly one consumer: `tolerance_for()` → the B-2
  divergence band → whether E(R) is published.** See `06-expected-return.md` §3, including the
  `evaluate.py:193` "reads into NO score" string, which is false as written.

## 4. NEGATIVE / ZERO / MISSING HANDLING — **the best in the engine**

Absence is a **first-class typed value** here (`Leg.absent(name, reason)`), not a `None` that
falls through a ladder. Every absence is persisted to `absent_legs` in the `name(reason)`
form and stamped `INPUTS-INCOMPLETE`.

| Condition | Behaviour | Verdict |
|---|---|---|
| income rows UNKNOWN (feed flake) | **classification SKIPPED, no row written** (`evaluate.py:156-163`) | **fail-closed ✓✓** |
| any DECLINE leg absent | **DECLINE cannot fire** (strict AND over presence) | fail-closed ✓ |
| cyclical, <8 FY | peak guard asserted-absent → **DECLINE unreachable** + `CYCLICAL-GUARD-BLIND` | fail-closed ✓ |
| cyclical FCF series absent | **YOUNG withheld** (`guard_unevaluable` blocks) | fail-closed ✓ |
| `revenue_cagr` absent | **HIGROWTH cannot fire** | fail-closed ✓ |
| bank basis uncomputable | `INPUTS-INCOMPLETE`, **never falls back to gross** | fail-closed ✓ |
| transient vs structural absence | **distinct flag** `INPUTS-INCOMPLETE-FEED-TRANSIENT` | ✓ |
| **everything absent but `fy_count ≥ 2`** | **falls through to MATURE (residual)** | **★★ fail-open** |

**★ THE SYMMETRY IS EXPLICIT AND CORRECT** (`:786-790`): *"the peak gate denies DECLINE when
it cannot measure; this gate denies YOUNG when it cannot measure. Each gate refuses the tag
it guards."* **This is the standing fail-closed rule implemented properly — and it is the
model the Growth PE-leg and the Financial-Health leverage ladder should have followed.**

**★★ FINDING A — MATURE IS THE SILENT RESIDUAL AND HAS NO EVIDENCE OF ITS OWN.** Rule 4
measures nothing. Its stored assertion reads *"no earlier rule fired"*. So MATURE means
**"not DECLINE, not YOUNG, not HIGROWTH"** — and *every* fail-closed refusal above pushes a
name **toward** MATURE. A name whose DECLINE legs are absent, whose YOUNG guard is
unevaluable and whose CAGR is missing lands on MATURE with `INPUTS-INCOMPLETE` and **the same
stage label as a genuinely mature issuer.** The flag distinguishes them; the `computed_stage`
column does not. Since stage drives the B-2 band, **a fully unmeasurable name receives the
DEFAULT 15% band** — which is the narrowest, i.e. the conservative direction. *The
consequence is benign today and the flag exists; the label is still doing double duty.*

**★★ FINDING B — `REINVESTMENT_HEAVY` READS VISA AS HEAVY-REINVESTMENT, AND THE BAR IS
UNCALIBRATED.** `sales_to_capital ≤ 1.50 → heavy`. **V's live row: `0.871 @ 2025-09-30 vs bar
1.50 — HEAVY reinvestment`.** Visa is the most asset-light business in the universe; CLAUDE.md's
own calibration table puts asset-light WU at **1.553-3.203** and capital-heavy MU at
**0.332-0.669**. **V at 0.871 reads as more capital-intensive than GOOG (1.195-2.241).** The
threshold is already flagged `REINVESTMENT-THRESHOLD-UNCALIBRATED` on every firing and is a
standing punch-list item ("only GOOG 1.195 and MU 0.668 measured") — **this audit adds that it
is not merely uncalibrated but currently produces an economically wrong reading on a live
golden ticker.** It changed nothing for V (rule 3 also failed on CAGR **and** on
`capital_returns`), so **it is a latent trap, not a live defect** — but a name with >15% CAGR
and no dividend would classify HIGROWTH partly on this false leg.

**★ FINDING C — `net_buyback` IS NULL FOR V AND `capital_returns` STILL READS TRUE.** V's
stored inputs carry `"net_buyback": null` — the share-count series was unavailable — while
`capital_returns: true`, satisfied by the dividend alone. The assertion detail degrades
honestly (`pays_dividend=True`, with no `net_buyback` clause, versus MU's
`pays_dividend=True; net_buyback=False`). **Correct behaviour on an OR: one true leg settles
it.** Recorded because for a **non-dividend-paying** issuer the same NULL would leave
`capital_returns` resting entirely on an unknown, and Rule 3 tests `capital_returns` **false**
— so an unmeasurable buyback could admit a name to HIGROWTH. Not observed; structural.

## 5. NOT APPLICABLE (E(R) section)

## 6. WORKED EXAMPLES — LAST PRODUCTION EVALUATION (2026-08-28 acceptance run)

Verbatim from `lifecycle_stage.inputs_json` / `assertions_json`, config `L-v1-2026-08-16`.

### QBTS — `YOUNG` / `rule2_young`, lens `cyclical`, `inputs_incomplete = 1`

| Leg | Value |
|---|---|
| `fy_count` | **6** |
| `revenue_basis` | `gross_revenue` |
| `decline_streak` | 0 |
| `revenue_cagr` | **0.5077693248454678** (50.78%/y) |
| `margin_trend_bp` | +42,069.83 bp |
| **`margin_sign`** | **−408.21572375645667** (−408.22%) |
| **`fcf_negative_2of3`** | **true** — *"3 of last 3 FY FCF negative (2023, 2024, 2025)"* |
| `cyclical_has_earned` | **false** — *"no FY in the last 4 measured has both a positive operating margin and positive FCF"* |
| `cyclical_peak_to_peak` | **absent** — `under_8_fy_cannot_see_a_cycle` |
| `capital_returns` | false |

**Cascade:** `fy_count 6 ≥ 2` → Rule 1 fails (streak 0, and the peak guard is absent so
DECLINE is unreachable anyway) → **Rule 2: `margin_neg` TRUE and `fcf_neg` TRUE**; the
cyclical guard does **not** block (`cyclical_has_earned = false`, and it is *present*, so not
unevaluable) → **`YOUNG` / `rule2_young`.** ✓
Flags: `CYCLICAL-GUARD-BLIND-WINDOW-TOO-SHORT`, `YOUNG-UNCALIBRATED` ✓

**★★ THIS ROW IS THE STALE-STAGE MECHANISM, CAUGHT IN THE ACT.** QBTS's prior stage
(2026-08-17) was **`HIGROWTH` / `rule3_higrowth`**. Nothing about QBTS's business changed:
`revenue_cagr` is 50.78%, comfortably over the 15% bar, and it pays nothing — Rule 3 still
matches. What changed is that **`fcf_negative_2of3` went from ABSENT to TRUE when the L-4c/L-4d
orders wrote QBTS's rows into `fundamental_series`**, and Rule 2 is evaluated *before* Rule 3.
**A DB table written by a separate tool flipped a stage by supplying a leg that had previously
been unmeasurable** — exactly the coupling CLAUDE.md records as *"EVERY stage row predates its
own inputs"*. The flip was approved (`stage_flip_approvals` id 1) and persisted by this run.
**It also moves QBTS's B-2 band 20% → 30%, so this is the one live case where the stage
cascade reaches a published E(R).**

### MU — `MATURE` / `rule4_mature`, lens `cyclical`, `inputs_incomplete = 0`

| Leg | Value |
|---|---|
| `fy_count` | **10** |
| `decline_streak` | 0 — *"0 consecutive declining FY ending 2025-08-28"* |
| `margin_trend_bp` | **−513.71 bp** — *"−514bp 2022-09-01→2025-08-28 (31.54% → 26.41%)"* — **satisfied** |
| `margin_sign` | **+26.405907218149714** (positive) |
| `revenue_cagr` | **0.06713489726936261** (6.71%/y) |
| `fcf_negative_2of3` | false — *"1 of last 3 FY FCF negative"* |
| `cyclical_has_earned` | **true** — *"earned in 2022, 2024, 2025"* |
| `cyclical_peaks` | **`["2018:30,391,000,000", "2022:30,758,000,000"]`** — two most recent delta **+1.21%** |
| `capital_returns` | **true** (`pays_dividend=True; net_buyback=False`) |
| `reinvestment_heavy` | **true** — sales/capital **0.668** vs bar 1.50 |

**Cascade:** Rule 1 — `margin_trend_bp` and `capital_returns` both satisfied, but
`decline_streak = 0 < 3` → fails. Rule 2 — margin positive, FCF only 1 of 3 negative, **and**
the cyclical guard would have blocked anyway (`cyclical_has_earned = true`) → fails. Rule 3 —
**`revenue_cagr 6.71% < 15%`** → fails on the non-negotiable leg (`capital_returns = true`
also fails `returns_absent_ok`). → **`MATURE`** ✓
Flags: `GUARD-TOLERANCE-UNCALIBRATED` (two peaks measured), `REINVESTMENT-THRESHOLD-UNCALIBRATED` ✓

**★ MU IS THE CASE THE CYCLICAL GUARD WAS BUILT FOR, AND IT IS CURRENTLY QUIET.** The peak
pair 2018 → 2022 is **+1.21% apart** — essentially flat through-cycle revenue — and it is
logged rather than acted on, precisely so a tolerance can later be calibrated *"against REAL
refusals instead of chosen in advance"*. `GUARD-TOLERANCE-UNCALIBRATED` is doing what
CLAUDE.md says it does: staying up indefinitely because **zero real peak comparisons have
occurred.** This row is one.

### V — `MATURE` / `rule4_mature`, lens `compounder`, `inputs_incomplete = 0`

| Leg | Value |
|---|---|
| `fy_count` | **10** |
| `decline_streak` | 0 |
| `margin_trend_bp` | **−420.13 bp** — *"64.19% → 59.98%"* — satisfied |
| `margin_sign` | **+59.985** |
| `revenue_cagr` | **0.10921242130254294** (10.92%/y — *"29,310,000,000 → 40,000,000,000"*) |
| `fcf_negative_2of3` | false — *"0 of last 3 FY FCF negative"* |
| `cyclical_has_earned` | **null** (not a cyclical-lens name) |
| **`net_buyback`** | **null — UNKNOWN** |
| `capital_returns` | **true** (*"pays_dividend=True"* only) |
| `reinvestment_heavy` | **true** — sales/capital **0.871** vs bar 1.50 |

**Cascade:** Rule 1 — margin and capital-returns legs satisfied, `decline_streak = 0 < 2` →
fails. Rule 2 — margin positive, no negative FCF → fails. Rule 3 — `revenue_cagr 10.92% <
15%` **and** `capital_returns = true` → fails twice. → **`MATURE`** ✓
Flags: `REINVESTMENT-THRESHOLD-UNCALIBRATED` ✓

**★ V CARRIES BOTH FINDING B AND FINDING C ON ONE ROW:** it is labelled **HEAVY
reinvestment** at 0.871 (economically wrong for a payments network), and its `net_buyback` is
**NULL** while `capital_returns` reads true off the dividend alone. Neither changed V's stage.

## 7. BUILT BUT NEVER READ

- **`cyclical_peaks`** — measured and persisted on every cyclical evaluation **purely to
  accumulate calibration evidence**; no rule reads its value (it is `_record`ed with outcome
  `None` at `:741`). **Deliberate and correct** — listed so it is not mistaken for a live
  input. MU's `["2018:…", "2022:…"]` is the record accumulating as designed.
- **`revenue_basis`** — recorded as a leg so the basis travels with the row; consulted only
  for the bank absent-check, never scored.
- **`margin_trend_bp`** is read **only by Rule 1**. On a name where Rule 1 cannot fire (any
  absent DECLINE leg, or a cyclical with <8 FY like QBTS) it is computed, stored and
  unreachable — QBTS's **+42,070 bp** is a real example of a persisted value no rule could act
  on.
- **`stage_flip_approvals`** currently holds **one row** (QBTS, id 1). The table and the
  `tools/stage_freshness_sweep.py` halt path (exit 6) are armed but have exercised exactly one
  approval.
