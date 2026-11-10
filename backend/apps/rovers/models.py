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
    """A farmer grants a device read access to their field (report §11 consent)."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="grants")
    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="device_grants")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("device", "field")


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
    A local rover reading (moisture/temperature/EC) — distinct from NASA data.

    ``message_id`` enables dedupe on device upload (plan §2). ``quality`` and
    ``calibrated`` carry the report's "with quality and calibration checks".
    """

    SENSOR_CHOICES = [
        ("moisture", "Soil moisture"),
        ("temperature", "Temperature"),
        ("ec", "Electrical conductivity"),
        ("ndvi_spot", "NDVI spot"),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="observations")
    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="observations")
    sensor = models.CharField(max_length=32, choices=SENSOR_CHOICES)
    value = models.FloatField()
    unit = models.CharField(max_length=16)
    taken_at = models.DateTimeField()
    message_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    quality = models.CharField(max_length=16, default="valid")  # valid | partial | suspect
    calibrated = models.BooleanField(default=False)
    depth_cm = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-taken_at"]
        indexes = [models.Index(fields=["field", "sensor", "taken_at"]),
                   models.Index(fields=["device", "taken_at"])]

    def __str__(self):
        return f"{self.sensor} {self.value}{self.unit} @ {self.field.name}"
