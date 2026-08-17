# L-1b — LIFECYCLE CLASSIFIER, LIVE DARK RUN REPORT

**Order:** `docs/orders/2026-08-16-phase-l-lifecycle-classifier.md` (complete, rulings R1–R11)
**Run date:** 2026-08-17 · **Commit:** L-1b `3ccad0b` · **Record:** `docs/l1b-dark-run.json`
**Stop-and-report boundary:** order §9, "after §3 classifier (dark run review)".
**NOTHING IN §5 IS ARMED.** The classifier is not imported by `core/pillars.py`,
`core/valuation_anchors.py`, `batch/runner.py`, `evaluate.py` or `synthesis/schema.py` —
pinned by `test_nothing_in_the_scoring_pipeline_reads_the_classifier_yet`.

## 0. Run conditions

| | |
|---|---|
| Universe | golden five (MU GOOG V NOW WU) + four calibration banks (JPM BK USB C) |
| Dividends | **LIVE** FMP `dividends?symbol=X&limit=8`, per Vic's ruling |
| Income / EDGAR | fixtures — `income_annual` is the L-1a 10-row splice; EDGAR share series from `tests/fixtures/edgar` |
| Series | `fundamental_series` read **read-only** from production `caliber.db` (`mode=ro`) |
| Destination | `caliber-l-dark-2026-08-17.db` (named per R10; gitignored by `*.db`) |
| Suite | **740** (682 + 58) |
| **production caliber.db md5** | **e13cbee6f204da1f117beca193e5b7df before AND after — VERIFIED UNCHANGED** |
| Dark db contents | 9 stage rows · 0 transitions (first classification is never a transition) · 0 overrides |

## 1. Verdict table

| Ticker | Lens | Stage | Rule | Decisive legs (measured) |
|---|---|---|---|---|
| **MU** | cyclical | **MATURE** | rule4 residual | streak **0** (FY2025 rose); guard: latest 37,378M vs prior peak 30,758M → NOT lower, 10 FY; margin −514bp; CAGR 6.71%/y |
| **GOOG** | compounder | **MATURE** | rule4 residual | streak 0; margin **+557bp** (fails flat/down); CAGR 12.51%/y (under 15%); sales/capital 1.195 HEAVY |
| **V** | compounder | **MATURE** | rule4 residual | streak 0; margin −420bp; CAGR 10.92%/y; FCF + reinvestment **asserted-absent** |
| **NOW** | growth | **HIGROWTH** | rule3 | CAGR **22.38%**/y; dividends **[] = pays none**; buyback none; reinvestment absent (1-point series) |
| **WU** | compounder | **DECLINE** | rule1 | streak **4** consecutive down FY; margin **−37bp** (inside ±100bp); dividend **paid** + net buyback |
| **JPM** | bank | **MATURE** | rule4 residual | streak 0; margin −406bp; CAGR 22.06%/y; dividend paid |
| **BK** | bank | **MATURE** | rule4 residual | streak 0; margin −12bp; CAGR 26.88%/y; dividend paid |
| **USB** | bank | **MATURE** | rule4 residual | streak 0; margin −444bp; CAGR 16.08%/y; dividend paid |
| **C** | bank | **MATURE** | rule4 residual | streak **1**; margin −698bp; CAGR 18.86%/y; dividend paid |

**§7's expectations are met on all five golden names:** MU MATURE (cyclical guard case),
GOOG MATURE, V MATURE, NOW HIGROWTH, **WU DECLINE** — the verdict R11 settled and R8
predicted, reached on measured data with every leg present and no `inputs_incomplete`.

Flags: `REINVESTMENT-THRESHOLD-UNCALIBRATED` on MU and GOOG (the only names whose
reinvestment leg is measurable). `INPUTS-INCOMPLETE` on V and all four banks.
**No ticker classified YOUNG.**

## 2. Delta vs the offline probe — one name moved, cause identified

Offline (fixture dividends → `None` → UNKNOWN) vs live. **No stage changed.**

| Ticker | Change | Cause |
|---|---|---|
| **V** | `capital_returns` **absent → measured (True)**; `absent_legs` 3 → 2 | Fixtures carry no `dividends` key, so offline V had *both* witnesses absent (no share series either). Live V returns 8 dividend records. |
| MU GOOG NOW WU | identical stage, flags, absent legs | — |

**One change the composite leg HID, and it is worth naming.** Offline, WU's DECLINE rested
on the **buyback leg alone** (dividends UNKNOWN). Live, the leg reads
`pays_dividend=True; net_buyback=True`. `absent_legs` is empty in *both* runs because the
composite `capital_returns` leg is "present" as soon as **one** witness is — so the
strengthening of the evidence under WU's most consequential classification is visible
**only in the per-point assertion detail**, not in the flags or the absence record. The
per-point trail is doing the work §2 asked it to do; the composite summary alone would not
have shown it.

**The G-4 contract earned its keep in live data, on NOW.** `dividends` returned `[]` — a
real "pays none" — which is what makes rule 3's returns-absent leg pass and lets NOW
classify HIGROWTH at all. Had `[]` and `None` been collapsed, NOW would have fallen to
MATURE on a fetch artifact.

## 3. FINDING 1 — the cyclical guard is semantically wrong. **NEEDS A RULING.**

Reported in the L-1b commit and pinned as-built. §3 rule 1 requires "through-cycle
**peak-to-peak** revenue lower". The leg as built compares the **latest revenue** to the
prior peak. These are different measurements, and the difference is not academic:

> A declining latest year is **by construction** below the prior peak. So the leg returns
> `LOWER = True` for **every** cyclical name that has a decline streak — i.e. it is vacuous
> in exactly the situation it gates.

Measured on a synthetic cycle whose successive **peaks** are 2018=700 → 2022=1100 (RISING,
which the order calls "not lower" and which should hold the name out of DECLINE): the
as-built leg says LOWER and **DECLINE fires**. Pinned in
`test_cyclical_guard_AS_BUILT_compares_latest_to_prior_peak_NOT_peak_to_peak`.

**MU is held out of DECLINE today by its STREAK (0 — FY2025 rose), not by the guard.** The
order file's "held out twice over" reading credits the guard with a check it did not
perform. Had this run happened mid-downcycle (FY2023: peak 2022 30,758M → 15,540M), the
as-built guard would have said LOWER and permitted DECLINE — the MU-type misclassification
the guard exists to prevent.

**Not fixed, deliberately.** A correct peak-to-peak needs a *peak-detection definition*
(what separates a cycle peak from a wiggle — a trough depth threshold, a minimum
separation, or a named window). That is a design decision, so it is Vic's to rule and not
Code's to invent. The test flips when the ruling lands.

## 4. FINDING 2 — the bank revenue basis makes the CAGR leg meaningless for banks, and one dividend cut flips all four to HIGROWTH. **NEEDS A RULING.**

All four banks post a 3y revenue CAGR **above the 15% HIGROWTH bar** (JPM 22.06%, BK
26.88%, C 18.86%, USB 16.08%). That is not growth — it is the rate cycle inflating a
**gross** line. Measured on JPM's latest FY:

```
revenue            279.7B      <- what the CAGR leg consumes
interestIncome     193.3B      <- GROSS of interest expense
netInterestIncome   95.4B
implied net-revenue basis ~= 181.8B     (revenue - interestIncome + netInterestIncome)
```

JPM `revenue` 2022 153.8B → 2025 279.7B is largely gross interest income repricing, while
net income went 37.7B → 57.0B. **This is the same defect class as the D/E units bug and the
FMP-net-vs-EDGAR-gross debt mismatch: a number that is measurable, but not the measure the
rule intends.**

**Why the banks nonetheless read MATURE — and why that is luck, not correctness.** They
fail rule 3 on one leg only: they pay dividends, so "capital returns absent" is False.
Their reinvestment leg is structurally absent (no `sales_to_capital` series), so under
remaining-legs the rule evaluates on **CAGR + capital-returns alone**. Measured
counterfactual on JPM's real income series with the dividend suspended:

| JPM | Stage |
|---|---|
| pays dividend (actual) | MATURE |
| **dividend suspended (`[]`)** | **HIGROWTH** |

**A bank that cuts its dividend in a crisis classifies HIGROWTH.** That is the worst
available failure mode, it is reachable on one input change, and §5.2 exempts the bank lens
from stage/lens compatibility flags — so nothing would flag it. The stage still feeds Phase
M's width priors, so it is not inert.

**The symmetric risk:** rates fall → gross interest income falls → two consecutive
declining "revenue" years, margins already trending down on all four (−12bp to −698bp),
dividends paid → **rule 1 fires and all four banks classify DECLINE simultaneously.** C is
already at streak 1.

Options, for Vic (Code proposes, does not choose): (a) route bank revenue to a net-revenue
basis — computable from the existing payload as `revenue − interestIncome +
netInterestIncome`, no new feed; (b) assert the revenue-derived legs absent for the bank
lens and let banks classify on the remaining legs, stamped `inputs_incomplete`; (c) accept
as-is and record the exposure.

## 5. R6 — the reinvestment default, for your ruling

R6 struck "top-half of sector" and directed Code to propose an **absolute** threshold on
sales-to-capital at dark-run review. **Proposed default: `1.50`.** Measured FY series
(production `fundamental_series`, read-only):

| Ticker | FY sales-to-capital | Read at 1.50 |
|---|---|---|
| MU | 0.575 0.669 0.659 0.332 0.515 **0.668** | HEAVY |
| GOOG | 2.032 2.241 1.659 1.450 **1.195** | HEAVY |
| WU | 2.673 2.726 3.203 1.722 **1.553** | light |
| NOW | **1.625** (single point) | asserted-absent per R6 |
| V, all banks | *(no series)* | asserted-absent |

Lower sales-to-capital means **heavier** reinvestment, so "heavy" is `<= threshold`. At 1.50
the capital-hungry names (MU, GOOG) sit on the heavy side and asset-light WU on the light
side, which matches the businesses.

**FOUR TICKERS IS NOT A CALIBRATION.** This is a reasoned default, and every reading that
consults it carries `REINVESTMENT-THRESHOLD-UNCALIBRATED` — deliberately, on the
BANK-RUNG-UNCALIBRATED precedent. Note WU crossed from 3.203 to 1.553 in two years and sits
**0.053 above the bar**; a small move reclassifies its reinvestment leg. WU is currently
DECLINE via rule 1, so the leg is not load-bearing for it today.

## 6. Coverage and the YOUNG tripwire

- **FCF leg (R2):** present for MU/GOOG/NOW/WU; asserted-absent `no_fcf_series` for V and
  all four banks — exactly as R2 anticipated. No bank or V is in `fundamental_series`.
- **Reinvestment (R6):** measurable for MU/GOOG/WU only; NOW single-point; V/banks absent.
- **Cyclical guard:** evaluable (10 FY ≥ `CYCLICAL_MIN_FY` = 8) — MU is the only cyclical name.
- **YOUNG never fired.** No name in the universe classifies YOUNG, so §5.3's supply-layer
  block and the 30% B-2 tolerance would arm on **synthetic evidence only**. R10's
  `YOUNG-UNCALIBRATED` tripwire is therefore confirmed necessary, not precautionary: the
  flag is already emitted on every YOUNG path (both the rule-2 and insufficient-history
  returns) so the first live YOUNG classification reports loudly before its
  stage-conditioned behaviours are trusted.

## 7. What L-1b changed, and what it did not

Suite **682 → 740**. Two latent defects fixed in the adopted build (`note_absent` never
deduped; the insufficient-history return omitted absence reasons — the second verified by
mutation to actually bite). Gate tests verified non-decorative by mutation: removing the
gap-break, equalising the cyclical streak bar, and dropping DECLINE's all-legs-present
requirement each fail a named test.

**No production write. No score, E(R), grade, confidence label or lens moved — none can:
nothing reads the classifier.**

## 8. Open for ruling

1. **The cyclical guard** (§3) — peak-detection definition, or accept the as-built latest-vs-prior-peak semantic. §4 above.
2. **Bank revenue basis** (§4 above) — net-revenue derivation, assert-absent for the bank lens, or accept the exposure.
3. **R6 reinvestment default `1.50`** — ratify, retune, or defer.
4. **§5 arming order** — nothing arms without a ruling, one behaviour at a time per §7/§9.
