# Exploratory Data Analysis - NASA environmental CSVs, 7 Bangladesh regions (2022-01-01 .. 2026-11)

Read-only analysis. Nothing in the source CSVs was modified; every number below was computed by the
three scripts in `Data\_report\eda\` (`eda_part1.py`, `eda_part2.py`, `eda_part3.py`) and the summary
tables they emit are saved alongside them. This document was assembled by `build_eda_md.py` directly
from those tables, so the figures are not transcribed by hand.

**Analysis window used throughout:** 2022-01-01 .. 2026-11-09 = **1,774 days x 7 regions = 12,418
region-days**. This is the GPM window (the widest daily series). Datasets narrower than this are
marked as such.

**Regions (7):** Central_Dhaka, North_Rangpur, Northeast_Sylhet, Northwest_Rajshahi, South_Barishal,
Southeast_Chattogram, Southwest_Khulna. Each region is a single 0.1 deg grid cell / mascon, so there
is no within-region spatial replication anywhere in this data.

## 0. Headline findings

1. **Only two series are daily-complete: GPM IMERG and POWER.** GPM has exactly 12,418/12,418 valid
   region-days; POWER 12,292/12,418 (98.99%). Everything else is an irregular observation stream.
2. **POWER `PRECTOTCORR` is stored 24x too large.** Every value in all 7 files is an exact multiple of
   0.24 (fraction = 1.000, max residual 3.6e-12) - the column is the sum of 24 hourly values that were
   each already expressed in mm/day. Raw annual totals reach 32,000-132,000 mm/yr (impossible); after
   `PRECTOTCORR/24` they are 1,320-5,503 mm/yr, which is climatologically correct for Bangladesh.
   **Divide by 24 before use.** The unit file in the same directory says `mm/day` and is wrong for the
   file as delivered.
3. **SMAP is 39.6% usable at pass level and its gaps are structural, not random**: of 1,774 days per
   region only 49 have no granule row at all; 928-1,099 days are masked by `surface_flag == 2047`
   (no retrieval / not mapped); 0 by `retrieval_qual_flag == 7` after that mask. Missingness is
   therefore spatially coherent and correlated with land surface, which is the worst kind for imputation.
4. **ECOSTRESS LST is a mixed day/night sample.** Overpass local time spans all 24 hours; only 230 of
   933 valid LST values are daytime (local 09-16) and daytime LST averages **31.25 C vs 23.52 C at
   night**. Any LST series built without filtering on hour is two populations glued together.
5. **HLS NDVI is not a monthly series.** 59 acquisition attempts per region over 59 months, of which
   193/413 rows have zero valid pixels; only 220 NDVI values exist in total, 42 of them (19%) computed
   from <=5 valid pixels out of 225 and 71 (32%) from <10% coverage.
6. **GRACE contains only 4 independent spatial series, not 7.** Central_Dhaka, Northeast_Sylhet,
   South_Barishal and Southwest_Khulna are all mapped to mascon 1321 and their `lwe_thickness_cm` and
   `uncertainty_cm` columns are byte-identical. The per-region `cri_scale_factor` differs but has
   **not** been applied to the LWE values.
7. **The GPM dry season (Nov-Feb) is essentially zero** - 0.33 mm/month per region in Dec 2022,
   0.02 mm/month in Jan 2026, 505 of 1,774 days with all 7 regions exactly 0, and a 59-day run of
   all-region zeros. POWER reports 1.4-27.6x more rain in the same months (396x in January 2026). Wet-season agreement is good
   (ratio 1.05-1.50). This is the single largest scientific risk in the dataset.
8. **A retrieval regime change sits mid-series**: GPM switches from `final` to `late` run on
   **2025-10-01**. Relative to POWER, the late run reports ~40-50% less rain in Jun-Aug than the final
   run did in the same months of 2022-2025. The two eras must not be silently concatenated.
9. **Autocorrelation is extreme for the atmospheric variables.** Lag-1 ACF is 0.983 for T2M and 0.969
   for surface pressure; T2M is still at 0.727 at lag 30. Effective sample size for T2M is ~15, not
   1,774. Random K-fold CV on daily rows is meaningless here.
10. **No value in any dataset violates a hard physical bound** (14 explicit rules, 0 flags). The
    problems are all structural/cadence/calibration, not out-of-range garbage.

## 1. Inventory, schema, duplicates


##### Table 1.1 Dataset inventory
|    | dataset   |   rows |   cols |   regions | date_min   | date_max   |   n_unique_dates |   dup_key_rows | key              | cadence                  | primary_var          | note                                                   |
|---:|:----------|-------:|-------:|----------:|:-----------|:-----------|-----------------:|---------------:|:-----------------|:-------------------------|:---------------------|:-------------------------------------------------------|
|  0 | GPM_IMERG |  12418 |     11 |         7 | 2022-01-01 | 2026-11-09 |             1774 |              0 | region+date+run  | daily (complete)         | precipitation_mm_day |                                                        |
|  1 | SMAP      |  24150 |     13 |         7 | 2022-01-01 | 2026-11-09 |             1725 |              0 | region+date+pass | 2 passes/day, gappy      | soil_moisture_m3_m3  | 56 duplicate rows removed (R..._001/_002)              |
|  2 | ECOSTRESS |   2819 |     14 |         7 | 2022-01-01 | 2026-11-03 |              646 |              0 | region+dt        | per-overpass (irregular) | lst_celsius          |                                                        |
|  3 | HLS       |    413 |     14 |         7 | 2022-01-01 | 2026-11-03 |              252 |              0 | region+dt        | ~monthly attempt         | ndvi                 |                                                        |
|  4 | GRACE     |    399 |     10 |         7 | 2022-01-16 | 2026-09-16 |               57 |              0 | region+date      | monthly                  | lwe_thickness_cm     |                                                        |
|  5 | POWER     |  12313 |     13 |         7 | 2022-01-01 | 2026-10-25 |             1759 |              0 | region+date      | daily (complete)         | PRECTOTCORR          | 3 trailing all-null rows/region; SW_DWN has extra gaps |
|  6 | SRTM      |      7 |     13 |         7 | static     | static     |                1 |              0 | region           | static (1 row/region)    | elevation_mean_m     | no time dimension                                      |


Duplicate-key check: after removing 56 duplicate SMAP rows (identical values written twice under
`source_file` versions `R19240_001` and `R19240_002`, 8 dates x 2 passes x 7 regions, 2026-10-22
onwards), **every dataset has zero duplicate keys**.

Cadence is the dominant fact, and it differs by an order of magnitude per dataset:

| dataset | rows | rows per region | what one row is | effective daily coverage |
|---|---:|---:|---|---|
| GPM IMERG | 12,418 | 1,774 | 1 region-day | 100% of region-days |
| POWER | 12,313 | 1,759 | 1 region-day | 99.0% of region-days |
| SMAP | 24,150 | 3,450 | 1 region-day-pass | 39.6% of pass rows, 35-45% of am region-days |
| ECOSTRESS | 2,819 | 371-478 | 1 satellite overpass | 646 of 1,774 days have any overpass (36.4%); 7.45% of region-days have a valid LST |
| HLS | 413 | 59 | 1 acquisition attempt (monthly) | 220 valid NDVI values in 59 months x 7 regions |
| GRACE | 399 | 57 | 1 region-month | 57 complete months (2022-01..2026-09) |
| SRTM | 7 | 1 | static terrain summary | n/a |

Column-level dtypes and null counts are in `eda\01_dtypes_nulls.csv`.


## 2. Missingness

### 2.1 Overall, on the common 1,774-day grid


##### Table 2.1 Overall missingness on the common 2022-01-01..2026-11-09 grid (7 regions x 1,774 days = 12,418 region-days)
|    | series                                     |   pct_missing |   pct_valid |   region_days_valid |   region_days_total |   days_with_any_obs |   pct_days_covered |   mean_regions_per_covered_day |
|---:|:-------------------------------------------|--------------:|------------:|--------------------:|--------------------:|--------------------:|-------------------:|-------------------------------:|
|  0 | GPM precipitation_mm_day                   |          0    |      100    |               12418 |               12418 |                1774 |              100   |                           7    |
|  1 | POWER PRECTOTCORR (mm/day)                 |          1.01 |       98.99 |               12292 |               12418 |                1756 |               99   |                           7    |
|  2 | POWER ALLSKY_SFC_SW_DWN                    |          5.69 |       94.31 |               11711 |               12418 |                1673 |               94.3 |                           7    |
|  3 | SMAP soil_moisture (am)                    |         62.27 |       37.73 |                4685 |               12418 |                 973 |               54.8 |                           4.82 |
|  4 | SMAP soil_moisture (pm)                    |         60.48 |       39.52 |                4907 |               12418 |                 869 |               49   |                           5.65 |
|  5 | SMAP soil_moisture (any pass)              |         34.89 |       65.11 |                8085 |               12418 |                1264 |               71.3 |                           6.4  |
|  6 | ECOSTRESS lst_celsius                      |         92.55 |        7.45 |                 925 |               12418 |                 375 |               21.1 |                           2.47 |
|  7 | HLS ndvi                                   |         98.23 |        1.77 |                 220 |               12418 |                 162 |                9.1 |                           1.36 |
|  8 | GRACE lwe_thickness_cm (daily-interp view) |         96.79 |        3.21 |                 399 |               12418 |                  57 |                3.2 |                           7    |


`pct_missing` counts region-day cells with no valid value for the primary variable.
`pct_days_covered` counts calendar days with at least one region reporting - this is the number that
matters for a time-series model, because a day with 1 of 7 regions is not a usable daily feature row.

### 2.2 Month x year missingness matrices

Each cell is the % of expected (region x day) cells in that calendar month that are missing.


##### Table 2.2 GPM - % missing of expected (region x day) cells, month x year
|   month |   2022 |   2023 |   2024 |   2025 |   2026 |
|--------:|-------:|-------:|-------:|-------:|-------:|
|       1 |      0 |      0 |      0 |      0 |      0 |
|       2 |      0 |      0 |      0 |      0 |      0 |
|       3 |      0 |      0 |      0 |      0 |      0 |
|       4 |      0 |      0 |      0 |      0 |      0 |
|       5 |      0 |      0 |      0 |      0 |      0 |
|       6 |      0 |      0 |      0 |      0 |      0 |
|       7 |      0 |      0 |      0 |      0 |      0 |
|       8 |      0 |      0 |      0 |      0 |      0 |
|       9 |      0 |      0 |      0 |      0 |      0 |
|      10 |      0 |      0 |      0 |      0 |      0 |
|      11 |      0 |      0 |      0 |      0 |      0 |
|      12 |      0 |      0 |      0 |      0 |    nan |

##### Table 2.3 POWER PRECTOTCORR - % missing of expected cells, month x year
|   month |   2022 |   2023 |   2024 |   2025 |   2026 |
|--------:|-------:|-------:|-------:|-------:|-------:|
|       1 |      0 |      0 |      0 |      0 |      0 |
|       2 |      0 |      0 |      0 |      0 |      0 |
|       3 |      0 |      0 |      0 |      0 |      0 |
|       4 |      0 |      0 |      0 |      0 |      0 |
|       5 |      0 |      0 |      0 |      0 |      0 |
|       6 |      0 |      0 |      0 |      0 |      0 |
|       7 |      0 |      0 |      0 |      0 |      0 |
|       8 |      0 |      0 |      0 |      0 |      0 |
|       9 |      0 |      0 |      0 |      0 |      0 |
|      10 |      0 |      0 |      0 |      0 |     29 |
|      11 |      0 |      0 |      0 |      0 |    100 |
|      12 |      0 |      0 |      0 |      0 |    nan |

##### Table 2.4 SMAP am pass - % missing of expected cells, month x year
|   month |   2022 |   2023 |   2024 |   2025 |   2026 |
|--------:|-------:|-------:|-------:|-------:|-------:|
|       1 |   59.4 |   60.8 |   59   |   62.2 |   61.8 |
|       2 |   69.9 |   67.9 |   61.1 |   60.7 |   62.8 |
|       3 |   59.4 |   61.8 |   58.5 |   61.8 |   58.1 |
|       4 |   62.9 |   57.6 |   65.2 |   61   |   61.9 |
|       5 |   59   |   64.1 |   59.4 |   58.1 |   60.8 |
|       6 |   61   |   61   |   60.5 |   62.9 |   59.5 |
|       7 |   58.5 |   61.3 |   61.8 |   59.9 |   58.5 |
|       8 |   93.1 |   60.8 |   60.4 |   62.2 |   61.8 |
|       9 |   88.6 |   58.6 |   60   |   60   |   61   |
|      10 |   64.1 |   59   |   62.2 |   62.2 |   63.6 |
|      11 |   61   |   63.8 |   63.3 |   62.4 |   69.8 |
|      12 |   61.3 |   58.1 |   65.4 |   58.5 |  nan   |

##### Table 2.5 SMAP any pass - % missing of expected cells, month x year
|   month |   2022 |   2023 |   2024 |   2025 |   2026 |
|--------:|-------:|-------:|-------:|-------:|-------:|
|       1 |   31.8 |   34.6 |   31.3 |   32.7 |   35   |
|       2 |   46.4 |   38.3 |   32   |   32.1 |   31.6 |
|       3 |   30   |   30.4 |   30.9 |   35.5 |   31.3 |
|       4 |   33.3 |   30   |   35.2 |   35.2 |   34.8 |
|       5 |   28.6 |   38.2 |   28.1 |   31.3 |   31.8 |
|       6 |   32.9 |   32.9 |   37.1 |   32.9 |   29   |
|       7 |   30.4 |   36.4 |   34.1 |   31.8 |   33.2 |
|       8 |   88.5 |   33.2 |   31.3 |   33.6 |   31.8 |
|       9 |   81.9 |   31   |   31.4 |   29   |   34.8 |
|      10 |   31.3 |   28.1 |   34.6 |   32.3 |   38.7 |
|      11 |   39   |   32.4 |   35.2 |   36.2 |   49.2 |
|      12 |   33.2 |   28.1 |   33.6 |   30.4 |  nan   |

##### Table 2.6 ECOSTRESS LST - % missing of expected cells, month x year
|   month |   2022 |   2023 |   2024 |   2025 |   2026 |
|--------:|-------:|-------:|-------:|-------:|-------:|
|       1 |   86.2 |   84.3 |   91.7 |   84.3 |   79.7 |
|       2 |   94.4 |   88.3 |   99.5 |   91.3 |   90.8 |
|       3 |   90.8 |   88.9 |   96.8 |   88.9 |   95.4 |
|       4 |   87.6 |   92.4 |   93.3 |   92.4 |   90   |
|       5 |   91.2 |   94   |   97.7 |   94   |   95.4 |
|       6 |   97.1 |   93.3 |  100   |   98.6 |   94.8 |
|       7 |   97.2 |   97.7 |   94.5 |   97.2 |   98.6 |
|       8 |   94.9 |   99.5 |   96.8 |   99.5 |   99.5 |
|       9 |   96.7 |   98.6 |   93.8 |   94.3 |   91   |
|      10 |   88.9 |   90.3 |   94.5 |   90.8 |   86.2 |
|      11 |   81.4 |   86.7 |   87.6 |   88.6 |   92.1 |
|      12 |   86.2 |   92.6 |   90.3 |   90.8 |  nan   |

##### Table 2.7 HLS NDVI - % missing of expected cells, month x year
|   month |   2022 |   2023 |   2024 |   2025 |   2026 |
|--------:|-------:|-------:|-------:|-------:|-------:|
|       1 |   98.2 |   97.7 |   98.6 |   98.6 |   98.6 |
|       2 |   97.4 |   97.4 |   98.5 |   96.9 |   98   |
|       3 |   97.2 |   97.7 |   96.8 |   96.8 |   99.5 |
|       4 |   99.5 |   96.7 |   98.6 |   97.6 |   98.6 |
|       5 |   98.6 |   97.2 |   98.2 |   98.6 |   98.2 |
|       6 |  100   |   97.1 |  100   |  100   |   99.5 |
|       7 |   97.7 |   98.2 |   99.5 |   99.1 |   98.2 |
|       8 |   98.2 |  100   |   99.1 |   99.5 |   99.1 |
|       9 |   99   |   98.1 |   97.6 |   98.1 |   98.6 |
|      10 |   97.2 |   99.1 |   99.1 |   97.2 |   98.2 |
|      11 |   96.7 |   96.7 |   97.6 |   97.1 |   96.8 |
|      12 |   97.2 |   98.2 |   98.2 |   98.6 |  nan   |

##### Table 2.8 GRACE - % missing of expected cells, month x year
|   month |   2022 |   2023 |   2024 |   2025 |   2026 |
|--------:|-------:|-------:|-------:|-------:|-------:|
|       1 |   96.8 |   96.8 |   96.8 |   96.8 |   96.8 |
|       2 |   96.4 |   96.4 |   96.6 |   96.4 |   96.4 |
|       3 |   96.8 |   96.8 |   96.8 |   96.8 |   96.8 |
|       4 |   96.7 |   96.7 |   96.7 |   96.7 |   96.7 |
|       5 |   96.8 |   96.8 |   96.8 |   96.8 |   96.8 |
|       6 |   96.7 |   96.7 |   96.7 |   96.7 |   96.7 |
|       7 |   96.8 |   96.8 |   96.8 |   96.8 |   96.8 |
|       8 |   96.8 |   96.8 |   96.8 |   96.8 |   96.8 |
|       9 |   96.7 |   96.7 |   96.7 |   96.7 |   96.7 |
|      10 |   96.8 |   96.8 |   96.8 |   96.8 |  100   |
|      11 |   96.7 |   96.7 |   96.7 |   96.7 |  100   |
|      12 |   96.8 |   96.8 |   96.8 |   96.8 |  nan   |

##### Table 2.9 ECOSTRESS overpass rows and valid LST per month
| dt      |   overpass_rows |   lst_valid |   daytime_overpass |
|:--------|----------------:|------------:|-------------------:|
| 2022-01 |              70 |          30 |                 21 |
| 2022-02 |              27 |          11 |                 15 |
| 2022-03 |              62 |          20 |                  4 |
| 2022-04 |              64 |          26 |                 35 |
| 2022-05 |              71 |          19 |                 12 |
| 2022-06 |              52 |           6 |                 20 |
| 2022-07 |              39 |           6 |                  1 |
| 2022-08 |              44 |          12 |                 16 |
| 2022-09 |              43 |           7 |                  7 |
| 2022-10 |              63 |          24 |                 18 |
| 2022-11 |              73 |          39 |                 25 |
| 2022-12 |              92 |          30 |                 32 |
| 2023-01 |              93 |          37 |                 28 |
| 2023-02 |              56 |          23 |                  6 |
| 2023-03 |              69 |          24 |                 28 |
| 2023-04 |              54 |          16 |                 20 |
| 2023-05 |              32 |          13 |                 10 |
| 2023-06 |              35 |          14 |                  8 |
| 2023-07 |              46 |           5 |                  3 |
| 2023-08 |              16 |           1 |                  3 |
| 2023-09 |              32 |           3 |                  5 |
| 2023-10 |              53 |          21 |                  7 |
| 2023-11 |              52 |          28 |                 11 |
| 2023-12 |              29 |          16 |                  3 |
| 2024-01 |              44 |          18 |                 13 |
| 2024-02 |               4 |           1 |                  0 |
| 2024-03 |              22 |           7 |                  0 |
| 2024-04 |              37 |          14 |                  0 |
| 2024-05 |              29 |           5 |                  7 |
| 2024-06 |               9 |           0 |                  0 |
| 2024-07 |              55 |          12 |                 17 |
| 2024-08 |              37 |           7 |                  3 |
| 2024-09 |              45 |          13 |                  6 |
| 2024-10 |              42 |          12 |                  0 |
| 2024-11 |              63 |          26 |                 20 |
| 2024-12 |              58 |          22 |                  2 |
| 2025-01 |              66 |          34 |                 15 |
| 2025-02 |              43 |          17 |                  5 |
| 2025-03 |              74 |          24 |                 10 |
| 2025-04 |              58 |          17 |                 13 |
| 2025-05 |              38 |          13 |                 11 |
| 2025-06 |              31 |           3 |                  8 |
| 2025-07 |              50 |           6 |                 26 |
| 2025-08 |              41 |           1 |                  0 |
| 2025-09 |              49 |          12 |                 16 |
| 2025-10 |              61 |          20 |                  1 |
| 2025-11 |              52 |          24 |                 14 |
| 2025-12 |              48 |          20 |                  0 |
| 2026-01 |              86 |          44 |                 28 |
| 2026-02 |              59 |          19 |                  0 |
| 2026-03 |              46 |          10 |                  4 |
| 2026-04 |              42 |          22 |                  0 |
| 2026-05 |              40 |          10 |                  9 |
| 2026-06 |              53 |          11 |                  9 |
| 2026-07 |              29 |           3 |                 17 |
| 2026-08 |              21 |           1 |                  0 |
| 2026-09 |              58 |          19 |                 27 |
| 2026-10 |              54 |          30 |                  0 |
| 2026-11 |               8 |           5 |                  0 |


The GPM and POWER matrices are blank except at the very end of the series (POWER: 2026-10 is 29%
missing and 2026-11 is 100% missing, because the POWER files stop at 2026-10-22). The SMAP matrix is
flat at 58-65% for the am pass in every month of every year - **there is no seasonal structure to the
SMAP gaps**, except two 2022 anomalies (Aug 2022: 93.1% missing, Sep 2022: 88.6% missing) which are a
real acquisition outage confined to that year. ECOSTRESS and HLS are missing almost everywhere by
construction (92.6% and 98.2%).

### 2.3 Structural gaps vs data gaps

This is the decomposition that matters: it separates "the sensor never intended to observe this cell
that day" from "the sensor observed and the value is unusable".


##### Table 2.10 SMAP am-pass gap decomposition (1,774-day grid per region)
|    | region               |   days |   valid |   no_granule_row |   row_but_not_mapped_surface_flag_2047 |   row_but_retrieval_qual_flag_7 |   row_but_null_other |   pct_valid |
|---:|:---------------------|-------:|--------:|-----------------:|---------------------------------------:|--------------------------------:|---------------------:|------------:|
|  0 | Central_Dhaka        |   1774 |     623 |               49 |                                   1099 |                               0 |                    3 |        35.1 |
|  1 | North_Rangpur        |   1774 |     634 |               49 |                                   1091 |                               0 |                    0 |        35.7 |
|  2 | Northeast_Sylhet     |   1774 |     625 |               49 |                                   1099 |                               0 |                    1 |        35.2 |
|  3 | Northwest_Rajshahi   |   1774 |     628 |               49 |                                   1097 |                               0 |                    0 |        35.4 |
|  4 | South_Barishal       |   1774 |     627 |               49 |                                   1098 |                               0 |                    0 |        35.3 |
|  5 | Southeast_Chattogram |   1774 |     751 |               49 |                                    973 |                               0 |                    1 |        42.3 |
|  6 | Southwest_Khulna     |   1774 |     797 |               49 |                                    928 |                               0 |                    0 |        44.9 |

##### Table 2.11 ECOSTRESS gap decomposition
|    |   grid_region_days |   region_days_with_overpass_row |   overpass_rows |   qc_fill_65535_rows |   lst_valid |   other_null_rows |   days_with_any_overpass |
|---:|-------------------:|--------------------------------:|----------------:|---------------------:|------------:|------------------:|-------------------------:|
|  0 |              12418 |                            2284 |            2819 |                  146 |         933 |              1740 |                      646 |

##### Table 2.12 HLS gap decomposition
|    |   attempt_rows |   rows_zero_valid_pixels |   rows_valid_pixels_1_to_5 |   rows_valid_pixels_6_to_50 |   rows_valid_pixels_gt50 |   ndvi_present |   ndvi_from_le5_pixels |   ndvi_from_coverage_lt_0p1 |   ndvi_from_coverage_ge_0p9 |
|---:|---------------:|-------------------------:|---------------------------:|----------------------------:|-------------------------:|---------------:|-----------------------:|----------------------------:|----------------------------:|
|  0 |            413 |                      193 |                         42 |                          51 |                      127 |            220 |                     42 |                          71 |                          42 |

##### Table 2.13 POWER gap decomposition
|    |   rows |   region_days_all_null |   SW_DWN_null |   SW_DWN_null_but_other_params_present | SW_DWN_gap_start   | SW_DWN_gap_end   |
|---:|-------:|-----------------------:|--------------:|---------------------------------------:|:-------------------|:-----------------|
|  0 |  12313 |                     21 |           602 |                                    581 | 2026-08-01         | 2026-10-22       |


Reading of the decomposition:

* **GPM - daily complete, no gaps.** 1,774/1,774 days x 7 regions, zero nulls. The file name says
  `..._to_20261111` but the last row is **2026-11-09**; 2026-11-10 and 2026-11-11 are absent.
* **POWER - daily complete except two small holes.** 12,313 rows; 21 of them (3 per region, 2026-10-23
  to 2026-10-25) are entirely null - the API returned the calendar and then ran out of data. Effective
  end of series is **2026-10-22**. Separately, `ALLSKY_SFC_SW_DWN` is null for 86 days per region
  (602 rows), 83 of which are the contiguous block **2026-08-01 .. 2026-10-22** where every other
  parameter is present. That is a data gap in one parameter, not a cadence effect.
* **SMAP - structural.** 49/1,774 days per region have no granule row at all (the satellite's daily
  coverage limit, identical for all regions). The remaining 1,078-1,125 missing days have a row, but
  `surface_flag == 2047`, i.e. SMAP's own land-surface mask refused a retrieval. This is a permanent
  property of those cells (urban/coastal/complex terrain), not a transient failure. Consequence: the
  missingness is a deterministic function of location and month, so an imputer conditioned on region
  will simply learn the mask.
* **ECOSTRESS - structural.** 2,819 overpass rows across 646 distinct days (36.4% of days). 146 rows
  are QC fill (65535). Of the remaining 2,673 rows, 1,740 have a QC value but a null LST - the
  extraction recorded the granule but not the value.
* **HLS - structural + cloud.** 413 = 59 monthly attempts x 7 regions, complete and regular. 193 rows
  have zero valid pixels (cloud/no-data); a further 42 have 1-5 valid pixels.
* **GRACE - regular monthly, complete.** 57 months, no gaps, no duplicates. It simply stops in
  2026-09; Oct/Nov 2026 do not exist yet.

### 2.4 Explicit statement: daily-complete vs sparse

| classification | datasets |
|---|---|
| **Daily-complete** (usable as a daily feature with no imputation) | GPM IMERG; POWER (7 of 8 parameters, ending 2026-10-22) |
| **Regular but coarse** (complete at its own cadence) | GRACE (monthly, ends 2026-09); SRTM (static) |
| **Sparse / irregular** (must be modelled as observations, never as a filled grid) | SMAP (35-45% of days, structurally masked); ECOSTRESS (21% of days, 24-hour overpass drift); HLS (220 values in 59 months, 19% from <=5 pixels) |


## 3. Distributions and plausibility

Quantiles below are computed on valid values only, per region. Full per-region tables for every
variable are in `eda\03_quantiles_by_region.csv`.


##### Table 3.1 Pooled quantiles (all 7 regions, valid values only)
|                                 |     n |   n_missing |       p0 |       p1 |       p5 |      p25 |      p50 |      p75 |      p95 |      p99 |     p100 |     mean |      sd |
|:--------------------------------|------:|------------:|---------:|---------:|---------:|---------:|---------:|---------:|---------:|---------:|---------:|---------:|--------:|
| ('GPM', 'precipitation_mm_day') | 12418 |           0 |   0      |   0      |   0      |   0      |   0.03   |   5.05   |  33.3307 |  73.5863 | 194.97   |   6.193  | 14.9859 |
| ('POWER', 'PRECTOTCORR')        | 12292 |          21 |   0      |   0      |   0      |   0      |   1.65   |  10.3825 |  37.7435 |  76.749  | 202.35   |   8.5316 | 16.3118 |
| ('POWER', 'T2M')                | 12292 |          21 |  12.65   |  14.99   |  16.87   |  22.1975 |  27.45   |  28.71   |  30.6145 |  32.8409 |  37.47   |  25.5293 |  4.509  |
| ('POWER', 'T2M_MAX')            | 12292 |          21 |  18.61   |  21.2791 |  23.04   |  27.74   |  30.63   |  32.33   |  36.93   |  40.9709 |  47.14   |  30.1546 |  4.0719 |
| ('POWER', 'T2M_MIN')            | 12292 |          21 |   6.34   |   8.68   |  10.85   |  16.56   |  24.01   |  26.09   |  27.18   |  27.8018 |  29.43   |  21.3924 |  5.6821 |
| ('POWER', 'RH2M')               | 12292 |          21 |  12.79   |  37.0591 |  49.82   |  70.78   |  80.765  |  87.34   |  91.7945 |  93.7309 |  95.83   |  77.135  | 13.2918 |
| ('POWER', 'WS2M')               | 12292 |          21 |   0.25   |   0.66   |   0.88   |   1.26   |   1.64   |   2.34   |   3.77   |   4.88   |  11.02   |   1.9129 |  0.9328 |
| ('POWER', 'ALLSKY_SFC_SW_DWN')  | 11711 |         602 |   1.24   |   3.912  |   7.24   |  13.12   |  16.42   |  19.43   |  23.065  |  25.058  |  27.51   |  16.0345 |  4.7001 |
| ('POWER', 'PS')                 | 12292 |          21 |  97.41   |  98.91   |  99.32   | 100.04   | 100.46   | 101.01   | 101.49   | 101.71   | 101.92   | 100.481  |  0.6626 |
| ('SMAP', 'soil_moisture_m3_m3') |  9592 |       14558 |   0.0367 |   0.1275 |   0.1897 |   0.2916 |   0.3723 |   0.4827 |   0.5699 |   0.5925 |   0.5925 |   0.3802 |  0.1199 |
| ('ECOSTRESS', 'lst_celsius')    |   933 |        1886 |   9.99   |  12.6444 |  15.254  |  20.25   |  25.21   |  29.35   |  37.874  |  44.2572 |  54.67   |  25.4279 |  7.0108 |
| ('HLS', 'ndvi')                 |   220 |         193 |   0.1616 |   0.1689 |   0.1986 |   0.2992 |   0.3839 |   0.4905 |   0.6301 |   0.7226 |   0.9833 |   0.3992 |  0.1326 |
| ('HLS', 'ndmi')                 |   220 |         193 |  -0.2306 |  -0.1604 |  -0.1115 |  -0.0404 |   0.015  |   0.0832 |   0.2063 |   0.2597 |   0.5077 |   0.0273 |  0.0996 |
| ('HLS', 'valid_coverage')       |   413 |           0 |   0      |   0      |   0      |   0      |   0.0089 |   0.4044 |   0.9822 |   1      |   1      |   0.2281 |  0.3466 |
| ('GRACE', 'lwe_thickness_cm')   |   399 |           0 | -77.2958 | -70.8486 | -57.3519 | -17.0778 |  -5.8166 |  16.0884 |  36.2975 |  44.0623 |  45.5196 |  -3.7082 | 26.1932 |
| ('GRACE', 'uncertainty_cm')     |   399 |           0 |   3.1771 |   3.2169 |   3.2854 |   3.679  |   4.542  |   4.6677 |   9.4432 |  14.8596 |  18.6776 |   4.8936 |  2.3458 |

**Zero-inflation and shape.** GPM precipitation is **48.6% exact zeros** (6,034 of 12,418
region-days), median 0.03 mm/day, mean 6.19, p99 73.6, max 194.97. POWER after /24 is less
zero-inflated (median 1.65) but has a similar upper tail (p99 76.7, max 202.4). SMAP soil moisture is
left-skewed and capped (see 3.3). LST spans 9.99-54.67 C. NDVI spans 0.162-0.983 with no negatives.

### 3.1 Per-region quantiles, headline variables


##### Table 3.2 GPM precipitation_mm_day - quantiles by region
| region               | dataset   | variable             |    n |   n_missing |   p0 |   p1 |   p5 |   p25 |    p50 |     p75 |     p95 |     p99 |    p100 |   mean |      sd |
|:---------------------|:----------|:---------------------|-----:|------------:|-----:|-----:|-----:|------:|-------:|--------:|--------:|--------:|--------:|-------:|--------:|
| Central_Dhaka        | GPM       | precipitation_mm_day | 1774 |           0 |    0 |    0 |    0 |     0 | 0.03   |  4.2125 | 30.005  | 61.8836 | 175.245 | 5.6194 | 13.9524 |
| North_Rangpur        | GPM       | precipitation_mm_day | 1774 |           0 |    0 |    0 |    0 |     0 | 0      |  3.9875 | 35.3722 | 79.0626 | 172.24  | 6.0726 | 15.3853 |
| Northeast_Sylhet     | GPM       | precipitation_mm_day | 1774 |           0 |    0 |    0 |    0 |     0 | 0.5925 | 11.2725 | 45.1485 | 96.0977 | 194.97  | 9.5182 | 19.5555 |
| Northwest_Rajshahi   | GPM       | precipitation_mm_day | 1774 |           0 |    0 |    0 |    0 |     0 | 0      |  2.03   | 20.176  | 42.9823 |  85.25  | 3.3605 |  8.609  |
| South_Barishal       | GPM       | precipitation_mm_day | 1774 |           0 |    0 |    0 |    0 |     0 | 0.05   |  5.1188 | 31.3925 | 67.5708 | 134.275 | 5.9726 | 14.0433 |
| Southeast_Chattogram | GPM       | precipitation_mm_day | 1774 |           0 |    0 |    0 |    0 |     0 | 0.135  |  7.2962 | 41.3397 | 99.6816 | 173.6   | 8.0887 | 18.53   |
| Southwest_Khulna     | GPM       | precipitation_mm_day | 1774 |           0 |    0 |    0 |    0 |     0 | 0.12   |  4.2313 | 25.822  | 53.7391 | 112.45  | 4.7192 | 10.9116 |

##### Table 3.3 SMAP soil_moisture_m3_m3 - quantiles by region
| region               | dataset   | variable            |    n |   n_missing |     p0 |     p1 |     p5 |    p25 |    p50 |    p75 |    p95 |    p99 |   p100 |   mean |     sd |
|:---------------------|:----------|:--------------------|-----:|------------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|
| Central_Dhaka        | SMAP      | soil_moisture_m3_m3 | 1258 |        2192 | 0.1241 | 0.1662 | 0.2539 | 0.3531 | 0.4355 | 0.5038 | 0.5389 | 0.5389 | 0.5389 | 0.4205 | 0.0947 |
| North_Rangpur        | SMAP      | soil_moisture_m3_m3 | 1468 |        1982 | 0.1688 | 0.1895 | 0.2089 | 0.2721 | 0.3414 | 0.4623 | 0.5059 | 0.5059 | 0.5059 | 0.3578 | 0.1026 |
| Northeast_Sylhet     | SMAP      | soil_moisture_m3_m3 | 1289 |        2161 | 0.0566 | 0.1185 | 0.1748 | 0.3072 | 0.387  | 0.5027 | 0.5925 | 0.5925 | 0.5925 | 0.3942 | 0.1317 |
| Northwest_Rajshahi   | SMAP      | soil_moisture_m3_m3 | 1252 |        2198 | 0.1277 | 0.1581 | 0.2044 | 0.2663 | 0.3178 | 0.3671 | 0.442  | 0.5001 | 0.5001 | 0.3192 | 0.0737 |
| South_Barishal       | SMAP      | soil_moisture_m3_m3 | 1408 |        2042 | 0.1252 | 0.1689 | 0.2194 | 0.3242 | 0.4114 | 0.5125 | 0.569  | 0.569  | 0.569  | 0.412  | 0.1127 |
| Southeast_Chattogram | SMAP      | soil_moisture_m3_m3 | 1328 |        2122 | 0.0367 | 0.077  | 0.1248 | 0.212  | 0.3004 | 0.3853 | 0.5079 | 0.5686 | 0.5686 | 0.3039 | 0.1178 |
| Southwest_Khulna     | SMAP      | soil_moisture_m3_m3 | 1589 |        1861 | 0.1358 | 0.1759 | 0.224  | 0.3456 | 0.4681 | 0.5462 | 0.5862 | 0.5862 | 0.5862 | 0.4414 | 0.12   |

##### Table 3.4 ECOSTRESS lst_celsius - quantiles by region
| region               | dataset   | variable    |   n |   n_missing |    p0 |      p1 |      p5 |    p25 |   p50 |    p75 |    p95 |     p99 |   p100 |    mean |     sd |
|:---------------------|:----------|:------------|----:|------------:|------:|--------:|--------:|-------:|------:|-------:|-------:|--------:|-------:|--------:|-------:|
| Central_Dhaka        | ECOSTRESS | lst_celsius | 143 |         259 | 11.51 | 15.0668 | 16.336  | 20.57  | 25.09 | 29.13  | 41.5   | 47.9172 |  50.75 | 25.5981 | 7.4108 |
| North_Rangpur        | ECOSTRESS | lst_celsius | 136 |         247 |  9.99 | 11.239  | 13.86   | 17.89  | 23.73 | 29.04  | 37.815 | 43.161  |  45.39 | 24.2769 | 7.4758 |
| Northeast_Sylhet     | ECOSTRESS | lst_celsius | 128 |         295 | 15.01 | 15.4889 | 16.319  | 19.61  | 24.88 | 29.365 | 36.926 | 45.5396 |  54.67 | 25.3634 | 7.1684 |
| Northwest_Rajshahi   | ECOSTRESS | lst_celsius | 137 |         341 | 10.97 | 11.898  | 14.566  | 20.15  | 25.61 | 29.35  | 38.926 | 42.854  |  46.41 | 25.4029 | 7.3014 |
| South_Barishal       | ECOSTRESS | lst_celsius | 124 |         258 | 12.51 | 14.2546 | 14.8115 | 20.93  | 25.09 | 28.69  | 36.244 | 40.9122 |  42.63 | 25.1746 | 6.4323 |
| Southeast_Chattogram | ECOSTRESS | lst_celsius | 140 |         240 | 14.89 | 15.4427 | 16.761  | 21.745 | 25.84 | 31.96  | 37.956 | 41.6738 |  44.69 | 26.4826 | 6.741  |
| Southwest_Khulna     | ECOSTRESS | lst_celsius | 125 |         246 | 12.09 | 14.2964 | 15.322  | 21.45  | 26.29 | 29.25  | 35.994 | 42.4468 |  46.01 | 25.649  | 6.3046 |

##### Table 3.5 HLS ndvi - quantiles by region
| region               | dataset   | variable   |   n |   n_missing |     p0 |     p1 |     p5 |    p25 |    p50 |    p75 |    p95 |    p99 |   p100 |   mean |     sd |
|:---------------------|:----------|:-----------|----:|------------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|
| Central_Dhaka        | HLS       | ndvi       |  30 |          29 | 0.2639 | 0.2694 | 0.2854 | 0.3201 | 0.3766 | 0.5084 | 0.6258 | 0.6572 | 0.6659 | 0.4129 | 0.1191 |
| North_Rangpur        | HLS       | ndvi       |  23 |          36 | 0.307  | 0.3201 | 0.3677 | 0.4125 | 0.4943 | 0.5479 | 0.5835 | 0.5985 | 0.6022 | 0.4753 | 0.0819 |
| Northeast_Sylhet     | HLS       | ndvi       |  36 |          23 | 0.1686 | 0.1692 | 0.1915 | 0.3182 | 0.4049 | 0.4572 | 0.5338 | 0.675  | 0.7281 | 0.3955 | 0.1138 |
| Northwest_Rajshahi   | HLS       | ndvi       |  29 |          30 | 0.1616 | 0.1633 | 0.1711 | 0.2051 | 0.2607 | 0.2924 | 0.3478 | 0.3944 | 0.4107 | 0.2551 | 0.0585 |
| South_Barishal       | HLS       | ndvi       |  20 |          39 | 0.2845 | 0.3087 | 0.4056 | 0.475  | 0.5454 | 0.6311 | 0.7131 | 0.9292 | 0.9833 | 0.5589 | 0.1422 |
| Southeast_Chattogram | HLS       | ndvi       |  44 |          15 | 0.1737 | 0.1756 | 0.1956 | 0.2639 | 0.3355 | 0.3893 | 0.5171 | 0.5701 | 0.5835 | 0.3369 | 0.1029 |
| Southwest_Khulna     | HLS       | ndvi       |  38 |          21 | 0.2638 | 0.2808 | 0.3276 | 0.3735 | 0.4143 | 0.4997 | 0.6399 | 0.7003 | 0.7285 | 0.4436 | 0.1049 |

##### Table 3.6 HLS ndmi - quantiles by region
| region               | dataset   | variable   |   n |   n_missing |      p0 |      p1 |      p5 |     p25 |     p50 |    p75 |    p95 |    p99 |   p100 |    mean |     sd |
|:---------------------|:----------|:-----------|----:|------------:|--------:|--------:|--------:|--------:|--------:|-------:|-------:|-------:|-------:|--------:|-------:|
| Central_Dhaka        | HLS       | ndmi       |  30 |          29 | -0.1598 | -0.154  | -0.1344 | -0.0387 |  0.0155 | 0.101  | 0.1872 | 0.1978 | 0.1988 |  0.0214 | 0.1049 |
| North_Rangpur        | HLS       | ndmi       |  23 |          36 | -0.042  | -0.0407 | -0.035  |  0.0164 |  0.0566 | 0.1041 | 0.1368 | 0.1385 | 0.1388 |  0.0583 | 0.0542 |
| Northeast_Sylhet     | HLS       | ndmi       |  36 |          23 | -0.1606 | -0.1474 | -0.116  | -0.0565 | -0.0004 | 0.0325 | 0.1245 | 0.2134 | 0.2571 | -0.0032 | 0.0821 |
| Northwest_Rajshahi   | HLS       | ndmi       |  29 |          30 | -0.0784 | -0.0771 | -0.0701 | -0.0289 | -0.0038 | 0.01   | 0.0654 | 0.1119 | 0.1287 | -0.0049 | 0.0436 |
| South_Barishal       | HLS       | ndmi       |  20 |          39 | -0.2173 | -0.1923 | -0.0922 |  0.0711 |  0.1504 | 0.2187 | 0.2934 | 0.4648 | 0.5077 |  0.1419 | 0.1482 |
| Southeast_Chattogram | HLS       | ndmi       |  44 |          15 | -0.2306 | -0.1966 | -0.1302 | -0.0715 | -0.0474 | 0.0188 | 0.0875 | 0.1897 | 0.2062 | -0.0274 | 0.0809 |
| Southwest_Khulna     | HLS       | ndmi       |  38 |          21 | -0.0723 | -0.0686 | -0.0493 |  0.0213 |  0.067  | 0.1026 | 0.2377 | 0.2593 | 0.26   |  0.0697 | 0.0829 |

##### Table 3.7 GRACE lwe_thickness_cm - quantiles by region
| region               | dataset   | variable         |   n |   n_missing |       p0 |       p1 |       p5 |      p25 |      p50 |      p75 |      p95 |     p99 |    p100 |     mean |      sd |
|:---------------------|:----------|:-----------------|----:|------------:|---------:|---------:|---------:|---------:|---------:|---------:|---------:|--------:|--------:|---------:|--------:|
| Central_Dhaka        | GRACE     | lwe_thickness_cm |  57 |           0 | -25.8273 | -23.6486 | -18.0417 |  -8.5628 |   6.3805 |  28.2381 |  37.3282 | 44.6869 | 45.5196 |   9.5985 | 20.2214 |
| North_Rangpur        | GRACE     | lwe_thickness_cm |  57 |           0 | -77.2958 | -76.5762 | -71.6817 | -61.3155 | -45.7927 | -29.4953 | -13.8529 | -5.3292 | -5.0064 | -44.7308 | 19.8278 |
| Northeast_Sylhet     | GRACE     | lwe_thickness_cm |  57 |           0 | -25.8273 | -23.6486 | -18.0417 |  -8.5628 |   6.3805 |  28.2381 |  37.3282 | 44.6869 | 45.5196 |   9.5985 | 20.2214 |
| Northwest_Rajshahi   | GRACE     | lwe_thickness_cm |  57 |           0 | -40.8659 | -40.6796 | -36.9899 | -21.0926 | -14.7454 |   0.1681 |  17.2806 | 22.3875 | 22.8954 | -11.6275 | 17.061  |
| South_Barishal       | GRACE     | lwe_thickness_cm |  57 |           0 | -25.8273 | -23.6486 | -18.0417 |  -8.5628 |   6.3805 |  28.2381 |  37.3282 | 44.6869 | 45.5196 |   9.5985 | 20.2214 |
| Southeast_Chattogram | GRACE     | lwe_thickness_cm |  57 |           0 | -21.8384 | -21.4091 | -18.9252 | -12.5861 |  -7.3332 |  -3.5145 |   2.3089 |  3.8952 |  4.5511 |  -7.9932 |  6.316  |
| Southwest_Khulna     | GRACE     | lwe_thickness_cm |  57 |           0 | -25.8273 | -23.6486 | -18.0417 |  -8.5628 |   6.3805 |  28.2381 |  37.3282 | 44.6869 | 45.5196 |   9.5985 | 20.2214 |

##### Table 3.8 POWER T2M - quantiles by region
| region               | dataset   | variable   |    n |   n_missing |    p0 |      p1 |      p5 |     p25 |    p50 |     p75 |     p95 |     p99 |   p100 |    mean |     sd |
|:---------------------|:----------|:-----------|-----:|------------:|------:|--------:|--------:|--------:|-------:|--------:|--------:|--------:|-------:|--------:|-------:|
| Central_Dhaka        | POWER     | T2M        | 1756 |           3 | 13.56 | 15.291  | 17.04   | 22.4325 | 27.61  | 28.72   | 30.465  | 31.9585 |  33.68 | 25.619  | 4.4052 |
| North_Rangpur        | POWER     | T2M        | 1756 |           3 | 13.85 | 15.021  | 16.38   | 21.1175 | 26.99  | 28.8625 | 30.565  | 32.077  |  35.13 | 25.1385 | 4.7526 |
| Northeast_Sylhet     | POWER     | T2M        | 1756 |           3 | 13.48 | 15.0455 | 16.89   | 21.2925 | 26.3   | 27.87   | 29.47   | 30.6035 |  31.81 | 24.6353 | 4.2066 |
| Northwest_Rajshahi   | POWER     | T2M        | 1756 |           3 | 12.65 | 13.9685 | 15.68   | 21.7625 | 27.84  | 29.4925 | 32.415  | 34.05   |  36.44 | 25.7821 | 5.252  |
| South_Barishal       | POWER     | T2M        | 1756 |           3 | 14.43 | 16.164  | 17.605  | 23.065  | 27.875 | 28.71   | 29.84   | 31.4245 |  32.79 | 25.8631 | 4.0892 |
| Southeast_Chattogram | POWER     | T2M        | 1756 |           3 | 14.7  | 16.2865 | 18.09   | 23.3525 | 27.57  | 28.42   | 29.5825 | 30.6925 |  32.76 | 25.762  | 3.8195 |
| Southwest_Khulna     | POWER     | T2M        | 1756 |           3 | 13.34 | 14.9775 | 16.4625 | 22.685  | 27.75  | 28.95   | 31.525  | 34.184  |  37.47 | 25.9051 | 4.7407 |

##### Table 3.9 POWER RH2M - quantiles by region
| region               | dataset   | variable   |    n |   n_missing |    p0 |      p1 |      p5 |     p25 |    p50 |     p75 |     p95 |     p99 |   p100 |    mean |      sd |
|:---------------------|:----------|:-----------|-----:|------------:|------:|--------:|--------:|--------:|-------:|--------:|--------:|--------:|-------:|--------:|--------:|
| Central_Dhaka        | POWER     | RH2M       | 1756 |           3 | 35.67 | 41.143  | 49.8175 | 69.5425 | 80.795 | 88.465  | 92.1525 | 93.9735 |  95.75 | 77.3133 | 13.35   |
| North_Rangpur        | POWER     | RH2M       | 1756 |           3 | 19.3  | 33.8115 | 44.165  | 67.7725 | 80.675 | 86.68   | 90.9    | 93.0935 |  95.56 | 75.4388 | 14.9    |
| Northeast_Sylhet     | POWER     | RH2M       | 1756 |           3 | 49.17 | 52.9965 | 59.39   | 73.3775 | 80.58  | 87.68   | 92.3325 | 94.2345 |  95.83 | 79.3424 | 10.0098 |
| Northwest_Rajshahi   | POWER     | RH2M       | 1756 |           3 | 12.79 | 27.575  | 40.1125 | 61.0625 | 77.455 | 84.9825 | 90.75   | 93.2985 |  95.14 | 72.3931 | 16.2848 |
| South_Barishal       | POWER     | RH2M       | 1756 |           3 | 43.55 | 50.4065 | 59.22   | 74.82   | 83.12  | 88.185  | 91.795  | 93.4635 |  94.58 | 80.3542 | 10.0498 |
| Southeast_Chattogram | POWER     | RH2M       | 1756 |           3 | 42.06 | 49.492  | 57.0525 | 73.465  | 81.79  | 87.18   | 91.155  | 92.919  |  94.24 | 79.0461 | 10.4576 |
| Southwest_Khulna     | POWER     | RH2M       | 1756 |           3 | 27.4  | 35.1875 | 46.2    | 66.215  | 80.51  | 87.975  | 92.45   | 94.428  |  95.37 | 76.0573 | 14.6918 |

##### Table 3.10 POWER PRECTOTCORR (after /24) - quantiles by region
| region               | dataset   | variable    |    n |   n_missing |   p0 |   p1 |   p5 |   p25 |   p50 |     p75 |     p95 |      p99 |   p100 |    mean |      sd |
|:---------------------|:----------|:------------|-----:|------------:|-----:|-----:|-----:|------:|------:|--------:|--------:|---------:|-------:|--------:|--------:|
| Central_Dhaka        | POWER     | PRECTOTCORR | 1756 |           3 |    0 |    0 |    0 |     0 | 2.445 |  9.67   | 29.5375 |  56.991  | 146.11 |  7.4092 | 12.7604 |
| North_Rangpur        | POWER     | PRECTOTCORR | 1756 |           3 |    0 |    0 |    0 |     0 | 0.8   |  9.1125 | 36.3025 |  61.2185 |  98.65 |  7.4517 | 13.449  |
| Northeast_Sylhet     | POWER     | PRECTOTCORR | 1756 |           3 |    0 |    0 |    0 |     0 | 3.98  | 18.7125 | 61.395  | 112.166  | 202.35 | 14.2298 | 24.5092 |
| Northwest_Rajshahi   | POWER     | PRECTOTCORR | 1756 |           3 |    0 |    0 |    0 |     0 | 0.725 |  5.9025 | 21.4075 |  38.1665 |  77.41 |  4.6789 |  8.5435 |
| South_Barishal       | POWER     | PRECTOTCORR | 1756 |           3 |    0 |    0 |    0 |     0 | 2.47  | 12.1125 | 44.6025 |  81.8465 | 198.59 |  9.745  | 17.8548 |
| Southeast_Chattogram | POWER     | PRECTOTCORR | 1756 |           3 |    0 |    0 |    0 |     0 | 2.205 | 12.655  | 44.885  |  91.0595 | 182.95 | 10.1295 | 18.4919 |
| Southwest_Khulna     | POWER     | PRECTOTCORR | 1756 |           3 |    0 |    0 |    0 |     0 | 1.26  |  7.77   | 26.0275 |  52.8425 | 139.64 |  6.077  | 11.2011 |

### 3.2 Hard physical-plausibility rules

14 rules were applied (precipitation > 300 mm/day, SM outside 0-0.65, NDVI/NDMI outside -1..1,
LST outside -20..70 C, RH outside 0-100, negative wind/irradiance/precipitation, PS outside
50-110 kPa, T2M outside -10..50 C, T2M outside its own [MIN, MAX]). **All 14 returned zero flagged
values.** Nothing needs to be dropped for being out of range.


##### Table 3.11 Physical-plausibility checks
|    | dataset   | variable             | rule                  | why                                     |   pct_of_valid |
|---:|:----------|:---------------------|:----------------------|:----------------------------------------|---------------:|
|  0 | GPM       | precipitation_mm_day | > 300 mm/day          | physically impossible for a daily total |              0 |
|  1 | POWER     | PRECTOTCORR          | > 300 mm/day          | physically impossible for a daily total |              0 |
|  2 | POWER     | PRECTOTCORR          | < 0 mm/day            | negative precipitation                  |              0 |
|  3 | POWER     | RH2M                 | outside 0-100 %       | invalid humidity                        |              0 |
|  4 | POWER     | WS2M                 | < 0 m/s               | negative wind speed                     |              0 |
|  5 | POWER     | ALLSKY_SFC_SW_DWN    | < 0 MJ/m2/day         | negative irradiance                     |              0 |
|  6 | POWER     | PS                   | outside 50-110 kPa    | invalid pressure                        |              0 |
|  7 | POWER     | T2M                  | outside -10..50 C     | implausible air temp                    |              0 |
|  8 | POWER     | T2M                  | T2M outside [MIN,MAX] | internal inconsistency                  |              0 |
|  9 | SMAP      | soil_moisture_m3_m3  | outside 0-0.65        | invalid volumetric SM                   |              0 |
| 10 | ECOSTRESS | lst_celsius          | outside -20..70 C     | invalid LST                             |              0 |
| 11 | HLS       | ndvi                 | outside -1..1         | invalid NDVI                            |              0 |
| 12 | HLS       | ndmi                 | outside -1..1         | invalid NDMI                            |              0 |
| 13 | HLS       | valid_coverage       | outside 0..1          | invalid coverage                        |              0 |

### 3.3 Soft implausibilities that the hard rules do not catch

These are the real distributional defects:

* **SMAP ceiling pile-up.** A single identical value is repeated at the top of each region's
  distribution: 0.5389 appears 116 times in Central_Dhaka (11.0% of that region's valid values),
  0.5059 236 times in North_Rangpur (18.8%), 0.5925 133 times in Northeast_Sylhet (12.6%), 0.5690
  139 times in South_Barishal (11.6%), 0.5862 127 times in Southwest_Khulna (10.1%). The second-highest distinct value is within 0.0007 of the maximum in every case.
  This is a clipped/censored retrieval ceiling, not weather. **p95 = p99 = p100 is not a coincidence**;
  any percentile-based extreme detector on SMAP is measuring the clip.
* **GPM dry-season floor.** 91.2% of January region-days and 89.1% of December region-days are
  exactly 0.0 mm, and on 83.9% of January days all seven regions are simultaneously dry (table 3.12). Combined with POWER this looks like a retrieval/threshold artefact in the cold-season
  IMERG daily product rather than a real drought (see section 7).
* **ECOSTRESS LST is bimodal in time-of-day**, not in value: same-day overpasses range over all 24
  local hours, and the LST difference between the 09-12 bucket and the 00-03 bucket is about 9 C.
* **GRACE `cri_scale_factor` is present but unused.** Values range 0.733-1.452 and are null for
  Southeast_Chattogram, yet four regions with four different scale factors share one identical LWE
  series. The column must be applied explicitly if region-level differentiation is wanted.


##### Table 3.12 GPM zero-rain structure by calendar month
|   month |   pct_region_days_exactly_zero |   pct_days_all_7_regions_dry |
|--------:|-------------------------------:|-----------------------------:|
|       1 |                           91.2 |                         83.9 |
|       2 |                           85.5 |                         68.1 |
|       3 |                           68.8 |                         45.2 |
|       4 |                           58.4 |                         20.7 |
|       5 |                           29.2 |                          3.9 |
|       6 |                           16.5 |                          0   |
|       7 |                            7   |                          0   |
|       8 |                            5.9 |                          0   |
|       9 |                           11.1 |                          1.3 |
|      10 |                           49.1 |                         23.9 |
|      11 |                           87.3 |                         71.3 |
|      12 |                           89.1 |                         79.8 |

##### Table 3.13 SMAP retrieval ceiling pile-up (identical maximum repeated many times)
|    | region               |   n_valid |    max |   n_at_max |   pct_at_max |   second_distinct_max |
|---:|:---------------------|----------:|-------:|-----------:|-------------:|----------------------:|
|  0 | Central_Dhaka        |      1053 | 0.5389 |        116 |        11.02 |                0.5387 |
|  1 | North_Rangpur        |      1255 | 0.5059 |        236 |        18.8  |                0.5052 |
|  2 | Northeast_Sylhet     |      1053 | 0.5925 |        133 |        12.63 |                0.5922 |
|  3 | Northwest_Rajshahi   |      1252 | 0.5001 |         16 |         1.28 |                0.4988 |
|  4 | South_Barishal       |      1202 | 0.569  |        139 |        11.56 |                0.5688 |
|  5 | Southeast_Chattogram |      1012 | 0.5686 |         13 |         1.28 |                0.565  |
|  6 | Southwest_Khulna     |      1258 | 0.5862 |        127 |        10.1  |                0.5861 |

##### Table 3.14 SMAP ceiling pile-up by pass
|                                |   n |    max |   n_at_max |   pct_at_max |
|:-------------------------------|----:|-------:|-----------:|-------------:|
| ('Central_Dhaka', 'am')        | 623 | 0.5389 |        133 |          7.7 |
| ('Central_Dhaka', 'pm')        | 635 | 0.5389 |         36 |          2.1 |
| ('North_Rangpur', 'am')        | 634 | 0.5059 |        130 |          7.5 |
| ('North_Rangpur', 'pm')        | 834 | 0.5059 |        155 |          9   |
| ('Northeast_Sylhet', 'am')     | 625 | 0.5925 |        102 |          5.9 |
| ('Northeast_Sylhet', 'pm')     | 664 | 0.5925 |         83 |          4.8 |
| ('Northwest_Rajshahi', 'am')   | 628 | 0.5001 |         11 |          0.6 |
| ('Northwest_Rajshahi', 'pm')   | 624 | 0.5001 |          5 |          0.3 |
| ('South_Barishal', 'am')       | 627 | 0.569  |        104 |          6   |
| ('South_Barishal', 'pm')       | 781 | 0.569  |         73 |          4.2 |
| ('Southeast_Chattogram', 'am') | 751 | 0.5686 |         22 |          1.3 |
| ('Southeast_Chattogram', 'pm') | 577 | 0.5686 |          9 |          0.5 |
| ('Southwest_Khulna', 'am')     | 797 | 0.5862 |        104 |          6   |
| ('Southwest_Khulna', 'pm')     | 792 | 0.5862 |         94 |          5.4 |

##### Table 3.15 ECOSTRESS overpass local-time distribution and LST by local-time bucket (UTC+6)
| bucket   |   overpasses |   lst_valid |   lst_mean |   lst_sd |
|:---------|-------------:|------------:|-----------:|---------:|
| 00-03    |          433 |         144 |      22.4  |     4.3  |
| 03-06    |          440 |         160 |      21.32 |     4.88 |
| 06-09    |          278 |          75 |      23.56 |     7.37 |
| 09-12    |          277 |         100 |      31.64 |     7.06 |
| 12-15    |          226 |         100 |      31.58 |     5.71 |
| 15-18    |          344 |         108 |      28.44 |     7.02 |
| 18-21    |          425 |         126 |      25.35 |     5.67 |
| 21-24    |          396 |         120 |      22.77 |     5.89 |

##### Table 3.16 GRACE: regions with byte-identical LWE series (same mascon 1321)
| region               |   mascon_id |   grid_lat |   grid_lon |   cri_scale_factor | identical_to_Central_Dhaka   |
|:---------------------|------------:|-----------:|-----------:|-------------------:|:-----------------------------|
| Central_Dhaka        |        1321 |      23.75 |      90.25 |           1.15919  | True                         |
| North_Rangpur        |        1214 |      25.75 |      89.25 |           1.45221  | False                        |
| Northeast_Sylhet     |        1321 |      24.75 |      91.75 |           0.945975 | True                         |
| Northwest_Rajshahi   |        1320 |      24.25 |      88.75 |           1.09043  | False                        |
| South_Barishal       |        1321 |      22.75 |      90.25 |           0.733391 | True                         |
| Southeast_Chattogram |        1431 |      22.25 |      91.75 |         nan        | False                        |
| Southwest_Khulna     |        1321 |      22.75 |      89.75 |           0.860325 | True                         |

## 4. Seasonality

Monthly climatology = mean over 7 regions of the monthly means of the series (so it is the shape of
the annual cycle, not a total).


##### Table 4.1 Monthly climatology, mean over 7 regions
|   month |   GPM precipitation (mm/day) |   POWER PRECTOTCORR (mm/day) |   POWER T2M (C) |   POWER RH2M (%) |   POWER ALLSKY_SFC_SW_DWN (MJ/m2/d) |   SMAP soil moisture am (m3/m3) |   ECOSTRESS LST (C) |   HLS NDVI |   HLS NDMI |   GRACE LWE (cm) |
|--------:|-----------------------------:|-----------------------------:|----------------:|-----------------:|------------------------------------:|--------------------------------:|--------------------:|-----------:|-----------:|-----------------:|
|       1 |                        0.108 |                        0.388 |          17.424 |           73.579 |                              12.684 |                           0.382 |              19.494 |      0.334 |     -0.028 |          -16.521 |
|       2 |                        0.473 |                        0.714 |          20.707 |           61.256 |                              16.27  |                           0.391 |              19.934 |      0.295 |     -0.034 |          -17.16  |
|       3 |                        1.597 |                        2.663 |          25.77  |           59.316 |                              18.201 |                           0.304 |              26.825 |      0.332 |     -0.005 |          -22.787 |
|       4 |                        3.566 |                        5.657 |          29.165 |           64.191 |                              19.487 |                           0.271 |              27.73  |      0.326 |     -0.015 |          -22.365 |
|       5 |                        9.846 |                       14.018 |          29.138 |           75.989 |                              18.408 |                           0.34  |              31.025 |      0.344 |     -0.029 |          -14.58  |
|       6 |                       13.486 |                       18.449 |          28.92  |           86.047 |                              15.564 |                           0.408 |              31.106 |      0.355 |     -0.029 |            1.116 |
|       7 |                       12.208 |                       16.843 |          28.742 |           87.883 |                              16.501 |                           0.456 |              32.604 |      0.473 |      0.089 |           13.664 |
|       8 |                       13.636 |                       17.482 |          28.366 |           88.529 |                              14.849 |                           0.481 |              30.775 |      0.477 |      0.065 |           17.353 |
|       9 |                       10.424 |                       12.869 |          28.272 |           87.548 |                              15.683 |                           0.402 |              33.209 |      0.499 |      0.094 |           17.312 |
|      10 |                        5.629 |                        7.877 |          26.648 |           83.229 |                              15.364 |                           0.341 |              26.188 |      0.484 |      0.067 |           11.541 |
|      11 |                        0.77  |                        1.31  |          22.478 |           79.492 |                              15.461 |                           0.349 |              25.248 |      0.43  |      0.047 |            0.976 |
|      12 |                        0.242 |                        0.494 |          18.59  |           78.492 |                              12.841 |                           0.348 |              18.818 |      0.401 |      0.017 |          -10.399 |


Month of peak, region-mean series: **rainfall Aug (13.64 mm/day)**, trough Jan (0.108 mm/day) - a 126x
annual swing. **T2M Apr (29.17 C)** vs Jan (17.42 C); the April/May peak is the pre-monsoon heat
maximum and April and May are within 0.03 C of each other, so the region-mean peak month is not
meaningful at that resolution (per-region peaks: 4 of 7 regions peak in April, 2 in July, 1 in May).
**RH2M Aug (88.5%)** vs Mar (59.3%). **SW_DWN Apr (19.49 MJ/m2/d)** vs Jan (12.68) - peak insolation in
the pre-monsoon, minimum in the winter haze season. **SMAP SM Aug (0.481)** vs Apr (0.271).
**NDVI Sep (0.499)** vs Feb (0.295). **GRACE LWE Sep (+17.3 cm)** vs Mar (-22.8 cm).

### 4.1 Per-region amplitude


##### Table 4.2 Per-region seasonal amplitude
| variable                          |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|:----------------------------------|----------------:|----------------:|-------------------:|---------------------:|-----------------:|-----------------------:|-------------------:|
| ECOSTRESS LST (C)                 |          19.083 |          24.93  |             17.489 |               21.413 |           19.746 |                 11.184 |             16.489 |
| GPM precipitation (mm/day)        |          11.099 |          16.615 |             27.97  |                7.971 |           15.697 |                 22.179 |             10.931 |
| GRACE LWE (cm)                    |          50.156 |          46.206 |             50.156 |               43.29  |           50.156 |                 12.962 |             50.156 |
| HLS NDMI                          |           0.231 |           0.137 |              0.205 |                0.089 |            0.612 |                  0.205 |              0.24  |
| HLS NDVI                          |           0.354 |           0.227 |              0.393 |                0.119 |            0.557 |                  0.261 |              0.288 |
| POWER ALLSKY_SFC_SW_DWN (MJ/m2/d) |           7.438 |           6.973 |              5.557 |                8.54  |            6.784 |                  5.94  |              6.89  |
| POWER PRECTOTCORR (mm/day)        |          14.139 |          21.593 |             38.788 |                9.77  |           23.297 |                 25.585 |             12.476 |
| POWER RH2M (%)                    |          31.698 |          33.122 |             22.225 |               40.294 |           22.879 |                 24.108 |             34.414 |
| POWER T2M (C)                     |          12.112 |          12.321 |             11.173 |               14.448 |           11.422 |                 10.393 |             13.752 |
| SMAP soil moisture am (m3/m3)     |           0.178 |           0.231 |              0.311 |                0.207 |            0.251 |                  0.188 |              0.311 |

##### Table 4.3 Peak month per region
| variable                          |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|:----------------------------------|----------------:|----------------:|-------------------:|---------------------:|-----------------:|-----------------------:|-------------------:|
| ECOSTRESS LST (C)                 |               9 |               6 |                  7 |                    9 |                7 |                      9 |                  6 |
| GPM precipitation (mm/day)        |               8 |               6 |                  6 |                    8 |                8 |                      8 |                  7 |
| GRACE LWE (cm)                    |               9 |               8 |                  9 |                    9 |                9 |                      6 |                  9 |
| HLS NDMI                          |               7 |               9 |                  8 |                   11 |               10 |                      7 |                  7 |
| HLS NDVI                          |               9 |               9 |                  8 |                   11 |               10 |                      9 |                  7 |
| POWER ALLSKY_SFC_SW_DWN (MJ/m2/d) |               4 |               4 |                  4 |                    4 |                4 |                      4 |                  4 |
| POWER PRECTOTCORR (mm/day)        |               6 |               6 |                  6 |                    9 |                8 |                      8 |                  7 |
| POWER RH2M (%)                    |               8 |               7 |                  8 |                    9 |                8 |                      8 |                  9 |
| POWER T2M (C)                     |               4 |               7 |                  7 |                    4 |                4 |                      5 |                  4 |
| SMAP soil moisture am (m3/m3)     |               8 |               2 |                  6 |                    8 |                8 |                      8 |                  8 |

Amplitude is `max(monthly mean) - min(monthly mean)`. Rainfall amplitude spans 7.97 mm/day
(Northwest_Rajshahi) to 27.97 mm/day (Northeast_Sylhet) - a 3.5x range in seasonal forcing across the
country, so a single national seasonal feature will under-fit both ends. SMAP amplitude 0.178-0.311
m3/m3, i.e. the annual cycle is roughly as large as the entire inter-region spread of the mean.

**One anomaly worth flagging:** SMAP soil moisture has *no* dry-season minimum. The region-mean
climatology is 0.382 in January and 0.391 in February, *higher* than April's 0.271, while January
rainfall is 0.108 mm/day. Soil moisture is not tracking rainfall in Nov-Mar. Two candidate
explanations - winter boro rice irrigation, or a cold-season retrieval artefact - and this dataset
cannot distinguish them. Either way, **a rain-driven model of soil moisture will fail in the dry
season**: corr(monthly SM, monthly rain) is 0.655 in Apr-Oct but **-0.086 in Nov-Mar**.


##### Table 4.4 Correlation between monthly SMAP soil moisture and monthly GPM rainfall, by season
|    | season        |   n_months |   corr |   mean_sm |   mean_rain |
|---:|:--------------|-----------:|-------:|----------:|------------:|
|  0 | dry (Nov-Mar) |         24 | -0.086 |     0.365 |        19.2 |
|  1 | wet (Apr-Oct) |         35 |  0.655 |     0.407 |       300.7 |
|  2 | all           |         59 |  0.552 |     0.39  |       186.2 |

## 5. Temporal structure and autocorrelation

ACF is computed with pairwise-complete observations (so sparse series contribute only the pairs where
both endpoints exist) and reported per region, lags 1-30 days. Full curves: `eda\05_acf_daily_curve_regionmean.csv`.


##### Table 5.1 Daily autocorrelation, lag 1-30 (pairwise-complete), mean/min/max over 7 regions
|    | variable                 |   lag1_mean |   lag1_min |   lag1_max |   lag7_mean |   lag30_mean |   n_pairs_lag1 | lag_where_acf<0.2   |
|---:|:-------------------------|------------:|-----------:|-----------:|------------:|-------------:|---------------:|:--------------------|
|  0 | ECOSTRESS LST (sparse)   |     nan     |    nan     |    nan     |     nan     |      nan     |          2.857 | >30                 |
|  1 | GPM precipitation_mm_day |       0.422 |      0.274 |      0.572 |       0.121 |        0.115 |       1773     | 4                   |
|  2 | POWER ALLSKY_SFC_SW_DWN  |       0.634 |      0.601 |      0.674 |       0.214 |        0.097 |       1672     | 12                  |
|  3 | POWER PRECTOTCORR mm/day |       0.638 |      0.571 |      0.709 |       0.199 |        0.178 |       1755     | 7                   |
|  4 | POWER PS                 |       0.969 |      0.967 |      0.973 |       0.835 |        0.703 |       1755     | >30                 |
|  5 | POWER RH2M               |       0.928 |      0.896 |      0.951 |       0.76  |        0.573 |       1755     | >30                 |
|  6 | POWER T2M                |       0.983 |      0.98  |      0.987 |       0.921 |        0.727 |       1755     | >30                 |
|  7 | POWER WS2M               |       0.74  |      0.645 |      0.8   |       0.272 |        0.241 |       1755     | >30                 |
|  8 | SMAP soil_moisture am    |       0.727 |      0.569 |      0.85  |       0.697 |        0.353 |        161.286 | >30                 |
|  9 | SMAP soil_moisture pm    |       0.697 |      0.611 |      0.812 |       0.642 |        0.422 |         75.429 | >30                 |

##### Table 5.2 Effective sample size implied by the lag-1 autocorrelation (n = 1,774 days)
|    | variable                 |   lag1_mean | lag_where_acf<0.2   |   n_days |   n_eff |
|---:|:-------------------------|------------:|:--------------------|---------:|--------:|
|  0 | ECOSTRESS LST (sparse)   |     nan     | >30                 |     1774 |   nan   |
|  1 | GPM precipitation_mm_day |       0.422 | 4                   |     1774 |   721.1 |
|  2 | POWER ALLSKY_SFC_SW_DWN  |       0.634 | 12                  |     1774 |   397.4 |
|  3 | POWER PRECTOTCORR mm/day |       0.638 | 7                   |     1774 |   392.1 |
|  4 | POWER PS                 |       0.969 | >30                 |     1774 |    27.9 |
|  5 | POWER RH2M               |       0.928 | >30                 |     1774 |    66.2 |
|  6 | POWER T2M                |       0.983 | >30                 |     1774 |    15.2 |
|  7 | POWER WS2M               |       0.74  | >30                 |     1774 |   265.1 |
|  8 | SMAP soil_moisture am    |       0.727 | >30                 |     1774 |   nan   |
|  9 | SMAP soil_moisture pm    |       0.697 | >30                 |     1774 |   nan   |

##### Table 5.3 Region-mean ACF curve, lags 1-30
|    |   GPM precipitation_mm_day |   POWER PRECTOTCORR mm/day |   POWER T2M |   POWER RH2M |   POWER WS2M |   POWER ALLSKY_SFC_SW_DWN |   POWER PS |   SMAP soil_moisture am |   SMAP soil_moisture pm |   ECOSTRESS LST (sparse) |
|---:|---------------------------:|---------------------------:|------------:|-------------:|-------------:|--------------------------:|-----------:|------------------------:|------------------------:|-------------------------:|
|  1 |                      0.422 |                      0.638 |       0.983 |        0.928 |        0.74  |                     0.634 |      0.969 |                   0.727 |                   0.697 |                      nan |
|  2 |                      0.269 |                      0.421 |       0.966 |        0.864 |        0.509 |                     0.451 |      0.925 |                   0.679 |                   0.685 |                      nan |
|  3 |                      0.211 |                      0.321 |       0.952 |        0.831 |        0.4   |                     0.344 |      0.896 |                   0.746 |                   0.743 |                      nan |
|  5 |                      0.151 |                      0.237 |       0.934 |        0.795 |        0.333 |                     0.245 |      0.866 |                   0.729 |                   0.719 |                      nan |
|  7 |                      0.121 |                      0.199 |       0.921 |        0.76  |        0.272 |                     0.214 |      0.835 |                   0.697 |                   0.642 |                      nan |
| 10 |                      0.131 |                      0.216 |       0.904 |        0.727 |        0.261 |                     0.217 |      0.811 |                   0.581 |                   0.606 |                      nan |
| 14 |                      0.137 |                      0.183 |       0.879 |        0.695 |        0.242 |                     0.14  |      0.788 |                   0.527 |                   0.563 |                      nan |
| 20 |                      0.178 |                      0.252 |       0.835 |        0.653 |        0.292 |                     0.207 |      0.76  |                   0.613 |                 nan     |                      nan |
| 25 |                      0.101 |                      0.173 |       0.785 |        0.604 |        0.25  |                     0.126 |      0.743 |                   0.514 |                   0.417 |                      nan |
| 30 |                      0.115 |                      0.178 |       0.727 |        0.573 |        0.241 |                     0.097 |      0.703 |                   0.353 |                   0.422 |                      nan |

##### Table 5.4 Lag-1 autocorrelation by region
| variable                 |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|:-------------------------|----------------:|----------------:|-------------------:|---------------------:|-----------------:|-----------------------:|-------------------:|
| GPM precipitation_mm_day |           0.274 |           0.372 |              0.506 |                0.297 |            0.487 |                  0.572 |              0.444 |
| POWER ALLSKY_SFC_SW_DWN  |           0.631 |           0.65  |              0.601 |                0.674 |            0.618 |                  0.615 |              0.647 |
| POWER PRECTOTCORR mm/day |           0.571 |           0.657 |              0.667 |                0.595 |            0.67  |                  0.709 |              0.593 |
| POWER PS                 |           0.968 |           0.969 |              0.967 |                0.973 |            0.97  |                  0.967 |              0.971 |
| POWER RH2M               |           0.938 |           0.943 |              0.896 |                0.947 |            0.915 |                  0.909 |              0.951 |
| POWER T2M                |           0.982 |           0.983 |              0.98  |                0.984 |            0.987 |                  0.982 |              0.984 |
| POWER WS2M               |           0.778 |           0.69  |              0.645 |                0.74  |            0.774 |                  0.8   |              0.753 |
| SMAP soil_moisture am    |           0.569 |         nan     |              0.81  |              nan     |            0.838 |                  0.569 |              0.85  |
| SMAP soil_moisture pm    |         nan     |           0.812 |              0.611 |              nan     |            0.618 |                nan     |              0.748 |


**Decorrelation** (first lag at which the region-mean ACF falls below 0.2): GPM precipitation **4 days**,
POWER precipitation **7 days**, ALLSKY_SFC_SW_DWN **12 days**, WS2M, RH2M, PS, T2M and SMAP all **>30
days**. T2M is still 0.727 at lag 30; RH2M 0.573; PS 0.703.

**Effective sample size** `n_eff = n(1-r1)/(1+r1)` with n = 1,774 daily observations:

| variable | lag-1 ACF | n_eff | interpretation |
|---|---:|---:|---|
| GPM precipitation | 0.422 | 721 | 1,774 rows behave like 721 independent ones |
| POWER PRECTOTCORR | 0.638 | 392 | |
| POWER ALLSKY_SFC_SW_DWN | 0.634 | 397 | |
| POWER WS2M | 0.740 | 265 | |
| POWER RH2M | 0.928 | 66 | |
| POWER T2M | 0.983 | **15** | a daily T2M series carries ~15 independent pieces of information |
| POWER PS | 0.969 | 28 | |
| SMAP (am) | 0.727 | n/a (gappy; only 161 lag-1 pairs exist) | |

Table 5.2 and `eda\05_acf_neff.csv` give the full list. The SMAP figure is deliberately not extrapolated: only 161 of
1,773 possible lag-1 pairs exist, and those 161 are the days when two consecutive days both passed the
land-surface mask - a biased subset. **ECOSTRESS daily ACF is not estimable at all** - on average 2.9 lag-1 pairs survive per region, so the daily row in table 5.1 is NaN by construction; use its monthly ACF (0.631 at lag 1, table 5.4) instead.

### 5.1 Monthly autocorrelation


##### Table 5.5 Monthly-series autocorrelation (lags 1-12 months)
|    |   GPM precip (monthly mean) |   GPM precip (monthly total) |   POWER PRECTOTCORR (monthly mean) |   POWER T2M (monthly mean) |   SMAP soil moisture am (monthly mean) |   HLS NDVI (monthly mean) |   ECOSTRESS LST (monthly mean) |   GRACE LWE (monthly, mascon 1321) |
|---:|----------------------------:|-----------------------------:|-----------------------------------:|---------------------------:|---------------------------------------:|--------------------------:|-------------------------------:|-----------------------------------:|
|  1 |                       0.711 |                        0.712 |                              0.692 |                      0.788 |                                  0.696 |                     0.487 |                          0.631 |                              0.814 |
|  2 |                       0.377 |                        0.379 |                              0.362 |                      0.304 |                                  0.152 |                     0.15  |                          0.438 |                              0.463 |
|  3 |                      -0.04  |                       -0.044 |                             -0.049 |                     -0.161 |                                 -0.198 |                     0.036 |                         -0.073 |                             -0.001 |
|  4 |                      -0.431 |                       -0.435 |                             -0.438 |                     -0.45  |                                 -0.239 |                    -0.247 |                         -0.272 |                             -0.416 |
|  5 |                      -0.708 |                       -0.704 |                             -0.723 |                     -0.593 |                                 -0.041 |                    -0.291 |                         -0.621 |                             -0.719 |
|  6 |                      -0.812 |                       -0.811 |                             -0.835 |                     -0.649 |                                  0.127 |                    -0.39  |                         -0.598 |                             -0.831 |
|  7 |                      -0.68  |                       -0.675 |                             -0.693 |                     -0.636 |                                  0.03  |                    -0.376 |                         -0.631 |                             -0.704 |
|  8 |                      -0.367 |                       -0.367 |                             -0.372 |                     -0.505 |                                 -0.167 |                    -0.233 |                         -0.31  |                             -0.402 |
|  9 |                       0.061 |                        0.063 |                              0.061 |                     -0.178 |                                 -0.153 |                     0.01  |                         -0.163 |                              0.01  |
| 10 |                       0.421 |                        0.424 |                              0.428 |                      0.317 |                                  0.184 |                     0.318 |                          0.311 |                              0.442 |
| 11 |                       0.731 |                        0.732 |                              0.759 |                      0.791 |                                  0.663 |                     0.396 |                          0.487 |                              0.785 |
| 12 |                       0.856 |                        0.856 |                              0.882 |                      0.974 |                                  0.892 |                     0.268 |                          0.785 |                              0.896 |

##### Table 5.6 Number of pairs at lag 1 and lag 12
|    |   GPM precip (monthly mean) |   GPM precip (monthly total) |   POWER PRECTOTCORR (monthly mean) |   POWER T2M (monthly mean) |   SMAP soil moisture am (monthly mean) |   HLS NDVI (monthly mean) |   ECOSTRESS LST (monthly mean) |   GRACE LWE (monthly, mascon 1321) |
|---:|----------------------------:|-----------------------------:|-----------------------------------:|---------------------------:|---------------------------------------:|--------------------------:|-------------------------------:|-----------------------------------:|
|  1 |                          58 |                           58 |                                 57 |                         57 |                                     58 |                        50 |                             56 |                                 56 |
| 12 |                          47 |                           47 |                                 46 |                         46 |                                     47 |                        41 |                             45 |                                 45 |

##### Table 5.7 Effective sample size of the monthly series (n = 59 months)
|                                      |   lag1_acf |   n_months |   n_eff |
|:-------------------------------------|-----------:|-----------:|--------:|
| GPM precip (monthly mean)            |   0.711467 |         59 |     9.9 |
| GPM precip (monthly total)           |   0.712043 |         59 |     9.9 |
| POWER PRECTOTCORR (monthly mean)     |   0.692248 |         59 |    10.7 |
| POWER T2M (monthly mean)             |   0.788492 |         59 |     7   |
| SMAP soil moisture am (monthly mean) |   0.695515 |         59 |    10.6 |
| HLS NDVI (monthly mean)              |   0.486712 |         59 |    20.4 |
| ECOSTRESS LST (monthly mean)         |   0.630819 |         59 |    13.4 |
| GRACE LWE (monthly, mascon 1321)     |   0.813855 |         59 |     6.1 |

Every monthly series is dominated by its annual cycle: ACF(12) is 0.856 for rainfall, 0.974 for T2M,
0.896 for GRACE, 0.892 for SMAP, and ACF(6) is strongly negative (-0.81 for rainfall) because the
half-year offset is the opposite season. Effective monthly sample size is **6.1 (GRACE) to 20.4
(HLS NDVI) out of 59 months**. A 59-row monthly training set is really a ~10-row dataset.

## 6. Cross-correlation between rainfall and the response variables

Sign convention: `corr(rain[t], response[t+L])`; **positive L means the response lags the rain.**
Both raw and deseasonalised (month-of-year climatology plus linear trend removed, so the annual cycle
cannot manufacture a correlation) versions are given. Full tables: `eda\06_crosscorr_daily.csv`,
`eda\06_crosscorr_monthly.csv`.


##### Table 6.1 Daily cross-correlation, rain (driver) vs response, lags -30..+30 days ('best_lag' = lag of maximum correlation; + = response lags rain)
|                                                                  | region   |   best_lag |   max_corr |   corr_lag0 |   corr_lag_neg5 |   corr_lag_pos5 |   corr_lag_pos10 |
|:-----------------------------------------------------------------|:---------|-----------:|-----------:|------------:|----------------:|----------------:|-----------------:|
| ('GPM rain -> SMAP SM am', 'raw')                                | POOLED   |          3 |      0.301 |       0.289 |           0.175 |           0.296 |            0.245 |
| ('GPM rain -> SMAP SM am', 'deseasonalised')                     | POOLED   |          0 |      0.14  |       0.14  |          -0.076 |           0.081 |            0.005 |
| ('GPM rain -> SMAP SM pm', 'raw')                                | POOLED   |          3 |      0.388 |       0.379 |           0.271 |           0.351 |            0.328 |
| ('GPM rain -> SMAP SM pm', 'deseasonalised')                     | POOLED   |          1 |      0.21  |       0.181 |          -0.013 |           0.099 |            0.046 |
| ('POWER rain -> SMAP SM am', 'raw')                              | POOLED   |         24 |      0.31  |       0.301 |           0.172 |           0.308 |            0.241 |
| ('POWER rain -> SMAP SM am', 'deseasonalised')                   | POOLED   |          0 |      0.223 |       0.223 |          -0.055 |           0.11  |            0.032 |
| ('GPM rain -> ECOSTRESS LST', 'raw')                             | POOLED   |         -9 |      0.412 |       0.363 |           0.364 |           0.362 |            0.253 |
| ('GPM rain -> ECOSTRESS LST', 'deseasonalised')                  | POOLED   |        -16 |      0.079 |      -0.003 |          -0.048 |          -0.016 |           -0.081 |
| ('POWER rain -> ECOSTRESS LST', 'raw')                           | POOLED   |          0 |      0.428 |       0.428 |           0.381 |           0.411 |            0.268 |
| ('POWER rain -> ECOSTRESS LST', 'deseasonalised')                | POOLED   |          1 |      0.087 |       0.071 |          -0.044 |           0.044 |           -0.032 |
| ('GPM rain -> SMAP SM (any pass)', 'raw')                        | POOLED   |          2 |      0.386 |       0.358 |           0.232 |           0.374 |            0.341 |
| ('GPM rain -> SMAP SM (any pass)', 'deseasonalised')             | POOLED   |          1 |      0.198 |       0.141 |          -0.073 |           0.115 |            0.032 |
| ('POWER rain -> SMAP SM (any pass)', 'raw')                      | POOLED   |          1 |      0.408 |       0.373 |           0.224 |           0.37  |            0.346 |
| ('POWER rain -> SMAP SM (any pass)', 'deseasonalised')           | POOLED   |          1 |      0.275 |       0.227 |          -0.058 |           0.129 |            0.077 |
| ('GPM rain -> ECOSTRESS LST (daytime only)', 'raw')              | POOLED   |         13 |      0.524 |       0.258 |           0.298 |           0.262 |            0.359 |
| ('GPM rain -> ECOSTRESS LST (daytime only)', 'deseasonalised')   | POOLED   |        -18 |      0.278 |      -0.26  |          -0.089 |          -0.078 |            0.079 |
| ('POWER rain -> ECOSTRESS LST (daytime only)', 'raw')            | POOLED   |         12 |      0.486 |       0.269 |           0.305 |           0.32  |            0.274 |
| ('POWER rain -> ECOSTRESS LST (daytime only)', 'deseasonalised') | POOLED   |        -22 |      0.263 |      -0.249 |          -0.13  |          -0.044 |           -0.076 |

##### Table 6.2 Per-region lag of maximum correlation, raw series
| pair                                       |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|:-------------------------------------------|----------------:|----------------:|-------------------:|---------------------:|-----------------:|-----------------------:|-------------------:|
| GPM rain -> ECOSTRESS LST                  |               6 |             -12 |                 18 |                   16 |                6 |                     17 |                -16 |
| GPM rain -> ECOSTRESS LST (daytime only)   |              13 |             nan |                 24 |                    8 |               26 |                     17 |                nan |
| GPM rain -> SMAP SM (any pass)             |               2 |               3 |                  2 |                    1 |                1 |                      2 |                 24 |
| GPM rain -> SMAP SM am                     |              29 |               2 |                  2 |                    1 |                3 |                      1 |                 21 |
| GPM rain -> SMAP SM pm                     |               2 |               3 |                  2 |                    1 |                1 |                      2 |                 22 |
| POWER rain -> ECOSTRESS LST                |               6 |             -15 |                 14 |                  -16 |              -19 |                      6 |                -16 |
| POWER rain -> ECOSTRESS LST (daytime only) |              23 |             nan |                 13 |                   12 |               23 |                    -27 |                nan |
| POWER rain -> SMAP SM (any pass)           |               1 |               3 |                  4 |                    1 |                1 |                      1 |                 24 |
| POWER rain -> SMAP SM am                   |               1 |               2 |                  0 |                    0 |                2 |                      2 |                  3 |

##### Table 6.3 Per-region maximum correlation, raw series
| pair                                       |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|:-------------------------------------------|----------------:|----------------:|-------------------:|---------------------:|-----------------:|-----------------------:|-------------------:|
| GPM rain -> ECOSTRESS LST                  |           0.396 |           0.395 |              0.466 |                0.367 |            0.409 |                  0.346 |              0.354 |
| GPM rain -> ECOSTRESS LST (daytime only)   |           0.598 |         nan     |              0.606 |                0.524 |            0.544 |                  0.433 |            nan     |
| GPM rain -> SMAP SM (any pass)             |           0.196 |           0.21  |              0.422 |                0.278 |            0.323 |                  0.334 |              0.213 |
| GPM rain -> SMAP SM am                     |           0.217 |           0.243 |              0.407 |                0.255 |            0.339 |                  0.335 |              0.227 |
| GPM rain -> SMAP SM pm                     |           0.211 |           0.213 |              0.41  |                0.312 |            0.326 |                  0.314 |              0.239 |
| POWER rain -> ECOSTRESS LST                |           0.453 |           0.471 |              0.547 |                0.456 |            0.452 |                  0.377 |              0.426 |
| POWER rain -> ECOSTRESS LST (daytime only) |           0.562 |         nan     |              0.768 |                0.59  |            0.536 |                  0.368 |            nan     |
| POWER rain -> SMAP SM (any pass)           |           0.256 |           0.28  |              0.473 |                0.289 |            0.38  |                  0.356 |              0.217 |
| POWER rain -> SMAP SM am                   |           0.237 |           0.285 |              0.482 |                0.266 |            0.435 |                  0.368 |              0.209 |

**Interpretation.**

* **Rain -> SMAP soil moisture: lag 0-1 day, and weak once seasonality is removed.** Raw, the peak is
  at lag +3 with r = 0.30 (am) / 0.39 (pm). After deseasonalising, the peak collapses to lag 0 with
  **r = 0.14 (am)** and lag +1 with r = 0.21 (pm). So the apparent 0.3-0.4 correlation is almost
  entirely the shared annual cycle; the genuine day-to-day soil-moisture response to a rain event is
  r ~ 0.2. The pm pass responds slightly more strongly and one day later, which is physically sensible
  (afternoon retrieval sees the same day's rain). Averaging the passes into one daily value is a
  better predictor than either pass alone: best lag +2 (GPM) / +1 (POWER) with r = 0.386 / 0.408 raw,
  0.198 / 0.275 deseasonalised.
* The raw POWER rain -> SMAP SM am peak at **lag +24** (r = 0.310 vs 0.301 at lag 0) is not a physical 24-day response: once both series carry the annual cycle the whole +/-30-day window is correlated at 0.24-0.31 and the argmax lands wherever the seasonal phase aligns. Read the deseasonalised row (lag 0, r = 0.223), not the raw argmax.
* Per-region raw lags are unstable - Central_Dhaka and Southwest_Khulna put the peak at +29 and +21
  days, which is not a physical response but an artefact of 60% missing data. **Only the pooled
  estimate should be used.**
* **Rain -> ECOSTRESS LST: not reliably estimable.** Raw pooled peak at lag -9 (r = 0.41); after
  deseasonalising, r = 0.08 - nothing. Restricting to daytime overpasses raises the raw peak to
  r = 0.52 at lag +13 (POWER: r = 0.49 at lag +12), but the deseasonalised value at that pair is 0.28
  at lag -18 (POWER: 0.26 at lag -22) - a negative lag, i.e. LST "leading" rain, which is physically
  impossible and is a sampling artefact: 230 daytime observations spread over 59 months cannot resolve
  a lag structure. Pooled raw r at lag 0 is 0.36 (GPM) / 0.43 (POWER), which drops to -0.00 / 0.07 once
  the annual cycle is removed. **Do not build a rain -> LST lag model on this dataset.**
* The full lag curves are saved in `eda\06_cc_curve_*.csv` (-30..+30 in steps of 1).

### 6.1 Monthly cross-correlation (the usable one)


##### Table 6.4 Monthly cross-correlation (lags -6..+6 months), monthly rain totals vs monthly means
|                                                    | region   |   best_lag_months |   max_corr |   corr_lag0 |   n |
|:---------------------------------------------------|:---------|------------------:|-----------:|------------:|----:|
| ('GPM monthly rain total', 'HLS NDVI')             | POOLED   |                 2 |      0.548 |       0.247 |  59 |
| ('GPM monthly rain total', 'SMAP SM (any pass)')   | POOLED   |                 1 |      0.589 |       0.559 |  59 |
| ('GPM monthly rain total', 'GRACE LWE')            | POOLED   |                 1 |      0.851 |       0.612 |  59 |
| ('POWER monthly rain total', 'HLS NDVI')           | POOLED   |                 2 |      0.558 |       0.251 |  59 |
| ('POWER monthly rain total', 'SMAP SM (any pass)') | POOLED   |                 1 |      0.594 |       0.528 |  59 |
| ('POWER monthly rain total', 'GRACE LWE')          | POOLED   |                 1 |      0.852 |       0.596 |  59 |

##### Table 6.5 Per-region best lag (months)
|                                                    |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   POOLED |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|:---------------------------------------------------|----------------:|----------------:|-------------------:|---------------------:|---------:|-----------------:|-----------------------:|-------------------:|
| ('GPM monthly rain total', 'GRACE LWE')            |               1 |               1 |                  1 |                    2 |        1 |                1 |                     -1 |                  1 |
| ('GPM monthly rain total', 'HLS NDVI')             |               0 |             nan |                  2 |                  nan |        2 |              nan |                      1 |                  1 |
| ('GPM monthly rain total', 'SMAP SM (any pass)')   |               1 |               0 |                  0 |                    2 |        1 |                1 |                      0 |                  2 |
| ('POWER monthly rain total', 'GRACE LWE')          |               1 |               1 |                  1 |                    2 |        1 |                1 |                     -1 |                  1 |
| ('POWER monthly rain total', 'HLS NDVI')           |               0 |             nan |                  2 |                  nan |        2 |              nan |                      1 |                  1 |
| ('POWER monthly rain total', 'SMAP SM (any pass)') |               1 |               0 |                  0 |                    2 |        1 |                1 |                      0 |                  2 |

##### Table 6.6 Per-region maximum correlation (monthly)
|                                                    |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   POOLED |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|:---------------------------------------------------|----------------:|----------------:|-------------------:|---------------------:|---------:|-----------------:|-----------------------:|-------------------:|
| ('GPM monthly rain total', 'GRACE LWE')            |           0.855 |           0.829 |              0.855 |                0.809 |    0.851 |            0.855 |                  0.509 |              0.855 |
| ('GPM monthly rain total', 'HLS NDVI')             |           0.542 |         nan     |              0.645 |              nan     |    0.548 |          nan     |                  0.771 |              0.654 |
| ('GPM monthly rain total', 'SMAP SM (any pass)')   |           0.605 |           0.334 |              0.778 |                0.559 |    0.589 |            0.635 |                  0.435 |              0.576 |
| ('POWER monthly rain total', 'GRACE LWE')          |           0.863 |           0.821 |              0.863 |                0.826 |    0.852 |            0.863 |                  0.443 |              0.863 |
| ('POWER monthly rain total', 'HLS NDVI')           |           0.484 |         nan     |              0.689 |              nan     |    0.558 |          nan     |                  0.766 |              0.678 |
| ('POWER monthly rain total', 'SMAP SM (any pass)') |           0.585 |           0.328 |              0.771 |                0.582 |    0.594 |            0.652 |                  0.403 |              0.596 |

**Lags of maximum correlation:**
* Monthly rain -> **SMAP SM: +1 month, r = 0.589** (pooled). Per region +0 to +2.
* Monthly rain -> **HLS NDVI: +2 months, r = 0.548** (pooled). NDVI lags the monsoon by about two
  months, which is the expected vegetation response. Only 4 of 7 regions have enough valid NDVI to
  fit; North_Rangpur (23 values), Northwest_Rajshahi (29) and South_Barishal (20) fall below the
  30-pair floor and return NaN.
* Monthly rain -> **GRACE LWE: +1 month, r = 0.851**. The strongest coupling in the dataset, and the
  only one that is spatially consistent (0.81-0.86 in 6 of 7 regions; Southeast_Chattogram 0.51).
* GPM and POWER give the same lags to within 0 months for every pair, which is a useful
  cross-validation of the rain side of the pipeline despite their amplitude disagreement.

## 7. Agreement between the two rainfall sources


##### Table 7.1 GPM vs POWER PRECTOTCORR (mm/day after /24), 12,292 paired region-days
|                   |   overall |      wet |      dry |
|:------------------|----------:|---------:|---------:|
| n                 | 12292     | 7427     | 4865     |
| mean_gpm          |     6.228 |    9.885 |    0.645 |
| mean_pw           |     8.532 |   13.374 |    1.14  |
| bias_pw_minus_gpm |     2.303 |    3.488 |    0.494 |
| rmse              |    12.176 |   15.308 |    4.101 |
| mae               |     5.633 |    8.687 |    0.972 |
| corr              |     0.712 |    0.681 |    0.602 |
| slope             |     0.772 |    0.716 |    0.781 |
| gpm_zero_days     |  5953     | 1863     | 4090     |
| pw_gt1_when_gpm0  |  1034     |  788     |  246     |

##### Table 7.2 Agreement by region
| region               |    n |   mean_gpm |   mean_pw |   bias_pw_minus_gpm |   rmse |   mae |   corr |   slope |   gpm_zero_days |   pw_gt1_when_gpm0 |
|:---------------------|-----:|-----------:|----------:|--------------------:|-------:|------:|-------:|--------:|----------------:|-------------------:|
| Central_Dhaka        | 1756 |      5.654 |     7.409 |               1.756 | 11.391 | 5.428 |  0.65  |   0.592 |             849 |                191 |
| North_Rangpur        | 1756 |      6.09  |     7.452 |               1.362 | 11.817 | 5.422 |  0.677 |   0.59  |             939 |                154 |
| Northeast_Sylhet     | 1756 |      9.6   |    14.23  |               4.63  | 19.015 | 9.413 |  0.671 |   0.838 |             725 |                 83 |
| Northwest_Rajshahi   | 1756 |      3.36  |     4.679 |               1.319 |  7.632 | 3.522 |  0.616 |   0.611 |             980 |                185 |
| South_Barishal       | 1756 |      6.028 |     9.745 |               3.717 | 11.327 | 5.631 |  0.801 |   1.013 |             844 |                179 |
| Southeast_Chattogram | 1756 |      8.145 |    10.129 |               1.985 | 12.532 | 6.242 |  0.777 |   0.773 |             810 |                113 |
| Southwest_Khulna     | 1756 |      4.721 |     6.077 |               1.356 |  7.951 | 3.776 |  0.749 |   0.77  |             806 |                129 |

Overall: **POWER is higher than GPM by +2.30 mm/day (37% of the GPM mean), RMSE 12.18, MAE 5.63,
r = 0.712, regression slope 0.772.** The wet season (Apr-Oct) carries bias +3.49 / RMSE 15.31 / r 0.681;
the dry season (Nov-Mar) bias +0.49 / RMSE 4.10 / r 0.602.

The aggregate numbers hide the important failure. **1,034 region-days have GPM = 0 but POWER > 1 mm/day**
(788 of them in the wet season, 246 in the dry). And the *ratio* of monthly totals is not stable:


##### Table 7.3 Monthly rainfall totals per region (mm), GPM vs POWER/24
| month   |   gpm_mm |   power_mm |   n |   ratio_power_over_gpm |
|:--------|---------:|-----------:|----:|-----------------------:|
| 2022-01 |    10.38 |      21.07 | 217 |                   2.03 |
| 2022-02 |    40.92 |      57.62 | 196 |                   1.41 |
| 2022-03 |     7.58 |      29.44 | 217 |                   3.88 |
| 2022-04 |   121.7  |     177.24 | 210 |                   1.46 |
| 2022-05 |   361.69 |     479.26 | 217 |                   1.33 |
| 2022-06 |   532.08 |     620.26 | 210 |                   1.17 |
| 2022-07 |   237.55 |     271.36 | 217 |                   1.14 |
| 2022-08 |   299.2  |     313.2  | 217 |                   1.05 |
| 2022-09 |   337.88 |     388.95 | 210 |                   1.15 |
| 2022-10 |   221.35 |     310.81 | 217 |                   1.4  |
| 2022-11 |     1.89 |      21.94 | 210 |                  11.62 |
| 2022-12 |     0.33 |       9.2  | 217 |                  27.58 |
| 2023-01 |     0.43 |       2.02 | 217 |                   4.73 |
| 2023-02 |     1.1  |       3.12 | 196 |                   2.82 |
| 2023-03 |    71.07 |     130.96 | 217 |                   1.84 |
| 2023-04 |    54.49 |     104.1  | 210 |                   1.91 |
| 2023-05 |   173.52 |     251.46 | 217 |                   1.45 |
| 2023-06 |   438.96 |     587.67 | 210 |                   1.34 |
| 2023-07 |   297.19 |     364.05 | 217 |                   1.22 |
| 2023-08 |   532.77 |     633.31 | 217 |                   1.19 |
| 2023-09 |   314.26 |     401.83 | 210 |                   1.28 |
| 2023-10 |   213.04 |     286.94 | 217 |                   1.35 |
| 2023-11 |    58.43 |      78.14 | 210 |                   1.34 |
| 2023-12 |    27.05 |      46.11 | 217 |                   1.7  |
| 2024-01 |     5.46 |      27.16 | 217 |                   4.97 |
| 2024-02 |    19.44 |      31.3  | 203 |                   1.61 |
| 2024-03 |    56.28 |     107.2  | 217 |                   1.9  |
| 2024-04 |    35.43 |      55.26 | 210 |                   1.56 |
| 2024-05 |   331.2  |     458.37 | 217 |                   1.38 |
| 2024-06 |   478.06 |     635.51 | 210 |                   1.33 |
| 2024-07 |   457.92 |     532.96 | 217 |                   1.16 |
| 2024-08 |   634.72 |     787.27 | 217 |                   1.24 |
| 2024-09 |   402.08 |     486.08 | 210 |                   1.21 |
| 2024-10 |   218.87 |     300.38 | 217 |                   1.37 |
| 2024-11 |     6.68 |      14.41 | 210 |                   2.16 |
| 2024-12 |     2.34 |       1.74 | 217 |                   0.74 |
| 2025-01 |     0.4  |       1.11 | 217 |                   2.75 |
| 2025-02 |     4.53 |       7.15 | 196 |                   1.58 |
| 2025-03 |     8.48 |      15.46 | 217 |                   1.82 |
| 2025-04 |   133.27 |     225.89 | 210 |                   1.69 |
| 2025-05 |   444.58 |     589.64 | 217 |                   1.33 |
| 2025-06 |   364.66 |     450.58 | 210 |                   1.24 |
| 2025-07 |   552.63 |     683.03 | 217 |                   1.24 |
| 2025-08 |   420.04 |     525.25 | 217 |                   1.25 |
| 2025-09 |   294.47 |     344.51 | 210 |                   1.17 |
| 2025-10 |   152.64 |     227.23 | 217 |                   1.49 |
| 2025-11 |    20.43 |      42.75 | 210 |                   2.09 |
| 2025-12 |     0.27 |       4.22 | 217 |                  15.58 |
| 2026-01 |     0.02 |       8.78 | 217 |                 396.39 |
| 2026-02 |     0.72 |       1.47 | 196 |                   2.04 |
| 2026-03 |   104.2  |     129.67 | 217 |                   1.24 |
| 2026-04 |   189.99 |     286.07 | 210 |                   1.51 |
| 2026-05 |   215.19 |     394.05 | 217 |                   1.83 |
| 2026-06 |   209.22 |     473.34 | 210 |                   2.26 |
| 2026-07 |   347    |     759.27 | 217 |                   2.19 |
| 2026-08 |   226.91 |     450.65 | 217 |                   1.99 |
| 2026-09 |   214.99 |     308.96 | 210 |                   1.44 |
| 2026-10 |    28.57 |      24.64 | 154 |                   0.86 |

##### Table 7.4 POWER/GPM monthly-total ratio, month x year
|   mon |   2022 |   2023 |   2024 |   2025 |   2026 |
|------:|-------:|-------:|-------:|-------:|-------:|
|     1 |   2.03 |   4.73 |   4.97 |   2.75 | 396.39 |
|     2 |   1.41 |   2.82 |   1.61 |   1.58 |   2.04 |
|     3 |   3.88 |   1.84 |   1.9  |   1.82 |   1.24 |
|     4 |   1.46 |   1.91 |   1.56 |   1.69 |   1.51 |
|     5 |   1.33 |   1.45 |   1.38 |   1.33 |   1.83 |
|     6 |   1.17 |   1.34 |   1.33 |   1.24 |   2.26 |
|     7 |   1.14 |   1.22 |   1.16 |   1.24 |   2.19 |
|     8 |   1.05 |   1.19 |   1.24 |   1.25 |   1.99 |
|     9 |   1.15 |   1.28 |   1.21 |   1.17 |   1.44 |
|    10 |   1.4  |   1.35 |   1.37 |   1.49 |   0.86 |
|    11 |  11.62 |   1.34 |   2.16 |   2.09 | nan    |
|    12 |  27.58 |   1.7  |   0.74 |  15.58 | nan    |

##### Table 7.5 Dry-season monthly totals (Dec/Jan/Feb), mm per region - GPM vs POWER
| month   |   gpm_mm |   power_mm |   n |   ratio_power_over_gpm |
|:--------|---------:|-----------:|----:|-----------------------:|
| 2022-01 |    10.38 |      21.07 | 217 |                   2.03 |
| 2022-02 |    40.92 |      57.62 | 196 |                   1.41 |
| 2022-12 |     0.33 |       9.2  | 217 |                  27.58 |
| 2023-01 |     0.43 |       2.02 | 217 |                   4.73 |
| 2023-02 |     1.1  |       3.12 | 196 |                   2.82 |
| 2023-12 |    27.05 |      46.11 | 217 |                   1.7  |
| 2024-01 |     5.46 |      27.16 | 217 |                   4.97 |
| 2024-02 |    19.44 |      31.3  | 203 |                   1.61 |
| 2024-12 |     2.34 |       1.74 | 217 |                   0.74 |
| 2025-01 |     0.4  |       1.11 | 217 |                   2.75 |
| 2025-02 |     4.53 |       7.15 | 196 |                   1.58 |
| 2025-12 |     0.27 |       4.22 | 217 |                  15.58 |
| 2026-01 |     0.02 |       8.78 | 217 |                 396.39 |
| 2026-02 |     0.72 |       1.47 | 196 |                   2.04 |

##### Table 7.6 Annual rainfall totals per region (mm) - GPM vs POWER/24 (2026 partial: Jan-Oct)
|   year |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|-------:|----------------:|----------------:|-------------------:|---------------------:|-----------------:|-----------------------:|-------------------:|
|   2022 |          1916.8 |          2313.4 |             4078.6 |               1020.6 |           1977.5 |                 2436.7 |             1464.5 |
|   2023 |          1940.6 |          2121.5 |             3399.9 |               1260.6 |           2139   |                 2677.4 |             1737.2 |
|   2024 |          2323.2 |          2248   |             3809.7 |               1375.2 |           2846.4 |                 3699.3 |             2237.5 |
|   2025 |          2288.1 |          2243.4 |             3264.8 |               1522.8 |           2381.6 |                 3120.5 |             1953.6 |
|   2026 |          1500.1 |          1846.5 |             2332.2 |                782.3 |           1251   |                 2415.4 |              978.9 |

**Where they agree:** May-Oct, ratio 1.05-1.50 in 2022-2025, correlation 0.68. The monsoon is
jointly measured well by both; GPM is systematically ~20% lower, which is a constant multiplicative
bias and is correctable.

**Where they diverge:** Nov-Feb, where the ratio spans 0.74-27.6x and reaches **396x in January 2026**
(GPM 0.02 mm over the whole month for the average region, POWER 8.78 mm). GPM's December total in 2022
was 0.33 mm per region; Dhaka's real December rainfall is of order 5-15 mm. Both sources may be low,
but **GPM is not a usable dry-season rainfall series without validation** - a model trained on it will
learn that Bangladesh has no rain for five months.

Annual totals are the sanity check that settles the /24 rescaling: GPM gives 1,021-4,079 mm/yr per
region and POWER/24 gives 1,320-5,503 mm/yr. Both are within the observed climatological range for
Bangladesh (Rajshahi ~1,400, Sylhet ~4,200). The raw POWER column would give 32,000-132,000 mm/yr.

### 7.1 The GPM final -> late run switch (2025-10-01)


##### Table 7.7 GPM final vs late run, mean daily precipitation by calendar month
|   mon |   ('mean', 'final') |   ('mean', 'late') |   ('count', 'final') |   ('count', 'late') |
|------:|--------------------:|-------------------:|---------------------:|--------------------:|
|     1 |               0.134 |              0.001 |                  868 |                 217 |
|     2 |               0.584 |              0.026 |                  791 |                 196 |
|     3 |               1.157 |              3.361 |                  868 |                 217 |
|     4 |               2.874 |              6.333 |                  840 |                 210 |
|     5 |              10.573 |              6.941 |                  868 |                 217 |
|     6 |              15.115 |              6.974 |                  840 |                 210 |
|     7 |              12.462 |             11.194 |                  868 |                 217 |
|     8 |              15.216 |              7.32  |                  868 |                 217 |
|     9 |              11.239 |              7.166 |                  840 |                 210 |
|    10 |               7.024 |              3.535 |                  651 |                 434 |
|    11 |               0.744 |              0.828 |                  630 |                 273 |
|    12 |               0.32  |              0.009 |                  651 |                 217 |

##### Table 7.8 GPM vs POWER monthly totals by calendar month, split at the final->late run switch (2025-10-01)
|                                  |   gpm_mm |   power_mm |   n_days |   power_over_gpm |
|:---------------------------------|---------:|-----------:|---------:|-----------------:|
| ('final (2022-01..2025-09)', 1)  |    16.67 |      51.36 |      124 |             3.08 |
| ('final (2022-01..2025-09)', 2)  |    66    |      99.2  |      113 |             1.5  |
| ('final (2022-01..2025-09)', 3)  |   143.41 |     283.07 |      124 |             1.97 |
| ('final (2022-01..2025-09)', 4)  |   344.89 |     562.49 |      120 |             1.63 |
| ('final (2022-01..2025-09)', 5)  |  1311    |    1778.73 |      124 |             1.36 |
| ('final (2022-01..2025-09)', 6)  |  1813.76 |    2294.02 |      120 |             1.26 |
| ('final (2022-01..2025-09)', 7)  |  1545.29 |    1851.39 |      124 |             1.2  |
| ('final (2022-01..2025-09)', 8)  |  1886.73 |    2259.03 |      124 |             1.2  |
| ('final (2022-01..2025-09)', 9)  |  1348.69 |    1621.38 |      120 |             1.2  |
| ('final (2022-01..2025-09)', 10) |   653.26 |     898.13 |       93 |             1.37 |
| ('final (2022-01..2025-09)', 11) |    67    |     114.5  |       90 |             1.71 |
| ('final (2022-01..2025-09)', 12) |    29.72 |      57.06 |       93 |             1.92 |
| ('late (2025-10..2026-10)', 1)   |     0.02 |       8.78 |       31 |           396.39 |
| ('late (2025-10..2026-10)', 2)   |     0.72 |       1.47 |       28 |             2.04 |
| ('late (2025-10..2026-10)', 3)   |   104.2  |     129.67 |       31 |             1.24 |
| ('late (2025-10..2026-10)', 4)   |   189.99 |     286.07 |       30 |             1.51 |
| ('late (2025-10..2026-10)', 5)   |   215.19 |     394.05 |       31 |             1.83 |
| ('late (2025-10..2026-10)', 6)   |   209.22 |     473.34 |       30 |             2.26 |
| ('late (2025-10..2026-10)', 7)   |   347    |     759.27 |       31 |             2.19 |
| ('late (2025-10..2026-10)', 8)   |   226.91 |     450.65 |       31 |             1.99 |
| ('late (2025-10..2026-10)', 9)   |   214.98 |     308.96 |       30 |             1.44 |
| ('late (2025-10..2026-10)', 10)  |   181.64 |     251.86 |       56 |             1.39 |
| ('late (2025-10..2026-10)', 11)  |    20.43 |      42.75 |       30 |             2.09 |
| ('late (2025-10..2026-10)', 12)  |     0.27 |       4.22 |       31 |            15.58 |

`run` is `final` for 2022-01-01..2025-09-30 (9,583 rows) and `late` for 2025-10-01..2026-11-09
(2,835 rows). The two never overlap, so they cannot be compared on the same days. The POWER comparison
in the table above is the substitute: in June, GPM drops from 453 mm/month (final-era mean) to 209 mm
(late era) while POWER drops only 573 -> 473; in August, GPM 472 -> 227 against POWER 565 -> 451. The
ratio POWER/GPM moves from 1.20-1.26 in the final era to 1.99-2.26 in the late era for Jun-Aug.
**Either the 2026 monsoon was genuinely much drier in a way POWER did not see, or the GPM late run is
biased low by roughly 40-50% in the wet season.** With only one late-run wet season in the record the
two hypotheses cannot be separated - treat the boundary as a regime change and always carry the `run`
column as a feature (or restrict training to the final-run era).

## 8. Extremes and anomalies


##### Table 8.1 Per-region p01/p99 extremes and counts (>= p99)
|                                           |    n |    p01 |    p99 |   n_ge_p99 |   n_le_p01 |     max | max_date   |    min | min_date   |
|:------------------------------------------|-----:|-------:|-------:|-----------:|-----------:|--------:|:-----------|-------:|:-----------|
| ('GPM', 'Central_Dhaka')                  | 1774 |  0     | 61.884 |         18 |        861 | 175.245 | 2023-10-05 |  0     | 2022-01-01 |
| ('GPM', 'North_Rangpur')                  | 1774 |  0     | 79.063 |         18 |        953 | 172.24  | 2023-06-15 |  0     | 2022-01-01 |
| ('GPM', 'Northeast_Sylhet')               | 1774 |  0     | 96.098 |         18 |        737 | 194.97  | 2022-06-18 |  0     | 2022-01-01 |
| ('GPM', 'Northwest_Rajshahi')             | 1774 |  0     | 42.982 |         18 |        993 |  85.25  | 2024-07-11 |  0     | 2022-01-01 |
| ('GPM', 'South_Barishal')                 | 1774 |  0     | 67.571 |         18 |        855 | 134.275 | 2022-10-24 |  0     | 2022-01-01 |
| ('GPM', 'Southeast_Chattogram')           | 1774 |  0     | 99.682 |         18 |        818 | 173.6   | 2023-08-06 |  0     | 2022-01-01 |
| ('GPM', 'Southwest_Khulna')               | 1774 |  0     | 53.739 |         18 |        817 | 112.45  | 2022-10-24 |  0     | 2022-01-01 |
| ('SMAP SM (any)', 'Central_Dhaka')        | 1053 |  0.185 |  0.539 |        116 |         11 |   0.539 | 2022-01-23 |  0.124 | 2025-03-17 |
| ('SMAP SM (any)', 'North_Rangpur')        | 1255 |  0.192 |  0.506 |        236 |         13 |   0.506 | 2022-01-30 |  0.174 | 2025-10-31 |
| ('SMAP SM (any)', 'Northeast_Sylhet')     | 1053 |  0.119 |  0.592 |        133 |         11 |   0.592 | 2022-05-14 |  0.057 | 2025-03-09 |
| ('SMAP SM (any)', 'Northwest_Rajshahi')   | 1252 |  0.158 |  0.5   |         16 |         13 |   0.5   | 2022-02-07 |  0.128 | 2025-05-08 |
| ('SMAP SM (any)', 'South_Barishal')       | 1202 |  0.169 |  0.569 |        139 |         13 |   0.569 | 2022-01-04 |  0.125 | 2025-03-05 |
| ('SMAP SM (any)', 'Southeast_Chattogram') | 1012 |  0.066 |  0.569 |         13 |         11 |   0.569 | 2022-02-10 |  0.037 | 2024-11-25 |
| ('SMAP SM (any)', 'Southwest_Khulna')     | 1258 |  0.186 |  0.586 |        127 |         13 |   0.586 | 2022-01-02 |  0.15  | 2025-05-16 |
| ('ECOSTRESS LST', 'Central_Dhaka')        |  142 | 15.066 | 47.966 |          2 |          2 |  50.75  | 2022-08-09 | 11.51  | 2026-01-04 |
| ('ECOSTRESS LST', 'North_Rangpur')        |  134 | 11.22  | 43.164 |          2 |          2 |  45.39  | 2025-09-20 |  9.99  | 2026-01-04 |
| ('ECOSTRESS LST', 'Northeast_Sylhet')     |  126 | 15.487 | 45.57  |          2 |          2 |  54.67  | 2024-07-25 | 15.01  | 2024-01-05 |
| ('ECOSTRESS LST', 'Northwest_Rajshahi')   |  137 | 11.898 | 42.854 |          2 |          2 |  46.41  | 2024-07-17 | 10.97  | 2026-01-04 |
| ('ECOSTRESS LST', 'South_Barishal')       |  123 | 14.254 | 40.921 |          2 |          2 |  42.63  | 2022-10-08 | 12.51  | 2026-01-04 |
| ('ECOSTRESS LST', 'Southeast_Chattogram') |  140 | 15.443 | 41.674 |          2 |          2 |  44.69  | 2023-05-30 | 14.89  | 2024-12-13 |
| ('ECOSTRESS LST', 'Southwest_Khulna')     |  123 | 14.289 | 42.5   |          2 |          2 |  46.01  | 2022-10-08 | 12.09  | 2026-01-04 |

The `n_ge_p99` column in that table is tautological (1% of n by construction, so 18 for a
1,774-day GPM series and 2 for a ~130-observation LST series). Use the fixed-threshold counts instead:


##### Table 8.2 GPM rainfall threshold exceedance counts per region (1,774 days)
|    | region               |   days_ge_10 |   days_ge_25 |   days_ge_50 |   days_ge_100 |   days_ge_150 |   days_eq_0 |   max_mm | max_date   |   annual_mean_mm |
|---:|:---------------------|-------------:|-------------:|-------------:|--------------:|--------------:|------------:|---------:|:-----------|-----------------:|
|  0 | Central_Dhaka        |          288 |          118 |           34 |             5 |             2 |         861 |   175.25 | 2023-10-05 |           2051.2 |
|  1 | North_Rangpur        |          282 |          142 |           45 |             6 |             1 |         953 |   172.24 | 2023-06-15 |           2216.6 |
|  2 | Northeast_Sylhet     |          466 |          208 |           71 |            16 |             5 |         737 |   194.97 | 2022-06-18 |           3474.3 |
|  3 | Northwest_Rajshahi   |          190 |           65 |           11 |             0 |             0 |         993 |    85.25 | 2024-07-11 |           1226.6 |
|  4 | South_Barishal       |          302 |          121 |           41 |             7 |             0 |         855 |   134.28 | 2022-10-24 |           2180.1 |
|  5 | Southeast_Chattogram |          377 |          178 |           63 |            18 |             2 |         818 |   173.6  | 2023-08-06 |           2952.5 |
|  6 | Southwest_Khulna     |          243 |           93 |           24 |             1 |             0 |         817 |   112.45 | 2022-10-24 |           1722.6 |

##### Table 8.3 7-region-mean daily rainfall, upper tail
|   threshold_mm |   n_days |
|---------------:|---------:|
|             10 |      391 |
|             20 |      152 |
|             30 |       58 |
|             40 |       26 |
|             50 |       13 |
|             60 |        6 |
|             80 |        1 |

##### Table 8.4 Top-5 daily rainfall events per region (GPM)
|   rank |   Central_Dhaka |   North_Rangpur |   Northeast_Sylhet |   Northwest_Rajshahi |   South_Barishal |   Southeast_Chattogram |   Southwest_Khulna |
|-------:|----------------:|----------------:|-------------------:|---------------------:|-----------------:|-----------------------:|-------------------:|
|      1 |          175.25 |          172.24 |             194.97 |                85.25 |           134.28 |                 173.6  |             112.45 |
|      2 |          152.44 |          147.27 |             187.03 |                80.55 |           121.73 |                 171.3  |              99.89 |
|      3 |          148.91 |          147.07 |             163.58 |                70.23 |           116.92 |                 144.59 |              88.73 |
|      4 |          143.93 |          129.57 |             159.63 |                69.78 |           116.47 |                 139.57 |              84.59 |
|      5 |          122.31 |          118.36 |             151.4  |                67.01 |           114.75 |                 138.73 |              82.81 |

##### Table 8.5 Top-15 most widespread heavy-rain days (ranked by 7-region mean)
|    | date       |   mean_mm_across_7_regions |   n_regions_gt_50mm |   max_region_mm | argmax_region        |
|---:|:-----------|---------------------------:|--------------------:|----------------:|:---------------------|
|  0 | 2024-05-27 |                      84.58 |                   5 |          171.3  | Southeast_Chattogram |
|  1 | 2024-07-01 |                      78.94 |                   5 |          142.19 | Northeast_Sylhet     |
|  2 | 2022-10-24 |                      75.85 |                   4 |          152.44 | Central_Dhaka        |
|  3 | 2022-06-17 |                      70.52 |                   3 |          159.63 | Northeast_Sylhet     |
|  4 | 2025-05-29 |                      63.2  |                   4 |          124.64 | Southeast_Chattogram |
|  5 | 2023-10-05 |                      62.94 |                   4 |          175.25 | Central_Dhaka        |
|  6 | 2023-08-07 |                      59.9  |                   4 |          108.43 | South_Barishal       |
|  7 | 2023-08-06 |                      57.56 |                   3 |          173.6  | Southeast_Chattogram |
|  8 | 2024-08-02 |                      57.29 |                   4 |           88.73 | Southwest_Khulna     |
|  9 | 2024-08-01 |                      56.78 |                   3 |          119.73 | Southeast_Chattogram |
| 10 | 2023-06-15 |                      53.66 |                   2 |          172.24 | North_Rangpur        |
| 11 | 2024-09-15 |                      51    |                   4 |           88.15 | South_Barishal       |
| 12 | 2024-06-18 |                      50.28 |                   3 |          129.57 | North_Rangpur        |
| 13 | 2025-06-01 |                      49.09 |                   3 |          138.73 | Southeast_Chattogram |
| 14 | 2022-06-16 |                      48.5  |                   3 |          144.25 | Northeast_Sylhet     |

**Largest events.** The most widespread heavy-rain day in the record is **2024-05-27** (7-region
mean 84.6 mm/day, 5 of 7 regions above 50 mm, peak 171.3 mm at Southeast_Chattogram) - consistent with
the pre-monsoon Cyclone Remal landfall period. Second is **2024-07-01** (78.9 mm mean), third
**2022-10-24** (75.9 mm mean, peak 152.4 mm at Central_Dhaka). The largest single region-day value is
**194.97 mm at Northeast_Sylhet on 2022-06-18**, the wettest region in the country by a factor of ~2 in
annual total (3,474 mm/yr vs 1,227 mm/yr for Northwest_Rajshahi).

Regional exposure is very unequal: Northeast_Sylhet has 71 days >= 50 mm and 5 days >= 150 mm;
Northwest_Rajshahi has 11 days >= 50 mm and **zero** days >= 100 mm. A single national extreme-event
threshold would be meaningless - use per-region percentiles.


##### Table 8.6 GRACE LWE linear trend per region (57 monthly values, 2022-01..2026-09)
|    | region               |   mascon |   trend_cm_per_yr |   se |   mean_cm |   sd_cm |   mean_uncertainty_cm |
|---:|:---------------------|---------:|------------------:|-----:|----------:|--------:|----------------------:|
|  0 | Central_Dhaka        |     1321 |              3.22 | 1.92 |      9.6  |   20.04 |                  5.44 |
|  1 | North_Rangpur        |     1214 |             -1.85 | 1.92 |    -44.73 |   19.65 |                  3.83 |
|  2 | Northeast_Sylhet     |     1321 |              3.22 | 1.92 |      9.6  |   20.04 |                  5.44 |
|  3 | Northwest_Rajshahi   |     1320 |              2.67 | 1.62 |    -11.63 |   16.91 |                  4.4  |
|  4 | South_Barishal       |     1321 |              3.22 | 1.92 |      9.6  |   20.04 |                  5.44 |
|  5 | Southeast_Chattogram |     1431 |             -1.67 | 0.57 |     -7.99 |    6.26 |                  4.26 |
|  6 | Southwest_Khulna     |     1321 |              3.22 | 1.92 |      9.6  |   20.04 |                  5.44 |

##### Table 8.7 SMAP am soil moisture, Jan-Feb mean by year (dry-season drift)
|   date |   jan_feb_mean_sm |
|-------:|------------------:|
|   2022 |            0.4668 |
|   2023 |            0.4516 |
|   2024 |            0.3947 |
|   2025 |            0.3392 |
|   2026 |            0.3418 |

## 9. Data-quality verdict per dataset

`usable_pct` = share of expected region-days (at each dataset's own cadence) carrying a valid value
for the primary variable. See `eda\09_verdict.csv`.


##### Table 9.1 Data-quality verdict
|    | dataset                  | cadence         |   region_days |   valid |   usable_pct | impute                                                                     | never_interpolate                                                                   |
|---:|:-------------------------|:----------------|--------------:|--------:|-------------:|:---------------------------------------------------------------------------|:------------------------------------------------------------------------------------|
|  0 | GPM IMERG precipitation  | daily           |         12418 |   12418 |        100   | none needed; late-run period (2025-10-01+) is a different retrieval        | do not gap-fill; do not splice final and late run without a run indicator           |
|  1 | POWER weather (8 params) | daily           |         12418 |   12292 |         99   | 3 trailing days per region; SW_DWN 86 days/region (2026-08-01..2026-10-22) | PRECTOTCORR rescaled /24 - never mix raw and rescaled columns                       |
|  2 | SMAP soil moisture       | 2 passes/day    |         24206 |    9592 |         39.6 | ~60% of pass-days; model as irregular observations, not a daily grid       | no linear interpolation across the 60% gap structure; ceiling values are clipped    |
|  3 | ECOSTRESS LST            | per-overpass    |          2819 |     933 |         33.1 | cannot be imputed at 92.5% day-level missing                               | never interpolate LST in time; overpass hour varies 0-23 local                      |
|  4 | HLS NDVI/NDMI            | monthly attempt |           413 |     220 |         53.3 | no - use as sparse labels only                                             | never interpolate; 19% of values come from <=5 valid pixels, 32% from <10% coverage |
|  5 | GRACE LWE                | monthly         |           399 |     399 |        100   | none within 2022-01..2026-09                                               | do not upsample to daily; only 4 independent mascon series exist                    |
|  6 | SRTM terrain             | static          |             7 |       7 |        100   | none                                                                       | static covariate                                                                    |

### 9.1 What each dataset can actually support

| dataset | usable fraction | can be imputed? | should never be interpolated |
|---|---|---|---|
| GPM precipitation | **100%** of region-days | nothing to impute; the dry-season and run-era problems are bias, not gaps | do not gap-fill (there are no gaps); do not splice final+late silently |
| POWER weather | **99.0%** of region-days (SW_DWN 94.3%) | 3 trailing days/region and 83 SW_DWN days/region - trivial | do not mix raw and /24 PRECTOTCORR; do not fill SW_DWN across the 2026-08..10 block without a flag |
| SMAP soil moisture | **39.6%** of pass-days; **35.1-44.9%** of am region-days | the mask is deterministic in space, so interpolation is really extrapolation into permanently unmapped cells | no linear/time interpolation; the ceiling values are censored, not measurements |
| ECOSTRESS LST | **33.1%** of overpass rows; **7.45%** of region-days | no - 92.55% of region-days have nothing | never interpolate in time; never pool day and night overpasses |
| HLS NDVI/NDMI | **53.3%** of attempt rows; **1.77%** of region-days | no | never interpolate; 19% of values come from <=5 pixels |
| GRACE LWE | **100%** of months (2022-01..2026-09) | nothing to impute inside the span | do not upsample to daily or weekly; only 4 independent series exist |
| SRTM terrain | 7/7 regions | n/a | static covariate, constant in time |

## 10. Modelling implications

**1. Build two feature tiers, not one wide table.** Tier A (daily, no imputation): GPM rainfall, POWER
T2M/T2M_MAX/T2M_MIN/RH2M/WS2M/SW_DWN/PS. Tier B (observation-time rows): SMAP, ECOSTRESS, HLS - join
them to the daily grid as *events* with an explicit `observed` indicator, or aggregate to weekly/monthly
means with a `n_obs` count column. A 7 x 1,774 daily matrix with SMAP forward-filled is 60% invented
data and will train a model on the imputer's behaviour.

**2. Fix the POWER precipitation units before anything else.** `PRECTOTCORR = PRECTOTCORR_raw / 24`.
Every value is an exact multiple of 0.24; the raw column yields 32,000-132,000 mm/yr. Keep both columns
and name them explicitly so a later join cannot reintroduce the raw one.

**3. Choose one rainfall source and declare it.** GPM and POWER agree at r = 0.71 with a 37% mean bias
in the monsoon and up to 27.6x disagreement in Nov-Feb (396x in Jan 2026). Recommended: GPM as the primary (physically
bounded, 100% coverage) with POWER PRECTOTCORR as a second channel and their difference as a feature;
never average them.

**4. Treat 2025-10-01 as a regime boundary.** GPM switches from final to late run there and the late
run looks 40-50% low in Jun-Aug relative to POWER. Options: (a) train and test only on
2022-01-01..2025-09-30 (1,369 days, 9,583 rows) and treat 2025-10+ as out-of-sample; (b) keep all data
and add `is_late_run` as a feature; (c) re-download the late period as final once available. Do not
ignore it - any model with a time trend will attribute the run change to climate.

**5. Split by time blocks, never at random.** Decorrelation times: GPM rainfall 4 days, POWER rainfall
7 days, SW_DWN 12 days, T2M/RH2M/PS/SMAP >30 days. Use forward-chaining (expanding-window) CV with an
embargo of at least 30 days for daily targets and at least 12 months for monthly targets. Effective
sample sizes at n = 1,774 are 15 (T2M), 28 (PS), 66 (RH2M), 265 (WS2M), 392-397 (precip, SW_DWN),
721 (GPM). At monthly scale n = 59 is effectively 6-20. A random 80/20 split on daily rows will report
R2 near 1.0 for T2M from one day to the next.

**6. Do not treat the 7 regions as 7 independent samples for GRACE.** Four of them share mascon 1321
byte-for-byte. Either collapse to the 4 distinct mascon series, or multiply the LWE by the per-region
`cri_scale_factor` (which is currently unapplied) to get genuine regional differentiation. Region-level
cross-validation on GRACE will leak.

**7. Model rainfall as a two-part process.** 48.6% of GPM region-days are exactly 0.0. Fit
P(rain > 0) and E[amount | rain > 0] separately (or a Tweedie/gamma GLM). Squared-error metrics on raw
mm/day are dominated by getting the zeros right and say nothing about the tail.

**8. Do not expect daily rainfall to predict soil moisture.** Deseasonalised r = 0.14-0.21 at lag 0-1.
The 0.30-0.39 raw correlation is the shared annual cycle. Useful SM predictors will need antecedent
precipitation accumulated over weeks (API), not same-day rain. And in Nov-Mar the SM-rain correlation is
-0.09, so the dry-season SM signal is irrigation/groundwater-driven and needs a different feature set.

**9. Watch two time trends that may be artefacts.** (a) Dry-season SMAP soil moisture falls
monotonically from 0.467 (Jan-Feb 2022) to 0.342 (Jan-Feb 2026), a -0.031/yr drift on a variable whose
interannual range should be small; it is either a real groundwater decline or sensor drift, and it will
dominate any tree model that sees a time index. (b) GPM annual totals fall from ~2,300 mm (2025) to
~1,500 mm (2026, Jan-Oct) in Central_Dhaka, which is partly the run change. De-trend or hold out.

**10. LST needs a daytime filter and an hour feature.** Only 230 of 933 valid LST values are daytime
(local 09-16) and the day/night means differ by 7.7 C. Either restrict to daytime (and accept n = 230
over 59 months) or include `hour_local` as a covariate and let the model separate the populations. Do
not compute an "LST anomaly" from the pooled sample.

**11. Drop or heavily caveat HLS NDVI.** 220 valid values across 59 months x 7 regions, 19% of them
from <=5 of 225 pixels, and 3 of 7 regions have fewer than 30 observations. It is not a vegetation time
series. Usable as (i) a monthly label for the 4 regions with >=30 values (Central_Dhaka,
Northeast_Sylhet, Southeast_Chattogram, Southwest_Khulna) or (ii) a seasonal-mean sanity check. The lag-2-month NDVI
response to rainfall (r = 0.55) is the one robust relationship in it.

**12. Encode "missing" rather than imputing for SMAP.** The 60% gap is `surface_flag == 2047` in
928-1,099 of 1,774 days per region - a permanent property of the cell, not a transient outage. If SMAP
is a feature, add `smap_valid` and let the model learn the masked regime; if SMAP is the target, train
only on valid retrievals. Either way, do not let a KNN/linear imputer invent values in permanently
unmapped cells.

**13. Cap-aware handling of SMAP extremes.** 10.1-18.8% of valid values in five of the seven regions sit
on a single repeated maximum. Treat the top of the distribution as right-censored (Tobit, or clip the
target and add a `at_ceiling` flag). Percentile-based extreme detection on SMAP returns the clip, not
weather.

**14. Regional stratification is required, not optional.** Seasonal rainfall amplitude ranges 7.97
(Northwest_Rajshahi) to 27.97 mm/day (Northeast_Sylhet); annual totals 1,227 to 3,474 mm; days >= 50 mm
range from 11 to 71. Pool all 7 regions only with region fixed effects or per-region normalisation.

**15. Provenance is clean.** Every row carries `source_file` (and `product`/`version` for GPM), so any
model input can be traced back to a granule. Keep those columns through the feature pipeline - they are
the only way to audit the 2026-10 SMAP `_001`/`_002` re-processing or the GPM run change later.

## 11. Reproducing this analysis

Scripts (all in `C:\Users\muhai\Desktop\BIG hero 6\Data\_report\eda\`):

```
# 1. inventory, dtypes, missingness matrices, quantiles, plausibility, seasonality
"C:\Users\muhai\Desktop\BIG hero 6\Data\.venv\Scripts\python.exe" -I eda_part1.py

# 2. autocorrelation, cross-correlation, GPM-vs-POWER agreement, extremes, verdict
"C:\Users\muhai\Desktop\BIG hero 6\Data\.venv\Scripts\python.exe" -I eda_part2.py

# 3. gap decomposition, annual totals, threshold extremes, sensor diagnostics
"C:\Users\muhai\Desktop\BIG hero 6\Data\.venv\Scripts\python.exe" -I eda_part3.py

# 4. assemble this document from the generated tables
"C:\Users\muhai\Desktop\BIG hero 6\Data\.venv\Scripts\python.exe" -I build_eda_md.py
```

`-I` isolates the interpreter from the current directory. The scripts only read the source CSVs and
only write into `Data\_report\eda\`. Versions used: Python 3.13.9, pandas 3.1.1, numpy 2.5.4,
matplotlib 3.11.2 (scikit-learn is *not* installed in this venv; nothing here needs it).

Output tables (`Data\_report\eda\`):

| file | contents |
|---|---|
| `01_inventory.csv`, `01_dtypes_nulls.csv` | shapes, spans, duplicate keys, per-column null counts |
| `02_missingness_overall.csv` | % missing / % days covered per series |
| `02_monthyear_*.csv` | month x year missingness matrices (gpm, power_prec, smap_am, smap_any, ecostress, hls, grace) |
| `02_hls_valid_obs_per_month.csv`, `02_ecostress_overpass_per_month.csv` | sparse-dataset cadence |
| `02b_gap_decomposition_*.csv` | structural vs data gaps (SMAP, ECOSTRESS, HLS, POWER) |
| `03_quantiles_by_region.csv` | p0/p1/p5/p25/p50/p75/p95/p99/p100 per variable per region |
| `03_plausibility_flags.csv`, `03_region_grid.csv` | 14 physical rules, per-region flag counts |
| `04_monthly_climatology.csv`, `04_seasonality_amplitude.csv` | annual cycle, peak month, amplitude |
| `05_acf_daily_*.csv`, `05_acf_monthly*.csv` | ACF curves, per-region lag-1, effective sample size |
| `06_crosscorr_daily.csv`, `06_crosscorr_monthly.csv`, `06_cc_curve_*.csv` | lag scans -30..+30 days and -6..+6 months |
| `07_agreement_*.csv`, `07_monthly_totals.csv`, `07_gpm_run_by_month.csv`, `07b_*.csv` | GPM vs POWER bias/RMSE/correlation, monthly and annual totals, run-era comparison |
| `08_extremes_p99_by_region.csv`, `08_top5_rainfall_per_region.csv`, `08_top15_widespread_rainfall_days.csv` | extremes |
| `08_smap_ceiling_clamp.csv`, `08b_*.csv` | sensor-specific diagnostics: SMAP ceiling by pass, retrieval-quality distribution, dry-season drift, ECOSTRESS diurnal cycle, GRACE trend, rainfall thresholds, GPM zero structure, SM-rain seasonal correlation |
| `09_verdict.csv` | per-dataset usable fraction and imputation policy |

Nothing in the source data was modified. No file outside `Data\_report\` was written.
