# -*- coding: utf-8 -*-

# Dependencies.
import requests
import dateutil
import asyncio
import aiohttp
import logging
import math
import time
import pytz
import json
import sys
import re

# Django:
from django_orghierarchy.models import Organization, OrganizationClass
from events.models import DataSource, BaseModel, Place
from .base import Importer, register_importer
from django.utils.html import strip_tags
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email, URLValidator

# GeoDjango:
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.gdal import SpatialReference, CoordTransform
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point

# Query speed measurement (used if need be).
from django.db import connection, reset_queries

# Type checking:
from typing import TYPE_CHECKING, Any, Tuple, List

# Per module logger
logger = logging.getLogger(__name__)

# Request headers.
HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0',
}

# List of supported municipalities.
MUNICIPALITIES = {
    'AURA': ('Aura', 'Aura'),
    'KAARINA': ('Kaarina', 'S:t Karins'),
    'KOSKI TL': ('Koski Tl', 'Koskis'),
    'KUSTAVI': ('Kustavi', 'Gustavs'),
    'KEMIÖNSAARI': ('Kemiönsaari', 'Kimitoön'),
    'LAITILA': ('Laitila', 'Letala'),
    'LIETO': ('Lieto', 'Lundo'),
    'LOIMAA': ('Loimaa', 'Loimaa'),
    'PARAINEN': ('Parainen', 'Pargas'),
    'MARTTILA': ('Marttila', 'S:t Mårtens'),
    'MASKU': ('Masku', 'Masko'),
    'MYNÄMÄKI': ('Mynämäki', 'Virmo'),
    'NAANTALI': ('Naantali', 'Nådendal'),
    'NOUSIAINEN': ('Nousiainen', 'Nousis'),
    'ORIPÄÄ': ('Oripää', 'Oripää'),
    'PAIMIO': ('Paimio', 'Pemar'),
    'PYHÄRANTA': ('Pyhäranta', 'Pyhäranta'),
    'PÖYTYÄ': ('Pöytyä', 'Pöytis'),
    'RAISIO': ('Raisio', 'Reso'),
    'RUSKO': ('Rusko', 'Rusko'),
    'SALO': ('Salo', 'Salo'),
    'SAUVO': ('Sauvo', 'Sagu'),
    'SOMERO': ('Somero', 'Somero'),
    'TAIVASSALO': ('Taivassalo', 'Tövsala'),
    'TURKU': ('Turku', 'Åbo'),
    'UUSIKAUPUNKI': ('Uusikaupunki', 'Nystad'),
    'VEHMAA': ('Vehmaa', 'Vemo'),
}

# Replacement words for the street.
REPLACEMENTS = {
    'rakennus': 'byggnad',
    ' rak ': ' byg ',
    ' rak.': ' byg.',
    'porras': 'trappa',
    'kerros': 'våning',
    'rappu': 'trappa',
    'krs': 'vån',
    'sairaala': 'sjukhus',
    ' talo ': ' hus ',
}

# List of unsupported service types:
SERVICE_TYPES = {
    'Kotisairaanhoidon palveluyksiköt',
    'Päihdehuollon yksiköt',
    'Kotipalvelun yksiköt',
    'Pankkiautomaatit',
    'Yksityiset hammaslääkäripalvelut',
    'Sähköauton latauspisteet',
    'Yksityiset lääkäripalvelut',
    'Katsastusasema',
    'parking',
    'charity',
    'taxi',
}

# Place regex calls need to cleaned.
SAFE_REGEX = ['\\', '`', '*', '_', '{', '}', '[', ']',
              '(', ')', '>', '#', '+', '.', '!', '$', '\'']


def proc_time_frmt(stage: str) -> None:
    """Formatter for logs."""
    ft = math.modf(time.process_time())
    curtime = float(str(ft[0])[:3])+ft[1]
    logger.info('%s finished after %s seconds from the initial start!' %
                (stage, curtime))


@register_importer
class LounaistietoUnitsImporter(Importer):
    # Importer class dependant attributes:
    name = "lounaistieto_units"  # Command calling name.
    supported_languages = ('fi', 'sv', 'en')  # Base file requirement.
    importer_start_time = BaseModel.now()

    def iterator(self, data: dict, key: str, query: Any, obj_model: tuple, attr_map: tuple) -> None:
        """
        Main class data logic. Create DB objects & set class attributes.
        This was created with easy expandability of the setup data dictionary in mind.
        We are using save() throughout this program to avoid race conditions with update_or_create()
        """
        attrs = iter(attr_map)
        for sub_key in data[key].values():
            q_obj = query()
            for cur_val_idx, current_value in enumerate(sub_key):
                for t_key in data['funcargs']['terms']:
                    for idx, sub_t_key in enumerate(data[t_key]):
                        key_to_find = "%s_%s" % (t_key, sub_t_key)
                        if current_value == key_to_find:
                            current_value = getattr(
                                self, data['attr_maps'][t_key][idx])
                setattr(q_obj, obj_model[cur_val_idx], current_value)
            q_obj.save()
            setattr(self, next(attrs), q_obj)

    def setup(self) -> None:
        """Setup phase with mapped needed data."""
        self.data = {
            # Public organization, PTV and OSM data_source.
            'ds': {
                'org': ('org', 'Ulkoa tuodut organisaatiotiedot', True),
                'tpr': ('tpr', 'Ulkoa tuodut paikkatiedot toimipisteille', True),
                'ptv': ('ptv', 'Palvelutietovaranto (PTV)', True),
                'osm': ('osm', 'OpenStreetMap (OSM)', True),
            },
            # Public organization class for all places.
            'orgclass': {
                'paikka': ('org:12', '12', 'Paikkatieto', BaseModel.now(), 'ds_org'),
            },
            # Organizations for places.
            'org': {
                'tpr': ('tpr:1100', '1100', 'Toimipisterekisteri', BaseModel.now(), 'org:12', 'ds_tpr'),
                'ptv': ('ptv:5000', '5000', 'PTV', BaseModel.now(), 'org:12', 'ds_ptv'),
                'osm': ('osm:6000', '6000', 'OSM', BaseModel.now(), 'org:12', 'ds_osm'),
            },
            # Attribute name mapping for all due to class related attributes (ex. data_source and organization are necessary).
            'attr_maps': {
                'ds': ('data_source', 'data_source_tpr', 'data_source_ptv', 'data_source_osm'),
                'orgclass': ('organization_class_12', ),
                'org': ('organization', 'organization_ptv', 'organization_osm'),
            },
            # Models for easy iteration (Selected attributes):
            'model_maps': {
                'ds': ('id', 'name', 'user_editable'),
                'orgclass': ('id', 'origin_id', 'name', 'created_time', 'data_source_id'),
                'org': ('id', 'origin_id', 'name', 'created_time', 'classification_id', 'data_source_id'),
            },
            # Function arguments.
            'funcargs': {
                'terms': ('ds', 'orgclass', 'org'),
                'termobjs': (DataSource, OrganizationClass, Organization)
            },
        }
        # Keys in data share per element relevant information. Bring together element per key in data dict for iterator params.
        mapped = list(map(lambda f, fto, mm, atm: [f, fto, self.data['model_maps'][mm], self.data['attr_maps'][atm]],
                      self.data['funcargs']['terms'], self.data['funcargs']['termobjs'], self.data['model_maps'], self.data['attr_maps']))
        # Call the iterator function. Params use the mapped elements.
        for args in mapped:
            self.iterator(
                data=self.data, key=args[0], query=args[1], obj_model=args[2], attr_map=args[3])
        proc_time_frmt('Setup')
        self.handle()

    def fetch(self) -> dict:
        """Gets the data synchronously."""
        URL = "https://geoserver.lounaistieto.fi/geoserver/service_points/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=service_points%3Apalvelukohteet&outputFormat=application%2Fjson"
        response = requests.get(URL, headers=HEADERS)
        if response.status_code != 200:
            logger.error(
                "Importing failed. Lounaistieto API responded with status_code: %s" % response.status_code)
            return None
        json_data = response.json()
        return json_data

    def __format_street(self, street_name: str) -> str:
        """Method for getting the street name only."""
        street_num = re.findall(r'[0-9]+', street_name)
        if street_num:
            street_name = street_name.split(street_num[0])[0].strip()
        else:
            street_name = street_name.split(',')[0].strip()
        return street_name

    def build_data(self, unit: dict, geom: dict) -> dict:
        """Processes, validates and builds the data. Skips invalid units."""
        data = {
            'ID': None,
            'ORIGIN_ID': None,
            'DATA_SOURCE': None,
            'NAME': None,
            'POSITION': None,
            'TELEPHONE': None,
            'STREET_ADDRESS': {'fi': None, 'sv': None, 'en': None},
            'EMAIL': None,
            'WWW': None,
            'ADDRESS_LOCALITY': {'fi': None, 'sv': None, 'en': None},
            'POST_CODE': None,
        }

        # Check service type:
        if isinstance(unit.get('palvelukohdetyyppi'), str):
            if unit['palvelukohdetyyppi'] in SERVICE_TYPES:
                logger.warn("Skipping unit due to unsupported service type...")
                return None

        # Get data source:
        if isinstance(unit.get('datalahde'), str):
            if unit['datalahde'] == 'OpenStreetMap':
                data['DATA_SOURCE'] = 'osm'
            elif unit['datalahde'] == 'PTV':
                data['DATA_SOURCE'] = 'ptv'
            else:
                logger.warn(
                    "Unsupported data source for Lounaistieto unit %s" % unit)

        if not data['DATA_SOURCE']:
            return None

        # Get origin ID:
        if isinstance(unit.get('orig_id'), str):
            uid = unit['orig_id'].strip()
            # Some OSM IDs are incorrectly set to negative.
            if uid != '':
                if data['DATA_SOURCE'] == 'osm':
                    try:
                        data['ORIGIN_ID'] = str(abs(int(uid)))
                    except ValueError:
                        logger.warn(
                            "Unexpected OSM ID format. OSM ID can not be converted into an integer: %s" % unit['orig_id'])
                else:
                    data['ORIGIN_ID'] = uid

        if not data['ORIGIN_ID']:
            return None
        else:
            if len(data['ORIGIN_ID']) > 100:
                return None
            # Create ID.
            data['ID'] = '%s:%s' % (data['DATA_SOURCE'], data['ORIGIN_ID'])

        # Get name:
        if isinstance(unit.get('kohteen_nimi'), str):
            name = unit['kohteen_nimi'].strip()
            if name != '':
                if len(name) <= 255:
                    data['NAME'] = name

        if not data['NAME']:
            return None

        # Get position:
        if isinstance(geom, dict):
            coords = geom.get('coordinates')
            if isinstance(coords, list):
                if len(coords) == 2:
                    if all(isinstance(coords[i], (float, int)) for i in range(len(coords))):
                        try:
                            pnt = Point(
                                coords[0], coords[1], srid=3067)
                            data['POSITION'] = pnt
                        except Exception as e:
                            logger.warn(
                                "Could not instantiate the location: %s" % e)

        # Get telephone:
        if isinstance(unit.get('puhelinnumero'), str):
            phone = unit['puhelinnumero'].strip()
            if phone != '':
                if len(phone) <= 128:
                    data['TELEPHONE'] = phone

        # Get osoite:
        if isinstance(unit.get('osoite'), str):
            street = self.__format_street(street_name=unit['osoite'])
            if street:
                if street.strip() != '':
                    # Safeguard from regex manipulation:
                    for ch in SAFE_REGEX:
                        street = street.replace(ch, '')

                    # Get the municipality:
                    splt = unit['osoite'].split(',')
                    if len(splt) > 1:
                        if len(splt) == 3:
                            # For parsing OSM streets:
                            splt[1] = splt[1] + splt[2]
                            splt = splt[:-1]
                        munisplt = splt[-1].strip().split(' ', 1)
                        if len(munisplt) == 2:
                            muni = munisplt[1].upper()
                            if muni in MUNICIPALITIES:
                                for idx, lang in enumerate(('fi', 'sv')):
                                    data['ADDRESS_LOCALITY'][lang] = MUNICIPALITIES[muni][idx]
                            else:
                                # We don't import units that are outside our region.
                                return None
                            post_code = munisplt[0]
                            if post_code != '':
                                data['POST_CODE'] = post_code
                    data['STREET_ADDRESS']['fi'] = unit['osoite']
                    # Find the street from the street registry.
                    try:
                        addr = Place.objects.filter(data_source_id='osoite', address_locality_fi=data['ADDRESS_LOCALITY']['fi']).filter(
                            **{"name__regex": r'^%s' % street})[:1]
                        if addr:
                            for addr_obj in addr:
                                if isinstance(addr_obj.name_sv, str):
                                    street_sv = self.__format_street(
                                        street_name=addr_obj.name_sv)
                                    data['STREET_ADDRESS']['sv'] = unit['osoite'].replace(
                                        street, street_sv)
                                    for r, v in REPLACEMENTS.items():
                                        data['STREET_ADDRESS']['sv'] = data['STREET_ADDRESS']['sv'].replace(
                                            r, v)

                    except Exception as e:
                        logger.error("Error while finding the address: %s" % e)

                    if data['ADDRESS_LOCALITY']['fi'] and data['ADDRESS_LOCALITY']['sv']:
                        for lang in ('fi', 'sv'):
                            if isinstance(data['STREET_ADDRESS'][lang], str):
                                data['STREET_ADDRESS'][lang] = data['STREET_ADDRESS'][lang].replace(
                                    data['ADDRESS_LOCALITY']['fi'].upper(), data['ADDRESS_LOCALITY'][lang])

        # Get email:
        if isinstance(unit.get('sahkoposti'), str):
            email = unit['sahkoposti'].strip()
            if 3 <= len(email) <= 254:
                try:
                    validate_email(email)
                except ValidationError as e:
                    logger.warn("Improper email: %s with details: %s" %
                                (email, e))
                else:
                    data['EMAIL'] = email

        # Get website:
        if isinstance(unit.get('verkkosivu'), str):
            website = unit['verkkosivu'].strip()
            if 3 <= len(website) <= 1000:
                try:
                    URLValidator(website)
                except ValidationError as e:
                    logger.warn("Improper URL: %s with details: %s" %
                                (website, e))
                else:
                    data['WWW'] = website

        return data

    def map_new_fields(self, obj: Any, data: dict) -> None:
        """Gives the object attributes new values."""
        obj.position = data['POSITION']
        obj.street_address = obj.street_address_fi = data['STREET_ADDRESS']['fi']
        obj.street_address_sv = data['STREET_ADDRESS']['sv']
        obj.email = data['EMAIL']
        obj.telephone = data['TELEPHONE']
        obj.info_url = obj.info_url_fi = data['WWW']
        obj.address_locality = obj.address_locality_fi = data['ADDRESS_LOCALITY']['fi']
        obj.address_locality_sv = data['ADDRESS_LOCALITY']['sv']
        obj.postal_code = data['POST_CODE']
        if data['DATA_SOURCE'] == 'osm':
            obj.publisher_id = 'osm:6000'
        else:
            obj.publisher_id = 'ptv:5000'

    def save_units(self, unit: dict) -> None:
        """Saving phase"""
        addr = Place.objects.filter(
            data_source__in=['tpr', 'ptv', 'osm']).filter(name=unit['NAME'])[:1]
        if addr:
            # If the name exists. We check if the ID is the current unit ID.
            for addr_obj in addr:
                # Only update the exact ID match unit.
                if unit['ID'] == addr_obj.id:
                    bm_now = BaseModel.now()
                    if (bm_now - addr_obj.last_modified_time) > (bm_now - self.importer_start_time):
                        """
                        If the current object with the specified name did not get modified during import runtime,
                        we can save 'new' data on top of it. Just an extra caution in case 2+ ID duplicates exist.
                        """
                        try:
                            self.map_new_fields(obj=addr_obj, data=unit)
                            addr_obj.save()
                            logger.info(
                                "Saved existing unit: %s with updated data." % unit['ID'])
                        except Exception as e:
                            logger.error(
                                "Could not save unit: %s due to: %s" % (unit['ID'], e))
        else:
            try:
                new_obj = Place(data_source=getattr(
                    self, 'data_source_%s' % unit['DATA_SOURCE']))
                new_obj.id = unit['ID']
                new_obj.origin_id = unit['ORIGIN_ID']
                new_obj.name = new_obj.name_fi = unit['NAME']
                self.map_new_fields(obj=new_obj, data=unit)
                new_obj.save()
                logger.info("Created new unit: %s with name: %s" %
                            (unit['ID'], unit['NAME']))
            except Exception as e:
                logger.error("Could not create unit: %s due to: %s" %
                             (unit['ID'], e))

    def process(self, data: dict) -> None:
        """Processing phase, loops through units."""
        if isinstance(data.get('features'), list):
            for lounais_unit in data['features']:
                if isinstance(lounais_unit.get('properties'), dict):
                    data = self.build_data(
                        unit=lounais_unit['properties'], geom=lounais_unit.get('geometry'))
                    if data:
                        self.save_units(unit=data)

    def remove_old_units(self) -> None:
        """Removes all PTV and OSM units that did not get updated."""
        ptv_osm = Place.objects.filter(
            data_source__in=['ptv', 'osm']).iterator(chunk_size=10)
        if ptv_osm:
            bm_now = BaseModel.now()
            for existing_obj in ptv_osm:
                if (bm_now - existing_obj.last_modified_time) > (bm_now - self.importer_start_time):
                    # This means we know that the object did not get updated during runtime.
                    try:
                        logger.info("Removing old unit: %s with name: %s" % (
                            existing_obj.id, existing_obj.name))
                        existing_obj.delete()
                    except Exception as e:
                        logger.error("Could not remove old unit: %s due to: %s" % (
                            existing_obj.id, e))

    def handle(self) -> None:
        """The core handler function."""
        data = self.fetch()
        proc_time_frmt('Fetching')
        self.process(data=data)
        proc_time_frmt('Processing and saving')
        self.remove_old_units()
        proc_time_frmt('Removing old units')
        proc_time_frmt('Importer')
