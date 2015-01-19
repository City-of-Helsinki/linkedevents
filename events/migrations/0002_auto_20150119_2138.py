# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='offer',
            name='price',
            field=models.CharField(max_length=512),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='offer',
            name='price_en',
            field=models.CharField(null=True, max_length=512),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='offer',
            name='price_fi',
            field=models.CharField(null=True, max_length=512),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='offer',
            name='price_sv',
            field=models.CharField(null=True, max_length=512),
            preserve_default=True,
        ),
    ]
