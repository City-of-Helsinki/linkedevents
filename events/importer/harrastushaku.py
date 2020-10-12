import logging
import traceback
from collections import namedtuple
from copy import deepcopy
from datetime import datetime, timedelta
from functools import lru_cache, partial

import pytz
import requests
from django.db import transaction
from django.utils.dateparse import parse_time
from django.utils.timezone import now
from django_orghierarchy.models import Organization

from events.importer.sync import ModelSyncher
from events.importer.util import clean_text
from events.importer.yso import KEYWORDS_TO_ADD_TO_AUDIENCE
from events.keywords import KeywordMatcher
from events.models import DataSource, Event, Keyword, Place

from .base import Importer, register_importer

# Per module logger
logger = logging.getLogger(__name__)

HARRASTUSHAKU_API_BASE_URL = 'http://nk.hel.fi/harrastushaku/api/'

TIMEZONE = pytz.timezone('Europe/Helsinki')

MAX_RECURRING_EVENT_LENGTH = 366  # days

MAIN_CATEGORY_KEYWORDS = {
    '1': {'yso:p3466'},
    '2': {'yso:p916', 'yso:p6062'},
    '3': {'yso:p13084', 'yso:p2023'},
    '4': {'yso:p2445', 'yso:p20405'},
    '5': {'yso:p1808'},
    '7': {'yso:p2851'},
    '8': {'yso:p1278'},
    '9': {'yso:p6940'},
    '11': {'yso:p143', 'yso:p9270'},
}

AUDIENCE_BY_AGE_RANGE = (
    ((0, 6), {'yso:p4354'}),
    ((7, 16), {'yso:p16485'}),
    ((10, 18), {'yso:p11617'}),
)

SubEventTimeRange = namedtuple('SubEventTimeRange', ['start', 'end'])


class HarrastushakuException(Exception):
    pass


@register_importer
class HarrastushakuImporter(Importer):
    name = 'harrastushaku'
    supported_languages = ['fi']

    def setup(self):
        logger.debug('Running Harrastushaku importer setup...')
        self.data_source, _ = DataSource.objects.get_or_create(id=self.name, defaults={'name': 'Harrastushaku'})
        self.tprek_data_source = DataSource.objects.get(id='tprek')
        self.ahjo_data_source, _ = DataSource.objects.get_or_create(id='ahjo', defaults={'name': 'Ahjo'})
        self.organization, _ = Organization.objects.get_or_create(origin_id='u48040030',
                                                                  data_source=self.ahjo_data_source)
        self.tprek_ids = {place.origin_id for place in Place.objects.filter(data_source=self.tprek_data_source)}
        self.keywords = {keyword.id: keyword for keyword in Keyword.objects.all()}
        self.keyword_matcher = KeywordMatcher()

    def import_places(self):
        """Import Harrastushaku locations as Places

        - If we can find a close-enough match for the location object coming from Harrastushaku in Toimipisterekisteri,
          we do not import that location object, as this this will cause duplicate location issue due to
          Harrastushaku data being of low quality.

        - If, however, we cannot find a match, location object will be imported with data source "harrastushaku".
        """
        logger.info('Importing places...')

        locations = self.fetch_locations()
        logger.debug('Handling {} locations...'.format(len(locations)))
        self.location_id_to_place_id = self.map_harrastushaku_location_ids_to_tprek_ids(locations)

        for location in locations:
            try:
                self.handle_location(location)
            except Exception as e:  # noqa
                message = e if isinstance(e, HarrastushakuException) else traceback.format_exc()
                logger.error('Error handling location {}: {}'.format(location.get('id'), message))

    def map_harrastushaku_location_ids_to_tprek_ids(self, harrastushaku_locations):
        '''
        Example mapped dictionary result:
        {
            '95': 'harrastushaku:95',
            '953': 'harrastushaku:953',
            '968': 'tprek:20479',
            '97': 'tprek:8062',
            '972': 'tprek:9079',
            '987': 'harrastushaku:987',
            '99': 'tprek:8064',
        }
        '''
        result = dict()

        for harrastushaku_location in harrastushaku_locations:
            harrastushaku_location_id = harrastushaku_location['id']

            strict_filters = {
                'id__startswith': self.tprek_data_source,
                'name': harrastushaku_location['name'],
                'address_locality': harrastushaku_location['city'],
                'postal_code': harrastushaku_location['zip'],
                'street_address': harrastushaku_location['address'],
            }
            flexible_filters = {
                'id__startswith': self.tprek_data_source,
                'address_locality': harrastushaku_location['city'],
                'postal_code': harrastushaku_location['zip'],
                'street_address': harrastushaku_location['address'],
            }

            tprek_place = (Place.objects.filter(**strict_filters).first() or
                           Place.objects.filter(**flexible_filters).first())

            if tprek_place:
                result[harrastushaku_location_id] = tprek_place.id
            else:
                result[harrastushaku_location_id] = '{}:{}'.format(self.data_source.id, harrastushaku_location_id)

        return result

    def import_courses(self):
        """Import Harrastushaku activities as Courses

        Activities having "active" anything else than "1" or "K" will be
        ignored.

        When importing and an existing course isn't present in imported data:
          - If the course's end time is in the past, the course will be left as
            it is.
          - If the course's end time is not in the past, the course will be soft
            deleted alongside its sub events.

        If an activity has something in field "timetables", it will be imported
        as a recurring event, otherwise as a one-time event.

        A recurring course will have a super event which includes the course's
        whole time period, and sub events which will represent individual course
        occurrences. Other than start and end times, a super event and its sub
        events will all contain the same data.

        A recurring course's sub event start and end datetimes will be build using
        the activity's "timetables". The time tables contain info out weekday,
        times, and repetition which means number of days there is between
        occurrences (basically a multiple of 7).

        A recurring course's sub events will be given an ID that has the
        activity's ID and start and end times of the sub event in a compressed
        form. This also means that between imports only sub events that are
        happening exactly at the same time are considered to be the same instance,
        so if a sub event's begin or end time changes at all, a new sub event will
        be created instead of updating an old one (because there is no unambiguous
        way to determine which old sub event the new one corresponds to).

        A course's keywords will come from both of the following:
          - The activity's main category. There are hardcoded keywords for every
            main category.
          - The activity's sub category's "searchwords". Those are manually
            entered words, which are mapped to keywords using KeywordMatcher
            (from events.keywords).

        A course's audience will come from both of the following:
          - The activity's "audience_max_age" and "audience_min_age" using
            hardcoded keywords for certain age ranges.
          - The course's keywords, adding the ones that are present in
            KEYWORDS_TO_ADD_TO_AUDIENCE (from events.importer.yso).
        """
        logger.info('Importing courses...')

        locations = self.fetch_locations()
        if not locations:
            logger.warning('No location data fetched, aborting course import.')
            return

        self.location_id_to_place_id = self.map_harrastushaku_location_ids_to_tprek_ids(locations)

        activities = self.fetch_courses()
        if not activities:
            logger.info('No activity data fetched.')
            return

        def event_delete(event):
            if event.end_time < now():
                return
            event.soft_delete()
            for sub_event in event.sub_events.all():
                sub_event.soft_delete()

        self.event_syncher = ModelSyncher(
            Event.objects.filter(data_source=self.data_source, super_event=None),
            lambda event: event.id,
            event_delete,
        )

        num_of_activities = len(activities)
        logger.debug('Handling {} activities...'.format(num_of_activities))

        for i, activity in enumerate(activities, 1):
            try:
                self.handle_activity(activity)
            except Exception as e:  # noqa
                message = e if isinstance(e, HarrastushakuException) else traceback.format_exc()
                logger.error('Error handling activity {}: {}'.format(activity.get('id'), message))

            if not i % 10:
                logger.debug('{} / {} activities handled.'.format(i, num_of_activities))

        self.event_syncher.finish(force=True)
        logger.info('Course import finished.')

    def fetch_locations(self):
        logger.debug('Fetching locations...')
        try:
            url = '{}location/'.format(HARRASTUSHAKU_API_BASE_URL)
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error('Cannot fetch locations: {}'.format(e))
        return []

    def fetch_courses(self):
        logger.debug('Fetching courses...')
        try:
            url = '{}activity/'.format(HARRASTUSHAKU_API_BASE_URL)
            response = requests.get(url)
            response.raise_for_status()
            return response.json()['data']
        except requests.RequestException as e:
            logger.error('Cannot fetch courses: {}'.format(e))
        return []

    @transaction.atomic
    def handle_location(self, location_data):
        harrastushaku_location_id = location_data.get('id')
        harrastushaku_location_mapped_id = self.location_id_to_place_id.get(harrastushaku_location_id)

        if harrastushaku_location_mapped_id.startswith(self.tprek_data_source.id):
            return
        else:
            self.handle_non_tprek_location(location_data)

    def handle_non_tprek_location(self, location_data):
        get_string = bind_data_getters(location_data)[0]

        place_data = {
            'name': get_string('name', localized=True),
            'info_url': get_string('url', localized=True),
            'street_address': get_string('address', localized=True),
            'address_locality': get_string('city', localized=True),
            'postal_code': get_string('zip'),
            'data_source': self.data_source,
            'origin_id': location_data['id'],
            'publisher': self.organization,
        }

        self.save_place(place_data)

    @transaction.atomic
    def handle_activity(self, activity_data):
        if activity_data.get('active') not in ('1', 'K'):
            logger.debug('Skipping inactive activity {}'.format(activity_data.get('id')))
            return

        event_data = self.get_event_data(activity_data)
        if event_data['start_time'] > event_data['end_time']:
            raise HarrastushakuException('Start time after end time')

        time_tables = activity_data.get('timetables', [])
        if time_tables:
            self.handle_recurring_event(event_data, time_tables)
        else:
            self.handle_one_time_event(event_data)

    def create_registration_links(self, activity_data):
        # Harrastushaku has own registration links which should be created in the imported events as well
        if activity_data.get('regavailable', 0) and '1' in activity_data['regavailable']:
            # regstart and regend sometimes take "false" value which seem to mean in the cases regavailable=='1' that
            # the registration is going on indefinitely
            reg_start = activity_data['regstartdate'] if isinstance(activity_data['regstartdate'], int) else 0
            reg_end = activity_data['regenddate'] if isinstance(activity_data['regenddate'], int) else 9999999999
            if datetime.utcfromtimestamp(reg_start) <= datetime.utcnow() <= datetime.utcfromtimestamp(reg_end):
                return {'fi': {'registration': f"https://harrastushaku.fi/register/{activity_data['id']}"}}
        return ''

    def get_event_data(self, activity_data):
        get_string, get_int, get_datetime = bind_data_getters(activity_data)

        keywords = self.get_event_keywords(activity_data)
        audience = self.get_event_audiences_from_ages(activity_data) | self.get_event_audiences_from_keywords(keywords)
        keywords |= audience
        event_data = {
            'name': get_string('name', localized=True),
            'description': get_string('description', localized=True),
            'audience_max_age': get_int('agemax'),
            'audience_min_age': get_int('agemin'),
            'start_time': get_datetime('startdate'),
            'end_time': get_datetime('enddate'),
            'date_published': get_datetime('publishdate'),
            'external_links': self.create_registration_links(activity_data),
            'organizer_info': self.get_organizer_info(activity_data),

            'extension_course': {
                'enrolment_start_date': get_datetime('regstartdate'),
                'enrolment_end_date': get_datetime('regenddate'),
                'maximum_attendee_capacity': get_int('maxentries'),
                'remaining_attendee_capacity': get_int('regavailable'),
            },

            'data_source': self.data_source,
            'origin_id': activity_data['id'],
            'publisher': self.organization,
            'location': self.get_event_location(activity_data),
            'keywords': keywords,
            'in_language': self.get_event_languages(activity_data),
            'images': self.get_event_images(activity_data),
            'offers': self.get_event_offers(activity_data),
            'audience': audience,
        }
        return event_data

    def handle_recurring_event(self, event_data, time_tables):
        start_date, end_date = self.get_event_start_and_end_dates(event_data)
        if not start_date:
            raise HarrastushakuException('No start time')
        if not end_date:
            raise HarrastushakuException('No end time')

        if end_date - start_date > timedelta(days=MAX_RECURRING_EVENT_LENGTH):
            raise HarrastushakuException('Too long recurring activity')

        sub_event_time_ranges = self.build_sub_event_time_ranges(start_date, end_date, time_tables)
        if not sub_event_time_ranges:
            raise HarrastushakuException('Erroneous time tables: {}'.format(time_tables))

        super_event = self.save_super_event(event_data)
        self.save_sub_events(event_data, sub_event_time_ranges, super_event)

    def handle_one_time_event(self, event_data):
        event_data['has_start_time'] = False
        event_data['has_end_time'] = False
        event = self.save_event(event_data)
        self.event_syncher.mark(event)

    def get_event_keywords(self, activity_data):
        keywords = (self.get_event_keywords_from_main_categories(activity_data) |
                    self.get_event_keywords_from_search_words(activity_data))
        return keywords

    def get_event_keywords_from_main_categories(self, activity_data):
        main_category_ids = {c.get('maincategory_id') for c in activity_data.get('categories', [])}

        keyword_ids = set()
        for main_category_id in main_category_ids:
            keyword_ids |= MAIN_CATEGORY_KEYWORDS.get(main_category_id, set())

        return {self.keywords.get(kw_id) for kw_id in keyword_ids if kw_id in self.keywords}

    def get_event_keywords_from_search_words(self, activity_data):
        keywords = set()
        search_words = activity_data.get('searchwords', [])

        cleaned_search_words = [s.strip().lower() for s in search_words.split(',') if s.strip()]
        for kw in cleaned_search_words:
            matches = self.match_keyword(kw)
            if matches:
                keywords |= set(matches)

        return keywords

    def get_event_languages(self, activity_data):
        language_text = activity_data.get('languages', '').lower()
        languages = {obj for code, obj in self.languages.items() if obj.name_fi and obj.name_fi in language_text}
        return languages

    def get_event_start_and_end_dates(self, event_data):
        start_datetime = event_data.get('start_time')
        start_date = start_datetime.date() if start_datetime else None
        end_datetime = event_data.get('end_time')
        end_date = end_datetime.date() if end_datetime else None
        return start_date, end_date

    def get_organizer_info(self, activity_data):
        org_details = clean_text(activity_data.get('organiserdetails', ''), strip_newlines=True, parse_html=True)
        reg_details = clean_text(activity_data.get('regdetails', ''), strip_newlines=True, parse_html=True)
        return {'fi': f'{reg_details} {org_details}'.strip()} if org_details or reg_details else ''

    def build_sub_event_time_ranges(self, start_date, end_date, time_tables):
        sub_event_time_ranges = []

        for time_table in time_tables:
            current_date = start_date
            weekday = int(time_table.get('weekday'))
            start_time = parse_time(time_table.get('starttime'))
            end_time = parse_time(time_table.get('endtime'))
            repetition = int(time_table.get('repetition'))
            if repetition == 0:
                repetition = 7  # assume repetition 0 and 7 mean the same thing

            if not (weekday and repetition) or start_time >= end_time:
                continue

            while current_date.isoweekday() != weekday:
                current_date += timedelta(days=1)

            while current_date <= end_date:
                sub_event_time_ranges.append(SubEventTimeRange(
                    datetime.combine(current_date, start_time).astimezone(TIMEZONE),
                    datetime.combine(current_date, end_time).astimezone(TIMEZONE),
                ))
                current_date += timedelta(days=repetition)

        return sub_event_time_ranges

    def save_super_event(self, event_data):
        super_event_data = deepcopy(event_data)
        super_event_data['super_event_type'] = Event.SuperEventType.RECURRING
        event = self.save_event(super_event_data)
        self.event_syncher.mark(event)
        return event

    def save_sub_events(self, event_data, sub_event_time_ranges, super_event):
        super_event._changed = False

        def delete_sub_event(obj):
            logger.debug('{} deleted'.format(obj))
            obj.deleted = True
            obj.save()

        sub_event_syncher = ModelSyncher(
            super_event.sub_events.filter(deleted=False), lambda o: o.id, delete_func=delete_sub_event)

        sub_event_data = deepcopy(event_data)
        sub_event_data['super_event'] = super_event

        for sub_event_time_range in sub_event_time_ranges:
            sub_event_data['start_time'] = sub_event_time_range.start
            sub_event_data['end_time'] = sub_event_time_range.end
            sub_event_data['origin_id'] = (
                    event_data['origin_id'] + self.create_sub_event_origin_id_suffix(sub_event_time_range))
            sub_event = self.save_event(sub_event_data)

            if sub_event._changed:
                super_event._changed = True
            sub_event_syncher.mark(sub_event)

        old_sub_event_count = super_event.sub_events.count()
        sub_event_syncher.finish(force=True)

        if super_event.sub_events.count() != old_sub_event_count:
            super_event._changed = True

        if super_event._changed:
            super_event.save()

    def create_sub_event_origin_id_suffix(self, sub_event_time_range):
        start, end = sub_event_time_range
        assert start.date() == end.date()
        date = start.date().strftime('%Y%m%d')
        times = '{}{}'.format(*(time.time().strftime('%H%M') for time in (start, end)))
        return '_{}{}'.format(date, times)

    def get_event_images(self, activity_data):
        image_data = activity_data.get('images')
        if not isinstance(image_data, dict):
            return []

        event_image_data = [{
            'name': image_datum.get('name', ''),
            'url': image_datum.get('filename', ''),
        } for image_datum in image_data.values()]

        return event_image_data

    def get_event_location(self, activity_data):
        location_id = activity_data.get('location_id')
        if not location_id:
            return None
        return {'id': self.location_id_to_place_id.get(location_id)}

    def get_event_offers(self, activity_data):
        offers = []

        for price_data in activity_data.get('prices', ()):
            get_string = bind_data_getters(price_data)[0]

            price = get_string('price', localized=False)
            description = get_string('description', localized=True)
            is_free = price is not None and price == '0'

            if not description and len(activity_data['prices']) == 1:
                description = get_string('pricedetails', localized=True)

            offers.append({
                'price': price if not is_free else None,
                'is_free': is_free,
                'description': description,
            })

        return offers

    def get_event_audiences_from_ages(self, activity_data):
        audience_keyword_ids = set()
        age_min = get_int_from_data(activity_data, 'agemin') or 0
        age_max = get_int_from_data(activity_data, 'agemax') or 200

        for age_range, keyword_ids in AUDIENCE_BY_AGE_RANGE:
            if ranges_overlap(age_min, age_max, age_range[0], age_range[1]):
                audience_keyword_ids |= keyword_ids

        return {self.keywords.get(k_id) for k_id in audience_keyword_ids if k_id in self.keywords}

    def get_event_audiences_from_keywords(self, keywords):
        return {kw for kw in keywords if kw.id in KEYWORDS_TO_ADD_TO_AUDIENCE}

    @lru_cache()
    def match_keyword(self, text):
        return self.keyword_matcher.match(text)


def get_string_from_data(data, field, localized=False):
    value = data.get(field)
    if not isinstance(value, str):
        return None
    value = clean_text(value)
    if not value:
        return None
    return {'fi': value} if localized else value


def get_int_from_data(data, field):
    value = data.get(field)
    if value in (None, False, ''):
        return None
    return int(value)


def get_datetime_from_data(data, field):
    value = data.get(field)
    if value in (None, False, ''):
        return None
    return datetime.utcfromtimestamp(int(value)).replace(tzinfo=pytz.utc).astimezone(TIMEZONE)


def bind_data_getters(data):
    get_string = partial(get_string_from_data, data)
    get_int = partial(get_int_from_data, data)
    get_datetime = partial(get_datetime_from_data, data)
    return get_string, get_int, get_datetime


def ranges_overlap(x1, x2, y1, y2):
    return x1 <= y2 and y1 <= x2
