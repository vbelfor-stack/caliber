"""Versioned, Vic-tunable configuration for the Phase L lifecycle classifier.

Every threshold the classifier consults lives here and nowhere else, so a tuning
decision is one edit in one file and the value that was in force is recorded on every
classification (`config_version` is stamped into `lifecycle_stage`).

WHY A VERSION STRING AND NOT JUST THE NUMBERS: a stage table read six months from now
has to answer "was this DECLINE computed under the 15% CAGR bar or a later one?" — a
question the stored stage alone cannot answer. Bump LIFECYCLE_CONFIG_VERSION whenever a
value below changes; the classifier never edits it.

Thresholds are OURS (order §3). Damodaran's model.xls informed the rule STRUCTURE only.
"""
from __future__ import annotations

LIFECYCLE_CONFIG_VERSION = "L-v1-2026-08-16"

# ── Windows ───────────────────────────────────────────────────────────────────
# R11: the margin-trend window is 3 fiscal years (latest FY vs FY-3, i.e. 4 data
# points), matching the CAGR leg's horizon so every DECLINE leg measures the SAME recent
# window. DECLINE is a current-state classification, not a decade verdict.
TREND_WINDOW_YEARS = 3
CAGR_WINDOW_YEARS = 3

# R9: peak-to-peak needs to SEE a cycle. Below this many measured fiscal years the
# cyclical guard is asserted-absent, and for a cyclical-lens name that means DECLINE
# cannot fire at all — through-cycle evidence or nothing.
CYCLICAL_MIN_FY = 8

# Order §2: below this, classify YOUNG with a data-insufficiency assertion.
MIN_FY_FOR_CLASSIFICATION = 2

# ── Rule thresholds ───────────────────────────────────────────────────────────
# R11: the flat band is calibrated TO THE DEFAULT 3y WINDOW. Widening the window means
# revisiting this number — drift accumulates with length, so ±100bp over 10y is a much
# tighter claim than ±100bp over 3y.
MARGIN_FLAT_BAND_BP = 100.0          # "flat/down" == delta <= +100bp

DECLINE_MIN_STREAK_YEARS = 2          # consecutive declining revenue years
DECLINE_MIN_STREAK_YEARS_CYCLICAL = 3  # cyclical guard raises the bar (order §3 rule 1)

HIGROWTH_MIN_CAGR = 0.15              # 15% revenue 3y CAGR

# R6 STRUCK "top-half of sector" — no compliant source, and peer-set fetches are
# rejected under the peer-anchor precedent. Replaced with an ABSOLUTE threshold on
# sales-to-capital. DEFAULT PROPOSED BY CODE AT DARK-RUN REVIEW, per R6.
#
# Proposed default and its basis (measured FY sales-to-capital, docs/orders record):
#   MU   0.575 0.669 0.659 0.332 0.515 0.668     capital-heavy cyclical
#   GOOG 2.032 2.241 1.659 1.450 1.195           heavy reinvestment, falling as capex rises
#   WU   2.673 2.726 3.203 1.722 1.553           asset-light, low reinvestment need
#   NOW  1.625 (single point — asserted-absent per R6)
# LOWER sales-to-capital == HEAVIER reinvestment (more capital consumed per unit of
# sales). So "reinvestment is high" is `sales_to_capital <= threshold`, NOT >=. Setting
# the bar at 1.50 puts MU and GOOG's recent years on the heavy side and WU on the light
# side, which matches the businesses. FOUR TICKERS IS NOT A CALIBRATION — this is a
# reasoned default awaiting Vic's ruling, and it is flagged REINVESTMENT-THRESHOLD-
# UNCALIBRATED on every reading that consults it.
REINVESTMENT_HEAVY_MAX_SALES_TO_CAPITAL = 1.50

# Rule 3 needs "capital returns absent or DE MINIMIS". A buyback counts as a real capital
# return only past this net share-count reduction over the trend window; below it, share
# count noise (option issuance netting against small repurchases) would read as a return.
BUYBACK_DE_MINIMIS_NET_REDUCTION = 0.01   # 1% net reduction over the window

# ── §5.1 stage-conditioned anchor-divergence tolerances ───────────────────────
# R10: the guard is B-2 (synthesis/schema.ANCHOR_DIVERGENCE_THRESHOLD), NOT B-1. The
# order's §5.1 label was an authoring error, corrected at ruling. These are DARK in this
# phase — defined, tested, and consumed by nothing until §5.1 is armed on its own.
B2_DIVERGENCE_TOLERANCE_BY_STAGE = {
    "YOUNG": 0.30,
    "HIGROWTH": 0.20,
    "MATURE": 0.15,
    "DECLINE": 0.15,
}

# ── §5.4 Phase M width priors (STUB — multipliers deferred to M arming) ───────
# Ordering is the only claim this phase makes: YOUNG widest, MATURE tightest. The
# numbers are placeholders and are NOT to be read as calibrated.
M_WIDTH_PRIOR_STUB = {
    "YOUNG": None,
    "HIGROWTH": None,
    "MATURE": None,
    "DECLINE": None,
}
M_WIDTH_PRIOR_ORDERING = ("MATURE", "DECLINE", "HIGROWTH", "YOUNG")  # tightest -> widest
