from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fleet", "0005_reported_planning_order")]

    operations = [
        migrations.AddField(
            model_name="instance",
            name="health_state",
            field=models.JSONField(default=dict),
        ),
    ]
