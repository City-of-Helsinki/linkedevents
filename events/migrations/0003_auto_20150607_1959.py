# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_auto_20150119_2138'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='event',
            name='custom_data',
        ),
        migrations.RemoveField(
            model_name='place',
            name='custom_data',
        ),
    ]
