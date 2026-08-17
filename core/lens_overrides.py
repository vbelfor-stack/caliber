"""Explicit per-ticker lens overrides. Hand-curated, never inferred.

RULED 2026-08-17 (L-2b). When SIC and the vendor's industry string both put a name on the
wrong lens, the fix is an EXPLICIT PER-ISSUER OVERRIDE WITH A STATED REASON — not another
keyword in a sweep. This is the same precedent as SEC_TICKER_ALIASES and the peer-anchor
rejection: a curated list a human wrote and signed beats a heuristic that will mis-file the
next name nobody checked.

WHY NOT PATCH THE KEYWORD LIST: `"hardware"` is what put IONQ and INFQ on the cyclical lens,
via FMP's "Computer Hardware" / "Hardware, Equipment & Parts". Removing or narrowing the
keyword would silently move every other name it currently catches, including ones where it is
right (FN — optics components on the hyperscaler capex cycle — is defensibly cyclical and
STAYS). A sweep cannot be corrected for one name without moving the rest; an override can.

EVERY ENTRY CARRIES A RATIONALE AND IT IS ENFORCED AT IMPORT. An unexplained reclassification
is exactly what the override record exists to prevent — same mechanics as the Phase L stage
override, which refuses a blank rationale before writing anything.

PUNCH-LIST (recorded, not built): replace the `_CYCLICAL_INDUSTRY` keyword sweep with explicit
SIC entries as names accumulate. Keyword matching against a vendor's free-text industry string
is the mechanism that produced these overrides in the first place.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

# ticker -> (lens, rationale). RATIONALE IS MANDATORY AND NON-EMPTY.
LENS_OVERRIDES: Dict[str, Tuple[str, str]] = {
    "IONQ": (
        "growth",
        "Pre-earnings quantum computing. FMP industry 'Computer Hardware' matched the "
        "cyclical keyword sweep, but IonQ has no end-market cycle to normalise to — it has "
        "no earnings at all. The cyclical lens would normalise to mid-cycle earnings that "
        "do not exist and expose it to a peak/rollover gate on noise.",
    ),
    "INFQ": (
        "growth",
        "Pre-earnings quantum computing (Infleqtion). Same cause as IONQ — FMP industry "
        "'Hardware, Equipment & Parts' matched the cyclical keyword. Neither the mid-cycle "
        "normalisation nor the peak gate has anything to act on.",
    ),
    "BE": (
        "growth",
        "Bloom Energy. SIC 3620 (Electrical Industrial Apparatus) put it on the cyclical "
        "lens, but the demand driver is SECULAR data-centre power, not an industrial cycle. "
        "Project lumpiness is not an end-market cycle, and the specific exposure is that a "
        "future lumpy dip builds a decline streak and trips the peak gate on revenue "
        "recognition timing rather than on a downcycle.",
    ),
}

# Deliberately NOT overridden, recorded so the decisions are visible rather than implied:
#   FN    optics components on the hyperscaler capex cycle — cyclical is defensible, STAYS.
#   SPCX  reads `standard` from SEC's OWN SIC 7370 for a launch company. The classification
#         is the SEC's, not ours, and it is not overridden on judgement alone — flagged for
#         review once the D-3 panel has more standard-lens evidence.

for _t, _v in LENS_OVERRIDES.items():
    if not isinstance(_v, tuple) or len(_v) != 2:
        raise ValueError(f"lens override for {_t} must be (lens, rationale)")
    if not _v[1] or not str(_v[1]).strip():
        raise ValueError(
            f"lens override for {_t} has no rationale — an unexplained reclassification is "
            f"the thing this record exists to prevent")


def lens_override(ticker: Optional[str]) -> Optional[Tuple[str, str]]:
    """(lens, rationale) for an explicitly overridden ticker, else None."""
    if not ticker:
        return None
    return LENS_OVERRIDES.get(ticker.upper().strip())
