# Generated by Django 3.2.23 on 2024-01-18 07:34

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0033_registration_price_group_vat"),
    ]

    operations = [
        migrations.AddField(
            model_name="registrationuseraccess",
            name="is_substitute_user",
            field=models.BooleanField(default=False),
        ),
    ]
