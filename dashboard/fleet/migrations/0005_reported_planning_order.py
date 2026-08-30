from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fleet", "0004_project_navigation")]

    operations = [
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="planning_order_source",
            field=models.CharField(default="not-applicable", max_length=24),
        ),
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="planning_position",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="planning_readiness",
            field=models.CharField(default="not-applicable", max_length=24),
        ),
    ]
