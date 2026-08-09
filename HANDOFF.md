> **SUPERSEDED 2026-08-09 — DO NOT READ AS CURRENT STATE. See CLAUDE.md, which auto-loads.**
>
> This file is a frozen 2026-07-17 snapshot, kept for the record. Its durable content was
> absorbed into CLAUDE.md (which is the fix its own last section asks for), and two of its
> claims were later DISPROVEN and must not be acted on:
>
> - "51 ok-evals have NULL E(R) — CONFIRMED correct-by-design" is **WRONG**. Those rows were
>   TEST CONTAMINATION: tests/test_batch.py ran fixture-mode batches against production
>   caliber.db with no db_path. 189 evaluations and 3,060 field_provenance rows were purged
>   2026-08-07 under a blast-radius assertion; conftest.py now pins the default DB to a temp
>   path. No real no-synthesis 'ok' eval ever existed.
> - Open threads 2 and 3 are both CLOSED (B-1 status semantics; run_grading's CLEAN EMPTY line).
>
> Current state, always: CLAUDE.md.

CALIBER — session state, 2026-07-17

GRADER — DONE, closed this session:
- Real-DB run DONE: 0 evals eligible (8 gradeable are ~5d old; filter requires >=90d).
  Nothing graded, grades table still 0 — CORRECT (grader refuses immature evals).
- NOTE on mechanism: at default min_age_days=90, PENDING is unreachable via run_grading()
  — the SQL query admits only >=90d, but the PENDING branch requires <90d (mutually
  exclusive). PENDING only appears if min_age_days is lowered or grade_evaluation() is
  called directly. The 8 Visa evals become eligible ~2026-10-10.
- Rubric 2a DONE: fixed grading.py docstring — A-line falsely said "(within 25% of
  magnitude)"; real rule is a one-sided 75% floor, no upper bound. Docs-only, no behavior change.
- Rubric 2b DONE: conviction-floor C (|E(R)|<5% -> C [no-conviction E(R)]) verified in
  assign_grade, checked first. Left as-is, no restructuring.
- Rubric 2c DONE: both-C-triggers precedence locked — when |E(R)|<5% AND |actual|<5%,
  [no-conviction E(R)] wins over [flat outcome]. Added test_both_c_triggers_conviction_wins.
- Suite green: 268 passed. Grader code-complete; live A-F path validated synthetically,
  confirms on real data ~Oct 2026 when Visa evals mature.

TWO OPEN THREADS (both parked, NOT urgent):
1. 51 ok-evals have NULL E(R) — CONFIRMED correct-by-design (synthesis never ran on them;
   nothing hidden in synthesis_json). Grader correctly excludes them.
2. Upstream: those 51 were written status='ok' despite having NO synthesis at all (pillar
   scores present, synthesis_json + verdict_conf NULL). status='ok' should mean a complete
   eval. Latent schema/semantics question in the evaluate/synthesis path — low priority, decide later.
3. Minor: "0 eligible / nothing graded" exits clean — correct today, but that same message
   could mask a real problem on a future run. Worth making "0 eligible" distinguishable from
   "something broke" eventually.

DURABLE-CONTEXT ROADMAP (next priority after this session):
- Write CLAUDE.md at repo root so Code wakes up warm on every boot. Replit does NOT persist
  Code sessions (home dir ~/.claude wiped between containers) — but repo files DO persist,
  and CLAUDE.md auto-loads at session start. This is the fix for the cold-start scramble.
- Encode into CLAUDE.md: the disciplines + roadmap phases C, D, G, EDGAR.
