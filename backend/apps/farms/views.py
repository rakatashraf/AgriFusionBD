"""
Field endpoints (plan §2):

    GET/POST  /fields
    GET/PATCH /fields/{id}
    PATCH     /fields/{id}/profile
    GET       /fields/{id}/crop-history
"""

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import IsFarmer, user_roles, ROLE_FARMER, ROLE_OFFICER, ROLE_RESEARCHER
from apps.audit.services import record

from .models import CropHistory, Field
from .serializers import CropHistorySerializer, FieldSerializer


class FieldViewSet(ModelViewSet):
    serializer_class = FieldSerializer
    queryset = Field.objects.select_related("farm", "farmer").all()
    lookup_field = "slug"
    permission_classes = [IsFarmer]

    def get_queryset(self):
        user = self.request.user
        roles = user_roles(user)
        qs = Field.objects.select_related("farm", "farmer")
        if ROLE_FARMER in roles and ROLE_OFFICER not in roles and ROLE_RESEARCHER not in roles:
            qs = qs.filter(farmer=user)
        # Officers/researchers see all (pilot scope); grants refine in prod.
        return qs

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if "farmer" not in ctx:
            ctx["farmer"] = self.request.user
        if "farm" not in ctx:
            ctx["farm"] = _farmer_farm(self.request.user)
        return ctx

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        field_obj = ser.save()
        record("field.create", request.user, target_type="field", target_id=field_obj.slug,
               ip=_ip(request))
        return Response(self.get_serializer(field_obj).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        ser = self.get_serializer(instance, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        old_geom = instance.geometry
        old_name = instance.name
        field_obj = ser.save()
        # If the boundary changed, record a new version (plan §1).
        new_geom = field_obj.geometry
        if new_geom is not None and (old_geom is None or not new_geom.equals(old_geom)):
            from apps.farms.models import FieldBoundaryVersion
            from django.contrib.gis.geos import Point
            try:
                lat, lng = (new_geom.y, new_geom.x) if new_geom.geom_type.upper() == "POINT" else (
                    new_geom.centroid.y, new_geom.centroid.x)
            except Exception:
                lat = lng = None
            from math import cos, radians
            area_ha = None
            if not field_obj.is_pin_estimate and hasattr(new_geom, "area"):
                if lat:
                    deg_to_m = 111_320.0 * max(cos(radians(lat)), 0.2)
                    area_ha = (new_geom.area * deg_to_m * deg_to_m) / 10_000.0
            field_obj.lat, field_obj.lng = lat, lng
            field_obj.is_pin_estimate = (new_geom.geom_type.upper() == "POINT") if new_geom else False
            field_obj.area_ha = area_ha
            field_obj.save()
            next_v = (FieldBoundaryVersion.objects.filter(field=field_obj).count() + 1)
            FieldBoundaryVersion.objects.create(
                field=field_obj, version=next_v, geometry=new_geom,
                area_ha=area_ha, recorded_by=request.user,
            )
        record("field.update", request.user, target_type="field", target_id=field_obj.slug,
               ip=_ip(request))
        return Response(self.get_serializer(field_obj).data)

    @action(detail=True, methods=["get"], url_path="soil-tests")
    def soil_tests(self, request, slug=None):
        """GET /fields/{slug}/soil-tests — the lab/field soil tests for this field.

        Object-level authorization: farmers see only their own field's tests
        (404 otherwise); officers and researchers see all (report §2, §11).
        """
        from apps.accounts.permissions import field_visible_to
        from apps.catalogue.models import SoilTest
        from apps.catalogue.serializers import SoilTestSerializer

        field = self.get_object()
        if not field_visible_to(request.user, field):
            return Response(
                {"error": {"code": "not_found", "message": "Field not found.", "details": None}},
                status=status.HTTP_404_NOT_FOUND,
            )
        qs = SoilTest.objects.filter(field=field).order_by("-tested_on")
        return Response(SoilTestSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="crop-history")
    def crop_history(self, request, slug=None):
        field = self.get_object()
        qs = CropHistory.objects.filter(field=field).select_related("crop")
        return Response(CropHistorySerializer(qs, many=True).data)

    @action(detail=True, methods=["patch"])
    def profile(self, request, slug=None):
        field = self.get_object()
        allowed = {"soil_type", "irrigation", "slope_pct", "drainage"}
        for key in allowed:
            if key in request.data:
                setattr(field, key, request.data[key])
        field.save(update_fields=[*allowed, "updated_at"])
        record("field.profile", request.user, target_type="field", target_id=field.slug,
               ip=_ip(request))
        return Response(FieldSerializer(field).data)


def _farmer_farm(user):
    """Return the user's single Farm, creating it on first use.

    Defensive: an anonymous user (or one without a name) must never crash the
    serializer context or spawn a Farm owned by AnonymousUser. ``IsFarmer``
    gates the viewset, but this is the last line of defence.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    from .models import Farm
    owner_name = getattr(user, "name", None) or getattr(user, "email", "") or "Farmer"
    farm, _ = Farm.objects.get_or_create(owner=user, name=f"{owner_name}'s farm")
    return farm


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
