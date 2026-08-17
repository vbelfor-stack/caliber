# L-2b — SIGN GATE, LENS MAP REWRITE, AND SIX SUPERSEDING RE-RUNS

**Order:** L-2b, ruled 2026-08-17 · **Commits:** `139e624` (fixes) + this one · **Suite:** 789 → **809**
**md5:** `e7be34a9315bbd03e4711dcce6c57576` → **`24df814597b6bab52b979e7fee6ca034`** (both WAL-checkpointed)
**§5 step 3 not armed. Step 4 blocked behind feed coverage, per ruling 4.**

## 1. Superseded rows — old → new

| ticker | old id | new id | lens | avg | E(R) |
|---|---|---|---|---|---|
| **RKLB** | 244 | 266 | standard → standard | **3.4 → 2.6** | −8.26 → **−8.26 (unchanged)** |
| **LLY** | 242 | 267 | **cyclical → compounder** | 3.8 → 3.8 | −4.74 → **+7.07** |
| **CAT** | 239 | 268 | **standard → cyclical** | 3.6 → 3.4 | −0.75 → **−4.38** |
| **BE** | 238 | 269 | **cyclical → growth** | 3.2 → 3.4 | −15.19 → −12.62 |
| **IONQ** | 248 | 270 | **cyclical → growth** | 2.8 → 3.0 | −21.43 → −19.19 |
| **INFQ** | 252 | 271 | **cyclical → growth** | 2.4 → 2.2 | −22.26 → −29.16 |

Every new row carries `supersedes_id` and a stated reason. No row was edited or deleted.

## 2. The Valuation cell — the pillar both fixes touch

| ticker | old → new | flag movement |
|---|---|---|
| **RKLB** | **5 → 1** | gains `NEGATIVE-MULTIPLE-CHEAP-RUNGS-WITHHELD` |
| LLY | 2 → 2 | **loses `CYCLE-PEAK-MARGINS` and `LOW-PE-AT-CYCLE-PEAK-NOT-CHEAP`** |
| CAT | 3 → 2 | gains `RICH-VS-RISK-FREE` |
| BE | 1 → 2 | cyclical flags → `RULE40=49`, `RATE-SHIFT-K=0.93`, `HIGH-EV-REVENUE-MULTIPLE` |
| IONQ | 2 → 3 | loses `MARGINS-CONTRACTING-EARNINGS-DECLINING` → `RULE40=-212` |
| INFQ | 2 → 1 | loses `MARGINS-CONTRACTING-EARNINGS-DECLINING` |

**RKLB is the headline: 5 → 1.** The maximum "cheapest" rung is gone, and the row now says
why. **LLY is the quieter one and matters as much:** its score did not move, but it shed
`CYCLE-PEAK-MARGINS` and `LOW-PE-AT-CYCLE-PEAK-NOT-CHEAP` — a pharma major was being told it
was at a cycle peak. Those flags feed the synthesis prompt, which is visible in its E(R)
moving −4.74 → **+7.07**, the largest swing of the six.

## 3. A FINDING THAT QUALIFIES THE ORDER'S PREMISE — RKLB's E(R) did not move

The order said RKLB's *"E(R) on record is derived from a defective Valuation 5 and will grade
in 90 days as a fabricated call."* **Measured: the corrected run produced an E(R) identical to
sixteen significant digits** (−8.260233918128652 both times). Not a caching artifact —
`evaluate.py` never reads `synthesis_cache`, so both were fresh live syntheses. The reason:

```
id=244  targets bear 38 / base 72 / bull 148   probabilities 35 / 45 / 20
id=266  targets bear 38 / base 72 / bull 148   probabilities 35 / 45 / 20   ← identical
```

**E(R) is computed from the model's scenario targets and probabilities against the live
price — not arithmetically from `avg_score`.** The defective Valuation 5 inflated `avg_score`
(3.4 vs 2.6), which is an input to the synthesis *prompt*, but the model's price targets were
unmoved by it. So the forecast that grades in 90 days is the same either way.

The correction is still right and worth having — the Valuation cell was wrong, `avg_score` was
wrong, and both are now correct and linked — but **the row was not a fabricated *call*; the
fabrication was in the pillar, not in the forecast.** Recorded because the distinction changes
what the supersede trail means: it documents a corrected *measurement*, not a corrected
prediction. Worth knowing that the pillar→E(R) coupling is looser than assumed; three of the
six names did move their E(R), so the coupling is real but not mechanical.

## 4. Stage movement, and one transition

| ticker | stage old → new |
|---|---|
| RKLB | standard/YOUNG → standard/YOUNG (unchanged) |
| LLY | cyclical/MATURE → **compounder**/MATURE |
| CAT | standard/MATURE → **cyclical**/MATURE (now carries `GUARD-TOLERANCE-UNCALIBRATED`) |
| BE | cyclical/HIGROWTH → **growth**/HIGROWTH |
| INFQ | cyclical/YOUNG → **growth**/YOUNG (insufficient history either way) |
| **IONQ** | cyclical/HIGROWTH → **growth/YOUNG** — *the only stage change, and a transition row was written* |

**IONQ's move is a real interaction worth your attention.** Rule 2's cyclical guard — the
L-1e fail-closed rule that blocked IONQ from YOUNG in step 2 — **is scoped to the cyclical
lens**. Overriding IONQ to `growth` removed that protection, so its negative margin now fires
rule 2 and it reads YOUNG. Nothing is wrong: on the growth lens it is a pre-earnings company
and YOUNG is the honest tag. But it means **the guard's protection travels with the lens**,
so any future lens override can silently change a name's stage. `lifecycle_transitions` caught
it (`IONQ: HIGROWTH → YOUNG`), which is the transition report doing exactly its job.

## 5. Updated censuses

**Stages:** MATURE 15 · HIGROWTH 7 · **YOUNG 5** · DECLINE 1 *(was MATURE 15 / HIGROWTH 8 / YOUNG 4 / DECLINE 1)*
**Lenses:** cyclical **13** · compounder 5 · growth **4** · bank 4 · standard **2** *(was cyclical 16 / compounder 4 / bank 4 / standard 3 / growth 1)*

The cyclical lens went from governing 16 of 28 names to 13 — pharma out, two quantum names
and one power name out, CAT in.

**The step-4 YOUNG population is now 5:** DPC, INFQ, RKLB, SPCX, **IONQ**. Three more
(CBRS, QBTS, XE) remain blocked by L-1e's fail-closed guard while they stay cyclical.

## 6. Fix 3 — GOOG/GOOGL required no write

Already satisfied by the write-time mechanism plus the earlier backfill: **GOOG 7 rows all
`calibration_instrument=1`**, **GOOGL 1 row `=0`**, **zero NULLs** across all 79 evaluations.
GOOGL is canonical. **Share-class dedup at CIK level is on the punch list, not built** — both
tickers resolve to CIK `0001652044`, and two rows with near-identical fundamentals would
double-weight one forecast in any grade rollup.

## 7. Expected-delta

| table | before | after | note |
|---|---|---|---|
| `evaluations` | 73 | **79** (+6) | six superseding re-runs |
| `lifecycle_stage` | 37 | **43** (+6) | one stage row per re-run |
| `lifecycle_transitions` | 0 | **1** | IONQ HIGROWTH → YOUNG |
| `field_provenance` | 1294 | **1416** (+122) | standing companion |

Nothing outside the stated set moved. All six re-runs exited 0.

## 8. Punch list added under ruling 4

- **Step 4 blocked behind `fundamental_series` coverage expansion** — the YOUNG/blocked
  boundary currently reflects which names have FCF data, not business reality.
- **Feed-repair tickets:** IONQ missing FY2020; XE missing FY2023 and FY2024.
- **Share-class dedup at CIK level** before grading aggregates.
- **Replace the `_CYCLICAL_INDUSTRY` keyword sweep with explicit SIC entries** — the sweep is
  what forced the IONQ/INFQ overrides.

**Step 3 (B-2 stage-conditioned tolerances) is unblocked and awaits your order. STOP.**
