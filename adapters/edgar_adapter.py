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
    date: str
    accession: str       # hyphenated: 0000723125-25-000028
    primary_doc: str     # e.g. mu-20250828.htm


# XBRL us-gaap / dei concepts extracted for FMP cross-check (E-1). This is the
# concept-pull list; synonym → canonical-field resolution + TTM alignment is E-2.
# (concept, namespace)
XBRL_CONCEPTS: List[Tuple[str, str]] = [
    ("Revenues", "us-gaap"),
    ("RevenueFromContractWithCustomerExcludingAssessedTax", "us-gaap"),
    ("GrossProfit", "us-gaap"),
    ("OperatingIncomeLoss", "us-gaap"),
    ("NetIncomeLoss", "us-gaap"),
    ("Assets", "us-gaap"),
    ("AssetsCurrent", "us-gaap"),
    ("Liabilities", "us-gaap"),
    ("LiabilitiesCurrent", "us-gaap"),
    ("CashAndCashEquivalentsAtCarryingValue", "us-gaap"),
    ("LongTermDebt", "us-gaap"),
    ("LongTermDebtNoncurrent", "us-gaap"),
    ("DebtCurrent", "us-gaap"),
    ("StockholdersEquity", "us-gaap"),
    ("NetCashProvidedByUsedInOperatingActivities", "us-gaap"),
    ("PaymentsToAcquirePropertyPlantAndEquipment", "us-gaap"),
    ("EntityCommonStockSharesOutstanding", "dei"),
]
_XBRL_VALID_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}


@dataclass
class EdgarFinancials:
    """Raw XBRL facts extracted from companyfacts (E-1: extraction only).

    concepts: {concept_name: [ {value, unit, start, end, fy, fp, form, accession}, ... ]}
    each list is most-recent-first, capped. E-2 maps synonyms → canonical fields and
    assembles TTM; E-3 cross-checks against FMP.
    """
    concepts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    latest_period_end: Optional[str] = None   # max period-end across concepts (E-3 staleness)


def _extract_xbrl_facts(facts_json: Dict, per_concept: int = 8) -> EdgarFinancials:
    """Pull the mapped concepts' recent facts from a companyfacts JSON.

    Extraction only: numeric coercion + latest-period-first ordering + form filter
    (10-K/10-Q family). No synonym resolution or TTM assembly (that is E-2).
    """
    facts = facts_json.get("facts", {}) if facts_json else {}
    ns_blocks = {"us-gaap": facts.get("us-gaap", {}), "dei": facts.get("dei", {})}
    out: Dict[str, List[Dict[str, Any]]] = {}
    latest_end: Optional[str] = None

    for concept, ns in XBRL_CONCEPTS:
        block = ns_blocks.get(ns, {}).get(concept)
        if not block:
            continue
        recs: List[Dict[str, Any]] = []
        for unit, entries in block.get("units", {}).items():
            for e in entries:
                if e.get("form") not in _XBRL_VALID_FORMS:
                    continue
                try:
                    val = float(e["val"])
                except (KeyError, TypeError, ValueError):
                    continue
                recs.append({
                    "value": val, "unit": unit,
                    "start": e.get("start"), "end": e.get("end"),
                    "fy": e.get("fy"), "fp": e.get("fp"),
                    "form": e.get("form"), "accession": e.get("accn"),
                })
        if not recs:
            continue
        recs.sort(key=lambda r: (r["end"] or ""), reverse=True)
        out[concept] = recs[:per_concept]
        # Staleness clock (E-3) tracks fiscal PERIOD-END from us-gaap financials only —
        # dei cover-page dates (e.g. shares-outstanding as-of) are not period ends.
        if ns == "us-gaap":
            top = out[concept][0]["end"]
            if top and (latest_end is None or top > latest_end):
                latest_end = top

    return EdgarFinancials(concepts=out, latest_period_end=latest_end)


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

    cik_int = _TICKERS_CACHE.get(ticker.upper())
    if cik_int is None:
        raise RuntimeError(
            f"[EDGAR] Ticker '{ticker}' not found in SEC tickers.json. "
            f"Check spelling or use the SEC-listed ticker symbol."
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

    tenk, tenq = [], []
    for i, f in enumerate(forms):
        ref = FilingRef(
            form=f,
            date=dates[i] if i < len(dates) else "",
            accession=accnums[i] if i < len(accnums) else "",
            primary_doc=docs[i] if i < len(docs) else "",
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
    financials = EdgarFinancials(
        concepts=xf.get("concepts", {}),
        latest_period_end=xf.get("latest_period_end"),
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
