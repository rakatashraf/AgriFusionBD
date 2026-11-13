"""EDA part 1: inventory, missingness, distributions, seasonality.
Reads NASA environmental CSVs (read-only) and writes summary tables to _report/eda/.
Run:  .venv\\Scripts\\python.exe -I eda_part1.py
"""
import pandas as pd, numpy as np, glob, os, json

D = r"C:\Users\muhai\Desktop\BIG hero 6\Data"
POWER_DIR = r"C:\Users\muhai\Desktop\BIG hero 6\API_NASA_POWER\src\data_accusition\bangladesh_weather"
OUT = os.path.join(D, "_report", "eda")
os.makedirs(OUT, exist_ok=True)
FRAG = []


def frag(title, df, note=""):
    s = f"\n#### {title}\n"
    if note:
        s += note + "\n"
    s += "\n" + df.to_markdown() + "\n"
    FRAG.append(s)


def save(df, name, index=True):
    df.to_csv(os.path.join(OUT, name), index=index)


# ----------------------------------------------------------------------------
# LOAD
# ----------------------------------------------------------------------------
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
srtm = pd.read_csv(os.path.join(D, "SRTM_Elevation", "SRTM_terrain_summary_all_regions.csv"))
pw = pd.concat([pd.read_csv(f) for f in
                sorted(glob.glob(os.path.join(POWER_DIR, "*_20220101_to_*.csv")))], ignore_index=True)

# --- cleaning / canonicalisation -------------------------------------------
# POWER: PRECTOTCORR in these files is the sum of 24 hourly values that are each
# already expressed in mm/day  => 24x inflated. Every value is an exact multiple
# of 0.24 (verified). Convert to mm/day.
pw["PRECTOTCORR_raw"] = pw["PRECTOTCORR"]
pw["PRECTOTCORR"] = pw["PRECTOTCORR_raw"] / 24.0

# SMAP: drop duplicate retrieval versions (R..._001 / _002) - identical values
smap["pass"] = smap["pass"].str.lower()
smap = smap.sort_values(["region", "date", "pass", "source_file"])
smap_dup_n = int(smap.duplicated(["region", "date", "pass"]).sum())
smap = smap.drop_duplicates(["region", "date", "pass"], keep="first")
# SMAP sentinels: soil_moisture_error and freeze_thaw_fraction are pure fill (-9999)
smap["soil_moisture_error_m3_m3"] = smap["soil_moisture_error_m3_m3"].replace(-9999.0, np.nan)
smap["freeze_thaw_fraction"] = smap["freeze_thaw_fraction"].replace(-9999.0, np.nan)
# retrieval_qual_flag == 7 means "no retrieval" -> mask
smap.loc[smap["retrieval_qual_flag"] == 7, "soil_moisture_m3_m3"] = np.nan
smap.loc[smap["surface_flag"] == 2047, "soil_moisture_m3_m3"] = np.nan

# ECOSTRESS: qc 65535 = fill
eco["dt"] = pd.to_datetime(eco["observed_utc"])
eco.loc[eco["qc"] == 65535, "lst_celsius"] = np.nan
eco.loc[eco["qc"] == 65535, "lst_kelvin"] = np.nan
eco["date"] = eco["dt"].dt.normalize()
eco["hour_utc"] = eco["dt"].dt.hour + eco["dt"].dt.minute / 60.0
eco["hour_local"] = (eco["hour_utc"] + 6.0) % 24.0   # Bangladesh = UTC+6
eco["daytime"] = eco["hour_local"].between(9, 16)

# HLS
hls["dt"] = pd.to_datetime(hls["observed_utc"], format="mixed", utc=True)
hls["date"] = hls["dt"].dt.tz_convert(None).dt.normalize()
hls["month"] = hls["dt"].dt.tz_convert(None).dt.to_period("M")

REGIONS = sorted(gpm["region"].unique())
GRID = pd.date_range("2022-01-01", "2026-11-09", freq="D")
NDAYS = len(GRID)

# ----------------------------------------------------------------------------
# 1. INVENTORY
# ----------------------------------------------------------------------------
inv = []
def add_inv(ds, df, varkey, datecol, cadence, keycols, span_note=""):
    d = pd.to_datetime(df[datecol])
    inv.append(dict(dataset=ds, rows=len(df), cols=df.shape[1], regions=df["region"].nunique(),
                    date_min=str(d.min().date()), date_max=str(d.max().date()),
                    n_unique_dates=d.dt.normalize().nunique(),
                    dup_key_rows=int(df.duplicated(keycols).sum()),
                    key="+".join(keycols), cadence=cadence, primary_var=varkey, note=span_note))

add_inv("GPM_IMERG", gpm, "precipitation_mm_day", "date", "daily (complete)", ["region", "date", "run"])
add_inv("SMAP", smap, "soil_moisture_m3_m3", "date", "2 passes/day, gappy", ["region", "date", "pass"],
        "56 duplicate rows removed (R..._001/_002)")
add_inv("ECOSTRESS", eco, "lst_celsius", "dt", "per-overpass (irregular)", ["region", "dt"])
add_inv("HLS", hls, "ndvi", "dt", "~monthly attempt", ["region", "dt"])
add_inv("GRACE", grace, "lwe_thickness_cm", "date", "monthly", ["region", "date"])
add_inv("POWER", pw, "PRECTOTCORR", "date", "daily (complete)", ["region", "date"],
        "3 trailing all-null rows/region; SW_DWN has extra gaps")
inv.append(dict(dataset="SRTM", rows=len(srtm), cols=srtm.shape[1], regions=srtm["region"].nunique(),
                date_min="static", date_max="static", n_unique_dates=1,
                dup_key_rows=int(srtm.duplicated(["region"]).sum()),
                key="region", cadence="static (1 row/region)", primary_var="elevation_mean_m", note="no time dimension"))
inv = pd.DataFrame(inv)
save(inv, "01_inventory.csv", index=False)
frag("1.1 Dataset inventory", inv)

# dtypes table
dt_rows = []
for name, df in [("GPM_IMERG", gpm), ("SMAP", smap), ("ECOSTRESS", eco), ("HLS", hls),
                 ("GRACE", grace), ("SRTM", srtm), ("POWER", pw)]:
    for c in df.columns:
        if c in ("PRECTOTCORR_raw",):
            continue
        dt_rows.append(dict(dataset=name, column=c, dtype=str(df[c].dtype),
                            n_null=int(df[c].isna().sum()),
                            pct_null=round(100 * df[c].isna().mean(), 2)))
dtypes_tbl = pd.DataFrame(dt_rows)
save(dtypes_tbl, "01_dtypes_nulls.csv", index=False)

# ----------------------------------------------------------------------------
# 2. MISSINGNESS
# ----------------------------------------------------------------------------
# Build canonical per-dataset "region x day" panels for the primary variable.
def panel(df, var, datecol="date", agg="first", regions=REGIONS):
    d = df.copy()
    d["date"] = pd.to_datetime(d[datecol]).dt.normalize()
    p = d.pivot_table(index="date", columns="region", values=var, aggfunc=agg)
    p = p.reindex(GRID)
    return p.reindex(columns=regions)

gpm_p = panel(gpm, "precipitation_mm_day")
pw_p = panel(pw, "PRECTOTCORR")
pw_sw = panel(pw, "ALLSKY_SFC_SW_DWN")
smap_am = panel(smap[smap["pass"] == "am"], "soil_moisture_m3_m3")
smap_pm = panel(smap[smap["pass"] == "pm"], "soil_moisture_m3_m3")
smap_any = panel(smap, "soil_moisture_m3_m3", agg="mean")
eco_p = panel(eco, "lst_celsius")            # NaN on days with no overpass
hls_p = panel(hls, "ndvi")
grace_p = panel(grace, "lwe_thickness_cm")

panels = {
    "GPM precipitation_mm_day": gpm_p,
    "POWER PRECTOTCORR (mm/day)": pw_p,
    "POWER ALLSKY_SFC_SW_DWN": pw_sw,
    "SMAP soil_moisture (am)": smap_am,
    "SMAP soil_moisture (pm)": smap_pm,
    "SMAP soil_moisture (any pass)": smap_any,
    "ECOSTRESS lst_celsius": eco_p,
    "HLS ndvi": hls_p,
    "GRACE lwe_thickness_cm (daily-interp view)": grace_p,
}

miss = pd.DataFrame({
    "pct_missing": {k: round(100 * v.isna().to_numpy().mean(), 2) for k, v in panels.items()},
    "pct_valid": {k: round(100 * v.notna().to_numpy().mean(), 2) for k, v in panels.items()},
    "region_days_valid": {k: int(v.notna().to_numpy().sum()) for k, v in panels.items()},
    "region_days_total": {k: int(v.size) for k, v in panels.items()},
    "days_with_any_obs": {k: int(v.notna().any(axis=1).sum()) for k, v in panels.items()},
    "pct_days_covered": {k: round(100 * v.notna().any(axis=1).mean(), 1) for k, v in panels.items()},
    "mean_regions_per_covered_day": {k: round(v.notna().any(axis=1).mul(1).sum() and
                                             v.notna().sum(axis=1).sum() / max(v.notna().any(axis=1).sum(), 1), 2)
                                     for k, v in panels.items()},
})
save(miss, "02_missingness_overall.csv")
frag("2.1 Overall missingness on the common 2022-01-01..2026-11-09 grid (7 regions x 1774 days = 12418 region-days)",
     miss.reset_index().rename(columns={"index": "series"}))

# month x year matrices (% missing of expected region-days in that month)
def monthyear_mat(p):
    d = p.copy()
    d["ym"] = d.index.to_period("M")
    g = d.groupby("ym")
    pct = g.apply(lambda x: 100 * x.isna().to_numpy().mean(), include_groups=False)
    cnt = g.apply(lambda x: int(x.notna().to_numpy().sum()), include_groups=False)
    days = g.apply(lambda x: len(x), include_groups=False)
    out = pd.DataFrame({"pct_missing": pct, "n_valid": cnt, "days_in_month": days})
    out["year"] = out.index.year
    out["month"] = out.index.month
    return out

for key, nm in [("GPM precipitation_mm_day", "gpm"), ("POWER PRECTOTCORR (mm/day)", "power_prec"),
                ("SMAP soil_moisture (am)", "smap_am"), ("SMAP soil_moisture (any pass)", "smap_any"),
                ("ECOSTRESS lst_celsius", "ecostress"), ("HLS ndvi", "hls"),
                ("GRACE lwe_thickness_cm (daily-interp view)", "grace")]:
    m = monthyear_mat(panels[key])
    save(m, f"02_monthyear_{nm}.csv")
    piv = m.pivot_table(index="month", columns="year", values="pct_missing")
    piv.index.name = "month"
    frag(f"2.{nm} - % missing of expected (region x day) cells, month x year", piv.round(1))

# HLS: extra view - valid NDVI counts per month
hls_valid = hls[hls["ndvi"].notna()].copy()
hls_month = hls_valid.groupby("month").size().reindex(
    pd.period_range("2022-01", "2026-11", freq="M"), fill_value=0)
save(hls_month.rename("n_valid_ndvi_obs_all_regions").to_frame(), "02_hls_valid_obs_per_month.csv")

# ECOSTRESS: overpass counts per month and day/night split
eco_m = eco.groupby(eco["dt"].dt.tz_localize(None).dt.to_period("M")).agg(
    overpass_rows=("qc", "size"),
    lst_valid=("lst_celsius", "count"),
    daytime_overpass=("daytime", "sum"))
save(eco_m, "02_ecostress_overpass_per_month.csv")
frag("2.ecox ECOSTRESS overpass rows / valid LST per month", eco_m)

# ----------------------------------------------------------------------------
# 3. DISTRIBUTIONS + PLAUSIBILITY
# ----------------------------------------------------------------------------
QS = [0, .01, .05, .25, .5, .75, .95, .99, 1]
series_defs = [
    ("GPM", "precipitation_mm_day", gpm),
    ("POWER", "PRECTOTCORR", pw),
    ("POWER", "T2M", pw), ("POWER", "T2M_MAX", pw), ("POWER", "T2M_MIN", pw),
    ("POWER", "RH2M", pw), ("POWER", "WS2M", pw),
    ("POWER", "ALLSKY_SFC_SW_DWN", pw), ("POWER", "PS", pw),
    ("SMAP", "soil_moisture_m3_m3", smap),
    ("ECOSTRESS", "lst_celsius", eco),
    ("HLS", "ndvi", hls), ("HLS", "ndmi", hls), ("HLS", "valid_coverage", hls),
    ("GRACE", "lwe_thickness_cm", grace), ("GRACE", "uncertainty_cm", grace),
]
qrows = []
for ds, var, df in series_defs:
    for reg in REGIONS + ["ALL"]:
        s = df[var] if reg == "ALL" else df.loc[df["region"] == reg, var]
        s = pd.to_numeric(s, errors="coerce").dropna()
        if len(s) == 0:
            continue
        r = {"dataset": ds, "variable": var, "region": reg, "n": int(len(s)), "n_missing": int(df[var].isna().sum()) if reg == "ALL" else int(df.loc[df["region"] == reg, var].isna().sum())}
        for q in QS:
            r[f"p{int(q*100)}"] = round(float(s.quantile(q)), 4)
        r["mean"] = round(float(s.mean()), 4)
        r["sd"] = round(float(s.std()), 4)
        qrows.append(r)
qt = pd.DataFrame(qrows)
save(qt, "03_quantiles_by_region.csv", index=False)

# region-mean summary table (all regions pooled) for the report body
pooled = qt[qt["region"] == "ALL"].drop(columns=["region"])
frag("3.1 Pooled quantiles (all 7 regions, valid values only)", pooled.set_index(["dataset", "variable"]))

# per-region table for the headline variables
for ds, var in [("GPM", "precipitation_mm_day"), ("SMAP", "soil_moisture_m3_m3"),
                ("ECOSTRESS", "lst_celsius"), ("HLS", "ndvi"), ("HLS", "ndmi"),
                ("GRACE", "lwe_thickness_cm"), ("POWER", "T2M"), ("POWER", "RH2M"),
                ("POWER", "PRECTOTCORR")]:
    t = qt[(qt["dataset"] == ds) & (qt["variable"] == var) & (qt["region"] != "ALL")]
    frag(f"3.x {ds} {var} - quantiles by region", t.set_index("region"))

# plausibility flags
checks = [
    ("GPM", "precipitation_mm_day", gpm, lambda s: s > 300, "> 300 mm/day", "physically impossible for a daily total"),
    ("POWER", "PRECTOTCORR", pw, lambda s: s > 300, "> 300 mm/day", "physically impossible for a daily total"),
    ("POWER", "PRECTOTCORR", pw, lambda s: s < 0, "< 0 mm/day", "negative precipitation"),
    ("POWER", "RH2M", pw, lambda s: (s < 0) | (s > 100), "outside 0-100 %", "invalid humidity"),
    ("POWER", "WS2M", pw, lambda s: s < 0, "< 0 m/s", "negative wind speed"),
    ("POWER", "ALLSKY_SFC_SW_DWN", pw, lambda s: s < 0, "< 0 MJ/m2/day", "negative irradiance"),
    ("POWER", "PS", pw, lambda s: (s < 50) | (s > 110), "outside 50-110 kPa", "invalid pressure"),
    ("POWER", "T2M", pw, lambda s: (s < -10) | (s > 50), "outside -10..50 C", "implausible air temp"),
    ("POWER", "T2M", pw, lambda s: (s > pw["T2M_MAX"]) | (s < pw["T2M_MIN"]), "T2M outside [MIN,MAX]", "internal inconsistency"),
    ("SMAP", "soil_moisture_m3_m3", smap, lambda s: (s < 0) | (s > 0.65), "outside 0-0.65", "invalid volumetric SM"),
    ("ECOSTRESS", "lst_celsius", eco, lambda s: (s < -20) | (s > 70), "outside -20..70 C", "invalid LST"),
    ("HLS", "ndvi", hls, lambda s: (s < -1) | (s > 1), "outside -1..1", "invalid NDVI"),
    ("HLS", "ndmi", hls, lambda s: (s < -1) | (s > 1), "outside -1..1", "invalid NDMI"),
    ("HLS", "valid_coverage", hls, lambda s: (s < 0) | (s > 1), "outside 0..1", "invalid coverage"),
]
prows = []
for ds, var, df, fn, rule, why in checks:
    s = pd.to_numeric(df[var], errors="coerce")
    try:
        bad = fn(s) & s.notna()
    except Exception:
        bad = pd.Series(False, index=s.index)
    per = df.loc[bad.fillna(False), "region"].value_counts().reindex(REGIONS, fill_value=0)
    prows.append(dict(dataset=ds, variable=var, rule=rule, why=why,
                      n_flagged=int(bad.fillna(False).sum()),
                      pct_of_valid=round(100 * bad.fillna(False).sum() / max(s.notna().sum(), 1), 4),
                      **{f"n_{r}": int(per[r]) for r in REGIONS}))
plaus = pd.DataFrame(prows)
save(plaus, "03_plausibility_flags.csv", index=False)
frag("3.2 Physical-plausibility checks", plaus.drop(columns=[c for c in plaus.columns if c.startswith('n_')]))
frag("3.2b Flag counts per region", plaus[["dataset", "variable", "rule"] + [c for c in plaus.columns if c.startswith('n_')]])

# inter-source sanity: does every region have the same latitude? does grid cell differ?
grid_chk = gpm.groupby("region")[["latitude", "longitude", "grid_lat", "grid_lon"]].first()
save(grid_chk, "03_region_grid.csv")

# ----------------------------------------------------------------------------
# 4. SEASONALITY
# ----------------------------------------------------------------------------
def climatology(p, how="mean"):
    d = p.copy()
    m = d.index.month
    g = d.groupby(m)
    return g.mean() if how == "mean" else g.sum()

seas_defs = [
    ("GPM precipitation (mm/day)", gpm_p, "mean"),
    ("POWER PRECTOTCORR (mm/day)", pw_p, "mean"),
    ("POWER T2M (C)", pw_p if False else panel(pw, "T2M"), "mean"),
    ("POWER RH2M (%)", panel(pw, "RH2M"), "mean"),
    ("POWER ALLSKY_SFC_SW_DWN (MJ/m2/d)", pw_sw, "mean"),
    ("SMAP soil moisture am (m3/m3)", smap_am, "mean"),
    ("ECOSTRESS LST (C)", eco_p, "mean"),
    ("HLS NDVI", hls_p, "mean"),
    ("HLS NDMI", panel(hls, "ndmi"), "mean"),
    ("GRACE LWE (cm)", grace_p, "mean"),
]
clim_rows = []
for nm, p, how in seas_defs:
    c = p.mean(axis=1).groupby(p.index.month).mean()   # mean across regions then month
    c = c.reindex(range(1, 13))
    clim_rows.append(pd.Series(c, name=nm))
clim = pd.DataFrame(clim_rows).T
clim.index.name = "month"
save(clim, "04_monthly_climatology.csv")
frag("4.1 Monthly climatology, mean over 7 regions (monthly means of the daily series)", clim.round(3))

amp_rows = []
for nm, p, how in seas_defs:
    per_reg = p.groupby(p.index.month).mean().reindex(range(1, 13))
    for reg in per_reg.columns:
        c = per_reg[reg].dropna()
        if len(c) < 6:
            continue
        amp_rows.append(dict(variable=nm, region=reg, peak_month=int(c.idxmax()), trough_month=int(c.idxmin()),
                             peak_value=round(float(c.max()), 3), trough_value=round(float(c.min()), 3),
                             amplitude=round(float(c.max() - c.min()), 3),
                             amplitude_pct_of_mean=round(100 * float(c.max() - c.min()) / float(c.mean()), 1),
                             cv_of_monthly_means=round(float(c.std() / c.mean()), 3)))
amp = pd.DataFrame(amp_rows)
save(amp, "04_seasonality_amplitude.csv", index=False)
frag("4.2 Per-region seasonal amplitude (from monthly means of the daily/monthly series)",
     amp.pivot_table(index="variable", columns="region", values="amplitude").round(3))
frag("4.2b Peak month per region", amp.pivot_table(index="variable", columns="region", values="peak_month"))

# GRACE month-of-year (calendar) vs month index
with open(os.path.join(OUT, "_fragments_part1.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(FRAG))

json.dump({"n_days_grid": NDAYS, "regions": REGIONS}, open(os.path.join(OUT, "_meta.json"), "w"))
print("part1 done; fragments:", len(FRAG))
print(qt.groupby(["dataset", "variable"]).size())
