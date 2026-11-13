"""
Rover ingest tasks — Celery-wired, eager by default (plan §5.3, §5.7).

The robot posts a sample to ``POST /rover/samples`` and the handler returns
**immediately** (202) after recording an idempotent outbox row. The actual
parsing, grant check, upsert and telemetry update happen here, off the request
path — the same eager-by-default Celery pattern used for analysis runs
(``analyses.tasks.execute_analysis_run``).

Why an outbox instead of enqueueing directly into the broker?

* The robot's link is low-bandwidth and lossy. A durable row in Postgres
  survives a broker outage; a message that only sits in the broker is lost.
* Replays are idempotent (``(run_id, sample_id)`` + ``message_id`` upserts),
  so a redelivered outbox row is a no-op.
* Eager mode (dev) runs the task synchronously at enqueue time, so the
  outbox is drained immediately and the flow stays simple in tests.

A worker/beat drains pending rows via ``process_rover_inbox``.
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from celery import shared_task

logger = logging.getLogger("fieldshift.rover.tasks")


# ---------------------------------------------------------------------------
# Core ingest logic (pure — no request object). Shared by the task and tests.
# ---------------------------------------------------------------------------

def _resolve_device(payload: dict):
    from .models import Device
    rover_id = payload.get("rover_id", "")
    if not rover_id:
        return None
    return Device.objects.filter(serial=rover_id).first()


def _parse_timestamp(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _grant_active(device, field_slug: str) -> bool:
    from django.utils import timezone as dj_tz
    from apps.farms.models import Field
    from .models import DeviceGrant

    try:
        field = Field.objects.get(slug=field_slug)
    except Field.DoesNotExist:
        return False
    return (
        DeviceGrant.objects.filter(device=device, field=field, expires_at__isnull=True).exists()
        or DeviceGrant.objects.filter(device=device, field=field, expires_at__gt=dj_tz.now()).exists()
    )


def _upsert_observation(device, field, *, sensor, value, unit, taken_at, message_id, quality, depth_cm):
    from django.utils import timezone as dj_tz
    from .models import Observation

    Observation.objects.update_or_create(
        message_id=message_id,
        defaults={
            "device": device,
            "field": field,
            "sensor": sensor,
            "value": value,
            "unit": unit,
            "taken_at": taken_at or dj_tz.now(),
            "quality": quality,
            "calibrated": False,
            "depth_cm": depth_cm,
        },
    )


def ingest_sample(payload: dict) -> tuple[bool, str]:
    """Process one AgriRover-Q sample payload. Returns (ok, message).

    Idempotent: replaying the same (run_id, sample_id) upserts, never duplicates.
    """
    from django.db import transaction
    from django.utils import timezone as dj_tz
    from apps.farms.models import Field
    from .models import RoverSample, SurveyRun

    device = _resolve_device(payload)
    if device is None:
        return False, f"Unknown rover_id: {payload.get('rover_id')!r}"

    run_id = payload.get("run_id", "")
    sample_id = payload.get("sample_id")
    if not run_id or sample_id is None:
        return False, "run_id and sample_id are required"

    field_slug = payload.get("field_slug") or payload.get("field_id") or ""
    if not field_slug:
        return False, "field_slug is required"

    if not _grant_active(device, field_slug):
        return False, f"No active grant for device {payload.get('rover_id')!r} → {field_slug!r}"

    try:
        field = Field.objects.get(slug=field_slug)
    except Field.DoesNotExist:
        return False, f"Field {field_slug!r} not found"

    soil = payload.get("soil", {})
    air = payload.get("air", {})
    battery = payload.get("battery", {})
    position = payload.get("position", {})
    gps = payload.get("gps", {})
    timestamp = _parse_timestamp(payload.get("timestamp"))
    probe_ok = bool(soil.get("probe_ok", True))

    with transaction.atomic():
        run, _created = SurveyRun.objects.update_or_create(
            run_id=run_id,
            defaults={"device": device, "field": field, "status": "running", "last_state": "sample"},
        )
        if not run.started_at:
            run.started_at = timestamp or dj_tz.now()
            run.save(update_fields=["started_at"])

        RoverSample.objects.update_or_create(
            run=run,
            sample_id=int(sample_id),
            defaults={
                "timestamp": timestamp,
                "lane": payload.get("lane"),
                "heading_deg": payload.get("heading_deg"),
                "lat": position.get("lat"),
                "lon": position.get("lon"),
                "gps_fix": gps.get("fix", ""),
                "gps_hdop": gps.get("hdop"),
                "gps_satellites": gps.get("satellites"),
                "probe_ok": probe_ok,
                "probe_depth_mm": soil.get("probe_depth_mm"),
                "moisture_vwc": soil.get("moisture_vwc"),
                "moisture_raw": soil.get("moisture_raw"),
                "soil_temp_c": soil.get("temperature_c"),
                "air_temp_c": air.get("temperature_c"),
                "air_humidity_pct": air.get("humidity_pct"),
                "air_pressure_hpa": air.get("pressure_hpa"),
                "battery_voltage": battery.get("voltage"),
                "battery_soc_pct": battery.get("soc_pct"),
                "raw_json": payload,
            },
        )

        if soil.get("moisture_vwc") is not None:
            _upsert_observation(
                device, field, sensor="moisture",
                value=float(soil["moisture_vwc"]) * 100.0, unit="%",
                taken_at=timestamp,
                message_id=f"{run_id}:{int(sample_id)}:moisture",
                quality="suspect" if not probe_ok else "valid",
                depth_cm=float(soil.get("probe_depth_mm", 50.0)) / 10.0,
            )
        if soil.get("temperature_c") is not None:
            _upsert_observation(
                device, field, sensor="temperature",
                value=float(soil["temperature_c"]), unit="°C",
                taken_at=timestamp,
                message_id=f"{run_id}:{int(sample_id)}:temperature",
                quality="suspect" if not probe_ok else "valid",
                depth_cm=float(soil.get("probe_depth_mm", 50.0)) / 10.0,
            )

        if battery.get("soc_pct") is not None:
            device.battery_pct = int(battery["soc_pct"])
        device.last_seen = dj_tz.now()
        device.save(update_fields=["battery_pct", "last_seen", "updated_at"])

        run.samples_count = run.samples.count()
        run.save(update_fields=["samples_count", "updated_at"])

    return True, "ok"


def ingest_image(payload: dict) -> tuple[bool, str]:
    """Store a sample photo (base64 JPEG/PNG) and attach it to the sample."""
    from django.conf import settings as dj_settings
    from .models import RoverSample, SurveyRun

    filename = Path(payload.get("filename", "")).name if payload.get("filename") else "sample.jpg"
    data_b64 = payload.get("data", "")
    if not data_b64:
        return False, "base64 'data' is required"

    try:
        raw = base64.b64decode(data_b64)
    except Exception:
        return False, "invalid base64"

    if raw[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif raw[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    else:
        return False, "only JPEG and PNG accepted"

    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        filename = (filename.rsplit(".", 1)[0] if "." in filename else filename) + ext

    media_dir = Path(dj_settings.MEDIA_ROOT) / "rover_images"
    media_dir.mkdir(parents=True, exist_ok=True)
    dest = media_dir / f"{payload.get('run_id', 'run')}_{payload.get('sample_id', 0)}_{filename}"
    dest.write_bytes(raw)

    run_id = payload.get("run_id", "")
    sample_id = payload.get("sample_id")
    if run_id and sample_id is not None:
        try:
            run = SurveyRun.objects.get(run_id=run_id)
            sample = run.samples.get(sample_id=int(sample_id))
            sample.image = f"rover_images/{dest.name}"
            sample.save(update_fields=["image", "updated_at"])
        except (SurveyRun.DoesNotExist, RoverSample.DoesNotExist):
            pass  # stored on disk; sample may land later

    return True, "ok"


def ingest_status(payload: dict) -> tuple[bool, str]:
    """Heartbeat: refresh device telemetry and advance the active run state."""
    from django.utils import timezone as dj_tz
    from .models import SurveyRun

    device = _resolve_device(payload)
    if device is None:
        return False, f"Unknown rover_id: {payload.get('rover_id')!r}"

    battery = payload.get("battery", {})
    if battery.get("soc_pct") is not None:
        device.battery_pct = int(battery["soc_pct"])
    device.last_seen = dj_tz.now()

    state = payload.get("state", "")
    if state:
        status_map = {"done": "complete", "abort": "aborted"}
        new_status = status_map.get(state, "running")
        SurveyRun.objects.filter(device=device, status="running").update(
            last_state=state,
            status=new_status,
            completed_at=dj_tz.now() if state == "done" else None,
        )

    device.save(update_fields=["battery_pct", "last_seen", "updated_at"])
    return True, "ok"


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=2)
def process_rover_sample(self, outbox_id: int) -> None:
    """Ingest one sample from a durable outbox row, then mark it delivered.

    Failures re-queue (with backoff) so a transient DB/network hiccup never
    drops a reading. After ``max_retries`` the row is marked dead-lettered.
    """
    from .models import RoverInbox

    try:
        row = RoverInbox.objects.get(pk=outbox_id)
    except RoverInbox.DoesNotExist:
        logger.info("rover inbox %s already gone", outbox_id)
        return

    if row.status not in ("pending", "retry"):
        return  # already delivered or dead — skip

    ok, msg = ingest_sample(row.payload)
    if ok:
        row.status = "delivered"
        row.delivered_at = datetime.now(timezone.utc)
        row.error = None
        row.save(update_fields=["status", "delivered_at", "error", "updated_at"])
        return

    # Business-level rejection (unknown rover, no grant, bad field) is not
    # transient — mark it dead immediately so we don't hammer the broker.
    row.attempts += 1
    row.error = msg
    row.status = "dead" if not _is_transient(msg) else "retry"
    row.save(update_fields=["attempts", "error", "status", "updated_at"])
    if row.status == "retry" and self.request.retries < self.max_retries:
        raise self.retry(exc=RuntimeError(msg))
    logger.warning("rover sample rejected: %s", msg)


def _is_transient(msg: str) -> bool:
    # "not found" / "no grant" / "required" are permanent; DB/IO errors are not.
    return not any(k in msg.lower() for k in ("unknown rover_id", "not found", "no active grant", "required", "accepted"))


@shared_task(bind=True, max_retries=2)
def process_rover_image(self, outbox_id: int) -> None:
    from .models import RoverInbox

    try:
        row = RoverInbox.objects.get(pk=outbox_id)
    except RoverInbox.DoesNotExist:
        return
    if row.status not in ("pending", "retry"):
        return

    ok, msg = ingest_image(row.payload)
    if ok:
        row.status = "delivered"
        row.delivered_at = datetime.now(timezone.utc)
        row.error = None
        row.save(update_fields=["status", "delivered_at", "error", "updated_at"])
        return
    row.attempts += 1
    row.error = msg
    row.status = "dead" if not _is_transient(msg) else "retry"
    row.save(update_fields=["attempts", "error", "status", "updated_at"])
    if row.status == "retry" and self.request.retries < self.max_retries:
        raise self.retry(exc=RuntimeError(msg))


@shared_task(bind=True)
def process_rover_status(self, outbox_id: int) -> None:
    from .models import RoverInbox

    try:
        row = RoverInbox.objects.get(pk=outbox_id)
    except RoverInbox.DoesNotExist:
        return
    if row.status not in ("pending", "retry"):
        return

    ok, msg = ingest_status(row.payload)
    if ok:
        row.status = "delivered"
        row.delivered_at = datetime.now(timezone.utc)
        row.error = None
        row.save(update_fields=["status", "delivered_at", "error", "updated_at"])
        return
    row.attempts += 1
    row.error = msg
    row.status = "dead"
    row.save(update_fields=["attempts", "error", "status", "updated_at"])


@shared_task(name="fieldshift.rover.drain_inbox")
def drain_rover_inbox(limit: int = 500) -> int:
    """Drain pending/retry inbox rows by enqueueing them for processing.

    Runs eager in dev (each task runs inline) and under a worker/beat in prod.
    Returns the number of rows enqueued.
    """
    from .models import RoverInbox

    rows = list(
        RoverInbox.objects.filter(status__in=["pending", "retry"])
        .order_by("created_at")[:limit]
    )
    for row in rows:
        if row.kind == "sample":
            process_rover_sample.delay(row.pk)
        elif row.kind == "image":
            process_rover_image.delay(row.pk)
        elif row.kind == "status":
            process_rover_status.delay(row.pk)
    return len(rows)
