"""
Analysis serializers shaped to the frontend ``types.ts`` contract (camelCase).

``AnalysisRunSerializer`` emits the run with its plans/warnings/evidence, and
``AnalysisRequestSerializer`` validates the farmer's submit payload (season,
weights, exclusions, equipment).
"""

from rest_framework import serializers


class WeightsSerializer(serializers.Serializer):
    waterEfficiency = serializers.FloatField(min_value=0, max_value=1, required=False, default=0.25)
    heatResilience = serializers.FloatField(min_value=0, max_value=1, required=False, default=0.15)
    canopyCover = serializers.FloatField(min_value=0, max_value=1, required=False, default=0.15)
    diversity = serializers.FloatField(min_value=0, max_value=1, required=False, default=0.15)
    netMargin = serializers.FloatField(min_value=0, max_value=1, required=False, default=0.30)


class AnalysisRequestSerializer(serializers.Serializer):
    season = serializers.ChoiceField(
        choices=["boro", "aman", "rabi", "autumn", "spring"], required=False, default="boro"
    )
    weights = WeightsSerializer(required=False)
    exclusions = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    equipment = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def to_internal_value(self, data):
        data = dict(data or {})
        # Accept camelCase weight keys from the UI.
        if isinstance(data.get("weights"), dict):
            w = data["weights"]
            data["weights"] = {
                "water_efficiency": w.get("waterEfficiency", w.get("water_efficiency", 0.25)),
                "heat_resilience": w.get("heatResilience", w.get("heat_resilience", 0.15)),
                "canopy_cover": w.get("canopyCover", w.get("canopy_cover", 0.15)),
                "diversity": w.get("diversity", 0.15),
                "net_margin": w.get("netMargin", w.get("net_margin", 0.30)),
            }
        return super().to_internal_value(data)


class AnalysisRunSerializer(serializers.Serializer):
    """Read model for a run (plans/warnings/evidence are stored as JSON)."""

    id = serializers.CharField()
    fieldId = serializers.CharField()
    status = serializers.CharField()
    progressPct = serializers.IntegerField()
    ruleVersion = serializers.CharField(allow_blank=True)
    idempotencyKey = serializers.CharField(allow_null=True)
    plans = serializers.ListField()
    warnings = serializers.ListField()
    evidence = serializers.DictField()
    missingData = serializers.ListField()
    submittedAt = serializers.DateTimeField()
    completedAt = serializers.DateTimeField(allow_null=True)
