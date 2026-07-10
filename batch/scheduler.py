"""
CALIBER v3 — weekly scheduler.

dry_run(): logs exactly what a scheduled run would do without executing it.
run_scheduled(): executes the batch and logs timing.

In production (Phase 3+), this is invoked by a cron job or Replit's Always-On scheduler.
For now, dry_run() is the gate-passing deliverable.

Usage:
  python -m batch.scheduler              # dry-run (default)
  python -m batch.scheduler --execute    # live run (requires all API keys)
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
except ImportError:
    pass

from batch.runner import read_universe, run_batch, DEFAULT_UNIVERSE

_SCHEDULE_DESC = "Weekly — every Monday 06:00 UTC before US market open"


def dry_run(
    universe_path: Path = DEFAULT_UNIVERSE,
    verbose: bool = True,
) -> List[str]:
    """
    Log what a scheduled run would do. Makes no API calls. Returns ticker list.
    """
    now = datetime.now(timezone.utc)
    tickers = read_universe(universe_path)

    lines = [
        f"[scheduler] dry-run  {now.isoformat()}",
        f"[scheduler] schedule  {_SCHEDULE_DESC}",
        f"[scheduler] universe  {universe_path}  ({len(tickers)} tickers)",
        f"[scheduler] mode      live (fixture_mode=False)",
        f"[scheduler] synthesis enabled",
        f"[scheduler] pipeline per ticker:",
        f"[scheduler]   1. yfinance (primary)",
        f"[scheduler]   2. EDGAR",
        f"[scheduler]   3. FRED 10Y rate",
        f"[scheduler]   4. AlphaVantage cross-check (if key set)",
        f"[scheduler]   5. lens selection + five pillars",
        f"[scheduler]   6. synthesis (Anthropic API)",
        f"[scheduler]   7. persist to SQLite",
        f"[scheduler] isolation: per-ticker try/except; failures stored as failed-with-diagnosis",
        f"[scheduler] tickers queued ({len(tickers)}):",
    ]
    for i, t in enumerate(tickers, 1):
        lines.append(f"[scheduler]   {i:3d}. {t}")

    est_duration = len(tickers) * 45
    lines.append(f"[scheduler] estimated duration: ~{est_duration}s ({len(tickers)} x 45s avg)")
    lines.append(f"[scheduler] dry-run complete — no API calls made")

    if verbose:
        for line in lines:
            print(line)

    return tickers


def run_scheduled(universe_path: Path = DEFAULT_UNIVERSE) -> None:
    """Execute a live scheduled batch run."""
    tickers = dry_run(universe_path, verbose=True)
    print(f"\n[scheduler] starting live run...\n")
    run_batch(tickers, fixture_mode=False, run_synthesis=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="CALIBER v3 — scheduler")
    parser.add_argument("--execute", action="store_true", help="Run live (default: dry-run)")
    parser.add_argument("--universe", default=str(DEFAULT_UNIVERSE))
    args = parser.parse_args()

    universe = Path(args.universe)
    if args.execute:
        run_scheduled(universe)
    else:
        dry_run(universe)


if __name__ == "__main__":
    main()
