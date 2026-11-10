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
    queryset = Field.objects.select_related("farm", "farmer", "crop").all()
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

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(farmer=request.user, farm=_farmer_farm(request.user))
        record("field.create", request.user, target_type="field", target_id=ser.data["id"],
               ip=_ip(request))
        return Response(ser.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        ser = self.get_serializer(instance, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        record("field.update", request.user, target_type="field", target_id=instance.slug,
               ip=_ip(request))
        return Response(ser.data)

    @action(detail=True, methods=["get"])
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
    from .models import Farm
    farm, _ = Farm.objects.get_or_create(owner=user, name=f"{user.name}'s farm")
    return farm


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
