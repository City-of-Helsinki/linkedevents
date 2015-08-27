# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_auto_20150607_2005'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='image',
            field=models.URLField(blank=True, null=True, max_length=400, verbose_name='Image URL'),
        ),
        migrations.AlterField(
            model_name='event',
            name='keywords',
            field=models.ManyToManyField(to='events.Keyword'),
        ),
        migrations.AlterField(
            model_name='keyword',
            name='image',
            field=models.URLField(blank=True, null=True, max_length=400, verbose_name='Image URL'),
        ),
        migrations.AlterField(
            model_name='organization',
            name='image',
            field=models.URLField(blank=True, null=True, max_length=400, verbose_name='Image URL'),
        ),
        migrations.AlterField(
            model_name='place',
            name='image',
            field=models.URLField(blank=True, null=True, max_length=400, verbose_name='Image URL'),
        ),
    ]
