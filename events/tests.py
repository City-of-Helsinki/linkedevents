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
        self.assertEquals(utils.convert_from_camelcase('LoremIpsumIndaHouse'),
                          'lorem_ipsum_inda_house')
        self.assertEquals(utils.convert_from_camelcase('startsWithSmall'),
                          'starts_with_small')

    def test_to_camelcase_conversions(self):
        self.assertEquals(utils.convert_to_camelcase('lorem_ipsum_inda_house'),
                          'loremIpsumIndaHouse')

    def test_dict_structure_conversions(self):
        obj1 = {
            "idField": 1,
            "valueField": "blahblah",
            "boolFieldHere": True,
            "nestedArray": [1, {"valValOne": 1}, {"valValTwo": 2},
                            {"nestedNestedArray": ["lorem", "ipsum"]}]
        }

        obj2 = {
            "id_field": 1,
            "value_field": "blahblah",
            "bool_field_here": True,
            "nested_array": [1, {"val_val_one": 1}, {"val_val_two": 2},
                             {"nested_nested_array": ["lorem", "ipsum"]}]
        }

        self.assertTrue(rename_fields(obj1) == obj2)


class APITests(APITestCase):
    def test_create_organization(self):
        url = reverse('organization-list')
        response = self.client.post(url, ORGANIZATION, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], ORGANIZATION["name"])

    def test_create_event(self):
        url = reverse('event-list')
        response = self.client.post(url, EVENT, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], EVENT['name'])

    def test_edit_event(self):
        change_to = 'different'
        url = reverse('event-list')
        event = EVENT.copy()
        response_post = self.client.post(url, event, format='json')
        event['name']['fi'] = change_to
        response_put = self.client.put(url + str(
            response_post.data['id']) + '/', event, format='json')
        self.assertEqual(response_put.status_code, status.HTTP_200_OK)
        self.assertEqual(response_put.data['name']['fi'], change_to)

    def test_create_and_get_with_super_event(self):
        url = reverse('event-list')
        response_one = self.client.post(url, EVENT, format='json')
        child_event = EVENT.copy()
        child_event['superEvent'] = {'@id': 'http://testserver' + url +
                                            str(response_one.data['id']) + '/'}
        response_two = self.client.post(url, child_event, format='json')
        response_three = self.client.get(url + str(response_two.data['id']) +
                                         '/', format='json')
        self.assertEquals(
            response_three.data['superEvent'], child_event['superEvent'])
        self.assertEqual(response_three.data['name'], EVENT['name'])

    def test_location_field_serialization(self):
        url = reverse('event-list')
        event = EVENT.copy()

        # Nested posting of place
        # TODO: This is still in the works
        event['location'] = PLACE
        response_post_event = self.client.post(url, event, format='json')
        response_two = self.client.get(url + str(
            response_post_event.data['id']) + '/')

        # Posting just a ID reference
        url_place = reverse('place-list')
        response_post_place = self.client.post(url_place, PLACE, format='json')
        event['location'] = {'@id': 'http://testserver' + url_place +
                                    str(response_post_place.data['id']) + '/'}
        response_post_event_two = self.client.post(url, event, format='json')
        self.assertEqual(response_post_event_two.data['location']['name'],
                         PLACE['name'])

    def test_create_place(self):
        url = reverse('place-list')
        response = self.client.post(url, PLACE, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], PLACE['name'])

    def test_delete_event(self):
        url = reverse('event-list')
        response_post = self.client.post(url, EVENT, format='json')
        response_delete = self.client.delete(url + str(
            response_post.data['id']) + '/', format='json')
        self.assertEqual(response_delete.status_code,
                         status.HTTP_204_NO_CONTENT)
        response_get = self.client.get(url + str(
            response_post.data['id']) + '/', format='json')
        self.assertEqual(response_get.status_code,
                         status.HTTP_404_NOT_FOUND)


class SerializerTests(SimpleTestCase):
    def test_iso8601_serialization(self):
        ser = ISO8601DurationField()
        formatted_str = ser.to_native(5 * 60 * 60 * 1000 + 45 * 60 * 1000)
        self.assertEqual(formatted_str, 'PT5H45M')

    def test_iso8601_deserialization(self):
        ser = ISO8601DurationField()
        duration = ser.from_native('PT5H45M')
        self.assertEqual(duration, 5 * 60 * 60 * 1000 + 45 * 60 * 1000)


ORGANIZATION = {
    "@type": "Organization",
    "creator": None,
    "editor": None,
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

PLACE = {
    "name": {
        "fi": "Paikka 1",
        "en": "Place 1",
        "sv": "Plats 1"
    },
    "description": {
        "fi": "lorem",
        "en": "ipsum",
        "sv": "dolor"
    },
    "creator": None,
    "editor": None,
    "geo": {
        "@type": "GeoShape",
        "elevation": "212",
        "box": "boxbox",
        "circle": "circlecircle",
        "line": "lineline",
        "polygon": "polygon"
    },
    "dataSource": None,
    "originId": None,
    "customFields": {},
    "image": "",
    "dateCreated": None,
    "dateModified": None,
    "discussionUrl": "",
    "thumbnailUrl": "",
    "sameAs": "",
    "address": None,
    "publishingPrinciples": "there are those!",
    "point": None,
    "logo": "",
    "map": "",
    "containedIn": None,
}

EVENT = {
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
        "seller": ORGANIZATION,
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
    "dataSource": None,
    "performer": []
}
