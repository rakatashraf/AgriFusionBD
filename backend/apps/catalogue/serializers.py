from rest_framework import serializers

from .models import Crop, SoilTest


class CropSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="slug", read_only=True)
    nameBn = serializers.CharField(source="name_bn", read_only=True)
    isLegume = serializers.BooleanField(source="is_legume", read_only=True)
    waterDemandMm = serializers.IntegerField(source="water_demand_mm", read_only=True)
    kcCanopy = serializers.FloatField(source="kc_canopy", read_only=True)
    kcInitial = serializers.FloatField(source="kc_initial", read_only=True)
    kcLate = serializers.FloatField(source="kc_late", read_only=True)
    heatTolerance = serializers.CharField(source="heat_tolerance", read_only=True)
    droughtTolerance = serializers.CharField(source="drought_tolerance", read_only=True)
    priceRangeBdtPerKg = serializers.ListField(source="price_range_bdt_per_kg", read_only=True)
    costPerHaBdt = serializers.ListField(source="cost_per_ha_bdt", read_only=True)
    yieldRangeT = serializers.ListField(source="yield_range_t", read_only=True)
    seasonMonths = serializers.ListField(source="season_months", read_only=True)
    irrigationMax = serializers.CharField(source="irrigation_max", read_only=True)
    equipment = serializers.ListField(read_only=True)

    class Meta:
        model = Crop
        fields = [
            "id", "name", "nameBn", "family", "isLegume",
            "waterDemandMm", "kcCanopy", "kcInitial", "kcLate",
            "heatTolerance", "droughtTolerance",
            "priceRangeBdtPerKg", "costPerHaBdt", "yieldRangeT",
            "seasonMonths", "irrigationMax", "equipment",
        ]
        read_only_fields = fields


class SoilTestSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    fieldId = serializers.CharField(source="field.slug", read_only=True)
    testedOn = serializers.DateField(source="tested_on", read_only=True)
    organicMatterPct = serializers.FloatField(source="organic_matter_pct", read_only=True)
    ecDsm = serializers.FloatField(source="ec_dsm", read_only=True)
    nPct = serializers.FloatField(source="n_pct", read_only=True)
    pPct = serializers.FloatField(source="p_pct", read_only=True)
    kPct = serializers.FloatField(source="k_pct", read_only=True)

    class Meta:
        model = SoilTest
        fields = ["id", "fieldId", "testedOn", "ph", "organicMatterPct",
                  "ecDsm", "nPct", "pPct", "kPct", "lab", "notes"]

    def get_id(self, obj):
        return f"st-{obj.pk}"
