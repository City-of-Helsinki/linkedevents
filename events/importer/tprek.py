# -*- coding: utf-8 -*-
import re
import requests
import requests_cache

from django import db
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.gdal import SpatialReference, CoordTransform
from django.utils.translation import activate, get_language

from events.models import *
from .sync import ModelSyncher
from .base import Importer, register_importer

URL_BASE = 'http://www.hel.fi/palvelukarttaws/rest/v3/'
GK25_SRID = 3879

def mark_deleted(obj):
    obj.deleted = True
    obj.save(update_fields=['deleted'])


@register_importer
class TprekImporter(Importer):
    name = 'tprek'
    supported_languages = ['fi', 'sv', 'en']

    def __init__(self, *args, **kwargs):
        super(TprekImporter, self).__init__(*args, **kwargs)
        ds_args = dict(id='tprek')
        defaults = dict(name='Toimipisterekisteri')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

    def clean_text(self, text):
        # remove consecutive whitespaces
        text = re.sub(r'\s\s+', ' ', text, re.U)
        # remove nil bytes
        text = text.replace(u'\u0000', ' ')
        text = text.strip()
        return text

    def pk_get(self, resource_name, res_id=None):
        url = "%s%s/" % (URL_BASE, resource_name)
        if res_id != None:
            url = "%s%s/" % (url, res_id)
        print("Fetching URL %s" % url)
        resp = requests.get(url)
        assert resp.status_code == 200
        return resp.json()

    def _save_translated_field(self, obj, obj_field_name, info, info_field_name):
        for lang in ('fi', 'sv', 'en'):
            key = '%s_%s' % (info_field_name, lang)
            if key in info:
                val = self.clean_text(info[key])
            else:
                val = None
            obj_key = '%s_%s' % (obj_field_name, lang)
            obj_val = getattr(obj, obj_key, None)
            if obj_val == val:
                continue

            setattr(obj, obj_key, val)
            if lang == 'fi':
                setattr(obj, obj_field_name, val)
            obj._changed = True

    @db.transaction.atomic
    def _import_unit(self, syncher, info):
        obj = syncher.get(str(info['id']))
        if not obj:
            obj = Place(data_source=self.data_source, origin_id=info['id'])
            obj._changed = True
            obj._created = True
        else:
            obj._created = False

        self._save_translated_field(obj, 'name', info, 'name')
        self._save_translated_field(obj, 'description', info, 'desc')
        self._save_translated_field(obj, 'street_address', info, 'street_address')
        self._save_translated_field(obj, 'address_locality', info, 'address_city')

        self._save_translated_field(obj, 'www_url', info, 'www')
        self._save_translated_field(obj, 'picture_caption', info, 'picture_caption')

        self._save_translated_field(obj, 'telephone', info, 'phone')

        field_map = {
            'address_zip': 'postal_code',
            'address_postal_full': None,
            'email': 'email',
            'picture_url': 'image',
        }
        for src_field, obj_field in field_map.items():
            if not obj_field:
                continue
            val = info.get(src_field, None)
            if getattr(obj, obj_field) != val:
                setattr(obj, obj_field, val)
                obj._changed = True

        n = info.get('latitude', 0)
        e = info.get('longitude', 0)
        location = None
        if n and e:
            p = Point(e, n, srid=4326) # GPS coordinate system
            if p.within(self.bounding_box):
                if self.target_srid != 4326:
                    p.transform(self.gps_to_target_ct)
                location = p
            else:
                print("Invalid coordinates (%f, %f) for %s" % (n, e, obj))

        if location and obj.location:
            # If the distance is less than 10cm, assume the location
            # hasn't changed.
            assert obj.location.srid == settings.PROJECTION_SRID
            if location.distance(obj.location) < 0.10:
                location = obj.location
        if location != obj.location:
            obj._changed = True
            obj.location = location

        if obj._changed:
            if obj._created:
                verb = "created"
            else:
                verb = "changed"
            print("%s %s" % (obj, verb))
            obj.save()

        syncher.mark(obj)

    def import_locations(self):
        if self.options['cached']:
            requests_cache.install_cache('tprek')

        queryset = Place.objects.filter(data_source=self.data_source).filter(deleted=False)
        if self.options.get('single', None):
            obj_id = self.options['single']
            obj_list = [self.pk_get('unit', obj_id)]
            queryset = queryset.filter(id=obj_id)
        else:
            obj_list = self.pk_get('unit')

        self.target_srid = settings.PROJECTION_SRID
        gps_srs = SpatialReference(4326)
        target_srs = SpatialReference(self.target_srid)
        if getattr(settings, 'BOUNDING_BOX'):
            self.bounding_box = Polygon.from_bbox(settings.BOUNDING_BOX)
            self.bounding_box.set_srid(self.target_srid)
            target_to_gps_ct = CoordTransform(target_srs, gps_srs)
            self.bounding_box.transform(target_to_gps_ct)
        else:
            self.bounding_box = None
        self.gps_to_target_ct = CoordTransform(gps_srs, target_srs)
        syncher = ModelSyncher(queryset, lambda obj: obj.origin_id, delete_func=mark_deleted)
        for idx, info in enumerate(obj_list):
            self._import_unit(syncher, info)

        syncher.finish()
