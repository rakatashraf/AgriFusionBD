"""Download SRTMGL1 v003 elevation tiles and summarise terrain per region.

SRTM is static, so it is downloaded once. Tiles intersecting the seven regions
(a one degree window around all of them) are kept as .hgt; each region also
gets a terrain summary computed from a 0.1 degree window around its point.

Output: Data/SRTM_Elevation/
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nasa_common import (  # noqa: E402
    load_earthdata_token,
    log,
    make_session,
    region_bbox,
    regions,
    write_csv,
)

OUT = Path(__file__).resolve().parent / "SRTM_Elevation"
TILES = OUT / "tiles"
CMR = "https://cmr.earthdata.nasa.gov/search"
COLLECTION = "C2763266360-LPCLOUD"
VOID = -32768

# Same window used for the other products.
WEST, SOUTH, EAST, NORTH = region_bbox(margin=0.5)
WINDOW_DEG = 0.05  # half-width of the terrain window around each point


def list_granules() -> list[tuple[str, str]]:
    r = requests.get(
        f"{CMR}/granules.umm_json",
        params={
            "collection_concept_id": COLLECTION,
            "bounding_box": f"{WEST},{SOUTH},{EAST},{NORTH}",
            "page_size": 200,
        },
        timeout=120,
    )
    r.raise_for_status()
    out = []
    for item in r.json().get("items", []):
        urls = [
            l["URL"]
            for l in item["umm"].get("RelatedUrls", [])
            if l.get("Type", "").startswith("GET DATA") and l["URL"].endswith(".zip")
        ]
        if urls:
            out.append((item["umm"]["GranuleUR"], urls[0]))
    return sorted(out)


def download_tiles(session) -> list[Path]:
    TILES.mkdir(parents=True, exist_ok=True)
    granules = list_granules()
    log(f"{len(granules)} SRTM tiles intersect the region window")
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def one(item):
        name, url = item
        zip_path = TILES / f"{name}.zip"
        hgt_path = TILES / f"{name}"
        if hgt_path.exists():
            return hgt_path
        if not zip_path.exists():
            r = session.get(url, timeout=600)
            r.raise_for_status()
            tmp = zip_path.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(TILES)
        return hgt_path

    paths = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(one, g): g for g in granules}
        for fut in as_completed(futures):
            name = futures[fut][0]
            try:
                paths.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                log(f"  FAILED {name}: {exc}")
    log(f"  {len(paths)} tiles ready")
    return paths


def read_window(hgt_path: Path, lat: float, lon: float) -> np.ndarray:
    """Read a small elevation window around a point from a 1 degree tile.

    SRTMGL1 .hgt: 3601 x 3601 big-endian int16, row 0 at the tile's north edge.
    """
    size = 3601
    data = np.fromfile(hgt_path, dtype=">i2").reshape(size, size)
    lat0 = int(np.floor(lat))
    lon0 = int(np.floor(lon))
    row = int(round((lat0 + 1 - lat) * (size - 1)))
    col = int(round((lon - lon0) * (size - 1)))
    half = int(WINDOW_DEG * (size - 1))
    r0, r1 = max(row - half, 0), min(row + half + 1, size)
    c0, c1 = max(col - half, 0), min(col + half + 1, size)
    win = data[r0:r1, c0:c1].astype("float64")
    win[win <= VOID + 1] = np.nan
    return win


def terrain_stats(window: np.ndarray) -> dict:
    if not np.isfinite(window).any():
        return {}
    valid = window[np.isfinite(window)]
    # 1 arc second is about 30 m; use 31 m as an even approximation.
    spacing = 30.0
    filled = np.where(np.isfinite(window), window, np.nanmedian(valid))
    dz_dy, dz_dx = np.gradient(filled, spacing)
    slope_deg = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    return {
        "elevation_mean_m": float(valid.mean()),
        "elevation_min_m": float(valid.min()),
        "elevation_max_m": float(valid.max()),
        "elevation_std_m": float(valid.std()),
        "slope_mean_deg": float(slope_deg.mean()),
        "slope_max_deg": float(slope_deg.max()),
        "valid_pixels": int(valid.size),
    }


def main() -> int:
    session = make_session(load_earthdata_token())
    download_tiles(session)
    session.close()

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for region, (lat, lon) in regions.items():
        name = f"N{int(np.floor(lat)):02d}E{int(np.floor(lon)):03d}.hgt"
        path = TILES / name
        if not path.exists():
            log(f"  {region}: missing tile {name}")
            continue
        window = read_window(path, lat, lon)
        row = {
            "region": region,
            "latitude": lat,
            "longitude": lon,
            "tile": name,
            "window_deg": f"+/-{WINDOW_DEG}",
            "pixel_size_m": 30,
        }
        row.update(terrain_stats(window))
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        log("No terrain summaries produced.")
        return 1

    write_csv(df, OUT / "SRTM_terrain_summary_all_regions.csv")
    for _, row in df.iterrows():
        write_csv(
            pd.DataFrame([row]),
            OUT / f"{row['region']}_SRTM_terrain_summary.csv",
        )

    meta = pd.DataFrame(
        [
            ("source", "NASA SRTMGL1 v003 (LP DAAC), 1 arc second global DEM"),
            ("collection", COLLECTION),
            ("coverage", f"{len(list(TILES.glob('*.hgt')))} one-degree tiles, {WEST:.2f},{SOUTH:.2f},{EAST:.2f},{NORTH:.2f}"),
            ("files", "Raw .hgt tiles kept in SRTM_Elevation/tiles (3601x3601 int16, big-endian)"),
            ("derived", "Terrain statistics from a 0.1 degree window (about 11 km) around each region point"),
            ("note", "About 30 m posting at the equator; vertical accuracy is metres, not centimetres."),
            ("note", "Static historical terrain; insufficient for centimetre-scale drainage design on flat fields."),
            ("note", "Void pixels (-32768) are excluded before statistics are computed."),
        ],
        columns=["field", "value"],
    )
    write_csv(meta, OUT / "SRTM_provenance.csv")

    log(f"\nSaved terrain summaries for {len(df)} regions -> {OUT}")
    print(df[["region", "elevation_mean_m", "elevation_min_m", "elevation_max_m", "slope_mean_deg"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
