"""
SQLite persistence for CALIBER evaluations.

Schema:
  evaluations     — one row per run (ticker, timestamp, all pillar scores + synthesis)
  field_provenance — provenance rows linked to an evaluation
  overrides       — user-accepted field overrides

All JSON blobs are stored as TEXT; compound data is serialized with json.dumps.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from adapters.base import PillarResult
from synthesis.schema import SynthesisOutput

_DEFAULT_DB = Path(__file__).parent.parent / "caliber.db"

# Statuses for evaluations that did not complete. Kept apart from the completing set
# ('ok' | 'no_synthesis' | 'anchor_unverified' | 'anchor_divergence') because these
# never carry pillars or an avg_score — there is nothing to grade.
_NON_COMPLETING_STATUSES = ("failed", "rate_unavailable")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn(db_path: Path = _DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class SupersedeLinkInvalid(Exception):
    """A supersede link was malformed. Raised BEFORE any row is written.

    Two rules, both loud (a bad audit trail is worse than no audit trail — it reads
    as provenance while pointing nowhere):
      1. supersedes_id must name an evaluation that EXISTS. The FK is the DB-level
         backstop; this is the typed signal that says which id was missing.
      2. supersedes_id requires supersede_reason. An unexplained supersede tells a
         future reader that a row was replaced but not why, which is the one thing
         the trail exists to record.
    """


# Columns added to `evaluations` after rows already existed. ADDITIVE ONLY — every
# existing row reads NULL, and nothing is migrated or rewritten.
#
# NOTE the pairing rule (supersedes_id requires supersede_reason) is enforced in
# Python at the single write boundary, NOT as a table CHECK. SQLite cannot add a
# multi-column CHECK via ALTER TABLE, so encoding it in the fresh-DB DDL alone would
# leave a migrated production DB and a fresh test DB under DIFFERENT constraints —
# and the tests would then be proving something production does not enforce. One
# enforcement point, identical everywhere. See SupersedeLinkInvalid.
_EVALUATIONS_ADDED_COLUMNS = {
    "supersedes_id": "INTEGER REFERENCES evaluations(id)",
    "supersede_reason": "TEXT",
}


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> List[str]:
    """Add any missing columns to `table`. Returns the names actually added.

    Idempotent: a column already present is left completely alone (never redefined,
    never backfilled). SQLite permits ADD COLUMN with a REFERENCES clause only when
    the column defaults to NULL, which is exactly the additive case here.
    """
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    added = []
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            added.append(name)
    return added


def init_db(db_path: Path = _DEFAULT_DB) -> None:
    """Create tables if they don't exist."""
    with _conn(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker      TEXT    NOT NULL,
                run_at      TEXT    NOT NULL,
                lens        TEXT,
                status      TEXT    NOT NULL DEFAULT 'ok',   -- ok | no_synthesis | anchor_unverified | anchor_divergence | rate_unavailable | failed
                error_msg   TEXT,
                pillars_json    TEXT,   -- JSON list of PillarResult dicts
                synthesis_json  TEXT,   -- JSON SynthesisOutput (raw dict)
                avg_score       REAL,
                overall_conf    TEXT,
                verdict_conf    TEXT,
                expected_return REAL,
                -- Supersede trail (ruled 2026-08-15). An evaluation is NEVER edited or
                -- deleted to correct it: the corrected run lands as a NEW ROW pointing at
                -- the one it replaces. Same principle as fundamental_series — overwriting
                -- destroys the evidence that a reading changed, which is the whole audit
                -- trail. Both columns are NULL on an ordinary (non-superseding) run.
                supersedes_id     INTEGER REFERENCES evaluations(id),
                supersede_reason  TEXT
            );

            CREATE TABLE IF NOT EXISTS field_provenance (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id   INTEGER NOT NULL REFERENCES evaluations(id),
                pillar          TEXT,
                field_name      TEXT,
                value           TEXT,
                source          TEXT,
                as_of           TEXT,
                confidence      TEXT
            );

            CREATE TABLE IF NOT EXISTS overrides (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT    NOT NULL,
                field_name      TEXT    NOT NULL,
                override_value  TEXT,
                override_at     TEXT    NOT NULL,
                note            TEXT
            );

            CREATE TABLE IF NOT EXISTS synthesis_cache (
                ticker          TEXT    NOT NULL,
                eval_date       TEXT    NOT NULL,
                synthesis_json  TEXT    NOT NULL,
                price_snapshot  REAL,
                created_at      TEXT    NOT NULL,
                PRIMARY KEY (ticker, eval_date)
            );

            CREATE TABLE IF NOT EXISTS grades (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id   INTEGER UNIQUE NOT NULL REFERENCES evaluations(id),
                ticker          TEXT    NOT NULL,
                eval_date       TEXT    NOT NULL,
                er_published    REAL,
                verdict_conf    TEXT,
                price_at_eval   REAL,
                price_at_90d    REAL,
                actual_return   REAL,
                grade           TEXT,
                graded_at       TEXT    NOT NULL,
                note            TEXT
            );

            -- Phase H-1 (schema addendum, ruled 2026-08-15). Per-period fundamental
            -- history, for Phase M (Monte Carlo) to derive input distributions from.
            --
            -- ISSUER-KEYED, NOT EVALUATION-KEYED. An FY2023 free cash flow is a property
            -- of the issuer, not of a run; keying it to evaluation_id would duplicate
            -- ~20 rows per ticker per run and leave Phase M unable to say which eval to
            -- trust. Every other table here is an evaluation snapshot; this one is not.
            --
            -- APPEND, NEVER OVERWRITE. A value is immutable once written. When a later
            -- run computes a DIFFERENT value for the same key, that is a restatement and
            -- it lands as a NEW ROW — overwriting would destroy the evidence that a
            -- historical figure changed, which is the exact defect class Phase G exists
            -- to catch. `last_confirmed` is the ONLY column ever updated in place, and it
            -- records re-observation, not a value.
            --
            -- `excluded` is a READ-TIME FILTER FOR THE ANCHOR, never a storage filter:
            -- negative-FCF periods are stored in full so Phase M sees the left tail.
            --
            -- TWO REASON COLUMNS, DELIBERATELY SEPARATE (F3, ruled 2026-08-15). A row is
            -- absent-from-the-anchor for one of two unrelated causes and they must not
            -- share a column:
            --   exclusion_reason -- set IFF excluded=1. The value is real but illegal for
            --                       the MIN-of-medians anchor (a negative FCF has no
            --                       yield interpretation).
            --   null_reason      -- set IFF value IS NULL and excluded=0. The value is
            --                       STRUCTURALLY UNAVAILABLE (no D&A spec), not rejected.
            -- Overloading one column would make `reason IS NOT NULL` mean two different
            -- things, and Phase M reads this table. reason-present must never have to be
            -- cross-checked against `excluded` to be understood.
            CREATE TABLE IF NOT EXISTS fundamental_series (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT    NOT NULL,
                metric          TEXT    NOT NULL,
                period_end      TEXT    NOT NULL,
                period_type     TEXT    NOT NULL,   -- FY | TTM_Q
                value           REAL,               -- NULL is legal (reinvestment)
                unit            TEXT,
                basis           TEXT,               -- G-4 split basis, or not_applicable
                method          TEXT,               -- TTM assembly method
                excluded        INTEGER NOT NULL DEFAULT 0,
                exclusion_reason TEXT,              -- set IFF excluded=1
                null_reason     TEXT,               -- set IFF value IS NULL, excluded=0
                components_json TEXT,
                first_observed  TEXT    NOT NULL,
                last_confirmed  TEXT    NOT NULL,
                superseded      INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_fundseries_key
                ON fundamental_series (ticker, metric, period_end, period_type, basis);

            -- ── Phase L: lifecycle stage ─────────────────────────────────────
            -- ISSUER-KEYED and APPEND-ONLY, on the fundamental_series precedent: a stage
            -- is a property of the issuer at a point in time, not of an evaluation run.
            -- Every classification lands as a new row, so the history a transition report
            -- reads is the table itself rather than a derived log that could disagree
            -- with it.
            --
            -- `absent_legs` and `inputs_incomplete` are NOT decoration. A DECLINE computed
            -- with every leg measured and a MATURE reached because a leg was missing are
            -- different claims, and Phase M reads this table.
            CREATE TABLE IF NOT EXISTS lifecycle_stage (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker           TEXT    NOT NULL,
                computed_stage   TEXT    NOT NULL,
                rule_fired       TEXT    NOT NULL,
                lens             TEXT,
                inputs_json      TEXT    NOT NULL,
                assertions_json  TEXT    NOT NULL,
                flags_json       TEXT    NOT NULL,
                absent_legs      TEXT,               -- NULL iff nothing was absent
                inputs_incomplete INTEGER NOT NULL DEFAULT 0,
                config_version   TEXT    NOT NULL,
                run_at           TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_lifecycle_stage_ticker
                ON lifecycle_stage (ticker, run_at);

            -- Vic's override. `rationale_text` is NOT NULL and is additionally checked
            -- non-empty by the writer: an override without a stated reason is exactly the
            -- laundering the anti-launder mechanics exist to prevent (order §4).
            -- Append-only — a superseding override is a NEW ROW, so the trail of what was
            -- believed when survives.
            CREATE TABLE IF NOT EXISTS lifecycle_overrides (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker           TEXT    NOT NULL,
                computed_stage   TEXT    NOT NULL,
                approved_stage   TEXT    NOT NULL,
                rationale_text   TEXT    NOT NULL,
                created_at       TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_lifecycle_overrides_ticker
                ON lifecycle_overrides (ticker, created_at);

            -- Transitions are INFORMATION, not noise (order §4). A real table rather than
            -- a view: the transition is detected against the previous row at write time,
            -- and recomputing it later from a table that has since grown would not
            -- reproduce what was actually reported.
            CREATE TABLE IF NOT EXISTS lifecycle_transitions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker           TEXT    NOT NULL,
                from_stage       TEXT    NOT NULL,
                to_stage         TEXT    NOT NULL,
                from_stage_id    INTEGER REFERENCES lifecycle_stage(id),
                to_stage_id      INTEGER REFERENCES lifecycle_stage(id),
                overridden       INTEGER NOT NULL DEFAULT 0,
                standing_override TEXT,
                detected_at      TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_lifecycle_transitions_ticker
                ON lifecycle_transitions (ticker, detected_at);
        """)

        # Bring a pre-existing evaluations table up to the current column set. A DB
        # created fresh by the DDL above already has them and this is a no-op.
        _ensure_columns(conn, "evaluations", _EVALUATIONS_ADDED_COLUMNS)


def _validate_supersede_link(
    supersedes_id: Optional[int],
    supersede_reason: Optional[str],
    db_path: Path = _DEFAULT_DB,
) -> None:
    """Enforce the supersede-link rules BEFORE anything is written.

    Checked here rather than left to the foreign key so the failure names the id it
    could not find, and so the pairing rule (which SQLite cannot express as an
    added CHECK) lives in the same place as the FK rule instead of being split
    across two layers. The FK remains as the DB-level backstop.
    """
    has_reason = supersede_reason is not None and supersede_reason.strip() != ""

    if supersedes_id is None:
        # A reason pointing at nothing is unqueryable noise that still reads as
        # provenance. NOTE: the ruling specified the other direction only; this
        # half is Code's addition, disclosed for Vic to strike or keep.
        if has_reason:
            raise SupersedeLinkInvalid(
                f"supersede_reason given ({supersede_reason!r}) with no supersedes_id — "
                "a reason must name the row it explains."
            )
        return

    if not has_reason:
        raise SupersedeLinkInvalid(
            f"supersedes_id={supersedes_id} requires a non-empty supersede_reason. "
            "An unexplained supersede records that a row was replaced but not why."
        )

    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM evaluations WHERE id=?", (supersedes_id,)
        ).fetchone()
    if row is None:
        raise SupersedeLinkInvalid(
            f"supersedes_id={supersedes_id} does not exist in evaluations — "
            "a supersede trail may not point at a nonexistent row."
        )


def _pillar_to_dict(p: PillarResult) -> Dict[str, Any]:
    return {
        "name": p.name,
        "score": p.score,
        "confidence": p.confidence,
        "rationale": p.rationale,
        "flags": p.flags,
        "method": p.method,
    }


def get_cached_synthesis(
    ticker: str,
    eval_date: str,
    db_path: Path = _DEFAULT_DB,
) -> Optional[Dict[str, Any]]:
    """Return cached synthesis dict for (ticker, eval_date), or None if absent."""
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT synthesis_json, price_snapshot FROM synthesis_cache WHERE ticker=? AND eval_date=?",
            (ticker, eval_date),
        ).fetchone()
    if not row:
        return None
    return {"synthesis_json": row["synthesis_json"], "price_snapshot": row["price_snapshot"]}


def save_synthesis_cache(
    ticker: str,
    eval_date: str,
    synthesis_json: str,
    price_snapshot: Optional[float],
    db_path: Path = _DEFAULT_DB,
) -> None:
    """Upsert a synthesis result into the cache."""
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO synthesis_cache
               (ticker, eval_date, synthesis_json, price_snapshot, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker, eval_date, synthesis_json, price_snapshot, _utc_now()),
        )


def save_evaluation(
    ticker: str,
    lens: str,
    pillars: List[PillarResult],
    synthesis: Optional[SynthesisOutput],
    expected_return: Optional[float] = None,
    db_path: Path = _DEFAULT_DB,
    status: Optional[str] = None,
    supersedes_id: Optional[int] = None,
    supersede_reason: Optional[str] = None,
) -> int:
    """
    Persist a complete evaluation. Returns the new evaluation id.

    status: caller override for the eval status (the anchor-guard verdict —
    'ok' | 'anchor_unverified' | 'anchor_divergence'). When None, it is derived
    from synthesis presence (B-1: 'ok' if synthesis else 'no_synthesis').

    supersedes_id / supersede_reason: this run REPLACES an earlier evaluation (e.g.
    it was scored under a defect since fixed). The earlier row is left completely
    untouched — appended-and-linked, never edited. Both or neither; see
    SupersedeLinkInvalid.
    """
    init_db(db_path)
    _validate_supersede_link(supersedes_id, supersede_reason, db_path)

    avg_score = sum(p.score for p in pillars) / len(pillars) if pillars else None
    from adapters.base import _RANK, _LEVEL
    overall_conf = _LEVEL[min(_RANK[p.confidence] for p in pillars)] if pillars else "low"

    pillars_json = json.dumps([_pillar_to_dict(p) for p in pillars])
    synthesis_json = json.dumps(synthesis.rawJson) if synthesis else None
    # status='ok' must mean a COMPLETE eval. A missing synthesis is a real,
    # auditable degraded state — record it honestly rather than masking as 'ok'.
    # (Pillars are still valid, so we keep the row instead of failing it.)
    # A caller-supplied status (anchor-guard verdict) always wins.
    if status is None:
        status = "ok" if synthesis is not None else "no_synthesis"
    verdict_conf = synthesis.verdictConfidence if synthesis else None
    # E(R) is computed downstream from scenario targets, never delegated to the
    # LLM. Only fall back to the LLM's number for a clean 'ok' eval; NEVER
    # reinstate it when the anchor guard withheld E(R) (anchor_unverified /
    # anchor_divergence both persist a NULL E(R) by design).
    if expected_return is None and synthesis is not None and status == "ok":
        expected_return = synthesis.expectedReturn

    with _conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO evaluations
              (ticker, run_at, lens, status, pillars_json, synthesis_json,
               avg_score, overall_conf, verdict_conf, expected_return,
               supersedes_id, supersede_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker, _utc_now(), lens, status,
                pillars_json, synthesis_json,
                avg_score, overall_conf, verdict_conf, expected_return,
                supersedes_id, supersede_reason,
            ),
        )
        eval_id = cur.lastrowid

        # Persist provenance rows for key inputs
        prov_rows = []
        for pillar in pillars:
            for prov in pillar.key_inputs:
                if prov is not None and not prov.is_missing():
                    prov_rows.append((
                        eval_id, pillar.name, None,
                        str(prov.value), prov.source, prov.as_of, prov.confidence,
                    ))
        if prov_rows:
            conn.executemany(
                """
                INSERT INTO field_provenance
                  (evaluation_id, pillar, field_name, value, source, as_of, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                prov_rows,
            )

    return eval_id


def backfill_no_synthesis_status(db_path: Path = _DEFAULT_DB) -> int:
    """One-shot, idempotent migration: relabel legacy false-complete rows.

    Rows written status='ok' despite having no synthesis (synthesis_json IS NULL)
    predate the status-semantics fix. Relabel them to 'no_synthesis' so 'ok' means
    a COMPLETE eval. Non-destructive (only the status label changes) and idempotent
    (after the first run, no status='ok' row has NULL synthesis_json, so re-runs
    match 0 rows). Returns the number of rows relabeled. Does NOT change grading
    eligibility — get_ungradeable_evals already excludes these via its
    expected_return IS NOT NULL clause.
    """
    init_db(db_path)
    with _conn(db_path) as conn:
        cur = conn.execute(
            "UPDATE evaluations SET status='no_synthesis' "
            "WHERE status='ok' AND synthesis_json IS NULL"
        )
        return cur.rowcount


def save_failed_evaluation(
    ticker: str,
    error_msg: str,
    db_path: Path = _DEFAULT_DB,
    status: str = "failed",
) -> int:
    """Record a non-completing evaluation so batch runs are fully auditable.

    status distinguishes WHY it did not complete. 'failed' is an operational DOA (the
    feed died, something raised). 'rate_unavailable' is a deliberate POLICY REFUSAL under
    the mandatory-rate ruling — the pipeline worked and declined to score. Collapsing the
    two would make a refusal read as a crash and hide the policy from the audit trail.
    """
    if status not in _NON_COMPLETING_STATUSES:
        raise ValueError(
            f"save_failed_evaluation status must be one of {_NON_COMPLETING_STATUSES}, "
            f"got {status!r}"
        )
    init_db(db_path)
    with _conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO evaluations (ticker, run_at, status, error_msg)
            VALUES (?, ?, ?, ?)
            """,
            (ticker, _utc_now(), status, error_msg[:2000]),
        )
        return cur.lastrowid


def list_evaluations(
    ticker: Optional[str] = None,
    limit: int = 50,
    db_path: Path = _DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """Return recent evaluations, optionally filtered by ticker."""
    init_db(db_path)
    with _conn(db_path) as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM evaluations WHERE ticker=? ORDER BY run_at DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM evaluations ORDER BY run_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_evaluation(eval_id: int, db_path: Path = _DEFAULT_DB) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM evaluations WHERE id=?", (eval_id,)
        ).fetchone()
        return dict(row) if row else None


# ── Web-layer additions (Phase 4) ─────────────────────────────────────────────

import re as _re


def _conflict_field_key(pillar: str, source: str) -> str:
    slug = _re.sub(r'[\s/&]+', '_', (pillar or '').lower()).strip('_')
    m1 = _re.match(r'(\w+)\[', source)
    m2 = _re.search(r'vs (\w+)\[', source)
    src_a = m1.group(1) if m1 else 'srcA'
    src_b = m2.group(1) if m2 else 'srcB'
    return f"{slug}::{src_a}::{src_b}"


def _parse_conflict_source(source: str) -> dict:
    m = _re.match(
        r'(\w+)\[([^\]@]+)@?([^\]]*)\] vs (\w+)\[([^\]@]+)@?([^\]]*)\]',
        source,
    )
    if m:
        return {
            'src_a': m.group(1), 'val_a': m.group(2), 'date_a': m.group(3) or None,
            'src_b': m.group(4), 'val_b': m.group(5), 'date_b': m.group(6) or None,
        }
    return {'src_a': '?', 'val_a': source, 'date_a': None,
            'src_b': None, 'val_b': None, 'date_b': None}


def get_conflicts(
    eval_id: Optional[int] = None,
    ticker: Optional[str] = None,
    db_path: Path = _DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """Return field_provenance rows with source-conflict. Attach parsed source info."""
    init_db(db_path)
    with _conn(db_path) as conn:
        if eval_id is not None:
            rows = conn.execute(
                """SELECT fp.id, fp.evaluation_id, fp.pillar, fp.field_name,
                          fp.value, fp.source, fp.as_of, fp.confidence, e.ticker
                   FROM field_provenance fp
                   JOIN evaluations e ON e.id = fp.evaluation_id
                   WHERE fp.evaluation_id = ? AND fp.source LIKE '%CONFLICT%'
                   ORDER BY fp.id""",
                (eval_id,),
            ).fetchall()
        elif ticker is not None:
            rows = conn.execute(
                """SELECT fp.id, fp.evaluation_id, fp.pillar, fp.field_name,
                          fp.value, fp.source, fp.as_of, fp.confidence, e.ticker
                   FROM field_provenance fp
                   JOIN evaluations e ON e.id = fp.evaluation_id
                   WHERE e.ticker = ? AND fp.source LIKE '%CONFLICT%'
                   ORDER BY fp.id DESC LIMIT 60""",
                (ticker.upper(),),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT fp.id, fp.evaluation_id, fp.pillar, fp.field_name,
                          fp.value, fp.source, fp.as_of, fp.confidence, e.ticker
                   FROM field_provenance fp
                   JOIN evaluations e ON e.id = fp.evaluation_id
                   WHERE fp.source LIKE '%CONFLICT%'
                   ORDER BY fp.id DESC LIMIT 200""",
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['field_key'] = _conflict_field_key(d.get('pillar', ''), d.get('source', ''))
        d['parsed'] = _parse_conflict_source(d.get('source', ''))
        result.append(d)
    return result


def save_override(
    ticker: str,
    field_name: str,
    override_value: str,
    note: str = '',
    db_path: Path = _DEFAULT_DB,
) -> None:
    init_db(db_path)
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT INTO overrides (ticker, field_name, override_value, override_at, note)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker.upper(), field_name, str(override_value), _utc_now(), note),
        )


def list_overrides(
    ticker: Optional[str] = None,
    db_path: Path = _DEFAULT_DB,
) -> List[Dict[str, Any]]:
    init_db(db_path)
    with _conn(db_path) as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM overrides WHERE ticker=? ORDER BY override_at DESC",
                (ticker.upper(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM overrides ORDER BY override_at DESC LIMIT 300"
            ).fetchall()
    return [dict(r) for r in rows]


def get_overrides_by_key(
    ticker: str,
    db_path: Path = _DEFAULT_DB,
) -> Dict[str, Any]:
    """Return {field_name: most_recent_override_row} for a ticker."""
    rows = list_overrides(ticker, db_path)
    result: Dict[str, Any] = {}
    for r in rows:
        key = r['field_name']
        if key not in result:
            result[key] = r
    return result


# ── Phase 5 — Grading ─────────────────────────────────────────────────────────

def save_grade(
    evaluation_id: int,
    ticker: str,
    eval_date: str,
    er_published: Optional[float],
    verdict_conf: Optional[str],
    price_at_eval: Optional[float],
    price_at_90d: Optional[float],
    actual_return: Optional[float],
    grade: str,
    note: str = "",
    db_path: Path = _DEFAULT_DB,
) -> int:
    init_db(db_path)
    with _conn(db_path) as conn:
        cur = conn.execute(
            """INSERT OR REPLACE INTO grades
               (evaluation_id, ticker, eval_date, er_published, verdict_conf,
                price_at_eval, price_at_90d, actual_return, grade, graded_at, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (evaluation_id, ticker, eval_date, er_published, verdict_conf,
             price_at_eval, price_at_90d, actual_return, grade, _utc_now(), note),
        )
        return cur.lastrowid


def list_grades(
    ticker: Optional[str] = None,
    limit: int = 200,
    db_path: Path = _DEFAULT_DB,
) -> List[Dict[str, Any]]:
    init_db(db_path)
    with _conn(db_path) as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM grades WHERE ticker=? ORDER BY eval_date DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM grades ORDER BY eval_date DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def get_ungradeable_evals(
    min_age_days: int = 90,
    db_path: Path = _DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """Return ok evaluations with expected_return that are old enough and not terminally graded.

    Never-graded evals qualify, as do evals whose last outcome was a transient
    PENDING or PRICE_UNAVAILABLE (retried; upserts into a real grade on success).
    Terminal states (A-F, N/A) are excluded.
    """
    init_db(db_path)
    with _conn(db_path) as conn:
        rows = conn.execute(
            """SELECT e.* FROM evaluations e
               LEFT JOIN grades g ON g.evaluation_id = e.id
               WHERE e.status = 'ok'
                 AND e.expected_return IS NOT NULL
                 AND (g.id IS NULL OR g.grade IN ('PENDING','PRICE_UNAVAILABLE'))
                 AND julianday('now') - julianday(e.run_at) >= ?
               ORDER BY e.run_at ASC LIMIT 200""",
            (min_age_days,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Phase H-1 — fundamental series (schema addendum, ruled 2026-08-15) ────────

# Two runs over identical inputs produce identical floats, so any difference at all means
# an INPUT changed — a restatement, not arithmetic noise. The tolerance exists only to
# absorb platform-level last-bit variation, and is deliberately far tighter than any real
# restatement.
_SERIES_VALUE_TOLERANCE = 1e-9


def _same_series_value(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= _SERIES_VALUE_TOLERANCE * max(1.0, abs(a), abs(b))


def save_fundamental_series(
    points: List[Any], db_path: Path = _DEFAULT_DB,
) -> tuple:
    """Persist series points. Returns (rows_written, restatements_detected).

    APPEND, NEVER OVERWRITE (ruled). A stored value is immutable. Three cases per point:

      unseen key          -> INSERT.
      identical reading   -> no new row; `last_confirmed` is touched so re-observation is
                             recorded. The value itself is not rewritten.
      DIFFERENT reading   -> the existing row is marked `superseded` and the new one is
                             INSERTED ALONGSIDE IT. The old figure stays readable. This is
                             the restatement trail; overwriting would delete exactly the
                             evidence that a historical number moved.

    "Identical" means identical in VALUE, `excluded`, both reason columns, `method`,
    `unit` AND `components` — every field describing the measurement, not the value alone
    (F4). `restatements_detected` counts only the subset where the VALUE moved, so a
    method-only change supersedes without being reported as a restated figure.

    `last_confirmed` and `superseded` are the only columns ever updated in place, and
    neither is a value — both are bookkeeping about observation, not measurement.

    Takes an explicit db_path from its caller. H-1 made this surface a writer, so the
    destination is named rather than defaulted (degraded-run write guard).
    """
    init_db(db_path)
    written = restatements = 0
    now = _utc_now()
    with _conn(db_path) as conn:
        for p in points:
            key = (p.ticker, p.metric, p.period_end, p.period_type, p.basis)
            components_json = json.dumps(p.components or {}, sort_keys=True)
            existing = conn.execute(
                """SELECT id, value, excluded, exclusion_reason, null_reason,
                          method, unit, components_json
                   FROM fundamental_series
                   WHERE ticker=? AND metric=? AND period_end=? AND period_type=?
                     AND basis=? AND superseded=0
                   ORDER BY id DESC LIMIT 1""",
                key,
            ).fetchone()

            if existing is not None:
                # EVERY field that DESCRIBES THE MEASUREMENT participates (F4, ruled
                # 2026-08-15) — not just the value. A TTM method moving
                # ttm_reconstructed -> ttm_summed at an identical value is a different
                # measurement that happens to agree, and silence about it would hide
                # exactly the assembly change a later reader would need to explain a
                # divergence. Same for the components: if a leg moved and the difference
                # cancelled, that is evidence, not a no-op.
                unchanged = (
                    _same_series_value(existing["value"], p.value)
                    and bool(existing["excluded"]) == bool(p.excluded)
                    and (existing["exclusion_reason"] or None)
                    == (p.exclusion_reason or None)
                    and (existing["null_reason"] or None) == (p.null_reason or None)
                    and (existing["method"] or None) == (p.method or None)
                    and (existing["unit"] or None) == (p.unit or None)
                    and (existing["components_json"] or "{}") == components_json
                )
                if unchanged:
                    conn.execute(
                        "UPDATE fundamental_series SET last_confirmed=? WHERE id=?",
                        (now, existing["id"]),
                    )
                    continue
                conn.execute(
                    "UPDATE fundamental_series SET superseded=1 WHERE id=?",
                    (existing["id"],),
                )
                if not _same_series_value(existing["value"], p.value):
                    restatements += 1

            conn.execute(
                """INSERT INTO fundamental_series
                   (ticker, metric, period_end, period_type, value, unit, basis, method,
                    excluded, exclusion_reason, null_reason, components_json,
                    first_observed, last_confirmed, superseded)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                (p.ticker, p.metric, p.period_end, p.period_type, p.value, p.unit,
                 p.basis, p.method, 1 if p.excluded else 0, p.exclusion_reason,
                 p.null_reason, components_json, now, now),
            )
            written += 1
    return written, restatements


def list_fundamental_series(
    ticker: Optional[str] = None,
    metric: Optional[str] = None,
    period_type: Optional[str] = None,
    include_excluded: bool = True,
    include_superseded: bool = False,
    db_path: Path = _DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """Read the series back, newest period first.

    The two consumers read this differently and the defaults say which is which:
      Phase M      — include_excluded=True (the DEFAULT). The full distribution,
                     negative periods included; that left tail is the point.
      anchor (H-3) — include_excluded=False. The MIN-of-medians read-time filter.

    period_type='FY' is the per-year series the schema addendum asks for — a query, not a
    separate build.
    """
    init_db(db_path)
    where, params = [], []
    if ticker:
        where.append("ticker=?")
        params.append(ticker.upper())
    if metric:
        where.append("metric=?")
        params.append(metric)
    if period_type:
        where.append("period_type=?")
        params.append(period_type)
    if not include_excluded:
        where.append("excluded=0")
    if not include_superseded:
        where.append("superseded=0")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with _conn(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM fundamental_series {clause} "
            f"ORDER BY ticker, metric, period_end DESC",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


# ── Phase L — lifecycle stage persistence ────────────────────────────────────

class OverrideRationaleMissing(ValueError):
    """An override was submitted without a rationale. Typed, and raised BEFORE the write.

    Order §4 makes the rationale mandatory under the same anti-launder mechanics as Phase
    M. A blank rationale is not a lesser override, it is an unexplained reclassification —
    which is the thing the override record exists to make impossible.
    """


def save_lifecycle_stage(result: Any, db_path: Path = _DEFAULT_DB) -> tuple:
    """Append one classification. Returns (stage_row_id, transition_row_id_or_None).

    APPEND, NEVER OVERWRITE, on the fundamental_series precedent. A transition row is
    written when the computed stage differs from this ticker's most recent computed stage;
    the FIRST classification of a ticker is not a transition (there is nothing to
    transition from) and writes no row.

    A STANDING OVERRIDE IS NEVER SILENTLY RECLASSIFIED (order §4). When one exists, the
    new computation is still recorded — suppressing it would hide the drift the re-review
    trigger exists to surface — and the transition row is stamped `overridden` with the
    approved stage, so the report says "computed moved, override still stands" rather than
    implying the ticker changed stage.

    Takes an explicit db_path from its caller: this is a writer, so the destination is
    named rather than defaulted (degraded-run write guard).
    """
    now = datetime.now(timezone.utc).isoformat()
    absent = ",".join(result.absent_legs) if result.absent_legs else None
    with _conn(db_path) as conn:
        prev = conn.execute(
            "SELECT id, computed_stage FROM lifecycle_stage "
            "WHERE ticker=? ORDER BY id DESC LIMIT 1",
            (result.ticker.upper(),),
        ).fetchone()

        cur = conn.execute(
            """INSERT INTO lifecycle_stage
               (ticker, computed_stage, rule_fired, lens, inputs_json, assertions_json,
                flags_json, absent_legs, inputs_incomplete, config_version, run_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (result.ticker.upper(), result.stage, result.rule_fired, result.lens,
             json.dumps(result.inputs, default=str),
             json.dumps([a.as_dict() for a in result.assertions]),
             json.dumps(result.flags), absent,
             1 if result.inputs_incomplete else 0,
             result.config_version, now),
        )
        stage_id = cur.lastrowid

        transition_id = None
        if prev is not None and prev["computed_stage"] != result.stage:
            standing = conn.execute(
                "SELECT approved_stage FROM lifecycle_overrides "
                "WHERE ticker=? ORDER BY id DESC LIMIT 1",
                (result.ticker.upper(),),
            ).fetchone()
            t = conn.execute(
                """INSERT INTO lifecycle_transitions
                   (ticker, from_stage, to_stage, from_stage_id, to_stage_id,
                    overridden, standing_override, detected_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (result.ticker.upper(), prev["computed_stage"], result.stage,
                 prev["id"], stage_id,
                 1 if standing is not None else 0,
                 standing["approved_stage"] if standing is not None else None, now),
            )
            transition_id = t.lastrowid
    return stage_id, transition_id


def save_lifecycle_override(
    ticker: str, computed_stage: str, approved_stage: str,
    rationale_text: Optional[str], db_path: Path = _DEFAULT_DB,
) -> int:
    """Record Vic's override. Raises OverrideRationaleMissing BEFORE any write.

    Validated ahead of the INSERT for the same reason DegradedRunWriteRefused and
    SupersedeLinkInvalid are: a refusal that has already written something is not a
    refusal.
    """
    if rationale_text is None or not str(rationale_text).strip():
        raise OverrideRationaleMissing(
            f"{ticker}: override {computed_stage} -> {approved_stage} refused — "
            f"a rationale is mandatory (order §4)")
    now = datetime.now(timezone.utc).isoformat()
    with _conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO lifecycle_overrides
               (ticker, computed_stage, approved_stage, rationale_text, created_at)
               VALUES (?,?,?,?,?)""",
            (ticker.upper(), computed_stage, approved_stage,
             str(rationale_text).strip(), now),
        )
        return cur.lastrowid


def get_standing_override(ticker: str, db_path: Path = _DEFAULT_DB) -> Optional[Dict]:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM lifecycle_overrides WHERE ticker=? ORDER BY id DESC LIMIT 1",
            (ticker.upper(),),
        ).fetchone()
    return dict(row) if row else None


def list_lifecycle_stages(
    ticker: Optional[str] = None, latest_only: bool = False,
    db_path: Path = _DEFAULT_DB,
) -> List[Dict]:
    with _conn(db_path) as conn:
        if latest_only:
            rows = conn.execute(
                "SELECT * FROM lifecycle_stage WHERE id IN "
                "(SELECT MAX(id) FROM lifecycle_stage GROUP BY ticker)"
                + (" AND ticker=?" if ticker else "") + " ORDER BY ticker",
                ((ticker.upper(),) if ticker else ()),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM lifecycle_stage"
                + (" WHERE ticker=?" if ticker else "")
                + " ORDER BY ticker, id DESC",
                ((ticker.upper(),) if ticker else ()),
            ).fetchall()
    return [dict(r) for r in rows]


def list_lifecycle_transitions(db_path: Path = _DEFAULT_DB) -> List[Dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM lifecycle_transitions ORDER BY detected_at DESC, id DESC"
        ).fetchall()
    return [dict(r) for r in rows]
