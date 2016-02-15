# -*- coding: utf-8 -*-
from .utils import versioned_reverse as reverse
import pytest
from .utils import get, assert_fields_exist


# === util methods ===

def get_list(api_client, version='v1'):
    list_url = reverse('event-list', version=version)
    return get(api_client, list_url)


def get_detail(api_client, detail_pk, version='v1'):
    detail_url = reverse('event-detail', version=version, kwargs={'pk': detail_pk})
    return get(api_client, detail_url)


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
        'image',
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
def test__api_get_event_list_check_fields_exist(all_api_get_list):
    """
    Tests that event list endpoint returns the correct fields.
    """
    response = all_api_get_list()
    assert_event_fields_exist(response.data['data'][0])
