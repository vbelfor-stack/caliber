"""ETF / fund refusal guard — Vic ruling 2, 2026-08-28.

**NO ETF IS EVER SCORED AS A COMPANY.** Pointing the evaluator at a fund used to produce a
confident garbage classification — a lens picked from a fund's "sector", pillars scored on a
fund's balance sheet, an E(R) with a price target — rather than a refusal. The signal was
ALREADY IN THE PAYLOAD production fetches: FMP `profile` carries `isEtf`, verified live on
LYTE ("Roundhill Photonics & Optics ETF"). It was fetched and thrown away.

★ WHY THIS IS A CLASS GUARD AND NOT A TICKER LIST. LYTE and FLTW are held but were kept out
of `tickers.txt` specifically to route around this gap. That is a workaround maintained by
hand, and the day someone adds a fund to the universe the hand stops working. The guard reads
the issuer's own type from the feed, so it covers funds nobody has thought of yet.

★★ "ANY TRUE VALUE REFUSES" IS PARSED, NEVER TAKEN AS PYTHON TRUTHINESS. `bool("false")` is
**True**, so a feed that serves the string `"false"` would refuse every fund-shaped name it
was trying to clear. The accepted-true set is explicit and the accepted-false set is explicit;
anything else is UNKNOWN.

★ UNKNOWN DOES **NOT** REFUSE, AND THAT IS A DELIBERATE DEPARTURE FROM FAIL-CLOSED, STATED
RATHER THAN SMUGGLED. The standing discipline is that a guard which cannot measure denies
what it guards. Here denial would mean refusing every name whose payload lacks the key — which
is EVERY RECORDED FIXTURE (they predate this field) and every live name the moment FMP drops
it from a response. Vic's ruling is "any TRUE value refuses", and absence is not a true value.
The cost is bounded and named: this guard cannot catch a fund whose payload omits `isEtf`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

ETF_TYPED_REASON = "etf:not_a_company"

_TRUE = {"true", "1", "yes", "y", "t"}
_FALSE = {"false", "0", "no", "n", "f", ""}


def parse_is_etf(raw: Any) -> Optional[bool]:
    """Tri-state: True / False / None(UNKNOWN). Never Python truthiness — see module docstring."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw == 1:
            return True
        if raw == 0:
            return False
        return None
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in _TRUE:
            return True
        if v in _FALSE:
            return False
    return None


@dataclass(frozen=True)
class EtfRefusal:
    """A refusal to evaluate. `refused` False means this name may proceed."""
    refused: bool
    typed_reason: Optional[str] = None
    detail: Optional[str] = None


class EtfNotEvaluable(Exception):
    """Raised at an evaluation boundary. A REFUSAL, not a failure."""


def etf_refusal(yf: Any) -> EtfRefusal:
    """Should this name be refused as a fund? Reads ONLY the issuer's own `is_etf` flag.

    It owns no taxonomy: no name matching on "ETF"/"Fund"/"Trust" in the company name, no
    exchange rule, no ticker list. A name-substring rule would catch "Trust" in a REIT and
    "Fund" in an operating company, which is the `_CYCLICAL_INDUSTRY` keyword-sweep defect
    that put IONQ and INFQ on the wrong lens and forced the L-2b overrides.
    """
    flag = getattr(yf, "is_etf", None)
    if flag is True:
        name = getattr(yf, "name", None) or getattr(yf, "ticker", "?")
        return EtfRefusal(
            True, ETF_TYPED_REASON,
            f"{name} is a fund (`profile.isEtf` is true), not an operating company. "
            f"No lens, pillar, score or E(R) applies to it.")
    return EtfRefusal(False)
