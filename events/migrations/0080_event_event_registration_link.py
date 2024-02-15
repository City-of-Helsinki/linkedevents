# Generated by Django 2.2.28 on 2024-02-15 13:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0079_allow_blank_as_image_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='event_registration_link',
            field=models.URLField(blank=True, max_length=1000, null=True, verbose_name='Event registration link'),
        ),
    ]
