# Generated by Django 4.2.20 on 2025-04-03 13:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0101_eventsearchindex"),
    ]

    operations = [
        migrations.AlterField(
            model_name="eventsearchindex",
            name="event",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                primary_key=True,
                related_name="full_text",
                serialize=False,
                to="events.event",
            ),
        ),
        migrations.AlterField(
            model_name="eventsearchindex",
            name="place",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="full_text_place",
                to="events.place",
            ),
        ),
    ]
