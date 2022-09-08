# -*- coding: utf-8 -*-
import logging

import pytz
from datetime import datetime, timedelta
from django import db
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.core.management import call_command
from django_orghierarchy.models import Organization
from django.utils import timezone as django_timezone
from pytz import timezone
import bleach
import base64

from events.importer.util import replace_location
from events.models import (
    DataSource,
    Event,
    Keyword,
    Place,
    License
)
from .sync import ModelSyncher
from .base import Importer, register_importer
from .util import clean_text
from events.importer.helper.importers import vapaaehtoistyofi

# Per module logger
logger = logging.getLogger(__name__)


@register_importer
class VapaaehtoistyofiImporter(Importer):
    importer_id = 'vapaaehtoistyofi'
    name = 'vapaaehtoistyö.fi'
    supported_languages = ['fi', 'sv', 'en']
    ok_tags = ['u', 'b', 'h2', 'h3', 'em', 'ul', 'li', 'strong', 'br', 'p', 'a']
    DEFAULT_DURATION_DAYS = 90
    LOCAL_TZ = timezone('Europe/Helsinki')
    UTC_TZ = timezone('UTC')

    VET_KEYWORD_ID = "p3050"
    KEYWORDS = {
        "": VET_KEYWORD_ID,  # https://finto.fi/yso/fi/page/p3050
        "67b79307eeb3170e4a73de97d7db25c1019969c0": "p4785",  # Järjestötoiminta
        "ee1522536826c4245203c832893bb710ecf26967": ["p4354", "p11617", "p4363"],  # Lapset, nuoret ja perheet
        "ba1a23bf86b46b59c31eda2a64871b516d31c6d7": "p26028",  # Ystävä- ja kaveritoiminta
        "21a2dd8eb252b77696873c225dc404e92d49a88b": "p2573",  # Also for English speakers
        "8b51c2d692707464b31d04954b843cbb808ea356": "p2433",  # Ikäihmiset
        "9d3f2f277cce1c52334409e42c957eabfce33095": ["p965", "p916", "p2771"],  # Urheilu, liikunta ja ulkoilu
        "33a38af4e473ea1de6cbfd227e512570d88d2425": "p4400",  # Sopii alle 18-vuotiaille
        "5eb6379a96c3b01b4126cfc9fc862a7d50b55aa9": "p22112",  # Maahanmuuttajat
        "655171ca3998761dac17d195b24b67890f3f58b3": "p10801",  # Etätyö puhelimitse tai verkossa
        "1cd7fe40093fe69631be00e07efac3cb1109bb8e": "p229",  # Seurakuntatoiminta
        "73a7a8af91c9375921ff8b6f96e2ccb3de620869": ["p8660", "p11", "p2023"],  # Ympäristö, luonnonsuojelu ja eläimet
        "83ac738e5bdaae0de9ce6a03375e78c993c87595": ["p2108", "p6904"],  # Tapahtumat ja talkoot
        "7aad71eb0bc6ad2a4a1b5bdfe5c9e99a5046892f": ["p7179", "p17354"],  # Vammaiset ja muut erityisryhmät
        "c359cf2be5277f1cab72c9f487bd11df5a6f7758": ["p6206", "p7913"],  # Päihde- ja mielenterveystyö
        "f8a74c0d3582666e58423cb34746189a5b3b4043": [
            "p10190", "p15322", "p20819"
        ],  # Päivystys, ensiapu, pelastus ja kriisityö
        "fa68d1dded69d8cb764c5d3a18449ae90cf10210": ["p1808", "p2851", "p4923"],  # Musiikki, taide ja käsityöt
        "f1d1b5fb6c50e5fadee65b85cae945ea891c9e1d": "p38829",  # Korona
    }

    def setup(self):
        ds_args = dict(id=self.importer_id)
        defaults = dict(name='Vapaaehtoistyö.fi')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(origin_id='u021600', data_source=self.data_source)
        defaults = dict(name='Vapaaehtoistyö.fi')
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        self.vetf_source = vapaaehtoistyofi.Reader(settings.VAPAAEHTOISTYOFI_API_KEY)

        try:
            self.event_only_license = License.objects.get(id='event_only')
        except License.DoesNotExist:
            self.event_only_license = None

    def pk_get(self, resource_name, res_id=None):
        logger.debug("pk_get(%s, %s)" % (resource_name, res_id))
        record = self.vetf_source.load_entry(res_id)

        return record

    def delete_and_replace(self, obj):
        obj.deleted = True
        obj.save(update_fields=['deleted'])
        # we won't stand idly by and watch Vapaaehtoistyö.fi delete needed units willy-nilly without raising a ruckus!
        if obj.events.count() > 0:
            # try to replace by Vapaaehtoistyö.fi and, failing that, matko
            replaced = replace_location(replace=obj, by_source=self.importer_id)
            if not replaced:
                # matko location may indeed be deleted by an earlier iteration
                replaced = replace_location(replace=obj, by_source='matko', include_deleted=True)
            if not replaced:
                # matko location may never have been imported in the first place, do it now!
                call_command('event_import', 'matko', places=True, single=obj.name)
                replaced = replace_location(replace=obj, by_source='matko')
            if not replaced:
                logger.warning("Vapaaehtoistyö.fi deleted location %s (%s) with events."
                               "No unambiguous replacement was found. "
                               "Please look for a replacement location and save it in the replaced_by field. "
                               "Until then, events will stay mapped to the deleted location." %
                               (obj.id, str(obj)))
        return True

    def mark_deleted(self, obj):
        if obj.deleted:
            return False
        return self.delete_and_replace(obj)

    def check_deleted(self, obj):
        return obj.deleted

    def _import_event(self, event_obj):
        event = dict(event_obj.__dict__)
        logger.debug("Task id %s" % event_obj.id)
        event['id'] = '%s:%s' % (self.data_source.id, event_obj.id)
        event['origin_id'] = event_obj.id
        event['data_source'] = self.data_source
        event['publisher'] = self.organization
        event['headline'] = {}
        event['description'] = {}

        title = bleach.clean(event_obj.title, tags=[], strip=True)
        # long description is html formatted, so we don't want plain text whitespaces
        title = clean_text(title, True)
        Importer._set_multiscript_field(title, event, event_obj.LOCALE, 'headline')

        desc = bleach.clean(event_obj.description, tags=self.ok_tags, strip=True)
        # long description is html formatted, so we don't want plain text whitespaces
        desc = clean_text(desc, True)
        Importer._set_multiscript_field(desc, event, event_obj.LOCALE, 'description')

        now = datetime.now(pytz.UTC)
        # Import only at most one month old events
        cut_off_date = now - timedelta(days=31)
        cut_off_date.replace(tzinfo=pytz.UTC)
        end_date = event_obj.timestamp_end.replace(tzinfo=pytz.UTC)
        if end_date < cut_off_date:
            logger.debug("Skipping task %s. Has ended %s" % (event_obj.id, end_date))
            return None

        event['start_time'] = django_timezone.make_aware(event_obj.timestamp_start, pytz.UTC)
        event['end_time'] = end_date

        # Note: In Vapaaehtoistyö.fi tasks do not contain language information
        lang = 'fi'
        event['info_url'] = {}
        event['external_links'] = {}
        event['info_url'][lang] = event_obj.get_url_locale(lang)
        event['external_links'][lang] = {}

        event['images'] = self._import_photo(event_obj)
        event['keywords'] = self._import_keywords(event_obj)
        event['location'] = self._import_location(event_obj)

        if not event['location']:
            # Skip events not located in Greater Helsinki area
            return None

        return event

    def _import_photo(self, event_obj):
        # Note: Photo is returned as data, not as an URL.
        # Note 2: There is nowhere we can store the data!
        mime_type, photo_bytes = self.vetf_source.load_photo(event_obj.id)
        if False and photo_bytes:
            image_url = "data:%s;base64,%s" % (mime_type, base64.b64encode(photo_bytes))
            return [{
                'url': image_url,
                'license': self.event_only_license,
            }]

        return []

    def _import_keywords(self, event_obj):
        event_keywords = []

        try:
            kw = Keyword.objects.get(id="yso:%s" % self.VET_KEYWORD_ID)
        except Keyword.DoesNotExist:
            kw = None
        if not kw:
            raise RuntimeError("Fata: Cannot import Vapaaehtoistyö.fi! Missing YSO:%s keyword." % self.VET_KEYWORD_ID)

        event_keywords.append(kw)
        for tag_dict in event_obj.tags:
            tag_id = list(tag_dict.keys())[0]
            if tag_id in self.KEYWORDS:
                keyword_value = self.KEYWORDS[tag_id]
                if isinstance(keyword_value, str):
                    keyword_value = [keyword_value]
                for keyword in keyword_value:
                    yso_id = "yso:%s" % keyword
                    # logger.debug("Keyword query for: %s" % yso_id)
                    try:
                        kw = Keyword.objects.get(id=yso_id)
                    except Keyword.DoesNotExist:
                        logger.warning("Task %s has keyword %s, which maps into a non-existent %s" % (
                            event_obj.id, tag_id, yso_id))
                        kw = None
                    if kw:
                        event_keywords.append(kw)
        logger.debug("Task %s: Got keywords: %s" % (event_obj.id, ', '.join([o.id for o in event_keywords])))

        return event_keywords

    def _import_location(self, event_obj):
        # DEBUG: Logging of all queries
        # logging.getLogger('django.db.backends').setLevel(logging.DEBUG)
        # Note: Vapaaehtoistyö.fi will return "standard" WGS 84 latitude/longtitude.
        # Note 2: WGS 84 == EPSG:4326
        # Note 3: In events_place table data is stored as EPSG:3067 (aka. ETRS89 / TM35FIN(E,N))
        #         See: https://epsg.io/3067
        # Note 4: PostGIS will do automatic translation from WGS 84 into EPSG:3067.
        #         For manual EPSG translations, see: https://epsg.io/transform
        ref_location = Point(event_obj.address_coordinates['lon'],
                             event_obj.address_coordinates['lat'],
                             srid=4326)
        # Query for anything within 100 meters
        # Note: flake8 doesn't allow this to be formatted in a readable way :-(
        places = Place.objects.filter(
            position__dwithin=(ref_location, 100.0)).filter(
            data_source_id='osoite').annotate(
            distance=Distance(
                "position", ref_location)).order_by(
            "distance")[:3]
        if not places:
            logger.warning("Failed to find any locations for task id %s!" % event_obj.id)
            return False

        logger.debug("Got %d places, picking %s" % (len(places), places[0].id))
        # for obj in places:
        #    logger.debug("%s: %s, %f" % (obj.id, obj.name, obj.distance))

        return {'id': places[0].id}

    def import_events(self):
        # DEBUG: Create keywords into empty database
        if False:
            self._debug_create_keywords()

        logger.info("Importing Vapaaehtoistyö.fi events")
        cnt_entries, event_list = self.vetf_source.load_entries()

        qs = Event.objects.filter(end_time__gte=datetime.now(),
                                  data_source=self.importer_id, deleted=False)

        self.syncher = ModelSyncher(qs, lambda obj: obj.origin_id, delete_func=VapaaehtoistyofiImporter._mark_deleted)

        for event_obj in event_list:
            event = self._import_event(event_obj)
            if event:
                obj = self.save_event(event)
                self.syncher.mark(obj)

        self.syncher.finish(force=self.options['force'])
        logger.info("%d events processed" % len(event_list))

    @staticmethod
    def _mark_deleted(obj):
        if obj.deleted:
            return False
        obj.deleted = True
        obj.save(update_fields=['deleted'])

        return True

    @db.transaction.atomic()
    def _debug_create_keywords(self):
        logger.info('confirming keywords...')

        ds_args = {"id": 'yso'}
        defaults = {"name": 'yso'}
        self.data_source, created = DataSource.objects.get_or_create(defaults=defaults, **ds_args)
        if created:
            logger.info('created datasource for YSO')
        else:
            logger.info('datasource for YSO already exist')

        for new_keyword_ext_id in self.KEYWORDS:
            keyword_value = self.KEYWORDS[new_keyword_ext_id]
            if isinstance(keyword_value, str):
                keyword_value = [keyword_value]
            for keyword in keyword_value:
                yso_id = "yso:%s" % keyword
                keyword_set, created = Keyword.objects.update_or_create(
                    id=yso_id,
                    defaults={
                        'id': yso_id,
                        'name_fi': '',
                        'data_source_id': 'yso',
                    }
                )
                if created:
                    logger.info('created keyword %s' % (keyword))
                else:
                    logger.info('keyword %s already exist' % keyword)
        logger.info('confirming keywords...')
