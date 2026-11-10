"""
Heat-stress days aligned to crop development windows (plan §4, Phase 4).

Pure function. Counts days where Tmax exceeds the crop-specific threshold
(35 °C base, scaled by heat tolerance). The threshold is applied over the
crop's flowering / grain-fill window — approximated here as the final third of
the season window (a declared simplification surfaced in the qualification).

Citation: FAO-56 context; threshold from local agronomy guidance (DAE/BARC).
"""

from __future__ import annotations

from dataclasses import dataclass

from .et0 import PowerDay
from . import rules


@dataclass
class HeatResult:
    threshold_days: int
    threshold_c: float
    max_tmax: float | None
    qualification: str = ""


def season_heat(days: list[PowerDay], heat_tolerance: str) -> HeatResult:
    """Count threshold days over the grain-fill window (final third)."""
    offset = rules.TOLERANCE_OFFSET_C.get(heat_tolerance, 0.0)
    threshold = rules.HEAT_TMAX_BASE_THRESHOLD_C - offset

    if not days:
        return HeatResult(threshold_days=0, threshold_c=threshold, max_tmax=None,
                          qualification="No POWER temperature series available.")

    # Flowering/grain-fill ≈ final third of the season window.
    window = days[max(0, len(days) - (len(days) // 3 or 1)):]
    threshold_days = 0
    max_tmax: float | None = None
    for d in window:
        if d.tmax is None:
            continue
        if max_tmax is None or d.tmax > max_tmax:
            max_tmax = d.tmax
        if d.tmax >= threshold:
            threshold_days += 1

    qualification = (
        f"Tmax >= {threshold:.0f} °C days during grain-fill "
        f"(tolerance: {heat_tolerance}); window = final third of season."
    )
    return HeatResult(threshold_days=threshold_days, threshold_c=threshold,
                      max_tmax=max_tmax, qualification=qualification)
