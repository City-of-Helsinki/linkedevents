# -*- coding: utf-8 -*-

import time
import requests
import json
import re

from .base import Importer, register_importer, recur_dict
from events.models import *
from util import active_language

LOCATIONS = {
    # Library name in Finnish -> (library node ids in event feed)
    u"Arabianrannan kirjasto": (10784, 11271),
    u"Entressen kirjasto": (10659, 11274),
    u"Etelä-Haagan kirjasto": (10786, 11276),
    u"Hakunilan kirjasto": (10787, 11278),
    u"Haukilahden kirjasto": (10788, 11280),
    u"Herttoniemen kirjasto": (10789, 11282),
    u"Hiekkaharjun kirjasto": (10790, 11284),
    u"Itäkeskuksen kirjasto": (10791, 11286),
    u"Jakomäen kirjasto": (10792, 11288),
    u"Kalajärven kirjasto": (10793, 11290),
    u"Kallion kirjasto": (10794, 11291),
    u"Kannelmäen kirjasto": (10795, 11294),
    u"Karhusuon kirjasto": (10796, 11296),
    u"Kauklahden kirjasto": (10798, 11298),
    u"Kauniaisten kirjasto": (10799, 11301),
    u"Kirjasto 10": (10800, 11303),
    u"Kirjasto Omena": (10801, 11305),
    u"Kivenlahden kirjasto": (10803, 11309),
#    u"Kohtaamispaikka@lasipalatsi": (10804, 11311),     # -> kaupunkiverstas ? 
    u"Kaupunkiverstas": (10804, 11311), # former Kohtaamispaikka
    u"Koivukylän kirjasto": (10805, 11313),
    u"Kontulan kirjasto u": (10806, 11315),
    u"Kotipalvelu": (10811, 11317),
    u"Käpylän kirjasto": (10812, 11319),
    u"Laajalahden kirjasto": (10813, 11321),
    u"Laajasalon kirjasto": (10814, 11323),
    u"Laaksolahden kirjasto": (10815, 11325),
    u"Laitoskirjastot": (10816, 11327),
    u"Lauttasaaren kirjasto": (10817, 11329),
    u"Lumon kirjasto": (10818, 11331),
    u"Länsimäen kirjasto": (10819, 11333),
    u"Malmin kirjasto": (10820, 11335),
    u"Malminkartanon kirjasto": (10821, 11337),
    u"Martinlaakson kirjasto": (10822, 11339),
    u"Maunulan kirjasto": (10823, 11341),
    #u"Mikkolan kirjasto": (10808, 11343),  #  Suljettu
    u"Monikielinen kirjasto": (10824, 11345),
    u"Munkkiniemen kirjasto": (10825, 11347),
    u"Myllypuron mediakirjasto": (10826, 11349),
    u"Myyrmäen kirjasto": (10827, 11351),
    u"Nöykkiön kirjasto": (10828, 11353),
    u"Oulunkylän kirjasto": (10829, 11355),
    u"Paloheinän kirjasto": (10830, 11357),
    u"Pasilan kirjasto": (10831, 11359),
    u"Pikku Huopalahden lastenkirjasto": (10832, 11361),
    u"Pitäjänmäen kirjasto": (10833, 11363),
    u"Pohjois-Haagan kirjasto": (10834, 11365),
    u"Pointin kirjasto": (10835, 11367),
    u"Puistolan kirjasto": (10837, 11369),
    u"Pukinmäen kirjasto": (10838, 11371),
    u"Pähkinärinteen kirjasto": (10839, 11373),
    u"Rikhardinkadun kirjasto": (10840, 11375),
    u"Roihuvuoren kirjasto": (10841, 11377),
    u"Ruoholahden lastenkirjasto": (10842, 11379),
    u"Sakarinmäen lastenkirjasto": (10843, 11381),
    u"Saunalahden kirjasto": (11712, 11714),
    u"Sellon kirjasto": (10844, 11383),
    u"Soukan kirjasto": (10845, 11385),
    u"Suomenlinnan kirjasto": (10846, 11387),
    u"Suutarilan kirjasto": (10847, 11389),
    u"Tapanilan kirjasto": (10848, 11391),
    u"Tapiolan kirjasto": (10849, 11395),
    u"Tapulikaupungin kirjasto": (10850, 11397),
    u"Tikkurilan kirjasto": (10851, 11202),
    u"Töölön kirjasto": (10852, 11393),
    u"Vallilan kirjasto": (10853, 11399),
    u"Viherlaakson kirjasto": (10854, 11401),
    u"Viikin kirjasto": (10855, 11403),
    u"Vuosaaren kirjasto": (10856, 11405),
}

SERVICEMAP_API_URL = 'http://www.hel.fi/palvelukarttaws/rest/v2/unit/'
HELMET_URL = (
    'http://www.helmet.fi/api/opennc/v1/ContentLanguages%28{lang_code}%29' +
    '/Contents?$filter=TemplateId%20eq%203&$expand=ExtendedProperties'
    '&$orderby=EventEndDate%20desc&$format=json'
)
HELMET_LANGUAGES = {
    'fi': 1,
    'sv': 3,
    'en': 2
}

@register_importer
class HelmetImporter(Importer):
    name = "helmet"
    data_source = DataSource.objects.get(pk=name)

    def import_locations(self):
        print("Importing HelMet libraries as locations")
        for name_fi, node_ids in LOCATIONS.iteritems():
            resp = requests.get(
                SERVICEMAP_API_URL,
                params={'search': name_fi.encode('iso-8859-1')}
            )
            time.sleep(0.2)  # Let's not DoS the API.
            assert resp.status_code == 200
            result = json.loads(resp.content)
            result = filter(lambda x: x['name_fi'] == name_fi, result)
            if len(result) != 1:
                print 'Not found:', len(result), name_fi, name_fi.replace('@', ' ')
                return None

            UNIT_URL = SERVICEMAP_API_URL + str(result[0]['id'])
            detailed_resp = requests.get(UNIT_URL)
            assert detailed_resp.status_code == 200
            unit_details = json.loads(detailed_resp.content)
            servicemap_datasource = DataSource.objects.get(pk='servicemap')

            name_keys = filter(lambda x: re.match(r'name_\w+', x), unit_details.keys())
            available_languages = [key.split('_')[1] for key in name_keys]
            location = recur_dict()

            translate = lambda d, k, l: d.get(k + '_' + l)
            for l in available_languages:
                location['name'][l] = translate(unit_details, 'name', l)
                location['address']['street_address'][l] = translate(
                    unit_details, 'street_address', l
                )
                location['address']['address_locality'][l] = translate(
                    unit_details, 'address_city', l
                )

            location['address']['postal_code'] = unit_details['address_zip']
            location['origin_id'] = unit_details['id']
            location['data_source'] = 'servicemap'
            location['geo'] = {
                'longitude': unit_details['longitude'],
                'latitude': unit_details['latitude'],
                'geo_type': 1
            }

            import pprint
            pprint.pprint(location)
            
            break
                
    def import_events(self):
        import pprint  # todo remove
        events = recur_dict()
        for lang, helmet_lang_id in HELMET_LANGUAGES.iteritems():
            url = HELMET_URL.format(lang_code=helmet_lang_id)
            response = requests.get(url)
            assert response.status_code == 200
            documents = json.loads(response.content)
            for doc in documents:
                pprint.pprint(doc)
                break
