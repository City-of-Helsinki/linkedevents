# -*- coding: utf-8 -*-
import json
import re
import datetime
from dateutil.parser import parse
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import CommandError
import pytz
import requests
from events.exporter.base import register_exporter, Exporter
from events.models import Event, ExportInfo, Category, Place
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from icalendar import Calendar, Event as CalendarEvent

BASE_API_URL = settings.CITYSDK_API_SETTINGS['CITYSDK_URL']
EVENTS_URL = BASE_API_URL + 'events/'
POIS_URL = BASE_API_URL + 'pois/'
CATEGORY_URL = BASE_API_URL + 'categories?List='

# maps ISO 639-1 alpha-2 to BCP 47 tags consumed by CitySDK
bcp47_lang_map = {
    "fi": "fi-FI",
    "sv": "sv-SE",  # or sv-FI?
    "en": "en-GB"
}

# CITYSDK_DEFAULT_AUTHOR = {
#     "term": "primary",
#     "href": "http://events.hel.fi",
#     "value": "linkedevents"
# }
CITYSDK_DEFAULT_AUTHOR = {
    "term": "primary",
    "value": "admin"
}

CITYSDK_DEFAULT_LICENSE = {
    "term": "primary",
    "value": "open-data"
}

CITYSDK_EVENT_DEFAULTS_TPL = {
    "base": EVENTS_URL,
    "lang": bcp47_lang_map[settings.LANGUAGES[0][0]],
    "author": CITYSDK_DEFAULT_AUTHOR,
    "license": CITYSDK_DEFAULT_LICENSE
}

CITYSDK_POI_DEFAULTS_TPL = {
    "base": POIS_URL,
    "lang": settings.LANGUAGES[0][0],
    "author": CITYSDK_DEFAULT_AUTHOR,
    "license": CITYSDK_DEFAULT_LICENSE
}

# Create and set default category before use!
DEFAULT_POI_CATEGORY = settings.CITYSDK_API_SETTINGS['DEFAULT_POI_CATEGORY']

# local Category.CATEGORY_TYPES to CitySDK category types
category_types = ["event", "poi"]

def jsonize(from_dict):
    return json.dumps(from_dict, cls=DjangoJSONEncoder)


def generate_icalendar_element(event):
    icalendar_event = CalendarEvent()
    if event.start_time:
        icalendar_event.add('dtstart', event.start_time)
    if event.end_time:
        icalendar_event.add('dtend', event.end_time)
    if event.name_en:
        icalendar_event.add('summary', event.name_en)

    cal = Calendar()
    cal.add('version', '2.0')
    cal.add('prodid', '-//events.hel.fi//NONSGML Feeder//EN')
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
            "value": cal.to_ical(),
            "type": "text/icalendar"
        }
    else:
        return None


@register_exporter
class CitySDKExporter(Exporter):
    name = 'CitySDK'
    session_cookies = None
    response_headers = {'content-type': 'application/json'}

    def setup(self):
        self.authenticate()

        # TODO: create default category for POIs to remote system if
        # not yet created

    def authenticate(self):
        """
        Authenticate, CitySDK uses session based username/password auth
        """
        username = settings.CITYSDK_API_SETTINGS['USERNAME']
        password = settings.CITYSDK_API_SETTINGS['PASSWORD']
        # noinspection PyUnusedLocal
        session_response = requests.get(
            '%sauth?username=%s&password=%s' %
            (BASE_API_URL, username, password))
        if session_response.status_code == 200:
            self.session_cookies = session_response.cookies
            print("Authentication successful with response: %s"
                  % session_response.text)
        else:
            raise CommandError(
                "Authentication failed with credentials %s:%s" % (
                    (username, password)
                ))

    def _generate_exportable_event(self, event):
        citysdk_event = CITYSDK_EVENT_DEFAULTS_TPL.copy()

        # fetch category ID from exported categories
        citysdk_event['category'] = []
        for category in event.categories.all():
            exported_category = ExportInfo.objects.filter(
                content_type=ContentType.objects.get_for_model(Category),
                object_id=category.id,
                target_system=self.name).first()
            citysdk_event['category'].append(
                {"id": exported_category.target_id})

        if event.location:
            exported_poi = ExportInfo.objects.filter(
                content_type=ContentType.objects.get_for_model(Place),
                object_id=event.location.id,
                target_system=self.name).first()

            citysdk_event['location'] = {
                "relationship": [
                    {
                        "targetPOI": exported_poi.target_id,
                        "term": "equal",
                        "base": "http://tourism.citysdk.cm-lisboa.pt/pois/"
                    }
                ]
            }

        citysdk_event['time'] = generate_icalendar_element(event)

        # Translated fields are processed in similar manner.
        # The url/link is a bit different beast as there's no actual lang
        # definition in CitySDK for links
        # -> just generate normal links for all lang versions
        for from_field_name, to_field_name in [("description", "description"),
                                               ("name", "label"),
                                               ("url", "link")]:
            citysdk_event[to_field_name] = []
            for lang in [x[0] for x in settings.LANGUAGES]:
                value = getattr(event, '%s_%s' % (from_field_name, lang))
                if value:
                    lang_dict = {}
                    if to_field_name == 'link':
                        lang_dict['term'] = 'related'  # something else?
                        lang_dict['href'] = value
                        lang_dict['type'] = 'text/html'
                    else:
                        lang_dict['value'] = value
                        lang_dict['lang'] = bcp47_lang_map[lang]
                        if to_field_name == 'label':
                            lang_dict['term'] = 'primary'

                        citysdk_event[to_field_name].append(lang_dict)

        return citysdk_event

    @staticmethod
    def _generate_exportable_category(event):
        citysdk_category = dict()

        citysdk_category['author'] = CITYSDK_DEFAULT_AUTHOR
        citysdk_category['lang'] = bcp47_lang_map[settings.LANGUAGES[0][0]]
        citysdk_category['term'] = 'category'

        to_field_name = 'label'
        citysdk_category[to_field_name] = []
        for lang in [x[0] for x in settings.LANGUAGES]:
            value = getattr(event, '%s_%s' % ("name", lang))
            if value:
                lang_dict = {
                    'term': 'primary',
                    'value': value,
                    'lang': bcp47_lang_map[lang]
                }
                citysdk_category[to_field_name].append(lang_dict)

        return citysdk_category

    @staticmethod
    def _generate_exportable_place(place):
        citysdk_place = CITYSDK_POI_DEFAULTS_TPL.copy()

        # Linked Events places don't have any categories yet,
        # use default ID
        citysdk_place['category'] = [{"id": DEFAULT_POI_CATEGORY}]

        # Support for bboxes later, now Point is only possible value
        if place.location:
            coords_as_wkt = place.location.json
            matches = re.search('POINT \\((.*)\\)', place.location.wkt)
            if matches:
                coords = matches.group(1)
                citysdk_place['location'] = {
                    "point": [
                        {
                            "Point": {
                                "posList": coords,
                                "srsName":
                                    settings.CITYSDK_API_SETTINGS['SRS_URL']
                            },
                            "term": "entrance",
                        }
                    ]
                }

        for from_field_name, to_field_name in [("description", "description"),
                                               ("name", "label")]:
            citysdk_place[to_field_name] = []
            for lang in [x[0] for x in settings.LANGUAGES]:
                value = getattr(place, '%s_%s' % (from_field_name, lang))
                if value:
                    lang_dict = {}
                    if to_field_name == 'link':
                        lang_dict['term'] = 'related'  # something else?
                        lang_dict['href'] = value
                        lang_dict['type'] = 'text/html'
                    else:
                        lang_dict['value'] = value
                        lang_dict['lang'] = bcp47_lang_map[lang]
                        if to_field_name == 'label':
                            lang_dict['term'] = 'primary'

                        citysdk_place[to_field_name].append(lang_dict)

        return citysdk_place

    def _export_new(self):
        self._export_categories()
        self._export_places()
        self._export_events()

    def _export_categories(self):
        category_type = ContentType.objects.get_for_model(Category)

        export_infos = ExportInfo.objects.filter(content_type=category_type,
                                                 target_system=self.name)

        # deleted or modified
        for export_info in export_infos:
            try:
                category = Category.objects.get(pk=export_info.object_id)
                category_type_str = category_types[category.category_for]
                if category.last_modified_time > export_info.last_exported_time:
                    citysdk_category = self._generate_exportable_category(
                        category)
                    citysdk_category['id'] = export_info.target_id
                    json = jsonize({'list': category_type_str,
                                    'category': citysdk_category})
                    response = requests.post(CATEGORY_URL + category_type_str,
                                             data=json,
                                             headers=self.response_headers,
                                             cookies=self.session_cookies)
                    if response.status_code == 200:
                        export_info.save()  # refresh last export date
                        print(
                        "Category updated (original id: %d, target id: %s)" %
                        (category.pk, export_info.target_id))

            except ObjectDoesNotExist:
                response = requests.delete(CATEGORY_URL +
                                           category_type_str,
                                           headers=self.response_headers,
                                           data=jsonize({
                                               "id": export_info.target_id}),
                                           cookies=self.session_cookies)
                if response.status_code == 200:
                    export_info.delete()
                    print("Category removed (original id: %d, target id: %s) "
                          "from target system" %
                          (export_info.object_id, export_info.target_id))

        # new
        for category in Category.objects.exclude(
                id__in=export_infos.values('object_id')):
            category_type_str = category_types[category.category_for]
            citysdk_category = self._generate_exportable_category(category)
            citysdk_category['created'] = datetime.datetime.utcnow().replace(
                tzinfo=pytz.utc)

            json = jsonize({'list': category_type_str,
                            'category': citysdk_category})
            response = requests.put(CATEGORY_URL + category_type_str,
                                    data=json,
                                    headers=self.response_headers,
                                    cookies=self.session_cookies)
            if response.status_code == 200:
                new_category = response.json()
                new_export_info = ExportInfo(content_object=category,
                                             target_id=new_category,
                                             target_system=self.name)
                new_export_info.save()
                print("Category exported (original id: %d, target id: %s)" %
                      (category.pk, new_category))

    def _export_places(self):
        place_type = ContentType.objects.get_for_model(Place)

        # get all exported
        export_infos = ExportInfo.objects.filter(content_type=place_type,
                                                 target_system=self.name)

        # deleted or modified
        for export_info in export_infos:
            try:
                place = Place.objects.get(pk=export_info.object_id)
                if place.last_modified_time > export_info.last_exported_time:
                    citysdk_place = self._generate_exportable_event(place)
                    citysdk_place['id'] = export_info.target_id
                    response = requests.post(POIS_URL,
                                             data=jsonize({"poi":
                                                          citysdk_place}),
                                             headers=self.response_headers,
                                             cookies=self.session_cookies)
                    if response.status_code == 200:
                        export_info.save()  # refresh last export date
                        print("Place/POI updated (original id: %d, "
                              "target id: %s)" %
                              (place.pk, export_info.target_id))

            except ObjectDoesNotExist:
                response = requests.delete(POIS_URL + export_info.target_id,
                                           headers=self.response_headers,
                                           cookies=self.session_cookies)
                if response.status_code == 200:
                    export_info.delete()
                    print("Place/POI removed (original id: %d, target id: %s) "
                          "from target system" %
                          (category_info.object_id, category_info.target_id))

        # new
        for place in Place.objects.exclude(id__in=export_infos.values("object_id")):
            citysdk_place = self._generate_exportable_place(place)
            print(citysdk_place)
            citysdk_place['created'] = datetime.datetime.utcnow().replace(
                tzinfo=pytz.utc)
            response = requests.put(POIS_URL,
                                    data=jsonize({"poi": citysdk_place}),
                                    headers=self.response_headers,
                                    cookies=self.session_cookies)
            if response.status_code == 200:
                new_event = response.json()
                print("Place/POI exported (original id: %d, target id: %s)" %
                      (place.pk, new_event['id']))
                new_export_info = ExportInfo(content_object=place,
                                             content_type=place_type,
                                             target_id=new_event['id'],
                                             target_system=self.name)
                new_export_info.save()
            else:
                print("Place/POI export failed (original id: %d)" % place.id)

    def _export_events(self):
        event_type = ContentType.objects.get_for_model(Event)

        # get all exported
        export_infos = ExportInfo.objects.filter(content_type=event_type,
                                                 target_system=self.name)

        # deleted or modified
        for export_info in export_infos:
            try:
                event = Event.objects.get(pk=export_info.object_id)
                if event.last_modified_time > export_info.last_exported_time:
                    citysdk_event = self._generate_exportable_event(event)
                    citysdk_event['id'] = export_info.target_id
                    response = requests.post(EVENTS_URL,
                                             data=jsonize({"event": citysdk_event}),
                                             headers=self.response_headers,
                                             cookies=self.session_cookies)
                    if response.status_code == 200:
                        export_info.save()  # refresh last export date
                        print("Event updated (original id: %d, target id: %s)" %
                              (event.pk, export_info.target_id))

            except ObjectDoesNotExist:
                response = requests.delete(EVENTS_URL + export_info.target_id,
                                           headers=self.response_headers,
                                           cookies=self.session_cookies)
                if response.status_code == 200:
                    export_info.delete()
                    print("Event removed (original id: %d, target id: %s) "
                          "from target system" %
                          (export_info.object_id, export_info.target_id))

        # new
        for event in Event.objects.exclude(
                id__in=export_infos.values("object_id")):
            citysdk_event = self._generate_exportable_event(event)
            citysdk_event['created'] = datetime.datetime.utcnow().replace(
                tzinfo=pytz.utc)
            response = requests.put(EVENTS_URL,
                                    data=jsonize({"event": citysdk_event}),
                                    headers=self.response_headers,
                                    cookies=self.session_cookies)
            if response.status_code == 200:
                new_event = response.json()
                print("Event exported (original id: %d, target id: %s)" %
                      (event.pk, new_event['id']))
                new_export_info = ExportInfo(content_object=event,
                                             content_type=event_type,
                                             target_id=new_event['id'],
                                             target_system=self.name)
                new_export_info.save()
            else:
                 print("Event export failed (original id: %d)" % event.pk)

    def __delete_resource(self, resource, url):
        response = requests.delete('%s/%s' % (url,
                                              resource.target_id),
                                              cookies=self.session_cookies)
        if response.status_code == 200:
            resource.delete()
            print("%s removed (original id: %d, target id: %s) from "
                  "target system" %
                  (str(resource.content_type).capitalize(),
                   resource.object_id, resource.target_id))

    def _delete_exported_from_target(self):
        """
        Convenience method to delete everything imported from the source API,
        avoid in production use.
        """
        get_type = lambda klass: ContentType.objects.get_for_model(klass)

        for event_info in ExportInfo.objects.filter(
                content_type=get_type(Event),
                target_system=self.name):
            self.__delete_resource(event_info, EVENTS_URL)

        for place_info in ExportInfo.objects.filter(
                content_type=get_type(Place),
                target_system=self.name):
            self.__delete_resource(place_info, POIS_URL)

        for category_info in ExportInfo.objects.filter(
                content_type=get_type(Category),
                target_system=self.name):
            try:
                category = Category.objects.get(pk=category_info.object_id)
                response = requests.delete(CATEGORY_URL +
                                           category_types[
                                               category.category_for],
                                           headers=self.response_headers,
                                           data=jsonize({
                                               "id": category_info.target_id}),
                                           cookies=self.session_cookies)
                if response.status_code == 200:
                    category_info.delete()
                    print("Category removed (original id: %d, target id: %s) "
                          "from target system" %
                          (category_info.object_id, category_info.target_id))
            except ObjectDoesNotExist:
                print("ERROR: Category (original id: %d) "
                      "does not exist in local database" %
                      category_info.object_id)

    def export_events(self, is_delete=False):

        if is_delete:
            self._delete_exported_from_target()
        else:
            self._export_new()
