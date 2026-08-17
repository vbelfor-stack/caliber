# L-1e — GUARD PRECONDITIONS, AND THE ARMING-ORDER ARGUMENT

**Order:** L-1e ruling 2026-08-17 · **Commit:** `9b58d39` (pushed) · **Suite:** 761 → **764**
**production caliber.db md5 `e13cbee6f204da1f117beca193e5b7df` — unchanged.**
**No dark run, as ordered.** §5 unarmed, no wiring into `batch/` or `evaluate.py`.

## 1. Both preconditions built, and the symmetry is explicit

| Gate | Cannot measure when | Denies | Reason recorded |
|---|---|---|---|
| peak-to-peak | fewer than two local peaks, **or any missing FY in the window** | **DECLINE** | `PEAK-GUARD-SERIES-GAP` |
| rule 2 "has earned" | **no FCF series** | **YOUNG** | `CYCLICAL-GUARD-UNEVALUABLE-FCF-ABSENT` |

Each gate denies the tag it guards. Neither grants a classification on evidence it could not
gather. Peaks are **not computed at all** on a gapped series, so fabricated structure cannot
reach the tolerance calibration set either — the refusal names feed repair as the remedy.

**Recorded as a deliberate departure from R1.** R1 says a missing input never satisfies a
condition. Here the condition *blocks*, so absence now **denies** a tag rather than
permitting one. That inversion is written into the code, the order file and CLAUDE.md so it
is not later read as an inconsistency.

## 2. "Nothing live changes" — measured, not reasoned

The ruling said to assert this rather than re-run. The assertion rests on two measurements:

| Ticker | Lens | FY span | Gaps | FY FCF points |
|---|---|---|---|---|
| MU | **cyclical** | 2016–2025 | none | **6** |
| GOOG | compounder | 2016–2025 | none | 6 |
| V | compounder | 2016–2025 | none | 0 |
| NOW | growth | 2016–2025 | none | 6 |
| WU | compounder | 2016–2025 | none | 6 |
| JPM · BK · USB · C | bank | 2016–2025 | none | 0 |

- **No gaps anywhere** → the `PEAK-GUARD-SERIES-GAP` branch is unreachable.
- **MU is the only cyclical-lens name and it has 6 FCF points** → the unevaluable-FCF branch
  is unreachable. V and the four banks have 0 FCF points, but **none of them is cyclical**,
  and the guard is scoped to the cyclical lens.

So MU's peak pair (2018 30,391M → 2022 30,758M) and all nine verdicts are unchanged **by
construction**: MU/GOOG/V MATURE, NOW HIGROWTH, WU DECLINE, four banks MATURE.

---

# 3. The arming order — three dependencies it breaks, one label, one tension

Taking up the invitation to argue. **The sequence itself is right** — annotation before
tolerance, calibration data before any threshold is consulted, hard-block last. I would not
reorder it. But four things need settling before step 1, and one of them changes what step 1
*is*.

## 3a. THE REAL ONE — "read-only annotation" and "builds the calibration set" cannot both be true

Step 1 is described as a read-only annotation with zero scoring effect, and also as the thing
where *"every run I do builds the calibration set for both uncalibrated thresholds."*

Those are in direct tension. A calibration set only accumulates if the stage row is
**persisted**. A read-only annotation prints a tag and forgets it. So step 1 is one of:

- **(a) Annotate only.** Zero blast radius, genuinely read-only — and **no calibration data
  accrues.** Both uncalibrated thresholds stay uncalibrated until the step-2 full-universe
  run, which is a single snapshot rather than an accumulating set.
- **(b) Annotate and persist.** Calibration accrues per run — but this is **a production
  write from the interactive path**, which needs the expected-delta discipline (`lifecycle_stage`
  +1 row per eval, `lifecycle_transitions` +1 when a stage moves, `sqlite_sequence` on first
  creation) and is no longer "zero blast radius" in the sense the step-1 framing implies.

I recommend **(b), stated as a write**, because (a) makes the phrase "every run builds the
calibration set" false and you would discover that only when the tolerance was still
uncalibrated three steps later. But it is your call, and it needs to be made *before* step 1
rather than inside it.

**A related defect this exposes, found while checking.** `save_lifecycle_stage`'s docstring
claims it "takes an explicit db_path from its caller: this is a writer, so the destination is
named rather than defaulted" — **but its signature is `db_path: Path = _DEFAULT_DB`, i.e. it
defaults to production caliber.db.** The claim is currently harmless because the only caller
is the probe, which requires `--db-path`. **Step 1(b) is exactly when it stops being
harmless**: an annotation that forgets to name a destination would write to production
silently. Recommend making `db_path` required on that writer, or wiring the
`DegradedRunWriteRefused` guard to it, as part of step 1. Not fixed in L-1e — out of order
scope.

## 3b. Step 1 flips a five-file pin, and four of those files should stay pinned

`test_nothing_in_the_scoring_pipeline_reads_the_classifier_yet` asserts in **one test** that
`core/pillars.py`, `core/valuation_anchors.py`, `batch/runner.py`, `evaluate.py` and
`synthesis/schema.py` all avoid the classifier. Arming step 1 touches `evaluate.py` — which
means the whole pin must be deleted or edited, **retiring the protection on the other four in
the same stroke.**

That is the "eleven-test silent dependency" shape from 2026-08-15: a protection retired as a
side effect of a change that only needed part of it. **Recommend splitting the pin per file
before step 1**, so arming `evaluate.py` flips exactly one assertion and the other four keep
failing loudly if anything reaches for the classifier. Cheap, and it keeps each arming step's
blast radius legible.

## 3c. Step 1 puts the stage tag behind an EDGAR dependency

Computing a stage needs the buyback leg, which comes from `instant_series(edgar.financials,
'shares_outstanding')` — and the FCF / sales-to-capital legs, which come from
`fundamental_series` in caliber.db. `evaluate.py` already calls `fetch_edgar` (2 sites), so
EDGAR is not new to the path, but the **stage tag** would newly depend on it.

Consequence to expect rather than discover: **when EDGAR 403s — and reachability is
intermittent by the 2026-08-15 re-ruling — the stage tag degrades to `INPUTS-INCOMPLETE`**,
because the buyback witness vanishes and `capital_returns` may fall to dividends alone. That
is honest behaviour, not a defect, but a run showing `INPUTS-INCOMPLETE` on names that read
clean in the dark table should not be mistaken for a classifier regression. Same for offline
or fixture runs, where `fundamental_series` may be absent entirely.

## 3d. The label is B-2, not B-1 — again

Step 3 is written as "B-1 stage-conditioned tolerances (15/20/30)". **R10 already ruled this
guard is B-2**, corrected the order's §5.1 authoring error, and the config key is
`B2_DIVERGENCE_TOLERANCE_BY_STAGE`. B-1 was the status-semantics work. Flagging because the
label has now slipped twice, and the code and config are already B-2 — if the arming ruling
says "B-1" the mismatch propagates into the commit trail.

Also, small: the sequence text says the full-universe run *"happens between steps 1 and 2"*
while itself being step 2. I read the intent as **step 1 → full-universe run → tolerances →
supply-layer block**, which is what I have planned against.

## 3e. One expectation worth lowering now: the tolerance may stay uncalibrated

`GUARD-TOLERANCE-UNCALIBRATED` calibrates against **real refusals** — cases where two peaks
were compared and the later was not lower. That requires a cyclical-lens name **with a
decline streak**. MU has streak 0, and it is the only cyclical name in the current nine.

So a ~20-name full-universe run may well produce **zero** peak comparisons and therefore zero
calibration data. That is not a failure of step 2; it means the guard's tolerance is
calibratable only when a cyclical name actually enters a downcycle, which could be quarters
away. Worth deciding now whether the tolerance stays flagged indefinitely (my recommendation
— the flag is doing its job) or whether a synthetic calibration is acceptable.

## 4. Summary of what I would settle before step 1

1. **Rule 3a**: annotate-only or annotate-and-persist. If persist, name the destination and the expected-delta set.
2. **Approve the pin split** (3b) as step-0 housekeeping.
3. **Note the EDGAR/series degradation** (3c) so `INPUTS-INCOMPLETE` in live annotation isn't misread.
4. **Confirm the guard is called B-2** (3d).
5. **Optionally fix `save_lifecycle_stage`'s db_path default** (3a) — the docstring already claims the behaviour the signature lacks.

Nothing above changes the order of your four steps. Awaiting the arming ruling.
