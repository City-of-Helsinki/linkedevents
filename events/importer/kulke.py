import os
from datetime import timezone
from lxml import etree
from modeltranslation.translator import translator
import dateutil
from django.conf import settings
from django.utils.timezone import get_default_timezone
from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
from .util import unicodetext, active_language
from events.models import DataSource, Place, Event

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
        tprek_id = None
        location = event['location']
        if location['name'] is None:
            print("Missing place for event '%s'" % event['id'])
            return None

        loc_name = location['name'].lower()
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
            if location['street_address']['fi']:
                addr = location['street_address']['fi'].lower()
                if addr in ADDRESS_TPREK_MAP:
                    tprek_id = LOCATION_TPREK_MAP[ADDRESS_TPREK_MAP[addr]]

        if tprek_id:
            return Place.objects.get(data_source=self.tprek_data_source,
                                     origin_id=tprek_id)
        else:
            print("No match found for place '%s' (event %s)" % (loc_name, event['name']['fi']))
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
                text_content = lambda k: clean(text(k))

                eid = int(event_el.attrib['id'])
                event = events[eid]
                event['id'] = eid

                event['name'][lang] = text_content('title')
                subtitle = text_content('subtitle')
                if subtitle:
                    event['custom']['subtitle'][lang] = subtitle

                caption = text_content('caption')
                bodytext = text_content('bodytext')
                description = ''
                if caption:
                    description += caption
                if caption and bodytext:
                    description += "\n\n"
                if bodytext:
                    description += bodytext
                event['description'][lang] = description

                event['url'][lang] = text_content('www')
                # todo: process extra links?
                # event_links = event_el.find(tag('links'))

                eventattachments = event_el.find(tag('attachments'))
                if eventattachments is not None:
                    for attachment in eventattachments:
                        if attachment.get('teaserimage'):
                            event['image'] = unicodetext(attachment).strip()
                            break

                start_date = dateutil.parser.parse(
                    text('starttime')
                )
                # todo: verify the input data time zones are correct.
                event['start_date'] = start_date
                event['door_time'] = start_date.time()
                if text('endtime'):
                    event['end_date'] = dateutil.parser.parse(
                        text('endtime')
                    )

                # todo: verify enrolment use cases, proper fields
                event['custom']['enrolment']['start'] = dateutil.parser.parse(
                    text('enrolmentstarttime')
                )
                event['custom']['enrolment']['end'] = dateutil.parser.parse(
                    text('enrolmentendtime')
                )

                price = text_content('price')
                price_el = event_el.find(tag('price'))
                free = (price_el.attrib['free'] == "true")
                url = price_el.get('ticketlink')
                info = price_el.get('ticketinfo')

                offers = event['offers']
                if free:
                    offers['price'] = '0'
                    if price and len(price) > 0:
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

                location = event['location']

                location['street_address'][lang] = text_content('address')
                location['postal_code'] = text_content('postalcode')
                municipality = text_content('postaloffice')
                if municipality == 'Helsingin kaupunki':
                    municipality = 'Helsinki'
                location['address_locality'][lang] = municipality
                location['telephone'][lang] = text_content('phone')
                location['name'] = text_content('location')

                if not 'place' in location:
                    event['location']['place'] = self.find_place(event)

                references = event_el.find(tag('references'))
                event['children'] = []
                if references is not None:
                    for reference in references:
                        event['children'].append(int(reference.get('id')))

        events.default_factory = None
        for eid, event in events.items():
            self.save_event_as_model(event)

    def save_event_as_model(self, event_dict):
        event_dict['location'] = event_dict['location']['place']
        del event_dict['offers']    # todo
        del event_dict['children']  # todo
        del event_dict['custom']    # todo
        trans_fields = {
            key: None for key
            in translator.get_options_for_model(Event).fields
        }
        try:
            event = Event.objects.get(
                data_source=self.data_source,
                origin_id=event_dict['id']
            )
        except Event.DoesNotExist:
            event = Event(
                data_source=self.data_source,
                origin_id=event_dict['id']
            )

        for key in trans_fields.keys():
            value = event_dict.pop(key, None)
            if value is not None:
                trans_fields[key] = value
        for key, value in event_dict.items():
            setattr(event, key, value)
        for l in trans_fields['name'].keys():
            # Don't overwrite existing values
            # with Nones.
            with active_language(l):
                for key, value in trans_fields.items():
                    if value and l in value:
                        setattr(event, key, value[l])

        event.save()

    def _gather_recurrings_groups(self, events):
        # Currently unused.
        # Gathers all recurring events in the same
        # group (some reference ids are missing from some of the events.)
        checked_for_children = set()
        recurring_groups = set()
        for eid, event in events.items():
            if eid not in checked_for_children:
                recurring_set = self._find_children(
                    events, eid, {eid}, checked_for_children
                )
                recurring_groups.add(tuple(sorted(recurring_set)))

        for eid in events.keys():
            matching_groups = [s for s in recurring_groups if int(eid) in s]
            assert len(matching_groups) == 1
            if len(matching_groups[0]) == 1:
                assert len(events[eid]['children']) == 0
        return recurring_groups

    def _verify_recurring_groups(self, recurring_groups):
        # Currently unused.
        for group in recurring_groups:
            identical_keys = set()
            eids_found = [eid for eid in group if eid in events]
            if len(eids_found) == 1:
                continue
            for eid in eids_found:
                identical_keys |= events[eid].keys()
            event_a = events[eids_found[0]]
            for eid in eids_found[1:]:
                event_b = events[eid]
                for key in list(identical_keys):
                    if event_a[key] != event_b[key]:
                        identical_keys.remove(key)
            if len(identical_keys) == 0:
                pass
            else:
                pass

    def _find_children(self, events, event_id, children_set, checked_events):
        if event_id in checked_events:
            return children_set
        checked_events.add(event_id)
        if event_id in events:
            children_set |= set(events[event_id]['children'])
        for child in list(children_set):
            children_set |= self.find_children(
                events, child, children_set, checked_events
            )
        return children_set

    def import_locations(self):
        print("Importing Kulke locations")
        pass
