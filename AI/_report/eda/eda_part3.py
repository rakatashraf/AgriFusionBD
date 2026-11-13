"""EDA part 3: gap decomposition, annual totals, threshold extremes, sensor-specific diagnostics.
Run:  .venv\\Scripts\\python.exe -I eda_part3.py
"""
import pandas as pd, numpy as np, glob, os

D = r"C:\Users\muhai\Desktop\BIG hero 6\Data"
POWER_DIR = r"C:\Users\muhai\Desktop\BIG hero 6\API_NASA_POWER\src\data_accusition\bangladesh_weather"
OUT = os.path.join(D, "_report", "eda")
FRAG = []


def frag(title, df, note=""):
    s = f"\n#### {title}\n"
    if note:
        s += note + "\n"
    s += "\n" + df.to_markdown() + "\n"
    FRAG.append(s)


def save(df, name, index=True):
    df.to_csv(os.path.join(OUT, name), index=index)


gpm = pd.read_csv(os.path.join(D, "GPM_IMERG_Rainfall",
                  "GPM_IMERG_all_regions_daily_20220101_to_20261111.csv"), parse_dates=["date"])
smap = pd.read_csv(os.path.join(D, "SMAP_SoilMoisture",
                   "SMAP_soil_moisture_all_regions_daily_20220101_to_20261109.csv"), parse_dates=["date"])
eco = pd.read_csv(os.path.join(D, "ECOSTRESS_LST_ET",
                  "ECOSTRESS_LST_all_regions_20220101_to_20261111.csv"))
hls = pd.read_csv(os.path.join(D, "HLS_Vegetation_Indices",
                  "HLS_indices_all_regions_20220101_to_20261111.csv"))
grace = pd.read_csv(os.path.join(D, "GRACE_WaterStorage",
                    "GRACE_mascon_all_regions_monthly_20220101_to_20260916.csv"), parse_dates=["date"])
pw = pd.concat([pd.read_csv(f, parse_dates=["date"]) for f in
                sorted(glob.glob(os.path.join(POWER_DIR, "*_20220101_to_*.csv")))], ignore_index=True)
pw["PRECTOTCORR"] = pw["PRECTOTCORR"] / 24.0

REGIONS = sorted(gpm["region"].unique())
GRID = pd.date_range("2022-01-01", "2026-11-09", freq="D")

# ---------------------------------------------------------------- gap decomposition
# SMAP: why is a region-day missing (am pass)?
s = smap.sort_values(["region", "date", "pass", "source_file"]).drop_duplicates(
    ["region", "date", "pass"], keep="first")
am = s[s["pass"] == "am"].set_index(["region", "date"])
rows = []
for reg in REGIONS:
    sub = am.loc[reg].reindex(GRID)
    present = sub["soil_moisture_m3_m3"].notna()
    no_row = sub["source_file"].isna()
    has_row = ~no_row
    surf_fill = has_row & (sub["surface_flag"] == 2047)
    no_retr = has_row & (sub["surface_flag"] != 2047) & (sub["retrieval_qual_flag"] == 7)
    other_null = has_row & ~surf_fill & ~no_retr & ~present
    rows.append(dict(region=reg, days=len(GRID), valid=int(present.sum()),
                     no_granule_row=int(no_row.sum()),
                     row_but_not_mapped_surface_flag_2047=int(surf_fill.sum()),
                     row_but_retrieval_qual_flag_7=int(no_retr.sum()),
                     row_but_null_other=int(other_null.sum())))
gap_smap = pd.DataFrame(rows)
gap_smap["pct_valid"] = (100 * gap_smap["valid"] / gap_smap["days"]).round(1)
save(gap_smap, "02b_gap_decomposition_smap_am.csv", index=False)
frag("2b.1 SMAP am-pass gap decomposition (1774-day grid per region)", gap_smap)

# ECOSTRESS: structural vs QC gap
e = eco.copy()
e["dt"] = pd.to_datetime(e["observed_utc"])
e["date"] = e["dt"].dt.normalize()
e["qcfill"] = e["qc"] == 65535
n_days_any_overpass = e["date"].nunique()
eco_gap = pd.DataFrame([dict(
    grid_region_days=len(GRID) * 7,
    region_days_with_overpass_row=int(e.groupby(["region", "date"]).ngroups),
    overpass_rows=len(e),
    qc_fill_65535_rows=int(e["qcfill"].sum()),
    lst_valid=int(e["lst_celsius"].notna().sum()),
    other_null_rows=int(((~e["qcfill"]) & e["lst_celsius"].isna()).sum()),
    days_with_any_overpass=int(n_days_any_overpass),
)])
save(eco_gap, "02b_gap_decomposition_ecostress.csv", index=False)
frag("2b.2 ECOSTRESS gap decomposition", eco_gap)

# HLS: structural (monthly attempt) vs cloud
h = hls.copy()
h["dt"] = pd.to_datetime(h["observed_utc"], format="mixed", utc=True)
hls_gap = pd.DataFrame([dict(
    attempt_rows=len(h),
    rows_zero_valid_pixels=int((h["valid_pixels"] == 0).sum()),
    rows_valid_pixels_1_to_5=int(h["valid_pixels"].between(1, 5).sum()),
    rows_valid_pixels_6_to_50=int(h["valid_pixels"].between(6, 50).sum()),
    rows_valid_pixels_gt50=int((h["valid_pixels"] > 50).sum()),
    ndvi_present=int(h["ndvi"].notna().sum()),
    ndvi_from_le5_pixels=int(((h["valid_pixels"] <= 5) & h["ndvi"].notna()).sum()),
    ndvi_from_coverage_lt_0p1=int(((h["valid_coverage"] < 0.1) & h["ndvi"].notna()).sum()),
    ndvi_from_coverage_ge_0p9=int(((h["valid_coverage"] >= 0.9) & h["ndvi"].notna()).sum()),
)])
save(hls_gap, "02b_gap_decomposition_hls.csv", index=False)
frag("2b.3 HLS gap decomposition", hls_gap)

# power trailing / SW gap
pwg = pd.DataFrame([dict(
    rows=len(pw), region_days_all_null=int(pw[["T2M", "PRECTOTCORR", "RH2M", "WS2M", "PS"]].isna().all(axis=1).sum()),
    SW_DWN_null=int(pw["ALLSKY_SFC_SW_DWN"].isna().sum()),
    SW_DWN_null_but_other_params_present=int((pw["ALLSKY_SFC_SW_DWN"].isna() & pw["T2M"].notna()).sum()),
    SW_DWN_gap_start="2026-08-01", SW_DWN_gap_end="2026-10-22")])
save(pwg, "02b_gap_decomposition_power.csv", index=False)
frag("2b.4 POWER gap decomposition", pwg)

# ---------------------------------------------------------------- annual totals, GPM vs POWER
ga = gpm.assign(year=gpm["date"].dt.year).groupby(["region", "year"])["precipitation_mm_day"].sum().rename("gpm_mm")
pa = pw.assign(year=pw["date"].dt.year).groupby(["region", "year"])["PRECTOTCORR"].sum().rename("power_mm")
ann = pd.concat([ga, pa], axis=1).reset_index()
ann["power_over_gpm"] = (ann["power_mm"] / ann["gpm_mm"]).round(2)
ann = ann.round(1)
save(ann, "07b_annual_totals_gpm_vs_power.csv", index=False)
frag("7b.1 Annual rainfall totals per region (mm) - GPM vs POWER/24 (2026 partial: Jan-Oct)",
     ann.pivot_table(index="year", columns="region", values="gpm_mm"))

# per-calendar-month ratio, final era vs late era
j = gpm[["date", "region", "precipitation_mm_day"]].merge(
    pw[["date", "region", "PRECTOTCORR"]], on=["date", "region"], how="inner")
j["month"] = j["date"].dt.to_period("M")
j["mon"] = j["date"].dt.month
j["run"] = np.where(j["date"] < "2025-10-01", "final (2022-01..2025-09)", "late (2025-10..2026-10)")
ratio = j.groupby(["run", "mon"]).apply(
    lambda g: pd.Series({"gpm_mm": g["precipitation_mm_day"].sum() / g["region"].nunique(),
                         "power_mm": g["PRECTOTCORR"].sum() / g["region"].nunique(),
                         "n_days": len(g) / g["region"].nunique()}), include_groups=False)
ratio["power_over_gpm"] = (ratio["power_mm"] / ratio["gpm_mm"]).round(2)
ratio = ratio.round(2)
save(ratio, "07b_run_era_monthly_ratio.csv")
frag("7b.2 GPM vs POWER monthly totals by calendar month, split at the final->late run switch (2025-10-01)", ratio)

# ---------------------------------------------------------------- threshold extremes
thr = []
for reg in REGIONS:
    srs = gpm.loc[gpm["region"] == reg].set_index("date")["precipitation_mm_day"]
    thr.append(dict(region=reg, days_ge_10=int((srs >= 10).sum()), days_ge_25=int((srs >= 25).sum()),
                    days_ge_50=int((srs >= 50).sum()), days_ge_100=int((srs >= 100).sum()),
                    days_ge_150=int((srs >= 150).sum()), days_eq_0=int((srs == 0).sum()),
                    max_mm=round(float(srs.max()), 2), max_date=str(srs.idxmax().date()),
                    annual_mean_mm=round(float(srs.sum()) / 4.86, 1)))
thr = pd.DataFrame(thr)
save(thr, "08b_rainfall_threshold_counts.csv", index=False)
frag("8b.1 GPM rainfall threshold exceedance counts per region (1774 days)", thr)

# region-mean series extremes
rm = gpm.pivot(index="date", columns="region", values="precipitation_mm_day").mean(axis=1)
frag("8b.2 7-region-mean daily rainfall, wet-season tail", pd.DataFrame({
    "threshold_mm": [10, 20, 30, 40, 50, 60, 80],
    "n_days": [int((rm >= t).sum()) for t in [10, 20, 30, 40, 50, 60, 80]]}).set_index("threshold_mm"))

# SMAP saturation by pass, and count of days at ceiling
sm = smap.sort_values(["region", "date", "pass", "source_file"]).drop_duplicates(
    ["region", "date", "pass"], keep="first")
sm.loc[sm["retrieval_qual_flag"] == 7, "soil_moisture_m3_m3"] = np.nan
sat = sm.groupby(["region", "pass"]).apply(
    lambda g: pd.Series({"n": g["soil_moisture_m3_m3"].notna().sum(),
                         "max": round(float(g["soil_moisture_m3_m3"].max()), 4),
                         "n_at_max": int((g["soil_moisture_m3_m3"] >= g["soil_moisture_m3_m3"].max() - 1e-9).sum()),
                         "pct_at_max": round(100 * float((g["soil_moisture_m3_m3"] >= g["soil_moisture_m3_m3"].max() - 1e-9).mean()), 1)}),
    include_groups=False)
save(sat, "08b_smap_saturation_by_pass.csv")
frag("8b.3 SMAP ceiling pile-up by pass", sat)

# retrieval quality flag distribution (valid retrievals only)
rq = sm.dropna(subset=["soil_moisture_m3_m3"]).groupby(["retrieval_qual_flag", "pass"]).size().unstack(fill_value=0)
save(rq, "08b_smap_retrieval_qual_distribution.csv")
frag("8b.4 SMAP retrieval_qual_flag distribution among valid retrievals", rq)

# ---------------------------------------------------------------- ECOSTRESS diurnal
e2 = eco.copy()
e2["dt"] = pd.to_datetime(e2["observed_utc"])
e2["hl"] = ((e2["dt"].dt.hour + e2["dt"].dt.minute / 60 + 6) % 24)
e2["bucket"] = pd.cut(e2["hl"], bins=[-0.1, 3, 6, 9, 12, 15, 18, 21, 24],
                      labels=["00-03", "03-06", "06-09", "09-12", "12-15", "15-18", "18-21", "21-24"])
db = e2.groupby("bucket", observed=True).agg(overpasses=("qc", "size"), lst_valid=("lst_celsius", "count"),
                                             lst_mean=("lst_celsius", "mean"), lst_sd=("lst_celsius", "std")).round(2)
save(db, "08b_ecostress_diurnal.csv")
frag("8b.5 ECOSTRESS overpass local-time distribution and LST by local-time bucket (UTC+6)", db)

# ---------------------------------------------------------------- GRACE trend
gt = []
for reg in REGIONS:
    sub = grace[grace.region == reg].sort_values("date")
    t = (sub["date"] - sub["date"].iloc[0]).dt.days.to_numpy() / 365.25
    y = sub["lwe_thickness_cm"].to_numpy()
    b1, b0 = np.polyfit(t, y, 1)
    resid = y - (b0 + b1 * t)
    se = np.sqrt((resid ** 2).sum() / (len(t) - 2) / ((t - t.mean()) ** 2).sum())
    gt.append(dict(region=reg, mascon=int(sub["mascon_id"].iloc[0]),
                   trend_cm_per_yr=round(float(b1), 2), se=round(float(se), 2),
                   mean_cm=round(float(y.mean()), 2), sd_cm=round(float(y.std()), 2),
                   mean_uncertainty_cm=round(float(sub["uncertainty_cm"].mean()), 2)))
gt = pd.DataFrame(gt)
save(gt, "08b_grace_trend.csv", index=False)
frag("8b.6 GRACE LWE linear trend per region (57 monthly values, 2022-01..2026-09)", gt)

# ---------------------------------------------------------------- SM-rain seasonal coupling and SMAP drift
sm_am = sm[s["pass"] == "am"].pivot(index="date", columns="region", values="soil_moisture_m3_m3")
sm_m = sm_am.resample("MS").mean().mean(axis=1)
rain_m = gpm.pivot(index="date", columns="region", values="precipitation_mm_day").resample("MS").sum().mean(axis=1)
draw = pd.DataFrame({"sm_monthly_mean": sm_m, "rain_monthly_total_mm": rain_m}).dropna()
dry = draw[draw.index.month.isin([11, 12, 1, 2, 3])]
wet = draw[~draw.index.month.isin([11, 12, 1, 2, 3])]
season = pd.DataFrame([
    dict(season="dry (Nov-Mar)", n_months=len(dry), corr=round(float(dry.sm_monthly_mean.corr(dry.rain_monthly_total_mm)), 3),
         mean_sm=round(float(dry.sm_monthly_mean.mean()), 3), mean_rain=round(float(dry.rain_monthly_total_mm.mean()), 1)),
    dict(season="wet (Apr-Oct)", n_months=len(wet), corr=round(float(wet.sm_monthly_mean.corr(wet.rain_monthly_total_mm)), 3),
         mean_sm=round(float(wet.sm_monthly_mean.mean()), 3), mean_rain=round(float(wet.rain_monthly_total_mm.mean()), 1)),
    dict(season="all", n_months=len(draw), corr=round(float(draw.sm_monthly_mean.corr(draw.rain_monthly_total_mm)), 3),
         mean_sm=round(float(draw.sm_monthly_mean.mean()), 3), mean_rain=round(float(draw.rain_monthly_total_mm.mean()), 1)),
])
save(season, "08b_sm_rain_seasonal_corr.csv", index=False)
frag("8b.7 Correlation between monthly SMAP soil moisture and monthly GPM rainfall, by season", season)

janfeb = sm_m[sm_m.index.month.isin([1, 2])]
drift = janfeb.groupby(janfeb.index.year).mean().round(4).to_frame("jan_feb_mean_sm")
save(drift, "08b_smap_dry_season_drift.csv")
frag("8b.8 SMAP am soil moisture, Jan-Feb mean by year (dry-season drift)", drift)

z = (gpm.pivot(index="date", columns="region", values="precipitation_mm_day") == 0).mean(axis=1)
zb = z.groupby(z.index.month).agg(pct_region_days_exactly_zero="mean")
zb["pct_region_days_exactly_zero"] = (100 * zb["pct_region_days_exactly_zero"]).round(1)
allz = (gpm.pivot(index="date", columns="region", values="precipitation_mm_day").max(axis=1) < 0.1)
zb["pct_days_all_7_regions_dry"] = (100 * allz.groupby(allz.index.month).mean()).round(1)
zb.index.name = "month"
save(zb, "08b_gpm_zero_fraction_by_month.csv")
frag("8b.9 GPM zero-rain structure by calendar month", zb)

with open(os.path.join(OUT, "_fragments_part3.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(FRAG))
print("part3 done:", len(FRAG))
