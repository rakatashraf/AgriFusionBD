"""
Rover endpoints (plan §2, §5):

    GET  /devices                      — fleet scoped to user's role
    GET  /observations?field=          — readings for a field (grant-enforced)
    POST /devices/{id}/observations   — operator upload (dedupe by message_id)
    GET  /runs                         — survey runs (new)
    GET  /runs/{run_id}/samples       — samples for a run (new)
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import user_roles, field_visible_to
from apps.audit.services import record
from apps.farms.models import Field

from .models import Device, Observation, SurveyRun, RoverSample
from .serializers import serialize_device, serialize_observation


class DeviceListView(APIView):
    """GET /devices — fleet scoped to the caller's role.

    Farmers see devices with an active grant on their fields.
    Officers / researchers see the full pilot fleet.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        from apps.accounts.permissions import ROLE_FARMER, ROLE_OFFICER, ROLE_RESEARCHER

        roles = user_roles(request.user)
        qs = Device.objects.select_related("operator").prefetch_related("grants__field")

        if ROLE_FARMER in roles and ROLE_OFFICER not in roles and ROLE_RESEARCHER not in roles:
            # Farmer: only devices granted on their fields
            qs = qs.filter(
                Q(grants__field__farmer=request.user) |
                Q(operator=request.user)
            ).distinct()

        return Response([serialize_device(d) for d in qs])


class ObservationListView(APIView):
    """GET /observations?field= — local rover readings for a field.

    Object-level authorization: farmers can only read observations for
    fields they own (report §2, §11). 404 for other farmers' fields.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.permissions import ROLE_FARMER, ROLE_OFFICER, ROLE_RESEARCHER

        qs = Observation.objects.select_related("field", "device")
        field_slug = request.query_params.get("field")

        if field_slug:
            try:
                field = Field.objects.get(slug=field_slug)
            except Field.DoesNotExist:
                return Response(
                    {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not field_visible_to(request.user, field):
                return Response(
                    {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                    status=status.HTTP_404_NOT_FOUND,
                )
            qs = qs.filter(field=field)
        else:
            # No field filter: scope by role
            roles = user_roles(request.user)
            if ROLE_FARMER in roles and ROLE_OFFICER not in roles and ROLE_RESEARCHER not in roles:
                qs = qs.filter(field__farmer=request.user)

        qs = qs.order_by("-taken_at")[:100]
        return Response([serialize_observation(o) for o in qs])


class SurveyRunListView(APIView):
    """GET /runs — survey runs visible to the caller."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.permissions import ROLE_FARMER, ROLE_OFFICER, ROLE_RESEARCHER

        roles = user_roles(request.user)
        qs = SurveyRun.objects.select_related("device", "field")

        if ROLE_FARMER in roles and ROLE_OFFICER not in roles and ROLE_RESEARCHER not in roles:
            qs = qs.filter(field__farmer=request.user)

        qs = qs.order_by("-created_at")[:50]
        return Response([
            {
                "id": r.run_id,
                "deviceId": f"rv-{r.device.pk}",
                "deviceName": r.device.name,
                "fieldId": r.field.slug,
                "fieldSlug": r.field.slug,
                "status": r.status,
                "lastState": r.last_state,
                "samplesCount": r.samples_count,
                "startedAt": r.started_at,
                "completedAt": r.completed_at,
            }
            for r in qs
        ])


class SurveyRunSamplesView(APIView):
    """GET /runs/{run_id}/samples — samples for a specific run."""

    permission_classes = [IsAuthenticated]

    def get(self, request, run_id: str):
        try:
            run = SurveyRun.objects.select_related("device", "field").get(run_id=run_id)
        except SurveyRun.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Run not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not field_visible_to(request.user, run.field):
            return Response(
                {"error": {"code": "not_found", "message": "Run not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        samples = run.samples.order_by("sample_id")
        return Response({
            "runId": run_id,
            "status": run.status,
            "samples": [
                {
                    "sampleId": s.sample_id,
                    "timestamp": s.timestamp,
                    "lane": s.lane,
                    "lat": s.lat,
                    "lon": s.lon,
                    "gpsFix": s.gps_fix,
                    "gpsHdop": s.gps_hdop,
                    "probeOk": s.probe_ok,
                    "probeDepthMm": s.probe_depth_mm,
                    "moistureVwc": s.moisture_vwc,
                    "soilTempC": s.soil_temp_c,
                    "airTempC": s.air_temp_c,
                    "airHumidityPct": s.air_humidity_pct,
                    "batterySocPct": s.battery_soc_pct,
                    "image": s.image,
                }
                for s in samples
            ],
        })


class ObservationUploadView(APIView):
    """
    POST /devices/{id}/observations — a device (or operator) uploads a reading.

    Dedupe on ``message_id``: a repeated upload with the same message_id is a
    no-op returning 200 with the existing observation (plan §2).

    Grant enforcement (P1 §5.5): the device must hold an active grant on
    the target field, and the caller must be the operator or an officer.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone
        from .models import DeviceGrant

        try:
            device = Device.objects.get(pk=pk)
        except Device.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Device not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Only the device's operator (or officer) may upload.
        roles = user_roles(request.user)
        if device.operator_id != request.user.pk and "officer" not in roles:
            return Response(
                {"error": {"code": "forbidden", "message": "Not authorized for this device.", "details": None}},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data
        field_slug = data.get("fieldId") or data.get("field_slug")
        try:
            field = Field.objects.get(slug=field_slug)
        except Field.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Grant enforcement: device must have an active (non-expired) grant
        if not DeviceGrant.objects.filter(device=device, field=field).filter(
            expires_at__isnull=True
        ).exists() and not DeviceGrant.objects.filter(
            device=device, field=field, expires_at__gt=timezone.now()
        ).exists():
            return Response(
                {"error": {"code": "forbidden",
                           "message": "Device has no active grant for this field.",
                           "details": {"device": pk, "field": field_slug}}},
                status=status.HTTP_403_FORBIDDEN,
            )

        message_id = data.get("message_id") or data.get("messageId")
        if message_id:
            existing = Observation.objects.filter(message_id=message_id).first()
            if existing is not None:
                return Response(serialize_observation(existing), status=status.HTTP_200_OK)

        # Parse value safely
        try:
            value = float(data.get("value", 0.0))
        except (ValueError, TypeError):
            return Response(
                {"error": {"code": "bad_request",
                           "message": "value must be a number.",
                           "details": {"value": data.get("value")}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Preserve the device's measurement timestamp when provided
        taken_at = None
        raw_ts = data.get("taken_at") or data.get("takenAt")
        if raw_ts:
            try:
                from datetime import datetime
                taken_at = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        if taken_at is None:
            taken_at = timezone.now()

        o = Observation.objects.create(
            device=device,
            field=field,
            sensor=data.get("sensor", "moisture"),
            value=value,
            unit=data.get("unit", "%"),
            taken_at=taken_at,
            message_id=message_id,
            quality=data.get("quality", "valid"),
            calibrated=bool(data.get("calibrated", False)),
            depth_cm=data.get("depth_cm") or data.get("depthCm"),
        )
        record("observation.upload", request.user, target_type="observation", target_id=str(o.pk),
               ip=_ip(request))
        return Response(serialize_observation(o), status=status.HTTP_201_CREATED)


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
