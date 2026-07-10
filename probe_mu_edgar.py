"""Re-probe EDGAR for MU only (corrected CIK 0000723125)."""
import json, os, time, traceback, requests
from datetime import datetime, timezone
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures")
NOW_ISO = datetime.now(timezone.utc).isoformat()
EDGAR_UA = "CALIBER/3.0 victor.belfor@8x8.com"
CIK = "0000723125"
TICKER = "MU"


def _sanitise(obj):
    if isinstance(obj, dict):
        return {str(k): _sanitise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitise(v) for v in obj]
    return obj


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_sanitise(data), f, indent=2, default=str)
    print(f"  saved {path}")


headers = {"User-Agent": EDGAR_UA, "Accept": "application/json"}

# 1. Submissions
sub_url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
r = requests.get(sub_url, headers=headers, timeout=20)
r.raise_for_status()
sub = r.json()

filings = sub.get("filings", {}).get("recent", {})
forms = filings.get("form", [])
dates = filings.get("filingDate", [])
accnums = filings.get("accessionNumber", [])
descriptions = filings.get("primaryDocument", [])

tenk = [(dates[i], accnums[i], descriptions[i])
        for i, f in enumerate(forms) if f in ("10-K", "10-K/A")][:3]
tenq = [(dates[i], accnums[i], descriptions[i])
        for i, f in enumerate(forms) if f in ("10-Q", "10-Q/A")][:3]

submissions_shape = {
    "company_name": sub.get("name"),
    "cik": sub.get("cik"),
    "sic": sub.get("sic"),
    "sic_description": sub.get("sicDescription"),
    "tickers": sub.get("tickers"),
    "exchanges": sub.get("exchanges"),
    "fiscal_year_end": sub.get("fiscalYearEnd"),
    "total_filings": len(forms),
    "recent_10K": tenk,
    "recent_10Q": tenq,
}
print(f"Company: {submissions_shape['company_name']}  SIC: {submissions_shape['sic']} ({submissions_shape['sic_description']})")
print(f"Recent 10-K dates: {[t[0] for t in tenk]}")

# 2. Filing index for most recent 10-K
filing_index_shape = {}
risk_excerpt = None
mda_excerpt = None

if tenk:
    accn_fmt = tenk[0][1]
    cik_int = int(CIK)
    idx_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_fmt.replace('-','')}/{accn_fmt}-index.json"
    try:
        ri = requests.get(idx_url, headers=headers, timeout=20)
        ri.raise_for_status()
        idx_data = ri.json()
        items = idx_data.get("directory", {}).get("item", [])
        filing_index_shape = {
            "keys": list(idx_data.keys()),
            "directory_items": [it.get("name") for it in items][:20],
        }
        htm_files = [it["name"] for it in items
                     if it.get("name", "").lower().endswith((".htm", ".html"))
                     and "10k" in it.get("name", "").lower()]
        if not htm_files:
            htm_files = [it["name"] for it in items
                         if it.get("name", "").lower().endswith((".htm", ".html"))
                         and it.get("name", "").lower() not in ("r1.htm",)][:3]
        filing_index_shape["htm_candidates"] = htm_files

        if htm_files:
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_fmt.replace('-','')}/{htm_files[0]}"
            rd = requests.get(doc_url, headers={**headers, "Accept": "text/html"}, timeout=30)
            raw_text = rd.text[:8000]
            risk_start = raw_text.lower().find("risk factor")
            mda_start = raw_text.lower().find("management")
            risk_excerpt = raw_text[risk_start:risk_start+500] if risk_start >= 0 else "not in first 8000 chars"
            mda_excerpt = raw_text[mda_start:mda_start+500] if mda_start >= 0 else "not in first 8000 chars"
            print(f"  10-K doc fetched: {doc_url}")
    except Exception as e:
        filing_index_shape = {"error": str(e)}
        print(f"  filing index error: {e}")

# 3. Company facts (XBRL)
facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
facts_shape = {}
try:
    rf = requests.get(facts_url, headers=headers, timeout=30)
    rf.raise_for_status()
    facts = rf.json()
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    facts_shape = {
        "taxonomy_keys": list(facts.get("facts", {}).keys()),
        "us_gaap_concept_count": len(us_gaap),
        "sample_concepts": list(us_gaap.keys())[:20],
        "entityName": facts.get("entityName"),
    }
    print(f"  XBRL concepts: {len(us_gaap)}")
except Exception as e:
    facts_shape = {"error": str(e)}

fixture = {
    "probed_at": NOW_ISO,
    "ticker": TICKER,
    "cik": CIK,
    "submissions_shape": submissions_shape,
    "filing_index_shape": filing_index_shape,
    "risk_factors_excerpt": risk_excerpt,
    "mda_excerpt": mda_excerpt,
    "facts_shape": facts_shape,
}

save(FIXTURE_ROOT / "edgar" / f"{TICKER}.json", fixture)
print("MU EDGAR re-probe complete")
