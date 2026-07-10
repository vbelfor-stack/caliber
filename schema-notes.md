# CALIBER Phase 0 — Schema Notes
Probed: 2026-07-09. Tickers: MU, GOOG, V. Reality wins — update this file when feeds diverge.

---

## yfinance (v0.2.61)

### General shape
- `yf.Ticker(ticker).info` returns ~170–180 keys. All values are scalars (int/float/str/None).
- Financial statement DataFrames (`financials`, `balance_sheet`, `cashflow`) have **Timestamp column headers** (not strings). Must call `str(col)` or `.strftime()` when serialising. This is the key quirk that caused the Phase 0 JSON serialisation crash.
- Columns are sorted descending (most recent first). Typically 4 annual periods.
- Row index is string labels (e.g. "Total Revenue", "Net Income", "Free Cash Flow").

### Key fields confirmed present
| Field | MU value | GOOG value | V value |
|-------|----------|------------|---------|
| `sector` | Technology | Communication Services | Financial Services |
| `industry` | Semiconductors | Internet Content & Information | Credit Services |
| `trailingPE` | 23.13 | present | present |
| `forwardPE` | 6.83 | present | present |
| `marketCap` | 1.15T | present | present |
| `debtToEquity` | 6.33 | present | present |
| `freeCashflow` | 7.64B | present | present |
| `revenueGrowth` | 3.46 (346%) | 0.218 (21.8%) | present |
| `grossMargins` | 0.726 | present | present |
| `enterpriseToEbitda` | present | present | 22.08 |
| `priceToBook` | present | present | 18.64 |

**Quirk — MU revenueGrowth=3.46:** yfinance returns YoY as a decimal (0.218 = 21.8%). A value of 3.46 = 346% YoY — consistent with Micron's FY2025 rebound from the memory downcycle trough. Adapter must multiply by 100 for display but store raw.

**Quirk — V sector="Financial Services", industry="Credit Services":** This is the golden-ticker trap for Visa. The lens selector must NOT trigger the bank/P/TBV path based on sector. Visa's `priceToBook`=18.6 confirms book value is irrelevant; must override to compounder lens based on industry keyword matching ("Credit Services" → compounder, not bank).

**Quirk — MU forwardPE=6.83 vs trailingPE=23.13:** Classic cyclical peak-earnings signature. The adapter must surface both and the lens selector must flag this spread as a mid-cycle signal requiring normalisation.

### earnings_history
- Columns: `epsActual`, `epsEstimate`, `epsDifference`, `surprisePercent`
- This is the beat/miss history for the management pillar. Rows indexed by quarterly date.
- surprisePercent is a float (e.g. 5.2 = 5.2% beat). Already in pct form.

### insider_transactions
- Columns: `Shares`, `Value`, `URL`, `Text`, `Insider`, `Position`, `Transaction`, `Start Date`, `Ownership`
- `Transaction` field contains human-readable strings (e.g. "Sale", "Purchase", "Option Exercise").
- No 10b5-1 flag in the raw data — must be inferred from `Text` field or treated as unknown.
- Adapter must classify: "Purchase" → potential cluster signal; "Sale" → check `Ownership` for context.

### Price history
- `tk.history(period="1y", interval="1d")` returns 252 rows for all three tickers.
- Columns: Open, High, Low, Close, Volume, Dividends, Stock Splits (with timezone-aware Timestamp index).
- Volume is an integer. 30-day avg volume must be computed from this series for the technicals pillar.

### Warnings (non-fatal, log and suppress in production)
- `Pandas4Warning: Timestamp.utcnow is deprecated` — internal yfinance issue with pandas 3.x. Does not affect data. Pin yfinance==0.2.61 and suppress with `warnings.filterwarnings("ignore", category=FutureWarning)`.

---

## EDGAR (direct HTTPS)

### Required header
```
User-Agent: CALIBER/3.0 victor.belfor@8x8.com
```
SEC blocks requests without a real User-Agent. This must be set on every request.

### CIK lookup — verified via https://www.sec.gov/files/company_tickers.json
| Ticker | CIK | Legal Name |
|--------|-----|------------|
| MU | 0000723125 | MICRON TECHNOLOGY INC |
| GOOG | 0001652044 | Alphabet Inc. |
| V | 0001403161 | VISA INC. |

**Critical fix from Phase 0:** Initial CIK for MU was `0000723254` (CINTAS CORP — a clothing manufacturer). Always look up CIK from `tickers.json`, never hardcode from memory. The adapter must fetch and cache this file at startup.

### Submissions API
- URL: `https://data.sec.gov/submissions/CIK{zero_padded_10_digit_cik}.json`
- Returns: company metadata + `filings.recent` dict with parallel arrays (form, filingDate, accessionNumber, primaryDocument, etc.)
- `primaryDocument` gives the main HTM filename (e.g. `mu-20250828.htm`).
- Filter on `form` in `("10-K", "10-K/A")` for annual; `("10-Q", "10-Q/A")` for quarterly.

### Filing document URL construction
- Base: `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_no_dashes}/{primary_document}`
- accn_no_dashes: strip hyphens from accessionNumber (e.g. `0000723125-25-000028` → `000072312525000028`)
- **Filing index JSON URL:** `{base_path}/{accn_hyphenated}-index.json` returns 404 for some filings. Use the index HTML instead: `{base_path}/{accn_hyphenated}-index.htm` or just fetch the primary document directly (it's in `primaryDocument`).
- **Adapter should:** fetch primary document directly using `submissions.filings.recent.primaryDocument` — no index lookup needed if the goal is Risk Factors + MD&A text.

### SIC codes observed
| Ticker | SIC | Description | Lens implication |
|--------|-----|-------------|-----------------|
| MU | 3674 | Semiconductors & Related Devices | → cyclical/mid-cycle |
| GOOG | 7370 | Computer Programming, Data Processing | → quality-compounder |
| V | 7389 | Business Services, NEC | → must NOT use SIC alone; override to compounder |

**Quirk — V SIC=7389:** "Business Services NEC" does not map to any obvious lens. Do NOT use SIC as the sole classifier for Visa. The lens selector must check industry keywords from both EDGAR SIC descriptions and yfinance `industry` field. "Credit Services" + "asset-light" + high priceToBook → compounder.

### Company Facts (XBRL)
- URL: `https://data.sec.gov/api/xbrl/companyfacts/CIK{zero_padded_10_digit_cik}.json`
- Returns structured financial data by GAAP concept with filing history.
- MU: 629 concepts, GOOG: 523 concepts, V: 625 concepts.
- Taxonomy key `us-gaap` is always present; `dei` also present.
- Useful for cross-checking specific metrics vs yfinance (revenue, net income, shares outstanding).
- Large payload (~5–15MB). Fetch lazily; don't load on every evaluation.

### Rate limiting
- SEC requests: add 0.5s sleep between calls. No formal rate limit stated but >10 req/s risks 429.

---

## FRED (fredapi v0.5.2 / direct API)

### Series used
- `DGS10` — 10-Year Treasury Constant Maturity Rate (daily, percent)

### Authentication
- `FRED_API_KEY` env var required for both fredapi and direct REST calls.
- Without key: fredapi skips gracefully; direct API returns HTTP 400 ("not a 32 character alpha-numeric lower-case string").
- **Degradation behaviour:** if key absent → log warning, set rate field to `{value: null, source: "FRED", as_of: null, confidence: "low"}`. Do NOT block evaluation; just lower rate-aware confidence.

### fredapi path (preferred when key present)
```python
from fredapi import Fred
fred = Fred(api_key=os.environ["FRED_API_KEY"])
series = fred.get_series("DGS10", observation_start="2024-01-01")
latest = float(series.dropna().iloc[-1])
as_of = str(series.dropna().index[-1])
```

### Direct REST path (fallback)
- URL: `https://api.stlouisfed.org/fred/series/observations`
- Params: `series_id=DGS10`, `sort_order=desc`, `limit=5`, `file_type=json`, `api_key={key}`
- Response: `{"observations": [{"date": "...", "value": "4.32"}, ...]}` — value is a STRING; cast to float. Value `"."` means missing (holiday/weekend); skip and take next.

### Quirk — value as string
`observations[i]["value"]` is always a string, including `"."` for missing. Filter: `[o for o in obs if o["value"] != "."]`.

---

## AlphaVantage (probed 2026-07-09, ticker MU, free tier)

### Endpoint used
- `OVERVIEW` — single call returns all fundamentals + price-derived ratios.
  `GET https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={key}`

### Response shape
All values are **strings**, including numeric fields and nulls. Missing = literal string `"None"`, `"-"`, or `""`. Must `float()` every field and filter these sentinel strings.

### Key fields confirmed present (MU values, 2026-07-09)
| Field | MU value | Used for |
|-------|----------|---------|
| `GrossProfitTTM` | 65510998000 | gross_margin = GrossProfitTTM / RevenueTTM |
| `RevenueTTM` | 90273997000 | denominator for gross_margin |
| `OperatingMarginTTM` | 0.804 | operating_margin cross-check |
| `ReturnOnEquityTTM` | 0.666 | roe cross-check |
| `ReturnOnAssetsTTM` | 0.349 | roa cross-check |
| `TrailingPE` | 21.23 | trailing_pe cross-check (price-derived) |
| `ForwardPE` | 6.36 | forward_pe cross-check |
| `PriceToBookRatio` | 10.94 | price_to_book cross-check |
| `EVToRevenue` | 11.99 | ev_to_revenue cross-check |
| `EVToEBITDA` | 15.84 | ev_to_ebitda cross-check |
| `Beta` | 2.142 | beta cross-check |
| `MarketCapitalization` | 1071568191000 | market_cap cross-check (price-derived) |
| `SharesOutstanding` | 1129393000 | shares_outstanding cross-check |

### Staleness behaviour (important for confidence)
- **Free tier data lag: up to 24-48 hours behind live market.** AV free tier OVERVIEW refreshes at EOD or next trading day. Intraday price-derived fields (TrailingPE, MarketCapitalization) may not match yfinance's live values even on the same calendar day.
- **Consequence for cross-check:** Price-derived fields (TrailingPE, MarketCapitalization, Beta) use `same_day_tol_pct=3.0` — a ±3% band for same-date comparisons — to avoid spurious conflicts from intraday timing differences. Genuine divergence >3% still degrades to LOW.
- **Fundamental ratios (margins, ROE/ROA):** Refreshed quarterly. Once an OVERVIEW is fresh, these are stable and typically agree with yfinance within 0.5%.

### Rate limit
- Free tier: 25 requests/day. Premium: 500/day.
- Each `run_single_ticker` makes 1 OVERVIEW call. A 25-ticker batch exhausts the free tier.
- Graceful degrade: if key absent or rate-limited, cross-check is skipped and all fields stay medium confidence.

### Cross-check agreement observed (MU, 2026-07-09)
| Field | yfinance | AlphaVantage | Diff | Result |
|-------|----------|--------------|------|--------|
| gross_margin | 0.7257 | 0.7257 | 0.0% | HIGH |
| operating_margin | 0.8037 | 0.804 | 0.04% | HIGH |
| roe | 0.6664 | 0.666 | 0.06% | HIGH |
| roa | 0.3487 | 0.349 | 0.09% | HIGH |
| forward_pe | 6.67 | 6.36 | 4.65% | HIGH |
| trailing_pe | 22.58 | 21.23 | 5.98% | **LOW** (same-day ±3% exceeded) |

**Quirk — trailing_pe divergence:** yfinance uses the live intraday price; AV free tier uses EOD or delayed. The 5.98% gap on TrailingPE is real methodology divergence, not a data error. LOW confidence on this field is the correct anti-launder outcome.

---

## Tiingo (not probed — replaced by AlphaVantage)

- Optional cross-check feed. TIINGO_API_KEY env var required.
- If absent: all yfinance fields degrade from high to medium confidence (single source).
- Phase 1 adapter must check for key at init and set a `tiingo_available` flag used by the confidence engine.
- Endpoint for fundamentals: `https://api.tiingo.com/tiingo/fundamentals/{ticker}/statements?token={key}`
- Endpoint for daily price: `https://api.tiingo.com/tiingo/daily/{ticker}/prices?token={key}`

---

## Cross-cutting adapter notes for Phase 1

1. **Timestamp column keys:** All DataFrame → dict conversions must call `str(k)` on column headers. Use a `_sanitise(obj)` helper that recurses through dicts and lists.
2. **NaN propagation:** yfinance returns `None` (Python None) for missing scalars in `info`. DataFrames may contain `NaN` (numpy float). Boundary: convert `NaN` → `None` at ingestion with `val if not (isinstance(val, float) and math.isnan(val)) else None`.
3. **Fiscal year alignment:** MU fiscal year ends August 31 (FYE code `0903` in EDGAR). GOOG ends December 31. V ends September 30. Financials DataFrame columns are period-end dates, not calendar years. The pillar scorer must label them correctly.
4. **Rate-of-change fields:** `revenueGrowth` from yfinance is YoY decimal (0.218 = 21.8%). A value > 1.0 (e.g. MU's 3.46) is valid — means 346% growth from a depressed base.
5. **CIK zero-padding:** Submissions API expects 10-digit zero-padded CIK in the URL (`CIK0000723125`). The integer form (723125) is used in the filing document path. Adapter must handle both.
6. **EDGAR filing document direct fetch:** Use `submissions.filings.recent.primaryDocument[i]` directly. The `-index.json` URL format 404s for some filings; do not rely on it.
