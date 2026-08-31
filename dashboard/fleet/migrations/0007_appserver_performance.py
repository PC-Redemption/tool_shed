from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fleet", "0006_instance_health_state")]

    operations = [
        migrations.AddField(
            model_name="appserveraggregate",
            name="performance",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="appserveraggregate",
            name="readiness_observed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
