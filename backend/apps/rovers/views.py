"""
Rover endpoints (plan §2):

    GET  /devices
    GET  /observations?field=
    POST /devices/{id}/observations   (device upload, dedupe by message_id)
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import user_roles
from apps.audit.services import record
from apps.farms.models import Field

from .models import Device, Observation
from .serializers import serialize_device, serialize_observation


class DeviceListView(APIView):
    """GET /devices — the fleet visible to the user's role."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Device.objects.select_related("operator").prefetch_related("grants__field")
        return Response([serialize_device(d) for d in qs])


class ObservationListView(APIView):
    """GET /observations?field= — local rover readings for a field."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Observation.objects.select_related("field", "device")
        field_slug = request.query_params.get("field")
        if field_slug:
            qs = qs.filter(field__slug=field_slug)
        qs = qs.order_by("-taken_at")[:100]
        return Response([serialize_observation(o) for o in qs])


class ObservationUploadView(APIView):
    """
    POST /devices/{id}/observations — a device (or operator) uploads a reading.

    Dedupe on ``message_id``: a repeated upload with the same message_id is a
    no-op returning 200 with the existing observation (plan §2).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
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
        field_slug = data.get("fieldId")
        try:
            field = Field.objects.get(slug=field_slug)
        except Field.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        message_id = data.get("message_id") or data.get("messageId")
        if message_id:
            existing = Observation.objects.filter(message_id=message_id).first()
            if existing is not None:
                return Response(serialize_observation(existing), status=status.HTTP_200_OK)

        from django.utils import timezone
        o = Observation.objects.create(
            device=device,
            field=field,
            sensor=data.get("sensor", "moisture"),
            value=float(data.get("value", 0.0)),
            unit=data.get("unit", "%"),
            taken_at=timezone.now(),
            message_id=message_id,
            quality=data.get("quality", "valid"),
            calibrated=bool(data.get("calibrated", False)),
            depth_cm=data.get("depth_cm"),
        )
        record("observation.upload", request.user, target_type="observation", target_id=str(o.pk),
               ip=_ip(request))
        return Response(serialize_observation(o), status=status.HTTP_201_CREATED)


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
