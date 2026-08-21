# L-4d — capex synonym + typed-reason corrections

Order (Vic, 2026-08-21): *"L-4d — capex synonym + typed-reason corrections. This is a
FIELD_SPECS change, not a coverage order."* Three steps, stop-and-report between each:
diagnose the five mis-typed names → add the capex synonym dark-before-arm → correct the
typed reasons.

Sequenced from `docs/l4c-coverage-expansion.md` §4/§6, whose ruling list this order
discharges items 1 and 2 of.

---

## STEP 1 — why five names report `no_operating_cashflow_tag` when the tag is filed

**Question as put: is this the same single-tag spec gap wearing a different error label,
or a distinct reader defect?**

**ANSWER: DISTINCT, AND IT IS NOT ONE MECHANISM BUT THREE.** None of the three is the
capex spec gap. The capex spec gap is real and is separately confirmed below — it just is
not what produces this label.

All evidence below is measured live from SEC `companyfacts` for each issuer's own CIK, on
the adapter's own fetch path (`_get_cik` → `_fetch_companyfacts` → `_extract_xbrl_facts` →
`resolve_financials`). Read-only; no database was opened.

### The label's actual trigger

`core/fundamental_series.py:257`:

```python
ocf = _flow_points(fin, "operating_cashflow")   # → ttm_series(...)
if not ocf:
    result.withheld[METRIC_FCF] = WITHHELD_NO_OCF     # "no_operating_cashflow_tag"
```

The reason string asserts a fact about the FILINGS. The condition it is attached to
asserts only that **`ttm_series` returned an empty list** — a fact about our reader. Those
are different claims, and every name below is a case where they diverge. `_flow_points`
discards the accurate typed reason that already exists one layer down in
`fin.fields["operating_cashflow"].reason` / `.detail`.

### Mechanism 1 — TTM UNASSEMBLABLE (CBRS, DPC, SPCX, XE)

The tag is filed. The resolver reason is **`ttm_unavailable`**, not `no_tag`.

| ticker | CIK | forms filed | OCF facts | fact durations | resolver reason |
|---|---|---|---|---|---|
| CBRS | 0002021728 | 10-Q only (632 facts) | 4 | 89d ×2, 180d ×2 | `ttm_unavailable` |
| DPC | 0002107018 | 10-Q only (244 facts) | 2 | 178d, 179d | `ttm_unavailable` |
| SPCX | 0001181412 | 10-Q only (417 facts) | 2 | 180d ×2 | `ttm_unavailable` |
| XE | 0002088896 | 10-Q only (506 facts) | 4 | 89d ×2, 180d ×2 | `ttm_unavailable` |

Recent listings with no 10-K yet. Their cash-flow facts are **year-to-date cumulative**,
which defeats all three `_assemble_ttm` paths at once: no fact spans `_FY_RANGE`
(350–380d), so `ttm_annual` fails; the facts are YTD not QTD so there is no set of four
contiguous `_QTD_RANGE` quarters, so `ttm_summed` fails; and there is no prior fiscal year
fact, so `ttm_reconstructed` has no leg to stand on. The resolver says exactly this:

```
NetCashProvidedByUsedInOperatingActivities: no clean 4-quarter set and prior FY
missing for the 180d window ending 2026-06-30
```

**The OUTCOME is correct — these four genuinely have no assemblable FCF history — and the
detail string already says why accurately. Only the reason the builder stamps is wrong.**

### Mechanism 2 — FORM FILTER (ARM)

Not insufficient data. **We throw the data away.**

`_XBRL_VALID_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}`. ARM is a foreign private
issuer filing **20-F and 6-K**: 4,366 us-gaap facts across 288 concepts, of which
**0 survive the form filter**. `latest_period_end` is therefore `None`, `concepts` is
empty, and all 19 fields resolve `no_tag` — which is a true statement about
`financials.concepts` and a false one about ARM's filings.

What is actually there, and would assemble on the `ttm_annual` path untouched:

| concept | form | period | days | value |
|---|---|---|---|---|
| NetCashProvidedByUsedInOperatingActivities | 20-F | 2025-04-01 .. 2026-03-31 | 364 | $1,524M |
| NetCashProvidedByUsedInOperatingActivities | 20-F | 2024-04-01 .. 2025-03-31 | 364 | $397M |
| PaymentsToAcquirePropertyPlantAndEquipment | 20-F | 2025-04-01 .. 2026-03-31 | 364 | $545M |
| PaymentsToAcquirePropertyPlantAndEquipment | 20-F | 2024-04-01 .. 2025-03-31 | 364 | $219M |

27 OCF facts run back to 2022-03-31. ARM's FCF history exists, is annual, is in the
standard us-gaap tags, and is discarded at extraction.

**Widening the form filter is NOT in this order** — it is L-4c ruling-list item 3 ("ARM's
20-F blindness, scope unknown, wider than FCF, its own diagnosis"), and it would change
lens selection and the cross-check for every foreign private issuer, not just FCF. Step 3
corrects ARM's *reason* to name the form filter. The filter itself stays as-is pending its
own ruling.

### Mechanism 3 — CAPEX SPEC GAP, AND IT REACHES ONE NAME L-4c DID NOT CLASSIFY

**★ NEW FINDING, revises `docs/l4c-coverage-expansion.md` §4.** L-4c put XE in Class 2
(insufficient history) only. XE is **also Class 1**:

```
XE  [CAPEX] PaymentsToAcquirePropertyPlantAndEquipment: ABSENT from companyfacts
    [CAPEX] PaymentsToAcquireProductiveAssets: 4 facts, forms={'10-Q': 4}
    field capex: reason=no_tag  trail=['PaymentsToAcquirePropertyPlantAndEquipment:absent']
```

So the Class-1 population is **at least five names, not four**, and it was undercounted
because the builder checks OCF first and `return`s (`core/fundamental_series.py:257-265`) —
XE's capex `no_tag` is never reached or reported. **A short-circuit on the first
withholding hides every subsequent one**, which is why the step-2 sweep must be run over
all 28 names against the raw facts rather than against the builder's output.

This does not make XE coverable: its OCF is still `ttm_unavailable`, so XE keeps its gap
under the fail-closed constraint. It changes only what XE's reason should say.

### The concept=None gate — a real coupling, measured NOT to be the active cause

`_resolve_one`'s unresolved return (`adapters/edgar_adapter.py:590`) constructs
`ResolvedField(name=..., reason=..., detail=..., trail=...)` and **does not carry
`concept`**. `ttm_series` then bails at `if rf is None or not rf.concept: return []`
(`:497`). So the HISTORICAL series reader is gated on the LIVE TTM resolving: a field
whose current-period TTM fails contributes no history at all, even at period-ends that
would assemble cleanly.

I tested this rather than asserting it — forcing the concept back on and re-running
`ttm_series` for all four Mechanism-1 names:

```
CBRS operating_cashflow  as-is=0 forced=0    DPC  operating_cashflow  as-is=0 forced=0
CBRS capex               as-is=0 forced=0    SPCX operating_cashflow  as-is=0 forced=0
XE   operating_cashflow  as-is=0 forced=0    SPCX capex               as-is=0 forced=0
```

**Forced=0 everywhere.** For these names the gate is not load-bearing — no period-end
assembles regardless, because the missing prior-FY leg is missing at every end. Recorded
as a **latent coupling**, not a live defect, and deliberately not fixed here: no name in
the universe currently demonstrates it, and changing it would alter series content on the
armed path with no measured case to validate against.

### Summary — what each name's reason SHOULD say

| ticker | reason emitted today | mechanism | accurate? |
|---|---|---|---|
| CBRS | `no_operating_cashflow_tag` | TTM unassemblable — 10-Q only, no prior FY leg | no |
| DPC | `no_operating_cashflow_tag` | TTM unassemblable — 10-Q only, no prior FY leg | no |
| SPCX | `no_operating_cashflow_tag` | TTM unassemblable — 10-Q only, no prior FY leg | no |
| XE | `no_operating_cashflow_tag` | TTM unassemblable **+ capex spec gap** (both true) | no |
| ARM | `no_operating_cashflow_tag` | form filter drops 4,366 of 4,366 facts (20-F/6-K) | no |

**None of the five is the capex spec gap wearing a different label.** Mechanisms 1 and 2
are distinct reader behaviours; the capex gap is a third thing that happens to also touch
XE. The single common defect across all five is the builder stamping a claim about the
filings onto a condition that only measures our own reader — which is step 3's fix, and
the information needed to fix it correctly already exists in `ResolvedField.reason` and
`.detail` and is being discarded.

---

## STEP 2 — the capex synonym, built dark

Ruled scope: add `PaymentsToAcquireProductiveAssets` to the `capex` FieldSpec; sweep RAW
FACTS for all 28; NVDA 2020 migration per the JPM precedent; expected coverage 15 → 19;
**stop and report if the sweep revises the class populations or the delta.**

**IT DOES. THE DELTA IS 15 → 18, NOT 15 → 19. LLY DOES NOT RECOVER.** Nothing has been
written and no source file has been changed — the diff below was produced by substituting
the FieldSpec in memory, so it measures the real resolver rather than a re-implementation.

### 2.1 ★ THE REVISION — LLY MIGRATED TWICE, AND THE SECOND MOVE IS PAST THE STALENESS GATE

L-4c put LLY in Class 1 ("files `PaymentsToAcquireProductiveAssets`, recovered by the
synonym"). The first half is true; the second is not. LLY **abandoned** that tag:

| concept | kept facts | span | lag vs `latest_period_end` 2026-06-30 | gate |
|---|---|---|---|---|
| `PaymentsToAcquirePropertyPlantAndEquipment` | 0 | — | — | absent |
| `PaymentsForProceedsFromProductiveAssets` | 64 | 2008-06-30 .. 2019-06-30 | 2557d | **STALE** |
| `PaymentsToAcquireProductiveAssets` | 20 | 2018-09-30 .. **2022-09-30** | **1369d** | **STALE** |
| `PaymentsToAcquireOtherPropertyPlantAndEquipment` | 73 | 2007-12-31 .. **2026-06-30** | 0d | **FRESH** |

`STALE_TAG_DAYS` is 450. At 1369 days the ruled synonym is skipped by design — "a stale
leading tag is skipped, never used" — so adding it changes LLY's *reason* and not its
*value*. **LLY is a THREE-STEP migration**, which is a stronger case of the punch list's own
thesis than the one that motivated it: the single-tag spec did not expire once, it expired
twice, and each expiry was silent.

LLY is not otherwise blocked — capex is its **only** missing input:

```
operating_cashflow  $28.083B  NetCashProvidedByUsedInOperatingActivities   (24 TTM pts)
revenue             $79.666B  Revenues
capex               None      no_tag  ->  stale_tag under the amendment
```

Its current tag reads as a real capex line, not an "other" residual —
FY2023 $3.448B → FY2024 $5.058B → FY2025 $7.841B, consistent with the manufacturing
build-out. **Adding `PaymentsToAcquireOtherPropertyPlantAndEquipment` as a third synonym
would take coverage to 19 and is measured below — but it is a DIFFERENT TAG FROM THE ONE
RULED, so it is presented for ruling and NOT applied.**

### 2.2 Raw-facts sweep, all 28 names

Run over `companyfacts` per CIK, using the adapter's own form filter — not builder output,
per amendment 1. Q2 is the regression question: if any covered name filed **both** tags
fresh and they disagreed by >0.5%, `conflict_check=True` would withhold capex and
**destroy an existing series**.

- **Q1 — who files `PaymentsToAcquireProductiveAssets` fresh:** NVDA, V, LRCX, XE. Stale
  copies at CAT (2019-12-31), WU (2020-12-31), LLY (2022-09-30).
- **Q2 — names filing BOTH tags fresh: ZERO.** Every stale copy sits behind a fresh
  `PaymentsToAcquirePropertyPlantAndEquipment` (CAT, WU) and is skipped by the staleness
  gate *before* the conflict check is reached. **The conflict path is unreachable on
  today's universe, so no covered name can regress.**
- **Q3 — any capex-like tag the amended spec would still miss:** yes, two, and neither is
  in scope. LLY's `PaymentsToAcquireOtherPropertyPlantAndEquipment` (§2.1), and
  JPM/USB/INFQ, which file **no PP&E-purchase concept of any kind** — checked across every
  us-gaap concept, confirming L-4c's Class 4.

### 2.3 THE DARK DIFF

**A. Capex resolution — 5 of 28 move, 3 of them recover a value.**

| ticker | current | ruled (+ProductiveAssets) | effect |
|---|---|---|---|
| NVDA | None (`stale_tag`) | **$6.572B** ProductiveAssets | **RECOVERS** |
| V | None (`no_tag`) | **$1.571B** ProductiveAssets | **RECOVERS** |
| LRCX | None (`no_tag`) | **$0.966B** ProductiveAssets | **RECOVERS** |
| LLY | None (`no_tag`) | None (`stale_tag`) | reason only — more accurate |
| XE | None (`no_tag`) | None (`ttm_unavailable`) | reason only — more accurate |

The NVDA case is the JPM precedent working exactly as designed: its
`PaymentsToAcquirePropertyPlantAndEquipment` ends 2020-07-26, the staleness gate skips it,
and the fresh synonym behind it supplies the value. **No special handling was needed** —
generic tag stays first, priority order plus the existing gate does the rest, same as
`CashAndCashEquivalentsAtCarryingValue` → `CashAndDueFromBanks`.

**B. Every other field, all 28 names: `non-capex field changes: 0`.** Nothing outside
capex moves anywhere.

**C. Resolved-field counts** — only the three recovering names move, each by exactly one:
NVDA 16/19 → 17/19, V 14/19 → 15/19, LRCX 16/19 → 17/19. LLY unchanged at 15/19. **All 15
covered names unchanged.**

**D. The ARMED cross-check surface** (`compute_cross_check`, pure; `apply_report` never
called). 12 comparisons per name:

| ticker | | current | ruled |
|---|---|---|---|
| NVDA | `free_cashflow` | `no_edgar` | `basis_mismatch` — EDGAR $119.076B vs FMP $96.676B |
| V | `free_cashflow` | `no_edgar` | `basis_mismatch` — EDGAR $21.185B vs FMP $21.577B |
| LRCX | `free_cashflow` | `no_edgar` | `basis_mismatch` — EDGAR $4.891252B vs FMP $4.891252B |
| LLY | `free_cashflow` | `no_edgar` | `no_edgar` — note now reads `capex(stale_tag)` |
| XE | `free_cashflow` | `no_edgar` | `no_edgar` — note now names both real reasons |
| MU / GOOGL / C | *(controls)* | **0 of 12 change** | **0 of 12 change** |

**THE ARMED SURFACE CANNOT MOVE A CONFIDENCE LABEL FROM THIS CHANGE.** The `free_cashflow`
comparison carries a permanent `basis_note` ("FMP cash-flow is annual; EDGAR is TTM"), so
its verdict is `basis_mismatch` — **advisory only, never proposes a confidence change**.
The three recovering names move from "no data" to "advisory", and advisory is where they
stop. No value, score, E(R), grade or confidence label moves anywhere in the universe.

Worth recording as corroboration rather than as a gate: **LRCX matches FMP to the dollar**
($4,891,252,000 both sides), and V agrees within 1.8%. NVDA's 23% gap is the documented
TTM-vs-annual basis difference on a fast-growing issuer, which is exactly what the
permanent advisory exists to describe.

**E. Step-4 coverage — the delta, stated before any write:**

| | evaluable (≥3 FY FCF pts) | recovered |
|---|---|---|
| current | **15** of 28 | — |
| ruled (+ProductiveAssets) | **18** of 28 | NVDA (5 FY pts), V (6), LRCX (6) |
| *if* +OtherPropertyPlantAndEquipment | *19* of 28 | *+ LLY (6)* |

The harness reproduces the recorded production baseline exactly — its "current" column
gives the same **15** names already in `fundamental_series` — which is what licenses the
18 as a prediction rather than an estimate. NVDA gets 5 FY points rather than 6 because
its migrated tag starts later; still comfortably over the three-point gate.

### 2.4 Punch-list answer: capex is NOT the only exposed single-tag spec

The standing question was "sweep the other single-concept specs for the same exposure."
Measured across the 27 names with XBRL. **9 of 19 specs are single-tag**, and three show
the silent-expiry shape (tag filed, then abandoned past the gate):

| single-tag spec | resolved | **STALE** | names |
|---|---|---|---|
| `net_income` (`NetIncomeLoss`) | 20 | **2** | **BE, CAT** |
| `capex` | 15 | **1** | NVDA *(→ 0 after this change)* |
| `operating_lease_liability` | 23 | **1** | LLY |
| `gross_profit`, `operating_income`, `total_assets`, `current_assets`, `total_liabilities`, `current_liabilities` | — | 0 | — |

**`net_income` going stale on two names is the one worth a follow-up order** — it is a core
field on a single tag with no synonym chain. Recorded here as evidence only; **not touched,
not in scope.**

### 2.5 What is being asked for

1. **Arm the ruled change** — add `PaymentsToAcquireProductiveAssets` to the `capex`
   chain, generic tag first, on the evidence above: 0 non-capex changes, 0 covered-name
   changes, 0 confidence movement, coverage **15 → 18**.
2. **`conflict_check` on the amended chain** — recommend `conflict_check=False`, matching
   the JPM `cash` precedent. The two concepts are distinct measures (productive assets is
   the broader class), and no issuer files both fresh today so the path is unreachable
   either way; the setting is about which behaviour a *future* dual-filer gets. `False`
   means priority order decides, `True` means the field is withheld.
3. **LLY — rule separately.** Adding `PaymentsToAcquireOtherPropertyPlantAndEquipment`
   takes coverage 18 → 19 and is measured clean, but it is a different tag from the one
   ruled and its name says "Other", so it deserves its own decision rather than being
   folded in.
4. **`net_income` single-tag exposure (BE, CAT)** — punch-list item, own order.

**Zero production writes in step 2. caliber.db md5 unchanged at `7342f1a8…`. No source
file modified. Awaiting the arm ruling.**

---

## STEP 3 — the LLY conditional gate, and what was armed

Vic's ruling of 2026-08-21 accepted the dark diff, set `conflict_check=False`, and made
LLY's third tag **conditional**: run the same FMP capex reconciliation the three recovering
names passed; arm it only if it lands inside the ~2% class V passed.

### 3.1 ★ THE GATE FAILED — BRANCH B FIRED. LLY IS NOT ARMED.

FMP annual `cash-flow-statement` (the feed production uses) against EDGAR
`PaymentsToAcquireOtherPropertyPlantAndEquipment`, per fiscal year:

| FY | EDGAR | FMP \|capex\| | diff | diff % | verdict |
|---|---|---|---|---|---|
| 2023 | 3,448,000,000 | 7,392,100,000 | −3,944,100,000 | **53.356%** | **FAIL** |
| 2024 | 5,058,000,000 | 8,403,600,000 | −3,345,600,000 | **39.812%** | **FAIL** |
| 2025 | 7,841,000,000 | 7,841,000,000 | 0 | **0.000%** | PASS |

Worst divergence **53.4%** against a ~2% tolerance. **Two of three years fail, so the
condition is not met and LLY stays out — coverage armed at 15 → 18, not 19.**

**THE CAUSE IS IDENTIFIED EXACTLY, AND IT IS NOT AN EDGAR GAP.** The shortfall equals
`PaymentsToAcquireInProcessResearchAndDevelopment` to the dollar in both failing years:

| FY | EDGAR OtherPP&E | + IPR&D | = | FMP capex | FMP's definition |
|---|---|---|---|---|---|
| 2023 | 3.448B | 3.944B | **7.392B** | 7.3921B | includes IPR&D |
| 2024 | 5.058B | 3.346B | **8.404B** | 8.4036B | includes IPR&D |
| 2025 | 7.841B | 3.008B | 10.849B | **7.841B** | **excludes IPR&D** |

So LLY's tag is a genuine PP&E capex line, and **the side that is inconsistent is FMP** —
it bundles IPR&D acquisitions into `capitalExpenditure` for FY2023 and FY2024 and drops
them again in FY2025, while EDGAR's tag means the same thing in all three years.

That does not overturn the branch. The ruled gate was a reconciliation against FMP and it
failed; arming on "our side looks more consistent" would be arbitrating a definitional
disagreement between two sources inside our own resolver — the exact move the standing
rule forbids ("NEVER FIX A CONTRADICTION BY TEACHING THE MODEL TO IGNORE IT"). It is
punch-listed with the numbers above so the re-ruling starts from evidence.

### 3.2 What was armed

`adapters/edgar_adapter.py` — `capex` chain becomes two entries, generic tag first,
`conflict_check=False`:

```python
FieldSpec("capex", "flow", (
    ("PaymentsToAcquirePropertyPlantAndEquipment", "us-gaap"),
    ("PaymentsToAcquireProductiveAssets", "us-gaap"),   # NVDA/V/LRCX current tag
), conflict_check=False),
```

`core/fundamental_series.py:261` — the comment the punch list flagged as wrong on one name
is corrected: V was a **spec gap wearing a data-limit label**, and the label is why it went
unexamined. JPM and USB remain a real data limit.

**Pins: `tests/test_l4d_capex_synonym.py`, 19 tests. Suite 884 → 903, no pre-existing test
broke.** Verified to **FAIL 8 of 19 against the pre-fix single-tag spec** before landing —
the spec was reverted in place, the file re-run, and then restored. The 11 that pass either
way are the no-regression guards, which are supposed to hold on both sides.

Four pins worth knowing about before editing them:

- **A POSITIVE CONTROL** (`test_a_single_tag_spec_goes_QUIET_on_this_input_POSITIVE_CONTROL`)
  resolves the same facts twice, against a one-synonym spec and against the real chain, and
  asserts the one-tag result is a **silent None**. Without it the other pins cannot
  distinguish "the chain works" from "the input was easy".
- **A RULED-OUT PIN** (`test_LLY_third_tag_is_deliberately_absent`) asserts
  `PaymentsToAcquireOtherPropertyPlantAndEquipment` is NOT in the chain, with §3.1 in its
  docstring — so a later session reads a decision, not an oversight.
- **The conflict pin asserts a VALUE, not the flag**, and additionally asserts the trail
  records both tags. Without that trail assertion it passes pre-fix for the wrong reason
  (PRD simply never consulted) — a vacuous pass that was caught and closed.
- **The end-to-end pin asserts numbers**, per the L-4a finding that this suite had been
  asserting provenance strings where it should have been asserting values.

### 3.3 The production write

One write point. Expected delta stated in full before writing, reconciled after:

| | expected | actual |
|---|---|---|
| `fundamental_series` | **+385** (NVDA 99, V 133, LRCX 153), 3 new tickers | **+385**, 15 → **18** tickers |
| restatements / superseded | 0 / 0 | **0 / 0** |
| every other table | unchanged | **unchanged** |

Every table in the database was re-counted, not a named subset: evaluations 80,
field_provenance 1437, lifecycle_stage 44, lifecycle_transitions 1, synthesis_cache 16,
grades 0, overrides 0, lifecycle_overrides 0, sqlite_sequence 5 rows — **all +0**.
`sqlite_sequence`'s `fundamental_series` counter moved 1917 → 2302 in place, no new row.
**Nothing landed outside the stated set.**

- md5 trail: `7342f1a8` (open, and unchanged across all of steps 1–2 and the suite) →
  **`c0bae79159d5d2a325c35fd87dceda88`** (the single production write).
- Backup before the write: `caliber.db.pre-l4d-7342f1a8.bak`, md5 verified equal to the
  pre-write database.
- `PRAGMA wal_checkpoint(TRUNCATE)` returned `(0,0,0)` before every md5 reading; the empty
  wal/shm pair each read connection creates was removed and the md5 re-verified after.

### 3.4 Verified through the production reader

`evaluate._fy_series_from_db` — the reader step 4 will actually use, not a re-derivation:

**18 of 28 evaluable**, matching the dark-diff prediction exactly. NVDA 5 FY points, V 6,
LRCX 6. The reader is documented and confirmed **oldest-first** (`ORDER BY period_end`), so
the R2 signal reads `s[-3:]`.

**The R2 YOUNG signal set is UNCHANGED** — all three new names are firmly FCF-positive on
their newest three FY points (NVDA 27.0/60.9/96.7B, V 19.7/18.7/21.6B, LRCX 4.3/5.4/4.9B),
so all-negative-last-3 remains **IONQ, QBTS, RKLB, C**. Near-boundary LITE (n/n/p) and BE
(n/p/p) are also unmoved. **This change added no name to the YOUNG supply signal and
removed none.**

Corroboration worth recording: NVDA's newest FY FCF point is **$96.676B**, matching FMP's
`freeCashFlow` to the dollar. The 23% gap the cross-check reported for NVDA was purely the
TTM-vs-annual basis difference — at the FY grain the two sources agree exactly, which is
what the permanent advisory on that comparison has always claimed and is now measured.

One honest limitation, stamped per point rather than hidden: **V's series is on the
`truncated` share basis**, not `split_restated` — its 2015-03-19 split is uncorroborated
(2-of-3 witnesses required, per G-4). That affects only `fcf_yield`, which divides by a
market cap. FCF itself is share-independent, so the step-4 FY FCF series V contributes is
unaffected.

### 3.5 Carried to the punch list (ruled: own orders, not touched here)

1. **LLY's capex tag** — §3.1. Needs a ruling on whose capex definition governs when FMP
   and EDGAR disagree definitionally *and FMP is not self-consistent across years*.
2. **`net_income` single-tag exposure** — `NetIncomeLoss` is STALE on **BE and CAT**. A
   core field on a bare tag, same silent-expiry shape as capex.
3. **The single-tag census** — 9 of 19 specs have no synonym chain; feeds L-4e scope.
4. **ARM's 20-F blindness** and **TTM assembly for 10-Q-only YTD filers** — ruled out of
   scope; step 3's reason corrections will describe them accurately without changing them.

---

*Typed-reason corrections (the remaining work) are a separate ruling. Note the amendment
already improved two reasons for free — LLY `no_tag` → `stale_tag` and XE `no_tag` →
`ttm_unavailable` — which that work builds on rather than duplicates.*
