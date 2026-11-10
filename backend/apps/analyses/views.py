"""
Analysis endpoints (plan §2):

    POST /fields/{id}/analyses   → 202 + run, honours Idempotency-Key
    GET  /analyses/{id}
    GET  /analyses/{id}/evidence
    POST /analyses/{id}/cancel
    GET  /analyses?field=        (list for a field)

Idempotency: the client sends an ``idempotencyKey`` in the body; a duplicate
POST with the same key returns the existing run (one persisted run per key,
plan §2 + plan §7 check 3).
"""

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.accounts.permissions import CanSubmitAnalysis, user_roles
from apps.audit.services import record
from apps.farms.models import Field

from .models import AnalysisRun
from .serializers import AnalysisRequestSerializer
from .tasks import execute_analysis_run


def _serialize_run(run: AnalysisRun) -> dict:
    return {
        "id": run.run_id,
        "fieldId": run.field.slug,
        "status": run.status,
        "progressPct": run.progress_pct,
        "ruleVersion": run.rule_version,
        "idempotencyKey": run.idempotency_key,
        "plans": run.plans,
        "warnings": run.warnings,
        "evidence": run.evidence,
        "missingData": run.evidence.get("missing_data", []),
        "submittedAt": run.submitted_at,
        "completedAt": run.completed_at,
    }


class AnalysisViewSet(ReadOnlyModelViewSet):
    """GET /analyses + GET /analyses/{run_id} + evidence + cancel."""

    permission_classes = [IsAuthenticated]
    lookup_field = "run_id"

    def list(self, request, *args, **kwargs):
        field_slug = request.query_params.get("field")
        qs = AnalysisRun.objects.select_related("field").all()
        if field_slug:
            qs = qs.filter(field__slug=field_slug)
        qs = qs.order_by("-submitted_at")[:50]
        return Response([_serialize_run(r) for r in qs])

    def retrieve(self, request, run_id=None):
        try:
            run = AnalysisRun.objects.select_related("field").get(run_id=run_id)
        except AnalysisRun.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Analysis not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        self._check_access(request, run)
        return Response(_serialize_run(run))

    def _check_access(self, request, run):
        roles = user_roles(request.user)
        if "officer" in roles or "researcher" in roles or "farmer" in roles:
            if "farmer" in roles and run.field.farmer_id != request.user.pk and \
               "officer" not in roles and "researcher" not in roles:
                return False
        return True

    @action(detail=True, methods=["get"])
    def evidence(self, request, run_id=None):
        try:
            run = AnalysisRun.objects.get(run_id=run_id)
        except AnalysisRun.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Analysis not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        self._check_access(request, run)
        snap = run.snapshot
        return Response({
            "evidence": run.evidence,
            "warnings": run.warnings,
            "missingData": run.evidence.get("missing_data", []),
            "ruleVersion": run.rule_version,
            "snapshot": {
                "powerAssetId": snap.power_asset_id if snap else "",
                "powerContentHash": snap.power_content_hash if snap else "",
                "hlsAssetId": snap.hls_asset_id if snap else "",
                "catalogueVersion": snap.catalogue_version if snap else "",
                "ruleVersion": snap.rule_version if snap else "",
                "soilTestId": snap.soil_test_id if snap else "",
            },
        })

    @action(detail=True, methods=["post"])
    def cancel(self, request, run_id=None):
        try:
            run = AnalysisRun.objects.get(run_id=run_id)
        except AnalysisRun.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Analysis not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        self._check_access(request, run)
        if run.status in ("queued", "running"):
            run.status = "cancelled"
            run.save(update_fields=["status"])
            record("analysis.cancel", request.user, target_type="analysis", target_id=run.run_id,
                   ip=_ip(request))
        return Response(_serialize_run(run))


class SubmitAnalysisView(APIView):
    """POST /fields/{field_slug}/analyses → 202 + run (idempotent)."""

    permission_classes = [CanSubmitAnalysis]

    def post(self, request, field_slug: str):
        try:
            field = Field.objects.get(slug=field_slug)
        except Field.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Permission: farmer owns the field, or officer/researcher.
        roles = user_roles(request.user)
        if "farmer" in roles and "officer" not in roles and "researcher" not in roles:
            if field.farmer_id != request.user.pk:
                return Response(
                    {"error": {"code": "forbidden", "message": "You can only analyse your own fields.",
                               "details": {"field": field_slug}}},
                    status=status.HTTP_403_FORBIDDEN,
                )

        ser = AnalysisRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        req = ser.validated_data
        idempotency_key = (request.data.get("idempotencyKey")
                           or request.headers.get("Idempotency-Key")
                           or None)

        # Idempotency: return the existing run if this key was already used.
        if idempotency_key:
            existing = AnalysisRun.objects.filter(idempotency_key=idempotency_key).first()
            if existing is not None:
                return Response(_serialize_run(existing), status=status.HTTP_202_ACCEPTED)

        with transaction.atomic():
            run = AnalysisRun.objects.create(
                field=field,
                submitted_by=request.user,
                idempotency_key=idempotency_key,
                status="queued",
                request={
                    "season": req.get("season", "boro"),
                    "weights": req.get("weights", {}),
                    "exclusions": req.get("exclusions", []),
                    "equipment": req.get("equipment", []),
                },
            )
        record("analysis.submit", request.user, target_type="analysis", target_id=str(run.pk),
               detail={"field": field_slug, "idempotency_key": idempotency_key}, ip=_ip(request))

        # Kick off the (eager) task.
        execute_analysis_run.delay(run.pk)

        # Re-read after the eager task completes so the client gets the result.
        run.refresh_from_db()
        return Response(_serialize_run(run), status=status.HTTP_202_ACCEPTED)


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
