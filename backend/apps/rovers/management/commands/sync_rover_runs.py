"""
sync_rover_runs — pull captured AgriRover-Q runs from the FastAPI service
into FieldShift's database (plan §5.3 item 4, §6 P1 item 8).

This is the **zero-firmware fallback**: instead of the robot pushing
samples to FieldShift, we pull from the robot's own cloud/api.py service.
Read-only on the robot side; no firmware changes required.

Usage:
    python manage.py sync_rover_runs --base-url http://192.168.1.42:8000 \
        --api-key dev-key [--rover-id agrirover-q-01] [--dry-run]

What it does:
    1. GET  /runs                     → list of run_ids
    2. GET  /runs/{run_id}/status     → status, samples_count
    3. GET  /runs/{run_id}/samples    → sample payloads
    4. For each sample: upsert SurveyRun + RoverSample + Observation rows
       (same mapping as POST /rover/samples, §5.4)

The command is idempotent: re-running with the same run_id upserts the
same rows (no duplicates).
"""

import json
import logging
from datetime import datetime, timezone

import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as dj_tz

from apps.farms.models import Field
from apps.rovers.models import (
    Device,
    DeviceGrant,
    Observation,
    RoverSample,
    SurveyRun,
)

logger = logging.getLogger("fieldshift.sync")


class Command(BaseCommand):
    help = "Sync AgriRover-Q runs from the robot's FastAPI service into FieldShift."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url", required=True,
            help="Base URL of the robot's cloud/api.py (e.g. http://192.168.1.42:8000)",
        )
        parser.add_argument(
            "--api-key", default="dev-key",
            help="Shared X-API-Key (default: dev-key)",
        )
        parser.add_argument(
            "--rover-id", default=None,
            help="Filter to a specific rover_id (default: all runs)",
        )
        parser.add_argument(
            "--timeout", type=int, default=10,
            help="HTTP timeout in seconds (default: 10)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print what would be written without touching the DB",
        )

    def handle(self, *args, **options):
        base = options["base_url"].rstrip("/")
        key = options["api_key"]
        rover_filter = options["rover_id"]
        timeout = options["timeout"]
        dry_run = options["dry_run"]

        headers = {"X-API-Key": key, "Accept": "application/json"}
        session = requests.Session()
        session.headers.update(headers)

        # 1) List runs
        self.stdout.write(f"Fetching runs from {base} ...")
        try:
            resp = session.get(f"{base}/runs", timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f"Cannot reach the robot at {base}: {exc}")

        runs_data = resp.json()
        # The robot returns {"runs": [...]} or a bare list
        runs = runs_data.get("runs", runs_data) if isinstance(runs_data, dict) else runs_data

        if rover_filter:
            runs = [r for r in runs if r.get("rover_id") == rover_filter or
                    r.get("run_id", "").startswith(rover_filter)]

        if not runs:
            self.stdout.write(self.style.WARNING("No runs found."))
            return

        self.stdout.write(f"Found {len(runs)} run(s).")

        synced = 0
        for run in runs:
            run_id = run.get("run_id", "")
            rover_id = run.get("rover_id", "")
            if not run_id:
                continue
            try:
                n = self._sync_one_run(
                    session, base, run_id, rover_id, timeout, dry_run,
                )
                synced += n
                self.stdout.write(
                    f"  {'[dry-run] ' if dry_run else ''}run {run_id}: "
                    f"{n} sample(s) synced"
                )
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f"  run {run_id}: failed — {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {synced} sample(s) {'would be' if dry_run else ''} synced."
            )
        )

    def _sync_one_run(self, session, base, run_id, rover_id, timeout, dry_run) -> int:
        """Pull one run's samples and upsert the DB rows."""

        # Resolve device
        device = Device.objects.filter(serial=rover_id).first()
        if device is None:
            raise ValueError(
                f"Unknown rover_id {rover_id!r}. "
                f"Register the device first (python manage.py seed_demo or admin)."
            )

        # Get run status
        status_resp = session.get(f"{base}/runs/{run_id}/status", timeout=timeout)
        status_resp.raise_for_status()
        run_status = status_resp.json()
        status = run_status.get("status", "running")
        last_state = run_status.get("last_state", "")

        # Get samples
        samples_resp = session.get(f"{base}/runs/{run_id}/samples", timeout=timeout)
        samples_resp.raise_for_status()
        samples_data = samples_resp.json()
        samples = samples_data.get("samples", samples_data) if isinstance(samples_data, dict) else samples_data

        # Determine the target field (from the first sample that has one,
        # or the most recently granted field)
        field = self._resolve_field(device, samples)
        if field is None:
            raise ValueError(
                f"No active grant for device {rover_id!r}; cannot determine target field."
            )

        # Map robot status → FieldShift status
        status_map = {"done": "complete", "complete": "complete",
                      "abort": "aborted", "aborted": "aborted"}
        fs_status = status_map.get(status, "running")

        if not dry_run:
            from django.db import transaction
            with transaction.atomic():
                run, created = SurveyRun.objects.update_or_create(
                    run_id=run_id,
                    defaults={
                        "device": device,
                        "field": field,
                        "status": fs_status,
                        "last_state": last_state,
                    },
                )
                if created:
                    run.started_at = dj_tz.now()
                    run.save()

                for i, s in enumerate(samples, start=1):
                    self._upsert_sample(run, device, field, s, i, rover_id)

                run.samples_count = run.samples.count()
                run.save(update_fields=["samples_count", "updated_at"])

                # Update device telemetry
                device.last_seen = dj_tz.now()
                device.save(update_fields=["last_seen", "updated_at"])
        else:
            # Dry-run: create a transient run to count samples
            run = SurveyRun(run_id=run_id, device=device, field=field, status=fs_status)
            count = len(samples) if isinstance(samples, list) else 0
            return count

        return len(samples) if isinstance(samples, list) else 0

    def _resolve_field(self, device, samples) -> Field | None:
        """Pick the target field: prefer the field named in the samples,
        else the most recently granted field."""
        # Try to find a field_slug in the samples
        if isinstance(samples, list):
            for s in samples:
                slug = s.get("field_slug") or s.get("field_id") or ""
                if slug:
                    try:
                        return Field.objects.get(slug=slug)
                    except Field.DoesNotExist:
                        continue
        # Fallback: most recently created active grant
        from django.utils import timezone as dj_tz
        grant = DeviceGrant.objects.filter(
            device=device,
        ).filter(expires_at__isnull=True).order_by("-created_at").first()
        if grant is None:
            grant = DeviceGrant.objects.filter(
                device=device, expires_at__gt=dj_tz.now()
            ).order_by("-created_at").first()
        return grant.field if grant else None

    def _upsert_sample(self, run, device, field, s: dict, sample_id: int, rover_id: str):
        """Upsert one RoverSample + derived Observation rows."""
        from datetime import datetime as dt

        def _ts(val):
            if not val:
                return None
            try:
                return dt.fromisoformat(str(val).replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None

        pos = s.get("position", {})
        gps = s.get("gps", {})
        soil = s.get("soil", {})
        air = s.get("air", {})
        batt = s.get("battery", {})
        probe_ok = bool(soil.get("probe_ok", True))

        sample, _ = RoverSample.objects.update_or_create(
            run=run, sample_id=sample_id,
            defaults={
                "timestamp": _ts(s.get("timestamp")),
                "lane": s.get("lane"),
                "heading_deg": s.get("heading_deg"),
                "lat": pos.get("lat"),
                "lon": pos.get("lon"),
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
                "battery_voltage": batt.get("voltage"),
                "battery_soc_pct": batt.get("soc_pct"),
                "raw_json": s,
            },
        )

        quality = "suspect" if not probe_ok else "valid"
        depth_cm = (float(soil.get("probe_depth_mm", 50.0)) / 10.0)
        taken_at = sample.timestamp or dj_tz.now()

        if soil.get("moisture_vwc") is not None:
            Observation.objects.update_or_create(
                message_id=f"{run.run_id}:{sample_id}:moisture",
                defaults={
                    "device": device, "field": field,
                    "sensor": "moisture",
                    "value": float(soil["moisture_vwc"]) * 100.0,
                    "unit": "%", "taken_at": taken_at,
                    "quality": quality, "calibrated": False, "depth_cm": depth_cm,
                },
            )
        if soil.get("temperature_c") is not None:
            Observation.objects.update_or_create(
                message_id=f"{run.run_id}:{sample_id}:temperature",
                defaults={
                    "device": device, "field": field,
                    "sensor": "temperature",
                    "value": float(soil["temperature_c"]),
                    "unit": "°C", "taken_at": taken_at,
                    "quality": quality, "calibrated": False, "depth_cm": depth_cm,
                },
            )
