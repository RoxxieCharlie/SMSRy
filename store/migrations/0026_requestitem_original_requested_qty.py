from django.db import migrations, models


def backfill_original_requested_qty(apps, schema_editor):
    RequestItem = apps.get_model("store", "RequestItem")
    RequestItem.objects.filter(original_requested_qty=0).update(
        original_requested_qty=models.F("requested_qty")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0025_request_needs_resubmission"),
    ]

    operations = [
        migrations.AddField(
            model_name="requestitem",
            name="original_requested_qty",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_original_requested_qty, migrations.RunPython.noop),
    ]
