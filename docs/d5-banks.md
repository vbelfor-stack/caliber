# Growth arming · JPM chain migration · four-bank onboarding + bank ladder proposal

**2026-08-09** · live FMP + EDGAR + FRED · **FRED 10Y = 4.69%**
Records: `docs/d5-bank-calibration.json`. `caliber.db` md5 `54aa42e5` — unchanged.
Suite **565 passed**.

**ARMED this pass:** growth (rate-shifted EV/Revenue thresholds).
**NOT ARMED:** bank — ladder proposed below, awaiting ruling.

---

## 1. Growth lens — armed, reviewed diff

Mechanism as ratified: EV/Revenue thresholds × `k = (R0 + ERP)/(R + ERP)`, **R0 = 4.0
provisional**, ERP = 4.5, clamp **[0.60, 1.80] locked**, revisit trigger 10Y outside 3–6%.
The instrument is untouched per the standing ruling — Rule-of-40 gate and rung ordering are
identical; only the thresholds move.

| Ticker | before | after | Δ | flags after |
|---|---|---|---|---|
| MU | 4 | 4 | +0 | `RATE-SHIFT-K=0.92`, `RULE40=115` |
| GOOG | 3 | 3 | +0 | `RATE-SHIFT-K=0.92`, `RULE40=48` |
| V | 4 | 4 | +0 | `RATE-SHIFT-K=0.92`, `RULE40=72` |
| NOW | 2 | 2 | +0 | `RATE-SHIFT-K=0.92`, `RULE40=32` |
| WU | 3 | 3 | +0 | `RATE-SHIFT-K=0.92`, `RULE40=12` |

**Δ0 on all five at k = 0.925, confirmed by re-measurement, not assumed.** Each score now
carries its shift factor as a flag, and a `RATE-SHIFT-CLAMPED` flag fires if the [0.60, 1.80]
clamp ever binds — because at that point the shift stops being a smooth function of the rate
and that must be visible rather than silently flattened.

`ARMED_LENSES` is kept distinct from `ARMED_PANEL_LENSES` in the code: growth is armed but
**rate-anchored, not panel-anchored**. "Armed" and "panel-scored" are not the same set.

---

## 2. JPM chain migration — executed, golden five verified unchanged

### Placement decision, and why it deviates from the literal ruling

`CashAndDueFromBanks` → **`cash`** chain, appended second so the generic tag still wins for
every non-bank.

`LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` → **`total_debt_reported`**,
**not `long_term_debt`**. Its name is explicit: it *includes current maturities*, making it a
debt **total**, not the non-current leg. Chaining it on `long_term_debt` would have conflated
two bases — the same error class the R-B lease work and the NET-vs-gross `debt_to_equity`
advisory exist to prevent — and would then have double-counted the current portion against
`current_debt` downstream.

**Consequence, stated: JPM's `long_term_debt` stays withheld.** It files no non-current-only
debt tag. That is the honest answer, and it is pinned by test.

### Golden-five verification — done LIVE, because the fixture check was misleading

The fixture-based check reported "no change" for all six, but that was an artifact: the golden
fixtures predate the new tags, so they *cannot* contain them. Re-run against live SEC data:

| Ticker | resolved | change |
|---|---|---|
| MU | 19/19 | — none — |
| **GOOG** | **18/19** | `total_debt_reported`: `no_tag` → **`stale_tag`** (still withheld) |
| V | 14/19 | — none — |
| NOW | 18/19 | — none — |
| WU | 15/19 | — none — |
| **JPM** | **9/19 → 11/19** | `cash` → **24.72B** @2026-06-30; `total_debt_reported` → **460.5B** @2026-06-30 |

**No golden-five resolution changed.** GOOG does file the new debt tag, but its newest fact is
2024-09-30 — ~639 days behind its latest filed period, so the 450-day stale gate withholds it.
Its *reason* becomes strictly more accurate: the tag exists and was abandoned, which is what
`stale_tag` means. `total_debt_reported` is a DARK field in any case (computed, applied to
nothing), so no confidence, score or grade could have moved either way.

The expected-fail pin `test_jpm_cash_is_withheld_by_the_stale_gate` fired as designed and has
been **flipped** to `test_jpm_cash_resolves_through_the_bank_tag`.

---

## 3. Bank onboarding — BK, USB, C

All recorded through the production paths. **All four select the `bank` lens** (SIC 602x).

### New integration finding: FMP ↔ SEC ticker mismatch

**BK could not be onboarded at all at first.** BNY Mellon trades as `BK` and FMP serves it that
way, but SEC's `company_tickers.json` lists it as **`BNY`** (CIK 1390777) after the 2024
rebrand, so `_get_cik` raised. Added `SEC_TICKER_ALIASES`, an **explicit per-issuer map** — no
fuzzy name matching, because two filers can share a name fragment and silently pairing the
wrong CIK would cross one issuer's fundamentals with another's price, the worst failure this
pipeline can have.

### E-2 coverage and tag migrations

| Ticker | CIK | SIC | resolved | latest period |
|---|---|---|---|---|
| JPM | 0000019617 | 6021 | 11/19 | 2026-06-30 |
| BK | 0001390777 | 6022 | 11/19 | 2026-06-30 |
| USB | 0000036104 | 6021 | 10/19 | 2026-06-30 |
| C | 0000831001 | 6021 | 11/19 | **2025-12-31** |

**Systematic finding — the equity conflict gate fires on 3 of 4 banks:**

| Ticker | StockholdersEquity | …IncludingNoncontrollingInterest | gap |
|---|---|---|---|
| BK | 44.664B | 45.264B | 1.3% |
| USB | 67.432B | 67.895B | 0.7% |
| C | 212.291B | 213.822B | 0.7% |

Banks routinely carry minority interests, so both tags are filed fresh and genuinely disagree.
The gate is **deliberately armed on `equity`** (the one chain kept conflict-checked), so this is
it working, not failing — but it means three of four banks have no EDGAR equity. It does **not**
block the bank instrument, which takes ROE from FMP. JPM is the exception: it files only one.

Other withholdings are structural and expected for banks: no `AssetsCurrent`/`LiabilitiesCurrent`
(unclassified balance sheet, so no current_ratio), no `CostOfRevenue`, no `OperatingIncomeLoss`.
USB's `long_term_debt` is stale 1004d; C's `cost_of_revenue` stale 1826d.

**C's latest period-end is 2025-12-31, two quarters behind the others** — worth noting before
any live bank run, since R1 symmetric gating would treat it as lagged.

---

## 4. Bank instrument — four-point calibration

`justified P/B = ROE / CoE`, `CoE = 10Y + β × ERP`, ERP = 4.5pp, 10Y = 4.69%.

| Ticker | P/B | ROE | β | CoE | justified P/B | **difference** | **ratio** | excess ROE |
|---|---|---|---|---|---|---|---|---|
| JPM | 2.66 | 17.81% | 0.977 | 9.09% | 1.96 | +0.70 | **1.36** | +8.72pp |
| BK | 2.20 | 14.18% | 1.040 | 9.37% | 1.51 | +0.68 | **1.45** | +4.81pp |
| USB | 1.47 | 12.49% | 0.978 | 9.09% | 1.37 | +0.10 | **1.07** | +3.40pp |
| C | 1.08 | 8.39% | 1.102 | 9.65% | 0.87 | +0.21 | **1.24** | **−1.26pp** |

### The headline: C is the discriminator, and it works

**C trades at 1.08× book — below-book-ish, the classic bank screen — but 1.24× *justified*
book**, because its ROE (8.39%) does not cover its cost of equity (9.65%). Cheap on book, dear
on what it actually earns. That is the bank-lens analogue of the value trap, and it is exactly
why you picked C.

### RECOMMENDATION: put the ladder on the RATIO, not the difference

You ruled the ladder as `P/B − justified P/B`. **The four readouts argue against it:**

- JPM **+0.70** and BK **+0.68** are indistinguishable on the difference, but sit at **1.36×**
  and **1.45×** of justified — BK is materially dearer relative to what it earns.
- The difference is **scale-dependent in the justified value**: +0.70 is a 36% premium on JPM's
  justified 1.96, but would be an 80% premium on C's justified 0.87. The ratio normalises that;
  the difference does not.

Both are computed and reported so you can compare directly. **Proposed ladder on
`r = P/B ÷ justified P/B`:**

| r | score |
|---|---|
| < 0.85 | 5 |
| < 1.05 | 4 |
| < 1.25 | 3 |
| < 1.50 | 2 (`RICH-VS-JUSTIFIED-PB`) |
| ≥ 1.50 | 1 (`VERY-RICH-VS-JUSTIFIED-PB`) |

**Plus an EXCESS-ROE GATE: excess ROE < 0 → cap at 3**, flagged `ROE-BELOW-COST-OF-EQUITY`.
Same shape as the cyclical peak gate and for the same reason — a low P/B on a bank that does
not cover its cost of equity is cheap *for a reason*, and no rung geometry over the price can
express that the denominator is impaired.

Applied to the calibration set:

| Ticker | ratio | raw | **score** | flags |
|---|---|---|---|---|
| JPM | 1.36 | 2 | **2** | `RICH-VS-JUSTIFIED-PB` |
| BK | 1.45 | 2 | **2** | `RICH-VS-JUSTIFIED-PB` |
| USB | 1.07 | 3 | **3** | — |
| C | 1.24 | 3 | **3** | `ROE-BELOW-COST-OF-EQUITY` |

### Honest limits of this calibration

1. **The gate does not bite on today's four.** C is already at 3 on the ratio alone. The gate is
   written for the case *not* in this set — a sub-book bank whose ROE has collapsed, precisely
   when the instrument would otherwise scream buy. It is tested synthetically, not live.
2. **No bank in the set trades below justified book**, so the 5 and 4 rungs are **uncalibrated**.
   Every live point lands on 2 or 3. If you want those rungs evidenced rather than reasoned,
   the set needs a genuinely distressed name.
3. **Four points cannot validate five rungs.** The boundaries are argued from the shape of the
   instrument and the spacing of the four, not measured.
4. **β is FMP-sourced and single-source.** It moves CoE directly, and there is no cross-check
   on it — a wrong β silently moves justified P/B.

**Bank remains unarmed pending your ruling.** Pinned by
`test_bank_lens_is_still_not_armed`.
