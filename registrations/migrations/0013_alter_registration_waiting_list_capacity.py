# Generated by Django 3.2.18 on 2023-04-05 23:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrations", "0012_mandatory_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="registration",
            name="waiting_list_capacity",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="Waiting list capacity"
            ),
        ),
    ]
