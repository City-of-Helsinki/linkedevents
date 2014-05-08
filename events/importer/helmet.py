# -*- coding: utf-8 -*-

import requests
import json
import re
import dateutil.parser
from django.utils.html import strip_tags
from .base import Importer, register_importer, recur_dict
from events.models import *
from pytz import timezone
import pytz

YSO_BASE_URL = 'http://www.yso.fi/onto/yso/'
YSO_CATEGORY_MAPS = {
    u'Yrittäjät': u'p1178',
    u'Lapset': u'p12262',
    u'Kirjastot': u'p2787',
    u'Opiskelijat': u'p16486',
    u'Konsertit ja klubit': (u'p11185', u'p20421'),  # -> konsertit, musiikkiklubit
    u'Kurssit': u'p9270',
    u'venäjä': u'p7643',  # -> venäjän kieli
    u'Seniorit': u'p2434',  # -> vanhukset
    u'Näyttelyt': u'p5121',
    u'Kirjallisuus': u'p8113',
    u'Kielikahvilat ja keskusteluryhmät': u'p18105',  # -> keskusteluryhmät
    u'Maahanmuuttajat': u'p6165',
    u'Opastukset ja kurssit': (u'p2149', u'p9270'),  # -> opastus, kurssit
    u'Nuoret': u'p11617',
    u'Pelitapahtumat': u'p6062',  # -> pelit
    u'Satutunnit': u'p14710',
    u'Koululaiset': u'p16485',
    u'Lasten ja nuorten tapahtumat': (u'p12262', u'p11617'),  # -> lapset, nuoret
    u'Lapset ja perheet': (u'p12262', u'p4363'),  # -> lapset, perheet
    #u'Opastuskalenteri ': '?',
    #u'Lukupiirit': '?',
    #u'muut kielet': '?'
}

LOCATIONS = {
    # Library name in Finnish -> ((library node ids in event feed), tprek id)
    u"Arabianrannan kirjasto": ((10784, 11271), 8234),
    u"Entressen kirjasto": ((10659, 11274), 15321),
    u"Etelä-Haagan kirjasto": ((10786, 11276), 8150),
    u"Hakunilan kirjasto": ((10787, 11278), 19580),
    u"Haukilahden kirjasto": ((10788, 11280), 19580),
    u"Herttoniemen kirjasto": ((10789, 11282), 8325),
    u"Hiekkaharjun kirjasto": ((10790, 11284), 18584),
    u"Itäkeskuksen kirjasto": ((10791, 11286), 8184),
    u"Jakomäen kirjasto": ((10792, 11288), 8324),
    u"Kalajärven kirjasto": ((10793, 11290), 15365),
    u"Kallion kirjasto": ((10794, 11291), 8215),
    u"Kannelmäen kirjasto": ((10795, 11294), 8141),
    u"Karhusuon kirjasto": ((10796, 11296), 15422),
    u"Kauklahden kirjasto": ((10798, 11298), 15317),
    u"Kauniaisten kirjasto": ((10799, 11301), 14432),
    u"Kirjasto 10": ((10800, 11303), 8286),
    u"Kirjasto Omena": ((10801, 11305), 15395),
    u"Kivenlahden kirjasto": ((10803, 11309), 15334),
#    u"Kohtaamispaikka@lasipalatsi": (10804, 11311),     # -> kaupunkiverstas ?
    u"Kaupunkiverstas": ((10804, 11311), 8145), # former Kohtaamispaikka
    u"Koivukylän kirjasto": ((10805, 11313), 19572),
    u"Kontulan kirjasto u": ((10806, 11315), 8178),
    u"Kotipalvelu": ((10811, 11317), 8285),
    u"Käpylän kirjasto": ((10812, 11319), 8302),
    u"Laajalahden kirjasto": ((10813, 11321), 15344),
    u"Laajasalon kirjasto": ((10814, 11323), 8143),
    u"Laaksolahden kirjasto": ((10815, 11325), 15309),
#    u"Laitoskirjastot": ((10816, 11327), ),
    u"Lauttasaaren kirjasto": ((10817, 11329), 8344),
    u"Lumon kirjasto": ((10818, 11331), 18262),
    u"Länsimäen kirjasto": ((10819, 11333), 18620),
    u"Malmin kirjasto": ((10820, 11335), 8192),
    u"Malminkartanon kirjasto": ((10821, 11337), 8220),
    u"Martinlaakson kirjasto": ((10822, 11339), 19217),
    u"Maunulan kirjasto": ((10823, 11341), 8350),
    #u"Mikkolan kirjasto": (10808, 11343),  #  Suljettu
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

HELMET_BASE_URL = 'http://www.helmet.fi'
HELMET_API_URL = (
    HELMET_BASE_URL + '/api/opennc/v1/ContentLanguages%28{lang_code}%29' +
    '/Contents?$filter=TemplateId%20eq%203&$expand=ExtendedProperties'
    '&$orderby=EventEndDate%20desc&$format=json'
)
HELMET_LANGUAGES = {
    'fi': 1,
    'sv': 3,
    'en': 2
}

LOCAL_TZ = timezone('Europe/Helsinki')

@register_importer
class HelmetImporter(Importer):
    name = "helmet"
    supported_languages = ['fi', 'sv', 'en']

    def setup(self):
        ds_args = dict(id=self.name)
        defaults = dict(name='HelMet-kirjastot', event_url_template='https://{origin_id}')
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args)
        self.tprek_data_source = DataSource.objects.get(id='tprek')
        self.yso_data_source = DataSource.objects.get(id='yso')

        # Build a cached list of Places
        loc_id_list = [l[1] for l in LOCATIONS.values()]
        place_list = Place.objects.filter(
            data_source=self.tprek_data_source
        ).filter(origin_id__in=loc_id_list)
        self.tprek_by_id = {p.origin_id: p.id for p in place_list}

        # Build a cached list of YSO categories
        cat_id_set = set()
        for yso_val in YSO_CATEGORY_MAPS.values():
            if isinstance(yso_val, tuple):
                for t_v in yso_val:
                    cat_id_set.add(YSO_BASE_URL + t_v)
            else:
                cat_id_set.add(YSO_BASE_URL + yso_val)

        self.category_list = Category.objects.filter(
            data_source=self.yso_data_source
        ).filter(url__in=cat_id_set)
        self.yso_by_id = {p.url: p.id for p in self.category_list}


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
        eid = int(event_el['ContentId'])
        event = events[eid]
        event['data_source'] = self.data_source
        event['origin_id'] = eid

        ext_props = HelmetImporter._get_extended_properties(event_el)

        if ext_props['Name']:
            event['name'][lang] = ext_props['Name']

        if ext_props['Description']:
            event['description'][lang] = strip_tags(ext_props['Description'])

        matches = re.findall(r'src="(.*?)"', unicode(ext_props['Images']))
        if matches:
            img_url = matches[0]
            event['image'] = HELMET_BASE_URL + img_url

        event['url'][lang] = '%s/api/opennc/v1/Contents(%s)' % (
            HELMET_BASE_URL, eid
        )

        # Custom stuff not in our data model, what we actually need?
        for p_k, p_v in ext_props.items():
            if p_k not in ('Description', 'Name', 'Images'):
                event['custom_fields'][p_k] = p_v

        # Times are in UTC+02:00 timezone
        to_utc = lambda dt: LOCAL_TZ.localize(
            dt, is_dst=None).astimezone(pytz.utc)
        dt_parse = lambda dt_str: to_utc(dateutil.parser.parse(dt_str))
        event['date_published'] = dt_parse(event_el['PublicDate'])
        event['start_time'] = dt_parse(event_el['EventStartDate'])
        event['end_time'] = dt_parse(event_el['EventEndDate'])

        # custom_fields only accepts strings
        event['custom_fields']['ExpiryDate'] = dt_parse(
            event_el['ExpiryDate']).strftime("%Y-%m-%dT%H:%M:%SZ")

        to_tprek_id = lambda k: self.tprek_by_id[unicode(k)]
        to_le_id = lambda nid: next(
            (to_tprek_id(v[1]) for k, v in LOCATIONS.iteritems()
             if nid in v[0]), None)
        yso_to_db = lambda v: self.yso_by_id[YSO_BASE_URL + v]

        event_categories = set()
        for classification in event_el['Classifications']:
            # Oddly enough, "Tapahtumat" node includes NodeId pointing to
            # HelMet location, which is mapped to Linked Events category ID
            if classification['NodeName'] == 'Tapahtumat':
                event['location']['id'] = to_le_id(classification['NodeId'])
                if not event['location']:
                    print('Missing TPREK location map for NodeId(' +
                          str(classification['NodeId']) +
                          ') in event ' + str(eid))
            else:
                # Map some classifications to YSO based categories
                if unicode(classification['NodeName']) in YSO_CATEGORY_MAPS.keys():
                    yso = YSO_CATEGORY_MAPS[unicode(classification['NodeName'])]
                    if isinstance(yso, tuple):
                        for t_v in yso:
                            event_categories.add(yso_to_db(t_v))
                    else:
                        event_categories.add(yso_to_db(yso))
        event['categories'] = event_categories

    def import_events(self):
        print("Importing HelMet events")
        events = recur_dict()
        for lang, helmet_lang_id in HELMET_LANGUAGES.iteritems():
            url = HELMET_API_URL.format(lang_code=helmet_lang_id)
            print("Processing lang " + lang)
            response = requests.get(url)
            assert response.status_code == 200
            documents = json.loads(response.content)['value']
            for doc in documents:
                self._import_event(lang, doc, events)
        for event in events.values():
            self.save_event(event)
        print("%d events processed" % len(events.values()))
