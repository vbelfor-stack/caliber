# L-4f — 20-F/6-K FORM ADMISSION: STEP 1 BLAST-RADIUS SCOPE

**Status: STEP 1 COMPLETE, READ-ONLY. STOPPED FOR RULING. No source file changed, no row
written, `caliber.db` md5 unchanged (`c0bae79159d5d2a325c35fd87dceda88`).**

Measured 2026-08-21 against raw SEC companyfacts for all 28 evaluated names, plus a live
SEC lookup for the two ETF candidates. Method: the form set was substituted **in memory**
and the REAL resolver + real `build_fcf_series` were run — not a re-implementation. Same
method as the L-4d step-2 dark diff.

---

## 0. HEADLINE — THE ORDER'S PAYLOAD IS INVERTED

The order names **SKHY and any other ADR** as the primary payload and ARM as the motivating
case. Measurement reverses this:

- **ARM is the ONLY name in the universe that admission moves. At all.**
- **SKHY gains NOTHING and cannot** — it files no 20-F, no 6-K, and no financial XBRL of any
  kind. Its current fail-closed reason is already correct and stays correct.
- **There is no other ADR.** No 40-F exists anywhere in the universe.
- **And admission alone still delivers `+0` step-4 evaluability**, because a second,
  independent gate blocks ARM after the forms are admitted. See §4 — this is the finding.

**Expected coverage delta: `fundamental_series` 18 → 19 tickers, but step-4 evaluable
`+0 onto 18`.** LLY lands separately (`+1`, independent of this order).

---

## 1. FORM CENSUS — ALL 28 NAMES

Facts outside the 10-K/10-Q family, as a share of every fact in companyfacts:

| Name | Excluded | Forms | Reading |
|---|---|---|---|
| **ARM** | **4,373 / 4,373 (100%)** | **6-K 2,756 · 20-F 1,613** · S-8 4 | Foreign private issuer. **The whole payload.** |
| **SKHY** | **10 / 10 (100%)** | **F-1 5 · F-1/A 5** | Registration fees only — see §3 |
| C | 15,064 / 60,145 (25.0%) | 424B2 9,990 · 8-K 4,954 · 424B8/B3 | prospectus + current reports |
| JPM | 5,280 / 53,358 (9.9%) | 424B2 3,281 · 8-K 1,951 · DEF 14A · S-3/A | " |
| CAT | 1,761 / 39,403 (4.5%) | 8-K 1,731 · DEF 14A 30 | " |
| MU | 1,254 / 27,074 (4.6%) | 8-K 1,250 · S-8 4 | " |
| GOOG / GOOGL | 729 / 20,907 (3.5%) | 8-K 637 · DEF 14A · 424B5/B2 · S-8 | " |
| LLY | 695 / 23,295 (3.0%) | 8-K 689 · 424B2 6 | " |
| USB | 300 / 44,642 (0.7%) | 424B2 294 · 424B7 6 | " |
| CBRS / DPC / SPCX / XE | 13–23 each (3–5%) | S-1, S-1/A, S-1MEF, S-8 | recent IPOs |
| BE, BK, INFQ, IONQ, LITE, NOW, NVDA, QBTS, RKLB, V, WU | ≤ 62 each (≤0.3%) | DEF 14A, 424B*, SC TO-I, S-8 | noise |
| FN, LRCX, STX | 0 | — | pure 10-K/10-Q |

**No domestic name files a single 20-F or 6-K fact.** The "zero domestic movement" hard
expectation is therefore not merely observed, it is **structural**: the forms being admitted
do not occur on any domestic filer, so no domestic cell *can* move.

Note the 424B2/8-K mass on C and JPM. Those are prospectus supplements and current reports —
**not** periodic financial statements, and **not** in this order's scope. They are named here
only so a later session does not read "25% of C's facts are excluded" as a coverage finding.

**ETF candidates, measured live, not assumed:** `LYTE` and `FLTW` **do not appear in SEC
`company_tickers.json` at all — no CIK, nothing filed under either ticker.** (ETFs file under
their trust's CIK.) They are already excluded from `tickers.txt` and remain out of scope.
`INFQ` was also checked and is a **domestic 10-K/10-Q filer** (INFLEQTION, INC.) — not a
foreign filer, and unaffected.

---

## 2. ARM — WHAT ADMISSION BUYS, MEASURED

**Cadence** (13 XBRL accessions, IPO Sept 2023, FY ends 03-31):

- **20-F, annual, filed late May** — FY2024/25/26 (period-ends 2024/2025/2026-03-31)
- **6-K, quarterly, filed Aug / Nov / Feb** — Q1/Q2/Q3 (Jun/Sep/Dec ends). **No Q4 6-K**;
  Q4 is subsumed by the 20-F. Latest fact: 6-K filed 2026-07-29 for 2026-06-30.

So the shape is **3 + 1 per year — the 10-Q × 3 + 10-K × 1 shape**, under different form
names.

### 2.1 The cumulative-basis question, answered per the order (not assumed away)

6-K interim reporting is **not** uniform, and the two statement types differ:

| Concept group | 6-K durations filed | Basis |
|---|---|---|
| revenue, cost_of_revenue, gross_profit, operating_income, net_income | **90/91d QTD *and* 182d/274d YTD** | both |
| operating_cashflow, capex | **90d, 182d, 274d only** | **YTD-cumulative only** — no standalone Q2/Q3 |

Against `_assemble_ttm`'s three paths at the live period-end 2026-06-30:

1. `ttm_annual` — newest fact is 90d. **Fails.**
2. `ttm_summed` — needs four contiguous QTD. **Fails even for the income statement**, because
   no Q4 QTD is filed: the run is Jun/Sep/Dec then a 91-day hole to the next Jun.
3. `ttm_reconstructed` — prior FY + current YTD − prior-year YTD. **SUCCEEDS.**

**And path 3 requires BOTH FORMS: the 20-F supplies `prior_fy` (FY2026, 364d, ending
2026-03-31) and the 6-K supplies `current` and `prior_ytd`.** This is the scope decision:

| Scope | Resolves via | Latest period-end | FCF points | Rows written |
|---|---|---|---|---|
| 20-F only | `ttm_annual` | 2026-03-31 | **5** (annual only) | 23 |
| 20-F + 6-K | `ttm_reconstructed` | **2026-06-30** | **14** (quarterly TTM) | 62 |

Values verified by hand against the filings: OCF `1,524 + 902 − 332 = 2,094M`;
capex `545 + 197 − 154 = 588M`; **FCF TTM = 1,506M**. FY2026 FCF = `1,524 − 545 = 979M`.

### 2.2 ARM field matrix — 19 fields, before and after

| Field | Now (A) | +20-F (B) | +20-F+6-K (C) | Post-admission status |
|---|---|---|---|---|
| revenue | `no_tag` | ✔ | **5,156M** `ttm_reconstructed` | resolvable |
| cost_of_revenue | `no_tag` | ✔ | **127M** | resolvable |
| gross_profit | `derive_incomplete` | ✔ | **5,029M** | resolvable (tagged, not derived) |
| operating_income | `no_tag` | ✔ | **877M** | resolvable |
| net_income | `no_tag` | ✔ | **1,044M** | resolvable |
| operating_cashflow | `no_tag` | ✔ | **2,094M** | resolvable |
| capex | `no_tag` | ✔ | **588M** | resolvable |
| total_assets | `no_tag` | ✔ | **11,196M** `instant` | resolvable |
| current_assets | `no_tag` | ✔ | **6,339M** | resolvable |
| total_liabilities | `no_tag` | ✔ | **2,566M** | resolvable |
| current_liabilities | `no_tag` | ✔ | **1,207M** | resolvable |
| cash | `no_tag` | ✔ | **3,058M** | resolvable |
| short_term_investments | `no_tag` | ✔ | **830M** | resolvable |
| operating_lease_liability | `no_tag` | ✔ | **432M** | resolvable (20-F only, 2026-03-31) |
| equity | `no_tag` | ✔ | **8,630M** | resolvable |
| shares_outstanding | `no_tag` | ✔ | **1,064,055,252** | resolvable (dei, 20-F) |
| **long_term_debt** | `no_tag` | `no_tag` | `no_tag` | **truthful `no_tag`** |
| **current_debt** | `no_tag` | `no_tag` | `no_tag` | **truthful `no_tag`** |
| **total_debt_reported** | `no_tag` | `no_tag` | `no_tag` | **truthful `no_tag`** |

**0 → 16 of 19.** The three that stay blocked are genuine: ARM files **no debt concept of any
kind** (all 9 synonyms across the three fields absent from companyfacts). That is a correct
fail-closed reason both before and after, and it is the right answer — ARM is debt-free.

---

## 3. SKHY — THE ORDER'S NAMED PAYLOAD, REFUTED ON MEASUREMENT

SKHY's **entire** companyfacts is 1,863 bytes and contains **no `us-gaap` namespace at all**.
Everything in it is `ffd` — SEC **filing-fee** data:

    ffd:NetFeeAmt        138,100 (F-1, filed 2026-06-24) · 4,031,505.56 (F-1/A, 2026-07-06)
    ffd:TtlFeeAmt        138,100 · 4,169,605.56
    ffd:TtlOfferingAmt   1,000,000,000

That is the registration-fee table from **SK hynix's $1B F-1 IPO registration statement**, a
new registrant that has not yet filed one periodic report. **F-1 is a registration statement,
not a periodic report**; an F-1 registrant becomes a 20-F filer only after its first fiscal
year-end post-effectiveness.

**Admitting 20-F/6-K buys SKHY exactly zero, now and until it files its first 20-F.** Its
current reason — `operating_cashflow:no_tag; capex:no_tag` — is **accurate and stays
accurate**. SKHY remains correctly fail-closed. Admitting F-1 would be admitting a fee table
as a financial statement and is not proposed.

---

## 4. ★ THE FINDING — ADMISSION ALONE BUYS `+0` STEP-4 EVALUABILITY

ARM resolves 16 of 19 fields and emits a 14-point FCF series. **Every one of those points is
labelled `TTM_Q`. Not one is labelled `FY`:**

```
ARM FCF series, +20-F+6-K          ARM FCF series, +20-F only
2026-06-30  TTM_Q  1,506M  recon   2026-03-31  TTM_Q  979M  ttm_annual
2026-03-31  TTM_Q    979M  annual  2025-03-31  TTM_Q  178M  ttm_annual
2025-12-31  TTM_Q    977M  recon   2024-03-31  TTM_Q  998M  ttm_annual
   … 11 more, all TTM_Q …          2023-03-31  TTM_Q  675M  ttm_annual
                                    2022-03-31  TTM_Q  424M  ttm_annual
```

The step-4 reader is FY-only:

```sql
-- evaluate.py:115  _fy_series_from_db
WHERE ticker=? AND metric=? AND period_type='FY' AND superseded=0
```

and the labeller (`core/fundamental_series.py:268`) is:

```python
if r.get("fp") == "FY" and str(r.get("form", "")).startswith("10-K"):
```

**ARM tags `fp='FY'` correctly — on form `20-F`. `_fy_ends(ARM)` returns the EMPTY SET**,
verified directly on all 15 qualifying facts. So the five points that genuinely ARE ARM's
fiscal year ends (2022–2026-03-31) are labelled `TTM_Q`.

**Consequences, stated plainly:**

1. **Step-4 evaluability delta is `+0 onto 18`.** ARM would appear in `fundamental_series`
   (18 → 19 tickers, +62 rows) while remaining invisible to step 4. `fundamental_series`
   coverage and step-4 evaluability, identical for all 18 names today, **would diverge for
   the first time.**
2. **It would write a known mislabel into production.** Five rows asserting `TTM_Q` about a
   period the issuer itself tagged `FY`. That is precisely the class L-4d killed — *"a
   constant asserting 'no tag' cannot know which of four causes occurred"* — in a new place.
   Landing forms without the FY gate trades a **truthful** block (`form_excluded`, which
   currently says exactly the right thing) for a **false** label.
3. ARM adds **no name to the R2 YOUNG signal** either way — its FCF is positive at every
   period-end, so all-negative-last-3 stays IONQ/QBTS/RKLB/C.

The fix is small — `startswith(("10-K", "20-F"))` — but it is a **different module**, it
changes what `period_type` *means* for a foreign filer, and this order says "admit the
forms." **It is not mine to fold in. It needs its own ruling.**

---

## 5. FIXTURE AGING — ZERO, AND THE REASON MATTERS

Per the pinned L-4d finding, checked before assuming:

- All 9 EDGAR fixtures (BK, C, GOOG, JPM, MU, NOW, USB, V, WU) are **domestic 10-K/10-Q
  filers**. **Not one 20-F or 6-K fact in any of them.** No ARM or SKHY fixture exists.
- **This change ages NO fixture** — unlike the L-4d synonym. The mechanism differs: a synonym
  changes *which concepts extraction pulls*, so a recorded concept dict goes stale. The form
  filter only drops facts that were **never recorded in the first place**.
- **But the same asymmetry produces a different hazard.** The fixture replay path
  (`edgar_adapter.py:952`) calls `resolve_financials` **directly, bypassing
  `_extract_xbrl_facts`** — so the form filter **never runs offline at all**. It follows that
  (a) no fixture-based test can cover this change, and Step 2's pins must be **synthetic-fact
  pins** against `_extract_xbrl_facts` (the shape `tests/test_l4d_typed_reasons.py` already
  uses); and (b) **`form_excluded` is never populated on the fixture path**, so offline
  `withheld_reason` can never report `form_excluded`. Pre-existing, latent, **recorded not
  fixed** — it is not this order's scope.

**Recommendation: do NOT re-record any fixture.** Nothing ages, so there is nothing to
re-record; and recording an ARM fixture is a deliberate baseline-moving step that should ride
with the arm ruling, not precede it.

---

## 6. CLASSIFICATION MATRIX — the order's three buckets

| Name | Bucket | Post-admission status |
|---|---|---|
| **ARM** | **a fourth bucket the taxonomy lacks** | **Fully resolvable (16/19), TTM *not* blocked — blocked on FY *labelling*.** Writes 62 rows, 0 FY, step-4 invisible. |
| **SKHY** | blocked on something else (typed) | No periodic filing exists. `no_tag` accurate before and after. **+0.** |
| all 26 others | unaffected | **Zero movement, structurally guaranteed** — no 20-F/6-K fact exists on any of them. |

ARM is neither "fully resolvable" nor "TTM-blocked". TTM assembles cleanly on
`ttm_reconstructed`; the block is one line of form-prefix matching in a different module.

---

## 7. RULINGS NEEDED BEFORE STEP 2

1. **Scope.** 20-F only (5 annual points, data to 2026-03-31) or **20-F + 6-K** (14 points,
   current to 2026-06-30)? Include the `/A` amendments? *Code's reading: 20-F + 6-K + both
   `/A` forms — it mirrors the existing 10-K/10-Q/`/A` family exactly, and 6-K is what
   supplies the `prior_ytd` leg that path 3 needs.*
2. **★ The FY gate (`_fy_ends`).** Admission alone is `+0` to step 4 and writes five
   mislabelled rows. Three options: **(a)** rule the gate into L-4f, **(b)** land forms now
   and accept a 19th ticker that step 4 cannot see, **(c)** hold the write until the gate is
   ruled separately. *Code's reading: (a) or (c). **(b) writes a known-false label into
   production**, which the L-4d ruling forbids in this exact shape.*
3. **Does the arm write ARM's rows at all**, or land the extraction change dark and write
   under a later order? The two are separable: the form admission is inert until
   `expand_fcf_series` is pointed at ARM.

**Nothing proceeds until these are ruled.** Measurement harness is `.scratch_l4f/scope.py`
(gitignored, read-only); the raw facts are the `.scratch_lly/facts/` dumps recorded
2026-08-21, re-verified live against SEC this session for ARM/SKHY/INFQ.

### Positive control on the harness

The offline harness reproduces the known production baseline **exactly**: 18 names carry FY
FCF points, NVDA 5 and the other 17 six apiece — matching the CLAUDE.md close block value for
value. A harness that could not reproduce the current state would prove nothing about the
change.

---
---

# STEP 2 — DARK DIFF (measured 2026-08-21, PRE-ARM)

Ruling received on all three §7 questions: **scope = 20-F + 6-K + `/A`**; **`_fy_ends` gate
folded into L-4f (option a)**; **ARM writes in this order, one write point.**

Both changes substituted **in memory**; the real resolver and the real `build_fcf_series`
measured. Nothing written, no source file modified, md5 unchanged.

## 8.1 The proposed change

```python
# adapters/edgar_adapter.py
_XBRL_ANNUAL_FORMS  = {"10-K", "10-K/A", "20-F", "20-F/A"}
_XBRL_INTERIM_FORMS = {"10-Q", "10-Q/A", "6-K", "6-K/A"}
_XBRL_VALID_FORMS   = _XBRL_ANNUAL_FORMS | _XBRL_INTERIM_FORMS

# core/fundamental_series.py:268
- if r.get("fp") == "FY" and str(r.get("form", "")).startswith("10-K"):
+ if r.get("fp") == "FY" and r.get("form") in _XBRL_ANNUAL_FORMS:
```

**The gate rewrite is provably a no-op domestically.** `_fy_ends` reads POST-extraction
concepts, so it can only ever see admitted forms. Over the old admitted set
`{10-K, 10-Q, 10-K/A, 10-Q/A}`, `startswith("10-K")` **is** membership in `{10-K, 10-K/A}`.
Verified across the universe: the only `10-K*`/`20-F*` strings that exist anywhere are
`10-K` (187,682), `10-K/A` (1,780) and `20-F` (1,613) — **no `10-KT`, no `10-K405`**, and any
such form would be dropped by the form filter before `_fy_ends` ever saw it.

## 8.2 THE DIFF — 28 names × 19 fields = 532 cells

| | |
|---|---|
| **Field cells moved** | **16 of 532** — all ARM |
| **Names moved** | **1 of 28** (ARM). 27 bit-identical. |
| **Domestic names moved** | **ZERO** — required, and structural |
| **Other ADRs moved** | **ZERO** — there are none; SKHY unchanged and correctly fail-closed |

ARM, every moved cell:

```
revenue                    no_tag             ->  5,156,000,000  ttm_reconstructed
cost_of_revenue            no_tag             ->    127,000,000  ttm_reconstructed
gross_profit               derive_incomplete  ->  5,029,000,000  ttm_reconstructed
operating_income           no_tag             ->    877,000,000  ttm_reconstructed
net_income                 no_tag             ->  1,044,000,000  ttm_reconstructed
operating_cashflow         no_tag             ->  2,094,000,000  ttm_reconstructed
capex                      no_tag             ->    588,000,000  ttm_reconstructed
total_assets               no_tag             -> 11,196,000,000  instant
current_assets             no_tag             ->  6,339,000,000  instant
total_liabilities          no_tag             ->  2,566,000,000  instant
current_liabilities        no_tag             ->  1,207,000,000  instant
cash                       no_tag             ->  3,058,000,000  instant
short_term_investments     no_tag             ->    830,000,000  instant
operating_lease_liability  no_tag             ->    432,000,000  instant
equity                     no_tag             ->  8,630,000,000  instant
shares_outstanding         no_tag             ->  1,064,055,252  instant
* latest_period_end        None               ->  2026-06-30
* withheld                 fcf: form_excluded ->  {} (nothing withheld)
* n_fy                     0                  ->  5      <-- THE GATE WORKS
```

`long_term_debt`, `current_debt`, `total_debt_reported` stay `no_tag` — **correct**, ARM
files no debt concept of any kind.

## 8.3 FY labelling post-gate — the point of option (a)

```
2026-06-30  TTM_Q  1,506M  ttm_reconstructed     2024-03-31  FY     998M  ttm_annual
2026-03-31  FY       979M  ttm_annual            2023-12-31  TTM_Q  809M  ttm_reconstructed
2025-12-31  TTM_Q    977M  ttm_reconstructed     2023-09-30  TTM_Q  921M  ttm_reconstructed
2025-09-30  TTM_Q  1,151M  ttm_reconstructed     2023-03-31  FY     675M  ttm_annual
2025-06-30  TTM_Q    675M  ttm_reconstructed     2022-03-31  FY     424M  ttm_annual
2025-03-31  FY       178M  ttm_annual
2024-12-31  TTM_Q    650M  ttm_reconstructed     14 points, 5 FY — labels now TRUTHFUL
2024-09-30  TTM_Q    579M  ttm_reconstructed
```

## 8.4 ★ ROW COUNT CORRECTED — 72, NOT 62

The §4 figure of 62 was measured with `price_history=None`, so `fcf_yield` never emitted.
Re-measured through the **real production path** (live `fetch_fmp` + `fetch_edgar` +
`fetch_splits`, the same calls `build_one` makes):

| metric | rows | of which FY |
|---|---|---|
| fcf | 14 | 5 |
| fcf_margin | 14 | 5 |
| reinvestment | 14 | 5 |
| fcf_growth | 10 | 4 |
| fcf_yield | 10 | 3 |
| revenue_growth | 10 | 4 |
| **TOTAL** | **72** | |

`sales_to_capital` emits **0** rows (no debt tags → invested capital uncomputable). Not
disqualifying: **5 of the current 18 covered names (BE, BK, C, FN, IONQ) already carry zero
`sales_to_capital` rows** and are counted evaluable. Step-4 evaluability is the `fcf` FY
series, and ARM has 5.

`basis = split_restated` (FMP returned 0 split events — corroborated, nothing to restate).

## 8.5 EXPECTED DELTA — stated before any write

| | before | after | delta |
|---|---|---|---|
| `fundamental_series` rows | 2,302 | **2,374** | **+72** |
| `fundamental_series` tickers | 18 | **19** | **+1 (ARM)** |
| **step-4 evaluable** | 18 of 28 | **19 of 28** | **+1** |
| every other table | — | — | **+0** |

ARM FY FCF, oldest-first as step 4 reads it:
`2022-03-31 424M · 2023-03-31 675M · 2024-03-31 998M · 2025-03-31 178M · 2026-03-31 979M`

**R2 YOUNG signal UNCHANGED.** ARM's last three FY FCF are `[998M, 178M, 979M]` — not
all-negative, so the all-negative set stays **IONQ / QBTS / RKLB / C**.

LLY lands separately under L-4d.1 (`+1`, independent of this order).

## 8.6 SECOND-ORDER EFFECT — ARM GAINS `high` CONFIDENCE ON 8 FIELDS

Not a defect; the system working. Stated because it is a scoring-path change the field/row
diff does not show. The armed cross-check goes from **15 × `no_edgar`** to:

- **`agree` × 8 → confidence `medium` → `high`, source `fmp+EDGAR`**: gross_margin (2.30%),
  operating_margin (1.68%), profit_margin (0.00%), roe (2.71%), roa (0.00%),
  current_ratio (0.00%), shares_outstanding (0.37%), total_cash@FY (0.00%)
- **`basis_mismatch` × 3, advisory only**: total_cash (MRQ vs annual), operating_cashflow and
  free_cashflow (EDGAR TTM vs FMP annual — a basis difference, not a disagreement)
- **`no_edgar` × 4**: the three total_debt variants + debt_to_equity — ARM has no debt tags

This makes the `[ANTI-LAUNDER: high-conf miss]` NOTE reachable on ARM.

## 9. ★ ARM'S CAPEX RECONCILES EXACTLY IN FY25/FY26 AND DIVERGES IN FY22–FY24 — THE LLY SHAPE AGAIN

Run per the LLY precedent, and it found the same class of defect in a different issuer.
**OCF matches FMP on all five years.** The entire divergence is capex:

| FY end | EDGAR FCF | FMP FCF | delta | |
|---|---|---|---|---|
| 2026-03-31 | 979M | 979M | **0.0%** | exact |
| 2025-03-31 | 178M | 178M | **0.0%** | exact |
| 2024-03-31 | 998M | 947M | +5.4% | diverges |
| 2023-03-31 | 675M | 646M | +4.5% | diverges |
| 2022-03-31 | 424M | 383M | +10.7% | diverges |

**Cause identified to the dollar: FMP's `capitalExpenditure` bundles
`PaymentsToAcquireIntangibleAssets` in FY2022–FY2024 and drops it in FY2025–FY2026.**

```
PaymentsToAcquireIntangibleAssets   FY22 41M  FY23 29M  FY24 51M   FY25 20M  FY26 30M
the unexplained gap                 FY22 41M  FY23 29M  FY24 51M   FY25  0   FY26  0
                                         ^^^^^^^^^^^^^^^^^^^^ exact match
```

**This is structurally the LLY finding** (`docs/l4d-capex-synonym.md` §3) with a different
bundled component — FMP not self-consistent across years while the EDGAR tag is.

**Code's reading — why this does NOT block the arm, stated for ruling, not assumed:**

1. **Our side is the consistent one.** ARM files ONE tag, `PaymentsToAcquire`
   `PropertyPlantAndEquipment`, across all five years — no migration, no staleness. It is the
   FIRST entry of the armed chain and the same tag 15 of the 18 covered names use. FMP is the
   side that changes basis.
2. **LLY is the opposite case and that is why it was gated out.** LLY's divergence hit the
   NEWEST years at 53.4% / 39.8% after a three-step tag migration, so *our* tag choice was the
   open question. Here the newest two years — the ones the live TTM and the newest FY point
   read — reconcile **to the dollar**, and there is no tag choice to make.
3. Ruling it in the resolver would be the *"never fix a contradiction by teaching the model to
   ignore it"* violation. We use the primary source's own consistent tag and **record** that
   FMP disagrees in three historical years.

**★ THE ARMED CROSS-CHECK CANNOT SEE THIS AND WILL NEVER REPORT IT.** It compares only the
latest period, which reconciles exactly. The three divergent years were found by hand and
would have shipped silently. **Carry this forward: the cross-check corroborates the LIVE
value only — a historical series it never inspects is written on one source's word.** That is
a general property of every name in `fundamental_series`, not an ARM quirk, and it is the
strongest argument yet for the per-point `first_filed` basis stamp G-1 already captures.

## 10. FIXTURE AGING — RE-VERIFIED AT DARK DIFF: ZERO

Re-confirmed against all 9 EDGAR fixtures: **no 20-F or 6-K fact in any of them; no ARM or
SKHY fixture exists.** Nothing ages, nothing to re-record, and **no fixture will be
re-recorded.** Pins must therefore be **synthetic-fact pins** driving `_extract_xbrl_facts`
directly (the `tests/test_l4d_typed_reasons.py` shape), because the fixture replay path
(`edgar_adapter.py:952`) calls `resolve_financials` directly and **never runs the form filter
at all**.

## 11. AWAITING ARM RULING

Dark diff is clean and matches the ruled expectation exactly. Outstanding for ruling:
**§9 — does ARM's FY22–FY24 capex divergence against FMP block the arm?** Code's reading is
no, for the three reasons above, but it is the LLY class and LLY was ruled, so this is Vic's.

---
---

# STEP 2 — ARMED AND WRITTEN (2026-08-21)

## 12. RULING §9 — ARM'S CAPEX BASIS (Vic, 2026-08-21)

> **EDGAR basis — ARM's canonical tag stands, per the LLY precedent (2026-08-21). FMP's
> series bundles `PaymentsToAcquireIntangibleAssets` in FY22-24 and drops it in FY25/26;
> ARM's own tag is definitionally consistent across all five years. Intangible/IPR&D-class
> acquisitions are not capital intensity. Advisory basis note on the cross-check,
> non-blocking.**

Note the ruling turns on a principle wider than ARM: **intangible/IPR&D-class acquisitions
are not capital intensity.** That is the same distinction the LLY case turns on — LLY's FMP
series bundles `PaymentsToAcquireInProcessResearchAndDevelopment` — so the two names are one
question answered once, and the reasoning is now on record for the next issuer whose feed
does this.

## 13. WHAT LANDED

**Two source changes, both minimal:**

```python
# adapters/edgar_adapter.py — ANNUAL split from INTERIM, because two different decisions
# read this set and they were the same question only by coincidence.
_XBRL_ANNUAL_FORMS  = {"10-K", "10-K/A", "20-F", "20-F/A"}
_XBRL_INTERIM_FORMS = {"10-Q", "10-Q/A", "6-K", "6-K/A"}
_XBRL_VALID_FORMS   = _XBRL_ANNUAL_FORMS | _XBRL_INTERIM_FORMS

# core/fundamental_series.py:_fy_ends — membership, not string prefix
- if r.get("fp") == "FY" and str(r.get("form", "")).startswith("10-K"):
+ if r.get("fp") == "FY" and r.get("form") in _XBRL_ANNUAL_FORMS:
```

**Suite 922 → 953** (+31 `tests/test_l4f_foreign_forms.py`). **Pins verified to FAIL 11 of 31
against pre-fix behaviour** before landing — including both critical ones,
`test_fy_ends_recognises_a_FY_fact_on_20F` and
`test_the_ARM_shape_emits_a_series_with_a_TRUTHFUL_FY_LABEL`. The 20 that pass pre-fix are
no-regression pins (boundedness, monotonicity, domestic equivalence, SKHY fail-closed) and
pass by design.

The pre-fix verification was run by **restoring the old BEHAVIOUR while keeping the new
constants defined**. Reverting the whole change instead yields a bare `ImportError` and a
single collection error — which proves only that the module does not import, not that any
pin detects the defect. Worth repeating for the next order that has to make this claim.

### Three L-4d tests were UPDATED, not broken — and deliberately

`test_the_invariant_BITES_positive_control`, `test_the_builder_reports_form_excluded_NOT_no_tag`
and `test_form_excluded_is_a_diagnostic_and_moves_no_resolution` all used **20-F as the
exemplar of "a form we do not read."** That was true when written and is now false. Each
swaps to **S-1**, a registration statement still outside `_XBRL_VALID_FORMS`; the mechanism
they pin is unchanged and still load-bearing — it is what will surface the NEXT form gap.
**Deleting them would have retired a live guard because one issuer stopped needing it.** Each
carries a `★ EXEMPLAR FORM CHANGED AT L-4f` note in place.

## 14. THE WRITE — ONE WRITE POINT, RECONCILED EXACTLY

| | |
|---|---|
| Backup | `caliber.db.pre-l4f-c0bae791.bak`, md5 verified equal to the pre-write db |
| md5 before | `c0bae79159d5d2a325c35fd87dceda88` |
| **md5 after** | **`e3fe5ff9868fcb05fc60106521779769`** |
| md5 across the suite | unchanged (`c0bae791`) — the 953-test run wrote nothing to production |
| Reconciliation | **expected +72, actual +72, restatements 0, superseded 0 — MATCH** |

**Every table re-counted after the write; all within the expected set:**

| table | before | after |
|---|---|---|
| **fundamental_series** | 2,302 | **2,374 (+72)** |
| evaluations · field_provenance · grades · lifecycle_overrides · lifecycle_stage · lifecycle_transitions · overrides · sqlite_sequence · synthesis_cache | 80 · 1437 · 0 · 0 · 44 · 1 · 0 · 5 · 16 | **all +0** |

ARM's 72 rows: fcf 14 (5 FY) · fcf_margin 14 (5) · reinvestment 14 (5) · fcf_growth 10 (4) ·
fcf_yield 10 (3) · revenue_growth 10 (4). `sales_to_capital` 0 — no debt tags, truthful.

**step-4 evaluable 18 → 19 of 28**, confirmed through the production reader
`evaluate._fy_series_from_db`. ARM's FY FCF series, oldest-first, as step 4 reads it:

```
2022-03-31  424M · 2023-03-31  675M · 2024-03-31  998M · 2025-03-31  178M · 2026-03-31  979M
```

**R2 YOUNG signal re-measured through the production reader and UNCHANGED:
`C / IONQ / QBTS / RKLB`.** ARM's last three FY FCF are `[998M, 178M, 979M]` — not
all-negative.

## 15. WHAT THIS ORDER DID NOT DO

- **No synonym added** (constraint honoured). ARM resolves on the tags already in the chain.
- **No TTM-assembly built** (constraint honoured). ARM resolves on the EXISTING path 3; the
  YTD-only filers CBRS/DPC/SPCX/XE remain truthfully `ttm_unavailable`.
- **No fixture re-recorded.** Nothing ages — re-verified at the write.
- **No punch-list item touched**: LLY (L-4d.1), net_income on BE/CAT, V's share basis, the
  L-4e census all remain parked.
- **F-1 and 40-F remain excluded**, each pinned and each its own ruling if ever wanted.
