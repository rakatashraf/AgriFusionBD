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
        farm, _ = Farm.objects.update_or_create(
            owner=farmer, name="Rafiqul's farm",
            defaults={"region": "Rajshahi Division"},
        )
        defs = [
            {
                "slug": "north-paddy-plot", "name": "North paddy plot",
                "lat": 24.447118, "lng": 88.568513, "area_ha": 2.4, "is_pin": False,
                "soil": "silt loam", "drainage": "moderate", "irrigation": "canal",
                # A working crop field in Paba upazila, Rajshahi (rural farmland).
                "polygon": [(88.567743, 24.446388), (88.569283, 24.446388),
                            (88.569283, 24.447848), (88.567743, 24.447848),
                            (88.567743, 24.446388)],
            },
            {
                "slug": "river-bend", "name": "Paba lowland field",
                "lat": 24.444842, "lng": 88.569011, "area_ha": 1.1, "is_pin": False,
                "soil": "silty clay", "drainage": "poor", "irrigation": "canal",
                "polygon": [(88.568491, 24.444352), (88.569531, 24.444352),
                            (88.569531, 24.445332), (88.568491, 24.445332),
                            (88.568491, 24.444352)],
            },
            {
                "slug": "pin-estimate-plot", "name": "Pin estimate plot",
                "lat": 24.445198, "lng": 88.567304, "area_ha": 0.3, "is_pin": True,
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

    # --- Devices + observations (AgriRover-Q v0.2 hardware — §5.6) ---------
    # One capacitive probe at 50 mm depth, no EC sensor, no NDVI-spot.
    # Moisture is VWC × 100 → %. Grant expiry set per report §2.
    def _seed_devices_and_observations(self):
        from datetime import timedelta
        from apps.rovers.models import SurveyRun, RoverSample

        operator = User.objects.get(email="rover_operator@pilot.example")
        north = Field.objects.get(slug="north-paddy-plot")
        river = Field.objects.get(slug="river-bend")

        rv1, _ = Device.objects.get_or_create(
            name="AgriRover-Q-01", operator=operator,
            defaults={"status": "idle", "battery_pct": 93, "serial": "agrirover-q-01"},
        )
        rv2, _ = Device.objects.get_or_create(
            name="AgriRover-Q-02", operator=operator,
            defaults={"status": "idle", "battery_pct": 87, "serial": "agrirover-q-02"},
        )

        now = timezone.now()
        # Grant with 30-day expiry (report §2: grants must carry an expiry)
        expires = now + timedelta(days=30)

        DeviceGrant.objects.update_or_create(
            device=rv1, field=north,
            defaults={"granted_by": operator, "expires_at": expires},
        )
        DeviceGrant.objects.update_or_create(
            device=rv1, field=river,
            defaults={"granted_by": operator, "expires_at": expires},
        )
        DeviceGrant.objects.update_or_create(
            device=rv2, field=north,
            defaults={"granted_by": operator, "expires_at": expires},
        )

        # --- SurveyRun + RoverSample: one run with 9 samples (spec §5.1) ---
        # The run mirrors the AgriRover-Q sample payload from the spec.
        run_id = "seed-demo-run-001"
        run, created = SurveyRun.objects.update_or_create(
            run_id=run_id,
            defaults={
                "device": rv1,
                "field": north,
                "status": "complete",
                "last_state": "done",
                "samples_count": 9,
                "started_at": now - timedelta(hours=2),
                "completed_at": now - timedelta(minutes=30),
            },
        )
        if not created:
            # Reset samples on re-seed to keep the count stable (idempotent)
            run.samples.all().delete()

        # 9 samples across 3 lanes, 50 mm probe depth, ~2.5 m GNSS CEP
        import random
        random.seed(42)
        base_lat, base_lon = north.lat, north.lng  # 24.447118, 88.568513
        samples_data = [
            # (sample_id, lane, lat_offset_m, lon_offset_m, vwc, temp_c, probe_ok)
            (1, 1, 0, 0, 0.2838, 18.31, True),
            (2, 1, 1.2, 0.8, 0.2791, 18.05, True),
            (3, 1, 2.5, 1.5, 0.2654, 17.82, True),
            (4, 2, 3.8, 0.5, 0.3012, 18.55, True),
            (5, 2, 5.1, -0.3, 0.2947, 18.40, True),
            (6, 2, 6.4, 1.1, 0.3105, 18.62, False),  # probe_ok=False → suspect
            (7, 3, 7.2, 0.2, 0.2756, 17.94, True),
            (8, 3, 8.5, -0.9, 0.2689, 17.78, True),
            (9, 3, 9.8, 0.4, 0.2901, 18.20, True),
        ]

        for (sid, lane, dlat_m, dlon_m, vwc, temp_c, probe_ok) in samples_data:
            lat = base_lat + dlat_m / 111_320.0
            lon = base_lon + dlon_m / (111_320.0 * 0.91)  # cos(24.37°) ≈ 0.91

            sample = RoverSample.objects.create(
                run=run,
                sample_id=sid,
                timestamp=now - timedelta(hours=2, minutes=(9 - sid) * 3),
                lane=lane,
                heading_deg=92.7 + lane * 15.0,
                lat=lat,
                lon=lon,
                gps_fix="3D",
                gps_hdop=round(0.85 + random.random() * 0.3, 2),
                gps_satellites=10 + random.randint(0, 5),
                probe_ok=probe_ok,
                probe_depth_mm=50.0,
                moisture_vwc=vwc,
                moisture_raw=int(vwc * 42000),
                soil_temp_c=temp_c,
                air_temp_c=round(24.0 + random.uniform(-1, 1), 2),
                air_humidity_pct=round(55.0 + random.uniform(-5, 5), 1),
                air_pressure_hpa=round(1008.0 + random.uniform(-2, 2), 1),
                battery_voltage=round(8.0 + random.uniform(0, 0.3), 2),
                battery_soc_pct=round(85 + random.randint(0, 10), 1),
                raw_json={"rover_id": "agrirover-q-01", "run_id": run_id, "sample_id": sid},
            )

            # Derive Observation rows (one value per row, §5.4)
            quality = "suspect" if not probe_ok else "valid"
            Observation.objects.update_or_create(
                message_id=f"{run_id}:{sid}:moisture",
                defaults={
                    "device": rv1, "field": north,
                    "sensor": "moisture",
                    "value": round(vwc * 100.0, 1),  # VWC → %
                    "unit": "%",
                    "quality": quality,
                    "calibrated": False,
                    "depth_cm": 5.0,  # 50 mm → 5 cm
                    "taken_at": sample.timestamp,
                },
            )
            Observation.objects.update_or_create(
                message_id=f"{run_id}:{sid}:temperature",
                defaults={
                    "device": rv1, "field": north,
                    "sensor": "temperature",
                    "value": temp_c,
                    "unit": "°C",
                    "quality": quality,
                    "calibrated": False,
                    "depth_cm": 5.0,
                    "taken_at": sample.timestamp,
                },
            )

        # Update run sample count
        run.samples_count = run.samples.count()
        run.save(update_fields=["samples_count", "updated_at"])
