# Model-ready feature tables

Built by `../build_model_ready.py` from the six NASA datasets plus POWER weather.
Regenerated in one command; nothing here is hand-edited.

```powershell
cd "C:\Users\muhai\Desktop\BIG hero 6\Data"
.\.venv\Scripts\python.exe build_model_ready.py
.\.venv\Scripts\python.exe train_baseline.py
```

## Files

| File | What it is |
|---|---|
| `daily_panel.csv` | 12,313 rows — 7 regions × 1,759 days (2022-01-01 → 2026-10-25). Features known at end of day *t*, targets for day *t+1*. |
| `monthly_panel.csv` | 406 rows — 7 regions × 58 months. Monthly aggregates and next-month targets. |
| `feature_dictionary.csv` | One row per column: source, unit, meaning, leakage note, completeness. |
| `split_manifest.json` | Time-based train/valid/test boundaries. |
| `data_quality_report.csv` | Non-null counts per column per table. |
| `baseline_results.json` | Scores of the reference models in `train_baseline.py`. |

## Rules the tables follow

1. **No future information.** Every feature is computed from data up to and including
   the row's date. Targets are explicit forward shifts (`target_*`, `*_next_month`) and
   are never filled.
2. **Missing stays missing.** No zero-filling, no unconditional interpolation. Where a
   sparse satellite variable is carried forward there is always a matching
   `*_age_days` column and a `*_observed_today` flag, so a model can tell a fresh
   observation from a two-week-old one.
3. **Carry-forward caps.** HLS 45 days, ECOSTRESS 10 days, GRACE 60 days. Beyond the
   cap the value is set to null rather than silently reused.
4. **Time-based splits.** `train` 2022–2024, `valid` 2025, `test` 2026. Series are
   heavily autocorrelated, so a random split leaks the future into training.

## Column families

| Family | Examples | Notes |
|---|---|---|
| Weather | `t2m_c`, `tmax_c`, `power_rain_mm`, `rh_pct`, `solar_mj_m2` | POWER, ~99.8% complete |
| Derived meteorology | `et0_best_mm`, `vpd_kpa`, `gdd_base10`, `heat_day_35` | FAO-56 Penman-Monteith with a Hargreaves fallback |
| Rainfall windows | `power_rain_sum_7d` … `_90d`, `gpm_rain_sum_30d`, `dry_spell_days` | windows end on the row date |
| Soil moisture | `sm_mean`, `sm_7d_mean`, `sm_anomaly_30d`, `sm_obs_age_days` | SMAP, 65% of days have a value |
| Vegetation | `ndvi_last`, `ndmi_last`, `hls_age_days` | HLS is roughly monthly |
| Surface temperature | `lst_c_last`, `ecostress_age_days` | clear-sky overpasses only |
| Water storage | `grace_lwe_cm_last`, `grace_age_days` | 4 mascon cells across the 7 regions |
| Terrain | `elevation_mean_m`, `slope_mean_deg` | static |
| Calendar | `doy_sin`, `doy_cos`, `month`, `is_monsoon`, `season` | boro / aman / rabi_aus |

## Targets

| Target | Column | Rows with a value |
|---|---|---|
| Next-day rainfall | `target_rain_next_day_mm` | 12,306 |
| Next-day soil moisture | `target_sm_next_day` | 8,025 |
| Next-day ET0 | `target_et0_next_day_mm` | 12,285 |
| Next-day heat day | `target_heat_next_day` | 12,285 |
| Next-month NDVI | `ndvi_next_month` (monthly table) | 214 |

## Two data defects found while building this

1. **POWER precipitation was 24× too large** in the original downloads. Verified
   against the live POWER API on 40 samples across every region and season: the ratio
   was exactly 24.00 each time, while all seven other parameters matched exactly.
   `../fix_power_precip.py` writes corrected copies to `../power_corrected/`; the
   original files are untouched and `build_model_ready.py` prefers the corrected ones.
2. **ECOSTRESS and HLS are sparse by nature** (cloud), not by download failure. Use
   the `*_age_days` columns to filter rather than assuming a daily series.

## Getting consistent results

- Always split by time, never randomly.
- Drop or mask rows with `sm_obs_age_days > 5` when predicting soil moisture.
- For rainfall targets, report a climatology baseline as well as persistence — most
  days are dry, so accuracy is a misleading headline metric; use MAE and event skill.
