# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'DataSource'
        db.create_table('events_datasource', (
            ('id', self.gf('django.db.models.fields.CharField')(primary_key=True, max_length=100)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('event_url_template', self.gf('django.db.models.fields.CharField')(null=True, max_length=200)),
        ))
        db.send_create_signal('events', ['DataSource'])

        # Adding model 'Language'
        db.create_table('events_language', (
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_language_created_by', null=True)),
            ('modified_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_language_modified_by', null=True)),
            ('data_source', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.DataSource'], blank=True, null=True)),
            ('origin_id', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=255)),
            ('name_fi', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name_sv', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name_en', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('image', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('created_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('last_modified_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('id', self.gf('django.db.models.fields.CharField')(primary_key=True, max_length=6)),
        ))
        db.send_create_signal('events', ['Language'])

        # Adding model 'KeywordLabel'
        db.create_table('events_keywordlabel', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_keywordlabel_created_by', null=True)),
            ('modified_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_keywordlabel_modified_by', null=True)),
            ('data_source', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.DataSource'], blank=True, null=True)),
            ('origin_id', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=255)),
            ('image', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('created_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('last_modified_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('language', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Language'])),
        ))
        db.send_create_signal('events', ['KeywordLabel'])

        # Adding unique constraint on 'KeywordLabel', fields ['name', 'language']
        db.create_unique('events_keywordlabel', ['name', 'language_id'])

        # Adding model 'Keyword'
        db.create_table('events_keyword', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_keyword_created_by', null=True)),
            ('modified_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_keyword_modified_by', null=True)),
            ('data_source', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.DataSource'], blank=True, null=True)),
            ('origin_id', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('custom_fields', self.gf('django_hstore.fields.DictionaryField')(blank=True, null=True)),
            ('name', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=255)),
            ('name_fi', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name_sv', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name_en', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('image', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('created_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('last_modified_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('url', self.gf('django.db.models.fields.CharField')(db_index=True, default='unknown', max_length=255)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('description_fi', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('description_sv', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('description_en', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('same_as', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('aggregate', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('events', ['Keyword'])

        # Adding M2M table for field alt_labels on 'Keyword'
        m2m_table_name = db.shorten_name('events_keyword_alt_labels')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('keyword', models.ForeignKey(orm['events.keyword'], null=False)),
            ('keywordlabel', models.ForeignKey(orm['events.keywordlabel'], null=False))
        ))
        db.create_unique(m2m_table_name, ['keyword_id', 'keywordlabel_id'])

        # Adding model 'Place'
        db.create_table('events_place', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_place_created_by', null=True)),
            ('modified_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_place_modified_by', null=True)),
            ('data_source', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.DataSource'], blank=True, null=True)),
            ('origin_id', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('custom_fields', self.gf('django_hstore.fields.DictionaryField')(blank=True, null=True)),
            ('name', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=255)),
            ('name_fi', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name_sv', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name_en', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('image', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('created_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('last_modified_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('same_as', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('url', self.gf('django.db.models.fields.URLField')(blank=True, max_length=200)),
            ('url_fi', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('url_sv', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('url_en', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('description_fi', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('description_sv', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('description_en', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('parent', self.gf('mptt.fields.TreeForeignKey')(to=orm['events.Place'], blank=True, related_name='children', null=True)),
            ('location', self.gf('django.contrib.gis.db.models.fields.PointField')(srid=3067, blank=True, null=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(blank=True, null=True, max_length=75)),
            ('telephone', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('telephone_fi', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('telephone_sv', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('telephone_en', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('contact_type', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('street_address', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('street_address_fi', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('street_address_sv', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('street_address_en', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('address_locality', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('address_locality_fi', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('address_locality_sv', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('address_locality_en', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('address_region', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('postal_code', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('post_office_box_num', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=128)),
            ('address_country', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=2)),
            ('deleted', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
        ))
        db.send_create_signal('events', ['Place'])

        # Adding unique constraint on 'Place', fields ['data_source', 'origin_id']
        db.create_unique('events_place', ['data_source_id', 'origin_id'])

        # Adding model 'OpeningHoursSpecification'
        db.create_table('events_openinghoursspecification', (
            ('place', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['events.Place'], unique=True, primary_key=True, related_name='opening_hour_specification')),
            ('opens', self.gf('django.db.models.fields.TimeField')(blank=True, null=True)),
            ('closes', self.gf('django.db.models.fields.TimeField')(blank=True, null=True)),
            ('days_of_week', self.gf('django.db.models.fields.SmallIntegerField')(blank=True, null=True)),
            ('valid_from', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('valid_through', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
        ))
        db.send_create_signal('events', ['OpeningHoursSpecification'])

        # Adding model 'Event'
        db.create_table('events_event', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_event_created_by', null=True)),
            ('modified_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, related_name='events_event_modified_by', null=True)),
            ('data_source', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.DataSource'], blank=True, null=True)),
            ('origin_id', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('custom_fields', self.gf('django_hstore.fields.DictionaryField')(blank=True, null=True)),
            ('name', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=255)),
            ('name_fi', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name_sv', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('name_en', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('image', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('created_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('last_modified_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('url', self.gf('django.db.models.fields.URLField')(blank=True, max_length=200)),
            ('url_fi', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('url_sv', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('url_en', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('description_fi', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('description_sv', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('description_en', self.gf('django.db.models.fields.TextField')(blank=True, null=True)),
            ('date_published', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('event_status', self.gf('django.db.models.fields.SmallIntegerField')(default=1)),
            ('location', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Place'], blank=True, null=True)),
            ('location_extra_info', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=400)),
            ('location_extra_info_fi', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=400)),
            ('location_extra_info_sv', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=400)),
            ('location_extra_info_en', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=400)),
            ('start_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True, db_index=True)),
            ('end_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True, db_index=True)),
            ('super_event', self.gf('mptt.fields.TreeForeignKey')(to=orm['events.Event'], blank=True, related_name='sub_event', null=True)),
            ('target_group', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('lft', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('rght', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('tree_id', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('level', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
        ))
        db.send_create_signal('events', ['Event'])

        # Adding M2M table for field keywords on 'Event'
        m2m_table_name = db.shorten_name('events_event_keywords')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm['events.event'], null=False)),
            ('keyword', models.ForeignKey(orm['events.keyword'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'keyword_id'])

        # Adding model 'ExportInfo'
        db.create_table('events_exportinfo', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('target_id', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('target_system', self.gf('django.db.models.fields.CharField')(db_index=True, blank=True, null=True, max_length=255)),
            ('last_exported_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal('events', ['ExportInfo'])

        # Adding unique constraint on 'ExportInfo', fields ['target_system', 'content_type', 'object_id']
        db.create_unique('events_exportinfo', ['target_system', 'content_type_id', 'object_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'ExportInfo', fields ['target_system', 'content_type', 'object_id']
        db.delete_unique('events_exportinfo', ['target_system', 'content_type_id', 'object_id'])

        # Removing unique constraint on 'Place', fields ['data_source', 'origin_id']
        db.delete_unique('events_place', ['data_source_id', 'origin_id'])

        # Removing unique constraint on 'KeywordLabel', fields ['name', 'language']
        db.delete_unique('events_keywordlabel', ['name', 'language_id'])

        # Deleting model 'DataSource'
        db.delete_table('events_datasource')

        # Deleting model 'Language'
        db.delete_table('events_language')

        # Deleting model 'KeywordLabel'
        db.delete_table('events_keywordlabel')

        # Deleting model 'Keyword'
        db.delete_table('events_keyword')

        # Removing M2M table for field alt_labels on 'Keyword'
        db.delete_table(db.shorten_name('events_keyword_alt_labels'))

        # Deleting model 'Place'
        db.delete_table('events_place')

        # Deleting model 'OpeningHoursSpecification'
        db.delete_table('events_openinghoursspecification')

        # Deleting model 'Event'
        db.delete_table('events_event')

        # Removing M2M table for field keywords on 'Event'
        db.delete_table(db.shorten_name('events_event_keywords'))

        # Deleting model 'ExportInfo'
        db.delete_table('events_exportinfo')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True', 'symmetrical': 'False'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
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
            'Meta': {'db_table': "'django_content_type'", 'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType'},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'events.datasource': {
            'Meta': {'object_name': 'DataSource'},
            'event_url_template': ('django.db.models.fields.CharField', [], {'null': 'True', 'max_length': '200'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'events.event': {
            'Meta': {'object_name': 'Event'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_event_created_by'", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'blank': 'True', 'null': 'True'}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'keywords': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.Keyword']", 'blank': 'True', 'symmetrical': 'False', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Place']", 'blank': 'True', 'null': 'True'}),
            'location_extra_info': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '400'}),
            'location_extra_info_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '400'}),
            'location_extra_info_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '400'}),
            'location_extra_info_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '400'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_event_modified_by'", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'to': "orm['events.Event']", 'blank': 'True', 'related_name': "'sub_event'", 'null': 'True'}),
            'target_group': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'url_en': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'url_fi': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'url_sv': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'})
        },
        'events.exportinfo': {
            'Meta': {'unique_together': "(('target_system', 'content_type', 'object_id'),)", 'object_name': 'ExportInfo'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_exported_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'target_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'target_system': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'})
        },
        'events.keyword': {
            'Meta': {'object_name': 'Keyword'},
            'aggregate': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'alt_labels': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.KeywordLabel']", 'blank': 'True', 'symmetrical': 'False', 'related_name': "'keywords'"}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_keyword_created_by'", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'blank': 'True', 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_keyword_modified_by'", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'same_as': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'url': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'default': "'unknown'", 'max_length': '255'})
        },
        'events.keywordlabel': {
            'Meta': {'unique_together': "(('name', 'language'),)", 'object_name': 'KeywordLabel'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_keywordlabel_created_by'", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_keywordlabel_modified_by'", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'})
        },
        'events.language': {
            'Meta': {'object_name': 'Language'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_language_created_by'", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '6'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_language_modified_by'", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'})
        },
        'events.openinghoursspecification': {
            'Meta': {'object_name': 'OpeningHoursSpecification'},
            'closes': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'days_of_week': ('django.db.models.fields.SmallIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'opens': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'place': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['events.Place']", 'unique': 'True', 'primary_key': 'True', 'related_name': "'opening_hour_specification'"}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'})
        },
        'events.place': {
            'Meta': {'unique_together': "(('data_source', 'origin_id'),)", 'object_name': 'Place'},
            'address_country': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '2'}),
            'address_locality': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'address_locality_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'address_locality_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'address_locality_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'address_region': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'contact_type': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_place_created_by'", 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'blank': 'True', 'null': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'blank': 'True', 'null': 'True', 'max_length': '75'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3067', 'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'blank': 'True', 'related_name': "'events_place_modified_by'", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'to': "orm['events.Place']", 'blank': 'True', 'related_name': "'children'", 'null': 'True'}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'street_address': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'street_address_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'street_address_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'street_address_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'telephone': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'telephone_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'telephone_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'telephone_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'url_en': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'url_fi': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'url_sv': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'})
        }
    }

    complete_apps = ['events']