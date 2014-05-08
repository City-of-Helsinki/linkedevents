# -*- coding: utf-8 -*-
import re
import dateutil.parser
import requests
import requests_cache
from django.db.models import Count

from lxml import etree

from events.models import DataSource, Place, Event
from events.categories import CategoryMatcher

from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
from .util import clean_text, unicodetext

MATKO_URLS = {
    'locations': {
        'fi': 'http://www.visithelsinki.fi/misc/feeds/helsinki_matkailu_poi.xml',
        'en': 'http://www.visithelsinki.fi/misc/feeds/helsinki_tourism_poi.xml',
        'sv': 'http://www.visithelsinki.fi/misc/feeds/helsingfors_turism_poi.xml',
    },
    'events': {
        'fi': 'http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat.xml',
        'en': 'http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat_en.xml',
        'sv': 'http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat_se.xml',
    }
}

LOCATION_TPREK_MAP = {
    'helsingin kaupunginteatteri / lilla teatern': '9353',
    'helsingin kaupunginteatteri / teatteristudio pasila': '9340',
    'finlandia-talo': '9294',
    'hietaniemen uimaranta': '7766',
    'helsingin kaupunginmuseo': '8663',
    'helsingin kaupunginmuseo/ hakasalmen huvila': '8645',
}

EXTRA_LOCATIONS = {
    732: {
        'name': {
            'fi': 'Helsinki',
            'sv': 'Helgingfors',
            'en': 'Helsinki',
        },
        'address': {
            'address_locality': {
                'fi': 'Helsinki',
            }
        },
        'latitude': 60.170833,
        'longitude': 24.9375,
    },
    1101: {
        'name': {
            'fi': 'Helsingin keskusta',
            'sv': 'Helgingfors centrum',
            'en': 'Helsinki City Centre',
        },
        'address': {
            'address_locality': {
                'fi': 'Helsinki',
            }
        },
        'latitude': 60.170833,
        'longitude': 24.9375,
    }
}

def matko_tag(tag):
    return '{https://aspicore-asp.net/matkoschema/}' + tag

def text(item, tag):
    return unicodetext(item.find(matko_tag(tag)))

def matko_status(num):
    if num == 2:
        return Event.SCHEDULED
    if num == 3:
        return Event.CANCELLED
    return None

def standardize_event_types(types):
    # fixme align with existing categories
    pass

def standardize_accessibility(accessibility, lang):
    pass

def zipcode_and_muni(text):
    if text is None:
        return None, None
    m = re.match(r'\D*(\d+)\s+(\D+)', text)
    if m is not None:
        return m.group(1), m.group(2).strip()
    return None, None


@register_importer
class MatkoImporter(Importer):
    name = "matko"
    supported_languages = ['fi', 'sv', 'en']

    def put(self, rdict, key, val):
        if key not in rdict:
            rdict[key] = val
        elif val != rdict[key]:
            self.logger.info('Values differ for %s, key %s, values %s and %s ' % (
                rdict, key, val, rdict[key]))

    def setup(self):
        defaults = dict(name='Matkailu- ja kongressitoimisto',
                        event_url_template='https://aspicore-asp.net/helsinki/xml/tapahtuma{origin_id}')
        self.data_source, _ = DataSource.objects.get_or_create(id=self.name, defaults=defaults)
        self.tprek_data_source = DataSource.objects.get(id='tprek')

        place_list = Place.objects.filter(data_source=self.tprek_data_source)
        # Get only places that have unique names
        place_list = place_list.annotate(count=Count('name_fi')).filter(count=1).values('id', 'origin_id', 'name_fi')
        self.tprek_by_name = {p['name_fi'].lower(): (p['id'], p['origin_id']) for p in place_list}

        if self.options['cached']:
            requests_cache.install_cache('matko')

    def _import_common(self, lang_code, item, result):
        result['name'][lang_code] = clean_text(unicodetext(item.find('title')))
        result['description'][lang_code] = unicodetext(item.find('description'))

        link = item.find('link')
        if link is not None:
            result['url'][lang_code] = unicodetext(link)

        typestring = text(item, 'type2') or text(item, 'type1')
        if typestring is not None:
            types = [t.strip() for t in typestring.split(",")]
            # The first letter is always capitalized in the source.
            types[0] = types[0].lower()
            self.put(result, 'types', types)

    def _find_place_from_tprek(self, location):
        place_name = location['name']['fi']
        if not place_name:
            return
        place_name = place_name.lower()
        place_id = None
        if place_name in self.tprek_by_name:
            place_id, tprek_id = self.tprek_by_name[place_name]
        elif place_name in LOCATION_TPREK_MAP:
            tprek_id = LOCATION_TPREK_MAP[place_name]
        else:
            return None

        if tprek_id and not place_id:
            place_id = Place.objects.get(data_source=self.tprek_data_source, origin_id=tprek_id).id

        return place_id

    def _find_place(self, location):
        place_id = self._find_place_from_tprek(location)
        if place_id:
            return place_id

        # No tprek match found, attempt to find the right entry from matko locations.
        matko_id = location['origin_id']
        try:
            place = Place.objects.get(data_source=self.data_source, origin_id=matko_id)
        except Place.DoesNotExist:
            place = None

        # No existing entry, load it from Matko.
        if not place:
            locations = self._fetch_locations()
            from pprint import pprint
            if matko_id not in locations:
                print("Matko location %s (%s) not found!" % (
                    location['name']['fi'], location['origin_id']))
                return None
            pprint(locations[matko_id])
            place = self.save_location(locations[matko_id])

        return place.id

    def _import_event_from_feed(self, lang_code, item, events, category_matcher):
        eid = int(text(item, 'uniqueid'))
        event = events[eid]

        if eid != int(text(item, 'id')):
            self.logger.info(
                'Unique id and id values differ for id %d uid %s' % (
                    eid, text(item, 'id')))

        event['origin_id'] = eid
        event['data_source'] = self.data_source
        event['date_published'] = dateutil.parser.parse(
            unicodetext(item.find('pubDate'))
        )

        self._import_common(lang_code, item, event)

        organizer = text(item, 'organizer')
        organizer_phone = text(item, 'organizerphone')

        if organizer is not None:
            event['organizer']['name'][lang_code] = clean_text(organizer)
        if organizer_phone is not None:
            event['organizer']['phone'][lang_code] = [
                clean_text(t) for t in organizer_phone.split(",")]

        start_time = dateutil.parser.parse(
            text(item, 'starttime'))

        # The feed doesn't contain proper end times (clock).
        end_time = dateutil.parser.parse(
            text(item, 'endtime'))

        standardize_event_types(event['types'])

        event['location']['name'][lang_code] = text(item, 'place')
        event['location']['extra_info'][lang_code] = text(item, 'placeinfo')

        self.put(event, 'start_time', start_time)
        self.put(event, 'end_time', end_time)
        self.put(event, 'event_status', matko_status(int(text(item, 'status'))))
        self.put(event['location'], 'origin_id', int(text(item, 'placeuniqueid')))

        ignore = [
            'ekokompassi',
            'helsinki-päivä',
            'helsinki-viikko',
            'top',
            'muu',
            'tapahtuma',
            'kesä',
            'talvi'
        ]
        use_as_target_group = [ # fixme
            'koko perheelle'
        ]
        mapping = {
            'tanssi ja teatteri': 'tanssi', # following visithelsinki.fi
            'messu': 'messut',
            'perinnetapahtuma': 'perinne',
            'pop/rock': 'populaarimusiikki',
            'konsertti': 'konsertit',
            'klassinen': 'klassinen musiikki',
            'kulttuuri': 'kulttuuritapahtumat'
        }

        categories = set()
        cat1, cat2 = text(item, 'type1'), text(item, 'type2')
        for c in (cat1, cat2):
            if c:
                categories.update(
                    map(lambda x: x.lower(), c.split(",")))

        keywords = []
        for c in categories:
            if c is None or c in ignore or c in use_as_target_group:
                continue
            if c in mapping:
                c = mapping[c]
            keyword = category_matcher.match(c)
            if keyword:
                keywords.append(keyword[0])
        if len(keywords) > 0:
            event['keywords'] = keywords
        else:
            print('Warning: no keyword matches for', event['name'], keywords)

        # FIXME: Place matching for events that are only in English (or Swedish)
        if lang_code == 'fi':
            place_id = self._find_place(event['location'])
            if place_id:
                event['location']['id'] = place_id

        return events

    def _parse_location(self, lang_code, item, locations):
        #if clean_text(text(item, 'isvenue')) == 'False':
        #    return

        lid = int(text(item, 'id'))
        location = locations[lid]

        location['origin_id'] = lid
        location['data_source'] = self.data_source

        self._import_common(lang_code, item, location)

        address = text(item, 'address')
        if address is not None:
            location['address']['street_address'][lang_code] = clean_text(address)

        zipcode, muni = zipcode_and_muni(text(item, 'zipcode'))
        if zipcode and len(zipcode) == 5:
            location['address']['postal_code'] = zipcode
        location['address']['address_locality'][lang_code] = muni
        location['address']['phone'][lang_code] = text(item, 'phone')
        # There was at least one case with different
        # email addresses for different languages.
        location['address']['email'][lang_code] = text(item, 'email')

        # not available in schema.org:
        # location['address']['fax'][lang_code] = text(item, 'fax')
        # location['directions'][lang_code] = text(item, 'location')
        # location['admission_fee'][lang_code] = text(item, 'admission')

        # todo: parse
        # location['opening_hours'][lang_code] = text(item, 'open')
        location['custom_fields']['accessibility'][lang_code] = text(item, 'disabled')

        standardize_accessibility(
            location['custom_fields']['accessibility'][lang_code], lang_code)

        lon, lat = clean_text(text(item, 'longitude')), clean_text(text(item, 'latitude'))
        if lon != '0' and lat != '0':
            self.put(location, 'longitude', float(lon))
            self.put(location, 'latitude', float(lat))

    def _parse_locations_from_feed(self, lang_code, items, locations):
        for item in items:
            self._parse_location(lang_code, item, locations)

        return locations

    def _import_organizers_from_events(self, events):
        organizers = recur_dict()
        for k, event in events.items():
            if not 'organizer' in event:
                continue
            organizer = event['organizer']
            if not 'name' in organizer or not 'fi' in organizer['name']:
                continue
            oid = organizer['name']['fi']
            organizers[oid]['name'].update(organizer['name'])
            organizers[oid]['phone'].update(organizer['phone'])
        return organizers

    def items_from_url(self, url):
        resp = requests.get(url)
        assert resp.status_code == 200
        root = etree.fromstring(resp.content)
        return root.xpath('channel/item')

    def import_events(self):
        print("Importing Matko events")
        events = recur_dict()
        category_matcher = CategoryMatcher()
        for lang, url in MATKO_URLS['events'].items():
            items = self.items_from_url(url)
            for item in items:
                self._import_event_from_feed(lang, item, events, category_matcher)
            organizers = self._import_organizers_from_events(events)

        for event in events.values():
            self.save_event(event)
        print("%d events processed" % len(events.values()))

    def _fetch_locations(self):
        if hasattr(self, 'locations'):
            return self.locations

        locations = recur_dict()

        for origin_id, loc_info in EXTRA_LOCATIONS.items():
            loc = loc_info.copy()
            loc['data_source'] = self.data_source
            loc['origin_id'] = origin_id
            locations[origin_id] = loc

        for lang, url in MATKO_URLS['locations'].items():
            items = self.items_from_url(url)
            self._parse_locations_from_feed(lang, items, locations)

        self.locations = locations

        return locations

    def import_locations(self):
        self._fetch_locations()
        place_list = Place.objects.filter(data_source=self.data_source)
        for place in place_list:
            origin_id = int(place.origin_id)
            if origin_id not in self.locations:
                self.logger.warning("%s not found in Matko locations" % place)
                continue
            location = self.locations[origin_id]
            self.save_location(location)
