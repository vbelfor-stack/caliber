# ORDER RECORD — Phase L: Lifecycle Stage Classification

**Recorded to repo:** 2026-08-16, BEFORE any implementation work, per the standing rule set
2026-08-15 (orders are recorded verbatim before execution so the terms survive a session
death mid-order).

**DELIVERY HISTORY — the order arrived in TWO parts.** Part 1 (§0–§4) arrived TRUNCATED at
the header `## 5. Stage-conditioned behaviors` with no body. It was recorded here
truncation-and-all, uncompleted, and the truncation was reported rather than silently
finished (precedent set 2026-08-15). Part 2 (§5–§9 plus six rulings R1–R6 amending §2/§3)
was supplied on request and is appended below in place. **The order is now COMPLETE.**
Both parts are verbatim. Code's reading, and the open questions that survive the completed
text, are stated SEPARATELY in the "RECORDING NOTE" section after the order text and are
not part of the order.

---

## ORDER TEXT — VERBATIM AS RECEIVED

# CALIBER — Phase L Work Order: Lifecycle Stage Classification
**Status:** ACTIVE — Phase H closed (H-4 deferred). Blocks Phase M.
**Author:** Chat (work-order author) · **Approver:** Vic (architect/gatekeeper) · **Implementer:** Claude Code
**Drafted:** 2026-08-15 · **Recorded to repo:** 2026-08-16 (original chat-side file did not persist)

---

## 0. Purpose

Add a **lifecycle stage tag** per ticker as a second classification axis, orthogonal to the Phase D valuation lens. Stage is classified from fundamentals — never from age-since-IPO or market cap. Stage feeds: (a) Phase M distribution-width priors, (b) reliability expectations (stage-conditioned divergence tolerance), (c) lens-compatibility integrity checks, (d) supply-layer discipline enforcement for Young names.

Taxonomy is a four-stage collapse of Damodaran's six (Start-Up + Young Growth merged; Mature Growth + Mature Stable merged):

| Stage | Code |
|---|---|
| Young / Pre-earnings | `YOUNG` |
| High Growth | `HIGROWTH` |
| Mature | `MATURE` |
| Decline | `DECLINE` |

## 1. Dependencies

- **H-FCF complete**: per-year series for FCF, margins, reinvestment, revenue growth in SQLite. The classifier consumes these series directly. (Note: reinvestment column is NULL pending the D&A spec — see §2 item 4 for the v1 fallback.)
- Phase D lens assignment operational (lens is an input to the compatibility check, not to classification itself).

## 2. Classifier inputs (fundamentals only)

All from existing FMP/EDGAR-sourced tables — **no new data feeds**. Per ticker, computed over available history (minimum 2 fiscal years; below that, classify `YOUNG` with a data-insufficiency assertion):

1. Revenue growth: trailing 3y CAGR and most recent year
2. Operating margin: sign, level vs. sector, 3y trend direction
3. FCF sign: trailing and most recent year (from H-FCF tables)
4. Reinvestment ratio: capex + ΔWC vs. operating cash flow (or sales-to-capital where cleaner)
5. Capital return presence: dividends and/or net buybacks (share count trend)
6. Revenue trend: absolute decline test (2+ consecutive years of falling revenue)

Every classification decision carries **per-point assertions**: which input, which value, which rule fired.

## 3. Classification rules (v1 — deterministic, ordered)

Evaluated top-down; first match wins:

1. **DECLINE**: revenue declining ≥2 consecutive years AND (margin trend flat/down) AND capital returns or debt paydown dominant. Cyclical guard: if lens = cyclical, revenue decline alone never triggers DECLINE — require ≥3 consecutive years AND through-cycle peak-to-peak revenue lower. (Prevents MU-type downcycle misclassification.)
2. **YOUNG**: operating margin negative OR FCF negative in ≥2 of last 3 years OR history < 2 fiscal years.
3. **HIGROWTH**: revenue 3y CAGR ≥ 15% AND reinvestment ratio high (top-half of sector) AND capital returns absent or de minimis.
4. **MATURE**: everything else (positive earnings, moderate growth, capital returns present or reinvestment moderate).

Thresholds (15% CAGR, 2-of-3 FCF, sector-half reinvestment) live in versioned config — Vic-tunable globally, with per-point assertions on defaults. Damodaran model.xls decision logic was the reference for rule structure; thresholds are ours.

## 4. Override and audit

- Vic can override stage per ticker; override record = `(ticker, computed_stage, approved_stage, rationale_text, timestamp)`. **Rationale mandatory** — same anti-launder mechanics as Phase M.
- Overrides persist; re-review trigger on new annual filing: reclassify, report drift vs. standing override. Never silently reclassify an overridden name.
- Stage transitions (any ticker whose computed stage changes between runs) surface in a transition report — transitions are information, not noise.

<<<<<<< PART 1 AS RECEIVED ENDED HERE, MID-ORDER. PART 2 FOLLOWS, AS SUPPLIED. >>>>>>>

## 5. Stage-conditioned behaviors (wired in this phase)

1. **Anchor-divergence tolerance (B-1 guard):** stage-conditioned thresholds. `MATURE` keeps 15%; `HIGROWTH` 20%; `YOUNG` 30%. `DECLINE` keeps 15%. Values in config, Vic-tunable. Assertion on every guard evaluation states which threshold applied and why.
2. **Lens-compatibility integrity check (non-blocking flags):**
   - `YOUNG` + compounder lens → flag
   - `DECLINE` + growth lens → flag
   - `MATURE` + growth lens → flag (soft)
   - Bank lens exempt from all stage checks (banks classified normally but bank lens always wins).
3. **Supply-layer enforcement for YOUNG:** if stage = `YOUNG`, evaluation output must include a supply-layer section (lockup dates, float quality, insider overhang) or explicitly assert data-not-found. Formalizes the IPO-method rule (25-session base, lockup cliffs) as a required output block rather than a manual habit.
4. **Phase M handoff:** stage → distribution-width prior table (stub in this phase; consumed by M). `YOUNG` widest, `MATURE` tightest, exact multipliers deferred to M arming.

## 6. Storage

- `lifecycle_stage` table: ticker, computed_stage, inputs snapshot (JSON), rule_fired, assertions, run timestamp.
- `lifecycle_overrides` table: per §4.
- `lifecycle_transitions` view or table for the transition report.
- Config additions: thresholds (§3), stage-conditioned B-1 tolerances (§5.1), width-prior stubs (§5.4).

## 7. Testing gates

- Golden tickers expected stages (validate on arming, adjust if data says otherwise): MU `MATURE` (cyclical guard must hold it out of DECLINE in downcycle test fixture), GOOG `MATURE`, V `MATURE`, NOW `HIGROWTH`, WU `MATURE` or `DECLINE` — WU is the deliberate edge case; both DECLINE rule and cyclical guard get exercised against it.
- Unit: each rule fires on synthetic fixtures; ordering respected; insufficient-history path yields `YOUNG` + assertion.
- Guard tests: override without rationale rejected; silent reclassification of overridden name impossible; B-1 threshold selection asserted correctly per stage.
- Suite green at every commit. Dark-before-arm: classifier runs dark across full current portfolio + golden tickers; Vic reviews the stage table before any stage-conditioned behavior (§5) is armed. §5 behaviors armed one at a time, stop-and-report between each.

## 8. Out of scope

- No new data vendors. No ML/probabilistic classification — deterministic rules v1.
- No Damodaran managerial/governance overlays (board, CEO-type content).
- No automated sizing or trade output.
- No modification to lens assignment logic — compatibility checks flag, never reassign.

## 9. Sequencing and close protocol

- Queue: **L** (this order) → M.
- Stop-and-report boundaries: after §3 classifier (dark run review), then per §5 behavior armed.
- End-of-session push to origin. Update CLAUDE.md phase registry on start and close.

## Rulings — 2026-08-16 (Vic, via chat), amending §2/§3

R1. **Asserted-absent doctrine:** any missing classifier input is stamped asserted-absent with a reason. A missing input never satisfies a rule condition. Rules evaluate on their remaining legs; any classification with a missing leg carries an `inputs_incomplete` flag listing the absent legs — visible in the stage table and transition report, never silent.
R2. **FCF sign (V, all banks):** asserted-absent per R1; does not count toward YOUNG's 2-of-3 FCF test. Banks classified normally; bank lens always wins per §5.2.
R3. **Operating margin:** v1 consumes current margin sign only (existing TickerData point value). 3y trend and sector-relative level are OUT of v1 — asserted-absent until an operating_income series exists (future scope, not this order). DECLINE rule 1's margin-trend leg follows R1.
R4. **Revenue levels (cyclical guard):** fetch annual revenue levels from FMP income statements at classification time — existing vendor and adapter, compliant with §8. Series gaps break consecutive-year streaks (a gap never extends or manufactures a decline). 3y CAGR requires both endpoints present, else asserted-absent per R1.
R5. **Capital returns:** dividend data via FMP dividend endpoint (same vendor, permitted). Buybacks via shares_outstanding trend (existing instant_series). Debt paydown from existing balance data. If the dividend endpoint proves unusable, dividends go asserted-absent and capital returns evaluate on buybacks + debt paydown.
R6. **Reinvestment threshold:** "top-half of sector" is struck — no compliant source, and peer-set fetches are rejected per the peer-anchor precedent. Replace with an absolute config threshold on sales-to-capital (Vic-tunable, default proposed by Code at dark-run review with per-point assertions). NOW's single-point series → reinvestment asserted-absent per R1; rule 3 evaluates on CAGR + capital-returns legs.

## Ruling R11 — 2026-08-16 (Vic, via chat), resolving Code's open question E

R11 (resolves E). Margin-trend window = 3 fiscal years (latest FY vs FY-3, i.e. 4 data points), matching the CAGR leg's horizon — all DECLINE legs measure the same recent window, and DECLINE is a current-state classification, not a decade verdict. Window is a versioned config value, Vic-tunable, default 3y. Flat band stays ±100bp and is understood as calibrated to the default window; anyone widening the window revisits the band. Under R11, WU classifies DECLINE on measured data (four down revenue years, −36bp margin over 3y, dividend-paying) — this is the intended verdict; §7's WU expectation is settled as DECLINE. Additional confirmations adopted into the record: FMP honours limit=10 on income_annual (nine tickers, FY2016–2025 contiguous); MU held out of DECLINE twice over on through-cycle evidence, §7 confirmed; dividend endpoint usable with G-4 contract discipline mandatory — empty list = pays-none, fetch failure = unknown/asserted-absent, the two must never collapse; GOOG-gap correction accepted, gap-breaking logic still built defensively with a synthetic test case since no live one exists.

## Rulings — 2026-08-16 (Vic, via chat), second set, resolving Code's audit A–D

R7 (resolves A). R3 is amended: operating-margin trend IS in v1 scope, derived from the same income_annual fetch R4 authorizes (operating income ÷ revenue per FY). No extra fetch, no new feed. What stays out of v1: sector-relative margin level. Trend definition (deterministic): trend = latest FY margin minus earliest FY margin over the measured window, flat band ±100bp; "flat/down" = delta ≤ +100bp. DECLINE rule 1 therefore remains a full three-leg AND. R1's remaining-legs mechanics apply only to inputs with no compliant source after R4/R5/R7 (currently: FCF for V/banks, reinvestment for NOW, dividends if the endpoint fails). Precedence for AND-rules: a leg that is asserted-absent means the rule CANNOT fire — a classification as consequential as DECLINE is never awarded on partial evidence; the ticker falls through to the next rule with inputs_incomplete stamped.

R8 (resolves B). WU is a live DECLINE candidate and that is intended, not drama. §7 amended: WU expected DECLINE if the capital-returns leg holds on measured data, MATURE otherwise — the dark run decides, per-point assertions show which.

R9 (resolves C). Raise income_annual limit to 10. Per the standing FMP-limit pin, measure delivered depth empirically on the adapter's own path before relying on it. Cyclical guard minimum window: peak-to-peak requires ≥8 measured FYs; below that the guard is asserted-absent and, for cyclical-lens names, DECLINE cannot fire at all (through-cycle evidence or nothing — a guard that can't see a cycle doesn't get to rule on one). 3y CAGR requires the two endpoint years present; interior gaps (GOOG 2022–23) break consecutive-year streaks per R4 and make CAGR asserted-absent if an endpoint is missing. The limit change moves the fixture baseline: expected-delta set must name income_annual fixtures for all nine tickers plus any dependents (field_provenance, synthesis_cache, sqlite_sequence).

R10 (resolves D + dark-run notes). The guard is B-2, not B-1 — all code, config keys, and assertions use B-2; the order's §5.1 label was an authoring error, corrected here. Approved: YOUNG-UNCALIBRATED tripwire — §5.3 and the 30% tolerance arm on synthetic evidence only, so the first live YOUNG classification in production trips a loud flag for Vic review before its stage-conditioned behaviors are trusted, same mechanics as BANK-RUNG-UNCALIBRATED. Approved: dark runs name their own --db-path.

<<<<<<< ORDER TEXT ENDS. COMPLETE. >>>>>>>

---

## RECORDING NOTE (Code, 2026-08-16) — NOT PART OF THE ORDER

### Status after completion
All four items the session kickoff named are now present and specified: the cyclical guard
(§3 rule 1), the stage-conditioned tolerances (§5.1, 15/20/30/15), the YOUNG supply-layer
block (§5.3), and dark-before-arm one-behavior-at-a-time (§7 final bullet, §9).

Rulings R1–R6 resolve five of the six data-availability findings Code raised at part-1
recording. Resolution recorded for audit:

| Pre-order finding | Resolved by |
|---|---|
| V + banks absent from `fundamental_series` (no FCF) | **R2** — asserted-absent, does not count toward YOUNG's 2-of-3 |
| `reinvestment` 100% NULL | already anticipated by §2 item 4; fallback is `sales_to_capital` |
| No operating margin series | **R3** — v1 uses current margin SIGN only; trend/sector-level out of v1 |
| No revenue level series | **R4** — FMP `income-statement` annual, existing vendor+adapter |
| No dividend/buyback source | **R5** — FMP dividend endpoint; buybacks via `shares_outstanding` trend |
| "Top-half of sector" reinvestment unsourceable | **R6** — STRUCK, replaced with absolute config threshold |

### Data-availability findings from the pre-order audit (measured 2026-08-16, not reasoned)
Recorded here because they bear on §2 and §3 as written. Read-only queries against
caliber.db (md5 e13cbee6, unchanged by the audit) and the source tree.

1. **`fundamental_series` covers 4 tickers, not 5+.** MU, GOOG, NOW, WU — 557 rows.
   **V is absent entirely** (no capex concept filed → no FCF series). No bank is present.
   §2 item 3 ("FCF sign, from H-FCF tables") is unavailable for V, JPM, BK, USB, C.
2. **`reinvestment` is 100% NULL** — 96 of 96 rows, `null_reason='no_da_spec'`, exactly as
   the order anticipates. The §2 item 4 fallback is REAL AND POPULATED: `sales_to_capital`
   has FY values for MU (6y), GOOG (5y), WU (5y) — but **NOW has only 1 FY point (2025)**,
   so a 3y reinvestment trend is not computable for NOW.
3. **`operating_margin` IS NOT IN `fundamental_series`.** §2 item 2 (sign, level vs sector,
   3y trend) has no series behind it. Available instead: a single point value on
   `TickerData.operating_margin`, and an `operating_income` EDGAR flow spec from which a
   series could be built — that build is not in the order's scope as written.
4. **No revenue LEVEL series exists** — only `revenue_growth`. §2 item 6's "absolute decline
   test" is derivable from growth signs, but §3 rule 1's cyclical guard needs
   "through-cycle peak-to-peak revenue LOWER", which needs levels. Also note FY
   `revenue_growth` depth is 5 years for MU/NOW/WU and **GOOG's FY series has a gap**
   (2018,2019,2020,2021,2024,2025 — 2022 and 2023 absent), so "≥2 consecutive years" and
   a "3y CAGR" must both define their behavior across a hole in the series.
5. **No dividend or buyback data exists anywhere in the codebase.** §2 item 5 ("capital
   return presence: dividends and/or net buybacks") has NO feed behind it — grep over
   core/adapters/store/batch finds only two comments. Share-count trend IS available
   (`instant_series(edgar.financials, 'shares_outstanding')`, already used by the
   own-history anchor), so the buyback half is proxyable; **the dividend half is not**.
   §3 rule 1 also requires "capital returns or debt paydown dominant" and rule 3 requires
   "capital returns absent or de minimis" — both depend on this missing input.
6. **"Top-half of sector" reinvestment (§3 rule 3) has no source.** The only sector-level
   datum CALIBER holds is `fetch_sector_pe` — an exchange-scoped sector EARNINGS multiple.
   There is no sector distribution of reinvestment or sales-to-capital, and obtaining one
   would mean per-peer fundamental fetches, i.e. a NEW DATA FEED, which §2 forbids.
7. **`fundamental_series` only exists in production because a full live batch run created
   it.** A fixture or `--no-synthesis` run must name its own destination (`--db-path`).

### POST-COMPLETION AUDIT — four items reported before any build (2026-08-16)
Measured against the completed text. Reported, not worked around; nothing reinterpreted.

**A. R1 vs R3 make DECLINE unreachable in v1 — under one of two readings.** R1 contains two
sentences that conflict for an AND-rule: "a missing input never satisfies a rule condition"
and "rules evaluate on their remaining legs." §3 rule 1 is an AND of three legs, and R3
strikes one of them (margin trend) from v1 entirely.
  - Strict reading: the margin-trend leg can never be satisfied → **DECLINE can never fire
    in v1, for any ticker, on any data, including synthetic fixtures.**
  - Remaining-legs reading: rule 1 evaluates on revenue-decline + capital-returns alone,
    stamped `inputs_incomplete`.
The two readings disagree about the order's own named edge case: §7 expects WU to exercise
"both DECLINE rule and cyclical guard", which the strict reading makes impossible. **Needs a
ruling before the classifier is written** — it is the single highest-consequence ambiguity.

**B. WU declines in all three measurable years — the §7 edge case is live, not synthetic.**
FMP annual revenue: 2022 4,475.5M → 2023 4,357.0M → 2024 4,209.7M → 2025 4,041.1M. Three
consecutive declining years. WU is compounder-lens, so the cyclical guard does NOT apply and
the ≥2-year bar is cleared. Operating margin by year: 19.77% → 18.76% → 17.24% → 19.41% —
down three years then UP in 2025, which is exactly the leg R3 removes from v1. So WU's
classification is decided entirely by ruling A.

**C. `income_annual` is fetched at `limit=4` — four annual rows, and the cyclical guard
needs more.** R4 routes revenue levels through the existing adapter; that call is
`income-statement?symbol=X&period=annual&limit=4` (adapters/fmp_adapter.py:436). Consequences,
all measured on the current fixtures:
  - 3y CAGR needs 4 points and gets exactly 4 — zero margin, and R4's "both endpoints
    present" test will fail the moment a vendor row is missing.
  - §3 rule 1's "through-cycle peak-to-peak revenue lower" cannot be evaluated on 4 years in
    the general case. MU happens to fit by luck (peak 2022 30,758M → trough 2023 15,540M →
    peak 2025 37,378M, higher, so the guard holds MU out of DECLINE as §7 expects), but a
    cycle longer than the window would be invisible.
  - Raising the limit is compliant with §8 (same vendor, same adapter, one parameter) but it
    **changes the payload production requests and therefore moves the fixture baseline** —
    a deliberate manual step, never incidental. NOT DONE. Awaiting ruling.
  - Standing pin applies: FMP does not reliably honour `limit` (`price_history` asks 365 and
    receives ~1,255). Actual returned depth must be MEASURED on the adapter's own path, never
    assumed from the parameter.

**D. §5.1 calls the anchor-divergence guard the "B-1 guard"; in CALIBER it is B-2.** The
guard lives at `synthesis/schema.py:237` under the comment "Anchor-divergence guard (B-2)",
`ANCHOR_DIVERGENCE_THRESHOLD = 0.15`. B-1 was the status-semantics work (ok requires
synthesis). The 15% default and the described behaviour match B-2 exactly, so the INTENT is
unambiguous and no clarification is needed to act — recorded so the label does not propagate
into code and config names as "B-1".

**Adjacent observation, explicitly OUT OF SCOPE and not acted on:** FMP's `income_annual`
rows carry `depreciationAndAmortization`. H-4 and the NULL `reinvestment` column are blocked
on the absence of a D&A spec among the 19 EDGAR specs. This does not unblock H-4 as ordered
(that blocker is EDGAR-side, and `fundamental_series.reinvestment` is EDGAR-derived), and §8
forbids scope creep — flagged only because it is adjacent information Vic may want later.

### R9-DIRECTED MEASUREMENT — live, read-only, adapter's own path (2026-08-16)
`_get("income-statement?symbol=X&period=annual&limit=10", key)` — the adapter's own fetch
function, no code changed, no writes. Nine tickers.

- **DEPTH: 10 rows delivered for all nine** (MU GOOG V NOW WU JPM BK USB C), contiguous
  FY2016–FY2025, no interior gaps anywhere. FMP HONOURS `limit` on this endpoint (unlike
  `historical-price-eod/full`, which over-delivers). The ≥8-FY cyclical-guard minimum is
  therefore MET for every ticker, and the guard is live rather than vacuous.
- **CORRECTION TO CODE'S OWN EARLIER FINDING, and to R9's parenthetical.** The "GOOG
  2022–23 gap" is in the EDGAR-derived `fundamental_series.revenue_growth` series — **it does
  NOT exist in FMP `income_annual`**, which carries GOOG 2016–2025 complete. Since R4/R7 route
  BOTH revenue levels and margin through `income_annual`, GOOG has no gap for L's purposes.
  Gap-breaking logic still gets built (defensive, and other tickers/years will need it), but
  GOOG is not an instance of it and must not be used as its test case.
- **MU, cyclical guard now evaluable and it holds:** revenue peaks FY2018 30,391M → FY2022
  30,758M → FY2025 37,378M, i.e. peak-to-peak RISING, so "through-cycle revenue lower" is
  FALSE. Longest consecutive decline streak is 2 (FY2019, FY2020) — under the ≥3 cyclical
  bar — and the streak ending at the latest FY is 0 (FY2025 rose). MU is held out of DECLINE
  twice over, on measured through-cycle evidence. §7's expectation confirmed.
- **DIVIDEND ENDPOINT (R5) IS USABLE:** `dividends?symbol=WU&limit=8` returns 8 quarterly
  records (dividend, paymentDate, declarationDate, frequency). `dividends?symbol=NOW&limit=8`
  returns an EMPTY LIST — NOW pays no dividend. **G-4's contract discipline applies directly:
  `[]` must mean "pays none" and a failure must mean "unknown", and the two must not collapse
  into the same value.** An empty list read as "no capital returns" when the call actually
  failed would push a ticker toward DECLINE/HIGROWTH on absent evidence.

### OBSERVATION BLOCK — vendor drift seen during L-1a, DEFERRED (ratified 2026-08-16)
`tools/record_fmp_fixture` re-records the WHOLE payload, not one key. A full re-record of the
nine therefore captured today's prices, today's ratios, and a `splits` key that 7 of 9
fixtures deliberately lacked since G-4 — a delta far wider than R9's stated set.

Measured, full re-record vs committed baseline, 45 pillar cells — **4 moved**:

| Ticker | Cell | Move |
|---|---|---|
| NOW | Valuation | 1 → 2 |
| C | Financial Health | 2 → 1, gains `HIGH-LEVERAGE` |
| C | Valuation | 3 → 2, gains `RICH-VS-JUSTIFIED-PB` |
| V | Financial Health | 4 → 4 (score held), gains `CURRENT-RATIO-BELOW-1` |

**NONE of it is attributable to R9's limit change.** Isolated by splice experiment (committed
payload + ONLY the new 10-row `income_annual`): **0 of 45 cells moved**, and every
`revenue_growth` identical to the last decimal. The four moves are fresh vendor data riding
along with the re-record.

**RULED 2026-08-16: SPLICE RATIFIED, FULL RE-RECORD REJECTED FOR THIS PHASE.** The four cells
are recorded here as OBSERVED VENDOR DRIFT and deferred to a future deliberate
fixture-refresh decision. They are not Phase L's problem. Rationale for keeping the splice:
it is what R9 literally authorized, and per the CLAUDE.md ledger the D/E unit defect was
caught ONLY because the fixtures preserved a convention the live feed had moved off —
migrating a baseline onto the source it checks retires the check.

### OPEN QUESTION E — the margin-trend WINDOW decides WU, and R7 does not fix it
R7 defines trend as "latest FY margin minus earliest FY margin **over the measured window**"
but does not say how long that window is. Measured operating margins make the choice decisive:

| Window | WU earliest | WU latest | Delta | R7 verdict | WU stage |
|---|---|---|---|---|---|
| 10 FY (2016→2025) | 8.92% | 19.41% | **+1,049bp** | UP → leg FAILS | **MATURE** |
| 4 FY (2022→2025) | 19.77% | 19.41% | **−36bp** | flat/down → leg PASSES | **DECLINE** |

WU's revenue leg is unambiguous either way (four consecutive declining years, FY2021 5,070.8M
→ FY2025 4,041.1M) and its capital-returns leg is unambiguous (pays a quarterly dividend).
**So the swing factor is the margin window, NOT the capital-returns leg that R8 anticipated.**
Recorded, not resolved — a window length will not be chosen by Code.

**Two YOUNG-specific notes for the dark run:** (i) no ticker in the current universe is
expected to classify YOUNG, so §5.3's supply-layer block and the 30% tolerance would be
SYNTHETIC-TEST-ONLY on arming — the same "reasoned, not measured" condition that put
BANK-RUNG-UNCALIBRATED on the bank ladder's cheap rungs, and it should carry an equivalent
tripwire on first live YOUNG classification. (ii) `fundamental_series` exists in production
only because a full live batch created it; any fixture or `--no-synthesis` dark run must
name its own `--db-path`.
