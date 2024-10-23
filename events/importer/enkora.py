import html
import logging
import re
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Generator, Optional
from zoneinfo import ZoneInfo

import requests
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from django_orghierarchy.models import Organization

from events.importer.sync import ModelSyncher
from events.models import DataSource, Event, Keyword, Place

from .base import Importer, recur_dict, register_importer

logger = logging.getLogger(__name__)


@register_importer
class EnkoraImporter(Importer):
    name = "enkora"
    supported_languages = ["fi", "sv", "en"]
    EEST = ZoneInfo("Europe/Helsinki")

    ERRORS_ALLOWED_BEFORE_STOP = 20

    COURSE_CONTACT_PHONE = "+358 9 310 32623"
    COURSE_CONTACT_LINK = (
        "https://www.hel.fi/fi/paatoksenteko-ja-hallinto/liikuntaluuri"
    )
    COURSE_PROVIDER_CONTACT_INFO = "Helsingin Kaupunki - Liikuntaluuri"

    ALL_COURSES_KEYWORDS = {"yso:p916"}  # liikunta
    COURSES = "yso:p9270"  # kurssit

    SPORT_ACROBATICS = "yso:p1277"  # akrobatia [voimistelu]
    SPORT_ADAPTED_PE = "yso:p3093"  # erityisliikunta
    SPORT_BADMINTON = "yso:p16210"  # sulkapallo [palloilu]
    SPORT_BALANCE = "yso:p29667"  # tasapainoharjoittelu
    SPORT_BODY_CONTROL = "yso:p24041"  # kehonhallinta
    SPORT_BROOMSTICK = "yso:p19453"  # keppijumppa [voimistelu]
    SPORT_CANOEING = "yso:p12078"  # melonta [vesiurheilu]
    SPORT_CIRCUS = "yso:p27786"  # sirkuskoulut [taideoppilaitokset]
    SPORT_CHAIR_PE = "yso:p27829"  # tuolijumppa [kuntoliikunta]
    SPORT_GAMES = "yso:p6062"  # pelit
    SPORT_GROUP_EXERCISE = "yso:p26740"  # ryhmäohjaus; YSOssa ei ole ryhmäliikuntaa
    SPORT_GYM = "yso:p8504"  # kuntosalit [liikuntatilat]
    SPORT_DANCE_SPORT = "yso:p7153"  # tanssiurheilu
    SPORT_DANCING = "yso:p1278"  # tanssi
    SPORT_ICE_HOCKEY = "yso:p12697"  # jääkiekko
    SPORT_JUMPPA = "yso:p3708"  # kuntoliikunta
    SPORT_KETTLEBELL = "yso:p23895"  # kahvakuulat
    SPORT_MAILAPELIT = "yso:p18503"  # mailat [liikuntavälineet]
    SPORT_MUSICAL_EXERCISE = "yso:p1884"  # musiikkiliikunta
    SPORT_MUSCLE_CARE = "yso:p22296"  # lihashuolto
    SPORT_MUSCLE_FITNESS = "yso:p7382"  # lihaskunto
    SPORT_NORDIC_WALKING = "yso:p18572"  # sauvakävely
    SPORT_OUTDOOR_PE = "yso:p26619"  # ulkoliikunta
    SPORT_PADEL = "yso:p37760"  # padel [palloilu]
    SPORT_PARKOUR = "yso:p22509"  # parkour [urheilu]
    SPORT_PLAYGROUND = "yso:p8105"  # leikkipuistot
    SPORT_RELAXATION = "yso:p5234"  # rentoutus
    SPORT_RUNNING = "yso:p9087"  # juoksu
    SPORT_SQUASH = "yso:p16903"  # squash [palloilu]
    SPORT_SKATING = "yso:p1245"  # luistelu [talviurheilu]
    SPORT_STRETCHING = "yso:p7858"  # venyttely
    SPORT_STRENGTH_TRAINING = "yso:p16233"  # voimaharjoittelu
    SPORT_SWIMMING = "yso:p4330"  # uinti
    SPORT_SWIMMING_POOL = "yso:p9415"  # uimahallit
    SPORT_SWIMMING_CLASSES = "yso:p17551"  # uimakoulut
    SPORT_SWIMMING_SCHOOL = "yso:p29121"  # uimaopetus
    SPORT_TEMPPUJUMPPA = "yso:p17018"  # liikuntaleikit
    SPORT_TENNIS = "yso:p1928"  # tennis [palloilu]
    SPORT_TRACK_N_FIELD = "yso:p935"  # yleisurheilu
    SPORT_TRAMPOLINING = "yso:p22130"  # trampoliinivoimistelu [voimistelu]
    SPORT_WALKING = "yso:p3706"  # kävely
    SPORT_WATER_EXERCISE = "yso:p6433"  # vesiliikunta
    SPORT_WELL_BEING = "yso:p1947"  # hyvinvointi
    SPORT_WORKOUT_STAIRS = "yso:p38999"  # kuntoportaat
    SPORT_YOGA = "yso:p3111"  # jooga

    LANGUAGE_ENGLISH = "yso:p2573"
    LANGUAGE_SWEDISH = "yso:p12469"
    LANGUAGES_FOREIGN = {LANGUAGE_ENGLISH, LANGUAGE_SWEDISH}

    AUDIENCE_CHILDREN = "yso:p4354"  # lapset (ikäryhmät)
    AUDIENCE_ADULTS = "yso:p5590"  # aikuiset [ikään liittyvä rooli]
    AUDIENCE_SENIORS = "yso:p2433"  # ikääntyneet
    AUDIENCE_MEN = "yso:p8173"  # miehet
    AUDIENCE_WOMEN = "yso:p16991"  # naiset
    AUDIENCE_INTELLECTUAL_DISABILITY = "yso:p10060"  # kehitysvammaiset
    AUDIENCE_HEARING_IMPAIRED = "yso:p4106"  # kuulovammaiset
    AUDIENCE_PSYCHIATRIC_REHAB = "yso:p12297"  # mielenterveyskuntoutujat
    AUDIENCE_PRESCHOOLERS = "yso:p6915"  # leikki-ikäiset
    AUDIENCE_SHCOOL_AGE = "yso:p6914"  # kouluikäiset
    AUDIENCE_YOUNG_PEOPLE = "yso:p11617"  # nuoret
    AUDIENCE_SPECIAL_GROUPS = "yso:p17354"  # erityisryhmät
    AUDIENCES = {
        AUDIENCE_CHILDREN,
        AUDIENCE_ADULTS,
        AUDIENCE_SENIORS,
        AUDIENCE_MEN,
        AUDIENCE_WOMEN,
        AUDIENCE_INTELLECTUAL_DISABILITY,
        AUDIENCE_HEARING_IMPAIRED,
        AUDIENCE_PSYCHIATRIC_REHAB,
        AUDIENCE_PRESCHOOLERS,
        AUDIENCE_SHCOOL_AGE,
        AUDIENCE_YOUNG_PEOPLE,
        AUDIENCE_SPECIAL_GROUPS,
    }

    PROVIDER = {
        "fi": "Helsingin kaupungin liikuntapalvelut",
        "sv": "Helsingfors stads idrottsservicen",
        "en": "City of Helsinki Sports Services",
    }
    ORGANIZATION = "ahjo:u021600"
    DATASOURCE_ORGANIZATION = "kuva-liikunta"

    service_map = {
        99: {
            "enkora-name": "Ryhmäliikunta",
            "keywords": {SPORT_GROUP_EXERCISE, COURSES},
            "image": "https://liikunta.hel.fi/shared-assets/images/"
            "event_placeholder_D.jpg",
        },
        100: {
            "enkora-name": "Uimakoulut",
            "keywords": {SPORT_SWIMMING_CLASSES, SPORT_SWIMMING_SCHOOL, COURSES},
            "image": "https://liikunta2.content.api.hel.fi/uploads/sites/9/2024/06/"
            "a1ed6f25-enkora-alapoista-uimakoulut.jpg",
        },
        101: {
            "enkora-name": "EasySport",
            "keywords": set(),
            "image": None,
        },  # Huom! Laji voi olla ihan mitä vaan
        102: {
            "enkora-name": "Vesiliikunta",
            "keywords": {"yso:p6433", COURSES},
            "image": "https://liikunta2.content.api.hel.fi/uploads/sites/9/2024/06/"
            "6fac6902-enkora-alapoista-vesiliikunta.jpg",
        },
        125: {
            "enkora-name": "EasySport, kausi",
            "keywords": set(),
            "image": None,
        },  # Huom! Laji voi olla ihan mitä vaan
        132: {
            "enkora-name": "Kuntosalikurssit",
            "keywords": {SPORT_GYM, COURSES},
            "image": "https://liikunta2.content.api.hel.fi/uploads/sites/9/2024/06/"
            "4826efdc-enkora-alapoista-kuntosalikurssit.jpg",
        },
        133: {
            "enkora-name": "Sovellettu liikunta",
            "keywords": {
                SPORT_ADAPTED_PE  # YSO: erityisliikunta, sisältää mm. soveltava liikunta  # noqa: E501
            },
            "image": None,
        },
    }

    audience_tag_map = {
        1: {
            "enkora-name": "Lapset, nuoret ja perheet",
            "keywords": {AUDIENCE_CHILDREN},
        },
        2: {"enkora-name": "Työikäiset", "keywords": {AUDIENCE_ADULTS}},
        3: {"enkora-name": "Seniorit", "keywords": {AUDIENCE_SENIORS}},
        4: {
            "enkora-name": "Soveltavaliikunta",
            "keywords": {SPORT_ADAPTED_PE},
        },  # erityisliikunta
        5: {"enkora-name": "Aikuiset", "keywords": {AUDIENCE_ADULTS}},
        6: {"enkora-name": "Juniorit (alle 20-vuotiaat)", "keywords": set()},
        7: {"enkora-name": "Erityisryhmät", "keywords": {AUDIENCE_SPECIAL_GROUPS}},
        8: {
            "enkora-name": "Seniorit (yli 63-vuotiaat)",
            "keywords": {AUDIENCE_SENIORS},
        },
    }

    audience_age_map = (
        ((0, 6), {AUDIENCE_CHILDREN, AUDIENCE_PRESCHOOLERS}),
        ((7, 16), {AUDIENCE_SHCOOL_AGE}),
        ((10, 18), {AUDIENCE_YOUNG_PEOPLE}),
        ((18, 200), {AUDIENCE_ADULTS}),
        ((63, 200), {AUDIENCE_SENIORS}),
    )

    place_map = {
        1: {
            "enkora-name": "Latokartanon liikuntahalli",  # 4 TPrek paikkaa
            "tprek-id": 72921,  # tprek-id appears to have changed
            "keywords": set(),
        },
        2: {
            "enkora-name": "Itäkeskuksen uimahalli",  # 4 TPrek paikkaa
            "tprek-id": 41835,
            "keywords": set(),  # kuntosalikursseja, ryhmäliikuntaa, vesiliikuntaa ja uimakouluja  # noqa: E501
        },
        3: {
            "enkora-name": "Jakomäen uimahalli",  # 2 TPrek paikkaa
            "tprek-id": 40838,
            "keywords": set(),  # kuntosalikursseja, vesiliikuntaa ja uimakouluja
        },
        4: {"enkora-name": "Liikuntamylly", "tprek-id": 45927, "keywords": set()},
        5: {
            "enkora-name": "Uimastadion",  # 15 TPrek paikkaa
            "tprek-id": 41047,
            "tprek-name": "Uimastadion / Maauimala",
            "keywords": set(),  # ryhmäliikuntaa, vesiliikuntaa ja uimakouluja
        },
        6: {
            "enkora-name": "Kumpulan maauimala",  # 6 TPrek paikkaa
            "tprek-id": 40823,
            "keywords": set(),  # vesiliikuntaa ja uimakouluja
        },
        7: {
            "enkora-name": "Yrjönkadun uimahalli",  # 3 TPrek paikkaa
            "tprek-id": 41102,
            "keywords": set(),  # kuntosalikursseja, ryhmäliikuntaa, vesiliikuntaa ja uimakouluja  # noqa: E501
        },
        8: {
            "enkora-name": "Pirkkolan uimahalli",  # 2 TPrek paikkaa
            "tprek-id": 40774,
            "keywords": set(),  # kuntosalikursseja, ryhmäliikuntaa, vesiliikuntaa ja uimakouluja  # noqa: E501
        },
        10: {
            "enkora-name": "Töölön kisahalli",  # 17 TPrek paikkaa
            "tprek-id": 45925,
            "keywords": set(),
        },
        12: {
            "enkora-name": "Kontulan kuntokellari",  # 4 TPrek paikkaa
            "tprek-id": 45926,
            "keywords": set(),
        },
        15: {
            "enkora-name": "Oulunkylän liikuntapuisto",  # 13 TPrek paikkaa
            "tprek-id": 45651,
            "keywords": set(),
        },
        16: {
            "enkora-name": "Ruskeasuon liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45611,
            "keywords": set(),
        },
        17: {
            "enkora-name": "Maunulan liikuntahalli",  # 7 TPrek paikkaa
            "tprek-id": 45932,
            "keywords": set(),
        },
        18: {
            "enkora-name": "Pirkkolan Jäähalli",
            "tprek-id": 67714,
            "keywords": set(),
        },
        26: {
            "enkora-name": "Herttoniemenrannan liikuntahalli",
            "tprek-id": 40029,
            "keywords": set(),
        },
        27: {
            "enkora-name": "Kampin liikuntakeskus",  # 5 TPrek paikkaa
            "tprek-id": 45928,
            "keywords": set(),
        },
        28: {
            "enkora-name": "Katajanokan liikuntahalli",  # 4 TPrek paikkaa
            "tprek-id": 45929,
            "keywords": set(),
        },
        30: {
            "enkora-name": "Pirkkolan liikuntapuisto",  # 20 TPrek paikkaa
            "tprek-id": 45596,
            "keywords": set(),
        },
        32: {
            "enkora-name": "Talin liikuntapuisto",  # 12 TPrek paikkaa
            "tprek-id": 45658,
            "keywords": set(),
        },
        40: {
            "enkora-name": "Herttoniemen liikuntapuisto",  # 30 TPrek paikkaa
            "tprek-id": 45633,
            "keywords": set(),
        },
        43: {
            "enkora-name": "Jakomäen liikuntapuisto",  # 7 TPrek paikkaa
            "tprek-id": 45643,
            "keywords": set(),
        },
        46: {
            "enkora-name": "Brahenkenttä",  # 5 TPrek paikkaa
            "tprek-id": 41995,
            "keywords": set(),
        },
        47: {
            "enkora-name": "Kannelmäen liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45642,
            "keywords": set(),
        },
        51: {
            "enkora-name": "Kontulan liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45648,
            "keywords": set(),
        },
        54: {
            "enkora-name": "Kurkimäen liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45638,
            "keywords": set(),
        },
        58: {
            "enkora-name": "Laajasalon liikuntapuisto",  # 19 TPrek paikkaa
            "tprek-id": 45656,
            "keywords": set(),
        },
        62: {
            "enkora-name": "Latokartanon liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45650,
            "keywords": set(),
        },
        63: {
            "enkora-name": "Lauttasaaren liikuntapuisto",  # 16 TPrek paikkaa
            "tprek-id": 45660,
            "keywords": set(),
        },
        72: {
            "enkora-name": "Myllypuron liikuntapuisto",  # 14 TPrek paikkaa
            "tprek-id": 45604,
            "keywords": set(),
        },
        74: {
            "enkora-name": "Paloheinän ulkoilualue",  # 13 TPrek paikkaa
            "tprek-id": 45422,
            "keywords": set(),
        },
        82: {
            "enkora-name": "Puotilankenttä",  # 7 TPrek paikkaa
            # "tprek-id": 41678,  # Place has been deleted.
            "tprek-id": 64979,  # Puotilankenttä / Ulkokuntosali
            "keywords": set(),
        },
        83: {
            "enkora-name": "Roihuvuoren liikuntapuisto",  # 13 TPrek paikkaa
            "tprek-id": 45663,
            "keywords": set(),
        },
        93: {
            "enkora-name": "Tehtaanpuiston kenttä",  # 2 TPrek paikkaa
            "tprek-id": 41665,
            "keywords": set(),
        },
        96: {
            "enkora-name": "Töölön pallokenttä",  # 6 TPrek paikkaa
            "tprek-id": 41294,
            "keywords": set(),
        },
        99: {
            "enkora-name": "Vuosaaren liikuntapuisto",  # 8 TPrek paikkaa
            "tprek-id": 45655,
            "keywords": set(),
        },
        160: {
            "enkora-name": "Oulunkylän aa, OV, Teinintie 12",
            "tprek-id": 6674,
            "keywords": set(),
        },
        180: {
            "enkora-name": "Sakarinmäen pk, OV, Knutersintie 924",
            "tprek-id": 33979,
            "keywords": set(),
        },
        205: {
            "enkora-name": "Töölön aa, OV, Töölönkatu 41-45",
            "tprek-id": 7155,
            "keywords": set(),
        },
        216: {
            "enkora-name": "Helsingin Melontakeskus",
            "tprek-id": 41044,
            "keywords": {SPORT_CANOEING},
        },
        217: {
            "enkora-name": "Kampin palvelukeskus",  # 2 TPrek paikkaa
            "tprek-id": 1923,
            "keywords": set(),
        },
        218: {
            "enkora-name": "Maunula sorsapuisto",
            "tprek-id": None,
            "street-address": "Metsäpurontie 25",
            "city": "Helsinki",
            "zip-code": "00630",
            "epsg:4326": (60.22790426985482, 24.924536415379556),
            "keywords": set(),
        },
        220: {
            "enkora-name": "Kinaporin seniorikeskus",
            "tprek-id": 1940,
            "keywords": set(),
        },
        221: {
            "enkora-name": "Puotilan leikkiniitty",  # 3 TPrek paikkaa
            "tprek-id": 40074,
            "keywords": {SPORT_PLAYGROUND},
        },
        222: {
            "enkora-name": "Suuntimontien puisto",  # 2 TPrek paikkaa
            "tprek-id": 42246,
            "keywords": set(),
        },
        223: {
            "enkora-name": "Töölönlahden lähiliikuntapaikka",
            "tprek-id": 68749,
            "keywords": set(),
        },
        224: {
            "enkora-name": "Töölönlahden puisto",  # 4 TPrek paikkaa
            "tprek-id": 68740,
            "keywords": set(),
        },
        230: {
            "enkora-name": "Oulunkylän jäähalli",
            "tprek-id": 40256,
            "keywords": set(),
        },
        231: {
            "enkora-name": "Vuosaaren jäähalli",  # 3 TPrek paikkaa
            "tprek-id": 40601,
            "keywords": set(),
        },
        232: {
            "enkora-name": "Circus Helsinki",  # 2 TPrek paikkaa
            "tprek-id": 20898,
            "keywords": set(),
        },
        233: {
            "enkora-name": "Paloheinän jäähalli",  # 2 TPrek paikkaa
            "tprek-id": 41623,
            "keywords": set(),
        },
        234: {
            "enkora-name": "Talihalli",  # 4 TPrek paikkaa
            "tprek-id": 41974,
            "keywords": set(),
        },
        235: {
            "enkora-name": "Malmin jäähalli",
            "tprek-id": 40025,
            "keywords": set(),
        },
        236: {
            "enkora-name": "Salmisaaren jäähalli",
            "tprek-id": 40832,
            "keywords": set(),
        },
        237: {
            "enkora-name": "SmashCenter",  # 8 TPrek paikkaa
            "tprek-id": 41789,
            "tprek-name": "Smash Center",
            "keywords": set(),
        },
        238: {
            "enkora-name": "Tanssikoulu Footlight, keskusta",  # 2 TPrek paikkaa
            "tprek-id": 24339,
            "tprek-name": "Footlight-salit",
            "keywords": {SPORT_DANCING},
        },
        239: {
            "enkora-name": "Konalan jäähalli",
            "tprek-id": 42171,
            "keywords": set(),
        },
        240: {
            "enkora-name": "Myllypuron jäähalli",  # 2 TPrek paikkaa
            "tprek-id": 40227,
            "keywords": set(),
        },
        241: {
            "enkora-name": "Hernesaaren jäähalli",
            "tprek-id": 41820,
            "keywords": set(),
        },
        242: {
            "enkora-name": "Sirkuskoulu Perhosvoltti",
            "tprek-id": None,
            "street-address": "Loisteputki 4 C (2. krs)",
            "city": "Helsinki",
            "zip-code": "00750",
            "epsg:4326": (60.28009905444841, 25.01913033251879),
            "keywords": set(),
        },
        243: {
            "enkora-name": "Töölön palvelukeskus",
            "tprek-id": 11407,
            "keywords": set(),
        },
        244: {
            "enkora-name": "Tanssikoulu Footlight, Lauttasaari",
            "tprek-id": None,
            "epsg:4326": (60.151487631902505, 24.880141113484108),
            "keywords": {SPORT_DANCING},
        },
        245: {
            "enkora-name": "Helsinginkadun uimahalli",
            "tprek-id": 40731,
            "tprek-name": "Helsingin urheilutalo / Urheiluhallit Kallio / Uimahalli",
            "keywords": {SPORT_SWIMMING, SPORT_SWIMMING_POOL},
        },
        246: {
            "enkora-name": "Pohjoinen",
            "tprek-id": None,
            "keywords": set(),
            "group": True,  # Note: groups in Enkora are not actual geographical locations  # noqa: E501
        },
        247: {
            "enkora-name": "Länsi",
            "tprek-id": None,
            "keywords": set(),
            "group": True,  # Note: groups in Enkora are not actual geographical locations  # noqa: E501
        },
        248: {
            "enkora-name": "Itä",
            "tprek-id": None,
            "keywords": set(),
            "group": True,  # Note: groups in Enkora are not actual geographical locations  # noqa: E501
        },
        257: {
            "enkora-name": "Malmin pk, OV, Talvelantie 1",
            "tprek-id": 46604,
            "keywords": set(),
        },
        258: {
            "enkora-name": "Merilahden pk, OV, Kallvikinniementie 1",
            "tprek-id": 51489,
            "keywords": set(),
        },
        262: {
            "enkora-name": "Käpylän pk, IV, Untamontie 2, Remontissa 2023-25",
            "tprek-id": 51480,
            "keywords": set(),
        },
        279: {
            "enkora-name": "Haagan pelastusasema",
            "tprek-id": 42248,
            "keywords": set(),
        },
        280: {
            "enkora-name": "Kaarelan jäähalli",
            "tprek-id": 59313,
            "keywords": set(),
        },
        281: {
            "enkora-name": "Kauppakeskus Redi, Gymi Redi",
            "tprek-id": 58441,
            "keywords": set(),
        },
        282: {
            "enkora-name": "Parkour Akatemia",  # 3 TPrek paikkaa
            "tprek-id": 72408,
            "keywords": set(),
        },
        284: {
            "enkora-name": "Pitäjänmäen peruskoulu",
            "tprek-id": 6994,
            "keywords": set(),
        },
        285: {
            "enkora-name": "Pirkkolan lähiliikuntapaikka",  # kts. Pirkkolan liikuntapuisto  # noqa: E501
            "tprek-id": 42006,
            "keywords": set(),
        },
        287: {
            "enkora-name": "Oltermannikeskus",  # 2 TPrek paikkaa
            "tprek-id": 65002,
            "keywords": set(),
        },
        288: {
            "enkora-name": "Taitoliikuntakeskus",
            "tprek-id": 41314,
            "keywords": set(),
        },
        294: {
            "enkora-name": "Herttoniemen portaat",
            "tprek-id": 57430,
            "tprek-name": "Länsi-Herttoniemen kuntoportaat",
            "keywords": {SPORT_WORKOUT_STAIRS},
        },
        297: {
            "enkora-name": "Rastilan leirintäalue",  # 3 TPrek paikkaa
            "tprek-id": 7808,
            "keywords": set(),
        },
        302: {
            # kts. 257: Malmin pk, OV, Talvelantie 1
            "enkora-name": "Malmin peruskoulu (Talvelantie 1)",
            "tprek-id": 46604,
            "keywords": set(),
        },
        303: {
            # kts. 262: Käpylän pk, IV, Untamontie 2
            "enkora-name": "Käpylän peruskoulu (Untamontie 2)",
            "tprek-id": 51480,
            "keywords": set(),
        },
        310: {
            "enkora-name": "Heteniitynkenttä (Vuosaari)",  # 8 TPrek paikkaa
            "tprek-id": 40605,
            "keywords": set(),
        },
        318: {
            "enkora-name": "Kuntosali Fabian, Fabianinkatu 21, -K2 kerros",
            "tprek-id": None,
            "street-address": "Fabianinkatu 21",
            "city": "Helsinki",
            "zip-code": "00130",
            "epsg:4326": (60.16631379895938, 24.94999595581348),
            "keywords": set(),
        },
        325: {
            # Replacing ELIXIA Ruoholahti / Kuntokeskus (tprek:40101) for Enkora courses
            # as it can't be displayed on liikunta.hel.fi because of contractual reasons
            "enkora-name": "Kuntosali Ruoholahti, Itämerenkatu 21, 4.krs.",
            "tprek-id": None,
            "street-address": "Itämerenkatu 21",
            "city": "Helsinki",
            "zip-code": "00180",
            "epsg:4326": (60.16377733194139, 24.91081911419979),
            "keywords": {SPORT_GYM},
        },
        327: {
            "enkora-name": "Perhetalo Unikko",
            "tprek-id": None,
            "street-address": "Unikkotie 8",
            "city": "Helsinki",
            "zip-code": "00720",
            "epsg:4326": (60.24545426653339, 24.99044444303867),
            "keywords": set(),
        },
    }

    description_word_map = {
        "äijäjumppa": {AUDIENCE_MEN, SPORT_JUMPPA},
        (
            "uimakoulu",
            "tekniikkauimakoulu",
            "alkeisuimakoulu",
            "alkeisjatkouimakoulu",
            "jatkouimakoulu",
            "koululaisuinti",
            "päiväkotiuinti",
            "uintitekniikka",
        ): {SPORT_SWIMMING_CLASSES},
        "nybörjarsim": {SPORT_SWIMMING_CLASSES, LANGUAGE_SWEDISH},
        "aikuisten": {AUDIENCE_ADULTS},
        ("naiset", "n"): {AUDIENCE_WOMEN},
        ("damer", "d"): {AUDIENCE_WOMEN, LANGUAGE_SWEDISH},
        ("miehet", "m"): {AUDIENCE_MEN},
        "työikäiset": {AUDIENCE_ADULTS},
        (
            "kuntosalin",
            "kuntosaliohjelman",
            "kuntosaliohjelmat",
            "kuntosalistartti",
            "kuntosalicircuit",
            "xxl_kuntosaliharjoittelu",
            "gym",
        ): {SPORT_GYM},
        (
            "livvoima",
            "voima",
            "circuit",
            "core",
            "livcore",
            "livcircuit",
            "voimaharjoittelu",
        ): {SPORT_STRENGTH_TRAINING},
        "kehonhuolto": {SPORT_BALANCE, SPORT_MUSCLE_CARE, SPORT_STRETCHING},
        (
            "senioricircuit",
            "senioricore",
            "seniorikuntosalistartti",
            "seniorivoima",
        ): {AUDIENCE_SENIORS, SPORT_STRENGTH_TRAINING},
        (
            "seniorikehonhuolto",
            "seniorivkehonhuolto",
        ): {SPORT_BALANCE, AUDIENCE_SENIORS, SPORT_MUSCLE_CARE, SPORT_STRETCHING},
        (
            "tanssi",
            "dancemix",
            "lattarijumppa",
            "livlattarit",
            "showjazz",
            "tanssillinen",
        ): {SPORT_DANCING},
        (
            "senioritanssi",
            "seniorikuntotanssi",
            "seniorilattarijumppa",
            "seniorilattarit",
            "seniorilattari",
            "senioriltanssi",
            "senioritanssillinensyke",
        ): {SPORT_DANCING, AUDIENCE_SENIORS},
        ("jääkiekko", "hockey", "kiekkokoulu"): {SPORT_ICE_HOCKEY},
        ("luistelu", "luistelukoulu"): {SPORT_SKATING},
        "mailapelit": {SPORT_MAILAPELIT, SPORT_GAMES},
        ("melonta", "melonkurssi"): {SPORT_CANOEING},
        "padel": {SPORT_PADEL},
        "parkour": {SPORT_PARKOUR},
        ("sirkus", "sirkuslajit"): {SPORT_CIRCUS},
        "sulkapallo": {SPORT_BADMINTON},
        "akrobatia": {SPORT_ACROBATICS},
        "squash": {SPORT_SQUASH},
        "tramppa": {SPORT_TRAMPOLINING},
        "tennis": {SPORT_TENNIS},
        "yleisurheilukoulu": {SPORT_TRACK_N_FIELD},
        (
            "aquapolo",
            "vesiliikunta",
            "vesiseikkailu",
            "hallivesijumppa",
            "vesijumppa",
            "syvänveden",
            "syvänvedenvesijumppa",
            "vesijuoksu",
            "vesitreeni",
        ): {SPORT_WATER_EXERCISE},
        "erityislasten": {SPORT_ADAPTED_PE},
        "kuntosaliharjoittelu": {
            SPORT_GYM,
            SPORT_STRENGTH_TRAINING,
            SPORT_MUSCLE_FITNESS,
        },
        "konditionssal": {
            SPORT_GYM,
            LANGUAGE_SWEDISH,
            SPORT_STRENGTH_TRAINING,
            SPORT_MUSCLE_FITNESS,
        },
        (
            "hyväolo",
            "hyvänolonjumppa",
            "livhyväolo",
        ): {SPORT_RELAXATION, SPORT_WELL_BEING, SPORT_JUMPPA},
        (
            "jumppakortti",
            "kesäjumppa",
            "kevytjumppa",
            "kiinteytys",
            "kuntojumppa",
            "livkevytjumppa",
            "livsyke",
            "maratonjumppa",
            "selkähuolto",
            "selkätunti",
            "jumppa",
            "sunnuntaijumppa",
            "syke",
            "voimajumppa",
        ): {SPORT_JUMPPA},
        "kroppsvård": {SPORT_JUMPPA, LANGUAGE_SWEDISH},
        (
            "temppujumppa",
            "temppuhulinat",
            "tempputaito",
        ): {SPORT_TEMPPUJUMPPA, AUDIENCE_CHILDREN},
        ("seniorijumppa", "seniorikevytjumppa", "seniorikuntojumppa", "seniorisyke"): {
            SPORT_JUMPPA,
            AUDIENCE_SENIORS,
        },
        "seniorikeppijumppa": {SPORT_BROOMSTICK, AUDIENCE_SENIORS},
        ("seniorit", "seniori"): {AUDIENCE_SENIORS},
        "seniorer": {AUDIENCE_SENIORS, LANGUAGE_SWEDISH},
        "juoksukoulu": {SPORT_RUNNING},
        ("kahvakuula", "livkahvakuula"): {SPORT_KETTLEBELL, SPORT_STRENGTH_TRAINING},
        "seniorikahvakuula": {
            SPORT_KETTLEBELL,
            AUDIENCE_SENIORS,
            SPORT_STRENGTH_TRAINING,
        },
        ("kehitysvammaiset", "kehitysvammaisten", "kehitysvammaise"): {
            AUDIENCE_INTELLECTUAL_DISABILITY,
            SPORT_ADAPTED_PE,
        },
        ("kuulonäkövammaiset", "kuulovammaiset", "kuulovammais", "kuulovammaisten"): {
            AUDIENCE_HEARING_IMPAIRED,
            SPORT_ADAPTED_PE,
        },
        ("mielenterveyskuntoutujat", "mielenterveyskuntoutu", "mielenterveysku"): {
            AUDIENCE_PSYCHIATRIC_REHAB,
            SPORT_ADAPTED_PE,
        },
        ("stretching", "venyttely", "livvenyttely"): {SPORT_STRETCHING},
        ("seniorivenytely", "seniorivenyttely"): {SPORT_STRETCHING, AUDIENCE_SENIORS},
        "kuntokävely": {SPORT_WALKING, SPORT_JUMPPA},
        ("jooga", "metsäjooga"): {SPORT_YOGA},
        (
            "ulkotreeni",
            "livulkotreeni",
            "puistojumppa",
            "ulkokuntosalistartti",
            "ulkoliikunta",
        ): {SPORT_OUTDOOR_PE},
        (
            "senioriulkojumppa",
            "senioriulkoliikunta",
            "senioriulkotreeni",
            "senioriulkovoima",
            "senioriuulkojumppa",
            "senioriuulkoliikunta",
        ): {SPORT_OUTDOOR_PE, AUDIENCE_SENIORS},
        "mammatreeni": {SPORT_JUMPPA, AUDIENCE_WOMEN},
        "porrastreeni": {SPORT_WORKOUT_STAIRS, SPORT_OUTDOOR_PE},
        "senioriporrastreeni": {
            SPORT_WORKOUT_STAIRS,
            AUDIENCE_SENIORS,
            SPORT_OUTDOOR_PE,
        },
        "kävely": {SPORT_WALKING, SPORT_OUTDOOR_PE},
        (
            "seniorikuntokävely",
            "seniorikuntokävelytreeni",
        ): {SPORT_OUTDOOR_PE, SPORT_WALKING, AUDIENCE_SENIORS},
        "sauvakävely": {SPORT_NORDIC_WALKING, SPORT_OUTDOOR_PE},
        "seniorisauvakävely": {
            SPORT_NORDIC_WALKING,
            AUDIENCE_SENIORS,
            SPORT_OUTDOOR_PE,
        },
        "seniorisäestys": {AUDIENCE_SENIORS, SPORT_MUSICAL_EXERCISE, SPORT_JUMPPA},
        "seniorisäpinät": {AUDIENCE_SENIORS},
        "senioriteema": {AUDIENCE_SENIORS},
        "tuolijumppa": {SPORT_CHAIR_PE, SPORT_JUMPPA},
        "stolgymnastik": {SPORT_CHAIR_PE, LANGUAGE_SWEDISH, SPORT_JUMPPA},
        "ulkovoima": {SPORT_OUTDOOR_PE, SPORT_STRENGTH_TRAINING},
        "uteträning": {SPORT_OUTDOOR_PE, LANGUAGE_SWEDISH, SPORT_JUMPPA},
        "vattengymnastik": {SPORT_WATER_EXERCISE, LANGUAGE_SWEDISH},
        ("veteraanit", "veteraani"): {AUDIENCE_SENIORS},
        "krigsveteraner": {AUDIENCE_SENIORS, LANGUAGE_SWEDISH},
        "seniorikiertoharjoittelu": {SPORT_STRENGTH_TRAINING, AUDIENCE_SENIORS},
        "seniorcirkelträning": {
            SPORT_STRENGTH_TRAINING,
            AUDIENCE_SENIORS,
            LANGUAGE_SWEDISH,
        },
        "kiertoharjoittelu": {SPORT_STRENGTH_TRAINING},
    }
    description_phrase_map = {
        "opetuskieli englanti": {LANGUAGE_ENGLISH},
        "på svenska": {LANGUAGE_SWEDISH},
        "foam roller": {SPORT_BODY_CONTROL},
        "75 vuotiaat": {AUDIENCE_SENIORS},
        "xxl-startti": {SPORT_GYM},
    }

    liikuntakauppa_link_base = "https://liikuntakauppa.hel.fi/helsinginkaupunki/ng/shop"
    liikuntakauppa_links = {
        99: f"{liikuntakauppa_link_base}/reservations/99/-/-/-/-/-/",
        100: f"{liikuntakauppa_link_base}/reservations/100/-/-/-/-/-/",
        102: f"{liikuntakauppa_link_base}/reservations/102/-/-/-/-/-/",
        132: f"{liikuntakauppa_link_base}/reservations/132/-/-/-/-/-/",
        "": f"{liikuntakauppa_link_base}/home",
    }

    def __init__(self, options) -> None:
        self.data_source = None
        self.publisher_datasource = None
        self.organization = None
        self.datasource_organization = None
        super().__init__(options)

        self.now_tz_is = timezone.now()
        self.driver_cls = Kurssidata

        self.debug_print_cache_invalidation = False

    def setup(self) -> None:
        logger.debug("Running Enkora importer setup...")

        defaults = dict(name="Enkora")
        self.data_source, _ = DataSource.objects.get_or_create(
            id=self.name, defaults=defaults
        )
        org_args = dict(origin_id="enkora", data_source=self.data_source)
        self.datasource_organization, _ = Organization.objects.get_or_create(
            defaults=defaults, **org_args
        )

        org_parts = EnkoraImporter.ORGANIZATION.split(":")
        ds_args = dict(id=org_parts[0])
        defaults = dict(name=org_parts[0].capitalize())
        self.publisher_datasource, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )
        org_args = dict(origin_id=org_parts[1], data_source=self.publisher_datasource)
        defaults = dict(name="Liikuntaan aktivointi")
        self.organization, _ = Organization.objects.get_or_create(
            defaults=defaults, **org_args
        )

        if self.options.get("remap", None):
            # This will prevent deletion checking, marking all deleted places as deleted
            # again and remapping them accordingly! Otherwise, places already deleted
            # will not be remapped by the syncher.
            self.check_deleted = lambda x: False

    @staticmethod
    def _get_timestamps() -> tuple[datetime, datetime]:
        """
        Return current time /w time zone.
        Note: This tiny method can be easily mocked during testing.
        :return:
        """
        return datetime.now(), timezone.now()

    def import_courses(self, months_back_from_today: int = 5) -> None:
        """
        Handles importing courses from Enkora API.
        :param: months_back_from_today, int determines how many months back from today data should be queried
        :return: None
        """  # noqa: E501
        kurssi_api = self.driver_cls(
            settings.ENKORA_API_USER, settings.ENKORA_API_PASSWORD, request_timeout=20.0
        )

        now_is, self.now_tz_is = self._get_timestamps()

        first_date = now_is.date() - relativedelta(months=months_back_from_today)
        last_date = now_is.date() + relativedelta(days=365)
        reservation_event_groups = []
        reservation_events = []

        # Round #1: past data
        for _ in kurssi_api.get_data_for_date_range(
            first_date,
            now_is,
            reservation_event_groups,
            reservation_events,
        ):
            # Skip reservations, they're not relevant here.
            pass

        # Round #2: future data
        for _ in kurssi_api.get_data_for_date_range(
            now_is,
            last_date,
            reservation_event_groups,
            reservation_events,
        ):
            # Skip reservations, they're not relevant here.
            pass

        # Fold a list of intoa a mapping dictionary per ID of the course
        reservation_event_groups = {
            reg["reservation_event_group_id"]: reg for reg in reservation_event_groups
        }

        # Fold sub-events inside the super-events
        for event in reservation_events:
            reservation_event_group_id = event["reservation_event_group_id"]
            reservation_event_group = reservation_event_groups[
                reservation_event_group_id
            ]
            if "reservation_events" not in reservation_event_group:
                reservation_event_group["reservation_events"] = []
            reservation_event_group["reservation_events"].append(event)

        # Start sync
        event_syncher = ModelSyncher(
            Event.objects.filter(data_source=self.data_source, super_event=None),
            lambda event: event.id,
            delete_func=self.mark_deleted,
            check_deleted_func=self.check_deleted,
        )

        # Now we have the course list populated, iterate it.
        if self.options["single"]:
            logger.info(
                "Requested sync of a single course: {}".format(self.options["single"])
            )

        course_count = 0
        course_event_count = 0
        course_sync_count = 0
        errors = []
        for course_id, course in reservation_event_groups.items():
            course_count += 1
            logger.debug("{}) Enkora course ID {}".format(course_count, course_id))
            if self.options["single"]:
                course_id = "enkora:{}".format(course["reservation_event_group_id"])
                if course_id != self.options["single"]:
                    # Single course was requested and this isn't it.
                    continue
            if self._is_course_expired(course, now_is):
                logger.debug(
                    "Skipping event with public visibility ended at: {}".format(
                        course["public_visibility_end"]
                    )
                )
                continue
            # Convert a course into Linked Event
            # Conversion can fail. Failures will be raised at end of iteration
            try:
                event_data, sub_events = self._handle_course(course)
            except Exception as exc:
                errors.append(exc)
                if len(errors) > self.ERRORS_ALLOWED_BEFORE_STOP:
                    logging.exception(
                        "Event conversion failed {} times. Stop iterating.".format(
                            len(errors)
                        )
                    )
                    raise
                logging.debug("Soft-fail: conversion failed. Continue iteration.")
                continue

            event = self.save_event(event_data)
            event_syncher.mark(event)
            old_sub_event_count = event.sub_events.count()

            # Sub-events:
            sub_event_syncher = ModelSyncher(
                event.sub_events.filter(deleted=False),
                lambda event: event.id,
                delete_func=self.mark_deleted_sub_event,
                check_deleted_func=self.check_deleted,
            )

            event._changed = False
            for sub_event_data in sub_events:
                sub_event_data["super_event"] = event

                sub_event = self.save_event(sub_event_data)
                if sub_event._changed:
                    event._changed = True
                sub_event_syncher.mark(sub_event)

            sub_event_syncher.finish(force=True)

            course_event_count += event.sub_events.count()
            if event.sub_events.count() != old_sub_event_count:
                event._changed = True

            if event._changed:
                event.save()

            course_sync_count += 1

        # After looping all the courses, delete the obsoleted ones (unless doing a
        # single event).
        event_syncher.finish(force=True)

        # Delayed conversion exception?
        if errors:
            logger.error(
                "Enkora course import finished with {} courses with {} events seen. {} courses synchronized. "  # noqa: E501
                "{} errors encounterd.".format(
                    course_count, course_event_count, course_sync_count, len(errors)
                )
            )
            raise errors[0]

        # Success
        logger.info(
            "Enkora course import finished with {} courses with {} events seen. {} courses synchronized. "  # noqa: E501
            "No errors encounterd.".format(
                course_count, course_event_count, course_sync_count
            )
        )

    def mark_deleted(self, event: Event) -> bool:
        if event.deleted:
            return False
        if event.end_time < self.now_tz_is:
            return False
        if self.options["single"]:
            # Don't delete events on single sync
            return False

        # Event expired, mark it deleted
        event.soft_delete()
        for sub_event in event.sub_events.all():
            sub_event.soft_delete()

        return True

    def mark_deleted_sub_event(self, event: Event) -> bool:
        if event.deleted:
            return False
        if event.end_time < self.now_tz_is:
            return False

        # Event expired, mark it deleted
        event.soft_delete()
        for sub_event in event.sub_events.all():
            sub_event.soft_delete()

        return True

    def check_deleted(self, event: Event) -> bool:
        if self.options["single"]:
            # Don't delete events on single sync
            return False

        return event.deleted

    def import_places(self, months_back_from_today: int = 5):
        kurssi_api = self.driver_cls(
            settings.ENKORA_API_USER, settings.ENKORA_API_PASSWORD, request_timeout=20.0
        )

        now_is, self.now_tz_is = self._get_timestamps()

        first_date = now_is.date() - relativedelta(months=months_back_from_today)
        last_date = now_is.date() + relativedelta(days=365)
        reservation_event_groups = []
        reservation_events = []

        # Round #1: past data
        for _ in kurssi_api.get_data_for_date_range(
            first_date, now_is, reservation_event_groups, reservation_events
        ):
            # Skip reservations, they're not relevant here.
            pass

        # Round #2: future data
        for _ in kurssi_api.get_data_for_date_range(
            now_is, last_date, reservation_event_groups, reservation_events
        ):
            # Skip reservations, they're not relevant here.
            pass

        # Fold a list of into a mapping dictionary per ID of the course
        reservation_event_groups = {
            reg["reservation_event_group_id"]: reg for reg in reservation_event_groups
        }

        course_count = 0
        place_count = 0
        places_done = set()
        for course_id, course in reservation_event_groups.items():
            course_count += 1
            logger.debug("{}) Enkora course ID {}".format(course_count, course_id))
            if self.options["single"]:
                course_id = "enkora:{}".format(course["reservation_event_group_id"])
                if course_id != self.options["single"]:
                    # Single course was requested and this isn't it.
                    continue

            if self._is_course_expired(course, now_is):
                logger.debug(
                    "Skipping event with public visibility ended at: {}".format(
                        course["public_visibility_end"]
                    )
                )
                continue

            # Location:
            if course["location_id"] not in EnkoraImporter.place_map:
                raise ValueError(
                    "Unknown Enkora location: {} for course {} / {}. Mapping missing!".format(  # noqa: E501
                        course["location_id"],
                        course["reservation_event_group_id"],
                        course["reservation_event_group_name"],
                    )
                )

            location_mapping = EnkoraImporter.place_map[course["location_id"]]
            if location_mapping["tprek-id"]:
                # Skip TPrek places
                continue

            if "street-address" not in location_mapping:
                # Skip non-Enkora places
                continue

            if course["location_id"] in places_done:
                continue

            # For any non-TPR Place, we'll create an own place. Make sure data exists.
            place_count += 1
            self._handle_place(course["location_id"], location_mapping)
            places_done.add(course["location_id"])

        # Success
        logger.info(
            "Enkora place import finished with {} courses having {} unique Enkora-places. No errors encounterd.".format(  # noqa: E501
                course_count, place_count
            )
        )

    @staticmethod
    def _is_course_expired(course: dict, now_is: datetime) -> bool:
        """
        Checks based on Enkora course public visiblity dates that a course isn't expired.
        :param: course, dict containing data for a course
        :param: now_is, datetime.datetime current
        :return: bool, true if now isn't between public_visibility_start and public_visibility_end
        """  # noqa: E501
        if not course["public_visibility_start"] or not course["public_visibility_end"]:
            logger.warning(
                "Course with ID {} lacks public_visibility_start or public_visibility_end information.".format(  # noqa: E501
                    course["reservation_event_group_id"]
                )
            )
            return True  # True, indicating that course shouldn't be processed before source data is valid  # noqa: E501

        is_expired = not (
            course["public_visibility_start"]
            <= now_is
            <= course["public_visibility_end"]
        )

        return is_expired

    @staticmethod
    def generate_documentation_md() -> str:  # noqa: C901
        """
        Generate MarkDown document out of Enkora importing rules.
        :return: documentation string
        """
        import git  # gitpython
        from snakemd import Inline, MDList, Paragraph, new_doc

        repo = git.Repo(search_parent_directories=True)
        commit_sha = repo.head.object.hexsha

        yso_base_url = r"https://finto.fi/yso/fi/page/{}"
        tprek_base_url = r"https://palvelukartta.hel.fi/fi/unit/{}"
        doc = new_doc()
        doc.add_heading("Linked Events - Enkora Course importer", level=1)

        # Section 0:
        # Meta section
        now = datetime.utcnow()
        now_str = now.strftime("%Y-%m-%d %H:%M UTC")
        doc.add_paragraph(f"Document generated at: {now_str}")
        doc.add_paragraph(f"Git commit: {commit_sha}")

        def _keyword_helper(mapping: set) -> list:
            kws = []
            for kw_id in mapping:
                try:
                    kw = Keyword.objects.get(id=kw_id)
                except ObjectDoesNotExist:
                    logger.error("Unknown keyword '{}'!".format(kw_id))
                    raise
                if kw.id.startswith("yso:"):
                    yso_id = kw.id[4:]
                    text = str(
                        Paragraph("[{}] {}".format(kw.id, kw.name)).insert_link(
                            kw.id, yso_base_url.format(yso_id)
                        )
                    )
                else:
                    text = "[{}] {}".format(kw.id, kw.name)
                kws.append(text)

            return kws

        # Section 0.6:
        # Contact information
        doc.add_heading("Course contact information", level=2)
        ul = []
        ul.append(
            "Liikuntaluuri, phone: {}".format(EnkoraImporter.COURSE_CONTACT_PHONE)
        )
        ul.append("Liikuntaluuri, link: {}".format(EnkoraImporter.COURSE_CONTACT_LINK))
        ul.append(
            "Event provider info: {}".format(
                EnkoraImporter.COURSE_PROVIDER_CONTACT_INFO
            )
        )
        doc.add_block(MDList(ul))

        # Section 0.7:
        # Common keywords
        doc.add_heading("Common YSO keywords", level=2)
        doc.add_paragraph("Importer adds a list of keywords to all imported courses.")
        ul = []
        for var_value in EnkoraImporter.ALL_COURSES_KEYWORDS:
            value_set = {var_value}
            kws = _keyword_helper(value_set)
            sport = str(Paragraph("Keyword: {}".format(kws[0])))
            ul.append(sport)

        doc.add_block(MDList(ul))

        # Section 0.8:
        # List of sport to YSO
        doc.add_heading("Sport to YSO", level=2)
        doc.add_paragraph(
            "Importer detects sport from: Location, Service or description text. "
            "All mapping and detection is done for the purpose of detecting for which "
            "sport/activity a course is about."
        )
        ul = []
        for var in vars(EnkoraImporter):
            if not var.startswith("SPORT_"):
                continue
            var_value = getattr(EnkoraImporter, var)
            value_set = {var_value}
            kws = _keyword_helper(value_set)
            sport = str(Paragraph("{}: {}".format(var[6:], kws[0])))
            ul.append(sport)

        doc.add_block(MDList(ul))

        # Section 0.9:
        # List of audience to YSO
        doc.add_heading("Audience to YSO", level=2)
        doc.add_paragraph(
            "Importer detects audience from: description text. "
            "Not all courses have audience."
        )
        ul = []
        for var in vars(EnkoraImporter):
            if not var.startswith("AUDIENCE_"):
                continue
            var_value = getattr(EnkoraImporter, var)
            value_set = {var_value}
            kws = _keyword_helper(value_set)
            audience = str(Paragraph("{}: {}".format(var[9:], kws[0])))
            ul.append(audience)

        doc.add_block(MDList(ul))

        # Section 1:
        # Places
        doc.add_heading("Enkora Locations to LE Places", level=2)
        doc.add_paragraph(
            "Importer detects Place from: Location. "
            "Additionally, a location can automatically indicate a sport/activity. "
            "Note: Typical locations are for multiple types of sport/activity. "
            "Note 2: Also non-TpRek Locations can be used."
        )
        ul = []
        for location_id, mapping in EnkoraImporter.place_map.items():
            item_text = Inline(
                "Location {}: {}:".format(location_id, mapping["enkora-name"])
            )
            ul.append(item_text)

            details = []
            if mapping["tprek-id"]:
                place_id = "tprek:{}".format(mapping["tprek-id"])
                try:
                    place = Place.objects.get(id=place_id)
                except Place.DoesNotExist:
                    logger.error("Unknown place '{}'!".format(place_id))
                    raise
                tprek = str(
                    Paragraph(
                        "Place: [{}] {}".format(place.id, place.name)
                    ).insert_link(place.id, tprek_base_url.format(mapping["tprek-id"]))
                )
            elif "street-address" in mapping:
                longitude = mapping["epsg:4326"][1]
                latitude = mapping["epsg:4326"][0]
                tprek = Inline(
                    "Non-Tprek place: {}, {}, {}. Coordinates: {}N, {}E".format(
                        mapping["street-address"],
                        mapping["city"],
                        mapping["zip-code"],
                        latitude,
                        longitude,
                    )
                )
            else:
                tprek = Inline("ERROR! not mapped to place", bold=True)
            details.append(tprek)
            if mapping["keywords"]:
                kws = _keyword_helper(mapping["keywords"])
                details.append(", ".join(kws))
            else:
                details.append(Inline("Note: not mapped to keywords", bold=False))
            ul.append(MDList(details))
        doc.add_block(MDList(ul))

        # Section 2:
        # Services
        doc.add_heading("Enkora Services to LE Keywords", level=2)
        doc.add_paragraph(
            "Importer detects sport from: Service. "
            "All mapping and detection is done for the purpose of detecting for which "
            "sport/activity a course is about."
        )
        ul = []
        for service_id, mapping in EnkoraImporter.service_map.items():
            item_text = "Service {} [{}]:".format(mapping["enkora-name"], service_id)
            ul.append(Inline(item_text))

            if mapping["keywords"]:
                kws = _keyword_helper(mapping["keywords"])
                details = ", ".join(kws)
            else:
                details = Inline("Warning: not mapped!", bold=True)

            image_url = mapping.get("image")
            if not image_url:
                image = "Image URL: -missing-"
            else:
                image = Paragraph("Image URL: {}".format(image_url)).insert_link(
                    image_url, image_url
                )
            ul.append(MDList([details, image]))

        doc.add_block(MDList(ul))

        # Section 3:
        # Audiences
        doc.add_heading("Enkora Audiences to LE Audience Keywords", level=2)
        doc.add_paragraph(
            "Importer detects audience from: Audience. "
            "In Enkora, audience is a weak data source. "
            "On typical case, audiences are detected from description text."
        )
        ul = []
        for service_id, mapping in EnkoraImporter.audience_tag_map.items():
            item_text = "Audience {} [{}]:".format(mapping["enkora-name"], service_id)
            ul.append(Inline(item_text))

            if mapping["keywords"]:
                kws = _keyword_helper(mapping["keywords"])
                details = ", ".join(kws)
            else:
                details = Inline("Warning: not mapped!", bold=True)
            ul.append(MDList([details]))

        doc.add_block(MDList(ul))

        # Section 4:
        # Description words and phrases
        doc.add_heading("Enkora Description to LE Keywords", level=2)
        doc.add_paragraph(
            "Importer detects sport and audience from: description text. "
            "Text is processed for phrases and single words."
        )
        ul = []
        for phrase, mapping in EnkoraImporter.description_phrase_map.items():
            item_text = (
                Paragraph("Phrase: '").add(Inline(phrase, italics=True)).add("':")
            )
            ul.append(item_text)

            kws = _keyword_helper(mapping)
            details = ", ".join(kws)
            ul.append(MDList([details]))

        for word, mapping in EnkoraImporter.description_word_map.items():
            item_text = None
            if isinstance(word, str):
                item_text = (
                    Paragraph("Word: '").add(Inline(word, italics=True)).add("':")
                )
            elif isinstance(word, tuple):
                item_text = Paragraph("Words: ")
                first = True
                for w in word:
                    if not first:
                        item_text.add(", '")
                    else:
                        item_text.add("'")
                        first = False
                    item_text.add(Inline(w, italics=True))
                    item_text.add("'")

            ul.append(item_text)

            kws = _keyword_helper(mapping)
            details = ", ".join(kws)
            ul.append(MDList([details]))

        doc.add_block(MDList(ul))

        # Section 5:
        # Registration links
        doc.add_heading("Enkora Service to Web Shop Link", level=2)
        doc.add_paragraph(
            "Importer sport/activity list mapping to Liikuntakauppa. "
            "Optimally the link would point directly to a course. Current implementation of "  # noqa: E501
            "liikuntakauppa doesn't allow this."
        )
        ul = []
        for service_id, link_url_base in EnkoraImporter.liikuntakauppa_links.items():
            link_url = "{}/<course-ID>".format(link_url_base)
            text = str(Paragraph("{}".format(link_url)).insert_link(link_url, link_url))

            item_text = "{}: {}:".format(service_id, text)
            ul.append(Inline(item_text))

        doc.add_block(MDList(ul))

        # Done!
        return str(doc)

    @transaction.atomic
    def _handle_course(self, course: dict) -> tuple[dict, list[dict]]:
        """
        Sample data:
        {
         'reservation_event_group_id': 32791,
         'reservation_event_group_name_fi': 'Koululaisuinti',
         'reservation_event_group_name_sv': '',
         'reservation_event_group_name_en': '',
         'created_timestamp': datetime.datetime(2021, 4, 13, 9, 54, 55),
         'created_user_id': 23698,
         'reservation_group_id': 32791,
         'reservation_group_name': 'Koululaisuinti',
         'description': 'Koululaisuinti',
         'description_fi': 'Koululaisuinti',
         'description_sv': '',
         'description_en': '',
         'description_long': None,
         'description_long_fi': None,
         'description_long_sv': None,
         'description_long_en': None,
         'description_form': None,
         'season_id': 24,
         'season_name': 'Kevät 2021',
         'public_reservation_start': datetime.datetime(2021, 1, 1, 0, 0),
         'public_reservation_end': datetime.datetime(2021, 1, 1, 0, 0),
         'public_visibility_start': datetime.datetime(2021, 1, 1, 0, 0),
         'public_visibility_end': datetime.datetime(2021, 1, 1, 0, 0),
         'instructor_visibility_start': None,
         'instructor_visibility_end': None,
         'is_course': True,
         'reservation_event_count': 1,
         'first_event_date': datetime.datetime(2021, 3, 1, 8, 0),
         'last_event_date': datetime.datetime(2021, 3, 1, 8, 0),
         'capacity': 0,
         'queue_capacity': 0,
         'service_id': 100,
         'service_name': 'Uimakoulut',
         'service_at_area_id': 691,
         'service_at_area_name': 'Uimakoulut at Pirkkolan uimahalli',
         'location_id': 8,
         'location_name': 'Pirkkolan uimahalli',
         'region_id': 2,
         'region_name': 'Pohjoinen',
         'reserved_count': None,
         'queue_count': None,
         'fare_products': None,
         'tags': [
                {'tag_id': '1', 'tag_name': 'Lapset, nuoret ja perheet',
                  'tag_group_id': '1', "tag_group_name": "Kohderyhmä"},
                {'tag_id': '45', 'tag_name': 'Suomeksi', 'tag_group_id': '5',
                  'tag_group_name': 'Ohjauskieli'}
            ]
        }
        Bonus:
        'reservation_events' containing all the dates and times of the event
        """

        capacity = 0
        remaining_capacity = 0
        capacity_full = None
        has_queue_capacity = None
        description = None
        sub_event_overrides = {}

        # Add time zone information
        dates = {}
        for field_name in (
            "first_event_date",
            "last_event_date",
            "public_visibility_start",
            "public_reservation_start",
            "public_reservation_end",
        ):
            if field_name not in course:
                dates[field_name] = None
            else:
                try:
                    dates[field_name] = timezone.make_aware(
                        course[field_name], EnkoraImporter.EEST
                    )
                except AttributeError:
                    logging.error(
                        (
                            "Enkora event ID {}: unable to add timezone info for field name {}"  # noqa: E501
                            ", skipping event and related sub-events"
                        ).format(
                            course["reservation_event_group_id"],
                            field_name,
                        )
                    )

        # Course capacity:
        if (
            course["capacity"]
            and isinstance(course["capacity"], int)
            and course["capacity"] > 0
        ):
            capacity = course["capacity"]
        if (
            capacity
            and course["reserved_count"]
            and isinstance(course["reserved_count"], int)
        ):
            remaining_capacity = capacity - course["reserved_count"]
            if remaining_capacity <= 0:
                capacity_full = True
            else:
                capacity_full = False
        if (
            capacity
            and course["queue_capacity"]
            and isinstance(course["queue_capacity"], int)
            and course["queue_count"]
            and isinstance(course["queue_count"], int)
        ):
            queue_capacity = course["queue_capacity"] - course["queue_count"]
            has_queue_capacity = queue_capacity > 0

        # Infer course language based on tag data
        language = self.infer_event_language(course["tags"])
        in_language = [self.languages[language]]

        # Course as dict, which can include translations
        sub_event_title, main_event_title = self.convert_title(course)

        # Enriched description, as HTML
        description = self.convert_description(
            course, capacity_full, has_queue_capacity
        )

        # Location
        location_data = self.convert_location(course)

        # Keywords
        location_kwids, service_kwids, images = self.convert_keywords(course)

        # Audience
        (
            audience_kwids,
            sport_kwids,
            audience_min_age,
            audience_max_age,
            liikuntakauppa_fi_link,
        ) = self.convert_audience(course)

        kw_ids = (
            self.ALL_COURSES_KEYWORDS | location_kwids | service_kwids | sport_kwids
        )
        keywords = self.keyword_ids_into_keywords(kw_ids)
        audience_keywords = self.keyword_ids_into_keywords(audience_kwids)

        keyword_types = []
        keyword_types += ["location"] if location_kwids else []
        keyword_types += ["service"] if service_kwids else []
        keyword_types += ["sport"] if sport_kwids else []
        keyword_types += ["audience"] if audience_kwids else []
        # More keyword types = more accurate
        keyword_accuracy = len(keyword_types) / 4
        if keyword_accuracy < 0.5:
            logging.warning(
                "Enkora event ID {0} '{1}': Poor mapping ({2:.0f}%) into keywords! "
                "Suggest improving mapping on: {3}".format(
                    course["reservation_event_group_id"],
                    course["reservation_event_group_name"].strip(),
                    keyword_accuracy * 100,
                    ", ".join(keyword_types),
                )
            )

        # Price [€ cents]
        offers = self.convert_price(course, liikuntakauppa_fi_link)

        # Wrapping up all details:
        event_data = {
            "type_id": Event.TypeId.COURSE,
            "name": {**main_event_title},
            "description": {**description},
            "audience_min_age": audience_min_age,
            "audience_max_age": audience_max_age,
            "audience": audience_keywords,
            "event_status": Event.Status.SCHEDULED,
            "start_time": dates["first_event_date"],
            "has_start_time": True,
            "end_time": dates["last_event_date"],
            "has_end_time": True,
            "date_published": dates["public_visibility_start"],
            # Obsoleted and should not be used anymore. Offers / URL replaces this.
            "external_links": None,  # {"fi": {"registration": liikuntakauppa_fi_link}},
            "provider": {**self.PROVIDER},
            "provider_contact_info": {
                "fi": self.COURSE_PROVIDER_CONTACT_INFO
            },  # ToDo: hard coded constant currently, needs to be extended upon? /AG
            "enrolment_start_time": dates["public_reservation_start"],
            "enrolment_end_time": dates["public_reservation_end"],
            "maximum_attendee_capacity": capacity,
            "extension_course": {
                # Note: base.Importer.save_event() has:
                # if "extension_course" in settings.INSTALLED_APPS:
                # Unless extension is enabled, this field will not be imported.
                "remaining_attendee_capacity": remaining_capacity,
            },
            "data_source": self.data_source,
            "origin_id": course["reservation_event_group_id"],
            "publisher": self.organization,
            "location": location_data,
            "location_extra_info": None,
            "keywords": keywords,
            "in_language": in_language,
            "offers": offers,
            "images": images,
        }

        # Sub-events:
        # Literally all Enkora courses are multi-event
        sub_event_overrides = {"name": {**sub_event_title}}
        _, sub_events = self.build_sub_events(course, event_data, sub_event_overrides)

        # For development/testing:
        # Output commands to invalidate event cache for the course being imported
        if self.debug_print_cache_invalidation:
            print(
                'curl --header "Content-Type: application/json" https://harrastukset.hel.fi/api/revalidate --data'  # noqa: E501
                """ '{{"secret": "", "uri": "/fi/courses/enkora:{}"}}' """.format(
                    course["reservation_event_group_id"]
                )
            )

        return event_data, sub_events

    def build_sub_events(
        self, course: dict, event_data: dict, overridden_event_data: dict
    ) -> tuple[dict, list[dict]]:
        """
        Enkora course consists of multiple events.
        Create the course's events as Linked Events sub-events.
        :param course: raw Enkora course data from API
        :param event_data: converted course data suitable for Linked Events storage,
                            Note: event_data dictionary will be mutated
        :return: event_data, altered with sub-events
        """

        sub_events = []

        for reservation_event in course["reservation_events"]:
            # Basis for all sub-events is the super-event
            sub_event_data = deepcopy(event_data)

            # Override?
            sub_event_data.update(overridden_event_data)

            if "super_event_type" in sub_event_data:
                del sub_event_data["super_event_type"]
            sub_event_data["super_event"] = None  # Note: This will be populated on save
            sub_event_data["start_time"] = timezone.make_aware(
                reservation_event["time_start"], EnkoraImporter.EEST
            )
            sub_event_data["end_time"] = timezone.make_aware(
                reservation_event["time_end"], EnkoraImporter.EEST
            )
            sub_event_data["origin_id"] = "{}_{}".format(
                course["reservation_event_group_id"],
                reservation_event["reservation_event_id"],
            )
            sub_events.append(sub_event_data)

        event_data["super_event_type"] = Event.SuperEventType.RECURRING

        return event_data, sub_events

    @staticmethod
    def convert_keywords(course: dict) -> tuple[set, set, list]:
        """
        Deduce a set of keywords from course data.
        Also convert service into an image
        Note: Course description is not part of this deduction, Service and location are.
        :param course:
        :return: set of keyword ids for service, set of keyword ids for audience, list of single image
        """  # noqa: E501
        if course["location_id"] not in EnkoraImporter.place_map:
            raise ValueError(
                "Unknown Enkora location: {} for course {} / {}. Mapping missing!".format(  # noqa: E501
                    course["location_id"],
                    course["reservation_event_group_id"],
                    course["reservation_event_group_name"],
                )
            )
        if course["service_id"] not in EnkoraImporter.service_map:
            raise ValueError(
                "Unknown Enkora service: {} for course {} / {}. Mapping missing!".format(  # noqa: E501
                    course["service_id"],
                    course["reservation_event_group_id"],
                    course["reservation_event_group_name"],
                )
            )

        location_mapping = EnkoraImporter.place_map[course["location_id"]]
        service_mapping = EnkoraImporter.service_map[course["service_id"]]

        # Images
        images = []
        if service_mapping["image"]:
            images.append(
                {
                    "name": service_mapping["enkora-name"],
                    "url": service_mapping["image"],
                }
            )

        return location_mapping["keywords"], service_mapping["keywords"], images

    @staticmethod
    def keyword_ids_into_keywords(kw_ids: set) -> list[Keyword]:
        # Convert the set of keywords into a list of Keyword-objects.
        # Note: Input set won't contain any duplicates.
        kws = []
        for kw_id in kw_ids:
            try:
                kw = Keyword.objects.get(id=kw_id)
            except (Keyword.DoesNotExist, ObjectDoesNotExist):
                logger.error("Unknown keyword '{}'!".format(kw_id))
                raise
            kws.append(kw)

        return kws

    @staticmethod
    def convert_title(course: dict) -> tuple[dict, Optional[dict]]:
        """
        Add information to course title about event hour and weekday
        :param course: dict, Enkora course information as returned from API
        :return: tuple[dict, Optional[dict]], dictionary of course titles
        and modified course titles in supported languages
        """
        course_title = {
            lang: course.get(f"reservation_event_group_name_{lang}")
            for lang in EnkoraImporter.supported_languages
        }

        # If there's no course title found for key:
        # reservation_event_group_name_fi, set the default one
        if not course_title["fi"]:
            course_title["fi"] = course.get("reservation_event_group_name")

        if not course["reservation_events"]:
            # This should never happen. A course typically has events.
            return (course_title, course_title)

        # Iterate course events and collect the weekdays
        start_times = {}
        weekdays = set()
        for event_idx, reservation_event in enumerate(course["reservation_events"]):
            start_time = reservation_event["time_start"].strftime("%H:%M")
            weekday = int(reservation_event["time_start"].strftime("%w"))
            weekdays.add(weekday)

            # Count occurrences in case there would be multiple
            if start_time in start_times:
                start_times[start_time][1] += 1
            else:
                start_times[start_time] = [event_idx, 1]

        # Start time, pick the one having most occurrences
        start_times_sorted = dict(
            sorted(start_times.items(), key=lambda item: item[1][1], reverse=True)
        )
        start_time = next(iter(start_times_sorted))
        event_idx = start_times[start_time][0]
        end_time = course["reservation_events"][event_idx]["time_end"].strftime("%H:%M")

        # Weekdays
        wkday_map = {
            1: {"fi": "ma", "sv": "må", "en": "mo"},
            2: {"fi": "ti", "sv": "ti", "en": "tu"},
            3: {"fi": "ke", "sv": "on", "en": "we"},
            4: {"fi": "to", "sv": "to", "en": "th"},
            5: {"fi": "pe", "sv": "fr", "en": "fr"},
            6: {"fi": "la", "sv": "lö", "en": "sa"},
            0: {"fi": "su", "sv": "sö", "en": "su"},
        }
        weekday_list = [wkday_map[wkday] for wkday in wkday_map if wkday in weekdays]

        # Translated texts
        translated_title_text = {
            "fi": "klo",
            "sv": "kl.",
            "en": "at",
        }
        formatted_title_w_transl = {
            lang: (
                "{} [{} {} {} - {}]".format(
                    course_title[lang].strip(),
                    ", ".join([wk_day[lang] for wk_day in weekday_list]),
                    translated_title_text[lang],
                    start_time,
                    end_time,
                )
                if course_title[lang]
                else None
            )
            for lang in EnkoraImporter.supported_languages
        }

        return (
            course_title,  # Used for sub-event titles
            formatted_title_w_transl,  # Used for super-event title
        )

    @staticmethod
    def convert_description(
        course: dict,
        capacity_full: Optional[bool],
        has_queue_capacity: Optional[bool],
    ) -> Optional[dict]:
        """
        Convert course description into HTML with additional information on course reservation status
        :param course: dict, Enkora course information as returned from API
        :param capacity_full: bool, if course capacity is known: true, if course is fully booked
        :param has_queue_capacity: bool, if course has a queue: true, if queue has capacity
        :return: dict, HTML-formatted course descriptions per language
        """  # noqa: E501
        description = {
            lang: (
                course.get(f"description_long_{lang}")
                or course.get(f"description_{lang}")
                or course.get(f"reservation_event_group_name_{lang}")
            )
            for lang in EnkoraImporter.supported_languages
        }

        # If there's no description found for keys:
        # description_long_fi, description_fi, reservation_event_group_name_fi,
        # set to the default one
        if not description["fi"]:
            description["fi"] = (
                course.get("description_long")
                or course.get("description")
                or course.get("reservation_event_group_name")
            )

        translated_description_text = {
            "fi": {
                "has_queue_capacity": "Jonopaikkoja",
                "capacity_full": "Kurssi täynnä",
                "add_on_text": "Kurssin lisätiedot",
            },
            "sv": {
                "has_queue_capacity": "Platser i kön",
                "capacity_full": "Kurssen fullbokad",
                "add_on_text": "Tilläggsinformation om kursen",
            },
            "en": {
                "has_queue_capacity": "Spots left in queue",
                "capacity_full": "Course fully booked",
                "add_on_text": "Additional information about the course",
            },
        }

        # Iterate over the different translations and form descriptions with
        # proper HTML tags
        for lang in EnkoraImporter.supported_languages:
            # Check if the course there's a course description for the language, if
            # there is, add additional info
            if description[lang]:
                # Convert imported plain-text into HTML
                # Make sure characters are escaped properly, form paragraphs
                desc_html = html.escape(description[lang].strip())
                desc_html = "<p>" + re.sub(r"\n+", "</p>\n</p>", desc_html) + "</p>"

                if capacity_full and has_queue_capacity:
                    desc_html = (
                        f"<p><b>{translated_description_text[lang]['has_queue_capacity']}</b></p>\n"
                        + desc_html
                    )
                elif capacity_full:
                    desc_html = (
                        f"<p><b>{translated_description_text[lang]['capacity_full']}</b></p>\n"
                        + desc_html
                    )

                desc_html += (
                    f'<p><b>{translated_description_text[lang]["add_on_text"]}</b></p>\n<p>'
                    f'<a href="{EnkoraImporter.COURSE_CONTACT_LINK}">Liikuntaluuri</a>: '  # noqa: E501
                    f'<a href="tel:{EnkoraImporter.COURSE_CONTACT_PHONE}">{EnkoraImporter.COURSE_CONTACT_PHONE}</a></p>'  # noqa: E501
                )

                description.update({lang: desc_html})

        return description

    @staticmethod
    def convert_location(course: dict) -> Optional[dict]:
        """
        Convert Enkora course information into location and extra information.
        Not all locations have Tprek mapping, then a street address will be returned.
        Fallback is to have no location.
        :param course: dict, Enkora course information as returned from API
        :return: dict/None
        """
        if course["location_id"] not in EnkoraImporter.place_map:
            raise ValueError(
                "Unknown Enkora location: {} for course {} / {}. Mapping missing!".format(  # noqa: E501
                    course["location_id"],
                    course["reservation_event_group_id"],
                    course["reservation_event_group_name"],
                )
            )

        location = recur_dict()
        location_mapping = EnkoraImporter.place_map[course["location_id"]]
        if location_mapping["tprek-id"]:
            tprek_id = "tprek:{}".format(location_mapping["tprek-id"])

            try:
                Place.objects.get(id=tprek_id)
            except ObjectDoesNotExist:
                logger.error(
                    "Unknown place '{} for course with ID {}".format(
                        tprek_id, course["reservation_event_group_id"]
                    )
                )
                raise

            location["id"] = tprek_id
        elif "street-address" in location_mapping:
            # For any non-TPR Place we must use Enkora-places.
            place_id = "enkora:{}".format(course["location_id"])
            enkora_place = Place.objects.get(pk=place_id)

            location["id"] = enkora_place.id
        else:
            location = None

        return location

    @transaction.atomic
    def _handle_place(self, enkora_place_id: int, info_in: dict) -> None:
        # Note:
        # Helsinki Palvelukartta can do geocoding if address is suitably accurate.
        # See: https://api.hel.fi/servicemap/schema/swagger-ui/#/v2/v2_search_retrieve

        # Map incoming information with _fi -affix to work with _save_translated_field()
        info = {f"{key}_fi": value for key, value in info_in.items()}

        # For any non-TPR Place, we'll create an own place.
        place_id = "enkora:{}".format(enkora_place_id)

        longitude = info_in["epsg:4326"][1]
        latitude = info_in["epsg:4326"][0]
        position = Point(
            longitude, latitude, srid=settings.WGS84_SRID
        )  # GPS coordinate system

        try:
            obj = Place.objects.get(pk=place_id)
        except ObjectDoesNotExist:
            obj = None
        if not obj:
            obj = Place(data_source=self.data_source, origin_id=enkora_place_id)
            obj._changed = True
            obj._created = True
            obj.id = place_id
            obj._changed_fields = []
        else:
            obj._changed = False
            obj._created = False
            obj._changed_fields = []

            if obj.position and position.distance(obj.position) < 0.10:
                position = obj.position
            if position != obj.position:
                obj._changed = True
                obj._changed_fields.append("position")
                obj.position = position
            if obj.deleted:
                obj.deleted = False
                obj._changed_fields.append("deleted")
                obj._changed = True

        self._save_translated_field(obj, "name", info, "enkora-name")
        self._save_translated_field(obj, "street_address", info, "street-address")
        self._save_translated_field(obj, "address_locality", info, "city")

        if obj.publisher_id != self.datasource_organization.id:
            obj.publisher = self.datasource_organization
            obj._changed_fields.append("publisher")
            obj._changed = True

        if obj._changed:
            if obj._created:
                logger.info("- Creating place {}".format(place_id))
            else:
                logger.info("- Updating place {}".format(place_id))
            obj.save()

    def convert_price(self, course: dict, url: str) -> list[dict]:
        offers = []
        fare_words_to_remove = ("itäinen", "läntinen", "pohjoinen")
        do_fare_description = False
        if course["fare_products"]:
            for fare_product in course["fare_products"]:
                if do_fare_description:
                    offer_desc = fare_product["fare_product_name"]
                    if offer_desc.lower().startswith(fare_words_to_remove):
                        # Let loose the first word and any possible white-space after it.  # noqa: E501
                        # Capitalize the first letter of the description
                        offer_desc = re.sub(r"^\b\w+\b\s*", "", offer_desc)
                        offer_desc = offer_desc[0].upper() + offer_desc[1:]
                offer = recur_dict()
                price_in_cents = float(fare_product["price"])
                if price_in_cents > 0.0:
                    offer["price"] = {"fi": "{0:.2f}€".format(price_in_cents / 100)}
                    if do_fare_description:
                        offer["description"] = {"fi": offer_desc}
                    price_is_free = False
                else:
                    price_is_free = True
                offer["is_free"] = price_is_free
                offer["info_url"] = {"fi": url}
                offers.append(offer)
        else:
            offer = recur_dict()
            offer["is_free"] = True
            offer["info_url"] = {"fi": url}
            offers.append(offer)

        return offers

    def convert_audience(
        self, course: dict
    ) -> tuple[str, set, set, Optional[int], Optional[int], str]:
        """
        Light NLP operation
        Based on given input text, determine audience and sport keywords
        :param course: (dict) course data
        :param description: (str) course description
        :return: Tuple:
            - set of Keyword IDs: detected audience
            - set of Keyword IDs: detected sport
            - int: participant minimum age
            - int: participant maximum age
            - str: Liikuntakauppa URL
        """
        audience_kw_ids = set()
        sport_kw_ids = set()

        for enkora_tag in course["tags"]:
            tag_id = int(enkora_tag["tag_id"])
            if tag_id in self.audience_tag_map:
                audience_mapping = self.audience_tag_map[tag_id]
                audience_kw_ids |= audience_mapping["keywords"]

        def _ranges_overlap(
            x1: Optional[int], x2: Optional[int], y1: int, y2: int
        ) -> bool:
            if not x1 or not x2:
                # raise ValueError("Cannot compare null-ranges!")
                return False

            return x1 <= y2 and y1 <= x2

        min_age, max_age = self._parse_title_age(course["reservation_event_group_name"])
        for age_range, age_kws in self.audience_age_map:
            if _ranges_overlap(min_age, max_age, age_range[0], age_range[1]):
                audience_kw_ids |= age_kws

        # Parse description
        title_kw_ids = self._parse_title_keywords(
            course["reservation_event_group_name"]
        )

        # Discarding title language keywords, as language is determined based on tags
        title_kw_ids.discard(self.LANGUAGE_SWEDISH)
        title_kw_ids.discard(self.LANGUAGE_ENGLISH)

        for kw_id in title_kw_ids:
            if kw_id in self.AUDIENCES:
                audience_kw_ids.add(kw_id)
            else:
                sport_kw_ids.add(kw_id)

        # Determine shop link:
        liikuntakauppa_fi_link = self.liikuntakauppa_link(course)

        return (
            audience_kw_ids,
            sport_kw_ids,
            min_age,
            max_age,
            liikuntakauppa_fi_link,
        )

    @staticmethod
    def infer_event_language(course_tags: list) -> str:
        """
        Infer the event language based on specific language tag_id values.
        Defaults to 'fi' if there is no match. If there are multiple language tags (shouldn't happen),
        only the first one encountered will be evaluated.
        :param course_tags: list, course tag data as a list of dicts
        :return: str, representing the abbreviated event language
        """  # noqa: E501
        language_tag_id = None
        event_language = "fi"
        for tag_group in course_tags:
            # Checking if tag_group_id = 5, i.e. Ohjauskieli
            if int(tag_group.get("tag_group_id", -1)) == 5:
                language_tag_id = int(tag_group.get("tag_id", -1))
                # Stopping iterations once first language tag encountered, there should
                # only be one
                break

        if language_tag_id == 45:
            event_language = "fi"

        elif language_tag_id == 46:
            event_language = "sv"

        elif language_tag_id == 47:
            event_language = "en"

        return event_language

    @staticmethod
    def liikuntakauppa_link(course: dict) -> str:
        service_id = course["service_id"]

        # Return first one
        if service_id not in EnkoraImporter.liikuntakauppa_links:
            return EnkoraImporter.liikuntakauppa_links[""]

        # All other link types, except default, will get the course ID attached to
        # the link
        chosen_link_base = EnkoraImporter.liikuntakauppa_links[service_id]
        chosen_link = chosen_link_base + str(course["reservation_event_group_id"])

        return chosen_link

    @staticmethod
    def _parse_title_age(course_title: str) -> tuple[Optional[int], Optional[int]]:
        min_age = None
        max_age = None

        # Age range?
        pattern = r"(\d+)\s*-\s*(\d+)(\s+|\s*-)(vuoti|år)"
        match = re.search(pattern, course_title, flags=re.IGNORECASE)
        if match:
            min_age = int(match.group(1))
            max_age = int(match.group(2))
            return min_age, max_age

        # Min age?
        pattern = r"(yli|över)?\s+\+?(\d+)\s*(-)?(vuoti|år|ja)"
        match = re.search(pattern, course_title, flags=re.IGNORECASE)
        if match:
            min_age = int(match.group(2))
            return min_age, max_age

        pattern = r"\s+(\d+)\+"
        match = re.search(pattern, course_title, flags=re.IGNORECASE)
        if match:
            min_age = int(match.group(1))
            return min_age, max_age

        # School class range?
        pattern = r"(\d+)\.?\s*-\s*(\d+)\.?\s*(-)?(lk\.|luokk)"
        match = re.search(pattern, course_title, flags=re.IGNORECASE)
        if match:
            min_class = int(match.group(1))
            max_class = int(match.group(2))
            min_age = 6 + min_class
            max_age = 6 + max_class + 1

            return min_age, max_age

        return min_age, max_age

    @staticmethod
    def _parse_title_keywords(course_title: str) -> set[str]:
        kws = set()

        # Split into words and map single words
        words = (
            course_title.lower()
            .replace(",", " ")
            .replace("-", " ")
            .replace("+", " ")
            .replace("/", " ")
            .replace("(", " ")
            .replace(")", " ")
        )
        words = re.sub(
            r"(\d+)\s+(m)", r"\1\2", words, flags=re.IGNORECASE
        )  # attach meters into number
        words = words.split()
        for description_word in words:
            if description_word in EnkoraImporter.description_word_map:
                kws |= EnkoraImporter.description_word_map[description_word]
            else:
                for keyword in EnkoraImporter.description_word_map:
                    if isinstance(keyword, tuple):
                        if description_word in keyword:
                            kws |= EnkoraImporter.description_word_map[keyword]

        # Map phrases
        tweaked_description = re.sub(r"\s+", " ", course_title).lower()
        for keyword in EnkoraImporter.description_phrase_map:
            if isinstance(keyword, str):
                if keyword in tweaked_description:
                    kws |= EnkoraImporter.description_phrase_map[keyword]
            elif isinstance(keyword, tuple):
                for phrase in keyword:
                    if phrase in tweaked_description:
                        kws |= EnkoraImporter.description_phrase_map[keyword]

        # men + women
        pattern = r"\s+m\s*\+\s*n\b"
        match = re.search(pattern, course_title, flags=re.IGNORECASE)
        if match:
            kws |= {EnkoraImporter.AUDIENCE_MEN, EnkoraImporter.AUDIENCE_WOMEN}
        pattern = r"\s+n\s*\+\s*m\b"
        match = re.search(pattern, course_title, flags=re.IGNORECASE)
        if match:
            kws |= {EnkoraImporter.AUDIENCE_MEN, EnkoraImporter.AUDIENCE_WOMEN}

        # men + women, in Swedish
        pattern = r"\s+d\s*\+\s*h\b"
        match = re.search(pattern, course_title, flags=re.IGNORECASE)
        if match:
            kws |= {
                EnkoraImporter.AUDIENCE_MEN,
                EnkoraImporter.AUDIENCE_WOMEN,
                EnkoraImporter.LANGUAGE_SWEDISH,
            }

        return kws


class Enkora:
    """
    Base class for Enkora API
    """

    ENDPOINT_BASE_URL = "https://oma.enkora.fi/liikuntavirasto"
    default_request_timeout = 5.0
    max_retries = 3

    def __init__(self, username: str, password: str, request_timeout=None):
        self._username = username
        self._password = password
        self._set_request_timeout(request_timeout)

    def _set_request_timeout(self, request_timeout):
        if not request_timeout:
            self._request_timeout = Enkora.default_request_timeout
        else:
            self._request_timeout = float(request_timeout)

    @staticmethod
    def enable_debugging():
        from http.client import HTTPConnection

        # Enable requests-library debug output
        HTTPConnection.debuglevel = 1

        urllib_log = logging.getLogger("requests.packages.urllib3")
        urllib_log.setLevel(logging.DEBUG)
        urllib_log.propagate = True
        requests_log = logging.getLogger("requests")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    def _setup_client(self) -> object:
        headers = {
            "Accept": "application/json",
        }

        s = requests.Session()
        s.headers.update(headers)

        return s

    def _request(
        self, endpoint_url: str, payload: dict, retries=0
    ) -> requests.Response:
        http_session = self._setup_client()

        data = {
            "authentication": (None, "{},{}".format(self._username, self._password)),
            "output_format": (None, "json"),
        }
        for key in payload:
            data[key] = (None, payload[key])

        # Note: Make the request Content-Type: multipart/form-data
        attempts_left = retries + 1
        while attempts_left > 0:
            try:
                response = http_session.post(
                    endpoint_url, files=data, timeout=self._request_timeout
                )
                attempts_left = 0
            except requests.exceptions.ReadTimeout:
                attempts_left -= 1
                if attempts_left <= 0:
                    logger.debug("Enkora API request: No attempts left!")
                    raise
                continue
            response.raise_for_status()

        return response

    def _request_json(self, url: str, payload) -> dict:
        response = self._request(url, payload)
        response_json = response.json()

        return response_json


class Kurssidata(Enkora):
    """
    Enkora API: Kurssit
    """

    endpoint_url = (
        f"{Enkora.ENDPOINT_BASE_URL}/call/api/getReservationEventGroupsWithTranslations"
    )
    list_endpoint_url = f"{Enkora.ENDPOINT_BASE_URL}/call/api/getCourseIds"

    def __init__(self, username: str, password: str, request_timeout=None):
        super().__init__(username, password, request_timeout)
        self._set_request_timeout(10.0)

    def get_course_by_id(self, course_id: int) -> tuple[dict, list, list]:
        payload = {
            "reservation_event_group_id": course_id,
        }

        logger.debug("Requesting Enkora course data for ID {}".format(course_id))

        response = self._request(self.endpoint_url, payload, retries=3)
        json = response.json()
        if json["errors"]:
            raise RuntimeError("Response has errors: {}".format(json["errors"]))

        reservation_event_groups = []
        reservation_events = []
        reservations = []
        reservation_generator = self._course_data_response_generator(
            json["result"], reservation_event_groups, reservation_events
        )
        for reservation in reservation_generator:
            reservations.append(reservation)

        # Sanity:
        if len(reservation_event_groups) != 1:
            raise RuntimeError(
                "Getting reservation event group {} " "resulted in {} items!".format(
                    course_id, len(reservation_event_groups)
                )
            )
        reservation_event_group = reservation_event_groups[0]

        return reservation_event_group, reservation_events, reservations

    def get_data_for_month(
        self,
        year: int,
        month: int,
        reservation_event_groups: list,
        reservation_events: list,
    ) -> Generator:
        """
        Get reservation tree for one month
        :param year: int, year
        :param month: int, month 1-12
        :param reservation_event_groups: list to append reservation event group data into
        :param reservation_events: list to append reservation event data into
        :return: reservation generator
        """  # noqa: E501
        start_date = datetime(year=year, month=month, day=1).date()
        end_date = start_date + relativedelta(months=1)
        end_date = end_date - timedelta(days=1)

        payload = {
            "start_date": "{0}-{1}-{2}--{0}-{1}-{3}".format(
                start_date.year, start_date.month, start_date.day, end_date.day
            ),
        }

        response = self._request(self.endpoint_url, payload)
        json = response.json()
        if json["errors"]:
            raise RuntimeError("Response has errors: {}".format(json["errors"]))

        return self._course_data_response_generator(
            json["result"], reservation_event_groups, reservation_events
        )

    def get_data_for_date_range(
        self,
        first_date: datetime.date,
        last_date: datetime.date,
        reservation_event_groups: list,
        reservation_events: list,
    ) -> Generator:
        """
        Get reservation tree for one month
        :param first_date: start of range
        :param last_date: end of range
        :param reservation_event_groups: list to append reservation event group data into
        :param reservation_events: list to append reservation event data into
        :return: reservation generator
        """  # noqa: E501
        payload = {
            "start_date": "{0}-{1}-{2}--{3}-{4}-{5}".format(
                first_date.year,
                first_date.month,
                first_date.day,
                last_date.year,
                last_date.month,
                last_date.day,
            ),
        }

        json_response = self._request_json(self.endpoint_url, payload)
        if json_response["errors"]:
            raise RuntimeError(
                "Response has errors: {}".format(json_response["errors"])
            )

        return self._course_data_response_generator(
            json_response["result"], reservation_event_groups, reservation_events
        )

    def get_data_for_region_and_year(
        self,
        region: int,
        end_date: date,
        reservation_event_groups: list,
        reservation_events: list,
    ) -> Generator:
        """
        List of regions in Enkora
        ID  Nimi               Aktiivinen
         1  Etelä              No
         2  Pohjoinen          Yes
         3  Itä                Yes
         4  Länsi              Yes
         5  Koulut Pohjoinen   Yes
         6  Koulut Itä         Yes
         7  Koulut Länsi       Yes
        :param region: int, 1-7 from above table
        :param end_date: datetime.date, range end, range start is -364 days from this
        :param reservation_event_groups: list to append reservation event group data into
        :param reservation_events: list to append reservation event data into
        :return: reservation generator
        """  # noqa: E501
        start_date = end_date - timedelta(days=364)

        payload = {
            "region_id": region,
            "start_date": "{}-{}-{}--{}-{}-{}".format(
                start_date.year,
                start_date.month,
                start_date.day,
                end_date.year,
                end_date.month,
                end_date.day,
            ),
        }

        logger.debug(
            "Requesting Enkora course data between {} and {} for region {}".format(
                start_date, end_date, region
            )
        )

        response = self._request(self.endpoint_url, payload, retries=3)
        json = response.json()
        if json["errors"]:
            raise RuntimeError("Response has errors: {}".format(json["errors"]))

        return self._course_data_response_generator(
            json["result"], reservation_event_groups, reservation_events
        )

    @staticmethod
    def _course_data_response_generator(
        json: dict, reservation_event_groups: list, reservation_events: list
    ) -> Generator:
        """
        Post-process the set of JSON-data received
        :param json: JSON-response
        :param reservation_event_groups: list to populate with course data
        :param reservation_events: list to populate with course event data
        :return: generator of reservations
        """
        for course in json["courses"]:
            # Prepare course data by a copy
            reservation_event_group = {
                "reservation_event_group_id": int(course["reservation_event_group_id"]),
                "reservation_event_group_name": course["reservation_event_group_name"],
                "reservation_event_group_name_fi": course.get(
                    "reservation_event_group_name_fi"
                ),
                "reservation_event_group_name_sv": course.get(
                    "reservation_event_group_name_se"
                ),  # Remapping 'se' to proper 'sv' ISO language code
                "reservation_event_group_name_en": course.get(
                    "reservation_event_group_name_en"
                ),
                "created_timestamp": datetime.strptime(
                    course["created_timestamp"], "%Y-%m-%d %H:%M:%S"
                ),
                "created_user_id": int(course["created_user_id"]),
                "reservation_group_id": int(course["reservation_event_group_id"]),
                "reservation_group_name": course["reservation_group_name"],
                "description": course["description"],
                "description_fi": course.get("description_fi"),
                "description_sv": course.get(
                    "description_se"
                ),  # Remapping 'se' to proper 'sv' ISO language code
                "description_en": course.get("description_en"),
                "description_long": course["description_long"],
                "description_long_fi": course.get("description_long_fi"),
                "description_long_sv": course.get(
                    "description_long_se"
                ),  # Remapping 'se' to proper 'sv' ISO language code
                "description_long_en": course.get("description_long_en"),
                "description_form": course["description_form"],
                "season_id": int(course["season_id"]) if course["season_id"] else None,
                "season_name": course["season_name"],
                "public_reservation_start": (
                    datetime.strptime(
                        course["public_reservation_start"], "%Y-%m-%d %H:%M:%S"
                    )
                    if course["public_reservation_start"]
                    else None
                ),
                "public_reservation_end": (
                    datetime.strptime(
                        course["public_reservation_end"], "%Y-%m-%d %H:%M:%S"
                    )
                    if course["public_reservation_end"]
                    else None
                ),
                "public_visibility_start": (
                    datetime.strptime(
                        course["public_visibility_start"], "%Y-%m-%d %H:%M:%S"
                    )
                    if course["public_visibility_start"]
                    else None
                ),
                "public_visibility_end": (
                    datetime.strptime(
                        course["public_visibility_end"], "%Y-%m-%d %H:%M:%S"
                    )
                    if course["public_visibility_end"]
                    else None
                ),
                "instructor_visibility_start": course["instructor_visibility_start"],
                "instructor_visibility_end": course["instructor_visibility_end"],
                "is_course": bool(course["is_course"]),
                "reservation_event_count": int(course["reservation_event_count"]),
                "first_event_date": datetime.strptime(
                    course["first_event_date"], "%Y-%m-%d %H:%M:%S"
                ),
                "last_event_date": datetime.strptime(
                    course["last_event_date"], "%Y-%m-%d %H:%M:%S"
                ),
                "capacity": int(course["capacity"]),
                "queue_capacity": int(course["queue_capacity"]),
                "service_id": int(course["service_id"]),
                "service_name": course["service_name"],
                "service_at_area_id": int(course["service_at_area_id"]),
                "service_at_area_name": course["service_at_area_name"],
                "location_id": (
                    int(course["location_id"]) if course["location_id"] else None
                ),
                "location_name": course["location_name"],
                "region_id": int(course["region_id"]) if course["region_id"] else None,
                "region_name": course["region_name"],
                "reserved_count": (
                    int(course["reserved_count"]) if course["reserved_count"] else None
                ),
                "queue_count": (
                    int(course["queue_count"]) if course["queue_count"] else None
                ),
                "fare_products": (
                    course["fare_products"]
                    if "fare_products" in course and course["fare_products"]
                    else None
                ),
                "tags": course["tags"] if "tags" in course and course["tags"] else None,
            }
            reservation_event_groups.append(reservation_event_group)

            # Prepare course event data by appending course information into it
            for reservation_event_in in course["reservation_events"]:
                reservation_event = {
                    "reservation_event_id": int(
                        reservation_event_in["reservation_event_id"]
                    ),
                    "reservation_event_name": reservation_event_in[
                        "reservation_event_name"
                    ],
                    "time_start": datetime.strptime(
                        reservation_event_in["time_start"], "%Y-%m-%d %H:%M:%S"
                    ),
                    "time_end": datetime.strptime(
                        reservation_event_in["time_end"], "%Y-%m-%d %H:%M:%S"
                    ),
                    "instructors": reservation_event_in["instructors"],
                    "quantity_attended": int(reservation_event_in["quantity_attended"]),
                    "reservation_event_group_id": reservation_event_group[
                        "reservation_event_group_id"
                    ],
                    "reservation_event_group_name": reservation_event_group[
                        "reservation_event_group_name"
                    ],
                }
                reservation_events.append(reservation_event)

            if "reservations" in course:
                # Note: In Enkora a reservation is for the entire course, not for a
                # specific event of it.
                for reservation_in in course["reservations"]:
                    reservation = {
                        "reservation_id": int(reservation_in["reservation_id"]),
                        "reservation_account_id": int(
                            reservation_in["reservation_account_id"]
                        ),
                        "reservation_timestamp": datetime.strptime(
                            reservation_in["reservation_timestamp"], "%Y-%m-%d %H:%M:%S"
                        ),
                        "reservation_status_id": int(
                            reservation_in["reservation_status_id"]
                        ),
                        "reservation_status_name": reservation_in[
                            "reservation_status_name"
                        ],
                        "reserving_user_id": int(reservation_in["reserving_user_id"]),
                        "sale_event_id": (
                            int(reservation_in["sale_event_id"])
                            if reservation_in["sale_event_id"]
                            else None
                        ),
                        "reservation_event_group_id": reservation_event_group[
                            "reservation_event_group_id"
                        ],
                        "reservation_event_group_name": reservation_event_group[
                            "reservation_event_group_name"
                        ],
                    }
                    yield reservation

    def get_active_course_list(self) -> set:
        """
        Reservation event group IDs will contain also events which are also courses
        :return:
        """
        payload = {}
        response = self._request(self.list_endpoint_url, payload)
        json = response.json()
        if json["errors"]:
            raise RuntimeError("Response has errors: {}".format(json["errors"]))

        course_ids = set()
        for course_id in json["result"]:
            if course_id in course_ids:
                raise RuntimeError("Course id {} already seen!".format(course_id))
            course_ids.add(int(course_id))

        return course_ids
