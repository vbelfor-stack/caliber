# PILLAR 2 — FINANCIAL HEALTH (Financial Strength)
**Glass-box audit, 2026-08-29. Read-only. No fixes applied.**
HEAD `ff02e21` · suite 1091 · caliber.db md5 `69dc2328ee3af8a43d506b64665da39b` (unchanged).
Implementation: **`core/pillars.py:197-267`, `score_financial_health(yf, lens)`**.

---

## 1. EXACT COMPUTATION

Three scored legs (max 7) plus one flag-only leg, plus **a bonus point that is added to the
numerator without being added to the denominator**.

| Leg | Input | FMP endpoint | FMP field | Grain | Ladder |
|---|---|---|---|---|---|
| 1 | `current_ratio` | `ratios-ttm` | `currentRatioTTM` | **TTM** | ≥2.0 → 2 · ≥1.0 → 1 · else **0** + `CURRENT-RATIO-BELOW-1` |
| 2 | `debt_to_equity` | `ratios-ttm` | `debtToEquityRatioTTM` **× 100** | **TTM** | ≤30 → 3 · ≤100 → 2 · ≤200 → 1 · else **0** + `HIGH-LEVERAGE` |
| 3 | `free_cashflow` | `cash-flow-statement?period=annual&limit=1` | `freeCashFlow` | **ANNUAL, 1 row** | >0 → 2 · else **0** + `NEGATIVE-FCF` |
| 3b | **bonus** | leg 3 ÷ `market_cap` | — | annual ÷ spot | `fcf/market_cap×100 ≥ 3` → `pts = min(pts+1, max_pts)` |
| 4 | `total_cash` − `total_debt` | `balance-sheet-statement?period=annual&limit=1` | `cashAndShortTermInvestments`, `totalDebt` | **ANNUAL, 1 row** | **flag only** — `NET-CASH-POSITIVE` |

`market_cap` ← `market-capitalization?symbol=X`.`marketCap` (Vic ruling 3, 2026-08-28), with a
**silent fallback to `key-metrics-ttm.marketCap` when the endpoint is absent** — which is the
state of every recorded fixture (`adapters/fmp_adapter.py:495-497`). Offline and live can
therefore score this leg on two different caps; pinned, deliberate, recorded in the adapter.

**★ UNIT NOTE — `debt_to_equity` IS IN PERCENT, NOT RATIO.** `_ratio_to_percent(...)` at
`fmp_adapter.py:430`. This is the **ratio-vs-percent defect that ran eight days behind 654
green tests** (CLAUDE.md, golden-harness ledger entry). The ladder constants 30/100/200 are
percent and the conversion is the fix. **Do not "simplify" either half.**

## 2. ★★ ANALYST / ESTIMATE-DERIVED INPUTS

**NONE.** Every input is a filed balance-sheet or cash-flow figure, or a market price.
Second of two clean pillars.

## 3. STAGE HANDLING

- **Stage: IGNORED.**
- **★ `lens` IS IN THE SIGNATURE AND NEVER READ.** `score_financial_health(yf, lens)` uses
  `lens` only as `method=lens` on the returned `PillarResult` (`:264`). Same shape as
  `score_growth`'s unused `edgar`. **A bank and a pre-revenue biotech meet the identical
  `current_ratio ≥ 2.0` and `debt/equity ≤ 30%` ladder** — and current ratio is close to
  meaningless for a bank, which is part of why the financials class was gated out entirely.

## 4. NEGATIVE / ZERO / MISSING HANDLING

| Condition | Behaviour | Verdict |
|---|---|---|
| any input missing | leg dropped, `max_pts` not incremented | **fail-open** |
| `current_ratio < 1` | 0 of 2 + flag | fail-closed ✓ |
| `free_cashflow ≤ 0` | 0 of 2 + `NEGATIVE-FCF` | fail-closed ✓ |
| `debt_to_equity > 200` | 0 of 3 + `HIGH-LEVERAGE` | fail-closed ✓ |
| **`debt_to_equity < 0`** | **3 of 3 — TOP RUNG** | **★★ FAIL-OPEN INVERSION** |
| `market_cap` missing/≤0 | bonus skipped, no flag | fail-closed ✓ |
| all three missing | **score 3 (neutral)**, no refusal | **fail-open** |

**★★ FINDING A — NEGATIVE EQUITY SCORES AS ZERO LEVERAGE. THE WORST FAIL-OPEN IN THE
ENGINE.** `core/pillars.py:214-222` tests `if de <= 30: pts += 3` **with no lower bound.**
A company with **negative book equity** produces a negative `debtToEquityRatioTTM`, and
`−150 ≤ 30` is `True`, so it collects **the maximum 3 of 3 leverage points and no flag.**
This is structurally identical to the RKLB defect that was ruled and fixed in
`_valuation_standard` — *"a NEGATIVE multiple is not a cheap one, it is an UNDEFINED one"*
(`core/pillars.py:895-905`, L-2b, after RKLB scored 5/5 on EV/EBITDA −372.6x). **The sign
gate was applied to the valuation ladders and never propagated to the leverage ladder.**
Negative equity is the *most* levered balance sheet there is, and it scores as the least.
*Not observed on a production row in the current 28-name universe — all three worked
examples are positive. Structural, unguarded, and it is the same defect class the project
has already ruled on once.* **Needs a ruling; not repaired here.**

**★★ FINDING B — THE FCF-YIELD BONUS IS A NUMERATOR-ONLY POINT ON A SECOND, DISAGREEING
BASIS.** Two separate things:
1. **Asymmetry.** `pts = min(pts + 1, max_pts)` (`:238`) adds to the numerator while
   `max_pts` stays at 7. The FCF leg is advertised as worth 2 points and can deliver 3.
2. **★★ TWO FCF YIELDS ON TWO BASES IN ONE EVALUATION.** This bonus computes
   `annual freeCashFlow ÷ market-capitalization`, while `TickerData.fcf_yield` — the field
   the **Valuation** pillar and the compounder panel read — is FMP's own
   `key-metrics-ttm.freeCashFlowYieldTTM`, a **TTM** figure. They are never reconciled.
   **V straddles the 3% threshold between them: its stored `fcf_yield` reads 0.02949 (2.95%),
   which is BELOW the bar, yet V demonstrably collected the bonus (§6).** One evaluation,
   one company, one concept, two numbers on opposite sides of a scoring threshold.

**★★ FINDING C — CALIBRATION, NOT CODE: A PRE-REVENUE COMPANY READS AS FINANCIALLY STRONG.**
QBTS scores **4 of 5** on Financial Strength while carrying negative FCF and a −1372.9%
operating margin, because a recent equity raise gives it `current_ratio 20.55` (+2) and
nobody lends to it so `debt/equity = 1.21%` (+3). **The two strongest signals in the pillar
are both artefacts of having raised equity and having no debt capacity.** The ladder cannot
distinguish "no debt because it is prudent" from "no debt because it is unfinanceable."
Recorded as a calibration finding for ruling, not as a code defect.

## 5. NOT APPLICABLE (E(R) section)

## 6. WORKED EXAMPLES — LAST PRODUCTION EVALUATION (2026-08-28 acceptance run)

Provenance order is the `inputs` list at `core/pillars.py:201-204`:
`[current_ratio, debt_to_equity, free_cashflow, total_debt, total_cash]`.

### QBTS — eval id 289

| Input | Value |
|---|---|
| `current_ratio` | **20.545114710840725** |
| `debt_to_equity` | **1.2072642667873068** (%) |
| `free_cashflow` | **−75,844,000** (−$0.076B) |
| `total_debt` | **43,457,000** |
| `total_cash` | **884,481,000** |

| Leg | pts | max |
|---|---|---|
| cr 20.55 ≥ 2.0 | +2 | 2 |
| d/e 1.21% ≤ 30 | +3 | 5 |
| FCF −$75.8M ≤ 0 → `NEGATIVE-FCF`; **bonus unreachable** | 0 | 7 |
| net cash = 884,481,000 − 43,457,000 = **+$841.0M** → `NET-CASH-POSITIVE` | flag | — |
| **TOTAL** | **5** | **7** |

`round(1 + (5/7)×4)` = `round(3.857)` = **4**. Stored: **4** ✓
Flags: `NEGATIVE-FCF`, `NET-CASH-POSITIVE` ✓ · confidence `medium` ✓

### MU — eval id 286

| Input | Value |
|---|---|
| `current_ratio` | **3.4245176518883413** |
| `debt_to_equity` | **6.330169572296573** (%) |
| `free_cashflow` | **1,668,000,000** |
| `total_debt` | **15,278,000,000** |
| `total_cash` | **10,307,000,000** |

| Leg | pts | max |
|---|---|---|
| cr 3.42 ≥ 2.0 | +2 | 2 |
| d/e 6.33% ≤ 30 | +3 | 5 |
| FCF +$1.668B > 0 | +2 | 7 |
| bonus: 1.668B ÷ ~$1.05T ≈ **0.16%** — below 3%, **not awarded** | — | — |
| net cash = 10.307B − 15.278B = **−$4.971B** → no flag | — | — |
| **TOTAL** | **7** | **7** |

`round(1 + 1.0×4)` = **5**. Stored: **5** ✓ · flags `[]` ✓ (net cash correctly negative)

### V — eval id 294

| Input | Value |
|---|---|
| `current_ratio` | **0.9852226141672228** |
| `debt_to_equity` | **67.82079708908977** (%) |
| `free_cashflow` | **21,577,000,000** |
| `total_debt` | **25,171,000,000** |
| `total_cash` | **21,987,000,000** |

| Leg | pts | max |
|---|---|---|
| cr 0.985 **< 1.0** → 0 + `CURRENT-RATIO-BELOW-1` | 0 | 2 |
| d/e 67.82% — in (30, 100] | +2 | 5 |
| FCF +$21.577B > 0 | +2 | 7 |
| **bonus AWARDED** — see derivation below | **+1** | 7 |
| net cash = 21.987B − 25.171B = **−$3.184B** → no flag | — | — |
| **TOTAL** | **5** | **7** |

`round(1 + (5/7)×4)` = `round(3.857)` = **4**. Stored: **4** ✓

**★ THE BONUS IS PROVEN BY THE STORED SCORE, NOT ASSUMED.** Without it `pts = 4` and
`round(1 + (4/7)×4) = round(3.286) = 3`. The stored score is **4**, so the bonus must have
fired — i.e. `freeCashFlow ÷ market_cap` cleared 3.0%. **And V's own stored `fcf_yield` is
0.02949 = 2.95%, which does NOT clear it.** That is Finding B measured on a live row: the
same company is simultaneously above and below the same 3% bar depending on which of the two
FCF-yield computations you read. **V is the case that makes the two-basis problem
non-theoretical.**

## 7. BUILT BUT NEVER READ

- **`operating_cashflow`** — fetched (`cash-flow-statement.netCashProvidedByOperatingActivities`),
  EDGAR-cross-checked (`core/edgar_cross_check.py:206`), and **listed in
  `MONETARY_SCORE_BEARING_FIELDS`** (`core/reporting_currency.py:180`) — i.e. the USD-only
  currency guard blocks it as *score-bearing* — **yet no scorer in the runtime reads it.**
  The guard is guarding a field nothing scores. Harmless today; the label is wrong.
- **`enterprise_value`** — same shape: fetched, in `MONETARY_SCORE_BEARING_FIELDS`
  (`:182`), read by nothing. Only the derived `ev_to_ebitda` / `ev_to_revenue` ratios are used.
- **`total_debt` and `total_cash`** are scored **only as a flag** (`NET-CASH-POSITIVE`).
  Neither contributes a point, on a pillar named Financial Strength.
