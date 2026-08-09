# Phase D-0 — valuation anchor panel: live measurement

**Measured 2026-08-09** · golden five (MU, GOOG, V, NOW, WU) · live FMP + EDGAR + FRED
**FRED 10Y = 4.69% (confidence: high)**
**APPLIED = NOTHING. PERSISTED = NOTHING.** No Prov, score, E(R) or grade moved; no row was
written to `caliber.db`.

## How to reproduce

```
python -m tools.probe_valuation_panel MU GOOG V NOW WU --json /tmp/d0.json
```

The probe is read-only **by construction, not by flag**. It calls the adapters directly, the
way `evaluate.py` does, and never imports `batch.runner` or `store.models` — so no writer is
reachable from it even by accident. `tests/test_d0_probe_readonly.py` asserts that three ways:
the import closure in a clean subprocess (catches a writer arriving transitively), the AST
import list, and the AST call list. Verified empirically on this run: `caliber.db` md5
`54aa42e56b4b753fab18b77b552665fb` and its 31 evaluations / 420 provenance rows were
byte-identical before and after.

Re-run this after D-4 to re-measure against armed ladders. Because it persists nothing, it is
safe to run at any time and as often as wanted.

## Reading the numbers

Everything is a **yield in percentage points**, so the three anchors share one currency:

```
spread = ticker_yield − anchor_yield        positive ⇒ CHEAPER than that denominator
```

"Dispersion" is the spread between the highest and lowest available anchor for that ticker and
metric, in pp. "Least-flattering" is the provisional MIN aggregation rule's pick.

---

## 1. Full spread table — 5 tickers × 4 metrics × 3 anchors

#### Trailing earnings yield (`earnings_yield_trailing`)

| Ticker | Ticker yield | vs risk-free | vs sector | vs own history | Least-flattering | Dispersion | Verdict |
|---|---|---|---|---|---|---|---|
| MU | 5.11 | +0.42 | +3.03 | -0.65 | own_history (-0.65) | 3.68 | **SPLIT** — cheap vs risk_free+sector, rich vs own_history |
| GOOG | 5.68 | +0.99 | +1.58 | +1.26 | risk_free (+0.99) | 0.59 | agree |
| V | 3.25 | -1.44 | -2.37 | — | sector (-2.37) | 0.93 | agree |
| NOW | 1.29 | -3.40 | -1.12 | — | risk_free (-3.40) | 2.28 | agree |
| WU | 17.66 | +12.97 | +12.03 | +1.38 | own_history (+1.38) | 11.58 | agree |

#### Forward earnings yield (`earnings_yield_forward`)

| Ticker | Ticker yield | vs risk-free | vs sector | vs own history | Least-flattering | Dispersion | Verdict |
|---|---|---|---|---|---|---|---|
| MU | 30.16 | +25.47 | +28.08 | — | risk_free (+25.47) | 2.61 | agree |
| GOOG | 6.89 | +2.20 | +2.79 | — | risk_free (+2.20) | 0.59 | agree |
| V | 5.29 | +0.60 | -0.34 | — | sector (-0.34) | 0.93 | **SPLIT** — cheap vs risk_free, rich vs sector |
| NOW | 6.81 | +2.12 | +4.40 | — | risk_free (+2.12) | 2.28 | agree |
| WU | 26.41 | +21.72 | +20.79 | — | sector (+20.79) | 0.93 | agree |

#### FCF yield (`fcf_yield`)

| Ticker | Ticker yield | vs risk-free | vs sector | vs own history | Least-flattering | Dispersion | Verdict |
|---|---|---|---|---|---|---|---|
| MU | 2.64 | -2.05 | +0.56 | — | risk_free (-2.05) | 2.61 | **SPLIT** — cheap vs sector, rich vs risk_free |
| GOOG | 1.24 | -3.45 | -2.86 | — | risk_free (-3.45) | 0.59 | agree |
| V | 3.10 | -1.59 | -2.52 | — | sector (-2.52) | 0.93 | agree |
| NOW | 3.55 | -1.14 | +1.13 | — | risk_free (-1.14) | 2.28 | **SPLIT** — cheap vs sector, rich vs risk_free |
| WU | 18.23 | +13.54 | +12.61 | — | sector (+12.61) | 0.93 | agree |

#### EBITDA yield (`ebitda_yield`)

| Ticker | Ticker yield | vs risk-free | vs sector | vs own history | Least-flattering | Dispersion | Verdict |
|---|---|---|---|---|---|---|---|
| MU | 7.04 | +2.35 | +4.97 | — | risk_free (+2.35) | 2.61 | agree |
| GOOG | 7.50 | +2.81 | +3.40 | — | risk_free (+2.81) | 0.59 | agree |
| V | 4.23 | -0.46 | -1.39 | — | sector (-1.39) | 0.93 | agree |
| NOW | 2.58 | -2.11 | +0.17 | — | risk_free (-2.11) | 2.28 | **SPLIT** — cheap vs sector, rich vs risk_free |
| WU | 23.51 | +18.82 | +17.89 | — | sector (+17.89) | 0.93 | agree |

Anchor levels behind those spreads: risk-free 4.69% everywhere; sector — Technology/NASDAQ
2.08% (48.1x), Technology/NYSE 2.41% (41.4x), Communication Services/NASDAQ 4.10% (24.4x),
Financial Services/NYSE 5.62% (17.8x); own history — MU 5.75%, GOOG 4.43%, WU 16.27%.

## 2. Per-metric distributions (spreads in pp, across the golden five)

| Metric | Anchor | n | min | median | max |
|---|---|---|---|---|---|
| trailing earnings | risk_free | 5 | -3.40 | +0.42 | +12.97 |
| trailing earnings | sector | 5 | -2.37 | +1.58 | +12.03 |
| trailing earnings | own_history | **3** | -0.65 | +1.26 | +1.38 |
| forward earnings | risk_free | 5 | +0.60 | +2.20 | +25.47 |
| forward earnings | sector | 5 | -0.34 | +4.40 | +28.08 |
| forward earnings | own_history | **0** | — | — | — |
| FCF | risk_free | 5 | -3.45 | -1.59 | +13.54 |
| FCF | sector | 5 | -2.86 | +0.56 | +12.61 |
| FCF | own_history | **0** | — | — | — |
| EBITDA | risk_free | 5 | -2.11 | +2.35 | +18.82 |
| EBITDA | sector | 5 | -1.39 | +3.40 | +17.89 |
| EBITDA | own_history | **0** | — | — | — |

Which anchor binds under MIN:

| Metric | risk_free binds | sector binds | own_history binds |
|---|---|---|---|
| trailing earnings | 2 | 1 | 2 |
| forward earnings | 3 | 2 | 0 |
| FCF | 3 | 2 | 0 |
| EBITDA | 3 | 2 | 0 |

## 3. Inter-anchor disagreement

**Dispersion (pp).** Trailing earnings: min 0.59 / median 2.28 / max 11.58. All three other
metrics: min 0.59 / median 0.93 / max 2.61.

A caveat that matters for D-3, and which the numbers make plain: on forward, FCF and EBITDA the
dispersion figure is **identical for a given ticker** (MU 2.61, GOOG 0.59, V 0.93, NOW 2.28,
WU 0.93) because with own-history absent it is just |risk-free − sector| — a property of the
ticker's sector and the 10Y, carrying no metric-specific information at all. Only trailing
earnings has genuine three-way dispersion. **"Dispersion is the signal" is currently true on
exactly one of four metrics.**

**Verdict splits (anchors disagreeing on the direction of cheapness) — 5 of 20 ticker-metric cells:**

| Ticker | Metric | Cheap vs | Rich vs |
|---|---|---|---|
| MU | trailing earnings | risk_free + sector | own_history |
| V | forward earnings | risk_free | sector |
| MU | FCF | sector | risk_free |
| NOW | FCF | sector | risk_free |
| NOW | EBITDA | sector | risk_free |

MU and NOW each split on two different metrics; GOOG never splits, its anchors sitting within
0.59pp on every metric.

## 4. Anchor availability

| Anchor | Readings available | Gap |
|---|---|---|
| risk-free | 20 / 20 | none — live FRED rate present at high confidence |
| sector | 20 / 20 | none — all five sectors present in the FMP snapshot |
| own history | **3 / 20** | trailing-earnings only (15/20 by construction), plus 2 tickers withheld |

Own history is the constraint. Per-ticker, with the typed reason:

| Ticker | Share points | Usable quarters | Span | Status / reason |
|---|---|---|---|---|
| MU | 24 | 15 | 2021-09-02 → 2026-05-28 | **available**; 5 FY2023 loss quarters excluded |
| GOOG | 24 | 17 | 2022-06-30 → 2026-06-30 | **available**; truncated at the 2022 20:1 split |
| WU | 24 | 20 | 2021-09-30 → 2026-06-30 | **available**; full series, no exclusions |
| V | **0** | 0 | — | withheld: `only 0 historical points (<8)`. **Root cause: no share-count series at all** — V's `dei` cover-page tag froze in 2010 and its multi-class `us-gaap` fallback is stale, so no quarter can be priced. Same accepted data limit already recorded for V under EDGAR. |
| NOW | 24 | **2** | 2026-03-31 → 2026-06-30 | withheld: `only 2 historical points (<8)`. **Root cause: the 5:1 split (208M → 1,046M shares)** truncates the series at the discontinuity, leaving 2 consistent quarters. Not a data gap — a split-adjustment gap. |

The two withholdings are **different in kind**, and D-3 should not treat them alike: V is an
accepted data limit (nothing to fix without a new source), while NOW is a **Phase G
dependency** — proper split adjustment would restore its full history, and possibly V's.

## 5. Trailing vs forward coverage

Both trailing and forward earnings yields resolved for **all five tickers** — forward estimates
are present across the board, so no ticker is trailing-only.

| Ticker | Trailing | Forward | Forward − trailing (pp) |
|---|---|---|---|
| MU | 5.11 | 30.16 | **+25.05** |
| GOOG | 5.68 | 6.89 | +1.21 |
| V | 3.25 | 5.29 | +2.04 |
| NOW | 1.29 | 6.81 | +5.52 |
| WU | 17.66 | 26.41 | +8.75 |

Forward is higher than trailing for every name, which is what consensus estimates always do.
The size of the gap is the interesting part — see the MU note below.

---

## 6. Analysis

### 6.1 The panel's founding case reproduces live — MU

MU is the **only three-anchor split in the set**: cheap against the risk-free rate (+0.42) and
cheap against its sector (+3.03), but **rich against its own history (-0.65)**. That is exactly
the configuration Phase D was scoped around, and it appeared on the first live measurement.

The corroborating detail is more pointed than the split itself. MU's **forward** earnings yield
is 30.16% — a ~3.3x forward P/E — putting it +25.47pp cheap against the 10Y and +28.08pp cheap
against semis, with **all anchors agreeing**. A forward-weighted panel would call MU the
cheapest asset in the universe by a wide margin. The only readings expressing any caution are
the trailing ones, and specifically the own-history anchor. This is the 2018 pattern in
miniature: at a cycle peak the forward E is the number that lies, and unanimity among anchors
on a forward metric is not evidence of safety.

### 6.2 The strongest result: own-history strips 11.6pp off WU

WU screens as the cheapest name in the set on every market-referenced denominator: +12.97pp vs
the 10Y, +12.03pp vs Financial Services, +13.54pp on FCF, +18.82pp on EBITDA. Against its own
history it is **+1.38pp** — a 6.1x median multiple against today's 5.7x. WU has always traded
like this, because it is a structurally declining money-transfer business, and the own-history
anchor is the only one in the panel that knows it.

MIN compresses a 13pp "table-pounding buy" into a 1.4pp "slightly cheap versus its own norm."
That is the value-trap discriminator doing precisely the job it was scoped to do, and it is the
single most decisive number in this dataset.

### 6.3 The sector anchor is exchange-scoped — a real defect for D-3

The FMP sector snapshot is published per exchange, so **the same sector carries two different
anchors depending on listing venue**: MU sits against Technology/NASDAQ at 48.1x while NOW sits
against Technology/NYSE at 41.4x. A company's sector denominator therefore depends on where its
shares happen to be listed, which has no economic content. It is a 6.7x multiple difference —
about 0.33pp of yield — small next to the spreads above, but it is an arbitrary term sitting
inside an anchor that would be armed. Flagging for a D-3 ruling; not touched in D-0.

### 6.4 On three of four metrics, the "panel" is a two-anchor panel

Own history exists only for trailing earnings, and only for 3 of 5 tickers — 3 of 20 readings
overall. On forward, FCF and EBITDA the panel is risk-free plus sector, and those two are not
independent in the way the panel's framing assumes: both are market-referenced, and their
difference is just the sector's premium to the 10Y. Under MIN on those metrics, risk-free binds
3 of 5 times and the exercise reduces to "is this cheaper than the 10Y, unless its sector is
even more expensive than it is."

That is not an argument against the panel; it is an argument that **the panel is only fully
itself on trailing earnings today**, and that its value scales directly with own-history
coverage.

### 6.5 Recommendation on aggregation: MIN, with two conditions — your ruling

**Recommend keeping MIN.** The direct comparison on trailing earnings, where all three anchors
are live:

| Ticker | MIN | Median | What median discards |
|---|---|---|---|
| MU | **-0.65** | +0.42 | the only anchor calling MU rich at a cycle peak |
| GOOG | +0.99 | +1.26 | little — anchors agree within 0.59pp |
| WU | **+1.38** | +12.03 | the entire value-trap finding |

Median-with-flag preserves WU as a +12pp screaming buy and flips MU from "rich" to "cheap."
In both cases the discarded anchor is own-history — the one carrying non-redundant information,
and structurally the minority anchor, so a median will discard it whenever it dissents. Since
own-history dissent *is* the value-trap signal, median systematically deletes the finding the
panel exists to produce. Averaging is also directly contrary to the framing ruling that
disagreement is the signal.

Two conditions I would attach:

1. **Record the anchor count with every aggregate, and treat a 2-anchor panel as narrowed.**
   MIN over 3 genuinely independent anchors is the rule you scoped. MIN over 2 correlated
   market-referenced anchors is a weaker object wearing the same name. D-3 should rule whether
   forward/FCF/EBITDA — currently 2-anchor everywhere — should score at all, or advise only.
2. **Keep dispersion as a reported flag, not an input, and state where it is meaningful.**
   On 3 of 4 metrics it is currently metric-invariant and carries no information; publishing it
   as if it did would be a small silent degradation of its own.

A secondary consequence worth your attention: **MIN's value is concentrated in the anchor with
the worst coverage.** Own-history binds 2 of 3 times where it exists and is absent 17 of 20
readings overall. That makes Phase G (split adjustment) a materially higher-value item than its
current "non-urgent, stays behind EDGAR" placement suggests — it would restore NOW immediately
and possibly V, taking own-history from 3/5 to 4/5 or 5/5 tickers.

## 7. Tracked follow-ups (not fixed in D-0)

- **`save_evaluation` unconditional write — latent footgun.** `batch/runner.py:224` calls
  `save_evaluation` unconditionally, outside any `if run_synthesis:` guard. A future
  `--no-synthesis` batch — the obvious way someone would try to re-measure cheaply — writes
  `no_synthesis` rows into production `caliber.db` and recontaminates the distribution the
  2026-08-07 purge established (`no_synthesis: 0`). The D-0 probe sidesteps it structurally
  rather than fixing it. **Likely folds into D-2 or a small standalone.**
- **Sector anchor is exchange-scoped** (§6.3) — needs a D-3 ruling.
- **GOOG FCF yield 1.24%** against a 5.68% earnings yield is a wide gap. Plausible on its face
  given current datacenter capex, but it drives GOOG's least-flattering reading on the FCF
  metric and is worth one confirmation pass before FCF is armed. Low priority, unverified.

---

*Generated by `tools/probe_valuation_panel.py`. Measurement only — D-0 applies nothing.*
