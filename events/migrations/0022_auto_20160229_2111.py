# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0021_auto_20160217_1832'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='event',
            managers=[
            ],
        ),
        migrations.AlterModelManagers(
            name='place',
            managers=[
            ],
        ),
        migrations.AlterField(
            model_name='event',
            name='image',
            field=models.ForeignKey(verbose_name='Image', blank=True, to='events.Image', null=True, on_delete=django.db.models.deletion.SET_NULL),
        ),
        migrations.AlterField(
            model_name='event',
            name='location',
            field=models.ForeignKey(blank=True, to='events.Place', null=True, on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AlterField(
            model_name='event',
            name='publisher',
            field=models.ForeignKey(verbose_name='Publisher', to='events.Organization', related_name='published_events', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AlterField(
            model_name='event',
            name='super_event',
            field=mptt.fields.TreeForeignKey(blank=True, to='events.Event', related_name='sub_events', null=True, on_delete=django.db.models.deletion.SET_NULL),
        ),
        migrations.AlterField(
            model_name='keyword',
            name='image',
            field=models.ForeignKey(verbose_name='Image', blank=True, to='events.Image', null=True, on_delete=django.db.models.deletion.SET_NULL),
        ),
        migrations.AlterField(
            model_name='keywordset',
            name='image',
            field=models.ForeignKey(verbose_name='Image', blank=True, to='events.Image', null=True, on_delete=django.db.models.deletion.SET_NULL),
        ),
        migrations.AlterField(
            model_name='organization',
            name='image',
            field=models.ForeignKey(verbose_name='Image', blank=True, to='events.Image', null=True, on_delete=django.db.models.deletion.SET_NULL),
        ),
        migrations.AlterField(
            model_name='place',
            name='image',
            field=models.ForeignKey(verbose_name='Image', blank=True, to='events.Image', null=True, on_delete=django.db.models.deletion.SET_NULL),
        ),
    ]
