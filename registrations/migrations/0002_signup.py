# Generated by Django 2.2.13 on 2021-11-25 09:31

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="registration",
            old_name="enrollment_end_time",
            new_name="enrolment_end_time",
        ),
        migrations.RenameField(
            model_name="registration",
            old_name="enrollment_start_time",
            new_name="enrolment_start_time",
        ),
        migrations.CreateModel(
            name="SignUp",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50)),
                ("city", models.CharField(blank=True, default="", max_length=50)),
                ("email", models.EmailField(max_length=254)),
                ("extra_info", models.TextField(blank=True, default="")),
                (
                    "membership_number",
                    models.CharField(blank=True, default="", max_length=50),
                ),
                (
                    "phone_number",
                    models.CharField(blank=True, default="", max_length=18),
                ),
                (
                    "notifications",
                    models.CharField(
                        choices=[
                            ("none", "No Notification"),
                            ("sms", "SMS"),
                            ("email", "E-Mail"),
                            ("sms and email", "Both SMS and email."),
                        ],
                        default="none",
                        max_length=25,
                        verbose_name="Notification type",
                    ),
                ),
                (
                    "cancellation_code",
                    models.UUIDField(default=uuid.uuid4, editable=False),
                ),
                (
                    "registration",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signups",
                        to="registrations.Registration",
                    ),
                ),
            ],
            options={
                "unique_together": {
                    ("email", "registration"),
                    ("phone_number", "registration"),
                },
            },
        ),
    ]
