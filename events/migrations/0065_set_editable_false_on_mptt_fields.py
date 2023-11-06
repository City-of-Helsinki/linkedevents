# Generated by Django 2.2.9 on 2020-01-08 07:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0064_lengthen_id_foreign_keys"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="level",
            field=models.PositiveIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name="event",
            name="lft",
            field=models.PositiveIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name="event",
            name="rght",
            field=models.PositiveIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name="place",
            name="level",
            field=models.PositiveIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name="place",
            name="lft",
            field=models.PositiveIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name="place",
            name="rght",
            field=models.PositiveIntegerField(editable=False),
        ),
    ]
