# ORDER RECORD — L-4d.1: the LLY capex-basis rider

**Issued** 2026-08-22 (Vic, via chat), revised in-session after a STOP.
**Status at issue** RULED, NOT LANDED. Predecessor session died mid-order 2026-08-21.
**Predecessor residue** `.scratch_lly/` (gitignored) — two read-only scripts + a 28-name
dated EDGAR facts snapshot. Preserved under ruling ④ (archive, do not delete).

This is the first L-4 order to receive its own document in `docs/orders/`. L-4a–L-4f were
issued inside close orders and transcribed into CLAUDE.md; that is recorded here rather
than smoothed over, because a reader looking for an "L-4c order document" will not find one.

---

## 1. Scope

Add `("PaymentsToAcquireOtherPropertyPlantAndEquipment", "us-gaap")` as the **THIRD** entry
of the `capex` FieldSpec chain in `adapters/edgar_adapter.py`, behind the two armed tags.
Then write LLY's `fundamental_series` rows. Takes `fundamental_series` coverage **19 → 20 of 28**.

**In scope:** the spec edit; the two superseded pin rewrites; new L-4d.1 pins; one
production write to `fundamental_series`; the snapshot disposition; the CLAUDE.md update.

**Out of scope:** step 4 (YOUNG supply-layer block) stays blocked and is NOT ruled by this
order. `.scratch_l4f/` and the three L-1 dark-run databases are untouched. No re-recording
of any fixture. No change to the form filter, the staleness gate, or `conflict_check`.

---

## 2. The ruling, quoted verbatim (ruling ③)

### 2a. CLAUDE.md, the L-4d.1 punch-list entry

> **★ LLY IS NOW ORDER L-4d.1 (LLY capex-basis rider) — RULED 2026-08-21, NOT YET LANDED.
> THIS IS THE NEXT ORDER.** Named L-4d.1 by ruling because it is a follow-on from L-4d's
> step-2 findings, not a new phase (L-4e stays reserved for the synonym census, L-4f was
> form admission). **The ruling: add `PaymentsToAcquireOtherPropertyPlantAndEquipment` as
> the THIRD capex chain entry, behind the two armed tags.** A session began executing it
> and DIED mid-order; its read-only scratch survives in **`.scratch_lly/`** (gitignored,
> do NOT delete — see the pickup block). **The dark-diff RESULTS were never recorded, so
> L-4d.1 must re-run `.scratch_lly/dark_diff.py` and `dark_series.py`.** Takes coverage
> 19 → 20. **The L-4f ruling on ARM is the governing precedent and settles the principle:
> intangible/IPR&D-class acquisitions are NOT capital intensity, so where FMP bundles them
> and the issuer's own tag is definitionally consistent, the EDGAR tag stands and the
> disagreement is an advisory basis note.** LLY's FMP series bundles
> `PaymentsToAcquireInProcessResearchAndDevelopment`; ARM's bundles
> `PaymentsToAcquireIntangibleAssets`. Same question, answered once. Original diagnosis
> retained: L-4c had it in Class 1;
> that was wrong. LLY migrated **THREE times** and abandoned
> `PaymentsToAcquireProductiveAssets` at 2022-09-30 (1369d lag, past the 450d gate). Its
> current tag is `PaymentsToAcquireOtherPropertyPlantAndEquipment`, which **FAILED the
> ruled FMP reconciliation: 53.4% off in FY2023, 39.8% in FY2024, exact in FY2025.**
> Cause identified exactly — **FMP's `capitalExpenditure` bundles
> `PaymentsToAcquireInProcessResearchAndDevelopment` in FY23/FY24 (to the dollar) and
> drops it in FY25, so FMP is not self-consistent across years while the EDGAR tag is.**
> The ruling needed: whose capex definition governs when the two disagree DEFINITIONALLY
> and the feed is internally inconsistent. Not arbitrated in the resolver — that would be
> the "never fix a contradiction by teaching the model to ignore it" violation.

### 2b. `.scratch_lly/dark_diff.py` docstring, in full

> ```
> """L-4e(LLY) DARK DIFF — measurement only. Nothing here writes, and no source file is
> modified: the amended FieldSpec is substituted IN MEMORY so the real resolver is measured
> rather than a re-implementation (same method as the L-4d step-2 dark diff).
>
> Adds ("PaymentsToAcquireOtherPropertyPlantAndEquipment", "us-gaap") as the THIRD entry of
> the capex chain, behind the two armed tags, per the Vic ruling of 2026-08-21.
> """
> ```

### 2c. `.scratch_lly/dark_series.py` docstring, in full

> ```
> """L-4e(LLY) DARK DIFF part 2 — the FCF SERIES and the ARMED CROSS-CHECK surface.
>
> Same in-memory spec substitution. Builds LLY's series through the SAME calls the writer
> (tools/expand_fcf_series.build_one) makes, and computes the cross-check report both ways.
> Nothing is written; compute_cross_check is pure and apply_report is never called.
> """
> ```

**Note on the `L-4e` label in both docstrings:** the predecessor session named this work
L-4e before the ruling renamed it L-4d.1 (L-4e stays reserved for the synonym census). The
docstrings are quoted unaltered; the label is historical, not a second order.

---

## 3. THE PIN CONFLICT AND ITS RESOLUTION (ruling ①)

The tree carried a committed pin asserting the **opposite** of this order, dated the same
day. It is quoted here in full because deleting it silently would destroy the evidence that
the question was once answered the other way.

### 3a. The superseded pin, verbatim (`tests/test_l4d_capex_synonym.py`, commit `c7a3813`)

> ```python
> def test_LLY_third_tag_is_deliberately_absent(self):
>     """RULED OUT, NOT OVERLOOKED (2026-08-21). LLY's current tag after a THREE-STEP
>     migration is PaymentsToAcquireOtherPropertyPlantAndEquipment. It failed the FMP
>     reconciliation the other three passed: FMP's capitalExpenditure for LLY bundles
>     PaymentsToAcquireInProcessResearchAndDevelopment in FY2023 (+$3.944B, to the
>     dollar) and FY2024 (+$3.346B), then drops it in FY2025 — so the two sides are not
>     the same measure and FMP is not self-consistent year to year. Adding this tag
>     without re-ruling would put one name's FCF on a basis nothing else shares.
>     """
>     assert OTHER_PPE not in {c for c, _ns in _capex_spec().synonyms}
> ```

A matching source comment in `adapters/edgar_adapter.py` opens **"DELIBERATELY NOT ADDED"**
and is superseded by the same ruling.

### 3b. Why it is superseded — the two grounds Vic ruled on

**Ground 1 — CHRONOLOGY.** The pin is L-4d step-2 era (`c7a3813`, 2026-08-21). The ruling in
§2a post-dates it: it is written *after* L-4f landed and cites the L-4f ARM precedent, which
did not exist when the pin was authored. Later ruling governs.

**Ground 2 — RETIRED PREDICATE.** The pin's stated rationale is that the tag "failed the FMP
reconciliation." The ARM precedent retires that predicate rather than disputing the
measurement: where FMP bundles intangible/IPR&D-class acquisitions and the issuer's own tag
is definitionally consistent, **the EDGAR tag stands and the disagreement is an advisory
basis note.** The pin's own text concedes FMP "is not self-consistent year to year" — that is
now a finding against the feed, not against the tag. The dark run confirms FY2025 reconciles
to the dollar (EDGAR-derived `8.972B` vs FMP `8972000000`).

**What is NOT claimed:** the pin was not wrong when written, and this is not a bug fix. It
recorded a real ruling that was later re-ruled on new evidence. Both pins get a
`★ SUPERSEDED AT L-4d.1` note naming this document and the ARM precedent, so the reversal is
readable at the point of change — the same treatment L-4f gave the three 20-F exemplar tests.

---

## 4. Dark-run evidence (re-run 2026-08-22, read-only, caliber.db md5 unchanged)

`dark_diff.py` runs off the cached 2026-08-21 facts, so it reproduces the predecessor
session's measurement rather than re-fetching.

```
  ticker  field                              BEFORE   ->  AFTER
  LLY     capex         stale_tag/None/None   ->  resolved/9893000000.0/PaymentsToAcquireOtherPropertyPlantAndEquipment

  NON-CAPEX FIELD CHANGES ACROSS ALL 28 NAMES: 0
  RESOLVED-FIELD COUNT CHANGES: LLY 15->16
  names whose resolved count is unchanged: 27 of 28

  RAW-FACTS SWEEP — who files the new tag, and is the conflict path reachable?
   LLY   freshtags=1  oductiveAssets…=2022-09-30(1369d,STALE) | herPropertyPlantAndE…=2026-06-30(0d,FRESH)
   FN    freshtags=1  opertyPlantAndEquipm…=2026-06-26(0d,FRESH) | herPropertyPlantAndE…=2012-06-29(5110d,STALE)
```

`dark_series.py`, CURRENT vs AMENDED (live path):

| | CURRENT | AMENDED |
|---|---|---|
| rows | 0 | **114** |
| basis | `not_applicable` | `split_restated` |
| withheld | `{'fcf': 'capex:stale_tag'}` | `{}` |
| FY FCF points | 0 | **6** — 2020 `5.112B`, 2021 `6.056B`, 2022 `5.731B`, 2023 `0.792B`, 2024 `3.760B`, 2025 `8.972B` |
| step-4 gate (≥3 FY pts) | FAIL | **PASS** |
| `free_cashflow` verdict | `no_edgar` | `basis_mismatch` (advisory) |
| would-change-confidence list | 6 fields | **identical — unchanged** |

**Three properties this order rests on, all measured:**
1. **The conflict path is unreachable.** Only LLY and FN file the new tag; both at
   `freshtags=1`. FN's copy is 5110 days stale and sits behind a fresh primary, so FN is
   untouched. `conflict_check=False` is not doing the work here — the staleness gate is.
2. **No confidence label moves.** The only verdict change is `no_edgar → basis_mismatch`,
   which is advisory; the would-change list is byte-identical before and after.
3. **No fixture ages.** Unlike L-4d, **no EDGAR fixture contains the new tag** (all 9 read
   zero occurrences), so the "adding a synonym silently ages every recorded fixture" hazard
   does not recur. The `V.json` pin is unaffected.

---

## 5. Expected delta — stated BEFORE the write

| Table | Expected |
|---|---|
| `fundamental_series` | **+114 rows**, one new ticker **LLY**, **0** restatements, **0** superseded |
| `field_provenance` | **+0** |
| `synthesis_cache` | **+0** |
| `evaluations` | **+0** |
| `lifecycle_stage` / `lifecycle_transitions` / `grades` / `overrides` / `lifecycle_overrides` | **+0** |
| `sqlite_sequence` | **+0** (no new AUTOINCREMENT table) |

Dependents are all `+0` because `tools/expand_fcf_series.py` runs no evaluation — that is the
property L-4c created it for. Coverage `fundamental_series` **19 → 20 of 28**; step-4
evaluable **19 → 20**, counted through `evaluate._fy_series_from_db`, never by
`SELECT DISTINCT ticker`.

Anything outside this set is reported, not absorbed. Backup taken before the write,
timestamped, md5-verified equal to the pre-write db.

---

## 6. Pin plan (ruling ②)

**Rewritten (2):** `test_both_concepts_are_in_the_chain` → asserts the three-tag chain in
order; `test_LLY_third_tag_is_deliberately_absent` → renamed to assert the tag is now
ARMED. Both carry `★ SUPERSEDED AT L-4d.1`.

**New:** three-tag chain composition and ordering; the generic tag still first (no-regression
argument); LLY-only reachability of the new tag; FN untouched at 5110d stale; the
advisory-only `no_edgar → basis_mismatch` movement; a positive control that the pins fail
against a two-tag spec.

Pins are written and verified to FAIL against unmodified source **before** the spec edit —
a pin that cannot fail proves nothing.

---

## 7. Snapshot disposition (ruling ④)

`.scratch_lly/facts/` is a **dated EDGAR snapshot (2026-08-21, 28 names, ~95 MB)**, not a
scratch byproduct: it is what makes the dark diff reproducible. Live re-fetch drifts.

Archive to `.snapshots/l4d1-lly-2026-08-21/` — `facts/`, both scripts, and a README. Confirm
`.snapshots/` is gitignored; the 95 MB does not enter git, consistent with the standing
"database files never go to the remote" ruling. **The two scripts additionally get committed
copies under `tools/`** so the analysis method survives in git even if the snapshot is lost.
Then `.scratch_lly/` is removed entirely.

---

## 8. Correction to CLAUDE.md's "only surviving record" claim

CLAUDE.md states `.scratch_lly/` "holds the ONLY surviving record of the LLY ruling of
2026-08-21." **That is loose and this order corrects it.** The ruling *text* is in CLAUDE.md
itself (quoted at §2a). What the residue uniquely held is (a) the two analysis scripts and
(b) the dated facts snapshot. `facts/` contains **no ruling text at all** — it is 28 raw
EDGAR companyfacts JSON payloads. The distinction matters: deleting the residue would have
destroyed *reproducibility of the measurement*, not the ruling. After this order, both are in
the durable record and the claim is retired.

---

## 9. STOP conditions

Any deviation from the §5 expected delta · any pre-existing test failure · any baseline drift
at a checkpoint → report and await ruling. No improvising around a deviation.
