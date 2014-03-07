# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Language'
        db.create_table(u'events_language', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('name_fi', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('name_sv', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('name_en', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('editor', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('code', self.gf('django.db.models.fields.CharField')(max_length=6)),
        ))
        db.send_create_signal(u'events', ['Language'])

        # Adding model 'Organization'
        db.create_table(u'events_organization', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('editor', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'events', ['Organization'])

        # Adding model 'Category'
        db.create_table(u'events_category', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('custom_fields', self.gf(u'django_hstore.fields.DictionaryField')(null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('name_fi', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('name_sv', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('name_en', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('editor', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('same_as', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('parent_category', self.gf('mptt.fields.TreeForeignKey')(to=orm['events.Category'], null=True, blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('description_fi', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('description_sv', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('description_en', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            (u'lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
        ))
        db.send_create_signal(u'events', ['Category'])

        # Adding model 'PlacePostalAddress'
        db.create_table(u'events_placepostaladdress', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('editor', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
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
            ('availableLanguage', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Language'])),
        ))
        db.send_create_signal(u'events', ['PlacePostalAddress'])

        # Adding model 'Place'
        db.create_table(u'events_place', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('custom_fields', self.gf(u'django_hstore.fields.DictionaryField')(null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('name_fi', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('name_sv', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('name_en', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('editor', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('same_as', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')(null=True)),
            ('description_fi', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('description_sv', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('description_en', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('address', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.PlacePostalAddress'], null=True, blank=True)),
            ('publishing_principles', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('elevation', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=2, blank=True)),
            ('point', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=10, decimal_places=2, blank=True)),
            ('logo', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('map', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('contained_in', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
        ))
        db.send_create_signal(u'events', ['Place'])

        # Adding model 'Offer'
        db.create_table(u'events_offer', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('editor', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('available_at_or_from', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('price', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=8, decimal_places=2, blank=True)),
            ('price_currency', self.gf('django.db.models.fields.CharField')(max_length=3, null=True, blank=True)),
            ('seller', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('valid_from', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('valid_through', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('sku', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
        ))
        db.send_create_signal(u'events', ['Offer'])

        # Adding model 'Event'
        db.create_table(u'events_event', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('custom_fields', self.gf(u'django_hstore.fields.DictionaryField')(null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('name_fi', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('name_sv', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('name_en', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('editor', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('image', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('discussion_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('thumbnail_url', self.gf('django.db.models.fields.URLField')(max_length=200, null=True, blank=True)),
            ('same_as', self.gf('django.db.models.fields.CharField')(max_length=255, unique=True, null=True, blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')(null=True)),
            ('description_fi', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('description_sv', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('description_en', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('publisher', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Organization'])),
            ('location', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Place'], null=True, blank=True)),
            ('language', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Language'], null=True, blank=True)),
            ('start_date', self.gf('django.db.models.fields.DateField')(db_index=True, null=True, blank=True)),
            ('end_date', self.gf('django.db.models.fields.DateField')(db_index=True, null=True, blank=True)),
            ('duration', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('date_published', self.gf('django.db.models.fields.DateTimeField')()),
            ('previous_start_date', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('event_status', self.gf('django.db.models.fields.SmallIntegerField')(default=1)),
            ('typical_age_range', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('slug', self.gf('django.db.models.fields.SlugField')(max_length=50, blank=True)),
            ('super_event', self.gf('mptt.fields.TreeForeignKey')(blank=True, related_name='children', null=True, to=orm['events.Event'])),
            ('target_group', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            (u'lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            (u'level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
        ))
        db.send_create_signal(u'events', ['Event'])

        # Adding M2M table for field categories on 'Event'
        m2m_table_name = db.shorten_name(u'events_event_categories')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm[u'events.event'], null=False)),
            ('category', models.ForeignKey(orm[u'events.category'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'category_id'])

        # Adding M2M table for field offers on 'Event'
        m2m_table_name = db.shorten_name(u'events_event_offers')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm[u'events.event'], null=False)),
            ('offer', models.ForeignKey(orm[u'events.offer'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'offer_id'])


    def backwards(self, orm):
        # Deleting model 'Language'
        db.delete_table(u'events_language')

        # Deleting model 'Organization'
        db.delete_table(u'events_organization')

        # Deleting model 'Category'
        db.delete_table(u'events_category')

        # Deleting model 'PlacePostalAddress'
        db.delete_table(u'events_placepostaladdress')

        # Deleting model 'Place'
        db.delete_table(u'events_place')

        # Deleting model 'Offer'
        db.delete_table(u'events_offer')

        # Deleting model 'Event'
        db.delete_table(u'events_event')

        # Removing M2M table for field categories on 'Event'
        db.delete_table(db.shorten_name(u'events_event_categories'))

        # Removing M2M table for field offers on 'Event'
        db.delete_table(db.shorten_name(u'events_event_offers'))


    models = {
        u'events.category': {
            'Meta': {'object_name': 'Category'},
            'creator': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'custom_fields': (u'django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
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
            'categories': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['events.Category']", 'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'custom_fields': (u'django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'duration': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
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
            'previous_start_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.Organization']"}),
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
        u'events.language': {
            'Meta': {'object_name': 'Language'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '6'}),
            'creator': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
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
            'available_at_or_from': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
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
        u'events.organization': {
            'Meta': {'object_name': 'Organization'},
            'creator': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'thumbnail_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'events.place': {
            'Meta': {'object_name': 'Place'},
            'address': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.PlacePostalAddress']", 'null': 'True', 'blank': 'True'}),
            'contained_in': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'custom_fields': (u'django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
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
        u'events.placepostaladdress': {
            'Meta': {'object_name': 'PlacePostalAddress'},
            'address_country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'null': 'True', 'blank': 'True'}),
            'address_locality': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'address_region': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'availableLanguage': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['events.Language']"}),
            'contact_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'discussion_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
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