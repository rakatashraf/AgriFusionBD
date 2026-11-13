from rest_framework import serializers

from .models import DataAsset, DatasetProduct, FieldIndicator


class DataAssetSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk", read_only=True)
    status = serializers.CharField(read_only=True)
    acquiredAt = serializers.DateTimeField(source="acquired_at", read_only=True)
    fetchedAt = serializers.DateTimeField(source="fetched_at", read_only=True)
    expiresAt = serializers.DateTimeField(source="expires_at", read_only=True)
    contentHash = serializers.CharField(source="content_hash", read_only=True)
    product = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = DataAsset
        fields = ["id", "status", "acquiredAt", "fetchedAt", "expiresAt", "contentHash", "product"]


_KIND_TO_METRIC = {
    "rainfall": "rainfall_mm",
    "temperature": "temp_mean_c",
    "temperature_max": "temp_max_c",
    "temperature_min": "temp_min_c",
    "relative_humidity": "relative_humidity_pct",
    "wind_speed": "wind_speed_ms",
    "shortwave_radiation": "shortwave_radiation_mj",
}


class FieldIndicatorSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    fieldId = serializers.CharField(source="field.slug", read_only=True)
    periodStart = serializers.DateTimeField(source="period_start", read_only=True)
    periodEnd = serializers.DateTimeField(source="period_end", read_only=True)
    coveragePct = serializers.FloatField(source="coverage_pct", read_only=True)
    isForecast = serializers.BooleanField(source="is_forecast", read_only=True)
    isInferred = serializers.BooleanField(source="is_inferred", read_only=True)
    metric = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    quality = serializers.SerializerMethodField()

    class Meta:
        model = FieldIndicator
        fields = [
            "id", "fieldId", "kind", "metric", "date",
            "provider", "product", "version",
            "periodStart", "periodEnd", "value", "unit", "coveragePct",
            "quality", "isForecast", "isInferred",
        ]

    def get_id(self, obj):
        return f"ind-{obj.pk}"

    def get_metric(self, obj):
        return _KIND_TO_METRIC.get(obj.kind, obj.kind)

    def get_date(self, obj):
        return obj.period_start.strftime("%Y-%m-%d")

    def get_quality(self, obj):
        # Map the DB "valid" → frontend "ok"
        q = obj.quality
        return "ok" if q == "valid" else q
