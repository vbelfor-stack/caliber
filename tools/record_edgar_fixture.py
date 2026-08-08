"""Record an EDGAR fixture for one ticker, in the shape adapters/edgar_adapter reads back.

    python -m tools.record_edgar_fixture NOW WU

Replaces the deleted Phase-0 probe.py for the EDGAR side. It reuses the adapter's own
live fetch + extraction functions rather than reimplementing them, so a recorded fixture
is by construction what the live path would have produced at record time — including the
depth-40 de-duplicated per-concept cap (PER_CONCEPT_DEPTH).

Golden-ticker fixtures must not depend on live SEC being reachable, so re-record
deliberately (fixtures are the regression baseline; a silent re-record moves the
baseline). Existing files are backed up to <name>.json.bak, which .gitignore excludes.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from adapters.edgar_adapter import (
    PER_CONCEPT_DEPTH,
    _extract_xbrl_facts,
    _extract_section,
    _fetch_companyfacts,
    _fetch_filing_text,
    _fetch_submissions,
    _get_cik,
)

FIXTURE_DIR = Path("tests/fixtures/edgar")


def _filing_rows(filings: dict, forms: tuple, limit: int = 3) -> list:
    """[filing_date, accession, primary_doc] rows, newest first — _from_fixture's shape."""
    form_list = filings.get("form", [])
    return [
        [filings["filingDate"][i], filings["accessionNumber"][i],
         filings.get("primaryDocument", [""] * len(form_list))[i]]
        for i, f in enumerate(form_list) if f in forms
    ][:limit]


def record(ticker: str) -> Path:
    cik = _get_cik(ticker)
    time.sleep(0.3)
    sub = _fetch_submissions(cik)
    time.sleep(0.3)

    recent = sub.get("filings", {}).get("recent", {})
    tenk = _filing_rows(recent, ("10-K", "10-K/A"))
    tenq = _filing_rows(recent, ("10-Q", "10-Q/A"))

    facts_json = _fetch_companyfacts(cik)
    if not facts_json:
        raise RuntimeError(f"[EDGAR] companyfacts unavailable for {ticker} (CIK {cik})")
    financials = _extract_xbrl_facts(facts_json)
    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})

    risk_txt = mda_txt = None
    if tenk:
        from adapters.edgar_adapter import FilingRef
        text = _fetch_filing_text(cik, FilingRef("10-K", tenk[0][0], tenk[0][1], tenk[0][2]))
        risk_txt = _extract_section(text, ["risk factor", "item 1a"]) or None
        mda_txt = _extract_section(text, ["management's discussion", "item 7"]) or None

    fixture = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "cik": cik,
        "submissions_shape": {
            "company_name": sub.get("name"),
            "cik": cik,
            "sic": sub.get("sic"),
            "sic_description": sub.get("sicDescription"),
            "tickers": sub.get("tickers"),
            "exchanges": sub.get("exchanges"),
            "fiscal_year_end": sub.get("fiscalYearEnd"),
            "total_filings": len(recent.get("form", [])),
            "recent_10K": tenk,
            "recent_10Q": tenq,
        },
        "filing_index_shape": None,
        "risk_factors_excerpt": risk_txt,
        "mda_excerpt": mda_txt,
        "facts_shape": {
            "taxonomy_keys": sorted(facts_json.get("facts", {})),
            "us_gaap_concept_count": len(us_gaap),
            "sample_concepts": sorted(us_gaap)[:20],
        },
        "xbrl_facts": {
            "concepts": financials.concepts,
            "latest_period_end": financials.latest_period_end,
            "_recorded_depth": PER_CONCEPT_DEPTH,
        },
    }

    path = FIXTURE_DIR / f"{ticker}.json"
    if path.exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2)

    resolved = sum(1 for rf in financials.fields.values() if rf.is_resolved())
    print(f"{ticker}: CIK {cik}, {len(financials.concepts)} concepts, "
          f"latest period-end {financials.latest_period_end}, "
          f"{resolved}/{len(financials.fields)} fields resolved -> {path}")
    for name, rf in sorted(financials.fields.items()):
        if not rf.is_resolved():
            print(f"    withheld {name}: {rf.reason} ({rf.detail or ''})")
    return path


if __name__ == "__main__":
    tickers = sys.argv[1:]
    if not tickers:
        raise SystemExit("usage: python -m tools.record_edgar_fixture TICKER [TICKER ...]")
    for t in tickers:
        record(t.upper())
        time.sleep(0.5)
