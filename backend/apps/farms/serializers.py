"""
Serializers shaped to the frontend ``types.ts`` contract (camelCase keys).

``FieldSerializer`` emits ``geometry`` as a GeoJSON object so the MapLibre
client can consume it directly.
"""

import json

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


class GeometryField(serializers.Field):
    """GeoJSON geometry in (Polygon or Point) / out.

    Accepts either a GeoJSON object or an OGC WKT string; returns the
    GeoJSON object the MapLibre client consumes.
    """

    def to_internal_value(self, data):
        from django.contrib.gis.geos import GEOSGeometry
        if isinstance(data, str):
            return GEOSGeometry(data, srid=4326)
        if isinstance(data, dict) and data.get("type"):
            return GEOSGeometry(json.dumps(data), srid=4326)
        raise serializers.ValidationError("geometry must be a GeoJSON object or WKT string.")

    def to_representation(self, value):
        if value is None:
            return None
        try:
            # ``GEOSGeometry.geojson`` is a JSON *string*; the frontend expects
            # a GeoJSON geometry object, so parse it before returning.
            return json.loads(value.geojson)
        except Exception:
            return None


class FieldSerializer(serializers.ModelSerializer, _GeoMixin):
    id = serializers.CharField(source="slug", read_only=True)
    name = serializers.CharField(max_length=160, required=True)
    geometry = GeometryField(required=False, allow_null=True)
    isPinEstimate = serializers.BooleanField(source="is_pin_estimate", read_only=True)
    pinRadiusM = serializers.IntegerField(source="pin_radius_m", read_only=True)
    areaHa = serializers.FloatField(source="area_ha", read_only=True)
    soilType = serializers.CharField(source="soil_type", required=False, allow_blank=True, default="")
    irrigation = serializers.CharField(required=False, allow_blank=True, default="")
    priorities = serializers.ListField(child=serializers.CharField(), required=False)
    currentCycleCrops = serializers.ListField(
        child=serializers.CharField(), source="current_cycle_crops", required=False
    )
    recentCycleCrops = serializers.ListField(
        child=serializers.CharField(), source="recent_cycle_crops", required=False
    )
    farmerName = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Field
        fields = [
            "id", "name", "isPinEstimate", "pinRadiusM", "areaHa",
            "soilType", "irrigation", "priorities", "currentCycleCrops",
            "recentCycleCrops", "geometry", "lat", "lng",
            "status", "version", "farmerName", "createdAt", "updatedAt",
        ]

    def get_farmerName(self, obj):
        return obj.farmer.name

    def validate_geometry(self, value):
        if value is None:
            return None
        geom_type = value.geom_type.upper()
        if geom_type in ("POLYGON", "MULTIPOLYGON"):
            return value
        if geom_type == "POINT":
            # Pin estimate: store the point; the view sets is_pin_estimate.
            return value
        raise serializers.ValidationError("geometry must be a Polygon, MultiPolygon or Point.")

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("name is required.")
        return value.strip()

    def create(self, validated_data):
        from django.contrib.gis.geos import Point, Polygon
        from django.utils.text import slugify
        from django.utils import timezone

        name = validated_data.pop("name")
        geom = validated_data.pop("geometry", None)
        farmer = self.context["farmer"]

        slug = slugify(name)[:180] or f"field-{timezone.now():%Y%m%d%H%M%S}"
        # Keep the slug unique per farmer (unique_together), with a numeric
        # suffix on collision.
        from apps.farms.models import Field as _Field
        base = slug
        n = 1
        while _Field.objects.filter(farmer=farmer, slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1

        is_pin = bool(geom and geom.geom_type.upper() == "POINT")
        area_ha = None
        lat = lng = None
        if geom is not None:
            try:
                lat, lng = (geom.y, geom.x) if geom.geom_type.upper() == "POINT" else (
                    geom.centroid.y, geom.centroid.x)
            except Exception:
                lat = lng = None
            if not is_pin and hasattr(geom, "area"):
                # SRID 4326 area is in steradians — approximate via GEOS geodetic
                # length is unavailable here; use the plan's declared approach:
                # a rough equatorial-km conversion is wrong at BD latitudes, so
                # we compute the area on the geodesic via shapely-free fallback:
                # use GEOS's own (planar) area scaled by the local degree length.
                from math import cos, radians
                if lat:
                    deg_to_m = 111_320.0 * max(cos(radians(lat)), 0.2)
                    area_ha = (geom.area * deg_to_m * deg_to_m) / 10_000.0
                else:
                    area_ha = 0.0

        field_obj = _Field(
            farmer=farmer,
            farm=self.context["farm"],
            name=name,
            slug=slug,
            geometry=geom,
            is_pin_estimate=is_pin,
            pin_radius_m=25 if is_pin else 25,
            area_ha=area_ha,
            lat=lat,
            lng=lng,
            soil_type=validated_data.pop("soil_type", "") or "",
            irrigation=validated_data.pop("irrigation", "") or "canal",
            priorities=validated_data.pop("priorities", []) or [],
            current_cycle_crops=validated_data.pop("current_cycle_crops", []) or [],
            recent_cycle_crops=validated_data.pop("recent_cycle_crops", []) or [],
            status="active",
            version=1,
        )
        field_obj.save()

        # Write a boundary version (plan §1: versioned boundary).
        if geom is not None:
            from apps.farms.models import FieldBoundaryVersion
            FieldBoundaryVersion.objects.create(
                field=field_obj, version=1, geometry=geom,
                area_ha=area_ha, recorded_by=farmer,
            )
        return field_obj


class CropHistorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    fieldId = serializers.CharField(source="field.slug", read_only=True)
    cropId = serializers.CharField(source="crop.slug", read_only=True)
    cropName = serializers.CharField(source="crop.name", read_only=True)
    cropFamily = serializers.CharField(source="crop.family", read_only=True)
    areaHa = serializers.FloatField(source="area_ha", read_only=True)
    yieldT = serializers.FloatField(source="yield_t", read_only=True)
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
