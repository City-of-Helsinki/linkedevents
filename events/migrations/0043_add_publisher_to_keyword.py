# Generated by Django 1.9.13 on 2017-08-31 17:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0042_add_replaced_by_to_place"),
    ]

    operations = [
        migrations.AddField(
            model_name="keyword",
            name="publisher",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="Published_keywords",
                to="events.Organization",
                verbose_name="Publisher",
            ),
        ),
    ]
