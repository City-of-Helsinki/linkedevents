import re
import dateutil.parser
import requests
import requests_cache
from django.db.models import Count

from lxml import etree

from events.models import DataSource, Place, Event

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

    def _find_place(self, event):
        place_name = event['location']['name']['fi']
        if not place_name:
            return
        place_name = place_name.lower()
        place_id = None
        if place_name in self.tprek_by_name:
            place_id, tprek_id = self.tprek_by_name[place_name]
        elif place_name in LOCATION_TPREK_MAP:
            tprek_id = LOCATION_TPREK_MAP[place_name]
        else:
            print("No match found for location %s" % place_name)
            return

        if tprek_id and not place_id:
            place_id = Place.objects.get(data_source=self.tprek_data_source, origin_id=tprek_id).id

        event['location']['id'] = place_id

    def _import_event_from_feed(self, lang_code, item, events):
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
        event['location']['info'][lang_code] = text(item, 'placeinfo')

        self.put(event, 'start_time', start_time)
        self.put(event, 'end_time', end_time)
        self.put(event, 'event_status', matko_status(int(text(item, 'status'))))
        self.put(event['location'], 'matko_location_id', int(text(item, 'placeuniqueid')))

        # FIXME: Place matching for events that are only in English (or Swedish)
        if lang_code == 'fi':
            self._find_place(event)

        return events

    def _import_locations_from_feed(self, lang_code, items, locations):
        for item in items:
            if clean_text(text(item, 'isvenue')) == 'False':
                continue

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
                self.put(location, 'geo', {
                    'longitude': lon,
                    'latitude': lat,
                    'geo_type': 1})

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
        for lang, url in MATKO_URLS['events'].items():
            items = self.items_from_url(url)
            for item in items:
                self._import_event_from_feed(lang, item, events)
            organizers = self._import_organizers_from_events(events)

        errors = set()
        for event in events.values():
            event_errors = self.save_event(event)
            errors.update(event_errors)
        print("%d events added" % len(events.values()))
        if len(errors) > 0:
            print('Errors:')
        for e in errors:
            print("%s: %s" % (e[0], u" ".join(e[1])))

    def import_locations(self):
        print("Importing Matko locations")
        locations = recur_dict()
        for lang, url in MATKO_URLS['locations'].items():
            items = self.items_from_url(url)
            self._import_locations_from_feed(lang, items, locations)
        for location in locations.values():
            self.save_location(location)
