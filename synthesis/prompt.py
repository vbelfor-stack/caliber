"""
Synthesis system prompt and user-message builder.
The LLM receives measured pillar data as structured context;
it does NOT re-research fundamentals — it researches only qualitative color.
"""
from __future__ import annotations

import json
from typing import List

from adapters.base import PillarResult
from adapters.yfinance_adapter import YFinanceData
from core.technicals import TechnicalOverlay

SYSTEM_PROMPT = """\
You are the synthesis engine inside CALIBER. You receive measured pillar data \
with provenance and confidence. Your job: produce bull/base/bear scenarios with \
probabilities and price targets, red flags, research tiering, and a verdict whose \
confidence NEVER exceeds its softest load-bearing input.

Rules:
- Never invent a number, source, or analyst view. Unverified attribution → omit. \
"No reputable independent coverage found" is a valid output.
- Value trap is emergent: construct it only if the provided data shows cheap + solvent + no growth.
- Respect the provided valuation lens; if data shows a cyclical near peak margins with a low \
multiple, say the multiple is a sell signal.
- For growth/SaaS lens: the bear thesis MUST address the risk of agentic-AI commoditization \
(AI agents reducing seat-based SaaS stickiness and expansion potential) and multiple compression \
from elevated rates. If this disruption question is material and unresolved, verdictConfidence \
must not be high — this is the anti-launder rule applied to qualitative uncertainty.
- Output ONLY valid JSON per the schema below. Numbers as bare digits (no commas, \
symbols, or units). null for unknown. Terse: rationales <220 chars. \
Probabilities for bull+base+bear must sum to ~100; each scenario carries a priceTarget.

Required JSON schema:
{
  "company": "string",
  "verdictConfidence": "high|medium|low",
  "verdictReason": "string <220 chars",
  "expectedReturn": null_or_number,
  "redFlags": ["string", ...],
  "scenarios": {
    "bull":  {"thesis": "string", "points": ["..."], "probability": int, "priceTarget": number_or_null},
    "base":  {"thesis": "string", "points": ["..."], "probability": int, "priceTarget": number_or_null},
    "bear":  {"thesis": "string", "points": ["..."], "probability": int, "priceTarget": number_or_null}
  },
  "research": [
    {"source": "string", "tier": "independent|sell-side|crowd", "view": "string", "conflicted": bool}
  ],
  "technicals": {
    "trend": "string", "above_ma50": bool_or_null, "above_ma200": bool_or_null,
    "rsi_14": number_or_null, "volume_confirmation": bool_or_null, "notes": "string"
  },
  "dataGaps": ["string", ...]
}
"""


def _pillar_dict(p: PillarResult) -> dict:
    return {
        "name": p.name,
        "score": p.score,
        "confidence": p.confidence,
        "rationale": p.rationale,
        "flags": p.flags,
        "method": p.method,
    }


def _tech_dict(tech: TechnicalOverlay) -> dict:
    return {
        "trend": tech.trend,
        "above_ma50": tech.above_ma50,
        "above_ma200": tech.above_ma200,
        "rsi_14": tech.rsi_14,
        "volume_confirmation": tech.volume_confirmation,
        "data_rows": tech.data_rows,
        "notes": tech.notes,
    }


def build_user_message(
    ticker: str,
    company_name: str,
    sector: str,
    industry: str,
    lens: str,
    pillars: List[PillarResult],
    tech: TechnicalOverlay,
    current_price: float | None,
) -> str:
    """
    Build the structured user message injected alongside the system prompt.
    The LLM receives all deterministic data here; it only adds qualitative color.
    """
    payload = {
        "ticker": ticker,
        "company": company_name,
        "sector": sector,
        "industry": industry,
        "valuation_lens": lens,
        "current_price": current_price,
        "pillars": [_pillar_dict(p) for p in pillars],
        "all_flags": [f for p in pillars for f in p.flags],
        "technicals": _tech_dict(tech),
        "instruction": (
            "Produce the full synthesis JSON. Use only the data above for pillar claims. "
            "You may add qualitative context (news, analyst views, filings themes) from your "
            "training knowledge but clearly mark anything beyond the provided data. "
            "Value trap: only construct if cheap + solvent + no growth align above. "
            "Probabilities must sum to ~100."
        ),
    }
    return json.dumps(payload, indent=2)
