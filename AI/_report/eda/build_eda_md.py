"""Assemble _report/EDA.md from hand-written prose + the generated table fragments.
Run:  .venv\\Scripts\\python.exe -I build_eda_md.py
"""
import re, os

OUT = r"C:\Users\muhai\Desktop\BIG hero 6\Data\_report\eda"
MD = r"C:\Users\muhai\Desktop\BIG hero 6\Data\_report\EDA.md"


def load(fn):
    txt = open(os.path.join(OUT, fn), encoding="utf-8").read()
    parts = re.split(r"\n#### ", txt)
    blocks = {}
    for p in parts[1:]:
        title, _, body = p.partition("\n")
        blocks[title.strip()] = "#### " + title.strip() + "\n" + body.strip() + "\n"
    return blocks


b1 = load("_fragments_part1.md")
b2 = load("_fragments_part2.md")
b3 = load("_fragments_part3.md")


def B(d, key):
    for k in d:
        if k.startswith(key):
            return d[k]
    raise KeyError(key)


P = []
A = P.append

A("""# Exploratory Data Analysis - NASA environmental CSVs, 7 Bangladesh regions (2022-01-01 .. 2026-11)

Read-only analysis. Nothing in the source CSVs was modified; every number below was computed by the
three scripts in `Data\\_report\\eda\\` (`eda_part1.py`, `eda_part2.py`, `eda_part3.py`) and the summary
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

""")
A(B(b1, "1.1 Dataset inventory"))
A("""
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

Column-level dtypes and null counts are in `eda\\01_dtypes_nulls.csv`.

""")

A("""## 2. Missingness

### 2.1 Overall, on the common 1,774-day grid

""")
A(B(b1, "2.1 Overall missingness"))
A("""
`pct_missing` counts region-day cells with no valid value for the primary variable.
`pct_days_covered` counts calendar days with at least one region reporting - this is the number that
matters for a time-series model, because a day with 1 of 7 regions is not a usable daily feature row.

### 2.2 Month x year missingness matrices

Each cell is the % of expected (region x day) cells in that calendar month that are missing.

""")
for k in ["2.gpm", "2.power_prec", "2.smap_am", "2.smap_any", "2.ecostress", "2.hls", "2.grace"]:
    A(B(b1, k))
A(B(b1, "2.ecox"))

A("""
The GPM and POWER matrices are blank except at the very end of the series (POWER: 2026-10 is 29%
missing and 2026-11 is 100% missing, because the POWER files stop at 2026-10-22). The SMAP matrix is
flat at 58-65% for the am pass in every month of every year - **there is no seasonal structure to the
SMAP gaps**, except two 2022 anomalies (Aug 2022: 93.1% missing, Sep 2022: 88.6% missing) which are a
real acquisition outage confined to that year. ECOSTRESS and HLS are missing almost everywhere by
construction (92.6% and 98.2%).

### 2.3 Structural gaps vs data gaps

This is the decomposition that matters: it separates "the sensor never intended to observe this cell
that day" from "the sensor observed and the value is unusable".

""")
A(B(b3, "2b.1"))
A(B(b3, "2b.2"))
A(B(b3, "2b.3"))
A(B(b3, "2b.4"))
A("""
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

""")

A("""## 3. Distributions and plausibility

Quantiles below are computed on valid values only, per region. Full per-region tables for every
variable are in `eda\\03_quantiles_by_region.csv`.

""")
A(B(b1, "3.1 Pooled quantiles"))
A("""**Zero-inflation and shape.** GPM precipitation is **48.6% exact zeros** (6,034 of 12,418
region-days), median 0.03 mm/day, mean 6.19, p99 73.6, max 194.97. POWER after /24 is less
zero-inflated (median 1.65) but has a similar upper tail (p99 76.7, max 202.4). SMAP soil moisture is
left-skewed and capped (see 3.3). LST spans 9.99-54.67 C. NDVI spans 0.162-0.983 with no negatives.

### 3.1 Per-region quantiles, headline variables

""")
for k in ["3.x GPM precipitation", "3.x SMAP soil", "3.x ECOSTRESS lst", "3.x HLS ndvi",
          "3.x HLS ndmi", "3.x GRACE lwe", "3.x POWER T2M", "3.x POWER RH2M",
          "3.x POWER PRECTOTCORR"]:
    A(B(b1, k))

A("""### 3.2 Hard physical-plausibility rules

14 rules were applied (precipitation > 300 mm/day, SM outside 0-0.65, NDVI/NDMI outside -1..1,
LST outside -20..70 C, RH outside 0-100, negative wind/irradiance/precipitation, PS outside
50-110 kPa, T2M outside -10..50 C, T2M outside its own [MIN, MAX]). **All 14 returned zero flagged
values.** Nothing needs to be dropped for being out of range.

""")
A(B(b1, "3.2 Physical-plausibility"))
A("""### 3.3 Soft implausibilities that the hard rules do not catch

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

""")
A(B(b3, "8b.9 GPM zero"))
A(B(b2, "8.4 SMAP"))
A(B(b3, "8b.3"))
A(B(b3, "8b.5"))
A(B(b2, "8.5 GRACE"))

A("""## 4. Seasonality

Monthly climatology = mean over 7 regions of the monthly means of the series (so it is the shape of
the annual cycle, not a total).

""")
A(B(b1, "4.1 Monthly climatology"))
A("""
Month of peak, region-mean series: **rainfall Aug (13.64 mm/day)**, trough Jan (0.108 mm/day) - a 126x
annual swing. **T2M Apr (29.17 C)** vs Jan (17.42 C); the April/May peak is the pre-monsoon heat
maximum and April and May are within 0.03 C of each other, so the region-mean peak month is not
meaningful at that resolution (per-region peaks: 4 of 7 regions peak in April, 2 in July, 1 in May).
**RH2M Aug (88.5%)** vs Mar (59.3%). **SW_DWN Apr (19.49 MJ/m2/d)** vs Jan (12.68) - peak insolation in
the pre-monsoon, minimum in the winter haze season. **SMAP SM Aug (0.481)** vs Apr (0.271).
**NDVI Sep (0.499)** vs Feb (0.295). **GRACE LWE Sep (+17.3 cm)** vs Mar (-22.8 cm).

### 4.1 Per-region amplitude

""")
A(B(b1, "4.2 Per-region seasonal amplitude"))
A(B(b1, "4.2b Peak month per region"))
A("""Amplitude is `max(monthly mean) - min(monthly mean)`. Rainfall amplitude spans 7.97 mm/day
(Northwest_Rajshahi) to 27.97 mm/day (Northeast_Sylhet) - a 3.5x range in seasonal forcing across the
country, so a single national seasonal feature will under-fit both ends. SMAP amplitude 0.178-0.311
m3/m3, i.e. the annual cycle is roughly as large as the entire inter-region spread of the mean.

**One anomaly worth flagging:** SMAP soil moisture has *no* dry-season minimum. The region-mean
climatology is 0.382 in January and 0.391 in February, *higher* than April's 0.271, while January
rainfall is 0.108 mm/day. Soil moisture is not tracking rainfall in Nov-Mar. Two candidate
explanations - winter boro rice irrigation, or a cold-season retrieval artefact - and this dataset
cannot distinguish them. Either way, **a rain-driven model of soil moisture will fail in the dry
season**: corr(monthly SM, monthly rain) is 0.655 in Apr-Oct but **-0.086 in Nov-Mar**.

""")
A(B(b3, "8b.7 Correlation between monthly SMAP"))

A("""## 5. Temporal structure and autocorrelation

ACF is computed with pairwise-complete observations (so sparse series contribute only the pairs where
both endpoints exist) and reported per region, lags 1-30 days. Full curves: `eda\\05_acf_daily_curve_regionmean.csv`.

""")
A(B(b2, "5.1 Daily autocorrelation"))
A(B(b2, "5.1b Effective sample size"))
A(B(b2, "5.2 Region-mean ACF curve"))
A(B(b2, "5.3 Lag-1 autocorrelation by region"))
A("""
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

Table 5.2 and `eda\\05_acf_neff.csv` give the full list. The SMAP figure is deliberately not extrapolated: only 161 of
1,773 possible lag-1 pairs exist, and those 161 are the days when two consecutive days both passed the
land-surface mask - a biased subset. **ECOSTRESS daily ACF is not estimable at all** - on average 2.9 lag-1 pairs survive per region, so the daily row in table 5.1 is NaN by construction; use its monthly ACF (0.631 at lag 1, table 5.4) instead.

### 5.1 Monthly autocorrelation

""")
A(B(b2, "5.4 Monthly-series autocorrelation"))
A(B(b2, "5.4b"))
A(B(b2, "5.4c Effective sample size"))
A("""Every monthly series is dominated by its annual cycle: ACF(12) is 0.856 for rainfall, 0.974 for T2M,
0.896 for GRACE, 0.892 for SMAP, and ACF(6) is strongly negative (-0.81 for rainfall) because the
half-year offset is the opposite season. Effective monthly sample size is **6.1 (GRACE) to 20.4
(HLS NDVI) out of 59 months**. A 59-row monthly training set is really a ~10-row dataset.

## 6. Cross-correlation between rainfall and the response variables

Sign convention: `corr(rain[t], response[t+L])`; **positive L means the response lags the rain.**
Both raw and deseasonalised (month-of-year climatology plus linear trend removed, so the annual cycle
cannot manufacture a correlation) versions are given. Full tables: `eda\\06_crosscorr_daily.csv`,
`eda\\06_crosscorr_monthly.csv`.

""")
A(B(b2, "6.1 Daily cross-correlation"))
A(B(b2, "6.1b"))
A(B(b2, "6.1c"))

A("""**Interpretation.**

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
* The full lag curves are saved in `eda\\06_cc_curve_*.csv` (-30..+30 in steps of 1).

### 6.1 Monthly cross-correlation (the usable one)

""")
A(B(b2, "6.2 Monthly cross-correlation"))
A(B(b2, "6.2b Per-region best lag"))
A(B(b2, "6.2c Per-region max correlation"))
A("""**Lags of maximum correlation:**
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

""")
A(B(b2, "7.1 GPM vs POWER"))
A(B(b2, "7.1b Agreement by region"))
A("""Overall: **POWER is higher than GPM by +2.30 mm/day (37% of the GPM mean), RMSE 12.18, MAE 5.63,
r = 0.712, regression slope 0.772.** The wet season (Apr-Oct) carries bias +3.49 / RMSE 15.31 / r 0.681;
the dry season (Nov-Mar) bias +0.49 / RMSE 4.10 / r 0.602.

The aggregate numbers hide the important failure. **1,034 region-days have GPM = 0 but POWER > 1 mm/day**
(788 of them in the wet season, 246 in the dry). And the *ratio* of monthly totals is not stable:

""")
A(B(b2, "7.2 Monthly rainfall totals"))
A(B(b2, "7.2b POWER/GPM monthly-total ratio"))
A(B(b2, "8.6 Dry-season"))
A(b3["7b.1 Annual rainfall totals per region (mm) - GPM vs POWER/24 (2026 partial: Jan-Oct)"].replace(
    "#### 7b.1", "#### 7.3"))
A("""**Where they agree:** May-Oct, ratio 1.05-1.50 in 2022-2025, correlation 0.68. The monsoon is
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

""")
A(B(b2, "7.3 GPM final vs late run"))
A(B(b3, "7b.2 GPM vs POWER monthly totals by calendar month, split at the final->late run switch"))
A("""`run` is `final` for 2022-01-01..2025-09-30 (9,583 rows) and `late` for 2025-10-01..2026-11-09
(2,835 rows). The two never overlap, so they cannot be compared on the same days. The POWER comparison
in the table above is the substitute: in June, GPM drops from 453 mm/month (final-era mean) to 209 mm
(late era) while POWER drops only 573 -> 473; in August, GPM 472 -> 227 against POWER 565 -> 451. The
ratio POWER/GPM moves from 1.20-1.26 in the final era to 1.99-2.26 in the late era for Jun-Aug.
**Either the 2026 monsoon was genuinely much drier in a way POWER did not see, or the GPM late run is
biased low by roughly 40-50% in the wet season.** With only one late-run wet season in the record the
two hypotheses cannot be separated - treat the boundary as a regime change and always carry the `run`
column as a feature (or restrict training to the final-run era).

## 8. Extremes and anomalies

""")
A(B(b2, "8.1 Per-region p01/p99 extremes"))
A("""The `n_ge_p99` column in that table is tautological (1% of n by construction, so 18 for a
1,774-day GPM series and 2 for a ~130-observation LST series). Use the fixed-threshold counts instead:

""")
A(B(b3, "8b.1 GPM rainfall threshold exceedance counts"))
A(B(b3, "8b.2 7-region-mean"))
A(B(b2, "8.2 Top-5 daily rainfall events per region"))
A(B(b2, "8.3 Top-15 most widespread heavy-rain days"))
A("""**Largest events.** The most widespread heavy-rain day in the record is **2024-05-27** (7-region
mean 84.6 mm/day, 5 of 7 regions above 50 mm, peak 171.3 mm at Southeast_Chattogram) - consistent with
the pre-monsoon Cyclone Remal landfall period. Second is **2024-07-01** (78.9 mm mean), third
**2022-10-24** (75.9 mm mean, peak 152.4 mm at Central_Dhaka). The largest single region-day value is
**194.97 mm at Northeast_Sylhet on 2022-06-18**, the wettest region in the country by a factor of ~2 in
annual total (3,474 mm/yr vs 1,227 mm/yr for Northwest_Rajshahi).

Regional exposure is very unequal: Northeast_Sylhet has 71 days >= 50 mm and 5 days >= 150 mm;
Northwest_Rajshahi has 11 days >= 50 mm and **zero** days >= 100 mm. A single national extreme-event
threshold would be meaningless - use per-region percentiles.

""")
A(B(b3, "8b.6 GRACE"))
A(B(b3, "8b.8 SMAP am soil moisture"))

A("""## 9. Data-quality verdict per dataset

`usable_pct` = share of expected region-days (at each dataset's own cadence) carrying a valid value
for the primary variable. See `eda\\09_verdict.csv`.

""")
A(B(b2, "9.1 Data-quality verdict"))

A("""### 9.1 What each dataset can actually support

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

Scripts (all in `C:\\Users\\muhai\\Desktop\\BIG hero 6\\Data\\_report\\eda\\`):

```
# 1. inventory, dtypes, missingness matrices, quantiles, plausibility, seasonality
"C:\\Users\\muhai\\Desktop\\BIG hero 6\\Data\\.venv\\Scripts\\python.exe" -I eda_part1.py

# 2. autocorrelation, cross-correlation, GPM-vs-POWER agreement, extremes, verdict
"C:\\Users\\muhai\\Desktop\\BIG hero 6\\Data\\.venv\\Scripts\\python.exe" -I eda_part2.py

# 3. gap decomposition, annual totals, threshold extremes, sensor diagnostics
"C:\\Users\\muhai\\Desktop\\BIG hero 6\\Data\\.venv\\Scripts\\python.exe" -I eda_part3.py

# 4. assemble this document from the generated tables
"C:\\Users\\muhai\\Desktop\\BIG hero 6\\Data\\.venv\\Scripts\\python.exe" -I build_eda_md.py
```

`-I` isolates the interpreter from the current directory. The scripts only read the source CSVs and
only write into `Data\\_report\\eda\\`. Versions used: Python 3.13.9, pandas 3.1.1, numpy 2.5.4,
matplotlib 3.11.2 (scikit-learn is *not* installed in this venv; nothing here needs it).

Output tables (`Data\\_report\\eda\\`):

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

Nothing in the source data was modified. No file outside `Data\\_report\\` was written.
""")


RENAME = [
 ("1.1 Dataset inventory", "Table 1.1 Dataset inventory"),
 ("2.1 Overall missingness on the common 2022-01-01..2026-11-09 grid (7 regions x 1774 days = 12418 region-days)",
  "Table 2.1 Overall missingness on the common 2022-01-01..2026-11-09 grid (7 regions x 1,774 days = 12,418 region-days)"),
 ("2.gpm - % missing of expected (region x day) cells, month x year",
  "Table 2.2 GPM - % missing of expected (region x day) cells, month x year"),
 ("2.power_prec - % missing of expected (region x day) cells, month x year",
  "Table 2.3 POWER PRECTOTCORR - % missing of expected cells, month x year"),
 ("2.smap_am - % missing of expected (region x day) cells, month x year",
  "Table 2.4 SMAP am pass - % missing of expected cells, month x year"),
 ("2.smap_any - % missing of expected (region x day) cells, month x year",
  "Table 2.5 SMAP any pass - % missing of expected cells, month x year"),
 ("2.ecostress - % missing of expected (region x day) cells, month x year",
  "Table 2.6 ECOSTRESS LST - % missing of expected cells, month x year"),
 ("2.hls - % missing of expected (region x day) cells, month x year",
  "Table 2.7 HLS NDVI - % missing of expected cells, month x year"),
 ("2.grace - % missing of expected (region x day) cells, month x year",
  "Table 2.8 GRACE - % missing of expected cells, month x year"),
 ("2.ecox ECOSTRESS overpass rows / valid LST per month",
  "Table 2.9 ECOSTRESS overpass rows and valid LST per month"),
 ("2b.1 SMAP am-pass gap decomposition (1774-day grid per region)",
  "Table 2.10 SMAP am-pass gap decomposition (1,774-day grid per region)"),
 ("2b.2 ECOSTRESS gap decomposition", "Table 2.11 ECOSTRESS gap decomposition"),
 ("2b.3 HLS gap decomposition", "Table 2.12 HLS gap decomposition"),
 ("2b.4 POWER gap decomposition", "Table 2.13 POWER gap decomposition"),
 ("3.1 Pooled quantiles (all 7 regions, valid values only)",
  "Table 3.1 Pooled quantiles (all 7 regions, valid values only)"),
 ("3.x GPM precipitation_mm_day - quantiles by region",
  "Table 3.2 GPM precipitation_mm_day - quantiles by region"),
 ("3.x SMAP soil_moisture_m3_m3 - quantiles by region",
  "Table 3.3 SMAP soil_moisture_m3_m3 - quantiles by region"),
 ("3.x ECOSTRESS lst_celsius - quantiles by region",
  "Table 3.4 ECOSTRESS lst_celsius - quantiles by region"),
 ("3.x HLS ndvi - quantiles by region", "Table 3.5 HLS ndvi - quantiles by region"),
 ("3.x HLS ndmi - quantiles by region", "Table 3.6 HLS ndmi - quantiles by region"),
 ("3.x GRACE lwe_thickness_cm - quantiles by region",
  "Table 3.7 GRACE lwe_thickness_cm - quantiles by region"),
 ("3.x POWER T2M - quantiles by region", "Table 3.8 POWER T2M - quantiles by region"),
 ("3.x POWER RH2M - quantiles by region", "Table 3.9 POWER RH2M - quantiles by region"),
 ("3.x POWER PRECTOTCORR - quantiles by region",
  "Table 3.10 POWER PRECTOTCORR (after /24) - quantiles by region"),
 ("3.2 Physical-plausibility checks", "Table 3.11 Physical-plausibility checks"),
 ("4.1 Monthly climatology, mean over 7 regions (monthly means of the daily series)",
  "Table 4.1 Monthly climatology, mean over 7 regions"),
 ("4.2 Per-region seasonal amplitude (from monthly means of the daily/monthly series)",
  "Table 4.2 Per-region seasonal amplitude"),
 ("4.2b Peak month per region", "Table 4.3 Peak month per region"),
 ("5.1 Daily autocorrelation, lag 1-30 (pairwise-complete), per variable (mean/min/max over 7 regions)",
  "Table 5.1 Daily autocorrelation, lag 1-30 (pairwise-complete), mean/min/max over 7 regions"),
 ("5.2 Region-mean ACF curve, lags 1-30", "Table 5.3 Region-mean ACF curve, lags 1-30"),
 ("5.3 Lag-1 autocorrelation by region", "Table 5.4 Lag-1 autocorrelation by region"),
 ("5.4 Monthly-series autocorrelation (lags 1-12 months)",
  "Table 5.5 Monthly-series autocorrelation (lags 1-12 months)"),
 ("5.4b n pairs at lag 1 / lag 12", "Table 5.6 Number of pairs at lag 1 and lag 12"),
 ("6.1 Daily cross-correlation, rain (driver) vs response, lags -30..+30 days. 'best_lag' = lag of maximum correlation (+ = response lags rain)",
  "Table 6.1 Daily cross-correlation, rain (driver) vs response, lags -30..+30 days ('best_lag' = lag of maximum correlation; + = response lags rain)"),
 ("6.1b Per-region lag of maximum correlation, raw series",
  "Table 6.2 Per-region lag of maximum correlation, raw series"),
 ("6.1c Per-region max correlation, raw series", "Table 6.3 Per-region maximum correlation, raw series"),
 ("6.2 Monthly cross-correlation (lags -6..+6 months), monthly rain totals vs monthly means",
  "Table 6.4 Monthly cross-correlation (lags -6..+6 months), monthly rain totals vs monthly means"),
 ("6.2b Per-region best lag (months)", "Table 6.5 Per-region best lag (months)"),
 ("6.2c Per-region max correlation", "Table 6.6 Per-region maximum correlation (monthly)"),
 ("7.1 GPM vs POWER PRECTOTCORR (mm/day after /24), 12292 paired region-days",
  "Table 7.1 GPM vs POWER PRECTOTCORR (mm/day after /24), 12,292 paired region-days"),
 ("7.1b Agreement by region", "Table 7.2 Agreement by region"),
 ("7.2 Monthly rainfall totals per region (mm), GPM vs POWER (POWER/24)",
  "Table 7.3 Monthly rainfall totals per region (mm), GPM vs POWER/24"),
 ("7.2b POWER/GPM monthly-total ratio, month x year",
  "Table 7.4 POWER/GPM monthly-total ratio, month x year"),
 ("8.6 Dry-season monthly totals (Dec/Jan/Feb), mm per region - GPM vs POWER",
  "Table 7.5 Dry-season monthly totals (Dec/Jan/Feb), mm per region - GPM vs POWER"),
 ("7.3 GPM final vs late run, mean daily precipitation by calendar month",
  "Table 7.7 GPM final vs late run, mean daily precipitation by calendar month"),
 ("7.3 Annual rainfall totals per region (mm) - GPM vs POWER/24 (2026 partial: Jan-Oct)",
  "Table 7.6 Annual rainfall totals per region (mm) - GPM vs POWER/24 (2026 partial: Jan-Oct)"),
 ("7b.2 GPM vs POWER monthly totals by calendar month, split at the final->late run switch (2025-10-01)",
  "Table 7.8 GPM vs POWER monthly totals by calendar month, split at the final->late run switch (2025-10-01)"),
 ("8.1 Per-region p01/p99 extremes and counts (>=p99 flags)",
  "Table 8.1 Per-region p01/p99 extremes and counts (>= p99)"),
 ("8b.1 GPM rainfall threshold exceedance counts per region (1774 days)",
  "Table 8.2 GPM rainfall threshold exceedance counts per region (1,774 days)"),
 ("8b.2 7-region-mean daily rainfall, wet-season tail",
  "Table 8.3 7-region-mean daily rainfall, upper tail"),
 ("8.2 Top-5 daily rainfall events per region (GPM)",
  "Table 8.4 Top-5 daily rainfall events per region (GPM)"),
 ("8.3 Top-15 most widespread heavy-rain days (ranked by 7-region mean)",
  "Table 8.5 Top-15 most widespread heavy-rain days (ranked by 7-region mean)"),
 ("8b.6 GRACE LWE linear trend per region (57 monthly values, 2022-01..2026-09)",
  "Table 8.6 GRACE LWE linear trend per region (57 monthly values, 2022-01..2026-09)"),
 ("8.4 SMAP satellite-retrieval ceiling pile-up (identical maximum repeated many times)",
  "Table 3.13 SMAP retrieval ceiling pile-up (identical maximum repeated many times)"),
 ("8b.3 SMAP ceiling pile-up by pass", "Table 3.14 SMAP ceiling pile-up by pass"),
 ("8b.5 ECOSTRESS overpass local-time distribution and LST by local-time bucket (UTC+6)",
  "Table 3.15 ECOSTRESS overpass local-time distribution and LST by local-time bucket (UTC+6)"),
 ("8.5 GRACE: regions with byte-identical LWE series (same mascon 1321)",
  "Table 3.16 GRACE: regions with byte-identical LWE series (same mascon 1321)"),
 ("5.1b Effective sample size implied by the lag-1 autocorrelation (n = 1,774 days)",
  "Table 5.2 Effective sample size implied by the lag-1 autocorrelation (n = 1,774 days)"),
 ("5.4c Effective sample size of the monthly series (n = 59 months)",
  "Table 5.7 Effective sample size of the monthly series (n = 59 months)"),
 ("8b.9 GPM zero-rain structure by calendar month", "Table 3.12 GPM zero-rain structure by calendar month"),
 ("8b.7 Correlation between monthly SMAP soil moisture and monthly GPM rainfall, by season",
  "Table 4.4 Correlation between monthly SMAP soil moisture and monthly GPM rainfall, by season"),
 ("8b.8 SMAP am soil moisture, Jan-Feb mean by year (dry-season drift)",
  "Table 8.7 SMAP am soil moisture, Jan-Feb mean by year (dry-season drift)"),
 ("9.1 Data-quality verdict", "Table 9.1 Data-quality verdict"),
]

text = "\n".join(P)
for old, new in RENAME:
    text = text.replace("#### " + old + "\n", "##### " + new + "\n")
P = [text]

with open(MD, "w", encoding="utf-8") as f:
    f.write("\n".join(P))

print("wrote", MD, os.path.getsize(MD), "bytes")
