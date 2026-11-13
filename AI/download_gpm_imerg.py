"""Download GPM IMERG daily precipitation for the seven Bangladesh regions.

Reads a small bounding box around the regions straight from each daily
granule via GES DISC OPeNDAP, so no 30-40 MB global files are stored. One
request per day; the seven region points are picked out of that grid.

Final Run (GPM_3IMERGDF v07) is used where it exists; the Late Run
(GPM_3IMERGDL v07) covers the most recent months. The run is recorded on
every row so the two are never silently mixed.

Output: Data/GPM_IMERG_Rainfall/
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nasa_common import (  # noqa: E402
    DEFAULT_START,
    date_range,
    load_earthdata_token,
    log,
    make_session,
    region_bbox,
    regions,
    slug_dates,
    today,
    write_csv,
)

OUT = Path(__file__).resolve().parent / "GPM_IMERG_Rainfall"
OPENDAP = "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3"
RUNS = {
    "final": ("GPM_3IMERGDF.07", "3B-DAY.MS.MRG.3IMERG"),
    "late": ("GPM_3IMERGDL.07", "3B-DAY-L.MS.MRG.3IMERG"),
}
FILL = -9999.9

# Requested window: every region plus a margin, on the 0.1 degree grid.
WEST, SOUTH, EAST, NORTH = region_bbox(margin=0.5)


def grid_index(lat: float, lon: float) -> tuple[int, int]:
    """0-based (lat, lon) index on the IMERG 0.1 degree global grid.

    The IMERG daily grid stores lat ascending from -89.95 and lon ascending
    from -179.95 at 0.1 degree spacing.
    """
    ilat = int(round((lat + 90.0) / 0.1))
    ilon = int(round((lon + 180.0) / 0.1))
    return ilat, ilon


ILAT_A, ILON_W = grid_index(NORTH, WEST)
ILAT_B, ILON_E = grid_index(SOUTH, EAST)
# OPeNDAP wants ascending indices; lat runs north->south, so the north edge
# has the smaller index.
ILON_SLICE = f"{ILON_W}:1:{ILON_E}"
ILAT_SLICE = f"{min(ILAT_A, ILAT_B)}:1:{max(ILAT_A, ILAT_B)}"


def month_catalog(session, run: str, year: int, month: int) -> dict:
    """Map date -> granule filename for one month of one run."""
    product, prefix = RUNS[run]
    url = f"{OPENDAP}/{product}/{year}/{month:02d}/catalog.xml"
    r = session.get(url, timeout=120)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = {}
    for node in root.iter():
        if not node.tag.endswith("dataset"):
            continue
        name = node.get("name") or ""
        if not name.endswith(".nc4") or not name.startswith(prefix):
            continue
        m = re.search(r"(\d{8})-S000000", name)
        if m:
            stamp = m.group(1)
            out[date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:]))] = name
    return out


def fetch_day(session, day: date, run: str, filename: str) -> list:
    """One ASCII OPeNDAP request; returns one row per region."""
    product, _ = RUNS[run]
    url = (
        f"{OPENDAP}/{product}/{day.year}/{day.month:02d}/{filename}.ascii"
        f"?precipitation[0:1:0][{ILON_SLICE}][{ILAT_SLICE}]"
    )
    r = session.get(url, timeout=180)
    r.raise_for_status()

    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    lat_line = next((ln for ln in lines if ln.startswith("precipitation.lat")), None)
    if lat_line is None:
        raise ValueError(f"no lat header for {day}")
    lats = [float(x) for x in lat_line.split(",")[1:]]

    grid = {}
    pat = re.compile(r"\[precipitation\.lon=([-\d.]+)\],\s*(.*)$")
    for ln in lines:
        m = pat.search(ln)
        if not m:
            continue
        lon = float(m.group(1))
        vals = [float(x) for x in m.group(2).split(",") if x.strip()]
        grid[lon] = vals

    if not grid:
        raise ValueError(f"no grid values for {day}")

    lons = sorted(grid)
    rows = []
    for region, (lat, lon) in regions.items():
        nearest_lon = min(lons, key=lambda v: abs(v - lon))
        col = min(range(len(lats)), key=lambda i: abs(lats[i] - lat))
        vals = grid[nearest_lon]
        value = vals[col] if col < len(vals) else float("nan")
        if value is not None and value <= FILL + 1:
            value = float("nan")
        rows.append(
            {
                "date": day,
                "region": region,
                "latitude": lat,
                "longitude": lon,
                "precipitation_mm_day": value,
                "run": run,
                "product": product,
                "version": "v07",
                "grid_lat": lats[col],
                "grid_lon": nearest_lon,
                "source_file": filename,
            }
        )
    return rows


def main() -> int:
    start = date.fromisoformat(DEFAULT_START)
    end = today()
    session = make_session(load_earthdata_token())

    log(f"Building granule catalog {start} -> {end} ...")
    catalogs = {"final": {}, "late": {}}
    months = pd.period_range(start=start, end=end, freq="M")
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(month_catalog, session, run, p.year, p.month): (run, p)
            for run in RUNS
            for p in months
        }
        for fut in as_completed(futures):
            run, p = futures[fut]
            try:
                catalogs[run].update(fut.result())
            except Exception as exc:  # noqa: BLE001
                log(f"  catalog {run} {p}: {exc}")
    log(f"  final granules: {len(catalogs['final'])}, late granules: {len(catalogs['late'])}")

    plan = []
    missing = []
    for day in date_range(DEFAULT_START, end.isoformat()):
        if day in catalogs["final"]:
            plan.append((day, "final", catalogs["final"][day]))
        elif day in catalogs["late"]:
            plan.append((day, "late", catalogs["late"][day]))
        else:
            missing.append(day)
    log(f"  days to fetch: {len(plan)}; unavailable: {len(missing)}")
    if missing:
        log(f"  unavailable range: {missing[0]} .. {missing[-1]}")

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_day, session, d, r, f): d for d, r, f in plan}
        for fut in as_completed(futures):
            day = futures[fut]
            try:
                rows.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                log(f"  FAILED {day}: {exc}")
            done += 1
            if done % 100 == 0:
                log(f"  {done}/{len(plan)} days")

    session.close()
    if not rows:
        log("No data retrieved.")
        return 1

    df = pd.DataFrame(rows).sort_values(["region", "date"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])

    for region, g in df.groupby("region"):
        write_csv(g, OUT / f"{region}_GPM_IMERG_daily_{slug_dates(start, end)}.csv")
    write_csv(df, OUT / f"GPM_IMERG_all_regions_daily_{slug_dates(start, end)}.csv")

    n_days = df["date"].nunique()
    meta = pd.DataFrame(
        [
            ("source", "NASA GPM IMERG (GES DISC), OPeNDAP point extraction"),
            ("products", "GPM_3IMERGDF v07 Final Run; GPM_3IMERGDL v07 Late Run"),
            ("variable", "precipitation - daily accumulated rate, mm/day"),
            ("requested_period", f"{start} to {end}"),
            ("returned_days", str(n_days)),
            ("final_run_days", str(df.loc[df["run"] == "final", "date"].nunique())),
            ("late_run_days", str(df.loc[df["run"] == "late", "date"].nunique())),
            ("grid_resolution", "0.1 degree global grid (about 11 km)"),
            ("note", "A coordinate selects a grid cell; it is not a measurement at that exact point."),
            ("note", "Final Run ends before present; the Late Run covers recent months and may be revised."),
        ],
        columns=["field", "value"],
    )
    write_csv(meta, OUT / "GPM_IMERG_provenance.csv")

    log(f"\nSaved {len(df)} rows across {df['region'].nunique()} regions -> {OUT}")
    for region, g in df.groupby("region"):
        log(
            f"  {region}: {len(g)} days, {int(g['precipitation_mm_day'].isna().sum())} missing, "
            f"mean {g['precipitation_mm_day'].mean():.2f} mm/day"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
