"""The FCF-model applicability CLASS — ruled by Vic 2026-08-28.

WHAT THIS IS. One predicate: may the FCF engine produce numbers for this issuer at all?
For banks, insurers and diversified financials the answer is no, and it is no for a reason
that has nothing to do with data coverage.

    "FCF-model inapplicability is a CLASS, not a per-ticker call. Names whose FMP
     sector/industry marks them as banks/insurers/diversified financials are flagged
     model-inapplicable: fetchable, stored, typed flag row, NO numeric scores from the FCF
     engine. JPM and USB resolve under this class."   — Vic, 2026-08-28

WHY A CLASS AND NOT A COVERAGE PROBLEM. Free cash flow is `operating cash flow − capex`,
and that expression assumes the operating cash flow measures OPERATIONS while capex measures
REINVESTMENT IN OPERATIONS. For a bank, "operating cash flow" is dominated by movements in
the loan book, trading inventory and deposits — balance-sheet financing that has no bearing
on whether the franchise generates cash — and capex is a rounding error. The arithmetic runs
fine and the answer means nothing. C is the worked example and it is not subtle: its stored
FY FCF reads −$80.0B (2023), −$26.2B (2024), −$74.2B (2025), which under the R2 lifecycle
signal is the shape of a PRE-EARNINGS company. Citigroup is not pre-earnings. The model is
being asked a question it cannot answer, and the honest response is to decline rather than
to keep improving the inputs.

★ THE DISTINCTION THIS CLASS TURNS ON IS *INDUSTRY*, NOT *SECTOR*, AND THAT IS LOAD-BEARING.
Measured over all 28 evaluated names on 2026-08-28: SIX are FMP sector "Financial Services"
— BK, C, JPM, USB, **V and WU**. V and WU are industry "Financial - Credit Services":
asset-light payment networks with large positive FCF, both scored on the COMPOUNDER lens,
both currently covered in `fundamental_series`. A sector-level rule would have swept them in
and destroyed working coverage on two names to enforce a class neither belongs to. Vic's
wording is "banks/insurers/diversified financials", not "the Financial Services sector".

★ THIS MODULE OWNS NO TAXONOMY OF ITS OWN, DELIBERATELY. The decision is delegated to
`core.lens_select.select_lens`, which ALREADY encodes banks/insurers/REITs in
`_BANK_INDUSTRY` and already checks `_COMPOUNDER_INDUSTRY` FIRST — that ordering is exactly
what keeps V and WU out, and it has been pinned by the golden tests since Phase 0. A second
keyword list here would be duplicate logic in the project's precise sense: two encodings of
one judgement, free to drift, with nothing to say which is authoritative when they disagree.

Two arguments to `select_lens` are pinned OFF, and each is its own small ruling:

  sic=None      Vic said FMP sector/industry. SIC comes from EDGAR, and under the
                FMP-is-the-source doctrine EDGAR is the arbiter, not a pipeline input.
                EDGAR is already score-bearing on every run through four unruled paths
                (the doctrine's open pre-flight item); this class will not become a fifth.

  ticker=None   Vic said "a CLASS, not a per-ticker call". `select_lens` consults the
                hand-curated `lens_overrides` list when given a ticker, and admitting it
                would reintroduce exactly the per-issuer judgement the ruling removes.
                Measured 2026-08-28: no override in the list would change the caught set
                today, so this costs nothing now and holds the line later.

WHAT "NO NUMERIC SCORES" MEANS HERE, PRECISELY. This module is a predicate; it withholds
nothing by itself. The enforcement points are named by the callers that consult it —
`build_fcf_series` (refuses to compute a series) and, through it, `own_history_fcf_yields`
(refuses the panel's FCF-yield own-history anchor). A rule recorded without naming its
enforcement point is a belief, not a guard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.lens_select import select_lens

# The class name, and the typed reason stamped on anything it blocks. `field:code` shape,
# matching `withheld_reason()` in core.fundamental_series, so a consumer parsing withholding
# reasons does not need a second format.
CLASS_FINANCIALS = "financials"
REASON_MODEL_INAPPLICABLE = "model_inapplicable"

# The date Vic ruled the class into existence. Used as the `period_end` of the stored flag
# row, because a class membership is not a period and needs a stable key: stamping the RUN
# date would mint a fresh row every day and grow without bound, while stamping the RULING
# date is idempotent — a re-run touches `last_confirmed` and nothing else. If the class is
# ever re-ruled, the new date makes a NEW row and the old one survives beside it, which is
# the append-never-overwrite contract applied to a decision rather than to a measurement.
CLASS_RULED_ON = "2026-08-28"

# The lens whose membership defines the class. Named rather than inlined so that the
# coupling to `select_lens` is greppable from both ends.
_INAPPLICABLE_LENS = "bank"


@dataclass(frozen=True)
class Applicability:
    """Whether the FCF engine may produce numbers for this issuer, and why not.

    `class_name` is None when the model APPLIES — there is no "applicable" class, only the
    absence of an inapplicable one. Keeping it None rather than inventing a
    `"general"` label means a consumer cannot accidentally branch on a class that was never
    ruled into existence.
    """
    applicable: bool
    class_name: Optional[str] = None
    reason: Optional[str] = None
    detail: Optional[str] = None

    @property
    def typed_reason(self) -> Optional[str]:
        """`fcf:model_inapplicable:financials`, or None when the model applies."""
        if self.applicable:
            return None
        return f"fcf:{self.reason}:{self.class_name}"


APPLICABLE = Applicability(applicable=True)


def fcf_model_applicability(sector: Optional[str],
                            industry: Optional[str]) -> Applicability:
    """Is the FCF model applicable to an issuer with this FMP sector/industry?

    PURE. Takes the two vendor strings and nothing else — no ticker, no SIC, no fetch. That
    signature IS the ruling: a class decided from anything per-issuer would not be a class.

    An issuer with no sector/industry at all is APPLICABLE, and that direction is chosen
    rather than inherited. The fail-closed rule says a guard that cannot measure denies the
    tag it guards; the tag here is the BLOCK, so denying it on absent evidence is the
    protective direction. The alternative — blocking every name whose profile lookup
    flaked — would silently withhold FCF from the whole universe on one bad fetch, which is
    a far worse failure than letting one unclassified bank through to a series that is then
    visibly nonsensical.
    """
    if select_lens(sector, industry, None, None) != _INAPPLICABLE_LENS:
        return APPLICABLE
    return Applicability(
        applicable=False,
        class_name=CLASS_FINANCIALS,
        reason=REASON_MODEL_INAPPLICABLE,
        detail=(f"FMP sector={sector!r} industry={industry!r} classifies as "
                f"{_INAPPLICABLE_LENS} — banks, insurers and diversified financials have no "
                f"meaningful free-cash-flow reading: operating cash flow is dominated by "
                f"balance-sheet financing and capex is immaterial, so `ocf - capex` computes "
                f"cleanly and measures nothing. RULED A CLASS by Vic 2026-08-28; not a "
                f"coverage gap and not fixable with better inputs."),
    )


def applicability_for(ticker_data: object) -> Applicability:
    """Convenience over anything carrying `.sector` and `.industry` (i.e. TickerData).

    Reads the attributes defensively: a caller holding a fixture-loaded or partially built
    object must get APPLICABLE rather than an AttributeError, for the same reason the
    missing-profile case above is applicable — a crash on this path would take down an
    evaluation over a classification question.
    """
    return fcf_model_applicability(getattr(ticker_data, "sector", None),
                                   getattr(ticker_data, "industry", None))
