# STEP 2 — FULL-UNIVERSE RUN (28 names, live, annotate-and-persist)

**Order:** step 2 of the §5 arming sequence, ruled 2026-08-17 · **Suite:** 789 · **Run:** 28/28, all exit 0
**§5 steps 3–4 NOT armed.** No B-2 tolerance change, no supply block, no scoring consultation of stages.
`pillars`, `valuation_anchors`, `batch/runner`, `synthesis/schema` remain pinned dark.

**PRE-FLIGHT (standing live-EDGAR discipline, adapter's own path, immediately before the run):**
FMP profile resolved for **all 28**; EDGAR CIK resolved for **all 28**. No name lost to a feed.

**Production md5:** `1e301195d756ab444641274ac732d682` → **`e7be34a9315bbd03e4711dcce6c57576`**
(both WAL-checkpointed before hashing).

| table | before | after | expected? |
|---|---|---|---|
| `lifecycle_stage` | 9 | **37** (+28) | YES — the target |
| `lifecycle_transitions` | 0 | 0 | YES — every name's first classification |
| `evaluations` | 45 | **73** (+28) | YES — a live run persists a real evaluation |
| `field_provenance` | 714 | **1294** (+580) | YES — standing companion |
| `synthesis_cache` | 16 | 16 | unchanged — `evaluate.py` never writes the cache |
| `sqlite_sequence` | 4 | 4 | no new AUTOINCREMENT table |

Membership split now recorded on every row: **44 held / 29 calibration, 0 NULL.**

---

## (a) FULL STAGE TABLE

| ticker | held | lens | stage | rule | flags |
|---|---|---|---|---|---|
| ARM | held | cyclical | HIGROWTH | rule3 | GUARD-BLIND, INPUTS-INCOMPLETE |
| BE | held | cyclical | HIGROWTH | rule3 | INPUTS-INCOMPLETE |
| CAT | held | **standard** | MATURE | rule4 | INPUTS-INCOMPLETE |
| CBRS | held | cyclical | HIGROWTH | rule3 | GUARD-BLIND, **HELD-OUT-OF-YOUNG**, UNEVALUABLE-FCF, INPUTS-INCOMPLETE |
| DPC | held | cyclical | **YOUNG** | rule2 insufficient-history | INSUFFICIENT-HISTORY, YOUNG-UNCALIBRATED |
| FN | held | cyclical | MATURE | rule4 | INPUTS-INCOMPLETE |
| GOOGL | held | compounder | MATURE | rule4 | INPUTS-INCOMPLETE |
| INFQ | held | cyclical | **YOUNG** | rule2 insufficient-history | INSUFFICIENT-HISTORY, YOUNG-UNCALIBRATED |
| IONQ | held | cyclical | HIGROWTH | rule3 | GUARD-BLIND, **HELD-OUT-OF-YOUNG**, UNEVALUABLE-FCF, INPUTS-INCOMPLETE |
| LITE | held | cyclical | HIGROWTH | rule3 | INPUTS-INCOMPLETE |
| LLY | held | **cyclical** | MATURE | rule4 | INPUTS-INCOMPLETE |
| LRCX | held | cyclical | MATURE | rule4 | GUARD-TOLERANCE-UNCALIBRATED, INPUTS-INCOMPLETE |
| MU | held | cyclical | MATURE | rule4 | GUARD-TOLERANCE-UNCALIBRATED, REINVEST-UNCALIBRATED |
| NVDA | held | cyclical | MATURE | rule4 | INPUTS-INCOMPLETE |
| QBTS | held | cyclical | HIGROWTH | rule3 | GUARD-BLIND, **HELD-OUT-OF-YOUNG**, UNEVALUABLE-FCF, INPUTS-INCOMPLETE |
| RKLB | held | **standard** | **YOUNG** | rule2 | YOUNG-UNCALIBRATED |
| SKHY | held | cyclical | HIGROWTH | rule3 | GUARD-TOLERANCE-UNCALIBRATED, INPUTS-INCOMPLETE |
| SPCX | held | **standard** | **YOUNG** | rule2 | YOUNG-UNCALIBRATED |
| STX | held | cyclical | MATURE | rule4 | GUARD-TOLERANCE-UNCALIBRATED, INPUTS-INCOMPLETE |
| V | held | compounder | MATURE | rule4 | INPUTS-INCOMPLETE |
| XE | held | cyclical | MATURE | rule4 | GUARD-BLIND, **HELD-OUT-OF-YOUNG**, UNEVALUABLE-FCF, INPUTS-INCOMPLETE |
| GOOG | calib | compounder | MATURE | rule4 | REINVEST-UNCALIBRATED |
| NOW | calib | growth | HIGROWTH | rule3 | INPUTS-INCOMPLETE |
| WU | calib | compounder | **DECLINE** | rule1 | — |
| JPM · BK · USB · C | calib | bank | MATURE | rule4 | INPUTS-INCOMPLETE |

**Census — stages:** MATURE 15 · HIGROWTH 8 · YOUNG 4 · DECLINE 1.
**Census — lenses:** cyclical 16 · compounder 4 · bank 4 · standard 3 · growth 1.

---

## HEADLINE 1 — TRIPWIRE 1 FIRED, AND IT FOUND A LIVE SCORING DEFECT ON A HELD NAME

The standard lens got its first production evaluations (CAT, RKLB, SPCX). Reporting the full
panel readouts as the D-3 ruling requires — and one of them is wrong.

**RKLB scores Valuation 5/5 — the maximum, "cheapest" rung — on these inputs:**

```
Rationale: Standard valuation lens. EV/EBITDA -372.6x. P/E -296.4x. FCF yield -0.8%. 10Y 4.68%.
Score: 5/5   [=][=][=][=][=]   [MED]
Other flags on the same evaluation: NEGATIVE-OPERATING-MARGIN, NEGATIVE-ROE, NEGATIVE-FCF
```

**A loss-making company is being scored as maximally cheap because its multiples are
NEGATIVE.** Mechanism, confirmed in `core/pillars.py:885`: when no panel is available the
standard lens falls back to a fixed absolute ladder whose first rung is `if ev_eb < 10:
score = 5`. **−372.6 satisfies `< 10`.** There is no negativity guard on the ladder. RKLB
took the fallback branch (no sector snapshot), so the ladder scored it directly.

This is the same defect class as the documented hard stop *"PE basis computed on negative
forward EPS"* (LCID is its test fixture) — but on **EV/EBITDA in the standard lens**, live,
on a **held** name, and it inflates the Valuation pillar to 5 which feeds avg_score → E(R).

Contrast, same run, same lens: **SPCX** has a *positive* EV/EBITDA of 445.9x and correctly
scores **1/5** with `VERY-RICH-VS-SECTOR`. **CAT** scores 3/5 through the panel path
(EBITDA yield vs risk_free −0.8pp). So the ladder is sane for positive multiples and
inverted for negative ones.

**NOT FIXED — this is scoring logic and therefore your ruling.** The natural shape mirrors
the existing negative-forward-PE stop: a negative EV/EBITDA (or negative P/E) is not a cheap
multiple, it is an *undefined* one, and the lens should refuse the rung rather than award it.

---

## HEADLINE 2 — THE SIC→LENS MAP IS INVERTED ON ITS TWO MOST IDENTIFIABLE CASES (deliverable g)

You asked me to flag anything whose SIC-selected lens looks wrong. Two are unambiguous, and
they fail in opposite directions.

**LLY (Eli Lilly) → CYCLICAL.** SIC **2834 "Pharmaceutical Preparations"** falls inside
`_CYCLICAL_SIC_RANGES` entry **(2800, 2900)**, which was written for *chemicals*. The 2833–2836
block is drugs and biologicals, and the range swallows it. A pharma major is now scored by a
lens that normalises to mid-cycle earnings and carries a peak/rollover hard gate capping
valuation at 2. **Every biotech and pharma name will inherit this.**

**CAT (Caterpillar) → STANDARD.** SIC **3531 "Construction Machinery"** falls in **no**
cyclical range: the list covers (3300,3500) metals and (3600,3700) electronics, leaving
**3500–3599 industrial machinery in the gap**. Its FMP industry string is "Agricultural -
Machinery", which matches no cyclical keyword either. **The archetypal industrial cyclical
gets the generic lens with no peak gate** — the exact failure the cyclical lens exists to
prevent.

**A third, softer one: `"hardware"` is a cyclical keyword**, so FMP's "Computer Hardware" /
"Hardware, Equipment & Parts" strings put **IONQ, INFQ and FN** on the cyclical lens.
Pre-revenue quantum-computing companies being normalised to mid-cycle earnings is not
obviously right; FN (contract optical manufacturing) plausibly is.

**Not a mispairing:** I verified every new CIK against the EDGAR entity name — SPCX really is
`SPACE EXPLORATION TECHNOLOGIES CORP` (CIK 1181412). Its odd `standard` lens comes from
**SEC's own SIC 7370 "Computer Programming Services"** for a launch company; the pairing is
right, the source classification is wrong.

**No fix applied — lens assignment is scoring logic.**

---

## (b) YOUNG NAMES — the step-4 population, 4 of 21 holdings

| ticker | lens | rule | why |
|---|---|---|---|
| **DPC** | cyclical | insufficient-history | 1 usable FY < 2 required |
| **INFQ** | cyclical | insufficient-history | 1 usable FY < 2 required |
| **RKLB** | standard | rule2 | latest FY operating margin **−38.03%** (trend +2605bp from −64.08%); FCF series absent |
| **SPCX** | standard | rule2 | latest FY operating margin **−13.86%**; margin trend absent (no FY exactly 3y back); FCF series absent |

All four carry `YOUNG-UNCALIBRATED`, so R10's tripwire is doing its job on first live contact.
DPC and INFQ reach YOUNG through the **insufficient-history** path, which returns before the
rule-2 cyclical guard is consulted — correct, since with under two fiscal years there is no
window to measure "has earned" in.

**AND THE POPULATION WOULD HAVE BEEN 8 WITHOUT THE L-1e RULING.** Four more names —
**CBRS, IONQ, QBTS, XE** — have negative margins and were **blocked** from YOUNG by the
fail-closed FCF guard (`CYCLICAL-GUARD-HELD-OUT-OF-YOUNG` + `CYCLICAL-GUARD-UNEVALUABLE-FCF-ABSENT`).
Under the pre-L-1e behaviour every one of them would read YOUNG today. **That ruling halved
the step-4 population on live data**, and it did so by withholding a tag it could not measure
rather than granting it — which is worth knowing before step 4 arms, because the four blocked
names are exactly the ones whose supply-layer profile you would most want.

## (c) DECLINE NAMES — 1

**WU** (calibration, compounder): streak **4 consecutive declining FY**; margin **−37bp**
(19.77% → 19.41%, inside the ±100bp flat band); capital returns present (dividend + net
buyback). Every leg measured, no absences. Identical to every prior run.

**No held name reads DECLINE.**

## (d) PEAK-COMPARISON LOG — every cyclical name, and the honest count is ZERO

**REAL PEAK COMPARISONS THIS RUN: 0.** No cyclical-lens name carries a decline streak, so
the guard never reached a peak-vs-peak comparison. `GUARD-TOLERANCE-UNCALIBRATED` therefore
remains uncalibrated, exactly as predicted — and per your standing ruling it stays that way
rather than being tuned on anything synthetic.

**But the calibration set is no longer empty — four names logged a real peak PAIR:**

| ticker | peaks | delta |
|---|---|---|
| LRCX | 2018 11,076,998,000 → 2023 17,426,706,000 | **+57.32%** |
| SKHY | 2018 40,445,066,000,000 → 2022 44,621,568,000,000 | **+10.33%** |
| STX | 2018 11,184,000,000 → 2022 11,661,000,000 | **+4.27%** |
| MU | 2018 30,391,000,000 → 2022 30,758,000,000 | **+1.21%** |

All four are peaks *rising* — i.e. had any of them been in a downcycle, the guard would have
**refused** the DECLINE permit. That is the first live evidence the peak-to-peak instrument
would bite.

Single-peak or no-peak (nothing to compare): BE, CBRS, QBTS, ARM, FN, LITE, LLY, NVDA.
Guard blind (under 8 FY): ARM, CBRS, DPC, INFQ, IONQ, QBTS, XE.

**THE L-1e CONTIGUITY PRECONDITION FIRED IN PRODUCTION — correcting my own earlier claim.**
I recorded it as latent and costless ("all nine names are contiguous"). On the real universe
it is **live**: **IONQ** has a series gap at **2020** and **XE** at **2023, 2024**, and for
both, peaks were `NOT COMPUTED — peak detection against a non-adjacent FY would fabricate
structure`. Two held names, not zero. The refusal is doing exactly what it was built for, and
per the ruling each is a **feed-repair ticket**, not a modelling question.

## (e) REINVESTMENT — the R6 1.50 bar, still two data points

| ticker | reading |
|---|---|
| GOOG | sales/capital **1.195** → HEAVY |
| MU | sales/capital **0.668** → HEAVY |

**Absent for the other 21 measured names** (`no_series` for all but NOW, which has
`only_1_point_series`). `fundamental_series` covers only MU/GOOG/NOW/WU — the full universe
adds **zero** new reinvestment data, because that table is built by the H-1 series builder,
which has never been run on the new names. **The R6 threshold is no better calibrated after
this run than before it**, and it stays flagged.

## (f) INPUTS-INCOMPLETE CENSUS

**FEED-TRANSIENT: NONE.** Every live lookup answered on all 28 names — no reading here should
be distrusted for feed reasons.

**STRUCTURAL** (permanent, actionable, by leg):

| absence | names |
|---|---|
| `fcf_negative_2of3(no_fcf_series)` | 24 of 28 — everything except MU, GOOG, NOW, WU |
| `reinvestment_heavy(no_series)` | 22 |
| `cyclical_has_earned(no_fcf_series…)` | 15 cyclical names |
| `cyclical_peak_to_peak(under_8_fy…)` | ARM, CBRS, DPC, INFQ, IONQ, QBTS, XE |
| `margin_trend_bp(no_fy_exactly_3y_before_latest)` | DPC, INFQ, SPCX |
| `revenue_cagr(no_fy_exactly_3y_before_latest)` | DPC, INFQ |
| `decline_streak(history_under_2_fy)` | DPC, INFQ |
| `net_buyback(insufficient_share_series)` | DPC |

**The dominant structural gap is `fundamental_series` coverage: 24 of 28 names have no FCF
history at all.** That single gap drives the FCF leg, the reinvestment leg and rule 2's
cyclical guard. Extending the H-1 series builder across the universe would close more of this
census than any other single action — noted, not scoped.

## (g) LENS CENSUS

| lens | names |
|---|---|
| cyclical (16) | ARM BE CBRS DPC FN INFQ IONQ LITE **LLY** LRCX MU NVDA QBTS SKHY STX XE |
| compounder (4) | GOOG GOOGL V WU |
| bank (4) | BK C JPM USB |
| standard (3) | **CAT** RKLB SPCX |
| growth (1) | NOW |

**16 of 28 on the cyclical lens** — the peak gate and mid-cycle normalisation now govern more
than half the universe, including a pharma major. See Headline 2.

---

## OPEN FOR RULING

1. **RKLB's Valuation 5/5 on a −372.6x EV/EBITDA** — negative multiples scored as maximally
   cheap in the standard lens's fallback ladder. Live, held name, feeds E(R).
2. **LLY → cyclical (pharma inside the chemicals SIC range)** and **CAT → standard
   (3500–3599 gap)**; softer, the `"hardware"` keyword sweeping IONQ/INFQ onto cyclical.
3. **GOOG/GOOGL are one issuer on one CIK** (0001652044) and both are now evaluated —
   two parallel `fundamental_series` for one company if the series builder is ever run on both.
4. **Step 4's YOUNG population is 4, and would be 8 but for L-1e's fail-closed guard** — the
   four blocked names (CBRS, IONQ, QBTS, XE) are the ones a supply-layer block would most
   want to see.
5. **ETF refusal guard** still unbuilt (punch list; `isEtf` is already in the payload).

**STOP.** Step 3 arms only after you review this table.
