from rest_framework import serializers

from .models import Device, Observation


class DeviceSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    batteryPct = serializers.IntegerField()
    lastSeen = serializers.DateTimeField(allow_null=True)
    fields = serializers.ListField()


def serialize_device(d: Device) -> dict:
    grants = d.grants.select_related("field")
    return {
        "id": f"rv-{d.pk}",
        "name": d.name,
        "status": d.status,
        "batteryPct": d.battery_pct,
        "lastSeen": d.last_seen,
        "fields": [
            {"slug": g.field.slug, "name": g.field.name}
            for g in d.grants.all().select_related("field")
        ],
    }


class ObservationSerializer(serializers.Serializer):
    id = serializers.CharField()
    fieldId = serializers.CharField()
    sensor = serializers.CharField()
    value = serializers.FloatField()
    unit = serializers.CharField()
    takenAt = serializers.DateTimeField()
    quality = serializers.CharField()
    calibrated = serializers.BooleanField()
    depthCm = serializers.FloatField(allow_null=True)


def serialize_observation(o: Observation) -> dict:
    return {
        "id": f"obs-{o.pk}",
        "fieldId": o.field.slug,
        "sensor": o.sensor,
        "value": o.value,
        "unit": o.unit,
        "takenAt": o.taken_at,
        "quality": o.quality,
        "calibrated": o.calibrated,
        "depthCm": o.depth_cm,
    }
