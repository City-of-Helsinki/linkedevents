# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Event.headline_fi'
        db.add_column('events_event', 'headline_fi',
                      self.gf('django.db.models.fields.CharField')(db_index=True, null=True, blank=True, max_length=255),
                      keep_default=False)

        # Adding field 'Event.headline_sv'
        db.add_column('events_event', 'headline_sv',
                      self.gf('django.db.models.fields.CharField')(db_index=True, null=True, blank=True, max_length=255),
                      keep_default=False)

        # Adding field 'Event.headline_en'
        db.add_column('events_event', 'headline_en',
                      self.gf('django.db.models.fields.CharField')(db_index=True, null=True, blank=True, max_length=255),
                      keep_default=False)

        # Adding field 'Event.secondary_headline_fi'
        db.add_column('events_event', 'secondary_headline_fi',
                      self.gf('django.db.models.fields.CharField')(db_index=True, null=True, blank=True, max_length=255),
                      keep_default=False)

        # Adding field 'Event.secondary_headline_sv'
        db.add_column('events_event', 'secondary_headline_sv',
                      self.gf('django.db.models.fields.CharField')(db_index=True, null=True, blank=True, max_length=255),
                      keep_default=False)

        # Adding field 'Event.secondary_headline_en'
        db.add_column('events_event', 'secondary_headline_en',
                      self.gf('django.db.models.fields.CharField')(db_index=True, null=True, blank=True, max_length=255),
                      keep_default=False)

        # Adding field 'Event.provider_fi'
        db.add_column('events_event', 'provider_fi',
                      self.gf('django.db.models.fields.CharField')(null=True, blank=True, max_length=512),
                      keep_default=False)

        # Adding field 'Event.provider_sv'
        db.add_column('events_event', 'provider_sv',
                      self.gf('django.db.models.fields.CharField')(null=True, blank=True, max_length=512),
                      keep_default=False)

        # Adding field 'Event.provider_en'
        db.add_column('events_event', 'provider_en',
                      self.gf('django.db.models.fields.CharField')(null=True, blank=True, max_length=512),
                      keep_default=False)


        # Renaming column for 'Event.provider' to match new field type.
        db.rename_column('events_event', 'provider_id', 'provider')
        # Changing field 'Event.provider'
        db.alter_column('events_event', 'provider', self.gf('django.db.models.fields.CharField')(null=True, max_length=512))
        # Removing index on 'Event', fields ['provider']
        db.delete_index('events_event', ['provider_id'])


    def backwards(self, orm):
        # Adding index on 'Event', fields ['provider']
        db.create_index('events_event', ['provider_id'])

        # Deleting field 'Event.headline_fi'
        db.delete_column('events_event', 'headline_fi')

        # Deleting field 'Event.headline_sv'
        db.delete_column('events_event', 'headline_sv')

        # Deleting field 'Event.headline_en'
        db.delete_column('events_event', 'headline_en')

        # Deleting field 'Event.secondary_headline_fi'
        db.delete_column('events_event', 'secondary_headline_fi')

        # Deleting field 'Event.secondary_headline_sv'
        db.delete_column('events_event', 'secondary_headline_sv')

        # Deleting field 'Event.secondary_headline_en'
        db.delete_column('events_event', 'secondary_headline_en')

        # Deleting field 'Event.provider_fi'
        db.delete_column('events_event', 'provider_fi')

        # Deleting field 'Event.provider_sv'
        db.delete_column('events_event', 'provider_sv')

        # Deleting field 'Event.provider_en'
        db.delete_column('events_event', 'provider_en')


        # Renaming column for 'Event.provider' to match new field type.
        db.rename_column('events_event', 'provider', 'provider_id')
        # Changing field 'Event.provider'
        db.alter_column('events_event', 'provider_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Organization'], null=True))

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True'}),
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
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True', 'related_name': "'user_set'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True', 'related_name': "'user_set'"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'db_table': "'django_content_type'", 'unique_together': "(('app_label', 'model'),)", 'ordering': "('name',)", 'object_name': 'ContentType'},
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
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_event_created_by'", 'blank': 'True'}),
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
            'headline': ('django.db.models.fields.CharField', [], {'null': 'True', 'db_index': 'True', 'max_length': '255'}),
            'headline_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'headline_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'headline_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'info_url_en': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url_fi': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'info_url_sv': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'keywords': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.Keyword']", 'null': 'True', 'symmetrical': 'False', 'blank': 'True'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_event_modified_by'", 'blank': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Place']", 'null': 'True', 'blank': 'True'}),
            'location_extra_info': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '400'}),
            'location_extra_info_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '400'}),
            'location_extra_info_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '400'}),
            'location_extra_info_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '400'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '50'}),
            'provider': ('django.db.models.fields.CharField', [], {'null': 'True', 'max_length': '512'}),
            'provider_en': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '512'}),
            'provider_fi': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '512'}),
            'provider_sv': ('django.db.models.fields.CharField', [], {'null': 'True', 'blank': 'True', 'max_length': '512'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Organization']", 'related_name': "'published_events'"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'secondary_headline': ('django.db.models.fields.CharField', [], {'null': 'True', 'db_index': 'True', 'max_length': '255'}),
            'secondary_headline_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'secondary_headline_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'secondary_headline_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'short_description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'short_description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'short_description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'short_description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True', 'db_index': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'to': "orm['events.Event']", 'null': 'True', 'related_name': "'sub_events'", 'blank': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'events.eventlink': {
            'Meta': {'unique_together': "(('event', 'language', 'link'),)", 'object_name': 'EventLink'},
            'event': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Event']", 'related_name': "'external_links'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'link': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'})
        },
        'events.exportinfo': {
            'Meta': {'unique_together': "(('target_system', 'content_type', 'object_id'),)", 'object_name': 'ExportInfo'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_exported_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'object_id': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'target_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'target_system': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'})
        },
        'events.keyword': {
            'Meta': {'object_name': 'Keyword'},
            'aggregate': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'alt_labels': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.KeywordLabel']", 'symmetrical': 'False', 'blank': 'True', 'related_name': "'keywords'"}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_keyword_created_by'", 'blank': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_keyword_modified_by'", 'blank': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '50'})
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
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_organization_created_by'", 'blank': 'True'}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '50'}),
            'image': ('django.db.models.fields.URLField', [], {'null': 'True', 'blank': 'True', 'max_length': '200'}),
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_organization_modified_by'", 'blank': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '50'})
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
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_place_created_by'", 'blank': 'True'}),
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
            'last_modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_place_modified_by'", 'blank': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '50'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'to': "orm['events.Place']", 'null': 'True', 'related_name': "'children'", 'blank': 'True'}),
            'position': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3067', 'null': 'True', 'blank': 'True'}),
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