"""
seed_real_data — populate the empty pages with realistic demo data.

Extends seed_demo with:
  - DataAsset + FieldIndicator rows (rainfall, temperature, NDVI per field)
  - A completed AnalysisRun with scenarios, plans, metrics
  - An AssistanceCase with messages and an officer review
  - A ResearchExportJob (complete, with provenance)

Idempotent: uses get_or_create / update_or_create throughout.
"""

import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analyses.models import AnalysisRun, InputSnapshot, Metric, RotationPlan, Scenario
from apps.catalogue.models import Crop
from apps.cases.models import AssistanceCase, CaseMessage, CaseReview
from apps.environment.models import DataAsset, DatasetProduct, FieldIndicator
from apps.farms.models import Field
from apps.research.models import ExportJob

User = None


class Command(BaseCommand):
    help = "Populate indicators, analyses, cases and export jobs with demo data."

    def handle(self, *args, **options):
        global User
        User = get_user_model()
        random.seed(2026)

        self._seed_indicators()
        self._seed_analysis()
        self._seed_case()
        self._seed_export()

        self.stdout.write(self.style.SUCCESS(
            "Real data seeded: indicators, 1 analysis, 1 case, 1 export."
        ))

    # ------------------------------------------------------------------
    # Field indicators (rainfall, temperature, NDVI) per field
    # ------------------------------------------------------------------
    def _seed_indicators(self):
        power = DatasetProduct.objects.get_or_create(
            slug="power-daily",
            defaults={"name": "NASA POWER Daily", "provider": "NASA POWER",
                      "product_id": "POWER", "resolution": "0.5 deg", "cadence": "daily"},
        )[0]
        hls = DatasetProduct.objects.get_or_create(
            slug="hls-l30-ndvi",
            defaults={"name": "USGS HLS NDVI (L30/S30)", "provider": "USGS HLS",
                      "product_id": "HLSL30.VI", "resolution": "30 m", "cadence": "16-day"},
        )[0]

        fields = Field.objects.all()
        now = timezone.now()

        for field in fields:
            # Clear existing indicators for this field so re-seed is clean
            FieldIndicator.objects.filter(field=field).delete()
            DataAsset.objects.filter(field=field).delete()

            # --- POWER asset (rainfall + temperature series) ---
            cache_key = f"power:{field.slug}:2026-01-01:2026-11-09"
            content_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:64]
            asset, _ = DataAsset.objects.update_or_create(
                cache_key=cache_key,
                defaults={
                    "product": power,
                    "field": field,
                    "content_hash": content_hash,
                    "status": "cached",
                    "acquired_at": now - timedelta(days=7),
                    "expires_at": now + timedelta(days=7),
                    "payload": {"source": "NASA POWER", "cell": "0.5°"},
                    "metadata": {"provider": "NASA POWER", "product": "POWER"},
                },
            )

            # --- HLS asset (NDVI series) ---
            hls_key = f"hls:{field.slug}:2026-01-01:2026-11-09"
            hls_hash = hashlib.sha256(hls_key.encode()).hexdigest()[:64]
            hls_asset, _ = DataAsset.objects.update_or_create(
                cache_key=hls_key,
                defaults={
                    "product": hls,
                    "field": field,
                    "content_hash": hls_hash,
                    "status": "cached",
                    "acquired_at": now - timedelta(days=14),
                    "expires_at": now + timedelta(days=14),
                    "payload": {"source": "USGS HLS", "scene": "HLSL30"},
                    "metadata": {"provider": "USGS HLS", "product": "HLSL30.VI"},
                },
            )

            # --- Generate ~20 weekly data points for each indicator kind ---
            start = now - timedelta(days=140)
            for week in range(20):
                period_start = start + timedelta(weeks=week)
                period_end = period_start + timedelta(days=7)

                # Seasonal rainfall: peaks in monsoon (Jun–Aug), low in dry (Dec–Feb)
                month = (period_start.month - 1) % 12
                monsoon_boost = [0.3, 0.5, 0.8, 1.2, 1.5, 2.0, 2.5, 2.8, 2.2, 1.4, 0.6, 0.2][month]
                base_rain = 20 + 60 * monsoon_boost
                rain_val = max(0, base_rain + random.gauss(0, 15))
                rain_cov = random.choice([100.0, 100.0, 100.0, 85.0, 72.0])
                rain_q = "valid" if rain_cov >= 80 else "partial"

                FieldIndicator.objects.create(
                    field=field, kind="rainfall", asset=asset,
                    provider="NASA POWER", product="POWER", version="v7",
                    period_start=period_start, period_end=period_end,
                    value=round(rain_val, 1), unit="mm",
                    coverage_pct=rain_cov, quality=rain_q,
                    is_forecast=False, is_inferred=False,
                )

                # Temperature: warm in Apr–May, cooler in Dec–Jan
                temp_base = 24 + 6 * [0.5, 0.8, 1.2, 1.8, 2.2, 2.5, 2.3, 2.1, 1.8, 1.2, 0.7, 0.3][month]
                temp_val = temp_base + random.gauss(0, 1.5)
                temp_cov = random.choice([100.0, 100.0, 100.0, 90.0])
                temp_q = "valid" if temp_cov >= 80 else "partial"

                FieldIndicator.objects.create(
                    field=field, kind="temperature", asset=asset,
                    provider="NASA POWER", product="POWER", version="v7",
                    period_start=period_start, period_end=period_end,
                    value=round(temp_val, 1), unit="°C",
                    coverage_pct=temp_cov, quality=temp_q,
                    is_forecast=False, is_inferred=False,
                )

                # NDVI: peaks in green season (Apr–Jun), low in dry (Dec–Feb)
                ndvi_base = 0.3 + 0.4 * [0.2, 0.4, 0.7, 0.9, 1.0, 1.0, 0.8, 0.7, 0.6, 0.4, 0.2, 0.1][month]
                ndvi_val = max(0.05, min(0.95, ndvi_base + random.gauss(0, 0.08)))
                ndvi_cov = random.choice([100.0, 95.0, 88.0, 72.0, 45.0])
                ndvi_q = "valid" if ndvi_cov >= 80 else "partial"
                ndvi_inferred = ndvi_cov < 40

                FieldIndicator.objects.create(
                    field=field, kind="ndvi", asset=hls_asset,
                    provider="USGS HLS", product="HLSL30.VI", version="v2",
                    period_start=period_start, period_end=period_end,
                    value=round(ndvi_val, 3), unit="fraction",
                    coverage_pct=ndvi_cov, quality=ndvi_q,
                    is_forecast=False, is_inferred=ndvi_inferred,
                )

    # ------------------------------------------------------------------
    # A completed AnalysisRun with realistic scenarios + metrics
    # ------------------------------------------------------------------
    def _seed_analysis(self):
        farmer = User.objects.get(email="farmer@pilot.example")
        field = Field.objects.get(slug="north-paddy-plot")

        # Idempotency: reuse existing run if one exists for this field
        existing = AnalysisRun.objects.filter(field=field, status="complete").first()
        if existing:
            return

        run_id = f"an-{uuid.uuid4().int % 1000000:06d}"
        now = timezone.now()

        run = AnalysisRun.objects.create(
            run_id=run_id,
            field=field,
            submitted_by=farmer,
            idempotency_key=f"seed-{uuid.uuid4().hex[:16]}",
            status="complete",
            progress_pct=100,
            rule_version="v2026.11.0",
            request={
                "season": "boro",
                "seasonStart": "2026-12-01",
                "seasonEnd": "2027-11-30",
                "weights": {
                    "waterEfficiency": 0.25,
                    "heatResilience": 0.15,
                    "soilCover": 0.15,
                    "rotationDiversity": 0.15,
                    "economics": 0.30,
                },
                "exclusions": [],
            },
            evidence={
                "power_cell": "0.5°",
                "hls_scenes": 12,
                "hls_coverage_pct": 82,
                "missing_data": ["HLS NDVI for 2 of 12 scenes (cloud > 80%)"],
                "rule_version": "v2026.11.0",
            },
            warnings=[
                "Rainfall data for 2 weeks in August was partial (coverage 72%).",
                "Economics uses mid-point of price/cost ranges; actual margins vary by season.",
            ],
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=58),
        )

        # Input snapshot
        InputSnapshot.objects.create(
            run=run,
            power_asset_id="power-daily:north-paddy-plot:2026",
            power_content_hash=hashlib.sha256(b"seed-power").hexdigest()[:64],
            hls_asset_id="hls-l30-ndvi:north-paddy-plot:2026",
            hls_content_hash=hashlib.sha256(b"seed-hls").hexdigest()[:64],
            catalogue_version="v2026.11.0",
            rule_version="v2026.11.0",
            soil_test_id="st-1",
        )

        # --- Scenarios ---
        crops = {c.slug: c for c in Crop.objects.all()}

        def _make_scenario(name, is_baseline, feasible, score, crops_seq):
            sc = Scenario.objects.create(
                run=run, name=name, is_baseline=is_baseline,
                feasible=feasible, score=score,
                reasons=[] if feasible == "feasible" else ["Constrained by water availability"],
            )
            for i, (slug, season) in enumerate(crops_seq, 1):
                crop = crops.get(slug)
                if not crop:
                    continue
                RotationPlan.objects.create(
                    scenario=sc, position=i, crop=crop,
                    season=season, family=crop.family,
                )
            return sc

        # Baseline: Boro rice → Wheat (current rotation)
        baseline = _make_scenario(
            "Boro rice + Wheat (current)",
            is_baseline=True, feasible="feasible", score=0.62,
            crops_seq=[("rice-boro", "boro"), ("wheat", "rabi")],
        )

        # Alternative 1: Boro rice + Mungbean + Mustard (diversity + legume)
        alt1 = _make_scenario(
            "Boro rice + Mungbean + Mustard",
            is_baseline=False, feasible="feasible", score=0.74,
            crops_seq=[("rice-boro", "boro"), ("mungbean", "autumn"), ("mustard", "rabi")],
        )

        # Alternative 2: Maize + Potato (higher margin, higher water)
        alt2 = _make_scenario(
            "Maize + Potato",
            is_baseline=False, feasible="constrained", score=0.58,
            crops_seq=[("maize", "boro"), ("potato", "rabi")],
        )

        # --- Metrics per scenario ---
        def _add_metrics(sc, water, heat, cover, div, margin):
            # (key, raw_value, normalized_0_to_1, weight)
            rows = [
                ("water_efficiency", water, round(1.0 - water / 2000.0, 3), 0.25),
                ("heat_resilience", heat, round(1.0 - heat / 30.0, 3), 0.15),
                ("canopy_cover", cover, cover, 0.15),
                ("diversity", div, div, 0.15),
                ("net_margin", margin, round(min(1.0, margin / 60000.0), 3), 0.30),
            ]
            for key, raw, norm, weight in rows:
                Metric.objects.create(
                    scenario=sc, key=key,
                    raw_value=raw, normalized=norm, weight=weight,
                    contribution=round(weight * norm, 4),
                    qualification="FAO-56 ET0 × crop Kc; canal efficiency 70%.",
                )

        _add_metrics(baseline, water=1420.0, heat=12.0, cover=0.72, div=0.35, margin=28500.0)
        _add_metrics(alt1, water=980.0, heat=8.0, cover=0.81, div=0.68, margin=34200.0)
        _add_metrics(alt2, water=1150.0, heat=15.0, cover=0.65, div=0.28, margin=41000.0)

        # Store plans in the run's JSON for the API
        run.plans = [
            {
                "name": "Boro rice + Wheat (current)",
                "isBaseline": True,
                "feasible": "feasible",
                "score": 0.62,
                "crops": ["rice-boro", "wheat"],
            },
            {
                "name": "Boro rice + Mungbean + Mustard",
                "isBaseline": False,
                "feasible": "feasible",
                "score": 0.74,
                "crops": ["rice-boro", "mungbean", "mustard"],
            },
            {
                "name": "Maize + Potato",
                "isBaseline": False,
                "feasible": "constrained",
                "score": 0.58,
                "crops": ["maize", "potato"],
            },
        ]
        run.save(update_fields=["plans"])

    # ------------------------------------------------------------------
    # AssistanceCase with messages + review
    # ------------------------------------------------------------------
    def _seed_case(self):
        farmer = User.objects.get(email="farmer@pilot.example")
        officer = User.objects.get(email="officer@pilot.example")
        field = Field.objects.get(slug="north-paddy-plot")

        existing = AssistanceCase.objects.filter(field=field, farmer=farmer).first()
        if existing:
            return

        case = AssistanceCase.objects.create(
            field=field,
            farmer=farmer,
            officer=officer,
            subject="Water stress in Boro rice — is a rotation change advisable?",
            body=(
                "The paddy plot showed visible wilting in mid-July despite canal "
                "irrigation. The comparison run shows Boro rice + Mungbean + Mustard "
                "scored highest (0.74). Is this a realistic alternative for the "
                "upcoming season, given our soil is silt loam and drainage is moderate?"
            ),
            status="in_review",
            decision="",
            linked_analysis=AnalysisRun.objects.filter(field=field, status="complete").first(),
        )

        CaseMessage.objects.create(
            case=case, author=farmer, author_role="farmer",
            body=(
                "I have been growing Boro rice + Wheat for 3 years. Yields have "
                "been stable at 4.8–5.1 t/ha, but water cost is rising and the "
                "July heatwave damaged about 10% of the plot. Open to trying "
                "Mungbean if the soil supports it."
            ),
        )
        CaseMessage.objects.create(
            case=case, author=officer, author_role="officer",
            body=(
                "Noted. The silt loam profile (pH 6.4, OM 1.8%) is well suited "
                "to Mungbean. The DAE soil test shows adequate P and K. I would "
                "recommend a 50/50 split: keep 1.2 ha in the existing rice-wheat "
                "rotation and trial Mungbean + Mustard on the other 1.2 ha. "
                "Can you confirm the canal water schedule for the autumn window?"
            ),
        )

        # Officer review (question — not yet accepted)
        CaseReview.objects.create(
            case=case,
            reviewer=officer,
            decision="question",
            note=(
                "Rotation change is agronomically sound. Need to confirm canal "
                "water availability for the autumn (Mungbean) window before "
                "formal acceptance."
            ),
        )

    # ------------------------------------------------------------------
    # ResearchExportJob (complete, with provenance)
    # ------------------------------------------------------------------
    def _seed_export(self):
        researcher = User.objects.get(email="researcher@pilot.example")
        field = Field.objects.get(slug="north-paddy-plot")

        existing = ExportJob.objects.filter(requester=researcher, status="complete").first()
        if existing:
            return

        now = timezone.now()
        ExportJob.objects.create(
            requester=researcher,
            scope="field",
            field=field,
            format="csv",
            status="complete",
            row_count=60,  # 20 weeks × 3 indicator kinds
            file_path="exports/seed-export-north-paddy-plot.csv",
            provenance_path="exports/seed-export-north-paddy-plot-provenance.json",
            provenance={
                "rule_version": "v2026.11.0",
                "power_asset": "power-daily:north-paddy-plot:2026",
                "hls_asset": "hls-l30-ndvi:north-paddy-plot:2026",
                "catalogue_version": "v2026.11.0",
                "field_slug": "north-paddy-plot",
                "period": "2026-01-01 to 2026-11-09",
            },
            completed_at=now - timedelta(hours=3),
        )
