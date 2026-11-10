"""
Serializers shaped to the frontend ``types.ts`` contract (camelCase keys).

``FieldSerializer`` emits ``geometry`` as a GeoJSON object so the MapLibre
client can consume it directly.
"""

from rest_framework import serializers

from apps.catalogue.serializers import CropSerializer

from .models import CropHistory, Farm, Field


class _GeoMixin:
    def _geometry(self, f: Field):
        if f.geometry is None:
            return None
        # GeoDjango returns an OGRGeometry; .geojson gives a Feature dict.
        try:
            return f.geometry.geojson
        except Exception:
            return None


class FieldSerializer(serializers.ModelSerializer, _GeoMixin):
    id = serializers.CharField(source="slug", read_only=True)
    name = serializers.CharField()
    isPinEstimate = serializers.BooleanField(source="is_pin_estimate", read_only=True)
    pinRadiusM = serializers.IntegerField(source="pin_radius_m", read_only=True)
    areaHa = serializers.DecimalField(max_digits=10, decimal_places=4, source="area_ha", read_only=True)
    soilType = serializers.CharField(source="soil_type", read_only=True)
    irrigation = serializers.CharField(read_only=True)
    geometry = serializers.SerializerMethodField()
    farmerName = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Field
        fields = [
            "id", "name", "isPinEstimate", "pinRadiusM", "areaHa",
            "soilType", "irrigation", "geometry", "lat", "lng",
            "status", "version", "farmerName", "createdAt", "updatedAt",
        ]
        read_only_fields = fields

    def get_geometry(self, obj):
        return self._geometry(obj)

    def get_farmerName(self, obj):
        return obj.farmer.name


class CropHistorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    fieldId = serializers.CharField(source="field.slug", read_only=True)
    cropId = serializers.CharField(source="crop.slug", read_only=True)
    cropName = serializers.CharField(source="crop.name", read_only=True)
    cropFamily = serializers.CharField(source="crop.family", read_only=True)
    areaHa = serializers.DecimalField(max_digits=10, decimal_places=4, source="area_ha", read_only=True)
    yieldT = serializers.DecimalField(max_digits=10, decimal_places=3, source="yield_t", read_only=True)
    plantedOn = serializers.DateField(source="planted_on", read_only=True)
    harvestedOn = serializers.DateField(source="harvested_on", read_only=True)

    class Meta:
        model = CropHistory
        fields = [
            "id", "fieldId", "cropId", "cropName", "cropFamily",
            "season", "year", "areaHa", "yieldT", "plantedOn", "harvestedOn",
            "notes",
        ]

    def get_id(self, obj):
        return f"ch-{obj.pk}"


class FarmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farm
        fields = ["id", "name", "region", "owner"]
        read_only_fields = fields
