"""Download SMAP surface soil moisture for the seven Bangladesh regions.

SPL3SMP_E v006 granules are about 650 MB each (global 9 km grid), so whole
files are never downloaded. Harmony's HOSS subsetter is asked for just the
bounding box around the regions; it returns one small NetCDF per day. Those
subsets are kept, and the region pixels are also flattened into CSV.

Output: Data/SMAP_SoilMoisture/
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nasa_common import (  # noqa: E402
    DEFAULT_START,
    load_earthdata_token,
    log,
    make_session,
    region_bbox,
    regions,
    slug_dates,
    today,
    write_csv,
)

OUT = Path(__file__).resolve().parent / "SMAP_SoilMoisture"
RAW = OUT / "raw"
COLLECTION = "C2938664763-NSIDC_CPRD"
HARMONY = "https://harmony.earthdata.nasa.gov"
FILL = -9999.0

WEST, SOUTH, EAST, NORTH = region_bbox(margin=0.5)
BBOX = f"lat({SOUTH:.3f}:{NORTH:.3f})"

# AM and PM groups expose differently suffixed names.
FIELDS = {
    "am": {
        "sm": ["soil_moisture"],
        "err": ["soil_moisture_error"],
        "qc": ["retrieval_qual_flag"],
        "surface": ["surface_flag"],
        "freeze": ["freeze_thaw_fraction"],
    },
    "pm": {
        "sm": ["soil_moisture_pm", "soil_moisture"],
        "err": ["soil_moisture_error_pm", "soil_moisture_error"],
        "qc": ["retrieval_qual_flag_pm", "retrieval_qual_flag"],
        "surface": ["surface_flag_pm", "surface_flag"],
        "freeze": ["freeze_thaw_fraction_pm", "freeze_thaw_fraction"],
    },
}


def submit(session, start: date, end: date) -> str:
    url = f"{HARMONY}/{COLLECTION}/ogc-api-coverages/1.0.0/collections/all/coverage/rangeset"
    params = [
        ("subset", BBOX),
        ("subset", f"lon({WEST:.3f}:{EAST:.3f})"),
        (
            "subset",
            f'time("{start.isoformat()}T00:00:00Z":"{end.isoformat()}T23:59:59Z")',
        ),
        ("maxResults", "2000"),
    ]
    r = session.get(url, params=params, timeout=300, allow_redirects=False)
    if r.status_code not in (303, 302):
        raise RuntimeError(f"Harmony submit failed {r.status_code}: {r.text[:300]}")
    return r.headers["location"].rstrip("/").split("/")[-1].split("?")[0]


def poll(session, job_id: str, timeout_s: int = 5400) -> dict:
    started = time.time()
    while True:
        d = session.get(f"{HARMONY}/jobs/{job_id}", timeout=120).json()
        status = d.get("status")
        if status in ("successful", "failed", "canceled"):
            return d
        if time.time() - started > timeout_s:
            raise TimeoutError(f"job {job_id} still {status} after {timeout_s}s")
        time.sleep(20)


def download(session, job: dict) -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    links = [l["href"] for l in job.get("links", []) if l.get("rel") == "data"]
    saved = 0
    for href in links:
        path = RAW / href.split("/")[-1].split("?")[0]
        if path.exists() and path.stat().st_size > 10_000:
            saved += 1
            continue
        r = session.get(href, timeout=300)
        if r.status_code != 200:
            log(f"    skip {path.name}: HTTP {r.status_code}")
            continue
        path.write_bytes(r.content)
        saved += 1
    return saved


def run_year(session, year: int) -> tuple[int, int]:
    start = max(date(year, 1, 1), date.fromisoformat(DEFAULT_START))
    end = min(date(year, 12, 31), today())
    if start > end:
        return 0, 0
    log(f"  {year}: submitting Harmony job {start} -> {end}")
    job_id = submit(session, start, end)
    job = poll(session, job_id)
    n_in = job.get("numInputGranules")
    if job.get("status") != "successful":
        log(f"  {year}: job {job_id} ended {job.get('status')}: {job.get('message')}")
        return 0, n_in or 0
    saved = download(session, job)
    log(f"  {year}: {saved} of {n_in} subset files available")
    return saved, n_in or 0


def _target_xy(paths: list[Path]) -> dict:
    """Find each region's projected coordinate (x_global, y_global).

    The latitude/longitude variables are masked wherever a retrieval is
    missing, so they cannot be relied on file by file. The projected x/y
    coordinates are not masked, so the region position is resolved once from
    a file that does contain valid coordinates and then mapped by x/y.
    """
    for path in paths:
        with netCDF4.Dataset(path) as nc:
            g = nc["Soil_Moisture_Retrieval_Data_AM"]
            lat = np.array(g["latitude"][:], dtype="float64")
            lon = np.array(g["longitude"][:], dtype="float64")
            ok = (lat > -90) & (lon > -180)
            if ok.sum() < 100:
                continue
            x = np.array(nc.variables["x_global"][:], dtype="float64")
            y = np.array(nc.variables["y_global"][:], dtype="float64")
            rr, cc = np.nonzero(ok)
            dims = list(g["latitude"].dimensions)
            targets = {}
            for region, (la, lo) in regions.items():
                d = (lat[rr, cc] - la) ** 2 + (lon[rr, cc] - lo) ** 2
                k = int(np.argmin(d))
                r, c = int(rr[k]), int(cc[k])
                targets[region] = {
                    "x": float(x[c]) if "x" in dims[1] else float(x[r]),
                    "y": float(y[r]) if "y" in dims[0] else float(y[c]),
                    "grid_lat": float(lat[r, c]),
                    "grid_lon": float(lon[r, c]),
                }
            log(f"  resolved region cells from {path.name} (dims {dims})")
            return targets
    raise RuntimeError("no subset file contained valid coordinates")


def cell_indices(nc, targets: dict) -> dict:
    """Map region -> (row, col) in this file using the projected coordinates."""
    x = np.array(nc.variables["x_global"][:], dtype="float64")
    y = np.array(nc.variables["y_global"][:], dtype="float64")
    g = nc["Soil_Moisture_Retrieval_Data_AM"]
    dims = list(g["latitude"].dimensions)
    x_is_col = "x" in dims[1]
    out = {}
    for region, t in targets.items():
        ic = int(np.argmin(np.abs((x if x_is_col else y) - t["x"])))
        ir = int(np.argmin(np.abs((y if x_is_col else x) - t["y"])))
        out[region] = (ir, ic)
    return out


def value_of(group, names):
    for name in names:
        if name in group.variables:
            v = group.variables[name]
            return v
    return None


def extract_file(path: Path, targets: dict) -> list:
    stamp = next((p for p in path.name.split("_") if p.isdigit() and len(p) == 8), None)
    if stamp is None:
        return []
    try:
        day = date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
    except ValueError:
        return []

    rows = []
    with netCDF4.Dataset(path) as nc:
        cells = cell_indices(nc, targets)
        for pass_name, group_name in (
            ("am", "Soil_Moisture_Retrieval_Data_AM"),
            ("pm", "Soil_Moisture_Retrieval_Data_PM"),
        ):
            if group_name not in nc.groups:
                continue
            g = nc[group_name]
            var = value_of(g, FIELDS[pass_name]["sm"])
            if var is None:
                continue
            arr = np.array(var[:], dtype="float64")
            err_v = value_of(g, FIELDS[pass_name]["err"])
            qc_v = value_of(g, FIELDS[pass_name]["qc"])
            surf_v = value_of(g, FIELDS[pass_name]["surface"])
            frz_v = value_of(g, FIELDS[pass_name]["freeze"])
            err = np.array(err_v[:], dtype="float64") if err_v is not None else None
            qc = np.array(qc_v[:]) if qc_v is not None else None
            surf = np.array(surf_v[:]) if surf_v is not None else None
            frz = np.array(frz_v[:], dtype="float64") if frz_v is not None else None

            for region, (r, c) in cells.items():
                glat = targets[region]["grid_lat"]
                glon = targets[region]["grid_lon"]
                sm = float(arr[r, c]) if r < arr.shape[0] and c < arr.shape[1] else np.nan
                if sm <= FILL + 1:
                    sm = np.nan
                rows.append(
                    {
                        "date": day,
                        "region": region,
                        "latitude": regions[region][0],
                        "longitude": regions[region][1],
                        "pass": pass_name,
                        "soil_moisture_m3_m3": sm,
                        "soil_moisture_error_m3_m3": (
                            None
                            if err is None or not np.isfinite(err[r, c]) or err[r, c] <= FILL + 1
                            else float(err[r, c])
                        ),
                        "retrieval_qual_flag": None if qc is None else int(qc[r, c]),
                        "surface_flag": None if surf is None else int(surf[r, c]),
                        "freeze_thaw_fraction": (
                            None
                            if frz is None or not np.isfinite(frz[r, c]) or frz[r, c] <= FILL + 1
                            else float(frz[r, c])
                        ),
                        "grid_lat": glat,
                        "grid_lon": glon,
                        "source_file": path.name,
                    }
                )
    return rows


def main() -> int:
    start = date.fromisoformat(DEFAULT_START)
    end = today()

    if "--extract-only" not in sys.argv:
        session = make_session(load_earthdata_token())
        log(f"Submitting Harmony subset jobs {start} -> {end}")
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(run_year, session, y): y for y in range(start.year, end.year + 1)}
            for fut in as_completed(futures):
                year = futures[fut]
                try:
                    fut.result()
                except Exception as exc:  # noqa: BLE001
                    log(f"  {year}: FAILED {exc}")
        session.close()

    files = sorted(RAW.glob("*_subsetted.nc4"))
    log(f"{len(files)} subset files on disk")
    if not files:
        return 1

    targets = _target_xy(files)
    log("Region cells resolved: " + ", ".join(f"{k}={v['grid_lat']:.2f},{v['grid_lon']:.2f}" for k, v in targets.items()))

    raw_rows = []
    for i, path in enumerate(files, 1):
        raw_rows.extend(extract_file(path, targets))
        if i % 200 == 0:
            log(f"  extracted {i}/{len(files)} files")

    df = pd.DataFrame(raw_rows)
    if df.empty:
        log("No observations extracted.")
        return 1
    df = df.sort_values(["region", "date", "pass"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    end_actual = df["date"].max().date()

    OUT.mkdir(parents=True, exist_ok=True)
    for region, g in df.groupby("region"):
        write_csv(g, OUT / f"{region}_SMAP_soil_moisture_daily_{start:%Y%m%d}_to_{end_actual:%Y%m%d}.csv")
    write_csv(df, OUT / f"SMAP_soil_moisture_all_regions_daily_{start:%Y%m%d}_to_{end_actual:%Y%m%d}.csv")

    retrieved = df["soil_moisture_m3_m3"].notna().sum()
    meta = pd.DataFrame(
        [
            ("source", "NASA SMAP SPL3SMP_E v006 (NSIDC DAAC), Harmony HOSS spatial subset"),
            ("collection", COLLECTION),
            ("variable", "soil_moisture (m3/m3 volumetric), soil_moisture_error, retrieval_qual_flag, surface_flag"),
            ("requested_period", f"{start} to {end}"),
            ("returned_period", f"{start} to {end_actual}"),
            ("days_on_disk", str(df["date"].nunique())),
            ("rows", str(len(df))),
            ("retrieved_values", str(int(retrieved))),
            ("grid_resolution", "9 km EASE-Grid 2.0 enhanced product"),
            ("note", "Grid spacing is not independent 9 km measurement detail; a point selects a grid cell."),
            ("note", "Not a rover-depth or field moisture substitute. AM and PM overpasses are separate retrievals."),
            ("note", "Values are volumetric fraction: 0.30 means 30 percent."),
            ("note", "soil_moisture_error and freeze_thaw_fraction are empty: the source subsets carry only the -9999 fill, which is stored as null rather than as a number."),
        ],
        columns=["field", "value"],
    )
    write_csv(meta, OUT / "SMAP_provenance.csv")

    log(f"\nSaved {len(df)} rows ({retrieved} with a value) -> {OUT}")
    for region, g in df.groupby("region"):
        v = g["soil_moisture_m3_m3"].dropna()
        log(f"  {region}: {len(g)} rows, {len(v)} values, mean {v.mean():.3f} m3/m3" if len(v) else f"  {region}: {len(g)} rows, no values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
