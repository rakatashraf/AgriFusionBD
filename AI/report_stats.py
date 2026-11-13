"""Compute the statistics quoted in the data report.

Reads the CSVs in Data/ and writes Data/_report/stats.json plus a few charts.
Every number in the report comes from here, so nothing is asserted by eye.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
OUT = BASE / "_report"
OUT.mkdir(exist_ok=True)

MONSOON = [6, 7, 8, 9]
REGION_ORDER = [
    "Northwest_Rajshahi",
    "North_Rangpur",
    "Central_Dhaka",
    "Northeast_Sylhet",
    "Southwest_Khulna",
    "South_Barishal",
    "Southeast_Chattogram",
]


def load(name: str, datecol: str) -> pd.DataFrame:
    path = sorted((BASE / name).glob("*.csv"))
    path = [p for p in path if "provenance" not in p.name and "_all_regions" in p.name]
    df = pd.read_csv(sorted(path)[-1])
    df[datecol] = pd.to_datetime(df[datecol])
    df["month"] = df[datecol].dt.month
    df["year"] = df[datecol].dt.year
    return df


def slope_per_year(x: pd.Series, y: pd.Series) -> float:
    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return float("nan")
    x, y = x[ok], y[ok]
    years = (x - x.min()) / (365.25 * 24 * 3600 * 1e9)
    years = (x - x.min()) / np.timedelta64(1, "D") / 365.25 if np.issubdtype(x.dtype, np.datetime64) else x
    return float(np.polyfit(years, y, 1)[0])


def corr(a, b) -> float:
    a = pd.Series(a, dtype="float64")
    b = pd.Series(b, dtype="float64")
    ok = a.notna() & b.notna()
    if ok.sum() < 6:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def main() -> int:
    stats: dict = {}
    gpm = load("GPM_IMERG_Rainfall", "date")
    smap = load("SMAP_SoilMoisture", "date")
    eco = load("ECOSTRESS_LST_ET", "observed_utc")
    hls = load("HLS_Vegetation_Indices", "observed_utc")
    grace = load("GRACE_WaterStorage", "date")
    srtm = pd.read_csv(BASE / "SRTM_Elevation" / "SRTM_terrain_summary_all_regions.csv")

    # ---- precipitation -------------------------------------------------
    rain = gpm.groupby(["region", "date"])["precipitation_mm_day"].mean().reset_index()
    rain["year"] = rain.date.dt.year
    rain["month"] = rain.date.dt.month
    annual = rain.groupby(["region", "year"])["precipitation_mm_day"].sum().reset_index()
    full_years = [2022, 2023, 2024, 2025]
    annual_full = annual[annual.year.isin(full_years)]
    per_region = {}
    for region, g in rain.groupby("region"):
        a = annual_full[annual_full.region == region]["precipitation_mm_day"]
        monthly = g.groupby("month")["precipitation_mm_day"].agg(["mean", "sum", "count"])
        monsoon_share = g[g.month.isin(MONSOON)]["precipitation_mm_day"].sum() / g["precipitation_mm_day"].sum()
        idx = g["precipitation_mm_day"].idxmax()
        per_region[region] = {
            "annual_mean_mm": round(float(a.mean()), 1),
            "annual_min_mm": round(float(a.min()), 1),
            "annual_max_mm": round(float(a.max()), 1),
            "annual_cv": round(float(a.std() / a.mean()), 3),
            "monsoon_share": round(float(monsoon_share), 3),
            "wettest_month": int(monthly["mean"].idxmax()),
            "wettest_month_mm_day": round(float(monthly["mean"].max()), 2),
            "driest_month": int(monthly["mean"].idxmin()),
            "driest_month_mm_day": round(float(monthly["mean"].min()), 2),
            "max_daily_mm": round(float(g["precipitation_mm_day"].max()), 1),
            "max_daily_date": str(g.loc[idx, "date"].date()),
            "wet_days_per_year": round(float((g["precipitation_mm_day"] >= 1).sum() / g.year.nunique()), 0),
            "heavy_days_per_year": round(float((g["precipitation_mm_day"] >= 50).sum() / g.year.nunique()), 1),
        }
    stats["precipitation"] = per_region
    stats["precipitation_monthly"] = (
        rain.groupby(["region", "month"])["precipitation_mm_day"].mean().unstack().round(2).to_dict()
    )

    # ---- soil moisture -------------------------------------------------
    sm = smap.groupby(["region", "date"]).agg(
        sm=("soil_moisture_m3_m3", "mean"), qc=("retrieval_qual_flag", "mean")
    ).reset_index()
    sm["month"] = sm.date.dt.month
    sm["year"] = sm.date.dt.year
    sm_stats = {}
    for region, g in sm.groupby("region"):
        v = g["sm"].dropna()
        sm_stats[region] = {
            "mean": round(float(v.mean()), 3),
            "median": round(float(v.median()), 3),
            "p10": round(float(v.quantile(0.1)), 3),
            "p90": round(float(v.quantile(0.9)), 3),
            "filled_share": round(float(g["sm"].notna().mean()), 3),
            "monthly_climatology": {int(m): round(float(x), 3) for m, x in g.groupby("month")["sm"].mean().items()},
        }
    stats["soil_moisture"] = sm_stats

    # ---- vegetation ----------------------------------------------------
    hls_stats = {}
    for region, g in hls.groupby("region"):
        v = g.dropna(subset=["ndvi"])
        hls_stats[region] = {
            "months_total": int(len(g)),
            "months_with_ndvi": int(len(v)),
            "ndvi_mean": round(float(v["ndvi"].mean()), 3),
            "ndvi_min": round(float(v["ndvi"].min()), 3),
            "ndvi_max": round(float(v["ndvi"].max()), 3),
            "ndmi_mean": round(float(v["ndmi"].dropna().mean()), 3) if v["ndmi"].notna().any() else None,
            "monthly_climatology": {int(m): round(float(x), 3) for m, x in v.groupby("month")["ndvi"].mean().items()},
            "peak_month": int(v.groupby("month")["ndvi"].mean().idxmax()) if len(v) > 3 else None,
            "trough_month": int(v.groupby("month")["ndvi"].mean().idxmin()) if len(v) > 3 else None,
        }
    stats["vegetation"] = hls_stats

    # ---- surface temperature -------------------------------------------
    eco_stats = {}
    for region, g in eco.groupby("region"):
        v = g["lst_celsius"].dropna()
        eco_stats[region] = {
            "observations": int(len(g)),
            "with_lst": int(len(v)),
            "mean_c": round(float(v.mean()), 1),
            "min_c": round(float(v.min()), 1),
            "max_c": round(float(v.max()), 1),
            "monthly_climatology": {int(m): round(float(x), 1) for m, x in g.groupby("month")["lst_celsius"].mean().items()},
        }
    stats["surface_temperature"] = eco_stats

    # ---- water storage --------------------------------------------------
    grace_stats = {}
    for region, g in grace.groupby("region"):
        g = g.sort_values("date")
        years = (g["date"] - g["date"].min()).dt.days / 365.25
        slope = float(np.polyfit(years, g["lwe_thickness_cm"], 1)[0])
        monthly = g.groupby("month")["lwe_thickness_cm"].mean()
        grace_stats[region] = {
            "slope_cm_per_year": round(slope, 2),
            "seasonal_amplitude_cm": round(float(monthly.max() - monthly.min()), 1),
            "first_cm": round(float(g["lwe_thickness_cm"].iloc[0]), 1),
            "last_cm": round(float(g["lwe_thickness_cm"].iloc[-1]), 1),
            "mean_uncertainty_cm": round(float(g["uncertainty_cm"].mean()), 1),
        }
    stats["water_storage"] = grace_stats

    # ---- terrain --------------------------------------------------------
    stats["terrain"] = {
        row["region"]: {
            "elevation_mean_m": round(float(row["elevation_mean_m"]), 1),
            "elevation_min_m": round(float(row["elevation_min_m"]), 1),
            "elevation_max_m": round(float(row["elevation_max_m"]), 1),
            "slope_mean_deg": round(float(row["slope_mean_deg"]), 2),
        }
        for _, row in srtm.iterrows()
    }

    # ---- cross-dataset relationships ------------------------------------
    # Monthly means per region, then pooled correlation across regions.
    rain_m = rain.groupby(["region", "year", "month"])["precipitation_mm_day"].mean().rename("rain").reset_index()
    sm_m = sm.groupby(["region", "year", "month"])["sm"].mean().rename("sm").reset_index()
    nd_m = (
        hls.dropna(subset=["ndvi"]).groupby(["region", "year", "month"])["ndvi"].mean().rename("ndvi").reset_index()
    )
    lst_m = eco.groupby(["region", "year", "month"])["lst_celsius"].mean().rename("lst").reset_index()

    def add_lag(df, col, lag):
        """Attach the value of `col` from `lag` months earlier."""
        d = df.copy()
        d["key"] = d["year"] * 12 + d["month"]
        ref = d[["region", "key", col]].copy()
        ref["key"] = ref["key"] + lag  # attach this month's value to a later row
        return d.merge(ref.rename(columns={col: f"{col}_lag{lag}"}), on=["region", "key"], how="left")

    merged = rain_m.merge(sm_m, on=["region", "year", "month"], how="outer")
    merged = merged.merge(nd_m, on=["region", "year", "month"], how="outer")
    merged = merged.merge(lst_m, on=["region", "year", "month"], how="outer")

    rel = {}
    for lag in (0, 1, 2):
        m = add_lag(merged, "sm", lag)
        m = add_lag(m, "ndvi", lag)
        rel[f"rain_vs_sm_lag{lag}"] = round(corr(m["rain"], m[f"sm_lag{lag}"]), 3)
        rel[f"rain_vs_ndvi_lag{lag}"] = round(corr(m["rain"], m[f"ndvi_lag{lag}"]), 3)
    rel["ndvi_vs_sm"] = round(corr(merged["ndvi"], merged["sm"]), 3)
    rel["lst_vs_ndvi"] = round(corr(merged["lst"], merged["ndvi"]), 3)
    rel["lst_vs_rain"] = round(corr(merged["lst"], merged["rain"]), 3)
    rel["sm_vs_ndvi"] = round(corr(merged["sm"], merged["ndvi"]), 3)
    rel["pairs_rain_sm"] = int((merged["rain"].notna() & merged["sm"].notna()).sum())
    rel["pairs_rain_ndvi"] = int((merged["rain"].notna() & merged["ndvi"].notna()).sum())
    stats["relationships"] = rel
    stats["monthly_pooled"] = merged.round(4).to_dict("records")

    # ---- inventory ------------------------------------------------------
    stats["inventory"] = {
        "GPM": {"rows": int(len(gpm)), "filled": int(gpm["precipitation_mm_day"].notna().sum())},
        "SMAP": {"rows": int(len(smap)), "filled": int(smap["soil_moisture_m3_m3"].notna().sum())},
        "ECOSTRESS": {"rows": int(len(eco)), "filled": int(eco["lst_celsius"].notna().sum())},
        "HLS": {"rows": int(len(hls)), "filled": int(hls["ndvi"].notna().sum())},
        "GRACE": {"rows": int(len(grace)), "filled": int(grace["lwe_thickness_cm"].notna().sum())},
        "SRTM": {"rows": int(len(srtm)), "filled": int(len(srtm))},
    }
    stats["region_order"] = REGION_ORDER

    (OUT / "stats.json").write_text(json.dumps(stats, indent=1, default=str), encoding="utf-8")

    print("=== precipitation ===")
    print(pd.DataFrame(per_region).T[["annual_mean_mm", "monsoon_share", "wettest_month", "max_daily_mm", "heavy_days_per_year"]])
    print("\n=== soil moisture ===")
    print(pd.DataFrame(sm_stats).T[["mean", "p10", "p90", "filled_share"]])
    print("\n=== vegetation ===")
    print(pd.DataFrame(hls_stats).T[["months_with_ndvi", "ndvi_mean", "peak_month", "trough_month"]])
    print("\n=== water storage ===")
    print(pd.DataFrame(grace_stats).T[["slope_cm_per_year", "seasonal_amplitude_cm"]])
    print("\n=== relationships ===")
    print(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
