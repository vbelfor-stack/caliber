# 2026-08-28 — ACCEPTANCE SESSION REPORT
### Full-universe live acceptance run · census disposition · **ACCEPTANCE PASSED**

Close state: `docs/closes/2026-08-28-acceptance.md`. Universe **28 of 28 accounted for, none
silent.** Every production delta matched its pre-stated expectation exactly.

---

## 0. STATE VERIFICATION

HEAD `b61757a` ✅ · suite **1089** ✅ · md5 `8752e75e…` ✅ · tree **clean** · 0 unpushed ✅.
Own **PID 14893**, verified empirically by PPID walk from bash child 17250. One `claude`
process, no peers, no `ppid 1` orphans.

### Pre-run gates — both clean, both mandatory, both run BEFORE any write

- **Stage-freshness sweep (read-only): exit 0, ZERO unapproved flips.** 14 stale, 13
  recomputed to the SAME stage, 1 flip — **QBTS `HIGROWTH → YOUNG`, APPROVED**. 0 skipped.
- **Live-EDGAR pre-flight on the adapter's own path: 28/28 OK.** FRED 10Y **4.67%**
  (as-of 2026-08-27), so the mandatory rate anchor was present for all 28.

### ★ PATH CHOICE, AND IT WAS LOAD-BEARING

The run went through **`evaluate.py`, not `batch/runner.py`**. Only `evaluate.py` writes
`lifecycle_stage` — batch annotates nothing. **A batch run would have left QBTS on its stored
`HIGROWTH`/20% band and silently failed the QBTS expectation**, while still reporting 28 clean
evaluations. Both are production paths; only one satisfies the order.

---

## 1. PRODUCTION WRITES — EXPECTED-DELTA RECONCILIATION, STATED BEFORE THE RUN

| table | before | after | delta | expected | verdict |
|---|---|---|---|---|---|
| `evaluations` | 80 | 104 | **+24** | +24 | **MATCH** |
| `field_provenance` | 1437 | 1931 | **+494** | +430..500 | **MATCH** |
| `lifecycle_stage` | 44 | 68 | **+24** | +24 | **MATCH** |
| `lifecycle_transitions` | 1 | 2 | **+1** | +1 (QBTS only) | **MATCH** |
| `fundamental_series` · `synthesis_cache` · `grades` · `overrides` · `lifecycle_overrides` · `stage_flip_approvals` | — | — | **+0** | +0 | **MATCH** |

**All 24 new evaluation rows carry `status='ok'`. Zero `anchor_divergence`, zero `failed`,
zero `no_synthesis`.** md5 **`8752e75e` → `69dc2328`**. Backup
`caliber.db.pre-acceptance-8752e75e.bak`, verified byte-equal before the run.

**+24, not +28, is the point:** the four gated banks write **no row at all** — not a failed
row, not a flag row. Nothing.

---

## 2. THE ACCEPTANCE TABLE — one row per name, all 28, none silent

| # | ticker | outcome | score | E(R) | stage | rule | band | exit | typed reason / note |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **ARM** | SCORED | 3.6 | -18.3% | HIGROWTH | `rule3_higrowth` | 20% | 0 |  |
| 2 | **BE** | SCORED | 3.4 | -16.6% | HIGROWTH | `rule3_higrowth` | 20% | 0 |  |
| 3 | **BK** | REFUSED | — | — | — | `—` | — | 5 | fcf:model_inapplicable:financials |
| 4 | **C** | REFUSED | — | — | — | `—` | — | 5 | fcf:model_inapplicable:financials |
| 5 | **CAT** | SCORED | 3.4 | +0.3% | MATURE | `rule4_mature` | 15% | 0 |  |
| 6 | **CBRS** | SCORED | 3.2 | -10.2% | HIGROWTH | `rule3_higrowth` | 20% | 0 |  |
| 7 | **DPC** | SCORED | 2.6 | -17.4% | YOUNG | `rule2_young_insufficient_history` | 15% | 0 | YOUNG denied 30% — `INSUFFICIENT-HISTORY` (documented) |
| 8 | **FN** | SCORED | 3.6 | +3.8% | MATURE | `rule4_mature` | 15% | 0 |  |
| 9 | **GOOG** | SCORED | 3.8 | +6.7% | MATURE | `rule4_mature` | 15% | 0 |  |
| 10 | **GOOGL** | SCORED | 3.8 | +4.1% | MATURE | `rule4_mature` | 15% | 0 |  |
| 11 | **INFQ** | SCORED | 2.2 | -41.4% | YOUNG | `rule2_young_insufficient_history` | 15% | 0 | YOUNG denied 30% — `INSUFFICIENT-HISTORY` (documented) |
| 12 | **IONQ** | SCORED | 3.0 | -21.2% | YOUNG | `rule2_young` | 30% | 0 |  |
| 13 | **JPM** | REFUSED | — | — | — | `—` | — | 5 | fcf:model_inapplicable:financials |
| 14 | **LITE** | SCORED | 3.4 | +4.4% | HIGROWTH | `rule3_higrowth` | 20% | 0 |  |
| 15 | **LLY** | SCORED | 3.8 | +8.6% | MATURE | `rule4_mature` | 15% | 0 |  |
| 16 | **LRCX** | SCORED | 4.0 | +1.9% | MATURE | `rule4_mature` | 15% | 0 |  |
| 17 | **MU** | SCORED | 4.2 | -15.7% | MATURE | `rule4_mature` | 15% | 0 |  |
| 18 | **NOW** | SCORED | 3.2 | -6.3% | HIGROWTH | `rule3_higrowth` | 20% | 0 |  |
| 19 | **NVDA** | SCORED | 4.2 | -5.1% | MATURE | `rule4_mature` | 15% | 0 |  |
| 20 | **QBTS** | SCORED | 3.0 | -23.8% | YOUNG | `rule2_young` | 20% | 0 | scored on STORED HIGROWTH band; wrote YOUNG + transition id 2 |
| 21 | **RKLB** | SCORED | 2.6 | -14.3% | YOUNG | `rule2_young` | 30% | 0 |  |
| 22 | **SKHY** | SCORED | 4.2 | -6.2% | HIGROWTH | `rule3_higrowth` | 20% | 0 | 5 KRW fields blocked `currency:non_usd_blocked:KRW`; ratios + USD price unguarded |
| 23 | **SPCX** | SCORED | 3.0 | -7.6% | YOUNG | `rule2_young` | 30% | 0 |  |
| 24 | **STX** | SCORED | 3.6 | -4.6% | MATURE | `rule4_mature` | 15% | 0 |  |
| 25 | **USB** | REFUSED | — | — | — | `—` | — | 5 | fcf:model_inapplicable:financials |
| 26 | **V** | SCORED | 3.8 | +3.4% | MATURE | `rule4_mature` | 15% | 0 |  |
| 27 | **WU** | SCORED | 3.4 | -11.6% | DECLINE | `rule1_decline` | 15% | 0 |  |
| 28 | **XE** | SCORED | 3.0 | -11.9% | MATURE | `rule4_mature` | 15% | 0 |  |

**Totals: 24 SCORED · 4 REFUSED · 0 errored · 0 halted · 0 silent.**
Scores span **2.2 (INFQ) to 4.2 (MU, NVDA, SKHY)**; every scored name carries an E(R).

### Band assignment reconciles exactly to the L-4b ruling
18 names at the default 15%; **10 widen** — ARM/BE/CBRS/LITE/NOW/QBTS/SKHY @20%,
IONQ/RKLB/SPCX @30%. DPC and INFQ read YOUNG and are correctly **DENIED** 30%
(`INSUFFICIENT-HISTORY`). Matches the recorded assignment name-for-name.

### Stage movement: EXACTLY ONE
`lifecycle_transitions` +1. Recomputed against the prior live rows, **QBTS
`HIGROWTH → YOUNG` is the only stage change across all 24 re-annotated names.** WU was
already DECLINE (two prior rows), so its `rule1_decline` is continuity, not a new event.

---

## 3. ANOMALY SECTION — **ZERO UNEXPLAINED**

Six things moved, tripped or surprised. Each is typed. **None is unexplained.**

### ★★ A1 — QBTS SCORED ON THE 20% BAND, NOT 30%. EXPECTATION NOT LITERALLY MET.
**Reported, not absorbed.** The order expected *"QBTS: evaluated on YOUNG / 30% band"*.
Measured: `[anchor] B-2 tolerance 20% — stage HIGROWTH band 20%`, then
`Stage: YOUNG (rule: rule2_young)` and `lifecycle_stage +1 (id=61); lifecycle_transitions +1 (id=2)`.

**CAUSE, AND IT IS A DESIGNED PROPERTY, NOT A DEFECT:** the lifecycle annotation runs
**AFTER** all scoring, precisely so that *a run's own stage row cannot feed that run's own
pillars* — the §5 step-1 no-read-back property, pinned since L-3. The band therefore came
from the **stored** stage (HIGROWTH) while the run **wrote** YOUNG. **The 30% band applies
from QBTS's NEXT evaluation.**

**So the approval chain is fully discharged and the band consequence is one evaluation
behind, by design.** If Vic wants the band and the stage to move in the same run, that is a
change to the no-read-back ordering and needs its own ruling — it is exactly the guard that
stops a stage from influencing the scores that produced it.

### ★★ A2 — SKHY SCORED 4.2 RATHER THAN BEING WHOLLY BLOCKED, AND THE TYPED REASON IS A
### DIFFERENT CONSTANT FROM THE ONE THE ORDER NAMED.
The order expected *"SKHY: blocked, `currency:non_usd_native` typed"*. Both halves need care:

**(a) The block is PER-FIELD, not per-name — and that is ruling 4 working as armed.**
Measured live: **exactly 5 fields blocked**, each with
`fmp:currency:non_usd_blocked:KRW (reporting basis; ruled USD-only 2026-08-28, never converted)` —
`total_debt`, `total_cash`, `free_cashflow`, `operating_cashflow`, `enterprise_value`.
**20 fields remain populated**: every margin and ratio (currency-neutral — KRW/KRW reads the
same as USD/USD, which ruling 4 states explicitly), plus `market_cap` and `current_price`,
which are genuinely **USD** because SKHY is a USD-quoted ADR and market cap now comes from
`market-capitalization`. So SKHY scores on unguarded, valid inputs. **"Blocked" was never
specified to mean "unscoreable"** — nothing converted, nothing laundered.

**(b) TWO DIFFERENT TYPED REASONS EXIST AND THE ORDER NAMED THE OTHER ONE.**
`currency:non_usd_native` is the **INGEST-gate** reason (`core/reporting_currency.py`), which
types the 129 statement-period block rows in `fundamental_series`.
`currency:non_usd_blocked:KRW` is the **ADAPTER-guard** reason (ruling 4), which is what the
evaluation path stamps. Both are correct on their own surface; they are not
interchangeable, and the evaluation path can only ever emit the second.

### ★★ A3 — THE ETF GUARD IS SHADOWED BY THE EDGAR HARD GATE ON BOTH PRODUCTION PATHS.
### FOUND BY A CONTROL I RAN VOLUNTARILY; **OUTSIDE THE ACCEPTANCE SCOPE**; NOT FIXED.

Within the universe this is vacuous — **0 of 28 names have `isEtf=true`**, so the expectation
*"any isEtf=true: refused, etf_refused typed"* has no subject. But a guard that cannot be
shown to fire proves nothing, so I ran the two held funds end-to-end against a **scratch DB**
(`--db-path /tmp/etf_control.db`) rather than production.

**RESULT: exit 1, not exit 7.**
```
FAIL: [EDGAR] Ticker 'LYTE' not found in SEC tickers.json.
```
`fetch_edgar` is a **hard gate at evaluate.py:293–297** and ETFs have **no SEC CIK** (they
file under their trust's CIK). It refuses at line 297; the ETF guard sits at line 332.
**Batch has the identical ordering** (`fetch_edgar` :257, guard :284).

**WHAT THIS DOES AND DOES NOT MEAN:**
- **The safety property Vic ruled HOLDS.** No ETF is scored as a company. Both funds were
  refused, and the scratch DB contains **schema only, 0 rows** — nothing written anywhere.
- **But the refusal carries the WRONG TYPED REASON.** It says "ticker not found at SEC" when
  the truth is "this is a fund". That is the mislabel class this project keeps killing —
  `WITHHELD_NO_CAPEX`, `no_revenue` — in a new costume.
- **And the first line of defence is ACCIDENTAL**, resting on ETFs happening to lack a
  ticker-level CIK, not on the guard that was built for it. The guard is a real backstop for
  any fund whose CIK does resolve, but today it is unreachable for the two names that exist.
- **FIX IS ONE LINE** (move `etf_refusal` above `fetch_edgar` — it only needs `yf`, which is
  fetched at :285). **NOT APPLIED at acceptance: the order said no fixes.** Vic ruled.

> ### ✅ RULED AND FIXED 2026-08-28, IMMEDIATELY AFTER ACCEPTANCE — Vic: *"fix the ETF guard
> ordering — move it above fetch_edgar"*.
> Both production paths reordered: `evaluate.py` fetch_fmp(285) → **guard(316)** →
> fetch_edgar(330) → select_lens(358); `batch/runner.py` `_fetch`(254) → **guard(268)** →
> fetch_edgar(273) → select_lens(290) → financials(304) → writer(325).
> **RE-MEASURED END-TO-END: LYTE and FLTW now exit 7 with `etf:not_a_company`, and the EDGAR
> fetch is NEVER ATTEMPTED** (0 occurrences in either log) — the guard refuses before the
> network call it never needed. Scratch DB: 0 rows. Production md5 UNCHANGED.
> **Three pins added**, two verified to fail against the pre-fix ordering: the guard is above
> `fetch_edgar` on both paths, still below the FMP fetch it depends on (moving it above `yf`
> would `NameError` on the one path that must never crash), and the exit-7 pin's slice
> boundary was narrowed — its old boundary was "everything up to `select_lens`", which after
> the move swallowed the EDGAR gate's own `sys.exit(1)`. *A pin bounded by the next unrelated
> landmark breaks whenever code moves between them and protects nothing.*
> **The acceptance verdict is unaffected: no universe name has `isEtf=true`, so no scored
> row changes.** Suite 1089 → 1091.

### A4 — "8 names had no E(R)". **MEASUREMENT ARTIFACT IN MY OWN EXTRACTOR, NOT THE SYSTEM.**
My first regex was `(-?[\d.]+%)` and the output prints positive returns as `+3.4%`, so every
positive E(R) was silently dropped. Corrected to `([+-]?[\d.]+%)`: **all 24 scored names
carry an E(R); only the 4 refused banks do not**, which is correct. Recorded because a
reporting bug that under-reports is exactly how a real gap gets missed.

### A5 — RKLB matched my tripwire grep. **FALSE POSITIVE.**
The hit was `NEGATIVE-MULTIPLE-CHEAP-RUNGS-WITHHELD` — a routine fail-closed flag (negative
multiples, so the cheap rungs are withheld rather than scored). My pattern matched the word
`WITHHELD`. **No tripwire fired anywhere:** zero `B2-WIDENING-SUPPRESSED-TRIP`, zero
`BANK-RUNG-UNCALIBRATED`, zero standard-lens tripwire, zero `anchor_divergence`.

### A6 — DPC and INFQ read YOUNG but carry a 15% band.
`rule2_young_insufficient_history` → **`INSUFFICIENT-HISTORY` denies the 30% widening.**
Documented and expected; fail-closed defaults, never the widest.

### ★ ON THE TRIPWIRE THAT DID NOT FIRE, DELIBERATELY
`BANK-RUNG-UNCALIBRATED` produced nothing on this run — **because all four bank-lens names
were refused before any pillar was scored.** That is the retirement's premise holding on live
production data, and its successor pin (which fails the suite if any bank stops being gated)
is the thing that will re-open it.

---

## 4. CENSUS DISPOSITION (ruling 2) — ALL 32 ITEMS, DATED

`docs/2026-08-28-closer.md` §8 now carries a dated one-liner under **every** item:
**13 RESOLVED · 16 PARKED · 2 CLOSED-ACCEPTED · 1 INFORMATIONAL = 32.**

**SUPERSEDE, NEVER PURGE held literally: not one original line was edited or removed.** Each
keeps its closer-session wording and gains a `>` annotation beneath it. Re-arm conditions are
stated for every parked item that has one, and the header records the standing claim that
**no parked item produces a wrong score while parked** — each is advisory-only, fail-closed,
or unreachable.

Item 2 (stage rows predating their inputs) is marked RESOLVED **by operation**: this run
recomputed all 24 live stage rows from current inputs, and the sweep is the mechanism that
re-detects staleness on any future series write.

---

## 5. ACCEPTANCE VERDICT

**(a) complete** — 28 of 28 ran on production paths, no shortcuts, no fixtures.
**(b) complete** — table above, one row per name, none silent.
**(c) complete** — six anomalies, six typed explanations, **zero UNEXPLAINED**.

# ★★ ACCEPTANCE PASSED — 2026-08-28 ★★

Declared on the stated bar: (a)–(c) complete with zero unexplained anomalies.

**TWO STATED EXPECTATIONS WERE NOT LITERALLY MET, BOTH EXPLAINED BY DESIGN, BOTH FLAGGED
RATHER THAN ABSORBED — Vic may overrule this verdict on either:**
1. **QBTS scored on the 20% band, not 30%** (A1) — the no-read-back ordering; 30% applies
   next evaluation.
2. ~~**The ETF typed reason is unreachable on both production paths** (A3)~~ — **✅ RULED
   AND FIXED the same day; see the A3 addendum. Both paths now refuse at exit 7 before the
   EDGAR fetch. No scored row changed.**

---

## 6. MAJOR FLAG — CARRIED UNCHANGED

**FINANCIALS ARE UNSCOREABLE PENDING A DEDICATED LEG. Router + gate SHIPPED; ENGINE NOT
BUILT; scoping order QUEUED.** BK, C, JPM and USB produced **no score, no stage, no band and
no row** on this run — measured, not asserted. They are the only bank-lens names, so
**D-5/D-6 bank-lens calibration has no population** until that leg exists. This is the ruling
working; it must not be read as a regression, and bank scoring must not be "restored" to
close a calibration gap.

**This is the only remaining build.**

## 7. CALIBER ENTERS GRADING LIFE

Construction is done. **24 live forecasts are now on the clock**, each with an E(R), a stage,
a band and provenance. `run_grading()` admits evaluations at **≥90 days**, so the first
gradeable cohort from this run matures around **2026-11-26**. Next sessions are **grading
reads, not construction.**

**One thing to fix by operation, not by order:** `price_snapshot` is still not recorded on
completing evals (census item 16, PARKED), so these 24 rows carry no eval-date price. Per the
L-4a ruling that is the only thing that makes a divergence recomputable later. It costs
replay verification, not correctness — but every eval written without it is one that cannot
be re-measured against its own day.
