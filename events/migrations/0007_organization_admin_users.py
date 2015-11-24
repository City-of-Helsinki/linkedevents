# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('events', '0006_auto_20150827_2020'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='admin_users',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL),
        ),
    ]
