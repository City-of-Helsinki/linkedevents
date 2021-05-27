import csv
import time
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


# Per module logger
logger = logging.getLogger(__name__)

GK23_SRID = 3877

POSITIONERROR = []
NONEVALUES = []


@register_importer
class OsmImporter(Importer):
    # Class dependencies.
    name = 'osm'
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

        # OSM data source.
        ds_args = dict(id='osm', user_editable=True)
        defaults = dict(name='Ulkoa tuodut paikkatiedot toimipisteille')
        self.data_source, _ = DataSource.objects.update_or_create(defaults=defaults, **ds_args)

        # Organization for units register.
        org_args = dict(origin_id='4000', data_source=self.data_source, classification_id="org:12")
        defaults = dict(name='OpenStreetMap')
        self.organization, _ = Organization.objects.update_or_create(defaults=defaults, **org_args)

        if self.options.get('remap', None):
            # This will prevent deletion checking, marking all deleted places as deleted
            # again and remapping them accordingly! Otherwise, places already deleted
            # will not be remapped by the syncher.
            self.check_deleted = lambda x: False


    def delete_and_replace(self, obj):
        obj.deleted = True
        obj.save(update_fields=['deleted'])
        if obj.events.count() > 0:
            replaced = replace_location(replace=obj, by_source='osm')
            if not replaced:
                replaced = replace_location(replace=obj, by_source='matko', include_deleted=True)
            if not replaced:
                call_command('event_import', 'matko', places=True, single=obj.name)
                replaced = replace_location(replace=obj, by_source='matko')
            if not replaced:
                logger.warning("OSM deleted location %s (%s) with events."
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
            n = float(info[1]['n'])  # latitude
            e = float(info[1]['e'])  # longitude
        except:
            isPositionOk == False
            POSITIONERROR.append(info[0]) # info[0] is OSM id.

        if isPositionOk:
            obj = syncher.get(str(info[0]))
            obj_id = 'osm:%s' % str(info[0])

            if not obj:
                obj = Place(data_source=self.data_source, origin_id=info[0])
                obj._changed = True
                obj._created = True
                obj.id = obj_id
            else:
                assert obj.id == obj_id
                obj._created = False
            obj._changed_fields = []

            # No time for improvements. Sorry for the if chain!
            # We don't want empty strings in the database -> None conversion.
            if info[1]['name']['fi'] == '':
                info[1]['name']['fi'] = None

            if info[1]['name']['sv'] == '':
                info[1]['name']['sv'] = None

            if info[1]['name']['en'] == '':
                info[1]['name']['en'] = None

            if info[1]['street_address']['fi'] == '':
                info[1]['street_address']['fi'] = None
            else:
                if info[1]['housenumber'] != '':
                    info[1]['street_address']['fi'] = info[1]['street_address']['fi'] + " " + info[1]['housenumber']

            if info[1]['street_address']['sv'] == '':
                info[1]['street_address']['sv'] = None
            else:
                if info[1]['housenumber'] != '':
                    info[1]['street_address']['sv'] = info[1]['street_address']['sv'] + " " + info[1]['housenumber']

            if info[1]['street_address']['en'] == '':
                info[1]['street_address']['en'] = None

            try:
                #self._save_translated_field_multilevel(obj, 'name', info[1], 'name')
                self._save_translated_field_multilevel(obj, 'name', info[1], 'name')
                self._save_translated_field_multilevel(obj, 'description', info[1], 'description')
                self._save_translated_field_multilevel(obj, 'street_address', info[1], 'street_address')
            except:
                NONEVALUES.append('OSM ID: ' + str(info[0]) + ' some multilanguage field is none')
                pass

            try:
                self._save_field(obj, 'info_url', info[1], 'www', max_length=1000)
            except:
                NONEVALUES.append('OSM ID: ' + str(info[0]) + ' info_url field is empty!')
                pass

            try:
                self._save_field(obj, 'address_locality', info[1], 'municipality')
            except:
                NONEVALUES.append('OSM ID: ' + str(info[0]) + ' address_locality field is empty!')
                pass

            try:
                self._save_field(obj, 'telephone', info[1], 'phone')
            except:
                NONEVALUES.append('OSM ID: ' + str(info[0]) + ' telephone field is empty!')
                pass

            field_map = {
                'address_zip': 'postal_code',
                'address_postal_full': None,
                'email': 'email',
            }

            for src_field, obj_field in field_map.items():
                if not obj_field:
                    continue
                val = info[1].get(src_field, None)
                if getattr(obj, obj_field) != val:
                    setattr(obj, obj_field, val)
                    obj._changed_fields.append(obj_field)
                    obj._changed = True

            position = None
            if n and e:
                if os.name == 'nt':
                    p = Point(e, n, srid=4326)  # GPS coordinate system (WGS 84)
                else:
                    p = Point(e, n, srid=4326)  # GPS coordinate system (WGS 84)

                if p.within(self.bounding_box):
                    if self.target_srid != 4326:
                        p.transform(self.gps_to_target_ct)
                    position = p
                else:
                    logger.warning("Invalid coordinates (%f, %f) for %s" % (n, e, obj))

            try:
                picture_url = info[1].get('picture_url', '').strip()
            except:
                NONEVALUES.append('OSM ID: ' + str(info[0]) + ' picture_url field is empty!')
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
        queryset = Place.objects.filter(data_source=self.data_source)

        syncher = ModelSyncher(queryset, lambda obj: obj.origin_id, delete_func=self.mark_deleted,
                                check_deleted_func=self.check_deleted)

        addressFilePath = r'/tmp/osm.csv'
        #addressFilePath = r'C:\Users\User\Desktop\importer_place_new\osm.csv'

        csv_all = {}
        # Read CSV file and gather data into tables.
        with open(addressFilePath,'r', encoding='utf-8') as csvfile:
            csvreader = csv.reader(csvfile)
            for x in csvreader:
                try:
                    if x[0] != "osm_id":
                        csv_all.update(dict({x[0]: {
                            'name': {'fi': x[1], 'sv': x[2], 'en': x[3]},
                            'street_address': {'fi': x[4], 'sv': x[5], 'en': ''}, # Added later.
                            'municipality': x[7],
                            'postcode': x[8],
                            'housenumber': x[6],
                            'www': x[9],
                            'phone': x[10],
                            'description': x[11],
                            'n': x[14],
                            'e': x[15],
                        }}))
                except Exception as e:
                    print(e)

            csv_all = sorted(csv_all.items(), key=lambda x: x[0])

        print("Importing places... ")

        for info in csv_all:
            self._import_unit(syncher, info)

        syncher.finish(self.options.get('remap', False))
        POSITIONERROR.sort()
        print("Location error: Coordinates is invalid and unit data was blocked out on Unit id's: \n\r")
        print([str(myelement) for myelement in POSITIONERROR])