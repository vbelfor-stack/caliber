"""
Provenance primitives — the atom of CALIBER's reliability model.
Every data field carries {value, source, as_of, confidence}.
Anti-launder: pillar confidence = min(input confidences).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Literal, Optional

Confidence = Literal["high", "medium", "low"]
_RANK: dict[str, int] = {"high": 2, "medium": 1, "low": 0}
_LEVEL: list[str] = ["low", "medium", "high"]


@dataclass
class Prov:
    """A single data field with full provenance."""
    value: Any
    source: str
    as_of: Optional[str]       # ISO date string, or None if undated
    confidence: Confidence

    def is_missing(self) -> bool:
        if self.value is None:
            return True
        if isinstance(self.value, float) and math.isnan(self.value):
            return True
        return False

    def __repr__(self) -> str:
        v = f"{self.value:.4g}" if isinstance(self.value, float) else str(self.value)
        return f"Prov({v} | {self.source} | {self.as_of} | {self.confidence})"


def min_conf(*provs: Optional[Prov]) -> Confidence:
    """
    Anti-launder rule: return the minimum confidence across all material inputs.
    Missing/None fields are excluded from the computation (they degrade separately).
    """
    ranks = [
        _RANK[p.confidence]
        for p in provs
        if p is not None and not p.is_missing()
    ]
    if not ranks:
        return "low"
    return _LEVEL[min(ranks)]  # type: ignore[return-value]


def missing_prov(source: str, as_of: Optional[str] = None) -> Prov:
    """Canonical missing-value placeholder."""
    return Prov(value=None, source=source, as_of=as_of, confidence="low")


def coerce(val: Any) -> Any:
    """Convert NaN → None at ingestion boundary. Never let NaN propagate."""
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


TRAJECTORY_TAGS = ("accelerating", "peaking", "rolling_over", "troughing", "stable")


def derive_trajectory_tag(
    ttm_val: Optional[float],
    mrq_val: Optional[float],
    guided_val: Optional[float],
    threshold: float,
    low_level_threshold: Optional[float] = None,
) -> str:
    """
    Derive directional trajectory tag.

    INVARIANTS (hard-tested):
      - MRQ > TTM by >threshold → "accelerating" (NEVER "peaking")
      - MRQ < TTM by >threshold → "rolling_over" (NEVER "peaking")
      - "peaking" only fires when delta is within threshold AND guide signals retreat
    """
    if ttm_val is None or mrq_val is None:
        return "stable"

    delta = mrq_val - ttm_val

    if delta > threshold:
        # Accelerating momentum; only call peaking if guide signals immediate reversal
        if guided_val is not None and (guided_val - mrq_val) < -threshold:
            return "peaking"
        return "accelerating"

    elif delta < -threshold:
        # Declining momentum — rolling_over regardless of guided or absolute level
        return "rolling_over"

    else:
        # Stable delta zone: sub-classify from guide and absolute level
        if guided_val is not None:
            g_delta = guided_val - mrq_val
            if g_delta > threshold:
                return "accelerating"
            elif g_delta < -threshold:
                return "peaking"
        if low_level_threshold is not None and mrq_val < low_level_threshold:
            return "troughing"
        return "stable"


@dataclass
class TrajectoryPoint:
    """Temporal trajectory for one metric: TTM, MRQ, optional guidance."""
    ttm: "Prov"
    mrq: "Prov"
    guided_next_q: "Prov"
    tag: str             # accelerating | peaking | rolling_over | troughing | stable
    tag_confidence: "Confidence"


@dataclass
class PillarResult:
    """Output of a single pillar scorer."""
    name: str                     # "Business Quality", etc.
    score: int                    # 1–5
    confidence: Confidence        # anti-launder: min of material inputs
    rationale: str                # ≤220 chars
    flags: List[str]              # e.g. ["CYCLE-PEAK-MARGINS"]
    method: str                   # lens or scoring method used
    key_inputs: List[Prov] = field(default_factory=list)

    def __post_init__(self) -> None:
        assert 1 <= self.score <= 5, f"Score out of range: {self.score}"
        if len(self.rationale) > 220:
            self.rationale = self.rationale[:217] + "..."
