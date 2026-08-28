# `docs/closes/` — full close state, one dated file per close

**Standing rule (Vic ruling 2, 2026-08-28).** A close writes its FULL measured state here —
md5 trail, write points, expected-vs-actual reconciliation, per-table counts. **CLAUDE.md
carries ONLY a ~10-line STATE POINTER block** (HEAD · suite · md5 · backup name · this
file's path · open-items pointer) and never a full state table.

Why: the state tables accreted three deep in CLAUDE.md, each labelled "supersedes every
table below it", so a cold-start session had to read all three to learn one md5. One
always-current pointer is cheaper to trust than a hand-ordered stack.

Newest first.

| close | file | md5 at close | suite |
|---|---|---|---|
| 2026-08-28 micro (QBTS approval, GOOG diagnosis, close-state migration) | `2026-08-28-micro.md` | `8752e75e` | 1051 |
| 2026-08-28 second, the "closer" order | `2026-08-28-closer.md` | `19d615fe` | 1051 |
| 2026-08-28 first, SKHY USD-only + financials class | `2026-08-28-first.md` | `70be9730` | 1011 |
| 2026-08-22, L-4d.1 LLY capex basis | `2026-08-22-l4d1.md` | `eec96270` | 975 |

The three pre-2026-08-28-micro files were **relocated verbatim** out of CLAUDE.md when this
rule landed — relocation only, nothing edited, all 44 lines verified present in the
destination before removal from the source.
