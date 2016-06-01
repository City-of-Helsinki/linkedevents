# -*- coding: utf-8 -*-
from .utils import versioned_reverse as reverse
import pytest
from .utils import get, assert_fields_exist
from django.conf import settings


# === util methods ===

def get_list(api_client, version='v1', data=None):
    list_url = reverse('event-list', version=version)
    return get(api_client, list_url, data=data)


def get_detail(api_client, detail_pk, version='v1', data=None):
    detail_url = reverse('event-detail', version=version, kwargs={'pk': detail_pk})
    return get(api_client, detail_url, data=data)


def assert_event_fields_exist(data, version='v1'):
    # TODO: incorporate version parameter into version aware
    # parts of test code
    fields = (
        '@context',
        '@id',
        '@type',
        'audience',
        'created_time',
        'custom_data',
        'data_source',
        'date_published',
        'description',
        'end_time',
        'event_status',
        'external_links',
        'id',
        'images',
        'in_language',
        'info_url',
        'keywords',
        'last_modified_time',
        'location',
        'location_extra_info',
        'name',
        'offers',
        'provider',
        'publisher',
        'short_description',
        'start_time',
        'sub_events',
        'super_event'
    )
    if version == 'v0.1':
        fields += (
            'origin_id',
            'last_modified_by',
            'headline',
            'secondary_headline',
        )
    assert_fields_exist(data, fields)


# === tests ===

@pytest.mark.django_db
def test_get_event_list_check_fields_exist(api_client, event):
    """
    Tests that event list endpoint returns the correct fields.
    """
    response = get_list(api_client)
    assert_event_fields_exist(response.data['data'][0])


@pytest.mark.django_db
def test_get_event_detail_check_fields_exist(api_client, event):
    """
    Tests that event detail endpoint returns the correct fields.
    """
    response = get_detail(api_client, event.pk)
    assert_event_fields_exist(response.data)


@pytest.mark.django_db
def test_get_event_list_verify_data_source_filter(api_client, data_source, event, event2):
    response = get_list(api_client, data={'data_source': data_source.id})
    assert event.id in [entry['id'] for entry in response.data['data']]
    assert event2.id not in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_data_source_negative_filter(api_client, data_source, event, event2):
    response = get_list(api_client, data={'data_source!': data_source.id})
    assert event.id not in [entry['id'] for entry in response.data['data']]
    assert event2.id in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_location_filter(api_client, place, event, event2):
    response = get_list(api_client, data={'location': place.id})
    assert event.id in [entry['id'] for entry in response.data['data']]
    assert event2.id not in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_keyword_filter(api_client, keyword, event):
    event.keywords.add(keyword)
    response = get_list(api_client, data={'keyword': keyword.id})
    assert event.id in [entry['id'] for entry in response.data['data']]
    response = get_list(api_client, data={'keyword': 'unknown_keyword'})
    assert event.id not in [entry['id'] for entry in response.data['data']]