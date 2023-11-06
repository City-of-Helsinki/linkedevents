# Generated by Django 1.11.11 on 2018-06-07 05:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0056_fix_chinese_lang_obj"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="audience_max_age",
            field=models.SmallIntegerField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Maximum recommended age",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="audience_min_age",
            field=models.SmallIntegerField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Minimum recommended age",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="provider_contact_info",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="Provider's contact info",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="provider_contact_info_ar",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="Provider's contact info",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="provider_contact_info_en",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="Provider's contact info",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="provider_contact_info_fi",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="Provider's contact info",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="provider_contact_info_ru",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="Provider's contact info",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="provider_contact_info_sv",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="Provider's contact info",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="provider_contact_info_zh_hans",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="Provider's contact info",
            ),
        ),
    ]
