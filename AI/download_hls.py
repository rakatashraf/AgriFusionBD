"""Sample HLS (HLSL30 / HLSS30 v2.0) vegetation indices for the seven regions.

Full 30 m scenes are hundreds of megabytes and there are thousands of them, so
bands are read through GDAL's HTTP range support and only a small window around
each region is touched. One scene per region per month is sampled (L30 first,
S30 as a fallback) to give a workable NDVI/NDMI series without storing imagery.

Quality handling follows the plan: exclude Fmask bits 0-5 and high aerosol
(bits 6-7 == 3), reject zero denominators, and report valid-pixel coverage.

Output: Data/HLS_Vegetation_Indices/
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.windows import Window
from rasterio.warp import transform

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nasa_common import (  # noqa: E402
    DEFAULT_START,
    load_earthdata_token,
    log,
    regions,
    slug_dates,
    today,
    write_csv,
)

OUT = Path(__file__).resolve().parent / "HLS_Vegetation_Indices"
CMR = "https://cmr.earthdata.nasa.gov/search"
COLLECTIONS = {"HLSL30": "C2021957657-LPCLOUD", "HLSS30": "C2021957295-LPCLOUD"}
RED = {"HLSL30": "B04", "HLSS30": "B04"}
NIR = {"HLSL30": "B05", "HLSS30": "B8A"}
SWIR = {"HLSL30": "B06", "HLSS30": "B11"}
HALF_BOX = 0.02
WINDOW = 15  # pixels either side -> 31x31 at 30 m (about 0.9 km)
SCALE = 0.0001


def search(product: str) -> list:
    cid = COLLECTIONS[product]
    start = date.fromisoformat(DEFAULT_START)
    temporal = f"{start}T00:00:00Z,{today()}T23:59:59Z"
    out = []
    for region, (lat, lon) in regions.items():
        bbox = f"{lon - HALF_BOX},{lat - HALF_BOX},{lon + HALF_BOX},{lat + HALF_BOX}"
        page = 1
        while True:
            r = requests.get(
                f"{CMR}/granules.umm_json",
                params={
                    "collection_concept_id": cid,
                    "bounding_box": bbox,
                    "temporal": temporal,
                    "page_size": 2000,
                    "page_num": page,
                },
                timeout=180,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            for item in items:
                ur = item["umm"]["GranuleUR"]
                urls = {
                    l["URL"].rsplit(".", 2)[-2]: l["URL"]
                    for l in item["umm"].get("RelatedUrls", [])
                    if l.get("Type", "").startswith("GET DATA")
                    and l["URL"].startswith("https://")
                    and l["URL"].endswith(".tif")
                }
                out.append(
                    {
                        "product": product,
                        "granule": ur,
                        "urls": urls,
                        "region": region,
                        "when": item["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"],
                    }
                )
            if len(items) < 2000:
                break
            page += 1
    return out


def pick_monthly(candidates: list, per_product: int = 3) -> dict:
    """Up to `per_product` L30 and S30 scenes per region-month.

    Cloud is common, so a month keeps alternatives: the next candidate is
    tried when the first has too few valid pixels.
    """
    grouped: dict[tuple, list] = {}
    for c in candidates:
        key = (c["region"], c["when"][:7])
        grouped.setdefault(key, []).append(c)
    out = {}
    for key, items in grouped.items():
        l30 = sorted((c for c in items if c["product"] == "HLSL30"), key=lambda c: c["when"])
        s30 = sorted((c for c in items if c["product"] == "HLSS30"), key=lambda c: c["when"])
        out[key] = l30[:per_product] + s30[:per_product]
    return out


MIN_COVERAGE = 0.5


def best_for_month(scenes: list, env_kwargs: dict) -> dict | None:
    """Sample candidates in order; return the first usable result."""
    fallback = None
    for scene in scenes:
        row = sample(scene, env_kwargs)
        if row is None:
            continue
        if row["ndvi"] is not None and row["valid_coverage"] >= MIN_COVERAGE:
            return row
        if fallback is None or (row["valid_coverage"] or 0) > (fallback["valid_coverage"] or 0):
            fallback = row
    return fallback


def read_window(ds, lat: float, lon: float, size: int) -> np.ndarray | None:
    xs, ys = transform("EPSG:4326", ds.crs, [lon], [lat])
    py, px = ds.index(xs[0], ys[0])
    if not (0 <= py < ds.height and 0 <= px < ds.width):
        return None
    win = Window(
        max(px - size // 2, 0),
        max(py - size // 2, 0),
        size,
        size,
    )
    win = Window(win.col_off, win.row_off, min(size, ds.width - win.col_off), min(size, ds.height - win.row_off))
    return ds.read(1, window=win).astype("float64")


def sample(scene: dict, env_kwargs: dict) -> dict | None:
    with rasterio.Env(**env_kwargs):
        try:
            with rasterio.open("/vsicurl/" + scene["urls"][RED[scene["product"]]]) as ds:
                red = read_window(ds, *regions[scene["region"]], WINDOW)
            with rasterio.open("/vsicurl/" + scene["urls"][NIR[scene["product"]]]) as ds:
                nir = read_window(ds, *regions[scene["region"]], WINDOW)
            with rasterio.open("/vsicurl/" + scene["urls"]["Fmask"]) as ds:
                fm = read_window(ds, *regions[scene["region"]], WINDOW)
            swir = None
            if SWIR[scene["product"]] in scene["urls"]:
                with rasterio.open("/vsicurl/" + scene["urls"][SWIR[scene["product"]]]) as ds:
                    swir = read_window(ds, *regions[scene["region"]], WINDOW)
        except Exception as exc:  # noqa: BLE001
            log(f"  {scene['granule']}: {exc}")
            return None

    if red is None or nir is None or fm is None:
        return None
    if red.shape != nir.shape or red.shape != fm.shape:
        n = min(red.shape[0], nir.shape[0], fm.shape[0])
        red, nir, fm = red[:n, :n], nir[:n, :n], fm[:n, :n]

    valid = (fm != 255) & ((fm.astype("int32") & 0x3F) == 0) & (((fm.astype("int32") >> 6) & 3) != 3)
    r = red * SCALE
    n = nir * SCALE
    valid &= (red != -9999) & (nir != -9999) & np.isfinite(r + n) & ((r + n) > 0) & (r >= 0) & (n >= 0)

    ndvi = np.where(valid, (n - r) / np.where(valid, n + r, np.nan), np.nan)
    coverage = float(valid.sum() / valid.size) if valid.size else 0.0
    value = float(np.nanmedian(ndvi)) if np.isfinite(ndvi).any() else None

    ndmi = None
    if swir is not None and swir.shape == red.shape:
        s = swir * SCALE
        ok = valid & (swir != -9999) & ((n + s) > 0)
        nd = np.where(ok, (n - s) / np.where(ok, n + s, np.nan), np.nan)
        ndmi = float(np.nanmedian(nd)) if np.isfinite(nd).any() else None

    return {
        "observed_utc": pd.to_datetime(scene["when"]),
        "region": scene["region"],
        "latitude": regions[scene["region"]][0],
        "longitude": regions[scene["region"]][1],
        "product": scene["product"],
        "ndvi": value,
        "ndmi": ndmi,
        "valid_coverage": round(coverage, 4),
        "valid_pixels": int(valid.sum()),
        "window_pixels": int(valid.size),
        "granule_id": scene["granule"],
    }


def main() -> int:
    token = load_earthdata_token()
    env_kwargs = {
        "GDAL_HTTP_HEADERS": "Authorization: Bearer " + token,
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_USE_HEAD": "NO",
        "VSI_CACHE": "TRUE",
        "VSI_CACHE_SIZE": "33554432",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "2",
    }

    candidates = []
    for product in COLLECTIONS:
        log(f"Searching {product}")
        candidates.extend(search(product))
    log(f"{len(candidates)} region-scene matches")
    groups = pick_monthly(candidates)
    log(f"{len(groups)} region-months, up to 6 candidate scenes each")

    previous = []
    combined_files = sorted(OUT.glob("HLS_indices_all_regions_*.csv"))
    if "--fill" in sys.argv and combined_files:
        prev = pd.read_csv(combined_files[-1])
        prev = prev.loc[:, ~prev.columns.str.startswith("Unnamed")]
        prev["observed_utc"] = pd.to_datetime(prev["observed_utc"])
        previous = prev.to_dict("records")
        done = {
            (r["region"], r["observed_utc"].strftime("%Y-%m"))
            for r in previous
            if pd.notna(r.get("ndvi"))
        }
        groups = {k: v for k, v in groups.items() if k not in done}
        log(f"  {len(done)} region-months already have NDVI; retrying {len(groups)}")

    start = date.fromisoformat(DEFAULT_START)
    end = today()
    rows = []
    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(best_for_month, scenes, env_kwargs): key for key, scenes in groups.items()}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                row = fut.result()
                if row:
                    rows.append(row)
                else:
                    log(f"  {key[0]} {key[1]}: no usable scene")
            except Exception as exc:  # noqa: BLE001
                log(f"  FAILED {key}: {exc}")
            done += 1
            if done % 50 == 0:
                log(f"  {done}/{len(groups)} region-months")

    if not rows and not previous:
        log("No vegetation indices extracted.")
        return 1

    df = pd.DataFrame(rows + previous if previous else rows)
    df["observed_utc"] = pd.to_datetime(df["observed_utc"])
    df["_month"] = df["observed_utc"].dt.strftime("%Y-%m")
    df["_has_ndvi"] = df["ndvi"].notna()
    # One row per region-month: when a backfill added a clearer scene for a
    # month that already had a cloudy row, keep the usable one.
    df = (
        df.sort_values(["region", "_month", "_has_ndvi"], ascending=[True, True, False])
        .drop_duplicates(subset=["region", "_month"], keep="first")
        .drop(columns=["_month", "_has_ndvi"])
        .reset_index(drop=True)
    )
    OUT.mkdir(parents=True, exist_ok=True)
    for region, g in df.groupby("region"):
        write_csv(g, OUT / f"{region}_HLS_indices_{slug_dates(start, end)}.csv")
    write_csv(df, OUT / f"HLS_indices_all_regions_{slug_dates(start, end)}.csv")

    meta = pd.DataFrame(
        [
            ("source", "NASA HLS HLSL30 / HLSS30 v2.0 (LP DAAC), GDAL HTTP range reads"),
            ("collections", "C2021957657-LPCLOUD (L30), C2021957295-LPCLOUD (S30)"),
            ("sampling", "One scene per region per month; L30 preferred, S30 used when no L30 exists"),
            ("window", f"{2 * WINDOW + 1} x {2 * WINDOW + 1} pixels at 30 m around the region coordinate"),
            ("indices", "NDVI = (NIR - Red) / (NIR + Red); NDMI = (NIR - SWIR1) / (NIR + SWIR1)"),
            ("bands", "L30 red B04 / NIR B05 / SWIR1 B06; S30 red B04 / NIR B8A / SWIR1 B11; Fmask for quality"),
            ("quality", "Fmask bits 0-5 excluded, aerosol bits 6-7 = 3 excluded, zero denominators rejected"),
            ("scale", "Surface reflectance scaled by 0.0001 before indexing"),
            ("requested_period", f"{start} to {end}"),
            ("note", "Indices are indicators, not direct measurements of soil moisture, nutrients or disease."),
            ("note", "Usable cloud-free observations are not guaranteed every month; coverage is reported per row."),
            ("note", "Imagery is not stored - only the sampled statistics."),
        ],
        columns=["field", "value"],
    )
    write_csv(meta, OUT / "HLS_provenance.csv")

    log(f"\nSaved {len(df)} index records -> {OUT}")
    for region, g in df.groupby("region"):
        log(f"  {region}: {len(g)} months sampled, mean NDVI {g['ndvi'].mean():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
