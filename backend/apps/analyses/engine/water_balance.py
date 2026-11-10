"""
Soil-water balance with effective rainfall and irrigation demand (plan §4).

Pure function — no ORM. Computes, for a season window:
  - daily ET0 (FAO-56) × crop coefficient Kc → ETc,
  - effective rainfall via a USDA-SCS curve-number-style loss fraction,
  - the root-zone bucket (declared capacity),
  - irrigation demand (mm) = max(0, ETc − effective rain) net of bucket,
  - dry-spell days (bucket < 20 % of capacity),
  - the paddy field-water term for the baseline rice season.

The engine never invents rainfall: a POWER gap day (``prectot is None``)
contributes 0 effective rain AND is counted as an uncertainty day, surfaced in
the metric qualification (plan §3: never replace missing rainfall with zero).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .et0 import PowerDay, compute_et0
from . import rules


@dataclass
class WaterBalanceResult:
    etc_mm: float
    effective_rainfall_mm: float
    irrigation_demand_mm: float
    dry_spell_days: int
    gap_days: int  # days with missing rainfall (uncertainty, not zero)
    bucket_capacity_mm: float
    paddy_field_water_mm: float
    qualification: str = ""


def _effective_rain(precip_mm: float | None, cn: int = 70) -> float | None:
    """
    USDA-SCS effective rainfall: ``Pe = (P - 0.2 * S)^2 / (P + 0.8 * S)``
    where ``S = 25400/CN - 254`` (mm). A gap (None) stays None — never 0.
    CN 70 ≈ typical upland paddy/vegetative soil; paddy bund is handled by
    the field-water term, not CN.
    """
    if precip_mm is None:
        return None
    if precip_mm <= 0:
        return 0.0
    s = 25400.0 / cn - 254.0
    if s <= 0:
        return precip_mm
    pe = ((precip_mm - 0.2 * s) ** 2) / (precip_mm + 0.8 * s)
    return max(0.0, min(pe, precip_mm))


def season_water_balance(
    days: list[PowerDay],
    kc_canopy: float,
    irrigation: str,
    drainage: str,
    is_paddy: bool,
) -> WaterBalanceResult:
    """Run the bucket model across the season window."""
    capacity = rules.BUCKET_CAPACITY_MM.get(drainage, rules.BUCKET_CAPACITY_MM["moderate"])
    eff = rules.IRRIGATION_EFFICIENCY.get(irrigation, 0.70)
    paddy_term = rules.PADDY_FIELD_WATER_MM if is_paddy else 0.0

    bucket = capacity  # start full (declared assumption)
    total_etc = 0.0
    total_peff = 0.0
    irrigation_demand = 0.0
    dry_spell_days = 0
    gap_days = 0

    for day in days:
        et0 = compute_et0(day)
        if et0 is None:
            # No ET0 possible (gap): count as gap day, skip bucket update.
            gap_days += 1
            continue
        etc = et0 * kc_canopy
        total_etc += etc
        pe = _effective_rain(day.prectot)
        if pe is None:
            gap_days += 1
            # Rainfall missing — do NOT add 0; treat as no replenishment and
            # let the bucket draw down (conservative).
            pe = 0.0
        else:
            total_peff += pe
        # Bucket update: replenish from effective rain, lose to ETc.
        bucket = min(capacity, bucket + pe)
        bucket = max(0.0, bucket - etc)
        if bucket < rules.STRESS_THRESHOLD_FRACTION * capacity:
            dry_spell_days += 1
            # Irrigation covers the shortfall to refill the bucket.
            shortfall = (capacity - bucket) * eff
            irrigation_demand += max(0.0, (capacity - bucket) - pe + etc)

    # Paddy field-water term reduces net irrigation demand for the baseline.
    irrigation_demand = max(0.0, irrigation_demand - paddy_term)

    qualification = (
        f"Reference ET0 × crop coefficients; {irrigation} irrigation "
        f"(efficiency {eff:.0%}); bucket capacity {capacity:.0f} mm; "
        f"paddy field-water term {paddy_term:.0f} mm; "
        f"{gap_days} day(s) with missing rainfall treated as uncertainty, not zero."
    )
    return WaterBalanceResult(
        etc_mm=total_etc,
        effective_rainfall_mm=total_peff,
        irrigation_demand_mm=irrigation_demand,
        dry_spell_days=dry_spell_days,
        gap_days=gap_days,
        bucket_capacity_mm=capacity,
        paddy_field_water_mm=paddy_term,
        qualification=qualification,
    )
