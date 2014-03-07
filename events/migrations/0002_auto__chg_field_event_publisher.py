# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'Event.publisher'
        db.alter_column(u'events_event', 'publisher_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Organization'], null=True))

    def backwards(self, orm):

        # Changing field 'Event.publisher'
        db.alter_column(u'events_event', 'publisher_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['events.Organization']))

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