# Generated by Django 3.2.18 on 2023-04-27 08:24

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0012_registration_mandatory_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="signup",
            name="registration",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="signups",
                to="registrations.registration",
            ),
        ),
    ]
