"""
Synthesis output schema: validation + tolerant JSON repair.

Repair pipeline (order matters):
  1. Strip markdown fences
  2. Strip trailing junk after last '}'
  3. Fix thousands separators in numbers (e.g. 1,234 → 1234)
  4. Close truncated JSON (append missing ']' / '}' as needed)
  5. Parse and validate against SynthesisOutput structure
  6. Reject silently-incomplete payloads (raise, never half-parse)

Anti-launder: if any load-bearing pillar confidence is "low",
verdictConfidence must be "low". Enforced here, not in the LLM.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from adapters.base import Confidence, _RANK, _LEVEL, PillarResult


# ── Scenario dataclass ────────────────────────────────────────────────────────

@dataclass
class Scenario:
    thesis: str
    points: List[str]
    probability: int       # integer 0-100
    priceTarget: Optional[float]


@dataclass
class ResearchItem:
    source: str
    tier: str              # "independent" | "sell-side" | "crowd"
    view: str
    conflicted: bool = False


@dataclass
class TechnicalsOut:
    trend: str
    above_ma50: Optional[bool]
    above_ma200: Optional[bool]
    rsi_14: Optional[float]
    volume_confirmation: Optional[bool]
    notes: str = ""


@dataclass
class SynthesisOutput:
    company: str
    ticker: str
    verdictConfidence: Confidence
    verdictReason: str
    expectedReturn: Optional[float]          # E(R) in %, computed downstream but may be present
    redFlags: List[str]
    bull: Scenario
    base: Scenario
    bear: Scenario
    research: List[ResearchItem]
    technicals: TechnicalsOut
    dataGaps: List[str]
    rawJson: Dict[str, Any] = field(default_factory=dict)   # preserved for debugging


# ── JSON repair ───────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` markdown fences."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


def _strip_trailing_junk(text: str) -> str:
    """Trim everything after the last closing brace."""
    idx = text.rfind("}")
    if idx == -1:
        return text
    return text[:idx + 1]


def _fix_thousands_separators(text: str) -> str:
    """
    Replace bare thousands-separator commas in numbers (e.g. 1,234 → 1234).
    Only fires when both sides of the comma are digits.
    """
    return re.sub(r"(\d),(\d{3})\b", r"\1\2", text)


def _close_truncated(text: str) -> str:
    """
    Append missing brackets/braces to make JSON parseable.
    Counts open vs closed delimiters; appends the deficit.
    """
    open_curly = text.count("{") - text.count("}")
    open_square = text.count("[") - text.count("]")
    # Close in reverse nesting order: first square, then curly
    text = text.rstrip().rstrip(",")
    text += "]" * max(0, open_square)
    text += "}" * max(0, open_curly)
    return text


def repair_json(raw: str) -> Dict[str, Any]:
    """
    Apply full repair pipeline. Returns parsed dict or raises ValueError.
    Never silently returns a partial/empty structure.
    """
    text = _strip_fences(raw)
    text = _fix_thousands_separators(text)
    text = _strip_trailing_junk(text)
    text = _close_truncated(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON repair failed: {exc}\nRepaired text (first 400 chars): {text[:400]}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at root, got {type(data).__name__}")
    return data


# ── Confidence enforcement (anti-launder) ─────────────────────────────────────

def enforced_verdict_confidence(
    pillars: List[PillarResult],
    llm_confidence: str,
) -> Confidence:
    """
    Anti-launder gate: verdictConfidence cannot exceed the minimum pillar confidence.
    If any pillar is 'low', verdict must be 'low'.
    """
    if not pillars:
        return "low"  # type: ignore[return-value]
    min_rank = min(_RANK[p.confidence] for p in pillars)
    min_allowed: Confidence = _LEVEL[min_rank]  # type: ignore[assignment]

    llm_rank = _RANK.get(llm_confidence, 0)
    final_rank = min(llm_rank, min_allowed if isinstance(min_allowed, int) else _RANK[min_allowed])
    # min_allowed is a string like "medium"
    allowed_rank = _RANK[min_allowed]
    final_rank = min(llm_rank, allowed_rank)
    return _LEVEL[final_rank]  # type: ignore[return-value]


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_scenario(d: Dict[str, Any], key: str) -> Scenario:
    s = d.get(key, {})
    if not isinstance(s, dict):
        raise ValueError(f"Scenario '{key}' must be a dict, got {type(s).__name__}")
    return Scenario(
        thesis=str(s.get("thesis", "")),
        points=[str(p) for p in s.get("points", [])],
        probability=int(s.get("probability", 0)),
        priceTarget=float(s["priceTarget"]) if s.get("priceTarget") is not None else None,
    )


def _parse_research(items: Any) -> List[ResearchItem]:
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(ResearchItem(
            source=str(item.get("source", "")),
            tier=str(item.get("tier", "unknown")),
            view=str(item.get("view", "")),
            conflicted=bool(item.get("conflicted", False)),
        ))
    return result


def _parse_technicals(d: Any) -> TechnicalsOut:
    if not isinstance(d, dict):
        return TechnicalsOut(trend="unknown", above_ma50=None, above_ma200=None, rsi_14=None, volume_confirmation=None)
    return TechnicalsOut(
        trend=str(d.get("trend", "unknown")),
        above_ma50=d.get("above_ma50"),
        above_ma200=d.get("above_ma200"),
        rsi_14=float(d["rsi_14"]) if d.get("rsi_14") is not None else None,
        volume_confirmation=d.get("volume_confirmation"),
        notes=str(d.get("notes", "")),
    )


def compute_er(
    synthesis: SynthesisOutput,
    current_price: float,
) -> Optional[float]:
    """
    Compute probability-weighted expected return from scenario price targets.
    E(R) % = Σ (p_i / 100) * ((target_i / price) - 1) * 100
           = Σ p_i * ((target_i / price) - 1)

    Returns None if current_price is zero or no scenarios have price targets.
    """
    if not current_price or current_price <= 0:
        return None
    total_er = 0.0
    total_prob = 0
    for sc in (synthesis.bull, synthesis.base, synthesis.bear):
        if sc.priceTarget is not None and sc.probability > 0:
            ret = (sc.priceTarget / current_price) - 1.0
            total_er += sc.probability * ret
            total_prob += sc.probability
    if total_prob == 0:
        return None
    # Normalise if probabilities don't sum to exactly 100
    return (total_er / total_prob) * 100.0


def per_scenario_returns(
    synthesis: SynthesisOutput,
    current_price: float,
) -> dict:
    """Returns {bull_ret, base_ret, bear_ret} as percentage floats, or None per missing target."""
    if not current_price or current_price <= 0:
        return {}
    result = {}
    for name, sc in [("bull", synthesis.bull), ("base", synthesis.base), ("bear", synthesis.bear)]:
        if sc.priceTarget is not None:
            result[name] = ((sc.priceTarget / current_price) - 1.0) * 100.0
        else:
            result[name] = None
    return result


def parse_synthesis(
    raw: str,
    pillars: List[PillarResult],
    ticker: str,
) -> SynthesisOutput:
    """
    Full parse + validate pipeline.
    Raises ValueError on unrecoverable payload.
    Anti-launder is enforced here (not delegated to LLM).
    """
    data = repair_json(raw)

    # Required top-level fields
    for required in ("scenarios", "verdictConfidence"):
        if required not in data:
            raise ValueError(f"Missing required field '{required}' in synthesis output")

    scenarios = data.get("scenarios", {})
    if not isinstance(scenarios, dict):
        raise ValueError("'scenarios' must be a dict")
    for sc_key in ("bull", "base", "bear"):
        if sc_key not in scenarios:
            raise ValueError(f"Missing scenario '{sc_key}'")

    llm_conf = str(data.get("verdictConfidence", "low"))
    enforced_conf = enforced_verdict_confidence(pillars, llm_conf)

    prob_sum = sum(
        int(scenarios.get(k, {}).get("probability", 0))
        for k in ("bull", "base", "bear")
        if isinstance(scenarios.get(k), dict)
    )
    if not (85 <= prob_sum <= 115):
        raise ValueError(f"Scenario probabilities sum to {prob_sum}, expected ~100")

    return SynthesisOutput(
        company=str(data.get("company", ticker)),
        ticker=ticker,
        verdictConfidence=enforced_conf,
        verdictReason=str(data.get("verdictReason", "")),
        expectedReturn=float(data["expectedReturn"]) if data.get("expectedReturn") is not None else None,
        redFlags=[str(f) for f in data.get("redFlags", [])],
        bull=_parse_scenario(scenarios, "bull"),
        base=_parse_scenario(scenarios, "base"),
        bear=_parse_scenario(scenarios, "bear"),
        research=_parse_research(data.get("research", [])),
        technicals=_parse_technicals(data.get("technicals", {})),
        dataGaps=[str(g) for g in data.get("dataGaps", [])],
        rawJson=data,
    )
