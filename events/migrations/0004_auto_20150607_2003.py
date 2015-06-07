# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0003_auto_20150607_1959'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datasource',
            name='name',
            field=models.CharField(max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='event',
            name='audience',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Audience'),
        ),
        migrations.AlterField(
            model_name='event',
            name='date_published',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Date published'),
        ),
        migrations.AlterField(
            model_name='event',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='event',
            name='description_en',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='event',
            name='description_fi',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='event',
            name='description_sv',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='event',
            name='end_time',
            field=models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='End time'),
        ),
        migrations.AlterField(
            model_name='event',
            name='event_status',
            field=models.SmallIntegerField(default=1, choices=[(1, 'EventScheduled'), (2, 'EventCancelled'), (3, 'EventPostponed'), (4, 'EventRescheduled')], verbose_name='Event status'),
        ),
        migrations.AlterField(
            model_name='event',
            name='headline',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Headline'),
        ),
        migrations.AlterField(
            model_name='event',
            name='headline_en',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Headline'),
        ),
        migrations.AlterField(
            model_name='event',
            name='headline_fi',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Headline'),
        ),
        migrations.AlterField(
            model_name='event',
            name='headline_sv',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Headline'),
        ),
        migrations.AlterField(
            model_name='event',
            name='image',
            field=models.URLField(null=True, blank=True, verbose_name='Image URL'),
        ),
        migrations.AlterField(
            model_name='event',
            name='info_url',
            field=models.URLField(null=True, blank=True, verbose_name='Event home page'),
        ),
        migrations.AlterField(
            model_name='event',
            name='location_extra_info',
            field=models.CharField(null=True, blank=True, max_length=400, verbose_name='Location extra info'),
        ),
        migrations.AlterField(
            model_name='event',
            name='location_extra_info_en',
            field=models.CharField(null=True, blank=True, max_length=400, verbose_name='Location extra info'),
        ),
        migrations.AlterField(
            model_name='event',
            name='location_extra_info_fi',
            field=models.CharField(null=True, blank=True, max_length=400, verbose_name='Location extra info'),
        ),
        migrations.AlterField(
            model_name='event',
            name='location_extra_info_sv',
            field=models.CharField(null=True, blank=True, max_length=400, verbose_name='Location extra info'),
        ),
        migrations.AlterField(
            model_name='event',
            name='name',
            field=models.CharField(db_index=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='event',
            name='name_en',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='event',
            name='name_fi',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='event',
            name='name_sv',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='event',
            name='origin_id',
            field=models.CharField(db_index=True, blank=True, max_length=50, null=True, verbose_name='Origin ID'),
        ),
        migrations.AlterField(
            model_name='event',
            name='provider',
            field=models.CharField(null=True, max_length=512, verbose_name='Provider'),
        ),
        migrations.AlterField(
            model_name='event',
            name='provider_en',
            field=models.CharField(null=True, max_length=512, verbose_name='Provider'),
        ),
        migrations.AlterField(
            model_name='event',
            name='provider_fi',
            field=models.CharField(null=True, max_length=512, verbose_name='Provider'),
        ),
        migrations.AlterField(
            model_name='event',
            name='provider_sv',
            field=models.CharField(null=True, max_length=512, verbose_name='Provider'),
        ),
        migrations.AlterField(
            model_name='event',
            name='publisher',
            field=models.ForeignKey(to='events.Organization', related_name='published_events', verbose_name='Publisher'),
        ),
        migrations.AlterField(
            model_name='event',
            name='secondary_headline',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Secondary headline'),
        ),
        migrations.AlterField(
            model_name='event',
            name='secondary_headline_en',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Secondary headline'),
        ),
        migrations.AlterField(
            model_name='event',
            name='secondary_headline_fi',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Secondary headline'),
        ),
        migrations.AlterField(
            model_name='event',
            name='secondary_headline_sv',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Secondary headline'),
        ),
        migrations.AlterField(
            model_name='event',
            name='short_description',
            field=models.TextField(blank=True, null=True, verbose_name='Short description'),
        ),
        migrations.AlterField(
            model_name='event',
            name='short_description_en',
            field=models.TextField(blank=True, null=True, verbose_name='Short description'),
        ),
        migrations.AlterField(
            model_name='event',
            name='short_description_fi',
            field=models.TextField(blank=True, null=True, verbose_name='Short description'),
        ),
        migrations.AlterField(
            model_name='event',
            name='short_description_sv',
            field=models.TextField(blank=True, null=True, verbose_name='Short description'),
        ),
        migrations.AlterField(
            model_name='event',
            name='start_time',
            field=models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='Start time'),
        ),
        migrations.AlterField(
            model_name='eventaggregatemember',
            name='event',
            field=models.OneToOneField(to='events.Event'),
        ),
        migrations.AlterField(
            model_name='eventlink',
            name='name',
            field=models.CharField(blank=True, max_length=100, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='keyword',
            name='image',
            field=models.URLField(null=True, blank=True, verbose_name='Image URL'),
        ),
        migrations.AlterField(
            model_name='keyword',
            name='name',
            field=models.CharField(db_index=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='keyword',
            name='name_en',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='keyword',
            name='name_fi',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='keyword',
            name='name_sv',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='keyword',
            name='origin_id',
            field=models.CharField(db_index=True, blank=True, max_length=50, null=True, verbose_name='Origin ID'),
        ),
        migrations.AlterField(
            model_name='keywordlabel',
            name='name',
            field=models.CharField(db_index=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='language',
            name='name',
            field=models.CharField(max_length=20, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='language',
            name='name_en',
            field=models.CharField(null=True, max_length=20, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='language',
            name='name_fi',
            field=models.CharField(null=True, max_length=20, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='language',
            name='name_sv',
            field=models.CharField(null=True, max_length=20, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Offer description'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='description_en',
            field=models.TextField(blank=True, null=True, verbose_name='Offer description'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='description_fi',
            field=models.TextField(blank=True, null=True, verbose_name='Offer description'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='description_sv',
            field=models.TextField(blank=True, null=True, verbose_name='Offer description'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='info_url',
            field=models.URLField(null=True, blank=True, verbose_name='Web link to offer'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='info_url_en',
            field=models.URLField(null=True, blank=True, verbose_name='Web link to offer'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='info_url_fi',
            field=models.URLField(null=True, blank=True, verbose_name='Web link to offer'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='info_url_sv',
            field=models.URLField(null=True, blank=True, verbose_name='Web link to offer'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='is_free',
            field=models.BooleanField(default=False, verbose_name='Is free'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='price',
            field=models.CharField(blank=True, max_length=512, verbose_name='Price'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='price_en',
            field=models.CharField(null=True, blank=True, max_length=512, verbose_name='Price'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='price_fi',
            field=models.CharField(null=True, blank=True, max_length=512, verbose_name='Price'),
        ),
        migrations.AlterField(
            model_name='offer',
            name='price_sv',
            field=models.CharField(null=True, blank=True, max_length=512, verbose_name='Price'),
        ),
        migrations.AlterField(
            model_name='organization',
            name='image',
            field=models.URLField(null=True, blank=True, verbose_name='Image URL'),
        ),
        migrations.AlterField(
            model_name='organization',
            name='name',
            field=models.CharField(db_index=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='organization',
            name='origin_id',
            field=models.CharField(db_index=True, blank=True, max_length=50, null=True, verbose_name='Origin ID'),
        ),
        migrations.AlterField(
            model_name='place',
            name='address_country',
            field=models.CharField(null=True, blank=True, max_length=2, verbose_name='Country'),
        ),
        migrations.AlterField(
            model_name='place',
            name='address_locality',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Address locality'),
        ),
        migrations.AlterField(
            model_name='place',
            name='address_locality_en',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Address locality'),
        ),
        migrations.AlterField(
            model_name='place',
            name='address_locality_fi',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Address locality'),
        ),
        migrations.AlterField(
            model_name='place',
            name='address_locality_sv',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Address locality'),
        ),
        migrations.AlterField(
            model_name='place',
            name='address_region',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Address region'),
        ),
        migrations.AlterField(
            model_name='place',
            name='contact_type',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Contact type'),
        ),
        migrations.AlterField(
            model_name='place',
            name='deleted',
            field=models.BooleanField(default=False, verbose_name='Deleted'),
        ),
        migrations.AlterField(
            model_name='place',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='place',
            name='description_en',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='place',
            name='description_fi',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='place',
            name='description_sv',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='place',
            name='email',
            field=models.EmailField(null=True, blank=True, max_length=254, verbose_name='E-mail'),
        ),
        migrations.AlterField(
            model_name='place',
            name='image',
            field=models.URLField(null=True, blank=True, verbose_name='Image URL'),
        ),
        migrations.AlterField(
            model_name='place',
            name='name',
            field=models.CharField(db_index=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='place',
            name='name_en',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='place',
            name='name_fi',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='place',
            name='name_sv',
            field=models.CharField(db_index=True, null=True, max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='place',
            name='origin_id',
            field=models.CharField(db_index=True, blank=True, max_length=50, null=True, verbose_name='Origin ID'),
        ),
        migrations.AlterField(
            model_name='place',
            name='post_office_box_num',
            field=models.CharField(null=True, blank=True, max_length=128, verbose_name='PO BOX'),
        ),
        migrations.AlterField(
            model_name='place',
            name='postal_code',
            field=models.CharField(null=True, blank=True, max_length=128, verbose_name='Postal code'),
        ),
        migrations.AlterField(
            model_name='place',
            name='publisher',
            field=models.ForeignKey(to='events.Organization', verbose_name='Publisher'),
        ),
        migrations.AlterField(
            model_name='place',
            name='street_address',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Street address'),
        ),
        migrations.AlterField(
            model_name='place',
            name='street_address_en',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Street address'),
        ),
        migrations.AlterField(
            model_name='place',
            name='street_address_fi',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Street address'),
        ),
        migrations.AlterField(
            model_name='place',
            name='street_address_sv',
            field=models.CharField(null=True, blank=True, max_length=255, verbose_name='Street address'),
        ),
        migrations.AlterField(
            model_name='place',
            name='telephone',
            field=models.CharField(null=True, blank=True, max_length=128, verbose_name='Telephone'),
        ),
        migrations.AlterField(
            model_name='place',
            name='telephone_en',
            field=models.CharField(null=True, blank=True, max_length=128, verbose_name='Telephone'),
        ),
        migrations.AlterField(
            model_name='place',
            name='telephone_fi',
            field=models.CharField(null=True, blank=True, max_length=128, verbose_name='Telephone'),
        ),
        migrations.AlterField(
            model_name='place',
            name='telephone_sv',
            field=models.CharField(null=True, blank=True, max_length=128, verbose_name='Telephone'),
        ),
    ]
