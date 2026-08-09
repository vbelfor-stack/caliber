# Phase D-4 — arming, reviewed diff, growth dark pass, JPM onboarding

**2026-08-09** · live FMP + EDGAR + FRED · **FRED 10Y = 4.69%**
Records: `docs/d4-diff.json` (before/after, 25 cells), `docs/d4-arming.json` (post-arm panel).
`caliber.db` md5 `54aa42e56b4b753fab18b77b552665fb` — unchanged. Suite **548 passed**.

**ARMED:** compounder, cyclical, standard.
**NOT ARMED:** growth (panel mapping rejected permanently; rate-shifted mechanism dark below),
bank (mechanism ruled, awaiting calibration ruling on JPM).

---

## 1. Golden-five re-baseline — REVIEWED DIFF

Before = fixed absolute ladders. After = panel-anchored (MIN across available anchors) for
the three armed lenses. Same live fetch, same 10Y, both sides. `*` = native lens.

| Ticker | Lens | | armed | before | after | Δ | binding anchor | spread |
|---|---|---|---|---|---|---|---|---|
| GOOG | compounder | `*` | YES | 1 | **1** | +0 | risk_free | −3.45pp |
| GOOG | cyclical | | YES | 2 | 2 | +0 | risk_free | +0.99pp |
| GOOG | standard | | YES | 4 | 4 | +0 | risk_free | +2.81pp |
| GOOG | growth | | no | 3 | 3 | +0 | — | — |
| GOOG | bank | | no | 1 | 1 | +0 | — | — |
| MU | cyclical | `*` | YES | 2 | **2** | +0 | **own_history** | −0.65pp |
| MU | compounder | | YES | 2 | 2 | +0 | risk_free | −2.05pp |
| MU | standard | | YES | 4 | 4 | +0 | risk_free | +2.35pp |
| MU | growth | | no | 4 | 4 | +0 | — | — |
| MU | bank | | no | 1 | 1 | +0 | — | — |
| NOW | growth | `*` | no | 2 | **2** | +0 | — | — |
| NOW | cyclical | | YES | 2 | **1** | **−1** | risk_free | −3.40pp |
| NOW | standard | | YES | 1 | **2** | **+1** | risk_free | −2.11pp |
| NOW | compounder | | YES | 2 | 2 | +0 | risk_free | −1.14pp |
| NOW | bank | | no | 1 | 1 | +0 | — | — |
| V | compounder | `*` | YES | 2 | **2** | +0 | **sector** | −2.52pp |
| V | cyclical | | YES | 2 | 2 | +0 | sector | −2.37pp |
| V | standard | | YES | 2 | 2 | +0 | sector | −1.39pp |
| V | growth | | no | 4 | 4 | +0 | — | — |
| V | bank | | no | 1 | 1 | +0 | — | — |
| WU | compounder | `*` | YES | 5 | **5** | +0 | **sector** | +12.61pp |
| WU | cyclical | | YES | 5 | **4** | **−1** | own_history | +1.38pp |
| WU | standard | | YES | 5 | 5 | +0 | sector | +17.89pp |
| WU | growth | | no | 3 | 3 | +0 | — | — |
| WU | bank | | no | 2 | 2 | +0 | — | — |

**3 of 25 cells moved. All five NATIVE cells are unchanged.** Every move is in a
counterfactual forced-lens cell — NOW cyclical (2→1), NOW standard (1→2), WU cyclical (5→4).
No ticker's actual score changed, so **no E(R) and no grade moves from this arming**.

### What changed even where the score did not

The binding denominator moved on three native cells without crossing a rung:

- **MU cyclical binds on own_history (−0.65pp)** — the founding case. The anchor calling MU
  rich at a cycle peak is now the one setting its score, and the peak gate caps it at 2 on
  top of that. Before arming, this cell was a forward-PE ladder that never saw own history.
- **V and WU compounder bind on sector**, not risk-free. Both were risk-free-only before.
- **WU compounder now carries `SECULAR-DECLINE-FCF-YIELD`** at a sector-bound +12.61pp — the
  declining-business guard firing on the name D-0 identified as the value-trap case.

That is the panel doing its work while leaving the rungs alone, which is the best available
outcome for a first arming: the mechanism is live and auditable before it ever moves a grade.

### Offline (fixture) baseline

The six pinned fixture cells in `tests/test_pillars.py::GOLDEN_VALUATION` are **unchanged in
score** (MU 2/2, GOOG 3/1, V 5/2). They gained `PANEL-NARROWED-MARKET-ONLY`, which is correct:
fixture calls carry no sector snapshot and no EDGAR, so the armed lenses fall back to a
risk-free-only panel and the flag is that fallback declaring itself. `PRE_D4_SCORES` is kept
in the test file so the diff stays auditable from the test alone.

### One real bug found and fixed during arming

Threading the panel from the boundaries left `panel=None` for anyone calling a lens function
**directly**. The compounder then skipped its entire FCF branch and fell through to
EV/EBITDA — silently dropping `SECULAR-DECLINE-FCF-YIELD`. Caught by the existing
secular-decline tests. The risk-free-only fallback now lives inside `_panel_score`, so a lens
behaves identically whether it is entered through the dispatcher or called directly. A guard
that only works when entered by the front door is not a guard.

`run_dark_panel` was also renamed **`build_panel`**: it is load-bearing now, and its broad
`except` no longer claims "evaluation unaffected" — it says it degrades to risk-free-only.

---

## 2. Growth lens — dark pass on the RULED mechanism

Ruling applied: **lenses keep their instruments, the rate shifts thresholds, not measures.**
The growth lens keeps Rule-of-40 × EV/Revenue and becomes rate-aware by moving the EV/Revenue
thresholds.

**Proposed mechanism.** Multiply every EV/Revenue threshold by

```
k = (R0 + ERP) / (R + ERP)        R0 = 4.0 (baseline 10Y), ERP = 4.5pp
k clamped to [0.60, 1.80]
```

A growth multiple is a duration asset, so its defensible level scales roughly inversely with
the discount rate. `k` is a pure threshold shift — the instrument, the Rule-of-40 gate and the
rung ordering are all untouched.

| 10Y | 0.0% | 1.0% | 2.0% | **4.0%** | **4.69%** | 6.0% | 8.0% | 12.0% |
|---|---|---|---|---|---|---|---|---|
| k | 1.800 | 1.545 | 1.308 | **1.000** | **0.925** | 0.810 | 0.680 | 0.600 |

**Proposed threshold ladder** (base → shifted at today's 4.69%):

| Rule-of-40 | base EV/Rev rungs | shifted at 4.69% | floor score |
|---|---|---|---|
| ≥ 60 | <10 → 5, <20 → 4 | <9.25 → 5, <18.50 → 4 | 3 |
| ≥ 40 | <8 → 4, <15 → 3 | <7.40 → 4, <13.87 → 3 | 2 |
| < 40 | <6 → 3, <10 → 2 | <5.55 → 3, <9.25 → 2 | 1 |

**Measured deltas at the live rate: ZERO.**

| Ticker | EV/Rev | Rule-of-40 | live | shifted | Δ |
|---|---|---|---|---|---|
| MU | 10.77 | 114.6 | 4 | 4 | +0 |
| GOOG | 9.74 | 48.2 | 3 | 3 | +0 |
| V | 15.47 | 72.0 | 4 | 4 | +0 |
| NOW | 9.17 | 32.3 | 2 | 2 | +0 |
| WU | 0.88 | 12.2 | 3 | 3 | +0 |

**But it is genuinely rate-sensitive** — which is the point, and the thing the current fixed
ladder cannot do:

| Ticker | 0% | 1% | 2% | 4% | 4.69% | 6% | 8% |
|---|---|---|---|---|---|---|---|
| MU | 5 | 5 | 5 | 4 | 4 | 4 | 4 |
| GOOG | 4 | 4 | 4 | 3 | 3 | 3 | 3 |
| V | 5 | 4 | 4 | 4 | 4 | 4 | 3 |
| NOW | 3 | 3 | 2 | 2 | 2 | **1** | 1 |
| WU | 3 | 3 | 3 | 3 | 3 | 3 | 3 |

Reading: at ZIRP every name earns a rung it does not earn today, and above 6% NOW falls to the
floor. WU is invariant because a 0.88x EV/Revenue is cheap in any rate regime — correct
behaviour, not a dead mechanism.

**Recommendation: arm it.** Zero disruption at the current rate, correct direction under
stress, no instrument swap, and one constant (`R0 = 4.0`) that is explicit and arguable rather
than buried in five hardcoded thresholds. **Your ruling — it is not armed.**

Open question for that ruling: `R0 = 4.0` is my reading of the rate the existing ladder was
implicitly calibrated at. It is a judgement call, not a measurement, and it sets where `k = 1`.

---

## 3. JPM onboarding — the bank-lens calibration instrument

Fixtures recorded through the production paths (`tools.record_fmp_fixture`,
`tools.record_edgar_fixture`). **CIK 0000019617, SIC 6021, Banks — Diversified, NYSE.**

**Lens selection confirmed: `bank`.** This is the first real bank in the set; every bank-lens
number in the D-3 report was a forced-lens counterfactual.

**Explicitly a calibration instrument, not a holding.** JPM is in the golden EDGAR/FMP fixture
set and in `CALIBRATION_CIKS`, and is deliberately **absent from `tickers.txt`** — pinned by
`test_jpm_is_not_in_the_batch_universe`, so it cannot drift into the batch universe and start
consuming synthesis budget for a position nobody holds.

### E-2 onboarding diagnostic — 9/19 fields resolved

Two of these are **tag migrations** and are the actionable findings:

| Field | Reason | Finding |
|---|---|---|
| **cash** | `stale_tag` (2738d) | **JPM abandoned `CashAndCashEquivalentsAtCarryingValue` at 2018-12-31 and now files the bank-specific `CashAndDueFromBanks` (current to 2026-06-30).** The stale gate correctly withheld a 7.5-year-old figure rather than serving it wearing a fresh label. |
| **long_term_debt** | `stale_tag` (4383d) | **`LongTermDebt` abandoned ~12 years ago; JPM now files `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` (current to 2026-06-30).** |
| current_assets, current_liabilities | `no_tag` | Unclassified balance sheet — banks file neither. Same accepted limit as WU. No current_ratio. |
| cost_of_revenue, gross_profit | `no_tag`, `derive_incomplete` | Structural: a bank has no cost of revenue. Not fixable, not a defect. |
| operating_income | `no_tag` | `OperatingIncomeLoss` not filed; banks present a different income structure. |
| capex, short_term_investments, total_debt_reported | `no_tag` | Not filed under any chained synonym. |

**I did not extend the synonym chains.** Adding `CashAndDueFromBanks` changes EDGAR field
resolution for *every* ticker and feeds the armed cross-check — that is E-2 work under its own
ruling, not something to slip into D-4. `test_jpm_cash_is_withheld_by_the_stale_gate` pins the
current state and **is expected to fail when the chain is extended** — that failure is the
signal the fix landed, same pattern as the anti-launder pin.

Core earnings fields the bank instrument needs — `revenue`, `net_income`, `equity`,
`total_assets` — all resolve.

### Bank instrument, dark-calibrated on JPM

`justified P/B = ROE / CoE`, `CoE = 10Y + β × ERP` (ERP 4.5pp).

| | JPM |
|---|---|
| P/B | **2.66** |
| ROE | 17.81% |
| β | 0.977 |
| CoE | 9.09% |
| **justified P/B** | **1.96** |
| P/B − justified | **+0.70** |

JPM trades ~36% above its justified P/B: a real bank, ROE comfortably above cost of equity
(excess ROE +8.7pp), and a premium that is material but not absurd. Every input the instrument
needs is present — unlike the golden five, where β on a cyclical (MU 2.19) inflated CoE into
nonsense. **The instrument behaves correctly on the name it was designed for.**

**Still missing for arming: a ladder.** One calibration point cannot set rungs over
`P/B − justified P/B`. To arm the bank lens I would want a handful of banks spanning the
quality range (a high-ROE trust bank, a low-ROE regional, ideally one below book). That is a
universe decision. **Recommendation: rule the ladder only after that set exists; bank stays
unarmed.**

---

## 4. Standard-lens tripwire (per ruling)

The standard lens is armed with the tripwire on record: **the first production evaluation that
scores through the standard lens is reported with its full panel readout before its result is
treated as validated.** No golden ticker is natively standard-lens, so that first live case is
the only real evidence the mapping will ever have had. Recorded in CLAUDE.md so it survives a
container wipe.
