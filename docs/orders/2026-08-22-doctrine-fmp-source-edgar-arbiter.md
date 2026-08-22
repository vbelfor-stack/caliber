# ORDER — DOCTRINE: FMP-SOURCE / EDGAR-ARBITER, + THE STEP-4 RULING

**Issued:** Vic, ratified 2026-08-21 · **Executed:** 2026-08-22 · **Session:** PID 9237
**Type:** doctrine + docs. **NO production db writes. NO code behaviour changes.**
**Predecessor:** `docs/orders/2026-08-22-l4d1-lly-capex-basis.md` (L-4d.1, HEAD `b813b1e`)

Committed BEFORE any application, per the standing "order document first" discipline.

---

## 1. THE DOCTRINE AS RULED

> **FMP is the source; EDGAR is the arbiter.**

**Rationale, in Vic's terms:** paid/normalized beats free for pipeline reliability. EDGAR
remains ground truth of record, invoked for arbitration, not pipeline.

### 1.1 What FMP does
FMP feeds **all pipeline runs** — series building, TTM assembly, scoring.

### 1.2 What EDGAR does — exactly three cases
- **(a) Divergence arbitration** — FMP fails a sanity gate, or diverges **>25%** from an
  EDGAR-visible figure.
- **(b) Filed-tag provenance** on a challenged verdict.
- **(c) Rulings.**

### 1.3 Pre-flight, rescoped
The standing live-EDGAR pre-flight (ruled 2026-08-15; `docs/phase-archive.md` §295-306)
is **mandatory on arbitration runs only**, no longer on every run.
**→ SEE §5. THIS CLAUSE IS RECORDED AS RULED BUT IS NOT OPERATIVE, ON MEASUREMENT.**

### 1.4 All other standing disciplines unchanged
Expected-delta on every write · supersede-never-purge · fail-closed defaults · one step per
order · WAL-checkpoint before md5 · push on landing · no synthetic calibration.

### 1.5 EDGAR machinery — DEMOTED, NOT UNWOUND
The capex chains (**including the three-tag chain armed at L-4d.1**), the typed withholding
reasons, and `field_provenance` are demoted to an **audit layer**.

**NOT unwound. NOT deleted. Deleting EDGAR-path code requires a Vic ruling.**
Pinned by `tests/test_doctrine_edgar_arbiter.py` (§6).

### 1.6 H-4 parked
**H-4 proper (the EDGAR D&A tag spec) is demoted from blocker to optional audit tooling and
parked indefinitely.** It was previously "DEFERRED behind EDGAR expansion"
(`docs/h-fcf-scoping.md:235`), i.e. a live blocker on the EBITDA leg and on the NULL
`reinvestment` column (`core/fundamental_series.py:435`). Under this doctrine the D&A input
comes from FMP if it comes from anywhere, so the EDGAR spec stops being on the critical path.
Roadmap updated.

### 1.7 Coexistence by design
EDGAR-chain capex and FMP `capitalExpenditure` **both live in the db with distinct
provenance**. They are permitted to disagree.

**LLY FY2024 is the worked example, and it is NOT a defect. It must not be "fixed."**
Measured this session (EDGAR from production `fundamental_series.components_json`; FMP live):

| FY | EDGAR capex | FMP \|capex\| | apart | % of FMP |
|---|---|---|---|---|
| 2025-12-31 | 7,841,000,000 | 7,841,000,000 | 0 | 0.0% |
| **2024-12-31** | **5,058,000,000** | **8,403,600,000** | **3,345,600,000** | **39.8%** |
| 2023-12-31 | 3,448,000,000 | 7,392,100,000 | 3,944,100,000 | 53.4% |
| 2022-12-31 | 1,854,300,000 | 2,985,300,000 | 1,131,000,000 | 37.9% |
| 2021-12-31 | 1,309,800,000 | 1,978,400,000 | 668,600,000 | 33.8% |
| 2020-12-31 | 1,387,900,000 | 2,029,100,000 | 641,200,000 | 31.6% |

The order's "~$3.3B apart" is confirmed exactly: **$3,345,600,000**. Cause is already ruled
(L-4d.1): FMP's `capitalExpenditure` bundles
`PaymentsToAcquireInProcessResearchAndDevelopment`; the EDGAR tag does not. Intangible/IPR&D
acquisition is not capital intensity. Both are internally coherent under their own
definitions, so this is a **basis difference, not an error on either side.**

---

## 2. THE STEP-4 RULING (Vic, 2026-08-21)

- **Coverage expansion proceeds on FMP basis.**
- **EDGAR YTD-assembly is not to be built.** The limit that parked CBRS/DPC/SPCX/XE
  dissolves under the new source.
- **JPM/USB/INFQ/SKHY are re-examined on FMP basis too.**
- **Expansion is NOT executed in this order.** This order records the ruling and reports
  read-only feasibility.

---

## 3. THE 8-NAME FMP FEASIBILITY REPORT (read-only, measured live 2026-08-22)

Method: direct GETs to `cash-flow-statement` (annual `limit=10`, quarter `limit=12`) and
`income-statement` (annual `limit=10`) on the `stable` API. Every field scored on **three
separate counts — key present, non-null, and non-zero** — because *presence is not
population*: LLY's `incomeTaxesPaid`/`interestPaid` are present on every row and dead
zero-filled, and a key-exists check would have called them usable.

**A note on what the production payload requests today:** `fetch_payload`
(`adapters/fmp_adapter.py:556`) asks for `cash-flow-statement?period=annual&limit=1` — **one
annual row, and no quarterly cash-flow at all.** So none of the history below is reachable
by the current pipeline. FMP-basis expansion is an **endpoint-scope change**, not merely a
re-pointing of an existing fetch.

### 3.1 The table

| # | Ticker | EDGAR-basis reason (today) | FMP FY rows | FMP FY OCF / capex populated | FMP quarterly | Step-4 feasible on FMP? |
|---|---|---|---|---|---|---|
| 1 | **JPM** | `capex:no_tag` | 10 (2016–2025) | OCF **10/10** · capex **0/10 DEAD** | 12 qtrs, capex **0/12 DEAD** | **NO — and worse than no data.** See §3.2 |
| 2 | **USB** | `capex:no_tag` | 10 (2016–2025) | OCF **10/10** · capex **0/10 DEAD** | 12 qtrs, capex **0/12 DEAD** | **NO — same trap as JPM.** |
| 3 | **INFQ** | `capex:no_tag` | 3 (2023–2025) | OCF 2/3 · capex **1/3** | 8 qtrs, capex 3/8 | **NO — too sparse, too holed.** |
| 4 | **SKHY** | no us-gaap namespace at all | **10 (2016–2025)** | OCF **10/10** · capex **10/10** | **12 qtrs, all populated** | **YES on completeness — BLOCKED on a currency contradiction.** See §3.3 |
| 5 | **CBRS** | `ttm_unavailable` (YTD-only) | 4 (2022–2025) | OCF **4/4** · capex **4/4** | 6 rows, **manufactured** | **FY: YES. Quarterly: NO — values are allocated duplicates.** See §3.4 |
| 6 | **DPC** | `ttm_unavailable` (YTD-only) | **1** (2025 only) | OCF 1/1 · capex 1/1 | 2 rows (Q1+Q2 2026) | **NO — one FY point cannot feed a 3-FY signal.** |
| 7 | **SPCX** | `ttm_unavailable` (YTD-only) | 3 (2023–2025) | OCF **3/3** · capex **3/3** | 3 rows, holed | **FY: MARGINAL (exactly 3).** Quarterly: no. |
| 8 | **XE** | `ttm_unavailable` (YTD-only) | 3 rows but **2025, 2022, 2021** | OCF 3/3 · capex 3/3 | 2 rows | **NO — FY2023 and FY2024 are MISSING.** See §3.5 |

**Headline: the ruling's premise holds for 1 of 8 outright (SKHY, modulo currency), partly
for 2 more (CBRS/SPCX on FY only), and FAILS for 5.** "The limit dissolves under the new
source" is true for the *YTD-assembly* limit specifically — FMP does serve annual
cash-flow for the YTD-only filers, which EDGAR could not assemble. It is **not** true that
the 8 become evaluable.

### 3.2 JPM / USB — FMP is not merely absent here, it is actively wrong

`capitalExpenditure` is `0` on **all 10 annual and all 12 quarterly rows**, and because
FMP computes `freeCashFlow = operatingCashFlow - capitalExpenditure`, it therefore publishes
**`freeCashFlow` exactly equal to `operatingCashFlow`** — JPM FY2025 `freeCashFlow` =
$100,867,000,000, which is its operating cash flow, not its free cash flow.

This is the presence≠populated trap in its most dangerous form: the value is present,
non-null, non-zero, large, and plausible. A builder that reads `freeCashFlow` would write a
confident wrong number for a $100B bank.

**EDGAR's `capex:no_tag` refusal is the more truthful answer of the two.** Migrating
JPM/USB to FMP basis would convert a correct fail-closed refusal into a silent false
positive — a direct inversion of "loud failure beats silent degradation". Recommend
JPM/USB stay fail-closed on **either** basis, and that any FMP-basis builder treat
`capitalExpenditure == 0` across an entire series as **absence, never zero**.

### 3.3 SKHY — the punch-list item is answered, and it brings a new contradiction

The ★★ TOP-PRIORITY punch-list item asked "whether a NON-EDGAR fundamentals source is wired
for issuers EDGAR structurally cannot serve." **Measured answer: FMP serves SK hynix in
full** — 10 FY rows and 12 quarters, every FCF input populated. The EDGAR-side finding
(1,863 bytes of F-1 filing-fee data, no us-gaap namespace) is unchanged and still correct;
it was a statement about EDGAR, not about the issuer.

**But two FMP endpoints disagree about SKHY's currency:**

| endpoint | field | value |
|---|---|---|
| `cash-flow-statement` | `reportedCurrency` | **KRW** |
| `profile` | `currency` | **USD** |

The magnitudes confirm KRW is the true one (FY2025 OCF = 53,373,126,000,000 — ~$39B at
~1,380 KRW/USD, not $53 trillion). **Writing this series into a USD-typed column without a
currency gate is a ~1,380x error.** Every other name measured — JPM, USB, INFQ, CBRS, DPC,
SPCX, XE, LLY — reports USD on both endpoints, so SKHY is the sole discrepancy and there is
no existing currency handling to lean on.

Per the standing rule **"never fix a contradiction by teaching the model to ignore it"**,
this is reported, not arbitrated. It is a precondition on any SKHY expansion, not a detail
of one.

### 3.4 CBRS — the quarterly rows are allocated, not reported

FMP returns 6 quarterly rows for CBRS: Q1+Q2 of 2026, 2024 and 2023. **Within each year the
two quarters are identical to the cent:**

| period | OCF | capex |
|---|---|---|
| 2024-06-30 Q2 | 155,906,500 | −5,894,000 |
| 2024-03-31 Q1 | **155,906,500** | **−5,894,000** |
| 2023-06-30 Q2 | −35,092,500 | −227,000 |
| 2023-03-31 Q1 | **−35,092,500** | **−227,000** |

Three things establish these are derived, not reported: the pairs are byte-identical (no
real business produces two consecutive quarters equal to the cent); the `.5` remainder is
the signature of a division by two; and **Q3/Q4 do not exist for any year.**

I initially hypothesised these were the annual figure halved. **That is wrong and I checked
before recording it** — 2024 annual OCF is 451,978,000, whose half is 225,989,000, not
155,906,500. The pairs do not reconcile to the annual row either. So they are an allocation
of some interim figure, and they agree with neither each other's independence nor the
annual total.

**Consequence: CBRS FY data is usable; CBRS quarterly data must not be used for TTM
assembly.** This is the same shape as the YTD-only problem the doctrine expected FMP to
dissolve — FMP has not dissolved it, it has *papered over* it with values that look
complete. That is a worse failure mode than EDGAR's honest `ttm_unavailable`.

### 3.5 XE — the existing feed-repair ticket is confirmed and widened

The punch list already carries "`income_annual` series gaps — XE missing FY2023 and FY2024."
**Measured: the gap is in the cash-flow endpoint too.** XE's annual cash-flow rows are
2025-12-31, 2022-12-31, 2021-12-31 — FY2023 and FY2024 absent from both statements. The
ticket is not income-statement-specific; it is an issuer-level FMP gap. A 3-FY window that
skips two years is **not** three consecutive years, and the R2 last-3-FY signal would
silently read across a two-year hole.

### 3.6 Two conversion traps any FMP-basis builder must clear

Neither is a blocker; both are the exact shape of a defect that has already cost this
project real time, so they are recorded before the build rather than after.

1. **SIGN.** FMP files capex **negative** (`-7,841,000,000`); EDGAR files it as a
   **positive outflow magnitude**, and `build_fcf_series` computes `fcf = ocf - capex`
   (`core/fundamental_series.py:410`). Reusing that expression on FMP input **adds** capex
   instead of subtracting it. This is the debt/equity ratio-vs-percent unit defect in a new
   costume — that one scored a percent ladder against a ratio for eight days with 654 green
   tests.
2. **STEP-4 SIGNAL CONTENT MOVES.** LLY's last three FY FCF points are
   **`[+0.792B, +3.760B, +8.972B]` on EDGAR basis** but **`[−3.152B, +0.414B, +8.972B]` on
   FMP basis** — two of three flip sign. LLY still does not join the R2 all-negative-last-3
   set (FY2025 is positive either way), so **that set remains IONQ/QBTS/RKLB/C**. But the
   doctrine switch is **not signal-neutral for step 4**, and the R2 boundary population must
   be re-measured on FMP basis before step 4 arms, not assumed to carry over.

---

## 4. WHAT THIS ORDER CHANGES

| Surface | Change |
|---|---|
| `docs/orders/2026-08-22-doctrine-fmp-source-edgar-arbiter.md` | NEW — this document |
| `CLAUDE.md` | doctrine section added; EDGAR demotion recorded; H-4 parked in roadmap; step-4 ruling recorded; SKHY punch-list item answered; feasibility table linked |
| `tests/test_doctrine_edgar_arbiter.py` | NEW — the no-delete-without-a-ruling pin (§6) |
| production db | **NOTHING. Zero writes.** md5 must be unchanged at close. |
| runtime code | **NOTHING.** No behaviour change anywhere. |

---

## 5. ★ STOP-CONDITION REPORT — ONE CONTRADICTION, NOT RESOLVED BY THE DOCTRINE

The order's stated stop condition: *"anything in CLAUDE.md contradicting this doctrine that
isn't resolved by it — report for ruling rather than improvising."* One qualifies.

### 5.1 The measured fact

**EDGAR is score-bearing on EVERY pipeline run today, through four paths that the doctrine's
three cases do not name.** Verified in source this session, not remembered:

| path | evaluate.py | batch/runner.py | effect |
|---|---|---|---|
| `yf.sic = edgar.sic` | :300 | :254 | SIC propagated into ticker data |
| `select_lens(..., edgar.sic, ...)` | :310 | :255 | **selects the valuation lens → moves scores** |
| `build_panel(yf, fred, edgar, ...)` | :320 | :268 | EDGAR is a panel input |
| `score_growth(yf, edgar, lens)` | via `core/pillars.py:988` | same | EDGAR is a **pillar** input |

And `fetch_edgar` is a **hard gate**, not an optional enrichment: `evaluate.py:282-287`
exits 1 on failure; `batch/runner.py:239` is deliberately *not* wrapped, so a mid-batch
failure raises into the broad handler and persists a **`failed` row per ticker**.

This is already ruled and recorded, in `docs/phase-archive.md:307-314`:

> **EDGAR IS SCORE-BEARING, NOT CONFIDENCE-ONLY (correction, ruled 2026-08-15).** … **EDGAR
> SELECTS THE LENS AND THE LENS MOVES SCORES.** Any claim that an EDGAR failure can only move
> a confidence label is WRONG. Blast radius of an EDGAR outage is a REFUSED evaluation, not a
> degraded one.

The doctrine's §1.5 demotion list names the **audit surfaces** — capex chains, typed reasons,
`field_provenance`. It does not reach SIC→lens, the panel, or the growth pillar. So the
demotion, as written, is consistent with the code; the **"exactly three cases"** clause is
not.

### 5.2 Why this blocks §1.3 specifically, and why I did not improvise past it

The pre-flight rescope (§1.3) is safe **only if** EDGAR is off the every-run path. It is
not. The pre-flight exists for precisely the failure the rescope would re-open —
`docs/phase-archive.md:295-306`:

> EDGAR reachability is INTERMITTENT, measured within a single session: both endpoints 200 at
> open, `www.sec.gov` 403 ~20min later while `data.sec.gov` stayed 200 … Five failed rows in
> production is exactly what loud-failure discipline exists to prevent; the pre-flight is the
> mechanism that prevents it.

Writing "pre-flight on arbitration runs only" into CLAUDE.md as settled operational guidance,
while `fetch_edgar` remains a hard gate on all 28 names, would hand the next session a
documented licence to skip the one check standing between an intermittent 403 and **28
`failed` rows in production**. That is a hazard created by a documentation edit alone, which
is why I am reporting it rather than smoothing it.

**§1.3 is therefore recorded in CLAUDE.md as RULED BUT NOT YET OPERATIVE, with the pre-flight
remaining mandatory on every live run pending Vic's ruling.** Nothing else in the doctrine is
held up by this.

### 5.3 Two coherent resolutions — Vic picks, I am not choosing

- **(a) Sequence it.** Keep the rescope as ruled intent, hold its arming until EDGAR is
  actually off the pipeline path (SIC/lens/panel/growth migrated to FMP or made optional).
  Pre-flight stays mandatory meanwhile. *Consistent with "nothing arms without a ruling" and
  with one-step-per-order.*
- **(b) Widen the doctrine.** Admit "classification + panel inputs" as a **fourth** EDGAR
  case. EDGAR then remains an every-run dependency by design, and the pre-flight stays
  mandatory on every run — i.e. §1.3 is withdrawn rather than deferred.

Both are defensible; they differ in whether the three-case list or the current architecture
is the thing that gives way. That is a Vic call.

### 5.4 One smaller gap, recorded not blocking

§1.2(a) invokes EDGAR when *"FMP fails a sanity gate"*. **No sanity gate exists.** There is
no such check anywhere in the runtime today, so that trigger is currently unreachable and the
arbitration path is in practice driven only by the >25% divergence clause. Not improvised
into existence here; noted as a build item the doctrine implies but does not specify.

---

## 6. THE PIN

`tests/test_doctrine_edgar_arbiter.py` — makes §1.5 ("demoted, NOT deleted; deleting
EDGAR-path code requires a Vic ruling") a **guard rather than a belief**, per the standing
rule that *a rule recorded without naming its enforcement point is a belief, not a guard*.

It pins, as structure and not as prose:
1. the capex chain still has **all three** tags in ruled order (L-4d.1 arming survives);
2. the typed-reason machinery still exists and the deleted constants stay deleted;
3. `field_provenance` is still written;
4. EDGAR's four score-bearing call sites still exist **— asserted over the AST, not the
   text** — so that if a future session removes one, the pin fails and forces §5 to be
   re-ruled rather than quietly resolved by deletion.

Point 4 is deliberately a *tripwire, not a prohibition*: it does not claim the call sites
ought to stay forever, only that removing them is a ruled act. The AST-over-text choice is
taken from the L-4b lesson that a pin prose can break is one a later session weakens instead
of heeding.

---

## 7. EXECUTION RECORD

- Session open: PID **9237** verified empirically (bash child → PPID). No peers, no orphans,
  no stray writers.
- Baseline verified at open: HEAD `b813b1e` · tree clean · 0 unpushed · suite **975 passed** ·
  caliber.db md5 `eec96270720d80d632aa3a6f9528ea49` (WAL checkpointed `(0,0,0)` first) ·
  backup `caliber.db.pre-l4d1-e3fe5ff9.bak` md5 `e3fe5ff9868f…` ·
  `.snapshots/l4d1-lly-2026-08-21/` 31 files / 93 MB · `.scratch_l4f/` and the three L-1 dark
  DBs untouched. **No deviation.**
- Measurement scratch: `.scratch_doctrine/` (gitignored) — `fmp_stepd_feasibility.py`,
  `supplement.py`, `feasibility.json`. Read-only: HTTP GETs and one `mode=ro` sqlite read.
- **Zero production writes. Zero code-behaviour changes.**
