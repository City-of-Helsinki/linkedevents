#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from events import utils
from events.parsers import rename_fields
from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from events.serializers.serializers import ISO8601DurationField


class FieldRenamingTestCase(SimpleTestCase):
    def test_from_camelcase_conversions(self):
        self.assertEquals(utils.convert_from_camelcase('LoremIpsumIndaHouse'), 'lorem_ipsum_inda_house')
        self.assertEquals(utils.convert_from_camelcase('startsWithSmall'), 'starts_with_small')

    def test_to_camelcase_conversions(self):
        self.assertEquals(utils.convert_to_camelcase('lorem_ipsum_inda_house'), 'loremIpsumIndaHouse')

    def test_dict_structure_conversions(self):
        obj1 = {
            "idField": 1,
            "valueField": "blahblah",
            "boolFieldHere": True,
            "nestedArray": [1, {"valValOne": 1}, {"valValTwo": 2}, {"nestedNestedArray": ["lorem", "ipsum"]}]
        }

        obj2 = {
            "id_field": 1,
            "value_field": "blahblah",
            "bool_field_here": True,
            "nested_array": [1, {"val_val_one": 1}, {"val_val_two": 2}, {"nested_nested_array": ["lorem", "ipsum"]}]
        }

        self.assertTrue(rename_fields(obj1) == obj2)


class EventTests(APITestCase):
    def test_create_organization(self):
        url = reverse('organization-list')
        response = self.client.post(url, ORG_POST_JSON, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], ORG_POST_JSON["name"])

    def test_create_event(self):
        url = reverse('event-list')
        response = self.client.post(url, EVENT_POST_JSON, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], EVENT_POST_JSON['name'])


class SerializerTests(SimpleTestCase):
    def test_iso8601_serializing(self):
        ser = ISO8601DurationField()
        formatted_str = ser.to_native(5 * 60 * 60 * 1000 + 45 * 60 * 1000)
        self.assertEqual(formatted_str, 'PT5H45M')

    def test_iso8601_deserializing(self):
        ser = ISO8601DurationField()
        duration = ser.from_native('PT5H45M')
        self.assertEqual(duration, 5 * 60 * 60 * 1000 + 45 * 60 * 1000)


ORG_POST_JSON = {
    "@context": "http://schema.org",
    "@type": "Organization",
    "creator": None,
    "editor": None,
    "id": 1,
    "name": "Org 1",
    "image": "",
    "dateCreated": None,
    "dateModified": None,
    "discussionUrl": "",
    "thumbnailUrl": "",
    "description": "",
    "baseIri": "",
    "compactIriName": ""
}

EVENT_POST_JSON = {
    "type": "Event/LinkedEvent",
    "name": {
        "fi": "Tapahtuma 1",
        "en": "Event 1",
        "sv": u"Händelse 1"
    },
    "description": {
        "fi": "lorem",
        "en": "ipsum",
        "sv": "lorem"
    },
    "url": {
        "fi": "",
        "en": "",
        "sv": ""
    },
    "location": None,
    "publisher": None,
    "provider": None,
    "category": [],
    "offers": {
        "@type": "Offer",
        "seller": ORG_POST_JSON,
        "id": 1,
        "name": "asdasd",
        "image": "",
        "dateCreated": None,
        "dateModified": None,
        "discussionUrl": "",
        "thumbnailUrl": "",
        "availableAtOrFrom": None,
        "price": None,
        "priceCurrency": "",
        "validFrom": None,
        "validThrough": None,
        "sku": "",
    },
    "creator": [],
    "editor": None,
    "superEvent": None,
    "subEvent": [],
    "eventStatus": "EventScheduled",
    "customFields": {
        "dasda": "asdads",
        "sad": "asdads",
    },
    "image": "",
    "dateCreated": None,
    "dateModified": None,
    "discussionUrl": "",
    "thumbnailUrl": "",
    "datePublished": "2014-03-06T15:10:32Z",
    "doorTime": "",
    "duration": "PT7H55M22S",
    "endDate": "2014-03-06",
    "previousStartDate": None,
    "startDate": "",
    "typicalAgeRange": "",
    "originId": "",
    "targetGroup": "",
    "slug": "dasdadad",
    "dataSource": None,
    "performer": []
}
