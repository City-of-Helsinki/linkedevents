# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'Offer'
        db.delete_table('events_offer')

        # Deleting field 'Event.previous_start_date'
        db.delete_column('events_event', 'previous_start_date')

        # Deleting field 'Event.publisher'
        db.delete_column('events_event', 'publisher_id')

        # Deleting field 'Event.typical_age_range'
        db.delete_column('events_event', 'typical_age_range')

        # Deleting field 'Event.editor'
        db.delete_column('events_event', 'editor_id')

        # Deleting field 'Event.slug'
        db.delete_column('events_event', 'slug')

        # Deleting field 'Event.offers'
        db.delete_column('events_event', 'offers_id')

        # Removing M2M table for field performer on 'Event'
        db.delete_table(db.shorten_name('events_event_performer'))

        # Removing M2M table for field creator on 'Event'
        db.delete_table(db.shorten_name('events_event_creator'))

        # Deleting field 'Category.creator'
        db.delete_column('events_category', 'creator_id')

        # Deleting field 'Category.parent_category'
        db.delete_column('events_category', 'parent_category_id')

        # Deleting field 'Category.editor'
        db.delete_column('events_category', 'editor_id')

        # Adding field 'Category.parent'
        db.add_column('events_category', 'parent',
                      self.gf('mptt.fields.TreeForeignKey')(blank=True, to=orm['events.Category'], null=True),
                      keep_default=False)


    def backwards(self, orm):
        # Adding model 'Offer'
        db.create_table('events_offer', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('price', self.gf('django.db.models.fields.DecimalField')(null=True, blank=True, max_digits=8, decimal_places=2)),
            ('origin_id', self.gf('django.db.models.fields.CharField')(blank=True, max_length=255, null=True, db_index=True)),
            ('created_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('price_currency', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=3)),
            ('image', self.gf('django.db.models.fields.URLField')(blank=True, null=True, max_length=200)),
            ('last_modified_time', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('valid_from', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('available_at_or_from', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Place'], blank=True, null=True)),
            ('seller_object_id', self.gf('django.db.models.fields.PositiveIntegerField')(blank=True, null=True)),
            ('sku', self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255)),
            ('valid_through', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('seller_content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'], blank=True, null=True)),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, null=True, related_name='events_offer_created_by')),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('modified_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], blank=True, null=True, related_name='events_offer_modified_by')),
            ('data_source', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.DataSource'], blank=True, null=True)),
        ))
        db.send_create_signal('events', ['Offer'])

        # Adding field 'Event.previous_start_date'
        db.add_column('events_event', 'previous_start_date',
                      self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True),
                      keep_default=False)

        # Adding field 'Event.publisher'
        db.add_column('events_event', 'publisher',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Organization'], blank=True, null=True, related_name='event_publishers'),
                      keep_default=False)

        # Adding field 'Event.typical_age_range'
        db.add_column('events_event', 'typical_age_range',
                      self.gf('django.db.models.fields.CharField')(blank=True, null=True, max_length=255),
                      keep_default=False)

        # Adding field 'Event.editor'
        db.add_column('events_event', 'editor',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Person'], blank=True, null=True, related_name='event_editors'),
                      keep_default=False)

        # Adding field 'Event.slug'
        db.add_column('events_event', 'slug',
                      self.gf('django.db.models.fields.SlugField')(blank=True, default='', max_length=50),
                      keep_default=False)

        # Adding field 'Event.offers'
        db.add_column('events_event', 'offers',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Offer'], blank=True, null=True),
                      keep_default=False)

        # Adding M2M table for field performer on 'Event'
        m2m_table_name = db.shorten_name('events_event_performer')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm['events.event'], null=False)),
            ('person', models.ForeignKey(orm['events.person'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'person_id'])

        # Adding M2M table for field creator on 'Event'
        m2m_table_name = db.shorten_name('events_event_creator')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('event', models.ForeignKey(orm['events.event'], null=False)),
            ('person', models.ForeignKey(orm['events.person'], null=False))
        ))
        db.create_unique(m2m_table_name, ['event_id', 'person_id'])

        # Adding field 'Category.creator'
        db.add_column('events_category', 'creator',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Person'], blank=True, null=True, related_name='category_creators'),
                      keep_default=False)

        # Adding field 'Category.parent_category'
        db.add_column('events_category', 'parent_category',
                      self.gf('mptt.fields.TreeForeignKey')(to=orm['events.Category'], blank=True, null=True),
                      keep_default=False)

        # Adding field 'Category.editor'
        db.add_column('events_category', 'editor',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['events.Person'], blank=True, null=True, related_name='category_editors'),
                      keep_default=False)

        # Deleting field 'Category.parent'
        db.delete_column('events_category', 'parent_id')


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
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'blank': 'True', 'related_name': "'user_set'", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'blank': 'True', 'related_name': "'user_set'", 'symmetrical': 'False'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'db_table': "'django_content_type'", 'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType'},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'events.category': {
            'Meta': {'object_name': 'Category'},
            'category_for': ('django.db.models.fields.SmallIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_category_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'label': ('django.db.models.fields.CharField', [], {'default': "'unknown'", 'max_length': '255'}),
            'labels': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['events.CategoryLabel']", 'blank': 'True', 'related_name': "'categories'", 'symmetrical': 'False'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_category_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'to': "orm['events.Category']", 'null': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'url': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'default': "'unknown'", 'max_length': '255'})
        },
        'events.categorylabel': {
            'Meta': {'object_name': 'CategoryLabel'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_categorylabel_created_by'"}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_categorylabel_modified_by'"}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'})
        },
        'events.datasource': {
            'Meta': {'object_name': 'DataSource'},
            'event_url_template': ('django.db.models.fields.CharField', [], {'null': 'True', 'max_length': '200'}),
            'id': ('django.db.models.fields.CharField', [], {'primary_key': 'True', 'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'events.event': {
            'Meta': {'object_name': 'Event'},
            'category': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'to': "orm['events.Category']", 'null': 'True', 'symmetrical': 'False'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_event_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'date_published': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'event_status': ('django.db.models.fields.SmallIntegerField', [], {'default': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'language': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Language']", 'null': 'True'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Place']", 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_event_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'provider': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Organization']", 'null': 'True', 'related_name': "'event_providers'"}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True', 'db_index': 'True'}),
            'super_event': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'to': "orm['events.Event']", 'null': 'True', 'related_name': "'sub_event'"}),
            'target_group': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'url_en': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'url_fi': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'url_sv': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'})
        },
        'events.language': {
            'Meta': {'object_name': 'Language'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '6'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_language_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_language_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'})
        },
        'events.openinghoursspecification': {
            'Meta': {'object_name': 'OpeningHoursSpecification'},
            'closes': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'days_of_week': ('django.db.models.fields.SmallIntegerField', [], {'blank': 'True', 'null': 'True'}),
            'opens': ('django.db.models.fields.TimeField', [], {'blank': 'True', 'null': 'True'}),
            'place': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['events.Place']", 'primary_key': 'True', 'related_name': "'opening_hour_specification'", 'unique': 'True'}),
            'valid_from': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'valid_through': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'})
        },
        'events.organization': {
            'Meta': {'object_name': 'Organization'},
            'base_IRI': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'compact_IRI_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_organization_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Person']", 'null': 'True', 'related_name': "'organization_creators'"}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Person']", 'null': 'True', 'related_name': "'organization_editors'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_organization_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'})
        },
        'events.person': {
            'Meta': {'object_name': 'Person'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_person_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Person']", 'null': 'True', 'related_name': "'person_creators'"}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'description_en': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_fi': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'description_sv': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'editor': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Person']", 'null': 'True', 'related_name': "'person_editors'"}),
            'email': ('django.db.models.fields.EmailField', [], {'blank': 'True', 'null': 'True', 'max_length': '75'}),
            'family_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.URLField', [], {'blank': 'True', 'null': 'True', 'max_length': '200'}),
            'last_modified_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'member_of': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.Organization']", 'null': 'True'}),
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_person_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True'})
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
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_place_created_by'"}),
            'created_time': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'custom_fields': ('django_hstore.fields.DictionaryField', [], {'blank': 'True', 'null': 'True'}),
            'data_source': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['events.DataSource']", 'null': 'True'}),
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
            'modified_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['auth.User']", 'null': 'True', 'related_name': "'events_place_modified_by'"}),
            'name': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'name_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'name_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'origin_id': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'parent': ('mptt.fields.TreeForeignKey', [], {'blank': 'True', 'to': "orm['events.Place']", 'null': 'True', 'related_name': "'children'"}),
            'post_office_box_num': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'same_as': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'null': 'True', 'max_length': '255'}),
            'street_address': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'street_address_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'street_address_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'street_address_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '255'}),
            'telephone': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'telephone_en': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'telephone_fi': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'telephone_sv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'null': 'True', 'max_length': '128'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['events']