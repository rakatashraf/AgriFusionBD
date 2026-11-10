"""
seed_demo — load the pilot dataset (plan §1, Phase 1).

Seeds: 4 demo users (one per role), 6 crops, 3 fields (with polygon or pin
geometry), crop history (the never-invented baseline), 1 soil test, 2 rover
devices + grants, and a few rover observations. Values mirror
``frontend/src/lib/mock-data.ts`` so the UI and the DB agree.

Idempotent: safe to re-run (uses get_or_create throughout).
"""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalogue.models import (
    Crop, CropCalendar, CropRuleVersion, SoilTest,
)
from apps.environment.models import DatasetProduct
from apps.farms.models import CropHistory, Farm, Field
from apps.rovers.models import Device, DeviceGrant, Observation

User = None  # set in handle()


class Command(BaseCommand):
    help = "Seed the FieldShift pilot dataset (users, crops, fields, soil, history, devices)."

    def handle(self, *args, **options):
        global User
        User = get_user_model()
        self._seed_users()
        self._seed_rule_version()
        self._seed_dataset_products()
        crops = self._seed_crops()
        self._seed_calendars(crops)
        self._seed_fields()
        self._seed_soil_tests()
        self._seed_crop_history(crops)
        self._seed_devices_and_observations()
        self.stdout.write(self.style.SUCCESS(
            "Seed complete: 4 users, 6 crops, 3 fields, 1 soil test, 2 devices."
        ))

    # --- Users -------------------------------------------------------------
    def _seed_users(self):
        demo = [
            ("farmer@pilot.example", "Rafiqul Islam", ["farmer"], "Pilot farmer"),
            ("officer@pilot.example", "Nasrin Akter", ["officer"], "DAE Field Officer"),
            ("researcher@pilot.example", "Dr. Tanvir Hasan", ["researcher"], "BARC Researcher"),
            ("rover_operator@pilot.example", "Kamal Uddin", ["rover_operator", "officer"], "Rover Operator"),
        ]
        for email, name, roles, org in demo:
            u, created = User.objects.get_or_create(
                email=email,
                defaults={"name": name, "roles": roles, "is_active": True},
            )
            if created:
                u.set_unusable_password()
                u.save(update_fields=["password"])

    # --- Rule version ------------------------------------------------------
    def _seed_rule_version(self):
        CropRuleVersion.objects.get_or_create(
            version="v2026.11.0",
            defaults={
                "is_active": True,
                "notes": "FieldShift pilot rule set — FAO-56 ET0, USDA-SCS effective "
                         "rainfall, 40% HLS coverage floor, Tiemann diversity, net-margin range.",
                "payload": {"source": "plan §4 Phase 4"},
            },
        )

    # --- Dataset products --------------------------------------------------
    def _seed_dataset_products(self):
        DatasetProduct.objects.get_or_create(
            slug="power-daily",
            defaults={"name": "NASA POWER Daily", "provider": "NASA POWER",
                      "product_id": "POWER", "resolution": "0.5 deg", "cadence": "daily"},
        )
        DatasetProduct.objects.get_or_create(
            slug="hls-l30-ndvi",
            defaults={"name": "USGS HLS NDVI (L30/S30)", "provider": "USGS HLS",
                      "product_id": "HLSL30.VI", "resolution": "30 m", "cadence": "16-day"},
        )

    # --- Crops (mirror mock-data.ts CROPS) --------------------------------
    def _seed_crops(self) -> dict[str, Crop]:
        specs = [
            # slug, name, name_bn, family, legume, water_mm, kc, heat, drought,
            # price[low,high], cost[low,high], yield[low,high], months
            ("rice-boro", "Boro rice", "বোরো ধান", "Poaceae", False, 1400, 1.2, "moderate", "low",
             [22, 28], [90000, 120000], [3.5, 5.5], [12, 1, 2, 3, 4], "canal"),
            ("wheat", "Wheat", "গম", "Poaceae", False, 450, 1.1, "high", "high",
             [18, 24], [60000, 80000], [2.5, 4.0], [12, 1, 2, 3], "canal"),
            ("mustard", "Mustard", "সরিষা", "Brassicaceae", False, 300, 1.0, "moderate", "high",
             [60, 80], [25000, 35000], [0.8, 1.2], [12, 1, 2], "rainfed"),
            ("maize", "Maize", "ভুট্টা", "Poaceae", False, 550, 1.15, "moderate", "moderate",
             [14, 18], [45000, 65000], [3.0, 4.5], [12, 1, 2, 3], "canal"),
            ("mungbean", "Mungbean", "মটর", "Fabaceae", True, 250, 1.05, "high", "high",
             [90, 120], [20000, 30000], [0.7, 1.1], [6, 7, 8, 9, 10], "rainfed"),
            ("potato", "Potato", "আলু", "Solanaceae", False, 500, 1.05, "high", "moderate",
             [30, 45], [70000, 95000], [15, 25], [12, 1, 2, 3], "canal"),
        ]
        out: dict[str, Crop] = {}
        for (slug, name, name_bn, family, legume, water, kc, heat, drought,
             price, cost, yld, months, irr) in specs:
            c, _ = Crop.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name, "name_bn": name_bn, "family": family,
                    "is_legume": legume, "water_demand_mm": water,
                    "kc_canopy": kc, "kc_initial": kc * 0.6, "kc_late": kc * 0.9,
                    "heat_tolerance": heat, "drought_tolerance": drought,
                    "price_range_bdt_per_kg": price, "cost_per_ha_bdt": cost,
                    "yield_range_t": yld, "season_months": months,
                    "irrigation_max": irr, "equipment": [],
                    "soil_ph_min": 5.5, "soil_ph_max": 8.0,
                },
            )
            out[slug] = c
        return out

    # --- Calendars ---------------------------------------------------------
    def _seed_calendars(self, crops: dict[str, Crop]):
        for slug, c in crops.items():
            months = c.season_months or []
            if not months:
                continue
            season = self._season_for_months(months)
            CropCalendar.objects.get_or_create(
                crop=c, season=season,
                defaults={
                    "start_month": months[0], "end_month": months[-1],
                    "region": "national", "source": "DAE/BARC crop calendar",
                },
            )

    def _season_for_months(self, months):
        if 12 in months or 1 in months:
            return "boro"
        if 6 in months or 7 in months:
            return "aman"
        if 9 in months or 10 in months:
            return "autumn"
        return "rabi"

    # --- Fields (mirror mock-data.ts FIELDS) -------------------------------
    def _seed_fields(self):
        farmer = User.objects.get(email="farmer@pilot.example")
        farm, _ = Farm.objects.get_or_create(owner=farmer, name="Rafiqul's farm",
                                             defaults={"region": "Dhaka Division"})
        defs = [
            {
                "slug": "north-paddy-plot", "name": "North paddy plot",
                "lat": 25.342, "lng": 88.610, "area_ha": 2.4, "is_pin": False,
                "soil": "silt loam", "drainage": "moderate", "irrigation": "canal",
                # A small polygon ~2.4 ha around the centroid.
                "polygon": [(88.606, 25.339), (88.614, 25.339), (88.614, 25.345),
                            (88.606, 25.345), (88.606, 25.339)],
            },
            {
                "slug": "river-bend", "name": "River-bend field",
                "lat": 25.350, "lng": 88.632, "area_ha": 1.1, "is_pin": False,
                "soil": "silty clay", "drainage": "poor", "irrigation": "canal",
                "polygon": [(88.629, 25.348), (88.635, 25.348), (88.635, 25.352),
                            (88.629, 25.352), (88.629, 25.348)],
            },
            {
                "slug": "pin-estimate-plot", "name": "Pin estimate plot",
                "lat": 25.330, "lng": 88.590, "area_ha": 0.3, "is_pin": True,
                "soil": "unknown", "drainage": "moderate", "irrigation": "canal",
            },
        ]
        for d in defs:
            if d["is_pin"]:
                geom = Point(d["lng"], d["lat"], srid=4326)
                pin_radius = 25
            else:
                ring = d["polygon"]
                geom = Polygon(ring, srid=4326)
                pin_radius = 0
            Field.objects.update_or_create(
                slug=d["slug"],
                defaults={
                    "farm": farm, "farmer": farmer, "name": d["name"],
                    "geometry": geom, "is_pin_estimate": d["is_pin"],
                    "pin_radius_m": pin_radius, "area_ha": d["area_ha"],
                    "lat": d["lat"], "lng": d["lng"],
                    "soil_type": d["soil"], "irrigation": d["irrigation"],
                    "drainage": d["drainage"], "status": "active", "version": 1,
                },
            )

    # --- Soil test (mirror mock-data.ts SOIL_TESTS st-1) -------------------
    def _seed_soil_tests(self):
        field = Field.objects.get(slug="north-paddy-plot")
        SoilTest.objects.get_or_create(
            field=field, tested_on=timezone.now().date(),
            defaults={
                "ph": 6.4, "organic_matter_pct": 1.8, "ec_dsm": 0.4,
                "n_pct": 0.12, "p_pct": 0.03, "k_pct": 0.08,
                "lab": "DAE Soil Lab", "notes": "Baseline pilot soil test.",
            },
        )

    # --- Crop history (the never-invented baseline) ------------------------
    def _seed_crop_history(self, crops: dict[str, Crop]):
        north = Field.objects.get(slug="north-paddy-plot")
        river = Field.objects.get(slug="river-bend")
        now = timezone.now()
        year = now.year

        def ch(field, crop_slug, season, yr, area, yld, planted=None, harvested=None):
            CropHistory.objects.get_or_create(
                field=field, crop=crops[crop_slug], season=season, year=yr,
                defaults={
                    "area_ha": area, "yield_t": yld,
                    "planted_on": planted, "harvested_on": harvested,
                    "recorded_by": User.objects.get(email="farmer@pilot.example"),
                },
            )

        # North paddy plot: 2-year history (rice-boro → wheat).
        ch(north, "rice-boro", "boro", year - 1, 2.4, 4.8)
        ch(north, "wheat", "rabi", year - 1, 2.4, 3.2)
        ch(north, "rice-boro", "boro", year, 2.4, 5.1)

        # River-bend: 1-year history (rice-boro only).
        ch(river, "rice-boro", "boro", year, 1.1, 4.2)

    # --- Devices + observations (mirror mock-data.ts) -----------------------
    def _seed_devices_and_observations(self):
        operator = User.objects.get(email="rover_operator@pilot.example")
        north = Field.objects.get(slug="north-paddy-plot")
        river = Field.objects.get(slug="river-bend")

        rv1, _ = Device.objects.get_or_create(
            name="Rover-1 (soil probe)", operator=operator,
            defaults={"status": "idle", "battery_pct": 82, "serial": "FS-RV-001"},
        )
        rv2, _ = Device.objects.get_or_create(
            name="Rover-2 (multi-sensor)", operator=operator,
            defaults={"status": "on_mission", "battery_pct": 64, "serial": "FS-RV-002"},
        )
        DeviceGrant.objects.get_or_create(device=rv1, field=north)
        DeviceGrant.objects.get_or_create(device=rv1, field=river)
        DeviceGrant.objects.get_or_create(device=rv2, field=north)

        now = timezone.now()
        obs = [
            (rv1, north, "moisture", 34.2, "%", "valid", True, 15.0),
            (rv1, north, "ec", 0.42, "dS/m", "valid", True, 15.0),
            (rv2, north, "temperature", 27.8, "°C", "valid", False, None),
            (rv2, river, "moisture", 28.1, "%", "partial", False, 10.0),
        ]
        for i, (dev, fld, sensor, val, unit, q, cal, depth) in enumerate(obs):
            Observation.objects.get_or_create(
                message_id=f"seed-obs-{i}",
                defaults={
                    "device": dev, "field": fld, "sensor": sensor, "value": val,
                    "unit": unit, "quality": q, "calibrated": cal, "depth_cm": depth,
                    "taken_at": now,
                },
            )
