# Generated by Django 2.2.13 on 2021-11-26 07:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0005_auto_20211125_1559"),
    ]

    operations = [
        migrations.AlterField(
            model_name="registration",
            name="event",
            field=models.OneToOneField(
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="registration",
                to="events.Event",
            ),
        ),
    ]
