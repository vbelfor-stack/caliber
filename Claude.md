# CALIBER v3 — Claude Code Build Prompt

Paste everything below this line into Claude Code, run from an empty project directory.

---

You are building **CALIBER v3**, a reliability-aware equity evaluation system for a single professional investor. Python backend, batch-capable, with persistent storage and an LLM synthesis layer. This document is the complete spec. Build it phase by phase, test-as-you-go, and do not advance a phase until its gate passes.

## Mission

A system that evaluates stocks across five measured pillars, runs probabilistic bull/base/bear synthesis via the Anthropic API, stores every evaluation forever, supports batch runs, and never presents a verdict more confident than its inputs. The final deliverable is a git repository ready for import into Replit (Replit is the hosting runtime only — you are the builder).

## Non-negotiable design ethos

These rules are the product. Violating them is a failed build even if everything runs.

1. **Provenance everywhere.** Every data field carries {value, source, as_of, confidence: high|medium|low}. Confidence rules: two independent sources agree and fresh → high; single source or undated → medium; sources conflict or known-unreliable category → low.
2. **Anti-launder rule.** A pillar's confidence cannot exceed the minimum confidence of its material inputs. The verdict's confidence cannot exceed its softest load-bearing pillar. Soft inputs → soft verdict, always, visibly.
3. **Sector-adaptive valuation.** The lens is selected per company and displayed:
   - software / high-growth → Rule of 40/60, EV/S vs growth, FCF margin
   - cyclical / hardware / semis / memory / materials → normalize to MID-CYCLE earnings; a low P/E on peak earnings is a SELL signal, not cheap; state cycle position
   - banks / insurers / REITs → P/TBV, P/FFO
   - asset-light financial networks (payments, exchanges, ratings) → quality-compounder lens (FCF yield, EV/EBITDA, growth durability), NOT P/TBV
   - otherwise → standard EV/EBITDA, P/E, FCF yield
4. **Management pillar is strictly factual.** Beat/miss history and surprise magnitude, insider activity (cluster buying = strong positive; routine 10b5-1 selling = noise; discretionary selling into strength = mild flag), dilution rate, ROIC trend, buyback timing. No intent inference. No guidance-sandbag detection.
5. **Value trap is emergent, never an input.** The synthesis constructs it only when cheap + solvent + no growth align in the measured pillars.
6. **Technicals are a timing overlay only.** Separate output. Flag contradiction with fundamentals. A bullish chart never lifts a broken company's verdict. Include volume confirmation: breakout on ≥1.5× 30-day average volume = conviction; thin volume = noise.
7. **Research tiering, cite-or-silent.** Analyst views tiered independent (Morningstar, CFRA, Argus, credible boutiques — highest weight) / sell-side (tag conflicted; flag if underwriter) / crowd (Seeking Alpha contributors, Motley Fool — lowest/excluded). Only verified attributions. "No reputable independent coverage found" is a valid output. Price targets are dated opinions, never valuation inputs.
8. **Expected-value verdict.** Bull/base/bear each get probability AND scenario price target. Output E(R) = Σ pᵢ·rᵢ against current price. Probabilities sum to ~100.
9. **EDGAR feeds the bear.** Latest 10-K/10-Q Risk Factors + MD&A excerpts are primary-source bear evidence, highest confidence tier.
10. **Rate-aware valuation.** Pull the current 10Y from FRED; judge multiples relative to the risk-free regime.

## Closed decisions (do not reopen)

- Data feeds: yfinance primary + Tiingo cross-check (free tier; TIINGO_API_KEY via env, optional — degrade to single-source/medium-confidence if absent). Upgrade path to FMP noted in README, not built.
- EDGAR: direct HTTPS with proper User-Agent header. FRED: fredapi or direct API (FRED_API_KEY via env).
- Store: SQLite. Single user.
- Frontend: served from the same app (FastAPI + simple server-rendered or light JS frontend), password-protected via APP_PASSWORD env var. No Okta, no external auth.
- Manual punch-in is demoted to override-on-flag: fields auto-accept on dual-source agreement; disagreement/staleness/missing → flagged for user override via frontend.
- First batch universe: user's holdings + watchlist (~20–30 names; ships as a editable tickers.txt).
- Re-run cadence: weekly scheduled + on-demand.
- Synthesis: Anthropic API, model claude-sonnet-4-6, ANTHROPIC_API_KEY via env, never hardcoded, never logged.

## Architecture

```
caliber/
  adapters/        # yfinance, tiingo, edgar, fred — each returns Provenanced fields
  core/            # cross_check, confidence, lens_select, pillars, ev_engine
  synthesis/       # prompt.py (system prompt), client.py (API call), schema.py (validation + truncation repair)
  store/           # sqlite models: evaluations, field_provenance, overrides, grades
  batch/           # queue runner + weekly scheduler
  web/             # FastAPI app: library, deep view, compare, batch queue, flag-resolution
  tests/
    fixtures/      # recorded live responses (see Phase 0)
    golden/        # the five golden-ticker behavioral tests
  evaluate.py      # CLI: python evaluate.py MU
  smoke.py         # prints PASS/FAIL per subsystem
```

## Build phases and gates

**Phase 0 — Probe reality first.** Before writing adapters, write and RUN a probe script hitting yfinance, Tiingo (if key present), EDGAR, FRED for MU, GOOG, V. Save raw responses under tests/fixtures/. All adapter unit tests run against these recorded fixtures; live calls are integration-only. This kills the guessed-data-shape bug class.
Gate: fixtures exist on disk; a schema-notes.md documents each feed's actual shape and quirks.

**Phase 1 — Adapters + scoring core.** Adapters with loud, context-rich failures (feed, ticker, URL, raw payload snippet in every error). Boundary validation: bad data fails at the door with a named field, never as a downstream NaN. Cross-check + confidence engine. Lens selector. Five-pillar scorer, deterministic.
Gate: `python evaluate.py MU` prints a full pillar readout with provenance stamps; full unit suite green; lens tests pass (see golden behaviors below).

**Phase 2 — Synthesis + store.** Port the synthesis system prompt (below). Schema validation with tolerant JSON repair (strip fences, fix thousands separators, close truncated brackets, progressively trim trailing incomplete elements). Persist complete evaluations to SQLite.
Gate: one real MU run persists and validates; adversarial tests pass — a truncated payload repairs or fails loudly (never half-parses silently), and a deliberately degraded input set produces verdictConfidence=low (anti-launder proof).

**Phase 3 — Batch + scheduler.** Queue runner with per-name isolation (one name failing never kills the batch; failures land in the store as failed-with-diagnosis).
Gate: 5-name batch completes; scheduler dry-run logs correctly.

**Phase 4 — Frontend.** Library, single-name deep view, compare (2–4 names side by side), batch queue, flag-resolution panel. Style: light "instrument paper" — off-white ground, deep slate text, brass hairline accents, jade/brick for bull/bear, hatching/visual softening for low confidence. Confidence dots on every field.
Gate: library lists stored runs; compare shows MU and NOW with visibly different valuation lenses; a simulated feed disagreement surfaces in flag-resolution and accepts an override that persists.

**Phase 5 — Grading.** Forward-return scoring of stored verdicts vs published E(R) (90-day default). Ships as a module + view; needs history to be meaningful.
Gate: grading runs against synthetic backdated rows.

**Finish:** README with Replit import steps (git import, set Secrets: ANTHROPIC_API_KEY, APP_PASSWORD, optional TIINGO_API_KEY/FRED_API_KEY, run command), pinned requirements.txt, smoke.py green top to bottom.

## Golden-ticker behavioral tests (tests/golden/)

These encode the product's judgment. Each is a real assertion against pillar/synthesis output. Where synthesis is involved, assert on structure and direction, not exact wording.

1. **MU (Micron)** — lens must be cyclical/mid-cycle. If trailing P/E is low while margins are near cycle highs, valuation rationale MUST contain the peak-earnings warning and the low multiple must NOT score as cheap. Cycle position stated.
2. **GOOG (Alphabet)** — mega-cap compounder. Must NOT get the hypergrowth Rule-of-40 framing as its primary lens; standard quality-compounder valuation with growth context. Sanity: pillar scores high on quality/health.
3. **V (Visa)** — the classifier trap. Sector metadata says "financial"; the lens MUST NOT be P/TBV (asset-light network — book value is meaningless). Correct: quality-compounder lens. This is a hard assertion: lens == compounder, lens != bank.
4. **NOW (ServiceNow)** — the false-positive boundary. Premium multiple: the synthesis MUST NOT label it a value trap today (assert "value trap" absent from bear thesis labels/red flags). The bear case MUST carry a derating/deceleration path (agentic-AI commoditization of seat-based SaaS, multiple compression) as a probabilistic scenario. verdictConfidence should not be high if the commoditization question is material and unresolved — anti-launder in action.
5. **WU (Western Union)** — the true-positive. Cheap + solvent + secular decline: the synthesis MUST construct the value-trap thesis in the bear case (assert presence). Tests that the emergent reasoning fires at all.

Run golden tests at every phase boundary from Phase 2 onward. A lens regression or a value-trap false positive/negative is a build failure.

## Synthesis system prompt (port into synthesis/prompt.py)

Use the following as the system prompt for the Anthropic call, with the deterministic pillar data injected as structured context in the user message (the model no longer researches fundamentals — it receives them; it researches only qualitative color: news, analyst views, filings context via its own knowledge cutoff limits, so keep claims tied to provided data and clearly mark anything beyond it):

- You are the synthesis engine inside CALIBER. You receive measured pillar data with provenance and confidence. Your job: bull/base/bear scenarios with probabilities and price targets, red flags, research tiering, and a verdict whose confidence NEVER exceeds its softest load-bearing input.
- Never invent a number, source, or analyst view. Unverified attribution → omit. "No reputable independent coverage found" is a valid output.
- Value trap is emergent: construct it only if the provided data shows cheap + solvent + no growth.
- Respect the provided valuation lens; if data shows a cyclical near peak margins with a low multiple, say the multiple is a sell signal.
- Output ONLY valid JSON per the provided schema. Numbers as bare digits (no separators, symbols, units). null for unknown. Terse: rationales <220 chars. Probabilities for bull+base+bear sum to ~100; each scenario carries a price target; compute nothing — targets are your judgment, E(R) is computed downstream.

(Full JSON schema: define in schema.py mirroring the pillar structure above — company, pillars×5 {score, confidence, rationale, flags, method}, redFlags[], scenarios{bull, base, bear: {thesis, points[], probability, priceTarget}}, research[], technicals{...volume fields...}, dataGaps[], verdictConfidence + reason.)

## Engineering discipline

- TDD for core/: tests first or alongside, never after. Nothing merges un-executed.
- Every adapter failure includes full context. Every boundary validates. No silent NaN propagation — assert or raise at ingestion.
- Pin all dependency versions. Python 3.11+.
- Secrets only via env. Never print or log key material.
- Commit per phase with the gate output in the commit message.
- If a live feed's shape contradicts a fixture, update the fixture from reality and note it in schema-notes.md — reality wins, always.

Begin with Phase 0.
