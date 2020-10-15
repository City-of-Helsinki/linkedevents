# -*- coding: utf-8 -*-
import logging
import requests
import requests_cache
import os

from django import db
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django_orghierarchy.models import Organization
from django_orghierarchy.models import OrganizationClass

from events.importer.util import replace_location
from events.models import DataSource, Place
from .sync import ModelSyncher
from .base import Importer, register_importer
from .tprapi import async_main

# Per module logger
logger = logging.getLogger(__name__)

URL_BASE = 'https://palvelukartta.turku.fi/api/v2/'
GK23_SRID = 3877

POSITIONERROR = []
NONEVALUES = []


@register_importer
class TprekImporter(Importer):
    name = 'tpr'
    supported_languages = ['fi', 'sv', 'en']

    def setup(self):

        # Public data source for organization model.
        ds_args = dict(id='org', user_editable=True)
        defaults = dict(name='Ulkoa tuodut organisaatiotiedot')
        self.data_source, _ = DataSource.objects.update_or_create(defaults=defaults, **ds_args)

        # Public organization class for all places.
        ds_args = dict(origin_id='12', data_source=self.data_source)
        defaults = dict(name='Paikkatieto')
        self.organizationclass, _ = OrganizationClass.objects.update_or_create(defaults=defaults, **ds_args)

        # Unit data source.
        ds_args = dict(id='tpr', user_editable=True)
        defaults = dict(name='Ulkoa tuodut paikkatiedot toimipisteille')
        self.data_source, _ = DataSource.objects.update_or_create(defaults=defaults, **ds_args)

        # Organization for units register.
        org_args = dict(origin_id='1100', data_source=self.data_source, classification_id="org:12")
        defaults = dict(name='Toimipisterekisteri')
        self.organization, _ = Organization.objects.update_or_create(defaults=defaults, **org_args)
        if self.options.get('remap', None):
            # This will prevent deletion checking, marking all deleted places as deleted
            # again and remapping them accordingly! Otherwise, places already deleted
            # will not be remapped by the syncher.
            self.check_deleted = lambda x: False

    def pk_get(self, resource_name, page, res_id=None):
        # Currently only used to get a single unit.
        url = "%s%s/%s" % (URL_BASE, resource_name, page)
        if res_id is not None:
            url = "%s%s/" % (url, res_id)
        logger.info("Fetching URL %s" % url)
        resp = requests.get(url)

        assert resp.status_code == 200
        return resp.json()

    def delete_and_replace(self, obj):
        obj.deleted = True
        obj.save(update_fields=['deleted'])
        if obj.events.count() > 0:
            replaced = replace_location(replace=obj, by_source='tpr')
            if not replaced:
                replaced = replace_location(replace=obj, by_source='matko', include_deleted=True)
            if not replaced:
                call_command('event_import', 'matko', places=True, single=obj.name)
                replaced = replace_location(replace=obj, by_source='matko')
            if not replaced:
                logger.warning("Tpr deleted location %s (%s) with events."
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

    @db.transaction.atomic
    def _import_unit(self, syncher, info):
        n = 0
        e = 0
        isPositionOk = True
        try:
            n = info['location']['coordinates'][0]  # latitude
            e = info['location']['coordinates'][1]  # longitude
        except:
            isPositionOk == False
            POSITIONERROR.append(info['id'])

        if isPositionOk:
            obj = syncher.get(str(info['id']))
            obj_id = 'tpr:%s' % str(info['id'])

            if not obj:
                obj = Place(data_source=self.data_source, origin_id=info['id'])
                obj._changed = True
                obj._created = True
                obj.id = obj_id
            else:
                assert obj.id == obj_id
                obj._created = False
            obj._changed_fields = []

            try:
                self._save_translated_field_multilevel(obj, 'name', info, 'name')
                self._save_translated_field_multilevel(obj, 'description', info, 'description')
                self._save_translated_field_multilevel(obj, 'street_address', info, 'street_address')
            except:
                NONEVALUES.append('unit ID: ' + str(info['id']) + ' some multilanguage field is none')
                pass

            try:
                self._save_field(obj, 'info_url', info, 'www', max_length=1000)
            except:
                NONEVALUES.append('unit ID: ' + str(info['id']) + ' info_url field is empty!')
                pass

            try:
                self._save_field(obj, 'address_locality', info, 'municipality')
            except:
                NONEVALUES.append('unit ID: ' + str(info['id']) + ' address_locality field is empty!')
                pass

            try:
                self._save_field(obj, 'telephone', info, 'phone')
            except:
                NONEVALUES.append('unit ID: ' + str(info['id']) + ' telephone field is empty!')
                pass

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

            position = None
            if n and e:
                if os.name == 'nt':
                    p = Point(e, n, srid=4326)  # GPS coordinate system (WGS 84)
                else:
                    p = Point(n, e, srid=4326)  # GPS coordinate system (WGS 84)

                if p.within(self.bounding_box):
                    if self.target_srid != 4326:
                        p.transform(self.gps_to_target_ct)
                    position = p
                else:
                    logger.warning("Invalid coordinates (%f, %f) for %s" % (n, e, obj))

            try:
                picture_url = info.get('picture_url', '').strip()
            except:
                NONEVALUES.append('unit ID: ' + str(info['id']) + ' picture_url field is empty!')
                pass

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
                replace_location(from_source='matko', by=obj)
                obj._changed_fields.append('deleted')
                obj._changed = True

            if obj._changed:
                if obj._created:
                    verb = "created"
                else:
                    verb = "changed (fields: %s)" % ', '.join(obj._changed_fields)
                logger.info("%s %s" % (obj, verb))
                obj.save()

            syncher.mark(obj)

    def import_places(self):
        if self.options['cached']:
            requests_cache.install_cache('tpr')

        queryset = Place.objects.filter(data_source=self.data_source)
        obj_list = []

        if self.options.get('single', None):
            obj_id = self.options['single']
            obj_list = [self.pk_get('unit', obj_id)]
            queryset = queryset.filter(id=obj_id)
        else:
            logger.info("Fetching all unit pages...")
            obj_list = async_main() # Optional async_main(True) if you want to log errors.
            if obj_list:
                logger.info("Successfully gathered unit data!")
            else:
                logger.warn("Something went wrong... No unit data was found?")

        syncher = ModelSyncher(queryset, lambda obj: obj.origin_id, delete_func=self.mark_deleted,
                               check_deleted_func=self.check_deleted)
        for idx, infos in enumerate(obj_list, start=1):
            logger.info("Page: %s was processed." % idx)
            for info in infos:
                self._import_unit(syncher, info)

        syncher.finish(self.options.get('remap', False))
        POSITIONERROR.sort()
        print("Location error: Coordinates is invalid and unit data was blocked out on Unit id's: \n\r")
        print([str(myelement) for myelement in POSITIONERROR])
