# Generated by Django 4.2.11 on 2024-05-10 11:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrations", "0045_signuppaymentrefund"),
    ]

    operations = [
        migrations.AlterField(
            model_name="webstoremerchant",
            name="url",
            field=models.URLField(editable=False, verbose_name="URL"),
        ),
    ]