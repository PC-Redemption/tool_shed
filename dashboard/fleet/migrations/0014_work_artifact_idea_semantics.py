from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fleet", "0013_instance_executive_state")]

    operations = [
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="discovery_status",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="next_action",
            field=models.CharField(blank=True, max_length=1000),
        ),
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="semantic_review_state",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="promotion_allowed",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
