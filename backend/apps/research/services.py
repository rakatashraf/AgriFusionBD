"""
Export generation (plan §5 definition of done #5): a real CSV/GeoJSON file +
a provenance.json manifest listing asset versions and the rule version.

The artifacts are written under ``MEDIA_ROOT/exports/`` so the download
endpoint can stream them back (fixing the "no downloadable artifact" defect).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.environment.models import DataAsset, FieldIndicator

from .models import ExportJob


def _exports_dir() -> Path:
    d = Path(settings.MEDIA_ROOT) / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_provenance(job: ExportJob) -> dict:
    """Assemble the provenance manifest (asset versions + rule version)."""
    assets = []
    if job.field_id:
        for a in DataAsset.objects.filter(field_id=job.field_id).select_related("product"):
            assets.append({
                "assetId": str(a.pk),
                "product": a.product.name,
                "provider": a.product.provider,
                "contentHash": a.content_hash,
                "status": a.status,
                "acquiredAt": a.acquired_at.isoformat() if a.acquired_at else None,
            })
    return {
        "ruleVersion": job.provenance.get("ruleVersion", ""),
        "dataAssets": assets,
        "catalogueVersion": job.provenance.get("catalogueVersion", ""),
        "scope": job.scope,
        "format": job.format,
        "rowCount": job.row_count,
        "generatedAt": timezone.now().isoformat(),
        "requesterId": f"u-{job.requester_id}",
    }


def generate(job: ExportJob) -> None:
    """Generate the file + provenance for a complete export job."""
    job.status = "running"
    job.save(update_fields=["status"])

    rows: list[dict] = []
    if job.field_id:
        qs = FieldIndicator.objects.filter(field_id=job.field_id).order_by("period_start")
        rows = [
            {
                "field": job.field.slug,
                "kind": ind.kind,
                "period_start": ind.period_start.isoformat(),
                "value": ind.value,
                "unit": ind.unit,
                "coverage_pct": ind.coverage_pct,
                "quality": ind.quality,
                "provider": ind.provider,
                "product": ind.product,
                "is_forecast": ind.is_forecast,
                "asset_id": str(ind.asset_id) if ind.asset_id else "",
            }
            for ind in qs
        ]
    job.row_count = len(rows)

    base = _exports_dir() / f"exp-{job.pk}"
    if job.format == "geojson":
        _write_geojson(job, rows, base)
    else:
        _write_csv(job, rows, base)

    provenance = build_provenance(job)
    prov_path = base.with_suffix(".provenance.json")
    prov_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    job.provenance = provenance
    job.provenance_path = str(prov_path.relative_to(settings.MEDIA_ROOT))
    job.status = "complete"
    job.completed_at = timezone.now()
    job.save(update_fields=["row_count", "provenance", "provenance_path", "status", "completed_at"])


def _write_csv(job: ExportJob, rows: list[dict], base: Path) -> None:
    if not rows:
        fieldnames = ["field", "kind", "period_start", "value", "unit", "coverage_pct",
                      "quality", "provider", "product", "is_forecast", "asset_id"]
    else:
        fieldnames = list(rows[0].keys())
    path = base.with_suffix(".csv")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    job.file_path = str(path.relative_to(settings.MEDIA_ROOT))


def _write_geojson(job: ExportJob, rows: list[dict], base: Path) -> None:
    from django.contrib.gis.geos import Point
    feature = None
    if job.field_id:
        field = job.field
        if field.geometry is not None:
            feature = {
                "type": "Feature",
                "geometry": field.geometry.geojson.get("geometry"),
                "properties": {
                    "fieldId": field.slug,
                    "name": field.name,
                    "areaHa": float(field.area_ha) if field.area_ha else None,
                    "isPinEstimate": field.is_pin_estimate,
                    "soilType": field.soil_type,
                    "irrigation": field.irrigation,
                    "indicators": len(rows),
                },
            }
        else:
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [field.lng or 0, field.lat or 0]},
                "properties": {"fieldId": field.slug, "name": field.name, "isPinEstimate": True},
            }
    collection = {
        "type": "FeatureCollection",
        "name": f"fieldshift-export-{job.pk}",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [feature] if feature else [],
    }
    path = base.with_suffix(".geojson")
    path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    job.file_path = str(path.relative_to(settings.MEDIA_ROOT))


def resolve_file(job: ExportJob) -> Path | None:
    if not job.file_path:
        return None
    p = Path(settings.MEDIA_ROOT) / job.file_path
    return p if p.exists() else None


def resolve_provenance(job: ExportJob) -> Path | None:
    if not job.provenance_path:
        return None
    p = Path(settings.MEDIA_ROOT) / job.provenance_path
    return p if p.exists() else None
