import logging
import re
import time
from datetime import datetime, timedelta

import bleach
import dateutil.parser
import pytz
import requests
import requests_cache
from django.conf import settings
from django.utils.html import strip_tags
from django_orghierarchy.models import Organization
from pytz import timezone

from events.models import DataSource, Event, Keyword, Place

from .base import Importer, recur_dict, register_importer
from .sync import ModelSyncher
from .util import clean_text
from .yso import KEYWORDS_TO_ADD_TO_AUDIENCE

# Per module logger
logger = logging.getLogger(__name__)

YSO_BASE_URL = "http://www.yso.fi/onto/yso/"
YSO_KEYWORD_MAPS = {
    "Yrittäjät": "p1178",
    "Lapset": "p4354",
    "Kirjastot": "p2787",
    "Opiskelijat": "p16486",
    "Konsertit ja klubit": (
        "p11185",
        "p20421",
        "p360",
    ),  # -> konsertit, musiikkiklubit, kulttuuritapahtumat
    "Kurssit": "p9270",
    "venäjä": "p7643",  # -> venäjän kieli
    "Seniorit": "p2433",  # -> vanhukset
    "Näyttelyt": "p5121",
    "Toivoa kirjallisuudesta": "p8113",  # -> kirjallisuus
    "Suomi 100": "p29385",  # -> Suomi 100 vuotta -juhlavuosi
    "Kirjallisuus": "p8113",
    "Kielikahvilat ja keskusteluryhmät": (
        "p14004",
        "p556",
    ),  # -> keskustelu, kieli ja kielet
    "Maahanmuuttajat": "p6165",
    "Opastukset ja kurssit": ("p2149", "p9270"),  # -> opastus, kurssit
    "Nuoret": "p11617",
    "Pelitapahtumat": "p6062",  # -> pelit
    "Satutunnit": "p14710",
    "Koululaiset": "p16485",
    "Lasten ja nuorten tapahtumat": ("p4354", "p11617"),  # -> lapset, nuoret
    "Lapset ja perheet": ("p4354", "p13050"),  # -> lapset, lapsiperheet
    "Lukupiirit": ("p11406", "p14004"),  # -> lukeminen, keskustelu
    "Musiikki": "p1808",  # -> musiikki
    "muut kielet": "p556",  # -> kielet
    "Etätapahtumat": "p26626",  # -> etäosallistuminen
}

LOCATIONS = {
    # Library name in Finnish -> ((library node ids in event feed), tprek id)
    "Arabianrannan kirjasto": ((10784, 11271), 8254),
    "Entressen kirjasto": ((10659, 11274), 15321),
    "Etelä-Haagan kirjasto": ((10786, 11276), 8150),
    "Hakunilan kirjasto": ((10787, 11278), 19580),
    "Haukilahden kirjasto": ((10788, 11280), 19580),
    "Herttoniemen kirjasto": ((10789, 11282), 8325),
    "Hiekkaharjun kirjasto": ((10790, 11284), 18584),
    "Itäkeskuksen kirjasto": ((10791, 11286), 8184),
    "Jakomäen kirjasto": ((10792, 11288), 8324),
    "Jätkäsaaren kirjasto": ((11858,), 45317),
    "Kalajärven kirjasto": ((10793, 11290), 15365),
    "Kallion kirjasto": ((10794, 11291), 8215),
    "Kannelmäen kirjasto": ((10795, 11294), 8141),
    "Karhusuon kirjasto": ((10796, 11296), 15422),
    "Kauklahden kirjasto": ((10798, 11298), 15317),
    "Kauniaisten kirjasto": ((10799, 11301), 14432),
    "Kirjasto 10": ((10800, 11303), 8286),
    "Kirjasto Omena": ((10801, 11305), 15395),
    "Kirjasto Oodi": ((11893, 11895), 51342),
    "Kivenlahden kirjasto": ((10803, 11309), 15334),
    "Kaupunkiverstas": ((10804, 11311), 8145),  # former Kohtaamispaikka
    "Koivukylän kirjasto": ((10805, 11313), 19572),
    "Kontulan kirjasto u": ((10806, 11315), 8178),
    "Kotipalvelu": ((10811, 11317), 8285),
    "Käpylän kirjasto": ((10812, 11319), 8302),
    "Laajalahden kirjasto": ((10813, 11321), 15344),
    "Laajasalon kirjasto": ((10814, 11323), 8143),
    "Laaksolahden kirjasto": ((10815, 11325), 15309),
    "Lauttasaaren kirjasto": ((10817, 11329), 8344),
    "Lumon kirjasto": ((10818, 11331), 18262),
    "Länsimäen kirjasto": ((10819, 11333), 18620),
    "Malmin kirjasto": ((10820, 11335), 8192),
    "Malminkartanon kirjasto": ((10821, 11337), 8220),
    "Martinlaakson kirjasto": ((10822, 11339), 19217),
    "Maunulan kirjasto": ((10823, 11341), 8350),
    "Monikielinen kirjasto": ((10824, 11345), 8223),
    "Munkkiniemen kirjasto": ((10825, 11347), 8158),
    "Myllypuron mediakirjasto": ((10826, 11349), 8348),
    "Myyrmäen kirjasto": ((10827, 11351), 18241),
    "Nöykkiön kirjasto": ((10828, 11353), 15396),
    "Otaniemen kirjasto": ((11980,), 60321),
    "Oulunkylän kirjasto": ((10829, 11355), 8177),
    "Paloheinän kirjasto": ((10830, 11357), 8362),
    "Pasilan kirjasto": ((10831, 11359), 8269),
    "Pikku Huopalahden lastenkirjasto": ((10832, 11361), 8294),
    "Pitäjänmäen kirjasto": ((10833, 11363), 8292),
    "Pohjois-Haagan kirjasto": ((10834, 11365), 8205),
    "Pointin kirjasto": ((10835, 11367), 18658),
    "Puistolan kirjasto": ((10837, 11369), 8289),
    "Pukinmäen kirjasto": ((10838, 11371), 8232),
    "Pähkinärinteen kirjasto": ((10839, 11373), 18855),
    "Rikhardinkadun kirjasto": ((10840, 11375), 8154),
    "Roihuvuoren kirjasto": ((10841, 11377), 8369),
    "Ruoholahden lastenkirjasto": ((10842, 11379), 8146),
    "Sakarinmäen lastenkirjasto": ((10843, 11381), 10037),
    "Saunalahden kirjasto": ((11712, 11714), 29805),
    "Sellon kirjasto": ((10844, 11383), 15417),
    "Soukan kirjasto": ((10845, 11385), 15376),
    "Suomenlinnan kirjasto": ((10846, 11387), 8244),
    "Suutarilan kirjasto": ((10847, 11389), 8277),
    "Tapanilan kirjasto": ((10848, 11391), 8359),
    "Tapiolan kirjasto": ((10849, 11395), 15311),
    "Tapulikaupungin kirjasto": ((10850, 11397), 8288),
    "Tikkurilan kirjasto": ((10851, 11202), 18703),
    "Töölön kirjasto": ((10852, 11393), 8149),
    "Vallilan kirjasto": ((10853, 11399), 8199),
    "Viherlaakson kirjasto": ((10854, 11401), 15429),
    "Viikin kirjasto": ((10855, 11403), 8308),
    "Vuosaaren kirjasto": ((10856, 11405), 8310),
}

# "Etätapahtumat" are mapped to our new fancy "Tapahtuma vain internetissä." location
INTERNET_LOCATION_ID = settings.SYSTEM_DATA_SOURCE_ID + ":internet"

HELMET_BASE_URL = "https://www.helmet.fi"
HELMET_API_URL = (
    HELMET_BASE_URL + "/api/opennc/v1/ContentLanguages({lang_code})"
    "/Contents?$filter=TemplateId eq 3&$expand=ExtendedProperties,LanguageVersions"
    "&$orderby=EventEndDate desc&$format=json"
)

HELMET_LANGUAGES = {"fi": 1, "sv": 3, "en": 2, "ru": 11}
LANG_BY_HELMET_ID = {id: lang for lang, id in HELMET_LANGUAGES.items()}

# try to detect any installed languages not officially present in the feed
LANGUAGES_TO_DETECT = [
    lang[0].replace("-", "_")
    for lang in settings.LANGUAGES
    if lang[0] not in HELMET_LANGUAGES
]


def get_lang(lang_id):
    for code, lid in HELMET_LANGUAGES.items():
        if lid == lang_id:
            return code
    return None


LOCAL_TZ = timezone("Europe/Helsinki")


def mark_deleted(obj):
    if obj.deleted:
        return False
    obj.deleted = True
    obj.save(update_fields=["deleted"])
    return True


class APIBrokenError(Exception):
    pass


@register_importer
class HelmetImporter(Importer):
    name = "helmet"
    supported_languages = ["fi", "sv", "en", "ru"]
    current_tick_index = 0
    kwcache = {}

    def setup(self):
        ds_args = dict(id=self.name)
        defaults = dict(name="HelMet-kirjastot")
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )
        self.tprek_data_source = DataSource.objects.get(id="tprek")
        self.ahjo_data_source = DataSource.objects.get(id="ahjo")
        system_data_source_defaults = {
            "user_editable_resources": True,
            "user_editable_organizations": True,
        }
        self.system_data_source, _ = DataSource.objects.get_or_create(
            id=settings.SYSTEM_DATA_SOURCE_ID, defaults=system_data_source_defaults
        )

        org_args = dict(origin_id="u4804001010", data_source=self.ahjo_data_source)
        defaults = dict(name="Helsingin kaupunginkirjasto")
        self.organization, _ = Organization.objects.get_or_create(
            defaults=defaults, **org_args
        )
        org_args = dict(origin_id="00001", data_source=self.ahjo_data_source)
        defaults = dict(name="Helsingin kaupunki")
        self.city, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        # Build a cached list of Places
        loc_id_list = [location[1] for location in LOCATIONS.values()]
        place_list = Place.objects.filter(data_source=self.tprek_data_source).filter(
            origin_id__in=loc_id_list
        )
        self.tprek_by_id = {p.origin_id: p.id for p in place_list}

        # Create "Tapahtuma vain internetissä" location if not present
        defaults = dict(
            data_source=self.system_data_source,
            publisher=self.city,
            name="Internet",
            description="Tapahtuma vain internetissä.",
        )
        self.internet_location, _ = Place.objects.get_or_create(
            id=INTERNET_LOCATION_ID, defaults=defaults
        )

        try:
            yso_data_source = DataSource.objects.get(id="yso")
        except DataSource.DoesNotExist:
            yso_data_source = None

        if yso_data_source:
            # Build a cached list of YSO keywords
            cat_id_set = set()
            for yso_val in YSO_KEYWORD_MAPS.values():
                if isinstance(yso_val, tuple):
                    for t_v in yso_val:
                        cat_id_set.add("yso:" + t_v)
                else:
                    cat_id_set.add("yso:" + yso_val)

            keyword_list = Keyword.objects.filter(data_source=yso_data_source).filter(
                id__in=cat_id_set
            )
            self.yso_by_id = {p.id: p for p in keyword_list}
        else:
            self.yso_by_id = {}

        if self.options["cached"]:
            requests_cache.install_cache("helmet")
            self.cache = requests_cache.get_cache()
        else:
            self.cache = None

    @staticmethod
    def _get_extended_properties(event_el):
        ext_props = recur_dict()
        for prop in event_el["ExtendedProperties"]:
            for data_type in ("Text", "Number", "Date"):
                if prop[data_type]:
                    ext_props[prop["Name"]] = prop[data_type]
                    continue
        return ext_props

    def _import_event(self, lang, event_el, events):  # noqa: C901
        def dt_parse(dt_str):
            """Convert a string to UTC datetime"""
            # Times are in UTC+02:00 timezone
            return LOCAL_TZ.localize(
                dateutil.parser.parse(dt_str), is_dst=None
            ).astimezone(pytz.utc)

        start_time = dt_parse(event_el["EventStartDate"])
        end_time = dt_parse(event_el["EventEndDate"])

        # Import only at most one month old events
        if end_time < datetime.now().replace(tzinfo=LOCAL_TZ) - timedelta(days=31):
            return {"start_time": start_time, "end_time": end_time}

        eid = int(event_el["ContentId"])
        event = None
        if lang != "fi":
            fi_ver_ids = [
                int(x["ContentId"])
                for x in event_el["LanguageVersions"]
                if x["LanguageId"] == 1
            ]
            fi_event = None
            for fi_id in fi_ver_ids:
                if fi_id not in events:
                    continue
                fi_event = events[fi_id]
                if (
                    fi_event["start_time"] != start_time
                    or fi_event["end_time"] != end_time
                ):
                    continue
                event = fi_event
                break

        if not event:
            event = events[eid]
            event["id"] = "%s:%s" % (self.data_source.id, eid)
            event["origin_id"] = eid
            event["data_source"] = self.data_source
            event["publisher"] = self.organization
            event["type_id"] = 1

        ext_props = HelmetImporter._get_extended_properties(event_el)

        if "Name" in ext_props:
            name = clean_text(ext_props["Name"], True)
            Importer._set_multiscript_field(
                name, event, [lang] + LANGUAGES_TO_DETECT, "name"
            )
            del ext_props["Name"]

        if ext_props.get("Description", ""):
            desc = ext_props["Description"]
            ok_tags = ("u", "b", "h2", "h3", "em", "ul", "li", "strong", "br", "p", "a")
            desc = bleach.clean(desc, tags=ok_tags, strip=True)
            # long description is html formatted, so we don't want plain text whitespaces
            desc = clean_text(desc, True)
            Importer._set_multiscript_field(
                desc, event, [lang] + LANGUAGES_TO_DETECT, "description"
            )
            del ext_props["Description"]

        if ext_props.get("LiftContent", ""):
            text = ext_props["LiftContent"]
            text = clean_text(strip_tags(text))
            Importer._set_multiscript_field(
                text, event, [lang] + LANGUAGES_TO_DETECT, "short_description"
            )
            del ext_props["LiftContent"]

        if "Images" in ext_props:
            matches = re.findall(r'src="(.*?)"', str(ext_props["Images"]))
            if matches:
                img_url = matches[0]
                event["images"] = [{"url": HELMET_BASE_URL + img_url}]
            del ext_props["Images"]

        if "WillTakePlace" in ext_props:
            # WillTakePlace value "1" rather counterintuitively means the event has been cancelled
            if ext_props["WillTakePlace"] == "1":
                event["event_status"] = Event.Status.CANCELLED

        event["url"][lang] = "%s/api/opennc/v1/Contents(%s)" % (HELMET_BASE_URL, eid)

        def set_attr(field_name, val):
            if field_name in event:
                if event[field_name] != val:
                    logger.warning(
                        "Event %s: %s mismatch (%s vs. %s)"
                        % (eid, field_name, event[field_name], val)
                    )
                    return
            event[field_name] = val

        if "date_published" not in event:
            # Publication date changed based on language version, so we make sure
            # to save it only from the primary event.
            event["date_published"] = dt_parse(event_el["PublicDate"])

        set_attr("start_time", dt_parse(event_el["EventStartDate"]))
        set_attr("end_time", dt_parse(event_el["EventEndDate"]))

        event_keywords = event.get("keywords", set())
        event_audience = event.get("audience", set())
        event_in_language = event.get("in_language", set())

        for classification in event_el["Classifications"]:
            # Save original keyword in the raw too
            node_id = classification["NodeId"]
            name = classification["NodeName"]
            node_type = classification["Type"]
            # Tapahtumat exists tens of times, use pseudo id
            if name in ("Tapahtumat", "Events", "Evenemang"):
                node_id = 1  # pseudo id
            keyword_id = "helmet:{}".format(node_id)
            kwargs = {
                "id": keyword_id,
                "origin_id": node_id,
                "data_source_id": "helmet",
            }
            if keyword_id in self.kwcache:
                keyword_orig = self.kwcache[keyword_id]
                created = False
            else:
                keyword_orig, created = Keyword.objects.get_or_create(**kwargs)
                self.kwcache[keyword_id] = keyword_orig

            name_key = "name_{}".format(lang)
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
            # Online events lurk in node 7 as well
            if node_type == 7:
                if "location" not in event:
                    if classification["NodeId"] == 11996:
                        # The event is only online, do not consider other locations
                        event["location"]["id"] = INTERNET_LOCATION_ID
                    else:
                        for _k, v in LOCATIONS.items():
                            if classification["NodeId"] in v[0]:
                                event["location"]["id"] = self.tprek_by_id[str(v[1])]
                                break
            if not self.yso_by_id:
                continue
            # Map some classifications to YSO based keywords, including online events
            if str(classification["NodeName"]) in YSO_KEYWORD_MAPS.keys():
                yso = YSO_KEYWORD_MAPS[str(classification["NodeName"])]
                if isinstance(yso, tuple):
                    for t_v in yso:
                        event_keywords.add(self.yso_by_id["yso:" + t_v])
                        if t_v in KEYWORDS_TO_ADD_TO_AUDIENCE:
                            # retain the keyword in keywords as well, for backwards compatibility
                            event_audience.add(self.yso_by_id["yso:" + t_v])

                else:
                    event_keywords.add(self.yso_by_id["yso:" + yso])
                    if yso in KEYWORDS_TO_ADD_TO_AUDIENCE:
                        # retain the keyword in keywords as well, for backwards compatibility
                        event_audience.add(self.yso_by_id["yso:" + yso])

        # Finally, go through the languages that are properly denoted in helmet:
        for translation in event_el["LanguageVersions"]:
            language = LANG_BY_HELMET_ID.get(translation["LanguageId"])
            if language:
                event_in_language.add(self.languages[language])
        # Also, the current language is always included
        event_in_language.add(self.languages[lang])

        event["keywords"] = event_keywords
        event["audience"] = event_audience
        event["in_language"] = event_in_language

        if "location" in event:
            extra_info = clean_text(ext_props.get("PlaceExtraInfo", ""))
            if extra_info:
                Importer._set_multiscript_field(
                    extra_info,
                    event,
                    [lang] + LANGUAGES_TO_DETECT,
                    "location_extra_info",
                )
                del ext_props["PlaceExtraInfo"]
        else:
            logger.warning(
                "Missing TPREK location map for event %s (%s)"
                % (event["name"][lang], str(eid))
            )
            del events[event["origin_id"]]
            return event

        # Custom stuff not in our data model, what we actually need?
        for p_k, p_v in ext_props.items():
            event["custom_fields"][p_k] = p_v
        # custom_fields only accepts strings
        event["custom_fields"]["ExpiryDate"] = dt_parse(
            event_el["ExpiryDate"]
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Add a default offer
        free_offer = {
            "is_free": True,
            "price": None,
            "description": None,
            "info_url": None,
        }
        event["offers"] = [free_offer]

        return event

    def _recur_fetch_paginated_url(self, url, lang, events):
        max_tries = 5
        for try_number in range(0, max_tries):
            response = requests.get(url)
            if response.status_code != 200:
                logger.warning("HelMet API reported HTTP %d" % response.status_code)
                time.sleep(2)
                if self.cache:
                    self.cache.delete_url(url)
                continue
            try:
                root_doc = response.json()
            except ValueError:
                logger.warning(
                    "HelMet API returned invalid JSON (try {} of {})".format(
                        try_number + 1, max_tries
                    )
                )
                if self.cache:
                    self.cache.delete_url(url)
                time.sleep(5)
                continue
            break
        else:
            logger.error("HelMet API broken again, giving up")
            raise APIBrokenError()

        documents = root_doc["value"]
        earliest_end_time = None
        for doc in documents:
            event = self._import_event(lang, doc, events)
            if not earliest_end_time or event["end_time"] < earliest_end_time:
                earliest_end_time = event["end_time"]

        now = datetime.now().replace(tzinfo=LOCAL_TZ)
        # We check 31 days backwards.
        if earliest_end_time < now - timedelta(days=31):
            return

        if "odata.nextLink" in root_doc:
            self._recur_fetch_paginated_url(
                "%s/api/opennc/v1/%s%s"
                % (HELMET_BASE_URL, root_doc["odata.nextLink"], "&$format=json"),
                lang,
                events,
            )

    def import_events(self):
        logger.info("Importing HelMet events")
        events = recur_dict()
        for lang in self.supported_languages:
            helmet_lang_id = HELMET_LANGUAGES[lang]
            url = HELMET_API_URL.format(
                lang_code=helmet_lang_id, start_date="2016-01-01"
            )
            logger.info("Processing lang {} from URL {}".format(lang, url))
            try:
                self._recur_fetch_paginated_url(url, lang, events)
            except APIBrokenError:
                return

        event_list = sorted(events.values(), key=lambda x: x["end_time"])
        qs = Event.objects.filter(
            end_time__gte=datetime.now(), data_source="helmet", deleted=False
        )

        self.syncher = ModelSyncher(
            qs, lambda obj: obj.origin_id, delete_func=mark_deleted
        )

        for event in event_list:
            obj = self.save_event(event)
            self.syncher.mark(obj)

        self.syncher.finish(force=self.options["force"])
        logger.info("%d events processed" % len(events.values()))
