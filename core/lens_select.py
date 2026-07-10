"""
Sector-adaptive lens selector — ethos rule 3.
Lens is selected per company and DISPLAYED in the output.

Hard assertions (golden tests):
  MU  → "cyclical"    (SIC 3674, industry "Semiconductors")
  V   → "compounder"  (industry "Credit Services") — NOT "bank"
  GOOG→ "compounder"  — NOT "growth" (Rule-of-40 wrong); NOT "standard" (mega-cap ad platform = asset-light compounder)
  NOW → "growth"      (SaaS/software; yfinance industry = "Software - Application" with regular dash)
  WU  → "compounder"  (payment/transfer network, asset-light; high FCF yield may reflect secular decline)

Lens types:
  growth     — Rule of 40/60, EV/S vs growth, FCF margin
  cyclical   — normalize to MID-CYCLE earnings; low P/E at peak = SELL signal
  bank       — P/TBV, P/FFO (banks, insurers, REITs)
  compounder — FCF yield, EV/EBITDA, growth durability (asset-light financial networks)
  standard   — EV/EBITDA, P/E, FCF yield (default)
"""
from __future__ import annotations

from typing import Optional

# ── keyword lists (all lowercase for case-insensitive matching) ──────────────

# Asset-light financial networks + mega-cap ad platforms — check BEFORE general financial sector
# V (Visa) must match "credit services"; GOOG must match "internet content" here.
_COMPOUNDER_INDUSTRY = [
    "credit services",
    "payment",
    "financial exchanges",
    "capital markets",
    "financial data",
    "financial markets",
    "asset management",
    "investment management",
    "rating",              # ratings agencies
    "internet content",    # GOOG (Alphabet): asset-light ad platform, massive FCF; NOT Rule-of-40
    "internet software",   # catch related mega-cap internet variants
]
_COMPOUNDER_SECTOR: list[str] = []  # sector alone is insufficient for compounder

# Cyclical: semis, memory, hardware, materials, energy
# MU (Micron) must match "semiconductor" here.
_CYCLICAL_INDUSTRY = [
    "semiconductor",
    "memory",
    "chip",
    "electronic component",
    "electronic equipment",
    "hardware",
    "steel",
    "aluminum",
    "copper",
    "chemical",
    "mining",
    "oil",
    "gas",
    "coal",
    "commodity",
    "auto",
]
# SIC ranges that map to cyclical (semiconductors: 3674)
_CYCLICAL_SIC_RANGES = [
    (2600, 2700),   # paper / packaging
    (2800, 2900),   # chemicals
    (3300, 3500),   # metals / fabricated metals
    (3600, 3700),   # electronic equipment (3674 = semiconductors)
    (1000, 1500),   # mining
    (2900, 3000),   # petroleum refining
]

# Banks / insurers / REITs
_BANK_INDUSTRY = [
    "bank",
    "banking",
    "savings",
    "mortgage",
    "insurance",
    "life insurance",
    "property & casualty",
    "reinsurance",
    "reit",
    "real estate investment trust",
]
_BANK_SIC_RANGES = [
    (6000, 6300),   # depository institutions, credit agencies
    (6300, 6400),   # insurance
    (6500, 6600),   # real estate (REITs)
]

# Software / high-growth SaaS — Rule of 40 framing
# GOOG must NOT match this; its industry is "Internet Content & Information"
# yfinance returns "Software - Application" (space-dash-space), NOT em-dash.
_GROWTH_INDUSTRY = [
    "software—application",     # em-dash (canonical)
    "software - application",   # yfinance actual output: "Software - Application"
    "software—infrastructure",
    "software - infrastructure", # yfinance actual output
    "software infrastructure",
    "software application",
    "saas",
    "cloud computing",
    "application software",
    "prepackaged software",      # SIC 7372 industry description
    "information technology services",  # careful — excludes GOOG
]
# Additional guard: exclude if sector is "Communication Services"
# (catches GOOG-like mega-caps that are NOT pure SaaS)
_GROWTH_EXCLUDED_SECTORS = ["communication services"]


def select_lens(
    sector: Optional[str],
    industry: Optional[str],
    sic: Optional[str] = None,
) -> str:
    """
    Return one of: "growth", "cyclical", "bank", "compounder", "standard".
    Checks are ordered; first match wins.
    """
    s = (sector or "").lower().strip()
    i = (industry or "").lower().strip()

    # 1. Asset-light compounder (must precede general financial check)
    if any(kw in i for kw in _COMPOUNDER_INDUSTRY):
        return "compounder"

    # 2. Cyclical — industry keywords
    if any(kw in i for kw in _CYCLICAL_INDUSTRY):
        return "cyclical"

    # 3. Cyclical — SIC range
    if sic:
        try:
            sic_int = int(str(sic).split(".")[0])
            for lo, hi in _CYCLICAL_SIC_RANGES:
                if lo <= sic_int < hi:
                    return "cyclical"
        except (ValueError, TypeError):
            pass

    # 4. Bank / insurer / REIT — industry keywords
    if any(kw in i for kw in _BANK_INDUSTRY):
        return "bank"

    # 5. Bank — SIC range
    if sic:
        try:
            sic_int = int(str(sic).split(".")[0])
            for lo, hi in _BANK_SIC_RANGES:
                if lo <= sic_int < hi:
                    return "bank"
        except (ValueError, TypeError):
            pass

    # 6. Software / high-growth SaaS
    #    Guard: exclude Communication Services sector (GOOG, META, etc.)
    if s not in _GROWTH_EXCLUDED_SECTORS:
        if any(kw in i for kw in _GROWTH_INDUSTRY):
            return "growth"

    # 7. Default
    return "standard"


LENS_LABELS = {
    "growth": "GROWTH / RULE-OF-40",
    "cyclical": "CYCLICAL / MID-CYCLE",
    "bank": "BANK / INSURER / REIT",
    "compounder": "QUALITY COMPOUNDER",
    "standard": "STANDARD",
}


def lens_label(lens: str) -> str:
    return LENS_LABELS.get(lens, lens.upper())
