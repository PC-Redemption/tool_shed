from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fleet", "0007_appserver_performance")]

    operations = [
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="closure_status",
            field=models.JSONField(default=dict),
        ),
    ]
