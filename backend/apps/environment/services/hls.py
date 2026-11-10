"""
HLS NDVI series reader (plan §3, Phase 3).

At runtime this reads the **committed** NDVI series produced by
``scripts/ingest_hls.py`` (earthaccess + rioxarray, run pre-event). The live
ingest path is offline by design — the demo must never depend on Earthdata
auth or a HLS download (plan §8).

Rules (plan §3):
  - ``NDVI = (NIR − Red) / (NIR + Red)``; L30 B5/B4, S30 B8/B4; 30 m.
  - Preserve acquisition dates; never invent daily cloud-free values.
  - Cloudy pixels never count as bare field.
  - Valid-coverage threshold 40 %; below it → ``quality: "missing"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from ..models import DataAsset, DatasetProduct, FieldIndicator


@dataclass
class NdviiRow:
    date: str          # acquisition date (YYYY-MM-DD), preserved verbatim
    ndvi: float
    coverage_pct: float  # fraction of valid (non-cloud) pixels, 0-100
    cloud_pct: float
    scene_id: str = ""
    quality: str = "valid"  # valid | partial | missing


@dataclass
class HlsSeries:
    rows: list[NdviiRow] = field(default_factory=list)
    source: str = "committed"  # committed | missing
    asset_id: str | None = None
    stale: bool = False


def _fixtures_nasa_dir() -> Path:
    from django.conf import settings as s
    return Path(s.BASE_DIR) / "fixtures" / "nasa"


def load_ndvi_series(field_model=None) -> HlsSeries:
    """
    Load the committed NDVI series for a field.

    Looks for ``fixtures/nasa/{field-slug}_ndvi.json`` (a list of NdviiRow
    dicts) or a single ``fixtures/nasa/default_ndvi.json`` fallback. If no
    series exists, returns an empty ``HlsSeries`` with ``source="missing"`` —
    the engine then marks NDVI evidence as ``missing`` rather than inventing.
    """
    ndvi_min = settings.HLS_VALID_COVERAGE_MIN  # 0.40

    candidates: list[Path] = []
    if field_model is not None:
        candidates.append(_fixtures_nasa_dir() / f"{field_model.slug}_ndvi.json")
    candidates.append(_fixtures_nasa_dir() / "default_ndvi.json")

    raw: list[dict] | None = None
    used: Path | None = None
    for path in candidates:
        if path.exists():
            import json
            raw = json.loads(path.read_text(encoding="utf-8"))
            used = path
            break

    if raw is None:
        return HlsSeries(rows=[], source="missing", asset_id=None, stale=False)

    rows: list[NdviiRow] = []
    for entry in raw:
        cov = float(entry.get("coverage_pct", 0.0))
        if cov < ndvi_min * 100:
            quality = "missing"
        elif cov < 100.0:
            quality = "partial"
        else:
            quality = "valid"
        rows.append(NdviiRow(
            date=entry["date"],
            ndvi=float(entry["ndvi"]),
            coverage_pct=cov,
            cloud_pct=float(entry.get("cloud_pct", 0.0)),
            scene_id=entry.get("scene_id", ""),
            quality=quality,
        ))

    # Materialise a DataAsset so provenance/exports can reference it.
    asset = None
    try:
        product, _ = DatasetProduct.objects.get_or_create(
            slug="hls-l30-ndvi",
            defaults={
                "name": "USGS HLS NDVI (L30/S30 composite)",
                "provider": "USGS HLS",
                "product_id": "HLSL30.VI",
                "resolution": "30 m",
                "cadence": "16-day",
            },
        )
        import hashlib
        from django.utils import timezone as dj_tz
        payload = {"rows": [vars(r) for r in rows], "source_file": str(used) if used else ""}
        content = hashlib.sha256(str(payload).encode()).hexdigest()
        asset, _ = DataAsset.objects.get_or_create(
            cache_key=f"hls-ndvi-{field_model.slug if field_model else 'default'}",
            defaults={
                "product": product,
                "field": field_model,
                "content_hash": content,
                "status": "cached",
                "acquired_at": dj_tz.now(),
                "payload": payload,
                "metadata": {"source_file": str(used) if used else "", "rows": len(rows)},
            },
        )
    except Exception:
        asset = None  # never let provenance bookkeeping break the read path

    return HlsSeries(rows=rows, source="committed", asset_id=str(asset.pk) if asset else None,
                     stale=False)


def ndvi_for_window(series: HlsSeries, start: str, end: str) -> NdviiRow | None:
    """Latest valid row within [start, end] by acquisition date."""
    in_window = [r for r in series.rows if start <= r.date <= end and r.quality != "missing"]
    if not in_window:
        return None
    return max(in_window, key=lambda r: r.date)
