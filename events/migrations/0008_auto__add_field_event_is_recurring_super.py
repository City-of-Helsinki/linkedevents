# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Event.is_recurring_super'
        db.add_column('events_event', 'is_recurring_super',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Event.is_recurring_super'
        db.delete_column('events_event', 'is_recurring_super')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
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
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'blank': 'True', 'symmetrical': 'False', 'related_name': "'user_set'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True', 'symmetrical': 'False', 'related_name': "'user_set'"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True'})
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
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'events.event': {
            'Meta': {'object_name': 'Event'},
            'audience': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['auth.User']", 'related_name': "'events_event_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'custom_data': ('django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True', 'db_index': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'has_end_time': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'has_start_time': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'headline': ('django.db.models.fields.CharField', [], {'null': 'True', 'max_length': '255', 'db_index': 'True'}),
            'headline_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'headline_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'headline_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'is_recurring_super': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'keywords': ('django.db.models.fields.related.ManyToManyField', [], {'null': 'True', 'to': "orm['events.Keyword']", 'symmetrical': 'False', 'blank': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['auth.User']", 'related_name': "'events_event_modified_by'"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'to': "orm['events.Place']", 'blank': 'True'}),
            'location_extra_info': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '400'}),
            'location_extra_info_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '400'}),
            'location_extra_info_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '400'}),
            'location_extra_info_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '400'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '50', 'db_index': 'True'}),
            'provider': ('django.db.models.fields.CharField', [], {'null': 'True', 'max_length': '512'}),
            'provider_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '512'}),
            'provider_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '512'}),
            'provider_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '512'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Organization']", 'related_name': "'published_events'"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'secondary_headline': ('django.db.models.fields.CharField', [], {'null': 'True', 'max_length': '255', 'db_index': 'True'}),
            'secondary_headline_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'secondary_headline_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'secondary_headline_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'short_description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'short_description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'short_description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'short_description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True', 'db_index': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['events.Event']", 'related_name': "'sub_events'"}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'events.eventaggregate': {
            'Meta': {'object_name': 'EventAggregate'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'super_event': ('django.db.models.fields.related.OneToOneField', [], {'null': 'True', 'to': "orm['events.Event']", 'unique': 'True', 'related_name': "'aggregate'"})
        },
        'events.eventaggregatemember': {
            'Meta': {'object_name': 'EventAggregateMember'},
            'event': ('django.db.models.fields.related.ForeignKey', [], {'unique': 'True', 'to': "orm['events.Event']"}),
            'event_aggregate': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.EventAggregate']", 'related_name': "'members'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'events.eventlink': {
            'Meta': {'unique_together': "(('event', 'language', 'link'),)", 'object_name': 'EventLink'},
            'event': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Event']", 'related_name': "'external_links'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'link': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        'events.exportinfo': {
            'Meta': {'unique_together': "(('target_system', 'content_type', 'object_id'),)", 'object_name': 'ExportInfo'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_exported_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'object_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'target_id': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'target_system': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'})
        },
        'events.keyword': {
            'Meta': {'object_name': 'Keyword'},
            'aggregate': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'alt_labels': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.KeywordLabel']", 'blank': 'True', 'symmetrical': 'False', 'related_name': "'keywords'"}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['auth.User']", 'related_name': "'events_keyword_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['auth.User']", 'related_name': "'events_keyword_modified_by'"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '50', 'db_index': 'True'})
        },
        'events.keywordlabel': {
            'Meta': {'unique_together': "(('name', 'language'),)", 'object_name': 'KeywordLabel'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'})
        },
        'events.language': {
            'Meta': {'object_name': 'Language'},
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '6'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'name_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '20'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '20'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '20'})
        },
        'events.offer': {
            'Meta': {'object_name': 'Offer'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'event': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Event']", 'related_name': "'offers'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'info_url': ('django.db.models.fields.URLField', [], {'null': 'True', 'max_length': '200'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'is_free': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'price': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'price_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'}),
            'price_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'}),
            'price_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'})
        },
        'events.openinghoursspecification': {
            'Meta': {'object_name': 'OpeningHoursSpecification'},
            'closes': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'days_of_week': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'opens': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'place': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Place']", 'related_name': "'opening_hours'"}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'events.organization': {
            'Meta': {'object_name': 'Organization'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['auth.User']", 'related_name': "'events_organization_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['auth.User']", 'related_name': "'events_organization_modified_by'"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '50', 'db_index': 'True'})
        },
        'events.place': {
            'Meta': {'unique_together': "(('data_source', 'origin_id'),)", 'object_name': 'Place'},
            'address_country': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '2'}),
            'address_locality': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'address_locality_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'address_locality_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'address_locality_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'address_region': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'contact_type': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['auth.User']", 'related_name': "'events_place_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'custom_data': ('django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'null': 'True', 'blank': 'True', 'max_length': '75'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url': ('django.db.models.fields.URLField', [], {'null': 'True', 'max_length': '200'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['auth.User']", 'related_name': "'events_place_modified_by'"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '50', 'db_index': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'null': 'True', 'blank': 'True', 'to': "orm['events.Place']", 'related_name': "'children'"}),
            'position': ('django.contrib.gis.db.models.fields.PointField', [], {'null': 'True', 'srid': '3067', 'blank': 'True'}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Organization']"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'street_address': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'street_address_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'street_address_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'street_address_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'telephone': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'}),
            'telephone_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'}),
            'telephone_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'}),
            'telephone_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '128'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['events']