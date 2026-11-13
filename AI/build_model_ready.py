"""Build model-ready feature tables from the collected NASA + POWER data.

Outputs (Data/model_ready/):
  daily_panel.csv          region x date, features known at end of that day, plus next-day targets
  monthly_panel.csv        region x month, monthly features and next-month targets
  feature_dictionary.csv   one row per feature: source, unit, how it is built, leakage note
  split_manifest.json      time-based train/valid/test boundaries
  data_quality_report.csv  per-feature completeness and coverage

Design rules:
  * A feature at day t uses information available at the end of day t only.
  * Targets are explicitly shifted forward; they are never filled.
  * Sparse satellite variables are carried forward with a maximum age and an
    age column, so a model can tell a fresh observation from a stale one.
  * Missing values stay missing (NaN). Nothing is silently zero-filled.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
_POWER_RAW = BASE.parent / "API_NASA_POWER" / "src" / "data_accusition" / "bangladesh_weather"
# PRECTOTCORR in the raw downloads is 24x too large (see fix_power_precip.py);
# prefer the corrected copies when they exist.
POWER_DIR = BASE / "power_corrected" if (BASE / "power_corrected").exists() else _POWER_RAW
OUT = BASE / "model_ready"
OUT.mkdir(exist_ok=True)

START = "2022-01-01"
REGIONS = [
    "Northwest_Rajshahi",
    "North_Rangpur",
    "Central_Dhaka",
    "Northeast_Sylhet",
    "Southwest_Khulna",
    "South_Barishal",
    "Southeast_Chattogram",
]
LAT = {
    "North_Rangpur": 25.75,
    "Northwest_Rajshahi": 24.37,
    "Central_Dhaka": 23.81,
    "Northeast_Sylhet": 24.89,
    "Southwest_Khulna": 22.85,
    "South_Barishal": 22.70,
    "Southeast_Chattogram": 22.36,
}

# Maximum age before a carried-forward observation is treated as unusable.
MAX_AGE = {"hls": 45, "grace": 60, "ecostress": 10, "smap": 5}


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------
def _pick(folder: Path, token: str) -> Path:
    files = [p for p in sorted(folder.glob("*.csv")) if token in p.name and "provenance" not in p.name]
    if not files:
        raise FileNotFoundError(f"no {token} csv in {folder}")
    return files[-1]


def load_power() -> pd.DataFrame:
    frames = []
    for path in sorted(POWER_DIR.glob("*_20220101_to_*.csv")):
        if "report" in path.name:
            continue
        df = pd.read_csv(path)
        if "region" not in df.columns:
            continue
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"no POWER csvs in {POWER_DIR}")
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= START]
    numeric = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "PS"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["date", "region"] + numeric].rename(
        columns={
            "T2M": "t2m_c",
            "T2M_MAX": "tmax_c",
            "T2M_MIN": "tmin_c",
            "PRECTOTCORR": "power_rain_mm",
            "RH2M": "rh_pct",
            "WS2M": "wind_ms",
            "ALLSKY_SFC_SW_DWN": "solar_mj_m2",
            "PS": "pressure_kpa",
        }
    )


def load_gpm() -> pd.DataFrame:
    df = pd.read_csv(_pick(BASE / "GPM_IMERG_Rainfall", "all_regions"))
    df["date"] = pd.to_datetime(df["date"])
    out = df.groupby(["region", "date"], as_index=False).agg(
        gpm_rain_mm=("precipitation_mm_day", "mean"),
        gpm_run=("run", "last"),
    )
    return out


def load_smap() -> pd.DataFrame:
    df = pd.read_csv(_pick(BASE / "SMAP_SoilMoisture", "all_regions"))
    df["date"] = pd.to_datetime(df["date"])
    wide = df.pivot_table(
        index=["region", "date"],
        columns="pass",
        values="soil_moisture_m3_m3",
        aggfunc="mean",
    ).reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={"am": "sm_am", "pm": "sm_pm"})
    wide["sm_mean"] = wide[["sm_am", "sm_pm"]].mean(axis=1, skipna=True)
    qc = df.groupby(["region", "date"], as_index=False)["retrieval_qual_flag"].mean()
    return wide.merge(qc, on=["region", "date"], how="left")


def load_ecostress() -> pd.DataFrame:
    df = pd.read_csv(_pick(BASE / "ECOSTRESS_LST_ET", "all_regions"))
    df["date"] = pd.to_datetime(df["observed_utc"], utc=True).dt.tz_localize(None).dt.normalize()
    daily = df.groupby(["region", "date"], as_index=False).agg(
        lst_c=("lst_celsius", "mean"),
        lst_n_obs=("lst_celsius", "count"),
    )
    return daily


def load_hls() -> pd.DataFrame:
    df = pd.read_csv(_pick(BASE / "HLS_Vegetation_Indices", "all_regions"))
    df["date"] = pd.to_datetime(df["observed_utc"], utc=True).dt.tz_localize(None).dt.normalize()
    return df.groupby(["region", "date"], as_index=False).agg(
        ndvi=("ndvi", "mean"),
        ndmi=("ndmi", "mean"),
        ndvi_coverage=("valid_coverage", "mean"),
    )


def load_grace() -> pd.DataFrame:
    df = pd.read_csv(_pick(BASE / "GRACE_WaterStorage", "all_regions"))
    df["date"] = pd.to_datetime(df["date"])
    return df[["region", "date", "lwe_thickness_cm", "uncertainty_cm"]].rename(
        columns={"lwe_thickness_cm": "grace_lwe_cm", "uncertainty_cm": "grace_uncert_cm"}
    )


def load_srtm() -> pd.DataFrame:
    return pd.read_csv(BASE / "SRTM_Elevation" / "SRTM_terrain_summary_all_regions.csv")[
        ["region", "elevation_mean_m", "slope_mean_deg"]
    ]


# --------------------------------------------------------------------------
# derived meteorology
# --------------------------------------------------------------------------
def extraterrestrial_radiation(lat_deg: float, doy: np.ndarray) -> np.ndarray:
    """FAO-56 eq. 21: Ra in MJ/m2/day."""
    phi = np.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    gsc = 0.0820
    return (
        (24 * 60 / np.pi)
        * gsc
        * dr
        * (ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))
    )


def fao56_et0(df: pd.DataFrame, lat: float, elevation: float) -> pd.Series:
    """Daily reference ET0 (mm/day), FAO-56 Penman-Monteith, complete form."""
    doy = df["date"].dt.day_of_year.to_numpy()
    tmax = df["tmax_c"].to_numpy(dtype=float)
    tmin = df["tmin_c"].to_numpy(dtype=float)
    tmean = (tmax + tmin) / 2.0
    rh = df["rh_pct"].to_numpy(dtype=float)
    u2 = df["wind_ms"].to_numpy(dtype=float)
    rs = df["solar_mj_m2"].to_numpy(dtype=float)
    p = df["pressure_kpa"].to_numpy(dtype=float)
    p = np.where(np.isfinite(p), p, 101.3 * ((293 - 0.0065 * elevation) / 293) ** 5.26)

    svp = lambda t: 0.6108 * np.exp(17.27 * t / (t + 237.3))  # noqa: E731
    es = (svp(tmax) + svp(tmin)) / 2.0
    ea = np.clip(rh / 100.0, 0, 1) * es
    delta = 4098 * (0.6108 * np.exp(17.27 * tmean / (tmean + 237.3))) / (tmean + 237.3) ** 2
    gamma = 0.000665 * p

    ra = extraterrestrial_radiation(lat, doy)
    rso = (0.75 + 2e-5 * elevation) * ra
    ratio = np.clip(np.divide(rs, rso, out=np.ones_like(rs), where=rso > 0), 0.3, 1.0)

    rns = (1 - 0.23) * rs
    sigma = 4.903e-9
    tk_max = tmax + 273.16
    tk_min = tmin + 273.16
    rnl = sigma * ((tk_max**4 + tk_min**4) / 2.0) * (0.34 - 0.14 * np.sqrt(np.clip(ea, 0, None))) * (
        1.35 * ratio - 0.35
    )
    rn = rns - rnl
    g = 0.0

    numerator = 0.408 * delta * (rn - g) + gamma * (900.0 / (tmean + 273.0)) * u2 * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * u2)
    et0 = numerator / denominator
    et0 = np.where(np.isfinite(et0), np.clip(et0, 0, 15), np.nan)
    return pd.Series(et0, index=df.index, name="et0_fao56_mm")


# --------------------------------------------------------------------------
# panel construction
# --------------------------------------------------------------------------
def carry_forward(panel: pd.DataFrame, cols: list, max_age: int, prefix: str) -> pd.DataFrame:
    """Forward-fill sparse observations, capped by age, with an age column."""
    for col in cols:
        filled = panel.groupby("region")[col].ffill(limit=max_age)
        panel[f"{col}_last"] = filled
        observed = panel["date"].where(panel[col].notna())
        observed = observed.groupby(panel["region"]).ffill()
        age = (panel["date"] - observed).dt.days
        panel[f"{prefix}_age_days"] = age.where(age <= max_age)
        panel[f"{prefix}_observed_today"] = panel[col].notna().astype(int)
    return panel


def build_daily(power, gpm, smap, eco, hls, grace, srtm) -> pd.DataFrame:
    dates = pd.date_range(power["date"].min(), power["date"].max(), freq="D")
    grid = pd.MultiIndex.from_product([REGIONS, dates], names=["region", "date"]).to_frame(index=False)

    panel = grid.merge(power, on=["region", "date"], how="left")
    panel = panel.merge(gpm[["region", "date", "gpm_rain_mm", "gpm_run"]], on=["region", "date"], how="left")
    # GPM switches from the Final to the Late run around 2025-10-01; the EDA found
    # the Late run reads 40-50% low in Jun-Aug. Keep it as an explicit feature so
    # a model cannot mistake the run change for a climate signal.
    panel["gpm_is_late_run"] = (panel["gpm_run"] == "late").astype(int)
    panel = panel.merge(smap, on=["region", "date"], how="left")
    panel = panel.merge(eco, on=["region", "date"], how="left")
    panel = panel.merge(hls, on=["region", "date"], how="left")
    panel = panel.merge(grace, on=["region", "date"], how="left")
    panel = panel.merge(srtm, on="region", how="left")
    panel["latitude"] = panel["region"].map(LAT)
    panel = panel.sort_values(["region", "date"]).reset_index(drop=True)

    # --- meteorology derived from POWER (complete series) -------------
    et0_parts = []
    for region, g in panel.groupby("region"):
        elev = float(srtm.loc[srtm.region == region, "elevation_mean_m"].iloc[0])
        part = g.copy()
        part["et0_fao56_mm"] = fao56_et0(part, LAT[region], elev)
        et0_parts.append(part)
    panel = pd.concat(et0_parts).sort_values(["region", "date"]).reset_index(drop=True)

    # Hargreaves fallback where POWER solar radiation is missing (86 days/region).
    # It uses only temperature and latitude, so it is an estimate, and the
    # et0_method column records which formula produced each value.
    def hargreaves(frame: pd.DataFrame, lat: float) -> pd.Series:
        doy = frame["date"].dt.day_of_year.to_numpy()
        ra_mm = extraterrestrial_radiation(lat, doy) * 0.408
        tr = np.clip(frame["tmax_c"].to_numpy(dtype=float) - frame["tmin_c"].to_numpy(dtype=float), 1, None)
        tmean = frame["t2m_c"].to_numpy(dtype=float)
        out = 0.0023 * ra_mm * (tmean + 17.8) * np.sqrt(tr)
        return pd.Series(np.clip(out, 0, 15), index=frame.index, name="et0_hargreaves_mm")

    hg_parts = []
    for region, part in panel.groupby("region"):
        part = part.copy()
        part["et0_hargreaves_mm"] = hargreaves(part, LAT[region])
        hg_parts.append(part)
    panel = pd.concat(hg_parts).sort_values(["region", "date"]).reset_index(drop=True)
    panel["et0_method"] = np.where(panel["et0_fao56_mm"].notna(), "penman_monteith", "hargreaves")
    panel["et0_method_hargreaves"] = (panel["et0_method"] == "hargreaves").astype(int)
    panel["et0_best_mm"] = panel["et0_fao56_mm"].fillna(panel["et0_hargreaves_mm"])

    svp = lambda t: 0.6108 * np.exp(17.27 * t / (t + 237.3))  # noqa: E731
    es = svp(panel["t2m_c"])
    panel["vpd_kpa"] = np.clip(es - panel["rh_pct"] / 100.0 * es, 0, None)
    panel["gdd_base10"] = np.clip((panel["t2m_c"] - 10.0) / 1.0, 0, None)
    panel["heat_day_35"] = (panel["tmax_c"] >= 35).astype(int)
    panel["diurnal_range_c"] = panel["tmax_c"] - panel["tmin_c"]

    g = panel.groupby("region", group_keys=False)
    for window in (3, 7, 14, 30, 60, 90):
        panel[f"power_rain_sum_{window}d"] = g["power_rain_mm"].apply(
            lambda s: s.rolling(window, min_periods=max(1, window // 3)).sum()
        )
        panel[f"et0_sum_{window}d"] = g["et0_best_mm"].apply(
            lambda s: s.rolling(window, min_periods=max(1, window // 3)).sum()
        )
    for window in (7, 30):
        panel[f"gpm_rain_sum_{window}d"] = g["gpm_rain_mm"].transform(
            lambda s: s.rolling(window, min_periods=max(1, window // 3)).sum()
        )

    # dry spell: consecutive days below 1 mm of measured rainfall
    def dry_run(s: pd.Series) -> pd.Series:
        below = (s.fillna(1.0) < 1.0).astype(int)
        grp = (below == 0).cumsum()
        return below.groupby(grp).cumsum()

    panel["dry_spell_days"] = g["gpm_rain_mm"].apply(dry_run)

    # --- sparse observations: carry forward with an age cap -----------
    panel = carry_forward(panel, ["ndvi", "ndmi"], MAX_AGE["hls"], "hls")
    panel = carry_forward(panel, ["lst_c"], MAX_AGE["ecostress"], "ecostress")
    panel = carry_forward(panel, ["grace_lwe_cm"], MAX_AGE["grace"], "grace")

    panel["sm_obs_age_days"] = (
        panel["date"].where(panel["sm_mean"].notna()).groupby(panel["region"]).ffill()
    )
    panel["sm_obs_age_days"] = (panel["date"] - panel["sm_obs_age_days"]).dt.days
    panel["sm_7d_mean"] = g["sm_mean"].apply(lambda s: s.rolling(7, min_periods=2).mean())
    panel["sm_anomaly_30d"] = panel["sm_7d_mean"] - g["sm_7d_mean"].transform(
        lambda s: s.rolling(30, min_periods=10).mean()
    )

    # --- calendar -----------------------------------------------------
    doy = panel["date"].dt.day_of_year
    panel["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    panel["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    panel["month"] = panel["date"].dt.month
    panel["is_monsoon"] = panel["month"].isin([6, 7, 8, 9]).astype(int)

    def season(m: int) -> str:
        if m in (12, 1, 2, 3, 4):
            return "boro"
        if m in (6, 7, 8, 9, 10):
            return "aman"
        if m in (11, 5):
            return "rabi_aus"
        return "other"

    panel["season"] = panel["month"].map(season)

    # --- targets: explicit forward shift, never filled ----------------
    panel["target_rain_next_day_mm"] = g["gpm_rain_mm"].shift(-1)
    panel["target_sm_next_day"] = g["sm_mean"].shift(-1)
    panel["target_et0_next_day_mm"] = g["et0_best_mm"].shift(-1)
    panel["target_heat_next_day"] = g["heat_day_35"].shift(-1)

    return panel


def build_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["ym"] = d["date"].dt.to_period("M")
    agg = (
        d.groupby(["region", "ym"], as_index=False)
        .agg(
            rain_mm=("gpm_rain_mm", lambda s: s.sum(min_count=1)),
            power_rain_mm=("power_rain_mm", lambda s: s.sum(min_count=1)),
            et0_mm=("et0_fao56_mm", lambda s: s.sum(min_count=1)),
            t2m_c=("t2m_c", "mean"),
            tmax_c=("tmax_c", "max"),
            tmin_c=("tmin_c", "min"),
            rh_pct=("rh_pct", "mean"),
            wind_ms=("wind_ms", "mean"),
            solar_mj_m2=("solar_mj_m2", "mean"),
            vpd_kpa=("vpd_kpa", "mean"),
            heat_days=("heat_day_35", "sum"),
            gdd=("gdd_base10", "sum"),
            sm_mean=("sm_mean", "mean"),
            sm_filled_days=("sm_mean", "count"),
            sm_7d_mean=("sm_7d_mean", "mean"),
            lst_c=("lst_c", "mean"),
            ndvi=("ndvi", "mean"),
            ndmi=("ndmi", "mean"),
            ndvi_coverage=("ndvi_coverage", "mean"),
            grace_lwe_cm=("grace_lwe_cm", "mean"),
            elevation_mean_m=("elevation_mean_m", "first"),
            slope_mean_deg=("slope_mean_deg", "first"),
        )
        .reset_index()
    )
    agg["date"] = agg["ym"].dt.to_timestamp()
    agg = agg.drop(columns=["ym"]).sort_values(["region", "date"]).reset_index(drop=True)

    g = agg.groupby("region", group_keys=False)
    agg["ndvi_next_month"] = g["ndvi"].shift(-1)
    agg["sm_next_month"] = g["sm_mean"].shift(-1)
    agg["rain_next_month"] = g["rain_mm"].shift(-1)
    agg["ndvi_3m_mean"] = g["ndvi"].apply(lambda s: s.rolling(3, min_periods=1).mean())
    agg["rain_3m_sum"] = g["rain_mm"].apply(lambda s: s.rolling(3, min_periods=1).sum())
    agg["et0_3m_sum"] = g["et0_mm"].apply(lambda s: s.rolling(3, min_periods=1).sum())
    agg["water_deficit_3m"] = agg["et0_3m_sum"] - agg["rain_3m_sum"]
    agg["ndvi_anomaly"] = agg["ndvi"] - g["ndvi"].transform(
        lambda s: s.rolling(12, min_periods=6).mean()
    )
    agg["month"] = agg["date"].dt.month
    agg["doy_sin"] = np.sin(2 * np.pi * agg["month"] / 12)
    agg["doy_cos"] = np.cos(2 * np.pi * agg["month"] / 12)
    agg["is_monsoon"] = agg["month"].isin([6, 7, 8, 9]).astype(int)
    return agg



FEATURE_DOCS = {
    # name: (source, unit, description, leakage_note)
    "t2m_c": ("POWER", "degC", "Mean air temperature at 2 m", "same-day observation"),
    "tmax_c": ("POWER", "degC", "Daily maximum air temperature", "same-day observation"),
    "tmin_c": ("POWER", "degC", "Daily minimum air temperature", "same-day observation"),
    "power_rain_mm": ("POWER (corrected)", "mm/day", "Corrected precipitation, divided by the erroneous factor of 24", "same-day observation"),
    "rh_pct": ("POWER", "%", "Relative humidity at 2 m", "same-day observation"),
    "wind_ms": ("POWER", "m/s", "Wind speed at 2 m", "same-day observation"),
    "solar_mj_m2": ("POWER", "MJ/m2/day", "All-sky surface shortwave downward irradiance", "same-day observation"),
    "pressure_kpa": ("POWER", "kPa", "Surface pressure", "same-day observation"),
    "gpm_rain_mm": ("GPM IMERG", "mm/day", "Satellite daily precipitation (Final/Late run in gpm_run)", "same-day observation"),
    "sm_am": ("SMAP", "m3/m3", "Surface soil moisture, AM overpass", "only where retrieved"),
    "sm_pm": ("SMAP", "m3/m3", "Surface soil moisture, PM overpass", "only where retrieved"),
    "sm_mean": ("SMAP", "m3/m3", "Mean of AM and PM retrievals", "only where retrieved"),
    "retrieval_qual_flag": ("SMAP", "flag", "Mean retrieval quality flag (0 = best)", "quality control"),
    "et0_fao56_mm": ("derived", "mm/day", "FAO-56 Penman-Monteith reference ET", "computed from same-day weather"),
    "et0_hargreaves_mm": ("derived", "mm/day", "Hargreaves ET, temperature-only fallback", "used where POWER solar is missing"),
    "et0_best_mm": ("derived", "mm/day", "Penman-Monteith where available, else Hargreaves", "see et0_method_hargreaves"),
    "et0_method_hargreaves": ("derived", "0/1", "1 = the value came from the fallback formula", "quality flag"),
    "vpd_kpa": ("derived", "kPa", "Vapour pressure deficit from T2M and RH2M", "computed from same-day weather"),
    "gdd_base10": ("derived", "degC-day", "Growing degree days above a 10 degC base", "same-day"),
    "heat_day_35": ("derived", "0/1", "Tmax >= 35 degC", "same-day"),
    "diurnal_range_c": ("derived", "degC", "Tmax - Tmin", "same-day"),
    "power_rain_sum_Nd": ("derived", "mm", "Rolling N-day rainfall total (N = 3..90)", "window ends today"),
    "et0_sum_Nd": ("derived", "mm", "Rolling N-day ET0 total (N = 3..90)", "window ends today"),
    "gpm_rain_sum_Nd": ("derived", "mm", "Rolling N-day GPM rainfall total (N = 7, 30)", "window ends today"),
    "dry_spell_days": ("derived", "days", "Consecutive days below 1 mm of measured rainfall", "same-day"),
    "ndvi_last": ("HLS", "index", "Most recent NDVI, carried forward at most 45 days", "see hls_age_days"),
    "ndmi_last": ("HLS", "index", "Most recent NDMI, carried forward at most 45 days", "see hls_age_days"),
    "hls_age_days": ("HLS", "days", "Age of the carried NDVI observation", "use to filter stale values"),
    "hls_observed_today": ("HLS", "0/1", "An HLS scene was sampled today", "same-day"),
    "lst_c_last": ("ECOSTRESS", "degC", "Most recent surface temperature, carried at most 10 days", "see ecostress_age_days"),
    "ecostress_age_days": ("ECOSTRESS", "days", "Age of the carried LST observation", "use to filter stale values"),
    "ecostress_observed_today": ("ECOSTRESS", "0/1", "An ECOSTRESS overpass was sampled today", "same-day"),
    "grace_lwe_cm_last": ("GRACE", "cm", "Most recent water-storage anomaly, carried at most 60 days", "see grace_age_days"),
    "grace_age_days": ("GRACE", "days", "Age of the carried GRACE value", "use to filter stale values"),
    "grace_observed_today": ("GRACE", "0/1", "A GRACE month starts today", "same-day"),
    "sm_obs_age_days": ("SMAP", "days", "Days since the last soil-moisture retrieval", "use to filter stale values"),
    "sm_7d_mean": ("derived", "m3/m3", "7-day mean soil moisture", "window ends today"),
    "sm_anomaly_30d": ("derived", "m3/m3", "7-day mean minus its 30-day mean", "window ends today"),
    "elevation_mean_m": ("SRTM", "m", "Mean elevation in a ~11 km window", "static"),
    "slope_mean_deg": ("SRTM", "deg", "Mean slope in a ~11 km window", "static"),
    "latitude": ("static", "deg", "Region latitude", "static"),
    "doy_sin": ("calendar", "-", "Seasonal position, sine encoding", "known in advance"),
    "doy_cos": ("calendar", "-", "Seasonal position, cosine encoding", "known in advance"),
    "month": ("calendar", "1-12", "Month of year", "known in advance"),
    "is_monsoon": ("calendar", "0/1", "June-September", "known in advance"),
    "season": ("calendar", "-", "boro / aman / rabi_aus, following the plan's season windows", "known in advance"),
    "target_rain_next_day_mm": ("target", "mm", "GPM rainfall on the following day", "TARGET"),
    "target_sm_next_day": ("target", "m3/m3", "SMAP soil moisture on the following day", "TARGET"),
    "target_et0_next_day_mm": ("target", "mm/day", "ET0 on the following day", "TARGET"),
    "target_heat_next_day": ("target", "0/1", "Heat day on the following day", "TARGET"),
    "ndvi_next_month": ("target", "index", "NDVI in the following month", "TARGET"),
    "sm_next_month": ("target", "m3/m3", "Mean soil moisture in the following month", "TARGET"),
    "rain_next_month": ("target", "mm", "Total rainfall in the following month", "TARGET"),
}


def write_feature_dictionary(daily: pd.DataFrame, monthly: pd.DataFrame) -> None:
    rows = []
    for table, frame in (("daily", daily), ("monthly", monthly)):
        for col in frame.columns:
            if col in ("region", "date"):
                continue
            key = next((k for k in FEATURE_DOCS if col == k or (k.endswith("_Nd") and col.startswith(k[:-3]))), None)
            source, unit, desc, leak = FEATURE_DOCS.get(key, ("derived", "", "", ""))
            if key is None and col.startswith(("power_rain_sum_", "et0_sum_", "gpm_rain_sum_")):
                window = col.rsplit("_", 1)[-1]
                desc = f"Rolling {window} total; window ends on the row date"
                source, unit, leak = "derived", "mm", "window ends today"
            rows.append(
                {
                    "column": col,
                    "table": table,
                    "source": source,
                    "unit": unit,
                    "description": desc,
                    "leakage_note": leak,
                    "is_target": int(col.startswith(("target_", "ndvi_next_month", "sm_next_month", "rain_next_month"))),
                    "pct_complete": round(float(frame[col].notna().mean()) * 100, 2),
                }
            )
    pd.DataFrame(rows).to_csv(OUT / "feature_dictionary.csv", index=False)


# --------------------------------------------------------------------------
def main() -> int:
    print("loading sources ...")
    power = load_power()
    gpm = load_gpm()
    smap = load_smap()
    eco = load_ecostress()
    hls = load_hls()
    grace = load_grace()
    srtm = load_srtm()
    print(
        f"  POWER {len(power):,} rows, GPM {len(gpm):,}, SMAP {len(smap):,}, "
        f"ECOSTRESS {len(eco):,}, HLS {len(hls):,}, GRACE {len(grace):,}"
    )

    daily = build_daily(power, gpm, smap, eco, hls, grace, srtm)
    monthly = build_monthly(daily)

    # drop the raw monthly-only columns that were merged but not carried
    daily = daily.drop(columns=["ndvi", "ndmi", "ndvi_coverage", "lst_c", "lst_n_obs", "grace_lwe_cm", "grace_uncert_cm"])

    daily.to_csv(OUT / "daily_panel.csv", index=False)
    monthly.to_csv(OUT / "monthly_panel.csv", index=False)

    # ---- data quality report ----------------------------------------
    rows = []
    for col in daily.columns:
        if col in ("region", "date", "season") or col.startswith("target_"):
            continue
        rows.append(
            {
                "column": col,
                "table": "daily",
                "non_null": int(daily[col].notna().sum()),
                "rows": len(daily),
                "pct_complete": round(float(daily[col].notna().mean()) * 100, 2),
            }
        )
    for col in monthly.columns:
        if col in ("region", "date"):
            continue
        rows.append(
            {
                "column": col,
                "table": "monthly",
                "non_null": int(monthly[col].notna().sum()),
                "rows": len(monthly),
                "pct_complete": round(float(monthly[col].notna().mean()) * 100, 2),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "data_quality_report.csv", index=False)
    write_feature_dictionary(daily, monthly)

    split = {
        "strategy": "time-based, no shuffling",
        "train": {"start": "2022-01-01", "end": "2024-12-31"},
        "valid": {"start": "2025-01-01", "end": "2025-12-31"},
        "test": {"start": "2026-01-01", "end": str(daily["date"].max().date())},
        "note": "Series are strongly autocorrelated; random splits leak future information.",
    }
    (OUT / "split_manifest.json").write_text(json.dumps(split, indent=1), encoding="utf-8")

    print(f"\ndaily_panel   {daily.shape[0]:,} rows x {daily.shape[1]} cols")
    print(f"monthly_panel {monthly.shape[0]:,} rows x {monthly.shape[1]} cols")
    print(f"targets: rain {daily['target_rain_next_day_mm'].notna().sum():,}, "
          f"sm {daily['target_sm_next_day'].notna().sum():,}, "
          f"et0 {daily['target_et0_next_day_mm'].notna().sum():,}, "
          f"ndvi(m) {monthly['ndvi_next_month'].notna().sum():,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
