# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Event.start_date'
        db.delete_column('events_event', 'start_date')

        # Deleting field 'Event.duration'
        db.delete_column('events_event', 'duration')

        # Deleting field 'Event.end_date'
        db.delete_column('events_event', 'end_date')

        # Deleting field 'Event.door_time'
        db.delete_column('events_event', 'door_time')

        # Adding field 'Event.start_time'
        db.add_column('events_event', 'start_time',
                      self.gf('django.db.models.fields.DateTimeField')(db_index=True, blank=True, null=True),
                      keep_default=False)

        # Adding field 'Event.end_time'
        db.add_column('events_event', 'end_time',
                      self.gf('django.db.models.fields.DateTimeField')(db_index=True, blank=True, null=True),
                      keep_default=False)


    def backwards(self, orm):
        # Adding field 'Event.start_date'
        db.add_column('events_event', 'start_date',
                      self.gf('django.db.models.fields.DateField')(null=True, blank=True, db_index=True),
                      keep_default=False)

        # Adding field 'Event.duration'
        db.add_column('events_event', 'duration',
                      self.gf('django.db.models.fields.BigIntegerField')(null=True, blank=True),
                      keep_default=False)

        # Adding field 'Event.end_date'
        db.add_column('events_event', 'end_date',
                      self.gf('django.db.models.fields.DateField')(null=True, blank=True, db_index=True),
                      keep_default=False)

        # Adding field 'Event.door_time'
        db.add_column('events_event', 'door_time',
                      self.gf('django.db.models.fields.TimeField')(null=True, blank=True),
                      keep_default=False)

        # Deleting field 'Event.start_time'
        db.delete_column('events_event', 'start_time')

        # Deleting field 'Event.end_time'
        db.delete_column('events_event', 'end_time')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True', 'symmetrical': 'False'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'object_name': 'Permission', 'unique_together': "(('content_type', 'codename'),)"},
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
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'blank': 'True', 'related_name': "'user_set'", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True', 'related_name': "'user_set'", 'symmetrical': 'False'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'db_table': "'django_content_type'", 'object_name': 'ContentType', 'unique_together': "(('app_label', 'model'),)"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'events.category': {
            'Meta': {'object_name': 'Category'},
            'category_for': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_category_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Person']", 'null': 'True', 'blank': 'True', 'related_name': "'category_creators'"}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Person']", 'null': 'True', 'blank': 'True', 'related_name': "'category_editors'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_category_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'parent_category': ('mptt.fields.TreeForeignKey', [], {'to': "orm['events.Category']", 'null': 'True', 'blank': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'events.datasource': {
            'Meta': {'object_name': 'DataSource'},
            'event_url_template': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'events.event': {
            'Meta': {'object_name': 'Event'},
            'category': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.Category']", 'null': 'True', 'blank': 'True', 'symmetrical': 'False'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_event_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.Person']", 'blank': 'True', 'related_name': "'event_creators'", 'symmetrical': 'False'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'null': 'True', 'blank': 'True'}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Person']", 'null': 'True', 'blank': 'True', 'related_name': "'event_editors'"}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']", 'null': 'True', 'blank': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Place']", 'null': 'True', 'blank': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_event_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'offers': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Offer']", 'null': 'True', 'blank': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'performer': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.Person']", 'blank': 'True', 'symmetrical': 'False'}),
            'previous_start_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'provider': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Organization']", 'null': 'True', 'blank': 'True', 'related_name': "'event_providers'"}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Organization']", 'null': 'True', 'blank': 'True', 'related_name': "'event_publishers'"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'blank': 'True'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'blank': 'True', 'null': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'to': "orm['events.Event']", 'null': 'True', 'blank': 'True', 'related_name': "'sub_event'"}),
            'target_group': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'typical_age_range': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'url_en': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'url_fi': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'url_sv': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'})
        },
        'events.language': {
            'Meta': {'object_name': 'Language'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '6'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_language_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_language_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'})
        },
        'events.offer': {
            'Meta': {'object_name': 'Offer'},
            'available_at_or_from': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Place']", 'null': 'True', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_offer_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_offer_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'price': ('django.db.models.fields.DecimalField', [], {'max_digits': '8', 'null': 'True', 'blank': 'True', 'decimal_places': '2'}),
            'price_currency': ('django.db.models.fields.CharField', [], {'max_length': '3', 'blank': 'True', 'null': 'True'}),
            'seller_content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'}),
            'seller_object_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'sku': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'events.openinghoursspecification': {
            'Meta': {'object_name': 'OpeningHoursSpecification'},
            'closes': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'days_of_week': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'opens': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'place': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'opening_hour_specification'", 'primary_key': 'True', 'to': "orm['events.Place']", 'unique': 'True'}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'events.organization': {
            'Meta': {'object_name': 'Organization'},
            'base_IRI': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'compact_IRI_name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_organization_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Person']", 'null': 'True', 'blank': 'True', 'related_name': "'organization_creators'"}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Person']", 'null': 'True', 'blank': 'True', 'related_name': "'organization_editors'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_organization_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'})
        },
        'events.person': {
            'Meta': {'object_name': 'Person'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_person_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Person']", 'null': 'True', 'blank': 'True', 'related_name': "'person_creators'"}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Person']", 'null': 'True', 'blank': 'True', 'related_name': "'person_editors'"}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True', 'null': 'True'}),
            'family_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'member_of': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Organization']", 'null': 'True', 'blank': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_person_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'events.place': {
            'Meta': {'object_name': 'Place', 'unique_together': "(('data_source', 'origin_id'),)"},
            'address_country': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True', 'null': 'True'}),
            'address_locality': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'address_locality_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'address_locality_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'address_locality_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'address_region': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'contact_type': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_place_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'null': 'True', 'blank': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.DataSource']", 'null': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3067', 'null': 'True', 'blank': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True', 'related_name': "'events_place_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'to': "orm['events.Place']", 'null': 'True', 'blank': 'True', 'related_name': "'children'"}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True', 'max_length': '255'}),
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