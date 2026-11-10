"""
Analyses: the run, its scenarios/plans/metrics, and the frozen input snapshot.

Key design points (plan §1 Phase 1 + §4 Phase 4):
  - ``AnalysisRun`` + its outbox event are written in ONE transaction (§8).
  - A completed run stores the **frozen InputSnapshot** (POWER asset ids +
    hashes, HLS asset id, catalogue version, rule version) so a rerun is
    reproducible.
  - Idempotency: ``idempotency_key`` is unique; a duplicate POST collapses to
    the existing run (plan §2).
  - Every ``Metric`` carries ``raw_value`` + ``qualification`` (plan §4).
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AnalysisRun(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("complete", "Complete"),
        ("partial", "Partial (insufficient evidence)"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    # Public, URL-safe identifier (e.g. "an-1"). The model's auto PK is internal;
    # the API exposes run_id as the "id" and looks it up with this slug.
    run_id = models.SlugField(max_length=16, unique=True, blank=True, editable=False)

    field = models.ForeignKey("farms.Field", on_delete=models.CASCADE, related_name="analyses")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="analyses")
    idempotency_key = models.CharField(max_length=128, unique=True, null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    progress_pct = models.PositiveIntegerField(default=0)

    # The farmer's request (weights + exclusions + season) — frozen on submit.
    request = models.JSONField(default=dict)
    # The rule version this run used (e.g. "v2026.11.0").
    rule_version = models.CharField(max_length=32, blank=True)
    # Result: the plans (baseline + ≤2 alternatives) + warnings.
    plans = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=dict, blank=True)

    # The frozen input snapshot lives on InputSnapshot.run (OneToOne,
    # related_name="snapshot"), accessible as ``run.snapshot``. We do NOT define
    # a reverse field here — two OneToOne fields pointing at each other clash
    # (fields.E302/E303).
    outbox_event_id = models.CharField(max_length=128, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["field", "status"]),
            models.Index(fields=["submitted_by"]),
        ]

    def save(self, *args, **kwargs):
        # Assign a stable, URL-safe public id on first save.
        if not self.run_id:
            self.run_id = f"an-{self.pk or uuid.uuid4().int % 1000000}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Analysis {self.run_id} · {self.field.name} · {self.status}"


class Scenario(models.Model):
    """A named candidate rotation (baseline or alternative)."""

    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name="scenarios")
    name = models.CharField(max_length=120)
    is_baseline = models.BooleanField(default=False)
    feasible = models.CharField(max_length=16, default="feasible")  # feasible | constrained | infeasible
    reasons = models.JSONField(default=list, blank=True)
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_baseline", "score"]

    def __str__(self):
        return f"{self.name} ({self.feasible})"


class RotationPlan(models.Model):
    """The ordered crop sequence of a scenario, one entry per season slot."""

    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="plan")
    position = models.PositiveIntegerField()
    crop = models.ForeignKey("catalogue.Crop", on_delete=models.PROTECT)
    season = models.CharField(max_length=16, blank=True)
    family = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        unique_together = ("scenario", "position")


class Metric(models.Model):
    """
    One scored metric for a scenario.

    ``raw_value`` is the unscaled number (e.g. mm irrigation demand);
    ``qualification`` is the human sentence that states assumptions (plan §4),
    e.g. "Reference ET × crop coefficients; canal efficiency 70%; paddy
    field-water term included".
    """

    KEY_CHOICES = [
        ("water_efficiency", "Water efficiency"),
        ("heat_resilience", "Heat resilience"),
        ("canopy_cover", "Canopy cover"),
        ("diversity", "Crop diversity"),
        ("net_margin", "Net margin"),
    ]

    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="metrics")
    key = models.CharField(max_length=32, choices=KEY_CHOICES)
    raw_value = models.FloatField()
    normalized = models.FloatField()  # 0..1 against declared bounds
    weight = models.FloatField(default=0.2)
    contribution = models.FloatField(null=True, blank=True)  # weight × normalized
    qualification = models.CharField(max_length=400, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scenario", "key")


class InputSnapshot(models.Model):
    """
    Frozen inputs for a completed run (plan §1, Phase 1).

    Storing the POWER asset id + content hash, the HLS asset id, the catalogue
    version and the rule version makes a rerun reproducible and proves
    provenance on export.
    """

    run = models.OneToOneField(AnalysisRun, on_delete=models.CASCADE, related_name="snapshot")
    power_asset_id = models.CharField(max_length=64, blank=True)
    power_content_hash = models.CharField(max_length=128, blank=True)
    hls_asset_id = models.CharField(max_length=64, blank=True)
    hls_content_hash = models.CharField(max_length=128, blank=True)
    catalogue_version = models.CharField(max_length=64, blank=True)
    rule_version = models.CharField(max_length=32, blank=True)
    soil_test_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Snapshot for run {self.run_id}"
