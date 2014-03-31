# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'PostalAddress'
        db.delete_table('events_postaladdress')

        # Deleting field 'Organization.date_modified'
        db.delete_column('events_organization', 'date_modified')

        # Deleting field 'Organization.thumbnail_url'
        db.delete_column('events_organization', 'thumbnail_url')

        # Deleting field 'Organization.discussion_url'
        db.delete_column('events_organization', 'discussion_url')

        # Deleting field 'Organization.date_created'
        db.delete_column('events_organization', 'date_created')

        # Adding field 'Organization.created_time'
        db.add_column('events_organization', 'created_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Organization.last_modified_time'
        db.add_column('events_organization', 'last_modified_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding index on 'Organization', fields ['origin_id']
        db.create_index('events_organization', ['origin_id'])

        # Deleting field 'Place.thumbnail_url'
        db.delete_column('events_place', 'thumbnail_url')

        # Deleting field 'Place.publishing_principles'
        db.delete_column('events_place', 'publishing_principles')

        # Deleting field 'Place.discussion_url'
        db.delete_column('events_place', 'discussion_url')

        # Deleting field 'Place.date_created'
        db.delete_column('events_place', 'date_created')

        # Deleting field 'Place.point'
        db.delete_column('events_place', 'point')

        # Deleting field 'Place.map'
        db.delete_column('events_place', 'map')

        # Deleting field 'Place.address'
        db.delete_column('events_place', 'address_id')

        # Deleting field 'Place.date_modified'
        db.delete_column('events_place', 'date_modified')

        # Deleting field 'Place.contained_in'
        db.delete_column('events_place', 'contained_in_id')

        # Deleting field 'Place.editor'
        db.delete_column('events_place', 'editor_id')

        # Deleting field 'Place.creator'
        db.delete_column('events_place', 'creator_id')

        # Deleting field 'Place.logo'
        db.delete_column('events_place', 'logo')

        # Adding field 'Place.created_time'
        db.add_column('events_place', 'created_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Place.last_modified_time'
        db.add_column('events_place', 'last_modified_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Place.parent'
        db.add_column('events_place', 'parent',
                      self.gf('mptt.fields.TreeForeignKey')(related_name='children', blank=True, to=orm['events.Place'], null=True),
                      keep_default=False)

        # Adding field 'Place.location'
        db.add_column('events_place', 'location',
                      self.gf('django.contrib.gis.db.models.fields.PointField')(blank=True, srid=3067, null=True),
                      keep_default=False)

        # Adding field 'Place.email'
        db.add_column('events_place', 'email',
                      self.gf('django.db.models.fields.EmailField')(blank=True, max_length=75, null=True),
                      keep_default=False)

        # Adding field 'Place.telephone'
        db.add_column('events_place', 'telephone',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=128, null=True),
                      keep_default=False)

        # Adding field 'Place.telephone_fi'
        db.add_column('events_place', 'telephone_fi',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=128, null=True),
                      keep_default=False)

        # Adding field 'Place.telephone_sv'
        db.add_column('events_place', 'telephone_sv',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=128, null=True),
                      keep_default=False)

        # Adding field 'Place.telephone_en'
        db.add_column('events_place', 'telephone_en',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=128, null=True),
                      keep_default=False)

        # Adding field 'Place.contact_type'
        db.add_column('events_place', 'contact_type',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.street_address'
        db.add_column('events_place', 'street_address',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.street_address_fi'
        db.add_column('events_place', 'street_address_fi',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.street_address_sv'
        db.add_column('events_place', 'street_address_sv',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.street_address_en'
        db.add_column('events_place', 'street_address_en',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.address_locality'
        db.add_column('events_place', 'address_locality',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.address_locality_fi'
        db.add_column('events_place', 'address_locality_fi',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.address_locality_sv'
        db.add_column('events_place', 'address_locality_sv',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.address_locality_en'
        db.add_column('events_place', 'address_locality_en',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.address_region'
        db.add_column('events_place', 'address_region',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Place.postal_code'
        db.add_column('events_place', 'postal_code',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=128, null=True),
                      keep_default=False)

        # Adding field 'Place.post_office_box_num'
        db.add_column('events_place', 'post_office_box_num',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=128, null=True),
                      keep_default=False)

        # Adding field 'Place.address_country'
        db.add_column('events_place', 'address_country',
                      self.gf('django.db.models.fields.CharField')(blank=True, max_length=2, null=True),
                      keep_default=False)

        # Adding field 'Place.deleted'
        db.add_column('events_place', 'deleted',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


        # Changing field 'Place.description'
        db.alter_column('events_place', 'description', self.gf('django.db.models.fields.TextField')(null=True))
        # Adding index on 'Place', fields ['origin_id']
        db.create_index('events_place', ['origin_id'])

        # Adding index on 'Place', fields ['same_as']
        db.create_index('events_place', ['same_as'])

        # Adding unique constraint on 'Place', fields ['data_source', 'origin_id']
        db.create_unique('events_place', ['data_source_id', 'origin_id'])

        # Deleting field 'Event.date_created'
        db.delete_column('events_event', 'date_created')

        # Deleting field 'Event.date_modified'
        db.delete_column('events_event', 'date_modified')

        # Deleting field 'Event.thumbnail_url'
        db.delete_column('events_event', 'thumbnail_url')

        # Deleting field 'Event.discussion_url'
        db.delete_column('events_event', 'discussion_url')

        # Adding field 'Event.created_time'
        db.add_column('events_event', 'created_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Event.last_modified_time'
        db.add_column('events_event', 'last_modified_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding index on 'Event', fields ['origin_id']
        db.create_index('events_event', ['origin_id'])

        # Deleting field 'Category.discussion_url'
        db.delete_column('events_category', 'discussion_url')

        # Deleting field 'Category.date_created'
        db.delete_column('events_category', 'date_created')

        # Deleting field 'Category.date_modified'
        db.delete_column('events_category', 'date_modified')

        # Deleting field 'Category.thumbnail_url'
        db.delete_column('events_category', 'thumbnail_url')

        # Adding field 'Category.created_time'
        db.add_column('events_category', 'created_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Category.last_modified_time'
        db.add_column('events_category', 'last_modified_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding index on 'Category', fields ['origin_id']
        db.create_index('events_category', ['origin_id'])

        # Deleting field 'Language.date_modified'
        db.delete_column('events_language', 'date_modified')

        # Deleting field 'Language.thumbnail_url'
        db.delete_column('events_language', 'thumbnail_url')

        # Deleting field 'Language.discussion_url'
        db.delete_column('events_language', 'discussion_url')

        # Deleting field 'Language.date_created'
        db.delete_column('events_language', 'date_created')

        # Adding field 'Language.created_time'
        db.add_column('events_language', 'created_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Language.last_modified_time'
        db.add_column('events_language', 'last_modified_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding index on 'Language', fields ['origin_id']
        db.create_index('events_language', ['origin_id'])


        # Changing field 'DataSource.event_url_template'
        db.alter_column('events_datasource', 'event_url_template', self.gf('django.db.models.fields.CharField')(max_length=200, null=True))
        # Deleting field 'Offer.date_modified'
        db.delete_column('events_offer', 'date_modified')

        # Deleting field 'Offer.thumbnail_url'
        db.delete_column('events_offer', 'thumbnail_url')

        # Deleting field 'Offer.discussion_url'
        db.delete_column('events_offer', 'discussion_url')

        # Deleting field 'Offer.date_created'
        db.delete_column('events_offer', 'date_created')

        # Adding field 'Offer.created_time'
        db.add_column('events_offer', 'created_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Offer.last_modified_time'
        db.add_column('events_offer', 'last_modified_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding index on 'Offer', fields ['origin_id']
        db.create_index('events_offer', ['origin_id'])

        # Deleting field 'Person.discussion_url'
        db.delete_column('events_person', 'discussion_url')

        # Deleting field 'Person.date_created'
        db.delete_column('events_person', 'date_created')

        # Deleting field 'Person.date_modified'
        db.delete_column('events_person', 'date_modified')

        # Deleting field 'Person.thumbnail_url'
        db.delete_column('events_person', 'thumbnail_url')

        # Adding field 'Person.created_time'
        db.add_column('events_person', 'created_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Person.last_modified_time'
        db.add_column('events_person', 'last_modified_time',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding index on 'Person', fields ['origin_id']
        db.create_index('events_person', ['origin_id'])


    def backwards(self, orm):
        # Removing index on 'Person', fields ['origin_id']
        db.delete_index('events_person', ['origin_id'])

        # Removing index on 'Offer', fields ['origin_id']
        db.delete_index('events_offer', ['origin_id'])

        # Removing index on 'Language', fields ['origin_id']
        db.delete_index('events_language', ['origin_id'])

        # Removing index on 'Category', fields ['origin_id']
        db.delete_index('events_category', ['origin_id'])

        # Removing index on 'Event', fields ['origin_id']
        db.delete_index('events_event', ['origin_id'])

        # Removing unique constraint on 'Place', fields ['data_source', 'origin_id']
        db.delete_unique('events_place', ['data_source_id', 'origin_id'])

        # Removing index on 'Place', fields ['same_as']
        db.delete_index('events_place', ['same_as'])

        # Removing index on 'Place', fields ['origin_id']
        db.delete_index('events_place', ['origin_id'])

        # Removing index on 'Organization', fields ['origin_id']
        db.delete_index('events_organization', ['origin_id'])

        # Adding model 'PostalAddress'
        db.create_table('events_postaladdress', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('post_office_box_num', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('modified_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name=u'events_postaladdress_modified_by', null=True)),
            ('street_address_fi', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('street_address_en', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('street_address_sv', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name=u'events_postaladdress_created_by', null=True)),
            ('available_language', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, to=orm['events.Language'], null=True)),
            ('data_source', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, to=orm['events.DataSource'], null=True)),
            ('telephone', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(blank=True, null=True, max_length=75)),
            ('origin_id', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('street_address', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('address_locality_en', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('telephone_fi', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('telephone_sv', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('address_locality_fi', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('telephone_en', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('address_region', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('contact_type', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('address_locality', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('postal_code', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('address_country', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=2)),
            ('address_locality_sv', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('image', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
        ))
        db.send_create_signal('events', ['PostalAddress'])

        # Adding field 'Organization.date_modified'
        db.add_column('events_organization', 'date_modified',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Organization.thumbnail_url'
        db.add_column('events_organization', 'thumbnail_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Organization.discussion_url'
        db.add_column('events_organization', 'discussion_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Organization.date_created'
        db.add_column('events_organization', 'date_created',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Deleting field 'Organization.created_time'
        db.delete_column('events_organization', 'created_time')

        # Deleting field 'Organization.last_modified_time'
        db.delete_column('events_organization', 'last_modified_time')

        # Adding field 'Place.thumbnail_url'
        db.add_column('events_place', 'thumbnail_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Place.publishing_principles'
        db.add_column('events_place', 'publishing_principles',
                      self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255),
                      keep_default=False)

        # Adding field 'Place.discussion_url'
        db.add_column('events_place', 'discussion_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Place.date_created'
        db.add_column('events_place', 'date_created',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Place.point'
        db.add_column('events_place', 'point',
                      self.gf('django.db.models.fields.DecimalField')(max_digits=10, blank=True, decimal_places=2, null=True),
                      keep_default=False)

        # Adding field 'Place.map'
        db.add_column('events_place', 'map',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Place.address'
        db.add_column('events_place', 'address',
                      self.gf('django.db.models.fields.related.ForeignKey')(blank=True, to=orm['events.PostalAddress'], null=True),
                      keep_default=False)

        # Adding field 'Place.date_modified'
        db.add_column('events_place', 'date_modified',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Place.contained_in'
        db.add_column('events_place', 'contained_in',
                      self.gf('mptt.fields.TreeForeignKey')(to=orm['events.Place'], blank=True, related_name='children', null=True),
                      keep_default=False)

        # Adding field 'Place.editor'
        db.add_column('events_place', 'editor',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Person'], blank=True, related_name='place_editors', null=True),
                      keep_default=False)

        # Adding field 'Place.creator'
        db.add_column('events_place', 'creator',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Person'], blank=True, related_name='place_creators', null=True),
                      keep_default=False)

        # Adding field 'Place.logo'
        db.add_column('events_place', 'logo',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Deleting field 'Place.created_time'
        db.delete_column('events_place', 'created_time')

        # Deleting field 'Place.last_modified_time'
        db.delete_column('events_place', 'last_modified_time')

        # Deleting field 'Place.parent'
        db.delete_column('events_place', 'parent_id')

        # Deleting field 'Place.location'
        db.delete_column('events_place', 'location')

        # Deleting field 'Place.email'
        db.delete_column('events_place', 'email')

        # Deleting field 'Place.telephone'
        db.delete_column('events_place', 'telephone')

        # Deleting field 'Place.telephone_fi'
        db.delete_column('events_place', 'telephone_fi')

        # Deleting field 'Place.telephone_sv'
        db.delete_column('events_place', 'telephone_sv')

        # Deleting field 'Place.telephone_en'
        db.delete_column('events_place', 'telephone_en')

        # Deleting field 'Place.contact_type'
        db.delete_column('events_place', 'contact_type')

        # Deleting field 'Place.street_address'
        db.delete_column('events_place', 'street_address')

        # Deleting field 'Place.street_address_fi'
        db.delete_column('events_place', 'street_address_fi')

        # Deleting field 'Place.street_address_sv'
        db.delete_column('events_place', 'street_address_sv')

        # Deleting field 'Place.street_address_en'
        db.delete_column('events_place', 'street_address_en')

        # Deleting field 'Place.address_locality'
        db.delete_column('events_place', 'address_locality')

        # Deleting field 'Place.address_locality_fi'
        db.delete_column('events_place', 'address_locality_fi')

        # Deleting field 'Place.address_locality_sv'
        db.delete_column('events_place', 'address_locality_sv')

        # Deleting field 'Place.address_locality_en'
        db.delete_column('events_place', 'address_locality_en')

        # Deleting field 'Place.address_region'
        db.delete_column('events_place', 'address_region')

        # Deleting field 'Place.postal_code'
        db.delete_column('events_place', 'postal_code')

        # Deleting field 'Place.post_office_box_num'
        db.delete_column('events_place', 'post_office_box_num')

        # Deleting field 'Place.address_country'
        db.delete_column('events_place', 'address_country')

        # Deleting field 'Place.deleted'
        db.delete_column('events_place', 'deleted')


        # Changing field 'Place.description'
        db.alter_column('events_place', 'description', self.gf('django.db.models.fields.TextField')(default=''))
        # Adding field 'Event.date_created'
        db.add_column('events_event', 'date_created',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Event.date_modified'
        db.add_column('events_event', 'date_modified',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Event.thumbnail_url'
        db.add_column('events_event', 'thumbnail_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Event.discussion_url'
        db.add_column('events_event', 'discussion_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Deleting field 'Event.created_time'
        db.delete_column('events_event', 'created_time')

        # Deleting field 'Event.last_modified_time'
        db.delete_column('events_event', 'last_modified_time')

        # Adding field 'Category.discussion_url'
        db.add_column('events_category', 'discussion_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Category.date_created'
        db.add_column('events_category', 'date_created',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Category.date_modified'
        db.add_column('events_category', 'date_modified',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Category.thumbnail_url'
        db.add_column('events_category', 'thumbnail_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Deleting field 'Category.created_time'
        db.delete_column('events_category', 'created_time')

        # Deleting field 'Category.last_modified_time'
        db.delete_column('events_category', 'last_modified_time')

        # Adding field 'Language.date_modified'
        db.add_column('events_language', 'date_modified',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Language.thumbnail_url'
        db.add_column('events_language', 'thumbnail_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Language.discussion_url'
        db.add_column('events_language', 'discussion_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Language.date_created'
        db.add_column('events_language', 'date_created',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Deleting field 'Language.created_time'
        db.delete_column('events_language', 'created_time')

        # Deleting field 'Language.last_modified_time'
        db.delete_column('events_language', 'last_modified_time')


        # Changing field 'DataSource.event_url_template'
        db.alter_column('events_datasource', 'event_url_template', self.gf('django.db.models.fields.CharField')(default='', max_length=200))
        # Adding field 'Offer.date_modified'
        db.add_column('events_offer', 'date_modified',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Offer.thumbnail_url'
        db.add_column('events_offer', 'thumbnail_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Offer.discussion_url'
        db.add_column('events_offer', 'discussion_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Offer.date_created'
        db.add_column('events_offer', 'date_created',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Deleting field 'Offer.created_time'
        db.delete_column('events_offer', 'created_time')

        # Deleting field 'Offer.last_modified_time'
        db.delete_column('events_offer', 'last_modified_time')

        # Adding field 'Person.discussion_url'
        db.add_column('events_person', 'discussion_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Adding field 'Person.date_created'
        db.add_column('events_person', 'date_created',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Person.date_modified'
        db.add_column('events_person', 'date_modified',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Person.thumbnail_url'
        db.add_column('events_person', 'thumbnail_url',
                      self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200),
                      keep_default=False)

        # Deleting field 'Person.created_time'
        db.delete_column('events_person', 'created_time')

        # Deleting field 'Person.last_modified_time'
        db.delete_column('events_person', 'last_modified_time')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True', 'symmetrical': 'False'})
        },
        'auth.permission': {
            'Meta': {'unique_together': "(('content_type', 'codename'),)", 'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'blank': 'True', 'max_length': '75'}),
            'first_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'blank': 'True', 'symmetrical': 'False', 'related_name': "'user_set'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True', 'symmetrical': 'False', 'related_name': "'user_set'"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'ordering': "('name',)", 'db_table': "'django_content_type'", 'object_name': 'ContentType'},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'events.category': {
            'Meta': {'object_name': 'Category'},
            'category_for': ('django.db.models.fields.SmallIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_category_created_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'category_creators'", 'blank': 'True', 'to': "orm['events.Person']", 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'category_editors'", 'blank': 'True', 'to': "orm['events.Person']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_category_modified_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'db_index': 'True', 'null': 'True'}),
            'parent_category': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'to': "orm['events.Category']", 'null': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'events.datasource': {
            'Meta': {'object_name': 'DataSource'},
            'event_url_template': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'events.event': {
            'Meta': {'object_name': 'Event'},
            'category': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.Category']", 'blank': 'True', 'symmetrical': 'False', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_event_created_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'creator': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.Person']", 'blank': 'True', 'symmetrical': 'False', 'related_name': "'event_creators'"}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'door_time': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'duration': ('django.db.models.fields.BigIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'event_editors'", 'blank': 'True', 'to': "orm['events.Person']", 'null': 'True'}),
            'end_date': ('django.db.models.fields.DateField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Language']", 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Place']", 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_event_modified_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'offers': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Offer']", 'null': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'db_index': 'True', 'null': 'True'}),
            'performer': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.Person']", 'blank': 'True', 'symmetrical': 'False'}),
            'previous_start_date': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'provider': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'event_providers'", 'blank': 'True', 'to': "orm['events.Organization']", 'null': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'event_publishers'", 'blank': 'True', 'to': "orm['events.Organization']", 'null': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'blank': 'True', 'max_length': '50'}),
            'start_date': ('django.db.models.fields.DateField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'related_name': "'sub_event'", 'blank': 'True', 'to': "orm['events.Event']", 'null': 'True'}),
            'target_group': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'typical_age_range': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'url_en': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'url_fi': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'url_sv': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'})
        },
        'events.language': {
            'Meta': {'object_name': 'Language'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '6'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_language_created_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_language_modified_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'db_index': 'True', 'null': 'True'})
        },
        'events.offer': {
            'Meta': {'object_name': 'Offer'},
            'available_at_or_from': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Place']", 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_offer_created_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_offer_modified_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'db_index': 'True', 'null': 'True'}),
            'price': ('django.db.models.fields.DecimalField', [], {'max_digits': '8', 'blank': 'True', 'decimal_places': '2', 'null': 'True'}),
            'price_currency': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '3', 'null': 'True'}),
            'seller_content_type': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['contenttypes.ContentType']", 'null': 'True'}),
            'seller_object_id': ('django.db.models.fields.PositiveIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'sku': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'})
        },
        'events.openinghoursspecification': {
            'Meta': {'object_name': 'OpeningHoursSpecification'},
            'closes': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'days_of_week': ('django.db.models.fields.SmallIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'opens': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'place': ('django.db.models.fields.related.OneToOneField', [], {'primary_key': 'True', 'related_name': "'opening_hour_specification'", 'to': "orm['events.Place']", 'unique': 'True'}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'})
        },
        'events.organization': {
            'Meta': {'object_name': 'Organization'},
            'base_IRI': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'compact_IRI_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_organization_created_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'organization_creators'", 'blank': 'True', 'to': "orm['events.Person']", 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'organization_editors'", 'blank': 'True', 'to': "orm['events.Person']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_organization_modified_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'db_index': 'True', 'null': 'True'})
        },
        'events.person': {
            'Meta': {'object_name': 'Person'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_person_created_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'person_creators'", 'blank': 'True', 'to': "orm['events.Person']", 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'person_editors'", 'blank': 'True', 'to': "orm['events.Person']", 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'blank': 'True', 'max_length': '75', 'null': 'True'}),
            'family_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'member_of': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Organization']", 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_person_modified_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'db_index': 'True', 'null': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'})
        },
        'events.place': {
            'Meta': {'unique_together': "(('data_source', 'origin_id'),)", 'object_name': 'Place'},
            'address_country': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '2', 'null': 'True'}),
            'address_locality': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'address_locality_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'address_locality_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'address_locality_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'address_region': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'contact_type': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_place_created_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'blank': 'True', 'max_length': '75', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.contrib.gis.db.models.fields.PointField', [], {'blank': 'True', 'srid': '3067', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_place_modified_by'", 'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'db_index': 'True', 'null': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'related_name': "'children'", 'blank': 'True', 'to': "orm['events.Place']", 'null': 'True'}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '128', 'null': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '128', 'null': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'db_index': 'True', 'null': 'True'}),
            'street_address': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'street_address_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'street_address_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'street_address_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'telephone': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '128', 'null': 'True'}),
            'telephone_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '128', 'null': 'True'}),
            'telephone_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '128', 'null': 'True'}),
            'telephone_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '128', 'null': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['events']