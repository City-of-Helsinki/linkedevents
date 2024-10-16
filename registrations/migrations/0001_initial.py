# Generated by Django 2.2.13 on 2021-10-20 04:51

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("events", "0085_remove_feedback_limit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Registration",
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
                ("attendee_registration", models.BooleanField(default=False)),
                (
                    "audience_min_age",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Minimum recommended age",
                    ),
                ),
                (
                    "audience_max_age",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Maximum recommended age",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created at"),
                ),
                (
                    "last_modified_at",
                    models.DateTimeField(
                        auto_now=True, null=True, verbose_name="Modified at"
                    ),
                ),
                (
                    "enrollment_start_time",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Enrollment start time"
                    ),
                ),
                (
                    "enrollment_end_time",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Enrollment end time"
                    ),
                ),
                (
                    "confirmation_message",
                    models.TextField(
                        blank=True, null=True, verbose_name="Confirmation message"
                    ),
                ),
                (
                    "instructions",
                    models.TextField(
                        blank=True, null=True, verbose_name="Instructions"
                    ),
                ),
                (
                    "maximum_attendee_capacity",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="Maximum attendee capacity"
                    ),
                ),
                (
                    "minimum_attendee_capacity",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="Minimum attendee capacity"
                    ),
                ),
                (
                    "waiting_list_capacity",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="Minimum attendee capacity"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "event",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="registration",
                        to="events.Event",
                    ),
                ),
                (
                    "last_modified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_last_modified_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
