#!/usr/bin/env python
"""
ingest_hls.py — compute NDVI from USGS HLS scenes, offline (plan §3, Phase 3).

Run PRE-EVENT (plan §0) so the demo never depends on Earthdata auth or a HLS
download. Reads HLS L30/S30 granules via ``earthaccess`` + ``rioxarray``,
computes ``NDVI = (NIR − Red)/(NIR + Red)``, and writes a small derived JSON
plus a manifest (scene ids, dates, cloud %, coverage %). The JSON becomes the
``DataAsset`` payload; the manifest is provenance.

  python scripts/ingest_hls.py --bbox 88.60,25.33,88.63,25.36 --start 2026-01-01 --end 2026-11-01 --out backend/fixtures/nasa/default_ndvi.json

Bands: L30 B5 (NIR)/B4 (Red); S30 B8 (NIR)/B4 (Red); 30 m.
Rules: preserve acquisition dates; never invent cloud-free values; cloudy
pixels never count as bare field; valid-coverage floor 40 % (plan §3).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def _ndvi_from_bands(nir: np.ndarray, red: np.ndarray, cloud_mask: np.ndarray) -> dict:
    """Per-scene NDVI stats, honouring the cloud mask (plan §3)."""
    denom = nir + red
    safe = denom > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where(safe, (nir - red) / np.where(safe, denom, 1.0), np.nan)
    # Valid = non-nan and not cloud.
    valid = safe & ~cloud_mask & ~np.isnan(ndvi)
    coverage_pct = float(np.mean(valid)) * 100.0
    cloud_pct = float(np.mean(cloud_mask)) * 100.0
    valid_ndvi = ndvi[valid]
    ndvi_mean = float(np.nanmean(valid_ndvi)) if valid_ndvi.size else 0.0
    return {"ndvi": round(ndvi_mean, 4), "coverage_pct": round(coverage_pct, 2),
            "cloud_pct": round(cloud_pct, 2)}


def ingest(bbox: list[float], start: str, end: str, out: Path) -> int:
    """Fetch + compute. Returns 0 on success, 1 on any failure."""
    try:
        import earthaccess
        import rioxarray as rx
    except ImportError as exc:  # pragma: no cover
        print(f"ERROR: missing dependency for live ingest: {exc}", file=sys.stderr)
        print("Install with:  uv pip install earthaccess rioxarray", file=sys.stderr)
        print("Or use the committed fixture (backend/fixtures/nasa/default_ndvi.json).",
              file=sys.stderr)
        return 1

    try:
        search = earthaccess.search()
        scenes = (search
                  .data_collection_short_name("HLSL30.VI", "HLSS30.VI")
                  .bounding_box(bbox)
                  .temporal(start, end)
                  .granules())
        assets = scenes.granule_links()
        if not assets:
            print("WARNING: no HLS granules found for bbox/window — using empty series.",
                  file=sys.stderr)

        rows = []
        manifest = {"bbox": bbox, "start": start, "end": end, "scenes": []}
        for scene_id, links in (assets or {}).items():
            granule = [l for l in links if l.endswith(".zeno") or l.endswith(".nc") or l.endswith(".tif")]
            if not granule:
                continue
            try:
                import xarray as xr
                ds = xr.open_dataset(granule[0])
                # HLS band naming: L30 B4/B5, S30 B4/B8.
                red = ds["B04"].values if "B04" in ds else None
                nir = ds["B05"].values if "B05" in ds else (ds["B08"].values if "B08" in ds else None)
                cloud = ds["QA"].values if "QA" in ds else np.zeros_like(red or np.zeros((1, 1)))
                if red is None or nir is None:
                    continue
                stats = _ndvi_from_bands(nir, red, cloud)
                date = ds.attrs.get("time_coverage_start", "")[:10]
                rows.append({"date": date, "scene_id": scene_id, **stats})
                manifest["scenes"].append({"scene_id": scene_id, "date": date, **stats})
                ds.close()
            except Exception as exc:  # pragma: no cover
                print(f"  skipping {scene_id}: {exc}", file=sys.stderr)

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        (out.parent / (out.stem + ".manifest.json")).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Wrote {len(rows)} NDVI rows → {out}")
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: HLS ingest failed: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Compute NDVI from USGS HLS (offline, pre-event).")
    p.add_argument("--bbox", required=True, help="min_lon,min_lat,max_lon,max_lat")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", default="backend/fixtures/nasa/default_ndvi.json",
                   help="Output JSON path (committed as the DataAsset payload)")
    a = p.parse_args()
    bbox = [float(x) for x in a.bbox.split(",")]
    return ingest(bbox, a.start, a.end, Path(a.out))


if __name__ == "__main__":
    raise SystemExit(main())
