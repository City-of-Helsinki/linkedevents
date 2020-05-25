"""
This is an importer for funactionnuorille.fi website.
One course: https://funactionnuorille.fi/wp-json/wp/v2/funaction_class/1768
Course listing: https://funactionnuorille.fi/wp-json/wp/v2/funaction_class
Pagination example: https://funactionnuorille.fi/wp-json/wp/v2/funaction_class?per_page=3&page=2
funactionnuorille.fi API created and maintained by Avidly

Inspired in parts by Harrastushaku importer.
"""

import logging
import re
from datetime import datetime
from functools import partial

import attr
import pytz
import requests
from dateutil.parser import isoparse, parse
from dateutil.rrule import FR, MO, SA, SU, TH, TU, WE, WEEKLY, rrule
from django.contrib.postgres.search import TrigramSimilarity
from django_orghierarchy.models import Organization
from Levenshtein import distance

from events.importer.base import Importer, register_importer
from events.keywords import KeywordMatcher
from events.models import DataSource, ImporterTimeLogger, Keyword, Place

logger = logging.getLogger(__name__)

FUNACTION_URL = (
    "https://funactionnuorille.fi/wp-json/wp/v2/funaction_class?per_page=100&page="
)

#  Acceptable Levenshtein (edit) distance between FunActionNuorille and Tprek records
#  for specific place. Larger dictance is logged as a warning, but the Tprek match is still used
ACCEPTABLE_ADDRESS_DISTANCE = 4
ACCEPTABLE_NAME_DISTANCE = 4
MAX_RECURRING_EVENT_LENGTH = 366
TIMEZONE = pytz.timezone("Europe/Helsinki")

# FunActionNuorille specific weekday taxonomy:
# 16 - Mon, 17 - Tue, 18 - Wed and so on up to 22 - Sunday.
DAY_MAP = {
    16: MO,
    17: TU,
    18: WE,
    19: TH,
    20: FR,
    21: SA,
    22: SU,
}


@attr.s(frozen=True, slots=True)
class HashedLocation(object):
    name = attr.ib()
    address = attr.ib()


@attr.s(slots=True)
class Location(object):
    fun_address = attr.ib()
    tprekId = attr.ib(default="")
    tprek_address = attr.ib(default="")
    tprek_name = attr.ib(default="")


class APIBrokenError(Exception):
    def __init__(self, message):
        super().__init__(message)
        logger.error(message)


class FunException(Exception):
    def __init__(self, message):
        super().__init__(message)
        logger.error(message)


@register_importer
class FunActionImporter(Importer):
    name = "fun"
    organization = "FunActionNuorille"
    supported_languages = ["fi"]
    keyword_cache = {}
    location_cache = {}

    def setup(self):
        self.tprek_data_source = DataSource.objects.get(id="tprek")

        self.data_source = DataSource.objects.get_or_create(
            id=self.name, name="FunAction", api_key=""
        )[0]

        # TODO: Figure out what the organization should be called actually
        self.organization, _ = Organization.objects.get_or_create(
            origin_id="funactionnuorille",
            data_source=self.data_source,
            name="funactionnuorille",
        )
        self.keyword_matcher = KeywordMatcher()

        #  Third positional argument lists the characters that will be mapped to None
        self.nodigits_trantab = str.maketrans("", "", "0123456789")

    def import_courses(self):
        src_data = self._fetch_paginated_data(FUNACTION_URL)
        itl, _ = ImporterTimeLogger.objects.get_or_create(importer_name=self.name)
        last_run = itl.last_run
        data = [
            i
            for i in src_data
            if not i["modified_gmt"] or isoparse(f"{i['modified_gmt']}Z") > last_run
        ]

        self.location_map = self._map_locations(data)

        events_info = [self._parse_event_data(i) for i in data]

        for event in events_info:
            if event["slug"]:
                event["keywords"] = self._find_keyword_or_split(event["slug"])
                logger.info(f"{event['slug']} mapped to: {event['keywords']}")

    def _create_recurring_event_dates(
        self, start_date: datetime, end_date: datetime, weekdays: list
    ):

        converted_days = [DAY_MAP[i] for i in weekdays]
        return list(
            rrule(WEEKLY, byweekday=converted_days, dtstart=start_date, until=end_date)
        )

    def _parse_event_data(self, d: dict):
        """Parsing individual activity data. d holds a dictionary that contains
        info on one course
        Following edits are made to the original data:
        - id has 'funactionnuorille:' added
        - location is set to tprek id
        - dates for the individual events of the recurring events are created
        - datetime objects are set to Helsinki/Europe timezone
        """
        get_nested, get_datetime, get_slug = self._bind_data_getters(d)

        event_data = {
            "origin_id": f"funactionnuorille:d['id']",
            "name": {"fi": f"{get_nested(fields=['title', 'rendered'])}"},
            "description": {"fi": f"{get_nested(fields=['sports', 'description'])}"},
            "start_time": get_datetime("date_from"),
            "end_time": get_datetime("date_to"),
            "time_from": d.get("time_from"),
            "time_to": d.get("time_to"),
            "days": d.get("funaction_weekdays"),
            "date_published": get_datetime("date"),
            "slug": get_slug(),
            "data_source": self.data_source,
            "publisher": self.organization,
        }

        location_description = d.get("locations")
        if isinstance(location_description, list) and len(location_description) > 0:
            location_name = location_description[0]["name"]
            event_data["location"] = self.location_map[location_name].tprekId

        if event_data["days"] and event_data["start_time"] and event_data["end_time"]:
            event_data["recurring_dates"] = self._create_recurring_event_dates(
                event_data["start_time"], event_data["end_time"], event_data["days"]
            )
        return event_data

    def _parse_slug(self, data: dict):
        """Currently "slug" is a short set of keywords separated for some reason
        with hyphens and having hardly explicable numbers attached to it as in
        amerikkalainen-jalkapallo-pojat-19.
        Real hyphens as in k-pop or hip-hop are not escaped and are currently
        indistinguishable from the hyphens as separators (ツ)_/¯.
        """

        slug = data.get("slug")
        if slug and not isinstance(slug, str):
            FunException(
                f"Slug is of type {type(slug)} instead of string in the"
                f" event {data['origin_id']}."
            )
            return None
        if slug:
            clean_slug = (
                slug.replace("-", " ").translate(self.nodigits_trantab).strip(" ")
            )
            return clean_slug

    def _find_keyword_or_split(self, text: str):
        """Attempts to find a keyword for the full string, in case of failure,
        attempts to chip off the last word and repeats. Similarity depends on
        the length of the string, hence edit (Levenshtein) distance filter was
        introduced so that 'amerikkalainen jalkapallo' is matched to one keyword
        and 'nuorisotalo jalkapallo' is matched to two.
        The function allows 2 typo per every 5 symbols, which helps both with
        simple plurals and true typos.

        TODO: when a two-word keyword is preceded by something as in
        'nuorisotalo amerikkalainen jalkapallo' which is mapped to 'nuorisotalo'
        'jalkapallo', and 'amerikkalaiset'.

        TODO: correct language treatment, so that 'body condition' is searched
        for in the English, not the Finnish keywords.
        """

        text = text.strip(" ")
        match = (
            Keyword.objects.annotate(similarity=TrigramSimilarity("name_fi", text))
            .order_by("-similarity")
            .first()
        )

        # 0.4: allow 2 edits per 5 symbols
        if match and distance(match.name_fi, text) / len(text) < 0.4:
            return set([match])

        if " " not in text:
            return set()

        split = text.rsplit(" ", 1)
        keywords = set()
        for i in split:
            keywords |= self._find_keyword_or_split(i)

        return keywords

    def _get_datetime_from_data(self, data: dict, field: str):
        value = data.get(field)
        if value in (None, False, ""):
            return None
        output = parse(value, dayfirst=True).astimezone(
            pytz.timezone("Europe/Helsinki")
        )
        return output if output else None

    def _get_nested_values(self, data: dict, fields: list):
        value = data.get(fields.pop(0))
        if isinstance(value, dict):
            self._get_nested_values(data=value, fields=fields)
        else:
            return value

    def _bind_data_getters(self, data: dict):
        """From harrastushaku"""
        get_datetime = partial(self._get_datetime_from_data, data)
        get_nested = partial(self._get_nested_values, data)
        get_slug = partial(self._parse_slug, data)
        return get_nested, get_datetime, get_slug

    def _map_locations(self, data):
        """Extracting place names -> Find exactly matching tprek records -> Check that their address is close enough ->
        find places by address -> select the ones with minimal distance in the name.
        The function expects place names to be unique and to have only one address.
        """

        src_locations = {
            HashedLocation(
                name=i["locations"][0]["name"],
                address=self._clean_address(i["locations"][0]["address"]),
            )
            for i in data
            if i["locations"]
        }
        self._log_duplicates(src_locations)

        #  Switching to unhashed representation of location for mutability and
        #  adding name as index
        locations = {i.name: Location(fun_address=i.address) for i in src_locations}

        tprek_places = Place.objects.filter(name__in=locations.keys()).values_list(
            "name", "id", "street_address"
        )
        found = set()
        for i in tprek_places:
            name, tprekId, tprek_address = i
            locations[name].tprekId = tprekId
            found.add(name)
            if locations[name].fun_address and tprek_address:
                if (
                    distance(
                        locations[name].fun_address.replace(" ", "").lower(),
                        tprek_address.replace(" ", "").lower(),
                    )
                    > ACCEPTABLE_ADDRESS_DISTANCE
                ):
                    logger.warning(
                        f"Place {name} has address {locations[name].fun_address}"
                        f" at FunActionNuorille and {tprek_address} at Tprek"
                    )
                    locations[name].tprek_address = tprek_address
            else:
                logger.warning(
                    f"Place {name} is missing the address. FunActionNuorille:"
                    f"{locations[name].fun_address}, Tprek: {tprek_address}"
                )

        still_missing_names = locations.keys() - found
        still_missing = {i: locations[i].fun_address for i in still_missing_names}

        #  tprek database holds multiple tprek objects sharing the same address.
        #  Let's find the ones that have the names most similar to the one
        #  registered on FunActionNuorille. When searching for street address we
        #  want to ignore case and spaces as Mannerheimintie 3 C should match Mannerheimintie 3c

        for name, address in still_missing.items():
            tprek_place = (
                Place.objects.extra(
                    where=[
                        f"LOWER(REPLACE(street_address,' ',''))='{str(address).replace(' ','').lower()}'"
                    ]
                )
                .annotate(similarity=TrigramSimilarity("name", name))
                .order_by("-similarity")
                .values_list("name", "id")
            )
            if tprek_place:
                found.add(name)
                locations[name].tprek_name, locations[name].tprekId = tprek_place[0]
                if (
                    distance(
                        name.replace(" ", "").lower(),
                        locations[name].tprek_name.replace(" ", "").lower(),
                    )
                    <= ACCEPTABLE_ADDRESS_DISTANCE
                ):
                    locations[name].tprek_name = ""
                else:
                    logger.warning(
                        f"Place {name} was mapped to tprek organization {locations[name].tprek_name}"
                    )

        still_missing.clear()
        still_missing_names = locations.keys() - found
        still_missing = {i: locations[i].fun_address for i in still_missing_names}
        for name, address in still_missing.items():
            logger.warning(f"{name} located at {address} was not found in tprek.")
            info = {
                "name": {"fi": name},
                "street_address": {"fi": address},
                "address_locality": {"fi": "Helsinki"},
                "data_source": self.data_source,
                "publisher": self.organization,
            }
            course = [
                i for i in data if i["locations"] and i["locations"][0]["name"] == name
            ][0]
            info["origin_id"] = course["id"]
            tprekId = self.save_place(info)
            locations[name].tprekId = tprekId
        return locations

    def _log_duplicates(self, places):
        checker = {}
        for place in places:
            checker[place.name] = checker.get(place.name, 0) + 1
        multiple_mentions = [k for k, v in checker.items() if v > 1]
        if multiple_mentions:
            logger.error(
                f'Following place names match several addresses in FunActionNuo'
                f'rille system: {" ".join(multiple_mentions)}'
            )

    def _clean_address(self, address):
        """The function extracts about 95% of the Finnish addresses of
           the type Mannerheimintie 3A for the Helsinki area. Street names from
           this link TODO ADD LINK
        """
        toponyms = "(aukio|kaari|kaski|katu|kuja|kulma|laituri|linja|\
                     metsätie|mäki|penger|piha|polku|porras|portti|puisto|\
                     puistokatu|puutarha|raitti|ranta|rinne|saari|silta|suu|tie\
                     |tori)"
        expr = re.compile(
            fr"(([A-ZÄÖ][a-zäåöé]+{toponyms})|(((-){{0,1}}[A-ZÄÖ][a-zåéäö]+\s){{1,2}}{toponyms}))[\s][0-9]{{1,3}}(([\s]{{0,1}}[A-Za-z])|(-[0-9]))?"  # noqa: E501
        )
        if expr.search(address):
            return (
                expr.search(address).group(0).rstrip()
            )  # TODO: implement a moderator-powered way to handle too messy addresses
        else:
            return None

    def _fetch_paginated_data(self, url):
        cnt = 1
        with requests.Session() as s:
            s.headers.update(
                {"User-Agent": ""}
            )  # TODO: without this request returns 403. to be fixed with API providers.

            data, code = self._fetch_page(session=s, counter=cnt)
            if code != 200:
                message = f"Could not fetch data, got HTTP code {code}"
                raise APIBrokenError(message=message)
            while code == 200:
                cnt = cnt + 1
                page, code = self._fetch_page(session=s, counter=cnt)
                if page:
                    data.extend(page)
            return data

    def _fetch_page(self, session, counter):
        response = session.get(f"{FUNACTION_URL}{counter}")
        if response.status_code == 200:
            try:
                root_doc = response.json()
                return (root_doc, response.status_code)
            except ValueError:
                message = "Invalid JSON received"
                raise APIBrokenError(message=message)
        else:
            return (None, response.status_code)
