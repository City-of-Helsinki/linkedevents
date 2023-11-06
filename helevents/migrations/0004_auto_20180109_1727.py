# Generated by Django 1.11.5 on 2018-01-09 15:27

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("helusers", "0001_add_ad_groups"),
        ("helevents", "0003_auto_20170915_1529"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={"ordering": ("id",)},
        ),
        migrations.AddField(
            model_name="user",
            name="ad_groups",
            field=models.ManyToManyField(blank=True, to="helusers.ADGroup"),
        ),
    ]
