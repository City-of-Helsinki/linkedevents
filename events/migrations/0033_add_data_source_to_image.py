# Generated by Django 1.9.11 on 2016-11-28 14:24
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_func(apps, schema_editor):
    Image = apps.get_model("events", "Image")

    for image in Image.objects.filter(event__isnull=False).distinct():
        image.data_source = image.event_set.all()[0].data_source
        image.save()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0032_add_super_event_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="image",
            name="data_source",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="provided_%(class)s_data",
                to=settings.DJANGO_ORGHIERARCHY_DATASOURCE_MODEL,
            ),
        ),
        migrations.RunPython(forwards_func, migrations.RunPython.noop),
    ]
