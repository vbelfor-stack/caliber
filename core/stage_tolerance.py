"""§5.1 — stage-conditioned B-2 anchor-divergence tolerance. ARMED L-3, 2026-08-17.

THE ONE SCORING-PATH CONSUMER OF LIFECYCLE STAGE. Nothing else reads a stage until a future
order says so, and there is a pin asserting exactly that.

WHAT IT DOES. The B-2 guard compares the model's implied price anchor against the live price
and withholds E(R) past a threshold. A flat 15% treats a pre-earnings launch company and a
mature payments network as equally predictable, which they are not: wider dispersion is the
NORMAL state of a young name, so a flat band flags it as broken for behaving as expected.
The band therefore widens with stage — YOUNG 30%, HIGROWTH 20%, MATURE/DECLINE 15%.

**IT READS THE PERSISTED STAGE, NOT A FRESH CLASSIFICATION.** That is deliberate: the stage
table is exactly the calibration set §5 step 1 was armed to accumulate, and a tolerance
derived from a stage computed inside the same run would move with the run rather than with
the issuer.

FAIL SEMANTICS — RULED IN ADVANCE, AND THE DIRECTION IS THE WHOLE POINT.
A name with no stage row, or one whose stage is not a measurement, gets the DEFAULT (the
pre-B-2 15%), **NEVER the widest band**. Absence of classification must not buy a name the
30% tolerance, because that would make missing data privately optimal — a name nobody could
classify would become the hardest to flag. Same fail-closed philosophy as L-1e, applied to
scoring instead of to a tag.

WHAT COUNTS AS "NOT A MEASUREMENT" (Code's reading of the ruling's phrase "INPUTS-INCOMPLETE
-flagged to the point of unreliability" — stated explicitly so Vic can correct it):
  1. `INSUFFICIENT-HISTORY` — the stage is a DEFAULT the rules assign when fewer than two
     fiscal years exist, not something measured. DPC and INFQ read YOUNG this way; granting
     them a 30% band on one fiscal year is precisely the "missing data is optimal" failure.
  2. `INPUTS-INCOMPLETE-FEED-TRANSIENT` — the reading itself says distrust it.
PLAIN `INPUTS-INCOMPLETE` DOES **NOT** DISQUALIFY. Structural absence with a named cause is
honest measurement, and 24 of 28 names carry it; treating it as unreliable would make the
arming inert while pretending to be armed. The distinction lands where it should: RKLB, SPCX
and IONQ read YOUNG on a MEASURED negative operating margin and earn the wider band; DPC and
INFQ read YOUNG on an absence and do not.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional

from core.lifecycle import (FLAG_INPUTS_INCOMPLETE_FEED_TRANSIENT,
                            FLAG_INSUFFICIENT_HISTORY)
from core.lifecycle_config import B2_DIVERGENCE_TOLERANCE_BY_STAGE

# The pre-B-2 flat band. Kept here as the explicit fallback so the fail path is a NAMED
# value rather than "whatever synthesis.schema happens to hold".
DEFAULT_TOLERANCE = 0.15

# Flags that make a stage reading unusable for widening the band. See the module docstring.
_DISQUALIFYING_FLAGS = (FLAG_INSUFFICIENT_HISTORY, FLAG_INPUTS_INCOMPLETE_FEED_TRANSIENT)


class StageTolerance(NamedTuple):
    tolerance: float
    stage: Optional[str]
    reason: str

    @property
    def is_default(self) -> bool:
        return self.stage is None or self.tolerance == DEFAULT_TOLERANCE


def _latest_stage_row(db_path: Path, ticker: str) -> Optional[Dict[str, Any]]:
    p = Path(db_path)
    if not p.exists():
        return None
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        # ★ RETIRED ROWS ARE NOT READ (ruling 1, 2026-08-28). A stage retired as
        # model-inapplicable is INADMISSIBLE, not merely old, so it must not be reachable
        # by the newest-row query — otherwise "retired" would be a label with no
        # consequence, which is a belief rather than a guard. Falling through to `None`
        # lands the name on DEFAULT_TOLERANCE, never the widest, which is the standing
        # fail-closed direction.
        row = conn.execute(
            "SELECT computed_stage, flags_json FROM lifecycle_stage "
            "WHERE ticker=? AND retired_reason IS NULL ORDER BY id DESC LIMIT 1",
            (ticker.upper().strip(),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None                     # table absent — same as no classification
    finally:
        conn.close()
    return dict(row) if row else None


def tolerance_for(ticker: str, db_path: Path) -> StageTolerance:
    """The B-2 tolerance this ticker's stage earns, with the reason it was chosen.

    Returns the DEFAULT for anything unclassified or not measured — never the widest.
    """
    row = _latest_stage_row(db_path, ticker)
    if row is None:
        return StageTolerance(DEFAULT_TOLERANCE, None,
                              "no stage row — default band (absence never widens)")

    stage = row["computed_stage"]
    try:
        flags = set(json.loads(row["flags_json"] or "[]"))
    except (ValueError, TypeError):
        flags = set()

    disqualifying = [f for f in _DISQUALIFYING_FLAGS if f in flags]
    if disqualifying:
        return StageTolerance(
            DEFAULT_TOLERANCE, stage,
            f"stage {stage} is not a measurement ({', '.join(disqualifying)}) — "
            f"default band, because absence must not buy the wider one")

    band = B2_DIVERGENCE_TOLERANCE_BY_STAGE.get(stage)
    if band is None:
        return StageTolerance(DEFAULT_TOLERANCE, stage,
                              f"stage {stage} has no configured band — default")
    return StageTolerance(band, stage, f"stage {stage} band {band * 100:.0f}%")


def suppressed_by_widening(divergence: Optional[float], tolerance: float) -> bool:
    """True when the STAGE BAND is the only reason this divergence did not trip.

    L-4b TRIPWIRE (ruled 2026-08-20). The batch arm was landed with 9 of the 10 widened
    names unverified — no eval-date price exists for them, so the widening was reasoned,
    not measured. The widened band is the RISK DIRECTION: past 15% a name now needs 20%
    or 30% to trip, so a real defect on a YOUNG/HIGROWTH name can pass silently.

    This predicate names the exact event that would validate or indict the widening — a
    divergence in `(DEFAULT_TOLERANCE, tolerance]`, i.e. one flat-15 WOULD have caught.
    Same pattern as the D-5 BANK-RUNG-UNCALIBRATED tripwire: an uncalibrated rung stays
    OBSERVABLE until a real event lands on it. Until one does, the readout is the only
    thing standing between a widened band and a laundered E(R).

    Returns False for the default band, where widening cannot be the cause by definition.
    """
    if divergence is None or tolerance <= DEFAULT_TOLERANCE:
        return False
    return DEFAULT_TOLERANCE < divergence <= tolerance
