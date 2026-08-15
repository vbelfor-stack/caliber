# H-1 — fundamental series builder (DARK)

**Status: BUILT, DARK, NOT ARMED. Nothing reads this series to produce a score.**
Built by predecessor session `c2` (2026-08-15, 19:44–19:48Z); audited and adopted by the
successor session. Provenance is recorded because the audit — not the authorship — is what
this document rests on.

Surfaces: `core/fundamental_series.py`, `store/models.py` (schema + writer/reader),
`batch/runner.py` (dark call site), `tools/probe_fcf_series.py` (read-only probe),
`tests/test_fundamental_series.py` (31 tests).

Four audit findings were fixed before adoption — the reason-column overload (F3), the
restatement detector ignoring `method`/`unit`/`components` (F4), the untested
`split_restated` path (F5), and the yield leg having never produced a value anywhere (F1).
A fifth, the EDGAR 403, was accepted as an environment limitation (§9a).

---

## 1. What it produces

A per-period series of the FCF family, assembled from EDGAR flows and instants at each
period-end the issuer actually filed:

| metric | unit | share-dependent? |
|---|---|---|
| `fcf` | USD | no |
| `fcf_margin` | pct | no |
| `sales_to_capital` | ratio | no |
| `reinvestment` | USD | no — always NULL, see §5 |
| `fcf_yield` | pct | **yes** — the only leg that divides by a market cap |
| `fcf_growth` | pct | no |
| `revenue_growth` | pct | no |

`fcf = operating_cashflow − capex`. capex is filed as a POSITIVE outflow magnitude
(`PaymentsToAcquirePropertyPlantAndEquipment`), so this is a subtraction. If the sign
convention ever inverts, GOOG FY2025 reads ~256B instead of 73.27B and
`test_fcf_is_ocf_minus_capex_at_a_named_period_end` fails loudly.

---

## 2. Table schema — `fundamental_series`

```sql
CREATE TABLE fundamental_series (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker           TEXT    NOT NULL,
    metric           TEXT    NOT NULL,
    period_end       TEXT    NOT NULL,
    period_type      TEXT    NOT NULL,   -- FY | TTM_Q
    value            REAL,               -- NULL is legal (reinvestment)
    unit             TEXT,
    basis            TEXT,               -- G-4 split basis, or not_applicable
    method           TEXT,               -- TTM assembly method
    excluded         INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT,               -- set IFF excluded=1
    null_reason      TEXT,               -- set IFF value IS NULL and excluded=0
    components_json  TEXT,
    first_observed   TEXT    NOT NULL,
    last_confirmed   TEXT    NOT NULL,
    superseded       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_fundseries_key
    ON fundamental_series (ticker, metric, period_end, period_type, basis);
```

**ISSUER-KEYED, NOT EVALUATION-KEYED.** An FY2023 free cash flow is a property of the
issuer, not of a run. Keying it to `evaluation_id` would duplicate ~20 rows per ticker per
run and leave Phase M unable to say which eval to trust. Every other table in this store is
an evaluation snapshot; this one deliberately is not.

**APPEND, NEVER OVERWRITE.** A stored value is immutable. Three cases per incoming point:

| case | behaviour |
|---|---|
| unseen key | INSERT |
| identical value | no new row; `last_confirmed` touched to record re-observation |
| **different value** | old row marked `superseded=1`, new value INSERTED alongside it |

`last_confirmed` and `superseded` are the only columns ever updated in place, and neither
is a measurement — both are bookkeeping about observation. A restatement therefore leaves
the superseded figure readable, which is the evidence Phase G exists to preserve.

Read it back with `list_fundamental_series(...)`; `include_superseded=False` is the default,
so ordinary reads see one row per key.

---

## 3. Grain (ruling 1)

Native **quarterly TTM**, with `period_type` flagging which period-ends are fiscal year
ends. Per-year is then a **query** (`period_type='FY'`), not a second build — the anchor
gets its quarterly series and Phase M gets ~4× the points from one table.

Fiscal year ends are taken from the filings (`fp == 'FY'` on a 10-K), **never inferred from
month-of-year**: MU's fiscal year ends in August, and a 52/53-week filer's year end moves.
Pinned by `test_fiscal_year_ends_come_from_the_filings_not_from_the_calendar`.

---

## 4. Excluded-flag semantics (ruling 2)

**Exclusion is a READ-TIME FILTER, never a storage filter.** Negative-FCF periods are
stored in full with `excluded=1`.

The scoping report argued the exclusion was safe because a higher median makes a stock look
richer and MIN takes the least flattering anchor. **That argument holds only while the
consumer is MIN-of-medians.** Phase M sampling this series would be handed a distribution
with its left tail removed — MU loses 8 of 24 quarters, C loses 14 of 21 — which is
precisely the downside Monte Carlo exists to model.

The two consumers therefore read the same table differently:

| consumer | read | rationale |
|---|---|---|
| Phase M | `include_excluded=True` (**the default**) | the full distribution; the left tail is the point |
| anchor (H-3) | `include_excluded=False` | MIN-of-medians cannot read a negative yield |

Exclusion reasons: `negative_fcf` (no yield interpretation), `non_positive_base`
(−1.1B → +0.9B is not "+180% growth"). A **negative FCF margin is a reading, not an
exclusion** — it is economically meaningful and must not inherit the yield's exclusion.

### Three distinct absences — do not conflate them

| state | meaning |
|---|---|
| **not emitted** | UNCOMPUTABLE. An input was missing (no capex tag, no revenue at that period-end, non-positive invested capital). Counted in `diagnostics.uncomputable`, never silently swallowed. |
| **emitted, `excluded=1`** | COMPUTABLE but illegal for the anchor. Value stored in full; `exclusion_reason` says why. Phase M reads it; the anchor skips it. |
| **emitted, `excluded=0`, `value IS NULL`** | STRUCTURALLY UNAVAILABLE, not rejected. `null_reason` says why. Reinvestment only (§5). |

**The two reasons live in separate columns, and that separation is load-bearing.** A row is
absent from the anchor for one of two unrelated causes, and if they shared a column then
`reason IS NOT NULL` would silently mean two different things to Phase M. No consumer
should ever have to cross-check `excluded` to interpret a reason. Verified across all 234
stored rows: 16 excluded rows all carry an `exclusion_reason`, 48 null rows all carry a
`null_reason`, **zero rows carry both**, zero carry neither.

---

## 5. Reinvestment is NULL, and says why (ruling 3)

Reinvestment needs `capex − D&A + ΔWC`, and there is **no depreciation/amortization spec
among the 19 EDGAR field specs** — the same missing spec that deferred the EBITDA leg to
H-4. The column exists so Phase M needs no migration when EDGAR expansion lands it.

**No proxy, silent or otherwise.** Rows are emitted with `value=NULL` and
`null_reason='no_da_spec'` — **never** `exclusion_reason`, which is reserved for values
that exist and are rejected. `sales_to_capital` carries reinvestment duty for Phase M v1.

---

## 6. Basis stamping (G-4 carried forward)

`fcf`, `fcf_margin`, `sales_to_capital` and the growth rates divide by no market cap, so a
split cannot touch them; their basis is `not_applicable`. Claiming a split basis for them
would be false provenance.

**Only `fcf_yield` carries the G-4 basis, and it carries it per point.** The share series is
resolved through the same contract as `own_history_series`: the restated basis is preferred,
the truncated one is the fallback, and the basis is RETURNED rather than hidden, because a
yield computed on a truncated share series is a *different measurement* from one computed on
a restated series.

`splits is None` means **UNKNOWN, never "never split"** — `restatement_blocked` refuses and
the series falls back to `truncated (<reason>)`. On the truncated fallback a point can be
wrong by exactly the split ratio, which is why the stamp is per point rather than per run.

---

## 7. Blast radius — NONE → WRITER

H-1 applies nothing: no score, E(R), grade or confidence label reads this series.
`test_no_score_reads_the_series_yet` asserts `core/pillars.py` does not mention it, and is
the test that should be flipped deliberately when H-3 arms.

But H-1 **reclassifies this surface from "computes and logs" to "writes"**, so the
degraded-run write guard applies: `run_dark_fcf_series` persists **only when given a
`db_path`**, and the batch boundary passes the path its own guard has already validated. A
caller naming no destination gets the computation and the log with no write at all
(`test_the_dark_surface_writes_nothing_when_no_destination_is_named`).

Consequence to know: a **full live batch run is not degraded**, so it defaults to production
and will create and populate `fundamental_series` inside `caliber.db` on first run.

---

## 8. Gate evidence

### 8a. Persistence — PROVEN

Degraded run naming its destination:
`python -m batch.runner --fixture --no-synthesis --db-path /tmp/h1_scratch.db`

```
[MU]   basis=truncated (split record unavailable — basis unknown)  persisted: 133 rows, 0 restatements
[GOOG] basis=split_restated                                        persisted: 101 rows, 0 restatements
[V]    WITHHELD fcf=no_capex_tag                                   (no rows — correct)
```

234 rows total. Re-running writes 0 new rows and 0 restatements (the confirm path).
**Production `caliber.db` md5 unchanged at `54aa42e56b4b753fab18b77b552665fb`**, and the
`fundamental_series` table still does not exist in it.

### 8b. Per-ticker series — OFFLINE (EDGAR fixtures)

`fcf` metric, nine tickers. **Live EDGAR is unreachable from this container (HTTP 403 —
see §9), so this is fixture-recorded, not live.**

| ticker | basis | fcf pts | FY | negative | % | anchor-usable | **fcf_yield pts** |
|---|---|---|---|---|---|---|---|
| MU | truncated | 24 | 6 | 8 | 33% | 16 | **0** |
| GOOG | truncated | 24 | 6 | 0 | 0% | 24 | **0** |
| V | — | 0 | 0 | — | — | 0 | 0 · withheld `no_capex_tag` |
| NOW | truncated | 24 | 6 | 0 | 0% | 24 | **0** |
| WU | truncated | 24 | 6 | 0 | 0% | 24 | **0** |
| JPM | — | 0 | 0 | — | — | 0 | 0 · withheld `no_capex_tag` |
| BK | truncated | 24 | 6 | 4 | 17% | 20 | **0** |
| USB | — | 0 | 0 | — | — | 0 | 0 · withheld `no_capex_tag` |
| C | truncated | 21 | 6 | 14 | 67% | 7 | **0** |

Negative counts reconcile exactly against scoping §4c's `quarters − positive FCF`
(MU 24−16=8, C 21−7=14, BK 24−20=4, GOOG/NOW/WU 0). The scoping table's larger "excluded"
figures (MU 10, C 14→5 usable) are **yield-series** exclusions, which additionally drop
quarters lacking a price or share match — a quantity this run could not measure, because no
yield point was produced anywhere.

---

### 8c. The yield leg — MEASURED (F1 closed)

The leg H-3 arms had never produced a value under test. It now does, against the EDGAR
fixture paired with the **FMP** fixture (1,254 dated price rows) and a real split report:
GOOG produces **20 yield points**, all non-null, all `basis=split_restated`, all inside a
0–15% sanity band, with `components` reconstructing `market_cap = price × shares` and the
value re-derivable from them.

**The G-4 artifact is now pinned per point.** Restated vs truncated on the same GOOG data:

| period_end | restated | truncated | ratio |
|---|---|---|---|
| 2022-03-31 | 3.7493% | **74.9867%** | 20.0× |
| 2021-09-30 | 3.7061% | **74.1221%** | 20.0× |

Both bases produce the *same number* of points (20), so a count comparison would have
passed a broken implementation — the standing per-point ruling earning its keep again.
Exactly two of twenty quarters move, not every pre-split one, because the share series is
**mixed-basis**: most pre-split period-ends were restated by later filings, so their
`first_filed` is already post-split and the factor is 1. These two were not.

---

## 9. Known limitations

### 9a. ENVIRONMENT — EDGAR unreachable from this host (accepted, not worked around)

`sec.gov` and `data.sec.gov` return **HTTP 403** from this container: with and without a
declared `User-Agent`, sandboxed and unsandboxed, via both the adapter and plain `curl`.
FMP is unaffected (`fetch_splits GOOG → 2 events`).

**Suspected egress-IP block.** Ruled 2026-08-15: **accepted as-is for H-1, not to be worked
around.** FMP is the sole live feed by standing discipline and EDGAR is the cross-check, so
an offline fixture-recorded delivery is honest rather than degraded. Investigating the block
is a **separate environment task**, deliberately not in H-1's scope.

Consequence: the live probe could not run, and every figure in §8b is fixture-recorded.

### 9b. RESOLVED 2026-08-15 — `--fixture` batch mode now exercises the yield leg

*Was:* the legacy `tests/fixtures/ticker/*.json` recordings carried 3 price rows with no
`date` key, so `_price_on_or_before` never matched and the batch reported 0 yield points.

Fixture mode was migrated to the `tests/fixtures/fmp/*.json` recordings — the payload
production actually fetches, 1,254 dated rows — and the legacy set was deleted. The yield
leg now produces **118 points across six tickers** in a fixture batch run:

| ticker | fcf | FY | neg | %neg | usable | **fcf_yield** | y-excl | yield basis |
|---|---|---|---|---|---|---|---|---|
| MU | 24 | 6 | 8 | 33% | 16 | **20** | 6 | truncated |
| GOOG | 24 | 6 | 0 | 0% | 24 | **20** | 0 | **split_restated** |
| V | — | — | — | — | — | 0 | 0 | withheld `no_capex_tag` |
| NOW | 24 | 6 | 0 | 0% | 24 | **20** | 0 | **split_restated** |
| WU | 24 | 6 | 0 | 0% | 24 | **20** | 0 | truncated |
| JPM | — | — | — | — | — | 0 | 0 | withheld `no_capex_tag` |
| BK | 24 | 6 | 4 | 17% | 20 | **20** | 3 | truncated |
| USB | — | — | — | — | — | 0 | 0 | withheld `no_capex_tag` |
| C | 21 | 6 | 14 | 67% | 7 | **18** | 13 | truncated |

NOW and WU also became runnable at all — they had no legacy ticker fixture, so they failed
outright in fixture mode before.

### 9c. What the migration cost — recorded deliberately

The legacy fixtures were a **second, disagreeing source**, and several tests depended on
that disagreement without saying so: the cross-check's conflict/downgrade path was covered
because the yfinance-shaped recordings pre-dated the EDGAR ones and happened to diverge.
Against the FMP payload those fields agree, so the coverage would have evaporated silently.

It is now **deliberate**: `_pair_with_forced_conflict(ticker, field)` pushes one named
field 1.5× out of tolerance, so the test states which field conflicts and by how much
instead of inheriting it from a stale recording. Same for the anti-launder downgrade test.
This is strictly better coverage than the accident it replaces — but the accident was load
bearing, and losing it unnoticed was the real risk.

Related: `test_alignment_revoked_when_the_primary_switches_to_mrq` now sets the MRQ value
explicitly. It used to arrive free because MU's legacy fixture served `total_cash` as MRQ;
the FMP payload serves the FY figure, which activates the R-A alignment path the legacy
recording had been suppressing.
