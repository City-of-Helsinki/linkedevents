# Generated by Django 3.2.20 on 2023-08-18 06:46

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0093_increase_provider_contact_info_max_length"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="image",
            name="alt_text_ar",
        ),
        migrations.RemoveField(
            model_name="image",
            name="alt_text_en",
        ),
        migrations.RemoveField(
            model_name="image",
            name="alt_text_fi",
        ),
        migrations.RemoveField(
            model_name="image",
            name="alt_text_ru",
        ),
        migrations.RemoveField(
            model_name="image",
            name="alt_text_sv",
        ),
        migrations.RemoveField(
            model_name="image",
            name="alt_text_zh_hans",
        ),
    ]
