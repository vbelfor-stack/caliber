# L-3 — STAGE-CONDITIONED B-2 BAND (§5 step 3, ARMED)

**Order:** L-3, ruled 2026-08-17 · **Commit:** `75cf503` · **Suite:** 809 → **825**
**No production write** — the dark pass showed zero flips, so per the order no name re-ran.
**md5 unchanged: `24df814597b6bab52b979e7fee6ca034`.** Step 4 stays blocked.

---

## 1. THE CONSUMER CENSUS (acknowledgment 1) — measured, and your hypothesis holds

**Question:** what consumes `avg_score` today?

**`avg_score` is DISPLAY + STORAGE ONLY. Nothing reads it back.**

| site | what it does |
|---|---|
| `evaluate.py:361-365` | computes it, **prints** "Composite avg score" |
| `batch/runner.py:259-263, 502` | computes it, logs it, **prints** it in the summary table |
| `store/models.py:408` | computes it, **stores** it in `evaluations.avg_score` |

Zero readers. No code path loads `avg_score` back out and acts on it.

**But the refinement matters:** the synthesis prompt does **not** receive `avg_score` — it
receives the **per-pillar scores and flags** (`synthesis/prompt.py:_pillar_dict` → `"score"`,
plus `all_flags`). So the prompt-bias channel is real but runs through *individual pillar
scores and their flags*, not the composite.

**Grading reads neither.** `core/grading.py` touches only `expected_return` and
`verdict_conf` — never `avg_score`, never `pillars_json`.

**So the chain is:**

```
pillar scores + flags ──► synthesis PROMPT ──► model's scenario targets ──► E(R) ──► grade
avg_score ────────────► printed and stored, read by nothing
```

**Your conclusion is supported: pillar defects are display + prompt-bias bugs, not forecast
bugs, and the grading system grades synthesis skill almost alone.** The RKLB case is the
demonstration — Valuation 5 → 1 moved `avg_score` 3.4 → 2.6 and the model returned *identical*
targets, so the graded forecast was untouched. Three of six L-2b names did move E(R), so the
prompt-bias channel is real; it is just loose, and it is the **only** channel.

**What that changes about future pillar work** (Code's read, for your ruling): pillar accuracy
buys better *prompt context* and a better *human-readable readout*, not directly better
forecasts. Work that improves E(R) has to go through the synthesis prompt, the scenario
schema, or the anchor guard. Pillar work is still worth doing — a wrong Valuation feeds a
wrong prompt, and LLY's 11.8-point swing shows what a wrong *frame* costs — but its value is
indirect and should be argued that way rather than assumed.

---

## 2. THE DARK PASS (item 4) — the entire blast radius, before arming

| band | names |
|---|---|
| **30% (YOUNG)** | IONQ, RKLB, SPCX |
| **20% (HIGROWTH)** | ARM, BE, CBRS, LITE, NOW, QBTS, SKHY |
| **15% (default)** | 18 of 28 — all MATURE/DECLINE, **plus DPC and INFQ** |

**DPC and INFQ read YOUNG and are still held to 15%** — the fail-closed rule working exactly
as ruled: their stage comes from `INSUFFICIENT-HISTORY` (one fiscal year), which is a default
the rules assign, not a measurement. Granting them the widest band is precisely the
"missing data is privately optimal" failure.

### The flip test — and a correction to my own first attempt

My first flip test reported "NONE" **by construction**: it fell back to `would_flag =
flagged_now` whenever `synthesis_json` carried no recorded divergence, and no row does. That
is a vacuous pass, so I redid it — recomputing each name's divergence with the guard's own
formula (`implied_anchor = weighted_target / (1 + modelER/100)`) against live prices. All 28
computed.

| ticker | band | divergence | @15% | @band |
|---|---|---|---|---|
| **STX** | 15% | **90.08%** | FLAG | FLAG |
| INFQ | 15% | **14.63%** | ok | ok |
| SPCX | 30% | 13.86% | ok | ok |
| IONQ | 30% | 12.23% | ok | ok |
| RKLB | 30% | 11.88% | ok | ok |
| NVDA | 15% | 9.93% | ok | ok |
| BE | 20% | 7.21% | ok | ok |
| XE · WU · USB · GOOGL · V · CAT | 15% | 4.3–6.4% | ok | ok |
| the rest | 15–20% | < 4% | ok | ok |

**FLIPS: NONE.** Arming changed no name's flag state. That is an armed change with no
immediate effect — worth stating plainly rather than dressing up.

**The near-miss is the interesting part: INFQ sits at 14.63% against the 15% band it is held
to by the fail-closed rule — 0.37pp from tripping.** Had it been granted YOUNG's 30% it would
have 15pp of headroom. So the fail-closed decision is not theoretical; it is one small price
move from mattering on a live held name.

**Also surfaced, not fixed: STX carries a 90.08% divergence and `status='anchor_divergence'`.**
Its synthesis anchored near **$94** while STX trades near **$995** — the same stale-anchor
shape as the MU case that motivated B-2 in the first place, now caught on a held name. E(R)
was withheld, which is the guard doing its job. Worth a look: a ~10x gap suggests the model
anchored to a pre-split or badly stale price level.

---

## 3. What was armed, and what stayed dark

`core/stage_tolerance.tolerance_for(ticker, db_path)` reads the **persisted** stage — the
calibration set step 1 exists to accumulate — and returns `(tolerance, stage, reason)`. The
reason string prints on every evaluation, so a run always says which band it used and why.

**The band is passed INTO `check_anchor` as its existing `threshold` parameter**, so
`synthesis/schema.py` never learns what a stage is. That keeps the coupling one-directional
and left three of the four dark pins untouched: `core/pillars.py`,
`core/valuation_anchors.py`, `batch/runner.py` and `synthesis/schema.py` still contain no
reference to the classifier or the stage table.

**Pin retired by name, as ordered:** `test_evaluate_annotates_but_never_consults_the_stage`.
Replaced by `test_the_tolerance_lookup_is_the_ONLY_scoring_path_consumer_of_stage`, which
asserts exactly one call site in `evaluate.py` and none anywhere else in the scoring path.
The retired pin's surviving half is still checked: the annotation runs **after** scoring, so a
run's own stage row cannot feed that run's own pillars.

**Ordered pin on IONQ passes:** after its lens override moved it HIGROWTH → YOUNG, the
tolerance follows the **post-override** stage and it gets 30%.

**One divergence I want ruled:** the band is armed in `evaluate.py` only. `batch/runner.py`
still calls the guard on the flat 15%, because its dark pin is separate and step 1 deliberately
left the batch path alone. **So the two paths now disagree about tolerance.** That is a
legible, bounded inconsistency rather than a hidden one, but it should not persist: either
batch gets the same lookup under its own order, or the divergence is recorded as intended.

---

## 4. Acknowledgment 3 — the override/guard-set note

Added to the override mechanism's record: an override changes not just the lens but **the
guard set that travels with it**, and `lifecycle_transitions` is the required evidence that
the mover was reviewed. No code change; the transition row for IONQ (HIGROWTH → YOUNG) is that
evidence.

---

## 5. Incidental finding, recorded not fixed

**Every `field_provenance` row has `field_name = NULL`.** 1,416 rows, and the column that
would make provenance queryable by field is empty on all of them. Provenance is currently
only inspectable by `(evaluation_id, pillar)`. Recorded for a future order.

---

## 6. STOP

Step 4 remains blocked behind `fundamental_series` coverage expansion per the standing ruling.
Open for you: the batch-vs-evaluate tolerance divergence (§3), my reading of "unreliable"
(§2 / the config docstring), STX's 90% divergence, and the NULL `field_name` column.
