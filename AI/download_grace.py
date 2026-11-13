"""Download GRACE / GRACE-FO mascon water-storage anomalies for the seven regions.

The JPL mascon product ships as one NetCDF holding the whole time series, so a
single download covers 2022 to the latest processed month. Values are liquid
water equivalent thickness anomalies in centimetres relative to the product's
own reference period - they are regional mass-change indicators, not field or
groundwater measurements.

Output: Data/GRACE_WaterStorage/
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import netCDF4
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nasa_common import (  # noqa: E402
    DEFAULT_START,
    load_earthdata_token,
    log,
    make_session,
    regions,
    write_csv,
)

OUT = Path(__file__).resolve().parent / "GRACE_WaterStorage"
RAW = OUT / "raw"
URL = (
    "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/"
    "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4/"
    "GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc"
)
FILENAME = URL.rsplit("/", 1)[-1]
EPOCH = date(2002, 1, 1)
FILL = -99999.0


def download(session) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / FILENAME
    if path.exists() and path.stat().st_size > 1_000_000:
        log(f"Using existing {path.name} ({path.stat().st_size / 1e6:.1f} MB)")
        return path
    log(f"Downloading {FILENAME} ...")
    r = session.get(URL, stream=True, timeout=900)
    r.raise_for_status()
    tmp = path.with_suffix(".part")
    with open(tmp, "wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk)
    tmp.replace(path)
    log(f"  saved {path.stat().st_size / 1e6:.1f} MB")
    return path


def main() -> int:
    session = make_session(load_earthdata_token())
    path = download(session)
    session.close()

    ds = netCDF4.Dataset(path)
    lons = ds.variables["lon"][:]
    lats = ds.variables["lat"][:]
    times = ds.variables["time"][:]
    units = ds.variables["time"].units
    lwe = ds.variables["lwe_thickness"]
    unc = ds.variables["uncertainty"]
    mascon = ds.variables["mascon_ID"][:]
    scale = ds.variables["scale_factor"][:]

    rows = []
    start = date.fromisoformat(DEFAULT_START)
    for ti, tval in enumerate(times):
        when = EPOCH + timedelta(days=float(tval))
        if when < start:
            continue
        for region, (lat, lon) in regions.items():
            ilat = int(round((lat - lats[0]) / 0.5))
            ilon = int(round((lon % 360 - lons[0]) / 0.5))
            value = float(lwe[ti, ilat, ilon])
            sigma = float(unc[ti, ilat, ilon])
            scale_val = float(scale[ilat, ilon])
            if scale_val <= FILL + 1:
                scale_val = None
            rows.append(
                {
                    "date": when,
                    "region": region,
                    "latitude": lat,
                    "longitude": lon,
                    "lwe_thickness_cm": None if value <= FILL + 1 else value,
                    "uncertainty_cm": None if sigma <= FILL + 1 else sigma,
                    "grid_lat": float(lats[ilat]),
                    "grid_lon": float(lons[ilon]),
                    "mascon_id": int(mascon[ilat, ilon]),
                    "cri_scale_factor": scale_val,
                }
            )
    ds.close()

    df = pd.DataFrame(rows).sort_values(["region", "date"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    end = df["date"].max().date()

    for region, g in df.groupby("region"):
        write_csv(g, OUT / f"{region}_GRACE_mascon_monthly_{start:%Y%m%d}_to_{end:%Y%m%d}.csv")
    write_csv(df, OUT / f"GRACE_mascon_all_regions_monthly_{start:%Y%m%d}_to_{end:%Y%m%d}.csv")

    meta = pd.DataFrame(
        [
            ("source", "NASA JPL GRACE/GRACE-FO Mascon CRI, RL06.3 v04 (PO.DAAC)"),
            ("file", FILENAME),
            ("variables", "lwe_thickness (cm), uncertainty (cm), mascon_ID, cri_scale_factor"),
            ("time_units", units),
            ("returned_period", f"{start} to {end}"),
            ("months", str(df["date"].nunique())),
            ("grid_resolution", "0.5 degree mascon grid (about 55 km at the equator)"),
            ("note", "Values are anomalies, not absolute storage; the display grid is not effective resolving power."),
            ("note", "Not a field groundwater measurement or well-depth estimate."),
            ("note", "GRACE and GRACE-FO gaps reflect the mission's mass-change sampling, not zero change."),
        ],
        columns=["field", "value"],
    )
    write_csv(meta, OUT / "GRACE_provenance.csv")

    log(f"\nSaved {len(df)} rows, {df['date'].nunique()} months -> {OUT}")
    for region, g in df.groupby("region"):
        v = g["lwe_thickness_cm"].dropna()
        log(f"  {region}: {len(g)} months, mean {v.mean():.2f} cm, range {v.min():.1f}..{v.max():.1f} cm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
