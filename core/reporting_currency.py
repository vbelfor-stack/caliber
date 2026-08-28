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
