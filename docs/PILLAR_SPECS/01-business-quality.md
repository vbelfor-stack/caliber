# PILLAR 1 — BUSINESS QUALITY (Profitability)
**Glass-box audit, 2026-08-29. Read-only. No fixes applied.**
HEAD `ff02e21` · suite 1091 · caliber.db md5 `69dc2328ee3af8a43d506b64665da39b` (unchanged).
Implementation: **`core/pillars.py:127-192`, `score_business_quality(yf, lens)`**.
Called once, from `score_all` at `core/pillars.py:986`.

---

## 1. EXACT COMPUTATION

Three scored legs, 3 points each, max 9. Score = `_score_from_points(pts, max_pts)` =
`round(1 + clamp(pts/max_pts, 0, 1) × 4)` → integer 1-5 (`core/pillars.py:37-42`).

| Leg | Input | FMP endpoint | FMP field | Grain | Ladder |
|---|---|---|---|---|---|
| 1 | `gross_margin` | `ratios-ttm` | `grossProfitMarginTTM` | **TTM** | ≥0.65 → 3 · ≥0.45 → 2 · ≥0.25 → 1 · else **0** |
| 2 | `operating_margin` | `ratios-ttm` | `operatingProfitMarginTTM` | **TTM** | ≥0.25 → 3 · ≥0.15 → 2 · ≥0.05 → 1 · else **0** |
| 3 | `roe` | `key-metrics-ttm` | `returnOnEquityTTM` | **TTM** | ≥0.25 → 3 · ≥0.15 → 2 · ≥0.05 → 1 · else **0** |
| — | `roa` | `key-metrics-ttm` | `returnOnAssetsTTM` | **TTM** | **NEVER SCORED — see §7** |

Flags: `CYCLE-PEAK-MARGINS` (lens is cyclical AND `gm > 0.55`) · `NEGATIVE-OPERATING-MARGIN`
(`om < 0`) · `NEGATIVE-ROE` (`roe < 0`). **All three are flag-only; none moves a point.**

Confidence = `min_conf(...)` over the four non-missing inputs including `roa`
(`adapters/base.py:37`) — the anti-launder minimum. **`roa` cannot change the score but CAN
lower the confidence label.**

EDGAR reaches this pillar **only through the cross-check confidence stamp**
(`core/edgar_cross_check.py`), which sets `source='fmp+EDGAR'` and may downgrade a field to
`low` on CONFLICT. It supplies no value.

## 2. ★★ ANALYST / ESTIMATE-DERIVED INPUTS

**NONE.** All four inputs are realised TTM accounting ratios off filed statements. **This is
the only pillar of the five with zero analyst contamination.** Stated explicitly so the
consolidated ★★ table in `INDEX.md` is not read as "everything is contaminated".

## 3. STAGE HANDLING

- **Stage: IGNORED.** No stage argument, no `lifecycle_stage` read. A pre-revenue YOUNG name
  and a MATURE compounder meet the same 0.65/0.45/0.25 ladder.
- **`lens`: READ, ONCE, FLAG-ONLY.** `core/pillars.py:139-140` — `if lens == "cyclical" and
  gm > 0.55` emits `CYCLE-PEAK-MARGINS` and appends a rationale clause. It changes **no
  point**. This is the only pillar besides Valuation where `lens` is read at all; contrast
  Growth and Financial Health, where it is signature-only.

## 4. NEGATIVE / ZERO / MISSING HANDLING

| Condition | Behaviour | Verdict |
|---|---|---|
| any input missing | leg dropped, **`max_pts` never incremented** — denominator shrinks | **fail-open** |
| `gross_margin < 0` | **0 of 3, NO FLAG** | fail-closed on points, silent |
| `operating_margin < 0` | 0 of 3 + `NEGATIVE-OPERATING-MARGIN` | fail-closed ✓ |
| `roe < 0` | 0 of 3 + `NEGATIVE-ROE` | fail-closed ✓ |
| **all three missing** | **score 3 (neutral), not a refusal** (`:172`, `else 3`) | **fail-open** |

**★★ FINDING A — NEGATIVE EQUITY INVERTS THE ROE LEG.** `roe = net income / book equity` is
scored on sign and magnitude with no equity-sign guard. A profitable issuer with **negative
book equity** (buyback-driven, common in mature compounders) produces `roe < 0` → **0 of 3
points and a `NEGATIVE-ROE` flag**, while a **loss-making** issuer with negative equity
produces `roe > 0` — **two negatives cancelling into a positive** — and can collect the full
3 points and the top rung. *Not demonstrated on a production row in this universe; recorded
as a structural inversion, unguarded.* Compare `_valuation_standard`'s sign gate at
`core/pillars.py:895-905`, which was ruled into existence for exactly this class of defect
("a negative multiple is an UNDEFINED one, not a cheap one") — **that reasoning was never
propagated to ROE.**

**★★ FINDING B — GROSS MARGIN IS SCORED IN ISOLATION FROM PROFITABILITY, AND QBTS IS THE
LIVE PROOF.** QBTS scores **2 of 3 gross-margin points on `gm = 64.19%`** while carrying
`om = −1372.9%`. Nothing relates the two legs; the ladder cannot see that the gross margin
is meaningless at that operating loss. **See the worked example in §6.**

**★★ FINDING C — `CYCLE-PEAK-MARGINS` FIRES ON A COMPANY WITH NO CYCLE.** The same QBTS row
carries `CYCLE-PEAK-MARGINS` and the rationale *"Peak-cycle margins inflate quality score"* —
on a pre-revenue quantum-computing issuer, because it sits on the **cyclical lens** via the
`_CYCLICAL_INDUSTRY` keyword sweep already punch-listed in CLAUDE.md (*"Matching keywords
against a vendor's free-text industry string is what put IONQ/INFQ on the cyclical lens"*).
**This is that known defect surfacing in a rationale string that ships to the synthesis
prompt.** The flag costs no points; the sentence reaches the model.

## 5. NOT APPLICABLE (E(R) section)

## 6. WORKED EXAMPLES — LAST PRODUCTION EVALUATION (2026-08-28 acceptance run)

### QBTS — eval id 289, lens `cyclical`, stage `YOUNG`/`rule2_young`

| Input | Value (verbatim from `field_provenance`) | Source | Conf |
|---|---|---|---|
| `gross_margin` | **0.641851106639839** (64.19%) | `fmp+EDGAR` | high |
| `operating_margin` | **−13.72877263581489** (−1372.88%) | `fmp+EDGAR` | high |
| `roe` | **−0.2666887569548216** (−26.67%) | `fmp+EDGAR` | high |
| `roa` | **−0.21468452992412143** (−21.47%) | `fmp+EDGAR` | high |

| Leg | pts | max |
|---|---|---|
| gm 0.6419 — ≥0.45, <0.65 | **+2** | 3 |
| om −13.73 — below every rung | 0 | 6 |
| roe −0.2667 — below every rung | 0 | 9 |
| **TOTAL** | **2** | **9** |

`round(1 + (2/9)×4)` = `round(1.889)` = **2**. Stored: **2** ✓
Flags: `CYCLE-PEAK-MARGINS`, `NEGATIVE-OPERATING-MARGIN`, `NEGATIVE-ROE` ✓ · confidence
`high` ✓ (all four inputs high).

### MU — eval id 286, lens `cyclical`, stage `MATURE`/`rule4_mature`

| Input | Value | Source | Conf |
|---|---|---|---|
| `gross_margin` | **0.7256906750559408** (72.57%) | `fmp+EDGAR` | high |
| `operating_margin` | **0.6573653543655981** (65.74%) | `fmp+EDGAR` | high |
| `roe` | **0.7054802658708248** (70.55%) | **`fmp[0.7055@2026-08-28] vs EDGAR[0.6664@2026-05-28] CONFLICT`** | **low** |
| `roa` | **0.3763197924123121** (37.63%) | `fmp+EDGAR` | high |

3 + 3 + 3 = **9 / 9** → `round(1 + 1.0×4)` = **5**. Stored: **5** ✓
Flags: `CYCLE-PEAK-MARGINS` (cyclical, gm 72.6% > 55%) ✓

**★ THE CONFIDENCE IS `low`, AND THE MECHANISM IS WORTH READING.** `min_conf` takes the
minimum across all four inputs, so the single **ROE CONFLICT** (FMP 0.7055 today vs EDGAR
0.6664 as of 2026-05-28 — a 5.9% basis gap, most likely stale-quarter vs TTM) drags the whole
pillar to `low` **while the score stays at the maximum 5.** The anti-launder rule is working
exactly as designed: full marks, explicitly low-confidence. **Do not read this as a defect.**

### V — eval id 294, lens `compounder`, stage `MATURE`/`rule4_mature`

| Input | Value | Source | Conf |
|---|---|---|---|
| `gross_margin` | **0.8018117245099802** (80.18%) | `fmp` | medium |
| `operating_margin` | **0.6068153209854342** (60.68%) | `fmp` | medium |
| `roe` | **0.6125605829520421** (61.26%) | `fmp` | medium |
| `roa` | **0.23884131514959298** (23.88%) | `fmp` | medium |

3 + 3 + 3 = **9 / 9** → **5**. Stored: **5** ✓ · no flags ✓ (lens is `compounder`, so the
cyclical peak-margin clause cannot fire even at an 80% gross margin) · confidence `medium`.

**★ NOTE THE ASYMMETRY V AND MU EXPOSE TOGETHER:** V's inputs are `fmp` only (no EDGAR
corroboration) and land at `medium`; MU's are `fmp+EDGAR` and land at `low` **because**
corroboration was attempted and disagreed. **A corroborated field can score WORSE on
confidence than an uncorroborated one.** That is the intended direction — an uncontested
single source is not evidence of agreement — but it means `medium` and `low` here mean
"never checked" and "checked, disagreed", which is not what the labels say.

## 7. BUILT BUT NEVER READ

- **`roa` IS FETCHED, EDGAR-CROSS-CHECKED, PERSISTED TO `field_provenance`, AND SCORES
  NOTHING.** `core/pillars.py:131` places it in `inputs`; **no ladder reads it.** It is the
  only asset-efficiency measure in the payload, and on a pillar named *Business Quality* it
  is inert. Its sole effect is via `min_conf`. Recorded, not fixed.
- **`profit_margin`** (`ratios-ttm.netProfitMarginTTM`) is fetched, carried on `TickerData`,
  EDGAR-cross-checked (`core/edgar_cross_check.py:147`) and classified currency-neutral
  (`core/reporting_currency.py:190`) — and **is read by no scorer at all**. Net margin does
  not enter Business Quality or any other pillar.
