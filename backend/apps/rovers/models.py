"""
Rovers: the field device fleet, grants, calibration, missions, observations.

MVP scope (report §10): observation upload + safe missions only — NO remote
driving. ``Observation`` is the local evidence the UI shows alongside NASA
data, with quality/calibration flags.
"""

from django.conf import settings
from django.contrib.gis.db import models as gis
from django.db import models


class Device(models.Model):
    STATUS_CHOICES = [
        ("idle", "Idle"),
        ("on_mission", "On mission"),
        ("maintenance", "Maintenance"),
        ("offline", "Offline"),
    ]

    name = models.CharField(max_length=120)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="idle")
    battery_pct = models.PositiveIntegerField(default=100)
    last_seen = models.DateTimeField(null=True, blank=True)
    serial = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DeviceGrant(models.Model):
    """A farmer grants a device read access to their field (report §11 consent).

    ``expires_at`` satisfies report §2 (grants must carry an expiry) and
    ``§10`` (device subscription is time-bounded).
    """

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="grants")
    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="device_grants")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("device", "field")

    def is_active(self) -> bool:
        if self.expires_at is None:
            return True
        from django.utils import timezone
        return timezone.now() < self.expires_at


class SurveyRun(models.Model):
    """
    A single rover survey run — the unit of idempotency for the AgriRover-Q
    contract (``run_id`` is unique; replaying a spooled sample upserts).

    Report §10 requires a per-run audit trail; this model provides it.
    """

    STATUS_CHOICES = [
        ("running", "Running"),
        ("complete", "Complete"),
        ("aborted", "Aborted"),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="survey_runs")
    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="survey_runs")
    run_id = models.CharField(max_length=128, unique=True)  # rover's run_id, e.g. "video-20261110-100504"
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="running")
    last_state = models.CharField(max_length=32, blank=True)  # last mission state from heartbeat
    samples_count = models.PositiveIntegerField(default=0)
    route = gis.GeometryField(null=True, blank=True, srid=4326)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["device", "run_id"], name="surveyrun_device_runidx"),
                   models.Index(fields=["field", "status"], name="surveyrun_field_status_idx")]

    def __str__(self):
        return f"Run {self.run_id} · {self.device.name} · {self.status}"


class RoverSample(models.Model):
    """
    One raw soil sample from an AgriRover-Q run.

    The composite key ``(run, sample_id)`` enforces the spec's upsert
    semantics at the database level: a replayed spooled sample overwrites,
    never duplicates.
    """

    run = models.ForeignKey(SurveyRun, on_delete=models.CASCADE, related_name="samples")
    sample_id = models.PositiveIntegerField()
    timestamp = models.DateTimeField(null=True, blank=True)  # measurement time (not upload time)
    lane = models.PositiveIntegerField(null=True, blank=True)
    heading_deg = models.FloatField(null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    gps_fix = models.CharField(max_length=16, blank=True)
    gps_hdop = models.FloatField(null=True, blank=True)
    gps_satellites = models.PositiveIntegerField(null=True, blank=True)
    probe_ok = models.BooleanField(default=True)
    probe_depth_mm = models.FloatField(null=True, blank=True)
    moisture_vwc = models.FloatField(null=True, blank=True)  # m3/m3
    moisture_raw = models.PositiveIntegerField(null=True, blank=True)
    soil_temp_c = models.FloatField(null=True, blank=True)
    air_temp_c = models.FloatField(null=True, blank=True)
    air_humidity_pct = models.FloatField(null=True, blank=True)
    air_pressure_hpa = models.FloatField(null=True, blank=True)
    battery_voltage = models.FloatField(null=True, blank=True)
    battery_soc_pct = models.FloatField(null=True, blank=True)
    image = models.FileField(upload_to="rover_images/", null=True, blank=True)
    raw_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-timestamp"]
        unique_together = ("run", "sample_id")
        indexes = [models.Index(fields=["run", "sample_id"], name="roversample_run_sampleidx")]

    def __str__(self):
        return f"Sample {self.sample_id} in run {self.run.run_id}"


class RoverInbox(models.Model):
    """Durable outbox for rover ingest (plan §5.3, §5.7).

    The robot posts a sample; the handler records a row here and returns 202
    immediately. A Celery worker (eager in dev) drains the queue and performs
    the actual upsert, so heavy work never blocks the robot's request and the
    message survives a broker outage.

    Idempotent per (run_id, sample_id, kind) — a redelivered or replayed
    message reuses the same row rather than duplicating work.
    """

    KIND_CHOICES = [
        ("sample", "Sample"),
        ("image", "Image"),
        ("status", "Status/heartbeat"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("retry", "Retry"),
        ("delivered", "Delivered"),
        ("dead", "Dead-lettered"),
    ]

    device = models.ForeignKey(Device, null=True, on_delete=models.SET_NULL, related_name="inbox")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    dedupe_key = models.CharField(max_length=160)  # e.g. "sample:run_id:sample_id"
    payload = models.JSONField()  # the full AgriRover-Q message
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="rover_inbox_status_created_idx"),
            models.Index(fields=["device", "kind"], name="rover_inbox_device_kind_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["dedupe_key"], name="rover_inbox_unique_dedupe"),
        ]

    def __str__(self):
        return f"{self.kind} {self.dedupe_key} · {self.status}"


class Command(models.Model):
    """
    A movement/driving command (model only — endpoints are out of scope for
    the pilot; report §10 gates remote driving behind tests that cannot be
    run before Saturday).

    Report §8 requires the entity to exist; §10 requires the audit trail.
    Keeping it inert is the honest position.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("acknowledged", "Acknowledged"),
        ("expired", "Expired"),
        ("rejected", "Rejected"),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="commands")
    command_id = models.CharField(max_length=128, unique=True)
    sequence = models.PositiveIntegerField()
    payload = models.JSONField(default=dict, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    ack_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="commands_issued")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [models.Index(fields=["device", "sequence"], name="command_device_seq_idx")]

    def __str__(self):
        return f"Cmd {self.command_id} · {self.device.name} · {self.status}"



class SensorCalibration(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="calibrations")
    sensor = models.CharField(max_length=32)  # moisture | temperature | ec
    calibrated_on = models.DateField()
    reference_value = models.FloatField(null=True, blank=True)
    uncertainty = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-calibrated_on"]


class Mission(models.Model):
    """A safe, pre-planned observation mission (no remote driving — report §10)."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="missions")
    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="missions")
    route = gis.GeometryField(null=True, blank=True, srid=4326)
    status = models.CharField(max_length=16, default="planned")  # planned | running | done
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Observation(models.Model):
    """
    A local rover reading (moisture/temperature) — distinct from NASA data.

    ``message_id`` enables dedupe on device upload (plan §2). ``quality`` and
    ``calibrated`` carry the report's "with quality and calibration checks".

    ``SENSOR_CHOICES`` excludes ``ec`` and ``ndvi_spot`` until a sensor for
    each exists (AgriRover-Q v0.2 hardware list — §5.6).
    """

    SENSOR_CHOICES = [
        ("moisture", "Soil moisture"),
        ("temperature", "Temperature"),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="observations")
    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="observations")
    sensor = models.CharField(max_length=32, choices=SENSOR_CHOICES)
    value = models.FloatField()
    unit = models.CharField(max_length=16)
    taken_at = models.DateTimeField()
    uploaded_at = models.DateTimeField(auto_now_add=True)  # separate from measurement time (report §10)
    message_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    quality = models.CharField(max_length=16, default="valid")  # valid | partial | suspect
    calibrated = models.BooleanField(default=False)
    calibration = models.ForeignKey(
        "SensorCalibration", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="observations",
    )  # derived, not trusted from the client (§5.5)
    depth_cm = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-taken_at"]
        indexes = [models.Index(fields=["field", "sensor", "taken_at"], name="observ_field_sensor_taken_idx"),
                   models.Index(fields=["device", "taken_at"], name="observ_device_taken_idx")]

    def __str__(self):
        return f"{self.sensor} {self.value}{self.unit} @ {self.field.name}"
