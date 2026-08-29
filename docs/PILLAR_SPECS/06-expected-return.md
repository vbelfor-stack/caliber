# EXPECTED RETURN — E(R)
**Glass-box audit, 2026-08-29. Read-only. No fixes applied.**
HEAD `ff02e21` · suite 1091 · caliber.db md5 `69dc2328ee3af8a43d506b64665da39b` (unchanged).
Implementation: **`synthesis/schema.py:195-217` `compute_er`**, guarded by
**`check_anchor` (`:295-338`)**, graded by **`core/grading.py`**.

---

## ★★ THE HEADLINE — READ THIS BEFORE THE ANSWERS TO 5(a)-(d)

**E(R) IS NOT A VALUATION MODEL. IT HAS NO REVERSION COMPONENT AND NO GROWTH COMPONENT,
BECAUSE IT HAS NO COMPONENTS AT ALL IN THAT SENSE.**

E(R) is the probability-weighted mean of **three price targets written by the LLM**:

```python
E(R) % = Σ (p_i / 100) × ((target_i / current_price) − 1) × 100
```

That is the entire computation — one line, three inputs, all three of them model output.
**No multiple, no earnings, no cash flow, no discount rate, and none of the five pillar
scores enter it.** The pillars are passed to the model *in the prompt*; the arithmetic that
produces the persisted number touches none of them.

**So the audit questions in §5 of the order have to be answered by saying the structure they
assume is not present.** The decomposition that *does* exist is bull/base/bear, and MU is
worked out that way in §5.5. This is a finding, not an evasion: **the single number CALIBER
is graded on is the only quantity in the system with no deterministic derivation.**

---

## 1. EXACT COMPUTATION

### 1.1 Inputs

| Input | Source | Grain |
|---|---|---|
| `bull.priceTarget`, `base.priceTarget`, `bear.priceTarget` | **★★ LLM synthesis output** | — |
| `bull.probability`, `base.probability`, `bear.probability` | **★★ LLM synthesis output** | — |
| `current_price` | FMP `profile` / quote, passed into the prompt AND into `compute_er` | spot |
| `expectedReturn` (the model's own) | **★★ LLM** — **discarded from E(R)**; used ONLY by the anchor guard | — |

### 1.2 The computation and its normalisation

```python
for sc in (bull, base, bear):
    if sc.priceTarget is not None and sc.probability > 0:
        total_er   += sc.probability * ((sc.priceTarget / current_price) - 1.0)
        total_prob += sc.probability
if total_prob == 0: return None
return (total_er / total_prob) * 100.0
```

**Only scenarios that carry BOTH a target and a positive probability enter, and the result
is renormalised over `total_prob` — not over 100.** See §4 Finding B.

### 1.3 The anchor guard (B-2), which is the only defence

`check_anchor` (`synthesis/schema.py:295`), `ANCHOR_DIVERGENCE_THRESHOLD = 0.15`:

```
Tw             = Σ pᵢ·targetᵢ / Σ pᵢ          (probability-weighted mean target)
implied_anchor = Tw / (1 + model_ER/100)      (the base price the model actually used)
divergence     = |implied_anchor / live_price − 1|
```

- `divergence > threshold` → **raise `AnchorPriceDivergence`**, E(R) withheld (NULL),
  `status='anchor_divergence'`, synthesis kept.
- `expectedReturn is None` → **bypass-by-omission guard**: withhold, `anchor_unverified`.
- no live price / no targets / `model_ER ≤ −100%` → `anchor_unverified`.

**The guard is anchor-AGNOSTIC** — it catches a stale LLM anchor *or* a bad feed price.

**★ THE THRESHOLD IS STAGE-CONDITIONED IN PRODUCTION.** The 15% constant here is the
interactive default; both production paths call `tolerance_for(ticker, db)`
(`evaluate.py:487`, `batch/runner.py:408`), which returns **15% / 20% / 30% by lifecycle
stage** (B-2, L-4b). **This is the ONLY place in the entire engine where lifecycle stage
changes an outcome** — see §3.

### 1.4 Grading

`core/grading.py`: `actual_return = (price_at_90d / price_at_eval − 1) × 100`, admitted at
`min_age_days = 90`. Rubric in CLAUDE.md; `|E(R)| < 5%` → C `[no-conviction E(R)]`.

## 2. ★★ ANALYST / ESTIMATE-DERIVED INPUTS — **THE DEEPEST CONTAMINATION IN THE SYSTEM**

**★★ E(R) IS 100% MODEL-DERIVED, AND THE PROMPT EXPLICITLY INVITES TRAINING-KNOWLEDGE
ANALYST VIEWS INTO IT.** `synthesis/prompt.py:104-106`:

> *"You may add qualitative context (news, **analyst views**, filings themes) from your
> training knowledge but clearly mark anything beyond the provided data."*

and the schema requires a `research` array with `"tier": "independent|sell-side|crowd"`.
So sell-side views are a **first-class, invited input** to the scenarios whose targets
*are* E(R). Every guard in the codebase — sole-source doctrine, USD-only, the negative-
multiple gates, `min_conf` — sits **upstream of the pillars**, and the pillars do not feed
the arithmetic. **The number CALIBER is graded on is the least-guarded quantity it
produces.** The one countervailing control is real and should be credited: the prompt's
anchoring instruction plus the B-2 divergence guard, which is what keeps the *base* honest.
It constrains the anchor, not the targets.

**★★ AND THE ONE NON-LLM PRICE TARGET IN THE PAYLOAD IS DISCARDED.**
`price-target-summary.lastMonthAvgPriceTarget` is fetched into
`TickerData.target_mean_price` (`adapters/fmp_adapter.py:452`), currency-guarded as
score-bearing (`core/reporting_currency.py:184`) — **and read by nothing.** The sell-side
consensus target is available, typed and guarded, and E(R) uses the model's numbers instead.
*Whether it should be used is a ruling; that it is fetched and silently dropped is a fact.*

## 3. STAGE HANDLING — **THE ONE PLACE STAGE IS LOAD-BEARING**

Every pillar ignores lifecycle stage. **E(R) does not.** `tolerance_for(ticker, db)`
(`core/stage_tolerance.py`) reads the live `lifecycle_stage` row and returns the B-2 band:

| Stage | Band |
|---|---|
| default / unclassified | **15%** |
| (mid) | **20%** |
| YOUNG etc. | **30%** |

Filtered on `retired_reason IS NULL` since the financials gate (2026-08-28). Stage does not
change the *value* of E(R) — it changes **whether E(R) is published at all**, by widening the
divergence band that withholds it.

**★ THE CODE SAYS THE OPPOSITE, IN PRINT.** `evaluate.py:193` prints:

> `LIFECYCLE STAGE  (Phase L — annotation only, reads into NO score)`

**That string is false as written.** Stage reaches `tolerance_for()` and gates E(R)
publication. It is defensible on a narrow reading — stage moves no *pillar score* — but it
is printed to the operator on every run and reads as "this is inert". Given the standing rule
that *a rule recorded without naming its enforcement point is a belief*, an operator-facing
line asserting inertness for something load-bearing is worth a ruling. **Recorded, not
edited.**

## 4. NEGATIVE / ZERO / MISSING HANDLING

| Condition | Behaviour | Verdict |
|---|---|---|
| `current_price` ≤ 0 or None | return `None` | fail-closed ✓ |
| no scenario has a target | return `None` | fail-closed ✓ |
| model `expectedReturn` absent | **withhold + `anchor_unverified`** | fail-closed ✓ |
| divergence > band | **withhold + `anchor_divergence`**, synthesis kept | fail-closed ✓ |
| model `expectedReturn ≤ −100%` | `anchor_unverified` | fail-closed ✓ |
| **one scenario missing a target** | **silently renormalised over the survivors** | **★★ fail-open** |
| probabilities not summing to 100 | silently renormalised | fail-open (documented) |
| negative target | arithmetically fine (return < −100%); no guard | unguarded |

**★★ FINDING A — THERE IS NO HORIZON. ANYWHERE.** A grep of `synthesis/prompt.py` for
`month|year|timeframe|horizon|term` returns **one hit**, and it carries no time period:

> *"Each priceTarget is a forward view RELATIVE TO current_price"*

The prompt never states over what period. The schema never states it. `compute_er` never
states it. **And then `core/grading.py` measures the outcome at exactly 90 days** — `A` is
awarded when `|actual| ≥ |E(R)| × 0.75` at day 90.

**So a horizon-free model estimate is graded against a fixed 90-day realised return, and the
mismatch is silent.** A model that produced a well-calibrated 12-month target would be
systematically graded `B` (right direction, "smaller" move) or `C` (`|actual| < 5%`), and
that would look like model error rather than a units mismatch. **Nothing in the system can
currently distinguish the two.** This bears directly on the first gradeable cohort due
**~2026-11-26** — *the grades will be read before this is ruled unless it is ruled first.*
**Highest-priority item in this audit.**

**★★ FINDING B — A MISSING SCENARIO TARGET INFLATES E(R), SILENTLY.** `compute_er`
accumulates `total_prob` **only over scenarios that carry a target**, then divides by it. If
the model returns `"priceTarget": null` for the **bear** case — which the schema explicitly
permits (`number_or_null`) — the bear scenario is dropped and E(R) is renormalised over
bull+base alone.

Worked on MU's real numbers (§5.5): dropping the bear leg takes E(R) from **−15.74%** to
**+(0.20×28.64 + 0.50×(−16.39)) / 0.70 = −3.52%** — a **+12.2pp** swing toward optimism, from
an *omission*. **Absence is privately optimal** — the same inversion class as the Growth
PE-leg finding, on the output number rather than a pillar. No flag, no note, no status
change. `dataGaps` exists in the schema but nothing ties it to this. **Needs a ruling.**

**★ FINDING C — THE GUARD VERIFIES THE ANCHOR, NOT THE TARGETS.** `check_anchor` confirms the
model priced *from* the right base. It cannot detect an unreasonable *spread* of targets, an
inconsistent probability set, or a target that ignores every pillar. **This is correctly
scoped and is noted as a limit, not a defect** — but it means the only quantitative check on
E(R) is a base-price check.

## 5. THE ORDER'S SPECIFIC E(R) QUESTIONS, ANSWERED

**5.1 Components (reversion vs growth): NEITHER EXISTS.** There is no multiple-reversion term
and no growth term. The only decomposition is **bull / base / bear**, each a model-authored
price target with a model-authored probability. Any reversion or growth reasoning lives
inside the LLM's prose and is not recoverable from the stored numbers.

**5.2 Horizon: UNSTATED IN THE MODEL, 90 DAYS IN THE GRADER.** See Finding A.

**5.3 Full vs partial reversion: NOT MODELLED.** No reversion coefficient, no fade, no
terminal multiple. The concept has no representation in the code.

**5.4 Dividends: EXCLUDED. E(R) IS PRICE-ONLY, ON BOTH SIDES.**
- `compute_er` uses `target / price − 1` — a pure price relative.
- `core/grading.py:202` uses `price_at_90d / price_at_eval − 1` — also price-only,
  from `_fetch_price_at_date`, an unadjusted close.

**Both sides are consistently price-only, so the grade is not biased by the omission** — this
is the benign case and it should be said plainly. The residue is that E(R) is a **price
return, not a total return**, and is not labelled as such anywhere. FMP's `dividends`
endpoint *is* already in the payload (fetched for the lifecycle classifier), so the input
exists if total return is ever wanted. For V at ~0.7% yield it is immaterial; across a
28-name book it is a systematic ~1-2%/yr understatement of holding-period return.

**5.5 WORKED MU EXAMPLE, PER-COMPONENT CONTRIBUTION** — eval id **286**, 2026-08-28.

Stored `expected_return = −15.742983941856230`. Model's own `expectedReturn = −14.2`
(discarded from E(R); used only for the anchor). `Tw = (20×1200 + 50×780 + 30×520)/100 =`
**$786.00**. Inverting the stored E(R) recovers the eval-date price:
`P = 786.00 / (1 − 0.1574298…)` = **$932.86**.

| Scenario | p | target | `(target/P − 1)` | **contribution to E(R)** |
|---|---|---|---|---|
| **bull** | 20% | $1,200.00 | **+28.64%** | **+5.7273 pp** |
| **base** | 50% | $780.00 | **−16.39%** | **−8.1931 pp** |
| **bear** | 30% | $520.00 | **−44.26%** | **−13.2772 pp** |
| | 100% | | | **Σ = −15.742984%** ✓ |

Reconciles to the stored value to **1e−9**. Anchor check:
`implied_anchor = 786.00 / (1 − 0.142) =` **$916.08** vs live **$932.86** →
**divergence 1.80%**, well inside the band → `status='ok'`, E(R) persisted.

**★ WHAT THE MU ROW SHOWS WHEN READ AGAINST ITS OWN PILLARS.** MU's five pillar scores are
**5 / 5 / 4 / 5 / 2** (avg 4.2 — the highest of the three names audited), and its E(R) is
**−15.7%**. The bear leg alone contributes −13.3pp. **The pillars and E(R) are not merely
weakly coupled — they are computed on disjoint inputs, and here they point in opposite
directions.** The only pillar that agrees with the E(R) is Valuation, the one carrying the
cycle-peak gate. Whether that divergence is the system working (deterministic quality vs
forward-looking price) or a coupling gap is **a ruling, not a defect** — but it should be
ruled with this row in front of it.

### QBTS — eval id 289 (for completeness)

`Tw = (15×38 + 55×11 + 30×4)/100 =` **$12.95**; stored E(R) **−23.845928%** → price
**$17.0050**.

| Scenario | p | target | return | contribution |
|---|---|---|---|---|
| bull | 15% | $38.00 | +123.46% | **+18.5196 pp** |
| base | 55% | $11.00 | −35.31% | **−19.4222 pp** |
| bear | 30% | $4.00 | −76.48% | **−22.9433 pp** |
| | | | | **Σ = −23.845928%** ✓ |

Anchor: implied **$15.8896** vs **$17.0050** → divergence **6.56%**. Inside the **30% YOUNG**
band **and** inside the 15% default — so the stage widening was not load-bearing here.

### V — eval id 294

`Tw = (25×457 + 50×408 + 25×305)/100 =` **$394.50**; stored E(R) **+3.380503%** → price
**$381.60**.

| Scenario | p | target | return | contribution |
|---|---|---|---|---|
| bull | 25% | $457.00 | +19.76% | **+4.9397 pp** |
| base | 50% | $408.00 | +6.92% | **+3.4591 pp** |
| bear | 25% | $305.00 | −20.07% | **−5.0183 pp** |
| | | | | **Σ = +3.380503%** ✓ |

Anchor: implied **$368.00** vs **$381.60** → divergence **3.56%** → `ok`.

**★ V IS BELOW THE CONVICTION FLOOR.** `|E(R)| = 3.38% < 5%`, so under rubric rule 1 V will
grade **C `[no-conviction E(R)]` regardless of what the price does.** The evaluation
completed, was persisted `status='ok'`, and is **structurally ungradeable for signal.**
Correct per the locked rubric — recorded because a reader scanning for "ok" rows will count
V as a live forecast, and it is not one.

## 6. RECONCILIATION NOTE

All three eval-date prices above were **recovered by inverting the stored E(R)** against the
scenario targets, and each reproduces the stored value to 1e−9. They were **not** read from
`synthesis_cache.price_snapshot` — that table holds 16 rows across 5 tickers, which is the
known capture gap already on the CLAUDE.md roadmap (*"RECORD `price_snapshot` ON EVERY
COMPLETING EVAL"*). **This audit is a fourth independent demonstration of why that item
matters: the eval-date price had to be reconstructed arithmetically because it was not
stored.**

## 7. BUILT BUT NEVER READ

- **`target_mean_price`** — sell-side consensus target, fetched, currency-guarded, **read by
  nothing**. The one non-LLM price target in the payload. See §2.
- **`per_scenario_returns`** (`synthesis/schema.py:220-236`) — computes bull/base/bear
  returns; **no production path calls it.** The per-scenario decomposition in §5.5 had to be
  recomputed by hand for this audit even though the function exists.
- **`AnchorCheck.divergence` / `.implied_anchor`** — computed on **every** evaluation and
  documented as a *"permanent dark-launch for ongoing calibration"*, but **there is no column
  for either in `evaluations`** (16 columns; none of them divergence). The calibration series
  the comment promises is not being accumulated in a queryable form.
- **`SynthesisOutput.expectedReturn`** — the model's own E(R) is parsed and then used
  **only** as the anchor-guard denominator; it is never persisted as a distinct field, so
  model-vs-computed drift (MU: −14.2 vs −15.74) is not recoverable after the fact except by
  re-deriving it from `synthesis_json`, as this audit did.
