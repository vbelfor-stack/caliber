# L-1d — DARK TABLE UNDER PEAK-TO-PEAK CYCLICAL SEMANTICS

**Order:** L-1d ruling 2026-08-17 · **Commits:** `32b82c3` + `c87815a` (both pushed)
**Record:** `docs/l1d-dark-run.json` · **Prior runs:** `docs/l1c-dark-run.md`, `docs/l1b-dark-run.md`
**Suite:** 752 → **761** · **Destination:** `caliber-l1d-dark-2026-08-17.db` (fresh, 9 stage rows, 0 transitions)
**production caliber.db md5 `e13cbee6f204da1f117beca193e5b7df` — verified unchanged before AND after.**
**§5 NOT ARMED. No wiring into `batch/` or `evaluate.py`.**

## 1. Verdict table

| Ticker | Lens | Stage | Rule | Cyclical legs / decisive evidence |
|---|---|---|---|---|
| **MU** | cyclical | MATURE | rule4 | peaks **2018 30,391M → 2022 30,758M (+1.21%)**; guard does not fire (streak 0); *earned in 2022, 2024, 2025* |
| GOOG | compounder | MATURE | rule4 | margin +557bp fails flat/down; CAGR 12.51% |
| V | compounder | MATURE | rule4 | FCF + reinvestment absent |
| NOW | growth | HIGROWTH | rule3 | CAGR 22.38%; dividends `[]` = pays none |
| WU | compounder | **DECLINE** | rule1 | streak 4; margin −37bp; dividend + buyback |
| JPM | bank | MATURE | rule4 | net-basis CAGR 12.50% |
| BK | bank | MATURE | rule4 | net-basis CAGR 6.87% |
| USB | bank | MATURE | rule4 | net-basis CAGR 5.68% |
| C | bank | MATURE | rule4 | net-basis CAGR 4.60% |

**All nine stages identical to L-1c and L-1b.** Three successive cyclical definitions and a
bank-basis change have moved **zero** live verdicts — because MU is the only cyclical name
and its streak is 0, so the guard is not on MU's critical path today. That is worth stating
plainly: **the live table does not exercise the guard, and never has.** The evidence that
the guard works is the harness and the synthetic tests, not this table.

MU's peak pair is now logged and persisted: `['2018:30,391,000,000', '2022:30,758,000,000']`,
delta **+1.21%**. Peaks are RISING, so had MU carried a 3-year streak the guard would have
refused the DECLINE permit — which is the MU-type protection §3 rule 1 was written for,
finally measurable rather than asserted.

## 2. The guard is two-sided at last — ordered harness re-run

Same seed and same generator as the L-1c harness, so the comparison is like-for-like:

| | L-1c (pre-streak peak) | **L-1d (peak-to-peak)** |
|---|---|---|
| series with a streak | 9,989 | 9,990 |
| guard compared two peaks | 9,989 | **9,966** |
| → **PERMIT** (peaks falling) | 9,989 (100%) | **4,648 (46.6%)** |
| → **REFUSE** (peaks rising) | **0 (0%)** | **5,318 (53.4%)** |
| gate refused (<2 local peaks) | — | 23 |
| asserted-absent | 1 | 1 |

Neither all-permit nor all-refuse, so by the ruling's own test the definition holds. The
~47/53 split is what a random walk should give: whether the later cycle top is above or
below the earlier one is close to a coin flip on noise, and the guard now reads that
difference instead of ignoring it.

`test_the_guard_can_both_permit_and_refuse_so_it_is_not_vacuous` now exists specifically to
catch a fourth one-sided definition — one-sidedness is the failure mode that survived two
rulings unnoticed, and it deserves a permanent tripwire rather than another report.

## 3. MU FY2023 counterfactual under both fixes — reads MATURE

Ordered pin 2a, measured on MU's own filed series truncated at FY2023 (revenue 30,758M →
15,540M, operating margin −36.97%, FCF −6,117M):

| Step | Measured | Effect |
|---|---|---|
| decline streak | **1** — under the cyclical bar of 3 | rule 1 blocked |
| peak-to-peak | **2018 30,391M → 2022 30,758M, RISING** | rule 1 blocked **again**, and this time the guard performed a real check |
| rule 2 cyclical guard | **earned in 2020, 2021, 2022** (positive margin AND positive FCF) | **YOUNG BLOCKED** → `CYCLICAL-GUARD-HELD-OUT-OF-YOUNG` |
| revenue CAGR 2020→2023 | negative | rule 3 cannot fire |
| **stage** | **MATURE** (`rule4_mature`) | |

Your expectation was MATURE via streak-1-blocks-DECLINE, and that holds — but it is now
belt-and-braces: the streak blocks rule 1 *and* the guard independently refuses. The
YOUNG misclassification is closed at the rule that caused it, not routed around.

Ordered pin 2b also passes: a synthetic cyclical with no profitable FY in the window
(negative margins and negative FCF throughout) still reaches YOUNG with
`YOUNG-UNCALIBRATED` and no block. The guard blocks troughs, not pre-earnings names.

## 4. Two limits recorded, neither patched

**(a) Rule 2's guard needs an FCF series.** Establishing "has earned" requires a margin AND
an FCF reading; with no FCF series the block cannot be established, so YOUNG stays reachable
(R1's direction — a missing input never satisfies a condition, including one that blocks).
**V and every bank have no FCF series.** No cyclical-lens name lacks one today (MU is the
only cyclical and it has one), so this is latent, not live. Pinned by
`test_the_rule2_guard_needs_an_FCF_series_and_says_so_when_it_has_none`.

**(b) Peak adjacency is series-adjacency, not year-adjacency.** If a fiscal year were
missing, the "adjacent" FY used for peak detection would not be year-adjacent. No gap exists
in FMP `income_annual` for any of the nine (FY2016–2025 contiguous, measured at L-1a), so
this is latent. Recorded rather than resolved because gap semantics for peak detection is a
ruling, not a detail.

## 5. Follow-up correction inside L-1d, disclosed

The peak leg was first built only in the branches where the guard reaches a comparison. MU's
guard does not fire, so **the first L-1d dark run carried no peak data at all** — the
calibration set the ruling asked for would have been empty. Fixed in `c87815a`: peaks are
computed once per cyclical evaluation and logged regardless of whether the guard fires. The
table above is from the re-run after that fix, and the persisted value is verified in
`lifecycle_stage.inputs_json`.

## 6. State

Suite **761**, all green. Three commits this session, all pushed, `unpushed = 0`. Production
`caliber.db` untouched throughout Phase L (md5 `e13cbee6` since 2026-08-15).

Order file amended in strike-through style: §3 rule 1 carries the peak-to-peak definition
with the harness numbers and the magnitude-bar rejection rationale, the L-1c note is struck
as superseded, and rule 2 carries the cyclical-guard text with its window reading and FCF
reach limit.

**Open for you:** §5 arming order. Nothing arms until you say the cyclical semantics are
believable. `REINVESTMENT-THRESHOLD-UNCALIBRATED` and `GUARD-TOLERANCE-UNCALIBRATED` both
remain on every reading that consults their thresholds, and full-universe calibration of
both sits on the Phase L punch list in CLAUDE.md.
