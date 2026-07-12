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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn(db_path: Path = _DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = _DEFAULT_DB) -> None:
    """Create tables if they don't exist."""
    with _conn(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker      TEXT    NOT NULL,
                run_at      TEXT    NOT NULL,
                lens        TEXT,
                status      TEXT    NOT NULL DEFAULT 'ok',   -- ok | failed
                error_msg   TEXT,
                pillars_json    TEXT,   -- JSON list of PillarResult dicts
                synthesis_json  TEXT,   -- JSON SynthesisOutput (raw dict)
                avg_score       REAL,
                overall_conf    TEXT,
                verdict_conf    TEXT,
                expected_return REAL
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
        """)


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
) -> int:
    """
    Persist a complete evaluation. Returns the new evaluation id.
    """
    init_db(db_path)

    avg_score = sum(p.score for p in pillars) / len(pillars) if pillars else None
    from adapters.base import _RANK, _LEVEL
    overall_conf = _LEVEL[min(_RANK[p.confidence] for p in pillars)] if pillars else "low"

    pillars_json = json.dumps([_pillar_to_dict(p) for p in pillars])
    synthesis_json = json.dumps(synthesis.rawJson) if synthesis else None
    verdict_conf = synthesis.verdictConfidence if synthesis else None
    # Use caller-computed E(R) (computed downstream from scenario targets, per spec).
    # Fall back to LLM-provided value only if no computed value was passed.
    if expected_return is None and synthesis is not None:
        expected_return = synthesis.expectedReturn

    with _conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO evaluations
              (ticker, run_at, lens, status, pillars_json, synthesis_json,
               avg_score, overall_conf, verdict_conf, expected_return)
            VALUES (?, ?, ?, 'ok', ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker, _utc_now(), lens,
                pillars_json, synthesis_json,
                avg_score, overall_conf, verdict_conf, expected_return,
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


def save_failed_evaluation(
    ticker: str,
    error_msg: str,
    db_path: Path = _DEFAULT_DB,
) -> int:
    """Record a failed evaluation so batch runs are fully auditable."""
    init_db(db_path)
    with _conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO evaluations (ticker, run_at, status, error_msg)
            VALUES (?, ?, 'failed', ?)
            """,
            (ticker, _utc_now(), error_msg[:2000]),
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
    """Return ok evaluations with expected_return that are not yet graded and old enough."""
    init_db(db_path)
    with _conn(db_path) as conn:
        rows = conn.execute(
            """SELECT e.* FROM evaluations e
               LEFT JOIN grades g ON g.evaluation_id = e.id
               WHERE e.status = 'ok'
                 AND e.expected_return IS NOT NULL
                 AND g.id IS NULL
                 AND julianday('now') - julianday(e.run_at) >= ?
               ORDER BY e.run_at ASC LIMIT 200""",
            (min_age_days,),
        ).fetchall()
    return [dict(r) for r in rows]
