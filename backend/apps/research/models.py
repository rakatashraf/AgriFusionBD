"""
Research: research projects + export jobs.

``ExportJob`` is the fix for the "createExportJob creates no downloadable
artifact" defect (plan §2): it stores the generated CSV/GeoJSON file under
``MEDIA_ROOT`` and a ``provenance.json`` manifest listing asset versions and
the rule version (plan §5 definition of done #5).
"""

from django.conf import settings
from django.db import models


class ResearchProject(models.Model):
    name = models.CharField(max_length=160)
    pi = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="projects")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]


class ExportJob(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("complete", "Complete"),
        ("failed", "Failed"),
    ]
    FORMAT_CHOICES = [("csv", "CSV"), ("geojson", "GeoJSON")]

    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="export_jobs")
    scope = models.CharField(max_length=64, default="field")  # field | region
    field = models.ForeignKey("farms.Field", null=True, blank=True, on_delete=models.SET_NULL, related_name="exports")
    format = models.CharField(max_length=16, choices=FORMAT_CHOICES, default="csv")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    row_count = models.PositiveIntegerField(default=0)

    # The real artifacts (plan §5 definition of done #5).
    file_path = models.CharField(max_length=512, blank=True)  # relative to MEDIA_ROOT
    provenance_path = models.CharField(max_length=512, blank=True)
    provenance = models.JSONField(default=dict, blank=True)  # inlined manifest

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Export {self.pk} · {self.format} · {self.status}"
