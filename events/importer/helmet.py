# -*- coding: utf-8 -*-

import requests
import requests_cache
import re
import dateutil.parser
from datetime import datetime, timedelta
import time
from django.utils.html import strip_tags
from .base import Importer, register_importer, recur_dict
from events.models import Event, Keyword, DataSource, Organization, Place
from pytz import timezone
import pytz
import bleach

from .sync import ModelSyncher

YSO_BASE_URL = 'http://www.yso.fi/onto/yso/'
YSO_KEYWORD_MAPS = {
    u'Yrittäjät': u'p1178',
    u'Lapset': u'p4354',
    u'Kirjastot': u'p2787',
    u'Opiskelijat': u'p16486',
    u'Konsertit ja klubit': (u'p11185', u'p20421'),  # -> konsertit, musiikkiklubit
    u'Kurssit': u'p9270',
    u'venäjä': u'p7643',  # -> venäjän kieli
    u'Seniorit': u'p2434',  # -> vanhukset
    u'Näyttelyt': u'p5121',
    u'Toivoa kirjallisuudesta': u'p8113',  # -> kirjallisuus
    u'Suomi 100': u'p29385',  # -> Suomi 100 vuotta -juhlavuosi
    u'Kirjallisuus': u'p8113',
    u'Kielikahvilat ja keskusteluryhmät': (u'p18105', u'p556'),  # -> keskusteluryhmät
    u'Maahanmuuttajat': u'p6165',
    u'Opastukset ja kurssit': (u'p2149', u'p9270'),  # -> opastus, kurssit
    u'Nuoret': u'p11617',
    u'Pelitapahtumat': u'p6062',  # -> pelit
    u'Satutunnit': u'p14710',
    u'Koululaiset': u'p16485',
    u'Lasten ja nuorten tapahtumat': (u'p4354', u'p11617'),  # -> lapset, nuoret
    u'Lapset ja perheet': (u'p4354', u'p4363'),  # -> lapset, perheet
    u'Lukupiirit': u'p11406',  # -> lukeminen
    u'Musiikki': u'p1808',  # -> musiikki
    u'muut kielet': u'p556',  # -> kielet
}

LOCATIONS = {
    # Library name in Finnish -> ((library node ids in event feed), tprek id)
    u"Arabianrannan kirjasto": ((10784, 11271), 8254),
    u"Entressen kirjasto": ((10659, 11274), 15321),
    u"Etelä-Haagan kirjasto": ((10786, 11276), 8150),
    u"Hakunilan kirjasto": ((10787, 11278), 19580),
    u"Haukilahden kirjasto": ((10788, 11280), 19580),
    u"Herttoniemen kirjasto": ((10789, 11282), 8325),
    u"Hiekkaharjun kirjasto": ((10790, 11284), 18584),
    u"Itäkeskuksen kirjasto": ((10791, 11286), 8184),
    u"Jakomäen kirjasto": ((10792, 11288), 8324),
    u"Jätkäsaaren kirjasto": ((11858,), 45317),
    u"Kalajärven kirjasto": ((10793, 11290), 15365),
    u"Kallion kirjasto": ((10794, 11291), 8215),
    u"Kannelmäen kirjasto": ((10795, 11294), 8141),
    u"Karhusuon kirjasto": ((10796, 11296), 15422),
    u"Kauklahden kirjasto": ((10798, 11298), 15317),
    u"Kauniaisten kirjasto": ((10799, 11301), 14432),
    u"Kirjasto 10": ((10800, 11303), 8286),
    u"Kirjasto Omena": ((10801, 11305), 15395),
    u"Kivenlahden kirjasto": ((10803, 11309), 15334),
    u"Kaupunkiverstas": ((10804, 11311), 8145),  # former Kohtaamispaikka
    u"Koivukylän kirjasto": ((10805, 11313), 19572),
    u"Kontulan kirjasto u": ((10806, 11315), 8178),
    u"Kotipalvelu": ((10811, 11317), 8285),
    u"Käpylän kirjasto": ((10812, 11319), 8302),
    u"Laajalahden kirjasto": ((10813, 11321), 15344),
    u"Laajasalon kirjasto": ((10814, 11323), 8143),
    u"Laaksolahden kirjasto": ((10815, 11325), 15309),
    u"Lauttasaaren kirjasto": ((10817, 11329), 8344),
    u"Lumon kirjasto": ((10818, 11331), 18262),
    u"Länsimäen kirjasto": ((10819, 11333), 18620),
    u"Malmin kirjasto": ((10820, 11335), 8192),
    u"Malminkartanon kirjasto": ((10821, 11337), 8220),
    u"Martinlaakson kirjasto": ((10822, 11339), 19217),
    u"Maunulan kirjasto": ((10823, 11341), 8350),
    u"Monikielinen kirjasto": ((10824, 11345), 8223),
    u"Munkkiniemen kirjasto": ((10825, 11347), 8158),
    u"Myllypuron mediakirjasto": ((10826, 11349), 8348),
    u"Myyrmäen kirjasto": ((10827, 11351), 18241),
    u"Nöykkiön kirjasto": ((10828, 11353), 15396),
    u"Oulunkylän kirjasto": ((10829, 11355), 8177),
    u"Paloheinän kirjasto": ((10830, 11357), 8362),
    u"Pasilan kirjasto": ((10831, 11359), 8269),
    u"Pikku Huopalahden lastenkirjasto": ((10832, 11361), 8294),
    u"Pitäjänmäen kirjasto": ((10833, 11363), 8292),
    u"Pohjois-Haagan kirjasto": ((10834, 11365), 8205),
    u"Pointin kirjasto": ((10835, 11367), 18658),
    u"Puistolan kirjasto": ((10837, 11369), 8289),
    u"Pukinmäen kirjasto": ((10838, 11371), 8232),
    u"Pähkinärinteen kirjasto": ((10839, 11373), 18855),
    u"Rikhardinkadun kirjasto": ((10840, 11375), 8154),
    u"Roihuvuoren kirjasto": ((10841, 11377), 8369),
    u"Ruoholahden lastenkirjasto": ((10842, 11379), 8146),
    u"Sakarinmäen lastenkirjasto": ((10843, 11381), 10037),
    u"Saunalahden kirjasto": ((11712, 11714), 29805),
    u"Sellon kirjasto": ((10844, 11383), 15417),
    u"Soukan kirjasto": ((10845, 11385), 15376),
    u"Suomenlinnan kirjasto": ((10846, 11387), 8244),
    u"Suutarilan kirjasto": ((10847, 11389), 8277),
    u"Tapanilan kirjasto": ((10848, 11391), 8359),
    u"Tapiolan kirjasto": ((10849, 11395), 15311),
    u"Tapulikaupungin kirjasto": ((10850, 11397), 8288),
    u"Tikkurilan kirjasto": ((10851, 11202), 18703),
    u"Töölön kirjasto": ((10852, 11393), 8149),
    u"Vallilan kirjasto": ((10853, 11399), 8199),
    u"Viherlaakson kirjasto": ((10854, 11401), 15429),
    u"Viikin kirjasto": ((10855, 11403), 8308),
    u"Vuosaaren kirjasto": ((10856, 11405), 8310),
}

HELMET_BASE_URL = 'https://www.helmet.fi'
HELMET_API_URL = (
    HELMET_BASE_URL + '/api/opennc/v1/ContentLanguages({lang_code})'
    '/Contents?$filter=TemplateId eq 3&$expand=ExtendedProperties,LanguageVersions'
    '&$orderby=EventEndDate desc&$format=json'
)

HELMET_LANGUAGES = {
    'fi': 1,
    'sv': 3,
    'en': 2
}


def get_lang(lang_id):
    for code, lid in HELMET_LANGUAGES.items():
        if lid == lang_id:
            return code
    return None


LOCAL_TZ = timezone('Europe/Helsinki')


def clean_text(text, strip_newlines=False):
    text = text.replace('\xa0', ' ').replace('\x1f', '')
    if strip_newlines:
        text = text.replace('\r', '').replace('\n', ' ')
    # remove consecutive whitespaces
    return re.sub(r'\s\s+', ' ', text, re.U).strip()


def mark_deleted(obj):
    if obj.deleted:
        return False
    obj.deleted = True
    obj.save(update_fields=['deleted'])
    return True


class APIBrokenError(Exception):
    pass


@register_importer
class HelmetImporter(Importer):
    name = "helmet"
    supported_languages = ['fi', 'sv', 'en']
    current_tick_index = 0
    kwcache = {}

    def setup(self):
        ds_args = dict(id=self.name)
        defaults = dict(name='HelMet-kirjastot')
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args)
        self.tprek_data_source = DataSource.objects.get(id='tprek')
        self.ahjo_data_source = DataSource.objects.get(id='ahjo')

        org_args = dict(id='ahjo:45400')
        defaults = dict(name='Helsingin kaupunginkirjasto', data_source=self.ahjo_data_source)
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        # Build a cached list of Places
        loc_id_list = [l[1] for l in LOCATIONS.values()]
        place_list = Place.objects.filter(
            data_source=self.tprek_data_source
        ).filter(origin_id__in=loc_id_list)
        self.tprek_by_id = {p.origin_id: p.id for p in place_list}

        try:
            yso_data_source = DataSource.objects.get(id='yso')
        except DataSource.DoesNotExist:
            yso_data_source = None

        if yso_data_source:
            # Build a cached list of YSO keywords
            cat_id_set = set()
            for yso_val in YSO_KEYWORD_MAPS.values():
                if isinstance(yso_val, tuple):
                    for t_v in yso_val:
                        cat_id_set.add('yso:' + t_v)
                else:
                    cat_id_set.add('yso:' + yso_val)

            keyword_list = Keyword.objects.filter(data_source=yso_data_source).\
                filter(id__in=cat_id_set)
            self.yso_by_id = {p.id: p for p in keyword_list}
        else:
            self.yso_by_id = {}

        if self.options['cached']:
            requests_cache.install_cache('helmet')
            self.cache = requests_cache.get_cache()
        else:
            self.cache = None

    @staticmethod
    def _get_extended_properties(event_el):
        ext_props = recur_dict()
        for prop in event_el['ExtendedProperties']:
            for data_type in ('Text', 'Number', 'Date'):
                if prop[data_type]:
                    ext_props[prop['Name']] = prop[data_type]
                    continue
        return ext_props

    def _import_event(self, lang, event_el, events):
        def dt_parse(dt_str):
            """Convert a string to UTC datetime"""
            # Times are in UTC+02:00 timezone
            return LOCAL_TZ.localize(
                    dateutil.parser.parse(dt_str),
                    is_dst=None).astimezone(pytz.utc)

        start_time = dt_parse(event_el['EventStartDate'])
        end_time = dt_parse(event_el['EventEndDate'])

        # Import only at most one month old events
        if end_time < datetime.now().replace(tzinfo=LOCAL_TZ) - timedelta(days=31):
            return {'start_time': start_time, 'end_time': end_time}

        eid = int(event_el['ContentId'])
        event = None
        if lang != 'fi':
            fi_ver_ids = [int(x['ContentId']) for x in event_el['LanguageVersions'] if x['LanguageId'] == 1]
            fi_event = None
            for fi_id in fi_ver_ids:
                if fi_id not in events:
                    continue
                fi_event = events[fi_id]
                if fi_event['start_time'] != start_time or fi_event['end_time'] != end_time:
                    continue
                event = fi_event
                break

        if not event:
            event = events[eid]
            event['id'] = '%s:%s' % (self.data_source.id, eid)
            event['origin_id'] = eid
            event['data_source'] = self.data_source
            event['publisher'] = self.organization

        ext_props = HelmetImporter._get_extended_properties(event_el)

        if 'Name' in ext_props:
            event['name'][lang] = clean_text(ext_props['Name'], True)
            del ext_props['Name']

        if ext_props.get('Description', ''):
            desc = ext_props['Description']
            ok_tags = ('u', 'b', 'h2', 'h3', 'em', 'ul', 'li', 'strong', 'br', 'p', 'a')
            desc = bleach.clean(desc, tags=ok_tags, strip=True)

            event['description'][lang] = clean_text(desc)
            del ext_props['Description']

        if ext_props.get('LiftContent', ''):
            text = ext_props['LiftContent']
            text = clean_text(strip_tags(text))
            event['short_description'][lang] = text
            del ext_props['LiftContent']

        if 'Images' in ext_props:
            matches = re.findall(r'src="(.*?)"', str(ext_props['Images']))
            if matches:
                img_url = matches[0]
                event['image'] = HELMET_BASE_URL + img_url
            del ext_props['Images']

        event['url'][lang] = '%s/api/opennc/v1/Contents(%s)' % (
            HELMET_BASE_URL, eid
        )

        def set_attr(field_name, val):
            if field_name in event:
                if event[field_name] != val:
                    self.logger.warning('Event %s: %s mismatch (%s vs. %s)' %
                                        (eid, field_name, event[field_name], val))
                    return
            event[field_name] = val

        if 'date_published' not in event:
            # Publication date changed based on language version, so we make sure
            # to save it only from the primary event.
            event['date_published'] = dt_parse(event_el['PublicDate'])

        set_attr('start_time', dt_parse(event_el['EventStartDate']))
        set_attr('end_time', dt_parse(event_el['EventEndDate']))

        event_keywords = event.get('keywords', set())

        for classification in event_el['Classifications']:
            # Save original keyword in the raw too
            node_id = classification['NodeId']
            name = classification['NodeName']
            node_type = classification['Type']
            # Tapahtumat exists tens of times, use pseudo id
            if name in ('Tapahtumat', 'Events', 'Evenemang'):
                node_id = 1  # pseudo id
            keyword_id = 'helmet:{}'.format(node_id)
            kwargs = {
                'id': keyword_id,
                'origin_id': node_id,
                'data_source_id': 'helmet',
            }
            if keyword_id in self.kwcache:
                keyword_orig = self.kwcache[keyword_id]
                created = False
            else:
                keyword_orig, created = Keyword.objects.get_or_create(**kwargs)
                self.kwcache[keyword_id] = keyword_orig

            name_key = 'name_{}'.format(lang)
            if created:
                keyword_orig.name = name  # Assume default lang Finnish
                # Set explicitly modeltranslation field
                setattr(keyword_orig, name_key, name)
                keyword_orig.save()
            else:
                current_name = getattr(keyword_orig, name_key)
                if not current_name:  # is None or empty
                    setattr(keyword_orig, name_key, name)
                    keyword_orig.save()

            if keyword_orig.publisher_id != self.organization.id:
                keyword_orig.publisher = self.organization
                keyword_orig.save()

            event_keywords.add(keyword_orig)
            # Saving original keyword ends

            # One of the type 7 nodes (either Tapahtumat, or just the library name)
            # points to the location, which is mapped to Linked Events keyword ID
            if node_type == 7:
                if 'location' not in event:
                    for k, v in LOCATIONS.items():
                        if classification['NodeId'] in v[0]:
                            event['location']['id'] = self.tprek_by_id[str(v[1])]
                            break
            else:
                if not self.yso_by_id:
                    continue
                # Map some classifications to YSO based keywords
                if str(classification['NodeName']) in YSO_KEYWORD_MAPS.keys():
                    yso = YSO_KEYWORD_MAPS[str(classification['NodeName'])]
                    if isinstance(yso, tuple):
                        for t_v in yso:
                            event_keywords.add(self.yso_by_id['yso:' + t_v])

                    else:
                        event_keywords.add(self.yso_by_id['yso:' + yso])

        event['keywords'] = event_keywords

        if 'location' in event:
            extra_info = clean_text(ext_props.get('PlaceExtraInfo', ''))
            if extra_info:
                event['location']['extra_info'][lang] = extra_info
                del ext_props['PlaceExtraInfo']
        else:
            self.logger.warning('Missing TPREK location map for event %s (%s)' %
                                (event['name'][lang], str(eid)))
            del events[event['origin_id']]
            return event

        # Custom stuff not in our data model, what we actually need?
        for p_k, p_v in ext_props.items():
            event['custom_fields'][p_k] = p_v
        # custom_fields only accepts strings
        event['custom_fields']['ExpiryDate'] = dt_parse(
            event_el['ExpiryDate']).strftime("%Y-%m-%dT%H:%M:%SZ")

        return event

    def _recur_fetch_paginated_url(self, url, lang, events):
        for _ in range(0, 5):
            response = requests.get(url)
            if response.status_code != 200:
                self.logger.error("HelMet API reported HTTP %d" % response.status_code)
                time.sleep(2)
                if self.cache:
                    self.cache.delete_url(url)
                continue
            try:
                root_doc = response.json()
            except ValueError:
                self.logger.error("HelMet API returned invalid JSON")
                if self.cache:
                    self.cache.delete_url(url)
                time.sleep(5)
                continue
            break
        else:
            self.logger.error("HelMet API broken again, giving up")
            raise APIBrokenError()

        documents = root_doc['value']
        earliest_end_time = None
        for doc in documents:
            event = self._import_event(lang, doc, events)
            if not earliest_end_time or event['end_time'] < earliest_end_time:
                earliest_end_time = event['end_time']

        now = datetime.now().replace(tzinfo=LOCAL_TZ)
        # We check 31 days backwards.
        if earliest_end_time < now - timedelta(days=31):
            return

        if 'odata.nextLink' in root_doc:
            self._recur_fetch_paginated_url(
                '%s/api/opennc/v1/%s%s' % (
                    HELMET_BASE_URL,
                    root_doc['odata.nextLink'],
                    "&$format=json"
                ), lang, events)

    def import_events(self):
        print("Importing HelMet events")
        events = recur_dict()
        for lang in self.supported_languages:
            helmet_lang_id = HELMET_LANGUAGES[lang]
            url = HELMET_API_URL.format(lang_code=helmet_lang_id, start_date='2016-01-01')
            print("Processing lang " + lang)
            print("from URL " + url)
            try:
                self._recur_fetch_paginated_url(url, lang, events)
            except APIBrokenError:
                return

        event_list = sorted(events.values(), key=lambda x: x['end_time'])
        qs = Event.objects.filter(end_time__gte=datetime.now(),
                                  data_source='helmet', deleted=False)

        self.syncher = ModelSyncher(qs, lambda obj: obj.origin_id, delete_func=mark_deleted)

        for event in event_list:
            obj = self.save_event(event)
            self.syncher.mark(obj)

        self.syncher.finish()
        print("%d events processed" % len(events.values()))
