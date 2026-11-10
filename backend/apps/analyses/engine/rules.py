"""
Rule set for the rotation engine (plan §4, Phase 4).

``RULE_VERSION`` is stamped onto every completed run so a rerun is reproducible
and the UI can display which rule set produced a score. Keep this module
deterministic — no randomness, no I/O.
"""

RULE_VERSION = "v2026.11.0"

# --- Water balance (water_balance.py) --------------------------------------
# Canal/drip efficiency: fraction of delivered water that reaches the root zone.
IRRIGATION_EFFICIENCY = {
    "canal": 0.70,
    "drip": 0.85,
    "rainfed": 0.0,   # rainfed: no applied irrigation
}
# Declared root-zone bucket capacity by soil drainage (mm of water storage).
BUCKET_CAPACITY_MM = {
    "poor": 80.0,
    "moderate": 110.0,
    "good": 140.0,
}
# Below this fraction of bucket, the crop is stressed (drives dry-spell count).
STRESS_THRESHOLD_FRACTION = 0.20
# Paddy field-water term (mm) — standing water in the bund during the early
# rice season; included in the water balance for paddy baseline.
PADDY_FIELD_WATER_MM = 60.0

# --- Heat (heat.py) ----------------------------------------------------------
# Threshold day count that flags heat stress at flowering / grain-fill,
# scaled by crop heat tolerance. Days with Tmax >= (35 − tolerance_offset).
HEAT_TMAX_BASE_THRESHOLD_C = 35.0
TOLERANCE_OFFSET_C = {
    "high": 2.0,     # tolerant crops tolerate 2 °C more before stress
    "moderate": 0.0,
    "low": -2.0,     # sensitive crops stress 2 °C earlier
}

# --- Canopy cover (cover.py) -------------------------------------------------
# Baseline canopy cover fraction per season when HLS coverage is inadequate.
DEFAULT_CANOPY_FRACTION = 0.60
# Below this HLS valid coverage we fall back to the calendar (inferred).
HLS_COVERAGE_FLOOR = 0.40

# --- Diversity (diversity.py) ------------------------------------------------
# Tiemann et al. (2015): more unique families + a legume in the rotation
# improves yield stability. We score family count and legume inclusion.
LEGUME_BONUS = 0.15
MAX_FAMILIES = 5  # cap the diversity score at 5 distinct families

# --- Economics (economics.py) ------------------------------------------------
# Net-margin sensitivity: we emit a RANGE (low/high) not a point, and expose
# whether a small weight change flips the preferred plan.
SENSITIVITY_WEIGHT_DELTA = 0.10

# --- Candidate enumeration (candidates.py) ----------------------------------
MAX_CANDIDATES = 50  # hard cap on enumerated rotations (plan §4)
# A candidate is "materially different" from baseline if >= 1 family differs.
MIN_DIFFERING_FAMILIES = 1

# --- Normalization bounds (score.py) ----------------------------------------
# Declared bounds used to normalize each metric to [0,1]. These are the
# "declared bounds" the report requires; the UI can show them on /method.
BOUNDS = {
    "water_efficiency": {  # irrigation demand (mm): lower is better
        "min": 0.0, "max": 500.0, "direction": "lower_is_better",
    },
    "heat_resilience": {  # threshold days (lower is better)
        "min": 0.0, "max": 30.0, "direction": "lower_is_better",
    },
    "canopy_cover": {  # fraction (higher is better)
        "min": 0.0, "max": 1.0, "direction": "higher_is_better",
    },
    "diversity": {  # 0..1 composite (higher is better)
        "min": 0.0, "max": 1.0, "direction": "higher_is_better",
    },
    "net_margin": {  # BDT per ha (higher is better)
        "min": 0.0, "max": 200_000.0, "direction": "higher_is_better",
    },
}

# Default farmer weights (sum to 1.0). The UI sliders override these.
DEFAULT_WEIGHTS = {
    "water_efficiency": 0.25,
    "heat_resilience": 0.15,
    "canopy_cover": 0.15,
    "diversity": 0.15,
    "net_margin": 0.30,
}

METRIC_KEYS = list(DEFAULT_WEIGHTS.keys())
