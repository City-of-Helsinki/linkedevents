import logging
import requests
import requests_cache
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

from events.utils import get_field_translations
from .util import clean_text
from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
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

TURKU_LUOKITUS_KEYWORD_IDS = {
    # Hobby content target:
    'Ajanvietepelit': 'tsl:p1',  # Ajanvietepelit
    'Eläimet': 'tsl:p2',  # Eläimet
    'Kielet': 'tsl:p3',  # Kielet
    'Kirjallisuus ja sanataide': 'tsl:p4',  # Kirjallisuus ja sanataide
    'Kuvataide ja media': 'tsl:p5',  # Kuvataide ja media
    'Kädentaidot': 'tsl:p6',  # Kädentaidot
    'Liikunta ja urheilu': 'tsl:p7',  # Liikunta ja urheilu
    'Luonto': 'tsl:p8',  # Luonto
    'Musiikki': 'tsl:p9',  # Musiikki
    'Ruoka ja juoma': 'tsl:p10',  # Ruoka ja juoma
    # Teatteri, tanssi ja sirkus (Previously "Teatteri, performanssi ja sirkus - tsl:p11")
    'Teatteri, tanssi ja sirkus': 'tsl:p56',
    'Tiede ja tekniikka': 'tsl:p12',  # Tiede ja tekniikka
    'Yhteisöllisyys ja auttaminen': 'tsl:p13',  # Yhteisöllisyys ja auttaminen
    'Muu': 'tsl:p58',  # Muu (Previously "Muut - tsl:p14")

    # Event content based:
    'Kuvataide': 'tsl:p28',  # Kuvataide
    'Tanssi': 'tsl:p29',  # Tanssi
    'Teatteri, performanssi ja sirkus': 'tsl:p11',  # Teatteri, performanssi ja sirkus
    'Elokuva': 'tsl:p30',  # Elokuva
    'Käsityöt': 'tsl:p31',  # Käsityöt
    'Terveys ja hyvinvointi': 'tsl:p32',  # Terveys ja hyvinvointi
    'Luonto ja kulttuuriympäristö': 'tsl:p33',  # Luonto ja kulttuuriympäristö
    'Uskonto ja hengellisyys': 'tsl:p34',  # Uskonto ja hengellisyys
    'Yritystoiminta ja työelämä': 'tsl:p35',  # Yritystoiminta ja työelämä
    'Yhteiskunta': 'tsl:p36',  # Yhteiskunta
    'Historia': 'tsl:p37',  # Historia
    'Muu sisältö': 'tsl:p55',  # Muu sisältö

    # Event type based:
    'Festivaalit': 'tsl:p38',  # Festivaalit
    'Kaupunkitapahtumat': 'tsl:p39',  # Kaupunkitapahtumat
    'Keskustelutilaisuudet': 'tsl:p40',  # Keskustelutilaisuudet
    'Kilpailut': 'tsl:p41',  # Kilpailut
    'Kokoukset, seminaarit ja kongressit': 'tsl:p42',  # Kokoukset, seminaarit ja kongressit
    'Konsertit': 'tsl:p43',  # Konsertit
    'Koulutustapahtumat': 'tsl:p44',  # Koulutustapahtumat
    'Leirit': 'tsl:p45',  # Leirit
    'Luennot': 'tsl:p46',  # Luennot
    'Markkinat': 'tsl:p47',  # Markkinat
    'Messut': 'tsl:p48',  # Messut
    'Myyjäiset': 'tsl:p49',  # Myyjäiset
    'Näyttelyt': 'tsl:p50',  # Näyttelyt
    'Opastukset': 'tsl:p51',  # Opastukset
    'Retket': 'tsl:p52',  # Retket
    'Työpajat': 'tsl:p53',  # Työpajat
    'Verkostoitumistapahtumat': 'tsl:p54',  # Verkostoitumistapahtumat
    'Muu tapahtumatyyppi': 'tsl:p57',  # Muu tapahtumatyyppi
}

# These words are not meant to be changed, as they come from the API.
TURKU_DRUPAL_CATEGORY_EN_YSOID = {
    'Exhibits': 'tsl:p50',  # Näyttelyt
    'Festival and major events': 'tsl:p38',  # Festivaalit
    'Meetings and congress ': 'tsl:p42',  # Kokoukset, seminaarit ja kongressit
    'Trade fair and fair': 'tsl:p48',  # Messut
    'Music': 'tsl:p9',  # Musiikki
    'Museum': 'tsl:p37',  # Historia
    'Lectures': 'tsl:p46',  # Luennot
    'Participation': 'tsl:p55',  # Muu
    'Multiculturalism': 'tsl:p55',  # Muu (Previously "Muut - p14")
    'cruises and tours': 'tsl:p52',  # Retket
    'Trips': 'tsl:p52',  # Retket
    'Guided tours and sightseeing tours': 'tsl:p51',  # Opastukset
    'Theatre and other performance art': 'tsl:p11',  # Teatteri, performanssi ja sirkus
    'Sports': 'tsl:p7',  # Liikunta ja urheilu
    'Literature': 'tsl:p4',  # Kirjallisuus, litteratur
    'Virtual events': 'tsl:p55',  # Muu
}

TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID = {
    'Adults': 'tsl:p21',  # Aikuiset
    'Child families': 'tsl:p18',  # Lapset ja lapsiperheet
    'Immigrants': 'tsl:p15',  # Maahamuuttaneet
    'Travellers': 'tsl:p20',  # Nuoret aikuiset (Previously "Matkailijat - tsl:p24")
    'Youth': 'tsl:p19',  # Nuoret
    'Elderly': 'tsl:p22',  # Ikääntyneet
    'Jobseekers': 'tsl:p25',  # Työnhakijat
    'Disabled': 'tsl:p16',  # Toimintarajoitteiset
    'Infants and toddlers': 'tsl:p17',  # Vauvat ja taaperot
    'Authorities': 'tsl:p26',  # Yrittäjät
    'Associations and communities': 'tsl:p26',  # Yrittäjät
    'Entrepreneurs': 'tsl:p26',  # Yrittäjät
}

LANGUAGES_TURKU_OLD = ['fi', 'sv', 'en']
CITY_LIST = [
    'turku', 'naantali', 'raisio', 'nousiainen', 'mynämäki', 'masku',
    'aura', 'marttila', 'kaarina', 'lieto', 'paimio', 'sauvo'
]
TZ = timezone('Europe/Helsinki')

SAFE_TAGS = (
    'u', 'b', 'h2', 'h3', 'em', 'ul',
    'li', 'strong', 'br', 'p', 'a'
)

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
            tsl_data_source = DataSource.objects.get(id='tsl')
        except DataSource.DoesNotExist:
            tsl_data_source = None

        if tsl_data_source:  # Build a cached list of YSO keywords
            cat_id_set = set()
            for tsl_val in TURKU_LUOKITUS_KEYWORD_IDS.values():
                if isinstance(tsl_val, tuple):
                    for t_v in tsl_val:
                        cat_id_set.add(t_v)
                else:
                    cat_id_set.add(tsl_val)
            KEYW_LIST = Keyword.objects.filter(data_source=tsl_data_source).\
                filter(id__in=cat_id_set)
            self.tsl_by_id = {p.id: p for p in KEYW_LIST}
        else:
            self.tsl_by_id = {}

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

    def get_or_empty(self, item, collection) -> list:
        item = collection.get(item, None)
        if item:
            return item.split(',')
        return []

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

        # if not bool(int(eventTku['is_hobby'])):

        eid = int(eventTku['drupal_nid'])
        evItem = events[eid]
        evItem['id'] = '%s:%s' % (self.data_source.id, eid)
        evItem['origin_id'] = eid
        evItem['data_source'] = self.data_source
        evItem['publisher'] = self.organization
        evItem['end_time'] = end_time

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

        location_extra_info_formatted = '%(address)s / %(extra)s' % {
            'address': eventTku['address'], 'extra': location_extra_info} if location_extra_info else eventTku['address']
        # Define location_extra_info dict.
        evItem['location_extra_info'] = {
            "fi": location_extra_info_formatted,
            "sv": location_extra_info_formatted,
            "en": location_extra_info_formatted
        }

        if eventTku['event_image_ext_url']:
            if int(eventTku['event_image_license']) == 1 and event_type in ('m', 's'):
                # Saves an image from the URL onto our server & database Image table.
                # We only want mother event images and single event images.

                IMAGE_TYPE = 'jpg'
                PATH_EXTEND = 'images'

                def request_image_url():
                    img = requests.get(eventTku['event_image_ext_url']['src'],
                                       headers={'User-Agent': 'Mozilla/5.0'}).content
                    imgfile = eventTku['drupal_nid']
                    path = '%(root)s/%(pathext)s/%(img)s.%(type)s' % ({
                        'root': settings.MEDIA_ROOT,
                        'pathext': PATH_EXTEND,
                        'img': imgfile,
                        'type': IMAGE_TYPE
                    })
                    with open(path, 'wb') as file:
                        file.write(img)
                    return '%s/%s.%s' % (PATH_EXTEND, imgfile, IMAGE_TYPE)

                self.image_obj, _ = Image.objects.update_or_create(
                    defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                        license=self.cc_by_license,
                        data_source=self.data_source,
                        publisher=self.organization,
                        image=request_image_url()))

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


        event_categories = self.get_or_empty('event_categories', eventTku)
        keywords = self.get_or_empty('keywords', eventTku)
        target_audience = self.get_or_empty('target_audience', eventTku)

        for name in map(str.strip, event_categories):
            if name == 'Theatre and other perfomance art':
                name = 'Theatre and other performance art'
                # Theatre and other performance art is spelled incorrectly in the JSON. "Perfomance".
            if name == 'Virtual events':
                evItem['location']['id'] = VIRTUAL_LOCATION_ID

            ysoId = TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID.get(name, None)
            if ysoId:
                if isinstance(ysoId, list):
                    for x in range(len(ysoId)):
                        event_keywords.add(
                            Keyword.objects.get(id=ysoId[x])
                        )
                    continue
                try:
                    event_keywords.add(
                        Keyword.objects.get(id=ysoId)
                    )
                except Keyword.DoesNotExist:
                    continue

        for name in map(str.strip, keywords):
            if not TURKU_DRUPAL_CATEGORY_EN_YSOID.get(name):
                try:
                    event_keywords.add(
                        Keyword.objects.get(name=name)
                    )
                except Keyword.DoesNotExist:
                    if name:
                        notFoundKeys.append({
                            name: eventTku['drupal_nid']
                        })

        for name in map(str.strip, target_audience):
            ysoId = TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID.get(name, None)
            if ysoId:
                event_audience.add(
                    Keyword.objects.get(id=ysoId)
                )

        evItem['keywords'] = event_keywords
        evItem['audience'] = event_audience

        evItem['info_url'] = {
            "fi": eventTku['website_url'],
            "sv": eventTku['website_url'],
            "en": eventTku['website_url']
        }

        if event_type in ('m', 's'):
            # Add a default offer
            offer = {
                'is_free': bool(int(eventTku.get('free_event', True))),
                'price': None,
                'description': None,
                'info_url': None,
            }
            # Fill if events is not free price event
            if not offer['is_free']:
                event_price = eventTku.get('event_price', '')
                buy_tickets_url = eventTku.get('buy_tickets_url', '')
                if event_price:
                    price = bleach.clean(event_price, tags=SAFE_TAGS, strip=True)
                    offer['description'] = {'fi': clean_text(price, True)}
                if buy_tickets_url:
                    offer['info_url'] = {'fi': buy_tickets_url}
            evItem['offers'] = [offer]

        if event_type == "m":
            evItem['super_event_type'] = Event.SuperEventType.RECURRING
        if event_type == "c" or event_type == "s":
            evItem['super_event_type'] = None

        evItem['is_hobby'] = eventTku['is_hobby']

        return evItem

    def _recur_fetch_paginated_url(self, url, lang, events):
        max_tries = 10
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

        def to_import(lang, ev, events, ev_type):
            self._import_event(lang, ev, events, ev_type)

        # Import Single Event(s).
        for x in jsr:
            for _, v in x.items():
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
        return root_doc, mothers_with_children, mothers_children

    def save_extra(self, drupal_url, mothersList, childList):

        for json_mother_event in drupal_url['events']:
            json_event = json_mother_event['event']

            try:
                # Updating the existing DB events that need is_hobby.
                eventToUpdate = Event.objects.get(
                    origin_id=json_event['drupal_nid'])
                if int(json_event['is_hobby']) == 1:
                    eventToUpdate.type_id = 4
                else:
                    eventToUpdate.type_id = 1

                eventToUpdate.save()
            except:
                pass

            if json_event.get('drupal_nid', None):
                for json_child in childList:
                    if json_event['drupal_nid'] != json_child['drupal_nid_super']:
                        continue

                    try:
                        child = Event.objects.get(
                            origin_id=json_child['drupal_nid'])
                        mother = Event.objects.get(
                            origin_id=json_event['drupal_nid'])
                    except Event.DoesNotExist:
                        continue

                    #sub_recurring, sub_umbrella
                    sub_event_type = f'sub_{mother.super_event_type}' \
                        if mother.super_event_type in ('recurring', 'umbrella') else None

                    child, _ = Event.objects.update_or_create(
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
                            'super_event': mother,
                            'sub_event_type': sub_event_type,
                        }
                    )

                    # Get object from Offer once we have the Event object.
                    try:
                        motherOffer = Offer.objects.get(
                            event_id=mother.id)
                    except Offer.DoesNotExist:
                        continue

                    offer, _ = Offer.objects.update_or_create(
                        event_id=child.id,
                        info_url=motherOffer.info_url,
                        is_free=motherOffer.is_free,
                    )
                    for lang, value in get_field_translations(motherOffer, 'price'):
                        description = getattr(motherOffer, 'description_%s' % lang, '') \
                            if lang else getattr(motherOffer, 'description', '')
                        field = 'description_%s' % lang if lang else 'description'
                        setattr(offer, field, '{value}{nl}{description}'.format(
                            value=value or '',
                            description=description or '',
                            nl='\n' if value else ''
                        ))
                    offer.save()

            def fb_tw(ft):
                originid = json_event['drupal_nid']
                # Get Language object.
                try:
                    myLang = Language.objects.get(id="fi")
                    eventObj = Event.objects.get(origin_id=originid)
                except (Language.DoesNotExist, Event.DoesNotExist):
                    return

                EventLink.objects.update_or_create(
                    name=f'extlink_{ft}',
                    event_id=eventObj.id,
                    language_id=myLang.id,
                    link=json_event.get(f'{ft}_url', '')
                )

            if json_event['facebook_url']:
                fb_tw('facebook')
            if json_event['twitter_url']:
                fb_tw('twitter')

            # Match Events & Images together in the ManyToMany relationship table.
            def _fetch_from_image_table(p, p2, raise_exception=True):
                try:
                    img = Image.objects.get(image=f'images/{json_event[p2]}.jpg')
                    event_obj = Event.objects.get(origin_id=json_event[p])
                except (Image.DoesNotExist, Event.DoesNotExist):
                    if not raise_exception:
                        return None
                    raise
                event_obj.images.add(img)

            # Match Events & Images together in the ManyToMany relationship table.      
            try:
                _fetch_from_image_table('drupal_nid', 'drupal_nid')
            except (Image.DoesNotExist, Event.DoesNotExist):
                _fetch_from_image_table('drupal_nid', 'drupal_nid_super', raise_exception=False)

    def import_events(self):
        events = recur_dict()
        URL = 'https://kalenteri.turku.fi/admin/event-exports/json_beta'
        lang = self.supported_languages
        # Fetch JSON for post-processing but also process & import events.
        try:
            RESPONSE_JSON, mother_events, child_events = self._recur_fetch_paginated_url(
                URL, lang, events)
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
