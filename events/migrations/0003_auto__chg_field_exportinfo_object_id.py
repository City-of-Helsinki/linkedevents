# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'ExportInfo.object_id'
        db.alter_column('events_exportinfo', 'object_id', self.gf('django.db.models.fields.CharField')(max_length=50))

    def backwards(self, orm):

        # Changing field 'ExportInfo.object_id'
        db.alter_column('events_exportinfo', 'object_id', self.gf('django.db.models.fields.PositiveIntegerField')())

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'symmetrical': 'False', 'to': "orm['auth.Permission']"})
        },
        'auth.permission': {
            'Meta': {'object_name': 'Permission', 'unique_together': "(('content_type', 'codename'),)", 'ordering': "('content_type__app_label', 'content_type__model', 'codename')"},
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
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'user_set'", 'symmetrical': 'False', 'to': "orm['auth.Group']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'user_set'", 'symmetrical': 'False', 'to': "orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'object_name': 'ContentType', 'unique_together': "(('app_label', 'model'),)", 'ordering': "('name',)", 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'events.datasource': {
            'Meta': {'object_name': 'DataSource'},
            'id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'events.event': {
            'Meta': {'object_name': 'Event'},
            'audience': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'events_event_created_by'", 'null': 'True', 'to': "orm['auth.User']"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_data': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'has_end_time': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'has_start_time': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'info_url': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'keywords': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'symmetrical': 'False', 'null': 'True', 'to': "orm['events.Keyword']"}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'events_event_modified_by'", 'null': 'True', 'to': "orm['auth.User']"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.Place']"}),
            'location_extra_info': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '400', 'null': 'True'}),
            'location_extra_info_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '400', 'null': 'True'}),
            'location_extra_info_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '400', 'null': 'True'}),
            'location_extra_info_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '400', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '50', 'null': 'True', 'db_index': 'True'}),
            'provider': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'provided_events'", 'null': 'True', 'to': "orm['events.Organization']"}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'published_events'", 'to': "orm['events.Organization']"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'short_description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'short_description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'short_description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'short_description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'related_name': "'sub_events'", 'null': 'True', 'to': "orm['events.Event']"}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'events.eventlink': {
            'Meta': {'object_name': 'EventLink', 'unique_together': "(('event', 'language', 'link'),)"},
            'event': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'external_links'", 'to': "orm['events.Event']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'link': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'})
        },
        'events.exportinfo': {
            'Meta': {'object_name': 'ExportInfo', 'unique_together': "(('target_system', 'content_type', 'object_id'),)"},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_exported_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'object_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'target_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'target_system': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'})
        },
        'events.keyword': {
            'Meta': {'object_name': 'Keyword'},
            'aggregate': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'alt_labels': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'related_name': "'keywords'", 'symmetrical': 'False', 'to': "orm['events.KeywordLabel']"}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'events_keyword_created_by'", 'null': 'True', 'to': "orm['auth.User']"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'events_keyword_modified_by'", 'null': 'True', 'to': "orm['auth.User']"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '50', 'null': 'True', 'db_index': 'True'})
        },
        'events.keywordlabel': {
            'Meta': {'object_name': 'KeywordLabel', 'unique_together': "(('name', 'language'),)"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'events.language': {
            'Meta': {'object_name': 'Language'},
            'id': ('django.db.models.fields.CharField', [], {'max_length': '6', 'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '20', 'null': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '20', 'null': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '20', 'null': 'True'})
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
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'events_organization_created_by'", 'null': 'True', 'to': "orm['auth.User']"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'events_organization_modified_by'", 'null': 'True', 'to': "orm['auth.User']"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '50', 'null': 'True', 'db_index': 'True'})
        },
        'events.place': {
            'Meta': {'object_name': 'Place', 'unique_together': "(('data_source', 'origin_id'),)"},
            'address_country': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '2', 'null': 'True'}),
            'address_locality': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'address_locality_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'address_locality_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'address_locality_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'address_region': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'contact_type': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'events_place_created_by'", 'null': 'True', 'to': "orm['auth.User']"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_data': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'blank': 'True', 'max_length': '75', 'null': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '50', 'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'info_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200', 'null': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'events_place_modified_by'", 'null': 'True', 'to': "orm['auth.User']"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '50', 'null': 'True', 'db_index': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': "orm['events.Place']"}),
            'position': ('django.contrib.gis.db.models.fields.PointField', [], {'blank': 'True', 'srid': '3067', 'null': 'True'}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '128', 'null': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '128', 'null': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Organization']"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
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