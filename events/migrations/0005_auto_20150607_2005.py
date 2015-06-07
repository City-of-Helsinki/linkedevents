# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.contrib.postgres.fields.hstore
from django.contrib.postgres.operations import HStoreExtension


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_auto_20150607_2003'),
    ]

    operations = [
        HStoreExtension(),
        migrations.AddField(
            model_name='event',
            name='custom_data',
            field=django.contrib.postgres.fields.hstore.HStoreField(null=True),
        ),
        migrations.AddField(
            model_name='place',
            name='custom_data',
            field=django.contrib.postgres.fields.hstore.HStoreField(null=True),
        ),
    ]
