"""Download ECOSTRESS land surface temperature for the seven regions.

ECO_L2T_LSTE v002 granules are 70 m tiled scenes with irregular overpass
times. Rather than storing imagery (tens of GB), each granule's LST and QC
tiles are streamed, the pixel over each region is sampled, and the tile is
discarded. Only the resulting point records are kept.

Output: Data/ECOSTRESS_LST_ET/
"""

from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nasa_common import (  # noqa: E402
    DEFAULT_START,
    load_earthdata_token,
    log,
    make_session,
    regions,
    slug_dates,
    today,
    write_csv,
)

OUT = Path(__file__).resolve().parent / "ECOSTRESS_LST_ET"
CMR = "https://cmr.earthdata.nasa.gov/search"
COLLECTION = "C2076090826-LPCLOUD"  # ECO_L2T_LSTE v002
HALF_BOX = 0.05  # degrees either side of the region point


def list_granules(session) -> dict:
    """Granule UR -> {urls, regions, start} for every granule over the regions."""
    start = date.fromisoformat(DEFAULT_START)
    end = today()
    temporal = f"{start}T00:00:00Z,{end}T23:59:59Z"
    found: dict[str, dict] = {}
    for region, (lat, lon) in regions.items():
        bbox = f"{lon - HALF_BOX},{lat - HALF_BOX},{lon + HALF_BOX},{lat + HALF_BOX}"
        page = 1
        while True:
            r = requests.get(
                f"{CMR}/granules.umm_json",
                params={
                    "collection_concept_id": COLLECTION,
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
                    l["URL"].rsplit("_", 1)[-1]: l["URL"]
                    for l in item["umm"].get("RelatedUrls", [])
                    if l.get("Type", "").startswith("GET DATA")
                    and l["URL"].startswith("https://")
                    and l["URL"].endswith(".tif")
                }
                entry = found.setdefault(
                    ur, {"urls": urls, "regions": set(), "start": item["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]}
                )
                entry["regions"].add(region)
                entry["urls"].update(urls)
            if len(items) < 2000:
                break
            page += 1
        log(f"  {region}: {sum(1 for v in found.values() if region in v['regions'])} granules")
    return found


def sample_granule(session, ur: str, info: dict) -> list:
    lst_url = next((u for k, u in info["urls"].items() if k.endswith("LST.tif")), None)
    qc_url = next((u for k, u in info["urls"].items() if k.endswith("QC.tif")), None)
    if lst_url is None:
        return []

    r = session.get(lst_url, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"LST HTTP {r.status_code}")
    qc_bytes = b""
    if qc_url:
        q = session.get(qc_url, timeout=300)
        if q.status_code == 200:
            qc_bytes = q.content

    m = re.search(r"_(\d{8}T\d{6})_", ur)
    observed = pd.to_datetime(m.group(1), format="%Y%m%dT%H%M%S") if m else pd.NaT

    rows = []
    with rasterio.MemoryFile(BytesIO(r.content)) as mem:
        with mem.open() as ds:
            scale = ds.scales[0] if ds.scales else 1.0
            offset = ds.offsets[0] if ds.offsets else 0.0
            nodata = ds.nodata
            for region in info["regions"]:
                lat, lon = regions[region]
                try:
                    xs, ys = transform("EPSG:4326", ds.crs, [lon], [lat])
                    py, px = ds.index(xs[0], ys[0])
                except Exception:  # noqa: BLE001
                    continue
                if not (0 <= py < ds.height and 0 <= px < ds.width):
                    continue
                win = rasterio.windows.Window(max(px - 1, 0), max(py - 1, 0), 3, 3)
                block = ds.read(1, window=win).astype("float64")
                if nodata is not None:
                    block[block == nodata] = np.nan
                block = block * scale + offset
                if np.all(np.isnan(block)):
                    value = np.nan
                else:
                    value = float(np.nanmedian(block))
                qc_val = None
                rows.append(
                    {
                        "observed_utc": observed,
                        "region": region,
                        "latitude": lat,
                        "longitude": lon,
                        "lst_kelvin": value,
                        "lst_celsius": None if np.isnan(value) else value - 273.15,
                        "granule_id": ur,
                        "tile_zone": ur.split("_")[6] if len(ur.split("_")) > 6 else None,
                        "_qc": qc_val,
                        "_px": (py, px),
                    }
                )
            if qc_bytes and rows:
                with rasterio.MemoryFile(BytesIO(qc_bytes)) as qmem:
                    with qmem.open() as qds:
                        for row in rows:
                            py, px = row.pop("_px")
                            if 0 <= py < qds.height and 0 <= px < qds.width:
                                row["qc"] = int(qds.read(1)[py, px])
                            else:
                                row["qc"] = None
            for row in rows:
                row.pop("_px", None)
                row.pop("_qc", None)
    return rows


def main() -> int:
    start = date.fromisoformat(DEFAULT_START)
    end = today()
    session = make_session(load_earthdata_token())

    log(f"Searching ECOSTRESS {start} -> {end}")
    granules = list_granules(session)
    log(f"{len(granules)} unique granules cover at least one region")
    if not granules:
        return 1

    rows: list = []
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(sample_granule, session, ur, info): ur for ur, info in granules.items()}
        for fut in as_completed(futures):
            ur = futures[fut]
            try:
                rows.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                log(f"  FAILED {ur}: {exc}")
            done += 1
            if done % 250 == 0:
                log(f"  {done}/{len(granules)} granules")
    session.close()

    if not rows:
        log("No LST values extracted.")
        return 1

    df = pd.DataFrame(rows).sort_values(["region", "observed_utc"]).reset_index(drop=True)
    # A point near a UTM zone boundary can appear in two adjacent tiles of the
    # same overpass; keep one record per region and overpass time.
    before = len(df)
    df = df.drop_duplicates(subset=["region", "observed_utc"], keep="first").reset_index(drop=True)
    if before != len(df):
        log(f"  dropped {before - len(df)} duplicate tile records")
    df["qc"] = df.get("qc")
    OUT.mkdir(parents=True, exist_ok=True)

    for region, g in df.groupby("region"):
        write_csv(g, OUT / f"{region}_ECOSTRESS_LST_{slug_dates(start, end)}.csv")
    write_csv(df, OUT / f"ECOSTRESS_LST_all_regions_{slug_dates(start, end)}.csv")

    end_actual = df["observed_utc"].max().date() if df["observed_utc"].notna().any() else end
    meta = pd.DataFrame(
        [
            ("source", "NASA ECOSTRESS ECO_L2T_LSTE v002 (LP DAAC)"),
            ("collection", COLLECTION),
            ("variable", "LST 3x3-pixel median around the region coordinate, converted to kelvin and celsius"),
            ("quality", "qc is the raw QC band value at the centre pixel; 0 means best quality"),
            ("requested_period", f"{start} to {end}"),
            ("returned_period", f"{start} to {end_actual}"),
            ("observations", str(len(df))),
            ("grid_resolution", "70 m product grid, irregular overpass times"),
            ("note", "Surface temperature is not 2 m air temperature."),
            ("note", "Granules are sampled then discarded; no imagery is stored, only point records."),
            ("note", "Multiple granules can cover one region on the same day; every overpass is kept."),
        ],
        columns=["field", "value"],
    )
    write_csv(meta, OUT / "ECOSTRESS_provenance.csv")

    log(f"\nSaved {len(df)} LST records -> {OUT}")
    for region, g in df.groupby("region"):
        v = g["lst_celsius"].dropna()
        log(f"  {region}: {len(g)} observations, {len(v)} values, mean {v.mean():.1f} C")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
