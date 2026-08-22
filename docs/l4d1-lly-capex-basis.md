# L-4d.1 — the LLY capex-basis rider. **CLOSED 2026-08-22.**

Order: `docs/orders/2026-08-22-l4d1-lly-capex-basis.md`.
Snapshot: `.snapshots/l4d1-lly-2026-08-21/` (gitignored; scripts also committed under `tools/`).

---

## 1. What landed

`("PaymentsToAcquireOtherPropertyPlantAndEquipment", "us-gaap")` armed as the **THIRD**
entry of the `capex` FieldSpec chain, behind the two armed tags. LLY's `fundamental_series`
rows written.

| | before | after |
|---|---|---|
| capex chain | 2 tags | **3 tags** |
| `fundamental_series` | 2374 rows / 19 tickers | **2488 rows / 20 tickers** |
| step-4 evaluable (via `evaluate._fy_series_from_db`) | 19 of 28 | **20 of 28** |
| LLY capex | `stale_tag`, FCF family withheld | **resolved $9.893B**, 6 FY FCF points |
| suite | 953 | **975** |
| caliber.db md5 | `e3fe5ff9…` | **`eec96270…`** |

LLY FY FCF, oldest-first: 2020 `5.112B` · 2021 `6.056B` · 2022 `5.731B` · 2023 `0.792B` ·
2024 `3.760B` · 2025 `8.972B`.

**LLY does NOT join the R2 YOUNG all-negative-last-3 signal** (`0.792B, 3.760B, 8.972B` are
all positive). That set is unchanged: IONQ, QBTS, RKLB, C.

## 2. The reversal — this order overturned a committed pin

`tests/test_l4d_capex_synonym.py::test_LLY_third_tag_is_deliberately_absent` (commit
`c7a3813`, 2026-08-21) asserted the **opposite** of this order and opened
**"RULED OUT, NOT OVERLOOKED."** Both it and `test_both_concepts_are_in_the_chain` were
superseded on two ruled grounds:

1. **CHRONOLOGY.** The pin is L-4d step-2 era. The governing ruling post-dates it and cites
   the L-4f ARM precedent, which did not exist when the pin was written.
2. **RETIRED PREDICATE.** The pin's rationale was a failed FMP reconciliation. The ARM
   precedent makes intangible/IPR&D bundling on FMP's side an **advisory basis note**, not a
   disqualification of the issuer's tag. The pin's own text concedes FMP "is not
   self-consistent year to year" — under the precedent that is a finding against the FEED.

**The pin was not wrong when written.** It recorded a real ruling that was later re-ruled on
new evidence. Both rewrites carry `★ SUPERSEDED AT L-4d.1` notes quoting the original
rationale in full, so the reversal is readable at the point of change — the treatment L-4f
gave the three 20-F exemplar tests. The matching `# DELIBERATELY NOT ADDED` source comment
was rewritten the same way rather than deleted.

## 3. Dark evidence (re-run 2026-08-22 off the cached 2026-08-21 facts)

```
  LLY  capex   stale_tag/None/None  ->  resolved/9893000000.0/PaymentsToAcquireOtherPropertyPlantAndEquipment
  NON-CAPEX FIELD CHANGES ACROSS ALL 28 NAMES: 0
  RESOLVED-FIELD COUNT CHANGES: LLY 15->16
  names whose resolved count is unchanged: 27 of 28
```

**Three properties the arm rests on, all measured:**

1. **The conflict path is unreachable.** Only LLY and FN file the new tag, both at
   `freshtags=1`. FN's copy ended 2012-06-29 — **5110 days stale**, behind a fresh generic
   tag — so FN is untouched. `conflict_check=False` is not doing the work; the staleness
   gate is.
2. **No confidence label moves.** The only cross-check movement is `no_edgar →
   basis_mismatch` on `free_cashflow` (EDGAR TTM `18.190B` vs FMP annual `8.972B`), which is
   advisory. The would-change-confidence list is byte-identical before and after. Pinned
   **structurally**: a `basis_mismatch` delta carries no `would_be_confidence`, so
   `would_change` cannot be True.
3. **★ NO FIXTURE AGES — and that is measured, not assumed.** L-4d established that adding a
   synonym silently ages every recorded fixture. **It does not recur here: no EDGAR fixture
   contains the new tag** (all 9 read zero). The `V.json` pin is unaffected. Pinned so the
   conclusion is re-derived if any fixture is ever re-recorded.

## 4. The write

One write point. Backup `caliber.db.pre-l4d1-e3fe5ff9.bak` taken first, md5 verified equal to
the pre-write db. Dry run against the destination first, matching the dark expectation
exactly before `--commit`.

```
  RECONCILIATION: expected +114 (new tickers), actual +114, restatements 0 — MATCH
```

Every table re-counted after:

| table | before | after | delta |
|---|---|---|---|
| `fundamental_series` | 2374 | 2488 | **+114** |
| distinct tickers | 19 | 20 | **+1** |
| `evaluations` · `field_provenance` · `synthesis_cache` · `lifecycle_stage` · `lifecycle_transitions` · `grades` · `overrides` · `lifecycle_overrides` · `sqlite_sequence` | — | — | **all +0** |

`superseded = 0` on all 114 new rows, and on all 2488 rows in the table.

**A probe that read wrong, recorded because it nearly became a false alarm:** an initial
check counted `superseded IS NOT NULL` and reported 114. The column is
`INTEGER NOT NULL DEFAULT 0`, so `IS NOT NULL` is true for every row ever written. The
correct probe is the value, not the nullness. Nothing was wrong with the write.

md5 trail: `e3fe5ff9` (open) → `e3fe5ff9` (order doc, pins, source edit, suite, dry run) →
**`eec96270`** (the single production write) → `eec96270` (post-write suite).
`PRAGMA wal_checkpoint(TRUNCATE)` returned `(0,0,0)` before every reading.

## 5. Pins

**Rewritten (2)**, both in `tests/test_l4d_capex_synonym.py`:
`test_both_concepts_are_in_the_chain` (widened to assert the exact three-tag chain in order,
so a fourth tag cannot arrive unnoticed either) and
`test_LLY_third_tag_is_deliberately_absent` → **renamed** `test_LLY_third_tag_is_ARMED`.

**New:** `tests/test_l4d1_lly_capex_basis.py` — chain composition and ordering; the new tag
is fetched from companyfacts; `conflict_check` untouched; the LLY shape resolves; a
**positive control** that the two-tag spec goes QUIET on identical facts; end-to-end into the
series builder at value level; both armed tags still beat a fresh new tag; the FN 5110-day
shape; no recorded fixture moves; the monotonicity property (the old chain must remain an
ordered PREFIX); the fixture-aging absence; the advisory-only structural pin.

**Verified to FAIL before the source edit: 9 of 41** (2 rewritten + 7 new). A pin that cannot
fail proves nothing.

## 6. Coverage after L-4d.1 — 8 names still uncovered

**Correctly fail-closed (4):** JPM, USB, INFQ (`capex:no_tag`), SKHY (no `us-gaap` namespace).
**Our limits (4):** CBRS, DPC, SPCX, XE — `ttm_unavailable`, YTD-only filers, ruled OUT of scope.

**LLY is no longer among them.** With the LLY rider discharged, **every remaining uncovered
name is either correctly fail-closed or explicitly ruled out of scope** — the first time that
has been true. The standing ruling that blocks step 4 behind coverage is now discharged as
far as any ruled order reaches. **Step 4 is ruleable on this evidence; it is NOT armed by
this order.**

## 7. Snapshot disposition

`.scratch_lly/` retired to `.snapshots/l4d1-lly-2026-08-21/` (`facts/` 28 files / 93 MB, both
scripts, a README). `.snapshots/` gitignored — verified with `git check-ignore` **before**
moving 93 MB into it. Committed copies of both scripts at `tools/l4d1_dark_diff.py` and
`tools/l4d1_dark_series.py`. `.scratch_lly/` removed with `rmdir`, which fails on a non-empty
directory — so nothing was discarded.

`.scratch_l4f/` and the three L-1 dark-run databases are out of this order's scope and
untouched.

**CLAUDE.md's "only surviving record" claim is corrected.** The ruling text was always in
CLAUDE.md; `facts/` holds no ruling text, only raw payloads. What the residue uniquely held
is **reproducibility of the measurement** — which is why it was archived, not deleted.
