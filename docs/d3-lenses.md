# Phase D-3 — per-lens rate anchoring: DARK measurement + proposals

**Measured 2026-08-09** · golden five (MU, GOOG, V, NOW, WU) · live FMP + EDGAR + FRED
**FRED 10Y = 4.69% (confidence: high)**
**APPLIED = NOTHING. PERSISTED = NOTHING.** No Prov, score, E(R) or grade moved; `caliber.db`
md5 `54aa42e56b4b753fab18b77b552665fb` byte-identical before and after.

Raw record: **`docs/d3-lenses.json`** (25 ticker×lens cells + the bank instrument readings).

```
python -m tools.probe_d3_lenses MU GOOG V NOW WU --json OUT
```

Read-only by construction, same discipline as the D-0 probe — it never imports
`batch.runner` or `store.models`. `tests/test_d0_probe_readonly.py` now pins that for **both**
probes (import closure in a clean subprocess + AST import list), so a convenience import that
would hand either probe a write path fails there.

The dark score is also wired at both evaluation boundaries (`evaluate.py`, `batch/runner.py`):
every eval now logs the live score beside the would-be panel score for its active lens. Applied
to nothing.

---

## 1. Score-delta table — 5 tickers × 5 lenses

`*` = the ticker's **native** lens (what CALIBER actually does to it). Unmarked rows are
**counterfactual**: the golden five exercise only three of five lenses, so every ticker is
scored under every lens to give the bank and standard proposals some live evidence rather
than none. `cut` = the score under the one-rung independence haircut (option A in §5).

| Ticker | Lens | | live | panel | cut | Δ | binding anchor | spread | gate |
|---|---|---|---|---|---|---|---|---|---|
| MU | cyclical | `*` | 2 | **2** | 2 | +0 | own_history | −0.65pp | peak |
| MU | compounder | | 2 | 2 | 1 | +0 | risk_free | −2.05pp | |
| MU | growth | | 4 | **5** | 4 | **+1** | risk_free | +2.35pp | |
| MU | standard | | 4 | 4 | 3 | +0 | risk_free | +2.35pp | |
| MU | bank | | 1 | — | — | — | — | — | no yield metric |
| GOOG | cyclical | | 2 | 2 | 2 | +0 | risk_free | +0.99pp | peak |
| GOOG | compounder | `*` | 1 | **1** | 1 | +0 | risk_free | −3.45pp | |
| GOOG | growth | | 3 | **5** | 4 | **+2** | risk_free | +2.81pp | |
| GOOG | standard | | 4 | 4 | 3 | +0 | risk_free | +2.81pp | |
| GOOG | bank | | 1 | — | — | — | — | — | no yield metric |
| V | cyclical | | 2 | 2 | 1 | +0 | sector | −2.37pp | rollover |
| V | compounder | `*` | 2 | **2** | 1 | +0 | sector | −2.52pp | |
| V | growth | | 4 | **3** | 2 | **−1** | sector | −1.39pp | |
| V | standard | | 2 | 2 | 1 | +0 | sector | −1.39pp | |
| V | bank | | 1 | — | — | — | — | — | no yield metric |
| NOW | cyclical | | 2 | **1** | 1 | **−1** | risk_free | −3.40pp | rollover |
| NOW | compounder | | 2 | 2 | 1 | +0 | risk_free | −1.14pp | |
| NOW | growth | `*` | 2 | **3** | 2 | **+1** | risk_free | −2.11pp | |
| NOW | standard | | 1 | **2** | 1 | **+1** | risk_free | −2.11pp | |
| NOW | bank | | 1 | — | — | — | — | — | no yield metric |
| WU | cyclical | | 5 | **4** | 4 | **−1** | own_history | +1.38pp | |
| WU | compounder | `*` | 5 | **5** | 4 | +0 | sector | +12.61pp | |
| WU | growth | | 3 | **5** | 4 | **+2** | sector | +17.89pp | |
| WU | standard | | 5 | 5 | 4 | +0 | sector | +17.89pp | |
| WU | bank | | 2 | — | — | — | — | — | no yield metric |

### Headline: on native lenses, almost nothing moves

**1 of 5 native cells changes** (NOW growth, 2→3). MU, GOOG, V and WU all score identically
under panel anchoring. That is the single most important number in this table, and it cuts
against the intuition that D-3 is a large change:

- The **compounder** lens is Δ0 on all five tickers — expected, since it was already
  spread-based, but note MIN over three anchors did not change a single rung versus the
  live risk-free-only ladder. Adding the sector anchor changed the binding denominator on
  V and WU (sector binds instead of risk-free) **without** changing the score.
- The **cyclical** lens is Δ0 on its only native name (MU), because the peak gate holds it
  at 2 either way.

Across all 20 scored cells, 8 move. Seven of those eight are in **counterfactual** cells,
and 5 of 8 are the growth lens. **The growth lens is where the risk concentrates.**

---

## 2. Per-lens proposals

### 2.1 Compounder — CONFIRM AS-IS (the prototype)

No change proposed. FCF yield vs the panel, `RATE_SPREAD_LADDER` (≥+3 → 5, ≥+1 → 4, ≥−1 → 3,
≥−3 → 2, else 1). Δ0 on all five tickers. The only change is that MIN now runs across three
anchors instead of one, which is the aggregation ruling applied — and it demonstrably does not
disturb the existing rungs.

### 2.2 Cyclical — TRAILING basis + HARD GATE (not a shifted ladder)

**Basis: trailing. This is the load-bearing recommendation of D-3.**

The measured comparison, cyclical lens, gate off vs on:

| Ticker | trailing binding | raw | forward binding | raw | gated (both) |
|---|---|---|---|---|---|
| **MU** | own_history −0.65pp | **3** | risk_free **+25.47pp** | **5** | 2 |
| GOOG | risk_free +0.99pp | 3 | risk_free +2.20pp | 4 | 2 |
| V | sector −2.37pp | 2 | sector −0.34pp | 3 | 2 |
| NOW | risk_free −3.40pp | 1 | risk_free +2.12pp | 4 | 2 |
| WU | own_history +1.38pp | 4 | sector +20.79pp | 5 | 4/5 |

On a **forward** basis MU scores **5 — maximally cheap — with every anchor agreeing**, at a
cycle peak. That is the 2018 signature exactly: a ~3.3x forward P/E that is an artifact of
peak-cycle estimates. On a **trailing** basis the same name scores 3 raw, and its own-history
anchor is already dissenting at −0.65pp.

Both bases end at 2 **once the gate fires** — so on today's data the basis choice looks free.
It is not. It determines the **failure mode**: if the trajectory read is ever unavailable or
wrong (missing gross-margin history, a new issuer, a mis-tagged series), forward hands the
model a 5 and trailing hands it a 3. Trailing is two rungs safer in exactly the case where the
guard is not there to help. Forward's only advantage — it is more current — is worth least
precisely on cyclicals, where currency of the estimate is the problem.

**Mechanism: hard gate, not a shifted ladder.** Recommend keeping the existing peak/rollover
gate and applying it as a **cap at 2** on the panel score. A shifted ladder cannot express this:
at peak margins the *denominator itself* is about to change, so no rung geometry over the
current E is meaningful. A gate says "this reading is not admissible", which is the true claim.
The gate only ever caps — pinned by test.

**Rungs:** unchanged from `RATE_SPREAD_LADDER`. MU at −0.65pp → 3 and NOW at −3.40pp → 1 are
both defensible, and no rung boundary in the golden five sits within 0.4pp of a spread, so the
data gives no reason to move one.

### 2.3 Growth — SHIFTED LADDER, and this is where I am least confident

**Proposed:** EBITDA yield against the panel, on a ladder shifted 2pp more permissive
(≥+1 → 5, ≥−1 → 4, ≥−3 → 3, ≥−5 → 2, else 1).

**Rationale:** a growth name is a duration asset. It can carry a negative current yield spread
and still be correctly priced, because the cash flow is expected in the out-years. Scoring it on
the default ladder would mark essentially every SaaS name 1–2 and make the lens a constant.

**But the measured deltas are the largest in the table and they run the wrong way:**

| Ticker | live | panel | Δ |
|---|---|---|---|
| GOOG | 3 | 5 | **+2** |
| WU | 3 | 5 | **+2** |
| MU | 4 | 5 | +1 |
| NOW (native) | 2 | 3 | +1 |
| V | 4 | 3 | −1 |

Four of five move **up**, two by two full rungs. The cause is structural, not a bad shift
constant: the live growth lens scores **EV/Revenue gated by Rule-of-40**, which is a
growth-quality instrument, while the panel scores an **EBITDA yield**, which is a
profitability instrument. They are not measuring the same thing, so this is not a
recalibration — it is an instrument swap wearing a ladder's clothes.

**Recommendation: do NOT arm the growth lens on this mapping in D-4.** Two defensible options,
and I would take (b):

- **(a)** Arm it, and accept that growth names get systematically cheaper-looking scores.
- **(b)** **Keep the live Rule-of-40 × EV/Revenue instrument as the growth lens's score, and
  let the rate enter as a shifted THRESHOLD on EV/Revenue rather than as a spread verdict** —
  i.e. the acceptable EV/Rev multiple falls as the 10Y rises. That preserves the instrument
  that actually discriminates growth quality while making it rate-aware, which is what ethos
  rule 10 asks for. It needs its own dark pass to calibrate the shift, which I have not run.

I am flagging this rather than quietly proposing (a) because the growth lens is the one place
where D-3's mapping is doing something other than what it claims.

### 2.4 Standard — CONFIRM, EBITDA yield, default ladder

EV/EBITDA is the standard lens's own primary input, so `ebitda_yield` is the natural anchor and
the mapping is an identity rather than a swap. Δ0 on 4 of 5 tickers; only NOW moves (1→2), and
that is the panel correctly reading NOW's −2.11pp as "rich but not extreme" against a live
ladder that had it at the floor.

**Caveat, stated plainly: no golden ticker is natively standard-lens.** Every cell above is
counterfactual. The proposal rests on the mapping being an identity and on 4/5 agreement, not
on live evidence of the standard lens in use. If you want live evidence before arming, the
golden set needs a standard-lens name added — that is a universe change, your call.

### 2.5 Bank — THE PANEL DOES NOT FIT. Use a different instrument.

**The honest answer is that the bank lens needs a different instrument, and I recommend not
forcing it into the panel at all.**

A yield spread asks "what does this earn against the risk-free rate". For a bank, book value
*is* the asset base and leverage is the business, so the meaningful question is whether it earns
more on its book than shareholders require. P/B is the market's standing answer to that, and it
has no yield interpretation to spread against the 10Y.

**Proposed instrument: P/B against justified P/B, where justified P/B = ROE / CoE and
CoE = 10Y + β × ERP** (ERP fixed at 4.5pp). This is the Gordon identity with g = 0. It is
**still rate-anchored** — the 10Y enters through CoE — so ethos rule 10 is satisfied without
pretending P/B is a yield. A bank earning exactly its cost of equity is worth book; the ratio
says how far from that it trades.

Measured on the golden five (all counterfactual — **there is no bank-lens name in the golden
set at all**):

| Ticker | P/B | ROE | β | CoE | justified P/B | P/B − justified |
|---|---|---|---|---|---|---|
| MU | 9.83 | 70.6% | 2.189 | 14.54% | 4.85 | +4.98 |
| GOOG | 6.72 | 50.8% | 1.234 | 10.24% | 4.96 | +1.76 |
| V | 19.72 | 61.3% | 0.754 | 8.08% | 7.58 | +12.14 |
| NOW | 10.31 | 13.8% | 0.930 | 8.88% | 1.55 | +8.76 |
| **WU** | **2.42** | 42.6% | 0.519 | 7.03% | **6.07** | **−3.65** |

The instrument behaves sensibly on names it was not designed for: NOW's low ROE (13.8%) against
a 10.31x P/B produces the largest quality-adjusted overvaluation in the set, and WU is the only
name trading *below* its justified P/B. It is also visibly wrong-domain for MU (β 2.19 on a
cyclical inflates CoE), which is the correct behaviour — it should only ever be used on the
bank lens.

**Two things I cannot give you:** any live bank-lens evidence (the golden five contain none),
and a calibrated ladder over `P/B − justified P/B` (I have five counterfactual points, which is
not a calibration). **Recommend: rule the mechanism now, arm it never in D-4** — add a bank name
to the golden set and run a dedicated dark pass first.

---

## 3. Independence-narrowed mechanism (binding condition 1)

**The measurement that decides this: 17 of 20 scored cells (85%) are independence-narrowed.**
Own history exists in only 3 cells — MU, GOOG and WU on trailing earnings — because it is a
trailing-earnings-only anchor and V and NOW have no usable series (V: no share-count series at
all; NOW: 5:1 split truncation, a Phase G dependency).

That single number rules out the option I would otherwise have recommended.

**Option A — one-rung ladder haircut when the surviving anchors are all market-referenced.**
Measured in the `cut` column above. **Recommend against.** A haircut applied to 85% of readings
is not an adjustment for a rare degraded case; it is a global recalibration of the whole ladder
applied through a side door. It would move 13 of the 20 cells, including 4 of 5 native ones,
and the resulting scores would no longer mean what the ladder says they mean. If a one-rung-
harsher ladder is right, it should be ruled as the ladder — visibly — not smuggled in as a
narrowing penalty.

**Option B — score cap (e.g. no narrowed panel may score 5).** Recommend against, for the same
reason plus one worse: it is discontinuous exactly where conviction is highest, so WU's
+12.61pp compounder reading would be capped for a reason unrelated to WU.

**Option C — FLAG ONLY, with the flag carried into the rationale and the synthesis prompt.
This is my recommendation.** Record `anchor_count`, emit `PANEL-NARROWED-MARKET-ONLY`, and say
in the rationale that the two surviving denominators are both market-referenced so a
market-wide re-rating would not be caught. Change no score.

The reasoning: the narrowing is not evidence the stock is more expensive — it is evidence
**we know less**. The honest response to knowing less is to say so, not to fabricate a
penalty that looks like knowledge. This is also the same shape as the R1 symmetric-gating
ruling on EDGAR ("a source too stale to raise confidence is too stale to lower it"), and
consistency there seems worth more than a small conservative nudge here.

**Consequence to accept if you take C:** on forward/FCF/EBITDA the panel is a two-anchor
market-referenced object nearly everywhere, and MIN over it reduces to "cheaper than the 10Y,
unless the sector is dearer still". That is a real weakening of the panel's claim, and the
flag is what keeps it visible until Phase G restores own-history coverage. **This is the
strongest argument for moving Phase G up, which you have already ruled.**

---

## 4. Exchange-scoped sector P/E

**Recommend: primary-listing convention. Simplest defensible, and the materiality does not
justify more.**

The defect: FMP publishes the sector P/E snapshot per exchange, so Technology/NASDAQ is 48.1x
(2.08% yield) while Technology/NYSE is 41.4x (2.41% yield). MU is scored against the first and
NOW against the second purely because of where the shares are listed — **~0.33pp of yield**, no
economic content.

| Option | What it does | Cost |
|---|---|---|
| **Primary-listing convention** *(recommend)* | Use the snapshot for the exchange the issuer is actually listed on. Document that the anchor is venue-scoped and that ~0.33pp of it is an artifact. | Zero — this is current behaviour, made explicit and documented. |
| Cap-weighted blend | Merge venues into one sector anchor weighted by market cap. | Needs a per-venue constituent list and cap data FMP does not serve in the snapshot; several extra calls per eval, and a blend nobody can reproduce by hand. |

**Materiality check against the rungs that would be armed:** 0.33pp is a third of the narrowest
rung (the ±1pp band). In the golden five, no ticker's sector spread sits within 0.33pp of a rung
boundary, so **the defect flips zero scores today**. It is a real arbitrariness, but it is
below the resolution of the instrument it feeds.

Recommend documenting it as a known artifact of the sector anchor and revisiting only if a
future ticker's sector spread lands inside a rung boundary by less than 0.5pp — which the panel
can detect and flag for itself.

---

## 5. What D-3 did not establish

Stated so the rulings are made with the gaps visible:

1. **No live bank-lens or standard-lens evidence.** The golden five contain neither. Both
   proposals rest on counterfactual cells.
2. **The growth mapping is an instrument swap, not a recalibration** (§2.3). I recommend not
   arming it on this mapping.
3. **No calibration for the bank instrument's ladder** — five counterfactual points is not a
   calibration.
4. **Own-history remains 3/20.** Every conclusion about MIN's behaviour on forward, FCF and
   EBITDA is a conclusion about a two-anchor market-referenced object, not the three-anchor
   panel Phase D was scoped around.
5. **One measurement, one day.** Prices, estimates and the 10Y all move; `docs/d3-lenses.json`
   is the fixed record this was argued from.
