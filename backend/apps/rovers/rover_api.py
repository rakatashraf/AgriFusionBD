"""
AgriRover-Q compatible ingest surface (plan §5.3, §6 P1).

The robot speaks HTTP/JSON with a shared ``X-API-Key`` header (AgriRover-Q
API v0.2). This adapter is mounted at ``/api/v1/rover/`` so it does not
collide with the Django API prefix at ``/api/v1/``.

Endpoints (matching the robot's expected paths under its own ``/api/v1``
prefix — the robot's ``API_BASE`` is configured to point at this adapter):

    POST   /rover/samples           one soil sample (upsert on run_id+sample_id)
    POST   /rover/status            heartbeat (updates Device.last_seen/battery)
    POST   /rover/images            sample photo (base64 JPEG/PNG)
    GET    /rover/runs              list runs for the given rover_id
    GET    /rover/runs/{run_id}/samples
    GET    /rover/runs/{run_id}/status
    GET    /rover/runs/{run_id}/geojson
    POST   /rover/fields/{field_id}/contains   geofence check
    GET    /health                  liveness (no key required)

Authentication: ``X-API-Key`` compared in constant time against
``settings.AGRI_API_KEY``. The payload's ``rover_id`` must resolve to a
``Device`` (looked up by ``serial``); unknown rover → 422.

Deduplication: ``(run_id, sample_id)`` upsert — a replayed spooled sample
overwrites, never duplicates (AgriRover-Q spool semantics, §5.1).

Grant enforcement: a sample can only be written to a field for which the
device holds an active (non-expired) ``DeviceGrant``.
"""

from __future__ import annotations

import hmac
import json
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (
    Device,
    DeviceGrant,
    SurveyRun,
)

logger = logging.getLogger("fieldshift.rover")

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _check_api_key(request) -> str | None:
    """Return the resolved Device if the key is valid, else None.

    The robot sends a single shared key; per-device identity comes from the
    payload's ``rover_id`` field (matched against ``Device.serial``).
    """
    supplied = request.headers.get("X-API-Key", "")
    expected = settings.AGRI_API_KEY
    if not supplied or not hmac.compare_digest(supplied, expected):
        return None
    return "ok"


def _resolve_device(payload: dict) -> Device | None:
    rover_id = payload.get("rover_id", "")
    if not rover_id:
        return None
    return Device.objects.filter(serial=rover_id).first()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jstatus(code: int, body: dict) -> JsonResponse:
    return JsonResponse(body, status=code)


def _err(code: int, message: str, details: dict | None = None) -> JsonResponse:
    body = {"ok": False, "error": {"code": str(code), "message": message}}
    if details:
        body["error"]["details"] = details
    return _jstatus(code, body)


def _grant_active(device: Device, field_slug: str) -> bool:
    from apps.farms.models import Field
    try:
        field = Field.objects.get(slug=field_slug)
    except Field.DoesNotExist:
        return False
    from django.utils import timezone as dj_tz
    return DeviceGrant.objects.filter(
        device=device, field=field,
    ).filter(
        # expires_at is null (no expiry) or in the future
        expires_at__isnull=True,
    ).exists() or DeviceGrant.objects.filter(
        device=device, field=field,
        expires_at__gt=dj_tz.now(),
    ).exists()


# ---------------------------------------------------------------------------
# POST /rover/samples
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def rover_samples(request):
    """Ingest one soil sample. Upsert on (run_id, sample_id).

    Expected payload (AgriRover-Q §5.1):
    {
      "rover_id": "agrirover-q-01",
      "run_id": "video-20261110-100504",
      "sample_id": 1,
      "timestamp": "2026-11-10T04:05:35+00:00",
      "lane": 1,
      "position": {"lat": 24.37, "lon": 88.60, "source": "fused"},
      "gps": {"lat": ..., "lon": ..., "fix": "3D", "hdop": 0.98, "satellites": 12},
      "heading_deg": 92.7,
      "soil": {"moisture_vwc": 0.2838, "moisture_raw": 12126,
                "temperature_c": 18.31, "probe_ok": true, "probe_depth_mm": 50.0},
      "air": {"temperature_c": 24.08, "humidity_pct": 56.6, "pressure_hpa": 1009.5},
      "battery": {"voltage": 8.18, "soc_pct": 93.0},
      "image": "video-20261110-100504_s001.jpg",
      "field_slug": "north-field"   (FieldShift extension — the robot's field_id maps here)
    }

    Response 201: {"ok": true, "run_id": ..., "sample_id": ...}
    """
    if _check_api_key(request) is None:
        return _err(401, "Missing or invalid X-API-Key.")

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _err(400, "Invalid JSON body.")

    rover_id = payload.get("rover_id", "")
    device = _resolve_device(payload)
    if device is None:
        return _err(422, f"Unknown rover_id: {rover_id!r}. Register the device first.",
                    {"rover_id": rover_id})

    run_id = payload.get("run_id", "")
    sample_id = payload.get("sample_id")
    if not run_id or sample_id is None:
        return _err(422, "run_id and sample_id are required.",
                    {"run_id": run_id, "sample_id": sample_id})

    field_slug = payload.get("field_slug") or payload.get("field_id") or ""
    if not field_slug:
        return _err(422, "field_slug is required (maps to farms.Field.slug).",
                    {"field_slug": field_slug})

    # Grant check
    if not _grant_active(device, field_slug):
        return _err(403, f"Device {rover_id!r} has no active grant for field {field_slug!r}.",
                    {"rover_id": rover_id, "field_slug": field_slug})

    # Fast checks pass — persist an idempotent outbox row and enqueue the real
    # upsert (grant check, field resolution, sample/observation upsert,
    # telemetry) onto the Celery worker. The robot gets a 202 back immediately;
    # a lossy link can safely replay without duplicating work.
    dedupe_key = f"sample:{run_id}:{int(sample_id)}"
    _enqueue("sample", device, payload, dedupe_key)

    return _jstatus(202, {"ok": True, "status": "accepted", "run_id": run_id, "sample_id": int(sample_id)})


def _enqueue(kind: str, device, payload: dict, dedupe_key: str) -> None:
    """Record an idempotent outbox row and enqueue it for async processing.

    The row is created (or reused, on replay) atomically, then the matching
    Celery task is enqueued. In eager mode (dev) the task runs inline and the
    row is drained immediately; under a worker it is picked up asynchronously.
    """
    from .models import RoverInbox
    from .tasks import process_rover_sample, process_rover_image, process_rover_status

    row, _created = RoverInbox.objects.update_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "kind": kind,
            "device": device,
            "payload": payload,
            "status": "pending",
            "attempts": 0,
            "error": "",
        },
    )
    task = {"sample": process_rover_sample, "image": process_rover_image, "status": process_rover_status}[kind]
    task.delay(row.pk)


# ---------------------------------------------------------------------------
# POST /rover/status  (heartbeat every 2 s)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def rover_status(request):
    """Heartbeat: update Device.last_seen and battery.

    Expected: {"rover_id": "...", "state": "follow", "battery": {"voltage": 8.1, "soc_pct": 91.0},
               "position": {"lat": ..., "lon": ...}}
    """
    if _check_api_key(request) is None:
        return _err(401, "Missing or invalid X-API-Key.")

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _err(400, "Invalid JSON body.")

    device = _resolve_device(payload)
    if device is None:
        return _err(422, f"Unknown rover_id: {payload.get('rover_id')!r}.")

    # Heartbeats are cheap but still off the request path: record an outbox
    # row and enqueue. The robot gets 202 immediately.
    state = payload.get("state", "")
    dedupe_key = f"status:{payload.get('rover_id', '')}:{int(payload.get('seq', 0))}"
    _enqueue("status", device, payload, dedupe_key)
    return _jstatus(202, {"ok": True, "status": "accepted", "state": state})


# ---------------------------------------------------------------------------
# POST /rover/images
# ---------------------------------------------------------------------------

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}

@csrf_exempt
@require_http_methods(["POST"])
def rover_images(request):
    """Store a sample photo (base64 JPEG/PNG).

    Expected: {"rover_id": "...", "run_id": "...", "sample_id": 1,
               "filename": "video-..._s001.jpg", "data": "<base64>"}
    """
    if _check_api_key(request) is None:
        return _err(401, "Missing or invalid X-API-Key.")

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _err(400, "Invalid JSON body.")

    device = _resolve_device(payload)
    if device is None:
        return _err(422, f"Unknown rover_id: {payload.get('rover_id')!r}.")

    if not payload.get("data"):
        return _err(400, "base64 'data' field is required.")

    # Persist the (potentially large) base64 to the outbox and enqueue the
    # decode + disk write off the request path.
    run_id = payload.get("run_id", "")
    sample_id = payload.get("sample_id")
    dedupe_key = f"image:{run_id}:{int(sample_id or 0)}"
    _enqueue("image", device, payload, dedupe_key)
    return _jstatus(202, {"ok": True, "status": "accepted", "run_id": run_id, "sample_id": sample_id})


# ---------------------------------------------------------------------------
# GET /rover/runs
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def rover_runs(request):
    """List survey runs for a rover_id (query param)."""
    if _check_api_key(request) is None:
        return _err(401, "Missing or invalid X-API-Key.")

    rover_id = request.GET.get("rover_id", "")
    device = _resolve_device({"rover_id": rover_id})
    if device is None:
        return _err(422, f"Unknown rover_id: {rover_id!r}.")

    runs = SurveyRun.objects.filter(device=device).order_by("-created_at")[:50]
    return _jstatus(200, {
        "ok": True,
        "runs": [
            {
                "run_id": r.run_id,
                "field_slug": r.field.slug,
                "status": r.status,
                "last_state": r.last_state,
                "samples_count": r.samples_count,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ],
    })


# ---------------------------------------------------------------------------
# GET /rover/runs/{run_id}/samples
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def rover_run_samples(request, run_id: str):
    if _check_api_key(request) is None:
        return _err(401, "Missing or invalid X-API-Key.")

    try:
        run = SurveyRun.objects.select_related("device").get(run_id=run_id)
    except SurveyRun.DoesNotExist:
        return _err(404, f"Run {run_id!r} not found.")

    samples = run.samples.order_by("sample_id")
    return _jstatus(200, {
        "ok": True,
        "run_id": run_id,
        "samples": [
            {
                "sample_id": s.sample_id,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                "lane": s.lane,
                "position": {"lat": s.lat, "lon": s.lon} if s.lat is not None else None,
                "gps": {"fix": s.gps_fix, "hdop": s.gps_hdop, "satellites": s.gps_satellites},
                "heading_deg": s.heading_deg,
                "soil": {
                    "moisture_vwc": s.moisture_vwc,
                    "moisture_raw": s.moisture_raw,
                    "temperature_c": s.soil_temp_c,
                    "probe_ok": s.probe_ok,
                    "probe_depth_mm": s.probe_depth_mm,
                },
                "air": {
                    "temperature_c": s.air_temp_c,
                    "humidity_pct": s.air_humidity_pct,
                    "pressure_hpa": s.air_pressure_hpa,
                },
                "battery": {"voltage": s.battery_voltage, "soc_pct": s.battery_soc_pct},
                "image": s.image,
            }
            for s in samples
        ],
    })


# ---------------------------------------------------------------------------
# GET /rover/runs/{run_id}/status
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def rover_run_status(request, run_id: str):
    if _check_api_key(request) is None:
        return _err(401, "Missing or invalid X-API-Key.")

    try:
        run = SurveyRun.objects.select_related("device", "field").get(run_id=run_id)
    except SurveyRun.DoesNotExist:
        return _err(404, f"Run {run_id!r} not found.")

    return _jstatus(200, {
        "ok": True,
        "run_id": run_id,
        "status": run.status,
        "last_state": run.last_state,
        "samples_count": run.samples_count,
        "field_slug": run.field.slug,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    })


# ---------------------------------------------------------------------------
# GET /rover/runs/{run_id}/geojson
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def rover_run_geojson(request, run_id: str):
    """Return the run's sample positions as a GeoJSON FeatureCollection.

    AgriRover-Q uses [lon, lat] order in GeoJSON (WGS84).
    """
    if _check_api_key(request) is None:
        return _err(401, "Missing or invalid X-API-Key.")

    try:
        run = SurveyRun.objects.get(run_id=run_id)
    except SurveyRun.DoesNotExist:
        return _err(404, f"Run {run_id!r} not found.")

    samples = run.samples.filter(lat__isnull=False, lon__isnull=False).order_by("sample_id")
    coordinates = [[s.lon, s.lat] for s in samples]  # GeoJSON: [lon, lat]

    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                "properties": {
                    "sample_id": s.sample_id,
                    "moisture_vwc": s.moisture_vwc,
                    "soil_temp_c": s.soil_temp_c,
                    "probe_ok": s.probe_ok,
                    "lane": s.lane,
                },
            }
            for s in samples
        ],
    }
    return JsonResponse(fc, status=200, content_type="application/geo+json")


# ---------------------------------------------------------------------------
# POST /rover/fields/{field_id}/contains
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def rover_field_contains(request, field_id: str):
    """Geofence check: is (lat, lon) inside the field boundary?

    Expected: {"lat": 24.37, "lon": 88.60}
    Returns:  {"inside": true, "distance_to_edge_m": 12.3}
    """
    if _check_api_key(request) is None:
        return _err(401, "Missing or invalid X-API-Key.")

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _err(400, "Invalid JSON body.")

    lat = payload.get("lat")
    lon = payload.get("lon")
    if lat is None or lon is None:
        return _err(422, "lat and lon are required.", {"lat": lat, "lon": lon})

    from apps.farms.models import Field
    try:
        field = Field.objects.get(slug=field_id)
    except Field.DoesNotExist:
        return _err(404, f"Field {field_id!r} not found.")

    if field.geometry is None or field.is_pin_estimate:
        # Pin estimate: use the radius as the geofence
        import math
        d = math.radians(111_320.0 * max(abs(lat - field.lat), abs(lon - field.lng)))
        dist_m = d * 6371_000.0 if field.lat and field.lng else float("inf")
        return _jstatus(200, {"ok": True, "inside": dist_m <= field.pin_radius_m,
                              "distance_to_edge_m": round(dist_m, 1)})

    try:
        from django.contrib.gis.geos import Point
        pt = Point(lon, lat, srid=4326)  # GeoDjango: (x=lon, y=lat)
        inside = field.geometry.contains(pt)
        distance = field.geometry.distance(pt)  # degrees; rough conversion to m
        import math
        dist_m = distance * 111_320.0  # approximate
        return _jstatus(200, {"ok": True, "inside": bool(inside),
                              "distance_to_edge_m": round(dist_m, 1)})
    except Exception as exc:
        logger.warning("geofence check failed for field %s: %s", field_id, exc)
        return _err(500, "Geofence check failed.", {"error": str(exc)})


# ---------------------------------------------------------------------------
# GET /rover/health  (no key required — liveness probe)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def rover_health(request):
    return _jstatus(200, {"ok": True, "service": "fieldshift-rover-adapter", "time": datetime.now(timezone.utc).isoformat()})
