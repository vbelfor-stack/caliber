# REPORT — SKHY USD-only expansion + financials classification

**Order:** `docs/orders/2026-08-28-skhy-usd-only-and-financials-class.md` (committed `9cd0e74`,
before any execution). **Closed 2026-08-28.** Steps (a)–(e) all executed. **STOP after (e)**
observed: no anchor write, no pre-flight rescope.

| | |
|---|---|
| HEAD at open | `390d20a` — matched the chat pointer |
| suite | **984 → 1011** (+27). No pre-existing test broke. **3 pins SUPERSEDED deliberately** (§7). **9 of 43 verified to FAIL against a disarmed gate before landing** |
| caliber.db md5 | **`eec96270720d80d632aa3a6f9528ea49` → `70be97300a3d53618532e9b7eb0c4cac`** |
| production writes | **ONE WRITE POINT: +133 rows in `fundamental_series`.** Expected delta stated before the write, dry-run against the destination first, reconciled exactly: expected +133, actual +133, restatements 0, superseded 0 — **MATCH**. Every other table re-counted after: **all +0** |
| backup | `caliber.db.pre-20260828-eec96270.bak`, md5 verified equal to the pre-write db |
| step-4 evaluable | **20 of 28 — UNCHANGED** (§6) |
| own PID | 209, verified empirically by PPID walk. No peers, no orphans |

---

## 1. STEP (a) — SKHY's USD/KRW split. **THE USD SET IS EMPTY.**

Six FMP statement endpoints, through the adapter's own `_get`, measured twice on independent
fetches with identical results:

| endpoint | rows | currencies |
|---|---|---|
| `income-statement` annual / quarter | 19 / 24 | KRW / KRW |
| `balance-sheet-statement` annual / quarter | 19 / 24 | KRW / KRW |
| `cash-flow-statement` annual / quarter | 19 / 24 | KRW / KRW |
| **TOTAL** | **129** | **`{KRW: 129}`** |

**0 of 129 periods are natively USD.** There is no split to report — it is a partition with
one side. Corroborating on magnitude, not inference: FY2025 `operatingCashFlow` reads
53,373,126,000,000, order 10¹³, impossible as USD.

## 2. STEP (b) — the ingest. **ZERO numeric rows; 129 typed block rows.**

Under ruling 2 the ingest set is empty, so (b) reduces to blocks. This is the ruling working,
not a shortfall — the ingest and the block are one measurement seen from two sides.

One block row per **(statement, period)**: `metric='ingest_block:{income|balance_sheet|
cash_flow}'`, `period_type='BLOCK_FY'|'BLOCK_Q'`, `value=NULL`, `excluded=1`,
`exclusion_reason='currency:non_usd_native'`, with the endpoint, fiscal year, period, filing
date and reported currency in `components_json` — **the evidence, not just the code**.

**The typed reason is NOT `currency:unconverted`, which is what the superseded §8.1(7)
named.** "Unconverted" asserts that conversion is the pending remedy; ruling 2 removed the
remedy, so the constant would be making a claim the ruling has already falsified. That is
precisely the `WITHHELD_NO_CAPEX`/`WITHHELD_NO_OCF` defect L-4d **deleted rather than
renamed**. `currency:non_usd_native` states only what was measured.

### ★ THE BLOCK-ROW SHAPE WAS CONSTRAINED BY MEASUREMENT, AND BOTH OBVIOUS DESIGNS WERE RULED OUT

`evaluate._fy_series_from_db` selects on `ticker/metric/period_type='FY'/superseded` and
**does not filter `excluded`** — verified empirically against a scratch db, where an
`excluded=1` row came back and a NULL-valued row came back as `(period_end, None)`.

- **Blocks as `metric='fcf'`/`period_type='FY'` — REJECTED.** They would flip the
  classifier's `fcf_fy` from `None` (UNKNOWN — "we hold no series") to a populated list,
  changing its absent-leg reason from `no_fcf_series` to `only_0_fy_fcf_points` — a claim
  that the *issuer* has no FY FCF points when in fact *we* blocked them. The L-4d
  typed-reason mislabel in a new costume.
- **Filtering the reader on `excluded=0` to fix that — REJECTED, AND IT IS THE WORSE OF THE
  TWO.** Measured: **30 FY `fcf` rows across 8 tickers (BE, BK, C, IONQ, LITE, MU, QBTS,
  RKLB) carry `excluded=1`**, because `EXCL_NEGATIVE_FCF` marks every negative point — and
  those negative points **ARE** the R2 all-negative-last-3 signal. The filter would silently
  delete it on four names.

So blocks use a metric and a `period_type` no existing consumer queries. Pinned two ways: a
structural pin, and a **positive control** that reads a real FY series back untouched with
blocks beside it *and* demonstrates the counterfactual naive row DOES move the reading — a
pin asserting only the safe half could pass while the blocks were silently absent. A third
pin **fails if a future session adds the `excluded=0` filter** thinking it is tidying up.

## 3. STEP (c) — the financials class. **CAUGHT: BK, C, JPM, USB.**

Swept over all 28 with no pre-filtering, re-fetched live twice.

| ticker | FMP sector | FMP industry |
|---|---|---|
| BK | Financial Services | Investment - Banking & Investment Services |
| C | Financial Services | Banks - Diversified |
| JPM | Financial Services | Banks - Diversified |
| USB | Financial Services | Banks - Diversified |

**NOT caught: V and WU** — also sector Financial Services, but industry "Financial - Credit
Services": asset-light payment networks, compounder lens, both **currently covered** in
`fundamental_series`. **A sector-level rule would have swept them in** and destroyed working
coverage on two names to enforce a class neither belongs to. Vic's wording is
"banks/insurers/diversified financials", not "the Financial Services sector".

**No new taxonomy.** The class delegates to `core.lens_select.select_lens`, which already
encodes banks/insurers/REITs and already checks the compounder industries FIRST — that
ordering is exactly what keeps V and WU out, and it has been pinned since Phase 0. Two
arguments are pinned OFF: **`sic=None`** (Vic said FMP sector/industry; EDGAR is the arbiter,
already score-bearing through four unruled paths, and will not become a fifth) and
**`ticker=None`** (a class, not a per-ticker call — the signature makes it unpassable).
`fcf_model_applicability` takes exactly two arguments and there is no third to smuggle.

**Enforcement points, named rather than believed:** `build_fcf_series` refuses **first, ahead
of every data check**, and `own_history_fcf_yields` threads it to the panel. The ordering is
the ruling: `capex:no_tag` is accurate and leads nowhere — it describes a coverage gap, and a
coverage gap invites the next session to go and find the missing tag. **JPM and USB sat under
exactly that label across four orders.**

**Measured score movement today: ZERO, and structurally so.** Every caught name scores on the
BANK lens; `bank` is not in `ARMED_PANEL_LENSES` and `_valuation_bank(yf, fred)` does not take
`panel` as a parameter at all. A bank's panel is computed and logged but never scored. Pinned
by a test that **fails loudly if the bank lens is ever panel-armed**, which is exactly when
the zero-movement claim stops being true.

**BK is the name that makes the class pins able to fire.** Unlike JPM and USB it *does* file
capex and *does* build a usable series, so if the gate ever stopped running JPM and USB would
merely swap one refusal reason for another — invisible — while BK would silently regain a
full FCF family.

---

## 4. ★★ THE FINDING OF THIS ORDER — **CITIGROUP CLASSIFIES AS *YOUNG* TODAY, LIVE**

Not hypothetical, not a projection. Measured on the production database, 2026-08-28:

```
C   live stage: YOUNG   rule_fired: rule2_young   flags: ['YOUNG-UNCALIBRATED']
    fcf_negative_2of3 = True — "3 of last 3 FY FCF negative (2023, 2024, 2025)"
    FY FCF: 2023 −$80.0B · 2024 −$26.2B · 2025 −$74.2B
```

**Why it is latent rather than visible.** C's stored `lifecycle_stage` rows are dated
**2026-08-17** and read `MATURE (rule4_mature)` with `absent_legs:
fcf_negative_2of3(no_fcf_series)`. C's `fundamental_series` rows were first observed
**2026-08-21** (L-4c). **The stored stage predates the series that now flips it.** C simply
has not been re-evaluated since. The condition has been armed for seven days.

**Why it is not annotation-only.** Stage drives the B-2 anchor-divergence band via
`tolerance_for()`:

| | stage | band |
|---|---|---|
| C's stored row today | MATURE | **15%** |
| C's live computed stage | YOUNG | **30%** |

`rule2_young` fired on a **MEASURED** negative-FCF leg, not on absence, so C is **not** denied
the wider band the way DPC and INFQ are (`INSUFFICIENT-HISTORY`). **The next evaluation
persists YOUNG; the one after that scores a ~$200B bank on a doubled divergence tolerance** —
on the strength of an FCF signal the financials class exists to say is meaningless for banks.
It is also exactly the direction the `B2-WIDENING-SUPPRESSED-TRIP` tripwire was armed to
watch.

**THIS ORDER DOES NOT FIX IT, AND THAT IS DELIBERATE.** The class gate binds
`build_fcf_series`; the lifecycle classifier reads the **stored** series, not the builder.
Reaching it means changing what the classifier reads, which is a scoring-path change and
CLAUDE.md requires a ruling first. **Ruled or not, it is now measured — see §8 item 1.**

---

## 5. STEP (d) — anchor re-measure, READ-ONLY. **NO ANCHOR WRITE.**

### The endpoint to quote

**`market-capitalization?symbol=SKHY` → field `marketCap` → `1,141,659,621,195` USD, date
`2026-08-28`.** It is the only one of the four cap-publishing endpoints carrying its own
`date`, which is what an anchor needs. It reconciles exactly:
`7,098,548,910 ADR shares × $160.83 = 1,141,659,621,195` — **0.000%**. The figure moves
intraday (a re-fetch minutes later read `1,143,150,316,466` at $161.04), so any stored anchor
must carry its price and timestamp.

### Reconciling Vic's ~$909.30B

| candidate | value | vs $909.30B |
|---|---|---|
| **free-float USD cap** (`floatShares 5,662,818,000 × ADR price`) | **$910.75B** | **+0.16%** |
| KRW cap ÷ today's USDKRW (1,378.24) | $851.37B | −6.37% |
| full ADR USD cap | $1,141.66B | +25.55% |

**Vic's ~$909.30B is the FREE-FLOAT market cap** (free float 79.7743%), matching to +0.16% —
a single price tick. The other two miss by 6.4% and 25.6%. **The gap is free-float vs
full-cap: a basis difference, not an error on either side.**

### ★ What the prior $37.4–37.8B band actually measured — the reconciliation asked for

**It measured FY2025 OPERATING CASH FLOW converted to USD. It was never a market cap.** It is
the doctrine order §8.3 verification anchor: KRW 53,373,126,000,000 ÷ a 2025-average USDKRW,
across six averaging conventions. A **one-year flow off the cash-flow statement** against a
**price-level stock**.

**So the "~24x gap" is not a discrepancy — it is a multiple, and it is Vic's own two numbers
divided:** $909.30B ÷ $37.61B = **24.18x**. A price-to-operating-cash-flow ratio. Nothing is
inverted, mis-united or mis-plumbed; the two figures were never the same measurement.

**This also retires the last live piece of the §8.3 item.** The band did not "fail by 1.0%"
against anything that still matters — ruling 2 removed the conversion it was verifying, so it
has no subject. The five ordered conversion pins are moot for the same reason and are
recorded as superseded rather than written.

### ★ TWO FINDINGS THAT FELL OUT OF (d) — measured, NOT fixed, both out of scope

**(i) `key-metrics-ttm.marketCap` IS SERVED IN KRW FOR SKHY, ON A SCORE-BEARING FIELD.**
`adapters/fmp_adapter.py:457` sets `market_cap` from `key_metrics_ttm` (`:587`), and
`core/pillars.py:237-238` computes `fcf / market_cap * 100` for the FCF-yield bonus. SKHY's
value is `1,173,390,134,823,000` — **byte-identical to `000660.KS`'s profile marketCap, delta
exactly 0**, i.e. the Korean ordinary listing's KRW cap. Controls: **NVDA and ARM both read
`key-metrics ÷ profile = 1.0000`**, so SKHY is the sole anomaly and the divergence is ~1,028x.

Today it is *accidentally self-consistent* — `free_cashflow` also comes from the (KRW)
cash-flow statement, so the ratio is KRW/KRW. **A latent 1,000x trap, not a live defect.**

**This settles the CLAUDE.md "two endpoints disagree" item, and the previous ruling on it was
too harsh.** `profile.currency = USD` is **not "WRONG for this issuer"** — it is the **QUOTE**
currency of a NASDAQ ADR, and it is correct. The control proves it: `000660.KS` reads
`profile.currency = KRW` on exchange KSC. Both fields are right; they answer different
questions. **There are THREE currency surfaces, not two**, and the surprising one is the
third — `key-metrics-ttm`, which silently switches basis to the home listing.

**(ii) THE ADR TRADES AT A +34.1% PREMIUM TO THE KOREAN ORDINARY.** The two caps imply USDKRW
**1,027.79**; the measured rate is **1,378.24**. A real price fact, not a data defect — but
it means an SKHY market cap is **basis-dependent by a third**, and any anchor must say which
listing it measures.

---

## 6. STEP (e) — DARK re-run. **SKHY lands exactly where it did. Nothing moved.**

Run as a **BEFORE/AFTER**, not a single reading: the classifier was run twice against two
databases differing *only* by this order's rows — production read-only, and a copy with the
133 rows written in. A single reading could not tell a no-op from a coincidence. Compared at
**leg level**, not stage level, because two different leg readings can land on the same stage.

| ticker | lens | class | stage BEFORE | stage AFTER | identical |
|---|---|---|---|---|---|
| **SKHY** | cyclical | APPLICABLE | HIGROWTH (rule3) | HIGROWTH (rule3) | **YES** |
| BK | bank | INAPPLICABLE | MATURE (rule4) | MATURE (rule4) | YES |
| C | bank | INAPPLICABLE | **YOUNG (rule2)** | **YOUNG (rule2)** | YES |
| JPM | bank | INAPPLICABLE | MATURE (rule4) | MATURE (rule4) | YES |
| USB | bank | INAPPLICABLE | MATURE (rule4) | MATURE (rule4) | YES |

**NAMES WHOSE CLASSIFIER READING MOVED: NONE.**

**How SKHY lands.** Lens `cyclical` (SIC 3674), stage **HIGROWTH / rule3_higrowth**, FCF
family fully withheld with an accurate typed reason —
`operating_cashflow:no_tag; capex:no_tag`, evidence naming all five concepts checked. Panel
FCF anchor: 0 points. Three legs asserted-absent (`fcf_negative_2of3`,
`cyclical_has_earned`, `reinvestment_heavy`). **SKHY is not made evaluable by this order and
was never going to be** — ruling 2 blocks every period it has.

### ★ `SELECT DISTINCT ticker` AND STEP-4 EVALUABILITY HAVE NOW DEFINITIVELY DIVERGED

`fundamental_series` holds **23 distinct tickers** (was 20). **Step-4 evaluable is
20 of 28 — UNCHANGED**, measured through the production reader `evaluate._fy_series_from_db`.
SKHY, JPM and USB hold **only block/flag rows and no numeric point**. CLAUDE.md already warned
these two numbers were no longer guaranteed equal; this order is where they actually parted.
**Count evaluability through the reader, never by `SELECT DISTINCT ticker`.**

**The R2 all-negative-last-3 set is `C, IONQ, QBTS, RKLB` — unchanged by this order**, and C's
membership is the subject of §4.

---

## 7. THREE PINS SUPERSEDED — deliberately, with the rationale carried verbatim

Same discipline as L-4d.1: renamed or narrowed, never silently deleted, original reasoning
retained.

- **`test_the_compounder_metric_now_has_an_own_history_anchor[BK]`** — BK removed from the
  parametrize list. It was there from the H-3 arming and the assertion was **TRUE ON
  MEASUREMENT** when written; the class ruling post-dates it.
- **`test_an_issuer_with_no_capex_concept_gets_NO_anchor_and_says_why[JPM]`, `[USB]`** —
  narrowed to `[V]`. The original rationale is retained verbatim and **is still true**: JPM
  and USB file no PP&E-purchase concept of any kind. What changed is which cause gets
  *reported*.

Successor: **`test_the_financials_class_WITHHOLDS_the_own_history_FCF_anchor[BK|JPM|USB]`**,
plus an opt-in positive control proving the gate is OFF by default and live when asked.

**Two of my own new pins were written wrong and were rewritten over the AST.** They scanned
module TEXT for `"bank"` and `"convert"` and fired on the prose explaining why those things
are forbidden — both modules are heavily commented precisely because their rulings are subtle.
This is the recorded L-4b lesson repeating: *a pin that prose can break is one a later session
weakens instead of heeding.* They now parse the AST and inspect non-docstring string constants
and call names.

**9 of 43 pins verified to FAIL before landing**, against a deliberately disarmed gate — the
class check short-circuited, the panel threading removed, and the `excluded=0` "tidying up"
regression introduced. The warning pin caught that third one, which is the whole reason it
exists.

---

## 8. OPEN — NOT DECIDED HERE. VIC RULES.

1. **★★ SHOULD THE FINANCIALS CLASS REACH THE LIFECYCLE CLASSIFIER? — now urgent, §4.** C
   reads **YOUNG live today** and the class as scoped does **not** stop it; the next
   evaluation persists YOUNG and doubles C's B-2 band from 15% to 30%. Either the classifier
   learns the class, or a bank's balance-sheet-driven negative FCF keeps counting as
   pre-earnings evidence. **This is a scoring-path change and needs a ruling.**
2. **The SKHY anchor basis** — free-float ($909.30B) vs full ADR cap ($1,141.66B) vs the
   Korean ordinary ($851.37B). They differ by 25.6% and 34.1%. **No anchor write this
   session**, per the order.
3. **The FMP-basis NUMERIC series builder** — not built, deliberately. With 0 USD periods
   universe-wide it would be a production write path nothing exercises, and it must clear the
   capex-sign trap and an R2 re-measurement blind. The ingest tool **REFUSES LOUDLY** if a USD
   period ever appears. A separate order.
4. **`key-metrics-ttm.marketCap` basis switching** (§5(i)) — latent ~1,028x trap on a
   score-bearing field. Measured, not fixed.
5. **The stale-`lifecycle_stage` question the C finding exposes, generally.** C is not
   special: any name whose `fundamental_series` arrived after its last evaluation carries a
   stage row computed without it. Nothing re-computes stages when the series changes. C is
   the one where it flips a rule — **that was found, not designed for.**
6. Unchanged and still open: **the pre-flight / EDGAR-score-bearing contradiction**, and
   **step 4** itself. Explicitly out of this order's scope.
