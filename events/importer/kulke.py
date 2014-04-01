import os
from lxml import etree
import dateutil
from django.conf import settings
from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
from .util import unicodetext

@register_importer
class KulkeImporter(Importer):
    name = "kulke"

    def import_events(self):
        print("Importing Kulke events")
        events = recur_dict()
        tag = lambda t: 'event' + t

        for lang in ['fi']:
            events_file = os.path.join(
                settings.IMPORT_FILE_PATH, 'event.xml')
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

                # todo: process ? 
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
                postal_address = event['instance']['location']['address']

                postal_address['street_address'][lang] = clean(text('address'))
                postal_address['postal_code'] = clean(text('postalcode'))
                municipality = clean(text('postaloffice'))
                if municipality == 'Helsingin kaupunki':
                    municipality = 'Helsinki'
                postal_address['address_locality'][lang] = municipality
                postal_address['telephone'][lang] = clean(text('phone'))

                event['children'] = []
                references = event_el.find(tag('references'))
                if references is not None:
                    for reference in references:
                        event['children'].append(reference.get('id'))


        import pprint
        for eid, event in events.items():
            pprint.pprint(event)

    def import_locations(self):
        print("Importing Kulke locations")
        pass
