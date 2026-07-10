# CALIBER v3

Reliability-aware equity evaluation system. Five-pillar scorecard with provenance, LLM-synthesised bull/base/bear scenarios, 90-day forward-return grading, and a password-protected web UI.

---

## Quick-start (local)

```bash
cd caliber
pip install -r requirements.txt
cp .env.example .env   # fill in your secrets — never commit .env
python evaluate.py MU  # single-name CLI
uvicorn web.app:app --reload --port 8000
```

---

## Deploying to Replit

### 1. Push to GitHub

```bash
# From the caliber/ directory:
git init
git add -A
git commit -m "Initial CALIBER v3 — all phases"
gh repo create caliber --private --push --source .
```

Or create the repo manually on github.com and push to it.

### 2. Import from GitHub on Replit

1. Log in to [replit.com](https://replit.com).
2. Click **+ Create Repl**.
3. Select the **Import from GitHub** tab.
4. Paste your repository URL (e.g. `https://github.com/YOUR_USER/caliber`).
5. Language: **Python**.
6. Click **Import from GitHub**.

### 3. Set Secrets

In the Replit sidebar, open **Tools → Secrets** and add the following keys exactly as shown. Their values must match what you put in your local `.env`.

| Key | Required | Notes |
|-----|----------|-------|
| `ANTHROPIC_API_KEY` | **Yes** | Claude claude-sonnet-4-6 synthesis. Never echoed or logged. |
| `APP_PASSWORD` | **Yes** | Web UI login password. Never echoed or logged. |
| `ALPHAVANTAGE_API_KEY` | Optional | Cross-check feed. Free tier: 25 req/day. Degrades to single-source (medium confidence) if absent. |
| `FRED_API_KEY` | Optional | 10-year Treasury rate. Degrades gracefully if absent. |

> `.env` is listed in `.gitignore` and must never be committed. Only Replit Secrets reach the process at runtime.

### 4. Set the run command

In the **`.replit`** file (Replit creates it on import, or create it at the repo root):

```toml
[deployment]
run = ["python", "run_server.py"]

[[ports]]
localPort = 8000
externalPort = 80
```

Or in the Replit **Run** button configuration, set the run command to:

```
python run_server.py
```

`run_server.py` reads `PORT` from the environment — Replit injects this automatically on each deployment. The server binds to `0.0.0.0` so Replit's proxy can reach it.

### 5. Install dependencies

Replit should detect `requirements.txt` automatically. If not, open the Shell and run:

```bash
pip install -r requirements.txt
```

### 6. First run

Click **Run**. The app starts at your Replit `.repl.co` URL. Log in with the password you set in `APP_PASSWORD`.

---

## Scheduling

### Default: manual batch trigger

The **Batch** page in the UI (`/batch`) has a **Run Batch** button that kicks off a background evaluation of every ticker in `tickers.txt`. This is the recommended default — trigger it whenever you want a fresh sweep.

### Optional: weekly cadence via Replit Scheduled Deployments

Replit's Scheduled Deployments can trigger a run on a cron schedule without keeping the Repl awake 24/7.

1. In your Repl, open **Deployments** in the sidebar.
2. Create a new **Scheduled** deployment.
3. Set the schedule (e.g. `0 7 * * 1` = every Monday at 07:00 UTC).
4. Set the run command to:
   ```
   python -c "
   import sys; sys.path.insert(0, '.')
   from batch.runner import run_batch, read_universe
   run_batch(read_universe())
   "
   ```
5. Deploy. The evaluation loop runs on the cron, persists results to SQLite, and exits.

> The web UI remains separate. Use a standard (always-on) deployment for the web, and a Scheduled deployment for the batch job.

---

## Architecture

```
caliber/
  adapters/       yfinance · EDGAR · FRED · AlphaVantage
  core/           cross_check · lens_select · pillars · grading
  synthesis/      prompt · client (Anthropic) · schema (validation + repair)
  store/          SQLite models — evaluations · overrides · grades
  batch/          queue runner · scheduler
  web/            FastAPI app — library · deep · compare · batch · grading
  tests/          fixtures/ · unit tests
  evaluate.py     CLI: python evaluate.py MU
  smoke.py        Subsystem sanity check: python smoke.py
  run_server.py   Production launcher (reads PORT from env)
  tickers.txt     Universe — edit to add/remove names
```

## Key design constraints

- **Provenance on every field.** `high` confidence = two independent sources agree and fresh; `medium` = single source; `low` = conflict or unreliable.
- **Anti-launder.** A verdict's confidence can never exceed its weakest load-bearing pillar.
- **Sector-adaptive valuation.** Cyclical stocks (MU) require mid-cycle normalisation; payment networks (V) use compounder lens, not P/TBV.
- **EDGAR feeds the bear.** Risk Factors and MD&A excerpts are primary-source evidence.
- **Secrets never logged.** `ANTHROPIC_API_KEY` and `APP_PASSWORD` are read from environment variables and never echoed.

## Smoke test

```bash
cd caliber
python smoke.py
```

All 9 checks must print `PASS`. Exit code 0 = push-ready.

## Upgrade path

- **More data feeds:** drop in a new adapter under `adapters/`; hook it into `apply_av_cross_checks` or add a new cross-check function.
- **Richer LLM model:** change `model` in `synthesis/client.py`.
- **Persistent grading history:** `core/grading.run_grading()` grades all ungraded evaluations ≥90 days old; run it on a cron alongside the batch sweep.
