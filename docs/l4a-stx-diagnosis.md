# L-4a — STX ANCHOR-DIVERGENCE DIAGNOSIS

**Order (2026-08-19, Vic):** "STX diagnosis — bad price feed vs stale LLM anchor. Verify live
price against a second source, check FMP for splits/adjustments. Feed defect → report blast
radius on every name's divergence check before fixing. Stale anchor → re-synthesize STX fresh,
supersede-linked. Expected-delta on any writes."

**STATUS: REPORT ONLY. ZERO WRITES PERFORMED.** `caliber.db` md5
`24df814597b6bab52b979e7fee6ca034` at session open and unchanged at report time. No code was
modified. Nothing arms without a ruling.

---

## 1. VERDICT — IT IS NEITHER OF THE TWO OFFERED CAUSES

The order framed the question as price-feed vs stale-LLM-anchor. **It is a THIRD cause, and it
is ours: a defect in `core/technicals.py`.** Naming it precisely matters, because the remedy for
each of the three is different and two of them are wrong here.

- **NOT a bad price feed.** FMP is correct to the cent against an independent source, and its
  series is internally consistent and continuous.
- **NOT a stale LLM anchor.** The model did not reach into training memory. **It was HANDED a
  stale price by our own pipeline, in the prompt**, and anchored to it — which is the correct
  thing to do with a provided price.
- **IT IS A MODULE-BOUNDARY CONTRACT MISMATCH.** `analyze_technicals` reads the price history
  from the WRONG END, so every technical it produces describes **August 2021**, not today.

**The B-2 guard worked exactly as designed.** It caught a genuine defect on a name where the
consequence would otherwise have been an invented E(R). E(R) is withheld on STX; that is the
guard doing its job. What the guard could not do is name the cause — hence this report.

---

## 2. ROOT CAUSE, EXACTLY

FMP's `historical-price-eod/full` returns rows **newest-first**. The adapter documents this and
deliberately preserves it — `adapters/fmp_adapter.py:33`:

> `- price_history list is sorted newest→oldest by FMP; we keep that order`

`core/technicals.py` documents its input (line 60) **without stating any order requirement**,
and then implements oldest-first assumptions:

| line | code | intent | actual effect on FMP data |
|---|---|---|---|
| 105 | `last_price = closes[-1]` | latest close | the **oldest** close, ~5 years stale |
| 31-34 | `sum(closes[-period:]) / period` | trailing MA | average of the **oldest** 50 / 200 sessions |
| 37-55 | `_rsi(closes)` | 14-day RSI | RSI over a **time-reversed** series (every delta's sign flipped) |
| ~115 | volume vs 30d avg | volume confirmation | 2021 volumes |

Both modules are internally coherent and separately documented. They disagree **at the
boundary**, and nothing asserted the contract. This is the same defect class as the F1 finding
already on record (the `fcf_yield` leg that "had never produced a value anywhere"): a
never-measured output that looked fine.

**Aggravating factor.** `adapters/fmp_adapter.py:119` already records that FMP does not honour
`limit`: the call asks for 365 rows and receives **1254**. So the stale end is ~5 years old
rather than ~1 year. The defect's severity was multiplied by a known, documented vendor quirk.

### Proof on live STX (2026-08-19, adapter's own fetch path)

```
price_history rows: 1254   row0 = 2026-08-19 $832.56   last row = 2021-08-20 $89.44

CORRECT (chronological):  last 832.56 | MA50 890.67 | MA200 559.98 | above_ma50=False above_ma200=True
AS PRODUCTION COMPUTES:   last  89.44 | MA50  84.84 | MA200  94.03 | above_ma50=True  above_ma200=False
```

**Both booleans are inverted.** The model was told "above MA50, below MA200 — structurally
bearish" when the truth is "below MA50, above MA200".

### The chain that produced the 90.08% divergence

`synthesis/prompt.py:77` passes `tech.notes` — a prose string — into the prompt. On
2026-08-17 that string read `"Price $89.03. MA50=84.81 MA200=94.09 RSI=59.3..."` while the same
prompt carried `current_price = $994.91`. **The model received a direct contradiction and
resolved it in favour of the technicals block.** Its stored output echoes the injected numbers
verbatim, including RSI 59.27 → "RSI 59.3", proving it was reading provided data faithfully
rather than hallucinating:

```
stored technicals notes (id 258): "Price $89.03 above MA50 $84.81 but below MA200 $94.09 — structurally bearish"
weighted target 94.55 / (1 + (-4.2)/100) = implied anchor 98.70   vs live 994.91 → divergence 90.08%
```

Re-measured today the same code yields MA50 84.84 / MA200 94.03 / RSI 59.33 — the 2026-08-17
values drifted only because the 5-year window slid two rows. Mechanism confirmed.

---

## 3. THE ORDER'S TWO EXPLICIT VERIFICATIONS — BOTH CLEAR FMP

**(a) Live price against a second source.** Independent source (stockanalysis.com) reports STX
**$832.56 as of 2026-08-19 16:00 EDT**, market cap $188.70B, 52-week range $152.50–$1,145.00.
FMP `profile.price` reads **$832.56** — identical. Corroborated on the prior session too:
second source $903.45 for 2026-08-18 vs FMP's $903.68. **FMP's price is right.**

**(b) Splits / adjustments.** `fetch_splits('STX')` returns **no splits**. Independently
confirmed by continuity: scanning all 1254 sessions chronologically, **zero single-day moves
>25%** — an unadjusted split would appear as a clean ~10x or ~-90% step. The 9.31x is genuine
appreciation, and it is visible year by year:

| year | min | max | last |
|---|---|---|---|
| 2021 | 79.01 | 115.00 | 112.98 |
| 2022 | 48.49 | 116.02 | 52.61 |
| 2023 | 51.88 | 86.79 | 85.37 |
| 2024 | 80.11 | 112.64 | 86.31 |
| 2025 | 66.54 | 307.85 | 275.39 |
| 2026 | 284.47 | 1094.04 | 832.56 |

**No feed defect exists.** The ~10x gap is five years of real price history being misread as
"today".

---

## 4. A RECORDED RESOLUTION IS OVERTURNED — MU / id 209 WAS MISDIAGNOSED

CLAUDE.md currently states, as settled fact:

> "MU root cause RESOLVED: it was a genuine stale LLM anchor, NOT a feed bug. Model anchored to
> ~$81 (stale training data) … FMP was CORRECT."

**The first half is wrong.** id 209's own stored technicals block reads:

```
"Price $80.21 above MA50 $72.12 and MA200 $78.10. RSI 67.6 …"      ← MU's 2021 prices
implied anchor = $80.88                                             ← matches to within 0.8%
```

The $81 was **not** recalled from training data — it was **in the input**, put there by this
same defect. Reproducing the mechanism from the MU fixture yields the same 2021 band
(Price $79.56, MA50 74.90, MA200 78.87); id 209 differs only because it ran live 20 sessions
later, sliding the window.

**Consequence — the B-2 prompt fix is a MASK, not a fix.** The 2026-08-07 remedy instructed the
model to anchor to `current_price` and never use remembered levels. It "worked" (MU divergence
90.8% → 1.1%, id 214) by making the model **ignore the contradictory technicals** instead of
removing the contradiction. id 214's stored notes still carry the same poisoned values
("Price above both MA50 (72.12) and MA200 (78.10)") on a stock at $885. So:

- the prompt fix is still worth keeping — it is correct guidance on its own terms;
- but it **suppressed the only visible symptom** of a live defect, and the defect kept running
  for 12 days across 5 further batch sessions with nothing objecting.

**This is the "loud failure beats silent degradation" rule inverted by accident.** It also
re-proves the standing lesson in the sharpest possible form: *recorded state is a claim, not a
measurement* — and this time the false claim was a **root-cause attribution** that had been
believed and acted upon.

---

## 5. BLAST RADIUS

### 5a. What is NOT affected — bounded structurally, not by inspection

- **PILLAR SCORES: UNAFFECTED.** `analyze_technicals` has exactly three consumers —
  `evaluate.py:372`, `batch/runner.py:252`, and `synthesis/prompt.py`. **No pillar, lens,
  anchor or valuation path reads technicals at all.** Verified by grep across the tree. So
  `avg_score` and every pillar cell are untouched.
- **GRADES: NONE AFFECTED.** The `grades` table has 0 rows.
- **`_price_on_or_before` (own-history anchors, G-4, H-3) IS IMMUNE.** It scans for the max
  date ≤ target rather than indexing, so it is order-agnostic. `fundamental_series` and
  `valuation_anchors` are therefore unaffected — which is also why the fix can be confined to
  `core/technicals.py`.

### 5b. What IS affected — every evaluation with a synthesis, without exception

FMP became the price feed on **2026-07-11** (`369ff5c`). The earliest `ok` evaluation is
**2026-07-12**. **All 68 evaluations carrying a synthesis were produced with 2021-era
technicals in the prompt.** There is no clean pre-defect population to compare against.

Reach: technicals → prompt → the model's `trend`, `redFlags`, narrative, `verdictConfidence`,
and in the two divergence cases its `priceTarget`s → `expectedReturn` → (eventually) grades.

**Divergence-check contamination, per the order's specific ask.** Recovering the price actually
used (`weighted_target / (1 + stored_ER/100)`) and comparing it to the stale price the prompt
injected:

| ticker | id | real price used | stale price injected | understated by |
|---|---|---|---|---|
| LLY | 242, 267 | $1185.16 | $72.60 | 16.32x |
| CAT | 239 | $881.65 | $54.40 | 16.21x |
| GOOG | 259 | $341.45 | $21.40 | 15.96x |
| GOOGL | 241 | $344.00 | $21.70 | 15.85x |
| MU | 229, 255 | $1011.75 | $70.62 | 14.33x |
| MU | 221 | $971.66 | $70.93 | 13.70x |
| GOOG | 210, 217 | ~$353.6 | $26.10 | ~13.5x |
| LITE | 253 | $968.90 | $81.67 | 11.86x |
| BE | 238, 269 | $232.16 | ~$20.5 | ~11.3x |
| LRCX | 254 | $343.84 | $56.95 | 6.04x |
| FN | 251 | $598.58 | $102.19 | 5.86x |
| NOW | 232 | $117.70 | $20.80 | 5.66x |
| ARM | 249 | $271.43 | $67.70 | 4.01x |
| RKLB, IONQ | 244/266, 248 | $82.08 / $46.84 | $22.40 / $12.79 | 3.66x |

**48 of 68 rows** show the injected price differing from the real price by >25%.

> CAVEAT, stated rather than glossed: the "stale price injected" column is a **regex extraction
> of the first numeric token from the model's prose `notes`**, so it is a proxy. For the large
> movers it is unambiguous and corroborated by the mechanism. For a few low-priced names
> (notably WU id 212's `78.40`) the token is probably not the price, and those individual
> ratios should not be relied on. The structural claim — all 68 prompts carried 2021
> technicals — does not depend on this column.

**The healthy-band calibration is contaminated.** The recorded B-2 band "0.6–8.2%, 15%
isolates the pathological case with ~6x margin" was measured entirely on poisoned prompts. Six
2026-08-17 rows already sit at 9.9–14.6% (INFQ 14.6%, SPCX 13.9%, RKLB 12.6%/11.9%, IONQ
12.2%/9.9%, NVDA 9.9%) — inside the flat 15% band but no longer with 6x margin. **The band
should be recalibrated after the fix, on clean prompts, before any conclusion is drawn from
divergence readings.** This bears directly on L-4b, which arms a tolerance band in
`batch/runner.py`.

### 5c. Why the golden harness could not catch it — and the fixture migration is implicated

Every one of the nine FMP fixtures is **newest-first**, because the recorders reuse the
adapter's own live fetch path (by design, and that discipline is right). So **the offline
baseline agrees with the bug**, and a before/after diff shows nothing.

CLAUDE.md already warned about exactly this, on 2026-08-15:

> "migrating a baseline onto the same source it is meant to check RETIRES THE CHECK … name what
> is being given up before doing it."

The retired yfinance fixtures were **ascending** (yfinance returns oldest-first). Under
yfinance the code was **correct**. The defect was introduced by the feed migration and then
made invisible by the fixture migration. **The thing given up was never named, because nobody
knew ordering was load-bearing.**

Compounding it: the only test that touches `analyze_technicals`
(`tests/test_adapters.py:374-380`) asserts a **provenance source string** and not one numeric
value. **No test has ever asserted an MA, an RSI, or a boolean.** 825 tests are green.

---

## 6. RECOMMENDED FIX — NOT APPLIED, AWAITING RULING

Per the order's feed-defect branch ("report blast radius before fixing"), nothing was changed.

**Recommended shape** — sort inside `core/technicals.py`, not at the adapter:

1. `analyze_technicals` sorts rows **by `date` ascending** before computing anything, rather
   than trusting caller order. It is the module with the ordering requirement, so it should own
   it. This leaves the adapter's documented newest-first contract — and
   `tests/test_corporate_actions.py:316`, which reads fixtures directly — untouched.
2. **State the requirement in the docstring** (line 60 currently omits it) and **pin it with a
   test that feeds the same series in both orders and asserts identical output.** That test is
   the guard; the sort alone is a belief.
3. **Add a value-level assertion** on at least one fixture (an MA and the two booleans), since
   nothing in the suite currently pins any technical value.
4. Consider a sanity tripwire: if `last_close` diverges from `current_price` by more than a set
   margin, say so loudly — the two came from the same vendor seconds apart and should agree.
   That single check would have caught this on day one.

**Expected blast radius of the fix** — measured offline across the nine fixtures, **8 of 18
boolean cells flip**:

| ticker | flip |
|---|---|
| WU | above_ma50 **True→False**, above_ma200 **True→False** |
| NOW | above_ma50 **False→True**, above_ma200 **False→True** |
| BK | above_ma200 False→True |
| C | above_ma50 True→False |
| JPM | above_ma50 False→True |
| USB | above_ma50 False→True |
| GOOG, MU, V | no flip — correct by luck (strong uptrends are above both MAs at either end) |

**WU is the validating case.** Production reports it above both MAs (its 2021 $22.73 vs MA
21.24 / 18.96); it is actually **$7.08, below both**. The project's canonical secular-decline
name was being described to the model as being in an uptrend. Note also that the names with no
flip are the strong trends — **the booleans are right by luck precisely when they carry least
information, and wrong at the turning points where technicals matter.**

### Why re-synthesizing STX now would be WRONG

The order's stale-anchor branch says re-synthesize STX supersede-linked. **That remedy must not
be executed yet.** The prompt still carries 2021 technicals, so a re-synthesis today would
either reproduce the poisoning or — more likely, given the B-2 prompt fix — mask it into a
healthy-looking divergence, converting a caught defect into an uncaught one. **STX must be
re-synthesized only AFTER the technicals fix lands**, and at that point it is a normal
supersede-linked re-run (`supersedes_id=258` + reason).

**Sequencing recommendation for the ruling:** technicals fix (with pins) → re-synthesize STX
supersede-linked → recalibrate the B-2 band on clean prompts → *then* L-4b batch tolerance
arming. L-4b arms a divergence band; arming it on contaminated calibration would bake this
defect into the guard.

Whether the other 67 evaluations warrant supersede-linked re-runs is **Vic's call, not
recorded here as a plan**. Argument for: every stored narrative and red-flag set was generated
against 2021 technicals. Argument against: pillar scores are untouched, grades are empty, and
E(R) was anchored to the correct `current_price` on all but the two caught rows — so the
damage is to narrative quality, not to the numbers that feed grading.

---

## 7. EXPECTED-DELTA STATEMENT

**Expected delta: NONE. Actual delta: NONE.** This order was diagnosis only.

- `caliber.db` md5 `24df814597b6bab52b979e7fee6ca034` — unchanged, verified at report time.
  All DB access used `sqlite3.connect('file:caliber.db?mode=ro', uri=True)`.
- No `evaluations`, `field_provenance`, `synthesis_cache` or `lifecycle_*` rows written.
- No production code modified.
- Live calls were read-only adapter fetches (`fetch_fmp`, `fetch_splits`) plus one
  second-source page fetch. `evaluate.py` was never invoked.

## 8. INCIDENTAL FINDING (not part of this order)

`caliber.db.pre-rerun-2026-08-15.bak-shm` (32 KB) and `-wal` (0 bytes) exist, dated
2026-08-17 19:52 — inside the contamination window. The WAL is empty so nothing is pending and
the `.bak` itself is intact, but something opened a **backup** as a live database that evening.
Recorded for the punch list, not investigated.
