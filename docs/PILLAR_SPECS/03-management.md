# PILLAR 3 — MANAGEMENT & CAPITAL ALLOCATION
**Glass-box audit, 2026-08-29. Read-only. No fixes applied.**
HEAD `ff02e21` · suite 1091 · caliber.db md5 `69dc2328ee3af8a43d506b64665da39b` (unchanged).
Implementation: **`core/pillars.py:272-343`, `score_management(yf, lens)`**, with
`_analyze_earnings` (`:51-86`) and `_analyze_insiders` (`:89-123`).

---

## ★★ THE HEADLINE

**THIS PILLAR CONTAINS NO MANAGEMENT ACTION AND NO CAPITAL ALLOCATION.**

Its 6 points are: **4 from analyst-estimate beats** and **2 from an insider leg whose input
is a hard-coded empty list**. There is no buyback measure, no dilution measure, no dividend
measure, no reinvestment measure, no insider measure that can ever fire. The one capital-
allocation signal actually present in the payload — `shares_outstanding` — is carried in
`inputs` and **scores nothing**.

So the pillar named *Management & Capital Allocation* measures **how often a company beats
sell-side EPS estimates**, plus a constant. Of the three golden-set rows below, **every one
scores exactly 1 free point from the dead insider leg.**

---

## 1. EXACT COMPUTATION

| Leg | Input | FMP endpoint | FMP field | Grain | Ladder |
|---|---|---|---|---|---|
| 1 | `beat_rate` | `earnings?limit=8` | `epsActual` vs `epsEstimated` | **QUARTERLY, ≤7 usable** | ≥0.75 → 2 · ≥0.50 → 1 · else 0 |
| 1b | trend bonus | same | same | same | `improving` → `pts = min(pts+1, max_pts)` |
| 2 | `avg_surprise` | same | same | same | ≥5 → 2 · ≥0 → 1 · else 0 + `AVERAGE-EARNINGS-MISS` |
| 3 | `insider_signal` | **NONE — hard-coded `[]`** | — | — | `cluster_buy` → 2 · `neutral`/`routine_sell`/**`no_data`** → **1** · `cluster_sell` → 0 |
| — | `shares_outstanding` | `shares-float` | `outstandingShares` | spot | **NEVER SCORED** |

`beat_rate` = fraction of usable quarters with `surprisePercent > 0`.
`avg_surprise` = **unweighted arithmetic mean** of `surprisePercent`.
`surprisePercent` = `(epsActual − epsEstimated) / |epsEstimated| × 100`, computed at
`adapters/fmp_adapter.py:371`, **with `0.0` substituted when `epsEstimated == 0`**.
`trend` = split-half mean comparison with a ±2pp deadband (`core/pillars.py:72-84`); needs
`n ≥ 4` or it returns `insufficient`.

Max points: 2 (beat) + 2 (surprise) + 2 (insider) = **6**, and **`max_pts += 2` for the
insider leg is UNCONDITIONAL** (`:312`) — outside any presence check, unlike every other leg
in the engine.

## 2. ★★ ANALYST / ESTIMATE-DERIVED INPUTS — **4 OF 6 POINTS, THE HIGHEST IN THE ENGINE**

- **`beat_rate` (2 pts) — ★★ fully analyst-derived.** Measured against `epsEstimated`.
- **`avg_surprise` (2 pts) — ★★ fully analyst-derived.** Same source.
- **The `improving` bonus — ★★ analyst-derived**, and it is the **same `trend` value the
  Growth pillar also spends a point on** (`core/pillars.py:396`). **The identical
  analyst-surprise signal is scored twice, in two pillars, from one computation.**

This is not "quality of management" — it is **the sell-side's ability to forecast this
company**, which is largely a function of guidance policy and coverage density. A company
that guides conservatively scores well by construction.

## 3. STAGE HANDLING

- **Stage: IGNORED.**
- **★ `lens` IS IN THE SIGNATURE AND NEVER READ** — `method=lens` only (`:340`). Third
  instance of the pattern (Growth's `edgar`, Financial Health's `lens`, this).

## 4. NEGATIVE / ZERO / MISSING HANDLING

| Condition | Behaviour | Verdict |
|---|---|---|
| no earnings records | `beat_rate`/`avg_surprise` = None → both legs dropped | fail-open |
| `epsEstimated == 0` | **`surprise` fabricated as `0.0`** | **★★ fail-open, invented datum** |
| `epsEstimated ≈ 0` | surprise unbounded (±hundreds of %) into an unweighted mean | **★★ fail-open** |
| `avg_surprise < 0` | 0 of 2 + `AVERAGE-EARNINGS-MISS` | fail-closed ✓ |
| `n < 4` quarters | `trend = insufficient` → no bonus, no penalty | neutral |
| **insider data absent (always)** | **`no_data` → +1 of 2**, `max_pts += 2` unconditionally | **★★ fail-open, permanent** |
| all legs missing | score 3 (neutral) — but unreachable, insider always adds 2 to `max_pts` | n/a |

**★★ FINDING A — THE INSIDER LEG IS STRUCTURALLY DEAD AND PAYS EVERY COMPANY THE SAME FREE
POINT.** `adapters/fmp_adapter.py:508`:
```python
insider_transactions: List[Dict] = []  # FMP stable has no free insider endpoint
```
The list is **hard-coded empty for every ticker on every run**. `_analyze_insiders([])`
returns `"no_data"` (`core/pillars.py:96`), which `:316` groups with `neutral` and
`routine_sell` and awards **1 point**. Meanwhile `max_pts += 2` is unconditional.

Consequences, all three of them real:
1. **Every evaluation in the database carries exactly `insider_signal = no_data` and +1/2.**
   Confirmed on all three worked examples below, and it will be true of all 28.
2. **A permanently absent input is neutral-filled rather than refused** — a direct inversion
   of the standing rule *"a guard that cannot measure DENIES the tag it guards; absence must
   never be privately optimal."* Here absence is not merely permitted, it is **paid**.
3. **It dilutes the real signal by a third.** Every score is dragged toward the middle by a
   constant 1-of-2. `_analyze_insiders` itself (35 lines, `cluster_buy` detection, option-
   exercise filtering) is **entirely unreachable code**.

**★★ FINDING B — THE `improving` BONUS IS AWARDED TO WEAK BEATERS AND DENIED TO PERFECT
ONES.** `core/pillars.py:291-293`:
```python
if trend == "improving":
    pts = min(pts + 1, max_pts)
```
`max_pts` at that moment is **2** — only the beat leg has been added; the surprise and
insider legs come later. So the cap is against the *running* subtotal, not the final one:

- **beat_rate = 1.00** → `pts = 2`, bonus = `min(2+1, 2) = 2` → **bonus swallowed, worth 0.**
- **beat_rate = 0.29** → `pts = 0`, bonus = `min(0+1, 2) = 1` → **bonus worth a full point.**

**A company that beat every quarter gets nothing for an improving trend; a company that
missed five of seven gets a point for it.** MU (beat 100%, trend improving) and QBTS (beat
29%, trend improving) are the two live sides of this in §6 — the flag
`BEAT-TREND-IMPROVING` is emitted for both, and it is worth 0 to one and 1 to the other.
An order-of-evaluation defect, not a design decision. **Needs a ruling.**

**★★ FINDING C — THE NEAR-ZERO-ESTIMATE OUTLIER IS LIVE, NOT THEORETICAL.** The Growth spec
recorded this as a structural exposure. **It has fired: QBTS's stored `avg surprise` is
−245.2%.** With pre-earnings EPS estimates near zero, `(actual − est)/|est|` explodes, and an
unweighted mean of ≤7 such values is not a statistic. That same corrupted series then set
`trend = improving`, which paid QBTS a point here **and** a point in Growth (§2).

## 5. NOT APPLICABLE (E(R) section)

## 6. WORKED EXAMPLES — LAST PRODUCTION EVALUATION (2026-08-28 acceptance run)

Provenance order is `inputs` at `core/pillars.py:322`:
`[beat_prov, insider_prov, shares_outstanding]`.

### QBTS — eval id 289

| Input | Value |
|---|---|
| `beat_rate` | **0.2857142857142857** (2 of 7) |
| `avg_surprise` | **−245.2%** (from the rationale string) |
| `trend` | `improving` |
| `insider_signal` | **`no_data`** |
| `shares_outstanding` | 367,269,074 — **unscored** |

| Leg | pts | max |
|---|---|---|
| beat 0.286 < 0.50 | 0 | 2 |
| trend `improving` → `min(0+1, 2)` | **+1** | 2 |
| avg surprise −245.2 < 0 → `AVERAGE-EARNINGS-MISS` | 0 | 4 |
| insider `no_data` → free point | **+1** | 6 |
| **TOTAL** | **2** | **6** |

`round(1 + (2/6)×4)` = `round(2.333)` = **2**. Stored: **2** ✓
Flags: `BEAT-TREND-IMPROVING`, `AVERAGE-EARNINGS-MISS` ✓

**Half of QBTS's 2 points come from the two defects in §4** — the swallowed-bonus inversion
paying out on a 29% beat rate, and the dead insider leg.

### MU — eval id 286

| Input | Value |
|---|---|
| `beat_rate` | **1.0** (7 of 7) |
| `avg_surprise` | **+15.7%** |
| `trend` | `improving` |
| `insider_signal` | **`no_data`** |
| `shares_outstanding` | 1,129,390,000 — **unscored** |

| Leg | pts | max |
|---|---|---|
| beat 1.00 ≥ 0.75 | +2 | 2 |
| trend `improving` → `min(2+1, 2) = 2` — **BONUS SWALLOWED** | **+0** | 2 |
| avg surprise +15.7 ≥ 5 | +2 | 4 |
| insider `no_data` | +1 | 6 |
| **TOTAL** | **5** | **6** |

`round(1 + (5/6)×4)` = `round(4.333)` = **4**. Stored: **4** ✓
Flags: `BEAT-TREND-IMPROVING` ✓ — **emitted, and worth nothing.**

**MU is the live proof of Finding B.** A perfect 7-of-7 beat record with a genuinely
improving surprise trend scores **4, not 5**, purely because the bonus was capped against a
running subtotal of 2. Had the same trend appeared on a weaker beat record it would have
counted.

### V — eval id 294

| Input | Value |
|---|---|
| `beat_rate` | **1.0** (7 of 7) |
| `avg_surprise` | **+3.1%** |
| `trend` | `stable` |
| `insider_signal` | **`no_data`** |
| `shares_outstanding` | 1,867,047,211 — **unscored** |

| Leg | pts | max |
|---|---|---|
| beat 1.00 ≥ 0.75 | +2 | 2 |
| trend `stable` → no bonus, no penalty | — | 2 |
| avg surprise +3.1 — ≥0 but <5 | +1 | 4 |
| insider `no_data` | +1 | 6 |
| **TOTAL** | **4** | **6** |

`round(1 + (4/6)×4)` = `round(3.667)` = **4**. Stored: **4** ✓ · flags `[]` ✓

**V and MU both score 4 on Management.** V beats by ~3% on a mature payments network; MU
beats by ~16% at a semiconductor cycle peak with an improving trend. The pillar cannot
separate them, because MU's advantage lands entirely in the one bonus that was swallowed.

## 7. BUILT BUT NEVER READ

- **`insider_transactions`** — the field exists on `TickerData` (`core/datatypes.py:71`),
  is populated with a hard-coded `[]`, and drives `_analyze_insiders`, **35 lines of
  unreachable analysis** (`cluster_buy`, `cluster_sell`, `routine_sell` are all dead
  branches). The only reachable return is `"no_data"`.
- **`shares_outstanding`** — fetched from `shares-float`, EDGAR-cross-checked
  (`core/edgar_cross_check.py:165`), persisted to `field_provenance`, and **scores nothing.**
  It is the single input in the whole payload from which dilution or buyback — actual capital
  allocation — could be measured, on the pillar named for it. Its only effect is `min_conf`.
- **`target_mean_price`** (`price-target-summary.lastMonthAvgPriceTarget`) — the sell-side
  consensus target. Fetched, currency-guarded as score-bearing
  (`core/reporting_currency.py:184`), and **read by nothing anywhere in the runtime.** Noted
  here because it is the natural companion to `analyst_count`, which the Growth pillar also
  fetches and does not score. See `05-expected-return.md` §7 — the one non-LLM price target
  in the payload is discarded while E(R) is built entirely from LLM-authored ones.
