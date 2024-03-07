# Generated by Django 3.2.23 on 2024-02-09 12:04

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0037_registration_remaining_capacities_db_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="signup",
            name="deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="signupcontactperson",
            name="deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="signupgroup",
            name="deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="signupgroupprotecteddata",
            name="deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="signuppayment",
            name="deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="signuppricegroup",
            name="deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="signupprotecteddata",
            name="deleted",
            field=models.BooleanField(default=False),
        ),
    ]