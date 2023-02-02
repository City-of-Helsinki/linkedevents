# Generated by Django 1.11.11 on 2018-06-24 18:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0057_add_new_fields_to_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="images",
            field=models.ManyToManyField(
                blank=True, related_name="events", to="events.Image"
            ),
        ),
    ]
