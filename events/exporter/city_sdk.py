import datetime
import json
import re

import pytz
import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import CommandError
from django.core.serializers.json import DjangoJSONEncoder
from httmock import HTTMock, all_requests, response
from icalendar import Calendar
from icalendar import Event as CalendarEvent

from events.exporter.base import Exporter, register_exporter
from events.models import Event, ExportInfo, Keyword, Place

BASE_API_URL = settings.CITYSDK_API_SETTINGS["CITYSDK_URL"]
EVENTS_URL = BASE_API_URL + "events/"
POIS_URL = BASE_API_URL + "pois/"
CATEGORY_URL = BASE_API_URL + "categories?List=event"

DRY_RUN_MODE = False  # If set True, do just local DB actions
VERBOSE = False  # If set to True, print verbose creation logs

# maps ISO 639-1 alpha-2 to BCP 47 tags consumed by CitySDK
bcp47_lang_map = {"fi": "fi-FI", "sv": "sv-SE", "en": "en-GB"}  # or sv-FI?

CITYSDK_DEFAULT_AUTHOR = {"term": "primary", "value": "admin"}

CITYSDK_DEFAULT_LICENSE = {"term": "primary", "value": "open-data"}

CITYSDK_EVENT_DEFAULTS_TPL = {
    "base": EVENTS_URL,
    "lang": bcp47_lang_map[settings.LANGUAGES[0][0]],
    "author": CITYSDK_DEFAULT_AUTHOR,
    "license": CITYSDK_DEFAULT_LICENSE,
}

CITYSDK_POI_DEFAULTS_TPL = {
    "base": POIS_URL,
    "lang": settings.LANGUAGES[0][0],
    "author": CITYSDK_DEFAULT_AUTHOR,
    "license": CITYSDK_DEFAULT_LICENSE,
}

# Create and set default category before use!
DEFAULT_POI_CATEGORY = settings.CITYSDK_API_SETTINGS["DEFAULT_POI_CATEGORY"]


def jsonize(from_dict):
    return json.dumps(from_dict, cls=DjangoJSONEncoder)


def generate_icalendar_element(event):
    icalendar_event = CalendarEvent()
    if event.start_time:
        icalendar_event.add("dtstart", event.start_time)
    if event.end_time:
        icalendar_event.add("dtend", event.end_time)
    if event.name_en:
        icalendar_event.add("summary", event.name_en)

    cal = Calendar()
    cal.add("version", "2.0")
    cal.add("prodid", "-//events.hel.fi//NONSGML Feeder//EN")
    cal.add_component(icalendar_event)

    term = None
    if event.start_time and event.end_time:
        term = "open"
    elif event.start_time:
        term = "open"
    elif event.end_time:
        term = "close"

    if term:
        return {
            "term": "open",
            "value": cal.to_ical().decode("utf8"),
            "type": "text/icalendar",
        }
    else:
        return None


@register_exporter
class CitySDKExporter(Exporter):
    name = "CitySDK"
    session_cookies = None
    response_headers = {"content-type": "application/json"}

    def setup(self):
        self.authenticate()

    def authenticate(self):
        """
        Authenticate, CitySDK uses session based username/password auth
        """
        username = settings.CITYSDK_API_SETTINGS["USERNAME"]
        password = settings.CITYSDK_API_SETTINGS["PASSWORD"]
        session_response = requests.get(
            "%sauth?username=%s&password=%s" % (BASE_API_URL, username, password)
        )
        if session_response.status_code == 200:
            self.session_cookies = session_response.cookies
            print("Authentication successful with response: %s" % session_response.text)
        else:
            raise CommandError(
                "Authentication failed with credentials %s:%s" % ((username, password))
            )

    def _generate_exportable_event(self, event):
        citysdk_event = CITYSDK_EVENT_DEFAULTS_TPL.copy()

        # fetch category ID from exported categories
        citysdk_event["category"] = []
        for category in event.keywords.all():
            exported_category = ExportInfo.objects.filter(
                content_type=ContentType.objects.get_for_model(Keyword),
                object_id=category.id,
                target_system=self.name,
            ).first()
            citysdk_event["category"].append({"id": exported_category.target_id})

        if event.location:
            exported_poi = ExportInfo.objects.filter(
                content_type=ContentType.objects.get_for_model(Place),
                object_id=event.location.id,
                target_system=self.name,
            ).first()

            citysdk_event["location"] = {
                "relationship": [
                    {
                        "targetPOI": exported_poi.target_id,
                        "term": "equal",
                        "base": POIS_URL,
                    }
                ]
            }

        citysdk_event["time"] = generate_icalendar_element(event)

        # Translated fields are processed in similar manner.
        # The url/link is a bit different beast as there's no actual lang
        # definition in CitySDK for links
        # -> just generate normal links for all lang versions
        for from_field_name, to_field_name in [
            ("description", "description"),
            ("name", "label"),
            ("info_url", "link"),
        ]:
            citysdk_event[to_field_name] = []
            for lang in [x[0] for x in settings.LANGUAGES]:
                value = getattr(event, "%s_%s" % (from_field_name, lang))
                if value:
                    lang_dict = {}
                    if to_field_name == "link":
                        lang_dict["term"] = "related"  # something else?
                        lang_dict["href"] = value
                        lang_dict["type"] = "text/html"
                    else:
                        lang_dict["value"] = value
                        lang_dict["lang"] = bcp47_lang_map[lang]
                        if to_field_name == "label":
                            lang_dict["term"] = "primary"

                        citysdk_event[to_field_name].append(lang_dict)

        return citysdk_event

    @staticmethod
    def _generate_exportable_category(event):
        citysdk_category = dict()

        citysdk_category["author"] = CITYSDK_DEFAULT_AUTHOR
        citysdk_category["lang"] = bcp47_lang_map[settings.LANGUAGES[0][0]]
        citysdk_category["term"] = "category"

        to_field_name = "label"
        citysdk_category[to_field_name] = []
        for lang in [x[0] for x in settings.LANGUAGES]:
            value = getattr(event, "%s_%s" % ("name", lang))
            if value:
                lang_dict = {
                    "term": "primary",
                    "value": value,
                    "lang": bcp47_lang_map[lang],
                }
                citysdk_category[to_field_name].append(lang_dict)

        return citysdk_category

    @staticmethod
    def _generate_exportable_place(place):
        citysdk_place = CITYSDK_POI_DEFAULTS_TPL.copy()

        # Linked Events places don't have any categories yet,
        # use default ID
        citysdk_place["category"] = [{"id": DEFAULT_POI_CATEGORY}]

        # Support for bboxes later, now Point is only possible value
        if place.position:
            matches = re.search("POINT \\((.*)\\)", place.position.wkt)
            if matches:
                coords = matches.group(1)
                citysdk_place["location"] = {
                    "point": [
                        {
                            "Point": {
                                "posList": coords,
                                "srsName": settings.CITYSDK_API_SETTINGS["SRS_URL"],
                            },
                            "term": "entrance",
                        }
                    ]
                }

        for from_field_name, to_field_name in [
            ("description", "description"),
            ("name", "label"),
        ]:
            citysdk_place[to_field_name] = []
            for lang in [x[0] for x in settings.LANGUAGES]:
                value = getattr(place, "%s_%s" % (from_field_name, lang))
                if value:
                    lang_dict = {}
                    if to_field_name == "link":
                        lang_dict["term"] = "related"  # something else?
                        lang_dict["href"] = value
                        lang_dict["type"] = "text/html"
                    else:
                        lang_dict["value"] = value
                        lang_dict["lang"] = bcp47_lang_map[lang]
                        if to_field_name == "label":
                            lang_dict["term"] = "primary"

                        citysdk_place[to_field_name].append(lang_dict)

        return citysdk_place

    def _export_new(self):
        self._export_categories()
        self._export_places()
        self._export_events()

    def _export_models(self, klass, generate, url, json_wrapper, extra_filters=None):
        model_type = ContentType.objects.get_for_model(klass)

        # get all exported
        export_infos = ExportInfo.objects.filter(
            content_type=model_type, target_system=self.name
        )

        model_name = klass.__name__
        modify_count = 0
        delete_count = 0
        new_count = 0

        # deleted or modified
        for export_info in export_infos:
            try:
                model = klass.objects.get(pk=export_info.object_id)
                if model.last_modified_time > export_info.last_exported_time:
                    citysdk_model = generate(model)
                    citysdk_model["id"] = export_info.target_id
                    if model_name == "Keyword":
                        data = {"list": "event", "category": citysdk_model}
                    else:
                        data = {json_wrapper: citysdk_model}
                    modify_response = self._do_req("post", url, data)
                    if modify_response.status_code == 200:
                        export_info.save()  # refresh last export date
                        print(
                            "%s updated (original id: %s, target id: %s)"
                            % (model_name, model.pk, export_info.target_id)
                        )
                        modify_count += 1

            except ObjectDoesNotExist:
                if model_name == "Keyword":
                    delete_response = self._do_req(
                        "delete", url, data={"id": export_info.target_id}
                    )
                else:
                    delete_response = self._do_req(
                        "delete", url + export_info.target_id
                    )
                if delete_response.status_code == 200:
                    export_info.delete()
                    print(
                        "%s removed (original id: %d, target id: %s) "
                        "from target system"
                        % (model_name, export_info.object_id, export_info.target_id)
                    )
                    delete_count += 1

        # new
        imported = {"id__in": export_infos.values("object_id")}
        if extra_filters:
            qs = klass.objects.exclude(**imported).filter(**extra_filters).distinct()
        else:
            qs = klass.objects.exclude(**imported)
        for model in qs:
            citysdk_model = generate(model)
            citysdk_model["created"] = datetime.datetime.utcnow().replace(
                tzinfo=pytz.utc
            )
            if model_name == "Keyword":
                data = {"list": "event", "category": citysdk_model}
            else:
                data = {json_wrapper: citysdk_model}
            new_response = self._do_req("put", url, data)
            if new_response.status_code == 200:
                new = new_response.json()
                if isinstance(new, dict) and "id" in new:
                    new_id = new["id"]
                else:
                    new_id = new
                if VERBOSE:
                    print(
                        "%s exported (original id: %d, target id: %s)"
                        % (model_name, model.pk, new_id)
                    )
                new_export_info = ExportInfo(
                    content_object=model,
                    content_type=model_type,
                    target_id=new_id,
                    target_system=self.name,
                )
                new_export_info.save()
                new_count += 1
            else:
                print("%s export failed (original id: %s)" % (model_name, model.pk))

        print(model_name + " items added: " + str(new_count))
        print(model_name + " items modified: " + str(modify_count))
        print(model_name + " items deleted: " + str(delete_count))

    def _do_req(self, method, url, data=None):
        kwargs = {"headers": self.response_headers, "cookies": self.session_cookies}
        if data:
            kwargs["data"] = jsonize(data)

        if DRY_RUN_MODE:
            with HTTMock(citysdk_mock):
                return requests.request(method, url, **kwargs)
        else:
            resp = requests.request(method, url, **kwargs)
            # if session dies while doing exporting
            if resp.status_code == 401:
                self.authenticate()
                return requests.request(method, url, **kwargs)
            assert resp.status_code == 200
            return resp

    def _export_categories(self):
        filters = {"event__in": Event.objects.all()}
        self._export_models(
            Keyword,
            self._generate_exportable_category,
            CATEGORY_URL,
            "poi",
            extra_filters=filters,
        )

    def _export_places(self):
        filters = {"event__in": Event.objects.all()}
        self._export_models(
            Place,
            self._generate_exportable_place,
            POIS_URL,
            "poi",
            extra_filters=filters,
        )

    def _export_events(self):
        self._export_models(Event, self._generate_exportable_event, EVENTS_URL, "event")

    def __delete_resource(self, resource, url):
        response = self._do_req("delete", "%s/%s" % (url, resource.target_id))
        if response.status_code == 200:
            resource.delete()
            print(
                "%s removed (original id: %d, target id: %s) from "
                "target system"
                % (
                    str(resource.content_type).capitalize(),
                    resource.object_id,
                    resource.target_id,
                )
            )

    def _delete_exported_from_target(self):
        """
        Convenience method to delete everything imported from the source API,
        avoid in production use.
        """
        for event_info in ExportInfo.objects.filter(
            content_type=ContentType.objects.get_for_model(Event),
            target_system=self.name,
        ):
            self.__delete_resource(event_info, EVENTS_URL)

        for place_info in ExportInfo.objects.filter(
            content_type=ContentType.objects.get_for_model(Place),
            target_system=self.name,
        ):
            self.__delete_resource(place_info, POIS_URL)

        for category_info in ExportInfo.objects.filter(
            content_type=ContentType.objects.get_for_model(Keyword),
            target_system=self.name,
        ):
            try:
                category_response = self._do_req(
                    "delete",
                    CATEGORY_URL + "event",
                    data={"id": category_info.target_id},
                )
                if category_response.status_code == 200:
                    category_info.delete()
                    print(
                        "Category removed (original id: %d, target id: %s) "
                        "from target system"
                        % (category_info.object_id, category_info.target_id)
                    )
            except ObjectDoesNotExist:
                print(
                    "ERROR: Category (original id: %d) "
                    "does not exist in local database" % category_info.object_id
                )

    def export_events(self, is_delete=False):
        if is_delete:
            self._delete_exported_from_target()
        else:
            self._export_new()


# For dry run request mocking
@all_requests
def citysdk_mock(url, request):
    foo = "foo"
    if request.method == "PUT":
        data = '"' + foo + '"'
    else:
        data = {"id": str(foo)}
    headers = {"content-type": "application/json"}
    return response(200, data, headers, None, 0, request)
