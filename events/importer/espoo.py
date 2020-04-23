# -*- coding: utf-8 -*-
import re
import logging
import time
from datetime import datetime, timedelta

import requests

import bleach
import dateutil.parser
import pytz
import requests_cache
from django.utils.html import strip_tags
from events.models import (
    DataSource,
    Event,
    Keyword,
    Place
)
from django_orghierarchy.models import Organization
from pytz import timezone

from .base import Importer, recur_dict, register_importer
from .yso import KEYWORDS_TO_ADD_TO_AUDIENCE
from .sync import ModelSyncher
from .util import clean_text, clean_url

# Per module logger
logger = logging.getLogger(__name__)

# Maximum number of attempts to fetch the event from the API before giving up
MAX_RETRY = 5

YSO_BASE_URL = 'http://www.yso.fi/onto/yso/'
YSO_KEYWORD_MAPS = {
    u'koululaiset ja opiskelijat': (u'p16485', u'p16486'),
    u'yhdistykset ja seurat': u'p1393',  # both words seems to mean associations
    u'näyttelyt ja tapahtumat': (u'p5121', u'p2108'),
    u'nuoriso': u'p11617',
    u'koulutus, kurssit ja luennot': (u'p84', u'p9270', u'p15875'),
    u'stand up ja esittävä taide': (u'p9244', u'p2850'),
    u'nuorisotyö': u'p1925',
    u'ohjaus, neuvonta ja tuki': (u'p178', u'p23'),
    u'hyvinvointi ja terveys': (u'p38424', u'p2762'),  # -> hyvinvointi, terveys
    u'ilmastonmuutos': u'p5729',
    u'leirit, matkat ja retket': (u'p143', u'p366', u'p25261'),
    u'kerhot ja kurssit': (u'p7642', u'p9270'),
    u'internet': u'p20405',
    u'tapahtumat': u'p2108',
    u'asukastoiminta': u'p2250',
    u'rakentaminen': u'p3673',
    u'kaavoitus': u'p8268',
    u'laitteet ja työtilat': (u'p2442', u'p546'),  # -> Laitteet, työtilat
    u'museot': u'p4934',
    u'museot ja kuvataide': (u'p4934', u'p2739'),  # -> museot, kuvataide
    u'näyttelyt ja galleriat': (u'p5121', u'p6044'),  # -> Näyttelyt, galleriat
    u'musiikki': u'p1808',
    u'teatteri': u'p2625',
    u'kevyt liikenne': u'p4288',
    u'liikenne': u'p3466',
    u'tiet ja kadut': (u'p1210', u'p8317'),  # -> Tiet, kadut
    u'liikuntapalvelut': u'p9824',
    u'liikuntapaikat': u'p5871',
    u'luonto- ja ulkoilureitit': (u'p13084', u'p5350'),  # -> Luonto, ulkoilureitit
    u'uimahallit': u'p9415',
    u'ulkoilualueet': u'p4858',
    u'urheilu- ja liikuntajärjestöt': (u'p965', u'p2042'),  # -> Urheilu, liikuntajärjestöt
    u'virkistysalueet': u'p4058',
    u'bändit': u'p5072',
    u'nuorisotilat': u'p17790',
    u'aikuiskoulutus': u'p300',
    u'korkeakouluopetus': u'p1246',
    u'perusopetus': u'p19327',
    u'päivähoito (lapsille)': u'p3523',  # -> Päivähoito
    u'lapsille': u'p4354',  # lapset (ikäryhmät)
    u'elokuva': u'p16327',  # elokuva (taiteet)
    u'elokuvat': u'p16327',  # elokuva (taiteet)
    u'musiikki ja konsertit': (u'p1808', u'p11185'),  # Musiikki, konsertit
    u'liikunta, ulkoilu ja urheilu': (u'p916', u'p2771', u'p965'),
    u'liikuntalajit': u'p916',
    u'ohjattu liikunta': u'p916',
    u'harrastus- ja kerhotoiminta': (u'p2901', u'p7642', u'p8090'),  # Harrastus, Kerho, toiminta
    u'perheet': u'p4363',  # perheet (ryhmät)
    u'koko perheelle': u'p4363',
    u'yrittäjät ja yritykset': (u'p1178', u'p3128'),
    u'yrittäjät': u'p1178',
    u'lapset': u'p4354',
    u'kirjastot': u'p2787',
    u'opiskelijat': u'p16486',
    u'konsertit ja klubit': (u'p11185', u'p20421'),  # -> konsertit, musiikkiklubit
    u'kurssit': u'p9270',
    u'venäjä': u'p7643',  # -> venäjän kieli
    u'seniorit': u'p2433',  # -> vanhukset
    u'senioreille': u'p2433',  # -> vanhukset
    u'senioripalvelut': u'p2433',
    u'näyttelyt': u'p5121',
    u'kirjallisuus': u'p8113',
    u'kielikahvilat ja keskusteluryhmät': u'p18105',  # -> keskusteluryhmät
    u'maahanmuuttajat': u'p6165',
    u'opastukset ja kurssit': (u'p2149', u'p9270'),  # -> opastus, kurssit
    u'nuoret': u'p11617',
    u'pelitapahtumat': u'p6062',  # -> pelit
    u'satutunnit': u'p14710',
    u'koululaiset': u'p16485',
    u'lasten ja nuorten tapahtumat': (u'p4354', u'p11617'),  # -> lapset, nuoret
    u'lapset ja perheet': (u'p4354', u'p4363'),  # -> lapset, perheet
    u'lukupiirit': u'p11406',  # -> lukeminen
    u'asuminen ja ympäristö  ': (u'p1797', u'p6033'),  # -> asuminen, ympäristö # note the typo!
    u'ympäristö ja luonto': u'p13084',  # -> luonto
    u'tanssi ja voimistelu': (u'p1278', u'p963'),  # -> tanssi, voimistelu
    u'tanssi ja sirkus': (u'p1278', u'p5007'),  # -> tanssi, sirkus,
    u'sosiaali- ja terveyspalvelut': (u'p1307', u'p3307'),  # -> sosiaalipalvelut, terveyspalvelut
    u'terveys ja hyvinvointi': (u'p38424', u'p2762'),  # -> hyvinvointi, terveys
    u'asemakaava': u'p8268',
    u'asemakaavat': u'p8268',
    u'asemakaavoituskohteet': u'p8268',
    u'kasvatus ja opetus': (u'p476', u'p2630'),  # -> kasvatus, opetus
    u'avoin varhaiskasvatus ja kerhot': (u'p1650', u'p7642'),  # -> varhaiskasvatus, kerhot
}

# retain the above for simplicity, even if espoo importer internally requires full keyword ids
KEYWORDS_TO_ADD_TO_AUDIENCE = ['yso:{}'.format(i) for i in KEYWORDS_TO_ADD_TO_AUDIENCE]

# certain classifications are too general, or locations that do not belong to keywords
CLASSIFICATIONS_TO_DISREGARD = [
    'tapahtumat',
    'kulttuuri',
    'kulttuuri ja liikunta',
    'kulttuuri ja liikunta  ',
    'kaikki tapahtumat',
    'muut tapahtumat',
    'sellosali',
    'espoon kulttuurikeskus',
    'espoon kaupunginmuseo',
    'kamu',
    'näyttelykeskus weegee',
    'karatalo',
    'ohjelmisto',
    'kulttuurikohteet ja -toimijat',
    'espoo.fi',
    'kulttuuriespoo.fi',
    'kulttuurikeskukset ja -talot'
]

LOCATIONS = {
    # Place name in Finnish -> ((place node ids in event feed), tprek id)
    u'matinkylän asukaspuisto': ((15728,), 20267),
    u'soukan asukaspuisto': ((15740,), 20355),
    u'espoon kulttuurikeskus': ((15325,), 58548),
    u'näyttelykeskus weegee': ((15349,), 20404),
    u'KAMU': ((28944,), 20405),
    u'Karatalo': ((15357,), 21432),
    u'Nuuksio': ((15041,), 28401),
    u'Olarin asukaspuisto': ((15730,), 20268),
    u'Lasten kulttuurikeskus Aurora': ((15350,), 21431),
    u'Suviniityn avoin päiväkoti': ((15781,), 20376),
    u'Sellosali': ((15281,), 59212),
    u'Talomuseo Glims': ((28954,), 59312),
}

ESPOO_BASE_URL = 'http://www.espoo.fi'
ESPOO_API_URL = (
    ESPOO_BASE_URL + '/api/opennc/v1/ContentLanguages({lang_code})'
    '/Contents?$filter=TemplateId eq 58&$expand=ExtendedProperties,LanguageVersions'
    '&$orderby=EventEndDate desc&$format=json'
)

ESPOO_LANGUAGES = {
    'fi': 1,
    'sv': 3,
    'en': 2,
}

ADDRESS_LANGUAGES = ('fi', 'sv')

LOCAL_TZ = timezone('Europe/Helsinki')


def get_lang(lang_id):
    for code, lid in ESPOO_LANGUAGES.items():
        if lid == lang_id:
            return code
    return None


def mark_deleted(obj):
    if obj.deleted:
        return False
    obj.deleted = True
    obj.save(update_fields=['deleted'])
    return True


def clean_street_address(address):
    LATIN1_CHARSET = u'a-zàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ'

    address = address.strip()
    pattern = re.compile(r'([%s\ -]*[0-9-\ ]*\ ?[a-z]{0,2}),?\ *(0?2[0-9]{3})?\ *(espoo|esbo)?' % LATIN1_CHARSET, re.I)
    match = pattern.match(address)
    if not match:
        logger.warning('Address not matching {}'.format(address))
        return {}
    groups = match.groups()
    street_address = groups[0]
    postal_code = None
    city = None
    if len(groups) == 2:
        city = groups[1]
    elif len(groups) == 3:
        postal_code = groups[1]
        city = groups[2]
    return {
        'street_address': clean_text(street_address) or '',
        'postal_code': postal_code or '',
        'address_locality': city or '',
    }


def find_url(url):
    """
    Extract the url from the html tag if any, and return it cleaned if valid
    """
    matches = re.findall(r'href=["\'](.*?)["\']', url)
    if matches:
        url = matches[0]
    return clean_url(url)


class APIBrokenError(Exception):
    pass


@register_importer
class EspooImporter(Importer):
    name = "espoo"
    supported_languages = ['fi', 'sv', 'en']
    keyword_cache = {}
    location_cache = {}

    def _build_cache_places(self):
        loc_id_list = [l[1] for l in LOCATIONS.values()]
        place_list = Place.objects.filter(
            data_source=self.tprek_data_source
        ).filter(origin_id__in=loc_id_list)
        self.tprek_by_id = {p.origin_id: p.id for p in place_list}

    def _cache_yso_keywords(self):
        try:
            yso_data_source = DataSource.objects.get(id='yso')
        except DataSource.DoesNotExist:
            self.keyword_by_id = {}
            return

        cat_id_set = set()
        for yso_val in YSO_KEYWORD_MAPS.values():
            if isinstance(yso_val, tuple):
                for t_v in yso_val:
                    cat_id_set.add('yso:' + t_v)
            else:
                cat_id_set.add('yso:' + yso_val)
        keyword_list = Keyword.objects.filter(data_source=yso_data_source, deprecated=False).filter(id__in=cat_id_set)
        self.keyword_by_id = {p.id: p for p in keyword_list}

    def setup(self):
        self.tprek_data_source = DataSource.objects.get(id='tprek')

        ds_args = dict(id=self.name)
        ds_defaults = dict(name='City of Espoo')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=ds_defaults, **ds_args)

        org_args = dict(origin_id='kaupunki', data_source=self.data_source)
        org_defaults = dict(name='Espoon kaupunki')
        self.organization, _ = Organization.objects.get_or_create(defaults=org_defaults, **org_args)
        self._build_cache_places()
        self._cache_yso_keywords()

        if self.options['cached']:
            requests_cache.install_cache('espoo')
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
        return ext_props

    def _get_next_place_id(self, origin):
        """
        Return the next sequential place id for the provided origin
        """
        last_place = Place.objects.filter(data_source_id=origin).extra({
                        'id_uint': 'CAST(origin_id as INTEGER)'
                     }).order_by('-id_uint').first()
        _id = 1
        if last_place:
            _id = int(last_place.origin_id) + 1
        return _id

    def get_or_create_place_id(self, street_address, lang, name='', url=''):
        """
        Return the id of the event place corresponding to the street_address.
        Create the event place with the address, name and url if not found.

        Espoo website does not maintain a place object with a dedicated id.
        This function tries to map the address to an existing place or create
        a new one if no place is found.

        :param street_address: The exact street address of the location
        :type street_address: String

        :param lang: The language the strings are provided in
        :type lang: String

        :param name: Optional name for the location
        :type name: String

        :param url: Optional info URL for the location
        :type url: String

        :rtype: id for the location
        """
        address_data = clean_street_address(street_address)
        street_address = address_data.get('street_address', None)
        if not street_address:
            return

        espoo_loc_id = self.location_cache.get(street_address, None)
        if espoo_loc_id:
            return espoo_loc_id

        address_lang = lang
        if address_lang not in ADDRESS_LANGUAGES:
            # pick the first preferred language (e.g. Finnish) if lang (e.g. English) has no address translations
            address_lang = ADDRESS_LANGUAGES[0]
        # do not use street addresses, we want metadata for espoo event locations too!
        filter_params = {
            'data_source__in': (self.tprek_data_source, self.data_source),
            'deleted': False,
            'street_address_'+address_lang+'__icontains': street_address,
        }
        # prefer tprek, prefer existing event locations
        places = Place.objects.filter(**filter_params).order_by('-data_source', '-n_events')
        place = places.first()  # Choose one place arbitrarily if many.
        if len(places) > 1:
            logger.warning('Several tprek and/or espoo id match the address "{}".'.format(street_address))
        if not place:
            origin_id = self._get_next_place_id("espoo")
            # address must be saved in the right language!
            address_data['street_address_'+address_lang] = address_data.pop('street_address')
            address_data.update({
                'publisher': self.organization,
                'origin_id': origin_id,
                'id': 'espoo:%s' % origin_id,
                'data_source': self.data_source,
                'name_'+lang: name,
                'info_url_'+lang: url
            })
            place = Place(**address_data)
            place.save()
        elif place.data_source == self.data_source:
            # update metadata in the given language if the place belongs to espoo:
            setattr(place, 'name_'+lang, name)
            setattr(place, 'info_url_'+lang, url)
            setattr(place, 'street_address_'+address_lang, street_address)
            place.save(update_fields=['name_'+lang, 'info_url_'+lang, 'street_address_'+lang])
        # Cached the location to speed up
        self.location_cache.update({street_address: place.id})  # location cache need not care about address language
        return place.id

    def _map_classification_keywords_from_dict(self, classification_node_name):
        """
        Try to map the classification to yso keyword using the hardcoded dictionary
        YSO_KEYWORD_MAPS.

        :param classification_node_name: The node name of the classification element
        :type classification_node_name: String

        :rtype: set of keywords
        """
        event_keywords = set()
        if not self.keyword_by_id:
            return

        def yso_to_db(v):
            return self.keyword_by_id['yso:%s' % v]

        node_name_lower = classification_node_name.lower()  # Use lower case to get ride of case sensitivity
        if node_name_lower in YSO_KEYWORD_MAPS.keys():
            yso = YSO_KEYWORD_MAPS[node_name_lower]
            if isinstance(yso, tuple):
                for t_v in yso:
                    event_keywords.add(yso_to_db(t_v))
            else:
                event_keywords.add(yso_to_db(yso))
        return event_keywords

    def _map_classification_keywords_from_db(self, classification_node_name, lang):
        """
        Try to map the classification to an yso keyword using the keyword name from the YSO
        stored keywords. If not available, tries to map it to an espoo keywords.

        :param classification_node_name: The node name of the classification element
        :type classification_node_name: String

        :rtype: set containing the keyword
        """
        yso_data_source = DataSource.objects.get(id='yso')
        espoo_data_source = DataSource.objects.get(id='espoo')
        node_name = classification_node_name.strip()
        query = Keyword.objects.filter(deprecated=False, data_source__in=[yso_data_source, espoo_data_source])\
            .order_by('-data_source_id')
        if not lang:
            keyword = query.filter(name__iexact=node_name).first()

        if lang == 'fi':
            keyword = query.filter(name_fi__iexact=node_name).first()
        if lang == 'sv':
            keyword = query.filter(name_sv__iexact=node_name).first()
        if lang == 'en':
            keyword = query.filter(name_en__iexact=node_name).first()

        if not keyword:
            return set()

        self.keyword_by_id.update({keyword.id: keyword})
        return {keyword}

    def _get_classification_keywords(self, classification_node_name, lang):
        """
        Try to map the classification node name to a yso keyword

        The mapping is done first using the hard-coded list YSO_KEYWORD_MAPS, then
        by querying the saved yso keywords.

        :param classification_node_name: The node name of the classification element
        :type classification_node_name: String

        :rtype: list of yso keywords
        """
        event_keywords = self._map_classification_keywords_from_dict(classification_node_name)
        if event_keywords:
            return event_keywords
        keywords = self._map_classification_keywords_from_db(classification_node_name, lang)
        if lang == 'fi' and not keywords:
            logger.warning('Cannot find yso classification for keyword: {}'.format(classification_node_name))
            return set()
        self.keyword_by_id.update(dict({k.id: k for k in keywords}))
        return keywords

    def _import_event(self, lang, event_el, events):
        # Times are in Helsinki timezone
        def to_utc(dt):
            return LOCAL_TZ.localize(dt, is_dst=None).astimezone(pytz.utc)

        def dt_parse(dt_str):
            return to_utc(dateutil.parser.parse(dt_str))

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

        ext_props = EspooImporter._get_extended_properties(event_el)

        if 'name' in ext_props:
            event['name'][lang] = clean_text(ext_props['name'], True)
            del ext_props['name']

        if ext_props.get('EventDescription', ''):
            desc = ext_props['EventDescription']
            ok_tags = ('u', 'b', 'h2', 'h3', 'em', 'ul', 'li', 'strong', 'br', 'p', 'a')
            desc = bleach.clean(desc, tags=ok_tags, strip=True)
            event['description'][lang] = clean_text(desc)
            del ext_props['EventDescription']

        if ext_props.get('LiftContent', ''):
            text = ext_props['LiftContent']
            text = clean_text(strip_tags(text))
            event['short_description'][lang] = text
            del ext_props['LiftContent']

        if 'offers' not in event:
            event['offers'] = [recur_dict()]
        offer = event['offers'][0]
        has_offer = False
        offer['event_id'] = event['id']
        if ext_props.get('Price', ''):
            text = clean_text(ext_props['Price'])
            offer['price'][lang] = text
            del ext_props['Price']
            has_offer = True
            if text.startswith('Vapaa pääsy') or text.startswith('Fritt inträde'):
                offer['is_free'] = True

        if ext_props.get('TicketLinks', ''):
            offer['info_url'][lang] = find_url(ext_props['TicketLinks'])
            del ext_props['TicketLinks']
            has_offer = True
        if ext_props.get('Tickets', ''):
            offer['description'][lang] = ext_props['Tickets']
            del ext_props['Tickets']
            has_offer = True
        if not has_offer:
            del event['offers']

        if ext_props.get('URL', ''):
            event['info_url'][lang] = find_url(ext_props['URL'])

        if ext_props.get('Organizer', ''):
            event['provider'][lang] = clean_text(ext_props['Organizer'])
            del ext_props['Organizer']

        if 'LiftPicture' in ext_props:
            matches = re.findall(r'src="(.*?)"', str(ext_props['LiftPicture']))
            if matches:
                img_url = matches[0]
                event['images'] = [{'url': img_url}]
            del ext_props['LiftPicture']

        event['url'][lang] = '%s/api/opennc/v1/Contents(%s)' % (
            ESPOO_BASE_URL, eid
        )

        def set_attr(field_name, val):
            if event.get(field_name, val) != val:
                logger.warning('Event {}: {} mismatch ({} vs. {})'
                               .format(eid, field_name, event[field_name], val))
                return
            event[field_name] = val

        if 'date_published' not in event:
            # Publication date changed based on language version, so we make sure
            # to save it only from the primary event.
            event['date_published'] = dt_parse(event_el['PublicDate'])

        set_attr('start_time', dt_parse(event_el['EventStartDate']))
        set_attr('end_time', dt_parse(event_el['EventEndDate']))

        def to_tprek_id(k):
            return self.tprek_by_id[str(k).lower()]

        def to_le_id(nid):
            return next((to_tprek_id(v[1]) for k, v in LOCATIONS.items() if nid in v[0]), None)

        event_keywords = event.get('keywords', set())
        event_audience = event.get('audience', set())

        for classification in event_el['Classifications']:
            # Save original keyword in the raw too
            # node_id = classification['NodeId']
            # name = classification['NodeName']
            node_type = classification['Type']
            # Do not use espoo keywords at all
            # # Tapahtumat exists tens of times, use pseudo id
            # if name in ('Tapahtumat', 'Events', 'Evenemang'):
            #     node_id = 1  # pseudo id
            # keyword_id = 'espoo:{}'.format(node_id)
            # kwargs = {
            #     'id': keyword_id,
            #     'origin_id': node_id,
            #     'data_source_id': 'espoo',
            # }
            # if name in self.keyword_cache:
            #     keyword_orig = self.keyword_cache[name]
            #     created = False
            # else:
            #     keyword_orig, created = Keyword.objects.get_or_create(**kwargs)
            #     self.keyword_cache[name] = keyword_orig
            #
            # name_key = 'name_{}'.format(lang)
            # if created:
            #     keyword_orig.name = name  # Assume default lang Finnish
            #     # Set explicitly modeltranslation field
            #     setattr(keyword_orig, name_key, name)
            #     keyword_orig.save()
            # else:
            #     current_name = getattr(keyword_orig, name_key)
            #     if not current_name:  # is None or empty
            #         setattr(keyword_orig, name_key, name)
            #         keyword_orig.save()
            #
            # event_keywords.add(keyword_orig)

            # Several nodes might match to location, do not classify them further
            location_id = to_le_id(classification['NodeId'])
            if location_id:
                if 'location' not in event:
                    event['location']['id'] = location_id
                continue
            # Type 12 node refers to presence online
            if node_type == 12:
                continue
            # disregard certain keywords that are pure spam
            if classification['NodeName'].lower() in CLASSIFICATIONS_TO_DISREGARD:
                continue
            node_name = str(classification['NodeName']).lower()
            yso_keywords = self._get_classification_keywords(node_name, lang)
            event_keywords = event_keywords.union(yso_keywords)
            # add audience keywords to audience too
            for keyword in yso_keywords:
                if keyword.id in KEYWORDS_TO_ADD_TO_AUDIENCE:
                    event_audience.add(keyword)

        event['keywords'] = event_keywords
        event['audience'] = event_audience

        if ext_props.get('StreetAddress', None):
            if 'location' in event:
                # Already assigned a location, sets the address as location extra info
                event['location']['extra_info'][lang] = ext_props.get('StreetAddress')
            else:
                # Get the place using the address, or create a new place
                place_id = self.get_or_create_place_id(ext_props.get('StreetAddress'), lang,
                                                       name=clean_text(ext_props.get('EventLocation', '')),
                                                       url=ext_props.get('URL', ''))
                if place_id:
                    event['location']['id'] = place_id
                else:
                    logger.warning('Cannot find {}'.format(ext_props['StreetAddress']))
            del ext_props['StreetAddress']

        if ext_props.get('EventLocation', ''):
            event['location']['extra_info'][lang] = clean_text(ext_props['EventLocation'])
            del ext_props['EventLocation']

        if 'location' not in event:
            logger.warning('Missing TPREK location map for event {} ({})'
                           .format(event['name'][lang], str(eid)))
            del events[event['origin_id']]
            return event

        # Espoo custom data not needed at the moment
        # for p_k, p_v in ext_props.items():
        #     if p_k == 'ExternalVideoLink' and p_v == 'http://':
        #         continue
        #     event['custom_data'][p_k] = p_v
        return event

    def _recur_fetch_paginated_url(self, url, lang, events):
        for _ in range(MAX_RETRY):
            response = requests.get(url)
            if response.status_code != 200:
                logger.error("Espoo API reported HTTP %d" % response.status_code)
                time.sleep(5)
                if self.cache:
                    self.cache.delete_url(url)
                continue
            try:
                root_doc = response.json()
            except ValueError:
                logger.error("Espoo API returned invalid JSON for url: {}".format(url))
                if self.cache:
                    self.cache.delete_url(url)
                time.sleep(5)
                continue
            break
        else:
            logger.error("Espoo API is broken, giving up")
            raise APIBrokenError()

        documents = root_doc['value']
        earliest_end_time = None
        for doc in documents:
            event = self._import_event(lang, doc, events)
            if not earliest_end_time or event['end_time'] < earliest_end_time:
                earliest_end_time = event['end_time']

        now = datetime.now().replace(tzinfo=LOCAL_TZ)
        # We check 31 days backwards.
        if earliest_end_time and earliest_end_time < now - timedelta(days=31):
            return

        if 'odata.nextLink' in root_doc:
            self._recur_fetch_paginated_url(
                '%s/api/opennc/v1/%s%s' % (
                    ESPOO_BASE_URL,
                    root_doc['odata.nextLink'],
                    "&$format=json"
                ), lang, events)

    def import_events(self):
        logger.info("Importing Espoo events")
        events = recur_dict()
        for lang in self.supported_languages:
            espoo_lang_id = ESPOO_LANGUAGES[lang]
            url = ESPOO_API_URL.format(lang_code=espoo_lang_id)
            logger.info("Processing lang {}".format(lang))
            logger.info("from URL {}".format(url))
            try:
                self._recur_fetch_paginated_url(url, lang, events)
            except APIBrokenError:
                return

        event_list = sorted(events.values(), key=lambda x: x['end_time'])
        qs = Event.objects.filter(end_time__gte=datetime.now(),
                                  data_source='espoo', deleted=False)

        self.syncher = ModelSyncher(qs, lambda obj: obj.origin_id, delete_func=mark_deleted)

        for event in event_list:
            obj = self.save_event(event)
            self.syncher.mark(obj)

        self.syncher.finish(force=self.options['force'])
        logger.info("{} events processed".format(len(events.values())))
