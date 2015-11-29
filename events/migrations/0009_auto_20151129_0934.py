# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0008_auto_20151127_1019'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='admin_users',
            field=models.ManyToManyField(related_name='organizations', blank=True, to=settings.AUTH_USER_MODEL),
        ),
    ]
