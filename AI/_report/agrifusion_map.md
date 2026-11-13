# AgriFusionBD — where the NASA datasets plug in

Read-only survey of `C:\Users\muhai\Desktop\BIG hero 6\AgriFusionBD-main`, 2026-11-11.
Line references are to the repository at that date.

## 1. Settings and configuration (`backend/config/`)

- `backend/config/settings/` holds `base.py`, `dev.py`, `prod.py`, `engine_test.py`.
  `DJANGO_SETTINGS_MODULE` defaults to `config.settings.dev` (`manage.py:9`).
- Installed local apps (`settings/base.py:40-50`): `accounts`, `farms`, `catalogue`,
  `environment`, `analyses`, `cases`, `rovers`, `research`, `audit`. **No new app is
  needed** for additional data sources — `environment` already owns datasets.
- Env vars actually read: `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`,
  `POSTGRES_*`, `CELERY_*`, `CORS_ALLOWED_ORIGINS` (`settings/dev.py:12-49`).
- Declared in `.env.example` but **never read**: `POWER_BASE_URL`,
  `POWER_TIMEOUT_SECONDS`, `POWER_RETRIES`, `POWER_CACHE_TTL_SECONDS`,
  `HLS_VALID_COVERAGE_MIN`, `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`. The values are
  hard-coded at `settings/base.py:139-143`; `base.py` does not import `os`.
- No feature flags exist. `prod.py` reads no environment at all, so database settings
  still come from the literal dict at `base.py:92-101`.

## 2. Models that already store environmental data (`apps/environment/models.py`)

| Model | Fields that matter |
|---|---|
| `DatasetProduct` (:13-29) | `slug` (unique), `name`, `provider`, `product_id`, `resolution`, `cadence` |
| `DataAsset` (:32-67) | `product` FK, `field` FK, `cache_key` (unique), `content_hash`, `status` (fresh/cached/stale), `acquired_at`, `expires_at`, `payload` JSON, `metadata` JSON |
| `FieldIndicator` (:70-114) | `field`, `kind` (choices at :79-88), `provider`, `product`, `version`, `period_start`, `period_end`, `value`, `unit`, `coverage_pct`, `quality`, `is_forecast`, `is_inferred` |

`FieldIndicator.kind` choices today: `rainfall`, `temperature`, `temperature_max`,
`temperature_min`, `relative_humidity`, `wind_speed`, `shortwave_radiation`, `ndvi`.
That is the list to extend for soil moisture, land-surface temperature, water storage,
terrain and NDMI.

Other relevant fields: `farms.Field` has `lat`, `lng`, `soil_type`, `irrigation`,
`slope_pct`, `drainage`, `geometry`, `area_ha` (`farms/models.py:29-70`); `Field.slope_pct`
exists but **nothing consumes it**. `rovers.Observation.sensor="moisture"` already holds
point soil moisture (`rovers/models.py:87-103`).

## 3. The engine contract (`apps/analyses/engine/`)

Pure functions, no ORM. The input unit is `PowerDay`
(`engine/et0.py:19-28`): `date`, `tmax`, `tmin`, `rh`, `ws`, `rs`, `prectot`. Nothing
else is available to the engine today.

`EngineInput` (`engine/runner.py:33-63`) adds `lat`, `lng`, `season`, `season_months`,
`irrigation`, `drainage`, `soil_ph`, `equipment`, `area_ha`, `weights`, `power_days`,
`ndvi`, `ndvi_coverage_pct`, crop traits and histories.

| Module | Entry point | Consumes | Produces |
|---|---|---|---|
| `et0.py` | `compute_et0(day, elevation_m=40.0)` :65 | tmax,tmin,rh,rs,ws | mm/day |
| `water_balance.py` | `season_water_balance(...)` :55 | `prectot`, ET0, Kc, soil bucket | irrigation demand, dry-spell days, gaps |
| `heat.py` | `season_heat(days, heat_tolerance)` :28 | `tmax` in the final third | threshold days |
| `cover.py` | `season_canopy_cover(expected, ndvi, coverage)` :28 | NDVI + coverage | canopy fraction |
| `diversity.py` | `rotation_diversity(...)` :29 | crop slugs/families | diversity score |
| `economics.py` | `rotation_economics(crops)` :37 | yield/price bands | net margin |
| `candidates.py` | `enumerate_candidates(...)` :85 | crop traits, filters | feasible rotations |
| `score.py` | `weighted_score(...)` :51 | metric values + weights | normalised score |
| `runner.py` | `run(inp)` :119 | all of the above | plans, warnings, evidence |

Season windows (`engine_inputs.py:39-47`): boro `[12,1,2,3,4]`, aman `[6,7,8,9,10]`,
rabi `[11,12,1]`, autumn `[9,10,11]`, spring `[3,4,5]`.
`_power_window_for_season` (:50-76) anchors to 2025 and asks for 31 days for the winter
season despite a docstring saying 60.

## 4. Where each dataset fits

| Dataset | Engine hook today | Extend |
|---|---|---|
| Rainfall | `PowerDay.prectot` → `_effective_rain` (`water_balance.py:37-52, 82`) | add a GPM series as an alternative `prectot`, or an explicit `precip` argument |
| Soil moisture | bucket starts full (`water_balance.py:67`); rover observations unused | new `FieldIndicator.kind`, init the bucket from SMAP, gate `dry_spell_days` |
| Land-surface temperature | none; `heat.py` uses air `tmax` only | add `lst_c` to `PowerDay` (defaulted) and use it in `heat.py:42-47` |
| Terrain | `elevation_m` parameter exists but is never passed (`water_balance.py:75`) | pass SRTM elevation at that call; optionally use slope in bucket capacity |
| Water storage | none | new kind + series; init bucket / capacity from GRACE |
| NDVI / NDMI | `cover.py:28` consumes one NDVI value + coverage | add NDMI as a second indicator kind |

## 5. Ordered integration steps

1. **Choose the storage shape.** One `DatasetProduct` per upstream product; raw payload in
   `DataAsset`; per-date values in `FieldIndicator`. No new Django app.
2. **Extend kinds**: add `soil_moisture`, `land_surface_temperature`, `ndmi`,
   `water_storage`, `elevation`, `slope` to `FieldIndicator.KIND_CHOICES`
   (`environment/models.py:79-88`), then `makemigrations environment`.
3. **Write a service per source**, modelled on `environment/services/power.py:111-202`:
   `get_or_create` the product, build a content-hashed `DataAsset` with `expires_at`,
   parse to rows with `None` for gaps, then `_store_indicators`.
4. **Thread values into the engine.** Prefer defaulted fields on `PowerDay`
   (`et0.py:20-28`) so existing constructors keep working; populate them in
   `engine_inputs.py:138-149`.
5. **Consume them** at the call sites in §4.
6. **Version the rules** if a metric definition changes: bump `RULE_VERSION`
   (`engine/rules.py:9`) and keep `BOUNDS`/`DEFAULT_WEIGHTS` (:65-90) in sync with
   `analyses/serializers.py:12-17`.
7. **Provenance**: append to `evidence` in `runner.py:242-257`, or add fields to
   `InputSnapshot` (`analyses/models.py:141-158`) plus persistence in `tasks.py:61-71`.
8. **Offline demo**: add a fixture under `backend/fixtures/nasa/` and an ingest script
   under `scripts/`, following `scripts/ingest_hls.py:44-99`.

## 6. Hazards found while reading

- `_store_indicators` omits `period_end` (`power.py:265-277`) while
  `FieldIndicator.period_end` is non-null without a default (`environment/models.py:99`):
  a fresh live POWER fetch would fail on the first insert.
- HLS writes a `DataAsset` but **never writes `FieldIndicator` rows** (`hls.py:112-123`),
  so NDVI never reaches `/fields/{slug}/indicators`.
- `DataAsset.cache_key` is globally unique and excludes the field (`power.py:68-71`),
  while `DataAsset.field` records only the first caller — per-field provenance can point
  at another field's asset.
- `engine/et0.py` is labelled FAO-56 but is not: `_net_radiation` (:48-62) ignores
  humidity in the longwave term and computes `abs(tmean - 273.0) ** 4` instead of
  `(T + 273.16) ** 4`. The ET0 series in `Data/model_ready/` implements the full FAO-56
  equation and can replace it.
- The engine tests assert on qualification text (`tests/test_engine.py:121`), so rewording
  water-balance messages breaks tests.
- Metric keys are coupled in four places (`rules.py:65-90`, `analyses/models.py:120-126`,
  `analyses/serializers.py:12-17`, `runner.py:66-116`); a key missing from `BOUNDS`
  silently normalises to 0 (`score.py:38-40`).
- CI builds only the frontend; backend regressions are caught only by local pytest.
- Frontend/backend contract drift: the frontend expects
  `{fieldId,date,kind,metric,value,...}` and calls `/fields/{id}/soil-tests`, which has no
  backend route.
