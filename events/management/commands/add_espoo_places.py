from functools import lru_cache

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Event, Keyword, KeywordSet, DataSource

logger = logging.getLogger(__name__)

ESPOO_DATA_SOURCE_ID = 'espoo'

ESPOO_PLACE_KEYWORD_SET_DATA = {
    'id': 'espoo:places',
    'name_en': 'Espoo\'s places',
    'name_fi': 'Espoon paikat',
    'name_sv': 'Esbos platser',
    'data_source_id': ESPOO_DATA_SOURCE_ID,
    'usage': KeywordSet.KEYWORD,
}

# Place keyword ID format: espoo:p<integer>, where p stands for place followed by a sequential integer (note that the p
# character has nothing to do with the YSO keyword ID)
CUSTOM_ESPOO_PLACE_KEYWORDS = [
    {
        'id': 'espoo:p1',
        'name_fi': 'Bodom',
        'name_sv': 'Bodom',
        'name_en': 'Bodom',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p2',
        'name_fi': 'Espoon keskus',
        'name_sv': 'Esbo centrum',
        'name_en': 'Espoon keskus',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p3',
        'name_fi': 'Espoonkartano',
        'name_sv': 'Esbogård',
        'name_en': 'Espoonkartano',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p4',
        'name_fi': 'Espoonlahti',
        'name_sv': 'Esboviken',
        'name_en': 'Espoonlahti',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p5',
        'name_fi': 'Finnoo',
        'name_sv': 'Finno',
        'name_en': 'Finnoo',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p6',
        'name_fi': 'Gumböle',
        'name_sv': 'Gumböle',
        'name_en': 'Gumböle',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p7',
        'name_fi': 'Haukilahti',
        'name_sv': 'Gäddvik',
        'name_en': 'Haukilahti',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p8',
        'name_fi': 'Henttaa',
        'name_sv': 'Hemtans',
        'name_en': 'Henttaa',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p9',
        'name_fi': 'Högnäs',
        'name_sv': 'Högnäs',
        'name_en': 'Högnäs',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p10',
        'name_fi': 'Järvenperä',
        'name_sv': 'Träskända',
        'name_en': 'Järvenperä',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p11',
        'name_fi': 'Kaitaa',
        'name_sv': 'Kaitans',
        'name_en': 'Kaitaa',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p12',
        'name_fi': 'Kalajärvi',
        'name_sv': 'Kalajärvi',
        'name_en': 'Kalajärvi',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p13',
        'name_fi': 'Karakallio',
        'name_sv': 'Karabacka',
        'name_en': 'Karakallio',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p14',
        'name_fi': 'Karhusuo',
        'name_sv': 'Björnkärr',
        'name_en': 'Karhusuo',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p15',
        'name_fi': 'Karvasmäki',
        'name_sv': 'Karvasbacka',
        'name_en': 'Karvasmäki',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p16',
        'name_fi': 'Kauklahti',
        'name_sv': 'Köklax',
        'name_en': 'Kauklahti',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p17',
        'name_fi': 'Kaupunginkallio',
        'name_sv': 'Stadsberget',
        'name_en': 'Kaupunginkallio',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p18',
        'name_fi': 'Keilaniemi',
        'name_sv': 'Kägeludden',
        'name_en': 'Keilaniemi',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p19',
        'name_fi': 'Kera',
        'name_sv': 'Kera',
        'name_en': 'Kera',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p20',
        'name_fi': 'Kilo',
        'name_sv': 'Kilo',
        'name_en': 'Kilo',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p21',
        'name_fi': 'Kivenlahti',
        'name_sv': 'Stensvik',
        'name_en': 'Kivenlahti',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p22',
        'name_fi': 'Kolmperä',
        'name_sv': 'Kolmpers',
        'name_en': 'Kolmperä',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p23',
        'name_fi': 'Kunnarla',
        'name_sv': 'Gunnars',
        'name_en': 'Kunnarla',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p24',
        'name_fi': 'Kurttila',
        'name_sv': 'Kurtby',
        'name_en': 'Kurttila',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p25',
        'name_fi': 'Kuurinniitty',
        'name_sv': 'Kurängen',
        'name_en': 'Kuurinniitty',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p26',
        'name_fi': 'Laajalahti',
        'name_sv': 'Bredvik',
        'name_en': 'Laajalahti',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p27',
        'name_fi': 'Laaksolahti',
        'name_sv': 'Dalsvik',
        'name_en': 'Laaksolahti',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p28',
        'name_fi': 'Lahnus',
        'name_sv': 'Lahnus',
        'name_en': 'Lahnus',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p29',
        'name_fi': 'Lakisto',
        'name_sv': 'Lakisto',
        'name_en': 'Lakisto',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p30',
        'name_fi': 'Latokaski',
        'name_sv': 'Ladusved',
        'name_en': 'Latokaski',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p31',
        'name_fi': 'Leppävaara',
        'name_sv': 'Alberga',
        'name_en': 'Leppävaara',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p32',
        'name_fi': 'Lintuvaara',
        'name_sv': 'Fågelberga',
        'name_en': 'Lintuvaara',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p33',
        'name_fi': 'Lippajärvi',
        'name_sv': 'Klappträsk',
        'name_en': 'Lippajärvi',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p34',
        'name_fi': 'Luukki',
        'name_sv': 'Luk',
        'name_en': 'Luukki',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p35',
        'name_fi': 'Mankkaa',
        'name_sv': 'Mankans',
        'name_en': 'Mankkaa',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p36',
        'name_fi': 'Matinkylä',
        'name_sv': 'Mattby',
        'name_en': 'Matinkylä',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p37',
        'name_fi': 'Muurala',
        'name_sv': 'Morby',
        'name_en': 'Muurala',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p38',
        'name_fi': 'Niipperi',
        'name_sv': 'Nipert',
        'name_en': 'Niipperi',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p39',
        'name_fi': 'Niittykumpu',
        'name_sv': 'Ängskulla',
        'name_en': 'Niittykumpu',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p40',
        'name_fi': 'Nupuri',
        'name_sv': 'Nupurböle',
        'name_en': 'Nupuri',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p41',
        'name_fi': 'Nuuksio',
        'name_sv': 'Noux',
        'name_en': 'Nuuksio',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p42',
        'name_fi': 'Nöykkiö',
        'name_sv': 'Nöykis',
        'name_en': 'Nöykkiö',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p43',
        'name_fi': 'Olari',
        'name_sv': 'Olars',
        'name_en': 'Olari',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p44',
        'name_fi': 'Otaniemi',
        'name_sv': 'Otnäs',
        'name_en': 'Otaniemi',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p45',
        'name_fi': 'Perusmäki',
        'name_sv': 'Grundbacka',
        'name_en': 'Perusmäki',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p46',
        'name_fi': 'Pohjois-Tapiola',
        'name_sv': 'Norra Hagalund',
        'name_en': 'Pohjois-Tapiola',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p47',
        'name_fi': 'Röylä',
        'name_sv': 'Rödskog',
        'name_en': 'Röylä',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p48',
        'name_fi': 'Saunalahti',
        'name_sv': 'Bastvik',
        'name_en': 'Saunalahti',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p49',
        'name_fi': 'Sepänkylä',
        'name_sv': 'Smedsby',
        'name_en': 'Sepänkylä',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p50',
        'name_fi': 'Siikajärvi',
        'name_sv': 'Siikajärvi',
        'name_en': 'Siikajärvi',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p51',
        'name_fi': 'Soukka',
        'name_sv': 'Sökö',
        'name_en': 'Soukka',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p52',
        'name_fi': 'Suurpelto',
        'name_sv': 'Storåkern',
        'name_en': 'Suurpelto',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p53',
        'name_fi': 'Suvisaaristo',
        'name_sv': 'Sommaröarna',
        'name_en': 'Suvisaaristo',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p54',
        'name_fi': 'Tapiola',
        'name_sv': 'Hagalund',
        'name_en': 'Tapiola',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p55',
        'name_fi': 'Vanhakartano',
        'name_sv': 'Gammelgård',
        'name_en': 'Vanhakartano',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p56',
        'name_fi': 'Vanha-Nuuksio',
        'name_sv': 'Gamla Noux',
        'name_en': 'Vanha-Nuuksio',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p57',
        'name_fi': 'Vanttila',
        'name_sv': 'Fantsby',
        'name_en': 'Vanttila',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p58',
        'name_fi': 'Velskola',
        'name_sv': 'Vällskog',
        'name_en': 'Velskola',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p59',
        'name_fi': 'Westend',
        'name_sv': 'Westend',
        'name_en': 'Westend',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p60',
        'name_fi': 'Viherlaakso',
        'name_sv': 'Gröndal',
        'name_en': 'Viherlaakso',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p61',
        'name_fi': 'Ämmässuo',
        'name_sv': 'Käringmossen',
        'name_en': 'Ämmässuo',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p62',
        'name_fi': 'Muu kuin Espoo',
        'name_sv': 'Annat än Esbo',
        'name_en': 'Other than Espoo',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:p63',
        'name_fi': 'Online-tapahtuma',
        'name_sv': 'Online-evenemang',
        'name_en': 'Online event',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    }
]

YSO_REMOTE_PARTICIPATION_KEYWORD_ID = 'yso:p26626'
NON_ESPOO_PLACE_KEYWORD_ID = 'espoo:p62'
ESPOO_ONLINE_PLACE_KEYWORD_ID = 'espoo:p63'

NON_DISTRICT_PLACE_KEYWORD_IDS = [
  NON_ESPOO_PLACE_KEYWORD_ID,
  ESPOO_ONLINE_PLACE_KEYWORD_ID,
]

# Note that mapping locations to districts based on postal codes is a naive implementation since the mapping isn't
# unambiguous. For instance, certain postal codes can map to multiple districts and vice versa. The mapping also isn't
# exactly one-to-one in the sense that postal code areas do not exactly follow district borders. Thus, it might happen
# that an event is organized in a location which has a certain postal code and is thus mapped to a certain district but
# the actual location is outside the district. Also, note that some locations may have postal codes that aren't exactly
# tied to the actual location. For instance, Sellosali has the postal code "02070" which is the postal code for the
# City of Espoo and not a certain geographical area such as Leppävaara where Sellosali is actually located. Thus,
# certain postal codes can't be used to map events to specific geographical districts automatically. Currently, there
# are 135 postal codes for Espoo of which 46 are mapped to actual geographical districts. These 46 postal codes have
# been mapped to districts in the below mapping. This mapping is based on information from:
# - Statistics Finland (http://www.stat.fi/tup/paavo/tietosisalto_ja_esimerkit.html, file: "Postinumero-kunta -avain
#   2020 (xlsx)") for getting the mapping of postal codes to districts
# - Wikipedia (https://fi.wikipedia.org/wiki/Luettelo_Suomen_postinumeroista_kunnittain) for getting the mapping of
#   postal codes to districts
# - The Paikkatietoikkuna service (https://kartta.paikkatietoikkuna.fi) for getting the mapping of postal codes to
#   districts based on postal code and district borders. This can be achieved by selecting, e.g., the map layers:
#   Paavo-postinumeroalueet 2020, Espoon tilastoalueet, and Kuntajako.
# - Posti's Postal Code Data File (PCF) for getting a listing of all postal codes for Espoo including those that aren't
#   tied to a certain geographical district (https://www.posti.fi/fi/asiakastuki/postinumerotiedostot)
# - Wikipedia (https://fi.wikipedia.org/wiki/Luettelo_Espoon_kaupunginosista) for a listing of Espoo's districts and
#   their postal codes
# NOTE! If you update this mapping, remember to also update the corresponding mapping in espooevents-frontend.
POSTAL_CODE_TO_PLACE_KEYWORD_ID = {
  # The names of the places in the comments are based on the postal code area name in the "Postinumero-kunta-avain"
  # file and the place keyword name in Espoo Events
  '02100': ['espoo:p54'],  # Tapiola -> Tapiola
  '02110': ['espoo:p54'],  # Otsolahti -> Tapiola
  '02120': ['espoo:p54'],  # Länsikorkee-Suvikumpu -> Tapiola
  '02130': ['espoo:p46'],  # Pohjois-Tapiola -> Pohjois-Tapiola
  '02140': ['espoo:p26'],  # Laajalahti -> Laajalahti
  '02150': ['espoo:p18', 'espoo:p44'],  # Otaniemi -> Keilaniemi, Otaniemi
  '02160': ['espoo:p59'],  # Westend -> Westend
  '02170': ['espoo:p7'],  # Haukilahti -> Haukilahti
  '02180': ['espoo:p35'],  # Mankkaa -> Mankkaa
  '02200': ['espoo:p39'],  # Niittykumpu -> Niittykumpu
  '02210': ['espoo:p43'],  # Olari -> Olari
  '02230': ['espoo:p36'],  # Matinkylä -> Matinkylä
  '02240': ['espoo:p43'],  # Friisilä -> Olari
  '02250': ['espoo:p8', 'espoo:p52'],  # Henttaa -> Henttaa, Suurpelto
  '02260': ['espoo:p11'],  # Kaitaa -> Kaitaa
  '02270': ['espoo:p5'],  # Finnoo-Eestinmalmi -> Finnoo
  '02280': ['espoo:p30', 'espoo:p42'],  # Malminmäki-Eestinlaakso -> Latokaski, Nöykkiö
  '02290': ['espoo:p43'],  # Puolarmetsän sairaala -> Olari
  '02300': ['espoo:p42'],  # Nöykkiönpuro -> Nöykkiö
  '02320': ['espoo:p4', 'espoo:p21'],  # Espoonlahti -> Espoonlahti, Kivenlahti
  '02330': ['espoo:p42', 'espoo:p48'],  # Saunalahti-Kattilalaakso -> Nöykkiö, Saunalahti
  '02340': ['espoo:p30'],  # Latokaski -> Latokaski
  '02360': ['espoo:p51'],  # Soukka -> Soukka
  '02380': ['espoo:p53'],  # Suvisaaristo -> Suvisaaristo
  '02600': ['espoo:p26', 'espoo:p31'],  # Etelä-Leppävaara -> Laajalahti, Leppävaara
  '02610': ['espoo:p20'],  # Kilo -> Kilo
  '02620': ['espoo:p13'],  # Karakallio -> Karakallio
  '02630': ['espoo:p19', 'espoo:p20'],  # Nihtisilta -> Kera, Kilo
  '02650': ['espoo:p31'],  # Pohjois-Leppävaara -> Leppävaara
  '02660': ['espoo:p32'],  # Lintuvaara -> Lintuvaara
  '02680': ['espoo:p32'],  # Uusmäki -> Lintuvaara
  '02710': ['espoo:p60'],  # Viherlaakso -> Viherlaakso
  '02720': ['espoo:p27'],  # Lähderanta -> Laaksolahti
  '02730': ['espoo:p30'],  # Jupperi -> Laaksolahti
  '02740': ['espoo:p15', 'espoo:p23'],  # Bemböle-Pakankylä -> Karvasmäki, Kunnarla
  '02750': ['espoo:p25', 'espoo:p35', 'espoo:p49'],  # Sepänkylä-Kuurinniitty -> Kuurinniitty, Mankkaa, Sepänkylä
  '02760': ['espoo:p2'],  # Tuomarila-Suvela -> Espoon keskus
  '02770': ['espoo:p2', 'espoo:p17', 'espoo:p37'],  # Espoon Keskus -> Espoon keskus, Kaupunginkallio, Muurala
  '02780': ['espoo:p3', 'espoo:p16', 'espoo:p24', 'espoo:p57'],  # Kauklahti -> Espoonkartano, Kauklahti, Kurttila, Vanttila  # noqa: E501
  '02810': ['espoo:p6', 'espoo:p14'],  # Gumböle-Karhusuo -> Gumböle, Karhusuo
  '02820': ['espoo:p22', 'espoo:p40', 'espoo:p41', 'espoo:p56'],  # Nupuri-Nuuksio -> Kolmperä, Nupuri, Nuuksio, Vanha-Nuuksio  # noqa: E501
  '02860': ['espoo:p50'],  # Siikajärvi -> Siikajärvi
  '02920': ['espoo:p38', 'espoo:p45', 'espoo:p55', 'espoo:p61'],  # Niipperi -> Niipperi, Perusmäki, Vanhakartano, Ämmässuo  # noqa: E501
  '02940': ['espoo:p1', 'espoo:p9', 'espoo:p10', 'espoo:p33', 'espoo:p47'],  # Lippajärvi-Järvenperä -> Bodom, Högnäs, Järvenperä, Lippajärvi, Röylä  # noqa: E501
  '02970': ['espoo:p12', 'espoo:p28', 'espoo:p34'],  # Kalajärvi -> Kalajärvi, Lahnus, Luukki
  '02980': ['espoo:p29', 'espoo:p58'],  # Lakisto -> Lakisto, Velskola
}


class Command(BaseCommand):
    """Creates a keyword set with Espoo's places and maps YSO keywords to custom Espoo place keywords.

    The mapping of the YSO keywords to custom Espoo keywords is done so that any imported events that have any of the
    YSO keywords specified in YSO_TO_ESPOO_PLACE_KEYWORD_MAPPING are also augmented with the corresponding custom
    Espoo place keywords. Of course, the existing importers could be modified to instead directly add the custom
    Espoo keywords instead of using this management command. However, then we'd need to modify multiple importers and
    the implementations of the existing importers would diverge from the upstream linkedevents repository. This could
    be more fragile since any future updates would need to take these changes into account. By making the update in
    this separate management command, the changes are better isolated from the existing functionality.

    Since some of the importers are run hourly, this management command should also be run hourly so that any imported
    events get augmented with the custom Espoo place keywords.
    """
    help = "Creates a keyword set with Espoo's places."
    help = (
     "Creates a keyword set with Espoo's places and maps YSO keywords to custom Espoo place keywords (this is meant "
     "to be run hourly)."
    )

    @lru_cache()
    def _get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError(f"keyword \"{keyword_id}\" does not exist")
        return keyword

    @transaction.atomic()
    def _create_espoo_place_keywords(self):
        logger.info('creating new Espoo place keywords...')

        for new_keyword in CUSTOM_ESPOO_PLACE_KEYWORDS:
            keyword_set, created = Keyword.objects.update_or_create(
                id=new_keyword['id'],
                defaults=new_keyword
            )
            if created:
                logger.info(f"created keyword {new_keyword['name_fi']} ({new_keyword['id']})")
            else:
                logger.info(f"keyword {new_keyword['name_fi']} ({new_keyword['id']}) already exists")

    @transaction.atomic()
    def _create_espoo_places_keyword_set(self):
        logger.info('creating Espoo places keyword set...')

        # create the set itself
        keyword_set, created = KeywordSet.objects.update_or_create(
            id=ESPOO_PLACE_KEYWORD_SET_DATA['id'],
            defaults=ESPOO_PLACE_KEYWORD_SET_DATA
        )
        if created:
            logger.info(f"created keyword set \"{ESPOO_PLACE_KEYWORD_SET_DATA['id']}\"")
        else:
            logger.info(f"keyword set \"{ESPOO_PLACE_KEYWORD_SET_DATA['id']}\" already exists")

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_dict in CUSTOM_ESPOO_PLACE_KEYWORDS:
            keyword = self._get_keyword_obj(keyword_dict['id'])

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                logger.info(f"added {keyword.name} ({keyword_dict['id']}) to the keyword set")

    @transaction.atomic()
    def _add_espoo_online_place_keyword_to_events(self):
        """Adds the Espoo online place keyword to remote events.

        In practice, this adds the 'espoo:p63' keyword to all events that have the YSO remote participation keyword
        'yso:p26626'.
        """
        logger.info('adding Espoo online place keyword to remote events...')

        espoo_online_place_keyword_obj = self._get_keyword_obj(ESPOO_ONLINE_PLACE_KEYWORD_ID)
        events_to_update = (
            Event.objects
            .filter(keywords__id=YSO_REMOTE_PARTICIPATION_KEYWORD_ID)
            .exclude(keywords__id=ESPOO_ONLINE_PLACE_KEYWORD_ID)
            .prefetch_related('keywords')
        )

        for event in events_to_update:
            # We only want to add place keywords to events that have not been edited by users so that we don't
            # accidentally overwrite any place keywords modified by a user
            if event.is_user_edited():
                continue

            event.keywords.add(espoo_online_place_keyword_obj)
            logger.info(f"added {espoo_online_place_keyword_obj} ({ESPOO_ONLINE_PLACE_KEYWORD_ID}) to {event}")

    def _is_espoo_district_place_keyword(self, keyword_id):
        return keyword_id.startswith('espoo:p') and keyword_id not in NON_DISTRICT_PLACE_KEYWORD_IDS

    def _add_espoo_district_keywords_based_on_postal_code(self, event):
        location_place_keyword_ids = POSTAL_CODE_TO_PLACE_KEYWORD_ID[event.location.postal_code]

        for keyword in event.keywords.all():
            # The location of the event might have changed if the event has been reimported. Thus, we remove any
            # existing Espoo place keywords from the event that don't correspond to the postal code's place
            # keywords.
            if self._is_espoo_district_place_keyword(keyword.id) and keyword.id not in location_place_keyword_ids:
                event.keywords.remove(keyword)
                logger.info(f"removed {keyword} ({keyword.id}) from {event}")

        for espoo_place_keyword_id in location_place_keyword_ids:
            espoo_place_keyword_obj = self._get_keyword_obj(espoo_place_keyword_id)

            if espoo_place_keyword_obj in event.keywords.all():
                continue

            event.keywords.add(espoo_place_keyword_obj)
            logger.info(f"added {espoo_place_keyword_obj} ({espoo_place_keyword_id}) to {event}")

    def _add_non_espoo_place_keyword(self, event):
        non_espoo_place_keyword_obj = self._get_keyword_obj(NON_ESPOO_PLACE_KEYWORD_ID)

        for keyword in event.keywords.all():
            # Remove any Espoo district place keywords
            if self._is_espoo_district_place_keyword(keyword.id):
                event.keywords.remove(keyword)
                logger.info(f"removed {keyword} ({keyword.id}) from {event}")

        if non_espoo_place_keyword_obj in event.keywords.all():
            return

        event.keywords.add(non_espoo_place_keyword_obj)
        logger.info(f"added {non_espoo_place_keyword_obj} ({NON_ESPOO_PLACE_KEYWORD_ID}) to {event}")

    @transaction.atomic()
    def _add_espoo_place_keywords_to_events_based_on_location(self):
        """Adds the Espoo district place keywords to events based on their postal code."""
        logger.info('adding Espoo district place keywords to events based on their postal code...')

        for event in Event.objects.filter(location__postal_code__isnull=False).prefetch_related('keywords'):
            # We only want to add place keywords to events that have not been edited by users so that we don't
            # accidentally overwrite any place keywords modified by a user
            if event.is_user_edited():
                continue

            # The events imported with the espoo importer already have the right Espoo place keywords
            if event.data_source.id == 'espoo':
                continue

            if event.location.postal_code in POSTAL_CODE_TO_PLACE_KEYWORD_ID:
                self._add_espoo_district_keywords_based_on_postal_code(event)
            else:
                self._add_non_espoo_place_keyword(event)

    def handle(self, *args, **options):
        # Espoo data source must be created if missing. Note that it is not necessarily the system data source.
        # If we are creating it, it *may* still be the system data source, so it must be user editable!
        espoo_data_source_defaults = {'user_editable': True}
        DataSource.objects.get_or_create(id=ESPOO_DATA_SOURCE_ID,
                                         defaults=espoo_data_source_defaults)
        self._create_espoo_place_keywords()
        self._create_espoo_places_keyword_set()
        self._add_espoo_online_place_keyword_to_events()
        self._add_espoo_place_keywords_to_events_based_on_location()
        logger.info('all done')
