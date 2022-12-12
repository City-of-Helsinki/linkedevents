"""
munigeo importer for Helsinki data
"""

import os
import re
import requests
import yaml

from django import db
from datetime import datetime

from django.contrib.gis.gdal import DataSource, SpatialReference, CoordTransform
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point
from django.contrib.gis import gdal

from munigeo.models import *
from munigeo.importer.sync import ModelSyncher
from munigeo import ocd

from munigeo.importer.base import Importer, register_importer

MUNI_URL = "http://tilastokeskus.fi/meta/luokitukset/kunta/001-2013/tekstitiedosto.txt"

# The Finnish national grid coordinates in TM35-FIN according to JHS-180
# specification. We use it as a bounding box.
FIN_GRID = [-548576, 6291456, 1548576, 8388608]
TM35_SRID = 3067

SERVICE_CATEGORY_MAP = {
    25480: ("library", "Library"),
    28148: ("swimming_pool", "Swimming pool"),
    25402: ("toilet", "Toilet"),
    25344: ("recycling", "Recycling point"),
    25664: ("park", "Park"),
}


GK25_SRID = 3879
GK25_SRS = SpatialReference(GK25_SRID)
PROJECTION_SRS = SpatialReference(PROJECTION_SRID)
WEB_MERCATOR_SRS = SpatialReference(3857)

coord_transform = None
if GK25_SRS.srid != PROJECTION_SRID:
    target_srs = SpatialReference(PROJECTION_SRID)
    coord_transform = CoordTransform(GK25_SRS, target_srs)

def convert_from_gk25(north, east):
    ps = "POINT (%f %f)" % (east, north)
    g = gdal.OGRGeometry(ps, GK25_SRS)
    if coord_transform:
        g.transform(coord_transform)
    return g

    pnt = Point(east, north, srid=GK25_SRID)
    if PROJECTION_SRID == GK25_SRID:
        return pnt
    pnt.transform(coord_transform)
    return pnt

def poly_diff(p1, p2):
    # Make sure we calculate the area with a 2d coordinate system
    if p1.srs.units[1] == 'degree':
        tf = CoordTransform(p1.srs, WEB_MERCATOR_SRS)
        p1 = p1.clone()
        p1.transform(tf)
        p2 = p2.clone()
        p2.transform(tf)
    return (p1 - p2).area


@register_importer
class HelsinkiImporter(Importer):
    name = "helsinki"

    def __init__(self, *args, **kwargs):
        super(HelsinkiImporter, self).__init__(*args, **kwargs)
        self.muni_data_path = 'fi/helsinki'

    def _find_parent_division(self, parent_info):
        args = {
            'type__type': parent_info['type'], 
            'origin_id': parent_info['id'],
            'parent__parent': parent_info['parent']
        }
        return AdministrativeDivision.objects.get(**args)

    def _import_division(self, muni, div, type_obj, syncher, parent_dict, feat):
        #
        # Geometry
        #
        geom = feat.geom
        if not geom.srid:
            geom.srid = GK25_SRID
        if geom.srid != PROJECTION_SRID:
            ct = CoordTransform(SpatialReference(geom.srid), SpatialReference(PROJECTION_SRID))
            geom.transform(ct)
        # geom = geom.geos.intersection(parent.geometry.boundary)
        geom = geom.geos
        if geom.geom_type == 'Polygon':
            geom = MultiPolygon(geom, srid=geom.srid)

        #
        # Attributes
        #
        attr_dict = {}
        lang_dict = {}
        for attr, field in div['fields'].items():
            if isinstance(field, dict):
                # Languages
                d = {}
                for lang, field_name in field.items():
                    val = feat[field_name].as_string()
                    # If the name is in all caps, fix capitalization.
                    if not re.search('[a-z]', val):
                        val = val.title()
                    d[lang] = val.strip()
                lang_dict[attr] = d
            else:
                val = feat[field].as_string()
                attr_dict[attr] = val.strip()

        origin_id = attr_dict['origin_id']
        del attr_dict['origin_id']

        if 'parent' in div:
            if 'parent_id' in attr_dict:
                parent = parent_dict[attr_dict['parent_id']]
                del attr_dict['parent_id']
            else:
                # If no parent id is available, we determine the parent
                # heuristically by choosing the one that we overlap with
                # the most.
                parents = []
                for parent in parent_dict.values():
                    diff_area = poly_diff(geom, parent.geometry.boundary)
                    if diff_area < 300:
                        parents.append(parent)
                if not parents:
                    raise Exception("No parent found for %s" % origin_id)
                elif len(parents) > 1:
                    raise Exception("Too many parents for %s" % origin_id)
                parent = parents[0]
        elif 'parent_ocd_id' in div:
            try:
                parent = AdministrativeDivision.objects.get(ocd_id=div['parent_ocd_id'])
            except AdministrativeDivision.DoesNotExist:
                parent = None
        else:
            parent = muni.division

        if 'parent' in div and parent:
            full_id = "%s-%s" % (parent.origin_id, origin_id)
        else:
            full_id = origin_id
        obj = syncher.get(full_id)
        if not obj:
            obj = AdministrativeDivision(origin_id=origin_id, type=type_obj)

        validity_time_period = div.get('validity')
        if validity_time_period:
            obj.start = validity_time_period.get('start')
            obj.end = validity_time_period.get('end')
            if obj.start:
                obj.start = datetime.strptime(obj.start, '%Y-%m-%d').date()
            if obj.end:
                obj.end = datetime.strptime(obj.end, '%Y-%m-%d').date()

        if div.get('no_parent_division', False):
            muni = None

        obj.parent = parent
        obj.municipality = muni

        for attr in attr_dict.keys():
            setattr(obj, attr, attr_dict[attr])
        for attr in lang_dict.keys():
            for lang, val in lang_dict[attr].items():
                key = "%s_%s" % (attr, lang)
                setattr(obj, key, val)

        if 'ocd_id' in div:
            assert (parent and parent.ocd_id) or 'parent_ocd_id' in div
            if parent:
                if div.get('parent_in_ocd_id', False):
                    args = {'parent': parent.ocd_id}
                else:
                    args = {'parent': muni.division.ocd_id}
            else:
                args = {'parent': div['parent_ocd_id']}
            val = attr_dict['ocd_id']
            args[div['ocd_id']] = val
            obj.ocd_id = ocd.make_id(**args)
            self.logger.debug("%s" % obj.ocd_id)
        obj.save()
        syncher.mark(obj)

        try:
            geom_obj = obj.geometry
        except AdministrativeDivisionGeometry.DoesNotExist:
            geom_obj = AdministrativeDivisionGeometry(division=obj)

        geom_obj.boundary = geom
        geom_obj.save()

    @db.transaction.atomic
    def _import_one_division_type(self, muni, div):
        def make_div_id(obj):
            if 'parent' in div:
                return "%s-%s" % (obj.parent.origin_id, obj.origin_id)
            else:
                return obj.origin_id

        self.logger.info(div['name'])
        if not 'origin_id' in div['fields']:
            raise Exception("Field 'origin_id' not defined in config section '%s'" % div['name'])
        try:
            type_obj = AdministrativeDivisionType.objects.get(type=div['type'])
        except AdministrativeDivisionType.DoesNotExist:
            type_obj = AdministrativeDivisionType(type=div['type'])
            type_obj.name = div['name']
            type_obj.save()

        div_qs = AdministrativeDivision.objects.filter(type=type_obj)
        if not div.get('no_parent_division', False):
            div_qs = div_qs.by_ancestor(muni.division).select_related('parent')
        syncher = ModelSyncher(div_qs, make_div_id)

        # Cache the list of possible parents. Assumes parents are imported
        # first.
        if 'parent' in div:
            parent_list = AdministrativeDivision.objects.\
                filter(type__type=div['parent']).by_ancestor(muni.division)
            parent_dict = {}
            for o in parent_list:
                assert o.origin_id not in parent_dict
                parent_dict[o.origin_id] = o
        else:
            parent_dict = None

        if 'file' in div:
            path = self.find_data_file(os.path.join(self.division_data_path, div['file']))
            ds = DataSource(path, encoding='iso8859-1')
        else:
            wfs_url = 'WFS:' + div['wfs_url']
            if '?' in wfs_url:
                sep = '&'
            else:
                sep = '?'
            url = wfs_url + sep + 'typeName=' + div['wfs_layer'] + '&' + "srsName=EPSG:%d" % PROJECTION_SRID + '&' + "outputFormat=application/json"
            ds = DataSource(url)
        lyr = ds[0]
        assert len(ds) == 1
        with AdministrativeDivision.objects.delay_mptt_updates():
            for feat in lyr:
                self._import_division(muni, div, type_obj, syncher, parent_dict, feat)

    def import_divisions(self):
        path = self.find_data_file(os.path.join(self.muni_data_path, 'config.yml'))
        config = yaml.safe_load(open(path, 'r', encoding='utf-8'))
        self.division_data_path = os.path.join(self.muni_data_path, config['paths']['division'])

        muni = Municipality.objects.get(division__origin_id=config['origin_id'])
        self.muni = muni
        for div in config['divisions']:
            try:
                self._import_one_division_type(muni, div)
            except GDALException as e:
                self.logger.warning('Skipping division %s : %s' % (div, e))

    def _import_plans(self, fname, in_effect):
        path = os.path.join(self.data_path, 'kaavahakemisto', fname)
        ds = DataSource(path, encoding='iso8859-1')
        lyr = ds[0]

        for idx, feat in enumerate(lyr):
            origin_id = feat['kaavatunnus'].as_string()
            geom = feat.geom
            geom.srid = GK25_SRID
            geom.transform(PROJECTION_SRID)
            if origin_id not in self.plan_map:
                obj = Plan(origin_id=origin_id, municipality=self.muni)
                self.plan_map[origin_id] = obj
            else:
                obj = self.plan_map[origin_id]
                if not obj.found:
                    obj.geometry = None
            poly = GEOSGeometry(geom.wkb, srid=geom.srid)
            if obj.geometry:
                obj.geometry.append(poly)
            else:
                obj.geometry = MultiPolygon(poly)
            obj.in_effect = in_effect
            obj.found = True
            if (idx % 500) == 0:
                self.logger.info("%d imported" % idx)
        if in_effect:
            type_str = "in effect"
        else:
            type_str = "development"
        self.logger.info("%d %s plans imported" % (idx, type_str))

    def import_plans(self):
        self.plan_map = {}
        self.muni = Municipality.objects.get(name="Helsinki")
        for obj in Plan.objects.filter(municipality=self.muni):
            self.plan_map[obj.origin_id] = obj
            obj.found = False
        self._import_plans('Lv_rajaus.TAB', True)
        self._import_plans('Kaava_vir_rajaus.TAB', False)
        self.logger.info("Saving")
        for key, obj in self.plan_map.items():
            if obj.found:
                obj.save()
            else:
                self.logger.info("Plan %s deleted" % obj.name)

    @db.transaction.atomic
    def import_addresses(self):

        #wfs_url = 'WFS:https://kartta.hel.fi/ws/geoserver/avoindata/wfs?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=avoindata:PKS_osoiteluettelo&SRSNAME=EPSG:3067&outputFormat=application/json'
        wfs_url = 'http://kartta.hel.fi/ws/geoserver/avoindata/wfs?' \
                  'SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&' \
                  'TYPENAME=avoindata:PKS_osoiteluettelo&' \
                  'SRSNAME=EPSG:3067&outputFormat=application/json'

        self.logger.info("Loading master data from WFS datasource")
        ds = DataSource(wfs_url)
        lyr = ds[0]
        assert len(ds) == 1

        muni_names = ('Helsinki', 'Espoo', 'Vantaa', 'Kauniainen')
        muni_list = Municipality.objects.filter(name_fi__in=muni_names)
        muni_dict = {}

        def make_addr_id(num, num_end, letter):
            if num_end is None:
                num_end = ''
            if letter is None:
                letter = ''
            return '%s-%s-%s' % (num, num_end, letter)

        for muni in muni_list:
            muni_dict[muni.name_fi] = muni

            self.logger.info("Loading existing data for {}".format(muni))

            streets = Street.objects.filter(municipality=muni)
            muni.streets_by_name = {}
            muni.streets_by_id = {}
            for s in streets:
                muni.streets_by_name[s.name_fi] = s
                muni.streets_by_id[s.id] = s
                s.addrs = {}
                s._found = False

            addr_list = Address.objects.filter(street__municipality=muni)
            for a in addr_list:
                a._found = False
                street = muni.streets_by_id[a.street_id]
                street.addrs[make_addr_id(a.number, a.number_end, a.letter)] = a

        bulk_addr_list = []
        bulk_street_list = []
        count = 0

        self.logger.info("starting data synchronization")
        for feat in lyr:
            count += 1
            if count % 1000 == 0:
                self.logger.debug("{} processed".format(count))

            street_name = feat.get('katunimi').strip()
            street_name_sv = feat.get('gatan').strip()
            num = feat.get('osoitenumero')

            if not num:
                self.logger.debug("Rejecting {}, due to {} not being valid street number".format(street_name, num))
                continue
            else:
                if num == '0':
                    self.logger.debug("Rejecting {}, due to {} not being valid street number".format(street_name, num))
                    continue

            num2 = feat.get('osoitenumero2')
            if num2 == 0:
                num2 = ''
            letter = feat.get('osoitekirjain').strip()
            coord_n = int(feat.get('n'))
            coord_e = int(feat.get('e'))
            muni_name = feat.get('kaupunki')

            muni = muni_dict[muni_name]
            street = muni.streets_by_name.get(street_name, None)
            if not street:
                self.logger.info("street {} not found in DB, creating it".format(street_name))
                street = Street(name_fi=street_name, name=street_name, municipality=muni)
                street.name_sv = street_name_sv

                #bulk_street_list.append(street)
                street.save()
                muni.streets_by_name[street_name] = street
                street.addrs = {}
            else:
                if street.name_sv != street_name_sv:
                    self.logger.warning("{}: {} -> {}".format(street, street.name_sv, street_name_sv))
                    street.name_sv = street_name_sv
                    street.save()
            street._found = True

            addr_id = make_addr_id(num, num2, letter)
            addr = street.addrs.get(addr_id, None)
            location = convert_from_gk25(coord_n, coord_e)
            if not addr:
                self.logger.debug("Street {} did not have address {}. Creating".format(street.name, addr_id))
                addr = Address(street=street, number=num, number_end=num2, letter=letter)
                addr.location = location.wkb
                bulk_addr_list.append(addr)
                street.addrs[addr_id] = addr
            else:
                if addr._found:
                    self.logger.debug("{}: is duplicate, skipping".format(addr))
                    continue
                # if the location has changed for more than 10cm, save the new one.
                assert addr.location.srid == location.srid, "SRID changed"
                #if addr.location.distance(location) >= 0.10:
                #    self.logger.info("%s: Location changed" % addr)
                #    addr.location = location
                #    addr.save()
            addr._found = True

            # self.logger.info("%s: %s %d%s N%d E%d (%f,%f)" % (muni_name, street, num, letter, coord_n, coord_e, pnt.y, pnt.x))

            if len(bulk_addr_list) >= 10000:
                self.logger.info("Saving %d new addresses" % len(bulk_addr_list))

                Address.objects.bulk_create(bulk_addr_list)
                bulk_addr_list = []

                # Reset DB query store to free up memory
                db.reset_queries()

        if bulk_addr_list:
            self.logger.info("Saving {} new addresses".format(len(bulk_addr_list)))
            Address.objects.bulk_create(bulk_addr_list)
            bulk_addr_list = []

        for muni in muni_list:
            for s in muni.streets_by_name.values():
                if not s._found:
                    self.logger.info("Street {} removed".format(s))
                    s.delete()
                    continue
                for a in s.addrs.values():
                    if not a._found:
                        self.logger.info("Address {} removed".format(a))
                        a.delete()

        self.logger.info("synchronization complete")

    def import_pois(self):
        URL_BASE = 'http://www.hel.fi/palvelukarttaws/rest/v2/unit/?service=%d'

        muni_dict = {}
        for muni in Municipality.objects.all():
            muni_dict[muni.name] = muni

        for srv_id in list(SERVICE_CATEGORY_MAP.keys()):
            cat_type, cat_desc = SERVICE_CATEGORY_MAP[srv_id]
            cat, c = POICategory.objects.get_or_create(type=cat_type, defaults={'description': cat_desc})

            self.logger.info("Importing %s" % cat_type)
            ret = requests.get(URL_BASE % srv_id)
            for srv_info in ret.json():
                srv_id = str(srv_info['id'])
                try:
                    poi = POI.objects.get(origin_id=srv_id)
                except POI.DoesNotExist:
                    poi = POI(origin_id=srv_id)
                poi.name = srv_info['name_fi']
                poi.category = cat
                if not 'address_city_fi' in srv_info:
                    self.logger.info("No city!")
                    self.logger.info(srv_info)
                    continue
                city_name = srv_info['address_city_fi']
                if not city_name in muni_dict:
                    city_name = city_name.encode('utf8')
                    post_code = srv_info.get('address_zip', '')
                    if post_code.startswith('00'):
                        self.logger.info("%s: %s (%s)" % (srv_info['id'], poi.name.encode('utf8'), city_name))
                        city_name = "Helsinki"
                    elif post_code.startswith('01'):
                        self.logger.info("%s: %s (%s)" % (srv_info['id'], poi.name.encode('utf8'), city_name))
                        city_name = "Vantaa"
                    elif post_code in ('02700', '02701', '02760'):
                        self.logger.info("%s: %s (%s)" % (srv_info['id'], poi.name.encode('utf8'), city_name))
                        city_name = "Kauniainen"
                    elif post_code.startswith('02'):
                        self.logger.info("%s: %s (%s)" % (srv_info['id'], poi.name.encode('utf8'), city_name))
                        city_name = "Espoo"
                    else:
                        self.logger.info(srv_info)
                poi.municipality = muni_dict[city_name]
                poi.street_address = srv_info.get('street_address_fi', None)
                poi.zip_code = srv_info.get('address_zip', None)
                if not 'northing_etrs_gk25' in srv_info:
                    self.logger.info("No location!")
                    self.logger.info(srv_info)
                    continue
                poi.location = convert_from_gk25(srv_info['northing_etrs_gk25'], srv_info['easting_etrs_gk25'])
                poi.save()
