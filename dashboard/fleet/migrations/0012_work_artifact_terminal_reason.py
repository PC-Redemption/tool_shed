from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fleet", "0011_loop_finding_expected_state_length")]

    operations = [
        migrations.AddField(
            model_name="workartifactsnapshot",
            name="terminal_reason",
            field=models.CharField(blank=True, max_length=240),
        )
    ]
