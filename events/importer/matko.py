import re
import dateutil.parser
import requests
import requests_cache
from collections import defaultdict
from lxml import etree

from events.models import *

from .sync import ModelSyncher
from .base import Importer, register_importer

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


def clean_text(text):
    text = text.replace('\n', ' ')
    # remove consecutive whitespaces
    return re.sub(r'\s\s+', ' ', text, re.U).strip()


def matko_tag(tag):
    return '{https://aspicore-asp.net/matkoschema/}' + tag


def matko_status(num):
    if num == 2:
        return Event.SCHEDULED
    if num == 3:
        return Event.CANCELLED
    return None


def unicodetext(item):
    return etree.tostring(item, encoding='unicode', method='text')


def text(item, tag):
    return unicodetext(item.find(matko_tag(tag)))


def standardize_event_types(types):
    # fixme align with existing categories
    pass


def standardize_accessibility(accessibility, lang):
    pass


# Using a recursive default dictionary
# allows easy updating of same data
# with different languages on different passes.
def recur_dict(): return defaultdict(recur_dict)


def put(rdict, key, val):
    if key not in rdict:
        rdict[key] = val
    elif val != rdict[key]:
        logger.info('Values differ for %s, key %s, values %s and %s ' % (
            rdict, key, val, rdict[key]))


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
    data_source = DataSource.objects.get(pk=name)

    def setup(self):
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
            put(result, 'types', types)

    def _import_events_from_feed(self, lang_code, items, events):
        for item in items:
            eid = int(text(item, 'uniqueid'))
            event = events[eid]

            if eid != int(text(item, 'id')):
                self.logger.info(
                    'Unique id and id values differ for id %d uid %s' % (
                        eid, text(item, 'id')))

            event['instance']['origin_id'] = eid
            event['common']['data_source'] = self.data_source
            event['instance']['date_published'] = dateutil.parser.parse(
                unicodetext(item.find('pubDate'))
            )

            self._import_common(lang_code, item, event['common'])

            organizer = text(item, 'organizer')
            organizer_phone = text(item, 'organizerphone')

            if organizer is not None:
                event['common']['organizer']['name'][lang_code] = clean_text(organizer)
            if organizer_phone is not None:
                event['common']['organizer']['phone'][lang_code] = [
                    clean_text(t) for t in organizer_phone.split(",")]

            start_date = dateutil.parser.parse(
                text(item, 'starttime'))
            start_time = start_date.time()

            # The feed doesn't contain proper end times (clock).
            end_date = dateutil.parser.parse(
                text(item, 'endtime'))

            standardize_event_types(event['common']['types'])

            put(event['instance'], 'start_date', start_date)
            put(event['instance'], 'door_time', start_time)
            put(event['instance'], 'end_date', end_date)
            put(event['instance'], 'event_status', matko_status(int(
                text(item, 'status'))))
            put(event['instance'], 'matko_location_id', int(
                text(item, 'placeuniqueid')))

        return events

    def _import_locations_from_feed(self, lang_code, items, locations):
        for item in items:
            if text(item, 'isvenue') == 'False':
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
                put(location, 'geo', {
                    'longitude': lon,
                    'latitude': lat,
                    'geo_type': 1})

        return locations

    def _import_organizers_from_events(self, events):
        organizers = recur_dict()
        for k, event in events.items():
            if 'organizer' in event:
                organizer = event['common']['organizer']
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
        for lang, url in MATKO_URLS['events'].iteritems():
            items = self.items_from_url(url)
            self._import_events_from_feed(lang, items, events)
            organizers = self._import_organizers_from_events(events)
        errors = set()
        for event in self.link_recurring_events(events.values()):
            errors.update(self.save_children_through_parent(event))
        if len(errors) > 0:
            print('Errors:')
        for e in errors:
            print("%s: %s" % (e[0], u" ".join(e[1])))

    def import_locations(self):
        print("Importing Matko locations")
        locations = recur_dict()
        for lang, url in MATKO_URLS['locations'].iteritems():
            items = self.items_from_url(url)
            self._import_locations_from_feed(lang, items, locations)
        for location in locations.values():
            self.save_location(location)
