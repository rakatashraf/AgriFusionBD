from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("farms", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="field",
            name="priorities",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="field",
            name="current_cycle_crops",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="field",
            name="recent_cycle_crops",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
