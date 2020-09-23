# Last updated 04/09/2020

# PEP8 mode (Exceeding line length unavoidable at times),
# Processing improvements (List comprehension, JSON update methods),
# JSON re-usage through return instead of global. (Globals are bad practice),
# Category key updated & JSON misspelling compensation,
# Necessary Image field improvements (alt_text, name, photographer),
# Images are shown on front-end without crash.

# Dependencies
import logging
import requests
import requests_cache
import re
import dateutil.parser
import time
import pytz
import bleach
from datetime import datetime, timedelta
from django.utils.html import strip_tags
from events.models import Event, Keyword, DataSource, Place, License, Image
from events.models import Language, EventLink, Offer
from django_orghierarchy.models import Organization, OrganizationClass
from pytz import timezone
from django.conf import settings
from .util import clean_text
from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
from .yso import KEYWORDS_TO_ADD_TO_AUDIENCE
from os import mkdir
from os.path import abspath, join, dirname, exists, basename, splitext
from copy import copy

if not exists(join(dirname(__file__), 'logs')):
    mkdir(join(dirname(__file__), 'logs'))

__setattr__ = setattr

logger = logging.getLogger(__name__)  # Per module logger
curFileExt = basename(__file__)
curFile = splitext(curFileExt)[0]
logFile = \
    logging.FileHandler(
        '%s' % (join(dirname(__file__), 'logs', curFile+'.logs'))
    )
logFile.setFormatter(
    logging.Formatter(
        '[%(asctime)s] <%(name)s> (%(lineno)d): %(message)s'
    )
)
logFile.setLevel(logging.DEBUG)
logger.addHandler(
    logFile
)

VIRTUAL_LOCATION_ID = "virtual:public"
KEYW_LIST = []

TURKU_KEYWORD_IDS = {
    'Festivaalit': 'yso:p1304',  # Festivaalit
    'Konferenssit ja kokoukset': 'yso:p38203',  # Konferenssit (ja kokoukset)
    'Messut': 'yso:p4892',  # Messut
    'Myyjäiset': 'yso:p9376',  # Myyjäiset
    'Musiikki': 'yso:p1808',  # Musiikki
    'Museot': 'yso:p4934',  # Museot
    'Näyttelyt': 'yso:p5121',  # Näyttelyt
    'Luennot': 'yso:p15875',  # Luennot
    'Osallisuus': 'yso:p5164',  # Osallisuus
    'Monikulttuurisuus': 'yso:p10647',  # Monikulttuurisuus
    'Retket': 'yso:p25261',  # Retket
    'Risteilyt': 'yso:p1917',  # Risteilyt
    'Matkat': 'yso:p366',  # Matkat
    'Matkailu': 'yso:p3917',  # Matkailu
    'Opastus': 'yso:p2149',  # Opastus
    'Teatteritaide': 'yso:p2625',  # Teatteritaide
    'Muu esittävä taide': 'yso:p2850',  # Muu esittävä taide
    'Urheilu': 'yso:p965',  # Urheilu
    'Kirjallisuus': 'yso:p8113',  # Kirjallisuus
    'Tapahtumat ja toiminnat': 'yso:p15238',  # Tapahtumat ja toiminnat
    'Ruoka': 'yso:p3670',  # Ruoka
    'Tanssi': 'yso:p1278',  # Tanssi
    'Työpajat': 'yso:p19245',  # Työpajat
    'Ulkoilu': 'yso:p2771',  # Ulkoilu
    'Etäosallistuminen': 'yso:p26626',  # Etäosallistuminen
}

TURKU_AUDIENCES_KEYWORD_IDS = {
    'Aikuiset': 'yso:p5590',  # Aikuiset
    'Lapsiperheet': 'yso:p13050',  # Lapsiperheet
    'Maahanmuttajat': 'yso:p6165',  # Maahanmuuttujat
    'Matkailijat': 'yso:p16596',  # Matkailijat
    'Nuoret': 'yso:p11617',  # Nuoret
    'Seniorit': 'yso:p2433',  # Seniorit
    'Työnhakijat': 'yso:p9607',  # Työnhakijat
    'Vammaiset': 'yso:p7179',  # Vammaiset
    'Vauvat': 'yso:p15937',  # Vauvat
    'Viranomaiset': 'yso:p6946',  # Viranomaiset
    'Järjestöt': 'yso:p1393',  # järjestöt
    'Yrittäjät': 'yso:p1178',  # Yrittäjät
}

TURKU_DRUPAL_CATEGORY_EN_YSOID = {
    'Exhibits': 'yso:p5121',  # Utställningar, Näyttelyt
    'Festival and major events': 'yso:p1304',  # Festivaalit ja suurtapahtumat
    'Meetings and congress ': 'yso:p7500',  # Möten, Kokoukset
    'Trade fair and fair': 'yso:p4892',  # Messut, mässor
    'Music': 'yso:p1808',  # Musiikki, musik
    'Museum': 'yso:p4934',  # Museo,  museum (en), museer
    'Lectures': 'yso:p15875',  # Luennot, föreläsningar
    'Participation': 'yso:p5164',  # Osallisuus, delaktighet
    'Multiculturalism': 'yso:p10647',  # Monikulttuurisuus, multikulturalism
    'cruises and tours': ['yso:p1917', 'yso:p366'],  # Risteily, Matkat
    'Trips': 'yso:p25261',  # Retket
    'Guided tours and sightseeing tours': 'yso:p2149',  # Guidning, Opastukset
    'Theatre and other performance art': ['yso:p2850', 'yso:p2625'],  # Esittävä taide
    'Sports': 'yso:p965',  # Urheilu, Idrott
    'Literature': 'yso:p8113',  # Kirjallisuus, litteratur
}

TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID = {
    'Adults': 'yso:p5590',
    'Child families': 'yso:p13050',
    'Immigrants': 'yso:p6165',
    'Travellers': 'yso:p16596',
    'Youth': 'yso:p11617',
    'Elderly': 'yso:p2433',
    'Jobseekers': 'yso:p9607',
    'Disabled': 'yso:p7179',
    'Infants and toddlers': 'yso:p15937',
    'Authorities': 'yso:p6946',
    'Associations and communities': 'yso:p1393',
    'Entrepreneurs': 'yso:p1178',
}

LANGUAGES_TURKU_OLD = ['fi', 'sv', 'en']
CITY_LIST = [
    'turku', 'naantali', 'raisio', 'nousiainen', 'mynämäki', 'masku',
    'aura', 'marttila', 'kaarina', 'lieto', 'paimio', 'sauvo'
]
TZ = timezone('Europe/Helsinki')
notFoundKeys = []


def set_deleted_false(obj):

    obj.deleted = False
    obj.save(update_fields=['deleted'])
    return True


class APIBrokenError(Exception):
    pass


@register_importer
class TurkuOriginalImporter(Importer):
    name = curFile
    supported_languages = LANGUAGES_TURKU_OLD  # LANGUAGES
    languages_to_detect = []
    current_tick_index = 0
    kwcache = {}

    def setup(self):
        self.languages_to_detect = [
            lang[0].replace('-', '_') for lang in settings.LANGUAGES
            if lang[0] not in self.supported_languages
        ]
        ds_args = dict(id='turku')
        defaults = dict(name='Kuntakohtainen data Turun Kaupunki')
        self.data_source, _ = DataSource.objects.update_or_create(
            defaults=defaults, **ds_args)
        self.tpr_data_source = DataSource.objects.get(id='tpr')
        self.org_data_source = DataSource.objects.get(id='org')
        self.system_data_source = DataSource.objects.get(
            id=settings.SYSTEM_DATA_SOURCE_ID
        )
        ds_args = dict(origin_id='3', data_source=self.org_data_source)
        defaults = dict(name='Kunta')
        self.organizationclass, _ = OrganizationClass.objects.update_or_create(
            defaults=defaults,
            **ds_args
        )
        org_args = dict(
            origin_id='853',
            data_source=self.data_source,
            classification_id="org:3"
        )
        defaults = dict(name='Turun kaupunki')
        self.organization, _ = Organization.objects.update_or_create(
            defaults=defaults,
            **org_args
        )
        ds_args4 = dict(id='virtual', user_editable=True)
        defaults4 = dict(name='Virtuaalitapahtumat (ei paikkaa, vain URL)')
        self.data_source_virtual, _ = DataSource.objects.update_or_create(
            defaults=defaults4,
            **ds_args4
        )
        org_args4 = dict(
            origin_id='3000',
            data_source=self.data_source_virtual,
            classification_id="org:14"
        )
        defaults4 = dict(name='Virtuaalitapahtumat')
        self.organization_virtual, _ = Organization.objects.update_or_create(
            defaults=defaults4,
            **org_args4
        )

        defaults5 = dict(
            data_source=self.data_source_virtual,
            publisher=self.organization_virtual,
            name='Virtuaalitapahtuma',
            name_fi='Virtuaalitapahtuma',
            name_sv='Virtuell evenemang',
            name_en='Virtual event',
            description='Virtuaalitapahtumat merkitään tähän paikkatietoon.'
            )
        self.internet_location, _ = Place.objects.update_or_create(
            id=VIRTUAL_LOCATION_ID,
            defaults=defaults5
        )

        try:
            self.event_only_license = License.objects.get(id='event_only')
        except License.DoesNotExist:
            self.event_only_license = None

        try:
            self.cc_by_license = License.objects.get(id='cc_by')
        except License.DoesNotExist:
            self.cc_by_license = None

        try:
            yso_data_source = DataSource.objects.get(id='yso')
        except DataSource.DoesNotExist:
            yso_data_source = None

        if yso_data_source:  # Build a cached list of YSO keywords
            cat_id_set = set()
            for yso_val in TURKU_KEYWORD_IDS.values():
                if isinstance(yso_val, tuple):
                    for t_v in yso_val:
                        cat_id_set.add(t_v)
                else:
                    cat_id_set.add(yso_val)
            KEYW_LIST = Keyword.objects.filter(data_source=yso_data_source).\
                filter(id__in=cat_id_set)
            self.yso_by_id = {p.id: p for p in KEYW_LIST}
        else:
            self.yso_by_id = {}

        if self.options['cached']:
            requests_cache.install_cache('turku')
            self.cache = requests_cache.get_cache()
        else:
            self.cache = None

    @staticmethod
    def _get_eventTku(event_el):
        eventTku = recur_dict()
        eventTku = event_el
        return eventTku

    def _cache_super_event_id(self, sourceEventSuperId):
        superid = (self.data_source.name + ':' + sourceEventSuperId)
        one_super_event = Event.objects.get(id=superid)
        return one_super_event

    def dt_parse(self, dt_str):
        """Convert a string to UTC datetime"""  # Times are in UTC+02:00 TZ
        return TZ.localize(
                dateutil.parser.parse(dt_str),
                is_dst=None).astimezone(pytz.utc)

    def timeToTimestamp(self, origTime):
        timestamp = time.mktime(time.strptime(origTime, '%d.%m.%Y %H.%M'))
        dt_object = datetime.fromtimestamp(timestamp)
        return str(dt_object)

    def with_value(self, data: dict, value: object, default: object):
        item = data.get(value, default)
        if not item:
            return default
        return item

    def _import_event(self, lang, event_el, events, event_type):
        eventTku = self._get_eventTku(event_el)
        start_time = self.dt_parse(
            self.timeToTimestamp(str(eventTku['start_date']))
        )
        end_time = self.dt_parse(self.timeToTimestamp(
            str(eventTku['end_date']))
        )

        # Import only at most one year old events.
        if end_time < datetime.now().replace(tzinfo=TZ) - timedelta(days=365):
            return {'start_time': start_time, 'end_time': end_time}

        if not bool(int(eventTku['is_hobby'])):
            eid = int(eventTku['drupal_nid'])
            evItem = events[eid]
            evItem['id'] = '%s:%s' % (self.data_source.id, eid)
            evItem['origin_id'] = eid
            evItem['data_source'] = self.data_source
            evItem['publisher'] = self.organization
            evItem['end_time'] = end_time

            ok_tags = (
                'u', 'b', 'h2', 'h3', 'em', 'ul',
                'li', 'strong', 'br', 'p', 'a'
            )

            evItem['name'] = {
                "fi": eventTku['title_fi'],
                "sv": eventTku['title_sv'],
                "en": eventTku['title_en']
            }

            evItem['description'] = {
                "fi": bleach.clean(self.with_value(
                    eventTku,
                    'description_markup_fi',
                    ''),   tags=[],   strip=True),
                "sv": bleach.clean(self.with_value(
                    eventTku,
                    'description_markup_sv',
                    ''),   tags=[],   strip=True),
                "en": bleach.clean(self.with_value(
                    eventTku,
                    'description_markup_en',
                    ''),   tags=[],   strip=True)
            }

            evItem['short_description'] = {
                "fi": bleach.clean(self.with_value(
                    eventTku,
                    'lead_paragraph_markup_fi',
                    ''),   tags=[],   strip=True),
                "sv": bleach.clean(self.with_value(
                    eventTku,
                    'lead_paragraph_markup_sv',
                    ''),   tags=[],   strip=True),
                "en": bleach.clean(self.with_value(
                    eventTku,
                    'lead_paragraph_markup_en',
                    ''),   tags=[],   strip=True)
            }

            if eventTku['event_organizer']:
                eo = eventTku['event_organizer']
                evItem['provider'] = {
                    "fi": eo, "sv": eo, "en": eo
                }
            else:
                evItem['provider'] = {
                    "fi": 'Turku', "sv": 'Åbo', "en": 'Turku'
                }

            location_extra_info = ''

            if self.with_value(eventTku, 'address_extension', ''):
                location_extra_info += '%s, ' % bleach.clean(self.with_value(
                    eventTku,
                    'address_extension',
                    ''), tags=[], strip=True)
            if self.with_value(eventTku, 'city_district', ''):
                location_extra_info += '%s, ' % bleach.clean(self.with_value(
                    eventTku,
                    'city_district',
                    ''), tags=[], strip=True)
            if self.with_value(eventTku, 'place', ''):
                location_extra_info += '%s' % bleach.clean(self.with_value(
                    eventTku,
                    'place',
                    ''), tags=[], strip=True)

            if location_extra_info.strip().endswith(','):
                location_extra_info = location_extra_info.strip()[:-1]

            evItem['location_extra_info'] = {
                "fi": location_extra_info if location_extra_info else None,
                "sv": location_extra_info if location_extra_info else None,
                "en": location_extra_info if location_extra_info else None
            }

            if eventTku['event_image_ext_url']:
                if int(eventTku['event_image_license']) == 1:
                    evItem['images'] = [{
                        'url': eventTku['event_image_ext_url']['src'],
                        'license': self.cc_by_license,
                        'alt_text': '',
                        'name': '',
                        'photographer_name': ''
                    }]

            def set_attr(field_name, val):
                if field_name in evItem:
                    if evItem[field_name] != val:
                        logger.warning(
                            'Event %s: %s mismatch (%s vs. %s)' %
                            (eid, field_name, evItem[field_name], val)
                        )
                        return
                evItem[field_name] = val

            evItem['date_published'] = self.dt_parse(self.timeToTimestamp(
                str(eventTku['start_date']))
            )
            set_attr('start_time', self.dt_parse(self.timeToTimestamp(
                str(eventTku['start_date'])))
            )
            set_attr('end_time', self.dt_parse(self.timeToTimestamp(
                str(eventTku['end_date'])))
            )
            event_in_language = evItem.get('in_language', set())
            try:
                eventLang = Language.objects.get(id='fi')
            except:
                logger.info('Language (fi) not found.')
            if eventLang:
                event_in_language.add(self.languages[eventLang.id])

            evItem['in_language'] = event_in_language

            event_keywords = evItem.get('keywords', set())
            event_audience = evItem.get('audience', set())

            if eventTku['event_categories'] is not None:
                eventTku['event_categories'] = eventTku['event_categories']+','
                categories = eventTku['event_categories'].split(',')
                for name in categories:
                    name = name.strip()
                    if name == 'Theatre and other perfomance art':
                        name = 'Theatre and other performance art'
                        # Theatre and other performance art is spelled incorrectly in the JSON. "Perfomance".
                    if name in TURKU_DRUPAL_CATEGORY_EN_YSOID.keys():
                        ysoId = TURKU_DRUPAL_CATEGORY_EN_YSOID[name]
                        if isinstance(ysoId, list):
                            for x in range(len(ysoId)):
                                event_keywords.add(
                                    Keyword.objects.get(id=ysoId[x])
                                )
                        else:
                            event_keywords.add(
                                Keyword.objects.get(id=ysoId)
                            )

            if eventTku.get('keywords', None):
                eventTku['keywords'] = eventTku['keywords'] + ','
                keywords = eventTku['keywords'].split(',')
                for name in keywords:
                    name.strip()
                    if name not in TURKU_DRUPAL_CATEGORY_EN_YSOID.keys():
                        try:
                            event_keywords.add(
                                Keyword.objects.get(name=name)
                            )
                        except:
                            if name != "":
                                notFoundKeys.append({
                                    name: eventTku['drupal_nid']
                                })
                            pass

            evItem['keywords'] = event_keywords

            if eventTku['target_audience'] is not None:
                eventTku['target_audience'] = eventTku['target_audience'] + ','
                audience = eventTku['target_audience'].split(',')
                for name in audience:
                    if name in TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID.keys():
                        ysoId = TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID[name]
                        event_audience.add(
                            Keyword.objects.get(id=ysoId)
                        )

            evItem['audience'] = event_audience
            evItem['info_url'] = {
                "fi": eventTku['website_url'],
                "sv": eventTku['website_url'],
                "en": eventTku['website_url']
            }

            tprNo = ''

            if eventTku.get('event_categories', None):
                node_type = eventTku['event_categories'][0]
                if node_type == 'Virtual events':
                    evItem['location']['id'] = VIRTUAL_LOCATION_ID
                elif str(eventTku['palvelukanava_code']):
                    tprNo = str(eventTku['palvelukanava_code'])
                    if tprNo == '10123':
                        tprNo = '148'
                    elif tprNo == '10132':
                        return
                    elif tprNo == '10174':
                        return
                    elif tprNo == '10129':
                        return

                    evItem['location']['id'] = ('tpr:' + tprNo)
                else:
                    def numeric(string):
                        from hashlib import md5
                        h = md5()
                        h.update(string.encode())
                        return str(int(h.hexdigest(), 16))[0:6]

                    if eventTku['address']:
                        import re
                        event_address = copy(eventTku['address'])
                        event_address_name = copy(eventTku['address'])
                        event_name = ""
                        event_postal_code = None
                        regex = re.search(
                            r'\d{4,6}', event_address_name, re.IGNORECASE
                        )
                        if regex:
                            event_postal_code = regex.group(0)
                        if event_address_name.startswith('('):

                            regex = re.search(
                                r'\((.*?)\)\\?(.*|[a-z]|[0-9])',
                                event_address,
                                re.IGNORECASE
                            )  # Match: (str, str) str
                            event_name = '%s' % regex.group(1)

                            try:
                                _regex = re.search(
                                    r'(?<=\))[^\]][^,]+',
                                    regex.group(0),
                                    re.IGNORECASE
                                )
                                event_address_name = _regex.group(0).strip().capitalize()
                            except:
                                _regex = re.search(
                                    r'(?<=\))[^\]][^,]+',
                                    regex.group(1),
                                    re.IGNORECASE
                                )
                                event_address_name = _regex.group(0).strip().capitalize()

                        else:
                            _regex = re.search(
                                r'(?<=)[^\]][^,]+',
                                event_address_name,
                                re.IGNORECASE
                            )
                            event_name = _regex.group(0).strip().capitalize()
                        city = ""
                        for _city in CITY_LIST:
                            if len(event_address.split(',')) >= 2:
                                q = event_address.split(',')[1].lower().strip()
                                if q == _city.lower():
                                    city = _city
                                    break

                        addr = 'osoite:%s' % (''.join(
                                event_address.replace(' ', '_')
                                .split(','))
                                .strip()
                                .lower()
                                .replace('k.', 'katu'))

                        if city and not addr.endswith(city):
                            addr += '_%s' % city.lower()
                        elif city and addr.endswith(city):
                            ...
                        elif not city and not addr.endswith('_turku'):
                            addr += '_turku'

                        origin_id = numeric(addr)
                        tpr = '%s:%s' % (
                            str(evItem.get('data_source')),
                            origin_id
                            )  # Mimic tpr
                        try:
                            place_id = Place.objects.get(id=tpr)
                        except:
                            def place_info(data: dict, translated=[]) -> Place:
                                p = Place()
                                for k in data:
                                    __setattr__(p, k, data[k])
                                    if k in translated:
                                        __setattr__(p, '%s_fi' % k, data[k])
                                        __setattr__(p, '%s_en' % k, data[k])
                                        __setattr__(p, '%s_sv' % k, data[k])
                                return p

                            place = \
                                place_info({
                                    'name': event_name,
                                    'street_address': event_address_name,
                                    'id': tpr,
                                    'origin_id': origin_id,
                                    'data_source': evItem.get('data_source'),
                                    'publisher': evItem.get('publisher'),
                                    'postal_code': event_postal_code
                                }, translated=[
                                    'name',
                                    'street_address'
                                    ]
                                )
                            place.save()
                        evItem['location']['id'] = tpr

            if event_type == "m" or event_type == "s":
                # Add a default offer
                free_offer = {
                    'is_free': True,
                    'price': None,
                    'description': None,
                    'info_url': None,
                    }
                eventOffer_is_free = bool(int(eventTku['free_event']))
                # Fill if events is not free price event
                if not eventOffer_is_free:
                    free_offer['is_free'] = False
                    if eventTku['event_price']:
                        ok_tags = (
                            'u', 'b', 'h2', 'h3', 'em', 'ul',
                            'li', 'strong', 'br', 'p', 'a'
                        )
                        price = str(eventTku['event_price'])
                        price = bleach.clean(price, tags=ok_tags, strip=True)
                        free_offer_price = clean_text(price, True)
                        free_offer['price'] = {'fi': free_offer_price}
                        free_offer['info_url'] = {'fi': None}
                    if str(eventTku['buy_tickets_url']):
                        free_offer_buy_tickets = eventTku['buy_tickets_url']
                        free_offer['info_url'] = {'fi': free_offer_buy_tickets}
                    free_offer['description'] = None
                evItem['offers'] = [free_offer]

            if event_type == "m":
                evItem['super_event_type'] = Event.SuperEventType.RECURRING
            if event_type == "c" or event_type == "s":
                evItem['super_event_type'] = None

            return evItem

    def _recur_fetch_paginated_url(self, url, lang, events):
        max_tries = 5
        logger.info("Establishing connection to Drupal JSON...")
        for try_number in range(0, max_tries):
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code != 200:
                logger.warning(
                    "Drupal orig API reported HTTP %d" % response.status_code
                )
            if self.cache:
                self.cache.delete_url(url)
                continue
            try:
                root_doc = response.json()
            except ValueError:
                logger.warning(
                    "Drupal orig API returned invalid JSON (try {} of {})"
                    .format(try_number + 1, max_tries)
                )
                if self.cache:
                    self.cache.delete_url(url)
                    continue
            break
        else:
            logger.error("Drupal orig API broken again, giving up")
            raise APIBrokenError()

        jsr = root_doc['events']

        earliest_end_time = None

        def to_import(lang, ev, events, ev_type):
            event = self._import_event(lang, ev, events, ev_type)

        # Import Single Event(s).
        for x in jsr:
            for k, v in x.items():
                if v['event_type'] == "Single event":
                    to_import(lang, v, events, 's')
        # Pre-Process.
        childrens_mother = [
            v['drupal_nid_super'] for x in jsr for k, v in x.items()
            if v['event_type'] == "Recurring event (in series)"
        ]
        mothers_with_children = [
            v for x in jsr for k, v in x.items()
            if v['drupal_nid'] in childrens_mother
        ]
        mothers_children = [
            v for x in jsr for k, v in x.items()
            for c in mothers_with_children
            for b, n in c.items()
            if b == "drupal_nid" and n == v['drupal_nid_super']
        ]
        # Import Mother & Child Event(s).
        for x in mothers_with_children:
            to_import(lang, x, events, 'm')
            for z in mothers_children:
                if z['drupal_nid_super'] == x['drupal_nid']:
                    z.update({
                        'event_image_ext_url': x['event_image_ext_url'],
                        'event_image_license': x['event_image_license'],
                        'facebook_url': x['facebook_url'],
                        'twitter_url': x['twitter_url']
                    })
                    to_import(lang, z, events, 'c')
        now = datetime.now().replace(tzinfo=TZ)
        return root_doc, mothers_with_children, mothers_children

    def save_extra(self, drupal_url, mothersList, childList):
        for json_mother_event in drupal_url['events']:
            json_event = json_mother_event['event']
            if json_event['drupal_nid']:
                for x in childList:
                    if json_event['drupal_nid'] == x['drupal_nid_super']:
                        try:
                            child = Event.objects.get(origin_id=x['drupal_nid'])
                            mother = Event.objects.get(origin_id=json_event['drupal_nid'])
                            try:
                                Event.objects.update_or_create(
                                    id=child.id,
                                    defaults={
                                        'date_published': mother.date_published,
                                        'provider': mother.provider,
                                        'provider_fi': mother.provider_fi,
                                        'provider_sv': mother.provider_sv,
                                        'provider_en': mother.provider_en,
                                        'description': mother.description,
                                        'description_fi': mother.description_fi,
                                        'description_sv': mother.description_sv,
                                        'description_en': mother.description_en,
                                        'short_description': mother.short_description,
                                        'short_description_fi': mother.short_description_fi,
                                        'short_description_sv': mother.short_description_sv,
                                        'short_description_en': mother.short_description_en,
                                        'location_id': mother.location_id,
                                        'location_extra_info': mother.location_extra_info,
                                        'location_extra_info_fi': mother.location_extra_info_fi,
                                        'location_extra_info_sv': mother.location_extra_info_sv,
                                        'location_extra_info_en': mother.location_extra_info_en,
                                        'info_url': mother.info_url,
                                        'info_url_fi': mother.info_url_fi,
                                        'info_url_sv': mother.info_url_fi,
                                        'info_url_en': mother.info_url_fi,
                                        'super_event': mother
                                    }
                                )
                            except Exception as ex:
                                pass
                        except Exception as ex:
                            pass

                        try:
                            # Re-get object from Event once saved.
                            child = Event.objects.get(origin_id=x['drupal_nid'])
                            mother = Event.objects.get(origin_id=json_event['drupal_nid'])
                            # Get object from Offer once we have the Event object.
                            try:
                                motherOffer = Offer.objects.get(event_id=mother.id)
                                Offer.objects.update_or_create(
                                    event_id=child.id,
                                    price=motherOffer.price,
                                    info_url=motherOffer.info_url,
                                    description=motherOffer.description,
                                    is_free=motherOffer.is_free
                                )
                            except Exception as ex:
                                pass
                        except Exception as ex:
                            pass

            def fb_tw(ft):
                originid = json_event['drupal_nid']
                # Get Language object.
                ft_name = "extlink_"+ft
                ft_link = ft+"_url"
                try:
                    myLang = Language.objects.get(id="fi")
                except:
                    pass
                try:
                    eventObj = Event.objects.get(origin_id=originid)
                    EventLink.objects.update_or_create(
                        name=ft_name,
                        event_id=eventObj.id,
                        language_id=myLang.id,
                        link=json_event[ft+'_url']
                    )
                except:
                    pass

            if json_event['facebook_url']:
                fb_tw('facebook')
            if json_event['twitter_url']:
                fb_tw('twitter')

    def import_events(self):
        import requests
        events = recur_dict()
        URL = 'https://kalenteri.turku.fi/admin/event-exports/json_beta'
        lang = self.supported_languages
        # Fetch JSON for post-processing but also process & import events.
        try:
            RESPONSE_JSON, mother_events, child_events = self._recur_fetch_paginated_url(URL, lang, events)
        except APIBrokenError:
            return

        event_list = sorted(events.values(), key=lambda x: x['end_time'])
        qs = Event.objects.filter(
            end_time__gte=datetime.now().replace(tzinfo=TZ),
            data_source='turku'
        )
        self.syncher = ModelSyncher(
            qs,
            lambda obj: obj.origin_id,
            delete_func=set_deleted_false
        )

        for event in event_list:
            try:
                obj = self.save_event(event)
                self.syncher.mark(obj)
            except:
                ...
        # Post processing; Facebook Url, Twitter Url & Additional child inheritance data.
        try:
            self.save_extra(RESPONSE_JSON, mother_events, child_events)
        except APIBrokenError:
            return

        self.syncher.finish(force=True)

        if len(notFoundKeys) != 0:
            logger.warning(
                'Moderator should add the missing Keywords:'+str(notFoundKeys)
            )

        logger.info("%d events processed" % len(events.values()))
