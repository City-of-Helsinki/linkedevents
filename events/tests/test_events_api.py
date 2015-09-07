#!/usr/bin/env python
# -*- coding: utf-8 -*-

# django
from django.test import TestCase

# 3rd party
from rest_framework.test import APIClient

# this app 
from events.models import Organization, DataSource


class EventAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.test_ds, _ = DataSource.objects.get_or_create(id='linkedevents')
        self.test_org, _ = Organization.objects.get_or_create(
            id='ytj:0586977-6',
            data_source=self.test_ds
        )

    def test__create_event_with_post(self):
        MINIMAL_EVENT = {
            "data_source": self.test_ds.id,
            "publisher": self.test_org.id,
            "name": {"fi": "Testitapahtuma"}
        }

        # save with post
        response = self.client.post('/v0.1/event/', MINIMAL_EVENT, format='json')
        self.assertEquals(response.status_code, 201)

        # double-check with get
        resp2 = self.client.get(response.data['@id'])
        self.assertEquals(resp2.status_code, 200)
