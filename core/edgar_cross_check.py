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
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from adapters.base import Confidence, Prov
from adapters.edgar_adapter import EdgarData, ResolvedField
from core.cross_check import apply_cross_check, apply_staleness_penalty

SECONDARY_SOURCE = "EDGAR"

# ── Freshness threshold (PROPOSED — NOT ARMED) ───────────────────────────────
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
    average_inputs: Tuple[str, ...] = ()
    """Inputs averaged with their prior-year value ((begin + end) / 2).

    FMP's returnOnEquityTTM is computed on average equity. Measured against period-end
    equity the gap tracks equity growth exactly — 29.0% on MU and 25.0% on GOOG, the two
    fastest compounders, versus ~2-3% on the rest. Averaging is basis alignment, not a
    fudge factor.
    """


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
    Comparison("total_debt", ("long_term_debt", "current_debt"),
               lambda v: v["long_term_debt"] + v["current_debt"],
               basis_note="FMP totalDebt is annual balance-sheet; EDGAR is MRQ"),
    Comparison("operating_cashflow", ("operating_cashflow",),
               lambda v: v["operating_cashflow"],
               basis_note="FMP cash-flow is annual; EDGAR is TTM"),
    Comparison("free_cashflow", ("operating_cashflow", "capex"),
               lambda v: v["operating_cashflow"] - v["capex"],
               basis_note="FMP cash-flow is annual; EDGAR is TTM"),
    Comparison("debt_to_equity", ("long_term_debt", "current_debt", "equity"),
               lambda v: ((v["long_term_debt"] + v["current_debt"]) / v["equity"]
                          if v["equity"] else None),
               basis_note="FMP debtToEquityRatioTTM is NET debt/equity; EDGAR is gross"),
)

# Verdicts
VERDICT_AGREE = "agree"                  # would upgrade → high
VERDICT_CONFLICT = "conflict"            # would downgrade → low
VERDICT_STALE_CAPPED = "stale_capped"    # agrees, but too old to upgrade → medium
VERDICT_NO_EDGAR = "no_edgar"            # EDGAR could not resolve the inputs
VERDICT_NO_FMP = "no_fmp"                # FMP has no value to corroborate
VERDICT_BASIS_MISMATCH = "basis_mismatch"  # not comparable; advisory only


@dataclass
class FieldDelta:
    """What the cross-check WOULD have done to one field. Nothing is applied."""
    fmp_field: str
    verdict: str
    fmp_value: Optional[float] = None
    edgar_value: Optional[float] = None
    divergence_pct: Optional[float] = None
    period_end: Optional[str] = None       # oldest EDGAR input's period-end
    age_days: Optional[int] = None         # today - period_end (per-field freshness)
    current_confidence: Optional[Confidence] = None
    would_be_confidence: Optional[Confidence] = None
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


def _gather_inputs(
    comparison: Comparison,
    fields: Dict[str, ResolvedField],
    concepts: Dict[str, List[Dict[str, Any]]],
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

    for name in comparison.inputs + comparison.optional:
        required = name in comparison.inputs
        rf = fields.get(name)
        if rf is None or not rf.is_resolved():
            (missing if required else missing_optional).append(
                f"{name}({rf.reason if rf else 'absent'})")
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

    filed = newest_filed_period(edgar)
    behind = filed if (lag_aware and filed and latest and filed > latest) else None

    fields = edgar.financials.fields
    for comp in COMPARISONS:
        fmp_prov: Optional[Prov] = getattr(ticker_data, comp.fmp_field, None)
        current = fmp_prov.confidence if fmp_prov is not None else None
        values, oldest, trail, missing, missing_opt = _gather_inputs(
            comp, fields, edgar.financials.concepts)

        if values is None:
            report.deltas.append(FieldDelta(
                fmp_field=comp.fmp_field, verdict=VERDICT_NO_EDGAR,
                fmp_value=None if fmp_prov is None or fmp_prov.is_missing() else fmp_prov.value,
                current_confidence=current, would_be_confidence=current,
                edgar_inputs=trail, note=f"EDGAR unresolved: {missing}",
            ))
            continue

        edgar_value = comp.compute(values)
        age = _age_days(oldest, today)

        if fmp_prov is None or fmp_prov.is_missing() or edgar_value is None:
            report.deltas.append(FieldDelta(
                fmp_field=comp.fmp_field, verdict=VERDICT_NO_FMP,
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
                fmp_field=comp.fmp_field, verdict=VERDICT_BASIS_MISMATCH,
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
        days_for_gate = age if age is not None else 10**6
        stale_by_lag = bool(behind and (oldest or "") < behind)
        if stale_by_lag:
            days_for_gate = max(days_for_gate, threshold_days + 1)
        aged = apply_staleness_penalty(
            checked, days_for_gate, stale_threshold=threshold_days
        )
        if checked.confidence == "high" and aged.confidence != "high":
            verdict = VERDICT_STALE_CAPPED
        elif aged.confidence == "high":
            verdict = VERDICT_AGREE
        elif aged.confidence == "low":
            verdict = VERDICT_CONFLICT
        else:
            verdict = VERDICT_STALE_CAPPED

        report.deltas.append(FieldDelta(
            fmp_field=comp.fmp_field, verdict=verdict,
            fmp_value=fmp_prov.value, edgar_value=edgar_value,
            divergence_pct=divergence, period_end=oldest, age_days=age,
            current_confidence=current, would_be_confidence=aged.confidence,
            edgar_inputs=trail,
            note=("XBRL behind submissions (newer period %s filed)" % behind
                  if verdict == VERDICT_STALE_CAPPED and stale_by_lag
                  else f"age {age}d > {threshold_days}d threshold"
                  if verdict == VERDICT_STALE_CAPPED else ""),
        ))

    return report


def render_report(report: CrossCheckReport) -> str:
    """Human-readable delta table (used by the dark log and the calibration report)."""
    lines = [
        f"[EDGAR-XCHECK dark] {report.ticker}  as_of={report.as_of}  "
        f"latest_period_end={report.latest_period_end}  APPLIED=NOTHING",
        f"  {'field':20s} {'FMP':>16s} {'EDGAR':>16s} {'div%':>8s} "
        f"{'period_end':>12s} {'age':>5s}  {'conf→would-be':16s} verdict",
    ]
    for d in sorted(report.deltas, key=lambda d: d.fmp_field):
        fmp = f"{d.fmp_value:,.4g}" if isinstance(d.fmp_value, (int, float)) else "—"
        edg = f"{d.edgar_value:,.4g}" if isinstance(d.edgar_value, (int, float)) else "—"
        div = f"{d.divergence_pct:.1f}" if d.divergence_pct is not None else "—"
        age = f"{d.age_days}d" if d.age_days is not None else "—"
        move = f"{d.current_confidence or '—'}→{d.would_be_confidence or '—'}"
        mark = "*" if d.would_change else " "
        lines.append(
            f" {mark}{d.fmp_field:20s} {fmp:>16s} {edg:>16s} {div:>8s} "
            f"{(d.period_end or '—'):>12s} {age:>5s}  {move:16s} {d.verdict}"
            + (f"  [{d.note}]" if d.note else "")
        )
    for f in report.flags:
        lines.append(f"  FLAG {f}")
    counts = ", ".join(f"{k}={v}" for k, v in sorted(report.counts().items()))
    changes = sum(1 for d in report.deltas if d.would_change)
    lines.append(f"  totals: {counts} | would-change {changes}/{len(report.deltas)} "
                 f"(none applied — dark)")
    return "\n".join(lines)


def run_dark_cross_check(
    edgar: EdgarData, ticker_data: Any, log: Optional[Callable[[str], None]] = None
) -> Optional[CrossCheckReport]:
    """Compute and log the delta table. Returns the report; changes nothing.

    Exceptions are contained deliberately. The hard-stop discipline applies to signals
    that gate output — this component gates nothing, so a bug in it must not be able to
    take down an evaluation it cannot influence. It reports its own failure loudly instead.
    """
    emit = log or print
    try:
        report = compute_cross_check(edgar, ticker_data)
        emit(render_report(report))
        return report
    except Exception as e:                              # noqa: BLE001 — see docstring
        emit(f"[EDGAR-XCHECK dark] FAILED for {getattr(edgar, 'ticker', '?')}: "
             f"{type(e).__name__}: {e} (dark component; evaluation unaffected)")
        return None
