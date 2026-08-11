# Phase H-FCF — FCF own-history anchor: SCOPING REPORT

**Measured 2026-08-11** · REPORT ONLY, NOTHING IMPLEMENTED · live FMP + EDGAR + FRED across
the golden five and the four calibration banks. `caliber.db` untouched (md5 `54aa42e5`).

> **Both falsifiable claims fail as stated.** Claim 1's *opportunity* is real and larger than
> expected — the basis mismatch collapses to **0.0%** on 5 of 6 resolvable tickers — but the
> mechanism that resolves it is **not H-FCF**, and arming it **still does not unblock
> Financial Health**. Claim 2 fails on principle: `fcf_yield`'s denominator is price, which
> EDGAR structurally cannot corroborate, so an "EDGAR fcf_yield" would share an identical
> denominator with FMP's and carry no information the `free_cashflow` row doesn't already.
> **The ceiling argument does not survive. `test_verdict_high_is_still_blocked` stays passing.**
>
> H-FCF's real value is what it was always going to be — the compounder lens gets its first
> issuer-referenced denominator, and independence-narrowing drops from 16/20 cells to 12/20.
> That is worth doing. It is not a path to verdict-high.

---

## 1. CLAIM 1 — does an EDGAR TTM FCF series move `free_cashflow` from advisory to armed?

### 1a. The basis mismatch is real, and period-matching collapses it

`free_cashflow` is `basis_note="FMP cash-flow is annual; EDGAR is TTM"` → permanent advisory.
Measured live, FMP's annual `freeCashFlow` against EDGAR `operating_cashflow − capex`,
first as resolved today (MRQ/TTM) and then **re-read at the issuer's fiscal year-end**:

| Ticker | FY end | FMP FCF ($B) | EDGAR @MRQ | div% | **EDGAR @FY** | **div%** | verdict @FY |
|---|---|---|---|---|---|---|---|
| MU | 2025-08-28 | 1.67 | 26.17 | **1469.1** | 1.67 | **0.0** | AGREE |
| GOOG | 2025-12-31 | 73.27 | 53.27 | 27.3 | 73.27 | **0.0** | AGREE |
| NOW | 2025-12-31 | 4.58 | 4.58 | 0.1 | 4.58 | **0.0** | AGREE |
| BK | 2025-12-31 | 5.18 | 1.59 | 69.2 | 5.18 | **0.0** | AGREE |
| C | 2025-12-31 | −74.15 | −74.15 | 0.0 | −74.15 | **0.0** | AGREE |
| **WU** | 2025-12-31 | 0.39 | 0.57 | 43.9 | 0.51 | **28.6** | **CONFLICT** |
| V / JPM / USB | — | — | — | — | — | — | no capex tag |

The advisory is doing real work today (MU diverges 1469% on the unmatched comparison), and
matching the period removes it entirely on 5 of 6. **WU is a genuine disagreement, not a
basis artifact** — it survives period matching at 28.6%, so arming this comparison would
**downgrade WU's `free_cashflow` to low**. Arming is not pure upside.

### 1b. But the mechanism is not H-FCF — and it already half-exists

`period_basis="annual_fy"` (ruling R-A) was built for exactly this and is already used by
`total_cash@FY` and `total_debt@FY`. It does **not** work for cash-flow fields for one
concrete reason: the matched re-read goes through `_instant_at`, which requires
`not rec.get("start")` — **instants only**. Flow facts carry a `start`, so they fall through.

Closing that gap means teaching `_gather_inputs` to re-read a FLOW input at the matched
period via TTM assembly. **That capability already exists** (`_assemble_ttm(as_of_end=…)`,
exposed as `ttm_series`, built for Phase D's own-history anchor). It is a small, self-contained
cross-check change.

**A historical FCF series is neither necessary nor sufficient for it.** H-FCF builds a series
of *past* FCF yields to serve as a scoring denominator; the cross-check operates on the
*current* value. They share one helper and nothing else.

> **Claim 1 verdict: the OPPORTUNITY SURVIVES, the ATTRIBUTION DOES NOT.** `free_cashflow`
> can be moved from advisory to armed — measured, 5 of 6 at 0.0% — but H-FCF is not what
> does it, and it should be ordered separately (see §5, H-X).

### 1c. …and even armed, it does not unblock Financial Health

Tested rather than reasoned. Financial Health's five key inputs, after the live armed
cross-check:

| Input | GOOG | MU | fixable by period matching? |
|---|---|---|---|
| `current_ratio` | **high** | **high** | already armed |
| `total_cash` | **high** | **high** | already armed (`total_cash@FY`) |
| `free_cashflow` | medium | medium | **yes** — §1a |
| `total_debt` | medium | medium | partly — `total_debt@FY` is DARK; MU agrees 0.5%, **GOOG conflicts 8.8%** |
| `debt_to_equity` | medium | medium | **NO** — FMP serves NET debt/equity, EDGAR gross |

Forcing all five to high does yield `Financial Health = high`, so the pillar is reachable in
principle. But **`debt_to_equity` is a DEFINITIONAL mismatch, not a period one** — no amount
of matching fixes net-vs-gross — and it is a key input of the same pillar. So Financial Health
stays blocked whatever happens to `free_cashflow`.

---

## 2. CLAIM 2 — does it give Valuation's `fcf_yield` a corroborant?

**No, and the reason is structural rather than empirical.**

`fcf_yield` is `freeCashFlowYieldTTM` = FCF_TTM / market cap, and market cap = **price ×
shares**. Price is FMP-only and is precisely the class of input the E-4 finding identified as
structurally uncorroborable by EDGAR.

Two supporting measurements:

**(i) FMP publishes no plain TTM FCF.** `key-metrics-ttm` offers `freeCashFlowYieldTTM`,
`evToFreeCashFlowTTM`, `freeCashFlowToFirmTTM` and `freeCashFlowToEquityTTM` — the first two
are price-denominated ratios and the last two are different measures (FCFF/FCFE). The TTM FCF
level is only reachable by multiplying a ratio back out by market cap, i.e. **by injecting the
price term into the reconstruction**.

**(ii) The reconstruction matches EDGAR to the dollar:**

| Ticker | EDGAR TTM FCF | FMP implied TTM (fcf_yield × mktcap) | div |
|---|---|---|---|
| MU | 26,172,000,000 | 26,172,000,000 | **0.000%** |
| GOOG | 53,273,000,000 | 53,273,000,000 | **0.000%** |
| NOW | 4,580,000,000 | 4,580,000,000 | **0.000%** |
| BK | 1,592,000,000 | 1,592,000,000 | **0.000%** |
| WU | 565,400,000 | 402,600,000 | 40.4% |

Exact-to-the-dollar agreement across four unrelated issuers is not two independent sources
concurring — it is strong evidence that **FMP's cash-flow fundamentals are themselves derived
from the same SEC XBRL filings**. That does not invalidate the EDGAR cross-check (WU shows it
still catches real discrepancies, and the whole E-3 armed set rests on the same footing), but
it should be stated plainly: for filed fundamentals this is a **transcription check**, not an
independent measurement. Worth recording because "high confidence" is being asked to mean
something specific here.

**The laundering argument.** An EDGAR-derived `fcf_yield` would be
`EDGAR_FCF / (FMP price × shares)`. Comparing it to `FMP_FCF / (FMP price × shares)` compares
two numerators over an **identical** denominator — it carries exactly the information of the
`free_cashflow` row and adds none. Stamping the resulting agreement onto `fcf_yield` would let
the uncorroborated price term inherit corroboration it never received. That is the precise
failure mode the anti-launder note exists to catch, and the reason the peer anchor was
rejected: manufactured corroboration is worse than none.

Valuation's other two blockers (`ev_to_ebitda`, `revenue_growth`) are untouched by H-FCF
either way.

> **Claim 2 verdict: FAILS.**

---

## 3. Consequence for the ceiling

Verdict confidence is min-across-five-pillars, and the pinned blocker set is
`{Financial Health, Management & Capital Allocation, Growth / Forward, Valuation}`.

- **Financial Health** — stays blocked by `debt_to_equity` (net-vs-gross), §1c.
- **Valuation** — stays blocked; `fcf_yield` is not corroborable, §2.
- **Management** — `earnings_history`, `insider_transactions`, hardcoded medium. Untouched.
- **Growth** — price/estimate-derived. Untouched.

**H-FCF closes blockers in ZERO of the four pillars, not two.**
`test_verdict_high_is_still_blocked` (ruling R-D, deliberately pinned) **stays passing** and
must not be touched. The medium ceiling is unmoved.

Recorded so the sequencing question stays answerable: the shortest remaining path to
verdict-high is not this one. It runs through `debt_to_equity` (needs a gross-D/E source or an
FMP field change), the Management pillar's hardcoded medium, and a second source for
price/estimate-derived fields — none of which EDGAR provides.

---

## 4. What H-FCF is actually worth (the case that survives)

### 4a. Coverage — own-history readings, per ticker per metric

The production universe **is** the golden five (`tickers.txt`), so this audit is complete
rather than a sample. 5 tickers × 4 metrics = 20 own-history cells.

| Metric | MU | GOOG | V | NOW | WU | before → after |
|---|---|---|---|---|---|---|
| trailing earnings | ✓ | ✓ | ✗ | ✓ | ✓ | 4 → 4 (unchanged, Phase G) |
| **FCF** | **✓ 14q** | **✓ 20q** | **✗ no capex tag** | **✓ 20q** | **✓ 20q** | **0 → 4** |
| forward earnings | ✗ | ✗ | ✗ | ✗ | ✗ | 0 → 0 (structural) |
| EBITDA | ✗ | ✗ | ✗ | ✗ | ✗ | 0 → 0 (deferred leg) |
| | | | | | | **4/20 → 8/20** |

**Independence-narrowing — the more important number.** D-3 ruling 6 recorded that 17 of 20
readings were independence-narrowed (two market-referenced anchors, no independent third).
Post-G it is 16/20. H-FCF takes the four FCF cells to three anchors:
**independence-narrowed 16/20 → 12/20.**

Banks (tracked, not in the universe): BK gains 17 quarters but the bank lens has no panel, so
it is inert; JPM and USB file no capex tag; C has only 5 positive-FCF quarters of 21 → withheld.

**CORRECTION to `docs/g-build.md` §6, which I wrote:** I stated the ceiling as 16/20 and that
"GOOG, V and WU" gain the anchor. Both need fixing. 16/20 counts forward-earnings cells that
**no lens consumes**, so the *useful* ceiling is **12/20** (trailing + FCF + EBITDA × the four
tickers with a share series). And **V gains nothing** — it files no capex tag, an accepted data
limit already recorded for its cross-check that I carried incorrectly into the lens claim. The
compounder beneficiaries are **GOOG and WU**, not three tickers.

### 4b. Blast-radius audit — load-bearing, per the standing rule

Own-history feeds `METRIC_FCF_YIELD` → the **compounder** lens only. Cyclical is on trailing
earnings, standard and growth on EBITDA, bank has no panel. Compounder is GOOG, V and WU —
**three of the five-ticker universe**, so unlike Phase G this genuinely can move scores.

Measured live, MIN re-aggregated with the FCF own-history anchor added:

| Ticker | lens | own-hist median | live FCF yield | oh spread | rf spread | sector spread | binding now → H | score |
|---|---|---|---|---|---|---|---|---|
| GOOG | compounder | 3.69% | 1.28% | −2.41 | **−3.44** | −2.90 | risk_free → risk_free | **1 → 1** |
| V | compounder | — (withheld) | 3.10% | — | −1.62 | **−2.54** | sector → sector | **2 → 2** |
| WU | compounder | 14.01% | 18.31% | **+4.30** | +13.59 | +12.67 | **sector → own_history** | **5 → 5** |

**COMPOUNDER SCORES MOVED: 0.** But the finding is not "nothing happens":

**WU's binding anchor changes.** Its compounder verdict stops resting on a market-referenced
denominator (+12.67pp vs sector) and starts resting on its own history (+4.30pp) — **8.37pp
stripped off the read**, and the panel stops being independence-narrowed. That is the same
shape as the D-0 headline, where own-history stripped 11.6pp off WU's trailing-earnings
screening buy. The score survives at 5 only because +4.30 still clears the top rung's +3.0.
A ticker sitting nearer a rung boundary would move.

### 4c. RISK REQUIRING A RULING — negative-FCF exclusion and survivorship

A negative FCF has no yield interpretation, so those quarters must be excluded exactly as
loss-making quarters are for the earnings yield. The magnitude is materially larger here:

| Ticker | overlapping quarters | positive FCF | usable | excluded |
|---|---|---|---|---|
| MU | 24 | 16 | **14** | **10 (42%)** |
| C | 21 | 7 | 5 → **withheld** | 14 (67%) |
| GOOG / NOW / WU | 24 | 24 | 20 | 0 |
| BK | 24 | 20 | 17 | 4 |

MU's "own FCF-yield history" is therefore *the median of the quarters in which FCF was
positive* — not its typical FCF yield. For a capex-heavy cyclical those are different
statements. **The bias direction is safe** (dropping weak quarters raises the median, making
the stock look richer, and MIN takes the least flattering anchor), but it is large enough that
it should be ruled rather than defaulted. Options: exclude and flag the count (the trailing-
earnings precedent); withhold the anchor above an exclusion threshold; or require positive
TTM FCF in a majority of quarters. **Vic rules at H-2.**

---

## 5. Phased plan — blast radius per phase, dark before arm

| Phase | Content | **Blast radius** | Gate |
|---|---|---|---|
| **H-1** | FCF own-history series builder on the G-4 restated share basis; logged beside the live panel, applied to nothing. | **NONE** — computed and logged only. | Per-quarter series for all five + banks; negative-exclusion counts reported. |
| **H-2** | Negative-FCF exclusion ruling (§4c) + coverage confirmation. | **NONE** — no code. | Vic rules the exclusion policy. |
| **H-3** | **ARM** the FCF own-history anchor on the compounder lens. | **REAL: 3 of the 5-ticker universe** (GOOG, V, WU). Expected zero score movement, but WU's binding anchor changes and its spread narrows 8.37pp. First H phase that can move a score → E(R) → grade. | Reviewed **per-quarter** diff (standing ruling) + armed panel diff across universe and banks. Any score movement is a finding, not a pass. |
| **H-4** | EBITDA leg. | — | **DEFERRED behind EDGAR expansion** (no D&A spec; EV build-out; EBITDA tagging varies far more than cash-flow tagging). Not part of this order. |

**Recommended as a SEPARATE order, not part of H:**

| **H-X** | Extend `period_basis="annual_fy"` to FLOW inputs (TTM at the matched period) and arm `free_cashflow`. | **Confidence labels only** — no score, E(R) or grade. But it can **DOWNGRADE**: WU conflicts at 28.6% post-match. | Matched-period divergence table for all nine; explicit ruling on WU's conflict. |

H-X is the piece of the original ceiling hypothesis that survived, and it is genuinely
worth doing on its own merits — it removes a permanent advisory that is currently masking a
1469% MU divergence and a real 28.6% WU disagreement. It just does not lead where the
hypothesis said it would, and it is a cross-check change rather than an anchor change, so
bundling it into H would mix two blast radii (confidence-only vs score-moving) in one arm.

---

## 6. What this report did NOT do

No code changed, no fixtures re-recorded, no database written — `caliber.db` md5 unchanged at
`54aa42e5`. Nothing armed. Live read-only probes only (FMP, EDGAR, FRED); both probe scripts
were removed after measurement.
