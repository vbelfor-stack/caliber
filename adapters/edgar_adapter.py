"""
EDGAR adapter — direct HTTPS to SEC.gov.
Provides: SIC code (for lens classification), latest 10-K/10-Q filing metadata,
Risk Factors + MD&A excerpts (bear evidence, highest confidence tier per ethos rule 9).

Rate limiting: 0.5s between requests (SEC courtesy limit).

Schema quirks (from schema-notes.md):
  - CIK must be fetched from tickers.json, never hardcoded.
  - Submissions URL uses 10-digit zero-padded CIK.
  - Filing document URL uses integer CIK and hyphen-stripped accession number.
  - Filing index JSON (-index.json) 404s for some accessions; use primaryDocument directly.
  - EDGAR is highest-confidence for Risk Factors / MD&A text (primary-source bear evidence).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from adapters.base import Confidence, Prov, missing_prov

TODAY = date.today().isoformat()
SOURCE = "EDGAR"
EDGAR_UA = "CALIBER/3.0 victor.belfor@8x8.com"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_TICKERS_CACHE: Optional[Dict[str, int]] = None  # ticker → cik_int


@dataclass
class FilingRef:
    form: str
    date: str            # filing date
    accession: str       # hyphenated: 0000723125-25-000028
    primary_doc: str     # e.g. mu-20250828.htm
    report_date: Optional[str] = None   # fiscal period covered; None from fixtures


# ── E-2: canonical field resolution ──────────────────────────────────────────
# Issuers migrate XBRL tags over time and ABANDON the old one (verified on the golden
# CIKs: MU tags StockholdersEquity, V only the including-NCI variant, GOOG only the
# plain one — no issuer files both concurrently). So each canonical field carries an
# EXPLICIT ordered synonym chain, no heuristics: the first chain entry that is present
# AND not stale wins. A stale leading tag (V's StockholdersEquity stopped in 2011) is
# skipped, never used.

@dataclass(frozen=True)
class FieldSpec:
    """One canonical field and the ordered XBRL tags that may supply it."""
    name: str
    kind: str                              # "instant" (balance sheet) | "flow" (TTM)
    synonyms: Tuple[Tuple[str, str], ...]  # ((concept, namespace), ...) priority order
    derive: Optional[Tuple[str, str]] = None   # (minuend_field, subtrahend_field)
    conflict_check: bool = True
    """Whether two fresh tags in this chain disagreeing means non-comparable.

    True for genuinely ambiguous synonyms. False where the chain holds DISTINCT measures
    that are merely substitutable in priority order — e.g. total Revenues vs the ASC 606
    contract-revenue subset, or ShortTermBorrowings vs the CommercialPaper component of
    it. Those are expected to differ; the priority order already says which we want, and
    flagging them as conflicts would withhold good data (and cascade into every ratio
    built on it).
    """


FIELD_SPECS: Tuple[FieldSpec, ...] = (
    # Flows — TTM-assembled
    # Revenues (total) is the FMP-comparable measure; the ASC 606 tag covers only revenue
    # from customer contracts and legitimately differs where a company books investment or
    # other non-contract income (WU: 1,995.9M vs 1,920.6M for the same period). Distinct
    # measures, not ambiguous synonyms — priority order decides, no conflict gate.
    FieldSpec("revenue", "flow", (
        ("Revenues", "us-gaap"),
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "us-gaap"),
    ), conflict_check=False),
    FieldSpec("cost_of_revenue", "flow", (
        ("CostOfRevenue", "us-gaap"),
        ("CostOfGoodsAndServicesSold", "us-gaap"),
    )),
    # GrossProfit is untagged by GOOG and V; derive it when both components resolve.
    FieldSpec("gross_profit", "flow", (
        ("GrossProfit", "us-gaap"),
    ), derive=("revenue", "cost_of_revenue")),
    FieldSpec("operating_income", "flow", (
        ("OperatingIncomeLoss", "us-gaap"),
    )),
    FieldSpec("net_income", "flow", (
        ("NetIncomeLoss", "us-gaap"),
    )),
    FieldSpec("operating_cashflow", "flow", (
        ("NetCashProvidedByUsedInOperatingActivities", "us-gaap"),
        ("NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", "us-gaap"),
    )),
    FieldSpec("capex", "flow", (
        ("PaymentsToAcquirePropertyPlantAndEquipment", "us-gaap"),
    )),
    # Instants — most recent period-end
    FieldSpec("total_assets", "instant", (("Assets", "us-gaap"),)),
    FieldSpec("current_assets", "instant", (("AssetsCurrent", "us-gaap"),)),
    FieldSpec("total_liabilities", "instant", (("Liabilities", "us-gaap"),)),
    FieldSpec("current_liabilities", "instant", (("LiabilitiesCurrent", "us-gaap"),)),
    # BANK TAG MIGRATION (JPM onboarding, 2026-08-09). JPM abandoned
    # CashAndCashEquivalentsAtCarryingValue at 2018-12-31 and files the bank-specific
    # CashAndDueFromBanks instead (current to 2026-06-30). The two are distinct
    # PRESENTATIONS of the same balance-sheet line — a bank shows cash and due-from-banks
    # where an industrial shows cash and equivalents — so priority order decides and a
    # disagreement is expected rather than ambiguous, exactly like revenue and
    # current_debt. Generic tag stays FIRST so no non-bank resolution changes.
    FieldSpec("cash", "instant", (
        ("CashAndCashEquivalentsAtCarryingValue", "us-gaap"),
        ("CashAndDueFromBanks", "us-gaap"),      # JPM/BK/USB/C current tag
    ), conflict_check=False),
    # FMP's total_cash is cashAndShortTermInvestments, so the EDGAR side needs the
    # investment leg to be the same measure. Chain runs broadest-first; the entries are
    # distinct measures (AFS debt securities are a subset of marketable securities), so
    # priority order decides rather than a conflict gate.
    FieldSpec("short_term_investments", "instant", (
        ("MarketableSecuritiesCurrent", "us-gaap"),
        ("AvailableForSaleSecuritiesDebtSecuritiesCurrent", "us-gaap"),
        ("ShortTermInvestments", "us-gaap"),
        ("AvailableForSaleSecuritiesCurrent", "us-gaap"),
        ("OtherShortTermInvestments", "us-gaap"),
    ), conflict_check=False),
    FieldSpec("long_term_debt", "instant", (
        ("LongTermDebtNoncurrent", "us-gaap"),   # GOOG/V current tag
        ("LongTermDebt", "us-gaap"),             # MU current tag
    )),
    # ShortTermBorrowings is the aggregate; CommercialPaper is a component of it (NOW
    # files both: 2,082M vs 2,100M). Distinct measures — priority order, no conflict gate.
    FieldSpec("current_debt", "instant", (
        ("LongTermDebtCurrent", "us-gaap"),      # GOOG/V current tag
        ("DebtCurrent", "us-gaap"),              # MU current tag
        ("ShortTermBorrowings", "us-gaap"),      # NOW current tag
        ("CommercialPaper", "us-gaap"),
    ), conflict_check=False),
    # A directly-reported debt TOTAL, where the issuer files one. WU files no fresh
    # current-portion tag at all, so long_term_debt + current_debt is unassemblable for
    # it, but DebtAndCapitalLeaseObligations carries exactly what FMP's totalDebt means.
    # Used as an ALTERNATIVE input set, never as a substitute for the components.
    # LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities is chained HERE,
    # not on long_term_debt, DESPITE being the tag JPM migrated to when it abandoned
    # LongTermDebt. Its name is explicit: it INCLUDES CURRENT MATURITIES, so it is a debt
    # TOTAL, not the non-current leg. Putting it on long_term_debt would have silently
    # conflated two bases — the same class of error the R-B lease work and the
    # NET-vs-gross debt_to_equity advisory exist to prevent — and would then have been
    # added to current_debt downstream, double-counting the current portion.
    # CONSEQUENCE, stated: JPM's long_term_debt stays WITHHELD (stale_tag). That is the
    # honest outcome; it has no non-current-only debt tag to resolve.
    FieldSpec("total_debt_reported", "instant", (
        ("DebtAndCapitalLeaseObligations", "us-gaap"),
        ("DebtLongtermAndShorttermCombinedAmount", "us-gaap"),
        ("LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities", "us-gaap"),
    ), conflict_check=False),
    # R-B: FMP's totalDebt is lease-inclusive for most issuers. Measured at the fiscal
    # year-end across the golden five, the gap between FMP and gross filed debt equals
    # the OPERATING lease liability almost exactly (NOW and WU to the dollar, MU to
    # 0.5%) — finance leases are already inside the reported debt totals and adding them
    # overshoots. Same playbook as short_term_investments: an optional aligning leg.
    FieldSpec("operating_lease_liability", "instant", (
        ("OperatingLeaseLiability", "us-gaap"),
    )),
    FieldSpec("equity", "instant", (
        ("StockholdersEquity", "us-gaap"),
        ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "us-gaap"),
    )),
    # dei cover-page count is absent for GOOG and frozen at 2010 for V (both multi-class);
    # us-gaap CommonStockSharesOutstanding is the fallback.
    FieldSpec("shares_outstanding", "instant", (
        ("EntityCommonStockSharesOutstanding", "dei"),
        ("CommonStockSharesOutstanding", "us-gaap"),
    )),
)

# CORPORATE-ACTIONS CORROBORATION (G-2). Pulled for split-ratio corroboration ONLY and
# deliberately kept OUT of FIELD_SPECS: it is not a canonical field, so it must not appear
# in the 19-spec coverage counts, the resolved-xor-reason invariant, or the cross-check.
# Issuers tag the ratio explicitly — GOOG 20 @ 2022-07-15, NOW 5 @ 2025-12-05 — which makes
# it the third witness, and two of the three then sit inside EDGAR, independent of FMP.
CORPORATE_ACTION_CONCEPTS: List[Tuple[str, str]] = [
    ("StockholdersEquityNoteStockSplitConversionRatio1", "us-gaap"),
]
_CORPORATE_ACTION_NAMES = {c for c, _ in CORPORATE_ACTION_CONCEPTS}

# The concept-pull list is derived from the spec table — one place to add a tag.
XBRL_CONCEPTS: List[Tuple[str, str]] = [
    syn for spec in FIELD_SPECS for syn in spec.synonyms
] + CORPORATE_ACTION_CONCEPTS
_XBRL_VALID_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}

# Per-concept staleness gate: a concept whose newest period-end lags the entity's latest
# filed period by more than this resolves to None. One fiscal year + a quarter of margin —
# MU legitimately tags LongTermDebt only in some quarters (182d lag observed).
STALE_TAG_DAYS = 450

# Typed reason codes. Recorded on every unresolved field; queryable as the tag-migration
# diagnostic map when onboarding new tickers.
REASON_NO_TAG = "no_tag"                      # no synonym present at all
REASON_STALE_TAG = "stale_tag"                # present but abandoned > STALE_TAG_DAYS ago
REASON_SYNONYM_CONFLICT = "synonym_conflict"  # two fresh synonyms disagree for one period
REASON_AMBIGUOUS_PERIOD = "ambiguous_period"  # one filing reports two values for a period
REASON_TTM_UNAVAILABLE = "ttm_unavailable"    # neither TTM path satisfiable
REASON_DERIVE_INCOMPLETE = "derive_incomplete"  # derivation components unresolved

# TTM assembly windows (days)
_QTD_RANGE = (80, 100)
_FY_RANGE = (350, 380)
_SYNONYM_TOLERANCE_PCT = 0.5   # fresh synonyms within this agree; beyond it, conflict

PER_CONCEPT_DEPTH = 40
"""Records kept per concept after de-duplication.

Depth is set by the TTM reconstruction path, which needs a full prior fiscal year plus
the current and prior-year year-to-date facts — i.e. ~2 fiscal years of period-ends, each
carrying several duration variants (QTD/YTD/FY). Measured on the golden CIKs, 15 de-duped
records cover 10 distinct period-ends worst-case; 40 leaves ~2.5x margin without bloating
the fixtures.
"""


@dataclass
class ResolvedField:
    """One canonical field after synonym resolution, staleness gating and TTM assembly.

    value is None whenever reason is set — a stale or ambiguous figure is withheld, never
    passed downstream wearing a fresh label (it could otherwise agree with FMP inside the
    cross-check tolerance and launder to high confidence).
    """
    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    concept: Optional[str] = None    # tag that supplied it, or "derived:a-b"
    method: Optional[str] = None     # instant | ttm_summed | ttm_reconstructed | ttm_annual | derived
    reason: Optional[str] = None     # typed code; None when resolved
    detail: Optional[str] = None     # human-readable amplification of reason
    trail: List[str] = field(default_factory=list)  # per-synonym outcome, in priority order
    # G-1: filing date this value FIRST appeared under. Populated on SERIES records only —
    # it identifies which split basis a fact is on, which the single latest-period value
    # has no use for. Optional so nothing downstream has to care.
    first_filed: Optional[str] = None

    def is_resolved(self) -> bool:
        return self.value is not None and self.reason is None


@dataclass
class EdgarFinancials:
    """XBRL facts from companyfacts, plus canonical fields resolved from them.

    concepts: {concept_name: [ {value, unit, start, end, fy, fp, form, accession}, ... ]}
      most-recent-first, de-duplicated, capped at PER_CONCEPT_DEPTH (raw extraction, E-1).
    fields:   {canonical_name: ResolvedField} — synonym-resolved, staleness-gated, TTM
      assembled (E-2). E-3 cross-checks these against FMP.
    """
    concepts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    latest_period_end: Optional[str] = None   # max period-end across concepts (E-3 staleness)
    fields: Dict[str, ResolvedField] = field(default_factory=dict)


def _days_between(earlier: Optional[str], later: Optional[str]) -> Optional[int]:
    """Whole days from earlier to later ISO date, or None if either is unparseable."""
    if not earlier or not later:
        return None
    try:
        return (date.fromisoformat(later[:10]) - date.fromisoformat(earlier[:10])).days
    except ValueError:
        return None


def _earliest(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """The earlier of two ISO dates, tolerating either being absent."""
    present = [d for d in (a, b) if d]
    return min(present) if present else None


def _extract_xbrl_facts(
    facts_json: Dict, per_concept: int = PER_CONCEPT_DEPTH
) -> EdgarFinancials:
    """Pull the mapped concepts' recent facts from a companyfacts JSON, then resolve
    canonical fields from them.

    Extraction: numeric coercion, form filter (10-K/10-Q family), de-duplication, and
    latest-period-first ordering. Companyfacts repeats an unchanged fact in every filing
    that references it, so identical (start, end, unit, value) tuples are collapsed —
    keeping the newest accession — before the depth cap, or duplicates would crowd out
    the older periods TTM reconstruction needs.
    """
    facts = facts_json.get("facts", {}) if facts_json else {}
    ns_blocks = {"us-gaap": facts.get("us-gaap", {}), "dei": facts.get("dei", {})}
    out: Dict[str, List[Dict[str, Any]]] = {}
    latest_end: Optional[str] = None

    for concept, ns in XBRL_CONCEPTS:
        block = ns_blocks.get(ns, {}).get(concept)
        if not block:
            continue
        deduped: Dict[Tuple[Any, Any, str, float], Dict[str, Any]] = {}
        for unit, entries in block.get("units", {}).items():
            for e in entries:
                if e.get("form") not in _XBRL_VALID_FORMS:
                    continue
                try:
                    val = float(e["val"])
                except (KeyError, TypeError, ValueError):
                    continue
                rec = {
                    "value": val, "unit": unit,
                    "start": e.get("start"), "end": e.get("end"),
                    "fy": e.get("fy"), "fp": e.get("fp"),
                    "form": e.get("form"), "accession": e.get("accn"),
                    # G-1: the filing date this exact value FIRST appeared under. A share
                    # count is on the split basis in effect when it was FILED, not when
                    # its period ended, so Phase G's restatement needs this and nothing
                    # else identifies it — the accession YEAR is too coarse (GOOG's
                    # 2022-03-31 and 2022-06-30 straddle the 2022 split and are both -22-).
                    "first_filed": e.get("filed"),
                }
                key = (rec["start"], rec["end"], unit, val)
                prior = deduped.get(key)
                if prior is None or (rec["accession"] or "") > (prior["accession"] or ""):
                    # EARLIEST wins, deliberately, and it is carried across the accession
                    # tie-break above. A later filing REPEATING a value verbatim did not
                    # restate it, so the value still carries its original basis; a genuine
                    # restatement changes the number and lands in a different dedupe group.
                    # Taking the latest date instead would read a repeated pre-split value
                    # as post-split and silently skip its adjustment.
                    rec["first_filed"] = _earliest(
                        rec["first_filed"], prior["first_filed"] if prior else None)
                    deduped[key] = rec
                elif prior is not None:
                    prior["first_filed"] = _earliest(
                        prior["first_filed"], rec["first_filed"])
        recs = list(deduped.values())
        if not recs:
            continue
        recs.sort(key=lambda r: (r["end"] or "", r["accession"] or ""), reverse=True)
        out[concept] = recs[:per_concept]
        # Staleness clock tracks fiscal PERIOD-END from us-gaap financials only —
        # dei cover-page dates (e.g. shares-outstanding as-of) are not period ends.
        # Corporate-action concepts are excluded too: a split-ratio fact is dated to the
        # split, not to a reporting period, so letting it into the clock would let a
        # corporate action move every field's freshness gate.
        if ns == "us-gaap" and concept not in _CORPORATE_ACTION_NAMES:
            top = out[concept][0]["end"]
            if top and (latest_end is None or top > latest_end):
                latest_end = top

    return resolve_financials(out, latest_end)


def _pick_instant(recs: List[Dict[str, Any]], name: str, concept: str) -> ResolvedField:
    """Balance-sheet value: the most recent period-end.

    A period restated across filings is resolved to the newest accession. Two different
    values for the same period inside ONE filing cannot be told apart here (companyfacts
    strips the dimensions that separate them), so the field is withheld.
    """
    top_end = max(r["end"] for r in recs if r.get("end"))
    same_period = [r for r in recs if r["end"] == top_end]
    newest_accn = max((r["accession"] or "") for r in same_period)
    from_newest = [r for r in same_period if (r["accession"] or "") == newest_accn]
    values = {r["value"] for r in from_newest}
    if len(values) > 1:
        return ResolvedField(
            name=name, concept=concept, reason=REASON_AMBIGUOUS_PERIOD,
            detail=(f"{concept}: {len(values)} distinct values for period {top_end} in "
                    f"accession {newest_accn or '?'} ({sorted(values)[:3]})"),
        )
    rec = from_newest[0]
    return ResolvedField(
        name=name, value=rec["value"], unit=rec["unit"], period_end=rec["end"],
        concept=concept, method="instant",
    )


def _in_range(days: Optional[int], bounds: Tuple[int, int]) -> bool:
    return days is not None and bounds[0] <= days <= bounds[1]


def _assemble_ttm(
    recs: List[Dict[str, Any]], name: str, concept: str,
    as_of_end: Optional[str] = None,
) -> ResolvedField:
    """Trailing-twelve-month value for a flow concept.

    Duration facts for one concept mix QTD, year-to-date and full-year windows, so a naive
    sum double-counts. Three paths, in order:
      1. ttm_annual       — the newest fact already spans a full fiscal year.
      2. ttm_summed       — four contiguous QTD facts covering ~365 days.
      3. ttm_reconstructed— prior FY + current YTD - prior-year YTD. Required for issuers
         that never report Q4 standalone (all three golden CIKs).
    Returns a partial sum under no circumstances: if no path is satisfiable the value is
    withheld with REASON_TTM_UNAVAILABLE.
    """
    by_period: Dict[Tuple[Any, Any], Dict[str, Any]] = {}
    for r in sorted(recs, key=lambda r: (r["accession"] or "")):
        if not r.get("start") or not r.get("end"):
            continue
        by_period[(r["start"], r["end"])] = r   # ascending accession → newest wins
    facts = []
    for r in by_period.values():
        days = _days_between(r["start"], r["end"])
        if days is None or days <= 0:
            continue
        facts.append({**r, "days": days})
    if not facts:
        return ResolvedField(
            name=name, concept=concept, reason=REASON_TTM_UNAVAILABLE,
            detail=f"{concept}: no duration facts (instant-only concept?)",
        )

    # as_of_end assembles the TTM as it stood at an EARLIER period-end, which is what
    # builds a historical series. Default (None) is the newest period — the live path.
    latest_end = as_of_end or max(f["end"] for f in facts)
    at_latest = [f for f in facts if f["end"] == latest_end]
    if not at_latest:
        return ResolvedField(
            name=name, concept=concept, reason=REASON_TTM_UNAVAILABLE,
            detail=f"{concept}: no duration fact ending {latest_end}",
        )
    current = max(at_latest, key=lambda f: f["days"])   # YTD spans further than QTD

    # 1. The newest fact is itself a full year.
    if _in_range(current["days"], _FY_RANGE):
        return ResolvedField(
            name=name, value=current["value"], unit=current["unit"],
            period_start=current["start"], period_end=current["end"],
            concept=concept, method="ttm_annual",
        )

    # 2. Four contiguous quarters.
    quarters, seen_ends = [], set()
    for f in sorted(facts, key=lambda f: f["end"], reverse=True):
        if _in_range(f["days"], _QTD_RANGE) and f["end"] not in seen_ends:
            seen_ends.add(f["end"])
            quarters.append(f)
        if len(quarters) == 4:
            break
    if len(quarters) == 4:
        ordered = sorted(quarters, key=lambda f: f["start"])
        contiguous = all(
            (_days_between(ordered[i]["end"], ordered[i + 1]["start"]) or 99) <= 3
            for i in range(3)
        )
        span = _days_between(ordered[0]["start"], ordered[-1]["end"])
        if contiguous and _in_range(span, _FY_RANGE):
            return ResolvedField(
                name=name, value=sum(f["value"] for f in quarters),
                unit=quarters[0]["unit"], period_start=ordered[0]["start"],
                period_end=ordered[-1]["end"], concept=concept, method="ttm_summed",
            )

    # 3. Reconstruct: prior FY + current YTD - prior-year YTD.
    prior_fy = next(
        (f for f in facts
         if _in_range(f["days"], _FY_RANGE)
         and abs(_days_between(f["end"], current["start"]) or 99) <= 5),
        None,
    )
    prior_ytd = next(
        (f for f in facts
         if abs((_days_between(f["end"], current["end"]) or 0) - 365) <= 10
         and abs(f["days"] - current["days"]) <= 10),
        None,
    )
    if prior_fy and prior_ytd:
        return ResolvedField(
            name=name,
            value=prior_fy["value"] + current["value"] - prior_ytd["value"],
            unit=current["unit"], period_start=prior_ytd["end"],
            period_end=current["end"], concept=concept, method="ttm_reconstructed",
        )

    missing = "prior FY" if not prior_fy else "prior-year YTD"
    return ResolvedField(
        name=name, concept=concept, reason=REASON_TTM_UNAVAILABLE,
        detail=(f"{concept}: no clean 4-quarter set and {missing} missing for the "
                f"{current['days']}d window ending {current['end']}"),
    )


def ttm_series(
    financials: "EdgarFinancials", field_name: str, limit: int = 24
) -> List[ResolvedField]:
    """The same TTM figure assembled at each historical period-end, newest first.

    Phase D's own-history anchor needs a multiple SERIES, which needs an earnings series.
    This reuses _assemble_ttm at each period-end rather than reimplementing the
    reconstruction rule, so a historical TTM is assembled by exactly the same three paths
    (annual / summed / reconstructed) as the live one, and periods that cannot be
    assembled are dropped rather than approximated.

    Follows the tag the field actually resolved to, so a migrated issuer keeps its series.
    """
    rf = financials.fields.get(field_name)
    if rf is None or not rf.concept or rf.concept.startswith("derived:"):
        return []
    recs = financials.concepts.get(rf.concept, [])
    ends = sorted({r["end"] for r in recs if r.get("end") and r.get("start")},
                  reverse=True)[:limit]
    out = []
    for end in ends:
        assembled = _assemble_ttm(recs, field_name, rf.concept, as_of_end=end)
        if assembled.is_resolved():
            out.append(assembled)
    return out


def instant_series(
    financials: "EdgarFinancials", field_name: str, limit: int = 24
) -> List[ResolvedField]:
    """A balance-sheet field's value at each historical period-end, newest first."""
    rf = financials.fields.get(field_name)
    if rf is None or not rf.concept or rf.concept.startswith("derived:"):
        return []
    seen, out = set(), []
    for r in sorted(financials.concepts.get(rf.concept, []),
                    key=lambda r: (r.get("end") or ""), reverse=True):
        end = r.get("end")
        if not end or r.get("start") or end in seen:
            continue
        seen.add(end)
        out.append(ResolvedField(
            name=field_name, value=float(r["value"]), unit=r.get("unit"),
            period_end=end, concept=rf.concept, method="instant",
            first_filed=r.get("first_filed"),
        ))
        if len(out) >= limit:
            break
    return out


def _resolve_one(
    spec: FieldSpec,
    concepts: Dict[str, List[Dict[str, Any]]],
    latest_period_end: Optional[str],
    stale_days: int,
) -> ResolvedField:
    """Walk a field's synonym chain in priority order, gating each on staleness."""
    trail: List[str] = []
    candidates: List[ResolvedField] = []

    for concept, _ns in spec.synonyms:
        recs = concepts.get(concept)
        if not recs:
            trail.append(f"{concept}:absent")
            continue
        newest_end = max((r["end"] for r in recs if r.get("end")), default=None)
        lag = _days_between(newest_end, latest_period_end)
        if lag is not None and lag > stale_days:
            trail.append(f"{concept}:stale({lag}d)")
            continue
        rf = (_pick_instant(recs, spec.name, concept) if spec.kind == "instant"
              else _assemble_ttm(recs, spec.name, concept))
        if rf.is_resolved():
            trail.append(f"{concept}:{'used' if not candidates else 'agrees'}")
            candidates.append(rf)
        else:
            trail.append(f"{concept}:{rf.reason}")
            candidates.append(rf)

    resolved = [c for c in candidates if c.is_resolved()]
    if resolved:
        winner = resolved[0]
        # Two fresh tags covering the same period must agree, else the field is
        # non-comparable and is withheld rather than arbitrated. Chains declared as
        # distinct measures skip this — see FieldSpec.conflict_check.
        for other in (resolved[1:] if spec.conflict_check else []):
            if other.period_end != winner.period_end or winner.value == 0:
                continue
            diff_pct = abs(other.value - winner.value) / abs(winner.value) * 100.0
            if diff_pct > _SYNONYM_TOLERANCE_PCT:
                return ResolvedField(
                    name=spec.name, reason=REASON_SYNONYM_CONFLICT, trail=trail,
                    detail=(f"{winner.concept}={winner.value:.6g} vs "
                            f"{other.concept}={other.value:.6g} for period "
                            f"{winner.period_end} ({diff_pct:.1f}% apart)"),
                )
        winner.trail = trail
        return winner

    # Nothing resolved — report the most specific reason seen along the chain.
    unresolved = [c for c in candidates if c.reason]
    if unresolved:
        first = unresolved[0]
        return ResolvedField(name=spec.name, reason=first.reason,
                             detail=first.detail, trail=trail)
    stale_tags = [t for t in trail if ":stale(" in t]
    if stale_tags:
        return ResolvedField(
            name=spec.name, reason=REASON_STALE_TAG, trail=trail,
            detail=f"all tags abandoned: {', '.join(stale_tags)}",
        )
    return ResolvedField(
        name=spec.name, reason=REASON_NO_TAG, trail=trail,
        detail=f"no tag filed: {', '.join(t.split(':')[0] for t in trail) or 'none mapped'}",
    )


def _apply_derivation(spec: FieldSpec, fields: Dict[str, ResolvedField]) -> ResolvedField:
    """Derive a field from two others (gross_profit = revenue - cost_of_revenue).

    Only fires when both components resolved over the SAME period by the SAME method —
    subtracting a TTM from an annual figure would be arithmetic nonsense. No guessing:
    if either component is unresolved the field stays None with a reason naming it.
    """
    minuend_name, subtrahend_name = spec.derive          # type: ignore[misc]
    a, b = fields.get(minuend_name), fields.get(subtrahend_name)
    if a is None or b is None or not a.is_resolved() or not b.is_resolved():
        missing = [
            n for n, f in ((minuend_name, a), (subtrahend_name, b))
            if f is None or not f.is_resolved()
        ]
        detail = "; ".join(
            f"{n} unresolved ({fields[n].reason})" if n in fields else f"{n} unresolved"
            for n in missing
        )
        return ResolvedField(name=spec.name, reason=REASON_DERIVE_INCOMPLETE, detail=detail)
    if a.period_end != b.period_end or a.method != b.method:
        return ResolvedField(
            name=spec.name, reason=REASON_DERIVE_INCOMPLETE,
            detail=(f"{minuend_name} ({a.method}@{a.period_end}) and {subtrahend_name} "
                    f"({b.method}@{b.period_end}) cover different periods"),
        )
    return ResolvedField(
        name=spec.name, value=a.value - b.value, unit=a.unit,
        period_start=a.period_start, period_end=a.period_end,
        concept=f"derived:{minuend_name}-{subtrahend_name}", method=a.method,
    )


def resolve_financials(
    concepts: Dict[str, List[Dict[str, Any]]],
    latest_period_end: Optional[str],
    stale_days: int = STALE_TAG_DAYS,
) -> EdgarFinancials:
    """Resolve every canonical field from extracted concept facts (E-2).

    Runs on both the live and fixture paths so recorded data exercises the same code.
    """
    fields: Dict[str, ResolvedField] = {}
    for spec in FIELD_SPECS:
        rf = _resolve_one(spec, concepts, latest_period_end, stale_days)
        if not rf.is_resolved() and spec.derive:
            derived = _apply_derivation(spec, fields)
            derived.trail = rf.trail
            rf = derived
        fields[spec.name] = rf
    return EdgarFinancials(
        concepts=concepts, latest_period_end=latest_period_end, fields=fields
    )


@dataclass
class EdgarData:
    ticker: str
    cik: str             # zero-padded 10-digit string
    company_name: Optional[str]
    sic: Optional[str]
    sic_description: Optional[str]
    fiscal_year_end: Optional[str]

    recent_10k: List[FilingRef]
    recent_10q: List[FilingRef]

    # Bear evidence (highest confidence per ethos rule 9)
    risk_factors_excerpt: Prov
    mda_excerpt: Prov

    # XBRL concept count (for adapter health check)
    xbrl_concept_count: Optional[int]

    # Extracted XBRL financials for FMP cross-check (E-1)
    financials: EdgarFinancials = field(default_factory=EdgarFinancials)

    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _headers() -> Dict[str, str]:
    return {"User-Agent": EDGAR_UA, "Accept": "application/json"}


# FMP <-> SEC ticker mismatches, EXPLICIT and per-issuer. Never a fuzzy name match: two
# filers can share a name fragment, and silently pairing the wrong CIK would cross an
# issuer's fundamentals with another's price — the worst failure this pipeline can have.
# Found during the 2026-08-09 bank onboarding.
SEC_TICKER_ALIASES = {
    # BNY Mellon trades on the NYSE as BK and FMP serves it that way, but SEC's
    # company_tickers.json lists it as BNY following the 2024 rebrand. Same CIK 1390777.
    "BK": "BNY",
}


def _get_cik(ticker: str) -> str:
    """Look up CIK from SEC tickers.json. Raises loudly on failure."""
    global _TICKERS_CACHE
    if _TICKERS_CACHE is None:
        try:
            r = requests.get(TICKERS_URL, headers=_headers(), timeout=20)
            r.raise_for_status()
            raw = r.json()
            _TICKERS_CACHE = {v["ticker"]: v["cik_str"] for v in raw.values()}
        except Exception as e:
            raise RuntimeError(
                f"[EDGAR] Failed to fetch CIK map from {TICKERS_URL}. "
                f"Error: {type(e).__name__}: {e}"
            ) from e

    symbol = ticker.upper()
    cik_int = _TICKERS_CACHE.get(symbol)
    if cik_int is None and symbol in SEC_TICKER_ALIASES:
        cik_int = _TICKERS_CACHE.get(SEC_TICKER_ALIASES[symbol])
    if cik_int is None:
        raise RuntimeError(
            f"[EDGAR] Ticker '{ticker}' not found in SEC tickers.json. "
            f"Check spelling, or add an explicit entry to SEC_TICKER_ALIASES if the SEC "
            f"symbol differs from the exchange symbol."
        )
    return str(cik_int).zfill(10)


def _fetch_submissions(cik: str) -> Dict:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        r = requests.get(url, headers=_headers(), timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise RuntimeError(
            f"[EDGAR] Submissions fetch failed. CIK={cik}, URL={url}. "
            f"Error: {type(e).__name__}: {e}"
        ) from e


def _parse_filings(sub: Dict) -> Tuple[List[FilingRef], List[FilingRef]]:
    filings = sub.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accnums = filings.get("accessionNumber", [])
    docs = filings.get("primaryDocument", [])
    reports = filings.get("reportDate", [])

    tenk, tenq = [], []
    for i, f in enumerate(forms):
        ref = FilingRef(
            form=f,
            date=dates[i] if i < len(dates) else "",
            accession=accnums[i] if i < len(accnums) else "",
            primary_doc=docs[i] if i < len(docs) else "",
            report_date=reports[i] if i < len(reports) else None,
        )
        if f in ("10-K", "10-K/A") and len(tenk) < 3:
            tenk.append(ref)
        elif f in ("10-Q", "10-Q/A") and len(tenq) < 3:
            tenq.append(ref)
    return tenk, tenq


def _fetch_filing_text(cik: str, ref: FilingRef, max_chars: int = 40000) -> str:
    """Fetch the primary filing document text (first max_chars chars)."""
    cik_int = int(cik)
    accn_clean = ref.accession.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_int}/{accn_clean}/{ref.primary_doc}"
    )
    try:
        r = requests.get(
            url,
            headers={**_headers(), "Accept": "text/html"},
            timeout=30,
        )
        r.raise_for_status()
        return r.text[:max_chars]
    except Exception as e:
        raise RuntimeError(
            f"[EDGAR] Filing document fetch failed. "
            f"ticker related, CIK={cik}, accession={ref.accession}, "
            f"doc={ref.primary_doc}, URL={url}. "
            f"Error: {type(e).__name__}: {e}"
        ) from e


def _extract_section(text: str, markers: List[str], max_len: int = 2000) -> str:
    """Find first marker in text (case-insensitive) and return excerpt."""
    lower = text.lower()
    for marker in markers:
        idx = lower.find(marker.lower())
        if idx >= 0:
            return text[idx: idx + max_len].strip()
    return ""


def _fetch_companyfacts(cik: str) -> Optional[Dict]:
    """Fetch the full XBRL companyfacts JSON, or None on any error (supplemental)."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_edgar(ticker: str, fixture_path: Optional[Path] = None) -> EdgarData:
    if fixture_path is not None:
        return _from_fixture(ticker, fixture_path)
    return _from_live(ticker)


def _from_live(ticker: str) -> EdgarData:
    cik = _get_cik(ticker)
    time.sleep(0.3)

    sub = _fetch_submissions(cik)
    time.sleep(0.3)

    tenk, tenq = _parse_filings(sub)

    risk_prov = missing_prov(SOURCE, TODAY)
    mda_prov = missing_prov(SOURCE, TODAY)

    if tenk:
        try:
            text = _fetch_filing_text(cik, tenk[0])
            time.sleep(0.5)
            risk_txt = _extract_section(text, ["risk factor", "item 1a"])
            mda_txt = _extract_section(text, ["management's discussion", "item 7"])
            # EDGAR = highest confidence tier per ethos rule 9
            conf: Confidence = "high" if risk_txt else "medium"
            risk_prov = Prov(
                value=risk_txt or None,
                source=SOURCE,
                as_of=tenk[0].date,
                confidence=conf,
            )
            mda_prov = Prov(
                value=mda_txt or None,
                source=SOURCE,
                as_of=tenk[0].date,
                confidence=conf,
            )
        except RuntimeError as e:
            # Log but don't kill evaluation — filing text is supplemental
            risk_prov = Prov(value=None, source=SOURCE, as_of=TODAY, confidence="low")
            mda_prov = Prov(value=None, source=SOURCE, as_of=TODAY, confidence="low")

    facts_json = _fetch_companyfacts(cik)
    xbrl_count = len(facts_json.get("facts", {}).get("us-gaap", {})) if facts_json else None
    financials = _extract_xbrl_facts(facts_json) if facts_json else EdgarFinancials()

    return EdgarData(
        ticker=ticker,
        cik=cik,
        company_name=sub.get("name"),
        sic=sub.get("sic"),
        sic_description=sub.get("sicDescription"),
        fiscal_year_end=sub.get("fiscalYearEnd"),
        recent_10k=tenk,
        recent_10q=tenq,
        risk_factors_excerpt=risk_prov,
        mda_excerpt=mda_prov,
        xbrl_concept_count=xbrl_count,
        financials=financials,
    )


def _from_fixture(ticker: str, path: Path) -> EdgarData:
    if not path.exists():
        raise RuntimeError(
            f"[EDGAR] fixture not found: {path}. Run probe.py first."
        )
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    sub = raw.get("submissions_shape", {})
    tenk_raw = sub.get("recent_10K", [])
    tenq_raw = sub.get("recent_10Q", [])

    def to_ref(r: List) -> FilingRef:
        return FilingRef(form="10-K", date=r[0], accession=r[1], primary_doc=r[2] if len(r) > 2 else "")

    tenk = [to_ref(r) for r in tenk_raw]
    tenq = [FilingRef(form="10-Q", date=r[0], accession=r[1], primary_doc=r[2] if len(r) > 2 else "")
            for r in tenq_raw]

    risk_txt = raw.get("risk_factors_excerpt")
    mda_txt = raw.get("mda_excerpt")
    as_of = tenk[0].date if tenk else TODAY

    risk_prov = Prov(
        value=risk_txt if risk_txt and "not in first" not in str(risk_txt) else None,
        source=SOURCE,
        as_of=as_of,
        confidence="high" if risk_txt and "not in first" not in str(risk_txt) else "low",
    )
    mda_prov = Prov(
        value=mda_txt if mda_txt and "not in first" not in str(mda_txt) else None,
        source=SOURCE,
        as_of=as_of,
        confidence="high" if mda_txt and "not in first" not in str(mda_txt) else "low",
    )

    xf = raw.get("xbrl_facts", {})
    # Fixtures record the extracted concept facts; field resolution runs here so the
    # recorded path exercises exactly the same E-2 code as the live path.
    financials = resolve_financials(
        xf.get("concepts", {}), xf.get("latest_period_end")
    )

    return EdgarData(
        ticker=ticker,
        cik=raw.get("cik", ""),
        company_name=sub.get("company_name"),
        sic=sub.get("sic"),
        sic_description=sub.get("sic_description"),
        fiscal_year_end=sub.get("fiscal_year_end"),
        recent_10k=tenk,
        recent_10q=tenq,
        risk_factors_excerpt=risk_prov,
        mda_excerpt=mda_prov,
        xbrl_concept_count=raw.get("facts_shape", {}).get("us_gaap_concept_count"),
        financials=financials,
    )
