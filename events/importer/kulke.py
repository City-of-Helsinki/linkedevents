# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import re
import functools
from lxml import etree
from modeltranslation.translator import translator
import dateutil
from pytz import timezone
from django.conf import settings
from django.utils.timezone import get_default_timezone
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import IntegrityError

from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
from .util import unicodetext, active_language
from events.models import DataSource, Place, Event, Keyword, KeywordLabel, Organization, EventAggregate, EventAggregateMember
from events.keywords import KeywordMatcher
from events.translation_utils import expand_model_fields

LOCATION_TPREK_MAP = {
    'malmitalo': '8740',
    'malms kulturhus': '8740',
    'malms bibliotek - malms kulturhus': '8192',
    'helsingin kaupungintalo': '28473',
    'stoa': '7259',
    'kanneltalo': '7255',
    'vuotalo': '7260',
    'vuosali': '7260',
    'savoy-teatteri': '7258',
    'savoy': '7258',
    'annantalo': '7254',
    'annegården': '7254',
    'espan lava': '7265',
    'caisa': '7256',
    'nuorisokahvila clubi': '8006',
    'haagan nuorisotalo': '8023',
    'vuosaaren kirjasto': '8310',
}

ADDRESS_TPREK_MAP = {
    'annankatu 30': 'annantalo',
    'annegatan 30': 'annantalo',
    'mosaiikkitori 2': 'vuotalo',
    'ala-malmin tori 1': 'malmitalo',
    'ala-malmin tori': 'malmitalo',
    'klaneettitie 5': 'kanneltalo',
    'klarinettvägen 5': 'kanneltalo',
}

CATEGORIES_TO_IGNORE = [
    286, 596, 614, 307, 632, 645, 675, 231, 364, 325, 324, 319, 646, 640,
    641, 642, 643, 670, 671, 673, 674, 725, 312, 344, 365, 239, 240, 308, 623,
    229, 230, 323, 320, 357, 358, 728, 729, 730, 735, 736,

    # The categories below are languages, ignore as categories
    # todo: add as event languages
    53, 54, 55
]

# These events are courses - not to be published
SKIP_EVENTS_WITH_CATEGORY = {
    70, 71, 72, 73, 75, 77, 79, 80,
    81, 83, 84, 85, 87, 316, 629, 632,
    728, 729, 730, 735,
}

def _query_courses():
    filter_out_keywords = map(
        make_kulke_id,
        SKIP_EVENTS_WITH_CATEGORY
    )
    return Event.objects.filter(
        data_source='kulke'
    ).filter(
        keywords__id__in=set(filter_out_keywords)
    )

def _delete_courses():
    courses_q = _query_courses()
    courses_q.delete()


SPORTS = ['p965']
GYMS = ['p8504']
CHILDREN = ['p4354']
MOVIES = ['p1235', 'p16327']
MANUAL_CATEGORIES = {
    # urheilu
    546: SPORTS, 547: SPORTS, 431: SPORTS, 638: SPORTS,
    # kuntosalit
    607: GYMS, 615: GYMS,
    # harrastukset
    626: ['p2901'],
    # erityisliikunta
    634: ['p3093'],
    # monitaiteisuus
    223: ['p25216'],
    # seniorit > ikääntyneet
    354: ['p2433'],
    # saunominen
    371: ['p11049'],
    # lastentapahtumat > lapset (!)
    105: CHILDREN,
    # steppi
    554: ['p19614'],
    # liikuntaleiri
    710: ['p143', 'p916'],
    # teatteri ja sirkus
    351: ['p2850'],
    # elokuva ja media
    205: MOVIES + ['p2445'],
    # skidikino
    731: CHILDREN + MOVIES,
    # luennot ja keskustelut
    733: ['p15875', 'p14004'],
    # nuorille
    734: ['p11617'],
    # elokuva
    737: MOVIES
}


LOCAL_TZ = timezone('Europe/Helsinki')

def make_kulke_id(num):
    return "kulke:{}".format(num)

def make_event_name(title, subtitle):
    if title and subtitle:
        return "{} – {}".format(title, subtitle)
    elif title:
        return title
    elif subtitle:
        return subtitle

def get_event_name(event):
    if 'fi' in event['name']:
        return event['name']['fi']
    else:
        names = list(event['name'].values())
        if len(names):
            return None
        else:
            return names[0]

@register_importer
class KulkeImporter(Importer):
    name = "kulke"
    supported_languages = ['fi', 'sv', 'en']

    def setup(self):
        ds_args = dict(id=self.name)
        defaults = dict(name='Kulttuurikeskus')
        self.tprek_data_source = DataSource.objects.get(id='tprek')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        ds_args = dict(id='ahjo')
        defaults = dict(name='Ahjo')
        ahjo_ds, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(id='ahjo:46101')
        defaults = dict(name='Kulttuurikeskus', data_source=ahjo_ds)
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        # Build a cached list of Places to avoid frequent hits to the db
        id_list = LOCATION_TPREK_MAP.values()
        place_list = Place.objects.filter(data_source=self.tprek_data_source).filter(origin_id__in=id_list)
        self.tprek_by_id = {p.origin_id: p.id for p in place_list}

        print('Preprocessing categories')
        categories = self.parse_kulke_categories()

        keyword_matcher = KeywordMatcher()
        for cid, c in list(categories.items()):
            if c is None:
                continue
            match_type = 'no match'
            ctext = c['text']
            # Ignore list (not used and/or not a category for general consumption)
            #
            # These are ignored for now, could be used for
            # target group extraction or for other info
            # were they actually used in the data:
            if cid in CATEGORIES_TO_IGNORE\
               or c['type'] == 2 or c['type'] == 3:
                continue

            manual = MANUAL_CATEGORIES.get(cid)
            if manual:
                try:
                    yso_ids = ['yso:{}'.format(i) for i in manual]
                    yso_keywords = Keyword.objects.filter(id__in=yso_ids)
                    c['yso_keywords'] = yso_keywords
                except Keyword.DoesNotExist:
                    pass
            else:
                replacements = [('jumppa', 'voimistelu'), ('Stoan', 'Stoa')]
                for src, dest in replacements:
                    ctext = re.sub(src, dest, ctext, flags=re.IGNORECASE)
                    c['yso_keywords'] = keyword_matcher.match(ctext)

        self.categories = categories

    def parse_kulke_categories(self):
        categories = {}
        categories_file = os.path.join(
            settings.IMPORT_FILE_PATH, 'kulke', 'category.xml')
        root = etree.parse(categories_file)
        for ctype in root.xpath('/data/categories/category'):
            cid = int(ctype.attrib['id'])
            typeid = int(ctype.attrib['typeid'])
            categories[cid] = {
                'type': typeid, 'text': ctype.text}
        return categories


    def find_place(self, event):
        tprek_id = None
        location = event['location']
        if location['name'] is None:
            print("Missing place for event %s (%s)" % (
                get_event_name(event), event['origin_id']))
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
            if 'fi' in location['street_address'] and location['street_address']['fi']:
                addr = location['street_address']['fi'].lower()
                if addr in ADDRESS_TPREK_MAP:
                    tprek_id = LOCATION_TPREK_MAP[ADDRESS_TPREK_MAP[addr]]

        if not tprek_id and 'sv' in location['street_address']:
            # Okay, try Swedish address.
            if 'sv' in location['street_address'] and location['street_address']['sv']:
                addr = location['street_address']['sv'].lower()
                if addr in ADDRESS_TPREK_MAP:
                    tprek_id = LOCATION_TPREK_MAP[ADDRESS_TPREK_MAP[addr]]

        if tprek_id:
            event['location']['id'] = self.tprek_by_id[tprek_id]
        else:
            print("No match found for place '%s' (event %s)" % (loc_name, get_event_name(event)))

    def _import_event(self, lang, event_el, events):
        tag = lambda t: 'event' + t
        text = lambda t: unicodetext(event_el.find(tag(t)))
        def clean(t):
            if t is None:
                return None
            t = t.strip()
            if not t:
                return None
            return t
        text_content = lambda k: clean(text(k))

        eid = int(event_el.attrib['id'])

        if text_content('servicecode') != 'Pelkkä ilmoitus':
            # Skip courses
            return False

        if self.options['single']:
            if str(eid) != self.options['single']:
                return False

        event = events[eid]
        event['data_source'] = self.data_source
        event['publisher'] = self.organization
        event['origin_id'] = eid

        title = text_content('title')
        subtitle = text_content('subtitle')
        event['headline'][lang] = title
        event['secondary_headline'][lang] = subtitle
        event['name'][lang] = make_event_name(title, subtitle)

        caption = text_content('caption')
        bodytext = text_content('bodytext')
        description = ''
        if caption:
            description += caption
            event['short_description'][lang] = caption
        else:
            event['short_description'][lang] = None
        if caption and bodytext:
            description += "\n\n"
        if bodytext:
            description += bodytext
        if description:
            event['description'][lang] = description
        else:
            event['description'][lang] = None

        event['info_url'][lang] = text_content('www')
        # todo: process extra links?
        links = event_el.find(tag('links'))
        if links is not None:
            links = links.findall(tag('link'))
            assert len(links)
        else:
            links = []
        external_links = []
        for link_el in links:
            link = unicodetext(link_el)
            if not re.match(r'^\w+?://', link):
                link = 'http://' + link
            try:
                self.url_validator(link)
            except ValidationError:
                continue
            except ValueError:
                print('value error with event %s and url %s ' % (eid, link))
            external_links.append({'link': link})
        event['external_links'][lang] = external_links

        eventattachments = event_el.find(tag('attachments'))
        if eventattachments is not None:
            for attachment in eventattachments:
                if attachment.attrib['type'] == 'teaserimage':
                    # with the event_only license, the larger picture may be served
                    event['image'] = unicodetext(attachment).strip().replace(
                        '/MediumEventPic', '/EventPic'
                    )
                    event['image_license'] = 'event_only'
                    break

        event['provider'][lang] = text_content('organizer')

        start_time = dateutil.parser.parse(text('starttime'))
        # Start and end times are in GMT. Sometimes only dates are provided.
        # If it's just a date, tzinfo is None.
        # FIXME: Mark that time is missing somehow?
        if not start_time.tzinfo:
            assert start_time.hour == 0 and start_time.minute == 0 and start_time.second == 0
            start_time = LOCAL_TZ.localize(start_time)
            event['has_start_time'] = False
        else:
            start_time = start_time.astimezone(LOCAL_TZ)
            event['has_start_time'] = True
        event['start_time'] = start_time
        if text('endtime'):
            end_time = dateutil.parser.parse(text('endtime'))
            if not end_time.tzinfo:
                assert end_time.hour == 0 and end_time.minute == 0 and end_time.second == 0
                end_time = LOCAL_TZ.localize(end_time)
                event['has_end_time'] = False
            else:
                end_time = end_time.astimezone(LOCAL_TZ)
                event['has_end_time'] = True

            event['end_time'] = end_time

        # todo: verify enrolment use cases, proper fields
        event['custom']['enrolment']['start_time'] = dateutil.parser.parse(
            text('enrolmentstarttime')
        )
        event['custom']['enrolment']['end_time'] = dateutil.parser.parse(
            text('enrolmentendtime')
        )

        if 'offers' not in event:
            event['offers'] = [recur_dict()]

        offer = event['offers'][0]
        price = text_content('price')
        price_el = event_el.find(tag('price'))
        free = (price_el.attrib['free'] == "true")

        offer['is_free'] = free
        description = price_el.get('ticketinfo')
        if description and 'href' in description:
            # the field sometimes contains some really bad invalid html
            # snippets
            description = None
        offer['description'][lang] = description
        if not free:
            offer['price'][lang] = price
        offer['info_url'][lang] = price_el.get('ticketlink')

        if hasattr(self, 'categories'):
            event_keywords = set()
            for category_id in event_el.find(tag('categories')):
                category = self.categories.get(int(category_id.text))
                if category:
                    # YSO keywords
                    if category.get('yso_keywords'):
                        for c in category.get('yso_keywords', []):
                            event_keywords.add(c)
                # Also save original kulke categories as keywords
                kulke_id = make_kulke_id(category_id.text)
                try:
                    kulke_keyword = Keyword.objects.get(pk=kulke_id)
                    event_keywords.add(kulke_keyword)
                except Keyword.DoesNotExist:
                    print('Could not find {}'.format(kulke_id))

            event['keywords'] = event_keywords

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
            self.find_place(event)
        return True

    def _gather_recurring_events(self, lang, event_el, events, recurring_groups):
        references = event_el.find('eventreferences')
        this_id = int(event_el.attrib['id'])
        if references is None or len(references) < 1:
            group = set()
        else:
            recurs = references.findall('recurring') or []
            recur_ids = map(lambda x: int(x.attrib['id']), recurs)
            group = set(recur_ids)
        group.add(this_id)
        recurring_groups[this_id] = group

    def _verify_recurs(self, recurring_groups):
        for key, group in recurring_groups.items():
            for inner_key in group:
                inner_group = recurring_groups.get(inner_key)
                if inner_group and inner_group != group:
                    print('Differing groups:', key, inner_key)
                    print('Differing groups:', group, inner_group)
                    if len(inner_group) == 0:
                        print(
                            'Event self-identifies to no group, removing.',
                            inner_key
                        )
                        group.remove(inner_key)

    def _update_super_event(self, super_event):
        events = super_event.get_children()
        first_event = events.order_by('start_time').first()
        super_event.start_time = first_event.start_time
        super_event.has_start_time = first_event.has_start_time
        last_event = events.order_by('-end_time').first()
        super_event.end_time = last_event.end_time
        super_event.has_end_time = last_event.has_end_time

        # Functions which map related models into simple comparable values.
        def simple(field):
            return frozenset(map(lambda x: x.simple_value(), field.all()))
        value_mappers = {
            'offers': simple,
            'external_links': simple
        }
        fieldnames = expand_model_fields(
            super_event, [
                'info_url', 'description', 'short_description', 'headline',
                'secondary_headline', 'provider', 'publisher', 'location',
                'location_extra_info', 'data_source',
                'image', 'offers', 'external_links'])

        # The set of fields which have common values for all events.
        common_fields = set(
            f for f in fieldnames
            if 1 == len(set(map(
                    value_mappers.get(f, lambda x: x),
                    (getattr(event, f) for event in events.all())))))

        for fieldname in common_fields:
            value = getattr(events.first(), fieldname)
            if hasattr(value, 'all'):
                manager = getattr(super_event, fieldname)
                simple = False
                if hasattr(value.first(), 'simple_value'):
                    # Simple related models can be deleted and copied.
                    manager.all().delete()
                    simple = True
                for m in value.all():
                    if simple:
                        m.id = None
                        m.event_id = super_event.id
                        m.save()
                    manager.add(m)
            else:
                setattr(super_event, fieldname, value)

        # The name may vary within a recurring event; hence, take the common part
        if expand_model_fields(super_event, ['headline'])[0] not in common_fields:
            words = getattr(events.first(), 'headline').split(' ')
            name = ''
            is_common = lambda: all(
                headline.startswith(name + words[0])
                for headline in [event.name for event in events]
            )
            while words and is_common():
                name += words.pop(0) + ' '
                print(words)
                print(name)
            setattr(super_event, 'name', name)

        for lang in self.languages.keys():
            headline = getattr(
                super_event, 'headline_{}'.format(lang)
            )
            secondary_headline = getattr(
                super_event, 'secondary_headline_{}'.format(lang)
            )
            setattr(super_event, 'name_{}'.format(lang),
                    make_event_name(headline, secondary_headline)
            )

        # Gather common keywords present in *all* subevents
        common_keywords = functools.reduce(
            lambda x, y: x & y,
            (set(event.keywords.all()) for event in events.all())
        )
        super_event.keywords.clear()
        for k in common_keywords:
            super_event.keywords.add(k)

        super_event.save()

    def _save_recurring_superevents(self, recurring_groups):
        groups = map(frozenset, recurring_groups.values())
        aggregates = set()
        for group in groups:
            kulke_ids = set(map(make_kulke_id, group))
            superevent_aggregates = EventAggregate.objects.filter(
                members__event__id__in=kulke_ids
            ).distinct()
            cnt = superevent_aggregates.count()

            if cnt > 1:
                print('Error: the superevent has an ambiguous aggregate group.')
                print('Aggregate ids: {}, group: {}'.format(
                    superevent_aggregates.values_list('id', flat=True), group))
                continue

            events = Event.objects.filter(id__in=kulke_ids)
            if events.count() < 2:
                continue

            aggregate = None
            if cnt == 0:
                if len(group) == 1:
                    # Do not create aggregates of only one.
                    continue
                aggregate = EventAggregate()
                aggregate.save()
                super_event = Event(
                    publisher=self.organization,
                    is_recurring_super=True,
                    data_source=DataSource.objects.get(pk='kulke'), # TODO
                    id="linkedevents:agg-{}".format(aggregate.id))
                super_event.save()
                aggregate.super_event = super_event
                aggregate.save()
                for event in events:
                    member = EventAggregateMember.objects.create(event=event,
                                                                 event_aggregate=aggregate)
            elif cnt == 1:
                aggregate = superevent_aggregates.first()
                if len(group) == 1:
                    events = Event.objects.get(
                        pk=make_kulke_id(group.pop()))
                    # The imported event is not part of an aggregate
                    # but one was found it in the db. Remove the event
                    # from the aggregate. This is the only case when
                    # an event is removed from a recurring aggregate.
                    aggregate.members.remove(events)
                else:
                    for event in events:
                        try:
                            member = EventAggregateMember.objects.create(event=event,
                                                                         event_aggregate=aggregate)
                        except IntegrityError:
                            # Ignore unique violations. They
                            # ensure that no duplicate members are added.
                            pass
            for event in events:
                event.super_event = aggregate.super_event
                event.save()
            aggregates.add(aggregate)
        return aggregates

    def import_events(self):
        print("Importing Kulke events")
        self.url_validator = URLValidator()
        events = recur_dict()
        recurring_groups = dict()
        for lang in ['fi', 'sv', 'en']:
            events_file = os.path.join(
                settings.IMPORT_FILE_PATH, 'kulke', 'events-%s.xml' % lang)
            root = etree.parse(events_file)
            for event_el in root.xpath('/eventdata/event'):
                success = self._import_event(lang, event_el, events)
                if success:
                    self._gather_recurring_events(lang, event_el, events, recurring_groups)

        events.default_factory = None

        filter_out_keywords = set(map(
            make_kulke_id,
            SKIP_EVENTS_WITH_CATEGORY
        ))
        for eid, event in events.items():
            skip = False
            for kw in event['keywords']:
                if kw.id in filter_out_keywords:
                    skip = True
                    break
            if skip:
                continue
            self.save_event(event)

        self._verify_recurs(recurring_groups)
        aggregates = self._save_recurring_superevents(recurring_groups)
        for agg in aggregates:
            self._update_super_event(agg.super_event)

    def import_keywords(self):
        print("Importing Kulke categories as keywords")
        categories = self.parse_kulke_categories()
        for kid, value in categories.items():
            try:
                # if the keyword exists, update the name if needed
                word = Keyword.objects.get(id=make_kulke_id(kid))
                if word.name != value['text']:
                    word.name = value['text']
                    word.save()
            except ObjectDoesNotExist:
                # if the keyword does not exist, save it for future use
                Keyword.objects.create(
                    id=make_kulke_id(kid),
                    name=value['text'],
                    data_source=self.data_source
                )
