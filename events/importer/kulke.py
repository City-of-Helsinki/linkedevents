# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import re
import functools
from lxml import etree
import logging
import dateutil
from datetime import time
from pytz import timezone
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django_orghierarchy.models import Organization

from .base import Importer, register_importer, recur_dict
from .yso import KEYWORDS_TO_ADD_TO_AUDIENCE
from .util import unicodetext, clean_url
from events.models import DataSource, Event, EventAggregate, EventAggregateMember, Keyword, Place, License
from events.keywords import KeywordMatcher
from events.translation_utils import expand_model_fields

# Per module logger
logger = logging.getLogger(__name__)

LOCATION_TPREK_MAP = {
    'malmitalo': '8740',
    'malms kulturhus': '8740',
    'malms bibliotek - malms kulturhus': '8192',
    'malmin kirjasto': '8192',
    'helsingin kaupungintalo': '28473',
    'stoa': '7259',
    'östra centrums bibliotek': '8184',
    'parvigalleria': '7259',
    'musiikkisali': '7259',
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
    'riistavuoren palvelukeskus': '47695',
    'kannelmäen palvelukeskus': '51869',
    'leikkipuisto lampi': '57117',
}

ADDRESS_TPREK_MAP = {
    'annankatu 30': 'annantalo',
    'annegatan 30': 'annantalo',
    'mosaiikkitori 2': 'vuotalo',
    'ala-malmin tori 1': 'malmitalo',
    'ala-malmin tori': 'malmitalo',
    'klaneettitie 5': 'kanneltalo',
    'klarinettvägen 5': 'kanneltalo',
    'turunlinnantie 1': 'stoa'
}

CATEGORIES_TO_IGNORE = [
    286, 596, 614, 307, 632, 645, 675, 231, 364, 325, 324, 319, 646, 640,
    641, 642, 643, 670, 671, 673, 674, 725, 312, 344, 365, 239, 240, 308, 623,
    229, 230, 323, 320, 357, 358, 728, 729, 730, 735, 736,

    # The categories below are languages, ignore as categories
    # todo: add as event languages
    53, 54, 55
]

# Events having one of these categories are courses - they are excluded when importing events
# and only they are included when importing courses.
COURSE_CATEGORIES = {
    70, 71, 72, 73, 75, 77, 79, 80,
    81, 83, 84, 85, 87, 316, 629, 632,
    728, 729, 730, 735,
}


def _query_courses():
    filter_out_keywords = map(
        make_kulke_id,
        COURSE_CATEGORIES
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
MOVIES = ['p1235']
CHILDREN = ['p4354']
YOUTH = ['p11617']
ELDERLY = ['p2433']
FAMILIES = ['p13050']

MANUAL_CATEGORIES = {
    # urheilu
    546: SPORTS, 547: SPORTS, 431: SPORTS, 638: SPORTS,
    # kuntosalit
    607: GYMS, 615: GYMS,
    # harrastukset
    626: ['p2901'],
    # erityisliikunta
    634: ['p3093', 'p916'],
    # monitaiteisuus
    223: ['p25216', 'p360'],
    # seniorit > ikääntyneet ja vanhukset
    354: ELDERLY,
    # saunominen
    371: ['p11049'],
    # lastentapahtumat > lapset (!)
    105: CHILDREN,
    # steppi
    554: ['p19614'],
    # liikuntaleiri
    710: ['p143', 'p916'],
    # teatteri ja sirkus
    351: ['p2625'],
    # elokuva ja media
    205: MOVIES,
    # skidikino
    731: CHILDREN + MOVIES,
    # luennot ja keskustelut
    733: ['p15875', 'p14004'],
    # nuorille
    734: YOUTH,
    # elokuva
    737: MOVIES,
    # perheliikunta
    628: SPORTS + FAMILIES,
    # lapset
    355: CHILDREN,
    # lapsi ja aikuinen yhdessä > perheet
    747: FAMILIES
}

# these are added to all courses
COURSE_KEYWORDS = ('p9270',)

# retain the above for simplicity, even if kulke importer internally requires full keyword ids
KEYWORDS_TO_ADD_TO_AUDIENCE = ['yso:{}'.format(i) for i in KEYWORDS_TO_ADD_TO_AUDIENCE]

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


def parse_age_range(secondary_headline):
    if not isinstance(secondary_headline, str):
        return (None, None)

    pattern = r'^\D*(\d{1,2}).(\d{1,2}).(v|år).*$'
    match = re.match(pattern, secondary_headline)

    if match:
        beginning_age = int(match.groups()[0])
        end_age = int(match.groups()[1])
        return (beginning_age, end_age)
    else:
        return (None, None)


def parse_course_time(secondary_headline):
    if not isinstance(secondary_headline, str):
        return (None, None)

    pattern = r'^.*klo?\s(\d{1,2})([.:](\d{1,2}))?[^.:](\d{1,2})([.:](\d{1,2}))?.*$'
    match = re.match(pattern, secondary_headline)

    if match:
        course_time_beginning_hour = int(match.groups()[0])
        course_time_beginning_minute = int(match.groups()[2]) if match.groups()[2] else 0
        course_time_end_hour = int(match.groups()[3])
        course_time_end_minute = int(match.groups()[5]) if match.groups()[5] else 0
        course_time_beginning = time(hour=course_time_beginning_hour, minute=course_time_beginning_minute)
        course_time_end = time(hour=course_time_end_hour, minute=course_time_end_minute)
        return (course_time_beginning, course_time_end)
    else:
        return (None, None)


@register_importer
class KulkeImporter(Importer):
    name = "kulke"
    supported_languages = ['fi', 'sv', 'en']
    languages_to_detect = []

    def setup(self):
        self.languages_to_detect = [lang[0].replace('-', '_') for lang in settings.LANGUAGES
                                    if lang[0] not in self.supported_languages]
        ds_args = dict(id=self.name)
        defaults = dict(name='Kulttuurikeskus')
        self.tprek_data_source = DataSource.objects.get(id='tprek')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        ds_args = dict(id='ahjo')
        defaults = dict(name='Ahjo')
        ahjo_ds, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(origin_id='u4804001050', data_source=ahjo_ds)
        defaults = dict(name='Yleiset kulttuuripalvelut')
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        # Build a cached list of Places to avoid frequent hits to the db
        id_list = LOCATION_TPREK_MAP.values()
        place_list = Place.objects.filter(data_source=self.tprek_data_source).filter(origin_id__in=id_list)
        self.tprek_by_id = {p.origin_id: p.id for p in place_list}

        logger.info('Preprocessing categories')
        categories = self.parse_kulke_categories()

        keyword_matcher = KeywordMatcher()
        for cid, c in list(categories.items()):
            if c is None:
                continue
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

        course_keyword_ids = ['yso:{}'.format(kw) for kw in COURSE_KEYWORDS]
        self.course_keywords = set(Keyword.objects.filter(id__in=course_keyword_ids))

        try:
            self.event_only_license = License.objects.get(id='event_only')
        except License.DoesNotExist:
            self.event_only_license = None

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
            logger.warning("Missing place for event %s (%s)" % (
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
            logger.warning("No match found for place '%s' (event %s)" % (loc_name, get_event_name(event)))

    @staticmethod
    def _html_format(text):
        """Format text into html

        The method simply wrap <p> tags around texts that are
        separated by empty line, and append <br> to lines if
        there are multiple line breaks within the same paragraph.
        """

        # do not preserve os separators, for conformity with helmet and other html data
        paragraph_sep = os.linesep * 2
        paragraphs = text.split(paragraph_sep)
        formatted_paragraphs = []
        for paragraph in paragraphs:
            lines = paragraph.strip().split(os.linesep)
            formatted_paragraph = '<p>{0}</p>'.format('<br>'.join(lines))
            formatted_paragraphs.append(formatted_paragraph)
        return ''.join(formatted_paragraphs)

    def _import_event(self, lang, event_el, events, is_course=False):
        def text(t):
            return unicodetext(event_el.find('event' + t))

        def clean(t):
            if t is None:
                return None
            t = t.strip()
            if not t:
                return None
            return t

        def text_content(k):
            return clean(text(k))

        eid = int(event_el.attrib['id'])

        if text_content('servicecode') != 'Pelkkä ilmoitus' and not is_course:
            # Skip courses when importing events
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
        name = make_event_name(title, subtitle)

        age_range = parse_age_range(subtitle)

        event['audience_min_age'] = age_range[0]
        event['audience_max_age'] = age_range[1]

        # kulke strings may be in other supported languages
        if name:
            Importer._set_multiscript_field(name, event, [lang] + self.languages_to_detect, 'name')

        caption = text_content('caption')
        # body text should not be cleaned, as we want to html format the whole shebang
        bodytext = event_el.find('eventbodytext')
        if bodytext is not None:
            bodytext = bodytext.text
        description = ''
        if caption:
            description += caption
            # kulke strings may be in other supported languages
            Importer._set_multiscript_field(caption, event, [lang]+self.languages_to_detect, 'short_description')
        else:
            event['short_description'][lang] = None
        if caption and bodytext:
            description += "\n\n"
        if bodytext:
            description += bodytext
        if description:
            description = self._html_format(description)
            # kulke strings may be in other supported languages
            Importer._set_multiscript_field(description, event, [lang]+self.languages_to_detect, 'description')
        else:
            event['description'][lang] = None

        event['info_url'][lang] = text_content('www')
        # todo: process extra links?
        links = event_el.find('eventlinks')
        if links is not None:
            links = links.findall('eventlink')
            assert len(links)
        else:
            links = []
        external_links = []
        for link_el in links:
            if link_el is None or link_el.text is None:
                continue
            link = clean_url(link_el.text)
            if link:
                external_links.append({'link': link})
        event['external_links'][lang] = external_links

        eventattachments = event_el.find('eventattachments')
        if eventattachments is not None:
            for attachment in eventattachments:
                if attachment.attrib['type'] == 'teaserimage':
                    # with the event_only license, the larger picture may be served
                    image_url = unicodetext(attachment).strip().replace('/MediumEventPic', '/EventPic')
                    if image_url:
                        if self.event_only_license:
                            event['images'] = [{
                                'url': image_url,
                                'license': self.event_only_license,
                            }]
                        else:
                            print('Cannot create an image, "event_only" License missing.')
                    break

        provider = text_content('organizer')
        if provider:
            Importer._set_multiscript_field(provider, event, [lang]+self.languages_to_detect, 'provider')

        course_time = parse_course_time(subtitle)

        start_time = dateutil.parser.parse(text('starttime'))
        # Start and end times are in GMT. Sometimes only dates are provided.
        # If it's just a date, tzinfo is None.
        # FIXME: Mark that time is missing somehow?
        if not start_time.tzinfo:
            assert start_time.hour == 0 and start_time.minute == 0 and start_time.second == 0
            if course_time[0]:
                start_time = start_time.replace(hour=course_time[0].hour, minute=course_time[0].minute)
                start_time = start_time.astimezone(LOCAL_TZ)
                event['has_start_time'] = True
            else:
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
                if course_time[1]:
                    end_time = end_time.replace(hour=course_time[1].hour, minute=course_time[1].minute)
                    end_time = end_time.astimezone(LOCAL_TZ)
                    event['has_end_time'] = True

                else:
                    end_time = LOCAL_TZ.localize(end_time)
                    event['has_end_time'] = False
            else:
                end_time = end_time.astimezone(LOCAL_TZ)
                event['has_end_time'] = True

            # sometimes, the data has errors. then we set end time to start time
            if end_time > start_time:
                event['end_time'] = end_time
            else:
                event['end_time'] = event['start_time']

        if is_course:
            event['extension_course'] = {
                'enrolment_start_time': dateutil.parser.parse(
                    text('enrolmentstarttime')
                ),
                'enrolment_end_time': dateutil.parser.parse(
                    text('enrolmentendtime')
                )
            }

        if 'offers' not in event:
            event['offers'] = [recur_dict()]

        offer = event['offers'][0]
        price = text_content('price')
        price_el = event_el.find('eventprice')
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
        link = price_el.get('ticketlink')
        if link:
            offer['info_url'][lang] = clean_url(link)

        if hasattr(self, 'categories'):
            event_keywords = set()
            event_audience = set()
            for category_id in event_el.find('eventcategories'):
                category = self.categories.get(int(category_id.text))
                if category:
                    # YSO keywords
                    if category.get('yso_keywords'):
                        for c in category.get('yso_keywords', []):
                            event_keywords.add(c)
                            if c.id in KEYWORDS_TO_ADD_TO_AUDIENCE:
                                # retain the keyword in keywords as well, for backwards compatibility
                                event_audience.add(c)
                # Also save original kulke categories as keywords
                kulke_id = make_kulke_id(category_id.text)
                try:
                    kulke_keyword = Keyword.objects.get(pk=kulke_id)
                    event_keywords.add(kulke_keyword)
                except Keyword.DoesNotExist:
                    logger.error('Could not find {}'.format(kulke_id))

            if is_course:
                event_keywords.update(self.course_keywords)
                event_audience.update(self.course_keywords & set(KEYWORDS_TO_ADD_TO_AUDIENCE))

            event['keywords'] = event_keywords
            event['audience'] = event_audience

        location = event['location']

        location['street_address'][lang] = text_content('address')
        location['postal_code'] = text_content('postalcode')
        municipality = text_content('postaloffice')
        if municipality == 'Helsingin kaupunki':
            municipality = 'Helsinki'
        location['address_locality'][lang] = municipality
        location['telephone'][lang] = text_content('phone')
        location['name'] = text_content('location')

        if 'place' not in location:
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
                    logger.warning('Differing groups:', key, inner_key)
                    logger.warning('Differing groups:', group, inner_group)
                    if len(inner_group) == 0:
                        logger.warning(
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
                'images', 'offers', 'external_links'])

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
            while words and all(
                    headline.startswith(name + words[0])
                    for headline in [event.name for event in events]
                    ):
                name += words.pop(0) + ' '
                logger.warning(words)
                logger.warning(name)
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

        common_audience = functools.reduce(
            lambda x, y: x & y,
            (set(event.audience.all()) for event in events.all())
        )
        super_event.audience.clear()
        for k in common_audience:
            super_event.audience.add(k)

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
                logger.error('Error: the superevent has an ambiguous aggregate group.')
                logger.error('Aggregate ids: {}, group: {}'.format(
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
                    super_event_type=Event.SuperEventType.RECURRING,
                    data_source=DataSource.objects.get(pk='kulke'),  # TODO
                    id="linkedevents:agg-{}".format(aggregate.id))
                super_event.save()
                aggregate.super_event = super_event
                aggregate.save()
                for event in events:
                    EventAggregateMember.objects.create(event=event,
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
                            EventAggregateMember.objects.create(event=event,
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
        logger.info("Importing Kulke events")
        self._import_events()

    def import_courses(self):
        logger.info("Importing Kulke courses")
        self._import_events(importing_courses=True)

    def _import_events(self, importing_courses=False):
        events = recur_dict()
        recurring_groups = dict()
        for lang in ['fi', 'sv', 'en']:
            events_file = os.path.join(
                settings.IMPORT_FILE_PATH, 'kulke', 'events-%s.xml' % lang)
            root = etree.parse(events_file)
            for event_el in root.xpath('/eventdata/event'):
                success = self._import_event(lang, event_el, events, importing_courses)
                if success:
                    self._gather_recurring_events(lang, event_el, events, recurring_groups)

        events.default_factory = None

        course_keywords = set(map(
            make_kulke_id,
            COURSE_CATEGORIES,
        ))

        for event in events.values():
            if any(kw.id in course_keywords for kw in event['keywords']) == importing_courses:
                self.save_event(event)

        self._verify_recurs(recurring_groups)
        aggregates = self._save_recurring_superevents(recurring_groups)
        for agg in aggregates:
            self._update_super_event(agg.super_event)

    def import_keywords(self):
        logger.info("Importing Kulke categories as keywords")
        categories = self.parse_kulke_categories()
        for kid, value in categories.items():
            try:
                # if the keyword exists, update the name if needed
                word = Keyword.objects.get(id=make_kulke_id(kid))
                if word.name != value['text']:
                    word.name = value['text']
                    word.save()
                if word.publisher_id != self.organization.id:
                    word.publisher = self.organization
                    word.save()
            except ObjectDoesNotExist:
                # if the keyword does not exist, save it for future use
                Keyword.objects.create(
                    id=make_kulke_id(kid),
                    name=value['text'],
                    data_source=self.data_source,
                    publisher=self.organization
                )
