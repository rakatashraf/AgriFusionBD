"""
Canopy-cover fraction for a season (plan §4, Phase 4).

Pure function. Uses the reviewed calendar's expected cover as a baseline and
corrects it with the HLS NDVI series where coverage is adequate. The result is
tagged ``inferred`` (calendar-only) vs ``observed`` (NDVI-corrected) so the UI
can show the distinction (report §1: historical vs inferred stay distinct).

NDVI → cover mapping: cover ≈ NDVI (a declared linearisation for the pilot).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import rules


@dataclass
class CoverResult:
    fraction: float      # 0..1
    source: str          # "observed" (NDVI) | "inferred" (calendar)
    ndvi: float | None
    coverage_pct: float | None
    qualification: str = ""


def season_canopy_cover(
    expected_fraction: float,
    ndvi: float | None,
    ndvi_coverage_pct: float | None,
) -> CoverResult:
    """Blend calendar expectation with NDVI where coverage is adequate."""
    if ndvi is not None and ndvi_coverage_pct is not None and ndvi_coverage_pct >= rules.HLS_COVERAGE_FLOOR * 100:
        # NDVI-corrected cover, clamped to [0,1].
        fraction = max(0.0, min(1.0, ndvi))
        return CoverResult(
            fraction=fraction,
            source="observed",
            ndvi=ndvi,
            coverage_pct=ndvi_coverage_pct,
            qualification=(
                f"Canopy cover from USGS HLS NDVI ({ndvi:.2f}); "
                f"valid coverage {ndvi_coverage_pct:.0f}% (>= {rules.HLS_COVERAGE_FLOOR:.0%})."
            ),
        )
    # Fall back to the calendar expectation (inferred).
    fraction = max(0.0, min(1.0, expected_fraction))
    reason = "HLS NDVI unavailable or below 40% valid coverage"
    return CoverResult(
        fraction=fraction,
        source="inferred",
        ndvi=ndvi,
        coverage_pct=ndvi_coverage_pct,
        qualification=(
            f"Canopy cover from reviewed calendar ({fraction:.0%}); {reason}."
        ),
    )
