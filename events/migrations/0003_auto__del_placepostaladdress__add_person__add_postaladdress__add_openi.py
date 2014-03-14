# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'PlacePostalAddress'
        db.delete_table(u'events_placepostaladdress')

        # Adding model 'Person'
        db.create_table(u'events_person', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('family_name', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, null=True, blank=True)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('password', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('member_of', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Organization'], null=True, blank=True)),
            ('role', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
        ))
        db.send_create_signal(u'events', ['Person'])

        # Adding model 'PostalAddress'
        db.create_table(u'events_postaladdress', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, null=True, blank=True)),
            ('telephone', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('contact_type', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('street_address', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('address_locality', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('address_region', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('postal_code', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('post_office_box_num', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('address_country', self.gf('django.db.models.fields.CharField')(max_length=2, null=True, blank=True)),
            ('available_language', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Language'])),
        ))
        db.send_create_signal(u'events', ['PostalAddress'])

        # Adding model 'OpeningHoursSpecification'
        db.create_table(u'events_openinghoursspecification', (
            ('place', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['events.Place'], unique=True, primary_key=True)),
            ('opens', self.gf('django.db.models.fields.TimeField')(null=True, blank=True)),
            ('closes', self.gf('django.db.models.fields.TimeField')(null=True, blank=True)),
            ('days_of_week', self.gf('django.db.models.fields.SmallIntegerField')(null=True, blank=True)),
            ('valid_from', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('valid_through', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'events', ['OpeningHoursSpecification'])

        # Adding model 'GeoShape'
        db.create_table(u'events_geoshape', (
            ('place', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['events.Place'], unique=True, primary_key=True)),
            ('elevation', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('box', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('circle', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('line', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('polygon', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'events', ['GeoShape'])

        # Adding model 'GeoCoordinates'
        db.create_table(u'events_geocoordinates', (
            ('place', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['events.Place'], unique=True, primary_key=True)),
            ('elevation', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('latitude', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('longitude', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
        ))
        db.send_create_signal(u'events', ['GeoCoordinates'])

        # Deleting field 'Place.creator'
        db.delete_column(u'events_place', 'creator')

        # Deleting field 'Place.contained_in'
        db.delete_column(u'events_place', 'contained_in')

        # Deleting field 'Place.editor'
        db.delete_column(u'events_place', 'editor')


        # Changing field 'Place.address'
        db.alter_column(u'events_place', 'address_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.PostalAddress'], null=True))
        # Deleting field 'Event.creator'
        db.delete_column(u'events_event', 'creator')

        # Deleting field 'Event.editor'
        db.delete_column(u'events_event', 'editor')

        # Adding field 'Event.door_time'
        db.add_column(u'events_event', 'door_time',
                      self.gf('django.db.models.fields.TimeField')(null=True, blank=True),
                      keep_default=False)

        # Adding field 'Event.performer'
        db.add_column(u'events_event', 'performer',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Person'], null=True, blank=True),
                      keep_default=False)

        # Removing M2M table for field categories on 'Event'
        db.delete_table(db.shorten_name(u'events_event_categories'))

        # Adding M2M table for field category on 'Event'
        m2m_table_name = db.shorten_name(u'events_event_category')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm[u'events.event'], null=False)),
            ('category', models.ForeignKey(orm[u'events.category'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'category_id'])

        # Deleting field 'Offer.available_at_or_from'
        db.delete_column(u'events_offer', 'available_at_or_from')

        # Deleting field 'Offer.creator'
        db.delete_column(u'events_offer', 'creator')

        # Deleting field 'Offer.editor'
        db.delete_column(u'events_offer', 'editor')

        # Deleting field 'Category.creator'
        db.delete_column(u'events_category', 'creator')

        # Deleting field 'Category.editor'
        db.delete_column(u'events_category', 'editor')

        # Deleting field 'Organization.creator'
        db.delete_column(u'events_organization', 'creator')

        # Deleting field 'Organization.editor'
        db.delete_column(u'events_organization', 'editor')

        # Adding field 'Organization.base_IRI'
        db.add_column(u'events_organization', 'base_IRI',
                      self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Organization.compact_IRI_name'
        db.add_column(u'events_organization', 'compact_IRI_name',
                      self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True),
                      keep_default=False)

        # Deleting field 'Language.creator'
        db.delete_column(u'events_language', 'creator')

        # Deleting field 'Language.editor'
        db.delete_column(u'events_language', 'editor')


    def backwards(self, orm):
        # Adding model 'PlacePostalAddress'
        db.create_table(u'events_placepostaladdress', (
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('contact_type', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('street_address', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('address_region', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('telephone', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('postal_code', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('address_locality', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('editor', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('post_office_box_num', self.gf('django.db.models.fields.CharField')(max_length=128, null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('address_country', self.gf('django.db.models.fields.CharField')(max_length=2, null=True, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, null=True, blank=True)),
            ('availableLanguage', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Language'])),
        ))
        db.send_create_signal(u'events', ['PlacePostalAddress'])

        # Deleting model 'Person'
        db.delete_table(u'events_person')

        # Deleting model 'PostalAddress'
        db.delete_table(u'events_postaladdress')

        # Deleting model 'OpeningHoursSpecification'
        db.delete_table(u'events_openinghoursspecification')

        # Deleting model 'GeoShape'
        db.delete_table(u'events_geoshape')

        # Deleting model 'GeoCoordinates'
        db.delete_table(u'events_geocoordinates')

        # Adding field 'Place.creator'
        db.add_column(u'events_place', 'creator',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Place.contained_in'
        db.add_column(u'events_place', 'contained_in',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Place.editor'
        db.add_column(u'events_place', 'editor',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)


        # Changing field 'Place.address'
        db.alter_column(u'events_place', 'address_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.PlacePostalAddress'], null=True))
        # Adding field 'Event.creator'
        db.add_column(u'events_event', 'creator',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Event.editor'
        db.add_column(u'events_event', 'editor',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Deleting field 'Event.door_time'
        db.delete_column(u'events_event', 'door_time')

        # Deleting field 'Event.performer'
        db.delete_column(u'events_event', 'performer_id')

        # Adding M2M table for field categories on 'Event'
        m2m_table_name = db.shorten_name(u'events_event_categories')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm[u'events.event'], null=False)),
            ('category', models.ForeignKey(orm[u'events.category'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'category_id'])

        # Removing M2M table for field category on 'Event'
        db.delete_table(db.shorten_name(u'events_event_category'))

        # Adding field 'Offer.available_at_or_from'
        db.add_column(u'events_offer', 'available_at_or_from',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Offer.creator'
        db.add_column(u'events_offer', 'creator',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Offer.editor'
        db.add_column(u'events_offer', 'editor',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Category.creator'
        db.add_column(u'events_category', 'creator',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Category.editor'
        db.add_column(u'events_category', 'editor',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Organization.creator'
        db.add_column(u'events_organization', 'creator',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Organization.editor'
        db.add_column(u'events_organization', 'editor',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Deleting field 'Organization.base_IRI'
        db.delete_column(u'events_organization', 'base_IRI')

        # Deleting field 'Organization.compact_IRI_name'
        db.delete_column(u'events_organization', 'compact_IRI_name')

        # Adding field 'Language.creator'
        db.add_column(u'events_language', 'creator',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Language.editor'
        db.add_column(u'events_language', 'editor',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True),
                      keep_default=False)


    models = {
        u'events.category': {
            'Meta': {'object_name': 'Category'},
            'custom_fields': (u'django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            u'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'parent_category': ('mptt.fields.TreeForeignKey', [], {'to': u"orm['events.Category']", 'null': 'True', 'blank': 'True'}),
            u'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            u'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        u'events.event': {
            'Meta': {'object_name': 'Event'},
            'category': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['events.Category']", 'null': 'True', 'blank': 'True'}),
            'custom_fields': (u'django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'door_time': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'duration': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'end_date': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.Language']", 'null': 'True', 'blank': 'True'}),
            u'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            u'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.Place']", 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'offers': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['events.Offer']", 'symmetrical': 'False', 'blank': 'True'}),
            'performer': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.Person']", 'null': 'True', 'blank': 'True'}),
            'previous_start_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.Organization']", 'null': 'True', 'blank': 'True'}),
            u'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'max_length': '255', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'blank': 'True'}),
            'start_date': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': u"orm['events.Event']"}),
            'target_group': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            u'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'typical_age_range': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'})
        },
        u'events.geocoordinates': {
            'Meta': {'object_name': 'GeoCoordinates'},
            'elevation': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'latitude': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'longitude': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'place': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['events.Place']", 'unique': 'True', 'primary_key': 'True'})
        },
        u'events.geoshape': {
            'Meta': {'object_name': 'GeoShape'},
            'box': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'circle': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'elevation': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'line': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'place': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['events.Place']", 'unique': 'True', 'primary_key': 'True'}),
            'polygon': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        u'events.language': {
            'Meta': {'object_name': 'Language'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '6'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'events.offer': {
            'Meta': {'object_name': 'Offer'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'price': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '8', 'decimal_places': '2', 'blank': 'True'}),
            'price_currency': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'True', 'blank': 'True'}),
            'seller': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'sku': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        u'events.openinghoursspecification': {
            'Meta': {'object_name': 'OpeningHoursSpecification'},
            'closes': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'days_of_week': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'opens': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'place': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['events.Place']", 'unique': 'True', 'primary_key': 'True'}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        u'events.organization': {
            'Meta': {'object_name': 'Organization'},
            'base_IRI': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'compact_IRI_name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'events.person': {
            'Meta': {'object_name': 'Person'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True', 'blank': 'True'}),
            'family_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'member_of': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.Organization']", 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'role': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'})
        },
        u'events.place': {
            'Meta': {'object_name': 'Place'},
            'address': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.PostalAddress']", 'null': 'True', 'blank': 'True'}),
            'custom_fields': (u'django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'elevation': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'logo': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'map': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'point': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '10', 'decimal_places': '2', 'blank': 'True'}),
            'publishing_principles': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'events.postaladdress': {
            'Meta': {'object_name': 'PostalAddress'},
            'address_country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True', 'blank': 'True'}),
            'address_locality': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'address_region': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'available_language': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.Language']"}),
            'contact_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'street_address': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'telephone': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['events']