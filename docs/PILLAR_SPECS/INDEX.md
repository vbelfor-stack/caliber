# CALIBER — GLASS-BOX AUDIT INDEX
**Read-only census of every scoring component, 2026-08-29.**
HEAD `ff02e21` · suite **1091 passed** · caliber.db md5 **`69dc2328ee3af8a43d506b64665da39b`**
(verified unchanged before and after; zero DB writes, zero code changes, engine frozen).

Worked examples throughout are the **2026-08-28 full-universe acceptance run**:
**QBTS** eval id 289 (YOUNG, cyclical) · **MU** id 286 (MATURE, cyclical) · **V** id 294
(MATURE, compounder). **Every worked example reconciles to its stored score by hand.**

| # | Component | File | Score |
|---|---|---|---|
| 1 | Business Quality (Profitability) | [`01-business-quality.md`](01-business-quality.md) | QBTS 2 · MU 5 · V 5 |
| 2 | Financial Health (Financial Strength) | [`02-financial-health.md`](02-financial-health.md) | QBTS 4 · MU 5 · V 4 |
| 3 | Management & Capital Allocation | [`03-management.md`](03-management.md) | QBTS 2 · MU 4 · V 4 |
| 4 | Growth / Forward | [`04-growth-forward.md`](04-growth-forward.md) | QBTS 5 · MU 5 · V 4 |
| 5 | Valuation | [`05-valuation.md`](05-valuation.md) | QBTS 2 · MU 2 · V 2 |
| 6 | Expected Return E(R) | [`06-expected-return.md`](06-expected-return.md) | QBTS −23.85% · MU −15.74% · V +3.38% |
| 7 | Stage Classifier | [`07-stage-classifier.md`](07-stage-classifier.md) | QBTS YOUNG · MU MATURE · V MATURE |

`04-growth-forward.md` is a **copy** of `docs/growth_pillar_spec.md` (2026-08-28), placed here
for symmetry. **The original was left in place, not moved** — CLAUDE.md and the prior session
summary reference that path, and the order confined writes to `docs/PILLAR_SPECS/`.

---

## 1. WHAT EACH COMPONENT ACTUALLY DOES, IN PLAIN ENGLISH

**1. Business Quality** scores three TTM profitability ratios — gross margin, operating
margin and ROE — on fixed ladders worth 3 points each, and divides by however many were
available. It reads no series, no history and no estimates: it is a snapshot of how
profitable the company is right now. It is one of only two components with **zero analyst
input**. `lens` is read once, to flag peak-cycle margins on cyclicals, and changes no score.
ROA is fetched, EDGAR-corroborated, stored — and never scored.

**2. Financial Health** scores liquidity (current ratio), leverage (debt/equity as a
percent) and free-cash-flow positivity, plus a bonus point if FCF yield clears 3%, and flags
a net cash position. Also estimate-free. Its ladders have no lower bound, which is where its
worst defect lives: a company with negative book equity collects **full marks for leverage**.
`lens` sits in the signature and is never read, so a bank and a biotech meet the same
current-ratio bar.

**3. Management & Capital Allocation** does not measure management or capital allocation. Its
six points are four for **beating sell-side EPS estimates** and two for an insider-trading leg
whose input is a hard-coded empty list — so every company in the database collects the same
free point from it. Share count is fetched and never scored, on the pillar named for capital
allocation. It is the most analyst-contaminated pillar by proportion.

**4. Growth / Forward** is a four-leg point-in-time scorecard, not a trajectory: one annual
year-over-year revenue change, a trailing-vs-forward P/E discount, and an "EPS trend" that is
actually an **analyst-surprise** trend. It reads no FCF, no operating income, no
`fundamental_series`, and does no CAGR or regression. Ten annual rows are fetched and two are
used. Its `edgar` parameter is accepted and never read.

**5. Valuation** is the only component with real machinery and the only one that can refuse
outright — it raises if the FRED 10-year rate is missing. Three anchors (risk-free, sector,
own-history) are measured as yields and the **least favourable binds**; five lenses reach it
by three different mechanisms. It handles negative and zero inputs better than everything
else in the engine, because those gates were ruled into existence individually after live
defects. Its scoring path is analyst-free by an explicit 2026-08-09 ruling.

**6. Expected Return E(R)** is the number CALIBER is graded on, and it is the **only quantity
in the system with no deterministic derivation**. It is the probability-weighted mean of
three price targets written by the LLM, divided by the live price. No pillar score enters it.
There is no reversion component, no growth component, and **no horizon stated anywhere** —
yet the grader measures the outcome at exactly 90 days. Its one real defence is the B-2
anchor-divergence guard, which verifies the model priced off the right base price.

**7. Stage Classifier** is a top-down rule cascade (DECLINE → YOUNG → HIGROWTH → MATURE,
first match wins) over legs that are each either measured or **typed as absent with a
reason**. It is the best-engineered component audited: absence is first-class, each gate
refuses the tag it guards, and a feed flake skips the write entirely rather than
manufacturing a verdict. It has **zero analyst input**. Three of its legs read the
`fundamental_series` **database table** rather than the live feed, which is the coupling
behind the stale-stage problem.

---

## 2. ★★ CONSOLIDATED TABLE — ANALYST CONTAMINATION AND FAIL-OPEN DEFECTS

### 2.1 Analyst / estimate-derived inputs

| Component | Analyst-derived input | Points at stake | Live evidence |
|---|---|---|---|
| **E(R)** | **★★ 100% — the three scenario price targets and their probabilities are LLM output; the prompt explicitly invites *"analyst views"* from training knowledge** (`synthesis/prompt.py:104`) | **the entire graded number** | every eval |
| **Management** | **★★ `beat_rate` (2 pts) + `avg_surprise` (2 pts) + the `improving` bonus — all measured against `epsEstimated`** | **4 of 6** | QBTS avg surprise **−245.2%** |
| **Growth** | **★★ `forward_pe` from `analyst-estimates.epsAvg` (2 pts); "EPS trend" is the same analyst-surprise trend as Management** | **3 of 6** | MU discount **83.07%** |
| **Valuation** | ★★ `forward_pe` → `earnings_yield_forward` — **computed into every panel, mapped to no lens, scores nothing**; can still lower confidence via `min_conf` | **0 scored** | MU forward yield 28.4%, unused |
| Business Quality | **none** | 0 | — |
| Financial Health | **none** | 0 | — |
| Stage Classifier | **none** | 0 | — |

**★★ THE SAME ANALYST-SURPRISE `trend` VALUE IS SCORED TWICE**, in Growth (`core/pillars.py:396`)
and in Management (`:277`), from one `_analyze_earnings` computation. QBTS collected a point
in both pillars off a surprise series whose mean is **−245.2%**.

**★ THE PRECEDENT ALREADY EXISTS.** The cyclical valuation basis was **ruled TRAILING** on
2026-08-09 for exactly this reason — *"on a forward basis MU scores 5 … at a cycle peak; that
unanimity IS the 2018 signature"*. That reasoning was applied to one lens and never
generalised.

### 2.2 Fail-open defects, ranked

| # | Component | Defect | Live evidence |
|---|---|---|---|
| **1** | **E(R)** | **★★ NO HORIZON EXISTS. The prompt states none; the grader measures at exactly 90 days.** A well-calibrated 12-month target grades as model error, and nothing can tell the two apart. | first gradeable cohort **~2026-11-26** |
| **2** | **Financial Health** | **★★ `if de <= 30: pts += 3` has no lower bound — NEGATIVE BOOK EQUITY SCORES FULL MARKS FOR LEVERAGE.** Identical class to the RKLB negative-EV/EBITDA defect already ruled and fixed in `_valuation_standard`; the sign gate was never propagated. | structural; none of the 28 currently negative |
| **3** | **Management** | **★★ The insider leg's input is a hard-coded `[]`. `no_data` → +1 of 2, and `max_pts += 2` unconditionally — every company in the DB gets the same free point.** Absence is not merely permitted, it is paid. | QBTS / MU / V all `no_data` |
| **4** | **Growth** | **★★ A negative or missing P/E DELETES the 2-point earnings leg instead of scoring it.** QBTS scores **5** with the leg absent; **4** with it present at minimum. | QBTS `trailing_pe = −23.95` |
| **5** | **E(R)** | **★★ A missing scenario target is silently renormalised away.** Dropping MU's bear leg moves E(R) from **−15.74% to −3.52%** — a **+12.2pp** swing from an omission. Schema permits `null`. | structural, arithmetic shown |
| **6** | **Management** | **★★ The `improving` bonus is capped against a RUNNING subtotal, so it pays weak beaters and is swallowed for perfect ones.** | **MU beat 100% → bonus worth 0; QBTS beat 29% → bonus worth 1** |
| **7** | **Growth / Mgmt** | **★★ `epsEstimated == 0` fabricates a `0.0%` surprise; near-zero estimates produce unbounded outliers into an unweighted mean of ≤7 points.** Exposed population is exactly the YOUNG names. | QBTS **−245.2%**, live |
| **8** | **Business Quality** | **★★ Negative equity inverts ROE: loss-making + negative equity → positive ROE → up to full marks.** No equity-sign guard. | structural |
| **9** | **All four scorecards** | **★★ A missing input DELETES its leg (`max_pts` not incremented) rather than scoring zero — the denominator shrinks.** Universal shape; #4 is its sharpest instance. | QBTS Growth 4/4 |
| **10** | **All four scorecards** | **★ Total input absence returns a NEUTRAL 3, never a refusal**, in contrast to `RateUnavailable`. | structural |
| **11** | **Valuation** | **★★ Every lens opens `score = 3` and returns it unflagged if nothing resolves.** A measured 3 and a total-failure 3 are indistinguishable in `pillars_json`. The bank lens alone emits `BANK-INSTRUMENT-UNAVAILABLE`. | structural |
| **12** | **Financial Health** | **★★ Two FCF yields on two bases in one evaluation** — the pillar's inline `annual FCF ÷ market_cap` vs `TickerData.fcf_yield` (vendor TTM) — straddling a 3% scoring threshold. | **V: 2.949% stored, yet the bonus fired** |
| **13** | **Valuation** | **★★ The cyclical gate fires and its own `CYCLE-GATE-CAP-*` flag is filtered out** by the lens's flag propagation. Score correct, audit trail lossy. | **MU: no RICH flag, raw ≥3, stored 2** |
| **14** | **Stage Classifier** | **★★ MATURE is the silent residual** — every fail-closed refusal pushes a name toward it, so an unmeasurable name carries the same `computed_stage` as a genuinely mature one (the `INPUTS-INCOMPLETE` flag distinguishes them; the column does not). | structural |
| **15** | **Stage Classifier** | **★★ `REINVESTMENT_HEAVY` bar 1.50 reads VISA as HEAVY reinvestment at 0.871** — more capital-intensive than GOOG. Already flagged uncalibrated; this audit shows it produces a wrong reading on a live golden ticker. | **V, latent (rule 3 failed anyway)** |
| **16** | **E(R) / stage** | **★ `evaluate.py:193` prints `"annotation only, reads into NO score"` — false as written.** Stage reaches `tolerance_for()` and gates whether E(R) is published at all. | every run |

### 2.3 Stage routing — the one-line answer

**Six of the seven components ignore lifecycle stage completely.** No pillar reads it; a
pre-revenue YOUNG name and a MATURE compounder meet identical ladders everywhere. **Stage is
load-bearing in exactly one place: `tolerance_for()` → the B-2 divergence band (15/20/30%) →
whether E(R) is published.** QBTS's approved `HIGROWTH → YOUNG` flip moved its band 20% → 30%.

### 2.4 Signature parameters accepted and never read

| Component | Parameter | Status |
|---|---|---|
| Growth | **`edgar`** | never referenced in the body |
| Financial Health | **`lens`** | `method=lens` label only |
| Management | **`lens`** | `method=lens` label only |
| Business Quality | `lens` | **read** — one flag, no score effect |
| Valuation | `lens` | **fully load-bearing** |
| Stage Classifier | `lens` | **fully load-bearing** (3 uses) |

---

## 3. DEAD CODE PATHS — BUILT, NEVER READ

| Item | Where | Note |
|---|---|---|
| **`insider_transactions`** + all of `_analyze_insiders` | `fmp_adapter.py:508`, `pillars.py:89-123` | hard-coded `[]`; `cluster_buy` / `cluster_sell` / `routine_sell` are **unreachable branches**; only `"no_data"` can return |
| **`target_mean_price`** | `fmp_adapter.py:452` | sell-side consensus target — fetched, currency-guarded as score-bearing, **read by nothing**, while E(R) is built from LLM targets |
| **`revenue_growth_trajectory`** | `fmp_adapter.py:513` | quarterly revenue-growth shape built and carried; **no scorer reads it** |
| **`roa`** | `pillars.py:131` | fetched, EDGAR-cross-checked, persisted; **scores nothing** — confidence only |
| **`shares_outstanding`** | `pillars.py:322` | the one capital-allocation signal available; **scores nothing** on the capital-allocation pillar |
| **`profit_margin`** | `edgar_cross_check.py:147` | fetched, cross-checked, currency-classified; **no scorer reads it** |
| **`operating_cashflow`** | `reporting_currency.py:180` | listed in `MONETARY_SCORE_BEARING_FIELDS`; **no scorer reads it** |
| **`enterprise_value`** | `reporting_currency.py:182` | same — only the derived `ev_to_*` ratios are used |
| **`METRIC_FORWARD_EARNINGS_YIELD`** | `valuation_anchors.py:508` | computed into every panel; **mapped to no lens** |
| **`haircut_score`** | `valuation_anchors.py:803` | computed on every panel, applied to no production score — *"MEASURED not applied"* by ruling. **V's is 1 against a stored 2.** |
| **`LENS_METRIC["growth"]`** | `valuation_anchors.py:710` | unreachable in production — `_valuation_growth` takes no panel; the panel mapping for growth was **rejected permanently** |
| **`per_scenario_returns`** | `synthesis/schema.py:220` | computes exactly the bull/base/bear decomposition this audit needed; **no production caller** |
| **`AnchorCheck.divergence` / `.implied_anchor`** | `synthesis/schema.py:274-277` | computed every eval as a *"permanent dark-launch for ongoing calibration"* — but **there is no column for either in `evaluations`**, so the series is not accumulating |
| **`SynthesisOutput.expectedReturn`** | `synthesis/schema.py:59` | model's own E(R); used only as the anchor denominator, **never persisted separately** (MU: −14.2 vs computed −15.74) |
| **`cyclical_peaks`** | `lifecycle.py:741` | recorded with outcome `None` — **deliberate** calibration evidence, no rule reads the value |
| **`fetch_at` / `fetched_at`** | `core/datatypes.py` | metadata, unread |

**Two are deliberate and must not be "cleaned up":** `haircut_score` and `cyclical_peaks` are
both measured-not-applied **by ruling**. They are listed so a later session does not mistake
them for live behaviour, and does not delete them as dead weight.

**★ ONE CORRECTION TO THIS AUDIT'S OWN METHOD, RECORDED BECAUSE THE SHAPE RECURS.** The first
dead-field sweep ran over `.attribute` text only and reported **`is_etf` as dead**. It is not:
`core/etf_guard.py:78` reads it via `getattr(yf, "is_etf", None)`, and the ETF guard shipped
yesterday (`05c37d3`). This is precisely the hazard CLAUDE.md already records for the
`--db-path` sweep — *"a sweep that only counts keywords will re-raise all five; count
positionals"*. The sweep was re-run over attribute **and** string forms before anything above
was written down.

---

## 4. WHAT THIS AUDIT DID NOT FIND — so it is not re-investigated

- **No ordering defect anywhere.** FMP serves `earnings` newest-first and `_analyze_earnings`
  reads it newest-first. The `core/technicals.py` reversal has no sibling in any component.
- **No currency exposure in any pillar.** Every growth, quality and management input is
  currency-neutral by construction and explicitly listed as such in
  `core/reporting_currency.py:188-198`.
- **No division-by-zero anywhere.** Every ratio site guards its denominator. It is what the
  guards **return** — a deleted leg or a neutral 3 — that is the finding, never a crash.
- **No reconciliation drift.** All 15 pillar scores and all 3 E(R) values across QBTS, MU and
  V were recomputed by hand from stored provenance and matched the stored values exactly
  (E(R) to 1e−9).
