#!/usr/bin/env python
# -*- coding: utf-8 -*-

# django
from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings

# 3rd party
import haystack
from haystack.management.commands import rebuild_index, clear_index
from rest_framework.test import APIClient

# this app
from events.models import Event

# this package
from events.tests.common import TestDataMixin


TEST_INDEX = settings.HAYSTACK_CONNECTIONS
TEST_INDEX['default']['INDEX_NAME'] = 'test_index'
TEST_INDEX['default-fi']['INDEX_NAME'] = 'test_index-fi'
TEST_INDEX['default-sv']['INDEX_NAME'] = 'test_index-sv'
TEST_INDEX['default-en']['INDEX_NAME'] = 'test_index-en'


@override_settings(HAYSTACK_CONNECTIONS=TEST_INDEX)
class EventSearchTests(TestCase, TestDataMixin):

    def setUp(self):
        self.client = APIClient()
        self.set_up_test_data()

        # setup haystack
        haystack.connections.reload('default')
        haystack.connections.reload('default-fi')
        haystack.connections.reload('default-en')
        haystack.connections.reload('default-sv')

        # create a dummy event
        self.dummy = Event(name='dummy event',
                           data_source=self.test_ds,
                           publisher=self.test_org)
        self.dummy.save()

        # refresh haystack's index
        rebuild_index.Command().handle(interactive=False)

        super(EventSearchTests, self).setUp()

    def _get_response(self, query):
        return self.client.get('/v0.1/search/', {'q': query}, format='json')

    def test__search_should_respond(self):
        response = self._get_response('a random search query')
        self.assertEquals(response.status_code, 200, msg=response.content)

    def test__search_should_return_at_least_one_match(self):
        query = self.dummy.name.split()[0]  # let's use just the first word
        response = self._get_response(query)

        self.assertEquals(response.status_code, 200, msg=response.content)
        self.assertTrue(response.data['meta']['count'] >= 1)

    def test__search_shouldnt_return_matches(self):
        response = self._get_response('ASearchQueryThatShouldntReturnMatches')
        self.assertEquals(response.status_code, 200, msg=response.content)
        self.assertTrue(response.data['meta']['count'] == 0)

    def tearDown(self):
        # delete dummy
        self.dummy.delete()

        # clear index
        clear_index.Command().handle(interactive=False)
