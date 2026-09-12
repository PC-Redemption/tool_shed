from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fleet", "0012_work_artifact_terminal_reason")]

    operations = [
        migrations.AddField(
            model_name="instance",
            name="executive_state",
            field=models.JSONField(default=dict),
        ),
    ]
