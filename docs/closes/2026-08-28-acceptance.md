# Close state — 2026-08-28 ACCEPTANCE SESSION

Report: `docs/2026-08-28-acceptance.md`. **★★ ACCEPTANCE PASSED — 2026-08-28 ★★**

## State verification at open — matched; tree clean

| pointer | expected | measured | |
|---|---|---|---|
| HEAD | `b61757a` | `b61757a39843625f68dcfef3d731674902609bf6` | ✅ |
| Suite | 1089 | **1089 passed** | ✅ |
| caliber.db md5 | `8752e75e…` | `8752e75e05a8a7ff225258ec99d36fc3` | ✅ |
| Tree / unpushed | clean / 0 | clean / 0 | ✅ |
| PID | — | **own pid 14893**, PPID walk from bash child 17250 | ✅ |

No peers, no `ppid 1` orphans. Pre-run gates: **stage-freshness sweep exit 0, zero unapproved
flips**; **live-EDGAR pre-flight 28/28 OK**; FRED 10Y 4.67%.

## State at close

| | |
|---|---|
| HEAD | the **acceptance close commit** — verify with `git log -1`. Previous was `b61757a`. |
| Suite | **1091 passed** (1089 at the acceptance run; +2 from the post-acceptance ETF-ordering pins). |
| caliber.db md5 | **`69dc2328ee3af8a43d506b64665da39b`** (was `8752e75e…`) |
| Backup | `caliber.db.pre-acceptance-8752e75e.bak`, verified byte-equal to the pre-run db |
| **PRODUCTION WRITES** | **ONE RUN, FOUR TABLES, ALL RECONCILED EXACTLY.** `evaluations` +24 (expected +24) · `field_provenance` +494 (expected +430..500) · `lifecycle_stage` +24 (expected +24) · `lifecycle_transitions` +1 (expected +1, QBTS only). Every other table **+0**, re-counted at close. |
| evaluations | **104** rows — all 24 new rows `status='ok'`; 0 anchor_divergence, 0 failed, 0 no_synthesis |
| lifecycle_stage | **68** rows (44 + 24); 8 remain RETIRED (the banks) |
| lifecycle_transitions | **2** rows — IONQ (2026-08-17) and **QBTS (this run)** |
| field_provenance | **1931** rows |
| fundamental_series / synthesis_cache / grades / overrides / lifecycle_overrides / stage_flip_approvals | 2622 / 16 / 0 / 0 / 0 / 1 — **all unchanged** |
| Universe outcome | **24 SCORED · 4 REFUSED · 0 errored · 0 silent** |

## Acceptance verdict

**(a)** 28/28 on production paths, no shortcuts · **(b)** full per-name table, none silent ·
**(c)** six anomalies, six typed explanations, **ZERO UNEXPLAINED**.

**Two stated expectations not literally met, both explained by design, both flagged for Vic
to overrule:** QBTS scored on the 20% band (no-read-back ordering; 30% applies next eval);
the ETF typed reason is unreachable on both paths because the EDGAR hard gate refuses first
(safety holds, label wrong, one-line fix NOT applied per the order).

## Census disposition (ruling 2)

All 32 items in `docs/2026-08-28-closer.md` §8 annotated with dated one-liners —
**13 RESOLVED · 16 PARKED · 2 CLOSED-ACCEPTED · 1 INFORMATIONAL**. Not one original line
edited or removed.

## MAJOR FLAG — carried unchanged

**FINANCIALS ARE UNSCOREABLE pending a dedicated leg. Router + gate SHIPPED; ENGINE NOT
BUILT; scoping order QUEUED.** BK/C/JPM/USB produced no score, no stage, no band, no row —
measured on this run. Bank-lens calibration has no population. **The only remaining build.**

## CALIBER enters grading life

24 live forecasts on the clock. `run_grading()` admits at ≥90d, so the first gradeable cohort
from this run matures around **2026-11-26**. Next sessions are grading reads, not
construction.

## Open

1. QBTS band lags its stage by one evaluation (by design) — Vic may rule.
2. ~~ETF guard shadowed by the EDGAR hard gate~~ — **✅ RULED AND FIXED 2026-08-28**, same
   day, immediately after acceptance. Guard moved above `fetch_edgar` on BOTH paths; LYTE and
   FLTW re-measured at **exit 7 / `etf:not_a_company`** with the EDGAR fetch never attempted.
   3 pins added (2 verified to fail pre-fix). Suite 1089 → **1091**. **ZERO production
   writes** — controls routed to scratch DBs; caliber.db md5 `69dc2328` unchanged. The
   acceptance verdict stands: no universe name has `isEtf=true`.
3. `price_snapshot` still not captured on completing evals (census 16, PARKED) — these 24
   rows cannot be replay-verified against their own day.
4. 16 parked census items, each with its re-arm condition.

## ★ FOUND AT THE CLOSE — CENSUS ITEM 29's MECHANISM, REPRODUCED

The 2026-08-19 diagnosis question *"what opened a backup as a live database?"* is answered,
by accident and by reproduction. This session's delta reconciliation opened
`caliber.db.pre-acceptance-8752e75e.bak` with `mode=ro`, and a `-shm` (32 KB) / `-wal`
(0 bytes) pair appeared — **the same byte sizes as the 2026-08-17 pair.**

**CAUSE: caliber.db is in WAL journal mode, and SQLite creates the shm/wal pair on OPEN,
including read-only.** The pair is a READ-SIDE artifact, not evidence of a write. Backup md5
verified unchanged after the read. **The original concern — that something could open the
evidence read-write — is answered: no write occurred and none was needed to produce it.**

Disposition stays CLOSED-ACCEPTED, now closed knowing why. Both stray pairs (2026-08-28 and
the surviving 2026-08-15 one) removed at this close; both backups' md5s verified intact
after removal.
