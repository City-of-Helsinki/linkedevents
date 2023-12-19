# Generated by Django 3.2.23 on 2023-12-13 12:36

from django.db import migrations, models
import registrations.models


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0029_alter_registration_mandatory_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="signup",
            name="phone_number",
            field=models.CharField(
                blank=True,
                default=None,
                max_length=18,
                null=True,
                verbose_name="Phone number",
            ),
        ),
        migrations.AlterField(
            model_name="registration",
            name="mandatory_fields",
            field=registrations.models.ChoiceArrayField(
                base_field=models.CharField(
                    blank=True,
                    choices=[
                        ("city", "City"),
                        ("first_name", "First name"),
                        ("last_name", "Last name"),
                        ("phone_number", "Phone number"),
                        ("street_address", "Street address"),
                        ("zipcode", "ZIP code"),
                    ],
                    max_length=16,
                ),
                blank=True,
                default=list,
                size=None,
                verbose_name="Mandatory fields",
            ),
        ),
    ]
