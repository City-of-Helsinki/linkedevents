
import codecs
import csv
import pytz
import re
import bleach
import requests
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.html import strip_tags
from django_orghierarchy.models import Organization
from events.models import DataSource, Event, Keyword, Place
from .base import Importer, recur_dict, register_importer
from .sync import ModelSyncher
from .util import clean_text


LIPPUPISTE_EVENT_API_URL = getattr(settings, 'LIPPUPISTE_EVENT_API_URL', None)

LOCAL_TZ = pytz.timezone('Europe/Helsinki')

HTML_BREAK_LINE_REGEX = re.compile(r'<br\s*/?>', re.IGNORECASE)


def mark_deleted(obj):
    if obj.deleted:
        return False
    obj.deleted = True
    obj.save(update_fields=['deleted'])
    return True


def replace_html_breaks_with_whitespace(text):
    return re.sub(HTML_BREAK_LINE_REGEX, ' ', text)


def clean_description(text):
    ok_tags = ('u', 'b', 'h2', 'h3', 'em', 'ul', 'li', 'strong', 'br', 'p', 'a')
    text = bleach.clean(text, tags=ok_tags, strip=True)
    text = clean_text(text)
    return text


def clean_short_description(text):
    text = replace_html_breaks_with_whitespace(text)
    text = strip_tags(text)
    text = clean_text(text)
    if '.' in text:
        text = text.split('.')
        text = text[0] + '.'
    text = text[:160]
    return text


@register_importer
class LippupisteImporter(Importer):
    name = 'lippupiste'
    supported_languages = ['fi']

    def setup(self):
        data_source_args = dict(id=self.name)
        data_source_defaults = dict(name="Lippupiste")
        self.data_source, _ = DataSource.objects.get_or_create(defaults=data_source_defaults, **data_source_args)

        ytj_data_source, _ = DataSource.objects.get_or_create(defaults={'name': "YTJ"}, id='ytj')
        org_args = dict(origin_id='1789232-4', data_source=ytj_data_source, internal_type=Organization.AFFILIATED)
        org_defaults = dict(name="Lippupiste Oy")
        self.organization, _ = Organization.objects.get_or_create(defaults=org_defaults, **org_args)

    def _fetch_event_source_data(self, url):
        # stream=True allows lazy iteration
        response = requests.get(url, stream=True)
        response_iter = response.iter_lines()
        # CSV reader wants str instead of byte, let's decode
        decoded_response_iter = codecs.iterdecode(response_iter, 'utf-8')
        reader = csv.DictReader(decoded_response_iter, delimiter=';', quotechar='"', doublequote=True)
        return reader

    def _import_event(self, source_event, events):
        # Namespaced source IDs, since they may overlap
        event_source_id = 'event%s' % source_event['EventId']
        superevent_source_id = 'serie%s' % source_event['EventSerieId']

        event = events[event_source_id]
        event['id'] = '%s:%s' % (self.data_source.id, event_source_id)
        event['origin_id'] = event_source_id
        event['data_source'] = self.data_source
        event['publisher'] = self.organization

        event_date = datetime.strptime(source_event['EventDate'], '%d.%m.%Y').date()
        event_time = datetime.strptime(source_event['EventTime'], '%H:%M').time()
        event_datetime = LOCAL_TZ.localize(datetime.combine(event_date, event_time))
        event_datetime = event_datetime.astimezone(pytz.utc)
        event['start_time'] = event_datetime
        event['provider']['fi'] = source_event['EventPromoterName']
        event['name']['fi'] = source_event['EventName']
        event['description']['fi'] = clean_description(source_event['EventSerieText'])
        event['short_description']['fi'] = clean_short_description(source_event['EventSerieText'])
        event['info_url']['fi'] = source_event['EventLink']
        event['image'] = source_event['EventSeriePictureBig_222x222']

        # TODO: EventVenue, EventStreet, EventZip, EventPlace

        # TODO: superevents

        # TODO: EventSerieCategories

    def import_events(self):
        if not LIPPUPISTE_EVENT_API_URL:
            raise ImproperlyConfigured("LIPPUPISTE_EVENT_API_URL must be set in local_settings")
        print("Importing Lippupiste events")
        events = recur_dict()

        for source_event in self._fetch_event_source_data(LIPPUPISTE_EVENT_API_URL):
            self._import_event(source_event, events)

        event_list = sorted(events.values(), key=lambda x: x['start_time'])

        now = datetime.now()
        syncher_queryset = Event.objects.filter(end_time__gte=now, data_source=self.data_source, deleted=False)
        self.syncher = ModelSyncher(syncher_queryset, lambda obj: obj.origin_id, delete_func=mark_deleted)

        for event in event_list:
            obj = self.save_event(event)
            self.syncher.mark(obj)

        self.syncher.finish()
        print("%d events processed" % len(events.values()))
