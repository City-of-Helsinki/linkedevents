# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'EventAggregateMember'
        db.create_table('events_eventaggregatemember', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('event_aggregate', self.gf('django.db.models.fields.related.ForeignKey')(related_name='members', to=orm['events.EventAggregate'])),
            ('event', self.gf('django.db.models.fields.related.ForeignKey')(unique=True, to=orm['events.Event'])),
        ))
        db.send_create_signal('events', ['EventAggregateMember'])

        # Adding model 'EventAggregate'
        db.create_table('events_eventaggregate', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('super_event', self.gf('django.db.models.fields.related.OneToOneField')(related_name='aggregate', unique=True, to=orm['events.Event'], null=True)),
        ))
        db.send_create_signal('events', ['EventAggregate'])


    def backwards(self, orm):
        # Deleting model 'EventAggregateMember'
        db.delete_table('events_eventaggregatemember')

        # Deleting model 'EventAggregate'
        db.delete_table('events_eventaggregate')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['auth.Permission']", 'blank': 'True'})
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
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'user_set'", 'to': "orm['auth.Group']", 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'user_set'", 'to': "orm['auth.Permission']", 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'ordering': "('name',)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'events.datasource': {
            'Meta': {'object_name': 'DataSource'},
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'events.event': {
            'Meta': {'object_name': 'Event'},
            'audience': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_event_created_by'", 'to': "orm['auth.User']", 'blank': 'True', 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_data': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'has_end_time': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'has_start_time': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'headline': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True', 'null': 'True'}),
            'headline_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'headline_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'headline_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'info_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'keywords': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['events.Keyword']", 'blank': 'True', 'null': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_event_modified_by'", 'to': "orm['auth.User']", 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Place']", 'blank': 'True', 'null': 'True'}),
            'location_extra_info': ('django.db.models.fields.CharField', [], {'max_length': '400', 'blank': 'True', 'null': 'True'}),
            'location_extra_info_en': ('django.db.models.fields.CharField', [], {'max_length': '400', 'blank': 'True', 'null': 'True'}),
            'location_extra_info_fi': ('django.db.models.fields.CharField', [], {'max_length': '400', 'blank': 'True', 'null': 'True'}),
            'location_extra_info_sv': ('django.db.models.fields.CharField', [], {'max_length': '400', 'blank': 'True', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '50', 'blank': 'True', 'null': 'True'}),
            'provider': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True'}),
            'provider_en': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True', 'null': 'True'}),
            'provider_fi': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True', 'null': 'True'}),
            'provider_sv': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True', 'null': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'published_events'", 'to': "orm['events.Organization']"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'secondary_headline': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True', 'null': 'True'}),
            'secondary_headline_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'secondary_headline_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'secondary_headline_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'short_description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'short_description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'short_description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'short_description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'related_name': "'sub_events'", 'to': "orm['events.Event']", 'blank': 'True', 'null': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'events.eventaggregate': {
            'Meta': {'object_name': 'EventAggregate'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'super_event': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'aggregate'", 'unique': 'True', 'to': "orm['events.Event']", 'null': 'True'})
        },
        'events.eventaggregatemember': {
            'Meta': {'object_name': 'EventAggregateMember'},
            'event': ('django.db.models.fields.related.ForeignKey', [], {'unique': 'True', 'to': "orm['events.Event']"}),
            'event_aggregate': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'members'", 'to': "orm['events.EventAggregate']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'events.eventlink': {
            'Meta': {'unique_together': "(('event', 'language', 'link'),)", 'object_name': 'EventLink'},
            'event': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'external_links'", 'to': "orm['events.Event']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'link': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        'events.exportinfo': {
            'Meta': {'unique_together': "(('target_system', 'content_type', 'object_id'),)", 'object_name': 'ExportInfo'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_exported_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'object_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'target_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'target_system': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'})
        },
        'events.keyword': {
            'Meta': {'object_name': 'Keyword'},
            'aggregate': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'alt_labels': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'keywords'", 'to': "orm['events.KeywordLabel']", 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_keyword_created_by'", 'to': "orm['auth.User']", 'blank': 'True', 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_keyword_modified_by'", 'to': "orm['auth.User']", 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '50', 'blank': 'True', 'null': 'True'})
        },
        'events.keywordlabel': {
            'Meta': {'unique_together': "(('name', 'language'),)", 'object_name': 'KeywordLabel'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'events.language': {
            'Meta': {'object_name': 'Language'},
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '6'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True', 'null': 'True'})
        },
        'events.offer': {
            'Meta': {'object_name': 'Offer'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'event': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'offers'", 'to': "orm['events.Event']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'info_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'is_free': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'price': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'price_en': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'price_fi': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'price_sv': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'})
        },
        'events.openinghoursspecification': {
            'Meta': {'object_name': 'OpeningHoursSpecification'},
            'closes': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'days_of_week': ('django.db.models.fields.SmallIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'opens': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'place': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'opening_hours'", 'to': "orm['events.Place']"}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'})
        },
        'events.organization': {
            'Meta': {'object_name': 'Organization'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_organization_created_by'", 'to': "orm['auth.User']", 'blank': 'True', 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_organization_modified_by'", 'to': "orm['auth.User']", 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '50', 'blank': 'True', 'null': 'True'})
        },
        'events.place': {
            'Meta': {'unique_together': "(('data_source', 'origin_id'),)", 'object_name': 'Place'},
            'address_country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True', 'null': 'True'}),
            'address_locality': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'address_locality_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'address_locality_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'address_locality_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'address_region': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'contact_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_place_created_by'", 'to': "orm['auth.User']", 'blank': 'True', 'null': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_data': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'info_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'events_place_modified_by'", 'to': "orm['auth.User']", 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '50', 'blank': 'True', 'null': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'related_name': "'children'", 'to': "orm['events.Place']", 'blank': 'True', 'null': 'True'}),
            'position': ('django.contrib.gis.db.models.fields.PointField', [], {'blank': 'True', 'null': 'True', 'srid': '3067'}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Organization']"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'street_address': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'street_address_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'street_address_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'street_address_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'telephone': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'telephone_en': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'telephone_fi': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'telephone_sv': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['events']