# NASA data for the seven Bangladesh regions

Supplementary NASA datasets named in `NASA_Data_Sources_and_Django_API_Plan.docx`,
collected for the same seven representative points and the same period as the
existing POWER weather files in
`API_NASA_POWER/src/data_accusition/bangladesh_weather`.

Period: **2022-01-01 to today** (Asia/Dhaka), matching the POWER download.

| Region | Latitude | Longitude |
|---|---|---|
| North_Rangpur | 25.75 | 89.25 |
| Northwest_Rajshahi | 24.37 | 88.60 |
| Central_Dhaka | 23.81 | 90.41 |
| Northeast_Sylhet | 24.89 | 91.87 |
| Southwest_Khulna | 22.85 | 89.54 |
| South_Barishal | 22.70 | 90.35 |
| Southeast_Chattogram | 22.36 | 91.78 |

A coordinate selects a grid cell or pixel. None of these files are measurements
taken at the exact point, and none of them are regional averages. Each folder
carries a `*_provenance.csv` recording the source, product version, variables,
resolution and the limits that apply to that dataset.

## Folders

| Folder | Source | Product | Native support |
|---|---|---|---|
| `GPM_IMERG_Rainfall/` | GPM IMERG (GES DISC) | `GPM_3IMERGDF` v07 Final Run, `GPM_3IMERGDL` v07 Late Run | 0.1° (~11 km) daily |
| `SMAP_SoilMoisture/` | SMAP (NSIDC DAAC) | `SPL3SMP_E` v006 via Harmony subsetting | 9 km EASE-Grid 2.0, AM and PM |
| `ECOSTRESS_LST_ET/` | ECOSTRESS (LP DAAC) | `ECO_L2T_LSTE` v002 | 70 m, irregular overpasses |
| `SRTM_Elevation/` | SRTM (LP DAAC) | `SRTMGL1` v003 | 1 arc second (~30 m) |
| `GRACE_WaterStorage/` | GRACE/GRACE-FO (PO.DAAC) | JPL Mascon CRI RL06.3 v04 | 0.5° monthly |
| `HLS_Vegetation_Indices/` | HLS (LP DAAC) | `HLSL30` / `HLSS30` v2.0 | 30 m, sampled monthly |

## What is currently in the folders

| Dataset | Rows | Filled values | Coverage reached |
|---|---|---|---|
| GPM IMERG | 12,418 | 12,418 | 1,774 days, 2022-01-01 → 2026-11-09 |
| SMAP | 24,206 | 9,618 (40 %) | 1,725 days × AM/PM, 2022-01-01 → 2026-11-09 |
| ECOSTRESS | 2,819 | 933 (33 %) | 2022-01-01 → 2026-11-03 |
| GRACE | 399 | 399 | 57 months, 2022-01 → 2026-09 |
| SRTM | 7 summaries | 7 | static |
| HLS | 413 | 220 have NDVI | 59 months per region |

Empty cells are the source products' own quality masking (cloud, no retrieval,
RFI), not failed downloads. Each row keeps its quality flags so they can be
filtered downstream.

## What each file contains

### `GPM_IMERG_Rainfall/`

- `{Region}_GPM_IMERG_daily_20220101_to_YYYYMMDD.csv` — one row per day.
- `GPM_IMERG_all_regions_daily_*.csv` — all regions stacked.
- Columns: `date`, `region`, `latitude`, `longitude`, `precipitation_mm_day`,
  `run`, `product`, `version`, `grid_lat`, `grid_lon`, `source_file`.

`precipitation_mm_day` is the daily accumulated rate in mm/day. The `run`
column separates Final Run (research quality, ends before the present) from
Late Run (recent months, still subject to revision) — the two are never merged
silently. Days are read straight from each granule with OPeNDAP, so no global
grid files are stored.

### `SMAP_SoilMoisture/`

- `{Region}_SMAP_soil_moisture_daily_*.csv` — one row per region, day and pass.
- `SMAP_soil_moisture_all_regions_daily_*.csv`, `SMAP_provenance.csv`.
- `raw/` — the Harmony-subsetted NetCDF for each day (bbox around the regions),
  kept as received so values can be re-derived.
- Columns: `date`, `region`, `pass` (am/pm), `soil_moisture_m3_m3`,
  `soil_moisture_error_m3_m3`, `retrieval_qual_flag`, `surface_flag`,
  `freeze_thaw_fraction`, `grid_lat`, `grid_lon`, `source_file`.

Volumetric fraction: 0.30 means 30 %. Missing retrievals are empty, not zero.
AM and PM overpasses are separate retrievals.

### `ECOSTRESS_LST_ET/`

- `{Region}_ECOSTRESS_LST_*.csv` — one row per overpass that covers the region.
- Columns: `observed_utc`, `region`, `latitude`, `longitude`, `lst_kelvin`,
  `lst_celsius`, `qc`, `granule_id`, `tile_zone`.

LST is the median of the 3 × 3 pixels at 70 m around the coordinate. `qc` is
the raw QC band value; the low two bits are the LST accuracy flag, where 0 is
best. Surface temperature is not 2 m air temperature. Granules are streamed,
sampled and discarded — no imagery is stored. The docx lists evapotranspiration
as optional; this folder contains surface temperature only.

### `SRTM_Elevation/`

- `SRTM_terrain_summary_all_regions.csv` and one file per region.
- `tiles/` — the 30 one-degree `.hgt` tiles that intersect the region window
  (3601 × 3601 int16, big-endian, void = −32768).
- Columns: `elevation_mean_m`, `elevation_min_m`, `elevation_max_m`,
  `elevation_std_m`, `slope_mean_deg`, `slope_max_deg`, `valid_pixels`, plus the
  tile name and window size.

Statistics come from a 0.1° window (~11 km) around each point. SRTM is static,
so this is downloaded once and reused. Vertical accuracy is metres, not
centimetres — insufficient for drainage design on flat fields.

### `GRACE_WaterStorage/`

- `{Region}_GRACE_mascon_monthly_*.csv` — one row per month.
- `raw/` — the JPL mascon NetCDF file (whole time series in one file).
- Columns: `date`, `region`, `lwe_thickness_cm`, `uncertainty_cm`, `grid_lat`,
  `grid_lon`, `mascon_id`, `cri_scale_factor`.

Values are liquid-water-equivalent thickness **anomalies** in centimetres, not
absolute storage. The 0.5° grid (~55 km) is far coarser than a field: several
regions share the same mascon cell, so identical values across neighbouring
regions are expected, not a bug. GRACE is a large-area water-trend indicator —
not a groundwater measurement or well-depth estimate.

### `HLS_Vegetation_Indices/`

- `{Region}_HLS_indices_*.csv` — one row per region and month.
- Columns: `observed_utc`, `region`, `product`, `ndvi`, `ndmi`,
  `valid_coverage`, `valid_pixels`, `window_pixels`, `granule_id`.

NDVI = (NIR − Red) / (NIR + Red) and NDMI = (NIR − SWIR1) / (NIR + SWIR1),
computed on a 31 × 31 pixel window (about 0.9 km) around each coordinate after
excluding Fmask bits 0–5 and the high-aerosol class. Surface reflectance is
scaled by 0.0001 first. One scene per region per month is used, with up to
six candidate scenes per month so a cloudy first pick can be replaced.
Full 30 m scenes are **not** stored — only the sampled statistics.

## Scripts

Run with the project virtual environment:

```powershell
cd "C:\Users\muhai\Desktop\BIG hero 6\Data"
.\.venv\Scripts\python.exe download_gpm_imerg.py
.\.venv\Scripts\python.exe download_smap.py        # submits the Harmony jobs
.\.venv\Scripts\python.exe run_smap_jobs.py       # resumes/downloads them
.\.venv\Scripts\python.exe download_ecostress.py
.\.venv\Scripts\python.exe download_srtm.py
.\.venv\Scripts\python.exe download_grace.py
.\.venv\Scripts\python.exe download_hls.py
```

| File | Role |
|---|---|
| `nasa_common.py` | Regions, `.env` token loading, retry session, CSV helpers |
| `http_range.py` | Seekable HTTP-range file object (used while exploring SMAP granules) |
| `download_gpm_imerg.py` | IMERG daily precipitation via GES DISC OPeNDAP |
| `download_smap.py` | SMAP Harmony submission and CSV extraction |
| `run_smap_jobs.py` | Advances paused Harmony jobs and streams their subsets |
| `download_ecostress.py` | ECOSTRESS LST pixel sampling |
| `download_srtm.py` | SRTM tile download and terrain statistics |
| `download_grace.py` | GRACE mascon point extraction |
| `download_hls.py` | HLS NDVI/NDMI sampling |
| `retry_gpm_gaps.py` | Re-fetches IMERG days that failed on transient errors |
| `extract_docx.py` | Converts the plan `.docx` to text (stdlib only) |

All scripts are idempotent: existing tiles, NetCDF subsets and CSV outputs are
reused rather than re-downloaded, so a re-run only fills gaps.

## Credentials

The Earthdata Login bearer token is read from `Data\.env` (`api_token="..."`).
It is never written into the output files. Earthdata tokens expire; if a script
starts returning 401, replace the token in `.env`.
