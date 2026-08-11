# Phase G — corporate-actions integrity: BUILD REPORT (G-1 → G-3, DARK)

**Built 2026-08-11** · G-1, G-2, G-3 COMPLETE AND DARK · **G-4 NOT ARMED, awaiting ruling**
Scoping report: `docs/g-scoping.md`. Suite 577 → **612 passed**. `caliber.db` md5 unchanged
at `54aa42e5`. Live verification via `--no-synthesis --db-path /tmp/g_scratch.db`.

> **The headline of the build is a defect the build itself introduced and the dark pass
> caught.** The restated series does not truncate — that is the point — so when it runs
> with an empty split list it emits the raw artifact with nothing holding it back: GOOG's
> 2022-03-31 reads **81.02%** against a ~4% norm. An empty list cannot distinguish "this
> issuer never split" from "we could not find out", and the second case is *strictly worse
> than today*. Closed by `restatement_blocked` (§4) before anything was armed.

---

## 1. G-1 — capture the filing date · GATE PASSED

`_extract_xbrl_facts` now records `first_filed` on every fact. Additive: the de-dup key
`(start, end, unit, value)` and the accession tie-break are untouched.

**EARLIEST wins, and it is carried across the accession tie-break.** A later filing
repeating a value verbatim did not restate it, so the value still carries its original
basis; a genuine restatement changes the number and lands in a different de-dup group.
Taking the latest date would read a repeated pre-split value as post-split and silently
skip its adjustment.

**Gate — resolution diff must be empty.** Measured on identical cached companyfacts,
before vs after the edit, across the golden five + four banks:

```
fields compared: 171   (9 tickers x 19 specs)
DIFFS: 0
GATE: PASS — resolution provably unmoved
```

Verified on the case that motivated it — GOOG's records around the 2022-07-18 split:

| period_end | value | accession | `first_filed` | basis |
|---|---|---|---|---|
| 2022-06-30 | 13,078,000,000 | -22- | 2022-07-27 | post-split |
| 2022-03-31 | 658,763,000 | -22- | 2022-04-27 | pre-split |
| 2021-12-31 | 13,242,000,000 | **-23-** | **2022-07-27** | post-split (restated) |
| 2021-12-31 | 662,121,000 | -22- | 2022-02-02 | pre-split (original) |
| 2021-09-30 | 664,682,000 | -21- | 2021-10-27 | pre-split |

Row 3 is why accession year was insufficient: the record carries a **-23-** accession but
first appeared in a **2022-07-27** filing. And rows 1–2 are both `-22-` while sitting on
opposite sides of the split.

---

## 2. G-2 — split acquisition + corroboration · GATE PASSED

Three witnesses, per the ruling; **ratio corroborated 2-of-3, date always from FMP**.
New: `adapters/fmp_adapter.fetch_splits`, `core/corporate_actions`, and one concept added
to the EDGAR pull (`StockholdersEquityNoteStockSplitConversionRatio1`), deliberately kept
**out of FIELD_SPECS** so the 19-spec coverage counts and the cross-check are unmoved, and
excluded from the staleness clock so a corporate action cannot move every field's
freshness gate.

**Live agreement table, all nine tickers:**

| Ticker | in-scope split | witnesses | out-of-scope | verdict |
|---|---|---|---|---|
| **GOOG** | 2022-07-18 20:1 | **3/3** fmp + restatement + tagged | 1 (2014) | corroborated |
| **NOW** | 2025-12-18 5:1 | **3/3** fmp + restatement + tagged | 0 | corroborated |
| **C** | 2011-05-09 0.1:1 | **2/3** fmp + tagged | 8 | corroborated |
| **V** | 2015-03-19 4:1 | **1/3** fmp only | 0 | **REFUSED, flagged** |
| MU / WU / JPM / BK / USB | none in scope | — | 3/0/4/5/8 | no-op |

Measured agreement is far inside tolerance: GOOG 20 vs **19.99937**, NOW 5 vs **5.00001**.

**THE SCOPE HORIZON — a design addition the gate forced.** EDGAR's XBRL record begins
~2009, so a pre-XBRL split can *never* earn a second witness: MU's are 1994–2000, JPM's
1982–2000, USB's 1979–2001. Demanding 2-of-3 for those would leave five of nine tickers
permanently uncorroborated and force a withhold — strictly worse than today, over splits
that provably cannot move a number (`split_factor` compares ex-date against a filing date
and would multiply by 1.0 regardless). Splits predating the oldest share filing are
therefore classed **out-of-scope**, not uncorroborated, and are silent. Without this the
report emitted 33 alarming NOTE lines across the nine and would have desensitised the one
warning that matters — V's.

---

## 3. G-3 — filed-date restatement · PER-QUARTER GATE PASSED

`own_history_restated` in `core/valuation_anchors`. No discontinuity inference, no `break`:
every share count is multiplied onto today's basis by the filing date it first appeared
under. Robust to *which* duplicate a period-end resolves to — the factor comes from the
chosen record's own filing date, so the restated and as-filed copies land on the same
number (asserted).

**GOOG — every existing quarter identical, three recovered:**

| period | live | restated | delta | factor | first_filed |
|---|---|---|---|---|---|
| 2026-06-30 … 2022-09-30 (16 rows) | — | — | **+0.00** | 1 | — |
| 2022-06-30 | 5.03 | 5.03 | **+0.00** | 1 | 2022-07-27 |
| 2022-03-31 | — | **4.05** | NEW | **20** | 2022-04-27 |
| 2021-12-31 | — | **3.97** | NEW | 1 | 2022-07-27 |
| 2021-09-30 | — | **3.99** | NEW | **20** | 2021-10-27 |

17 → 20 quarters, median 4.43% → 4.34%. **The three recovered quarters land at
3.97/4.05/3.99 against a ~4% norm — the naive rule's 0.25% / 0.20% signature is absent.**
That is the check that matters; the median would have passed either way.

**NOW — 2 → 19 quarters**, all recovered at factor 5, series 0.18% → 1.63%, median 0.78%.

**All nine, quarter-for-quarter:** only GOOG and NOW move. MU, V, WU, JPM, BK, USB, C are
identical point for point (C has a corroborated 2011 split but no fact in the window
predates it, so it correctly applies to nothing). **Zero existing quarters moved on any
ticker** — the restatement is purely additive.

**Dark surface wired at both boundaries** (`evaluate.py`, `batch/runner.py`), reporting per
quarter, applying nothing. Skipped in fixture mode — recorded fixtures predate G-1 and
carry no filing date, so reporting on them would be a guess dressed as a measurement.
Live proof:

```
[NOW]  [SPLITS] 1 corroborated, 0 uncorroborated, 0 out-of-scope (horizon 2015-02-27)
       OK 2025-12-18  5:1  witnesses=3/3 [fmp_splits,edgar_restatement,edgar_tagged_ratio]
       [G-3 DARK] own-history 2 -> 19 quarters, 17 recovered, 0 lost, 0 existing moved
[GOOG] [G-3 DARK] own-history 17 -> 20 quarters, 3 recovered, 0 lost, 0 existing moved
[MU]   [G-3 DARK] own-history 15 -> 15 quarters, 0 recovered, 0 lost, 0 existing moved
[V]    !! 2015-03-19  4:1  witnesses=1/3 [fmp_splits]
       [G-3 DARK] restatement REFUSED: 1 in-scope split(s) uncorroborated (2015-03-19)
                  — 2-of-3 witnesses required — the truncated series stands
```

---

## 4. The trap the dark pass caught — `restatement_blocked`

Because the restated path has no truncation to fall back on, an **empty** split list is
not a safe default. Measured on GOOG with `events=[]`:

```
2022-06-30   5.03%
2022-03-31  81.02%   <-- the exact artifact Phase G exists to remove
2021-12-31   3.97%
2021-09-30  79.72%
```

An empty list is ambiguous between *"this issuer never split"* and *"we could not find
out"*, and those must not be conflated. `restatement_blocked` refuses the restated series
whenever the split state is not established:

- split record unavailable → refuse
- any **in-scope** split uncorroborated (V) → refuse
- no splits at all, known → **allowed** (a known-empty state is safe)

`own_history_restated` takes the **report**, not a list of events, so it cannot be called
with the ambiguous empty list at all. On refusal it returns empty and the caller keeps the
truncated series — lossy but honest. Pinned by `TestRestatementRefusal`.

**This is the argument for dark-before-arm, restated.** The fix was correct on both
tickers it was built for and would still have regressed the pipeline on the third.

---

## 5. STOP — G-4 arm gate, open items for the ruling

Nothing is armed. The live anchor still comes from `own_history_earnings_yields`.

1. **ARM?** Per `docs/g-scoping.md` §6 the expected armed diff is **zero score movement on
   all nine**, because own-history reaches a score only through the cyclical lens and MU
   (the only cyclical name) has no truncation. The value is latent-trap removal and GOOG
   accuracy, not score movement.
2. **Fixture-mode contract at arm.** Recorded fixtures carry no `first_filed`, so the armed
   path must pass `None` → refused → truncation. Offline golden behaviour is then
   **unchanged**, but the offline baseline diverges from live for GOOG and NOW. Recommend
   accepting the divergence and recording it, rather than re-recording EDGAR fixtures
   (a deliberate baseline move) to close a gap in a degraded mode.
3. **V stays refused** under the 2-of-3 ruling. It has no usable series anyway (0 quarters),
   so nothing is lost today — but a corroborated-only rule means a future single-witness
   split silently keeps the truncated series. That is the conservative choice and it is
   what the ruling says; flagging it so the consequence is on record rather than discovered.
4. **Two tests flip at arm**, the JPM-cash-tag pattern:
   `test_series_truncates_at_a_split_boundary`, `test_a_recent_split_can_cost_the_anchor_entirely`.

---

## 6. Phase H — trailing-only expansion: cost / value (requested, for sequencing vs EDGAR)

Own-history is trailing-earnings-only, which is **15 of the 17 missing readings** — far
more than G's one cell. Extending it lifts the ceiling from 4/20 to **16/20** (4 metrics ×
the 4 tickers that have a share series; V is excluded structurally). The value is not the
cell count, it is **which lenses gain an issuer-referenced discriminator**: today own-history
reaches only the **cyclical** lens, i.e. MU alone among the nine. An **FCF** own-history
series would give the **compounder** lens its first own-history anchor — that is GOOG, V and
WU, three of the golden five and the most common lens in the universe — and an **EBITDA**
series would do the same for **standard**. Forward earnings is worth nothing (no lens is
anchored on it) and growth gains nothing either (rate-shifted, it does not consume the
panel), so H is really two legs, not four. On cost, **the FCF leg is cheap and should be
sequenced first**: `operating_cashflow` and `capex` are already flow specs, so `ttm_series`
works on them today — measured coverage is **24 overlapping quarters for MU, GOOG, NOW and
WU** (V has no capex tag, its existing accepted limit), and EV needs only the cash and debt
instants that already resolve. The **EBITDA leg is the expensive one**: there is no D&A
spec, so it needs a new synonym chain plus the EV build-out, and EBITDA tagging varies far
more across issuers than cash-flow tagging. Sequencing view: **H's FCF leg is higher value
per unit of work than further EDGAR expansion** — it deepens the aggregation rule on tickers
already onboarded and turns MIN from a two-market-anchor rule into a genuine three-anchor
one for the majority lens, whereas EDGAR expansion adds breadth to a panel that is still
independence-narrowed 85% of the time. The EBITDA leg can wait behind EDGAR.

---

## 7. What changed

| File | Change |
|---|---|
| `adapters/edgar_adapter.py` | `first_filed` capture (earliest-wins) · `_earliest` · corporate-action concept pull, excluded from staleness clock · `ResolvedField.first_filed` on series |
| `adapters/fmp_adapter.py` | `fetch_splits` (cached, returns empty rather than raising) |
| `core/corporate_actions.py` | NEW — witnesses, corroboration, scope horizon, `split_factor`, `restatement_blocked` |
| `core/valuation_anchors.py` | `own_history_restated` (dark) · `run_dark_split_restatement` |
| `evaluate.py`, `batch/runner.py` | dark surface wired at both boundaries, live-only |
| `tests/test_corporate_actions.py` | NEW — 35 tests: witnesses, corroboration, horizon, per-point restatement, refusal guard, price-depth pin |

**Price-depth pin (ruled, done):** `TestPriceHistoryDepthPin` asserts the recorded FMP
fixtures span ≥4 years. `fetch_payload` requests `limit=365` and FMP returns ~1,255 rows;
the entire depth of the own-history anchor rests on that limit being ignored. The fixtures
are captured through the adapter's own live fetch path, so the day a re-record brings back
a one-year series this fails — at the deliberate baseline-move gate, which is where it
should surface. A second test pins the 4-year threshold to `MIN_HISTORY_POINTS` rather than
to a magic number.

---

# G-4 — ARMED (2026-08-11). PHASE G CLOSED.

Ruled ARM on correctness, not score movement: GOOG's series was known-wrong and feeds the
binding anchor class. `restatement_blocked` and the scope horizon both **RATIFIED**.

## What arming changed

`own_history_series(edgar, price_history, split_report)` now selects the basis and
**returns it**: the restated series when the split state is established, the truncated one
otherwise. `compute_panel`/`build_panel` take the split report; both boundaries pass it.
The basis is stamped on the anchor reading's note (`basis=split_restated` /
`basis=truncated (<reason>)`) — a panel anchor built on a truncated series is a different
measurement from one built on a restated series, and provenance has to say which.

`fetch_splits` returns **`None` for UNKNOWN and `[]` for "none exist"**, and `splits` joined
`fetch_payload` so the recorder captures it through the one path production requests.

## ARMED DIFF — live, all nine. **ZERO SCORES MOVED.**

| Ticker | lens | quarters pre → armed | basis | own-hist pre → armed | score | binding anchor |
|---|---|---|---|---|---|---|
| MU | cyclical | 15 → 15 | split_restated | 5.75 → 5.75 | **3 → 3** | own_history |
| GOOG | compounder | **17 → 20** | split_restated | **4.43 → 4.34** | **1 → 1** | risk_free |
| V | compounder | 0 → 0 | **truncated (refused)** | — | **2 → 2** | sector |
| NOW | growth | **2 → 19** | split_restated | **— → 0.78** | **3 → 3** | risk_free |
| WU | compounder | 20 → 20 | split_restated | 16.27 → 16.27 | **5 → 5** | sector |
| JPM / BK / USB / C | bank | unchanged | split_restated | unchanged | **unchanged** | n/a (no panel) |

Matches the scoping prediction (`docs/g-scoping.md` §6) exactly: own-history reaches a score
only through the cyclical lens, and MU — the only cyclical name — had no truncation.

**Per-quarter, reviewed (standing per-point ruling):** GOOG — all 17 pre-existing quarters
`+0.00`, three recovered at 4.05 / 3.97 / 3.99. NOW — both pre-existing quarters `+0.00`,
seventeen recovered spanning 0.18–1.10. **Identical to the dark diff**, as expected.

## Fixture re-record (ruled: recorder discipline wins over recorded divergence)

GOOG and NOW re-recorded through `tools.record_edgar_fixture` and `tools.record_fmp_fixture`.
Offline now reproduces live exactly — GOOG 20 quarters @ 4.34, NOW 19 @ 0.78.

**Resolution diff reviewed, 1 field of 38 moved:** GOOG `total_debt_reported`
`no_tag → stale_tag`. Value withheld either way, the field is DARK, and the movement is the
one already recorded live at D-5 — GOOG does file
`LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` but abandoned it in 2024,
so the 450d gate withholds it and `stale_tag` is strictly more accurate. The fixture had
predated the D-5 chain extension; it has now caught up. NOW: zero movement.
`test_reported_debt_total_absent_is_typed` updated to pin the distinction per ticker —
`no_tag` (never filed) vs `stale_tag` (filed and abandoned) must not be conflated or the
tag-migration signal is lost.

MU, V, WU and the four banks were deliberately **not** re-recorded: their fixtures carry no
split data, so they return `None` → refused → truncated, and their truncated series already
equals their restated one (no in-scope discontinuity). No drift to close.

## Tests flipped

- `test_series_truncates_at_a_split_boundary` → **`test_the_truncating_series_is_now_the_FALLBACK_and_still_truncates`**. The truncating function is unchanged and still pinned, because it is the only thing standing between an unknown split and GOOG's ~81% quarters.
- `test_a_recent_split_can_cost_the_anchor_entirely` → **`test_a_recent_split_no_longer_costs_the_anchor`**. NOW's anchor is now AVAILABLE and stamped `split_restated`.
- Added `test_without_a_split_report_the_panel_keeps_the_truncated_basis` — `None` is UNKNOWN, never "no splits".

Suite **613 passed**. `caliber.db` md5 unchanged `54aa42e5`.

## Phase G closed — what it delivered

Mixed-basis rule (basis at filing date) · 2-of-3 witness corroboration with the date from FMP
· scope horizon for pre-XBRL splits · `restatement_blocked` · the `limit=365` pin. Own-history
coverage **3/20 → 4/20 readings, 7/9 → 8/9 tickers**. No score, E(R) or grade moved.
