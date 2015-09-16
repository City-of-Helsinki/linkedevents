#!/usr/bin/env python
# -*- coding: utf-8 -*-

# django
from django.test import TestCase
from django.utils import timezone

# 3rd party
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

# this app
from events.api import KeywordSerializer, PlaceSerializer
from events.models import (
    Event, DataSource, Organization, Keyword, Language, KeywordLabel, Place
)


class TestDataMixin:

    def _set_up_keyword(self, name, lang_code):
        lang_obj, _ = Language.objects.get_or_create(id=lang_code)
        label_obj, _ = KeywordLabel.objects.get_or_create(name=name,
                                                          language=lang_obj)

        obj, _ = Keyword.objects.get_or_create(id=name,
                                               name=name,
                                               data_source=self.test_ds)
        obj.alt_labels.add(label_obj)
        obj.save()

        obj_id = reverse(KeywordSerializer().view_name, kwargs={'pk': obj.id})
        return 'http://testserver%s' % obj_id

    def _set_up_location(self, id):
        obj, _ = Place.objects.get_or_create(id=id,
                                             data_source=self.test_ds,
                                             publisher=self.test_org)
        obj_id = reverse(PlaceSerializer().view_name, kwargs={'pk': obj.id})
        return 'http://testserver%s' % obj_id

    def set_up_test_data(self):

        # dummy inputs
        TEXT = 'testing'
        URL = "http://localhost"
        DATETIME = timezone.now().isoformat()

        # data source
        self.test_ds, _ = DataSource.objects.get_or_create(id=TEXT)

        #  organization
        self.test_org, _ = Organization.objects.get_or_create(
            id=TEXT,
            data_source=self.test_ds
        )

        # location / place
        self.test_location = self._set_up_location(TEXT)

        # event link
        self.test_event_link, _ = None, None

        # offer
        self.test_offer, _ = None, None

        # keywords
        self.test_keyword1 = self._set_up_keyword('%s1' % TEXT, 'fi')
        self.test_keyword2 = self._set_up_keyword('%s2' % TEXT, 'sv')
        self.test_keyword3 = self._set_up_keyword('%s3' % TEXT, 'en')

        # minimal event json
        self.MINIMAL_EVENT = {
            "data_source": self.test_ds.id,
            "publisher": self.test_org.id,
            "name": {"fi": TEXT}
        }

        # complex event json
        self.COMPLEX_EVENT = {
            "location": {"@id": self.test_location},
            "keywords": [
                {"@id": self.test_keyword1},
                {"@id": self.test_keyword2},
                {"@id": self.test_keyword3}
            ],
            "event_status": Event.SCHEDULED,
            "external_links": [
                {"name": TEXT, "link": URL, "event": None, "language": "en"},
                {"name": TEXT, "link": URL, "event": None, "language": "fi"},
                {"name": TEXT, "link": URL, "event": None, "language": "sv"},
            ],
            "offers": [
                {
                    "is_free": False,
                    "price": {"en": TEXT, "sv": TEXT, "fi": TEXT},
                    "description": {"en": TEXT, "sv": TEXT, "fi": TEXT},
                    "info_url": {"en": URL, "sv": URL, "fi": URL}
                }
            ],
            "sub_events": [],
            "custom_data": {"my": "data", "your": "data"},
            "image": URL,
            "origin_id": TEXT,
            "created_time": DATETIME,
            "date_published": DATETIME,
            "start_time": DATETIME,
            "end_time": DATETIME,
            "audience": TEXT,
            "data_source": self.test_ds.id,
            "publisher": self.test_org.id,
            "location_extra_info": {"fi": TEXT},
            "info_url": {"en": URL, "sv": URL, "fi": URL},
            "name": {"en": TEXT, "sv": TEXT, "fi": TEXT},
            "secondary_headline": {"en": TEXT, "sv": TEXT, "fi": TEXT},
            "description": {"en": TEXT, "sv": TEXT, "fi": TEXT},
            "headline": {"en": TEXT, "sv": TEXT, "fi": TEXT},
            "short_description": {"en": TEXT, "sv": TEXT, "fi": TEXT},
            "provider": {"en": TEXT, "sv": TEXT, "fi": TEXT},
        }


class EventAPITests(TestCase, TestDataMixin):

    def setUp(self):
        self.client = APIClient()
        self.set_up_test_data()

    def _create_with_post(self, event_data):
        # save with post
        response = self.client.post('/v0.1/event/', event_data, format='json')
        self.assertEquals(response.status_code, 201, msg=response.content)

        # double-check with get
        resp2 = self.client.get(response.data['@id'])
        self.assertEquals(resp2.status_code, 200, msg=response.content)

        return resp2

    def _update_with_put(self, event_id, event_data):
        response = self.client.put(event_id, event_data, format='json')
        return response

    def _assert_event_data_is_equal(self, d1, d2):
        # make sure the saved data is equal to the one we posted before
        FIELDS = (
            'data_source',
            'publisher',
            'location',
            'name',
            'event_status',
            'sub_events',
            'custom_data',
            'image',
            'origin_id',
            'audience',
            'location_extra_info',
            'info_url',
            'secondary_headline',
            'description',
            'headline',
            'short_description',
            'provider',

            'keywords',
            'offers',

            # 'external_links',

            # 'start_time',  # fails because of Javascript's "Z" vs Python's "+00:00"
            # 'end_time',    # -"-
        )
        for key in FIELDS:
            if key in d1:
                self.assertEquals(d1[key], d2[key])

    def test__create_a_minimal_event_with_post(self):
        data = self.MINIMAL_EVENT
        response = self._create_with_post(data)
        self._assert_event_data_is_equal(data, response.data)

    def test__create_a_complex_event_with_post(self):
        data = self.COMPLEX_EVENT
        response = self._create_with_post(data)
        self._assert_event_data_is_equal(data, response.data)

    def test__update_an_event_with_put(self):

        # dummy inputs
        TEXT = 'text updated'
        URL = "http://localhost"

        # create an event
        data = self.COMPLEX_EVENT
        response = self._create_with_post(data)

        # set up updates
        data2 = response.data
        for key in ('name', 'headline'):
            for lang in ('fi', 'en', 'sv'):
                if lang in data2[key]:
                    data2[key][lang] = '%s updated' % data2[key][lang]

        # test updates to offers
        data2['offers'] = [
            {
                "is_free": False,
                "price": {"en": TEXT, "sv": TEXT, "fi": TEXT},
                "description": {"en": TEXT, "fi": TEXT},
                "info_url": {"en": URL, "sv": URL, "fi": URL}
            }
        ]

        # store updates
        event_id = data2.pop('@id')
        response2 = self._update_with_put(event_id, data2)

        # assert
        self._assert_event_data_is_equal(data2, response2.data)
