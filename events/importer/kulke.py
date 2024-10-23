import functools
import itertools
import logging
import os
import re
from datetime import datetime, time, timedelta
from posixpath import join as urljoin
from textwrap import dedent
from typing import Iterator, Sequence, Union

import dateutil
import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Q
from django_orghierarchy.models import Organization
from lxml import etree
from pytz import timezone

from events.keywords import KeywordMatcher
from events.models import (
    DataSource,
    Event,
    EventAggregate,
    EventAggregateMember,
    Keyword,
    License,
    Place,
)
from events.translation_utils import expand_model_fields

from .base import Importer, recur_dict, register_importer
from .utils import clean_url, unicodetext
from .yso import KEYWORDS_TO_ADD_TO_AUDIENCE

logger = logging.getLogger(__name__)


EVENTS_URL_TEMPLATE = urljoin(
    settings.ELIS_EVENT_API_URL,
    "event?searchstarttime={begin_date}&sort=starttime&show=100&offset={offset}&language={language}",
)
CATEGORY_URL = urljoin(settings.ELIS_EVENT_API_URL, "category")


LOCATION_TPREK_MAP = {
    "malmitalo": "8740",
    "malms kulturhus": "8740",
    "malms bibliotek - malms kulturhus": "8192",
    "malmin kirjasto": "8192",
    "helsingin kaupungintalo": "28473",
    "stoa": "7259",
    "östra centrums bibliotek": "8184",
    "parvigalleria": "7259",
    "musiikkisali": "7259",
    "kanneltalo": "7255",
    "vuotalo": "7260",
    "vuosali": "7260",
    "savoy-teatteri": "7258",
    "savoy": "7258",
    "annantalo": "7254",
    "annegården": "7254",
    "espan lava": "7265",
    "caisa": "7256",
    "nuorisokahvila clubi": "8006",
    "haagan nuorisotalo": "8023",
    "vuosaaren kirjasto": "8310",
    "riistavuoren palvelukeskus": "47695",
    "kannelmäen palvelukeskus": "51869",
    "leikkipuisto lampi": "57117",
}

# "Etäosallistuminen" is also mapped to our new fancy "Tapahtuma vain internetissä." location  # noqa: E501
INTERNET_LOCATION_ID = settings.SYSTEM_DATA_SOURCE_ID + ":internet"

ADDRESS_TPREK_MAP = {
    "annankatu 30": "annantalo",
    "annegatan 30": "annantalo",
    "mosaiikkitori 2": "vuotalo",
    "ala-malmin tori 1": "malmitalo",
    "ala-malmin tori": "malmitalo",
    "klaneettitie 5": "kanneltalo",
    "klarinettvägen 5": "kanneltalo",
    "turunlinnantie 1": "stoa",
}

CATEGORIES_TO_IGNORE = [
    286,
    596,
    614,
    307,
    675,
    231,
    364,
    325,
    324,
    319,
    646,
    641,
    642,
    643,
    670,
    671,
    673,
    674,
    725,
    312,
    344,
    365,
    239,
    240,
    308,
    623,
    229,
    230,
    323,
    320,
    357,
    358,
    728,
    729,
    735,
    736,
    # The categories below are languages, ignore as categories
    # todo: add as event languages
    53,
    54,
    55,
]

# If you update this, please be sure to update generate_documentation_md too
CATEGORY_TYPES_TO_IGNORE = [
    2,
    3,
]

# Events having one of these categories are courses - they are excluded when importing events  # noqa: E501
# and only they are included when importing courses.
COURSE_CATEGORIES = {
    70,
    71,
    72,
    73,
    75,
    77,
    79,
    80,
    81,
    83,
    84,
    85,
    87,
    316,
    629,
    728,
    729,
    735,
}


def _query_courses():
    filter_out_keywords = map(make_kulke_id, COURSE_CATEGORIES)
    return Event.objects.filter(data_source="kulke").filter(
        keywords__id__in=set(filter_out_keywords)
    )


SPORTS = ["p965"]
GYMS = ["p8504"]
MOVIES = ["p1235"]
CHILDREN = ["p4354"]
YOUTH = ["p11617"]
ELDERLY = ["p2433"]
FAMILIES = ["p13050"]

MANUAL_CATEGORIES = {
    # urheilu
    546: SPORTS,
    547: SPORTS,
    431: SPORTS,
    638: SPORTS,
    # kuntosalit
    607: GYMS,
    615: GYMS,
    # harrastukset
    626: ["p2901"],
    # erityisliikunta
    634: ["p3093", "p916"],
    # monitaiteisuus
    223: ["p25216", "p360"],
    # seniorit > ikääntyneet ja vanhukset
    354: ELDERLY,
    # saunominen
    371: ["p11049"],
    # lastentapahtumat > lapset (!)
    105: CHILDREN,
    # steppi
    554: ["p19614"],
    # liikuntaleiri
    710: ["p143", "p916"],
    # teatteri ja sirkus
    351: ["p2625"],
    # elokuva ja media
    205: MOVIES,
    # skidikino
    731: CHILDREN + MOVIES,
    # luennot ja keskustelut
    733: ["p15875", "p14004"],
    # nuorille
    734: YOUTH,
    # elokuva
    737: MOVIES,
    # perheliikunta
    628: SPORTS + FAMILIES,
    # lapset
    355: CHILDREN,
    # lapsi ja aikuinen yhdessä > perheet
    747: FAMILIES,
}

# these are added to all courses
COURSE_KEYWORDS = ("p9270",)

# retain the above for simplicity, even if kulke importer internally
# requires full keyword ids
KEYWORDS_TO_ADD_TO_AUDIENCE = ["yso:{}".format(i) for i in KEYWORDS_TO_ADD_TO_AUDIENCE]

# category text replacements for keyword determination
CATEGORY_TEXT_REPLACEMENTS = [("jumppa", "voimistelu"), ("Stoan", "Stoa")]

LOCAL_TZ = timezone("Europe/Helsinki")


def make_kulke_id(num):
    return "kulke:{}".format(num)


def make_event_name(title, subtitle):
    if title and subtitle:
        return "{} – {}".format(title, subtitle)
    elif title:
        return title
    elif subtitle:
        return subtitle


def get_event_name(event):
    if "fi" in event["name"]:
        return event["name"]["fi"]
    else:
        names = list(event["name"].values())
        if len(names):
            return None
        else:
            return names[0]


def parse_age_range(secondary_headline):
    if not isinstance(secondary_headline, str):
        return (None, None)

    pattern = r"^\D*(\d{1,2}).(\d{1,2}).(v|år).*$"
    match = re.match(pattern, secondary_headline)

    if match:
        beginning_age = int(match.groups()[0])
        end_age = int(match.groups()[1])
        return (beginning_age, end_age)
    else:
        return (None, None)


def parse_course_time(secondary_headline):
    if not isinstance(secondary_headline, str):
        return (None, None)

    pattern = r"^.*klo?\s(\d{1,2})([.:](\d{1,2}))?[^.:](\d{1,2})([.:](\d{1,2}))?.*$"
    match = re.match(pattern, secondary_headline)

    if match:
        course_time_beginning_hour = int(match.groups()[0])
        course_time_beginning_minute = (
            int(match.groups()[2]) if match.groups()[2] else 0
        )
        course_time_end_hour = int(match.groups()[3])
        course_time_end_minute = int(match.groups()[5]) if match.groups()[5] else 0
        course_time_beginning = time(
            hour=course_time_beginning_hour, minute=course_time_beginning_minute
        )
        course_time_end = time(hour=course_time_end_hour, minute=course_time_end_minute)
        return (course_time_beginning, course_time_end)
    else:
        return (None, None)


@register_importer
class KulkeImporter(Importer):
    name = "kulke"
    supported_languages = ["fi", "sv", "en"]
    languages_to_detect = []

    def setup(self):
        self.languages_to_detect = [
            lang[0].replace("-", "_")
            for lang in settings.LANGUAGES
            if lang[0] not in self.supported_languages
        ]
        ds_args = dict(id=self.name)
        defaults = dict(name="Kulttuurikeskus")

        self.tprek_data_source, _ = DataSource.objects.get_or_create(
            id="tprek", defaults=dict(name="Toimipisterekisteri")
        )
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )

        ds_args = dict(id="ahjo")
        defaults = dict(name="Ahjo")
        ahjo_ds, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(origin_id="u48040010", data_source=ahjo_ds)
        defaults = dict(name="Kulttuuripalvelukokonaisuus")
        self.organization, _ = Organization.objects.get_or_create(
            defaults=defaults, **org_args
        )

        # Create the internet location if missing
        org_args = dict(origin_id="00001", data_source=ahjo_ds)
        defaults = dict(name="Helsingin kaupunki")
        self.city, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        system_data_source_defaults = {
            "user_editable_resources": True,
            "user_editable_organizations": True,
        }
        self.system_data_source, _ = DataSource.objects.get_or_create(
            id=settings.SYSTEM_DATA_SOURCE_ID, defaults=system_data_source_defaults
        )
        defaults = dict(
            data_source=self.system_data_source,
            publisher=self.city,
            name="Internet",
            description="Tapahtuma vain internetissä.",
        )
        self.internet_location, _ = Place.objects.get_or_create(
            id=INTERNET_LOCATION_ID, defaults=defaults
        )

        # Build a cached list of Places to avoid frequent hits to the db
        id_list = LOCATION_TPREK_MAP.values()
        place_list = Place.objects.filter(data_source=self.tprek_data_source).filter(
            origin_id__in=id_list
        )
        self.tprek_by_id = {p.origin_id: p.id for p in place_list}

        logger.info("Preprocessing categories")
        categories = self.fetch_kulke_categories()

        keyword_matcher = KeywordMatcher()
        for cid, c in list(categories.items()):
            if c is None:
                continue
            ctext = c["text"]
            # Ignore list (not used and/or not a category for general consumption)
            #
            # These are ignored for now, could be used for
            # target group extraction or for other info
            # were they actually used in the data:
            if cid in CATEGORIES_TO_IGNORE or c["type"] in CATEGORY_TYPES_TO_IGNORE:
                continue

            manual = MANUAL_CATEGORIES.get(cid)
            if manual:
                try:
                    yso_ids = ["yso:{}".format(i) for i in manual]
                    yso_keywords = Keyword.objects.filter(id__in=yso_ids)
                    c["yso_keywords"] = yso_keywords
                except Keyword.DoesNotExist:
                    pass
            else:
                for src, dest in CATEGORY_TEXT_REPLACEMENTS:
                    ctext = re.sub(src, dest, ctext, flags=re.IGNORECASE)
                c["yso_keywords"] = keyword_matcher.match(ctext)

        self.categories = categories

        course_keyword_ids = ["yso:{}".format(kw) for kw in COURSE_KEYWORDS]
        self.course_keywords = set(Keyword.objects.filter(id__in=course_keyword_ids))

        try:
            self.event_only_license = License.objects.get(id="event_only")
        except License.DoesNotExist:
            self.event_only_license = None

    def fetch_kulke_categories(self) -> dict[str, Union[str, int]]:
        response = requests.get(CATEGORY_URL, timeout=self.default_timeout)
        response.raise_for_status()
        root = etree.fromstring(response.content)
        categories = {}
        for ctype in root.xpath("/data/categories/category"):
            cid = int(ctype.attrib["id"])
            typeid = int(ctype.attrib["typeid"])
            categories[cid] = {"type": typeid, "text": ctype.text}
        return categories

    def find_place(self, event):
        tprek_id = None
        location = event["location"]
        if location["name"] is None:
            logger.warning(
                "Missing place for event %s (%s)"
                % (get_event_name(event), event["origin_id"])
            )
            return None

        loc_name = location["name"].lower()
        if loc_name in LOCATION_TPREK_MAP:
            tprek_id = LOCATION_TPREK_MAP[loc_name]

        if not tprek_id:
            # Exact match not found, check for string begin
            for k in LOCATION_TPREK_MAP.keys():
                if loc_name.startswith(k):
                    tprek_id = LOCATION_TPREK_MAP[k]
                    break

        if not tprek_id:
            # Check for venue name inclusion
            if "caisa" in loc_name:
                tprek_id = LOCATION_TPREK_MAP["caisa"]
            elif "annantalo" in loc_name:
                tprek_id = LOCATION_TPREK_MAP["annantalo"]

        if not tprek_id and "fi" in location["street_address"]:
            # Okay, try address.
            if "fi" in location["street_address"] and location["street_address"]["fi"]:
                addr = location["street_address"]["fi"].lower()
                if addr in ADDRESS_TPREK_MAP:
                    tprek_id = LOCATION_TPREK_MAP[ADDRESS_TPREK_MAP[addr]]

        if not tprek_id and "sv" in location["street_address"]:
            # Okay, try Swedish address.
            if "sv" in location["street_address"] and location["street_address"]["sv"]:
                addr = location["street_address"]["sv"].lower()
                if addr in ADDRESS_TPREK_MAP:
                    tprek_id = LOCATION_TPREK_MAP[ADDRESS_TPREK_MAP[addr]]

        if tprek_id:
            event["location"]["id"] = self.tprek_by_id[tprek_id]
        elif Keyword.objects.get(id="yso:p26626") in event["keywords"]:
            # "Etäosallistuminen" is also mapped to our new fancy "Tapahtuma vain internetissä." location  # noqa: E501
            event["location"]["id"] = INTERNET_LOCATION_ID
        elif "virtuaalinen" in loc_name.lower():
            event["location"]["id"] = INTERNET_LOCATION_ID
        else:
            logger.warning(
                "No match found for place '%s' (event %s)"
                % (loc_name, get_event_name(event))
            )

    @staticmethod
    def _html_format(text):
        """Format text into html

        The method simply wrap <p> tags around texts that are
        separated by empty line, and append <br> to lines if
        there are multiple line breaks within the same paragraph.
        """

        # do not preserve os separators, for conformity with helmet and other html data
        paragraph_sep = os.linesep * 2
        paragraphs = text.split(paragraph_sep)
        formatted_paragraphs = []
        for paragraph in paragraphs:
            lines = paragraph.strip().split(os.linesep)
            formatted_paragraph = "<p>{0}</p>".format("<br>".join(lines))
            formatted_paragraphs.append(formatted_paragraph)
        return "".join(formatted_paragraphs)

    def _import_event(self, lang, event_el, events, is_course=False):  # noqa: C901
        def text(t):
            return unicodetext(event_el.find("event" + t))

        def clean(t):
            if t is None:
                return None
            t = t.strip()
            if not t:
                return None
            return t

        def text_content(k):
            return clean(text(k))

        eid = int(event_el.attrib["id"])
        if text_content("servicecode") != "Pelkkä ilmoitus" and not is_course:
            # Skip courses when importing events
            return False

        if (single := self.options.get("single")) and single != str(eid):
            return False

        event = events[eid]
        if is_course:
            event["type_id"] = 2
        else:
            event["type_id"] = 1

        event["data_source"] = self.data_source
        event["publisher"] = self.organization
        event["origin_id"] = eid

        title = text_content("title")
        subtitle = text_content("subtitle")
        event["headline"][lang] = title
        event["secondary_headline"][lang] = subtitle
        name = make_event_name(title, subtitle)

        age_range = parse_age_range(subtitle)

        event["audience_min_age"] = age_range[0]
        event["audience_max_age"] = age_range[1]

        # kulke strings may be in other supported languages
        if name:
            Importer._set_multiscript_field(
                name, event, [lang] + self.languages_to_detect, "name"
            )

        caption = text_content("caption")
        # body text should not be cleaned, as we want to html format the whole shebang
        bodytext = event_el.find("eventbodytext")
        if bodytext is not None:
            bodytext = bodytext.text
        description = ""
        if caption:
            description += caption
            # kulke strings may be in other supported languages
            Importer._set_multiscript_field(
                caption, event, [lang] + self.languages_to_detect, "short_description"
            )
        else:
            event["short_description"][lang] = None
        if caption and bodytext:
            description += "\n\n"
        if bodytext:
            description += bodytext
        if description:
            description = self._html_format(description)
            # kulke strings may be in other supported languages
            Importer._set_multiscript_field(
                description, event, [lang] + self.languages_to_detect, "description"
            )
        else:
            event["description"][lang] = None

        event["info_url"][lang] = text_content("www")
        # todo: process extra links?
        links = event_el.find("eventlinks")
        if links is not None:
            links = links.findall("eventlink")
            assert len(links)
        else:
            links = []
        external_links = {}
        for link_el in links:
            if link_el is None or link_el.text is None:
                continue
            link = clean_url(link_el.text)
            if link:
                external_links["link"] = link
        event["external_links"][lang] = external_links

        eventattachments = event_el.find("eventattachments")
        if eventattachments is not None:
            for attachment in eventattachments:
                if attachment.attrib["type"] == "teaserimage":
                    # with the event_only license, the larger picture may be served
                    image_url = (
                        unicodetext(attachment)
                        .strip()
                        .replace("/MediumEventPic", "/EventPic")
                    )
                    if image_url:
                        if self.event_only_license:
                            event["images"] = [
                                {
                                    "url": image_url,
                                    "license": self.event_only_license,
                                }
                            ]
                        else:
                            logger.error(
                                'Cannot create an image, "event_only" License missing.'
                            )
                    break

        provider = text_content("organizer")
        if provider:
            Importer._set_multiscript_field(
                provider, event, [lang] + self.languages_to_detect, "provider"
            )

        course_time = parse_course_time(subtitle)

        start_time = dateutil.parser.parse(text("starttime"))
        # Start and end times are in GMT. Sometimes only dates are provided.
        # If it's just a date, tzinfo is None.
        # FIXME: Mark that time is missing somehow?
        if not start_time.tzinfo:
            assert (
                start_time.hour == 0
                and start_time.minute == 0
                and start_time.second == 0
            )
            if course_time[0]:
                start_time = start_time.replace(
                    hour=course_time[0].hour, minute=course_time[0].minute
                )
                start_time = start_time.astimezone(LOCAL_TZ)
                event["has_start_time"] = True
            else:
                start_time = LOCAL_TZ.localize(start_time)
                event["has_start_time"] = False
        else:
            start_time = start_time.astimezone(LOCAL_TZ)
            event["has_start_time"] = True
        event["start_time"] = start_time

        if text("endtime"):
            end_time = dateutil.parser.parse(text("endtime"))
            if not end_time.tzinfo:
                assert (
                    end_time.hour == 0 and end_time.minute == 0 and end_time.second == 0
                )
                if course_time[1]:
                    end_time = end_time.replace(
                        hour=course_time[1].hour, minute=course_time[1].minute
                    )
                    end_time = end_time.astimezone(LOCAL_TZ)
                    event["has_end_time"] = True

                else:
                    end_time = LOCAL_TZ.localize(end_time)
                    event["has_end_time"] = False
            else:
                end_time = end_time.astimezone(LOCAL_TZ)
                event["has_end_time"] = True

            # sometimes, the data has errors. then we set end time to start time
            if end_time > start_time:
                event["end_time"] = end_time
            else:
                event["end_time"] = event["start_time"]

        if is_course:
            event["extension_course"] = {
                "enrolment_start_time": dateutil.parser.parse(
                    text("enrolmentstarttime")
                ),
                "enrolment_end_time": dateutil.parser.parse(text("enrolmentendtime")),
            }

        if "offers" not in event:
            event["offers"] = [recur_dict()]

        offer = event["offers"][0]
        price = text_content("price")
        price_el = event_el.find("eventprice")
        free = price_el.attrib["free"] == "true"

        offer["is_free"] = free
        description = price_el.get("ticketinfo")
        if description and "href" in description:
            # the field sometimes contains some really bad invalid html
            # snippets
            description = None
        offer["description"][lang] = description
        if not free:
            offer["price"][lang] = price
        link = price_el.get("ticketlink")
        if link:
            offer["info_url"][lang] = clean_url(link)

        if hasattr(self, "categories"):
            event_keywords = set()
            event_audience = set()
            for category_id in event_el.find("eventcategories"):
                category = self.categories.get(int(category_id.text))
                if category:
                    # YSO keywords
                    if category.get("yso_keywords"):
                        for c in category.get("yso_keywords", []):
                            event_keywords.add(c)
                            if c.id in KEYWORDS_TO_ADD_TO_AUDIENCE:
                                # retain the keyword in keywords as well, for backwards
                                # compatibility
                                event_audience.add(c)
                # Also save original kulke categories as keywords
                kulke_id = make_kulke_id(category_id.text)
                try:
                    kulke_keyword = Keyword.objects.get(pk=kulke_id)
                    event_keywords.add(kulke_keyword)
                except Keyword.DoesNotExist:
                    logger.exception("Could not find {}".format(kulke_id))

            if is_course:
                event_keywords.update(self.course_keywords)
                event_audience.update(
                    self.course_keywords & set(KEYWORDS_TO_ADD_TO_AUDIENCE)
                )

            event["keywords"] = event_keywords
            event["audience"] = event_audience

        location = event["location"]

        location["street_address"][lang] = text_content("address")
        location["postal_code"] = text_content("postalcode")
        municipality = text_content("postaloffice")
        if municipality == "Helsingin kaupunki":
            municipality = "Helsinki"
        location["address_locality"][lang] = municipality
        location["telephone"][lang] = text_content("phone")
        location["name"] = text_content("location")

        if "place" not in location:
            self.find_place(event)
        return True

    def _gather_recurring_events(self, lang, event_el, events, recurring_groups):
        references = event_el.find("eventreferences")
        this_id = int(event_el.attrib["id"])
        if references is None or len(references) < 1:
            group = set()
        else:
            recurs = references.findall("recurring") or []
            recur_ids = map(lambda x: int(x.attrib["id"]), recurs)
            group = set(recur_ids)
        group.add(this_id)
        recurring_groups[this_id] = group

    def _verify_recurs(self, recurring_groups):
        for key, group in recurring_groups.items():
            for inner_key in group:
                inner_group = recurring_groups.get(inner_key)
                if inner_group and inner_group != group:
                    logger.warning(
                        "Differing groups: key: %s - inner key: %s", key, inner_key
                    )
                    logger.warning(
                        "Differing groups: group: %s - inner group: %s",
                        group,
                        inner_group,
                    )
                    if len(inner_group) == 0:
                        logger.warning(
                            "Event self-identifies to no group, removing.", inner_key
                        )
                        group.remove(inner_key)

    def _update_super_event(
        self, super_event: Event, member_events: list[Event]
    ) -> None:
        first_event = sorted(
            member_events, key=lambda x: (x.start_time is None, x.start_time)
        )[0]
        last_event = sorted(
            member_events, key=lambda x: (x.end_time is not None, x.end_time)
        )[-1]

        super_event.start_time = first_event.start_time
        super_event.has_start_time = first_event.has_start_time
        super_event.end_time = last_event.end_time
        super_event.has_end_time = last_event.has_end_time

        # Functions which map related models into simple comparable values.
        def simple(field):
            return frozenset(map(lambda x: x.simple_value(), field.all()))

        value_mappers = {"offers": simple, "external_links": simple}
        fieldnames = expand_model_fields(
            super_event,
            [
                "info_url",
                "description",
                "short_description",
                "headline",
                "secondary_headline",
                "provider",
                "publisher",
                "location",
                "location_extra_info",
                "data_source",
                "images",
                "offers",
                "external_links",
            ],
        )

        # The set of fields which have common values for all events.
        common_fields = set(
            f
            for f in fieldnames
            if 1
            == len(
                set(
                    map(
                        value_mappers.get(f, lambda x: x),
                        (getattr(event, f) for event in member_events),
                    )
                )
            )
        )

        for fieldname in common_fields:
            value = getattr(first_event, fieldname)
            if hasattr(value, "all"):
                manager = getattr(super_event, fieldname)
                simple = False
                if hasattr(value.first(), "simple_value"):
                    # Simple related models can be deleted and copied.
                    manager.all().delete()
                    simple = True
                for m in value.all():
                    if simple:
                        m.id = None
                        m.event_id = super_event.id
                        m.save()
                    manager.add(m)
            else:
                setattr(super_event, fieldname, value)

        # The name may vary within a recurring event; hence, take the common part
        # in each language
        for lang in self.languages:
            name_attr = f"name_{lang}"
            first_name = getattr(first_event, name_attr)
            words = first_name.split(" ") if first_name else []

            if name_attr not in common_fields:
                name = ""
                member_event_names = [
                    getattr(event, name_attr) for event in member_events
                ]

                # Try to find the common part of the names
                for word in words:
                    if all(
                        member_event_name and member_event_name.startswith(name + word)
                        for member_event_name in member_event_names
                    ):
                        name += word + " "
                    else:
                        name = name.rstrip()
                        break

                # If a common part was not found, default to the first event's name
                setattr(super_event, name_attr, name or getattr(first_event, name_attr))

        # Gather common keywords present in *all* subevents
        common_keywords = functools.reduce(
            lambda x, y: x & y, (set(event.keywords.all()) for event in member_events)
        )
        super_event.keywords.clear()
        for k in common_keywords:
            super_event.keywords.add(k)

        common_audience = functools.reduce(
            lambda x, y: x & y, (set(event.audience.all()) for event in member_events)
        )
        super_event.audience.clear()
        for k in common_audience:
            super_event.audience.add(k)

    @transaction.atomic
    def _save_super_event(self, recurring_group):
        kulke_ids = set(make_kulke_id(event) for event in recurring_group)
        superevent_aggregates = EventAggregate.objects.filter(
            members__event__id__in=kulke_ids
        ).distinct()
        n_super_events = superevent_aggregates.count()

        if n_super_events > 1:
            logger.error(
                "Error: the superevent has an ambiguous aggregate group.\nAggregate ids: {}, group: {}".format(  # noqa: E501
                    superevent_aggregates.values_list("id", flat=True), recurring_group
                )
            )
            return False

        events = list(Event.objects.filter(id__in=kulke_ids))
        if len(events) != len(recurring_group):
            logger.warning(
                "Not all events referenced in the group were found in the database. Group: %s - Events: %s",  # noqa: E501
                recurring_group,
                set(e.id for e in events),
            )

        if n_super_events == 0:
            # Don't create a super event if there is only one event in the database
            if len(events) < 2:
                return False

            aggregate = EventAggregate.objects.create()
            super_event = Event(
                publisher=self.organization,
                super_event_type=Event.SuperEventType.RECURRING,
                data_source=self.data_source,
                id="linkedevents:agg-{}".format(aggregate.id),
            )
            self._update_super_event(super_event, events)
            super_event.save()
            aggregate.super_event = super_event
            aggregate.save()
            event_aggregates = [
                EventAggregateMember(event=event, event_aggregate=aggregate)
                for event in events
            ]
            EventAggregateMember.objects.bulk_create(event_aggregates)
        else:
            aggregate = superevent_aggregates.first()
            if len(events) < 2:
                # The imported event is not part of an aggregate but one was found it in the db.  # noqa: E501
                # Remove the super event. This is the only case when an event is removed from  # noqa: E501
                # a recurring aggregate.
                aggregate.super_event.soft_delete()
                aggregate.super_event.sub_events.all().update(super_event=None)
                return False
            else:
                for event in events:
                    EventAggregateMember.objects.get_or_create(
                        event=event, event_aggregate=aggregate
                    )
                # Remove any extra event aggregate members
                EventAggregateMember.objects.filter(event_aggregate=aggregate).exclude(
                    event__in=events
                ).delete()
        for event in events:
            event.super_event = aggregate.super_event
        Event.objects.bulk_update(events, ("super_event",))

        return True

    def _handle_removed_events(
        self, elis_event_ids: Sequence[int], begin_date: datetime
    ) -> None:
        # Find Kulke events that are not referenced in the latest data from Elis
        # and delete them.
        unreferenced_events = Event.objects.filter(
            data_source=self.data_source,
            start_time__gte=begin_date,
            super_event_type__isnull=True,
            deleted=False,
        ).exclude(origin_id__in=elis_event_ids)
        unreferenced_events.update(super_event=None)
        count = unreferenced_events.soft_delete()

        if count:
            logger.debug("Deleted %d events", count)

        self._handle_referenced_deleted_events(elis_event_ids, begin_date)

        # Find super events that no longer contain at least two events and delete them
        count = (
            Event.objects.exclude(super_event_type__isnull=True)
            .annotate(
                aggregate_member_count=Count(
                    "aggregate__members",
                    filter=Q(aggregate__members__event__deleted=False),
                )
            )
            .filter(
                data_source=self.data_source,
                aggregate_member_count__lt=2,
                deleted=False,
            )
            .soft_delete()
        )
        if count:
            logger.debug(
                "Deleted %d empty super events",
                count,
            )

    def _handle_referenced_deleted_events(
        self, elis_event_ids: Sequence[int], begin_date: datetime
    ) -> None:
        count = Event.objects.filter(
            data_source=self.data_source,
            start_time__gte=begin_date,
            deleted=True,
            origin_id__in=elis_event_ids,
        ).undelete()

        if count:
            logger.debug(
                "Restored %d events",
                count,
            )

    def import_events(self):
        logger.info("Importing Kulke events")
        self._import_events()

    # FIXME: Commented out to avoid any unfortunate accidents.
    #        Not quite sure if course import works or not.
    #        Uncomment to enable course import.
    # def import_courses(self):
    #     logger.info("Importing Kulke courses")
    #     self._import_events(importing_courses=True)

    def _iter_elis_events(
        self, language: str, begin_date: datetime
    ) -> Iterator[etree.Element]:
        begin_date = begin_date.strftime("%d.%m.%Y")
        offset = 0
        parser = etree.XMLParser(recover=True)
        while True:
            logger.debug("Fetching events: %s - %d", language, offset)
            response = requests.get(
                EVENTS_URL_TEMPLATE.format(
                    begin_date=begin_date, offset=offset, language=language
                ),
                timeout=self.default_timeout,
            )
            response.raise_for_status()
            root = etree.fromstring(response.content, parser=parser)
            events = root.xpath("/eventdata/event")
            if not events:
                break
            for event in events:
                yield event
            offset += 100

    def _import_events(self, importing_courses=False):
        begin_date = datetime.now(tz=LOCAL_TZ) - timedelta(days=60)
        events = recur_dict()
        recurring_groups = dict()
        for lang in self.supported_languages:
            for event_el in self._iter_elis_events(lang, begin_date):
                success = self._import_event(lang, event_el, events, importing_courses)
                if success:
                    self._gather_recurring_events(
                        lang, event_el, events, recurring_groups
                    )

        events.default_factory = None

        course_keywords = set(
            map(
                make_kulke_id,
                COURSE_CATEGORIES,
            )
        )

        for event in events.values():
            contains_course_keywords = any(
                kw.id in course_keywords for kw in event["keywords"]
            )
            if contains_course_keywords == importing_courses:
                self.save_event(event)

        self._verify_recurs(recurring_groups)
        for group in recurring_groups.values():
            if group:
                self._save_super_event(group)

        self._handle_removed_events(events.keys(), begin_date)

    def import_keywords(self):
        logger.info("Importing Kulke categories as keywords")
        categories = self.fetch_kulke_categories()
        for kid, value in categories.items():
            try:
                # if the keyword exists, update the name if needed
                word = Keyword.objects.get(id=make_kulke_id(kid))
                if word.name != value["text"]:
                    word.name = value["text"]
                    word.save()
                if word.publisher_id != self.organization.id:
                    word.publisher = self.organization
                    word.save()
            except ObjectDoesNotExist:
                # if the keyword does not exist, save it for future use
                Keyword.objects.create(
                    id=make_kulke_id(kid),
                    name=value["text"],
                    data_source=self.data_source,
                    publisher=self.organization,
                )

    @staticmethod
    def generate_documentation_md() -> str:
        """
        Generate MarkDown document covering Kulke importer logic and mappings.
        :return: documentation string
        """

        from snakemd import new_doc

        doc = new_doc()

        doc.add_heading("Kulke Importer")
        doc.add_paragraph(
            "When importing data from Elis to Linked Events, some mappings and transformations are "  # noqa: E501
            "applied, and there is some special logic regarding the creation of super events. "  # noqa: E501
            "This document covers these aspects of the importer with the target audience being someone "  # noqa: E501
            "who creates events and needs to understand how the event will be represented in LE."  # noqa: E501
        )

        # Section about field mapping
        KulkeImporter._md_doc_fields(doc)

        # Section about event locations
        KulkeImporter._md_doc_location(doc)

        # Section about categories, with subsections about ignored categories,
        # course categories, and YSO keywords
        doc.add_heading("Categories", level=2)
        KulkeImporter.md_doc_ignored_categories(doc)
        KulkeImporter._md_doc_courses(doc)
        KulkeImporter._md_doc_keywords(doc)

        # Section about super events
        KulkeImporter._md_doc_super_events(doc)

        return str(doc)

    @staticmethod
    def _md_doc_fields(doc):
        doc.add_heading("Fields", level=2)
        doc.add_raw(
            dedent(
                """
            Some of the fields in Linked Events are different from Elis, so some mapping needs to be performed
            when importing events from Elis. The following is a non-exhaustive list of these mappings.
            """  # noqa: E501
            )
        )
        doc.add_table(
            header=("Field in LE", "Source (field in Elis or other)"),
            data=[
                ("`headline`", "Elis: `title`"),
                ("`secondary_headline`", "Elis: `subtitle`"),
                ("`audience_{min/max}_age`", "Parsed from `subtitle` if possible"),
                ("`{start/end}_time`", "Elis: `{start/end}time`"),
                ("`data_source`", "Always `Kulttuurikeskus`"),
                ("`publisher`", "Always `Yleiset kulttuuripalvelut`"),
                ("`short_description`", "Elis: `caption`"),
                ("`description`", "Elis: `caption` and `bodytext`"),
                ("`info_url`", "Elis: `www`"),
                ("`offer`: `is_free`", "Elis: `price`"),
                ("`offer`: `info_url`", "Elis: `ticketlink`"),
            ],
        )

    @staticmethod
    def _md_doc_super_events(doc):
        doc.add_heading("Super Events", level=2)
        doc.add_heading("Event References", level=3)
        doc.add_raw(
            dedent(
                """
        Events in Elis can contain references to other events. In LE, super events are constructed from such events.
        A super event is constructed for each group of events that has at least two events in it.
        Before constructing the super event,the importer collects all such events and references and checks
        their validity. Super events can be constructed in two valid ways:

        1. One event containing references to the rest. E.g. the first event A contains references to B and C, but B
        and C don't contain any references.
        2. All events refer to each other. E.g. A refers to B & C, B refers to A & C, and C refers to A & B.

        If there are inconsistent references, e.g. A refers to B and C, but B only refers to A, a warning will be logged
        and the super event construction may be unsuccessful.
        """  # noqa: E501
            )
        )

        doc.add_heading("Metadata", level=3)
        doc.add_raw(
            dedent(
                """
        The super event's metadata is constructed using its member events. Some fields are shared between all member
        events, and they are used as is. The following fields are copied as-is IF they are the same for each member
        event. The list shows the name in LE first, and the name in Elis in parentheses if applicable.

        - `info_url`
        - `description`
        - `short_description`
        - `headline`
        - `secondary_headline`
        - `provider`
        - `publisher`
        - `location`
        - `location_extra_info`
        - `data_source`
        - `images`
        - `offers`
        - `external_links`

        If the member events don't have a common value for the field, then the field is typically left empty. There are
        some exceptions to this logic, and some fields have custom logic.
        Headlines (event names), try to find the common part of the name. For example, if there is a recurring event
        with three occurrences, and each event has suffixes like 1/3, 2/3, and 3/3, then the super event name will be
        the common part without this suffix. If a common part cannot be found, the super event will use the name of the
        first event, as determined by start time.

        The subset of keywords and audiences that are common to all member events will be attached to the super event.
        """  # noqa: E501
            )
        )

    @staticmethod
    def _md_doc_location(doc):
        doc.add_raw(
            dedent(
                """\
        ## Location
        The following table shows the mapping of location names to Tprek IDs.
        """
            )
        )
        tprek_id_to_name = {
            id: name
            for id, name in Place.objects.filter(
                data_source=DataSource.objects.get(id="tprek"),
                origin_id__in=list(LOCATION_TPREK_MAP.values()),
            ).values_list("id", "name")
        }
        doc.add_table(
            header=("Name", "Tprek ID", "Tprek Name (in Finnish)"),
            data=[
                [name, tprek_id, tprek_id_to_name.get(f"tprek:{tprek_id}", "(missing)")]
                for name, tprek_id in LOCATION_TPREK_MAP.items()
            ],
        )

        doc.add_raw(
            dedent(
                """\
        If an exact match is not found, the importer tries to check if there is a partial match,
        i.e. whether the event's location name starts with one of the location names in the above mapping.
        The mapping, like all mappings described here, is case-insensitive.
        Additionally, remote participation (category 751, "Etäosallistuminen") is mapped to the online only
        ("tapahtuma vain internetissä") location.
        If the place is not found using the location name, finding the location using the address is attempted,
        in both Finnish and Swedish. These addresses are mapped to the following cultural centers, which in
        turn are mapped to the Tprek IDs shown above.
        """  # noqa: E501
            )
        )

        doc.add_table(header=("Address", "Name"), data=ADDRESS_TPREK_MAP.items())

    @staticmethod
    def md_doc_ignored_categories(doc):
        doc.add_raw(
            dedent(
                """\
        ### Ignored Categories
        All of the following categories from Elis will be ignored.
        They will not appear in the event in LE or have any effect on it.
        """
            )
        )

        id_to_name = {
            kw_id: name
            for kw_id, name in Keyword.objects.filter(
                id__in=[make_kulke_id(c) for c in CATEGORIES_TO_IGNORE]
            ).values_list("id", "name")
        }
        doc.add_table(
            header=("Category ID", "Name"),
            data=[
                (c, id_to_name.get(make_kulke_id(c), "(name not available)"))
                for c in CATEGORIES_TO_IGNORE
            ],
        )

        doc.add_paragraph(
            "In addition, any categories with the following category types are ignored."
        )
        doc.add_table(
            header=("Category Type ID", "Category Type Name"),
            data=([(2, "Nostokategoria"), (3, "Kohde")]),
        )

    @staticmethod
    def _md_doc_courses(doc):
        doc.add_heading("Courses", level=3)
        doc.add_paragraph(
            "Any event that has at least one of these categories is considered to be a course."  # noqa: E501
        )
        id_to_name = {
            kw_id: name
            for kw_id, name in Keyword.objects.filter(
                id__in=[make_kulke_id(c) for c in COURSE_CATEGORIES]
            ).values_list("id", "name")
        }
        doc.add_table(
            header=("Category ID", "Name"),
            data=[
                (c, id_to_name.get(make_kulke_id(c), "(name not available)"))
                for c in COURSE_CATEGORIES
            ],
        )

    @staticmethod
    def _md_doc_keywords(doc):
        doc.add_raw(
            dedent(
                """\
        ### Keyword Mapping


        The importer will try to determine relevant YSO keywords when importing events and courses.
        For some categories, this is done using a manual mapping, but for the remaining categories,
        the importer will attempt to perform a keyword match to determine the keywords.
        The mapping, both manual and automatic, is shown in the table below.
        """  # noqa: E501
            )
        )

        # At doc generation time we don't have access to the category type info, so this is  # noqa: E501
        # a dirty workaround to filter categories with these types out of the table
        categories_of_ignored_type = [36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49]

        keyword_matcher = KeywordMatcher()
        keyword_mapping_data = []
        for category in Keyword.objects.filter(
            data_source=DataSource.objects.get(id="kulke")
        ).exclude(
            id__in=[
                make_kulke_id(c)
                for c in CATEGORIES_TO_IGNORE
                + categories_of_ignored_type
                + list(MANUAL_CATEGORIES)
            ]
        ):
            category_text = category.name
            for src, dest in CATEGORY_TEXT_REPLACEMENTS:
                category_text = re.sub(src, dest, category_text, flags=re.IGNORECASE)
            yso_keywords = keyword_matcher.match(category_text)
            if yso_keywords:
                yso_keywords = ", ".join(
                    f"{kw.id.split(':')[-1]} - {kw.name}" for kw in yso_keywords
                )
            else:
                yso_keywords = "None"

            keyword_mapping_data.append(
                (
                    int(category.id.split(":")[-1]),
                    category_text,
                    yso_keywords,
                    "Match",
                )
            )

        id_to_name = {
            kw_id: name
            for kw_id, name in Keyword.objects.filter(
                id__in=[make_kulke_id(c) for c in MANUAL_CATEGORIES]
                + [
                    f"yso:{c}"
                    for c in list(itertools.chain(*MANUAL_CATEGORIES.values()))
                    + KEYWORDS_TO_ADD_TO_AUDIENCE
                ]
            ).values_list("id", "name")
        }

        for kulke_id, yso_ids in MANUAL_CATEGORIES.items():
            kulke_name = id_to_name.get(make_kulke_id(kulke_id), "(name not available)")
            yso_categories = [
                f"{c} - " + id_to_name.get(f"yso:{c}", "(name not available)")
                for c in yso_ids
            ]

            keyword_mapping_data.append(
                (kulke_id, kulke_name, ", ".join(yso_categories), "Manual")
            )

        doc.add_table(
            header=("Category ID", "Category Name", "YSO Keywords", "Method"),
            data=sorted(keyword_mapping_data, key=lambda x: x[0]),
        )

        doc.add_paragraph(
            "Additionally, the keyword p9270 (courses) is added to every course."
        )

        doc.add_paragraph(
            "If the event or course contains any of the following YSO keywords, "
            "these keywords will be added to the event's audience."
        )

        doc.add_table(
            header=("YSO Keyword ID", "Keyword Name"),
            data=[
                (kw.strip("yso:"), id_to_name.get(kw, "(name not available)"))
                for kw in KEYWORDS_TO_ADD_TO_AUDIENCE
            ],
        )
