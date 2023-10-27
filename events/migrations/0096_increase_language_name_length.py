# Generated by Django 3.2.22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0095_datasource_user_editable_registrations"),
    ]

    operations = [
        migrations.AlterField(
            model_name="language",
            name="name",
            field=models.CharField(max_length=100, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="language",
            name="name_ar",
            field=models.CharField(max_length=100, null=True, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="language",
            name="name_en",
            field=models.CharField(max_length=100, null=True, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="language",
            name="name_fi",
            field=models.CharField(max_length=100, null=True, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="language",
            name="name_ru",
            field=models.CharField(max_length=100, null=True, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="language",
            name="name_sv",
            field=models.CharField(max_length=100, null=True, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="language",
            name="name_zh_hans",
            field=models.CharField(max_length=100, null=True, verbose_name="Name"),
        ),
    ]
