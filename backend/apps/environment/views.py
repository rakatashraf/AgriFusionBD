"""
Environment endpoints (plan §2):

    GET /fields/{id}/indicators
    GET /environmental/assets   (list of data assets for provenance)
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import field_visible_to
from apps.farms.models import Field

from .models import DataAsset, FieldIndicator
from .serializers import DataAssetSerializer, FieldIndicatorSerializer


class IndicatorsView(APIView):
    """GET /fields/{field_slug}/indicators — the series the UI charts.

    Object-level authorization (report §2, §11): a farmer may only read
    indicators for fields they own (or hold a grant on); 404 otherwise so
    other farmers' field slugs are not enumerated.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, field_slug: str):
        try:
            field = Field.objects.get(slug=field_slug)
        except Field.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                status=404,
            )
        if not field_visible_to(request.user, field):
            return Response(
                {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                status=404,
            )
        qs = FieldIndicator.objects.filter(field=field).order_by("kind", "period_start")
        return Response(FieldIndicatorSerializer(qs, many=True).data)


class AssetsView(APIView):
    """GET /environmental/assets — provenance list for evidence cards.

    Scoped to fields the caller may see (farmers: own fields; officers and
    researchers: the pilot set).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        qs = DataAsset.objects.select_related("product").order_by("-fetched_at")
        from apps.accounts.permissions import user_roles, ROLE_FARMER, ROLE_OFFICER, ROLE_RESEARCHER
        roles = user_roles(request.user)
        if ROLE_FARMER in roles and ROLE_OFFICER not in roles and ROLE_RESEARCHER not in roles:
            qs = qs.filter(
                Q(field__farmer=request.user) |
                Q(field__grants__user=request.user)
            ).distinct()
        return Response(DataAssetSerializer(qs, many=True).data)
