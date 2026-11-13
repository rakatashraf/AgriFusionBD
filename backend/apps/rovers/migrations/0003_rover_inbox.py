from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rovers", "0002_add_survey_run_rover_sample_command_grant_expiry"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoverInbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("sample", "Sample"), ("image", "Image"), ("status", "Status/heartbeat")], max_length=16)),
                ("dedupe_key", models.CharField(max_length=160)),
                ("payload", models.JSONField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("retry", "Retry"), ("delivered", "Delivered"), ("dead", "Dead-lettered")], default="pending", max_length=16)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="inbox", to="rovers.device")),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="rover_inbox_status_created_idx"),
                    models.Index(fields=["device", "kind"], name="rover_inbox_device_kind_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=["dedupe_key"], name="rover_inbox_unique_dedupe"),
                ],
            },
        ),
    ]
