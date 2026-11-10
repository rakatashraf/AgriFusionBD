"""
Assemble a frozen ``EngineInput`` from the ORM for a given AnalysisRun.

This is the single bridge between Django models and the pure engine (plan §4:
the engine itself has no ORM). It:
  - fetches the field + soil test + crop history (baseline),
  - fetches the POWER series (cached/stale per plan §3) and HLS NDVI,
  - loads the catalogue crop traits,
  - records the provenance ids (asset ids + content hashes) for the snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.utils import timezone

from apps.catalogue.models import Crop, SoilTest
from apps.environment.models import FieldIndicator
from apps.environment.services import hls as hls_service
from apps.environment.services import power as power_service
from apps.farms.models import CropHistory, Field

from .engine.candidates import CropTraits
from .engine.et0 import PowerDay
from .engine.runner import EngineInput
from .engine import rules


@dataclass
class BuiltSnapshot:
    engine_input: EngineInput
    power_asset_id: str = ""
    power_content_hash: str = ""
    hls_asset_id: str = ""
    hls_content_hash: str = ""


def _season_window_months(season: str) -> list[int]:
    # Declared season windows for the Bangladesh pilot (DAE/BARC calendars).
    return {
        "boro": [12, 1, 2, 3, 4],      # winter (Dec–Apr)
        "aman": [6, 7, 8, 9, 10],      # monsoon (Jun–Oct)
        "rabi": [11, 12, 1],           # late winter
        "autumn": [9, 10, 11],
        "spring": [3, 4, 5],
    }.get(season, [12, 1, 2, 3])


def _power_window_for_season(season: str) -> tuple[str, str]:
    """
    A 60-day POWER window appropriate for the season.

    Boro (Dec–Apr) and Rabi seasons use the prior year's winter window so the
    POWER API serves real historical data (it does not serve future dates).
    Aman (Jun–Oct) uses the prior monsoon.
    """
    from datetime import date

    # Anchor to a historical year that is guaranteed to have POWER data.
    anchor_year = 2025  # last fully-observed year

    if season in ("boro", "rabi", "autumn"):
        # Winter: Dec 1 of anchor_year → Jan 30 (60 days)
        start = date(anchor_year, 12, 1)
        end = date(anchor_year, 12, 31)
    elif season == "aman":
        # Monsoon: Jun 1 – Jul 30
        start = date(anchor_year, 6, 1)
        end = date(anchor_year, 7, 30)
    else:
        # Default: last 60 days of anchor_year
        start = date(anchor_year, 10, 1)
        end = date(anchor_year, 11, 30)

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _crop_traits(crop: Crop) -> CropTraits:
    price = crop.price_range_bdt_per_kg or [0, 0]
    cost = crop.cost_per_ha_bdt or [0, 0]
    yieldr = crop.yield_range_t or [0, 0]
    return CropTraits(
        slug=crop.slug,
        name=crop.name,
        family=crop.family,
        is_legume=crop.is_legume,
        water_demand_mm=crop.water_demand_mm,
        kc_canopy=crop.kc_canopy,
        heat_tolerance=crop.heat_tolerance,
        drought_tolerance=crop.drought_tolerance,
        price_low=price[0] if len(price) > 0 else 0,
        price_high=price[1] if len(price) > 1 else (price[0] if len(price) > 0 else 0),
        cost_low=cost[0] if len(cost) > 0 else 0,
        cost_high=cost[1] if len(cost) > 1 else (cost[0] if len(cost) > 0 else 0),
        yield_low_t=yieldr[0] if len(yieldr) > 0 else 0,
        yield_high_t=yieldr[1] if len(yieldr) > 1 else (yieldr[0] if len(yieldr) > 0 else 0),
        soil_ph_min=crop.soil_ph_min,
        soil_ph_max=crop.soil_ph_max,
        irrigation_max=crop.irrigation_max,
        equipment=crop.equipment or [],
        season_months=crop.season_months or [],
        is_paddy=(crop.slug in ("rice-boro", "rice-aman", "paddy")),
    )


def build_input_snapshot(run_obj) -> BuiltSnapshot:
    """Build the frozen EngineInput + provenance for a run."""
    field: Field = run_obj.field
    request = run_obj.request or {}

    season = request.get("season") or "boro"
    season_months = _season_window_months(season)
    weights = request.get("weights") or dict(rules.DEFAULT_WEIGHTS)
    exclusions = request.get("exclusions") or []

    # --- Soil test (latest) -----------------------------------------------
    soil = SoilTest.objects.filter(field=field).order_by("-tested_on").first()
    soil_ph = soil.ph if soil else None
    soil_test_id = f"st-{soil.pk}" if soil else ""

    # --- Baseline from crop history (NEVER invented) -----------------------
    history = (
        CropHistory.objects.filter(field=field).order_by("-year", "-season").select_related("crop")
    )
    last_season_rows = list(history[:2])
    baseline_seq: list[str] = []
    for row in last_season_rows:
        if row.crop.slug not in baseline_seq:
            baseline_seq.append(row.crop.slug)
    baseline_is_paddy = any(s in ("rice-boro", "rice-aman", "paddy") for s in baseline_seq)

    # --- POWER series (cached / stale) ------------------------------------
    lat = field.lat or 25.34
    lng = field.lng or 88.61
    start, end = _power_window_for_season(season)
    power_result = power_service.get_daily_series(lat, lng, start, end, field_model=field)
    power_days: list[PowerDay] = [
        PowerDay(
            date=r.get("date", ""),
            tmax=r.get("tmax"),
            tmin=r.get("tmin"),
            rh=r.get("rh"),
            ws=r.get("ws"),
            rs=r.get("rs"),
            prectot=r.get("prectot"),
        )
        for r in power_result.rows
    ]

    # --- HLS NDVI (committed) ---------------------------------------------
    hls_series = hls_service.load_ndvi_series(field_model=field)
    from datetime import date as _date
    in_window = [
        r for r in hls_series.rows
        if any(m in _month_map(r.date) for m in season_months)
    ]
    ndvi_row = max(in_window, key=lambda r: r.date) if in_window else (
        max(hls_series.rows, key=lambda r: r.date) if hls_series.rows else None
    )
    ndvi = ndvi_row.ndvi if ndvi_row else None
    ndvi_cov = ndvi_row.coverage_pct if ndvi_row else None

    # --- Catalogue ---------------------------------------------------------
    crops_qs = Crop.objects.all().select_related()
    crops: dict[str, CropTraits] = {}
    crop_families: dict[str, str] = {}
    crop_is_legume: dict[str, bool] = {}
    for c in crops_qs:
        traits = _crop_traits(c)
        crops[c.slug] = traits
        crop_families[c.slug] = c.family
        crop_is_legume[c.slug] = c.is_legume

    # --- Catalogue + rule version -----------------------------------------
    from apps.catalogue.models import CropRuleVersion
    active_rule = CropRuleVersion.objects.filter(is_active=True).order_by("-created_at").first()
    catalogue_version = active_rule.version if active_rule else "unversioned"

    inp = EngineInput(
        lat=lat,
        lng=lng,
        season=season,
        season_months=season_months,
        irrigation=field.irrigation or "canal",
        drainage=field.drainage or "moderate",
        soil_ph=soil_ph,
        equipment=set(request.get("equipment") or []),
        exclusions=exclusions,
        area_ha=float(field.area_ha) if field.area_ha else 1.0,
        weights=weights,
        power_days=power_days,
        ndvi=ndvi,
        ndvi_coverage_pct=ndvi_cov,
        crops=crops,
        crop_families=crop_families,
        crop_is_legume=crop_is_legume,
        baseline_seq=baseline_seq,
        baseline_is_paddy=baseline_is_paddy,
        soil_test_id=soil_test_id,
        catalogue_version=catalogue_version,
        rule_version=rules.RULE_VERSION,
    )

    return BuiltSnapshot(
        engine_input=inp,
        power_asset_id=power_result.asset_id or "",
        power_content_hash=power_result.content_hash or "",
        hls_asset_id=hls_series.asset_id or "",
        hls_content_hash="",  # HLS content hash stored on its DataAsset
    )


def _month_map(date_str: str) -> int:
    try:
        return int(date_str.split("-")[1])
    except (IndexError, ValueError):
        return 1
