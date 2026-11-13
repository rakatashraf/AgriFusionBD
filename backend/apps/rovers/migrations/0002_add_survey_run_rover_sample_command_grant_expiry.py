# Migration for the P1 rover plane (plan §5, §6 P1).
#
# Adds:
#   - DeviceGrant.expires_at
#   - SurveyRun  (run_id unique — the AgriRover-Q idempotency unit)
#   - RoverSample (run+sample_id unique — DB-level upsert)
#   - Command    (model only; endpoints out of scope, report §8/§10)
#   - Observation.uploaded_at (separate from taken_at, report §10)
#   - Observation.calibration FK
#   - Observation.SENSOR_CHOICES: ec and ndvi_spot retired (§5.6)
#
# Written by hand because GDAL is not available on this Windows host.
# Apply with: python manage.py migrate rovers

import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rovers", "0001_initial"),
    ]

    operations = [
        # DeviceGrant.expires_at
        migrations.AddField(
            model_name="devicegrant",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),

        # SurveyRun
        migrations.CreateModel(
            name="SurveyRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_id", models.CharField(max_length=128, unique=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("running", "Running"), ("complete", "Complete"), ("aborted", "Aborted")], default="running", max_length=16)),
                ("last_state", models.CharField(blank=True, max_length=32)),
                ("samples_count", models.PositiveIntegerField(default=0)),
                ("route", django.contrib.gis.db.models.fields.GeometryField(blank=True, null=True, srid=4326)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="survey_runs", to="rovers.device")),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="survey_runs", to="farms.field")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["device", "run_id"], name="rovers_surr_device__c9a1f0_idx"),
                    models.Index(fields=["field", "status"], name="rovers_surr_field__8b7c2d_idx"),
                ],
            },
        ),

        # RoverSample
        migrations.CreateModel(
            name="RoverSample",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sample_id", models.PositiveIntegerField()),
                ("timestamp", models.DateTimeField(blank=True, null=True)),
                ("lane", models.PositiveIntegerField(blank=True, null=True)),
                ("heading_deg", models.FloatField(blank=True, null=True)),
                ("lat", models.FloatField(blank=True, null=True)),
                ("lon", models.FloatField(blank=True, null=True)),
                ("gps_fix", models.CharField(blank=True, max_length=16)),
                ("gps_hdop", models.FloatField(blank=True, null=True)),
                ("gps_satellites", models.PositiveIntegerField(blank=True, null=True)),
                ("probe_ok", models.BooleanField(default=True)),
                ("probe_depth_mm", models.FloatField(blank=True, null=True)),
                ("moisture_vwc", models.FloatField(blank=True, null=True)),
                ("moisture_raw", models.PositiveIntegerField(blank=True, null=True)),
                ("soil_temp_c", models.FloatField(blank=True, null=True)),
                ("air_temp_c", models.FloatField(blank=True, null=True)),
                ("air_humidity_pct", models.FloatField(blank=True, null=True)),
                ("air_pressure_hpa", models.FloatField(blank=True, null=True)),
                ("battery_voltage", models.FloatField(blank=True, null=True)),
                ("battery_soc_pct", models.FloatField(blank=True, null=True)),
                ("image", models.FileField(blank=True, null=True, upload_to="rover_images/")),
                ("raw_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="samples", to="rovers.surveyrun")),
            ],
            options={
                "ordering": ["-timestamp"],
                "unique_together": {("run", "sample_id")},
                "indexes": [models.Index(fields=["run", "sample_id"], name="rovers_rov_sample__d3e4f5_idx")],
            },
        ),

        # Command (model only)
        migrations.CreateModel(
            name="Command",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("command_id", models.CharField(max_length=128, unique=True)),
                ("sequence", models.PositiveIntegerField()),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("ack_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("acknowledged", "Acknowledged"), ("expired", "Expired"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commands", to="rovers.device")),
                ("issued_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commands_issued", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-issued_at"],
                "indexes": [models.Index(fields=["device", "sequence"], name="rovers_comma_device__a1b2c3_idx")],
            },
        ),

        # Observation: uploaded_at
        migrations.AddField(
            model_name="observation",
            name="uploaded_at",
            field=models.DateTimeField(auto_now_add=True),
        ),

        # Observation: calibration FK
        migrations.AddField(
            model_name="observation",
            name="calibration",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="observations", to="rovers.sensorcalibration"),
        ),

        # Observation: retire ec and ndvi_spot from SENSOR_CHOICES (§5.6)
        migrations.AlterField(
            model_name="observation",
            name="sensor",
            field=models.CharField(
                choices=[("moisture", "Soil moisture"), ("temperature", "Temperature")],
                max_length=32,
            ),
        ),
    ]
