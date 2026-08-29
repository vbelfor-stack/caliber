# PILLAR 5 — VALUATION
**Glass-box audit, 2026-08-29. Read-only. No fixes applied.**
HEAD `ff02e21` · suite 1091 · caliber.db md5 `69dc2328ee3af8a43d506b64665da39b` (unchanged).
Implementation: **`core/pillars.py:487-966`** (dispatcher + five lens functions) over
**`core/valuation_anchors.py`** (panel, anchors, ladders, bank instrument, rate shift).

**This is the only pillar that does not use the `pts / max_pts` scorecard.** Each lens
returns a 1-5 score directly from a ladder or a gate. It is also **the only pillar with a
hard refusal.**

---

## 1. EXACT COMPUTATION

### 1.1 Dispatch and the one hard refusal

`score_valuation(yf, fred, lens, panel)` (`core/pillars.py:487-522`):

1. **`if fred.rate_10y.is_missing(): raise RateUnavailable`** — checked **before** the lens
   dispatch so it binds all five lenses. `evaluate.py` exits 3; `batch/runner.py` persists
   `status='rate_unavailable'` and continues. **The only genuine refusal in the pillar set.**
   `0.0` is a rate (ZIRP), not a missing one.
2. Dispatch: `cyclical` · `compounder` · `bank` · `growth` · else `standard`.

Rate source: **FRED `DGS10`** (`fetch_fred`), not FMP. The single non-FMP pipeline input.

### 1.2 The valuation panel — three anchors, MIN aggregation

`compute_panel(yf, fred, edgar, sector_pe, lens)` (`core/valuation_anchors.py:487`) measures
every metric against every anchor. Everything is expressed as a **yield in percentage
points** so the anchors are commensurable.

| Anchor | Source | Grain |
|---|---|---|
| `risk_free` | **FRED `DGS10`** | spot |
| `sector` | FMP sector P/E snapshot, **per exchange** | spot |
| `own_history` | **EDGAR** TTM earnings + share count × FMP `price_history` | historical median |

| Metric | Built from | FMP field | Grain |
|---|---|---|---|
| `earnings_yield_trailing` | `100 / trailing_pe` | `ratios-ttm.priceToEarningsRatioTTM` | TTM |
| `fcf_yield` | `fcf_yield × 100` | `key-metrics-ttm.freeCashFlowYieldTTM` | TTM |
| `ebitda_yield` | `100 / ev_to_ebitda` | `key-metrics-ttm.evToEBITDATTM` | TTM |
| `earnings_yield_forward` | `100 / forward_pe` | **★★ `analyst-estimates.epsAvg`** | NTM | 

**Lens → metric** (`LENS_METRIC`, `:706`): compounder → `fcf_yield` · cyclical →
`earnings_yield_trailing` · standard → `ebitda_yield` · growth → `ebitda_yield` *(dark only —
`_valuation_growth` takes no panel)* · bank → `None`.

**Ladder** (`RATE_SPREAD_LADDER`, `:123`), on the spread in pp: `≥3.0 → 5` · `≥1.0 → 4` ·
`≥−1.0 → 3` · `≥−3.0 → 2` + `RICH` · `else 1` + `VERY-RICH`. The growth lens uses
`GROWTH_SPREAD_LADDER`, shifted one notch more generous.

**AGGREGATION: MIN across available anchors, RULED PERMANENT 2026-08-09** (`:786`,
`min(rated, key=lambda s: s.spread)`). The *least* favourable anchor binds.

**Narrowing is FLAG-ONLY** (`_panel_flags`, `core/pillars.py:543`): `PANEL-NARROWED`
(<3 anchors) and `PANEL-NARROWED-MARKET-ONLY` (survivors are all market-referenced).
Ruled flag-only because 17 of 20 measured readings were narrowed — a haircut would have been
a global recalibration through a side door.

### 1.3 Per-lens mechanisms — three different ones

| Lens | Mechanism | Panel? | Gate |
|---|---|---|---|
| **cyclical** | trailing earnings yield vs panel | yes | **peak/rollover CAPS at 2** |
| **compounder** | FCF yield vs panel; fallback EV/EBITDA ladder | yes | secular-decline flag only |
| **standard** | EBITDA yield vs panel; fallback EV/EBITDA then P/E ladder | yes | **negative-multiple sign gate** |
| **growth** | Rule-of-40 × EV/Revenue, **rate-shifted thresholds** | **no — deliberate** | none |
| **bank** | P/B vs justified P/B = ROE / CoE, CoE = 10Y + β×4.5pp | no | **excess ROE < 0 CAPS at 3** |

`ARMED_PANEL_LENSES = ("compounder","cyclical","standard")`; `ARMED_LENSES` adds `growth`
and `bank`. **"Armed" and "panel-scored" are deliberately different sets** (`:458-468`).

Rate shift (growth lens): `k = (4.0 + 4.5) / (rate + 4.5)`, clamped `[0.60, 1.80]`; a binding
clamp emits `RATE-SHIFT-CLAMPED`.

## 2. ★★ ANALYST / ESTIMATE-DERIVED INPUTS

**★★ `forward_pe` → `earnings_yield_forward` IS ANALYST-DERIVED** — built from
`analyst-estimates.epsAvg` (`adapters/fmp_adapter.py:443-448`). It is **computed into every
panel and no lens scores it**: `LENS_METRIC` maps no lens to
`METRIC_FORWARD_EARNINGS_YIELD`. It also sits in the `inputs` list of `_valuation_cyclical`
(`core/pillars.py:617`), so it **can lower the pillar's confidence via `min_conf` without
ever affecting the score.**

**Net: the Valuation pillar's SCORING path is analyst-free.** The cyclical basis was
explicitly **RULED TRAILING** in 2026-08-09 precisely to keep it that way — *"on a forward
basis MU scores 5 — maximally cheap, every anchor agreeing — at a cycle peak; that unanimity
IS the 2018 signature"* (`core/pillars.py:604-609`). **That ruling is the single best
precedent in the codebase for the analyst-contamination question this audit raises, and it
was already made once, for one lens.**

`beta` (bank lens, → CoE) is FMP single-source and uncorroborated; `_cap_beta_confidence`
(`:471`) caps the bank pillar at `medium` while it is in use. Not analyst-derived, but
recorded as the one other soft input.

## 3. STAGE HANDLING

- **Stage: IGNORED.** No lens reads `lifecycle_stage`.
- **`lens` IS FULLY LOAD-BEARING here** — it selects the function, the metric, the ladder and
  the gate. This is the one pillar where `lens` is not decorative. **`lens` is derived from
  SIC/industry, not from stage**, so a YOUNG pre-revenue name and a MATURE issuer in the same
  industry get the identical lens, ladder and gate.
- `lens_compatibility_flags` (`core/lifecycle.py:857`) records stage/lens mismatches
  (`YOUNG+compounder`, `DECLINE+growth`, `MATURE+growth`) as **flags only — it NEVER
  reassigns a lens** (order §8).

## 4. NEGATIVE / ZERO / MISSING HANDLING

**This pillar handles negatives better than any other, and it is the only one where the
reasoning was ruled explicitly.**

| Condition | Behaviour | Verdict |
|---|---|---|
| **`rate_10y` missing** | **`raise RateUnavailable`** | **fail-closed — the only true refusal** |
| negative multiple → yield | `_yield_from_multiple` returns **None** for `≤ 0` (`:177-183`) | fail-closed ✓ |
| standard lens, `ev_ebitda < 0` | `score = 1` + `NEGATIVE-MULTIPLE-CHEAP-RUNGS-WITHHELD` | fail-closed ✓ |
| standard lens, `pe < 0` | `score = 1` + same flag | fail-closed ✓ |
| standard lens, any negative + `score ≥ 4` | **capped to 3, applied LAST** so no input ordering routes around it (`:938-950`) | fail-closed ✓ |
| cyclical, peak/rollover | **CAPS at 2, never raises** | fail-closed ✓ |
| bank, excess ROE < 0 | caps at 3 | fail-closed ✓ |
| bank, no ROE or no beta | reports P/B, **does NOT score off it** + `BANK-INSTRUMENT-UNAVAILABLE` | fail-closed ✓ |
| **panel unavailable, no fallback** | **`score = 3` (neutral), silently** | **★★ fail-open** |
| panel narrowed to 1-2 anchors | scored anyway, flag only | **fail-open by ruling** |

**★★ FINDING A — `score = 3` IS THE SILENT DEFAULT ON EVERY LENS.** Each lens function opens
with `score = 3` (`:626`, `:673`, `:742`, `:801`, `:871`) and returns it untouched if no
anchor and no fallback resolves. **There is no flag for "nothing was measured."** A
neutral 3 from a full three-anchor panel and a neutral 3 from total measurement failure are
indistinguishable in `pillars_json`. Contrast the bank lens, which *does* emit
`BANK-INSTRUMENT-UNAVAILABLE` when its instrument is missing — **the pattern exists in the
codebase and was applied to exactly one lens.** *Not the same severity as an
absence-is-optimal inversion — 3 is neither the best nor the worst score — but it is
unflagged.*

**★★ FINDING B — THE CYCLICAL GATE FIRES AND ITS OWN EVIDENCE FLAG IS FILTERED OUT.**
`dark_lens_score` emits `CYCLE-GATE-CAP-PEAK` / `CYCLE-GATE-CAP-ROLLOVER` when it caps a
score (`core/valuation_anchors.py:814`). But `_valuation_cyclical` propagates only
`RICH*`/`VERY-RICH*` and `PANEL-NARROWED*`:
```python
flags.extend(f for f in ps.flags if f.startswith(("RICH", "VERY-RICH")))
flags.extend(_panel_flags(ps))
```
**`CYCLE-GATE-CAP-*` is dropped.** The lens separately appends
`LOW-PE-AT-CYCLE-PEAK-NOT-CHEAP`, so a peak *condition* is visible — but the record that the
gate **actually moved a score** is discarded. **MU's row proves the gate fired and carries no
gate flag (§6).** *The score is correct; the audit trail is lossy.*

**★ FINDING C — `haircut_score` IS COMPUTED ON EVERY PANEL AND APPLIED TO NOTHING.**
`:803-805` computes a one-rung independence haircut, documented "MEASURED not applied". No
production path reads it — only a diagnostic print (`:870`) and `tools/probe_d3_lenses.py`.
**Correct per the flag-only ruling; listed in §7 so it is not mistaken for live behaviour.**

**★ FINDING D — SECTOR ANCHOR IS EXCHANGE-SCOPED.** Already on the CLAUDE.md roadmap
(Technology/NASDAQ 48.1x vs Technology/NYSE 41.4x). Re-confirmed reachable: `sector` is a
binding anchor on live rows — **it binds V below.** An economically arbitrary term inside an
armed anchor. Unruled.

## 5. NOT APPLICABLE (E(R) section)

## 6. WORKED EXAMPLES — LAST PRODUCTION EVALUATION (2026-08-28 acceptance run)

All three carry `rate_10y = 4.67` from `FRED`, confidence `high`.

### QBTS — eval id 289, lens `cyclical` → `_valuation_cyclical`

| Input (provenance order `[trailing_pe, forward_pe, gross_margin, rate_10y]`) | Value |
|---|---|
| `trailing_pe` | **−23.950704225352112** |
| `forward_pe` | **ABSENT** (3 rows persisted, not 4) |
| `gross_margin` | **0.641851106639839** |
| `rate_10y` | **4.67** (`FRED`, high) |

**Path, step by step:**
1. `_cycle_position_from_trajectory` → gross-margin trajectory tag `rolling_over` →
   `cycle_pos = "contracting/late-cycle"`, `warn_type = "rollover"`.
2. `gm 0.6419 > 0.55` and `warn_type` in (peak, rollover) → `CYCLE-PEAK-MARGINS`.
3. `_panel_score` → metric is `earnings_yield_trailing` →
   `_yield_from_multiple(−23.95)` returns **None** (the `≤ 0` guard) → no rated anchor →
   `panel_score = None`.
4. **else branch**: `warn_type == "rollover"` → `MARGINS-CONTRACTING-EARNINGS-DECLINING`,
   **`score = 2`**.

Stored: **2** ✓ · flags `['CYCLE-PEAK-MARGINS', 'MARGINS-CONTRACTING-EARNINGS-DECLINING']` ✓
Rationale: *"Cyclical. Cycle: contracting/late-cycle. Trailing earnings yield unavailable.
10Y rate 4.67%."* ✓

**★ Note what carried QBTS's valuation: the negative-PE guard REFUSED to score it, and the
rollover gate then set 2 by itself.** This is the fail-closed path working — and it is the
exact input (`trailing_pe = −23.95`) that the **Growth** pillar silently deleted a leg for,
scoring QBTS **5**. *Same number, same evaluation: Valuation refuses it, Growth is rewarded
by its absence.*

### MU — eval id 286, lens `cyclical` → `_valuation_cyclical`

| Input | Value |
|---|---|
| `trailing_pe` | **20.81812095514394** → earnings yield **4.804%** |
| `forward_pe` | **3.5246155589979975** → forward yield 28.4% — **computed, never scored** |
| `gross_margin` | **0.7256906750559408** |
| `rate_10y` | **4.67** |

1. Trajectory tag `accelerating` with MRQ gross margin > 0.65 →
   `cycle_pos = "accelerating-toward-peak"`, `warn_type = "peak"`.
2. `gm 72.57% > 55%` → `CYCLE-PEAK-MARGINS`.
3. Panel resolves; **binding anchor `own_history`, binding spread `−1.0pp`** (MIN across
   anchors — own history is the least favourable).
4. Ladder: `−1.0 ≥ −1.0` → **raw panel score 3**.
5. **Cyclical gate**: `warn_type == "peak"` and `3 > 2` → **capped to 2**, and
   `CYCLE-GATE-CAP-PEAK` is emitted by `dark_lens_score` — **and then filtered out by the
   lens (Finding B).**
6. `LOW-PE-AT-CYCLE-PEAK-NOT-CHEAP` appended.

Stored: **2** ✓ · flags `['CYCLE-PEAK-MARGINS', 'LOW-PE-AT-CYCLE-PEAK-NOT-CHEAP']` ✓

**★ THE CAP IS PROVEN FROM THE STORED ROW, NOT ASSUMED.** No `RICH` flag is present. `RICH`
is emitted for any spread in `[−3.0, −1.0)`, so its absence means the raw ladder score was
**≥ 3**, while the stored score is **2** — therefore the gate demonstrably moved it. **This
is the MU-2018 guard doing exactly the job it was built for, on a live row: a 20.8x trailing
P/E at peak semiconductor margins, refused the "cheap" reading.** And it is worth putting
beside the other four pillars: **the same MU evaluation scores 5 / 5 / 4 / 5 on Business
Quality, Financial Health, Management and Growth, and 2 on Valuation.** Four pillars read
peak-cycle earnings as excellence; one of the five knows what it is looking at.

### V — eval id 294, lens `compounder` → `_valuation_compounder`

| Input (order `[fcf_yield, ev_to_ebitda, revenue_growth, rate_10y]`) | Value |
|---|---|
| `fcf_yield` | **0.02949336969219439** → **2.949%** |
| `ev_to_ebitda` | **24.880205365248468** |
| `revenue_growth` | **0.1133997661860491** (11.34%) |
| `rate_10y` | **4.67** |

1. `_growth_weak` = `0.1134 < 0.03`? **No** → the secular-decline branch cannot fire.
2. Panel resolves on `fcf_yield`; **binding anchor `sector`, spread `−2.6pp`**.
3. Ladder: `−2.6 ≥ −3.0` → **score 2**, flag `RICH` scoped to the anchor → **`RICH-VS-SECTOR`**.
4. `anchor_count < 3` and survivors ⊆ {`risk_free`, `sector`} → **`PANEL-NARROWED-MARKET-ONLY`**
   — i.e. **V's `own_history` anchor is absent**, so the two survivors are two views of the
   same market rather than two independent checks.
5. `haircut_score` = `2 − 1` = **1**, computed and **not applied** (Finding C).

Stored: **2** ✓ · flags `['RICH-VS-SECTOR', 'PANEL-NARROWED-MARKET-ONLY']` ✓
Rationale: *"Quality compounder (asset-light network) lens. FCF yield vs sector (−2.6pp).
10Y rate 4.67%."* ✓

**★ V IS THE LIVE CASE FOR THREE SEPARATE RECORDED ITEMS AT ONCE:** the exchange-scoped
sector anchor is **binding** on it (Finding D); the independence haircut is **computed and
discarded** on it (Finding C); and its `fcf_yield` of **2.949%** is the same number that the
**Financial Health** pillar's independent `freeCashFlow ÷ market_cap` computation put
**above** its own 3% bonus threshold (see `02-financial-health.md` §6). *One company, one
concept, two numbers, two pillars, opposite sides of a threshold.*

## 7. BUILT BUT NEVER READ

- **`METRIC_FORWARD_EARNINGS_YIELD`** — computed into every panel (`:508`), **mapped to no
  lens** in `LENS_METRIC`. The panel's only analyst-derived metric is never scored.
- **`haircut_score`** — computed on every `DarkLensScore`, applied to no production score.
  Diagnostic print and `tools/probe_d3_lenses.py` only. Correct per ruling; listed so it is
  not mistaken for live behaviour.
- **`LENS_METRIC["growth"] = METRIC_EBITDA_YIELD`** — unreachable in production:
  `_valuation_growth` takes no panel and never calls `_panel_score`. Reachable only through
  `dark_lens_score` in dark/probe runs. **The panel mapping for growth was REJECTED
  PERMANENTLY** (`:453-455`); the map entry survives it.
- **`enterprise_value`** — fetched, currency-guarded as score-bearing, read by nothing (only
  the `ev_to_*` ratios are used). Also listed in `02-financial-health.md` §7.
- **`_analyze_insiders` cluster branches** — see `03-management.md` §7.
