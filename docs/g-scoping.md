# Phase G — corporate-actions integrity: SCOPING REPORT

**Measured 2026-08-11** · REPORT ONLY, NOTHING IMPLEMENTED, NOTHING ARMED.
Evidence: offline fixtures (golden five + four calibration banks) + three read-only live
probes (SEC `companyconcept`, FMP `/stable/splits`). `caliber.db` untouched; no code changed.

> **Headline for the ruling.** The root cause is confirmed and the fix is well-posed and
> exact. But two measured findings cut against the premise that moved G up the roadmap:
> (1) split truncation costs **exactly one** of the 17 missing own-history readings — 15 of
> the 17 are missing *by construction*, not by defect; and (2) the fix moves **zero scores**
> across all nine tracked tickers, even when the cyclical lens is forced. G is worth doing,
> but as **latent-trap removal and accuracy**, not as coverage recovery. See §5 and §6.

---

## 1. Scope boundary (bias against creep)

**IN SCOPE.** Own-history anchor coverage lost to *corporate actions* — specifically, the
share-count series in `own_history_earnings_yields` (core/valuation_anchors.py:203) being on
a different basis from the FMP price series it is multiplied against.

**OUT OF SCOPE, named so it cannot drift in:**

| Excluded | Why |
|---|---|
| V's missing own-history | No share series at any basis (`stale_tag`). An accepted EDGAR data limit; a split fix does nothing for it — **measured, 0 → 0 quarters**. |
| Own-history for forward / FCF / EBITDA | The anchor is trailing-earnings-only *by construction*. This is the real coverage constraint (§5) and is **not** a corporate-actions defect. Parked for Vic. |
| Zero-with-coverage sentinels, >5x adjacent-year EPS jump flagging | Listed under "Phase G" in the roadmap but are a *different* defect class (value integrity, not basis integrity). Recommend they be split into G-2 and ruled separately. |
| Restating anything other than the own-history share series | Split adjustment must **not** touch the EDGAR cross-check, `shares_outstanding` as a *field*, or any pillar input. Blast radius stays at one function (§6). |

---

## 2. Root cause — NOW, measured

NOW's own-history anchor is withheld with `only 2 historical points (<8)`. Four mechanisms
stack; only the first is the headline, and the fourth is why NOW keeps 2 quarters and not 3.

**Layer 1 — BASIS MISMATCH (the defect).** FMP prices are split-adjusted back to today's
basis. EDGAR share counts are **as filed** and are not restated. Multiplying them across a
split yields a market cap wrong by exactly the split factor, so the earnings yield is wrong
by that factor. Confirmed arithmetic: GOOG's pre-2022 quarters read ~81% against a ~4% norm
— a clean 20x, exactly the 20:1 split ratio.

**Layer 2 — the current mitigation is truncation.** `own_history_earnings_yields` walks the
series newest-first and `break`s at the first adjacent-quarter share ratio outside
`_SPLIT_RATIO_TOLERANCE = 1.5`. This is **correct** — it refuses to launder a 20x artifact
into a median — but it is lossy, and it cuts at the *newest* discontinuity.

**Layer 3 — NOW's split.** dei `EntityCommonStockSharesOutstanding`, as filed:

```
2026-06-30  1,034,000,000     2025-09-30    208,000,000
2026-03-31  1,031,000,000     2025-06-30    208,000,000
2026-01-23  1,046,000,000     2025-03-31    207,000,000   ← 5:1, ex-date 2025-12-18
```

**Layer 4 — why 2 quarters and not 3.** NOW resolves shares from the **dei cover-page tag**,
whose dates are filing cover dates (`2026-01-23`), not period-ends. `shares_as_of("2025-12-31")`
cannot see a cover date that is *later* than the period-end, so it falls back to 2025-09-30's
pre-split 208M and the truncation fires one quarter early. The split is real at 2025-12-31;
the series loses that quarter to the as-of join, not to the split.

---

## 3. The finding that changes the design — the series is MIXED-BASIS

GOOG's share series is **not** "post-split, then pre-split". It interleaves:

```
2022-06-30  13,078,000,000   ratio_vs_newer  1.008
2022-03-31     658,763,000                   0.050   ← looks like the split boundary
2021-12-31  13,242,000,000                  20.101   ← but this one is RESTATED
2021-09-30     664,682,000                   0.050   ← and this one is not
```

A post-split filing restates *some* prior period-ends (annual comparatives) but not others
(original 10-Q cover pages), and `instant_series` de-duplicates by period-end keeping
whichever record sorts first. So restated and as-filed values sit side by side.

**Consequence, measured:** a naive adjacent-ratio detector fires **three** times on GOOG
(20:1, 1:20, 20:1). Running a cumulative-factor restatement off those inferred events
poisons 2 of 20 quarters — 2022-06-30 reads 0.25% and 2021-12-31 reads 0.20% against a ~4%
norm — while the **median barely moves (4.43% → 4.26%)**. The corruption is invisible in the
aggregate and real in the series. *Any G validation that compares only medians will pass a
broken implementation.* This is the strongest argument in this report for dark-before-arm
and for per-point assertions.

**The well-posed rule.** A fact is on the basis in effect at its **filing date**:

> `adjusted_shares = raw_value × Π { ratio : split.ex_date > fact.filed }`

No discontinuity inference at all. Verified exactly against live SEC data:

| period_end | filed | as-filed value | ex-date 2022-07-18 | adjusted |
|---|---|---|---|---|
| 2021-09-30 | 2021-10-27 | 664,682,000 | before → ×20 | 13,293,640,000 |
| 2021-12-31 | 2022-02-02 | 662,121,000 | before → ×20 | 13,242,420,000 |
| 2021-12-31 | 2022-07-27 | **13,242,000,000** | after → ×1 | 13,242,000,000 |
| 2022-03-31 | 2022-04-27 | 658,763,000 | before → ×20 | 13,175,260,000 |
| 2022-06-30 | 2022-07-27 | **13,078,000,000** | after → ×1 | 13,078,000,000 |

The two 2021-12-31 rows **reconcile to 0.003%** — the restated value *is* the as-filed value
times the split ratio. The rule is self-validating on the issuer's own data.

**BLOCKER (one field).** `_extract_xbrl_facts` (adapters/edgar_adapter.py:294) keeps
`start/end/fy/fp/form/accession` but **drops `filed`**, which companyfacts does provide.
Accession *year* is not a sufficient substitute: it separates GOOG's two 2021-12-31 rows
(`-22-` vs `-23-`) but **not** 2022-03-31 from 2022-06-30, which are both `-22-` and sit on
opposite sides of the split. Capturing `filed` is a prerequisite, not an optimisation.

---

## 4. Split detection and the SINGLE-SOURCE RISK

**The risk, named.** FMP `/stable/splits` is the only source guaranteed basis-consistent with
FMP's own adjusted prices — and FMP is the sole live feed, so by default it is uncorroborated.
A **missed** split silently reintroduces the artifact; a **phantom** split silently
manufactures one. Both failures produce a clean multiple (5x, 20x) that reads as a valuation
rather than an error — precisely the laundering class the anchor guard exists to catch, and
precisely why "trust the vendor" is not acceptable here.

**The risk is mitigable, and the mitigations were measured — all three agree:**

| Witness | GOOG | NOW | Cost |
|---|---|---|---|
| FMP `/stable/splits` | 20:1, ex 2022-07-18 | 5:1, ex 2025-12-18 | 1 call/ticker |
| EDGAR **restatement ratio** (same period-end filed on two bases) | **19.99937** | **5.00001** | **zero — already in the fetched payload** |
| EDGAR **tagged ratio** `StockholdersEquityNoteStockSplitConversionRatio1` | **20** @ 2022-07-15 | **5** @ 2025-12-05 | 1 concept added to `XBRL_CONCEPTS` |

Two of the three are inside EDGAR and therefore **genuinely independent of FMP**. This is the
same shape as the EDGAR cross-check: a second source that makes a single-source number
checkable.

**Design consequences:**
- Take the **ratio** corroborated; take the **date** from FMP. The EDGAR tag's date is a
  declaration/record date, not an ex-date (GOOG 07-15 vs 07-18; NOW 12-05 vs 12-18). Only the
  ex-date matches the basis FMP adjusted its prices on. The EDGAR date serves as a sanity band.
- **Disagreement → withhold the anchor** with a typed reason. Never pick a side, never average.
- The restatement witness **decays**: it exists only while a post-split filing restating a
  pre-split period-end remains inside the depth-40 extraction window. It covers recent splits
  — which are the ones that matter, since a split old enough to fall out of the window is also
  old enough to sit beyond the 24-quarter series.
- When **no** witness is available, FMP is uncorroborated. That state must be **flagged on the
  reading**, not hidden — the single-source condition should be visible, like the β cap.
- Rounding duplicates are **not** split witnesses (NOW 2020-12-31 ratio 1.00001, 2018-12-31
  ratio 1.00000). The witness test must require a materially non-unit ratio near a simple
  rational, or it will fire on filing-precision noise.

---

## 5. EXPECTED OWN-HISTORY COVERAGE AFTER THE FIX (required by the order)

Measured, not projected. Counterfactual run with the filed-date rule of §3.

**Readings (D-0 basis: golden five × 4 metrics = 20 cells):**

| | Now | After G | Ceiling for G |
|---|---|---|---|
| own-history available | **3 / 20** | **4 / 20** | **4 / 20** |

The remaining 16 cells decompose as **15 structural + 1 out of scope**:
- **15** — own-history is trailing-earnings-only by construction (forward, FCF and EBITDA ×
  5 tickers). Not a defect and not reachable by G.
- **1** — V's trailing cell: no share series at any basis. Measured 0 → 0 under the fix.

> **This is the number that should drive the ruling.** The roadmap's stated rationale was
> that "own-history is absent 17 of 20 readings" and that NOW's absence is a G defect
> "starving the aggregation rule". The second half is true; the first half is not evidence
> for G. G's entire reach is **one cell**. The 15-cell constraint is the trailing-only
> restriction, which is a *different* piece of work and is explicitly not scoped here.

**Per ticker, trailing-earnings anchor (measured, pre → post):**

| Ticker | Quarters now | Quarters after | Anchor now | Anchor after | Median yield |
|---|---|---|---|---|---|
| MU | 15 | 15 | available | available | 5.75% → 5.75% (no change) |
| GOOG | 17 | **20** | available | available | 4.43% → **4.34%** (accuracy) |
| WU | 20 | 20 | available | available | 16.27% (no change) |
| **NOW** | **2** | **19** | **withheld** | **AVAILABLE** | — → **0.78%** |
| V | 0 | 0 | withheld | withheld | — (out of scope) |
| JPM / BK / USB / C | 20 / 17 / 20 / 18 | unchanged | available | available | no change |

- **Golden five, trailing anchor: 3/5 → 4/5.**
- **Nine-ticker universe: 7/9 → 8/9.**
- GOOG is an **accuracy** gain, not a coverage gain: 3 more quarters and a correctly restated
  pre-split region, shifting the median 0.09pp.

---

## 6. Blast-radius audit — golden five + four banks

**Structural reach first.** The own-history anchor feeds `METRIC_EARNINGS_YIELD` only
(`_own_history_reading` returns unavailable for every other metric). Of the armed lenses, only
**cyclical** is panel-anchored on trailing earnings — compounder is on FCF, standard on EBITDA,
growth is rate-shifted (no panel), bank is cost-of-equity (no panel). So:

> **Own-history can move a score through the cyclical lens and nowhere else.**

| Ticker | Native lens | Panel metric | Own-history can reach score? | Affected by split fix? |
|---|---|---|---|---|
| MU | cyclical | trailing earnings | **YES** | no — no truncation |
| GOOG | compounder | fcf_yield | no | median shifts, inert |
| V | compounder | fcf_yield | no | no |
| **NOW** | **growth** | ebitda_yield | **no** | **anchor restored, inert** |
| WU | compounder | fcf_yield | no | no |
| JPM / BK / USB / C | bank | — | no | no |

**Measured counterfactual — cyclical lens FORCED on all nine, pre-fix vs post-fix:**

| Ticker | own-hist spread pre → post | risk-free spread | Binding anchor | Score pre → post |
|---|---|---|---|---|
| MU | −1.18 → −1.18 | −0.11 | own_history | **2 → 2** |
| GOOG | −0.72 → −0.63 | −0.98 | risk_free | **3 → 3** |
| V | — → — | −1.40 | risk_free | **2 → 2** |
| NOW | — → **+0.51** | −3.40 | risk_free | **1 → 1** |
| WU | +1.38 → +1.38 | +12.97 | own_history | **4 → 4** |
| JPM / BK / USB / C | unchanged | — | own_history | **2 / 2 / 2 / 1 unchanged** |

**Zero score movement on all nine, even with the lens forced.** NOW gains a full 19-quarter
anchor but reads *cheap* against it (+0.51pp), so under MIN it never binds — risk-free stays
the least-flattering denominator at −3.40. The one ticker whose lens *does* consume the anchor
(MU) has no truncation to fix.

**Therefore:** no E(R) moves, no grade moves, no golden-ticker score moves. The blast radius
of the fix itself is one function. The blast radius of the `filed` capture in §3 is wider —
it touches the extraction every EDGAR consumer reads — but it is **additive** (a new key on
each record), and the de-dup key `(start, end, unit, value)` is unchanged, so resolution
cannot move. That must be asserted, not assumed (G-1 below).

*(Offline panels are market-narrowed — fixtures carry no sector snapshot — so the sector
anchor is absent from the table above. Checked against D-0's live sector readings for NOW:
sector spread −1.12, still not binding. The conclusion holds live.)*

---

## 7. Phased plan — DARK BEFORE ARM

| Phase | Content | Gate |
|---|---|---|
| **G-1** | Capture `filed` on every extracted fact. **Additive only.** Prove resolution is unmoved: all 19 field specs across all nine tickers resolve to identical value/period/concept/reason before and after. | Golden-five + four-bank resolution diff must be **empty**. Report to Vic. |
| **G-2** | Split-record acquisition + corroboration, **DARK**. FMP `/stable/splits`; EDGAR restatement witness; tagged-ratio concept. Log agreement/disagreement per ticker. Applied to nothing. | Three-witness agreement table for all nine. Ratio and date semantics reported separately. |
| **G-3** | Filed-date basis restatement inside `own_history_earnings_yields`, **DARK**: compute the restated series alongside the live truncated one and log both. | **Per-point** diff, not medians (§3 — a median comparison passes a broken build). Every restated quarter's yield must be within a defensible band; the 0.25%/0.20% signature must be absent. |
| **G-4** | ARM on Vic's ruling. Flip the two pinned tests. | Reviewed diff across golden five + four banks; expected **all cells unchanged** per §6 — any movement is a finding, not a pass. |
| **G-5** *(separate ruling)* | Zero-with-coverage sentinels, >5x adjacent-year EPS jump flagging. Different defect class; recommend it not ride along. | — |

**Withholding rule to be ruled at G-4:** when a split is detected but its ratio is
uncorroborated *and* FMP is the only witness, does the anchor (a) apply FMP's ratio flagged
single-source, or (b) fall back to today's truncation? Recommendation: **(a) with a flag** —
truncation is the strictly worse outcome and the flag preserves the audit trail. Vic rules.

**Two tests will flip when G lands** (the same expected-fail signal pattern as JPM's cash tag):
- `test_series_truncates_at_a_split_boundary` (GOOG: asserts the series stops at 2022-06-30)
- `test_a_recent_split_can_cost_the_anchor_entirely` (NOW: asserts the anchor is withheld)

---

## 8. Recorded risks and open questions

1. **Price-history depth is an undocumented dependency.** `fetch_payload` requests
   `historical-price-eod/full?limit=365`, but FMP returns **1,255 rows (~5 years)** — the
   `limit` is not honoured. Own-history's entire depth rests on that. If FMP ever honours it,
   every own-history series drops below `MIN_HISTORY_POINTS` and the anchor goes to **0/20
   silently**. Not G's job to fix; recommend a cheap assertion on recorded price span so the
   day it changes is loud. **Vic's call.**
2. **The trailing-only restriction is the real coverage constraint** (15 of 17 missing
   readings). Extending own-history to FCF / EBITDA / forward would raise the ceiling from
   4/20 to 16/20. Deliberately not scoped. **Vic's call whether this becomes its own phase.**
3. **Layer-4 as-of join** (§2): matching a period-end to a dei cover-page date costs NOW one
   quarter and is a mild inaccuracy on every dei-resolved ticker. Fixable inside G-3 at no
   extra cost once bases are consistent, but it is a *second* change to the same function —
   flagging it rather than bundling it silently.
4. **The split witness decays** (§4). Acceptable today; worth a note in provenance so a future
   uncorroborated state is visible rather than assumed-checked.

---

## 9. What this report did NOT do

No code changed. No fixtures re-recorded. No database written — `caliber.db` untouched. No
lens armed, no threshold moved, no test modified. Three read-only live probes were made (SEC
`companyconcept` ×3, FMP `/stable/splits` ×2); everything else ran against recorded fixtures.
