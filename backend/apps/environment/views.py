"""
Environment endpoints (plan §2):

    GET /fields/{id}/indicators
    GET /environmental/assets   (list of data assets for provenance)
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.farms.models import Field

from .models import DataAsset, FieldIndicator
from .serializers import DataAssetSerializer, FieldIndicatorSerializer


class IndicatorsView(APIView):
    """GET /fields/{field_slug}/indicators — the series the UI charts."""

    permission_classes = [IsAuthenticated]

    def get(self, request, field_slug: str):
        try:
            field = Field.objects.get(slug=field_slug)
        except Field.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                status=404,
            )
        qs = FieldIndicator.objects.filter(field=field).order_by("kind", "period_start")
        return Response(FieldIndicatorSerializer(qs, many=True).data)


class AssetsView(APIView):
    """GET /environmental/assets — provenance list for evidence cards."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DataAsset.objects.select_related("product").order_by("-fetched_at")
        return Response(DataAssetSerializer(qs, many=True).data)
