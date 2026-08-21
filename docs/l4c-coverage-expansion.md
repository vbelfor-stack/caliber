# L-4c — `fundamental_series` coverage expansion

**Status: COVERAGE EXPANSION LANDED. §5 STEP 4 IS *NOT* ARMED AND MUST NOT BE ARMED ON
THIS EVIDENCE ALONE — see §4, which is the reason this report exists.**

Order (CLAUDE.md, from Vic's 2026-08-17 close order): *"then coverage expansion capped at
one order, step 4 ruled on its evidence."* Fail-closed constraint carried with it:
coverage expansion must not manufacture FCF where the filings do not support it — a name
that cannot be covered gets a TYPED REASON, never a synthetic series.

Executed 2026-08-21. Zero writes outside `fundamental_series`.

---

## 1. What landed

`fundamental_series` coverage went from **4 tickers to 15** of the 28-name universe.

| | before | after |
|---|---|---|
| rows | 557 | **1917** (+1360) |
| tickers | 4 (MU/GOOG/NOW/WU) | **15** |
| restatements | — | **0** |
| superseded rows | 0 | **0** |
| caliber.db md5 | `8557a157ee92e22df01cfe04cb1e1d55` | `7342f1a87c812ab5c2f0248f97ddcf65` |

Eleven names added, each a ticker the table had never held, so the expected delta was
assertable exactly and was asserted exactly:

| ticker | rows | FY fcf pts | basis | ticker | rows | FY fcf pts | basis |
|---|---|---|---|---|---|---|---|
| BE | 120 | 6 | split_restated | LITE | 123 | 6 | split_restated |
| BK | 104 | 6 | split_restated | QBTS | 109 | 6 | split_restated |
| C | 105 | 6 | split_restated | RKLB | 132 | 6 | split_restated |
| CAT | 153 | 6 | split_restated | STX | 153 | 6 | split_restated |
| FN | 128 | 6 | split_restated | GOOGL | 121 | 6 | split_restated |
| IONQ | 112 | 6 | split_restated | | | | |

Every one of the eleven carries **six full FY points running to a 2026 period-end**
(newest `period_end` between 2026-03-31 and 2026-07-03), so none is a silently truncated
series. That was checked BEFORE the write, not after — a series that stops in 2020 while
looking complete is precisely the failure mode §4 turns out to describe.

**Expected-delta reconciliation: expected +1360 across 11 new tickers, actual +1360,
restatements 0 — MATCH.** Every other table was re-counted after the write and is
unchanged: evaluations 80 (max id 272), field_provenance 1437, lifecycle_stage 44,
lifecycle_transitions 1, synthesis_cache 16, grades 0, overrides 0, lifecycle_overrides 0.
`sqlite_sequence` moved only its `fundamental_series` counter (557 → 1917), in place.

Backup taken before the write: `caliber.db.pre-l4c-8557a157.bak`, md5 verified equal to
the pre-write database.

---

## 2. The new surface — `tools/expand_fcf_series.py`

`fundamental_series` had only ever been written from inside
`batch/runner.run_single_ticker`. The only way to give a name FCF history was therefore to
also write it an evaluation, a lifecycle_stage row, provenance and a synthesis — which
this order explicitly forbids. So the series build got its own named entry point.

It is `tools/probe_fcf_series.py` plus a destination and adds no computation of its own:
same calls (`fetch_fmp` → `fetch_edgar` → `fetch_splits` → `build_split_report` →
`build_fcf_series`), same order, so a series written here cannot differ from one the batch
path would have written.

Three properties worth knowing before editing it:

- **Writes are opt-in.** Without `--commit` it computes, prints the full expected delta and
  persists nothing — not even an empty destination file. That readout IS the
  expected-delta statement, and `--commit` then writes from THE SAME IN-MEMORY BUILD that
  was printed, so there is no fetch between the statement and the write for reality to
  drift through.
- **The destination resolves once**, `db_path or _DEFAULT_DB`, exactly as evaluate.py:259.
  `save_fundamental_series` is the only writer reachable from the module, pinned over the
  AST.
- **The expected delta is computed against the destination, not assumed.** A ticker the
  destination has never held is held to an exact count; a ticker it already holds is a
  RE-OBSERVATION, where the append-only writer correctly adds zero rows. The first cut
  asserted `+N` unconditionally and reported correct idempotent behaviour as a MISMATCH.
  That was fixed before the production run and is pinned, because a reconciliation that
  cries wolf is one a later session learns to wave through.

Pinned by `tests/test_l4c_coverage_expansion.py` (8 tests): fail-closed writes nothing and
does not even create its destination; a raising build becomes a typed reason rather than
killing the run; table isolation asserted over EVERY declared table rather than a named
list; named destination takes the rows AND production is untouched; dry run leaves no
file; new-vs-re-observed delta semantics, with a **positive control** that forces a short
count and requires exit 3 — without it the "no MISMATCH" assertions would be vacuous.

Suite 876 → **884**, no pre-existing test broke. Production md5 unchanged by the suite.

---

## 3. Fail-closed: the 13 names that got no rows

Thirteen of the 24 wrote nothing. **No partial series, no zero rows, no carried-forward
values, no placeholder.** That part of the constraint held completely.

What did NOT hold is the second half of it — *"gets a TYPED REASON"*. The builder emitted
only two reasons, `no_capex_tag` and `no_operating_cashflow_tag`, and **for 9 of the 13
that reason is either wrong or misdescribes the cause.** Taking the reason at face value
would record OUR extraction limits as the issuers' filing limits.

---

## 4. ★ THE FINDING — "uncovered" is mostly OUR gap, not the filings'

**This is the part that bears on step 4 and it is the reason step 4 is not being armed in
this order.** Every claim below is measured from SEC `companyfacts` for the issuer's own
CIK, alongside what our adapter resolved.

### Class 1 — CAPEX SPEC GAP. The filings DO support FCF. **4 names: NVDA, LLY, V, LRCX**

`FIELD_SPECS` gives `capex` exactly ONE concept,
`PaymentsToAcquirePropertyPlantAndEquipment` (`adapters/edgar_adapter.py:99`). All four
file capex under **`PaymentsToAcquireProductiveAssets`** — a standard us-gaap concept —
and our spec does not list it. They resolve 14–16 of 19 fields otherwise; only capex is
missing, and only capex is needed to unblock the whole family.

**NVDA is the sharpest case and it is a repeat of a defect this codebase has already
diagnosed once.** It files the concept we DO look for — but the last fact under it ends
**2020-07-26**, after which NVDA migrated to `PaymentsToAcquireProductiveAssets`. That is
the same shape as the recorded JPM bank-tag migration (`CashAndCashEquivalentsAtCarryingValue`
→ `CashAndDueFromBanks`, handled by adding the synonym). A single-tag spec silently expires
when an issuer restates its taxonomy.

Note this also revises a comment already in the tree. `core/fundamental_series.py:261` reads
*"V, JPM and USB file no PaymentsToAcquirePropertyPlantAndEquipment concept at all. This is
an ACCEPTED DATA LIMIT."* For **V that is a spec gap, not a data limit** — V files
`PaymentsToAcquireProductiveAssets`. For JPM and USB the comment is correct (Class 4).

### Class 2 — INSUFFICIENT FILING HISTORY. **4 names: CBRS, DPC, SPCX, XE**

Recent listings: **10-Q forms only, no 10-K**. They file
`NetCashProvidedByUsedInOperatingActivities` and a capex concept, but `operating_cashflow`
resolves to None and the builder reports `no_operating_cashflow_tag`.

The *outcome* (no FCF history) is right — a company with no annual filing genuinely has
none. **The typed reason is wrong**: it says the tag is absent when the tag is filed. The
true mechanism (staleness gate, or TTM assembly having no prior-year leg) is a diagnosis
question, not settled here.

### Class 3 — NON-10-K FILER. **1 name: ARM**

ARM files **20-F and 6-K** — a foreign private issuer. The adapter resolves **0 of 19
fields**. This is not an FCF problem: the *entire EDGAR surface is blind for ARM*, which
also means its lens selection and cross-check run without filings. Blast radius wider than
L-4c; recorded here because L-4c is where it surfaced.

### Class 4 — GENUINELY ABSENT IN THE FILINGS. **4 names: JPM, USB, INFQ, SKHY**

JPM, USB and INFQ file **no capex-like concept at all** — checked across every us-gaap
concept, not just our spec. Banks bundle premises-and-equipment purchases elsewhere. SKHY
files **no XBRL facts at all** (no OCF concept, no capex concept, no forms).

**These four, and only these four, are correctly fail-closed with an accurate reason.**

### Summary

| class | names | filings support FCF? | reason emitted is accurate? |
|---|---|---|---|
| 1 — capex spec gap | NVDA, LLY, V, LRCX | **YES** | **no** |
| 2 — insufficient history | CBRS, DPC, SPCX, XE | no (no annual filing yet) | **no — tag IS filed** |
| 3 — non-10-K filer | ARM | unknown (surface blind) | **no** |
| 4 — genuinely absent | JPM, USB, INFQ, SKHY | no | yes |

Note BK and C — both banks — **do** resolve capex and are covered. So "banks file no capex"
is not a uniform rule and Class 4 cannot be inferred from sector; it was checked per issuer.

---

## 5. Step-4 readiness, read through the reader step 4 will actually use

Verified via `evaluate._fy_series_from_db(db, ticker, 'fcf')` — the production reader, not
a re-derivation. The classifier's gate refuses below three usable FY points
(`only_N_fy_fcf_points`, `core/lifecycle.py:516`).

**15 of 28 names are now step-4 evaluable, up from 4.** All 15 carry 6 usable FY points;
none sits near the three-point boundary.

The names whose last three FY FCF readings are **all negative** — the R2 YOUNG signal step 4
would act on — are **IONQ, QBTS, RKLB and C**. LITE reads neg/neg/pos and BE reads
neg/pos/pos, so both are near the boundary and would move on one more year of data.

**Why this is still not sufficient to rule step 4.** Of the 13 names with no series, 9 lack
one because of Class 1–3 above rather than because their businesses have no FCF history.
Arming a YOUNG supply block now would block or exempt names on the basis of **which XBRL
concept their accountants chose**, which is the exact failure the standing ruling names:
*"the YOUNG/blocked boundary currently reflects FEED COVERAGE, not business reality, and a
hard block on that basis would be arbitrary."* That ruling is not yet discharged — it is
better evidenced. Class 1 in particular is four large, unambiguously FCF-positive issuers
that would read as absent.

---

## 6. What needs a ruling (NOT done in this order)

1. **Add `PaymentsToAcquireProductiveAssets` to the `capex` FieldSpec** (Class 1). One
   synonym recovers NVDA, LLY, V and LRCX — 15 of 28 would become 19 of 28. **Not done
   here: `FIELD_SPECS` feeds the EDGAR cross-check and the ARMED SET, so adding a concept
   changes data resolution beyond this order's scope, and the standing rule is to stop
   before that.** Precedent and template exist (the JPM tag migration). Worth pairing with
   a sweep for other single-tag specs that can expire the same way — `capex` is unlikely to
   be the only one.
2. **Correct the typed reasons** so Class 2/3 do not report as `no_*_tag` when the tag is
   filed. A reason that misdescribes its cause is how a spec gap gets filed as a data limit
   — which is what happened to V at `core/fundamental_series.py:261`.
3. **ARM's 20-F blindness** (Class 3) — scope unknown, wider than FCF, its own diagnosis.
4. **Then rule step 4** on the recovered evidence.
5. **GOOG/GOOGL now both carry a full series on ONE CIK** (`0001652044`), as the
   share-class dedup punch-list item predicted. This is correct for step 4, which reads
   per ticker and needs GOOGL (the held line) to be evaluable at all. It is a live
   double-count hazard **only for grade rollups**, which do not exist yet. Dedup by CIK
   before any aggregate, per the existing punch-list entry.

---

## 7. Execution record

- Read-only survey of all 24 missing names first, via `tools/probe_fcf_series.py`
  (imports no writer). caliber.db md5 unchanged across it.
- EDGAR pre-flight on the adapter's own fetch path immediately before the run, per the
  2026-08-15 standing discipline: all 28 CIKs resolved, `fetch_edgar` clean.
- Writer validated on a scratch db before production: table isolation confirmed (only
  `fundamental_series` non-empty), idempotency confirmed (382 rows → re-run → 382 rows, 0
  superseded).
- `PRAGMA wal_checkpoint(TRUNCATE)` returned `(0,0,0)` before each md5 reading.
- md5 trail: `8557a157` (open) → `8557a157` (survey, scratch validation) →
  **`7342f1a8`** (after the single production write) → `7342f1a8` (after the suite).
  **One write point this session.**
