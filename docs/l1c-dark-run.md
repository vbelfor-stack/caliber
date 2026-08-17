# L-1c — CORRECTED DARK TABLE (ruled guard definition + bank net-revenue basis)

**Order:** L-1c ruling 2026-08-17, amending `docs/orders/2026-08-16-phase-l-lifecycle-classifier.md`
**Commit:** `58b7196` (pushed) · **Record:** `docs/l1c-dark-run.json` · **Prior run:** `docs/l1b-dark-run.md`
**Suite:** 740 → **752** · **Destination:** `caliber-l1c-dark-2026-08-17.db` (fresh, 9 stage rows, 0 transitions)
**production caliber.db md5 `e13cbee6f204da1f117beca193e5b7df` — verified unchanged before AND after.**
**§5 NOT ARMED. No wiring into `batch/` or `evaluate.py`.**

## 1. Corrected verdict table

| Ticker | Lens | Stage | Rule | 3y CAGR (net basis for banks) | Decisive leg |
|---|---|---|---|---|---|
| MU | cyclical | MATURE | rule4 | 6.71%/y | streak 0 — guard does not fire |
| GOOG | compounder | MATURE | rule4 | 12.51%/y | margin +557bp fails flat/down |
| V | compounder | MATURE | rule4 | 10.92%/y | FCF + reinvestment absent |
| NOW | growth | **HIGROWTH** | rule3 | **22.38%/y** | dividends `[]` = pays none |
| WU | compounder | **DECLINE** | rule1 | — | streak 4, margin −37bp, returns present |
| JPM | bank | MATURE | rule4 | **12.50%/y** *(was 22.06% gross)* | CAGR now under the bar |
| BK | bank | MATURE | rule4 | **6.87%/y** *(was 26.88%)* | CAGR now under the bar |
| USB | bank | MATURE | rule4 | **5.68%/y** *(was 16.08%)* | CAGR now under the bar |
| C | bank | MATURE | rule4 | **4.60%/y** *(was 18.86%)* | CAGR now under the bar |

**No stage moved from L-1b — all nine identical.** That is the headline and it needs stating
carefully: **the verdicts did not change, but the reasons did.** Before, the banks avoided
HIGROWTH only because they pay dividends; now they avoid it because they are not growing.
The right answer for the right reason, and the failure mode is closed.

## 2. What the bank basis actually changed

| Bank | 3y CAGR | Decline streak | Margin trend |
|---|---|---|---|
| JPM | 22.06% → **12.50%** | 0 → 0 | −406bp → **+378bp** |
| BK | 26.88% → **6.87%** | 0 → 0 | −12bp → **+1422bp** |
| USB | 16.08% → **5.68%** | 0 → 0 | −444bp → **+316bp** |
| C | 18.86% → **4.60%** | **1 → 0** | −698bp → **−199bp** |

Three things worth your eye:

1. **All four dropped below the 15% HIGROWTH bar** — the gross basis had every one of them
   reading as a high-growth business.
2. **Every bank's margin trend flipped from falling to rising** (except C, whose decline
   narrowed from −698bp to −199bp). On the gross basis the "margin" was operating income
   over gross interest income, which *falls* when rates rise regardless of performance. All
   four were one leg away from satisfying DECLINE's margin condition on an artifact.
3. **C's decline streak went 1 → 0.** On gross revenue C had already started "declining".
   The symmetric risk flagged in L-1b — a rate-cut cycle marching all four banks into
   DECLINE together — **is closed at the source**, not merely made less likely.

**Golden five: every leg byte-identical to L-1b** (CAGR, streak, margin trend, capital
returns). The bank basis is correctly scoped to the bank lens and touched nothing else.

**The pinning test the ruling asked for passes:** JPM with its dividend suspended no longer
classifies HIGROWTH — it classifies MATURE. The one-input-away crisis failure is gone.

## 3. THE GUARD RULING IS IMPLEMENTED AND STILL CANNOT REFUSE — reported, not patched

The ruled definition is in force: prior peak = max(FY revenue) over all FYs strictly before
the decline-streak start year; streak 0 → does not fire; streak spanning the window →
asserted-absent with `INPUTS-INCOMPLETE` and no verdict.

**It is still vacuous, and this is now a proof rather than an observation:**

```
let k = streak >= 1, series oldest-first, latest = index n-1
the streak means      rev[n-1] < rev[n-2] < ... < rev[n-k-1]   (adjacent fiscal years)
the pre-streak window is series[0 .. n-k-1], which CONTAINS rev[n-k-1]
so  prior_peak = max(pre-streak) >= rev[n-k-1] > rev[n-1] = latest
therefore  latest < prior_peak   ALWAYS                                            QED
```

Measured to match: **9,989 random cyclical series with a streak and an evaluable guard →
9,989 permits, 0 refusals.**

The cause is that the ruled window includes *the current cycle's own run-up*. The year
immediately before a decline begins is, by definition, a local high — so it is always above
where the decline ends. To refuse anything, the comparator has to exclude the run-up and
reach back to the **previous** cycle's top.

**Consequence in force today: the raised streak bar (3 vs 2) is the only cyclical
protection.** Pinned in `test_the_RULED_guard_still_cannot_refuse_a_streak_REPORTED_UNRESOLVED`.

Options, for your ruling (Code does not pick):

- **(a) Magnitude bar** — smallest change that makes it bite: permit DECLINE only if
  `latest < prior_peak × (1 − X)`. One number, no cycle segmentation. Turns "has it
  declined" into "has it declined *materially*".
- **(b) Prior-cycle peak** — walk back past the run-up: find the trough preceding the
  streak, take the max of FYs before *that*. Needs a trough definition.
- **(c) Local-peak detection** — compare the last two local peaks, where a peak is a year
  above all years within ±W. Needs W.
- **(d) Drop the guard** and rely on the streak bar alone, recording that the cyclical
  protection is a streak length and nothing more.

## 4. ORDERED MU FY2023 COUNTERFACTUAL — the answer is YOUNG, not DECLINE

Ruling: "If it permits DECLINE, report that as a fact — do NOT patch it away." Measured on
MU's own filed series truncated at FY2023 (revenue 30,758M → 15,540M, 8 FY, guard evaluable):

| Leg | Measured |
|---|---|
| decline streak | **1** (FY2023 only) — under the cyclical bar of 3 |
| cyclical guard | **PERMITS** — latest 15,540M < pre-streak peak 30,758M @ FY2022 |
| margin trend | −5,098bp (14.01% → **−36.97%**) |
| capital returns | dividend paid |
| **stage** | **YOUNG** (`rule2_young`), flag `YOUNG-UNCALIBRATED` |

**So the guard permits, but rule 1 cannot fire anyway on the streak — and the classification
is neither DECLINE nor MATURE. MU classifies YOUNG.**

FY2023 operating margin was −36.97% and FCF −6,117M, and **rule 2 has no cyclical guard at
all**. A cyclical trough produces negative margins and negative FCF by nature, so
`YOUNG / Pre-earnings` is what a 1978-vintage memory maker reads mid-downcycle. Under §5
that would attract the widest distribution prior, the 30% anchor-divergence tolerance, and a
mandatory supply-layer block on lockup dates and insider overhang.

`YOUNG-UNCALIBRATED` fires, which is exactly the net R10 put there — the tripwire works.

**Not patched.** A cyclical guard on rule 2 is a rule change, so it is yours. If you want
one, the natural shape mirrors rule 1: for a cyclical-lens name, a negative margin or
negative FCF in a trough year does not establish YOUNG unless it persists across a
through-cycle window. Pinned meanwhile in
`test_MU_mid_downcycle_classifies_YOUNG_on_real_filed_data_REPORTED`.

## 5. R6 and the punch list

`REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL` stays at **1.50**; every reading that consults it
still carries `REINVESTMENT-THRESHOLD-UNCALIBRATED` (MU and GOOG in this run). Full-universe
calibration is on the Phase L punch list in CLAUDE.md, deferred until after §5 arms. No
tuning was done on the four-name sample.

Dedupe test left as a latent guard per the ruling — no rule was manufactured to exercise it.

## 6. Open for ruling

1. **The cyclical guard** — options (a)–(d) in §3. It is implemented as ruled and provably cannot refuse.
2. **Rule 2 has no cyclical guard** — MU reads YOUNG at a trough (§4). New finding, this run.
3. **§5 arming order** — nothing arms until you review this table.
