"""Recompute-on-detect, halt-and-report — Vic's ruling 2, 2026-08-28.

    "STAGE FRESHNESS: RECOMPUTE, LOUD. Any name whose series is newer than its stored
     stage triggers recompute-on-detect. The run HALTS and reports: name, old stage → new
     stage, band consequence (e.g. 15% → 30%). NOTHING persists until Vic approves per
     name. No silent stage flips, ever."   — Vic, 2026-08-28

WHY THIS EXISTS, IN ONE MEASUREMENT. Citigroup's stored `lifecycle_stage` rows are dated
2026-08-17 and read MATURE. Its `fundamental_series` rows were first observed 2026-08-21,
and its last three FY FCF are all negative, so the classifier now returns YOUNG on
`rule2_young` — fired on a MEASURED leg, not an absence, so it is not denied the wider band.
Stage drives the B-2 anchor-divergence tolerance, so the next evaluation would have moved a
~$200B bank from a 15% band to a 30% band, silently, as a side effect of a coverage order
run four days earlier. Nobody would have looked.

★ AND C IS NOT SPECIAL — THAT IS THE POINT OF THE RULING. Measured across the universe on
2026-08-28: **every single stage row in the table predates its own inputs.** All 44 were
written 2026-08-17; L-4c/L-4d/L-4f/L-4d.1 then wrote series for 16 names on 21–22 August.
Nothing in the system recomputes a stage when its inputs change. C is merely the one name
where the gap happens to flip a RULE rather than reproduce the same answer.

★★ THE STALENESS SIGNAL IS *NOT* "ANY NEWER ROW", AND THE NAIVE VERSION IS ALREADY WRONG.
Taking `max(first_observed)` over every row in `fundamental_series` flags 19 of 28 — but
JPM, SKHY and USB appear in that 19 ONLY because of the currency-block and class-flag rows
written on 2026-08-28, which carry `value=NULL` and a `period_type` the classifier cannot
read. **A row the classifier cannot read cannot change a stage**, so counting it as
staleness would raise three false halts on the first run and teach the next session to
distrust the guard. The signal here is therefore exactly what `evaluate.py` feeds
`build_legs`: `period_type='FY'`, `value IS NOT NULL`, `metric IN ('fcf',
'sales_to_capital')`.

THE APPROVAL CHANNEL IS `stage_flip_approvals`, NOT `lifecycle_overrides`. An override says
"the approved stage REPLACES the computed one" — a disagreement with the classifier. An
approval says "the classifier is right and MAY WRITE" — consent to persist. Folding one into
the other would make every approval silently pin a standing override on the name.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# The metrics `evaluate._fy_series_from_db` actually feeds the classifier. Named here so
# the coupling is greppable from both ends: if a third leg is ever wired into `build_legs`,
# this tuple is the thing that must move with it, or the guard goes quietly blind to it.
CLASSIFIER_INPUT_METRICS = ("fcf", "sales_to_capital")

REASON_SERIES_NEWER = "series_newer_than_stage"


class StageFlipRequiresApproval(Exception):
    """Typed halt. Raised at the stage-WRITE boundary, never at the compute boundary.

    Sibling of DegradedRunWriteRefused, AnchorPriceDivergence, RateUnavailable and
    PriceUnavailable — raised loud at the point of detection, converted to an honest
    persisted status or a distinct exit code at the boundary.

    RAISED BEFORE ANY WRITE, deliberately: a refusal that has already written something is
    not a refusal.
    """


@dataclass(frozen=True)
class Freshness:
    ticker: str
    stage_run_at: Optional[str]
    newest_readable_row: Optional[str]

    @property
    def is_stale(self) -> bool:
        """True when a row the classifier CAN read arrived after the stage was computed.

        Both absences mean NOT STALE, and for different reasons worth separating:
          * no stage row  — there is nothing to be stale relative to; the first
            classification is not a flip and needs no approval.
          * no readable row — the classifier's inputs have not changed, whatever else has.
        """
        if not self.stage_run_at or not self.newest_readable_row:
            return False
        return self.newest_readable_row > self.stage_run_at


def freshness_for(db_path: Path, ticker: str) -> Freshness:
    """READ-ONLY. Compare the newest CLASSIFIER-READABLE row against the stored stage."""
    t = ticker.upper().strip()
    p = Path(db_path)
    if not p.exists():
        return Freshness(t, None, None)
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        stage = conn.execute(
            "SELECT MAX(run_at) AS ra FROM lifecycle_stage "
            "WHERE ticker=? AND retired_reason IS NULL",
            (t,),
        ).fetchone()
        placeholders = ",".join("?" * len(CLASSIFIER_INPUT_METRICS))
        series = conn.execute(
            f"SELECT MAX(first_observed) AS fo FROM fundamental_series "
            f"WHERE ticker=? AND superseded=0 AND period_type='FY' "
            f"AND value IS NOT NULL AND metric IN ({placeholders})",
            (t, *CLASSIFIER_INPUT_METRICS),
        ).fetchone()
    except sqlite3.OperationalError:
        return Freshness(t, None, None)          # table absent — nothing to compare
    finally:
        conn.close()
    return Freshness(t, stage["ra"] if stage else None,
                     series["fo"] if series else None)


def band_consequence(db_path: Path, old_stage: Optional[str],
                     new_stage: Optional[str]) -> str:
    """"15% → 30%" — the sentence Vic's ruling asks the halt to print.

    The band is the reason this rule exists at all: without it a stage flip is an
    annotation, and an annotation nobody reads is not worth halting a run over. With it,
    the flip silently re-tunes the one guard standing between a bad E(R) and the database.
    """
    from core.lifecycle_config import B2_DIVERGENCE_TOLERANCE_BY_STAGE
    from core.stage_tolerance import DEFAULT_TOLERANCE

    def band(stage: Optional[str]) -> float:
        if stage is None:
            return DEFAULT_TOLERANCE
        return B2_DIVERGENCE_TOLERANCE_BY_STAGE.get(stage, DEFAULT_TOLERANCE)

    o, n = band(old_stage), band(new_stage)
    arrow = f"{o * 100:.0f}% → {n * 100:.0f}%"
    if o == n:
        return f"{arrow} (unchanged)"
    direction = "WIDER — the risk direction" if n > o else "tighter"
    return f"{arrow}  [{direction}]"


def stored_stage(db_path: Path, ticker: str) -> Optional[str]:
    """The newest LIVE (non-retired) computed stage, or None."""
    from core.stage_tolerance import _latest_stage_row
    row = _latest_stage_row(db_path, ticker)
    return row["computed_stage"] if row else None


def guard_stage_write(db_path: Path, ticker: str, new_stage: str,
                      rule_fired: str = "") -> None:
    """HALT unless this stage write is safe or approved. Call BEFORE persisting.

    Four outcomes, and only the last one raises:

      not stale            the classifier's inputs have not moved — write freely.
      stale, same stage    the recompute REPRODUCED the stored answer. Nothing flips, so
                           there is nothing to approve. Writing is safe and the refreshed
                           row is worth having.
      stale, flipped, APPROVED   Vic has consented to this exact transition. Write.
      stale, flipped, unapproved  -> StageFlipRequiresApproval. NOTHING PERSISTS.

    A first-ever classification never raises: `is_stale` is False without a stage row, so
    onboarding a new name is not gated behind an approval for a flip that did not happen.
    """
    from store.models import get_stage_flip_approval

    fresh = freshness_for(db_path, ticker)
    if not fresh.is_stale:
        return
    old = stored_stage(db_path, ticker)
    if old is None or old == new_stage:
        return
    if get_stage_flip_approval(ticker, old, new_stage, db_path=db_path) is not None:
        return

    raise StageFlipRequiresApproval(
        f"{ticker}: STAGE FLIP DETECTED AND NOT APPROVED — nothing persisted.\n"
        f"    stored stage      : {old}\n"
        f"    recomputed stage  : {new_stage}"
        f"{f' ({rule_fired})' if rule_fired else ''}\n"
        f"    band consequence  : {band_consequence(db_path, old, new_stage)}\n"
        f"    why it recomputed : the series moved after the stage was computed —\n"
        f"                        stage written {fresh.stage_run_at}\n"
        f"                        newest classifier-readable row "
        f"{fresh.newest_readable_row}\n"
        f"    NO SILENT STAGE FLIPS (Vic, 2026-08-28). Approve this exact transition "
        f"before it can be written."
    )
