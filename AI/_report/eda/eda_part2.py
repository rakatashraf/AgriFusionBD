"""EDA part 2: temporal structure, cross-correlation, source agreement, extremes, verdicts.
Run:  .venv\\Scripts\\python.exe -I eda_part2.py
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


# ---------------------------------------------------------------- load (same cleaning as part 1)
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
pw = pd.concat([pd.read_csv(f) for f in
                sorted(glob.glob(os.path.join(POWER_DIR, "*_20220101_to_*.csv")))], ignore_index=True)
pw["PRECTOTCORR"] = pw["PRECTOTCORR"] / 24.0

smap = smap.sort_values(["region", "date", "pass", "source_file"]).drop_duplicates(
    ["region", "date", "pass"], keep="first")
smap.loc[smap["retrieval_qual_flag"] == 7, "soil_moisture_m3_m3"] = np.nan
smap.loc[smap["surface_flag"] == 2047, "soil_moisture_m3_m3"] = np.nan

eco["dt"] = pd.to_datetime(eco["observed_utc"])
eco.loc[eco["qc"] == 65535, "lst_celsius"] = np.nan
eco["date"] = eco["dt"].dt.normalize()
eco["hour_local"] = ((eco["dt"].dt.hour + eco["dt"].dt.minute / 60.0) + 6.0) % 24.0
eco["daytime"] = eco["hour_local"].between(9, 16)

hls["dt"] = pd.to_datetime(hls["observed_utc"], format="mixed", utc=True)
hls["date"] = hls["dt"].dt.tz_convert(None).dt.normalize()
hls["month"] = hls["dt"].dt.tz_convert(None).dt.to_period("M")

REGIONS = sorted(gpm["region"].unique())
GRID = pd.date_range("2022-01-01", "2026-11-09", freq="D")


def panel(df, var, datecol="date", agg="first", index=GRID):
    d = df.copy()
    d["date"] = pd.to_datetime(d[datecol]).dt.normalize()
    p = d.pivot_table(index="date", columns="region", values=var, aggfunc=agg)
    return p.reindex(index).reindex(columns=REGIONS)


gpm_p = panel(gpm, "precipitation_mm_day")
pw_p = panel(pw, "PRECTOTCORR")
pw_sw = panel(pw, "ALLSKY_SFC_SW_DWN")
smap_am = panel(smap[smap["pass"] == "am"], "soil_moisture_m3_m3")
smap_pm = panel(smap[smap["pass"] == "pm"], "soil_moisture_m3_m3")
smap_any = panel(smap, "soil_moisture_m3_m3", agg="mean")
eco_p = panel(eco, "lst_celsius")
hls_p = panel(hls, "ndvi")

# ---------------------------------------------------------------- 5. temporal structure
def acf_pairwise(s, max_lag):
    """ACF with pairwise-complete observations; returns acf, n_pairs."""
    s = pd.Series(s).astype(float)
    out, npair = {}, {}
    v = s.to_numpy()
    for L in range(1, max_lag + 1):
        x, y = v[:-L], v[L:]
        m = ~np.isnan(x) & ~np.isnan(y)
        npair[L] = int(m.sum())
        out[L] = float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 30 else np.nan
    return pd.Series(out), pd.Series(npair)


daily_vars = [
    ("GPM precipitation_mm_day", gpm_p),
    ("POWER PRECTOTCORR mm/day", pw_p),
    ("POWER T2M", panel(pw, "T2M")),
    ("POWER RH2M", panel(pw, "RH2M")),
    ("POWER WS2M", panel(pw, "WS2M")),
    ("POWER ALLSKY_SFC_SW_DWN", pw_sw),
    ("POWER PS", panel(pw, "PS")),
    ("SMAP soil_moisture am", smap_am),
    ("SMAP soil_moisture pm", smap_pm),
    ("ECOSTRESS LST (sparse)", eco_p),
]
acf_rows = []
acf_detail = {}
for nm, p in daily_vars:
    a_all = {}
    for reg in REGIONS:
        a, npair = acf_pairwise(p[reg], 30)
        a_all[reg] = a
        acf_rows.append(dict(variable=nm, region=reg, lag1=a[1], lag2=a[2], lag3=a[3], lag7=a[7],
                             lag14=a[14], lag30=a[30], n_pairs_lag1=int(npair[1]),
                             n_pairs_lag30=int(npair[30])))
    acf_detail[nm] = pd.DataFrame(a_all)
acf = pd.DataFrame(acf_rows)
save(acf, "05_acf_daily_by_region.csv", index=False)

summary = acf.groupby("variable").agg(
    lag1_mean=("lag1", "mean"), lag1_min=("lag1", "min"), lag1_max=("lag1", "max"),
    lag7_mean=("lag7", "mean"), lag30_mean=("lag30", "mean"),
    n_pairs_lag1=("n_pairs_lag1", "mean")).round(3)
# decorrelation lag: first lag where region-mean acf < 0.2
dec = {}
for nm, df in acf_detail.items():
    m = df.mean(axis=1)
    below = m[m < 0.2]
    dec[nm] = int(below.index[0]) if len(below) else ">30"
summary["lag_where_acf<0.2"] = pd.Series(dec)
save(summary, "05_acf_daily_summary.csv")
frag("5.1 Daily autocorrelation, lag 1-30 (pairwise-complete), per variable (mean/min/max over 7 regions)",
     summary.reset_index())

# effective sample size from lag-1 autocorrelation: n_eff = n(1-r1)/(1+r1)
neff = summary.reset_index()[['variable', 'lag1_mean', 'lag_where_acf<0.2']].copy()
neff['n_days'] = 1774
neff['n_eff'] = (1774 * (1 - neff['lag1_mean']) / (1 + neff['lag1_mean'])).round(1)
neff.loc[neff['variable'].str.contains('SMAP|ECOSTRESS'), 'n_eff'] = np.nan
save(neff, '05_acf_neff.csv', index=False)
frag('5.1b Effective sample size implied by the lag-1 autocorrelation (n = 1,774 days)', neff)

# full ACF curve at selected lags, region-mean
curve = pd.DataFrame({nm: df.mean(axis=1) for nm, df in acf_detail.items()})
save(curve, "05_acf_daily_curve_regionmean.csv")
frag("5.2 Region-mean ACF curve, lags 1-30", curve.loc[[1, 2, 3, 5, 7, 10, 14, 20, 25, 30]].round(3))

# region-level lag1 table
frag("5.3 Lag-1 autocorrelation by region", acf.pivot_table(index="variable", columns="region", values="lag1").round(3))

# monthly series autocorrelation
MIDX = pd.period_range("2022-01", "2026-11", freq="M").to_timestamp()
mon = pd.DataFrame({
    "GPM precip (monthly mean)": gpm_p.resample("MS").mean().mean(axis=1),
    "GPM precip (monthly total)": gpm_p.resample("MS").sum().mean(axis=1),
    "POWER PRECTOTCORR (monthly mean)": pw_p.resample("MS").mean().mean(axis=1),
    "POWER T2M (monthly mean)": panel(pw, "T2M").resample("MS").mean().mean(axis=1),
    "SMAP soil moisture am (monthly mean)": smap_am.resample("MS").mean().mean(axis=1),
    "HLS NDVI (monthly mean)": hls_p.resample("MS").mean().mean(axis=1),
    "ECOSTRESS LST (monthly mean)": eco_p.resample("MS").mean().mean(axis=1),
    "GRACE LWE (monthly, mascon 1321)": grace.pivot(
        index="date", columns="region", values="lwe_thickness_cm")["Central_Dhaka"].set_axis(
        grace.pivot(index="date", columns="region", values="lwe_thickness_cm").index.to_period("M").to_timestamp()),
}).reindex(MIDX)
macf = {}
mn = {}
for c in mon.columns:
    a, npair = acf_pairwise(mon[c].to_numpy(), 12)
    macf[c] = a
    mn[c] = npair
macf = pd.DataFrame(macf)
save(macf, "05_acf_monthly.csv")
frag("5.4 Monthly-series autocorrelation (lags 1-12 months)", macf.round(3))
frag("5.4b n pairs at lag 1 / lag 12", pd.DataFrame(mn).loc[[1, 12]])
mneff = pd.DataFrame({'lag1_acf': macf.loc[1], 'n_months': 59})
mneff['n_eff'] = (59 * (1 - mneff['lag1_acf']) / (1 + mneff['lag1_acf'])).round(1)
save(mneff, '05_acf_monthly_neff.csv')
frag('5.4c Effective sample size of the monthly series (n = 59 months)', mneff)

# ---------------------------------------------------------------- 6. cross-correlation
def xcorr(a, b, lags):
    """corr(a[t], b[t+L]); L>0 means b lags a."""
    a = pd.Series(a).astype(float).to_numpy()
    b = pd.Series(b).astype(float).to_numpy()
    out = {}
    for L in lags:
        if L >= 0:
            x, y = a[:len(a) - L] if L > 0 else a, b[L:]
        else:
            x, y = a[-L:], b[:len(b) + L]
        m = ~np.isnan(x) & ~np.isnan(y)
        out[L] = float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 30 else np.nan
    return pd.Series(out)


def deseason(p):
    """remove month-of-year climatology per column, plus linear trend."""
    out = p.copy()
    for c in out.columns:
        s = out[c]
        clim = s.groupby(s.index.month).transform("mean")
        r = s - clim
        t = np.arange(len(r))
        m = r.notna()
        if m.sum() > 10:
            b1, b0 = np.polyfit(t[m], r[m], 1)
            r = r - (b0 + b1 * t)
        out[c] = r
    return out


def bestlag(x):
    if x.notna().sum() == 0:
        return np.nan, np.nan
    return int(x.idxmax()), round(float(x.max()), 3)


LAGS = list(range(-30, 31))
cc_rows = []
pairs_daily = [
    ("GPM rain -> SMAP SM am", gpm_p, smap_am),
    ("GPM rain -> SMAP SM pm", gpm_p, smap_pm),
    ("POWER rain -> SMAP SM am", pw_p, smap_am),
    ("GPM rain -> ECOSTRESS LST", gpm_p, eco_p),
    ("POWER rain -> ECOSTRESS LST", pw_p, eco_p),
    ("GPM rain -> SMAP SM (any pass)", gpm_p, smap_any),
    ("POWER rain -> SMAP SM (any pass)", pw_p, smap_any),
]
for nm, a, b in pairs_daily:
    for mode, (aa, bb) in {"raw": (a, b), "deseasonalised": (deseason(a), deseason(b))}.items():
        for reg in REGIONS + ["POOLED"]:
            if reg == "POOLED":
                av, bv = aa.mean(axis=1), bb.mean(axis=1)
            else:
                av, bv = aa[reg], bb[reg]
            x = xcorr(av, bv, LAGS)
            bl, mc = bestlag(x)
            cc_rows.append(dict(pair=nm, mode=mode, region=reg,
                                best_lag=bl, max_corr=mc,
                                corr_lag0=round(float(x[0]), 3),
                                corr_lag_neg5=round(float(x[-5]), 3) if -5 in x else np.nan,
                                corr_lag_pos5=round(float(x[5]), 3),
                                corr_lag_pos10=round(float(x[10]), 3)))
        # store full curve for pooled
        xp = xcorr(aa.mean(axis=1), bb.mean(axis=1), LAGS)
        if mode == "raw":
            save(xp.rename(nm).to_frame(), f"06_cc_curve_{nm.split('->')[1].strip().replace(' ','_')}.csv")

# daytime-only ECOSTRESS LST, both rainfall sources, raw and deseasonalised
eco_day = panel(eco[eco["daytime"]], "lst_celsius")
for src_name, src in [("GPM", gpm_p), ("POWER", pw_p)]:
    for mode in ["raw", "deseasonalised"]:
        for reg in REGIONS + ["POOLED"]:
            a = src.mean(axis=1) if reg == "POOLED" else src[reg]
            b = eco_day.mean(axis=1) if reg == "POOLED" else eco_day[reg]
            if mode == "deseasonalised":
                a = deseason(a.to_frame("a"))["a"]
                b = deseason(b.to_frame("b"))["b"]
            x = xcorr(a, b, LAGS)
            bl, mc = bestlag(x)
            cc_rows.append(dict(pair=f"{src_name} rain -> ECOSTRESS LST (daytime only)", mode=mode, region=reg,
                                best_lag=bl, max_corr=mc,
                                corr_lag0=round(float(x[0]), 3), corr_lag_neg5=round(float(x[-5]), 3),
                                corr_lag_pos5=round(float(x[5]), 3), corr_lag_pos10=round(float(x[10]), 3)))

cc = pd.DataFrame(cc_rows)
save(cc, "06_crosscorr_daily.csv", index=False)
frag("6.1 Daily cross-correlation, rain (driver) vs response, lags -30..+30 days. 'best_lag' = lag of maximum correlation (+ = response lags rain)",
     cc[cc.region == "POOLED"].set_index(["pair", "mode"]).round(3))
frag("6.1b Per-region lag of maximum correlation, raw series",
     cc[(cc["mode"] == "raw") & (cc.region != "POOLED")].pivot_table(index="pair", columns="region", values="best_lag"))
frag("6.1c Per-region max correlation, raw series",
     cc[(cc["mode"] == "raw") & (cc.region != "POOLED")].pivot_table(index="pair", columns="region", values="max_corr").round(3))

# monthly cross-correlation (rain monthly total vs HLS NDVI monthly mean, GRACE, SM)
def monthly(p, how="mean"):
    return p.resample("MS").agg(how)

m_rain_gpm = monthly(gpm_p, "sum").mean(axis=1)
m_rain_pw = monthly(pw_p, "sum").mean(axis=1)
m_ndvi = monthly(hls_p, "mean")
m_sm = monthly(smap_any, "mean")
m_grace = grace.pivot(index="date", columns="region", values="lwe_thickness_cm")
m_grace.index = m_grace.index.to_period("M").to_timestamp()
m_grace = m_grace.resample("MS").mean()

# put every monthly series on one common index so xcorr sees equal-length arrays
m_rain_gpm = m_rain_gpm.reindex(MIDX)
m_rain_pw = m_rain_pw.reindex(MIDX)
m_ndvi = m_ndvi.reindex(MIDX)
m_sm = m_sm.reindex(MIDX)
m_grace = m_grace.reindex(MIDX)

MLAGS = list(range(-6, 7))
mrow = []
for nm, a in [("GPM monthly rain total", m_rain_gpm), ("POWER monthly rain total", m_rain_pw)]:
    for bname, b in [("HLS NDVI", m_ndvi), ("SMAP SM (any pass)", m_sm), ("GRACE LWE", m_grace)]:
        for reg in (REGIONS + ["POOLED"]):
            av = a
            bv = b.mean(axis=1) if reg == "POOLED" else b[reg]
            x = xcorr(av, bv, MLAGS)
            if x.notna().sum() == 0:
                continue
            bl, mc = bestlag(x)
            mrow.append(dict(driver=nm, response=bname, region=reg,
                             best_lag_months=bl, max_corr=mc,
                             corr_lag0=round(float(x[0]), 3), n=int(len(av))))
mcc = pd.DataFrame(mrow)
save(mcc, "06_crosscorr_monthly.csv", index=False)
frag("6.2 Monthly cross-correlation (lags -6..+6 months), monthly rain totals vs monthly means",
     mcc[mcc.region == "POOLED"].set_index(["driver", "response"]))
frag("6.2b Per-region best lag (months)", mcc.pivot_table(index=["driver", "response"], columns="region",
                                                          values="best_lag_months"))
frag("6.2c Per-region max correlation", mcc.pivot_table(index=["driver", "response"], columns="region",
                                                        values="max_corr").round(3))

# ---------------------------------------------------------------- 7. GPM vs POWER agreement
j = pd.DataFrame({"gpm": gpm_p.stack(), "pw": pw_p.stack()}).dropna()
j.index.names = ["date", "region"]
j = j.reset_index()
j["month"] = j["date"].dt.to_period("M")
j["season"] = np.where(j["date"].dt.month.isin([11, 12, 1, 2, 3]), "dry (Nov-Mar)", "wet (Apr-Oct)")
j["diff"] = j["pw"] - j["gpm"]

def stats(g):
    return pd.Series(dict(n=len(g), mean_gpm=g["gpm"].mean(), mean_pw=g["pw"].mean(),
                          bias_pw_minus_gpm=g["diff"].mean(),
                          rmse=np.sqrt((g["diff"] ** 2).mean()),
                          mae=g["diff"].abs().mean(),
                          corr=g["gpm"].corr(g["pw"]),
                          slope=np.polyfit(g["gpm"], g["pw"], 1)[0],
                          gpm_zero_days=int((g["gpm"] == 0).sum()),
                          pw_gt1_when_gpm0=int(((g["gpm"] == 0) & (g["pw"] > 1)).sum())))

agree_all = pd.DataFrame({"overall": stats(j), "wet": stats(j[j.season.str.startswith("wet")]),
                          "dry": stats(j[j.season.str.startswith("dry")])}).round(3)
save(agree_all, "07_agreement_overall.csv")
frag("7.1 GPM vs POWER PRECTOTCORR (mm/day after /24), 12292 paired region-days", agree_all)

per_reg = j.groupby("region").apply(stats, include_groups=False).round(3)
save(per_reg, "07_agreement_by_region.csv")
frag("7.1b Agreement by region", per_reg)

monthly_tot = j.groupby("month").agg(gpm_mm=("gpm", "sum"), power_mm=("pw", "sum"), n=("gpm", "size"))
monthly_tot["gpm_mm"] = monthly_tot["gpm_mm"] / 7
monthly_tot["power_mm"] = monthly_tot["power_mm"] / 7
monthly_tot["ratio_power_over_gpm"] = (monthly_tot["power_mm"] / monthly_tot["gpm_mm"]).round(2)
monthly_tot = monthly_tot.round(2)
save(monthly_tot, "07_monthly_totals.csv")
frag("7.2 Monthly rainfall totals per region (mm), GPM vs POWER (POWER/24)", monthly_tot)

mt = monthly_tot.copy()
mt["year"] = mt.index.year
mt["mon"] = mt.index.month
save(mt.pivot_table(index="mon", columns="year", values="ratio_power_over_gpm"),
     "07_ratio_month_year.csv")
frag("7.2b POWER/GPM monthly-total ratio, month x year",
     mt.pivot_table(index="mon", columns="year", values="ratio_power_over_gpm").round(2))

# GPM final vs late, matched months
g = gpm.copy()
g["mon"] = g["date"].dt.month
gm = g.groupby(["run", "mon"])["precipitation_mm_day"].agg(["mean", "count"]).round(3)
save(gm, "07_gpm_run_by_month.csv")
frag("7.3 GPM final vs late run, mean daily precipitation by calendar month", gm.unstack(0))

# ---------------------------------------------------------------- 8. anomalies / extremes
ext_rows = []
targets = [("GPM", gpm_p), ("POWER PRECTOTCORR", pw_p), ("SMAP SM (any)", smap_any),
           ("ECOSTRESS LST", eco_p), ("POWER T2M", panel(pw, "T2M"))]
for nm, p in targets:
    for reg in REGIONS:
        s = p[reg].dropna()
        if len(s) < 30:
            continue
        q99 = s.quantile(0.99)
        q01 = s.quantile(0.01)
        ext_rows.append(dict(variable=nm, region=reg, n=int(len(s)), p01=round(float(q01), 3),
                             p99=round(float(q99), 3), n_ge_p99=int((s >= q99).sum()),
                             n_le_p01=int((s <= q01).sum()),
                             max=round(float(s.max()), 3), max_date=str(s.idxmax().date()),
                             min=round(float(s.min()), 3), min_date=str(s.idxmin().date())))
ext = pd.DataFrame(ext_rows)
save(ext, "08_extremes_p99_by_region.csv", index=False)
frag("8.1 Per-region p01/p99 extremes and counts (>=p99 flags)",
     ext[ext.variable.isin(["GPM", "SMAP SM (any)", "ECOSTRESS LST"])].set_index(["variable", "region"]).round(3))

# largest rainfall events
top_reg = []
for reg in REGIONS:
    s = gpm_p[reg].dropna().sort_values(ascending=False).head(5)
    for d, v in s.items():
        top_reg.append(dict(region=reg, rank=len(top_reg) % 5 + 1, date=str(d.date()), mm=round(float(v), 2)))
top_reg = pd.DataFrame(top_reg)
save(top_reg, "08_top5_rainfall_per_region.csv", index=False)
frag("8.2 Top-5 daily rainfall events per region (GPM)", top_reg.pivot_table(
    index="rank", columns="region", values="mm"))

top_mean = gpm_p.mean(axis=1).sort_values(ascending=False).head(15)
tm = pd.DataFrame({"date": top_mean.index.strftime("%Y-%m-%d"), "mean_mm_across_7_regions": top_mean.round(2).values,
                   "daily_uniform": ""})
tm["n_regions_gt_50mm"] = [int((gpm_p.loc[d] > 50).sum()) for d in top_mean.index]
tm["max_region_mm"] = [round(float(gpm_p.loc[d].max()), 2) for d in top_mean.index]
tm["argmax_region"] = [gpm_p.loc[d].idxmax() for d in top_mean.index]
save(tm, "08_top15_widespread_rainfall_days.csv", index=False)
frag("8.3 Top-15 most widespread heavy-rain days (ranked by 7-region mean)", tm.drop(columns=["daily_uniform"]))

# SMAP ceiling clamp
clamp = []
for reg in REGIONS:
    s = smap_any[reg].dropna()
    mx = s.max()
    clamp.append(dict(region=reg, n_valid=len(s), max=round(float(mx), 4),
                      n_at_max=int((s >= mx - 1e-9).sum()),
                      pct_at_max=round(100 * (s >= mx - 1e-9).mean(), 2),
                      second_distinct_max=round(float(s[s < mx - 1e-9].max()), 4)))
clamp = pd.DataFrame(clamp)
save(clamp, "08_smap_ceiling_clamp.csv", index=False)
frag("8.4 SMAP satellite-retrieval ceiling pile-up (identical maximum repeated many times)", clamp)

# GRACE duplicate regions / independent spatial information
gp = grace.pivot(index="date", columns="region", values="lwe_thickness_cm")
dup = pd.DataFrame({"mascon_id": grace.groupby("region")["mascon_id"].first(),
                    "grid_lat": grace.groupby("region")["grid_lat"].first(),
                    "grid_lon": grace.groupby("region")["grid_lon"].first(),
                    "cri_scale_factor": grace.groupby("region")["cri_scale_factor"].first()})
dup["identical_to_Central_Dhaka"] = [bool(np.allclose(gp[r], gp["Central_Dhaka"])) for r in dup.index]
save(dup, "08_grace_duplicate_check.csv")
frag("8.5 GRACE: regions with byte-identical LWE series (same mascon 1321)", dup)

# GPM dry-season suppression evidence
dry = monthly_tot[(monthly_tot.index.month.isin([12, 1, 2]))]
frag("8.6 Dry-season monthly totals (Dec/Jan/Feb), mm per region - GPM vs POWER", dry)

# ---------------------------------------------------------------- 9. verdict
verd = pd.DataFrame([
    dict(dataset="GPM IMERG precipitation", cadence="daily",
         region_days=12418, valid=12418, usable_pct=100.0,
         impute="none needed; late-run period (2025-10-01+) is a different retrieval",
         never_interpolate="do not gap-fill; do not splice final and late run without a run indicator"),
    dict(dataset="POWER weather (8 params)", cadence="daily",
         region_days=12418, valid=12292, usable_pct=99.0,
         impute="3 trailing days per region; SW_DWN 86 days/region (2026-08-01..2026-10-22)",
         never_interpolate="PRECTOTCORR rescaled /24 - never mix raw and rescaled columns"),
    dict(dataset="SMAP soil moisture", cadence="2 passes/day",
         region_days=24206, valid=9592, usable_pct=39.6,
         impute="~60% of pass-days; model as irregular observations, not a daily grid",
         never_interpolate="no linear interpolation across the 60% gap structure; ceiling values are clipped"),
    dict(dataset="ECOSTRESS LST", cadence="per-overpass",
         region_days=2819, valid=933, usable_pct=33.1,
         impute="cannot be imputed at 92.5% day-level missing",
         never_interpolate="never interpolate LST in time; overpass hour varies 0-23 local"),
    dict(dataset="HLS NDVI/NDMI", cadence="monthly attempt",
         region_days=413, valid=220, usable_pct=53.3,
         impute="no - use as sparse labels only",
         never_interpolate="never interpolate; 19% of values come from <=5 valid pixels, 32% from <10% coverage"),
    dict(dataset="GRACE LWE", cadence="monthly",
         region_days=399, valid=399, usable_pct=100.0,
         impute="none within 2022-01..2026-09",
         never_interpolate="do not upsample to daily; only 4 independent mascon series exist"),
    dict(dataset="SRTM terrain", cadence="static",
         region_days=7, valid=7, usable_pct=100.0,
         impute="none",
         never_interpolate="static covariate"),
])
save(verd, "09_verdict.csv", index=False)
frag("9.1 Data-quality verdict", verd)

with open(os.path.join(OUT, "_fragments_part2.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(FRAG))
print("part2 done; fragments:", len(FRAG))
