
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


YSO_KEYWORD_MAPS = {
    'baletti': ('yso:p1278', 'yso:p10218'),
    'dance': ('yso:p1278',),
    'draama': ('yso:p2625',),
    'elokuva': ('yso:p1235',),
    'elokuvafestivaali': ('yso:p1304', 'yso:p1235'),
    'elämänhallinta': ('yso:p4357',),
    'farssi, satiiri': ('yso:p2625',),
    'hard rock': ('yso:p1808', 'yso:p1882', 'yso:p29778'),
    'hard rock -festivaali': ('yso:p1304', 'yso:p1808', 'yso:p1882', 'yso:p29778'),
    'iskelmä- ja tanssimusiikki': ('yso:p1808', 'yso:p1857', 'yso:p181'),
    'jalkapallo': ('yso:p965', 'yso:p6409'),
    'jazz & blues': ('yso:p1808', 'yso:p4484', 'yso:p4482'),
    'jazz & blues -festivaali': ('yso:p1304', 'yso:p1808', 'yso:p4484', 'yso:p4482'),
    'jääkiekko': ('yso:p965', 'yso:p12697'),
    'kabaree': ('yso:p1808', 'yso:p181', 'yso:p7158'),
    'kansanmusiikki': ('yso:p1808', 'yso:p2841'),
    'kesäteatteri': ('yso:p2625', 'yso:p17654'),
    'klassinen musiikki': ('yso:p1808', 'yso:p18434'),
    'klassisen musiikin festivaali': ('yso:p1304', 'yso:p1808', 'yso:p18434'),
    'klubit': ('yso:p1808', 'yso:p20421'),
    'komedia': ('yso:p2625', 'yso:p13876'),
    'koripallo': ('yso:p965', 'yso:p8781'),
    'lastennäytelmä': ('yso:p2625', 'yso:p16164'),
    'musikaali, musiikkiteatteri': ('yso:p1808', 'yso:p11693', 'yso:p6422'),
    'muu urheilu': ('yso:p965',),
    'nyrkkeily': ('yso:p965', 'yso:p9034'),
    'näyttelyt, messut': ('yso:p5121', 'yso:p4892'),
    'ooppera, operetti': ('yso:p1808', 'yso:p13810'),
    'perhetapahtuma': ('yso:p4363',),
    'ravintolaviihde': ('yso:p5', 'yso:p1634'),
    'rock & pop': ('yso:p1808', 'yso:p3064'),
    'rock & pop -festivaali': ('yso:p1304', 'yso:p1808', 'yso:p3064'),
    'salibandy': ('yso:p965', 'yso:p16555'),
    'show': ('yso:p5', 'yso:p7157'),
    'sirkus': ('yso:p5007',),
    'sotilasmusiikki': ('yso:p1808', 'yso:p11574'),
    'stand up': ('yso:p5', 'yso:p9244'),
    'tanssi': ('yso:p1278',),
    'tanssifestivaali': ('yso:p1304', 'yso:p1278'),
    'tapahtumapaketit - kasino': ('yso:p22939',),
    'tapahtumapaketit - konsertit': ('yso:p1808', 'yso:p11185'),
    'tapahtumapaketit - kulttuuri': ('yso:p360',),
    'tapahtumapaketit - viihde': ('yso:p5',),
    'teatterifestivaali': ('yso:p1304', 'yso:p2625'),
    'viihdekonsertti': ('yso:p1808', 'yso:p5', 'yso:p11185'),
}

HKT_TPREK_PLACE_MAP = {
    'Arena-näyttämö': 'tprek:46367',  # As of writing, tprek has duplicate, so we will map manually
}

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

    def _cache_yso_keyword_objects(self):
        try:
            yso_data_source = DataSource.objects.get(id='yso')
        except DataSource.DoesNotExist:
            self.keyword_by_id = {}
            return
        keyword_id_set = set()
        for yso_keyword_ids in YSO_KEYWORD_MAPS.values():
            for keyword_id in yso_keyword_ids:
                keyword_id_set.add(keyword_id)
        keyword_list = Keyword.objects.filter(data_source=yso_data_source).filter(id__in=keyword_id_set)
        self.keyword_by_id = {keyword.id: keyword for keyword in keyword_list}

    def _cache_place_data(self):
        self.place_data_list = Place.objects.filter(data_source=self.tprek_data_source).values(
            'id', 'name', 'street_address_fi', 'street_address_sv', 'address_locality'
        )
        for place_data in self.place_data_list:
            place_data['name__lower'] = place_data['name'].lower()

            if place_data['street_address_fi']:
                place_data['street_address_fi__lower'] = place_data['street_address_fi'].lower()
            else:
                place_data['street_address_fi__lower'] = None

            if place_data['street_address_sv']:
                place_data['street_address_sv__lower'] = place_data['street_address_sv'].lower()
            else:
                place_data['street_address_sv__lower'] = None

            if place_data['address_locality']:
                place_data['address_locality__lower'] = place_data['address_locality'].lower()
            else:
                place_data['address_locality__lower'] = None

        self.existing_place_id_matches = {}

    def setup(self):
        data_source_args = dict(id=self.name)
        data_source_defaults = dict(name="Lippupiste")
        self.data_source, _ = DataSource.objects.get_or_create(defaults=data_source_defaults, **data_source_args)
        self.tprek_data_source = DataSource.objects.get(id='tprek')

        ytj_data_source, _ = DataSource.objects.get_or_create(defaults={'name': "YTJ"}, id='ytj')
        org_args = dict(origin_id='1789232-4', data_source=ytj_data_source, internal_type=Organization.AFFILIATED)
        org_defaults = dict(name="Lippupiste Oy")
        self.organization, _ = Organization.objects.get_or_create(defaults=org_defaults, **org_args)
        self._cache_yso_keyword_objects()
        self._cache_place_data()

    def _fetch_event_source_data(self, url):
        # stream=True allows lazy iteration
        response = requests.get(url, stream=True)
        response_iter = response.iter_lines()
        # CSV reader wants str instead of byte, let's decode
        decoded_response_iter = codecs.iterdecode(response_iter, 'utf-8')
        reader = csv.DictReader(decoded_response_iter, delimiter=';', quotechar='"', doublequote=True)
        return reader

    def _get_keywords_from_source_category(self, source_category):
        source_category_key = source_category.lower()
        keyword_set = set()
        for keyword_id in YSO_KEYWORD_MAPS.get(source_category_key, []):
            if keyword_id in self.keyword_by_id:
                keyword_obj = self.keyword_by_id[keyword_id]
                keyword_set.add(keyword_obj)
        return keyword_set

    def _get_keywords_from_source_categories(self, source_categories):
        source_categories = source_categories.split('|')
        keyword_set = set()
        for category in source_categories:
            keyword_set = keyword_set.union(self._get_keywords_from_source_category(category))
        return keyword_set

    def _get_place_id_from_source_event(self, source_event):
        if source_event['EventVenue'] in self.existing_place_id_matches:
            return self.existing_place_id_matches[source_event['EventVenue']]
        if source_event['EventVenue'] in HKT_TPREK_PLACE_MAP:
            return HKT_TPREK_PLACE_MAP[source_event['EventVenue']]

        matches_by_partial_name = []
        matches_by_address = []
        matches_by_partial_address = []

        source_place_name = source_event['EventVenue'].lower()
        source_address = source_event['EventStreet'].lower()
        source_locality = source_event['EventPlace'].lower()

        for place_data in self.place_data_list:
            place_id = place_data['id']
            candidate_place_name = place_data['name__lower']
            candidate_address_fi = place_data['street_address_fi__lower']
            candidate_address_sv = place_data['street_address_sv__lower']
            candidate_locality = place_data['address_locality__lower']

            # If the name matches exactly, the list will not produce better matches, so we can skip the rest
            if source_place_name == candidate_place_name:
                self.existing_place_id_matches[source_event['EventVenue']] = place_id
                return place_id

            if source_place_name in candidate_place_name or candidate_place_name in source_place_name:
                matches_by_partial_name.append(place_id)

            # Street addresses alone are not unique, locality must match
            elif source_locality == candidate_locality:
                is_exact_address_match = (
                    (
                        candidate_address_fi is not None
                        and source_address == candidate_address_fi
                    )
                    or (
                        candidate_address_sv is not None
                        and source_address == candidate_address_sv
                    )
                )
                is_partial_address_match = (
                    (
                        candidate_address_fi is not None
                        and (
                            source_address in candidate_address_fi
                            or
                            candidate_address_fi in source_address
                        )
                    )
                    or (
                        candidate_address_sv is not None
                        and (
                            source_address in candidate_address_sv
                            or
                            candidate_address_sv in source_address
                        )
                    )
                )
                if is_exact_address_match:
                    matches_by_address.append(place_id)
                if is_partial_address_match:
                    matches_by_partial_address.append(place_id)

        if matches_by_partial_name:
            place_id = matches_by_partial_name[0]
            self.existing_place_id_matches[source_event['EventVenue']] = place_id
            return place_id
        if matches_by_address:
            place_id = matches_by_address[0]
            self.existing_place_id_matches[source_event['EventVenue']] = place_id
            return place_id
        if matches_by_partial_address:
            place_id = matches_by_partial_address[0]
            self.existing_place_id_matches[source_event['EventVenue']] = place_id
            return place_id
        return None

    def _import_event(self, source_event, events):
        # Event and serie IDs separated with namespace, since they may overlap
        event_source_id = source_event['EventId']
        superevent_source_id = 'serie-%s' % source_event['EventSerieId']

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
        event['image_license'] = 'event_only'

        existing_keywords = event.get('keywords', set())
        keywords_from_source = self._get_keywords_from_source_categories(source_event['EventSerieCategories'])
        event['keywords'] = existing_keywords.union(keywords_from_source)

        place_id = self._get_place_id_from_source_event(source_event)
        if place_id:
            event['location']['id'] = place_id
        else:
            print("No match found for place '%s' (event %s)" % (source_event['EventVenue'], event['name']['fi']))

        # TODO: superevents

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
