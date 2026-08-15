# ORDER — RE-RUN THE ARMED PASS FOR IDS 216-220

**Issued:** 2026-08-15 by Vic (architect/gatekeeper)
**Recorded by:** Code, BEFORE execution, per the order's own first term.
**Status at recording:** NOT YET EXECUTED. Tree at 590997d, clean, suite 670,
caliber.db md5 54aa42e5, max evaluation id 220.

---

## 1. The order, VERBATIM

> Restated order — RE-RUN THE ARMED PASS FOR IDS 216-220. Record this
> order verbatim in docs/orders/2026-08-15-rerun-armed-pass.md BEFORE
> executing, so the terms survive any session death. Then execute.
>
> RULING ON GAP 1 (supersede mechanism): add it to the evaluations
> schema. Two nullable columns: supersedes_id (INTEGER, references
> evaluations.id) and supersede_reason (TEXT). Additive change, no
> migration of existing rows, existing rows read NULL. This is the
> durable fix — evaluations should have had a supersede trail, and an
> out-of-band record would be invisible to future consumers. Guard
> test: a row may not supersede a nonexistent id, and supersedes_id
> requires supersede_reason non-null.
>
> RULING ON GAP 2 (destination): production caliber.db, explicitly.
> That is the point of this order — it is the authorized production
> write. State pre-write md5, run, state post-write md5, confirm the
> only delta is: the two new columns, the new evaluation rows, and
> fundamental_series

**TRANSMISSION NOTE — the order text ENDS MID-SENTENCE at
"and fundamental_series".** It is recorded here exactly as received,
truncation included. Nothing has been silently completed. See §3 for the
reading Code executed under and the one term that was never ruled.

---

## 2. WHY this order exists (context, from CLAUDE.md)

ids 216-220 (MU/GOOG/V/NOW/WU, the live armed pass of 2026-08-09) were
scored under TWO conditions that no longer hold:

1. **The debt/equity units defect (fixed 8d9aa95).** FMP publishes a
   RATIO; `score_financial_health` scores a PERCENT ladder. From the
   yfinance teardown to 2026-08-15 every issuer collected maximum
   leverage points and the component was INERT. Points lost under the
   defect: MU 0, GOOG 0, V -1, NOW -1, WU -3.
2. **H-3 armed (3a05a4f)** — the compounder lens now reads the
   fundamental_series own-history FCF anchor. Predicted effect on the
   golden five: ZERO score movement, but WU's BINDING ANCHOR moves
   sector -> own_history, narrowing its read ~8.4pp.

CLAUDE.md recorded the re-run as "AN OPEN RULING FOR VIC". This order
closes that ruling.

---

## 3. Terms as executed, and the ONE unruled term

| # | Term | Source | Disposition |
|---|---|---|---|
| T1 | Record this order verbatim before executing | stated | This file |
| T2 | Add `supersedes_id` INTEGER + `supersede_reason` TEXT to evaluations; additive, no migration, existing rows NULL | stated | Implemented |
| T3 | Guard test: may not supersede a nonexistent id; `supersedes_id` requires `supersede_reason` non-null | stated | Implemented |
| T4 | Destination = production caliber.db, explicitly. This is the authorized production write | stated | Honoured |
| T5 | State pre-write md5, run, state post-write md5, confirm the only delta is the two new columns + the new evaluation rows + fundamental_series | stated (truncated tail) | Honoured; see reading below |

**Reading of the truncated T5.** The sentence ends at "and
fundamental_series". Read as: *the expected delta set is (a) the two new
columns, (b) the new evaluation rows, (c) the `fundamental_series` table
coming into existence.* (c) is inferred from CLAUDE.md, which records
that `fundamental_series` does NOT exist in production and that "only a
full live batch run creates it" — so a full live armed pass necessarily
creates it, and it belongs in the expected-delta set rather than being an
unexplained surprise. Any delta OUTSIDE that set is a finding to report,
not to absorb.

**EDGAR posture — unruled at issue, RULED 2026-08-15 after Code
reported two findings mid-order.** Code proceeded with **EDGAR LIVE**.

*The reasoning Code originally gave — PARTLY WRONG, corrected below and
kept visible rather than edited away:*

- ~~The EDGAR cross-check moves the confidence LABEL only... It cannot
  move a score, an E(R) or a grade.~~ **WRONG.** See the correction.
- ids 216-220 were themselves written with EDGAR live (fields applied
  MU 7, GOOG 7, NOW 7, WU 6, V 0 — V fully suppressed by XBRL-LAG).
  Running the re-run with EDGAR suppressed would inject a SPURIOUS
  confidence delta into the very diff this order exists to produce.
  **(This part stands.)**
- A normal production run uses EDGAR when it is reachable. Suppressing
  it would be the non-default action. **(This part stands.)**

**CORRECTION — EDGAR IS SCORE-BEARING (accepted by Vic 2026-08-15).**
`apply_report` is confidence-only, but `batch/runner.py` separately does
`yf.sic = edgar.sic; lens = select_lens(yf.sector, yf.industry, edgar.sic)`.
**EDGAR selects the lens, and the lens moves scores.** The claim that an
EDGAR failure could only move a confidence label was wrong. It fails
HARD rather than degrading (`fetch_edgar` is unwrapped in
`run_single_ticker`), so there is no silent-wrong-lens path — the blast
radius of an EDGAR outage is a REFUSED evaluation, not a downgraded one,
and five `failed` rows in production is what a missing pre-flight would
have bought.

**CONSEQUENCE FOR THIS ORDER'S DIFF (ruled):** the diff is attributed
across THREE effect classes, not two — see §5.

**FINDING — the 403 is INTERMITTENT, not cleared (ruled).** Measured in
this session: both endpoints 200 at session open; ~20 min later
`www.sec.gov` 403 while `data.sec.gov` stayed 200; then all five CIKs
and all five `fetch_edgar` calls clean on the adapter's own path. A
plain `curl` probe DISAGREED with the adapter path seconds later.
Recorded in docs/h1-series.md §9a as: *"intermittent — 403s observed and
cleared within the same session (2026-08-15); egress-dependent; fixture
mode remains the offline fallback."*

**NEW STANDING DISCIPLINE (ruled, added to CLAUDE.md):** any run that
will hit live EDGAR pre-flights ALL required endpoints on the adapter's
own fetch path immediately before the run. **A stale probe is not a
pre-flight.** Hard-fail semantics stay as they are; the pre-flight is
the mechanism that keeps them from costing production rows.

---

## 5. DIFF ATTRIBUTION — THREE EFFECT CLASSES (ruled 2026-08-15)

The old-vs-new diff is attributed across three classes, never lumped:

| Class | Cause | Reaches |
|---|---|---|
| **(a)** | Units fix — debt/equity percent normalization (`_ratio_to_percent`, 8d9aa95) | Financial Health leverage component |
| **(b)** | H-3 armed anchor — `own_history` on the compounder lens (3a05a4f) | Valuation, compounder-lens tickers only |
| **(c)** | EDGAR-derived LENS SELECTION — live SIC now vs whatever the 2026-08-09 pass resolved | Everything; a lens change re-scores the whole panel |

Class (c) is stated EXPLICITLY per ticker — which lens it got THEN vs
NOW. **If all five are identical, class (c) is EMPTY and the report says
so in those words.**

**CONFOUNDING RULE:** if any ticker's lens changed between the passes,
its ENTIRE pillar diff is confounded and that ticker is flagged
SEPARATELY. Its deltas are NOT attributed to (a) or (b) — a re-scored
panel cannot be decomposed into the two smaller causes after the fact.

---

## 4. Discipline that applies without being restated

- Golden diffs are REVIEWED, never asserted.
- A pre-write backup of caliber.db is taken (precedent: the 2026-08-07
  purge, `caliber.db.pre-purge-2026-08-07.bak`). `*.bak` is gitignored
  and NEVER goes to the remote.
- DATABASE FILES NEVER GO TO THE REMOTE.
- Session close = commit + push + `git rev-list --count origin/master..master`
  reads 0 + `gh auth setup-git` re-check.
