"""
EDGAR × FMP cross-check — E-3, DARK LAUNCH.

EDGAR is the wired SECOND source. Since the AlphaVantage teardown every field has been
stuck at 'medium' (single source), which made the "[ANTI-LAUNDER: high-conf miss]" NOTE
unfirable. This module computes what a live cross-check WOULD do to each field's
confidence — and applies NOTHING.

Dark means dark: no Prov is mutated, nothing is written back to TickerData, no score,
E(R) or grade can move. The output is a delta table for calibration, exactly like the
anchor guard's logging phase before it was armed at 15%.

Two engines are reused rather than reimplemented (never add duplicate logic):
  core.cross_check.apply_cross_check      — agreement/conflict → high/low
  core.cross_check.apply_staleness_penalty — age cap → medium

FRESHNESS IS PER-FIELD (ruling, 2026-08-08). Each comparison is aged from its OWN
period-end, never from a per-ticker as-of. A field built from several EDGAR values ages
from the OLDEST of them. MU's long_term_debt lags its siblings by a full quarter and
must stay capped while they upgrade.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from adapters.base import Confidence, Prov
from adapters.edgar_adapter import EdgarData, ResolvedField
from core.cross_check import apply_cross_check, apply_staleness_penalty

SECONDARY_SOURCE = "EDGAR"

# ── Freshness threshold (LOCKED 2026-08-08) ──────────────────────────────────
# The 150d day-count is the BACKSTOP. The PRIMARY staleness signal is the lag-aware
# submissions cross-reference below (newest_filed_period / filing_freshness_flags): a
# day-count alone cannot see a companyfacts lag, as V proves at 130d and a full quarter
# behind. Locked with the XBRL-LAG / MISSING-EXPECTED-10Q split as built.
# Derived from the golden five's actual filing behaviour, not assumed. The quantity that
# matters is how old the freshest available period-end legitimately gets right before new
# data lands: (next filing date - current newest period-end). Measured over the last 9
# filings of MU/GOOG/V/NOW/WU (n=40 windows): min 112d, max 143d (WU, whose 10-K lands
# 51 days after fiscal year-end). A 120d gate would false-flag 17 of those 40 legitimate
# windows; 150d false-flags none, with 7 days of margin over the observed maximum.
#
# The next genuine signal — a skipped quarter — does not arrive until ~200d+, so 150-200
# is a real warning band rather than routine filing cadence.
FRESHNESS_THRESHOLD_DAYS = 150

# Observed p90 filing lag across the golden five (n=45 filings): 36 days. Used only to
# decide when the NEXT periodic report is overdue.
FILING_LAG_P90_DAYS = 36
QUARTER_DAYS = 91

DIVERGENCE_TOLERANCE_PCT = 5.0   # matches core.cross_check's default


@dataclass(frozen=True)
class Comparison:
    """One FMP field and the EDGAR-derived value that should corroborate it."""
    fmp_field: str                              # attribute on TickerData (a Prov)
    inputs: Tuple[str, ...]                     # EDGAR canonical fields required
    compute: Callable[[Dict[str, float]], Optional[float]]
    basis_note: str = ""                        # non-empty ⇒ known basis mismatch
    optional: Tuple[str, ...] = ()
    """Inputs that improve basis alignment but are not filed by every issuer.

    Missing ones do not block the comparison; they downgrade it to advisory, because the
    remaining value measures something narrower than the FMP field it faces.
    """
    optional_missing_note: str = ""
    label: str = ""
    """Row key when several comparisons target one FMP field. Defaults to fmp_field."""
    input_alternatives: Tuple[Tuple[str, ...], ...] = ()
    """Ordered alternative required-input sets; the first fully-resolved set wins.

    Lets one comparison be satisfied by either a directly-reported total or its
    components, without inventing a preference inside compute(). WU files no fresh
    current-debt tag, so its total_debt is only reachable via the reported total.
    """
    period_basis: str = "mrq"
    """'mrq' — the fields as resolved (most recent period). 'annual_fy' — every input
    re-read at the issuer's latest FISCAL YEAR END, for FMP fields served off the annual
    statements. Converts a permanent as-of advisory into a real like-for-like test."""
    age_basis: str = "absolute"
    """'absolute' — days from the input's period-end to today (the default semantic).
    'alignment' — days between the two SIDES' periods, which is 0 for a matched-period
    comparison: a correctly-labelled annual figure corroborating an annual FMP field
    launders nothing, since neither side claims to be more recent than it is.

    APPROVED 2026-08-09, SCOPED (R-A). Alignment aging holds only while all three
    conditions do:
      1. the periods are matched          — period_basis == 'annual_fy'
      2. the bases are proven identical   — any missing aligning input makes the row
                                            advisory before the gate is ever reached
      3. the primary's IN-USE value is still the matched-period figure
    Condition 3 is a premise about someone else's feed, so it is re-checked at runtime on
    every evaluation rather than trusted (see _tracks_matched_period). If FMP switches
    total_cash to the MRQ balance sheet, the row silently reverts to absolute aging and
    starts capping — which is the safe direction — instead of quietly corroborating an
    annual figure against a quarterly one.
    """
    dark: bool = False
    """Computed and logged, never applied. New comparison surface stays dark until the
    delta table it produces has been reviewed."""
    average_inputs: Tuple[str, ...] = ()
    """Inputs averaged with their prior-year value ((begin + end) / 2).

    FMP's returnOnEquityTTM is computed on average equity. Measured against period-end
    equity the gap tracks equity growth exactly — 29.0% on MU and 25.0% on GOOG, the two
    fastest compounders, versus ~2-3% on the rest. Averaging is basis alignment, not a
    fudge factor.
    """


def _sum_debt(v: Dict[str, float]) -> Optional[float]:
    """Reported debt total where the issuer files one, else long-term + current."""
    if "total_debt_reported" in v:
        return v["total_debt_reported"]
    return v["long_term_debt"] + v["current_debt"]


def _sum_debt_lease_inclusive(v: Dict[str, float]) -> Optional[float]:
    """Debt on FMP's basis: filed debt plus the OPERATING lease liability.

    Finance leases are deliberately excluded — they already sit inside the reported debt
    totals, and adding them overshoots (MU 15.3% high, GOOG 13.9%).
    """
    base = _sum_debt(v)
    return None if base is None else base + v.get("operating_lease_liability", 0.0)


def _ratio(num: str, den: str) -> Callable[[Dict[str, float]], Optional[float]]:
    def f(v: Dict[str, float]) -> Optional[float]:
        return v[num] / v[den] if v[den] else None
    return f


# FMP margins/ratios are TTM decimals (grossProfitMarginTTM = 0.726), which is the same
# basis as our EDGAR TTM fields. Where the bases genuinely differ, basis_note says so and
# the comparison is advisory only — it never proposes a confidence change.
COMPARISONS: Tuple[Comparison, ...] = (
    Comparison("gross_margin", ("gross_profit", "revenue"),
               _ratio("gross_profit", "revenue")),
    Comparison("operating_margin", ("operating_income", "revenue"),
               _ratio("operating_income", "revenue")),
    Comparison("profit_margin", ("net_income", "revenue"),
               _ratio("net_income", "revenue")),
    Comparison("roe", ("net_income", "equity"), _ratio("net_income", "equity"),
               average_inputs=("equity",),
               optional_missing_note="no prior-year equity filed; period-end basis"),
    Comparison("roa", ("net_income", "total_assets"), _ratio("net_income", "total_assets")),
    Comparison("current_ratio", ("current_assets", "current_liabilities"),
               _ratio("current_assets", "current_liabilities")),
    # FMP maps cashAndShortTermInvestments off the ANNUAL balance sheet. Adding the
    # investment leg makes the measures identical: verified to 0.0% against FMP at the
    # matching fiscal year-end for MU, GOOG and NOW. The residual gap here is purely
    # as-of (FMP annual vs our MRQ), same as total_debt.
    Comparison("total_cash", ("cash",),
               lambda v: v["cash"] + v.get("short_term_investments", 0.0),
               optional=("short_term_investments",),
               optional_missing_note="no ST-investment tag filed; cash-only vs FMP "
                                     "cash+ST-investments",
               basis_note="FMP total_cash is annual balance-sheet; EDGAR is MRQ"),
    Comparison("shares_outstanding", ("shares_outstanding",),
               lambda v: v["shares_outstanding"]),
    # Components only, deliberately. The reported-total alternative (R3(a)) is confined
    # to the dark rows below: MU files a FRESH DebtAndCapitalLeaseObligations while its
    # component tags lag a quarter, so adopting it here would silently re-source an armed
    # row and erase the per-field-freshness case the ruling requires the table to show.
    Comparison("total_debt", ("long_term_debt", "current_debt"),
               lambda v: v["long_term_debt"] + v["current_debt"],
               basis_note="FMP totalDebt is annual balance-sheet; EDGAR is MRQ"),
    # R3(a) DARK: the same field satisfied by a directly-reported debt total where the
    # issuer files one. This is the only route to a total_debt row for WU, which files no
    # fresh current-portion tag at all.
    Comparison("total_debt", ("total_debt_reported",), _sum_debt_lease_inclusive,
               label="total_debt(reported)",
               input_alternatives=(("total_debt_reported",),),
               optional=("operating_lease_liability",),
               optional_missing_note="no operating-lease tag filed; gross debt vs FMP "
                                     "lease-inclusive totalDebt",
               dark=True,
               basis_note="FMP totalDebt is annual balance-sheet; EDGAR is MRQ"),
    # R3(b), ARMED 2026-08-09: the same field read at the issuer's latest fiscal
    # year-end, which is the basis FMP actually serves. The measures are proven identical
    # there — EDGAR cash+ST-investments matched FMP to 0.0% on MU, GOOG and NOW — so this
    # is a real like-for-like test where only a permanent advisory was possible before.
    # Issuers with no ST-investment tag (V, WU) fall to the cash-only advisory and are
    # never compared here.
    Comparison("total_cash", ("cash",),
               lambda v: v["cash"] + v.get("short_term_investments", 0.0),
               label="total_cash@FY", optional=("short_term_investments",),
               optional_missing_note="no ST-investment tag filed; cash-only vs FMP "
                                     "cash+ST-investments",
               period_basis="annual_fy", age_basis="alignment"),
    Comparison("total_debt", ("long_term_debt", "current_debt"),
               _sum_debt_lease_inclusive,
               label="total_debt@FY",
               input_alternatives=(("total_debt_reported",),
                                   ("long_term_debt", "current_debt")),
               optional=("operating_lease_liability",),
               optional_missing_note="no operating-lease tag filed; gross debt vs FMP "
                                     "lease-inclusive totalDebt",
               period_basis="annual_fy", age_basis="alignment", dark=True),
    Comparison("operating_cashflow", ("operating_cashflow",),
               lambda v: v["operating_cashflow"],
               basis_note="FMP cash-flow is annual; EDGAR is TTM"),
    Comparison("free_cashflow", ("operating_cashflow", "capex"),
               lambda v: v["operating_cashflow"] - v["capex"],
               basis_note="FMP cash-flow is annual; EDGAR is TTM"),
    # x100: the FMP side is normalised to PERCENT at the adapter boundary
    # (_ratio_to_percent), so the EDGAR side must speak percent too or the comparison
    # measures the unit difference instead of the definitional one. Both sides percent
    # -> the reported divergence is the genuine NET-vs-gross gap (~32%) rather than a
    # units artifact (~99%). The row stays permanently advisory either way.
    Comparison("debt_to_equity", ("long_term_debt", "current_debt", "equity"),
               lambda v: ((v["long_term_debt"] + v["current_debt"]) / v["equity"] * 100.0
                          if v["equity"] else None),
               basis_note="FMP debtToEquityRatioTTM is NET debt/equity; EDGAR is gross"),
)

# Verdicts
VERDICT_AGREE = "agree"                  # would upgrade → high
VERDICT_CONFLICT = "conflict"            # would downgrade → low
VERDICT_STALE_CAPPED = "stale_capped"    # too old/lagged to move confidence EITHER way
VERDICT_NO_EDGAR = "no_edgar"            # EDGAR could not resolve the inputs
VERDICT_NO_FMP = "no_fmp"                # FMP has no value to corroborate
VERDICT_BASIS_MISMATCH = "basis_mismatch"  # not comparable; advisory only


@dataclass
class FieldDelta:
    """One comparison's outcome for one field."""
    fmp_field: str
    verdict: str
    label: str = ""      # row key; differs from fmp_field when a field has several rows
    dark: bool = False   # computed and logged, never applied
    fmp_value: Optional[float] = None
    edgar_value: Optional[float] = None
    divergence_pct: Optional[float] = None
    period_end: Optional[str] = None       # oldest EDGAR input's period-end
    age_days: Optional[int] = None         # today - period_end (per-field freshness)
    current_confidence: Optional[Confidence] = None
    would_be_confidence: Optional[Confidence] = None
    would_be_source: Optional[str] = None  # engine's corroborated/CONFLICT source string
    edgar_inputs: str = ""                 # concept/method trail of the inputs used
    note: str = ""

    @property
    def would_change(self) -> bool:
        return (self.would_be_confidence is not None
                and self.would_be_confidence != self.current_confidence)


@dataclass
class CrossCheckReport:
    ticker: str
    as_of: str
    latest_period_end: Optional[str]
    deltas: List[FieldDelta] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    watch: Optional[str] = None      # FRESHNESS-WATCH line; informational only

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for d in self.deltas:
            out[d.verdict] = out.get(d.verdict, 0) + 1
        return out


def _age_days(period_end: Optional[str], today: str) -> Optional[int]:
    if not period_end:
        return None
    try:
        return (date.fromisoformat(today[:10]) - date.fromisoformat(period_end[:10])).days
    except ValueError:
        return None


def newest_filed_period(edgar: EdgarData) -> Optional[str]:
    """Newest fiscal period covered by a filing in the SUBMISSIONS index.

    Deliberately a different source from the XBRL facts: the submissions index lists the
    filing the moment it lands, while companyfacts populates on its own schedule. The gap
    between the two is what separates "issuer is late" from "the API is behind".
    """
    dates = [
        ref.report_date for ref in (list(edgar.recent_10k) + list(edgar.recent_10q))
        if ref.report_date
    ]
    return max(dates) if dates else None


def filing_freshness_flags(
    edgar: EdgarData, latest_period_end: Optional[str], today: str
) -> List[str]:
    """Flag stale XBRL facts, distinguishing the two causes.

    XBRL-LAG   — the issuer filed a newer period than companyfacts has published. The data
                 we hold is provably behind what exists; a day-count gate cannot see this
                 (V is 130d old, inside any sane threshold, yet a full quarter behind).
    MISSING-EXPECTED-10Q — no newer filing in the submissions index either, and the next
                 report is past due. Here the absence is the issuer's, not the API's.

    Silence must not read as freshness in either case.
    """
    flags: List[str] = []
    if not latest_period_end:
        return flags
    filed = newest_filed_period(edgar)
    if filed and filed > latest_period_end:
        flags.append(
            f"XBRL-LAG: submissions index has period {filed} but companyfacts tops out at "
            f"{latest_period_end} — EDGAR values are one filing behind FMP"
        )
        return flags
    try:
        end = date.fromisoformat(latest_period_end[:10])
        now = date.fromisoformat(today[:10])
    except ValueError:
        return flags
    overdue = (now - end).days - (QUARTER_DAYS + FILING_LAG_P90_DAYS)
    if overdue > 0:
        flags.append(
            f"MISSING-EXPECTED-10Q: newest period-end {latest_period_end}, nothing newer "
            f"filed — the next report was due ~{overdue}d ago (quarter {QUARTER_DAYS}d + "
            f"p90 lag {FILING_LAG_P90_DAYS}d)"
        )
    return flags


# ── FRESHNESS-WATCH (R-NEW, 2026-08-08) ──────────────────────────────────────
# Informational only — it never touches confidence. Its job is to answer the question a
# stale-looking figure always raises: when does better data arrive? The prediction is
# built from the ISSUER'S OWN history (its period cadence and its median filing lag), not
# from a global constant, because filing behaviour differs materially across the golden
# five (lags run 21-51d).
FRESHNESS_WATCH_DAYS = 60
_CADENCE_RANGE = (60, 130)   # plausible gap between consecutive fiscal period-ends


def _median(xs: List[int]) -> Optional[int]:
    if not xs:
        return None
    s = sorted(xs)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) // 2


def _all_filings(edgar: EdgarData) -> List[Any]:
    return list(edgar.recent_10k) + list(edgar.recent_10q)


def issuer_filing_lag(edgar: EdgarData) -> Optional[int]:
    """Median (filing date - period covered) over this issuer's recent filings.

    None when no filing carries a report_date — the fixture path, which records filings
    without one. Callers fall back to the golden-five p90 and say that they did.
    """
    return _median([
        d for d in (_age_days(ref.report_date, ref.date) for ref in _all_filings(edgar))
        if d is not None and d >= 0
    ])


_CADENCE_ANCHOR_FIELDS = ("total_assets", "equity", "cash")


def issuer_period_cadence(edgar: EdgarData) -> Optional[int]:
    """Median gap between this issuer's consecutive fiscal period-ends.

    Taken from the XBRL instants rather than the submissions index so it works offline,
    and so a 52/53-week filer's real cadence is measured instead of assumed to be 91d
    (MU reports 91d quarters with a 98d catch-up quarter in each 53-week year).

    Measured on ONE core balance-sheet concept, following the tag the issuer actually
    resolved to. Pooling every concept's instants poisons the median with dei cover-page
    dates, which sit between period-ends and halved MU's cadence to 77d.
    """
    concept = next(
        (rf.concept for name in _CADENCE_ANCHOR_FIELDS
         for rf in [edgar.financials.fields.get(name)]
         if rf is not None and rf.concept and not rf.concept.startswith("derived:")),
        None,
    )
    ends = sorted({
        r["end"] for r in edgar.financials.concepts.get(concept or "", [])
        if r.get("end") and not r.get("start")
    })
    gaps = [
        d for d in (_age_days(a, b) for a, b in zip(ends, ends[1:]))
        if d is not None and _CADENCE_RANGE[0] <= d <= _CADENCE_RANGE[1]
    ]
    return _median(gaps)


def _period_label(period_end: str, form: str) -> str:
    """'June-Q' / 'September-FY' — how a human refers to the period, per Vic's format."""
    try:
        month = date.fromisoformat(period_end[:10]).strftime("%B")
    except ValueError:
        return period_end
    return f"{month}-{'FY' if form.startswith('10-K') else 'Q'}"


def _next_form(edgar: EdgarData, next_period_end: str) -> str:
    """10-K if the next period-end lands on the issuer's fiscal year-end, else 10-Q."""
    fye = (edgar.fiscal_year_end or "").strip()      # 'MMDD' from the submissions index
    if len(fye) != 4 or not fye.isdigit():
        return "10-Q"
    try:
        end = date.fromisoformat(next_period_end[:10])
    except ValueError:
        return "10-Q"
    # 52/53-week filers drift a few days year to year, so match on proximity not equality.
    try:
        anchor = date(end.year, int(fye[:2]), int(fye[2:]))
    except ValueError:
        return "10-Q"
    return "10-K" if abs((end - anchor).days) <= 7 else "10-Q"


def freshness_watch(
    edgar: EdgarData, latest_period_end: Optional[str], today: str
) -> Optional[str]:
    """One informational line when EDGAR data is over FRESHNESS_WATCH_DAYS old.

    Two shapes, because a prediction is only honest when the data is genuinely absent:
      XBRL-LAG active — the filing already landed and extraction is pending. Predicting a
        filing date here would be predicting something that has already happened.
      otherwise — next expected period-end (issuer cadence) + issuer median filing lag.
    """
    age = _age_days(latest_period_end, today)
    if age is None or age <= FRESHNESS_WATCH_DAYS:
        return None
    head = f"[FRESHNESS-WATCH] {edgar.ticker}: EDGAR data {age}d old"

    filed = newest_filed_period(edgar)
    if filed and latest_period_end and filed > latest_period_end:
        ref = next((r for r in _all_filings(edgar) if r.report_date == filed), None)
        label = _period_label(filed, getattr(ref, "form", "10-Q"))
        when = f" filed {ref.date}" if ref is not None else ""
        return (f"{head}; {label}{when}, extraction pending (XBRL-LAG); "
                f"fresher data expected imminently")

    cadence = issuer_period_cadence(edgar) or QUARTER_DAYS
    lag = issuer_filing_lag(edgar)
    basis = "" if lag is not None else " (p90 lag — issuer filing history unavailable)"
    lag = lag if lag is not None else FILING_LAG_P90_DAYS
    try:
        end = date.fromisoformat(latest_period_end[:10])          # type: ignore[arg-type]
    except (ValueError, TypeError):
        return head
    next_end = end + timedelta(days=cadence)
    expected = next_end + timedelta(days=lag)
    form = _next_form(edgar, next_end.isoformat())
    return f"{head}; next {form} expected ~{expected.isoformat()}{basis}"


PRIOR_YEAR_WINDOW_DAYS = (300, 430)


def _prior_year_instant(
    concepts: Dict[str, List[Dict[str, Any]]], rf: ResolvedField
) -> Optional[float]:
    """Same concept's value roughly one year before rf's period-end.

    Looks up the tag the field actually resolved from, so an issuer on a migrated tag
    (V's equity) is followed rather than lost.
    """
    if not rf.concept or not rf.period_end:
        return None
    best_end, best_value = None, None
    for rec in concepts.get(rf.concept, []):
        end = rec.get("end")
        if rec.get("start") or not end or end >= rf.period_end:
            continue
        gap = _age_days(end, rf.period_end)
        if gap is None or not (PRIOR_YEAR_WINDOW_DAYS[0] <= gap <= PRIOR_YEAR_WINDOW_DAYS[1]):
            continue
        if best_end is None or end > best_end:
            best_end, best_value = end, float(rec["value"])
    return best_value


FY_END_TOLERANCE_DAYS = 7   # 52/53-week filers drift a few days year to year


def latest_fiscal_year_end(edgar: EdgarData) -> Optional[str]:
    """The issuer's most recent FISCAL YEAR END period, from its own filed instants.

    Matched on proximity to the submissions index's fiscal_year_end (MMDD) rather than
    equality, because 52/53-week filers move by a few days each year (MU's year-ends run
    2025-08-28, 2024-08-29, 2023-08-31).
    """
    fye = (edgar.fiscal_year_end or "").strip()
    if len(fye) != 4 or not fye.isdigit():
        return None
    concept = next(
        (rf.concept for name in _CADENCE_ANCHOR_FIELDS
         for rf in [edgar.financials.fields.get(name)]
         if rf is not None and rf.concept and not rf.concept.startswith("derived:")),
        None,
    )
    best: Optional[str] = None
    for rec in edgar.financials.concepts.get(concept or "", []):
        end = rec.get("end")
        if not end or rec.get("start"):
            continue
        try:
            d = date.fromisoformat(end[:10])
            anchor = date(d.year, int(fye[:2]), int(fye[2:]))
        except ValueError:
            continue
        if abs((d - anchor).days) <= FY_END_TOLERANCE_DAYS and (best is None or end > best):
            best = end
    return best


def _tracks_matched_period(
    fmp_value: float, matched_value: Optional[float], mrq_value: Optional[float]
) -> bool:
    """Is the primary's in-use value the MATCHED-period figure rather than the current one?

    The runtime half of the alignment scope (R-A condition 3). Non-circular: it does not
    ask whether FMP agrees with EDGAR, it asks WHICH OF TWO EDGAR PERIODS the FMP value
    tracks. A feed serving the annual balance sheet sits closer to the fiscal year-end
    figure than to the most recent quarter; one that has switched to MRQ does the
    opposite, and that flip revokes alignment aging.

    Fails CLOSED: when the two periods cannot be told apart — either counterpart missing,
    or the two EDGAR figures identical — the premise is unverifiable and alignment is
    withheld.
    """
    if matched_value is None or mrq_value is None:
        return False
    if matched_value == mrq_value:
        return False
    return abs(fmp_value - matched_value) < abs(fmp_value - mrq_value)


def _newer_fiscal_year_filed(edgar: EdgarData, matched_fy: Optional[str]) -> Optional[str]:
    """A 10-K covering a LATER fiscal year than the one we matched, per the submissions
    index — i.e. newer annual data exists that companyfacts has not published.

    The XBRL-LAG check still applies to alignment rows (R-A): matching periods says
    nothing about whether a fresher matched pair is already available. A quarterly lag is
    correctly ignored here — V being a quarter behind does not make its FY-2025 figures
    the wrong ones to compare against an annual FMP field.
    """
    if not matched_fy:
        return None
    later = [ref.report_date for ref in edgar.recent_10k
             if ref.report_date and ref.report_date > matched_fy]
    return max(later) if later else None


def _instant_at(
    concepts: Dict[str, List[Dict[str, Any]]], rf: ResolvedField, target_end: str
) -> Optional[float]:
    """The same concept's value at a specific period-end, or None if not filed then.

    Follows the tag the field actually resolved to, so a migrated issuer is tracked
    rather than lost — the same rule _prior_year_instant uses.
    """
    if not rf.concept:
        return None
    for rec in concepts.get(rf.concept, []):
        if rec.get("end") == target_end and not rec.get("start"):
            return float(rec["value"])
    return None


def _required_inputs(
    comparison: Comparison, fields: Dict[str, ResolvedField]
) -> Tuple[str, ...]:
    """The input set this comparison will run on: the first fully-resolved alternative,
    else its declared inputs (so an unresolved run still reports what was missing)."""
    for alt in comparison.input_alternatives:
        if all((rf := fields.get(n)) is not None and rf.is_resolved() for n in alt):
            return alt
    return comparison.input_alternatives[-1] if comparison.input_alternatives \
        else comparison.inputs


def _gather_inputs(
    comparison: Comparison,
    fields: Dict[str, ResolvedField],
    concepts: Dict[str, List[Dict[str, Any]]],
    match_period: Optional[str] = None,
) -> Tuple[Optional[Dict[str, float]], Optional[str], str, str, List[str]]:
    """Collect a comparison's EDGAR inputs.

    Returns (values, oldest_period_end, trail, missing_required, missing_optional).
    values is None when a REQUIRED input is unresolved — a comparison is never run on a
    partial required set. Missing optional inputs are reported, not fatal.
    """
    values: Dict[str, float] = {}
    oldest: Optional[str] = None
    trail_parts: List[str] = []
    missing: List[str] = []
    missing_optional: List[str] = []

    required_names = _required_inputs(comparison, fields)
    for name in tuple(required_names) + comparison.optional:
        required = name in required_names
        rf = fields.get(name)
        if rf is None or not rf.is_resolved():
            (missing if required else missing_optional).append(
                f"{name}({rf.reason if rf else 'absent'})")
            continue

        if match_period is not None:
            # Period-matched: re-read the SAME concept at the target period-end. An input
            # the issuer did not file then is missing, never silently the MRQ figure.
            matched = _instant_at(concepts, rf, match_period)
            if matched is None:
                (missing if required else missing_optional).append(
                    f"{name}(not filed @{match_period})")
                continue
            values[name] = matched
            trail_parts.append(f"{name}={rf.concept}@{match_period}")
            if oldest is None or match_period < oldest:
                oldest = match_period
            continue

        value = float(rf.value)                 # type: ignore[arg-type]
        label = f"{name}={rf.concept}/{rf.method}@{rf.period_end}"
        if name in comparison.average_inputs:
            prior = _prior_year_instant(concepts, rf)
            if prior is None:
                missing_optional.append(f"{name}_prior_year(absent)")
            else:
                value = (value + prior) / 2.0
                label += "(avg w/ prior yr)"
        values[name] = value
        trail_parts.append(label)
        if rf.period_end and (oldest is None or rf.period_end < oldest):
            oldest = rf.period_end

    trail = "; ".join(trail_parts)
    if missing:
        return None, oldest, trail, ", ".join(missing), missing_optional
    return values, oldest, trail, "", missing_optional


def compute_cross_check(
    edgar: EdgarData,
    ticker_data: Any,
    today: Optional[str] = None,
    threshold_days: int = FRESHNESS_THRESHOLD_DAYS,
    lag_aware: bool = True,
) -> CrossCheckReport:
    """Compute the would-be confidence delta for every comparable field.

    Pure: reads EDGAR + TickerData, mutates neither.

    lag_aware also caps a field when the submissions index proves newer data exists that
    companyfacts has not published yet — a condition no day-count threshold can detect.
    Pass False to see what a pure age gate alone would do.
    """
    today = today or date.today().isoformat()
    latest = edgar.financials.latest_period_end
    report = CrossCheckReport(ticker=edgar.ticker, as_of=today, latest_period_end=latest)
    report.flags.extend(filing_freshness_flags(edgar, latest, today))
    report.watch = freshness_watch(edgar, latest, today)

    filed = newest_filed_period(edgar)
    behind = filed if (lag_aware and filed and latest and filed > latest) else None

    fields = edgar.financials.fields
    fy_end = latest_fiscal_year_end(edgar)
    for comp in COMPARISONS:
        label = comp.label or comp.fmp_field
        fmp_prov: Optional[Prov] = getattr(ticker_data, comp.fmp_field, None)
        current = fmp_prov.confidence if fmp_prov is not None else None

        match_period = fy_end if comp.period_basis == "annual_fy" else None
        if comp.period_basis == "annual_fy" and match_period is None:
            report.deltas.append(FieldDelta(
                fmp_field=comp.fmp_field, label=label, dark=comp.dark,
                verdict=VERDICT_NO_EDGAR,
                fmp_value=None if fmp_prov is None or fmp_prov.is_missing() else fmp_prov.value,
                current_confidence=current, would_be_confidence=current,
                note="no fiscal year-end period identifiable for this issuer",
            ))
            continue

        values, oldest, trail, missing, missing_opt = _gather_inputs(
            comp, fields, edgar.financials.concepts, match_period)

        # The MRQ counterpart of a matched-period row, used only to re-check the
        # alignment scope below — never compared against, never shown as the value.
        mrq_counterpart: Optional[float] = None
        if match_period is not None:
            mrq_values, *_ = _gather_inputs(comp, fields, edgar.financials.concepts)
            if mrq_values is not None:
                try:
                    mrq_counterpart = comp.compute(mrq_values)
                except (KeyError, TypeError, ZeroDivisionError):
                    mrq_counterpart = None

        if values is None:
            report.deltas.append(FieldDelta(
                fmp_field=comp.fmp_field, label=label, dark=comp.dark,
                verdict=VERDICT_NO_EDGAR,
                fmp_value=None if fmp_prov is None or fmp_prov.is_missing() else fmp_prov.value,
                current_confidence=current, would_be_confidence=current,
                edgar_inputs=trail, note=f"EDGAR unresolved: {missing}",
            ))
            continue

        edgar_value = comp.compute(values)
        age = _age_days(oldest, today)

        if fmp_prov is None or fmp_prov.is_missing() or edgar_value is None:
            report.deltas.append(FieldDelta(
                fmp_field=comp.fmp_field, label=label, dark=comp.dark,
                verdict=VERDICT_NO_FMP,
                edgar_value=edgar_value, period_end=oldest, age_days=age,
                current_confidence=current, would_be_confidence=current,
                edgar_inputs=trail,
                note="FMP field missing" if edgar_value is not None else "EDGAR value undefined",
            ))
            continue

        try:
            divergence = (abs(float(fmp_prov.value) - edgar_value)
                          / abs(float(fmp_prov.value)) * 100.0
                          if float(fmp_prov.value) else None)
        except (TypeError, ValueError):
            divergence = None

        # Known non-comparable basis — declared, or created by an absent optional input
        # that would have aligned the measures. Measured and shown, but never allowed to
        # move confidence in either direction.
        advisory = comp.basis_note
        if missing_opt and comp.optional_missing_note:
            advisory = "; ".join(filter(None, [
                advisory, f"{comp.optional_missing_note} [{', '.join(missing_opt)}]"]))
        if advisory:
            report.deltas.append(FieldDelta(
                fmp_field=comp.fmp_field, label=label, dark=comp.dark,
                verdict=VERDICT_BASIS_MISMATCH,
                fmp_value=fmp_prov.value, edgar_value=edgar_value,
                divergence_pct=divergence, period_end=oldest, age_days=age,
                current_confidence=current, would_be_confidence=current,
                edgar_inputs=trail, note=advisory,
            ))
            continue

        checked = apply_cross_check(
            fmp_prov, edgar_value, SECONDARY_SOURCE, oldest,
            tolerance_pct=DIVERGENCE_TOLERANCE_PCT,
        )
        # R-A: alignment aging is re-earned on every evaluation, never assumed. Scope
        # conditions 1 and 2 are structural (matched period; a missing aligning input
        # made the row advisory above); condition 3 is checked here against the feed as
        # it actually behaves today.
        aligned = False
        scope_note = ""
        if comp.age_basis == "alignment" and match_period is not None:
            newer_fy = _newer_fiscal_year_filed(edgar, match_period)
            if newer_fy:
                scope_note = (f"alignment revoked — FY {newer_fy} filed but not yet in "
                              f"companyfacts (matched {match_period})")
            elif not _tracks_matched_period(
                    float(fmp_prov.value), edgar_value, mrq_counterpart):
                scope_note = ("alignment revoked — FMP value no longer tracks the "
                              f"matched period (FMP {float(fmp_prov.value):.4g} vs "
                              f"matched {edgar_value:.4g} vs MRQ "
                              f"{mrq_counterpart if mrq_counterpart is None else format(mrq_counterpart, '.4g')})"
                              "; aged absolutely")
            else:
                aligned = True

        # Aligned rows see a zero gap; everything else ages absolutely. The absolute age
        # is recorded in the row either way.
        days_for_gate = 0 if aligned else (age if age is not None else 10**6)
        stale_by_lag = bool(behind and (oldest or "") < behind and not aligned)
        if stale_by_lag:
            days_for_gate = max(days_for_gate, threshold_days + 1)

        # R1 — SYMMETRIC GATING (ruling 2026-08-08). A source too stale to RAISE
        # confidence is equally too stale to LOWER it. apply_staleness_penalty only caps
        # 'high', so the gate is probed with the upgrade case and its answer suppresses
        # BOTH directions: a conflict measured on stale or lagged data renders
        # stale_capped, keeps its divergence in the log, and moves nothing.
        probe = apply_staleness_penalty(
            Prov(value=checked.value, source=checked.source,
                 as_of=checked.as_of, confidence="high"),
            days_for_gate, stale_threshold=threshold_days,
        )
        is_stale = probe.confidence != "high"

        note = ""
        would_be_source = None
        if is_stale:
            verdict = VERDICT_STALE_CAPPED
            would_be = current                       # neither direction moves
            suppressed = {"high": "agreement", "low": "conflict"}.get(
                checked.confidence, "no signal")
            note = f"{suppressed} suppressed — " + (
                f"XBRL behind submissions (newer period {behind} filed)" if stale_by_lag
                else f"age {age}d > {threshold_days}d threshold")
        elif checked.confidence == "high":
            verdict, would_be = VERDICT_AGREE, checked.confidence
            would_be_source = checked.source
        elif checked.confidence == "low":
            verdict, would_be = VERDICT_CONFLICT, checked.confidence
            would_be_source = checked.source
        else:
            verdict, would_be = VERDICT_STALE_CAPPED, current

        if comp.age_basis == "alignment":
            basis = (f"matched period {oldest} (abs age {age}d); gated on alignment"
                     if aligned else scope_note)
            note = "; ".join(filter(None, [basis, note]))

        report.deltas.append(FieldDelta(
            fmp_field=comp.fmp_field, label=label, dark=comp.dark, verdict=verdict,
            fmp_value=fmp_prov.value, edgar_value=edgar_value,
            divergence_pct=divergence, period_end=oldest, age_days=age,
            current_confidence=current, would_be_confidence=would_be,
            would_be_source=would_be_source, edgar_inputs=trail, note=note,
        ))

    return report


def render_report(report: CrossCheckReport, applied: Optional[List[str]] = None) -> str:
    """Human-readable delta table.

    Permanent verdict logging: this renders on EVERY evaluation, armed or dark, so the
    calibration record continues after arming. `applied` is the list of fields actually
    written back — None means the report was computed but not applied (dark).
    """
    mode = "dark" if applied is None else "ARMED"
    head = ("APPLIED=NOTHING" if applied is None
            else f"APPLIED={len(applied)} field(s)")
    lines = [
        f"[EDGAR-XCHECK {mode}] {report.ticker}  as_of={report.as_of}  "
        f"latest_period_end={report.latest_period_end}  {head}",
        f"  {'field':20s} {'FMP':>16s} {'EDGAR':>16s} {'div%':>8s} "
        f"{'period_end':>12s} {'age':>5s}  {'conf→would-be':16s} verdict",
    ]
    for d in sorted(report.deltas, key=lambda d: (d.label or d.fmp_field)):
        fmp = f"{d.fmp_value:,.4g}" if isinstance(d.fmp_value, (int, float)) else "—"
        edg = f"{d.edgar_value:,.4g}" if isinstance(d.edgar_value, (int, float)) else "—"
        div = f"{d.divergence_pct:.1f}" if d.divergence_pct is not None else "—"
        age = f"{d.age_days}d" if d.age_days is not None else "—"
        move = f"{d.current_confidence or '—'}→{d.would_be_confidence or '—'}"
        # A dark row is marked 'd', never '*': it cannot change anything yet.
        mark = "d" if d.dark else ("*" if d.would_change else " ")
        lines.append(
            f" {mark}{(d.label or d.fmp_field):20s} {fmp:>16s} {edg:>16s} {div:>8s} "
            f"{(d.period_end or '—'):>12s} {age:>5s}  {move:16s} {d.verdict}"
            + (f"  [{d.note}]" if d.note else "")
        )
    for f in report.flags:
        lines.append(f"  FLAG {f}")
    if report.watch:
        lines.append(f"  {report.watch}")
    counts = ", ".join(f"{k}={v}" for k, v in sorted(report.counts().items()))
    changes = sum(1 for d in report.deltas if d.would_change and not d.dark)
    tail = ("(none applied — dark)" if applied is None
            else f"applied {len(applied)}: {', '.join(applied)}" if applied
            else "(nothing to apply)")
    lines.append(f"  totals: {counts} | would-change {changes}/{len(report.deltas)} "
                 f"{tail}")
    return "\n".join(lines)


# Only these two verdicts may move confidence. basis_mismatch, stale_capped, no_edgar and
# no_fmp are measured and logged, and leave the field exactly as the feed delivered it.
APPLICABLE_VERDICTS = (VERDICT_AGREE, VERDICT_CONFLICT)


def apply_report(report: CrossCheckReport, ticker_data: Any) -> List[str]:
    """Write the report's verdicts back onto the TickerData Provs. ARMED path.

    Mutates confidence and source ONLY — the value a field carries is never touched by a
    cross-check, exactly as the AlphaVantage engine behaved before it was torn out. The
    source string records the corroboration ("FMP+EDGAR") or the conflict with both
    values and as-of stamps, so a downgraded field says why on inspection.

    Returns the fields actually changed, for the log.
    """
    movers: Dict[str, List[FieldDelta]] = {}
    for d in report.deltas:
        if d.dark or d.verdict not in APPLICABLE_VERDICTS or not d.would_change:
            continue
        if d.would_be_confidence is not None:
            movers.setdefault(d.fmp_field, []).append(d)

    applied: List[str] = []
    for field_name, deltas in movers.items():
        prov: Optional[Prov] = getattr(ticker_data, field_name, None)
        if prov is None:
            continue
        # A field can carry several armed rows (total_cash has an MRQ and an @FY row).
        # If they disagree there is no defensible answer, so take none of them and say
        # so — a contradiction resolved by row order would be silent degradation.
        verdicts = {d.would_be_confidence for d in deltas}
        if len(verdicts) > 1:
            applied.append(
                f"!CONTRADICTION {field_name}: "
                + ", ".join(f"{d.label or d.fmp_field}→{d.would_be_confidence}"
                            for d in deltas)
                + " — nothing applied")
            continue
        d = deltas[0]
        prov.confidence = d.would_be_confidence     # type: ignore[assignment]
        if d.would_be_source:
            prov.source = d.would_be_source
        applied.append(f"{field_name}→{d.would_be_confidence}")
    return applied


def run_cross_check(
    edgar: EdgarData,
    ticker_data: Any,
    log: Optional[Callable[[str], None]] = None,
    apply: bool = True,
) -> Optional[CrossCheckReport]:
    """Compute, apply (when armed) and log. ARMED at both boundaries since 2026-08-08.

    Application is all-or-nothing: the report is computed in full first, so a failure
    mid-computation cannot leave some fields corroborated and others not.

    Exceptions are still contained, and the reasoning has NOT changed with arming. What
    this component moves is the confidence LABEL and source string; it cannot move a
    value, a score, an E(R) or a grade. Its only reach into output is the anti-launder
    NOTE. A failure therefore degrades to exactly the pre-EDGAR state — every field stays
    at the feed's 'medium', which can never launder a miss into high confidence — and it
    is reported loudly rather than silently swallowed.
    """
    emit = log or print
    try:
        report = compute_cross_check(edgar, ticker_data)
        applied = apply_report(report, ticker_data) if apply else None
        emit(render_report(report, applied))
        return report
    except Exception as e:                              # noqa: BLE001 — see docstring
        emit(f"[EDGAR-XCHECK] FAILED for {getattr(edgar, 'ticker', '?')}: "
             f"{type(e).__name__}: {e} — NOTHING APPLIED, all fields remain at feed "
             f"confidence (cannot move a value, score, E(R) or grade)")
        return None


def run_dark_cross_check(
    edgar: EdgarData, ticker_data: Any, log: Optional[Callable[[str], None]] = None
) -> Optional[CrossCheckReport]:
    """Compute and log without applying — the calibration path, kept for replays."""
    return run_cross_check(edgar, ticker_data, log=log, apply=False)
