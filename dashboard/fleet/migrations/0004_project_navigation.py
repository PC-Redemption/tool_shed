from django.db import migrations, models


def backfill_project_activity(apps, schema_editor):
    project = apps.get_model("fleet", "Project")
    project.objects.filter(last_activity_at__isnull=True, last_seen__isnull=False).update(
        last_activity_at=models.F("last_seen")
    )


class Migration(migrations.Migration):
    dependencies = [("fleet", "0003_attention_condition")]

    operations = [
        migrations.AddField(
            model_name="project",
            name="last_activity_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="is_hidden",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_project_activity, migrations.RunPython.noop),
    ]
