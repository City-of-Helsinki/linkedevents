# Generated by Django 3.2.19 on 2023-06-14 11:25

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0014_alter_signup_unique_together"),
    ]

    operations = [
        migrations.AddField(
            model_name="registration",
            name="maximum_group_size",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Maximum group size",
            ),
        ),
    ]
