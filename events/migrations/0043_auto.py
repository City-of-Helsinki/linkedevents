# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Removing M2M table for field categories on 'Event'
        db.delete_table(db.shorten_name('events_event_categories'))

        # Adding M2M table for field keywords on 'Event'
        m2m_table_name = db.shorten_name('events_event_keywords')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm['events.event'], null=False)),
            ('category', models.ForeignKey(orm['events.category'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'category_id'])


    def backwards(self, orm):
        # Adding M2M table for field categories on 'Event'
        m2m_table_name = db.shorten_name('events_event_categories')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm['events.event'], null=False)),
            ('category', models.ForeignKey(orm['events.category'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'category_id'])

        # Removing M2M table for field keywords on 'Event'
        db.delete_table(db.shorten_name('events_event_keywords'))


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'blank': 'True', 'to': "orm['auth.Permission']"})
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
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'blank': 'True', 'to': "orm['auth.Group']", 'related_name': "'user_set'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'blank': 'True', 'to': "orm['auth.Permission']", 'related_name': "'user_set'"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'ordering': "('name',)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'events.category': {
            'Meta': {'object_name': 'Category'},
            'aggregate': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'alt_labels': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'blank': 'True', 'to': "orm['events.CategoryLabel']", 'related_name': "'categories'"}),
            'category_for': ('django.db.models.fields.SmallIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_category_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.DataSource']"}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_category_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.Category']"}),
            'same_as': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'url': ('django.db.models.fields.CharField', [], {'default': "'unknown'", 'max_length': '255', 'db_index': 'True'})
        },
        'events.categorylabel': {
            'Meta': {'unique_together': "(('name', 'language'),)", 'object_name': 'CategoryLabel'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_categorylabel_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['events.Language']"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_categorylabel_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'})
        },
        'events.datasource': {
            'Meta': {'object_name': 'DataSource'},
            'event_url_template': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '100', 'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'events.event': {
            'Meta': {'object_name': 'Event'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_event_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.DataSource']"}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'keywords': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'blank': 'True', 'null': 'True', 'to': "orm['events.Category']"}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.Language']"}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.Place']"}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_event_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.Event']", 'related_name': "'sub_event'"}),
            'target_group': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'url_en': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'url_fi': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'url_sv': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'})
        },
        'events.language': {
            'Meta': {'object_name': 'Language'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_language_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.DataSource']"}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '6', 'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_language_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'})
        },
        'events.openinghoursspecification': {
            'Meta': {'object_name': 'OpeningHoursSpecification'},
            'closes': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'days_of_week': ('django.db.models.fields.SmallIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'opens': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'place': ('django.db.models.fields.related.OneToOneField', [], {'primary_key': 'True', 'to': "orm['events.Place']", 'unique': 'True', 'related_name': "'opening_hour_specification'"}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'})
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
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_place_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.DataSource']"}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True', 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.contrib.gis.db.models.fields.PointField', [], {'blank': 'True', 'null': 'True', 'srid': '3067'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['auth.User']", 'related_name': "'events_place_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'null': 'True', 'to': "orm['events.Place']", 'related_name': "'children'"}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True', 'null': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True', 'null': 'True', 'db_index': 'True'}),
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