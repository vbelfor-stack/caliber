"""Phase G — corporate-actions integrity: split detection and basis restatement.

THE DEFECT. FMP prices are split-adjusted back to today's basis; EDGAR share counts are
AS FILED and are not restated. Multiplying them across a split yields a market cap wrong
by exactly the split factor, so the own-history earnings yield is wrong by that factor —
GOOG's pre-2022 quarters read ~81% against a ~4% norm, a clean 20x.

THE RULE (ruled 2026-08-11). A fact is on the basis in effect at its FILING date:

    adjusted = raw_value x prod{ ratio : split.ex_date > fact.first_filed }

No discontinuity inference. NAIVE ADJACENT-RATIO DETECTION IS REJECTED PERMANENTLY, on
measured evidence: the share series is MIXED-BASIS, because a post-split filing restates
SOME prior period-ends (annual comparatives) and not others (original 10-Q cover pages).
A ratio detector therefore fires three times on GOOG (20:1, 1:20, 20:1) and poisons 2 of
20 quarters — while the MEDIAN BARELY MOVES (4.43% -> 4.26%). The corruption is invisible
in the aggregate and real in the series, which is why G is validated PER POINT.

CORROBORATION (ruled): a split ratio must be attested by 2 OF 3 witnesses before it is
used. The DATE always comes from FMP — EDGAR dates a split to a declaration or record
date (GOOG 07-15 vs ex 07-18; NOW 12-05 vs ex 12-18), and only the ex-date matches the
basis FMP adjusted its own prices on.

    fmp_splits          FMP /stable/splits          ex-date + exact numerator/denominator
    edgar_restatement   same period-end filed twice on two bases   ZERO extra cost
    edgar_tagged_ratio  StockholdersEquityNoteStockSplitConversionRatio1

Two of the three sit inside EDGAR and are therefore INDEPENDENT OF FMP, which is the
whole point: FMP is the sole live feed, and an uncorroborated split ratio fails as a
clean 5x or 20x that reads as a valuation rather than as an error.

This is the pipeline's FIRST corroborated-by-design input, and the intended template for
the beta cross-check.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

WITNESS_FMP = "fmp_splits"
WITNESS_RESTATEMENT = "edgar_restatement"
WITNESS_TAGGED = "edgar_tagged_ratio"

# Concepts whose instant facts carry a share count. A restatement witness is two DIFFERENT
# values filed for one period-end on these.
_SHARE_CONCEPTS = ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding")
_TAGGED_CONCEPT = "StockholdersEquityNoteStockSplitConversionRatio1"

# A witness ratio must differ from 1 by at least this much. Filings disagree at the last
# digit for ordinary rounding reasons — NOW reports 2020-12-31 as both 195,844,000 and
# 195,845,000 (ratio 1.00001) — and none of that is a corporate action.
MIN_RATIO_DEVIATION = 0.10

# How close two witnesses must sit to be treated as attesting the same ratio. The measured
# agreements are far inside this: GOOG 20 vs 19.99937 (0.003%), NOW 5 vs 5.00001 (0.000%).
RATIO_AGREEMENT_TOLERANCE = 0.02

REQUIRED_WITNESSES = 2


@dataclass
class SplitEvent:
    """One corporate action, with the evidence that it happened at that ratio."""
    ex_date: str
    ratio: float
    witnesses: List[str] = field(default_factory=list)
    detail: str = ""

    @property
    def corroborated(self) -> bool:
        return len(self.witnesses) >= REQUIRED_WITNESSES


@dataclass
class SplitReport:
    """Everything the restatement knows, including what it deliberately refused to use."""
    ticker: str
    events: List[SplitEvent] = field(default_factory=list)
    out_of_scope: List[str] = field(default_factory=list)
    rejected: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    horizon: Optional[str] = None

    @property
    def usable(self) -> List[SplitEvent]:
        return [e for e in self.events if e.corroborated]

    @property
    def has_uncorroborated(self) -> bool:
        return any(not e.corroborated for e in self.events)


def earliest_share_filing(financials: Any) -> Optional[str]:
    """Oldest filing date behind any share fact — the restatement's SCOPE HORIZON.

    Nothing older than this exists to be adjusted, so a split with an earlier ex-date
    cannot change a single value (`split_factor` compares ex-date against a filing date
    and would multiply by 1.0 regardless).

    THIS IS WHY THE HORIZON EXISTS, and it is not a convenience. EDGAR's XBRL record only
    begins ~2009, so a pre-XBRL split can NEVER earn a second witness: MU's splits are
    1994-2000, JPM's 1982-2000, USB's 1979-2001. Demanding 2-of-3 for those would leave
    every one of those tickers permanently uncorroborated and force a withhold — strictly
    worse than today's behaviour, over splits that provably cannot move a number. Scoping
    the requirement to splits that can actually apply is what keeps the loud warning
    meaningful for the case that matters: an in-window split only FMP attests to.
    """
    dates = [r["first_filed"]
             for c in _SHARE_CONCEPTS
             for r in (getattr(financials, "concepts", {}) or {}).get(c, [])
             if r.get("first_filed")]
    return min(dates) if dates else None


def _instants(financials: Any, concept: str) -> Dict[str, set]:
    """{period_end: {values}} for one concept's instant facts."""
    out: Dict[str, set] = {}
    for r in (getattr(financials, "concepts", {}) or {}).get(concept, []):
        if r.get("end") and not r.get("start") and r.get("value"):
            out.setdefault(r["end"], set()).add(float(r["value"]))
    return out


def restatement_witnesses(financials: Any) -> List[Tuple[float, str]]:
    """Split ratios implied by one period-end being filed at two materially different values.

    A post-split filing restates a prior period-end onto the new basis while the original
    filing's value survives in companyfacts. The two therefore differ by EXACTLY the split
    ratio, measured from the issuer's own filings at no extra fetch cost.
    """
    found: List[Tuple[float, str]] = []
    for concept in _SHARE_CONCEPTS:
        for end, values in sorted(_instants(financials, concept).items(), reverse=True):
            if len(values) < 2:
                continue
            lo, hi = min(values), max(values)
            ratio = hi / lo if lo else 0.0
            if abs(ratio - 1.0) < MIN_RATIO_DEVIATION:
                continue        # filing-precision noise, not a corporate action
            found.append((ratio, f"{concept}@{end}: {lo:,.0f} vs {hi:,.0f}"))
    return found


def tagged_ratio_witnesses(financials: Any) -> List[Tuple[float, str]]:
    """Split ratios the issuer tagged explicitly in XBRL.

    The date on these is a declaration/record date, NOT an ex-date, so only the ratio is
    taken from here — see the module docstring.
    """
    out: List[Tuple[float, str]] = []
    for r in (getattr(financials, "concepts", {}) or {}).get(_TAGGED_CONCEPT, []):
        val = r.get("value")
        if val and abs(float(val) - 1.0) >= MIN_RATIO_DEVIATION:
            out.append((float(val), f"{_TAGGED_CONCEPT}@{r.get('end')}: {float(val):g}"))
    return out


def _agrees(a: float, b: float) -> bool:
    return abs(a - b) / b <= RATIO_AGREEMENT_TOLERANCE if b else False


def build_split_report(
    ticker: str, fmp_splits: List[Dict[str, Any]], financials: Any
) -> SplitReport:
    """Assemble corroborated split events. PURE — fetches nothing, applies nothing."""
    horizon = earliest_share_filing(financials)
    report = SplitReport(ticker=ticker, horizon=horizon)
    restatements = restatement_witnesses(financials)
    tagged = tagged_ratio_witnesses(financials)
    # Every ratio FMP reports, in-scope or not. The unplaceable scan below asks whether FMP
    # KNOWS about a ratio, which is a different question from whether we will apply it —
    # without this, scoping an old split out would re-report it as missing from FMP.
    reported_ratios: List[float] = []

    for row in fmp_splits or []:
        ratio, ex = float(row["ratio"]), row["ex_date"]
        if abs(ratio - 1.0) < MIN_RATIO_DEVIATION:
            report.rejected.append(f"{ex} ratio {ratio:g} — within noise of 1:1, ignored")
            continue
        reported_ratios.append(ratio)
        if horizon and ex <= horizon:
            report.out_of_scope.append(
                f"{ex} {ratio:g}:1 — predates the oldest share filing ({horizon}), "
                f"cannot apply to any fact")
            continue
        witnesses, bits = [WITNESS_FMP], [f"fmp {ratio:g} ex {ex}"]
        for pool, name in ((restatements, WITNESS_RESTATEMENT), (tagged, WITNESS_TAGGED)):
            hit = next((d for r, d in pool if _agrees(r, ratio)), None)
            if hit:
                witnesses.append(name)
                bits.append(hit)
        ev = SplitEvent(ex_date=ex, ratio=ratio, witnesses=witnesses,
                        detail="; ".join(bits))
        report.events.append(ev)
        if not ev.corroborated:
            report.notes.append(
                f"UNCORROBORATED SPLIT {ticker} {ex} {ratio:g}:1 — FMP is the only witness "
                f"(single-source). EDGAR offers no restatement or tagged ratio for it.")

    # A ratio EDGAR attests but FMP does not report has no ex-date, so it cannot be placed
    # on the timeline and cannot be applied. Loud, because it means a real corporate action
    # is missing from the source that sets the price basis.
    for pool, name in ((restatements, WITNESS_RESTATEMENT), (tagged, WITNESS_TAGGED)):
        for r, detail in pool:
            if not any(_agrees(r, known) for known in reported_ratios):
                report.notes.append(
                    f"UNPLACEABLE SPLIT {ticker} — {name} implies ~{r:.4g}:1 ({detail}) but "
                    f"FMP reports no matching split, so there is no ex-date to apply it at.")
    return report


def restatement_blocked(report: Optional[SplitReport]) -> Optional[str]:
    """Why the restated series must NOT be used, or None when it is safe.

    THIS GUARD IS LOAD-BEARING AND WAS ADDED ON MEASURED EVIDENCE. The restatement does
    not truncate — that is the point — so if it runs with an EMPTY split list on a ticker
    that actually split, it emits the raw artifact with nothing to stop it: GOOG's
    2022-03-31 reads 81.02% against a ~4% norm. An empty list is ambiguous between "this
    issuer never split" and "we could not find out", and those two must not be conflated:
    the second is strictly worse than today's truncation, not better.

    So the restated path requires the split state to be KNOWN and every in-scope split to
    be corroborated. Anything else falls back to truncation, which is lossy but honest.
    """
    if report is None:
        return "split record unavailable — basis unknown"
    if report.has_uncorroborated:
        bad = [e.ex_date for e in report.events if not e.corroborated]
        return (f"{len(bad)} in-scope split(s) uncorroborated ({', '.join(bad)}) — "
                f"2-of-3 witnesses required")
    return None


def split_factor(first_filed: Optional[str], events: List[SplitEvent]) -> float:
    """Multiplier putting a fact filed on `first_filed` onto TODAY's share basis.

    A fact carries the basis in effect when it was filed, so every split whose ex-date is
    LATER than the filing has yet to be reflected in it and must be applied.
    """
    if not first_filed:
        return 1.0
    factor = 1.0
    for e in events:
        if e.ex_date > first_filed:
            factor *= e.ratio
    return factor


def render_split_report(report: SplitReport) -> str:
    lines = [f"[SPLITS] {report.ticker}: {len(report.usable)} corroborated, "
             f"{len(report.events) - len(report.usable)} uncorroborated, "
             f"{len(report.out_of_scope)} out-of-scope (horizon {report.horizon or '—'})"]
    for e in report.events:
        mark = "OK " if e.corroborated else "!! "
        lines.append(f"  {mark}{e.ex_date}  {e.ratio:g}:1  "
                     f"witnesses={len(e.witnesses)}/{3} [{','.join(e.witnesses)}]")
        lines.append(f"      {e.detail}")
    for n in report.notes:
        lines.append(f"  NOTE {n}")
    for r in report.rejected:
        lines.append(f"  REJECTED {r}")
    for r in report.out_of_scope:
        lines.append(f"  OUT-OF-SCOPE {r}")
    return "\n".join(lines)
