import logging
import re
from collections import OrderedDict

import dateutil.parser
import pytz
import requests
import requests_cache
from django.db.models import Count
from django_orghierarchy.models import Organization
from lxml import etree

from events.keywords import KeywordMatcher
from events.models import DataSource, Event, Place

from .base import Importer, recur_dict, register_importer
from .util import clean_text, replace_location, unicodetext

logger = logging.getLogger(__name__)

MATKO_URLS = {
    "places": OrderedDict(
        [
            ("fi", "http://www.visithelsinki.fi/misc/feeds/helsinki_matkailu_poi.xml"),
            ("en", "http://www.visithelsinki.fi/misc/feeds/helsinki_tourism_poi.xml"),
            ("sv", "http://www.visithelsinki.fi/misc/feeds/helsingfors_turism_poi.xml"),
        ]
    ),
    "events": OrderedDict(
        [
            ("fi", "http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat.xml"),
            ("en", "http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat_en.xml"),
            ("sv", "http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat_se.xml"),
        ]
    ),
}

LOCATION_TPREK_MAP = {
    "helsingin kaupunginteatteri / lilla teatern": "9353",
    "helsingin kaupunginteatteri / teatteristudio pasila": "9340",
    "finlandia-talo": "9294",
    "helsingin kaupunginmuseo": "8663",
    "helsingin kaupunginmuseo/ hakasalmen huvila": "8645",
    "tuomiokirkko": "43181",
    "sotamuseo": "25782",
    "mäkelänrinteen uintikeskus": "41783",
    "uimastadion": "41047",
    "eläintarhan yleisurheilukenttä": "40498",
    "korkeasaaren eläintarha": "7245",
    "helsingin taidemuseo ham": "8675",
    "info- ja näyttelytila laituri": "8609",
}

EXTRA_LOCATIONS = {
    732: {
        "name": {
            "fi": "Helsinki",
            "sv": "Helsingfors",
            "en": "Helsinki",
        },
        "address": {
            "address_locality": {
                "fi": "Helsinki",
            }
        },
        "latitude": 60.170833,
        "longitude": 24.9375,
    },
    1101: {
        "name": {
            "fi": "Helsingin keskusta",
            "sv": "Helgingfors centrum",
            "en": "Helsinki City Centre",
        },
        "address": {
            "address_locality": {
                "fi": "Helsinki",
            }
        },
        "latitude": 60.170833,
        "longitude": 24.9375,
    },
}


def matko_tag(tag):
    return "{https://aspicore-asp.net/matkoschema/}" + tag


def text(item, tag):
    return unicodetext(item.find(matko_tag(tag)))


def matko_status(num):
    if num == 2:
        return Event.Status.SCHEDULED
    if num == 3:
        return Event.Status.CANCELLED
    return None


def zipcode_and_muni(text):
    if text is None:
        return None, None
    m = re.match(r"\D*(\d+)\s+(\D+)", text)
    if m is not None:
        return m.group(1), m.group(2).strip()
    return None, None


@register_importer
class MatkoImporter(Importer):
    name = "matko"
    supported_languages = ["fi", "sv", "en"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timezone = pytz.timezone("Europe/Helsinki")

    def put(self, rdict, key, val):
        if key not in rdict:
            rdict[key] = val
        elif val != rdict[key]:
            logger.info(
                "Values differ for %s, key %s, values %s and %s "
                % (rdict, key, val, rdict[key])
            )

    def setup(self):
        defaults = dict(name="Matkailu- ja kongressitoimisto")
        self.data_source, _ = DataSource.objects.get_or_create(
            id=self.name, defaults=defaults
        )
        self.tprek_data_source = DataSource.objects.get(id="tprek")

        ytj_ds, _ = DataSource.objects.get_or_create(defaults={"name": "YTJ"}, id="ytj")

        org_args = dict(origin_id="0586977-6", data_source=ytj_ds)
        defaults = dict(name="Helsingin Markkinointi Oy")

        self.organization, _ = Organization.objects.get_or_create(
            defaults=defaults, **org_args
        )

        place_list = Place.objects.filter(
            data_source=self.tprek_data_source, deleted=False
        )
        deleted_place_list = Place.objects.filter(
            data_source=self.tprek_data_source, deleted=True
        )
        # Get only places that have unique names
        place_list = (
            place_list.annotate(count=Count("name_fi"))
            .filter(count=1)
            .values("id", "origin_id", "name_fi")
        )
        deleted_place_list = (
            deleted_place_list.annotate(count=Count("name_fi"))
            .filter(count=1)
            .values("id", "origin_id", "name_fi", "replaced_by_id")
        )
        self.tprek_by_name = {
            p["name_fi"].lower(): (p["id"], p["origin_id"]) for p in place_list
        }
        self.deleted_tprek_by_name = {
            p["name_fi"].lower(): (p["id"], p["origin_id"], p["replaced_by_id"])
            for p in deleted_place_list
        }

        if self.options["cached"]:
            requests_cache.install_cache("matko")

    def _import_common(self, lang_code, item, result):
        result["name"][lang_code] = clean_text(unicodetext(item.find("title")))
        result["description"][lang_code] = unicodetext(item.find("description"))

        link = item.find("link")
        if link is not None:
            result["info_url"][lang_code] = unicodetext(link)

    def _find_place_from_tprek(self, location, include_deleted=False):
        if "fi" in location["name"]:
            place_name = location["name"]["fi"]
        else:
            place_name = location["name"].values()[0]
        if not place_name:
            return
        place_name = place_name.lower()
        if place_name in LOCATION_TPREK_MAP:
            tprek_id = LOCATION_TPREK_MAP[place_name]
            place_id = Place.objects.get(
                data_source=self.tprek_data_source, origin_id=tprek_id
            ).id
        elif place_name in self.tprek_by_name:
            place_id, tprek_id = self.tprek_by_name[place_name]
        else:
            # fallback to deleted if requested
            if include_deleted and place_name in self.deleted_tprek_by_name:
                place_id, tprek_id, replaced_by_id = self.deleted_tprek_by_name[
                    place_name
                ]
                if replaced_by_id:
                    logger.info("Place " + place_id + " replaced by " + replaced_by_id)
                    place_id = replaced_by_id
            else:
                return None

        # found places are kept mapped to tprek even if literal matko match exists
        place = Place.objects.get(id=place_id)
        try:
            matko_place = Place.objects.get(
                data_source=self.data_source, origin_id=location["origin_id"]
            )
            if not (matko_place.deleted and matko_place.replaced_by == place):
                replace_location(replace=matko_place, by=place)
        except Place.DoesNotExist:
            pass

        return place_id

    def _find_place(self, location):
        place_id = self._find_place_from_tprek(location)
        if place_id:
            return place_id

        # No tprek match found, attempt to find the right entry from matko locations.
        matko_id = location["origin_id"]
        try:
            place = Place.objects.get(data_source=self.data_source, origin_id=matko_id)
        except Place.DoesNotExist:
            place = None
        if place and place.deleted:
            # The matko location has been superseded by tprek, but the tprek location no longer exists!
            replace_location(from_source="tprek", by=place)

        # No existing entry, load it from Matko.
        if not place:
            places = self._fetch_places()
            from pprint import pprint

            if matko_id not in places:
                # The final fallback is to use deleted tprek locations.
                logger.info(
                    "Matko location %s (%s) not found in feed!"
                    % (location["name"]["fi"], location["origin_id"])
                )
                logger.info("Reverting back to deleted tprek locations.")
                place_id = self._find_place_from_tprek(location, include_deleted=True)
                if place_id:
                    logger.warning(location["name"]["fi"] + " found deleted in tprek!")
                    return place_id
                logger.warning(location["name"]["fi"] + " not found in tprek history!")
                return None
            logger.info(
                "Place %s found in matko feed, importing." % location["name"]["fi"]
            )
            pprint(places[matko_id])
            place = self.save_place(places[matko_id])

        return place.id

    def _import_event_from_feed(self, lang_code, item, events, keyword_matcher):
        eid = int(text(item, "uniqueid"))
        if self.options["single"] and str(eid) != self.options["single"]:
            return

        event = events[eid]

        if eid != int(text(item, "id")):
            logger.info(
                "Unique id and id values differ for id %d uid %s"
                % (eid, text(item, "id"))
            )

        event["origin_id"] = eid
        event["data_source"] = self.data_source
        event["date_published"] = dateutil.parser.parse(
            unicodetext(item.find("pubDate"))
        )
        event["publisher"] = self.organization

        self._import_common(lang_code, item, event)

        organizer = text(item, "organizer")
        organizer_phone = text(item, "organizerphone")

        if organizer is not None:
            event["organizer"]["name"][lang_code] = clean_text(organizer)
        if organizer_phone is not None:
            event["organizer"]["phone"][lang_code] = [
                clean_text(t) for t in organizer_phone.split(",")
            ]

        start_time = dateutil.parser.parse(text(item, "starttime"))

        # The feed doesn't contain proper end times (clock).
        end_time = dateutil.parser.parse(text(item, "endtime"))

        # Check if the time of day is at midnight, and if so, treat
        # the timestamp as not having the time component.
        if start_time.hour == 0 and start_time.minute == 0 and start_time.second == 0:
            self.put(event, "has_start_time", False)
        # The time zone in the incoming data doesn't take into account daylight savings.
        start_time = self.timezone.localize(start_time.replace(tzinfo=None))
        end_time = self.timezone.localize(end_time.replace(tzinfo=None))
        if end_time.hour == 0 and end_time.minute == 0 and end_time.second == 0:
            self.put(event, "has_end_time", False)

        event["location"]["name"][lang_code] = text(item, "place")
        event["location"]["extra_info"][lang_code] = text(item, "placeinfo")

        self.put(event, "start_time", start_time)
        self.put(event, "end_time", end_time)
        self.put(event, "event_status", matko_status(int(text(item, "status"))))
        if text(item, "placeuniqueid") is None:
            del events[eid]
            return
        self.put(event["location"], "origin_id", int(text(item, "placeuniqueid")))

        ignore = [
            "ekokompassi",
            "helsinki-päivä",
            "helsinki-viikko",
            "top",
            "muu",
            "tapahtuma",
            "kesä",
            "talvi",
            "yksittäiset",
            "ryhmät",
        ]
        mapping = {
            "tanssi ja teatteri": "tanssi",  # following visithelsinki.fi
            "messu": "messut (tapahtumat)",
            "perinnetapahtuma": "perinne",
            "pop/rock": "populaarimusiikki",
            "konsertti": "konsertit",
            "klassinen": "taidemusiikki",
            "kulttuuri": "kulttuuritapahtumat",
            "suomi100": "suomi 100 vuotta -juhlavuosi",
            "markkinat": "markkinat (tapahtumat)",
            "lapset": "lapset (ikäryhmät)",
            "koko perheelle": "perheet (ryhmät)",
        }
        use_as_target_group = [
            "perheet (ryhmät)",
            "lapset (ikäryhmät)",
            "nuoret",
            "eläkeläiset",
        ]

        event_types = set()
        type1, type2, target_group = (
            text(item, "type1"),
            text(item, "type2"),
            text(item, "targetgroup"),
        )
        for t in (type1, type2, target_group):
            if t:
                event_types.update(map(lambda x: x.lower(), t.split(",")))

        # Save offers.is_free if 'ilmaistapahtumat' tag is present
        if "ilmaistapahtumat" in event_types:
            if "offers" not in event:
                event["offers"] = [recur_dict()]
            offer = event["offers"][0]
            offer["is_free"] = True

        keywords = []
        audience = []
        for t in event_types:
            if t is None or t in ignore:
                continue
            # match to LE keyword
            if t in mapping:
                t = mapping[t]
            keyword = keyword_matcher.match(t)
            if keyword:
                keywords.append(keyword[0])
                if t in use_as_target_group:
                    # retain the keyword in keywords as well, for backwards compatibility
                    audience.append(keyword[0])
        if len(keywords) > 0 or len(audience) > 0:
            event["keywords"] = keywords
            event["audience"] = audience
        else:
            logger.warning(
                "Warning: no keyword matches for {} keywords".format(event["name"])
            )

        if "id" not in event["location"]:
            place_id = self._find_place(event["location"])
            if place_id:
                event["location"]["id"] = place_id

        return events

    def _parse_location(self, lang_code, item, places):
        lid = int(text(item, "id"))
        location = places[lid]

        location["origin_id"] = lid
        location["data_source"] = self.data_source

        location["publisher"] = self.organization

        self._import_common(lang_code, item, location)

        address = text(item, "address")
        if address is not None:
            location["address"]["street_address"][lang_code] = clean_text(address)

        zipcode, muni = zipcode_and_muni(text(item, "zipcode"))
        if zipcode and len(zipcode) == 5:
            location["address"]["postal_code"] = zipcode
        location["address"]["address_locality"][lang_code] = muni
        location["address"]["phone"][lang_code] = text(item, "phone")
        # There was at least one case with different
        # email addresses for different languages.
        location["address"]["email"][lang_code] = text(item, "email")

        # not available in schema.org:
        # location['address']['fax'][lang_code] = text(item, 'fax')
        # location['directions'][lang_code] = text(item, 'location')
        # location['admission_fee'][lang_code] = text(item, 'admission')

        # todo: parse
        # location['opening_hours'][lang_code] = text(item, 'open')
        location["custom_fields"]["accessibility"][lang_code] = text(item, "disabled")

        lon, lat = clean_text(text(item, "longitude")), clean_text(
            text(item, "latitude")
        )
        if lon != "0" and lat != "0":
            self.put(location, "longitude", float(lon))
            self.put(location, "latitude", float(lat))

    def _parse_places_from_feed(self, lang_code, items, places):
        for item in items:
            self._parse_location(lang_code, item, places)

        return places

    def items_from_url(self, url):
        resp = requests.get(url, timeout=self.default_timeout)
        assert resp.status_code == 200
        root = etree.fromstring(resp.content)
        return root.xpath("channel/item")

    def import_events(self):
        logger.info("Importing Matko events")
        events = recur_dict()
        keyword_matcher = KeywordMatcher()
        for lang, url in MATKO_URLS["events"].items():
            items = self.items_from_url(url)
            for item in items:
                self._import_event_from_feed(lang, item, events, keyword_matcher)

        for event in events.values():
            self.save_event(event)
        logger.info("%d events processed" % len(events.values()))

    def _fetch_places(self):
        if hasattr(self, "places"):
            return self.places

        places = recur_dict()

        for origin_id, loc_info in EXTRA_LOCATIONS.items():
            loc = loc_info.copy()
            loc["data_source"] = self.data_source
            loc["origin_id"] = origin_id
            loc["publisher"] = self.organization
            places[origin_id] = loc

        for lang, url in MATKO_URLS["places"].items():
            items = self.items_from_url(url)
            self._parse_places_from_feed(lang, items, places)

        self.places = places

        return places

    def import_places(self):
        self._fetch_places()
        if self.options["single"]:
            logger.info(
                "Trying to find single matko location %s" % self.options["single"]
            )
            for matko_id, location in self.places.items():
                if (
                    location["name"]["fi"]
                    and location["name"]["fi"].lower() == self.options["single"].lower()
                ):
                    logger.info(
                        "Location %s (%s) found in matko feed"
                        % (self.options["single"], matko_id)
                    )
                    self.save_place(location)
                    return
            logger.warning(
                "Location %s not found in matko feed" % self.options["single"]
            )
            return
        logger.info("Updating existing matko places")
        place_list = Place.objects.filter(data_source=self.data_source)
        for place in place_list:
            origin_id = int(place.origin_id)
            if origin_id not in self.places:
                logger.warning("%s not found in Matko feed anymore" % place)
                continue
            place = self.places[origin_id]
            self.save_place(place)
