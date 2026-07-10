"""
Phase 0 probe script — hits yfinance, EDGAR, FRED for MU, GOOG, V.
Saves raw responses to tests/fixtures/. Documents shapes in schema-notes.md.
Run: python probe.py
"""
import io
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout so Unicode chars don't blow up on cp1252 terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests
import yfinance as yf

TICKERS = ["MU", "GOOG", "V"]
FIXTURE_ROOT = Path("tests/fixtures")
NOW_ISO = datetime.now(timezone.utc).isoformat()

# FRED — DGS10 (10-Year Treasury Constant Maturity Rate)
FRED_SERIES = "DGS10"
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# EDGAR — SEC EDGAR full-text search / submissions API
EDGAR_UA = "CALIBER/3.0 victor.belfor@8x8.com"  # required by SEC

RESULTS = {}  # feed -> ticker -> {ok, shape_notes, errors}

# ── helpers ──────────────────────────────────────────────────────────────────

def _json_default(obj):
    """Coerce non-JSON-serialisable types; Timestamp keys need pre-processing."""
    return str(obj)


def _sanitise(obj):
    """Recursively convert dict keys that are Timestamps (or non-str) to strings."""
    if isinstance(obj, dict):
        return {str(k): _sanitise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitise(v) for v in obj]
    return obj


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_sanitise(data), f, indent=2, default=_json_default)
    print(f"  OK saved {path}")


def record(feed, ticker, status, notes="", error=""):
    RESULTS.setdefault(feed, {})[ticker] = {
        "status": status,
        "notes": notes,
        "error": error,
    }


# ── yfinance probe ────────────────────────────────────────────────────────────

def probe_yfinance(ticker: str):
    print(f"\n[yfinance] {ticker}")
    try:
        tk = yf.Ticker(ticker)

        info = tk.info
        # Document top-level keys present
        info_keys = list(info.keys()) if isinstance(info, dict) else []

        # Fast_info (lightweight)
        try:
            fi = tk.fast_info
            fast_info = {k: getattr(fi, k, None) for k in [
                "lastPrice", "marketCap", "sharesOutstanding",
                "currency", "exchange", "timezone",
            ]}
        except Exception:
            fast_info = {}

        # Financials — annual income statement
        try:
            fin = tk.financials
            financials_shape = {
                "columns": [str(c) for c in fin.columns.tolist()],
                "index": fin.index.tolist(),
                "sample_row": fin.iloc[0].to_dict() if not fin.empty else {},
            }
        except Exception as e:
            financials_shape = {"error": str(e)}

        # Balance sheet
        try:
            bs = tk.balance_sheet
            balance_shape = {
                "columns": [str(c) for c in bs.columns.tolist()],
                "index": bs.index.tolist(),
            }
        except Exception as e:
            balance_shape = {"error": str(e)}

        # Cash flow
        try:
            cf = tk.cashflow
            cashflow_shape = {
                "columns": [str(c) for c in cf.columns.tolist()],
                "index": cf.index.tolist(),
            }
        except Exception as e:
            cashflow_shape = {"error": str(e)}

        # Quarterly earnings history
        try:
            eh = tk.earnings_history
            if eh is not None and not eh.empty:
                earnings_shape = {
                    "columns": eh.columns.tolist(),
                    "rows": len(eh),
                    "sample": eh.head(2).to_dict(orient="records"),
                }
            else:
                earnings_shape = {"note": "empty or None"}
        except Exception as e:
            earnings_shape = {"error": str(e)}

        # Insider transactions
        try:
            it = tk.insider_transactions
            if it is not None and not it.empty:
                insider_shape = {
                    "columns": it.columns.tolist(),
                    "rows": len(it),
                    "sample": it.head(2).to_dict(orient="records"),
                }
            else:
                insider_shape = {"note": "empty or None"}
        except Exception as e:
            insider_shape = {"error": str(e)}

        # Analyst price targets
        try:
            apt = tk.analyst_price_targets
            analyst_shape = apt if isinstance(apt, dict) else (
                apt.to_dict(orient="records") if hasattr(apt, "to_dict") else str(apt)
            )
        except Exception as e:
            analyst_shape = {"error": str(e)}

        # Recommendations summary
        try:
            rec = tk.recommendations_summary
            if rec is not None and not rec.empty:
                rec_shape = rec.to_dict(orient="records")
            else:
                rec_shape = {"note": "empty or None"}
        except Exception as e:
            rec_shape = {"error": str(e)}

        # 1Y daily price history (for technicals)
        try:
            hist = tk.history(period="1y", interval="1d")
            price_shape = {
                "columns": hist.columns.tolist(),
                "rows": len(hist),
                "date_range": [str(hist.index[0]), str(hist.index[-1])] if not hist.empty else [],
                "sample": hist.tail(3).to_dict(orient="records"),
            }
        except Exception as e:
            price_shape = {"error": str(e)}

        # Quarterly income statement — needed for MRQ trajectory computation
        try:
            qf = tk.quarterly_financials
            _QF_ROWS = ["Total Revenue", "Gross Profit", "Operating Income",
                        "Basic EPS", "Diluted EPS"]
            if qf is not None and not qf.empty:
                cols_str = [str(c) for c in qf.columns.tolist()]
                data = {}
                for row in _QF_ROWS:
                    if row in qf.index:
                        row_vals = qf.loc[row].to_dict()
                        data[row] = {
                            str(k): (float(v) if isinstance(v, (int, float)) and v == v else None)
                            for k, v in row_vals.items()
                        }
                quarterly_financials_shape = {
                    "columns": cols_str,
                    "index": [r for r in _QF_ROWS if r in qf.index],
                    "data": data,
                }
            else:
                quarterly_financials_shape = {"note": "empty or None"}
        except Exception as e:
            quarterly_financials_shape = {"error": str(e)}

        fixture = {
            "probed_at": NOW_ISO,
            "ticker": ticker,
            "info_keys": info_keys,
            "info_sample": {k: info.get(k) for k in [
                "shortName", "longName", "sector", "industry", "country",
                "marketCap", "trailingPE", "forwardPE", "priceToBook",
                "enterpriseValue", "enterpriseToRevenue", "enterpriseToEbitda",
                "revenueGrowth", "grossMargins", "operatingMargins", "profitMargins",
                "returnOnEquity", "returnOnAssets", "currentRatio", "debtToEquity",
                "totalDebt", "totalCash", "freeCashflow", "operatingCashflow",
                "dividendYield", "payoutRatio", "sharesOutstanding", "sharesShort",
                "shortRatio", "beta", "52WeekChange", "currency", "exchange",
                "quoteType", "currentPrice", "targetMeanPrice", "numberOfAnalystOpinions",
            ]},
            "fast_info": fast_info,
            "financials_shape": financials_shape,
            "balance_shape": balance_shape,
            "cashflow_shape": cashflow_shape,
            "earnings_shape": earnings_shape,
            "insider_shape": insider_shape,
            "analyst_shape": analyst_shape,
            "recommendations_shape": rec_shape,
            "price_shape": price_shape,
            "quarterly_financials_shape": quarterly_financials_shape,
        }

        save(FIXTURE_ROOT / "yfinance" / f"{ticker}.json", fixture)
        notes = (
            f"info_keys={len(info_keys)}; "
            f"financials_cols={financials_shape.get('columns',['?'])[:2]}; "
            f"price_rows={price_shape.get('rows','?')}"
        )
        record("yfinance", ticker, "ok", notes=notes)

    except Exception as e:
        tb = traceback.format_exc()
        print(f"  FAIL ERROR: {e}")
        save(FIXTURE_ROOT / "yfinance" / f"{ticker}_error.json", {"error": str(e), "traceback": tb})
        record("yfinance", ticker, "error", error=str(e))


# ── EDGAR probe ───────────────────────────────────────────────────────────────

# Map tickers to CIK (from SEC EDGAR)
EDGAR_CIK = {
    "MU":   "0000723125",  # Micron Technology Inc — verified via SEC tickers.json
    "GOOG": "0001652044",  # Alphabet Inc
    "V":    "0001403161",  # Visa Inc
}

def probe_edgar(ticker: str):
    print(f"\n[EDGAR] {ticker}")
    cik = EDGAR_CIK[ticker]
    headers = {"User-Agent": EDGAR_UA, "Accept": "application/json"}

    try:
        # 1. Submissions (filing history)
        sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        r = requests.get(sub_url, headers=headers, timeout=20)
        r.raise_for_status()
        sub = r.json()

        # Pull recent 10-K and 10-Q filings
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

        # 2. Fetch most recent 10-K index to locate Risk Factors / MD&A doc
        latest_10k_accn = tenk[0][1].replace("-", "") if tenk else None
        risk_excerpt = None
        mda_excerpt = None
        filing_index_shape = {}

        if latest_10k_accn:
            idx_url = (
                f"https://www.sec.gov/Archives/edgar/full-index/"
                f"cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
                f"&type=10-K&dateb=&owner=include&count=1&search_text="
            )
            # Use the filing viewer API instead
            filing_url = (
                f"https://www.sec.gov/cgi-bin/browse-edgar"
                f"?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=include&count=1"
            )

            # Direct filing index JSON
            accn_fmt = tenk[0][1]  # already hyphenated
            idx_url2 = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn_fmt.replace('-','')}/{accn_fmt}-index.json"
            try:
                ri = requests.get(idx_url2, headers=headers, timeout=20)
                ri.raise_for_status()
                idx_data = ri.json()
                filing_index_shape = {
                    "keys": list(idx_data.keys()),
                    "directory_items": [
                        item.get("name") for item in idx_data.get("directory", {}).get("item", [])
                    ][:20],
                }
                # Try to find the 10-K htm document
                items = idx_data.get("directory", {}).get("item", [])
                htm_files = [it["name"] for it in items
                             if it.get("name", "").lower().endswith((".htm", ".html"))
                             and "10k" in it.get("name", "").lower()]
                if not htm_files:
                    htm_files = [it["name"] for it in items
                                 if it.get("name", "").lower().endswith((".htm", ".html"))
                                 and it.get("name", "").lower() not in ("r1.htm",)][:3]
                filing_index_shape["htm_candidates"] = htm_files

                # Pull first ~8000 chars of the filing for shape-check (not full parse)
                if htm_files:
                    doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn_fmt.replace('-','')}/{htm_files[0]}"
                    try:
                        rd = requests.get(doc_url, headers={**headers, "Accept": "text/html"}, timeout=30)
                        raw_text = rd.text[:8000]
                        # Rough excerpt markers
                        risk_start = raw_text.lower().find("risk factor")
                        mda_start = raw_text.lower().find("management")
                        risk_excerpt = raw_text[risk_start:risk_start+500] if risk_start >= 0 else "not in first 8000 chars"
                        mda_excerpt = raw_text[mda_start:mda_start+500] if mda_start >= 0 else "not in first 8000 chars"
                    except Exception as de:
                        risk_excerpt = f"doc_fetch_error: {de}"
                        mda_excerpt = f"doc_fetch_error: {de}"

            except Exception as ie:
                filing_index_shape = {"error": str(ie)}

        # 3. Company facts (XBRL) — shape only
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
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
        except Exception as fe:
            facts_shape = {"error": str(fe)}

        fixture = {
            "probed_at": NOW_ISO,
            "ticker": ticker,
            "cik": cik,
            "submissions_shape": submissions_shape,
            "filing_index_shape": filing_index_shape,
            "risk_factors_excerpt": risk_excerpt,
            "mda_excerpt": mda_excerpt,
            "facts_shape": facts_shape,
        }

        save(FIXTURE_ROOT / "edgar" / f"{ticker}.json", fixture)
        notes = (
            f"name={submissions_shape.get('company_name')}; "
            f"sic={submissions_shape.get('sic')} ({submissions_shape.get('sic_description')}); "
            f"10-K_recent={[t[0] for t in tenk]}; "
            f"gaap_concepts={facts_shape.get('us_gaap_concept_count','?')}"
        )
        record("edgar", ticker, "ok", notes=notes)
        time.sleep(0.5)  # SEC rate-limit courtesy

    except Exception as e:
        tb = traceback.format_exc()
        print(f"  FAIL ERROR: {e}")
        save(FIXTURE_ROOT / "edgar" / f"{ticker}_error.json", {"error": str(e), "traceback": tb})
        record("edgar", ticker, "error", error=str(e))


# ── FRED probe ────────────────────────────────────────────────────────────────

def probe_fred():
    print(f"\n[FRED] DGS10 (10-Year Treasury)")
    results = {}

    # Strategy A: fredapi (if installed)
    try:
        from fredapi import Fred
        if FRED_API_KEY:
            fred = Fred(api_key=FRED_API_KEY)
            series = fred.get_series(FRED_SERIES, observation_start="2024-01-01")
            latest = series.dropna().iloc[-1]
            results["fredapi"] = {
                "method": "fredapi",
                "series_id": FRED_SERIES,
                "latest_value": float(latest),
                "latest_date": str(series.dropna().index[-1]),
                "obs_count": len(series),
            }
            print(f"  OK fredapi: DGS10={latest:.2f}%")
        else:
            results["fredapi"] = {"note": "FRED_API_KEY not set — skipped fredapi path"}
    except ImportError:
        results["fredapi"] = {"note": "fredapi not installed"}
    except Exception as e:
        results["fredapi"] = {"error": str(e)}

    # Strategy B: direct FRED API (no key needed for public series with key=)
    try:
        params = {
            "series_id": FRED_SERIES,
            "sort_order": "desc",
            "limit": 10,
            "file_type": "json",
        }
        if FRED_API_KEY:
            params["api_key"] = FRED_API_KEY
        else:
            # FRED allows unauthenticated if you include api_key param pointing to demo
            params["api_key"] = "demo_key_caliber"  # will 403 but documents the path

        r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                         params=params, timeout=15)
        results["direct_api"] = {
            "status_code": r.status_code,
            "url_shape": r.url.split("?")[0],
            "response_keys": list(r.json().keys()) if r.status_code == 200 else [],
            "sample_observations": r.json().get("observations", [])[:3] if r.status_code == 200 else [],
            "error_message": r.json().get("error_message") if r.status_code != 200 else None,
        }
        if r.status_code == 200:
            obs = r.json().get("observations", [])
            valid = [(o["date"], o["value"]) for o in obs if o.get("value") != "."]
            if valid:
                print(f"  OK direct API: DGS10={valid[0][1]}% on {valid[0][0]}")
    except Exception as e:
        results["direct_api"] = {"error": str(e)}

    fixture = {
        "probed_at": NOW_ISO,
        "series": FRED_SERIES,
        "fred_api_key_present": bool(FRED_API_KEY),
        "results": results,
    }
    save(FIXTURE_ROOT / "fred" / "DGS10.json", fixture)

    # Summarize for record
    best = "ok" if any(
        "latest_value" in v or ("status_code" in v and v["status_code"] == 200)
        for v in results.values()
    ) else "partial"
    notes = "; ".join(f"{k}={list(v.keys())[:3]}" for k, v in results.items())
    record("fred", "DGS10", best, notes=notes)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("CALIBER Phase 0 — Reality Probe")
    print(f"Started: {NOW_ISO}")
    print("=" * 60)

    for ticker in TICKERS:
        probe_yfinance(ticker)
        time.sleep(1)

    for ticker in TICKERS:
        probe_edgar(ticker)
        time.sleep(1)

    probe_fred()

    # Summary
    print("\n" + "=" * 60)
    print("PROBE SUMMARY")
    print("=" * 60)
    all_ok = True
    for feed, tickers in RESULTS.items():
        for t, r in tickers.items():
            status = r["status"]
            flag = "OK" if status == "ok" else ("~~" if status == "partial" else "FAIL")
            print(f"  {flag} [{feed}] {t}: {r.get('notes') or r.get('error','')}")
            if status not in ("ok", "partial"):
                all_ok = False

    print()
    if all_ok:
        print("Gate: ALL FEEDS REACHED — fixtures written. Ready for schema-notes.md review.")
    else:
        print("Gate: SOME FEEDS FAILED — check fixture error files.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
