"""Reconnaissance pass: surface data quirks before the full EDA."""
import pandas as pd, numpy as np, glob, os

D = r"C:\Users\muhai\Desktop\BIG hero 6\Data"
P = r"C:\Users\muhai\Desktop\BIG hero 6\API_NASA_POWER\src\data_accusition\bangladesh_weather"
out = []
def w(*a):
    s = " ".join(str(x) for x in a)
    print(s); out.append(s)

gpm = pd.read_csv(os.path.join(D, "GPM_IMERG_Rainfall",
        "GPM_IMERG_all_regions_daily_20220101_to_20261111.csv"))
smap = pd.read_csv(os.path.join(D, "SMAP_SoilMoisture",
        "SMAP_soil_moisture_all_regions_daily_20220101_to_20261109.csv"))
eco = pd.read_csv(os.path.join(D, "ECOSTRESS_LST_ET",
        "ECOSTRESS_LST_all_regions_20220101_to_20261111.csv"))
hls = pd.read_csv(os.path.join(D, "HLS_Vegetation_Indices",
        "HLS_indices_all_regions_20220101_to_20261111.csv"))
grace = pd.read_csv(os.path.join(D, "GRACE_WaterStorage",
        "GRACE_mascon_all_regions_monthly_20220101_to_20260916.csv"))
pw = pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(P, "*_20220101_to_*.csv"))],
               ignore_index=True)

for name, df in [("gpm", gpm), ("smap", smap), ("eco", eco), ("hls", hls),
                 ("grace", grace), ("power", pw)]:
    w("\n===", name, "===", df.shape)
    w("cols:", list(df.columns))
    w("dtypes:", dict(df.dtypes.astype(str)))

w("\n--- GPM run values ---"); w(gpm["run"].value_counts(dropna=False).to_string())
gpm["date"] = pd.to_datetime(gpm["date"])
w("run by year-month (min/max date per run):")
w(gpm.groupby("run")["date"].agg(["min", "max", "count"]).to_string())
w("nulls:\n" + gpm.isna().sum().to_string())
w("dup region+date:", gpm.duplicated(["region", "date"]).sum())
w("regions:", sorted(gpm["region"].unique()))
w("precip desc:\n" + gpm["precipitation_mm_day"].describe().to_string())
w("neg precip:", (gpm["precipitation_mm_day"] < 0).sum())
w("days per region:\n" + gpm.groupby("region")["date"].agg(["min", "max", "count"]).to_string())

w("\n--- SMAP ---")
w("pass values:", smap["pass"].value_counts(dropna=False).to_dict())
w("nulls:\n" + smap.isna().sum().to_string())
w("error uniq:", smap["soil_moisture_error_m3_m3"].unique()[:10])
w("ftf uniq:", smap["freeze_thaw_fraction"].unique()[:10])
w("surface_flag:", smap["surface_flag"].value_counts(dropna=False).to_dict())
w("retrieval_qual_flag:", smap["retrieval_qual_flag"].value_counts(dropna=False).to_dict())
w("sm desc:\n" + smap["soil_moisture_m3_m3"].describe().to_string())
smap["date"] = pd.to_datetime(smap["date"])
w("dup region+date+pass:", smap.duplicated(["region", "date", "pass"]).sum())
w("per region/pass counts:\n" + smap.groupby(["region", "pass"]).size().to_string())
w("dates per region (unique):\n" + smap.groupby("region")["date"].nunique().to_string())

w("\n--- ECOSTRESS ---")
w("nulls:\n" + eco.isna().sum().to_string())
w("qc values:", eco["qc"].value_counts(dropna=False).to_dict())
eco["dt"] = pd.to_datetime(eco["observed_utc"])
w("dt range:", eco["dt"].min(), eco["dt"].max())
w("dup region+dt:", eco.duplicated(["region", "dt"]).sum())
w("lst desc:\n" + eco["lst_celsius"].describe().to_string())
w("per region counts:\n" + eco.groupby("region").size().to_string())
w("hour of day dist:\n" + eco["dt"].dt.hour.value_counts().sort_index().to_string())

w("\n--- HLS ---")
w("nulls:\n" + hls.isna().sum().to_string())
hls["dt"] = pd.to_datetime(hls["observed_utc"], format="mixed", utc=True)
w("dt range:", hls["dt"].min(), hls["dt"].max())
w("dup region+dt:", hls.duplicated(["region", "dt"]).sum())
w("product:", hls["product"].value_counts().to_dict())
w("per region counts:\n" + hls.groupby("region").size().to_string())
w("valid_coverage desc:\n" + hls["valid_coverage"].describe().to_string())
w("valid_coverage==0 count:", (hls["valid_coverage"] == 0).sum())
w("ndvi desc:\n" + hls["ndvi"].describe().to_string())
w("ndmi desc:\n" + hls["ndmi"].describe().to_string())
w("unique dates per region:\n" + hls.groupby("region")["dt"].nunique().to_string())
w("months covered overall:", sorted(hls["dt"].dt.to_period("M").astype(str).unique()))

w("\n--- GRACE ---")
w("nulls:\n" + grace.isna().sum().to_string())
grace["date"] = pd.to_datetime(grace["date"])
w("dup region+date:", grace.duplicated(["region", "date"]).sum())
w("per region counts:\n" + grace.groupby("region").size().to_string())
w("mascon per region:\n" + grace.groupby("region")["mascon_id"].unique().to_string())
w("lwe desc:\n" + grace["lwe_thickness_cm"].describe().to_string())
w("dates:\n" + grace["date"].dt.strftime("%Y-%m-%d").unique().tolist().__str__())

w("\n--- POWER ---")
w("nulls:\n" + pw.isna().sum().to_string())
pw["date"] = pd.to_datetime(pw["date"])
w("dup region+date:", pw.duplicated(["region", "date"]).sum())
w("per region:\n" + pw.groupby("region")["date"].agg(["min", "max", "count"]).to_string())
w("rows with all-null params:", pw[["T2M","PRECTOTCORR","RH2M","WS2M","ALLSKY_SFC_SW_DWN","PS"]].isna().all(axis=1).sum())
nn = pw.dropna(subset=["T2M"])
w("last non-null T2M date per region:\n" + nn.groupby("region")["date"].max().to_string())
w("first non-null T2M date per region:\n" + nn.groupby("region")["date"].min().to_string())
w("-999 counts:\n" + (pw.select_dtypes("number") == -999).sum().to_string())
w("PRECTOTCORR desc:\n" + pw["PRECTOTCORR"].describe().to_string())

with open(r"C:\Users\muhai\Desktop\BIG hero 6\Data\_report\eda\recon.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
