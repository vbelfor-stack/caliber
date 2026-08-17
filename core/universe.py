"""Held universe vs calibration universe — the one place membership is decided.

RULED 2026-08-17. The D-5/D-6 ruling says the four banks (JPM/BK/USB/C) are CALIBRATION
INSTRUMENTS, NEVER HOLDINGS. That ruling governs WHAT VIC BUYS, not what the system is
allowed to learn from: a bank E(R) graded in 90 days is evidence about the BANK LENS, which
is the newest and least-proven lens, and excluding the only four names that exercise it
would leave D-6 permanently ungradeable.

So calibration names ARE graded, and the flag exists so the two populations can be sliced
apart. A BLENDED ACCURACY NUMBER WOULD MISLEAD IN BOTH DIRECTIONS — it would let a
calibration instrument's miss discredit the held universe, and let held-universe hits
flatter an unproven lens.

THE FIREWALL IS AT THE RECOMMENDATION LAYER, NOT THE GRADING LAYER. Grading admits
everything; nothing that ranks or recommends holdings may show a calibration name.

`tickers.txt` is the sole source of truth for the held universe (it already is for scheduled
runs). Membership is resolved AT WRITE TIME and stored on the row, not re-derived at read
time: the file changes as the portfolio changes, and a grade rollup six months from now must
know what the name was WHEN IT WAS EVALUATED, not what it is when the query runs.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

_ROOT = Path(__file__).parent.parent
DEFAULT_UNIVERSE = _ROOT / "tickers.txt"


def held_universe(path: Optional[Path] = None) -> List[str]:
    """Upper-cased tickers from the universe file. Comments and blanks ignored."""
    p = Path(path) if path is not None else DEFAULT_UNIVERSE
    if not p.exists():
        return []
    out: List[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line.upper())
    return out


def is_calibration_instrument(ticker: str, path: Optional[Path] = None) -> bool:
    """True when `ticker` is NOT in the held universe.

    FAILS TOWARD 'CALIBRATION' BY CONSTRUCTION: anything not explicitly listed as held is
    treated as a calibration instrument. That is the protective direction — the consequence
    of the flag is exclusion from anything that recommends holdings, so a mistake here
    withholds a recommendation rather than manufacturing one. A missing or empty universe
    file therefore marks EVERYTHING calibration, which is loud in the reports and cannot
    quietly promote a name.
    """
    return ticker.upper().strip() not in set(held_universe(path))
