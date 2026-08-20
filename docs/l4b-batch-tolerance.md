# L-4b — BATCH TOLERANCE ARMING

**Session 2026-08-20. Order: "batch tolerance arming" (L-4b of the 2026-08-17 close order).
Status: LANDED AND ARMED, on Vic's ruling of 2026-08-20.**

`caliber.db` md5 `8557a157ee92e22df01cfe04cb1e1d55` at open **and at close — UNCHANGED.
THIS ORDER WROTE NOTHING TO PRODUCTION.** It is a code-path arming; no evaluation, stage,
provenance or cache row was created, altered or removed. Every verification run below was
directed at a scratch database and the md5 was re-read after each one.

---

## 1. WHAT WAS WRONG

Since L-3 (2026-08-17) the two write paths disagreed about the B-2 anchor-divergence
tolerance:

| path | band used | source |
|---|---|---|
| `evaluate.py` | stage-conditioned — YOUNG 30 / HIGROWTH 20 / MATURE 15 / DECLINE 15 | `core.stage_tolerance.tolerance_for()` |
| `batch/runner.py` | **flat 15%** | `synthesis.schema.ANCHOR_DIVERGENCE_THRESHOLD` default |

The same ticker, with the same synthesis and the same price, could therefore receive a
**different verdict depending on which entry point produced it** — `ok` with an E(R) from
one path, `anchor_divergence` with E(R) withheld from the other. That is a defect class in
its own right, independent of which band is correct: a guard whose strictness depends on how
the run was launched is not a guard on the issuer, it is a guard on the operator's habits.

## 2. THE RULING (Vic, 2026-08-20)

Arm now on the existing stage-conditioned set. Two codicils, both recorded below and both
carried in code rather than prose.

> Rationale for arming rather than clamping batch to flat 15: the stage-conditioned set is
> already armed on the interactive path per §5 step 3 — clamping batch to flat 15 creates
> per-path tolerance divergence (same name, different verdict by entry point), which is its
> own defect class. Monotone-widening + empty dark diff + path consistency carries it.

The B-2 band values themselves were **not re-derived**. The L-4a finding that the calibration
population is contaminated (68 defect-tagged rows) bears on *whether 30/20/15 are the right
numbers* — that question is already-shipped state on the interactive path and is **not**
reopened here. L-4b changes no number; it removes an inconsistency.

## 3. WHAT LANDED

**`batch/runner.py`**
- Imports `tolerance_for`, `DEFAULT_TOLERANCE`, `suppressed_by_widening`.
- Calls `tolerance_for(ticker, db_path or _DEFAULT_DB)` — **the DESTINATION db, never
  unconditionally production.** A `--db-path` run finds no stage rows and every name falls to
  the DEFAULT band. Fail-closed, and it forecloses the inverse-contamination shape where an
  isolated run borrows production's classifications to widen its own tolerance.
- Passes `threshold=_tol.tolerance` into `check_anchor`, and logs the band with its reason.
- **`ANCHOR_DIVERGENCE_THRESHOLD` is no longer imported at all.** An unused import of the
  flat value is how a path quietly drifts back onto the behaviour an order just removed; the
  removal is pinned.

**`core/stage_tolerance.py`** — new pure predicate `suppressed_by_widening(divergence,
tolerance)`: true exactly when the stage widening is the *only* reason a divergence did not
trip, i.e. `DEFAULT_TOLERANCE < divergence <= tolerance`. Defined here, not in the batch
runner, so the interactive path can adopt the same tripwire in one line under its own order.

**Pins.** `tests/test_l4b_batch_tolerance.py`, 19 tests. Suite **853 → 871**
(−1 retired pin, +19 new). No pre-existing test broke.

## 4. THE PIN THAT WAS RETIRED, AND WHERE ITS PROTECTION WENT

`tests/test_lifecycle.py::test_batch_runner_does_not_read_the_classifier` — **retired by
name.** It asserted "the batch path stays dark until its own arming order"; this is that
order. It was removed rather than weakened in place, and its *surviving* half — batch may
never touch the classifier or the raw stage table, only the derived band — is re-asserted in
two places (`test_batch_reads_the_band_and_never_the_classifier`, and the widened L-3
successor pin). Deleting a pin without naming where its remaining protection went is the
2026-08-15 eleven-test silent-dependency shape.

`test_the_tolerance_lookup_is_the_ONLY_scoring_path_consumer_of_stage` was **widened, not
weakened**: it now admits `batch/runner.py` as the second *write path* making the *same one*
decision, and still fails on a third call site or on any call site in a non-write-path
module. Two changes were forced out of it in the process, both worth naming:

1. **The classifier/table prohibition is asymmetric and deliberately so.** `evaluate.py` is
   the ANNOTATOR (§5 step 1 writes the stage row after scoring) and must import both;
   `batch/runner.py` annotates nothing and may learn only the band. The first draft of the
   widening applied the prohibition to both and failed correctly on `evaluate.py`.
2. **The call-site count is now taken over the AST, not the text.** The substring count was
   tripped by a *comment* mentioning `tolerance_for()`. A pin that prose can break is a pin a
   later session weakens instead of heeding.

## 5. DARK VERIFICATION — REVIEWED, NOT ASSERTED

### 5.1 The safety property the arm rests on

`min(B2_DIVERGENCE_TOLERANCE_BY_STAGE.values()) == DEFAULT_TOLERANCE == 0.15`. No stage band
is *tighter* than the flat default, so moving batch onto the stage set **can only ever
suppress a trip, never create one.** Nothing that passes the batch guard today starts failing
it. The risk therefore runs in exactly one direction, which is what makes an empty dark diff
on partial coverage sufficient — and what codicil 2 is pointed at. Pinned by
`test_the_arm_is_monotone_widening`, which fails loudly if any future band drops below 15%.

### 5.2 Band assignment across the live universe (28 names)

18 sit at the default 15%; **10 widen** — ARM, BE, CBRS, LITE, NOW, QBTS, SKHY at 20%;
IONQ, RKLB, SPCX at 30%.

DPC and INFQ read YOUNG but are correctly **denied** the 30% band by the not-a-measurement
rule (`INSUFFICIENT-HISTORY`, one fiscal year each). This matters concretely: INFQ sits
**0.37pp from tripping** at its fail-closed 15% (14.63%). Had the arm handed it 30% it would
have gained ~15pp of headroom on an absence rather than a measurement.

### 5.3 Replay against the eval-date-pinned population

The only population where divergence can be honestly recomputed is `synthesis_cache`, which
carries a same-date `price_snapshot` — 16 rows, 5 tickers. (Per the L-4a ruling 5(b), a
"stored anchor vs live price" comparison is meaningful **only** same-day; re-running it days
later measures price drift, not divergence.)

| | flat 15% | stage-conditioned |
|---|---|---|
| trips | 0 | 0 |
| behaviour deltas | — | **0** |

Divergences ranged 0.11%–8.15%, comfortably inside both bands.

### 5.4 End-to-end exercise of the armed block

`--fixture --no-synthesis` does **not** reach the guard (the anchor block is inside
`if synthesis is not None`), so it verifies nothing about this arm. The armed block was
instead driven directly for NOW (HIGROWTH → 20%), scratch db, real stored synthesis, with the
price chosen to place the divergence in each regime:

| regime | band applied | outcome | tripwire |
|---|---|---|---|
| 6.9% (control) | 20% | `ok`, E(R) −2.18% | silent |
| **18% — widened zone** | 20% | `ok`, E(R) +7.97% | **FIRES, full readout** |
| 25% — above the band | 20% | `anchor_divergence`, **E(R) withheld** | n/a |

The third row is the one that matters most: **the guard is still armed, not disabled.**
Production md5 re-read after every run — unchanged.

## 6. CODICIL 1 — COVERAGE LIMIT ON RECORD

**9 of the 10 widened names were UNVERIFIED at arm time.** The replay in §5.3 covers 5
tickers, of which only NOW widens. ARM, BE, CBRS, LITE, QBTS, SKHY, IONQ, RKLB and SPCX have
**no eval-date price stored at all**, because `evaluate.py` never writes `synthesis_cache`
and these names have only ever been evaluated interactively. Their bands are therefore
**reasoned, not measured**.

**The widened band is the risk direction.** Past 15%, a name now needs 20% or 30% to trip, so
a real defect on a YOUNG or HIGROWTH name can pass where flat-15 would have caught it.

## 7. CODICIL 2 — THE TRIPWIRE

The first divergence on any name that lands in `(15%, stage band]` — one flat-15 *would* have
tripped — emits `** B2-WIDENING-SUPPRESSED-TRIP **` with implied anchor, live price, the band
and its reason, and reports to Vic **before that E(R) is treated as trusted**. Same pattern as
the D-5 `BANK-RUNG-UNCALIBRATED` tripwire: an uncalibrated rung stays *observable* until a
real event validates it.

**It ADVISES; it does not withhold.** E(R) is still computed and persisted on a
suppressed-trip row. The codicil ordered a report, and withholding would be a second, unruled
guard smuggled in under a reporting order. Pinned by
`test_the_tripwire_advises_and_does_not_withhold`.

The tag string is grep-able by design — the whole point is that this event must not scroll
past unnoticed in a 28-name batch log the way the technicals defect did for 12 days.

Boundary note: the guard trips on `divergence > threshold`, so a divergence of *exactly* 15%
does not trip at flat-15 either. The tripwire uses the same strict comparison, or it would
report events flat-15 would not in fact have caught.

## 8. ROADMAP ITEM (ruled NOT this order)

**The batch path should record `price_snapshot` to `synthesis_cache` (or equivalent) for
every completing eval going forward**, so the 9 unverified names accumulate replayable
eval-date coverage on their next real evals. The verification gap then closes **by
operation** — no dedicated capture order needed.

## 9. FOUND WHILE VERIFYING — NOT FIXED, OUTSIDE THE ORDER

**`get_cached_synthesis(ticker, today_str)` at `batch/runner.py:309` is called WITHOUT
`db_path`.** It therefore always reads **production** `caliber.db`, even under a
`--db-path` scratch run — while the matching `save_synthesis_cache` twelve lines below
*does* honour the destination. A scratch or fixture run can consequently reuse a production
synthesis.

This is a **read**, so it is not contamination and nothing was written anywhere it should not
have been. But it is the same *shape* as the 2026-08-17 contamination and as the
`--db-path` help-string defect already on the punch list: **a destination flag whose real
scope is narrower than a human reads it.** `--db-path` is documented as routing every write;
it does not route this read. One-line fix, but it belongs to its own order.
