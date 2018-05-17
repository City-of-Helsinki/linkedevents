# -*- coding: utf-8 -*-
import logging
import re
import requests
import requests_cache

from django import db
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django_orghierarchy.models import Organization

from events.importer.util import replace_location
from events.models import DataSource, Place
from .sync import ModelSyncher
from .base import Importer, register_importer

URL_BASE = 'http://www.hel.fi/palvelukarttaws/rest/v4/'
GK25_SRID = 3879


@register_importer
class TprekImporter(Importer):
    name = 'tprek'
    supported_languages = ['fi', 'sv', 'en']

    def __init__(self, *args, **kwargs):
        super(TprekImporter, self).__init__(*args, **kwargs)
        ds_args = dict(id='tprek')
        defaults = dict(name='Toimipisterekisteri')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        ds_args = dict(id='ahjo')
        defaults = dict(name='Ahjo')
        ahjo_ds, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(origin_id='U021600', data_source=ahjo_ds)
        defaults = dict(name='Tietotekniikka- ja viestintäosasto')
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)
        if self.options.get('remap', None):
            # This will prevent deletion checking, marking all deleted places as deleted
            # again and remapping them accordingly! Otherwise, places already deleted
            # will not be remapped by the syncher.
            self.check_deleted = lambda x: False
            self.mark_deleted = self.delete_and_replace

    def clean_text(self, text):
        # remove consecutive whitespaces
        text = re.sub(r'\s\s+', ' ', text, re.U)
        # remove nil bytes
        text = text.replace(u'\u0000', ' ')
        text = text.strip()
        return text

    def pk_get(self, resource_name, res_id=None):
        url = "%s%s/" % (URL_BASE, resource_name)
        if res_id is not None:
            url = "%s%s/" % (url, res_id)
        logging.info("Fetching URL %s" % url)
        resp = requests.get(url)
        assert resp.status_code == 200
        return resp.json()

    def delete_and_replace(self, obj):
        obj.deleted = True
        obj.save(update_fields=['deleted'])
        # we won't stand idly by and watch tprek delete needed units willy-nilly without raising a ruckus!
        if obj.events.count() > 0:
            # try to replace by tprek and, failing that, matko
            replaced = replace_location(replace=obj, by_source='tprek')
            if not replaced:
                # matko location may indeed be deleted by an earlier iteration
                replaced = replace_location(replace=obj, by_source='matko', include_deleted=True)
            if not replaced:
                # matko location may never have been imported in the first place, do it now!
                call_command('event_import', 'matko', places=True, single=obj.name)
                replaced = replace_location(replace=obj, by_source='matko')
            if not replaced:
                logging.warning("Tprek deleted location %s (%s) with events."
                                "No unambiguous replacement was found. "
                                "Please look for a replacement location and save it in the replaced_by field. "
                                "Until then, events will stay mapped to the deleted location." %
                                (obj.id, str(obj)))
        return True

    def mark_deleted(self, obj):
        if obj.deleted:
            return False
        return self.delete_and_replace(obj)

    def check_deleted(self, obj):
        return obj.deleted

    def _save_translated_field(self, obj, obj_field_name, info,
                               info_field_name, max_length=None):
        for lang in ('fi', 'sv', 'en'):
            key = '%s_%s' % (info_field_name, lang)
            if key in info:
                val = self.clean_text(info[key])
            else:
                val = None

            if max_length and val and len(val) > max_length:
                logging.warning("%s: field %s too long" % (obj, info_field_name))
                val = None

            obj_key = '%s_%s' % (obj_field_name, lang)
            obj_val = getattr(obj, obj_key, None)
            if obj_val == val:
                continue

            setattr(obj, obj_key, val)
            if lang == 'fi':
                setattr(obj, obj_field_name, val)
            obj._changed_fields.append(obj_key)
            obj._changed = True

    def _save_field(self, obj, obj_field_name, info,
                    info_field_name, max_length=None):
            if info_field_name in info:
                val = self.clean_text(info[info_field_name])
            else:
                val = None

            if max_length and val and len(val) > max_length:
                logging.warning("%s: field %s too long" % (obj, info_field_name))
                val = None

            obj_val = getattr(obj, obj_field_name, None)
            if obj_val == val:
                return

            setattr(obj, obj_field_name, val)
            obj._changed_fields.append(obj_field_name)
            obj._changed = True

    @db.transaction.atomic
    def _import_unit(self, syncher, info):
        obj = syncher.get(str(info['id']))
        obj_id = 'tprek:%s' % str(info['id'])
        if not obj:
            obj = Place(data_source=self.data_source, origin_id=info['id'])
            obj._changed = True
            obj._created = True
            obj.id = obj_id
        else:
            assert obj.id == obj_id
            obj._created = False
        obj._changed_fields = []

        self._save_translated_field(obj, 'name', info, 'name')
        self._save_translated_field(obj, 'description', info, 'desc')
        self._save_translated_field(obj, 'street_address', info, 'street_address')
        self._save_translated_field(obj, 'address_locality', info, 'address_city')

        self._save_translated_field(obj, 'info_url', info, 'www', max_length=1000)

        self._save_field(obj, 'telephone', info, 'phone')

        field_map = {
            'address_zip': 'postal_code',
            'address_postal_full': None,
            'email': 'email',
        }
        for src_field, obj_field in field_map.items():
            if not obj_field:
                continue
            val = info.get(src_field, None)
            if getattr(obj, obj_field) != val:
                setattr(obj, obj_field, val)
                obj._changed_fields.append(obj_field)
                obj._changed = True

        n = info.get('latitude', 0)
        e = info.get('longitude', 0)
        position = None
        if n and e:
            p = Point(e, n, srid=4326)  # GPS coordinate system
            if p.within(self.bounding_box):
                if self.target_srid != 4326:
                    p.transform(self.gps_to_target_ct)
                position = p
            else:
                logging.warning("Invalid coordinates (%f, %f) for %s" % (n, e, obj))

        picture_url = info.get('picture_url', '').strip()
        image_object = self.get_or_create_image(picture_url)
        self.set_image(obj, image_object)

        if position and obj.position:
            # If the distance is less than 10cm, assume the location
            # hasn't changed.
            assert obj.position.srid == settings.PROJECTION_SRID
            if position.distance(obj.position) < 0.10:
                position = obj.position
        if position != obj.position:
            obj._changed = True
            obj._changed_fields.append('position')
            obj.position = position

        if obj.publisher_id != self.organization.id:
            obj.publisher = self.organization
            obj._changed_fields.append('publisher')
            obj._changed = True

        if obj.deleted:
            obj.deleted = False
            # location has been reinstated in tprek, hip hip hooray!
            replace_location(from_source='matko', by=obj)
            obj._changed_fields.append('undeleted')
            obj._changed = True

        if obj._changed:
            if obj._created:
                verb = "created"
            else:
                verb = "changed (fields: %s)" % ', '.join(obj._changed_fields)
            logging.info("%s %s" % (obj, verb))
            obj.save()

        syncher.mark(obj)

    def import_places(self):
        if self.options['cached']:
            requests_cache.install_cache('tprek')

        queryset = Place.objects.filter(data_source=self.data_source)
        if self.options.get('single', None):
            obj_id = self.options['single']
            obj_list = [self.pk_get('unit', obj_id)]
            queryset = queryset.filter(id=obj_id)
        else:
            logging.info("Loading units...")
            obj_list = self.pk_get('unit')
            logging.info("%s units loaded" % len(obj_list))
        syncher = ModelSyncher(queryset, lambda obj: obj.origin_id, delete_func=self.mark_deleted,
                               check_deleted_func=self.check_deleted)
        for idx, info in enumerate(obj_list):
            if idx and (idx % 1000) == 0:
                logging.info("%s units processed" % idx)
            self._import_unit(syncher, info)

        syncher.finish(self.options.get('remap', False))
