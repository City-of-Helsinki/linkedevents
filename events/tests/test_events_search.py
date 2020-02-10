#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.conf import settings
from django.test import TestCase
import haystack
import datetime
# from haystack.management.commands import rebuild_index, clear_index
from rest_framework.test import APIClient

from ..models import Event

from .common import TestDataMixin


# Make sure we don't overwrite our main indices
for key, val in settings.HAYSTACK_CONNECTIONS.items():
    if 'INDEX_NAME' in val:
        val['INDEX_NAME'] = 'test_%s' % val['INDEX_NAME']


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
                           publisher=self.test_org,
                           start_time=datetime.datetime.now(),
                           end_time=datetime.datetime.now()
                           )
        self.dummy.save()

        # refresh haystack's index
        # simple backend doesn't have an index, so we cannot test indexing
        # rebuild_index.Command().handle(interactive=False)

        super(EventSearchTests, self).setUp()

    def _get_response(self, query):
        return self.client.get('/v1/search/', {'q': query}, format='json')

    def test__search_should_respond(self):
        response = self._get_response('a random search query')
        self.assertEqual(response.status_code, 200, msg=response.content)

    def test__search_should_return_at_least_one_match(self):
        query = self.dummy.name.split()[0]  # let's use just the first word
        response = self._get_response(query)

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertTrue(response.data['meta']['count'] >= 1)

    def test__search_shouldnt_return_matches(self):
        response = self._get_response('ASearchQueryThatShouldntReturnMatches')
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertTrue(response.data['meta']['count'] == 0)

    # simple backend doesn't have an index, so we cannot test index updates
    # def test__search_shouldnt_return_deleted_matches(self):
    #     self.dummy.deleted = True
    #     self.dummy.save()
    #
    #
    #     query = self.dummy.name.split()[0]  # let's use just the first word
    #     response = self._get_response(query)
    #
    #     self.assertEqual(response.status_code, 200, msg=response.content)
    #     self.assertTrue(response.data['meta']['count'] == 0)

    def tearDown(self):
        # delete dummy
        self.dummy.delete()

        # clear index
        # simple backend doesn't have an index, so we cannot test indexing
        # clear_index.Command().handle(interactive=False)
