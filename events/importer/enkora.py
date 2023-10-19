import logging
import re
from datetime import date, datetime, timedelta
from typing import Generator, Optional

import pytz
import requests
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django_orghierarchy.models import Organization

from events.importer.sync import ModelSyncher
from events.models import DataSource, Event, Keyword, Place

from .base import Importer, register_importer
from .util import clean_text

logger = logging.getLogger(__name__)


@register_importer
class EnkoraImporter(Importer):
    name = "enkora"
    supported_languages = ["fi", "sv", "en"]
    EEST = pytz.timezone("Europe/Helsinki")

    SPORT_ACROBATICS = "yso:p1277"  # akrobatia [voimistelu]
    SPORT_ADAPTED_PE = "yso:p3093"  # erityisliikunta
    SPORT_BADMINTON = "yso:p16210"  # sulkapallo [palloilu]
    SPORT_BROOMSTICK = "yso:p19453"  # keppijumppa [voimistelu]
    SPORT_CANOEING = "yso:p12078"  # melonta [vesiurheilu]
    SPORT_CIRCUS = "yso:p27786"  # sirkuskoulut [taideoppilaitokset]
    SPORT_CHAIR_PE = "yso:p27829"  # tuolijumppa [kuntoliikunta]
    SPORT_GYM = "yso:p8504"  # kuntosalit [liikuntatilat]
    SPORT_DANCE = "yso:p7153"  # tanssiurheilu
    SPORT_ICE_HOCKEY = "yso:p12697"  # jääkiekko
    SPORT_JUMPPA = "yso:p3708"  # kuntoliikunta
    SPORT_KETTLEBELL = "yso:p23896"  # kahvakuulaurheilu [voimailu]
    SPORT_MAILAPELIT = "yso:p18503"  # mailat [liikuntavälineet]
    SPORT_NORDIC_WALKING = "yso:p18572"  # sauvakävely
    SPORT_OUTDOOR_PE = "yso:p26619"  # ulkoliikunta
    SPORT_PADEL = "yso:p37760"  # padel [palloilu]
    SPORT_PARKOUR = "yso:p22509"  # parkour [urheilu]
    SPORT_RELAXATION = "yso:p5234"  # rentoutus
    SPORT_RUNNING = "yso:p9087"  # juoksu
    SPORT_SQUASH = "yso:p16903"  # squash [palloilu]
    SPORT_SKATING = "yso:p1245"  # luistelu [talviurheilu]
    SPORT_STRETCHING = "yso:p7858"  # venyttely
    SPORT_SWIM_SCHOOL = "yso:p29121"  # uimaopetus
    SPORT_TENNIS = "yso:p1928"  # tennis [palloilu]
    SPORT_TRACK_N_FIELD = "yso:p935"  # yleisurheilu
    SPORT_TRAMPOLINING = "yso:p22130"  # trampoliinivoimistelu [voimistelu]
    SPORT_WALKING = "yso:p3706"  # kävely
    SPORT_WATER_EXERCISE = "yso:p6433"  # vesiliikunta
    SPORT_WORKOUT_STAIRS = "yso:p38999"  # kuntoportaat
    SPORT_YOGA = "yso:p3111"  # jooga

    LANGUAGE_ENGLISH = "yso:p2573"
    LANGUAGE_SWEDISH = "yso:p12469"
    LANGUAGES_FOREIGN = {LANGUAGE_ENGLISH, LANGUAGE_SWEDISH}

    AUDIENCE_CHILDREN = "yso:p4354"  # lapset (ikäryhmät)
    AUDIENCE_ADULTS = "yso:p5590"  # aikuiset [ikään liittyvä rooli]
    AUDIENCE_WORKING_AGE = "yso:p5594"  # työikäiset
    AUDIENCE_SENIORS = "yso:p2431"  # eläkeläiset
    AUDIENCE_MEN = "yso:p8173"
    AUDIENCE_WOMEN = "yso:p16991"
    AUDIENCE_INTELLECTUAL_DISABILITY = "yso:p10060"  # kehitysvammaiset
    AUDIENCE_HEARING_IMPAIRED = "yso:p4106"  # kuulovammaiset
    AUDIENCE_PSYCHIATRIC_REHAB = "yso:p12297"  # mielenterveyskuntoutujat
    AUDIENCES = {
        AUDIENCE_CHILDREN,
        AUDIENCE_ADULTS,
        AUDIENCE_WORKING_AGE,
        AUDIENCE_SENIORS,
        AUDIENCE_MEN,
        AUDIENCE_WOMEN,
        AUDIENCE_INTELLECTUAL_DISABILITY,
        AUDIENCE_HEARING_IMPAIRED,
        AUDIENCE_PSYCHIATRIC_REHAB,
    }

    PROVIDER = "Helsingin kaupungin liikuntapalvelut"
    ORGANIZATION = "ahjo:u48040020"

    service_map = {
        99: {
            "enkora-name": "Ryhmäliikunta",
            "keywords": {
                "yso:p20748"  # YSOssa ei ole ryhmäliikuntaa, tämä on ryhmätoiminta
            },
        },
        100: {"enkora-name": "Uimakoulut", "keywords": {"yso:p17551"}},
        101: {
            "enkora-name": "EasySport",
            "keywords": set(),
        },  # Huom! Laji voi olla ihan mitä vaan
        102: {"enkora-name": "Vesiliikunta", "keywords": {"yso:p6433"}},
        125: {
            "enkora-name": "EasySport, kausi",
            "keywords": set(),
        },  # Huom! Laji voi olla ihan mitä vaan
        132: {"enkora-name": "Kuntosalikurssit", "keywords": {"yso:p8504"}},
        133: {
            "enkora-name": "Sovellettu liikunta",
            "keywords": {
                "yso:p3093"  # YSO: erityisliikunta, sisältää mm. soveltava liikunta
            },
        },
    }

    audience_tag_map = {
        1: {
            "enkora-name": "Lapset, nuoret ja perheet",
            "keywords": {AUDIENCE_CHILDREN, "yso:p6915", "yso:p11617", "yso:p4363"},
        },
        2: {"enkora-name": "Työikäiset", "keywords": {AUDIENCE_WORKING_AGE}},
        3: {"enkora-name": "Seniorit", "keywords": {AUDIENCE_SENIORS}},
        4: {
            "enkora-name": "Soveltavaliikunta",
            "keywords": {"yso:p3093"},
        },  # erityisliikunta
        5: {"enkora-name": "Aikuiset", "keywords": {AUDIENCE_ADULTS}},
        6: {"enkora-name": "Juniorit (alle 20-vuotiaat)", "keywords": set()},
        7: {"enkora-name": "Erityisryhmät", "keywords": {"yso:p17354"}},
        8: {
            "enkora-name": "Seniorit (yli 63-vuotiaat)",
            "keywords": {AUDIENCE_SENIORS},
        },
    }

    audience_age_map = (
        ((0, 6), {AUDIENCE_CHILDREN, "yso:p6915"}),  # lapset, leikki-ikäiset
        ((7, 16), {"yso:p6914"}),  # kouluikäiset
        ((10, 18), {"yso:p11617"}),  # nuoret
        ((18, 200), {AUDIENCE_ADULTS}),
        ((63, 200), {AUDIENCE_SENIORS}),
    )

    place_map = {
        1: {
            "enkora-name": "Latokartanon liikuntahalli",  # 4 TPrek paikkaa
            "tprek-id": 45931,
            "keywords": set(),
        },
        2: {
            "enkora-name": "Itäkeskuksen uimahalli",  # 4 TPrek paikkaa
            "tprek-id": 9004,
            "keywords": {"yso:p4330", "yso:p9415"},
        },
        3: {
            "enkora-name": "Jakomäen uimahalli",  # 2 TPrek paikkaa
            "tprek-id": 40838,
            "keywords": {"yso:p4330", "yso:p9415"},
        },
        4: {"enkora-name": "Liikuntamylly", "tprek-id": 45927, "keywords": set()},
        5: {
            "enkora-name": "Uimastadion",  # 15 TPrek paikkaa
            "tprek-id": 41047,
            "tprek-name": "Uimastadion / Maauimala",
            "keywords": {"yso:p4330"},
        },
        6: {
            "enkora-name": "Kumpulan maauimala",  # 6 TPrek paikkaa
            "tprek-id": 40823,
            "keywords": {"yso:p4330"},
        },
        7: {
            "enkora-name": "Yrjönkadun uimahalli",  # 3 TPrek paikkaa
            "tprek-id": 41102,
            "keywords": {"yso:p4330", "yso:p9415"},
        },
        8: {
            "enkora-name": "Pirkkolan uimahalli",  # 2 TPrek paikkaa
            "tprek-id": 40774,
            "keywords": {"yso:p4330", "yso:p9415"},
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
            "keywords": {"yso:p26619"},
        },
        16: {
            "enkora-name": "Ruskeasuon liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45611,
            "keywords": {"yso:p26619"},
        },
        17: {
            "enkora-name": "Maunulan liikuntahalli",  # 7 TPrek paikkaa
            "tprek-id": 45932,
            "keywords": set(),
        },
        18: {
            "enkora-name": "Pirkkolan Jäähalli",
            "tprek-id": 67714,
            "keywords": {"yso:p1245"},
        },
        21: {
            "enkora-name": "Käpylinna",
            "tprek-id": 103,
            "tprek-name": "Päiväkoti Käpylinna",
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
            "keywords": {"yso:p26619"},
        },
        32: {
            "enkora-name": "Talin liikuntapuisto",  # 12 TPrek paikkaa
            "tprek-id": 45658,
            "keywords": {"yso:p26619"},
        },
        40: {
            "enkora-name": "Herttoniemen liikuntapuisto",  # 30 TPrek paikkaa
            "tprek-id": 45633,
            "keywords": {"yso:p26619"},
        },
        43: {
            "enkora-name": "Jakomäen liikuntapuisto",  # 7 TPrek paikkaa
            "tprek-id": 45643,
            "keywords": {"yso:p26619"},
        },
        46: {
            "enkora-name": "Brahenkenttä",  # 5 TPrek paikkaa
            "tprek-id": 41995,
            "keywords": {"yso:p26619"},
        },
        47: {
            "enkora-name": "Kannelmäen liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45642,
            "keywords": {"yso:p26619"},
        },
        51: {
            "enkora-name": "Kontulan liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45648,
            "keywords": {"yso:p26619"},
        },
        54: {
            "enkora-name": "Kurkimäen liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45638,
            "keywords": {"yso:p26619"},
        },
        58: {
            "enkora-name": "Laajasalon liikuntapuisto",  # 19 TPrek paikkaa
            "tprek-id": 45656,
            "keywords": {"yso:p26619"},
        },
        62: {
            "enkora-name": "Latokartanon liikuntapuisto",  # 11 TPrek paikkaa
            "tprek-id": 45650,
            "keywords": {"yso:p26619"},
        },
        63: {
            "enkora-name": "Lauttasaaren liikuntapuisto",  # 16 TPrek paikkaa
            "tprek-id": 45660,
            "keywords": {"yso:p26619"},
        },
        72: {
            "enkora-name": "Myllypuron liikuntapuisto",  # 14 TPrek paikkaa
            "tprek-id": 45604,
            "keywords": {"yso:p26619"},
        },
        74: {
            "enkora-name": "Paloheinän ulkoilualue",  # 13 TPrek paikkaa
            "tprek-id": 45422,
            "keywords": {"yso:p26619"},
        },
        82: {
            "enkora-name": "Puotilankenttä",  # 7 TPrek paikkaa
            "tprek-id": 41581,
            "keywords": {"yso:p26619"},
        },
        83: {
            "enkora-name": "Roihuvuoren liikuntapuisto",  # 13 TPrek paikkaa
            "tprek-id": 45663,
            "keywords": {"yso:p26619"},
        },
        93: {
            "enkora-name": "Tehtaanpuiston kenttä",  # 2 TPrek paikkaa
            "tprek-id": 41665,
            "keywords": {"yso:p26619"},
        },
        96: {
            "enkora-name": "Töölön pallokenttä",  # 6 TPrek paikkaa
            "tprek-id": 41294,
            "keywords": {"yso:p26619"},
        },
        99: {
            "enkora-name": "Vuosaaren liikuntapuisto",  # 8 TPrek paikkaa
            "tprek-id": 45655,
            "keywords": {"yso:p26619"},
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
            "keywords": {"yso:p12078"},
        },
        217: {
            "enkora-name": "Kampin palvelukeskus",  # 2 TPrek paikkaa
            "tprek-id": 41410,
            "keywords": set(),
        },
        218: {
            "enkora-name": "Maunula sorsapuisto",
            "tprek-id": None,
            "keywords": {"yso:p26619"},
        },
        220: {
            "enkora-name": "Kinaporin seniorikeskus",
            "tprek-id": 1940,
            "keywords": set(),
        },
        221: {
            "enkora-name": "Puotilan leikkiniitty",  # 3 TPrek paikkaa
            "tprek-id": 40074,
            "keywords": {"yso:p8105", "yso:p26619"},
        },
        222: {
            "enkora-name": "Suuntimontien puisto",  # 2 TPrek paikkaa
            "tprek-id": 42246,
            "keywords": {"yso:p26619"},
        },
        223: {
            "enkora-name": "Töölönlahden lähiliikuntapaikka",
            "tprek-id": 68749,
            "keywords": {"yso:p26619"},
        },
        224: {
            "enkora-name": "Töölönlahden puisto",  # 4 TPrek paikkaa
            "tprek-id": 68740,
            "keywords": {"yso:p26619"},
        },
        230: {
            "enkora-name": "Oulunkylän jäähalli",
            "tprek-id": 40256,
            "keywords": {"yso:p1245"},
        },
        231: {
            "enkora-name": "Vuosaaren jäähalli",  # 3 TPrek paikkaa
            "tprek-id": 40601,
            "keywords": {"yso:p1245"},
        },
        232: {
            "enkora-name": "Circus Helsinki",  # 2 TPrek paikkaa
            "tprek-id": 20898,
            "keywords": set(),
        },
        233: {
            "enkora-name": "Paloheinän jäähalli",  # 2 TPrek paikkaa
            "tprek-id": 41623,
            "keywords": {"yso:p1245"},
        },
        234: {
            "enkora-name": "Talihalli",  # 4 TPrek paikkaa
            "tprek-id": 68825,
            "keywords": set(),
        },
        235: {
            "enkora-name": "Malmin jäähalli",
            "tprek-id": 40025,
            "keywords": {"yso:p1245"},
        },
        236: {
            "enkora-name": "Salmisaaren jäähalli",
            "tprek-id": 40832,
            "keywords": {"yso:p1245"},
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
            "keywords": {"yso:p1278"},
        },
        239: {
            "enkora-name": "Konalan jäähalli",
            "tprek-id": 42171,
            "keywords": {"yso:p1245"},
        },
        240: {
            "enkora-name": "Myllypuron jäähalli",  # 2 TPrek paikkaa
            "tprek-id": 40227,
            "keywords": {"yso:p1245"},
        },
        241: {
            "enkora-name": "Hernesaaren jäähalli",
            "tprek-id": 41820,
            "keywords": {"yso:p1245"},
        },
        242: {
            "enkora-name": "Sirkuskoulu Perhosvoltti",
            "tprek-id": None,
            "keywords": set(),
        },
        243: {
            "enkora-name": "Töölön palvelukeskus",
            "tprek-id": 41523,
            "keywords": set(),
        },
        244: {
            "enkora-name": "Tanssikoulu Footlight, Lauttasaari",
            "tprek-id": None,
            "keywords": {"yso:p1278"},
        },
        245: {
            "enkora-name": "Helsinginkadun uimahalli",
            "tprek-id": 40731,
            "tprek-name": "Helsingin urheilutalo / Urheiluhallit Kallio / Uimahalli",
            "keywords": {"yso:p4330", "yso:p9415"},
        },
        246: {"enkora-name": "Pohjoinen", "tprek-id": None, "keywords": set()},
        247: {"enkora-name": "Länsi", "tprek-id": None, "keywords": set()},
        248: {"enkora-name": "Itä", "tprek-id": None, "keywords": set()},
        249: {"enkora-name": "JUMPPAKORTTI", "tprek-id": None, "keywords": set()},
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
            "tprek-id": None,
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
            "keywords": {"yso:p1245"},
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
            "enkora-name": "Pirkkolan lähiliikuntapaikka",  # kts. Pirkkolan liikuntapuisto
            "tprek-id": 40855,
            "keywords": {"yso:p26619"},
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
            "keywords": {"yso:p934", "yso:p26619"},
        },
        297: {
            "enkora-name": "Rastilan leirintäalue",  # 3 TPrek paikkaa
            "tprek-id": 7808,
            "keywords": {"yso:p26619"},
        },
        302: {
            "enkora-name": "Malmin peruskoulu (Talvelantie 1)",  # kts. 257: Malmin pk, OV, Talvelantie 1
            "tprek-id": 46604,
            "keywords": set(),
        },
        303: {
            "enkora-name": "Käpylän peruskoulu (Untamontie 2)",  # kts. 262: Käpylän pk, IV, Untamontie 2
            "tprek-id": None,
            "keywords": set(),
        },
        310: {
            "enkora-name": "Heteniitynkenttä (Vuosaari)",  # 8 TPrek paikkaa
            "tprek-id": 41553,
            "keywords": set(),
        },
    }

    description_word_map = {
        "äijäjumppa": {AUDIENCE_MEN, SPORT_JUMPPA},
        (
            "uimakoulu",
            "tekniikkauimakoulu",
            "alkeisuimakoulu",
            "aquapolo",
            "alkeisjatkouimakoulu",
            "jatkouimakoulu",
            "koululaisuinti",
            "päiväkotiuinti",
            "uintitekniikka",
        ): {SPORT_SWIM_SCHOOL},
        "nybörjarsim": {SPORT_SWIM_SCHOOL, LANGUAGE_SWEDISH},
        "aikuisten": {AUDIENCE_ADULTS},
        ("naiset", "n"): {AUDIENCE_WOMEN},
        ("damer", "d"): {AUDIENCE_WOMEN, LANGUAGE_SWEDISH},
        ("miehet", "m"): {AUDIENCE_MEN},
        "työikäiset": {AUDIENCE_WORKING_AGE},
        (
            "circuit",
            "core",
            "kehonhuolto",
            "kuntosalin",
            "kuntosaliohjelman",
            "kuntosaliohjelmat",
            "kuntosalistartti",
            "livcore",
            "liikuntakaruselli",
            "livcircuit",
            "livvoima",
            "kuntosalicircuit",
            "voimaharjoittelu",
            "voima",
            "xxl_kuntosaliharjoittelu",
        ): {SPORT_GYM},
        (
            "senioricircuit",
            "senioricore",
            "seniorikehonhuolto",
            "seniorikuntosalistartti",
            "seniorivkehonhuolto",
            "seniorivoima",
        ): {SPORT_GYM, AUDIENCE_SENIORS},
        (
            "tanssi",
            "dancemix",
            "lattarijumppa",
            "livlattarit",
            "showjazz",
            "tanssillinen",
        ): {SPORT_DANCE},
        (
            "senioritanssi",
            "seniorikuntotanssi",
            "seniorilattarijumppa",
            "seniorilattarit",
            "senioriltanssi",
            "senioritanssillinensyke",
        ): {SPORT_DANCE, AUDIENCE_SENIORS},
        ("jääkiekko", "hockey", "kiekkokoulu"): {SPORT_ICE_HOCKEY},
        ("luistelu", "luistelukoulu"): {SPORT_SKATING},
        "mailapelit": {SPORT_MAILAPELIT},
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
        "kuntosaliharjoittelu": {SPORT_GYM},
        "konditionssal": {SPORT_GYM, LANGUAGE_SWEDISH},
        "hyväolo": {SPORT_RELAXATION},
        (
            "hyvänolonjumppa",
            "jumppakortti",
            "kesäjumppa",
            "kevytjumppa",
            "kiinteytys",
            "kuntojumppa",
            "livhyväolo",
            "livkevytjumppa",
            "livsyke",
            "maratonjumppa",
            "selkähuolto",
            "selkätunti",
            "jumppa",
            "sunnuntaijumppa",
            "syke",
            "temppujumppa",
            "temppuhulinat",
            "tempputaito",
            "voimajumppa",
        ): {SPORT_JUMPPA},
        "kroppsvård": {SPORT_JUMPPA, LANGUAGE_SWEDISH},
        ("seniorijumppa", "seniorikevytjumppa", "seniorikuntojumppa", "seniorisyke"): {
            SPORT_JUMPPA,
            AUDIENCE_SENIORS,
        },
        "seniorikeppijumppa": {SPORT_BROOMSTICK, AUDIENCE_SENIORS},
        ("seniorit", "seniori"): {AUDIENCE_SENIORS},
        "seniorer": {AUDIENCE_SENIORS, LANGUAGE_SWEDISH},
        "juoksukoulu": {SPORT_RUNNING},
        ("kahvakuula", "livkahvakuula"): {SPORT_KETTLEBELL},
        "seniorikahvakuula": {SPORT_KETTLEBELL, AUDIENCE_SENIORS},
        ("kehitysvammaiset", "kehitysvammaisten", "kehitysvammaise"): {
            AUDIENCE_INTELLECTUAL_DISABILITY
        },
        ("kuulonäkövammaiset", "kuulovammaiset", "kuulovammais", "kuulovammaisten"): {
            AUDIENCE_HEARING_IMPAIRED
        },
        ("mielenterveyskuntoutujat", "mielenterveyskuntoutu", "mielenterveysku"): {
            AUDIENCE_PSYCHIATRIC_REHAB
        },
        ("stretching", "venyttely", "livvenyttely"): {SPORT_STRETCHING},
        ("seniorivenytely", "seniorivenyttely"): {SPORT_STRETCHING, AUDIENCE_SENIORS},
        "kuntokävely": {SPORT_WALKING},
        ("jooga", "metsäjooga", "pilates"): {SPORT_YOGA},
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
        "porrastreeni": {SPORT_WORKOUT_STAIRS},
        "senioriporrastreeni": {SPORT_WORKOUT_STAIRS, AUDIENCE_SENIORS},
        "kävely": {SPORT_WALKING},
        (
            "seniorikuntokävely",
            "seniorikuntokävelytreeni",
        ): {SPORT_WALKING, AUDIENCE_SENIORS},
        "sauvakävely": {SPORT_NORDIC_WALKING},
        "seniorisauvakävely": {SPORT_NORDIC_WALKING, AUDIENCE_SENIORS},
        "seniorisäestys": {AUDIENCE_SENIORS},
        "seniorisäpinät": {AUDIENCE_SENIORS},
        "senioriteema": {AUDIENCE_SENIORS},
        "tuolijumppa": {SPORT_CHAIR_PE},
        "stolgymnastik": {SPORT_CHAIR_PE, LANGUAGE_SWEDISH},
        "ulkovoima": {SPORT_GYM, SPORT_OUTDOOR_PE},
        "uteträning": {SPORT_OUTDOOR_PE, LANGUAGE_SWEDISH},
        "vattengymnastik": {SPORT_WATER_EXERCISE, LANGUAGE_SWEDISH},
        ("veteraanit", "veteraani"): {AUDIENCE_SENIORS},
        "krigsveteraner": {AUDIENCE_SENIORS, LANGUAGE_SWEDISH},
    }
    description_phrase_map = {
        "opetuskieli englanti": {LANGUAGE_ENGLISH},
        "på svenska": {LANGUAGE_SWEDISH},
        "foam roller": {SPORT_GYM},
        "75 vuotiaat": {AUDIENCE_SENIORS},
    }

    def __init__(self, options) -> None:
        self.data_source = None
        self.organization = None
        super().__init__(options)

        self.now_tz_is = timezone.now()
        self.driver_cls = Kurssidata

    def setup(self) -> None:
        logger.debug("Running Enkora importer setup...")
        ds_defaults = dict(name="Enkora")
        self.data_source, _ = DataSource.objects.get_or_create(
            id=self.name, defaults=ds_defaults
        )

        enkora_ds, _ = DataSource.objects.get_or_create(
            defaults={"name": "Enkora Oy"}, id="enkora"
        )

        org_args = dict(origin_id=self.ORGANIZATION, data_source=enkora_ds)
        defaults = dict(name="Enkora")
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
        return datetime.now(), timezone.now()

    def import_courses(self) -> bool:
        kurssi_api = self.driver_cls(
            settings.ENKORA_API_USER, settings.ENKORA_API_PASSWORD, request_timeout=20.0
        )

        # now_is = datetime.now()
        # self.now_tz_is = timezone.now()
        now_is, self.now_tz_is = self._get_timestamps()

        def _is_course_expired(course: dict) -> bool:
            if "public_visibility_end" not in course:
                raise ValueError(
                    "Expected to have 'public_visibility_end' field in course! Missing."
                )

            visibility_expiry_timestamp = None
            if course["public_visibility_end"]:
                # This is the primary attempt: course has a proper public visibility end date
                visibility_expiry_timestamp = course["public_visibility_end"]
            elif course["public_reservation_end"]:
                # Secondary attempt: when public reservation ends
                visibility_expiry_timestamp = course["public_reservation_end"]
            elif course["first_event_date"]:
                # Tertiary attempt: when course begins, we'll assume it isn't visible anymore
                visibility_expiry_timestamp = course["first_event_date"]
            else:
                raise ValueError(
                    "Expected to have something for expiry date in course data! Missing."
                )

            return visibility_expiry_timestamp < now_is

        first_date = now_is.date() - relativedelta(months=2)
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
        # We don't need the instances of a course
        del reservation_events

        # Start sync
        self.event_syncher = ModelSyncher(
            Event.objects.filter(data_source=self.data_source, super_event=None),
            lambda event: event.id,
            delete_func=self.mark_deleted,
            check_deleted_func=self.check_deleted,
        )

        # Now we have the course list populated, iterate it.
        for course_idx, course in enumerate(reservation_event_groups):
            logger.debug(
                "{}) Enkora course ID {}".format(
                    course_idx + 1, course["reservation_event_group_id"]
                )
            )
            if _is_course_expired(course):
                logger.debug(
                    "Skipping event with public visibility ended at: {}".format(
                        course["public_visibility_end"]
                    )
                )
                continue
            event_data = self._handle_course(course)
            event = self.save_event(event_data)
            self.event_syncher.mark(event)

        self.event_syncher.finish(force=True)
        logger.info("Enkora course import finished.")

    def mark_deleted(self, event: Event) -> bool:
        if event.deleted:
            return False
        if event.end_time < self.now_tz_is:
            return False

        # Event expired, mark it deleted
        event.soft_delete()

        return True

    def check_deleted(self, event: Event) -> bool:
        return event.deleted

    @staticmethod
    def generate_documentation_md() -> str:  # noqa: C901
        """
        Generate MarkDown document out of Enkora importing rules.
        :return: documentation string
        """
        from snakemd import Inline, MDList, new_doc, Paragraph

        yso_base_url = r"https://finto.fi/yso/fi/page/{}"
        tprek_base_url = r"https://palvelukartta.hel.fi/fi/unit/{}"
        doc = new_doc()
        doc.add_heading("Linked Events - Enkora Course importer", level=1)

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

        # Section 1:
        # Places
        doc.add_heading("Enkora Locations to LE Places", level=2)
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
                except ObjectDoesNotExist:
                    logger.error("Unknown place '{}'!".format(place_id))
                    raise
                tprek = str(
                    Paragraph(
                        "Place: [{}] {}".format(place.id, place.name)
                    ).insert_link(place.id, tprek_base_url.format(mapping["tprek-id"]))
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
        ul = []
        for service_id, mapping in EnkoraImporter.service_map.items():
            item_text = "Service {} [{}]:".format(mapping["enkora-name"], service_id)
            ul.append(Inline(item_text))

            if mapping["keywords"]:
                kws = _keyword_helper(mapping["keywords"])
                details = ", ".join(kws)
            else:
                details = Inline("Warning: not mapped!", bold=True)
            ul.append(MDList([details]))

        doc.add_block(MDList(ul))

        # Section 3:
        # Audiences
        doc.add_heading("Enkora Audiences to LE Audience Keywords", level=2)
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

        # Done!
        return str(doc)

    def _handle_course(self, course: dict) -> dict:
        """
        {'reservation_event_group_id': 32791,
        'reservation_event_group_name': 'Koululaisuinti',
         'created_timestamp': datetime.datetime(2021, 4, 13, 9, 54, 55),
         'created_user_id': 23698,
         'reservation_group_id': 32791,
         'reservation_group_name': 'Koululaisuinti',
         'description': 'Koululaisuinti',
         'description_long': None,
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
         'tags': [{'tag_id': '1', 'tag_name': 'Lapset, nuoret ja perheet'}]}
        """

        capacity = 0
        remaining_capacity = 0
        description = None

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
                dates[field_name] = timezone.make_aware(
                    course[field_name], EnkoraImporter.EEST
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

        # Description:
        if course["description_long"]:
            description = course["description_long"]
        elif course["description"]:
            description = course["description"]
        elif course["reservation_event_group_name"]:
            description = course["reservation_event_group_name"]

        # Location:
        location_id, location_extra_info = self.convert_location(course)

        # Keywords
        keywords = self.convert_keywords(course)

        # Audience
        (
            language,
            audience_keywords,
            sport_keywords,
            audience_min_age,
            audience_max_age,
        ) = self.convert_audience(course, description)
        keywords.extend(sport_keywords)
        in_language = [self.languages[language]]

        # Wrapping up all details:
        event_data = {
            "type_id": Event.TypeId.COURSE,
            "name": {"fi": course["reservation_event_group_name"]},
            "description": {"fi": description},
            "audience_min_age": audience_min_age,
            "audience_max_age": audience_max_age,
            "audience": audience_keywords,
            "start_time": dates["first_event_date"],
            "end_time": dates["last_event_date"],
            "date_published": dates["public_visibility_start"],
            "external_links": {"fi": {"registration": "https://www.hel.fi/fi"}},
            "provider": {"fi": self.PROVIDER},
            "provider_contact_info": {"fi": "Hki - KUVA - Liikunta"},
            "enrolment_start_time": dates["public_reservation_start"],
            "enrolment_end_time": dates["public_reservation_end"],
            "maximum_attendee_capacity": capacity,
            "remaining_attendee_capacity": remaining_capacity,
            "data_source": self.data_source,
            "origin_id": course["reservation_event_group_id"],
            "publisher": self.organization,
            "location": location_id,
            "keywords": keywords,
            "in_language": in_language,
            "images": [],  # must have a list of images, even if there are no images
            "offers": [],  # must have a list of offers, even if there are no offers
        }

        if location_extra_info:
            event_data["location_extra_info"] = {"fi": location_extra_info}

        return event_data

    def convert_keywords(self, course: dict) -> list:
        """
        Deduce a set of keywords from course data.
        Note: Course description is not part of this deduction.
        :param course:
        :return: list of keyword DB-objects
        """
        if course["location_id"] not in EnkoraImporter.place_map:
            raise ValueError(
                "Unknown Enkora location: {} for course {} / {}. Mapping missing!".format(
                    course["location_id"],
                    course["reservation_event_group_id"],
                    course["reservation_event_group_name"],
                )
            )
        if course["service_id"] not in EnkoraImporter.service_map:
            raise ValueError(
                "Unknown Enkora service: {} for course {} / {}. Mapping missing!".format(
                    course["service_id"],
                    course["reservation_event_group_id"],
                    course["reservation_event_group_name"],
                )
            )

        location_mapping = EnkoraImporter.place_map[course["location_id"]]
        service_mapping = EnkoraImporter.service_map[course["service_id"]]
        kw_ids = location_mapping["keywords"] | service_mapping["keywords"]
        kws = []
        for kw_id in kw_ids:
            try:
                kw = Keyword.objects.get(id=kw_id)
            except ObjectDoesNotExist:
                logger.error("Unknown keyword '{}'!".format(kw_id))
                raise
            kws.append(kw)

        return kws

    def convert_location(self, course: dict) -> tuple[dict, Optional[str]]:
        if course["location_id"] not in EnkoraImporter.place_map:
            raise ValueError(
                "Unknown Enkora location: {} for course {} / {}. Mapping missing!".format(
                    course["location_id"],
                    course["reservation_event_group_id"],
                    course["reservation_event_group_name"],
                )
            )

        location_mapping = EnkoraImporter.place_map[course["location_id"]]
        tprek_id = "tprek:{}".format(location_mapping["tprek-id"])

        # Extra info:
        extra_info = clean_text(course["service_at_area_name"])

        return {"id": tprek_id}, extra_info

    def convert_audience(
        self, course: dict, description: str
    ) -> tuple[str, list, list, Optional[int], Optional[int]]:
        audience_kw_ids = set()
        sport_kw_ids = set()

        for enkora_tag in course["tags"]:
            tag_id = int(enkora_tag["tag_id"])
            audience_mapping = self.audience_tag_map[tag_id]
            audience_kw_ids |= audience_mapping["keywords"]

        def _ranges_overlap(
            x1: Optional[int], x2: Optional[int], y1: int, y2: int
        ) -> bool:
            if not x1 or not x2:
                # raise ValueError("Cannot compare null-ranges!")
                return False

            return x1 <= y2 and y1 <= x2

        min_age, max_age = self._parse_description_age(description)
        for age_range, age_kws in self.audience_age_map:
            if _ranges_overlap(min_age, max_age, age_range[0], age_range[1]):
                audience_kw_ids |= age_kws

        # Parse description
        event_language = "fi"
        desc_kw_ids = self._parse_description_keywords(description)
        if self.LANGUAGE_SWEDISH in desc_kw_ids:
            event_language = "sv"
            desc_kw_ids.remove(self.LANGUAGE_SWEDISH)
        if self.LANGUAGE_ENGLISH in desc_kw_ids:
            event_language = "en"
            desc_kw_ids.remove(self.LANGUAGE_ENGLISH)
        for kw_id in desc_kw_ids:
            if kw_id in self.AUDIENCES:
                audience_kw_ids.add(kw_id)
            else:
                sport_kw_ids.add(kw_id)

        # post-process
        audience_kws = []
        for kw_id in audience_kw_ids:
            kw = Keyword.objects.get(id=kw_id)
            audience_kws.append(kw)
        sport_kws = []
        for kw_id in sport_kw_ids:
            kw = Keyword.objects.get(id=kw_id)
            sport_kws.append(kw)

        return event_language, audience_kws, sport_kws, min_age, max_age

    @staticmethod
    def _parse_description_age(description: str) -> tuple[Optional[int], Optional[int]]:
        min_age = None
        max_age = None

        # Age range?
        match = re.search(
            r"(\d+)\s*-\s*(\d+)(\s+|\s*-)(vuoti|år)", description, flags=re.IGNORECASE
        )
        if match:
            min_age = int(match.group(1))
            max_age = int(match.group(2))
            return min_age, max_age

        # Min age?
        match = re.search(
            r"(yli|över)?\s+\+?(\d+)\s*(-)?(vuoti|år|ja)",
            description,
            flags=re.IGNORECASE,
        )
        if match:
            min_age = int(match.group(2))
            return min_age, max_age
        match = re.search(r"\s+(\d+)\+", description, flags=re.IGNORECASE)
        if match:
            min_age = int(match.group(1))
            return min_age, max_age

        # School class range?
        match = re.search(
            r"(\d+)\.?\s*-\s*(\d+)\.?\s*(-)?(lk\.|luokk)",
            description,
            flags=re.IGNORECASE,
        )
        if match:
            min_class = int(match.group(1))
            max_class = int(match.group(2))
            min_age = 6 + min_class
            max_age = 6 + max_class + 1

            return min_age, max_age

        return min_age, max_age

    @staticmethod
    def _parse_description_keywords(description: str) -> set[str]:
        kws = set()

        # Split into words and map single words
        words = (
            description.lower()
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
        tweaked_description = re.sub(r"\s+", " ", description).lower()
        for keyword in EnkoraImporter.description_phrase_map:
            if isinstance(keyword, str):
                if keyword in tweaked_description:
                    kws |= EnkoraImporter.description_phrase_map[keyword]
            elif isinstance(keyword, tuple):
                for phrase in keyword:
                    if phrase in tweaked_description:
                        kws |= EnkoraImporter.description_phrase_map[keyword]

        # men + women
        match = re.search(r"\s+m\s*\+\s*n\b", description, flags=re.IGNORECASE)
        if match:
            kws |= {EnkoraImporter.AUDIENCE_MEN, EnkoraImporter.AUDIENCE_WOMEN}
        match = re.search(r"\s+n\s*\+\s*m\b", description, flags=re.IGNORECASE)
        if match:
            kws |= {EnkoraImporter.AUDIENCE_MEN, EnkoraImporter.AUDIENCE_WOMEN}

        # men + women, in Swedish
        match = re.search(r"\s+d\s*\+\s*h\b", description, flags=re.IGNORECASE)
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

    endpoint_base_url = "https://oma.enkora.fi/liikuntavirasto"
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

    endpoint_url = f"{Enkora.endpoint_base_url}/call/api/getReservationEventGroups"
    list_endpoint_url = f"{Enkora.endpoint_base_url}/call/api/getCourseIds"

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
                "Getting reservation event group {} "
                "resulted in {} items!".format(course_id, len(reservation_event_groups))
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
        """
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
        """
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
        """
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
                "created_timestamp": datetime.strptime(
                    course["created_timestamp"], "%Y-%m-%d %H:%M:%S"
                ),
                "created_user_id": int(course["created_user_id"]),
                "reservation_group_id": int(course["reservation_event_group_id"]),
                "reservation_group_name": course["reservation_group_name"],
                "description": course["reservation_event_group_name"],
                "description_long": course["description_long"],
                "description_form": course["description_form"],
                "season_id": int(course["season_id"]) if course["season_id"] else None,
                "season_name": course["season_name"],
                "public_reservation_start": datetime.strptime(
                    course["public_reservation_start"], "%Y-%m-%d %H:%M:%S"
                )
                if course["public_reservation_start"]
                else None,
                "public_reservation_end": datetime.strptime(
                    course["public_reservation_end"], "%Y-%m-%d %H:%M:%S"
                )
                if course["public_reservation_end"]
                else None,
                "public_visibility_start": datetime.strptime(
                    course["public_visibility_start"], "%Y-%m-%d %H:%M:%S"
                )
                if course["public_visibility_start"]
                else None,
                "public_visibility_end": datetime.strptime(
                    course["public_visibility_end"], "%Y-%m-%d %H:%M:%S"
                )
                if course["public_visibility_end"]
                else None,
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
                "location_id": int(course["location_id"])
                if course["location_id"]
                else None,
                "location_name": course["location_name"],
                "region_id": int(course["region_id"]) if course["region_id"] else None,
                "region_name": course["region_name"],
                "reserved_count": int(course["reserved_count"])
                if course["reserved_count"]
                else None,
                "queue_count": int(course["queue_count"])
                if course["queue_count"]
                else None,
                "fare_products": course["fare_products"]
                if "fare_products" in course and course["fare_products"]
                else None,
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
                # Note: In Enkora a reservation is for the entire course, not for a specific event of it.
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
                        "sale_event_id": int(reservation_in["sale_event_id"])
                        if reservation_in["sale_event_id"]
                        else None,
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
