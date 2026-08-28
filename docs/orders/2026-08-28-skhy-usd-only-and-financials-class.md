# ORDER — SKHY expansion (USD-only) + financials classification
**Issued by Vic, 2026-08-28. Committed BEFORE any execution, per standing discipline.**

Order document only. Every measurement below was taken READ-ONLY, live, before this file
was committed, and every one was taken TWICE on independent fetches (the "re-check" pass).

---

## 0. STATE VERIFICATION (chat-carried pointers re-measured in container)

| | expected (chat) | measured | verdict |
|---|---|---|---|
| HEAD | `390d20a` | `390d20a45974561c085c98b2c5141cd5284ab6de` | MATCH |
| suite | 984 | **984 passed** (twice, 16.80s / 14.54s) | MATCH |
| caliber.db md5 | — | **`eec96270720d80d632aa3a6f9528ea49`** | matches the L-4d.1 close value in CLAUDE.md |
| unpushed | — | `git rev-list --count origin/master..master` = **0** | clean |
| tree | — | one modification: `.gitignore` (+3, `.scratch_skhy/`) — made by this session | stated, not hidden |
| own PID | — | **209**, verified EMPIRICALLY by spawning a bash child and walking PPID → 209 → 77 → 35 → 14 | verified this session |
| peers | — | **NONE.** The only other `claude`-matching rows were this session's own bash children | clear |
| orphans (ppid 1) | — | **NONE** (`ps -eo pid,ppid,etime,cmd | awk '$2==1'` filtered for python/evaluate/batch/pytest) | clear |

WAL checkpointed `(0,0,0)` before each md5 reading. No `caliber.db-wal`/`-shm` pair exists.

---

## 1. VIC'S RULINGS (transcribed verbatim from the 2026-08-28 chat)

> **1. FINANCIALS CLASSIFICATION.** FCF-model inapplicability is a CLASS, not a per-ticker
> call. Names whose FMP sector/industry marks them as banks/insurers/diversified financials
> are flagged model-inapplicable: fetchable, stored, typed flag row, NO numeric scores from
> the FCF engine. JPM and USB resolve under this class. Report which current-universe names
> the class catches — no pre-filtering, list them all.
>
> **2. SKHY CURRENCY: USD ONLY.** Ingest only what FMP supplies natively in USD. KRW-only
> periods excluded with typed block rows — never converted. Short history accepted;
> YOUNG/coverage rules apply to whatever USD depth survives.
>
> **3. H-4:** stays parked. No FMP reinvestment.

**Ruling 2 SUPERSEDES the 2026-08-21 SKHY currency addendum** (folded into the doctrine
order §8), which ordered period-matched KRW→USD conversion. Conversion is now ruled OUT.
Consequences, stated rather than left to be rediscovered:

- §8.1(1)–(5) (period-matched conversion, the ingest-date-rate prohibition, the FMP forex
  source, the per-row rate record, KRW preservation) are **MOOT** — there is no conversion
  to govern. They are not deleted from the record; they are superseded.
- §8.1(7)'s **standing currency gate SURVIVES and is what this order builds**, but its typed
  reason cannot keep the name `currency:unconverted`. "Unconverted" presupposes conversion
  is the remedy, and ruling 2 removed that remedy — a constant that asserts the wrong cause
  is exactly the `WITHHELD_NO_CAPEX`/`WITHHELD_NO_OCF` defect L-4d deleted rather than
  renamed. This order uses **`currency:non_usd_native`**, which states only what was
  measured.
- The **$38–40B FY2025-OCF verification anchor is MOOT too.** It existed to prove the
  conversion plumbing; there is no conversion plumbing. It is not "still failing by 1.0%" —
  it no longer has a subject. See §4 for what it actually measured.

---

## 2. STEP (a) — SKHY USD vs KRW, MEASURED

**Method.** Six FMP statement endpoints (income / balance-sheet / cash-flow × annual /
quarter), through the adapter's own `_get`, so the request shape cannot drift from
production. Every returned row's `reportedCurrency` counted. Run twice.

| endpoint | rows | currencies |
|---|---|---|
| `income-statement?period=annual` | 19 | `{KRW: 19}` |
| `income-statement?period=quarter` | 24 | `{KRW: 24}` |
| `balance-sheet-statement?period=annual` | 19 | `{KRW: 19}` |
| `balance-sheet-statement?period=quarter` | 24 | `{KRW: 24}` |
| `cash-flow-statement?period=annual` | 19 | `{KRW: 19}` |
| `cash-flow-statement?period=quarter` | 24 | `{KRW: 24}` |
| **TOTAL** | **129** | **`{KRW: 129}`** |

### ★ THE USD SET IS EMPTY. **0 of 129 periods.** There is no split to report — it is a
### partition with one side.

Corroborating detail, not inference: the FY2025 cash-flow row reads
`operatingCashFlow = 53,373,126,000,000`, `capitalExpenditure = -28,579,343,000,000`. Both
are order 10¹³, consistent with KRW and impossible as USD.

**CONSEQUENCE FOR STEP (b), STATED PLAINLY.** Under ruling 2 the ingest set is empty, so
step (b) writes **zero numeric rows** and reduces to typed block rows. This is the ruling
operating correctly, not a shortfall: the ingest and the block are the same measurement seen
from two sides.

**AND THEREFORE ONE THING THIS ORDER DELIBERATELY DOES NOT BUILD — flagged for Vic, not
decided here.** An FMP-basis *numeric* series builder (the one that would clear the two
recorded conversion traps: FMP's negative capex sign against `build_fcf_series`'s
`ocf - capex`, and the R2 boundary re-measurement) **is not written this session.** With
zero USD periods anywhere in the universe's only non-USD name, such a builder would be a
production write path exercised by nothing — and *a sweep that cannot fire proves nothing*
cuts both ways. Instead the ingest tool **REFUSES LOUDLY** if a USD period ever appears, so
the day one does, it stops and reports rather than writing down an unbuilt path.
**If Vic wants the builder now, it is a separate order and this is the place that says so.**

---

## 3. STEP (c) — THE FINANCIALS CLASS, MEASURED OVER ALL 28

**No pre-filtering.** All 28 evaluated names were re-fetched live and classified.

**Class definition — reuse, not a second taxonomy.** A name is FCF-model-inapplicable when
`core.lens_select.select_lens(sector, industry, sic=None, ticker=None)` returns `"bank"`.
Three properties, each deliberate:

- **`sic=None`.** Ruling 1 says *FMP sector/industry*. Passing SIC would make the class
  EDGAR-score-bearing, and the doctrine's unresolved pre-flight contradiction is already one
  such path too many.
- **`ticker=None`.** Ruling 1 says the inapplicability is *a CLASS, not a per-ticker call*.
  Admitting the hand-curated override list would reintroduce exactly the per-ticker judgement
  the ruling removes.
- **No new keyword list.** `_BANK_INDUSTRY` already encodes banks / insurers / REITs, and
  `_COMPOUNDER_INDUSTRY` is already checked FIRST, which is what keeps payment networks out.
  A parallel list would be duplicate logic and would drift.

### CAUGHT — 4 of 28: **BK, C, JPM, USB**

| ticker | FMP sector | FMP industry |
|---|---|---|
| BK | Financial Services | Investment - Banking & Investment Services |
| C | Financial Services | Banks - Diversified |
| JPM | Financial Services | Banks - Diversified |
| USB | Financial Services | Banks - Diversified |

JPM and USB resolve under the class exactly as Vic's ruling anticipated. BK and C join them.

### NOT CAUGHT, AND THIS IS THE PART TO READ: **V and WU**

Both are FMP sector **Financial Services**. Both are industry **Financial - Credit
Services**, so `_COMPOUNDER_INDUSTRY` claims them before the bank check runs, and both score
on the **compounder** lens. **A sector-level rule would have caught them and been wrong** —
they are asset-light payment networks with real, large, positive FCF, they are *currently
covered* in `fundamental_series`, and flagging them model-inapplicable would destroy working
coverage on two names to enforce a class neither belongs to. Ruling 1's wording is
"banks/insurers/diversified financials", not "the Financial Services sector", and the
distinction is load-bearing here rather than pedantic.

The remaining 24 names classify to cyclical / standard / compounder / growth; none is caught.

### ★ THE MEASURED CONSEQUENCE ON C — the one place this class changes a live signal

C is a bank AND it is one of the four names in the R2 YOUNG all-negative-last-3-FY-FCF set.
Its stored FY FCF: `2023 −$80.0B, 2024 −$26.2B, 2025 −$74.2B` — all three negative.

For a bank, a large negative FCF is a **financing-and-balance-sheet artifact, not evidence
of a pre-earnings company**, which is the whole reason the class exists. So the class, if it
reaches the classifier, would take the R2 set from **IONQ/QBTS/RKLB/C → IONQ/QBTS/RKLB.**

**THIS ORDER DOES NOT MAKE THAT CHANGE.** Reaching it means changing what the lifecycle
classifier reads, which is a scoring-path change and is not in this order's scope. It is
measured here, named as an open question, and left for Vic — see §6.

### Where the class IS enforced this session, and why the effect is zero today

`own_history_fcf_yields` (the FCF-yield own-history panel anchor) refuses for a class member.
**Measured effect on scores today: ZERO, and structurally so** — `ARMED_PANEL_LENSES` is
`('compounder','cyclical','standard')`; `bank` is not in it, and `_valuation_bank(yf, fred)`
does not take `panel` as a parameter at all (verified by `inspect.signature`). A bank-lens
name's panel is computed and logged but never scored. So the guard is real and binds the day
a financials-class name lands on a panel-scored lens, while moving nothing now.

---

## 4. STEP (d) — ANCHOR RE-MEASURE, READ-ONLY. NO ANCHOR WRITE.

### 4.1 What FMP serves, exactly

| endpoint | field | value | currency | date |
|---|---|---|---|---|
| `profile?symbol=SKHY` | `marketCap` | **1,141,659,621,195** | USD | (no date field; `price` 160.83) |
| `market-capitalization?symbol=SKHY` | `marketCap` | **1,141,659,621,195** | USD | **2026-08-28** |
| `quote?symbol=SKHY` | `marketCap` | 1,141,659,621,195 | USD | (`price` 160.83) |
| `key-metrics-ttm?symbol=SKHY` | `marketCap` | **1,173,390,134,823,000** | **KRW** | — |
| `shares-float?symbol=SKHY` | `outstandingShares` | 7,098,548,910 | — | 2026-08-28 18:30:18 |
| `shares-float?symbol=SKHY` | `floatShares` / `freeFloat` | 5,662,818,000 / 79.7743% | — | 2026-08-28 |

**The endpoint to quote is `market-capitalization?symbol=SKHY`, field `marketCap`** — it is
the only one of the four that carries its own `date`, which is precisely what an anchor
needs. **Value $1,141,659,621,195 USD as of 2026-08-28.**

It reconciles exactly: `7,098,548,910 × $160.83 = 1,141,659,621,195` — **0.000%**. Note the
figure moves intraday (a re-fetch minutes later read 1,143,150,316,466 at price 161.04), so
any stored anchor must carry its price and timestamp.

### 4.2 Reconciling Vic's ~$909.30B — measured, not guessed

| candidate | value | vs $909.30B |
|---|---|---|
| **free-float USD cap** (full × 79.7743%) = `floatShares × ADR price` | **$910.75B** | **+0.16%** |
| KRW cap ÷ today's USDKRW (1,378.24) | $851.37B | −6.37% |
| full ADR USD cap | $1,141.66B | +25.55% |

**Vic's ~$909.30B is the FREE-FLOAT market cap** — it matches to +0.16%, a single price
tick (the exact figure falls out at an ADR price of $160.56 against today's float). The
other two candidates miss by 6.4% and 25.6% and are not close enough to be the source. The
gap between Vic's number and the full cap is therefore **not an error on either side — it is
free-float vs full-cap**, and which one the anchor should store is a decision, not a
correction.

### 4.3 What the prior $37.4–37.8B band actually measured — the reconciliation Vic asked for

**It measured FY2025 OPERATING CASH FLOW, converted to USD. It was never a market cap.**

It is the doctrine order §8.3 verification anchor: SKHY's FY2025 `operatingCashFlow` of
KRW 53,373,126,000,000 divided by a 2025-average USDKRW, across six averaging conventions,
landing $37.43B–$37.61B. That is a **one-year flow off the cash-flow statement**. A market
cap is a **price-level stock**. They are different quantities measured in different units of
meaning, and there is no sense in which one should equal the other.

**So the "~24x gap" is not a discrepancy — it is a multiple, and it is almost exactly the
P/OCF ratio implied by Vic's own two numbers:**

| numerator | ÷ FY2025 OCF | multiple |
|---|---|---|
| Vic's $909.30B (free float) | $37.61B | **24.18x** |
| Vic's $909.30B (free float) | $37.43B | 24.29x |
| full ADR USD cap $1,141.66B | $37.61B | 30.36x |

**24.18x ≈ the "~24x" in the order.** Nothing is inverted, mis-united or mis-plumbed; the
two figures were simply never the same measurement. This also retires the last live piece of
the §8.3 item: the band did not "fail by 1.0%" against anything that matters any more,
because ruling 2 removed the conversion it was verifying.

### 4.4 ★ TWO FINDINGS THAT FELL OUT OF (d), NEITHER IN SCOPE, BOTH MEASURED

**(i) `key-metrics-ttm.marketCap` IS SERVED IN KRW FOR SKHY, AND THAT FIELD IS
SCORE-BEARING.** `adapters/fmp_adapter.py:457` sets `market_cap = _p(metrics.get("marketCap"))`
where `metrics` is `key_metrics_ttm` (`:587`), and `core/pillars.py:237-238` computes
`fcf / yf.market_cap.value * 100` for the FCF-yield bonus. For SKHY that field is
**1,173,390,134,823,000 — byte-identical to `000660.KS`'s (the Korean ordinary listing)
profile marketCap, delta exactly 0.** Controls: NVDA and ARM both read `key-metrics ÷ profile
= 1.0000`, so **SKHY is the sole anomaly in the universe**, and the divergence is ~1,028x.

Today it happens to be *self-consistent* — `free_cashflow` comes from the cash-flow statement
and is also KRW — so the FCF-yield ratio is KRW/KRW and is not wrong. **It is a latent
1,000x trap, not a live defect**, and it is recorded, not fixed: fixing it is a change to a
score-bearing adapter field on a name whose evaluation this order does not touch.

**This also finally settles the CLAUDE.md item "TWO FMP ENDPOINTS DISAGREE ABOUT SKHY'S
CURRENCY", and the previous ruling on it was too harsh.** `profile.currency = USD` is **not
"WRONG for this issuer"** — it is the **QUOTE** currency of the NASDAQ ADR, and it is
correct. Control measurement: `000660.KS` reads `profile.currency = KRW` on exchange KSC.
The field means listing currency; `reportedCurrency` means reporting currency; they are
different questions and both answers are right. **There are in fact THREE currency surfaces,
not two**, and the genuinely surprising one is the third — `key-metrics-ttm`, which silently
switches basis to the home listing.

**(ii) THE ADR TRADES AT A +34.1% PREMIUM TO THE KOREAN ORDINARY.** The two caps imply
USDKRW **1,027.79**; the measured rate is **1,378.24** (FMP `USDKRW` close, 2026-08-28).
That is a real price fact about the ADR, not a data defect — but it means an SKHY market cap
is **basis-dependent by a third**, and any anchor must say which listing it is measuring.

---

## 5. WHAT THIS ORDER EXECUTES

One bounded order, steps (a)–(e), **STOP after (e)**.

1. **`core/model_applicability.py`** — the class, defined by reuse of `select_lens` as in §3.
2. **`core/reporting_currency.py`** — the USD-only gate and the typed reason
   `currency:non_usd_native`.
3. **`build_fcf_series` / `own_history_fcf_yields` / `compute_panel`** — thread an optional
   applicability so the FCF engine REFUSES for a class member with a typed reason. Optional
   and defaulting to None, so every existing caller keeps exactly its present behaviour.
4. **`tools/ingest_fmp_usd_series.py`** — dry-run-by-default writer, `--commit` opt-in,
   `--db-path` resolving as `db_path or _DEFAULT_DB`, expected delta stated before the write
   and reconciled after. Writes `fundamental_series` and **no other table**.
5. **Pins**, including a positive control on each gate.

### ★ THE BLOCK-ROW SHAPE IS CONSTRAINED BY MEASUREMENT, NOT BY TASTE

`evaluate._fy_series_from_db` selects `WHERE ticker=? AND metric=? AND period_type='FY' AND
superseded=0` — **it does NOT filter `excluded`.** Verified empirically against a scratch db:
an `excluded=1` row IS returned, and a NULL-valued row IS returned as `(period_end, None)`.

Two consequences, both of which rule out the obvious designs:

- **Block rows may NOT be written as `metric='fcf'`, `period_type='FY'`.** They would flip
  `fcf_fy` from `None` (UNKNOWN — "we hold no series") to a populated list, and the
  classifier's absent-leg reason would change from `no_fcf_series` to `only_0_fy_fcf_points`
  — a statement that the ISSUER has no FY FCF points, when in fact WE blocked them. That is
  the L-4d typed-reason mislabel reappearing in a new costume.
- **`_fy_series_from_db` may NOT simply be filtered to `excluded=0` to fix that.** Measured:
  **30 FY `fcf` rows across 8 tickers (BE, BK, C, IONQ, LITE, MU, QBTS, RKLB) carry
  `excluded=1`**, because `EXCL_NEGATIVE_FCF` marks every negative-FCF point excluded — and
  those negative points ARE the R2 all-negative-last-3 signal. Filtering them out would
  silently delete the signal on four names. **REJECTED.**

So block rows get a **distinct `metric` and a distinct `period_type` (`BLOCK`)**, which no
existing consumer queries. Coexistence by construction; nothing downstream can pick them up
by accident.

---

## 6. OPEN — NOT DECIDED HERE, VIC RULES

1. **Should the financials class reach the LIFECYCLE CLASSIFIER?** If it does, C leaves the
   R2 all-negative-last-3 set (§3). If it does not, a bank's balance-sheet-driven negative
   FCF keeps counting as pre-earnings evidence. Not changed here: it is a scoring-path
   change, and CLAUDE.md requires a ruling before one.
2. **Free-float vs full-cap for the SKHY anchor**, and **which listing** (§4.2, §4.4(ii)) —
   the two differ by 25.6% and 34.1% respectively. **No anchor write this session**, per the
   order.
3. **The FMP-basis numeric series builder** (§2) — not built, deliberately, with the reason
   on the record.
4. **`key-metrics-ttm.marketCap` basis switching** (§4.4(i)) — latent 1,000x trap on a
   score-bearing field. Measured, not fixed.
5. Unchanged and still open from the doctrine order: **the pre-flight / EDGAR-score-bearing
   contradiction**. Explicitly out of this order's scope, per Vic.
