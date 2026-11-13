# Feature screening: which candidate predictors actually carry signal

Generated 2026-11-11T22:49:28 from the 7-region Bangladesh panel (2022-2026). Machine-readable results: `feature_screening.json`. Pooled correlations are region-demeaned (anomalies); per-region correlations are plain within-region. Lags are measured back from the last known day/month t, with the target at t+1.

## Headline

| target | usable rows | AR(1) baseline R2 (pooled / within-region / anomaly) | ridge R2 (pooled / within-region / anomaly) | verdict |
|---|---|---|---|---|
| A. Next-month NDVI (monthly panel) | 139 | 0.52 / 0.29 / -0.12 | 0.58 / 0.52 / 0.12 | weak; monthly panel too thin and cloud-biased |
| B. Next-day surface soil moisture (daily, SMAP AM) | 4535 | 0.31 / 0.16 / -0.05 | 0.72 / 0.67 / 0.57 | real skill, but mostly amalgamated SMAP persistence |
| C1. Next-day rainfall occurrence (daily, >= 1 mm) | 12306 | 0.36 / 0.35 / -0.08 | 0.48 / 0.47 / 0.12 | modest genuine gain over persistence |
| C2. Next-day rainfall amount (daily, mm) | 12306 | 0.22 / 0.21 / 0.18 | 0.31 / 0.30 / 0.28 | weak; monotone but heavy tails mute Pearson |
| D. Next-month reference ET0 (monthly, Hargreaves) | 399 | 0.57 / 0.51 / -1.09 | 0.62 / 0.62 / -0.83 | seasonal cycle only; partly definitional |

Train 2022-2024, test 2025-2026. The anomaly R2 removes each region's calendar-month mean (estimated on train), so it asks whether the model beats climatology rather than whether it reproduces the annual cycle. An anomaly R2 at or below zero means the model has no skill beyond "it is that time of year". Feature rankings only consider (feature, lag) pairs observed on at least 5% of the usable rows (capped at 500 rows, floor 30), so a feature measured on 31 days cannot top a 4,500-day target; sparser sensors are listed separately for each target.

## A. Next-month NDVI (monthly panel)

**Target:** NDVI at month t+1 (HLS monthly mean) where months t and t+1 both have a valid clear-sky granule.

**Usable rows: 139** (93 train / 46 test), 2022-01-01 to 2026-09-01. Per region: Central_Dhaka 16, North_Rangpur 10, Northeast_Sylhet 24, Northwest_Rajshahi 16, South_Barishal 12, Southeast_Chattogram 34, Southwest_Khulna 27.

**Own-series lag profile (ndvi_m):** lag 0 r=0.44 (n=139), lag 1 r=0.26 (n=98), lag 2 r=-0.03 (n=88), lag 3 r=-0.05 (n=74).
On the identical common sample (n=48) the same lags give: lag 0 r=0.42, lag 1 r=0.03, lag 2 r=-0.11, lag 3 r=-0.16.

**Baseline vs ridge (2025-2026 hold-out)**

| model | pooled R2 | within-region R2 | anomaly R2 | MAE |
|---|---|---|---|---|
| AR(1) persistence | 0.519 | 0.286 | -0.117 | 0.072 |
| Ridge (top 8 features) | 0.576 | 0.522 | 0.117 | 0.068 |

Ridge features (selected on training rows only): precip_power_m__L0, ps_m__L0, rain_days_m__L0, smap_am_m__L1, t2m_range_m__L0, t2m_min_m__L0, t2m_min_m__L1, smap_am_m__L2; alpha=30.079.

**Top 10 features** (score = 0.4·|residual r| + 0.25·|deseasonalised r| + 0.2·|Pearson| + 0.15·MI; at most 2 lags per feature)

| # | feature | lag | Pearson | Pearson (deseasonalised) | Spearman | MI (nats) | MI per-region | residual r | n |
|---|---|---|---|---|---|---|---|---|---|
| 1 | precip_power_m | 0 | 0.633 | 0.292 | 0.446 | 0.122 | n/a | 0.440 | 139 |
| 2 | ps_m | 0 | -0.574 | -0.068 | -0.137 | 0.157 | n/a | -0.407 | 139 |
| 3 | rain_days_m | 0 | 0.611 | 0.190 | 0.425 | 0.061 | n/a | 0.385 | 139 |
| 4 | smap_am_m | 1 | 0.412 | 0.344 | 0.521 | 0.210 | n/a | 0.259 | 135 |
| 5 | t2m_range_m | 0 | -0.589 | -0.145 | -0.390 | 0.145 | n/a | -0.346 | 139 |
| 6 | t2m_min_m | 0 | 0.595 | -0.053 | 0.395 | 0.140 | n/a | 0.403 | 139 |
| 7 | t2m_min_m | 1 | 0.596 | -0.106 | 0.456 | 0.184 | n/a | 0.324 | 135 |
| 8 | smap_am_m | 2 | 0.383 | 0.349 | 0.533 | 0.291 | n/a | 0.189 | 130 |
| 9 | lst_m | 1 | 0.475 | -0.241 | 0.364 | 0.122 | n/a | 0.346 | 118 |
| 10 | ps_m | 1 | -0.632 | -0.044 | -0.227 | 0.140 | n/a | -0.361 | 135 |

Per-region Pearson for the top feature (precip_power_m, lag 0): Central_Dhaka 0.38, North_Rangpur 0.50, Northeast_Sylhet 0.78, Northwest_Rajshahi 0.33, South_Barishal 0.41, Southeast_Chattogram 0.75, Southwest_Khulna 0.64.

**What it means.** NDVI is only weakly predictable one month ahead. NDVI's own value correlates r=0.44 with next month's NDVI, r=0.26 at a two-month separation and r=-0.03 at three months, so the memory is short. The feature that ranks first is precip_power_m at lag 0 (r=0.63), a wet-season indicator whose correlation is the shared annual cycle rather than a mechanism. On the 46 held-out months the AR(1) baseline scores pooled R2 0.52 (within-region 0.29, anomaly -0.12) and the ridge model 0.58 (within-region 0.52, anomaly 0.12). The ridge model does beat the training climatology on anomalies (R2 0.12), which is the only positive sign here, but with 46 test months and 8 features that is a single draw. The panel itself is the main obstacle: 139 usable region-months, and the missing months are the monsoon ones, so the sample is conditioned on future cloud cover.

**Leakage and validity flags**

- Target availability is not random: a region-month enters the panel only if HLS returned a clear-sky granule (valid_coverage>0.1) in BOTH month t and month t+1. The monsoon months are precisely the ones missing, so the panel over-represents dry months and conditions the target on future cloud cover.
- ndvi_m at lag 0 is the AR(1) parent of the target: its correlation is persistence, not new information.
- Only 139 region-month pairs exist across 7 regions and 58 months (10-34 per region); per-region correlations rest on n=10-34 and are unstable.
- Derived from GPM IMERG final-run precipitation; same latency caveat.
- Monthly mean of ~10-15 SMAP AM retrievals; sparse, non-random sampling.
- ECOSTRESS monthly means rest on few granules with cloud gaps (clear-sky sampling).

## B. Next-day surface soil moisture (daily, SMAP AM)

**Target:** SMAP L3 AM soil_moisture_m3_m3 on day t+1; rows kept only where day t+1 is observed.

**Usable rows: 4535** (2771 train / 1764 test), 2022-01-01 to 2026-10-24. Per region: Central_Dhaka 600, North_Rangpur 610, Northeast_Sylhet 605, Northwest_Rajshahi 604, South_Barishal 607, Southeast_Chattogram 729, Southwest_Khulna 780.

**Own-series lag profile (smap_am):** lag 0 r=0.71 (n=1124), lag 1 r=0.65 (n=874), lag 2 r=0.75 (n=2085), lag 3 r=0.77 (n=1994), lag 7 r=0.83 (n=4320), lag 14 r=0.62 (n=1076), lag 30 r=0.51 (n=1050).
Common-sample check not possible: no row has all lags [0, 1, 2, 3, 7, 14, 30] observed simultaneously (irregular sampling); lag-to-lag comparisons use different subsets and their n is reported per lag

**Baseline vs ridge (2025-2026 hold-out)**

| model | pooled R2 | within-region R2 | anomaly R2 | MAE |
|---|---|---|---|---|
| AR(1) persistence | 0.315 | 0.157 | -0.054 | 0.086 |
| Ridge (top 8 features) | 0.722 | 0.674 | 0.573 | 0.052 |

Ridge features (selected on training rows only): smap_am__L7, smap_am_ffill3d__L7, smap_am__L2, smap_am_ffill3d__L14, smap_am__L3, smap_am_ffill3d__L2, smap_am_ffill3d__L3; alpha=6.700.

**Top 10 features** (score = 0.4·|residual r| + 0.25·|deseasonalised r| + 0.2·|Pearson| + 0.15·MI; at most 2 lags per feature)

| # | feature | lag | Pearson | Pearson (deseasonalised) | Spearman | MI (nats) | MI per-region | residual r | n |
|---|---|---|---|---|---|---|---|---|---|
| 1 | smap_am | 7 | 0.829 | 0.676 | 0.860 | 0.824 | 0.606 | 0.517 | 4320 |
| 2 | smap_am_ffill3d | 7 | 0.821 | 0.664 | 0.854 | 0.800 | 0.586 | 0.501 | 4475 |
| 3 | smap_am | 2 | 0.755 | 0.501 | 0.771 | 0.611 | 0.514 | 0.235 | 2085 |
| 4 | smap_am_ffill3d | 14 | 0.674 | 0.412 | 0.745 | 0.528 | 0.334 | 0.350 | 4412 |
| 5 | rain_30d | 0 | 0.467 | 0.176 | 0.373 | 0.176 | 0.254 | 0.187 | 4498 |
| 6 | grace_lwe | 1 | 0.415 | 0.037 | 0.500 | 0.452 | 0.354 | 0.173 | 4475 |
| 7 | grace_lwe | 0 | 0.416 | 0.029 | 0.500 | 0.464 | 0.350 | 0.172 | 4480 |
| 8 | rain_30d | 1 | 0.459 | 0.157 | 0.369 | 0.154 | 0.234 | 0.178 | 4498 |
| 9 | rain_days_7d | 0 | 0.439 | 0.181 | 0.382 | 0.110 | 0.171 | 0.191 | 4527 |
| 10 | rain_7d | 0 | 0.408 | 0.220 | 0.356 | 0.108 | 0.157 | 0.178 | 4527 |

**Below the coverage threshold** (excluded from the ranking because they are measured on too few rows, not because they are weak): ndmi lag 7 r=0.68 (residual r=0.53, n=31); ndvi lag 7 r=0.49 (residual r=0.29, n=31); ndvi lag 3 r=0.46 (residual r=0.18, n=72); ndvi lag 30 r=0.43 (residual r=0.14, n=42).

Per-region Pearson for the top feature (smap_am, lag 7): Central_Dhaka 0.82, North_Rangpur 0.85, Northeast_Sylhet 0.89, Northwest_Rajshahi 0.78, South_Barishal 0.79, Southeast_Chattogram 0.72, Southwest_Khulna 0.90.

**What it means.** This is the only target with substantial, usable signal. The top feature, smap_am at lag 7, reaches r=0.83 with tomorrow's SMAP value (residual r=0.52 after the AR(1) baseline). The ridge model lifts pooled R2 from 0.31 to 0.72 and within-region R2 from 0.16 to 0.67 on 1764 held-out days; on anomalies it keeps R2 0.57 where the baseline gets -0.05. The catch is sampling, not physics: SMAP sees each region on roughly a 3-day cycle, so the number of usable pairs changes with lag (n=874 at lag 1 against n=4320 at lag 7) and long-lag pairs are the same ground track. The pooled r=0.83 at lag 7 is therefore not comparable to the lag-0 value; the per-region correlations for this feature run 0.72 to 0.90. Vegetation indices do show up (ndmi at lag 7, r=0.68, residual r=0.53), but on only 31 of 4535 rows they fail the coverage rule and cannot carry a forecast. The gain over persistence comes from combining several stale SMAP looks, not from an independent sensor.

**Leakage and validity flags**

- Rows exist only where a SMAP AM retrieval succeeds on day t+1; days with missing retrieval are dropped, so evaluation excludes exactly the conditions (RFI, dense vegetation, frozen ground) where a model would operate blind.
- SMAP revisits Bangladesh roughly every 3 days, so the number of usable pairs differs strongly by lag (e.g. lag 1: 874 rows, lag 7: 4,320 rows). The lag profile therefore mixes sampling geometry with physics and must not be read as a decay curve.
- smap_am_ffill3d / smap_am at lag 0 are the persistence parent: legitimate at forecast time but not independent information.
- soil_moisture_error_m3_m3 is -999 throughout the file (unusable) and was not used.
- SMAP AM retrieval exists on only ~38% of days (roughly a 3-day revisit); conditioning on an observed target day selects overpass/quality conditions and is not a random sample.
- Last SMAP AM value carried forward up to 3 days - stale by 1-3 days.

## C1. Next-day rainfall occurrence (daily, >= 1 mm)

**Target:** 1 if GPM IMERG precipitation on day t+1 >= 1.0 mm/day, else 0.

**Usable rows: 12306** (7672 train / 4634 test), 2022-01-01 to 2026-10-24. Per region: Central_Dhaka 1758, North_Rangpur 1758, Northeast_Sylhet 1758, Northwest_Rajshahi 1758, South_Barishal 1758, Southeast_Chattogram 1758, Southwest_Khulna 1758.

**Own-series lag profile (gpm_occ):** lag 0 r=0.58 (n=12306), lag 1 r=0.51 (n=12299), lag 2 r=0.47 (n=12292), lag 3 r=0.46 (n=12285), lag 7 r=0.43 (n=12257), lag 14 r=0.39 (n=12208), lag 30 r=0.35 (n=12096).
On the identical common sample (n=12096) the same lags give: lag 0 r=0.58, lag 1 r=0.51, lag 2 r=0.47, lag 3 r=0.46, lag 7 r=0.43, lag 14 r=0.39, lag 30 r=0.35.

**Baseline vs ridge (2025-2026 hold-out)**

| model | pooled R2 | within-region R2 | anomaly R2 | MAE |
|---|---|---|---|---|
| AR(1) persistence | 0.358 | 0.355 | -0.078 | 0.315 |
| Ridge (top 8 features) | 0.477 | 0.475 | 0.122 | 0.270 |

Occurrence metrics (test positive rate 0.422): persistence AUC 0.800 and accuracy 0.805; logistic model AUC 0.899 and accuracy 0.816.

Ridge features (selected on training rows only): doy_cos__L0, t2m_range__L0, rain_days_7d__L0, rain_days_7d__L1, t2m_min__L0, t2m_min__L1, rain_days_7d__L2, t2m_min__L2; alpha=2.462.

**Top 10 features** (score = 0.4·|residual r| + 0.25·|deseasonalised r| + 0.2·|Pearson| + 0.15·MI; at most 2 lags per feature)

| # | feature | lag | Pearson | Pearson (deseasonalised) | Spearman | MI (nats) | MI per-region | residual r | n |
|---|---|---|---|---|---|---|---|---|---|
| 1 | doy_cos | 0 | -0.584 | -0.175 | -0.573 | 0.265 | 0.244 | -0.298 | 12306 |
| 2 | t2m_range | 0 | -0.577 | -0.245 | -0.588 | 0.211 | 0.217 | -0.270 | 12292 |
| 3 | rain_days_7d | 0 | 0.623 | 0.209 | 0.629 | 0.229 | 0.222 | 0.234 | 12285 |
| 4 | rain_days_7d | 1 | 0.595 | 0.141 | 0.601 | 0.211 | 0.196 | 0.275 | 12278 |
| 5 | t2m_min | 0 | 0.552 | 0.157 | 0.562 | 0.200 | 0.215 | 0.289 | 12292 |
| 6 | t2m_min | 1 | 0.549 | 0.145 | 0.561 | 0.198 | 0.214 | 0.281 | 12292 |
| 7 | t2m_range | 1 | -0.546 | -0.166 | -0.555 | 0.189 | 0.191 | -0.260 | 12292 |
| 8 | rain_30d | 0 | 0.533 | 0.102 | 0.587 | 0.235 | 0.225 | 0.241 | 12208 |
| 9 | rain_30d | 1 | 0.523 | 0.082 | 0.576 | 0.215 | 0.219 | 0.243 | 12201 |
| 10 | ps | 7 | -0.561 | -0.095 | -0.509 | 0.156 | 0.204 | -0.288 | 12257 |

**Below the coverage threshold** (excluded from the ranking because they are measured on too few rows, not because they are weak): ndvi lag 1 r=0.36 (residual r=0.24, n=218); ndvi lag 3 r=0.32 (residual r=0.17, n=218); ndvi lag 2 r=0.31 (residual r=0.12, n=218); ndvi lag 7 r=0.28 (residual r=0.15, n=216).

Per-region Pearson for the top feature (doy_cos, lag 0): Central_Dhaka -0.57, North_Rangpur -0.55, Northeast_Sylhet -0.68, Northwest_Rajshahi -0.45, South_Barishal -0.61, Southeast_Chattogram -0.67, Southwest_Khulna -0.55.

**What it means.** Rain occurrence is strongly autocorrelated. The seasonal calendar term doy_cos ranks first (r=-0.58), and the measured variable with the largest raw correlation is rain_days_7d at lag 0 (r=0.62, residual r=0.23), i.e. a substantial part of the raw correlation survives the AR(1) baseline. The AR(1) baseline alone reaches pooled R2 0.36 and AUC 0.800; the ridge model reaches R2 0.48 and the logistic model AUC 0.899 on 4634 held-out days. On anomalies the baseline falls to R2 -0.08 while the model holds 0.12, so the gain is real but modest. Practically: rain persistence (7- and 30-day rain-day counts), the seasonal calendar and temperature carry almost all of it; soil moisture and vegetation add little beyond that.

**Leakage and validity flags**

- GPM IMERG daily totals are accumulated on UTC days: UTC day t covers local 06:00 t to 06:00 t+1, so the day-t predictor window overlaps the first 6 hours of target day t+1.
- 'final' vs 'late' run: 9,583 of 12,418 region-days are final-run (retrospective only).
- Occurrence is binary with a 39% positive rate; Pearson on a binary target is a point-biserial r.
- Trailing 7-day rain-day count ending day t; inherits final-run latency.
- Trailing 30-day GPM sum ending day t (known at t) but inherits final-run latency.

## C2. Next-day rainfall amount (daily, mm)

**Target:** GPM IMERG precipitation (mm/day) on day t+1.

**Usable rows: 12306** (7672 train / 4634 test), 2022-01-01 to 2026-10-24. Per region: Central_Dhaka 1758, North_Rangpur 1758, Northeast_Sylhet 1758, Northwest_Rajshahi 1758, South_Barishal 1758, Southeast_Chattogram 1758, Southwest_Khulna 1758.

**Own-series lag profile (gpm_precip):** lag 0 r=0.45 (n=12306), lag 1 r=0.30 (n=12299), lag 2 r=0.23 (n=12292), lag 3 r=0.20 (n=12285), lag 7 r=0.14 (n=12257), lag 14 r=0.16 (n=12208), lag 30 r=0.13 (n=12096).
On the identical common sample (n=12096) the same lags give: lag 0 r=0.45, lag 1 r=0.30, lag 2 r=0.23, lag 3 r=0.19, lag 7 r=0.14, lag 14 r=0.16, lag 30 r=0.13.

**Baseline vs ridge (2025-2026 hold-out)**

| model | pooled R2 | within-region R2 | anomaly R2 | MAE |
|---|---|---|---|---|
| AR(1) persistence | 0.220 | 0.212 | 0.184 | 6.527 |
| Ridge (top 8 features) | 0.310 | 0.304 | 0.278 | 5.961 |

Ridge features (selected on training rows only): precip_power__L0, doy_cos__L0, rain_days_7d__L0, rain_3d__L0, gpm_precip__L0, t2m_range__L0, rain_30d__L0, rain_7d__L0; alpha=222.754.

**Top 10 features** (score = 0.4·|residual r| + 0.25·|deseasonalised r| + 0.2·|Pearson| + 0.15·MI; at most 2 lags per feature)

| # | feature | lag | Pearson | Pearson (deseasonalised) | Spearman | MI (nats) | MI per-region | residual r | n |
|---|---|---|---|---|---|---|---|---|---|
| 1 | precip_power | 0 | 0.512 | 0.403 | 0.704 | 0.297 | 0.265 | 0.206 | 12292 |
| 2 | doy_cos | 0 | -0.344 | -0.097 | -0.633 | 0.309 | 0.291 | -0.215 | 12306 |
| 3 | rain_days_7d | 0 | 0.368 | 0.124 | 0.685 | 0.288 | 0.277 | 0.202 | 12285 |
| 4 | rain_3d | 0 | 0.423 | 0.281 | 0.688 | 0.280 | 0.262 | 0.082 | 12299 |
| 5 | gpm_precip | 0 | 0.454 | 0.353 | 0.703 | 0.297 | 0.253 | 0.000 | 12306 |
| 6 | t2m_range | 0 | -0.349 | -0.172 | -0.644 | 0.263 | 0.284 | -0.206 | 12292 |
| 7 | rain_30d | 0 | 0.359 | 0.099 | 0.645 | 0.293 | 0.277 | 0.180 | 12208 |
| 8 | rain_7d | 0 | 0.374 | 0.176 | 0.659 | 0.284 | 0.276 | 0.120 | 12285 |
| 9 | gpm_occ | 0 | 0.368 | 0.190 | 0.637 | 0.223 | 0.222 | 0.166 | 12306 |
| 10 | rain_days_7d | 1 | 0.343 | 0.075 | 0.654 | 0.265 | 0.247 | 0.199 | 12278 |

**Below the coverage threshold** (excluded from the ranking because they are measured on too few rows, not because they are weak): ndvi lag 1 r=0.25 (residual r=0.17, n=218); ndvi lag 7 r=0.20 (residual r=0.15, n=216); ndmi lag 1 r=0.16 (residual r=0.10, n=218); ndmi lag 14 r=0.16 (residual r=0.11, n=215).

Per-region Pearson for the top feature (precip_power, lag 0): Central_Dhaka 0.37, North_Rangpur 0.52, Northeast_Sylhet 0.53, Northwest_Rajshahi 0.42, South_Barishal 0.54, Southeast_Chattogram 0.61, Southwest_Khulna 0.44.

**What it means.** Amount is much harder than occurrence. The best predictor is precip_power at lag 0 (r=0.51) but its residual correlation after the AR(1) baseline is only 0.21, and the largest surviving residual among rankable features is 0.22 (lst_c at lag 2). The ridge model moves pooled R2 from 0.22 to 0.31 (within-region 0.21 to 0.30) on 4634 held-out days. For this target Spearman is consistently higher than Pearson (precip_power 0.51 against 0.70), so the monotone association is stronger than the linear one and a few extreme days pull the Pearson columns down. With 48.6% exact zeros the kNN MI estimates are fragile; the mi_binned column is the one to trust.

**Leakage and validity flags**

- GPM IMERG daily totals are accumulated on UTC days: UTC day t covers local 06:00 t to 06:00 t+1, so the day-t predictor window overlaps the first 6 hours of target day t+1.
- Amount is highly skewed (48.6% exact zeros, mean 6.2, max 195 mm/day): Pearson is dominated by extremes, Spearman is the more robust summary, and zero-inflation stresses MI estimators (mi_binned is included as an independent check).
- 'final' vs 'late' run: 9,583 of 12,418 region-days are final-run (retrospective only).
- Trailing 7-day rain-day count ending day t; inherits final-run latency.
- Trailing 3-day GPM sum ending day t (known at t) but inherits final-run latency.
- GPM IMERG 'final' run has ~3.5-month latency; only 'late' (~12 h) / 'early' (~4 h) runs exist in real time, so final-run values are retrospective.
- Trailing 30-day GPM sum ending day t (known at t) but inherits final-run latency.
- Trailing 7-day GPM sum ending day t (known at t) but inherits final-run latency.
- Derived from GPM IMERG final-run precipitation; same latency caveat.

## D. Next-month reference ET0 (monthly, Hargreaves)

**Target:** Hargreaves ET0 (mm/day, monthly mean) at month t+1.

**Usable rows: 399** (252 train / 147 test), 2022-01-01 to 2026-09-01. Per region: Central_Dhaka 57, North_Rangpur 57, Northeast_Sylhet 57, Northwest_Rajshahi 57, South_Barishal 57, Southeast_Chattogram 57, Southwest_Khulna 57.

**Own-series lag profile (et0_m):** lag 0 r=0.73 (n=399), lag 1 r=0.23 (n=392), lag 2 r=-0.18 (n=385), lag 3 r=-0.44 (n=378).
On the identical common sample (n=378) the same lags give: lag 0 r=0.75, lag 1 r=0.30, lag 2 r=-0.14, lag 3 r=-0.44.

**Baseline vs ridge (2025-2026 hold-out)**

| model | pooled R2 | within-region R2 | anomaly R2 | MAE |
|---|---|---|---|---|
| AR(1) persistence | 0.570 | 0.512 | -1.090 | 0.414 |
| Ridge (top 8 features) | 0.623 | 0.620 | -0.831 | 0.411 |

Ridge features (selected on training rows only): rh2m_m__L0, t2m_min_m__L2, t2m_m__L2, month_sin__L0, t2m_range_m__L0, t2m_min_m__L1, t2m_m__L1, t2m_max_m__L2; alpha=1.492.

**Top 10 features** (score = 0.4·|residual r| + 0.25·|deseasonalised r| + 0.2·|Pearson| + 0.15·MI; at most 2 lags per feature)

| # | feature | lag | Pearson | Pearson (deseasonalised) | Spearman | MI (nats) | MI per-region | residual r | n |
|---|---|---|---|---|---|---|---|---|---|
| 1 | rh2m_m | 0 | -0.748 | -0.311 | -0.580 | 0.634 | 0.758 | -0.542 | 399 |
| 2 | t2m_min_m | 2 | -0.837 | -0.065 | -0.766 | 0.591 | 0.763 | -0.665 | 385 |
| 3 | t2m_m | 2 | -0.773 | -0.061 | -0.580 | 0.473 | 0.676 | -0.709 | 385 |
| 4 | month_sin | 0 | 0.756 | 0.000 | 0.763 | 0.875 | 1.169 | 0.578 | 399 |
| 5 | t2m_range_m | 0 | 0.542 | 0.375 | 0.476 | 0.552 | 0.588 | 0.576 | 399 |
| 6 | t2m_min_m | 1 | -0.555 | -0.118 | -0.492 | 0.425 | 0.641 | -0.767 | 392 |
| 7 | t2m_m | 1 | -0.430 | -0.105 | -0.276 | 0.392 | 0.600 | -0.781 | 392 |
| 8 | t2m_max_m | 2 | -0.574 | -0.069 | -0.355 | 0.468 | 0.641 | -0.686 | 385 |
| 9 | ps_m | 2 | 0.721 | 0.120 | 0.564 | 0.361 | 0.683 | 0.621 | 385 |
| 10 | ps_m | 3 | 0.829 | 0.150 | 0.683 | 0.399 | 0.692 | 0.436 | 378 |

Per-region Pearson for the top feature (rh2m_m, lag 0): Central_Dhaka -0.77, North_Rangpur -0.75, Northeast_Sylhet -0.23, Northwest_Rajshahi -0.83, South_Barishal -0.80, Southeast_Chattogram -0.70, Southwest_Khulna -0.82.

**What it means.** ET0 is essentially the seasonal cycle plus its own definition. The top features - rh2m_m at lag 0 (r=-0.75) among them - are either phase-shifted views of the annual cycle or, in the case of temperature, the very inputs the Hargreaves formula consumes. The ridge model lifts pooled R2 from 0.57 to 0.62 (within-region 0.51 to 0.62), but on anomalies the baseline scores -1.09 and the model -0.83: neither beats the training climatology. Correlations that peak away from lag 0 (Tmin peaks at lag 2 with r=-0.84) are a phase artefact - Tmin peaks in the monsoon while ET0 peaks in March-April - not evidence that temperature two months back causes ET0 next month.

**Leakage and validity flags**

- ET0 is a deterministic function of T2M, T2M_MAX, T2M_MIN, latitude and day-of-year (Hargreaves). Any same-month temperature feature is definitional rather than predictive; with a next-month target the temperature signal is essentially persistence of the seasonal cycle.
- et0_m at lag 0 is the same formula applied one month earlier - perfectly collinear with its temperature inputs, so it adds no independent information.
- NASA POWER files contain no ET0 variable: this is our own Hargreaves proxy, not an observation, and its skill cannot be validated against a reference ET product here.
- The best lags (2-3 months) are a phase artefact of the seasonal cycle: Tmin peaks in the monsoon while ET0 peaks in March-April, so a 2-month offset maximises the sinusoid cross-correlation.

## Data coverage and cadence rules

- POWER weather: 12313 rows = 1759 days x 7 regions, 2022-01-01 to 2026-10-25. The files contain no ET0 variable.
- Daily panel: 12313 region-days. Monthly panel: 406 region-months (2022-01 to 2026-10).
- GPM IMERG: 12418 region-days; run counts {'final': 9583, 'late': 2835}; final-run share by year {'2022': 1.0, '2023': 1.0, '2024': 1.0, '2025': 0.747945, '2026': 0.0}; 39% of days reach 1 mm.
- SMAP AM: 4652 observed region-days (38% of region-days); per region {'Central_Dhaka': 618, 'North_Rangpur': 630, 'Northeast_Sylhet': 621, 'Northwest_Rajshahi': 624, 'South_Barishal': 622, 'Southeast_Chattogram': 746, 'Southwest_Khulna': 791}; gaps between retrievals (days) {'1': 1124, '2': 874, '3': 1667, '4': 870, '5': 58, '6': 17, '7': 24, '8': 4} - a ~3-day revisit, not a daily product.
- ECOSTRESS LST: 933 non-null LST values in the file, 915 of them land on a region-day in the POWER grid; per region {'Central_Dhaka': 140, 'North_Rangpur': 131, 'Northeast_Sylhet': 125, 'Northwest_Rajshahi': 137, 'South_Barishal': 122, 'Southeast_Chattogram': 138, 'Southwest_Khulna': 122}. Only 0.1% of the valid values carry qc==0 (the QC field is a bit field and was not decoded), so no quality filter is applied - this is the weakest-quality input in the screen.
- HLS: 220 valid NDVI granules; 218 of 406 region-months have NDVI; per region {'Central_Dhaka': 30, 'North_Rangpur': 23, 'Northeast_Sylhet': 36, 'Northwest_Rajshahi': 29, 'South_Barishal': 20, 'Southeast_Chattogram': 43, 'Southwest_Khulna': 37}.
- NDVI availability by calendar month (share of region-months with a granule): {'1': 0.514, '2': 0.657, '3': 0.743, '4': 0.543, '5': 0.571, '6': 0.2, '7': 0.457, '8': 0.257, '9': 0.514, '10': 0.571, '11': 0.893, '12': 0.607}. The monsoon months are exactly the missing ones.
- GRACE: {'Central_Dhaka': 57, 'North_Rangpur': 57, 'Northeast_Sylhet': 57, 'Northwest_Rajshahi': 57, 'South_Barishal': 57, 'Southeast_Chattogram': 57, 'Southwest_Khulna': 57} monthly values per region.
- SRTM: elevation and slope are constant within a region, so they cannot correlate with anything within a region and were not used as predictors.

**ET0 formula (Hargreaves, FAO-56 Eq. 52):** ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * Ra ; Ra in mm/day (Ra_MJ * 0.408); Ra_MJ = (24*60/pi)*0.0820*dr*(ws*sin(phi)*sin(delta) + cos(phi)*cos(delta)*sin(ws)); dr = 1+0.033cos(2*pi*J/365); delta = 0.409sin(2*pi*J/365 - 1.39); ws = arccos(-tan(phi)tan(delta)).

Domain mean 3.86 mm/day, range 1.55 to 8.82; monthly means {'1': 2.849673, '2': 3.780215, '3': 4.874748, '4': 5.553479, '5': 4.82474, '6': 4.100233, '7': 3.926075, '8': 3.686064, '9': 3.399543, '10': 3.298329, '11': 2.995565, '12': 2.652143}; per-region means {'Central_Dhaka': 3.959805, 'North_Rangpur': 3.930118, 'Northeast_Sylhet': 3.679309, 'Northwest_Rajshahi': 4.291941, 'South_Barishal': 3.433899, 'Southeast_Chattogram': 3.525949, 'Southwest_Khulna': 4.214858}.

**Join and aggregation rule.** Daily variables are joined on the exact region-day with no interpolation, and missing values are dropped pairwise per (feature, lag) with n reported for every correlation. ECOSTRESS and HLS UTC timestamps are shifted to the UTC+6 local day. Monthly variables are calendar-month means of the daily values, with sums for monthly rainfall totals, counts for rain days, and valid granules only for NDVI/NDMI/LST. GRACE monthly values are attached to every day of their month. Three staleness-capped carry-forward series are screened explicitly alongside the raw ones: SMAP AM up to 3 days, ECOSTRESS LST up to 5 days, HLS NDVI up to 16 days.

## Method notes

- Daily targets: lags 0,1,2,3,7,14,30 days. Monthly targets: lags 0,1,2,3 months (6 and 12 leave too few rows). Lag 0 is the most recent observation before the target period. Lag columns are built on the full grid, so lag L is exactly L days/months even across sensor gaps.
- Calendar features (day-of-year and month sin/cos) are screened at lag 0 only: they are deterministic and lag-invariant, so lagging them adds no information.
- Pearson and Spearman per region and pooled, plus a deseasonalised pooled Pearson (region x calendar-month means removed). Pooled values exceed per-region values almost everywhere because the monsoon cycle moves all seven regions together.
- MI: sklearn `mutual_info_regression` (n_neighbors=3) on raw values with discrete-feature flags; a quantile-binned plug-in MI with Miller-Madow correction (`mi_binned`) is the robustness check. Demeaning a binary target before MI destroys its entropy bound and made the kNN estimator return 2.14 nats against a target entropy of 0.67, which is why raw values are used and a per-region mean MI (n>=200) is reported too.
- Residual r: correlation of the predictor with the residual of a within-region AR(1) fit of the target. It is descriptive and in-sample; it says how much of a predictor's correlation is not just the target's own persistence. A residual r of exactly 0 marks the AR(1) parent feature itself (for example gpm_precip at lag 0 against next-day rainfall amount): it is orthogonal to its own regression residual by construction. Calendar terms likewise score 0 on the deseasonalised correlation, because that adjustment removes calendar-month means.
- Model selection and evaluation: top 8 features chosen on training rows only, ridge with median imputation, time-based split (train <= 2024, test 2025-2026).
- No multiplicity control: roughly 20-30 features x up to 7 lags are screened per target, so at the monthly sample size (139 rows) a single |r| below about 0.17 is indistinguishable from noise, and far larger values are needed after any correction.

