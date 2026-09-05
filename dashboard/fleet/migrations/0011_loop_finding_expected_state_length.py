from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fleet", "0010_loopfindingsnapshot")]

    operations = [
        migrations.AlterField(
            model_name="loopfindingsnapshot",
            name="expected_state",
            field=models.CharField(max_length=64),
        ),
    ]
