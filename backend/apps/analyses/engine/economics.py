"""
Net-margin RANGE for a rotation (plan §4, Phase 4).

Pure function. The report and plan both require a **range**, not a point
estimate: ``net_margin = yield × price − cost``, each taken over its declared
[low, high] band. We emit both the low and high ends plus a sensitivity flag:
whether shifting any single weight by SENSITIVITY_WEIGHT_DELTA would change
the preferred plan (surfaced by score.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EconCrop:
    """Per-crop economics band for one season slot."""
    slug: str
    yield_low_t: float
    yield_high_t: float
    price_low: float  # BDT/kg
    price_high: float
    cost_low: float   # BDT/ha
    cost_high: float
    area_ha: float = 1.0


@dataclass
class EconomicsResult:
    net_margin_low: float   # BDT/ha (pessimistic)
    net_margin_high: float  # BDT/ha (optimistic)
    per_crop: list[dict] = field(default_factory=list)
    qualification: str = ""


def rotation_economics(crops: list[EconCrop]) -> EconomicsResult:
    """Sum the net-margin band across the rotation's crop slots."""
    low = 0.0
    high = 0.0
    per_crop: list[dict] = []
    for c in crops:
        rev_low = c.yield_low_t * 1000.0 * c.price_low * c.area_ha
        rev_high = c.yield_high_t * 1000.0 * c.price_high * c.area_ha
        crop_low = rev_low - c.cost_low * c.area_ha
        crop_high = rev_high - c.cost_high * c.area_ha
        low += crop_low
        high += crop_high
        per_crop.append({
            "slug": c.slug,
            "revenue_low": round(rev_low, 0),
            "revenue_high": round(rev_high, 0),
            "cost_low": round(c.cost_low * c.area_ha, 0),
            "cost_high": round(c.cost_high * c.area_ha, 0),
            "net_low": round(crop_low, 0),
            "net_high": round(crop_high, 0),
        })
    low = max(0.0, low)
    high = max(0.0, high)
    qualification = (
        "Net-margin RANGE from yield × price − cost over declared bands; "
        "no single point estimate. Sensitivity checked in score.py."
    )
    return EconomicsResult(
        net_margin_low=low,
        net_margin_high=high,
        per_crop=per_crop,
        qualification=qualification,
    )
