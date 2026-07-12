"""
Anthropic API client for CALIBER synthesis.

Model: claude-sonnet-4-6 (per spec closed decisions).
Key: ANTHROPIC_API_KEY env var — never hardcoded, never logged.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

# Load .env so client.py works when imported directly (not via evaluate.py).
# override=False: shell environment always wins over file.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).parent.parent / ".env", override=False)
except ImportError:
    pass

from adapters.base import PillarResult
from adapters.yfinance_adapter import YFinanceData
from core.technicals import TechnicalOverlay
from synthesis.prompt import SYSTEM_PROMPT, build_user_message
from synthesis.schema import SynthesisOutput, parse_synthesis

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048


def run_synthesis(
    ticker: str,
    company_name: str,
    sector: str,
    industry: str,
    lens: str,
    pillars: List[PillarResult],
    tech: TechnicalOverlay,
    current_price: float | None,
) -> SynthesisOutput:
    """
    Call the Anthropic API and return a validated SynthesisOutput.
    Raises RuntimeError on missing key or API failure.
    Raises ValueError if the response fails schema validation after repair.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set.\n"
            "  Add it to caliber/.env  (see .env.example for the full list of keys).\n"
            "  The key is never printed or logged by CALIBER."
        )

    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)

    user_msg = build_user_message(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        lens=lens,
        pillars=pillars,
        tech=tech,
        current_price=current_price,
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as exc:
        raise RuntimeError(f"Anthropic API call failed: {exc}") from exc

    raw_text = response.content[0].text if response.content else ""
    if not raw_text:
        raise ValueError("Empty response from synthesis API")

    return parse_synthesis(raw_text, pillars, ticker)
