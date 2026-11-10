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


class FieldIndicatorSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    fieldId = serializers.CharField(source="field.slug", read_only=True)
    periodStart = serializers.DateTimeField(source="period_start", read_only=True)
    periodEnd = serializers.DateTimeField(source="period_end", read_only=True)
    coveragePct = serializers.FloatField(source="coverage_pct", read_only=True)
    isForecast = serializers.BooleanField(source="is_forecast", read_only=True)
    isInferred = serializers.BooleanField(source="is_inferred", read_only=True)

    class Meta:
        model = FieldIndicator
        fields = [
            "id", "fieldId", "kind", "provider", "product", "version",
            "periodStart", "periodEnd", "value", "unit", "coveragePct",
            "quality", "isForecast", "isInferred",
        ]

    def get_id(self, obj):
        return f"ind-{obj.pk}"
