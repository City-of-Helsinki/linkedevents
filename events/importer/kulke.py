import os
from datetime import timezone
from lxml import etree
import dateutil
from django.conf import settings
from django.utils.timezone import get_default_timezone
from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
from .util import unicodetext
from events.models import DataSource, Place

LOCATION_TPREK_MAP = {
    'malmitalo': '8740',
    'malms kulturhus': '8740',
    'stoa': '7259',
    'kanneltalo': '7255',
    'vuotalo': '7591',
    'vuosali': '7591',
    'savoy-teatteri': '7258',
    'savoy': '7258',
    'annantalo': '7254',
    'annegården': '7254',
    'espan lava': '7265',
    'caisa': '7256',
    'nuorisokahvila clubi': '8006',
    'haagan nuorisotalo': '8023',
}

ADDRESS_TPREK_MAP = {
    'annankatu 30': 'annantalo',
    'mosaiikkitori 2': 'vuotalo',
    'ala-malmin tori 1': 'malmitalo',
}


@register_importer
class KulkeImporter(Importer):
    name = "kulke"

    def setup(self):
        ds_args = dict(id=self.name)
        defaults = dict(name='Kulttuurikeskus')
        self.tprek_data_source = DataSource.objects.get(id='tprek')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

    def find_place(self, event):
        location = event['location']
        loc_name = location['name'].lower()
        tprek_id = None
        if loc_name in LOCATION_TPREK_MAP:
            tprek_id = LOCATION_TPREK_MAP[loc_name]

        if not tprek_id:
            # Exact match not found, check for string begin
            for k in LOCATION_TPREK_MAP.keys():
                if loc_name.startswith(k):
                    tprek_id = LOCATION_TPREK_MAP[k]
                    break

        if not tprek_id:
            # Check for venue name inclusion
            if 'caisa' in loc_name:
                tprek_id = LOCATION_TPREK_MAP['caisa']
            elif 'annantalo' in loc_name:
                tprek_id = LOCATION_TPREK_MAP['annantalo']

        if not tprek_id and 'fi' in location['street_address']:
            # Okay, try address.
            addr = location['street_address']['fi'].lower()
            if addr in ADDRESS_TPREK_MAP:
                tprek_id = LOCATION_TPREK_MAP[ADDRESS_TPREK_MAP[addr]]

        if tprek_id:
            return Place.objects.get(data_source=self.tprek_data_source,
                                     origin_id=tprek_id)
        else:
            print("No match found for place '%s' (event %s)" % (loc_name, event['common']['name']['fi']))
            return None

    def import_events(self):
        print("Importing Kulke events")
        events = recur_dict()
        tag = lambda t: 'event' + t

        for lang in ['fi', 'sv', 'en']:
            events_file = os.path.join(
                settings.IMPORT_FILE_PATH, 'kulke', 'events-%s.xml' % lang)
            root = etree.parse(events_file)
            for event_el in root.xpath('/eventdata/event'):
                text = lambda t: unicodetext(event_el.find(tag(t)))
                clean = lambda t: t.strip() if t is not None else None

                eid = event_el.attrib['id']
                event = events[eid]
                event['instance']['id'] = eid
                name = clean(text('title'))
                subtitle = clean(text('subtitle'))
                if len(subtitle) > 0:
                    name += ' - ' + subtitle
                event['common']['name'][lang] = name
                event['common']['description'][lang] = clean(text('caption'))

                # todo: process extra links?
                # event_links = event_el.find(tag('links'))

                event['instance']['url'][lang] = clean(text('www'))
                eventattachments = event_el.find(tag('attachments'))
                if eventattachments is not None:
                    for attachment in eventattachments:
                        if attachment.get('teaserimage'):
                            event['instance']['image'] = unicodetext(attachment).strip()
                            break

                bodytext = clean(text('bodytext'))
                if bodytext and len(bodytext) > 0:
                    event['common']['description'][lang] += bodytext

                start_date = dateutil.parser.parse(
                    text('starttime')
                )
                # todo: verify the input data time zones are correct.
                event['instance']['start_date'] = start_date
                event['instance']['door_time'] = start_date.time()
                event['instance']['end_date'] = dateutil.parser.parse(
                    text('endtime')
                )

                # todo: verify enrolment use cases, proper fields
                event['instance']['custom']['enrolment']['start'] = dateutil.parser.parse(
                    text('enrolmentstarttime')
                )
                event['instance']['custom']['enrolment']['end'] = dateutil.parser.parse(
                    text('enrolmentendtime')
                )

                price = clean(text('price'))
                price_el = event_el.find(tag('price'))
                free = (price_el.attrib['free'] == "true")
                url = price_el.get('ticketlink')
                info = price_el.get('ticketinfo')

                offers = event['instance']['offers']
                if free:
                    offers['price'] = '0'
                    if len(price) > 0:
                        if info is not None:
                            offers['description'] = info + '; ' + price
                        else:
                            offers['description'] = price
                    else:
                        offers['description'] = info
                else:
                    offers['price'] = price
                offers['url'] = url

                # todo categories

                # Note: "postal address" is named after schema.org,
                # and is actually interpreted to be the location's street
                # address.

                location = event['location']

                location['street_address'][lang] = clean(text('address'))
                location['postal_code'] = clean(text('postalcode'))
                municipality = clean(text('postaloffice'))
                if municipality == 'Helsingin kaupunki':
                    municipality = 'Helsinki'
                location['address_locality'][lang] = municipality
                location['telephone'][lang] = clean(text('phone'))
                location['name'] = clean(text('location'))
                if not 'place' in location:
                    self.find_place(event)

                event['children'] = []
                references = event_el.find(tag('references'))
                if references is not None:
                    for reference in references:
                        event['children'].append(reference.get('id'))


        for eid, event in events.items():
            # First save children, then parent
            pass

    def import_locations(self):
        print("Importing Kulke locations")
        pass
