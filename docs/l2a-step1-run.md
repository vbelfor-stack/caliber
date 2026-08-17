# L-2a STEP 1 — SANCTIONED PRODUCTION RUN (§5 arming step 1 of 4)

**Order:** L-2a, ruled 2026-08-17 · **Commits:** `f2904dc` (step 0) · `1ab384a` (step 1)
**Run:** `python evaluate.py <T>` live, interactive path, golden five + four calibration banks
**Suite:** 776 · **§5 steps 2–4 NOT armed.** `pillars`, `valuation_anchors`, `batch/runner`,
`synthesis/schema` remain pinned dark.

## 1. Stage rows written — 9, one per name

| id | ticker | lens | stage | flags |
|---|---|---|---|---|
| 1 | MU | cyclical | MATURE | GUARD-TOLERANCE-UNCALIBRATED, REINVESTMENT-THRESHOLD-UNCALIBRATED |
| 2 | GOOG | compounder | MATURE | REINVESTMENT-THRESHOLD-UNCALIBRATED |
| 3 | V | compounder | MATURE | INPUTS-INCOMPLETE |
| 4 | NOW | growth | HIGROWTH | INPUTS-INCOMPLETE |
| 5 | WU | compounder | DECLINE | — |
| 6 | JPM | bank | MATURE | INPUTS-INCOMPLETE |
| 7 | BK | bank | MATURE | INPUTS-INCOMPLETE |
| 8 | USB | bank | MATURE | INPUTS-INCOMPLETE |
| 9 | C | bank | MATURE | INPUTS-INCOMPLETE |

`lifecycle_transitions` = **0**, correct: a first classification is never a transition.

## 2. Verdicts vs the L-1d dark table — IDENTICAL, all nine

MU/GOOG/V MATURE · NOW HIGROWTH · WU DECLINE · JPM/BK/USB/C MATURE.
**Flag sets are identical too**, not just the stages — the comparison of L-1d's recorded flags
against the persisted `flags_json` produced an empty diff. Live interactive annotation and the
offline dark run agree exactly.

## 3. Transient-feed readings — ZERO

No `INPUTS-INCOMPLETE-FEED-TRANSIENT` on any of the nine: every live dividend lookup answered.
The five `INPUTS-INCOMPLETE` readings are all **structural and permanent**, and say so —
`fcf_negative_2of3(no_fcf_series)` and `reinvestment_heavy(no_series)` for V and the four
banks, `reinvestment_heavy(only_1_point_series)` for NOW. Exactly the R2/R6 absences on
record. The distinction the ruling asked for is now visible in production data: nothing here
is a reading to distrust.

## 4. Production md5 — CHANGED, EXPECTED, both values logged

```
before  e5f337b806d3590a9a5cb484cb1edada     (the post-purge clean baseline)
after   dc03507894f870f277e335ce3befbb6e     (this run)
```

**Full delta set, with dependents named:**

| table | before | after | expected? |
|---|---|---|---|
| `lifecycle_stage` | 0 | **9** | YES — the sanctioned target |
| `lifecycle_transitions` | 0 | 0 | YES — first classification is not a transition |
| `evaluations` | 36 | **45** | YES — a live evaluate.py run persists a real evaluation |
| `field_provenance` | 525 | **714** | YES — +21 per eval, the standing companion |
| `sqlite_sequence` | 3 | **4** | YES — the new AUTOINCREMENT table |
| `synthesis_cache` | 16 | 16 | **unchanged** — `evaluate.py` does not write the cache; only `batch/runner` does |

**Nothing outside the stated set changed.**

**ID CONTINUITY: the purge gap is preserved and that is a feature.** The nine new evaluations
are ids **229–237**; 226–228 are permanently skipped because AUTOINCREMENT does not reuse.
The gap is standing evidence that three rows were removed.

## 5. TWO DEPENDENTS NEITHER OF US NAMED IN ADVANCE — reported, not absorbed

The order named stage rows. The run also produced **nine real, live, full-synthesis
evaluations** (ids 229–237, all `status='ok'`, all carrying E(R)). Those are legitimate — a
full live run is not degraded and defaults to production by design — but two consequences
follow that the order did not state, and the expected-delta discipline exists to surface
exactly this:

1. **FOUR BANK EVALUATIONS ARE NOW IN PRODUCTION AND WILL BE GRADEABLE IN ~90 DAYS.**
   JPM (234), BK (235), USB (236), C (237). Per the D-5/D-6 ruling the four banks are
   **CALIBRATION INSTRUMENTS, NEVER HOLDINGS** — pinned absent from `tickers.txt`, held in
   `CALIBRATION_CIKS`. Nothing about that ruling anticipated bank rows entering the
   **grading set**, where they will be scored as if they were positions. **This needs a
   ruling:** leave them (grades on calibration instruments are informative but not
   portfolio evidence), or mark/exclude them from `run_grading`'s eligibility query. I have
   changed nothing.
2. **Five golden + four bank E(R)s are now on record for 2026-08-17**, which moves the
   grading baseline. Values: MU −12.33, GOOG +6.16, V +6.04, NOW +2.80, WU −7.38,
   JPM −3.59, BK −7.69, USB +3.28, C −3.86.

## 6. Two open D-phase tripwires CHECKED — neither fired

- **Tripwire 1 (first standard-lens eval):** lenses seen were bank, compounder, cyclical,
  growth. **No standard-lens eval occurred**, so the tripwire remains un-fired and the
  standard mapping remains unvalidated by live evidence.
- **Tripwire 2 (first live bank eval in rung 4 or 5):** bank Valuation cells came in at
  JPM 2, BK 2, USB 3, C 2 — **none in the provisional-uncalibrated rungs**, so
  BANK-RUNG-UNCALIBRATED did not fire.
- Incidentally corroborated: C scores Valuation 2 with `RICH-VS-JUSTIFIED-PB` **and**
  `ROE-BELOW-COST-OF-EQUITY` (avg 2.4, the lowest of the nine) — the bank value trap the
  D-6 instrument was built to catch, now visible in live production data rather than in a
  calibration record.

## 7. The batch synthesis-cache leak — AUDITED AND CLOSED

Question: did any batch run between 2026-08-09 and today execute `--fixture` WITH synthesis?
**No**, on three independent measurements:

1. **Orphan test:** all 16 `synthesis_cache` rows have a matching production evaluation for
   the same ticker+date. A `--fixture --db-path` run would by construction leave a cache row
   whose evaluation went to the scratch DB — an orphan. There are none.
2. The only post-08-09 cache rows are the five from the sanctioned live re-run of 2026-08-15,
   and every price is a live value differing from the fixture value (GOOG 343.54 vs 343,
   MU 971.66 vs 979.3, NOW 124.0 vs 127.54, V 364.15 vs 348.97, WU 7.45 vs 7.08).
3. The only `--fixture` batch invocation in the repo record is
   `--fixture --no-synthesis --db-path /tmp/h1_scratch.db` (`docs/h1-series.md:191`), which
   writes no cache row.

**RED HERRING, named so it is not re-opened:** cache row `V 2026-07-12 price=348.97` matches
V's fixture price exactly. Benign — it predates both the window and D-2's `--db-path` (before
which everything went to production by design), it has a matching production evaluation from
the documented genuine live session, and V's fixture was recorded in that era.

## 8. Incident closure

The contaminated backup `caliber.db.contaminated-2026-08-17-195e6687.bak` is **deleted** now
that this report verifies, per ruling — a contaminated backup outliving its purpose is its own
hazard. md5 trail preserved in CLAUDE.md: `e13cbee6` → `195e6687` (contaminated) →
`e5f337b8` (purged baseline) → **`dc035078`** (this sanctioned run).

## 9. STOP

Step 2 (full-universe dark run, ~20 live names + watchlist) is its own order. Two items above
want a ruling first: **the four bank evaluations in the grading set** (§5.1), and nothing else
blocks.
