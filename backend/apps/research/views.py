"""
Research endpoints (plan §2):

    GET  /research/locations
    GET/POST /research/exports
    GET  /research/exports/{id}/download
"""

import json

from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import user_roles
from apps.audit.services import record
from apps.catalogue.models import CropRuleVersion
from apps.environment.models import FieldIndicator
from apps.farms.models import Field

from .models import ExportJob
from .serializers import serialize_job
from .services import generate, resolve_file, resolve_provenance


class ResearchLocationsView(APIView):
    """GET /research/locations — fields available to a researcher (read-all)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if "researcher" not in user_roles(request.user):
            return Response(
                {"error": {"code": "forbidden", "message": "Researcher role required.", "details": None}},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = Field.objects.select_related("farm")[:100]
        return Response([
            {
                "slug": f.slug,
                "name": f.name,
                "lat": f.lat,
                "lng": f.lng,
                "areaHa": float(f.area_ha) if f.area_ha else None,
                "isPinEstimate": f.is_pin_estimate,
                "region": f.farm.region if f.farm else "",
                "indicatorCount": FieldIndicator.objects.filter(field=f).count(),
            }
            for f in qs
        ])


class ExportListCreateView(APIView):
    """GET/POST /research/exports."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExportJob.objects.filter(requester=request.user).order_by("-created_at")[:50]
        return Response([serialize_job(j) for j in qs])

    def post(self, request):
        roles = user_roles(request.user)
        if "researcher" not in roles and "officer" not in roles:
            return Response(
                {"error": {"code": "forbidden", "message": "Researcher or officer role required.",
                           "details": None}},
                status=status.HTTP_403_FORBIDDEN,
            )
        scope = request.data.get("scope", "field")
        fmt = request.data.get("format", "csv")
        if fmt not in ("csv", "geojson"):
            return Response(
                {"error": {"code": "validation_error", "message": "format must be csv|geojson",
                           "details": {"format": fmt}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        field_slug = request.data.get("fieldId")
        field = Field.objects.filter(slug=field_slug).first() if field_slug else None

        active_rule = CropRuleVersion.objects.filter(is_active=True).order_by("-created_at").first()
        job = ExportJob.objects.create(
            requester=request.user,
            scope=scope,
            format=fmt,
            field=field,
            status="queued",
            provenance={"ruleVersion": active_rule.version if active_rule else "unversioned",
                        "catalogueVersion": active_rule.version if active_rule else ""},
        )
        # Generate eagerly (the engine is fast; Celery eager by default).
        generate(job)
        job.refresh_from_db()
        record("export.create", request.user, target_type="export", target_id=str(job.pk),
               detail={"format": fmt, "rows": job.row_count}, ip=_ip(request))
        return Response(serialize_job(job), status=status.HTTP_201_CREATED)


class ExportDownloadView(APIView):
    """GET /research/exports/{id}/download — the real artifact + provenance."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = ExportJob.objects.filter(pk=pk, requester=request.user).first()
        if job is None:
            return Response(
                {"error": {"code": "not_found", "message": "Export not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if job.status != "complete":
            return Response(
                {"error": {"code": "not_found", "message": "Export not ready.", "details": {"status": job.status}}},
                status=status.HTTP_409_CONFLICT,
            )
        want = request.query_params.get("what", "file")
        if want == "provenance":
            path = resolve_provenance(job)
            if path is None:
                return Response(
                    {"error": {"code": "not_found", "message": "Provenance not available.", "details": None}},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return FileResponse(path.open("rb"), content_type="application/json",
                                filename=f"exp-{job.pk}.provenance.json")
        path = resolve_file(job)
        if path is None:
            return Response(
                {"error": {"code": "not_found", "message": "File not available.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        ctype = "application/geo+json" if job.format == "geojson" else "text/csv"
        return FileResponse(path.open("rb"), content_type=ctype,
                            filename=path.name)


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
