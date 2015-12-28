# -*- coding: utf-8 -*-
from django.core.urlresolvers import reverse
import pytest
from .utils import get, assert_fields_exist


# === util methods ===

def get_list(api_client):
    list_url = reverse('event-list')
    return get(api_client, list_url)


def get_detail(api_client, detail_pk):
    detail_url = reverse('event-detail', kwargs={'pk': detail_pk})
    return get(api_client, detail_url)


def assert_event_fields_exist(data):
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
        'headline',
        'id',
        'image',
        'in_language',
        'info_url',
        'keywords',
        'last_modified_by',
        'last_modified_time',
        'location',
        'location_extra_info',
        'name',
        'offers',
        'origin_id',
        'provider',
        'publisher',
        'secondary_headline',
        'short_description',
        'start_time',
        'sub_events',
        'super_event'
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
