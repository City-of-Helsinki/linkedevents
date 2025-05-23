# Generated by Django 4.2.20 on 2025-04-02 09:13

import django.contrib.postgres.fields
import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0100_alter_event_maximum_attendee_capacity_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventSearchIndex",
            fields=[
                (
                    "event",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        primary_key=True,
                        related_name="full_text",
                        serialize=False,
                        to="events.event",
                    ),
                ),
                ("event_last_modified_time", models.DateTimeField()),
                ("place_last_modified_time", models.DateTimeField()),
                (
                    "words_fi",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=64),
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "words_en",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=64),
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "words_sv",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=64),
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "search_vector_fi",
                    django.contrib.postgres.search.SearchVectorField(),
                ),
                (
                    "search_vector_en",
                    django.contrib.postgres.search.SearchVectorField(),
                ),
                (
                    "search_vector_sv",
                    django.contrib.postgres.search.SearchVectorField(),
                ),
                (
                    "place",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="full_text_place",
                        to="events.place",
                    ),
                ),
            ],
            options={
                "ordering": ["-pk"],
            },
        ),
        migrations.DeleteModel(
            name="EventFullText",
        ),
        migrations.AddIndex(
            model_name="eventsearchindex",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector_fi"], name="events_even_search__95ba89_gin"
            ),
        ),
        migrations.AddIndex(
            model_name="eventsearchindex",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector_en"], name="events_even_search__9d9fe8_gin"
            ),
        ),
        migrations.AddIndex(
            model_name="eventsearchindex",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector_sv"], name="events_even_search__88c403_gin"
            ),
        ),
    ]
