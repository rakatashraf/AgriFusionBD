"""
Catalogue: crops, varieties, rule versions, planting calendars, soil tests.

The engine reads ``Crop`` traits + ``CropCalendar`` season windows + ``SoilTest``
to enumerate feasible rotations (plan §4, Phase 4).
"""

from django.db import models


class Crop(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    name_bn = models.CharField(max_length=120, blank=True)
    family = models.CharField(max_length=80)  # e.g. Poaceae, Fabaceae, Brassicaceae
    is_legume = models.BooleanField(default=False)

    # Agronomic traits used by the engine (bounds are declared in rules.py).
    water_demand_mm = models.PositiveIntegerField()  # seasonal water demand, mm
    kc_canopy = models.FloatField()  # peak canopy coefficient Kc
    kc_initial = models.FloatField()  # early-season Kc
    kc_late = models.FloatField()
    heat_tolerance = models.CharField(max_length=16, default="moderate")  # high | moderate | low
    drought_tolerance = models.CharField(max_length=16, default="moderate")

    # Economics (ranges, BDT) — the engine emits a net-margin RANGE, not a point.
    price_range_bdt_per_kg = models.JSONField(default=list)  # [low, high]
    cost_per_ha_bdt = models.JSONField(default=list)  # [low, high]
    yield_range_t = models.JSONField(default=list)  # [low, high] per ha

    # Hard-filter bounds (candidates.py applies these).
    soil_ph_min = models.FloatField(null=True, blank=True)
    soil_ph_max = models.FloatField(null=True, blank=True)
    irrigation_max = models.CharField(max_length=16, blank=True)  # canal | drip | rainfed
    equipment = models.JSONField(default=list, blank=True)  # ["tractor", ...]
    season_months = models.JSONField(default=list)  # e.g. [12,1,2,3]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.slug})"


class Variety(models.Model):
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name="varieties")
    name = models.CharField(max_length=120)
    region = models.CharField(max_length=120, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]


class CropRuleVersion(models.Model):
    """Versioned agronomic rule set; the engine stamps RULE_VERSION on runs."""

    version = models.CharField(max_length=32, unique=True)  # "v2026.11.0"
    git_sha = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)  # Kc tables, thresholds, bounds
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.version


class CropCalendar(models.Model):
    """Reviewed planting calendar: which crops fit which season window."""

    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name="calendars")
    season = models.CharField(max_length=16)  # boro | aman | rabi | autumn | spring
    start_month = models.PositiveIntegerField()  # 1-12
    end_month = models.PositiveIntegerField()
    region = models.CharField(max_length=120, blank=True, default="national")
    source = models.CharField(max_length=160, blank=True)  # DAE/BARC citation
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["season", "crop__name"]
        indexes = [models.Index(fields=["crop", "season"], name="soiltest_crop_season_idx")]


class SoilTest(models.Model):
    """A lab/field soil test for a field. The engine uses pH + organic matter."""

    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="soil_tests")
    tested_on = models.DateField()
    ph = models.FloatField()
    organic_matter_pct = models.FloatField(null=True, blank=True)
    ec_dsm = models.FloatField(null=True, blank=True)  # electrical conductivity
    n_pct = models.FloatField(null=True, blank=True)
    p_pct = models.FloatField(null=True, blank=True)
    k_pct = models.FloatField(null=True, blank=True)
    lab = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-tested_on"]

    def __str__(self):
        return f"Soil test {self.field.name} {self.tested_on} (pH {self.ph})"
