"""The USD-only reporting-currency gate — ruled by Vic 2026-08-28.

    "SKHY CURRENCY: USD ONLY. Ingest only what FMP supplies natively in USD. KRW-only
     periods excluded with typed block rows — never converted. Short history accepted;
     YOUNG/coverage rules apply to whatever USD depth survives."   — Vic, 2026-08-28

★ THIS RULING SUPERSEDES THE 2026-08-21 CURRENCY ADDENDUM, WHICH ORDERED CONVERSION.
That addendum (folded into the doctrine order §8) ruled SKHY would be evaluated in USD via
period-matched KRW→USD conversion, with a per-row rate record and a preserved native figure.
Conversion is now ruled OUT. What survives from it is §8.1(7) — the STANDING CURRENCY GATE,
which is this module — and what dies with it is the whole conversion apparatus: the
period-average convention, the ingest-date-rate prohibition, the forex source, the per-row
rate stamp, and the FY2025 $38–40B verification anchor that existed to prove the plumbing.
None of those has a subject any more. They are superseded, not deleted from the record.

★ AND THE TYPED REASON IS **NOT** `currency:unconverted`, WHICH IS WHAT §8.1(7) NAMED.
"Unconverted" asserts that conversion is the pending remedy. Ruling 2 removed that remedy,
so the constant would be making a claim about the future that the ruling has already
falsified — the exact defect L-4d found in `WITHHELD_NO_CAPEX`/`WITHHELD_NO_OCF`, which
asserted "no tag filed" on a condition that only measured whether our reader returned
points. Those were DELETED rather than renamed, and the deletion was the fix. The reason
here therefore states only what was measured: this period is reported natively in a currency
that is not USD. `currency:non_usd_native`.

WHY USD-ONLY IS THE SAFE DIRECTION, beyond it being ruled. A conversion path silently
rewrites history on every refresh unless it is period-matched perfectly, it makes every
stored figure a function of a second feed, and the measurement that would have verified it
(§8.3) turned out to be testing a remembered exchange rate rather than the plumbing. USD-only
gives up depth on one name and gives up nothing else. Vic's "short history accepted" is the
explicit acknowledgement of that trade.

WHAT THE GATE MEASURES. FMP stamps `reportedCurrency` on every statement row it serves. This
module partitions rows on that field and nothing else — it does not infer currency from
magnitude, from the exchange, from the country, or from `profile.currency`.

    ★ `profile.currency` IS THE QUOTE CURRENCY, NOT THE REPORTING CURRENCY, AND READING IT
    HERE WOULD BE A DEFECT. Measured 2026-08-28: SKHY's profile reads `currency=USD`
    (it is a NASDAQ-listed ADR quoted in dollars) while all 129 of its statement rows read
    `reportedCurrency=KRW`. The control settles it — the same issuer's Korean ordinary line
    `000660.KS` reads `profile.currency=KRW` on exchange KSC. Both fields are CORRECT; they
    answer different questions. CLAUDE.md previously recorded this as "profile.currency is
    WRONG for this issuer", which was too harsh and is corrected by that control.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

# The only reporting currency this pipeline ingests.
USD = "USD"

# Typed reason for a period blocked by this gate. `field:code` shape, matching
# `withheld_reason()` in core.fundamental_series.
REASON_NON_USD_NATIVE = "non_usd_native"
REASON_CURRENCY_UNKNOWN = "currency_unstated"

# The field FMP stamps the reporting currency on. Named so the coupling is greppable.
CURRENCY_FIELD = "reportedCurrency"


@dataclass
class CurrencySplit:
    """The partition of one endpoint's rows into ingestable and blocked.

    `blocked` keeps the WHOLE row, not just its date. A block row has to be able to say what
    it blocked and on what evidence, and re-fetching to find out later would measure a
    different day.
    """
    usd: List[Dict[str, Any]] = field(default_factory=list)
    blocked: List[Tuple[Dict[str, Any], str, str]] = field(default_factory=list)
    # (row, typed_reason, currency) — currency carried separately because it is the single
    # most useful thing to group a report by, and digging it back out of the reason string
    # would mean parsing a message.

    @property
    def currencies(self) -> Dict[str, int]:
        """{reported_currency: row_count} across BOTH sides — the readout Vic asked for."""
        out: Dict[str, int] = {}
        for r in self.usd:
            out[USD] = out.get(USD, 0) + 1
        for _row, _reason, ccy in self.blocked:
            out[ccy] = out.get(ccy, 0) + 1
        return out

    @property
    def has_usd(self) -> bool:
        return bool(self.usd)


def currency_of(row: Any) -> Optional[str]:
    """The row's stated reporting currency, upper-cased, or None when it states none.

    None means UNSTATED, never "assume USD". A row that does not say what currency it is in
    is not evidence that it is in dollars, and the whole point of a gate is that absence
    does not pass it.
    """
    if not isinstance(row, dict):
        return None
    val = row.get(CURRENCY_FIELD)
    if val is None:
        return None
    text = str(val).strip().upper()
    return text or None


def split_by_currency(rows: Optional[Sequence[Any]]) -> CurrencySplit:
    """Partition FMP statement rows into natively-USD and blocked.

    FAIL-CLOSED ON BOTH FAILURE MODES, and they are deliberately given DIFFERENT typed
    reasons rather than one shared "not USD":

      non_usd_native     the row states a currency and it is not USD. A fact about the
                         ISSUER. SKHY's 129 KRW rows are this.
      currency_unstated  the row states no currency at all. A fact about the FEED, and a
                         much more alarming one — it means we cannot tell, and an
                         undetectable currency error is worse than a detected foreign one.

    Collapsing them would be the typed-reason mislabel again: one constant cannot know which
    of two causes occurred, so any code holding it is forced to guess.
    """
    split = CurrencySplit()
    for row in rows or []:
        ccy = currency_of(row)
        if ccy == USD:
            split.usd.append(row)
        elif ccy is None:
            split.blocked.append((row if isinstance(row, dict) else {},
                                  f"currency:{REASON_CURRENCY_UNKNOWN}", "UNSTATED"))
        else:
            split.blocked.append((row, f"currency:{REASON_NON_USD_NATIVE}", ccy))
    return split


def render_split(ticker: str, endpoint: str, split: CurrencySplit) -> str:
    """One line per endpoint for the dry-run readout."""
    total = len(split.usd) + len(split.blocked)
    return (f"  {ticker:6s} {endpoint:26s} {total:3d} rows  "
            f"USD {len(split.usd):3d}  blocked {len(split.blocked):3d}  "
            f"{split.currencies}")


# ═════════════════════════════════════════════════════════════════════════════
#  THE SCORE-BEARING-FIELD CURRENCY GUARD — Vic's ruling 4, 2026-08-28
# ═════════════════════════════════════════════════════════════════════════════
#
#     "KRW GUARD: currency guard on ALL score-bearing fields — any non-USD value on a
#      score-bearing field is a typed, loud block, never ingested, never converted. Kills
#      the key-metrics-ttm ~1,028x trap and its whole class."   — Vic, 2026-08-28
#
# ★ "ALL SCORE-BEARING FIELDS" IS READ AS "EVERY SCORE-BEARING FIELD A CURRENCY ERROR CAN
# REACH", AND THE PARTITION BELOW IS THE WHOLE SUBSTANCE OF THE GUARD. A ratio whose
# numerator and denominator share a basis is CURRENCY-NEUTRAL: KRW/KRW and USD/USD give the
# same number, so blocking it would discard valid data and manufacture the absences the
# fail-closed rule is supposed to prevent. Verified on the live case rather than assumed —
# SKHY's `freeCashFlowYieldTTM` reads 0.0777, and KRW TTM FCF ÷ KRW market cap reproduces
# 7.77%: FMP's key-metrics block is internally consistent on the ISSUER basis.
#
# So the guard binds the MONETARY fields, where a basis error is a raw magnitude error.
#
# ★★ THE FIELD THIS RULING WAS WRITTEN FOR IS `market_cap`, AND IT IS THE ONE THAT PROVES
# THE POINT. Measured 2026-08-28: SKHY's `key-metrics-ttm.marketCap` is 1,173,390,134,823,000
# — byte-identical to the Korean ordinary listing `000660.KS`, i.e. KRW — while
# `profile`/`quote`/`market-capitalization` all serve the ADR's USD cap. Controls: NVDA and
# ARM read `key-metrics ÷ profile = 1.0000`. One endpoint silently resolves to the ISSUER,
# the others to the LISTING, and nothing in the payload says so.
#
# ★★★ AND THE GUARD IS WHAT MAKES RULING 3 SAFE, NOT AN INDEPENDENT IMPROVEMENT.
# `core/pillars.py:237-238` computes `fcf / market_cap * 100`. For SKHY both legs are KRW
# today, so the ratio is ACCIDENTALLY CORRECT. Ruling 3 moves `market_cap` onto the USD
# `market-capitalization` endpoint — and if `free_cashflow` were left on its KRW basis, that
# division would become wrong by a factor of ~1,378. The fix would have created a
# cross-currency trap of the same family as the one it removed. Blocking `free_cashflow`
# is what prevents it. THE TWO RULINGS LAND TOGETHER OR NOT AT ALL.

# Fields whose VALUE is a currency amount. A wrong basis is a wrong magnitude.
MONETARY_SCORE_BEARING_FIELDS = (
    "total_debt",
    "total_cash",
    "free_cashflow",
    "operating_cashflow",
    "market_cap",
    "enterprise_value",
    "current_price",
    "target_mean_price",
)

# Fields that are score-bearing but CURRENCY-NEUTRAL. Listed explicitly, not left implicit,
# so that "why isn't X guarded?" has an answer in the code rather than in someone's memory.
CURRENCY_NEUTRAL_SCORE_BEARING_FIELDS = (
    "gross_margin", "operating_margin", "profit_margin",   # percentages
    "roe", "roa",                                          # ratios
    "current_ratio", "debt_to_equity",                     # ratios
    "revenue_growth",                                      # percent change
    "trailing_pe", "forward_pe", "price_to_book",          # price ÷ per-share, same basis
    "ev_to_ebitda", "ev_to_revenue", "fcf_yield",          # value ÷ flow, same basis
    "beta",                                                # unitless
    "shares_outstanding", "analyst_count",                 # counts, not currency
)

# Which basis each guarded field is served on. THIS MAP IS THE GUARD'S REAL CONTENT — the
# whole defect class is that two fields on one payload can sit on two different bases.
#   reporting — from the statements, or from key-metrics, which resolves to the ISSUER.
#   quote     — from profile/price endpoints, which resolve to the LISTING.
#
# ★★ `market_cap` IS DELIBERATELY ABSENT FROM THIS MAP — ITS BASIS IS NOT STATIC, AND
# ASSUMING IT WAS IS A DEFECT THIS ORDER'S OWN DARK DIFF CAUGHT BEFORE ANYTHING SHIPPED.
#
# A field's currency basis is a property of THE ENDPOINT THAT SUPPLIED IT, not of the field
# name. Ruling 3 moved `market_cap` from `key-metrics-ttm` (which resolves to the ISSUER,
# hence the reporting basis) to `market-capitalization` (which resolves to the LISTING,
# hence the quote basis) — and the adapter still falls back to key-metrics when the newer
# endpoint is absent, which is exactly what recorded fixtures do. So the SAME FIELD sits on
# EITHER basis depending on which source answered.
#
# The first version of this map hard-coded "reporting" and the dark diff showed SKHY's
# market_cap being BLOCKED — the guard suppressing the very USD figure ruling 3 exists to
# supply. A static map would have been a quiet, permanent wrong answer on the one name both
# rulings were written for. `market_cap_basis()` below resolves it from the payload instead.
FIELD_CURRENCY_BASIS = {
    "total_debt": "reporting",
    "total_cash": "reporting",
    "free_cashflow": "reporting",
    "operating_cashflow": "reporting",
    "enterprise_value": "reporting",       # still key-metrics — NOT moved by ruling 3
    "current_price": "quote",
    "target_mean_price": "quote",
}


def market_cap_basis(raw: Any) -> str:
    """Which currency basis `market_cap` is on FOR THIS PAYLOAD.

    'quote' when the `market-capitalization` endpoint answered (ruling 3's source, which
    resolves to the LISTING), 'reporting' when the adapter fell back to
    `key-metrics-ttm.marketCap` (which resolves to the ISSUER).

    FAILS TOWARD 'reporting', which is the protective direction: reporting is the basis
    that gets BLOCKED for a non-USD issuer, so an unresolvable case withholds the field
    rather than admitting a possibly-KRW figure as dollars.
    """
    if not isinstance(raw, dict):
        return "reporting"
    rows = raw.get("market_capitalization")
    if isinstance(rows, dict):
        rows = [rows]
    for row in rows or []:
        if isinstance(row, dict) and row.get("marketCap") is not None:
            return "quote"
    return "reporting"

REASON_FIELD_BLOCKED = "non_usd_blocked"


def payload_currencies(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """(reporting_currency, quote_currency) from a fetched FMP payload.

    The reporting currency is taken from whichever statement rows are present, and a
    DISAGREEMENT between statements yields None — UNKNOWN, which the guard treats as
    unguardable and therefore blocks. Two statements claiming different currencies for one
    issuer is not a thing to average.
    """
    if not isinstance(raw, dict):
        return None, None

    stated = set()
    for key in ("cashflow", "balance", "income_annual", "income_q"):
        rows = raw.get(key)
        if isinstance(rows, dict):
            rows = [rows]
        for row in rows or []:
            ccy = currency_of(row)
            if ccy:
                stated.add(ccy)

    reporting = stated.pop() if len(stated) == 1 else None

    profile = raw.get("profile")
    if isinstance(profile, list):
        profile = profile[0] if profile else {}
    quote = None
    if isinstance(profile, dict) and profile.get("currency"):
        quote = str(profile["currency"]).strip().upper() or None

    return reporting, quote


def field_is_blocked(field: str, reporting: Optional[str], quote: Optional[str],
                     basis_override: Optional[str] = None) -> Optional[str]:
    """The typed block reason for `field`, or None when it may be ingested.

    UNKNOWN BLOCKS. A field whose basis currency could not be established is blocked, not
    admitted: "we could not tell" is precisely the case where an undetected currency error
    lives, and the fail-closed rule says a guard that cannot measure denies what it guards.

    A field that is not monetary is never blocked — see the partition above.

    `basis_override` carries a basis resolved from the payload rather than from the static
    map — see `market_cap_basis` for the one field that needs it and why.
    """
    basis = basis_override or FIELD_CURRENCY_BASIS.get(field)
    if basis is None:
        return None                                  # not a guarded field
    ccy = reporting if basis == "reporting" else quote
    if ccy == USD:
        return None
    stated = ccy or "UNSTATED"
    return (f"currency:{REASON_FIELD_BLOCKED}:{stated}"
            f" ({basis} basis; ruled USD-only 2026-08-28, never converted)")

