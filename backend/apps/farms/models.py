"""
Farms: Farm, versioned Field boundary, crop history, management events.

``Field`` uses a GeoDjango ``PolygonField`` (srid=4326). A pin-only field is
stored with ``is_pin_estimate=True`` + ``pin_radius_m`` and a point geometry,
never a fabricated polygon (plan §1, Phase 1).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.gis.db import models as gis


class Farm(models.Model):
    name = models.CharField(max_length=160)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="farms")
    region = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Field(models.Model):
    """A managed plot. Boundary is a versioned polygon (or a pin estimate)."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="fields")
    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fields")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)

    # Geometry: polygon for mapped boundaries, point for pin estimates.
    geometry = gis.GeometryField(null=True, blank=True, srid=4326)
    is_pin_estimate = models.BooleanField(default=False)
    pin_radius_m = models.PositiveIntegerField(default=25)
    area_ha = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # Location metadata (denormalised for display; geometry is authoritative).
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    # Profile (soil type, irrigation, etc.) — edited via PATCH /fields/{id}/profile.
    soil_type = models.CharField(max_length=80, blank=True)
    irrigation = models.CharField(max_length=80, blank=True, default="canal")
    slope_pct = models.FloatField(null=True, blank=True)
    drainage = models.CharField(max_length=80, blank=True, default="moderate")

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["farmer", "slug"], name="unique_field_slug_per_farmer"),
        ]

    def __str__(self):
        return self.name


class FieldBoundaryVersion(models.Model):
    """Immutable history of a field's boundary (plan §1: versioned boundary)."""

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="boundary_versions")
    version = models.PositiveIntegerField()
    geometry = gis.GeometryField(srid=4326)
    area_ha = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        unique_together = ("field", "version")


class CropHistory(models.Model):
    """A season of actual planting — the source of the (never-invented) baseline."""

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="crop_history")
    crop = models.ForeignKey("catalogue.Crop", on_delete=models.PROTECT, related_name="history")
    season = models.CharField(max_length=16, default="boro")  # boro | aman | rabi | autumn | spring
    year = models.PositiveIntegerField()
    planted_on = models.DateField(null=True, blank=True)
    harvested_on = models.DateField(null=True, blank=True)
    area_ha = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    yield_t = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-season"]
        indexes = [models.Index(fields=["field", "year"])]

    def __str__(self):
        return f"{self.field.name} · {self.crop.name} {self.season} {self.year}"


class ManagementEvent(models.Model):
    """Fertiliser, irrigation, pest events — context for the engine's warnings."""

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=32)  # fertiliser | irrigation | pest | harvest | other
    occurred_on = models.DateField()
    detail = models.JSONField(default=dict, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_on"]

    def __str__(self):
        return f"{self.kind} @ {self.field.name} {self.occurred_on}"
