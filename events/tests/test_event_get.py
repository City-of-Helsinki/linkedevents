# -*- coding: utf-8 -*-
from .utils import versioned_reverse as reverse
import pytest
from .utils import get, assert_fields_exist
from events.models import (
    Event, PublicationStatus, Language
)
from django.contrib.gis.gdal import SpatialReference, CoordTransform
from django.contrib.gis.geos import Point
from django.conf import settings
import dateutil.parser
from freezegun import freeze_time

# === util methods ===


def get_list(api_client, version='v1', data=None, query_string=None):
    url = reverse('event-list', version=version)
    if query_string:
        url = '%s?%s' % (url, query_string)
    return get(api_client, url, data=data)


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
        'provider_contact_info',
        'publisher',
        'short_description',
        'audience_min_age',
        'audience_max_age',
        'start_time',
        'sub_events',
        'super_event',
        'super_event_type',
        'videos',
        'replaced_by',
        'deleted',
    )
    if version == 'v0.1':
        fields += (
            'origin_id',
            'headline',
            'secondary_headline',
        )
    assert_fields_exist(data, fields)


def assert_events_in_response(events, response):
    response_event_ids = {event['id'] for event in response.data['data']}
    expected_event_ids = {event.id for event in events}
    assert response_event_ids == expected_event_ids


# === tests ===

@pytest.mark.django_db
def test_get_event_list_html_renders(api_client, event):
    url = reverse('event-list', version='v1')
    response = api_client.get(url, data=None, HTTP_ACCEPT='text/html')
    assert response.status_code == 200, str(response.content)


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
def test_get_unknown_event_detail_check_404(api_client):
    response = api_client.get(reverse('event-detail', kwargs={'pk': 'möö'}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_event_list_verify_text_filter(api_client, event, event2):
    response = get_list(api_client, data={'text': 'event'})
    assert event.id not in [entry['id'] for entry in response.data['data']]
    assert event2.id in [entry['id'] for entry in response.data['data']]


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
def test_get_event_list_verify_bbox_filter(api_client, event, event2):
    # API parameters must be provided in EPSG:4326 instead of the database SRS
    left_bottom = Point(25, 25)
    right_top = Point(75, 75)
    ct = CoordTransform(SpatialReference(settings.PROJECTION_SRID), SpatialReference(4326))
    left_bottom.transform(ct)
    right_top.transform(ct)
    bbox_string = f"{left_bottom.x},{left_bottom.y},{right_top.x},{right_top.y}"
    response = get_list(api_client, data={'bbox': bbox_string})
    # this way we will catch any errors if the default SRS changes, breaking the API
    assert event.id in [entry['id'] for entry in response.data['data']]
    assert event2.id not in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_keyword_filter(api_client, keyword, event):
    event.keywords.add(keyword)
    response = get_list(api_client, data={'keyword': keyword.id})
    assert event.id in [entry['id'] for entry in response.data['data']]
    response = get_list(api_client, data={'keyword': 'unknown_keyword'})
    assert event.id not in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_keyword_or_filter(api_client, keyword, event):
    # "keyword_OR" filter should be the same as "keyword" filter
    event.keywords.add(keyword)
    response = get_list(api_client, data={'keyword_OR': keyword.id})
    assert event.id in [entry['id'] for entry in response.data['data']]
    response = get_list(api_client, data={'keyword_OR': 'unknown_keyword'})
    assert event.id not in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_combine_keyword_and_keyword_or(api_client, keyword, keyword2, event, event2):
    # If "keyword" and "keyword_OR" are both present "AND" them together
    event.keywords.add(keyword, keyword2)
    event2.keywords.add(keyword2)
    response = get_list(api_client, data={'keyword': keyword.id, 'keyword_OR': keyword2.id})
    assert event.id in [entry['id'] for entry in response.data['data']]
    assert event2.id not in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_keyword_and(api_client, keyword, keyword2, event, event2):
    event.keywords.add(keyword)
    event2.keywords.add(keyword, keyword2)
    response = get_list(api_client, data={'keyword_AND': ','.join([keyword.id, keyword2.id])})
    assert event.id not in [entry['id'] for entry in response.data['data']]
    assert event2.id in [entry['id'] for entry in response.data['data']]

    event2.keywords.remove(keyword2)
    event2.audience.add(keyword2)
    response = get_list(api_client, data={'keyword_AND': ','.join([keyword.id, keyword2.id])})
    assert event.id not in [entry['id'] for entry in response.data['data']]
    assert event2.id in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_keyword_negative_filter(api_client, keyword, keyword2, event, event2):
    event.keywords.set([keyword])
    event2.keywords.set([keyword2])
    response = get_list(api_client, data={'keyword!': keyword.id})
    assert event.id not in [entry['id'] for entry in response.data['data']]
    assert event2.id in [entry['id'] for entry in response.data['data']]

    response = get_list(api_client, data={'keyword!': ','.join([keyword.id, keyword2.id])})
    assert event.id not in [entry['id'] for entry in response.data['data']]
    assert event2.id not in [entry['id'] for entry in response.data['data']]

    event.keywords.set([])
    event.audience.set([keyword])
    response = get_list(api_client, data={'keyword!': keyword.id})
    assert event.id not in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_replaced_keyword_filter(api_client, keyword, keyword2, event):
    event.keywords.add(keyword2)
    keyword.replaced_by = keyword2
    keyword.deleted = True
    keyword.save()
    response = get_list(api_client, data={'keyword': keyword.id})
    # if we asked for a replaced keyword, return events with the current keyword instead
    assert event.id in [entry['id'] for entry in response.data['data']]
    response = get_list(api_client, data={'keyword': 'unknown_keyword'})
    assert event.id not in [entry['id'] for entry in response.data['data']]


@pytest.mark.django_db
def test_get_event_list_verify_division_filter(api_client, event, event2, event3, administrative_division,
                                               administrative_division2):
    event.location.divisions.set([administrative_division])
    event2.location.divisions.set([administrative_division2])

    # filter using one value
    response = get_list(api_client, data={'division': administrative_division.ocd_id})
    data = response.data['data']
    assert len(data) == 1
    assert event.id in [entry['id'] for entry in data]

    # filter using two values
    filter_value = '%s,%s' % (administrative_division.ocd_id, administrative_division2.ocd_id)
    response = get_list(api_client, data={'division': filter_value})
    data = response.data['data']
    assert len(data) == 2
    ids = [entry['id'] for entry in data]
    assert event.id in ids
    assert event2.id in ids


@pytest.mark.django_db
def test_get_event_list_super_event_filters(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    # fetch non-subevents
    response = get_list(api_client, query_string='super_event=none')
    assert len(response.data['data']) == 1
    assert response.data['data'][0]['id'] == event.id

    # fetch subevents
    response = get_list(api_client, query_string='super_event='+event.id)
    assert len(response.data['data']) == 1
    assert response.data['data'][0]['id'] == event2.id


@pytest.mark.django_db
def test_get_event_list_recurring_filters(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    # fetch superevents
    response = get_list(api_client, query_string='recurring=super')
    assert len(response.data['data']) == 1
    assert response.data['data'][0]['id'] == event.id

    # fetch subevents
    response = get_list(api_client, query_string='recurring=sub')
    assert len(response.data['data']) == 1
    assert response.data['data'][0]['id'] == event2.id


@pytest.mark.django_db
def test_super_event_type_filter(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    # "none" and "null" should return only the non super event
    for value in ('none', 'null'):
        response = get_list(api_client, query_string='super_event_type=%s' % value)
        ids = {e['id'] for e in response.data['data']}
        assert ids == {event2.id}

    # "recurring" should return only the recurring super event
    response = get_list(api_client, query_string='super_event_type=recurring')
    ids = {e['id'] for e in response.data['data']}
    assert ids == {event.id}

    # "recurring,none" should return both
    response = get_list(api_client, query_string='super_event_type=recurring,none')
    ids = {e['id'] for e in response.data['data']}
    assert ids == {event.id, event2.id}

    response = get_list(api_client, query_string='super_event_type=fwfiuwhfiuwhiw')
    assert len(response.data['data']) == 0


@pytest.mark.django_db
def test_get_event_disallow_simultaneous_include_super_and_sub(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    # fetch event with super event
    detail_url = reverse('event-detail', version='v1', kwargs={'pk': event2.pk})

    # If not specifically handled, the following combination of
    # include parameters causes an infinite recursion, because the
    # super events of sub events of super events ... are expanded ad
    # infinitum. This test is here to check that execution finishes.
    detail_url += '?include=super_event,sub_events'
    response = get(api_client, detail_url)
    assert_event_fields_exist(response.data)
    assert(type(response.data['super_event'] == 'dict'))


@pytest.mark.django_db
def test_language_filter(api_client, event, event2, event3):
    event.name_sv = 'namn'
    event.save()
    event2.in_language.add(Language.objects.get_or_create(id='en')[0])
    event2.in_language.add(Language.objects.get_or_create(id='sv')[0])
    event2.save()
    event3.name_ru = 'название'
    event3.in_language.add(Language.objects.get_or_create(id='et')[0])
    event3.save()

    # Finnish should be the default language
    response = get_list(api_client, query_string='language=fi')
    ids = {e['id'] for e in response.data['data']}
    assert ids == {event.id, event2.id, event3.id}

    # Swedish should have two events (matches in_language and name_sv)
    response = get_list(api_client, query_string='language=sv')
    ids = {e['id'] for e in response.data['data']}
    assert ids == {event.id, event2.id}

    # English should have one event (matches in_language)
    response = get_list(api_client, query_string='language=en')
    ids = {e['id'] for e in response.data['data']}
    assert ids == {event2.id}

    # Russian should have one event (matches name_ru)
    response = get_list(api_client, query_string='language=ru')
    ids = {e['id'] for e in response.data['data']}
    assert ids == {event3.id}

    # Chinese should have no events
    response = get_list(api_client, query_string='language=zh_hans')
    ids = {e['id'] for e in response.data['data']}
    assert ids == set()

    # Estonian should have one event (matches in_language), even without translations available
    response = get_list(api_client, query_string='language=et')
    ids = {e['id'] for e in response.data['data']}
    assert ids == {event3.id}


@pytest.mark.django_db
def test_event_list_filters(api_client, event, event2):
    filters = (
        ([event.publisher.id, event2.publisher.id], 'publisher'),
        ([event.data_source.id, event2.data_source.id], 'data_source'),
    )

    for filter_values, filter_name in filters:
        q = ','.join(filter_values)
        response = get_list(api_client, query_string='%s=%s' % (filter_name, q))
        data = response.data['data']
        assert(len(data) == 2)
        ids = [e['id'] for e in data]
        assert event.id in ids
        assert event2.id in ids


@pytest.mark.django_db
def test_event_list_publisher_ancestor_filter(api_client, event, event2, organization, organization2, organization3):
    organization2.parent = organization
    organization2.save()
    event.publisher = organization2
    event.save()
    event2.publisher = organization3
    event2.save()
    response = get_list(api_client, query_string=f'publisher_ancestor={organization.id}')
    data = response.data['data']
    assert(len(data) == 1)
    ids = [e['id'] for e in data]
    assert event.id in ids


@pytest.mark.django_db
def test_publication_status_filter(api_client, event, event2, user, organization, data_source):
    event.publication_status = PublicationStatus.PUBLIC
    event.save()

    event2.publication_status = PublicationStatus.DRAFT
    event2.save()

    api_client.force_authenticate(user=user)

    response = get_list(api_client, query_string='show_all=true&publication_status=public')
    ids = {e['id'] for e in response.data['data']}
    assert event.id in ids
    assert event2.id not in ids

    # cannot see drafts from other organizations
    response = get_list(api_client, query_string='show_all=true&publication_status=draft')
    ids = {e['id'] for e in response.data['data']}
    assert event2.id not in ids
    assert event.id not in ids

    event2.publisher = organization
    event2.data_source = data_source
    event2.save()

    response = get_list(api_client, query_string='show_all=true&publication_status=draft')
    ids = {e['id'] for e in response.data['data']}
    assert event2.id in ids
    assert event.id not in ids


@pytest.mark.django_db
def test_event_status_filter(api_client, event, event2, event3, event4, user, organization, data_source):
    event.event_status = Event.Status.SCHEDULED
    event.save()

    event2.event_status = Event.Status.RESCHEDULED
    event2.save()

    event3.event_status = Event.Status.CANCELLED
    event3.save()

    event4.event_status = Event.Status.POSTPONED
    event4.save()

    response = get_list(api_client, query_string='event_status=eventscheduled')
    ids = {e['id'] for e in response.data['data']}
    assert event.id in ids
    assert event2.id not in ids
    assert event3.id not in ids
    assert event4.id not in ids

    response = get_list(api_client, query_string='event_status=eventrescheduled')
    ids = {e['id'] for e in response.data['data']}
    assert event.id not in ids
    assert event2.id in ids
    assert event3.id not in ids
    assert event4.id not in ids

    response = get_list(api_client, query_string='event_status=eventcancelled')
    ids = {e['id'] for e in response.data['data']}
    assert event.id not in ids
    assert event2.id not in ids
    assert event3.id in ids
    assert event4.id not in ids

    response = get_list(api_client, query_string='event_status=eventpostponed')
    ids = {e['id'] for e in response.data['data']}
    assert event.id not in ids
    assert event2.id not in ids
    assert event3.id not in ids
    assert event4.id in ids


@pytest.mark.django_db
def test_admin_user_filter(api_client, event, event2, user):
    api_client.force_authenticate(user=user)

    response = get_list(api_client, query_string='admin_user=true')
    ids = {e['id'] for e in response.data['data']}
    assert event.id in ids
    assert event2.id not in ids


@pytest.mark.django_db
def test_redirect_if_replaced(api_client, event, event2, user):
    api_client.force_authenticate(user=user)

    event.replaced_by = event2
    event.save()

    url = reverse('event-detail', version='v1', kwargs={'pk': event.pk})
    response = api_client.get(url, format='json')
    assert response.status_code == 301

    response2 = api_client.get(response.url, format='json')
    assert response2.status_code == 200
    assert response2.data['id'] == event2.pk


@pytest.mark.django_db
def test_redirect_to_end_of_replace_chain(api_client, event, event2, event3, user):
    api_client.force_authenticate(user=user)

    event.replaced_by = event2
    event.save()
    event2.replaced_by = event3
    event2.save()

    url = reverse('event-detail', version='v1', kwargs={'pk': event.pk})
    response = api_client.get(url, format='json')
    assert response.status_code == 301

    response2 = api_client.get(response.url, format='json')
    assert response2.status_code == 200
    assert response2.data['id'] == event3.pk


@pytest.mark.django_db
def test_get_event_list_sub_events(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    # fetch event with sub event
    detail_url = reverse('event-detail', version='v1', kwargs={'pk': event.pk})
    response = get(api_client, detail_url)
    assert_event_fields_exist(response.data)
    assert response.data['sub_events']


@pytest.mark.django_db
def test_get_event_list_deleted_sub_events(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.deleted = True
    event2.save()

    # fetch event with sub event deleted
    detail_url = reverse('event-detail', version='v1', kwargs={'pk': event.pk})
    response = get(api_client, detail_url)
    assert_event_fields_exist(response.data)
    assert not response.data['sub_events']


@pytest.mark.django_db
def test_event_list_show_deleted_param(api_client, event, event2, user):
    api_client.force_authenticate(user=user)

    event.soft_delete()

    response = get_list(api_client, query_string='show_deleted=true')
    assert response.status_code == 200
    assert event.id in {e['id'] for e in response.data['data']}
    assert event2.id in {e['id'] for e in response.data['data']}

    expected_keys = ['id', 'name', 'last_modified_time', 'deleted', 'replaced_by']
    event_data = next((e for e in response.data['data'] if e['id'] == event.id))
    assert len(event_data) == len(expected_keys)
    for key in event_data:
        assert key in expected_keys
    assert event_data['name']['fi'] == 'POISTETTU'
    assert event_data['name']['sv'] == 'RADERAD'
    assert event_data['name']['en'] == 'DELETED'

    response = get_list(api_client)
    assert response.status_code == 200
    assert event.id not in {e['id'] for e in response.data['data']}
    assert event2.id in {e['id'] for e in response.data['data']}


@pytest.mark.django_db
def test_event_list_deleted_param(api_client, event, event2, user):
    api_client.force_authenticate(user=user)

    event.soft_delete()

    response = get_list(api_client, query_string='deleted=true')
    assert response.status_code == 200
    assert event.id in {e['id'] for e in response.data['data']}
    assert event2.id not in {e['id'] for e in response.data['data']}

    expected_keys = ['id', 'name', 'last_modified_time', 'deleted', 'replaced_by']
    event_data = next((e for e in response.data['data'] if e['id'] == event.id))
    assert len(event_data) == len(expected_keys)
    for key in event_data:
        assert key in expected_keys
    assert event_data['name']['fi'] == 'POISTETTU'
    assert event_data['name']['sv'] == 'RADERAD'
    assert event_data['name']['en'] == 'DELETED'

    response = get_list(api_client)
    assert response.status_code == 200
    assert event.id not in {e['id'] for e in response.data['data']}
    assert event2.id in {e['id'] for e in response.data['data']}


@pytest.mark.django_db
def test_event_list_is_free_filter(api_client, event, event2, event3, offer):
    response = get_list(api_client, query_string='is_free=true')
    assert {event2.id} == {e['id'] for e in response.data['data']}

    response = get_list(api_client, query_string='is_free=false')
    assert {event.id, event3.id} == {e['id'] for e in response.data['data']}


@pytest.mark.django_db
def test_start_end_iso_date(api_client, make_event):
    parse_date = dateutil.parser.parse
    event1 = make_event('1', parse_date('2020-02-19 23:00:00+02'), parse_date('2020-02-19 23:30:00+02'))
    event2 = make_event('2', parse_date('2020-02-19 23:30:00+02'), parse_date('2020-02-20 00:00:00+02'))
    event3 = make_event('3', parse_date('2020-02-19 23:30:00+02'), parse_date('2020-02-20 00:30:00+02'))
    event4 = make_event('4', parse_date('2020-02-20 00:00:00+02'), parse_date('2020-02-20 00:30:00+02'))
    event5 = make_event('5', parse_date('2020-02-20 12:00:00+02'), parse_date('2020-02-20 13:00:00+02'))
    event6 = make_event('6', parse_date('2020-02-21 12:00:00+02'), parse_date('2020-02-21 13:00:00+02'))
    event7 = make_event('7')   # postponed event

    # Start parameter

    response = get_list(api_client, query_string='start=2020-02-19')
    expected_events = [event1, event2, event3, event4, event5, event6, event7]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='start=2020-02-20')
    expected_events = [event3, event4, event5, event6, event7]
    assert_events_in_response(expected_events, response)

    # End parameter

    response = get_list(api_client, query_string='end=2020-02-19')
    expected_events = [event1, event2, event3, event4]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='end=2020-02-20')
    expected_events = [event1, event2, event3, event4, event5]
    assert_events_in_response(expected_events, response)

    # Start and end parameters

    response = get_list(api_client, query_string='start=2020-02-20&end=2020-02-20')
    expected_events = [event3, event4, event5]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='start=2020-02-19&end=2020-02-21')
    expected_events = [event1, event2, event3, event4, event5, event6]
    assert_events_in_response(expected_events, response)


@pytest.mark.django_db
def test_start_end_iso_date_time(api_client, make_event):
    parse_date = dateutil.parser.parse
    event1 = make_event('1', parse_date('2020-02-19 10:00:00+02'), parse_date('2020-02-19 11:22:33+02'))
    event2 = make_event('2', parse_date('2020-02-19 11:22:33+02'), parse_date('2020-02-19 22:33:44+02'))
    event3 = make_event('3', parse_date('2020-02-20 11:22:33+02'), parse_date('2020-02-20 22:33:44+02'))
    event4 = make_event('4')   # postponed event

    # Start parameter

    response = get_list(api_client, query_string='start=2020-02-19T11:22:32')
    expected_events = [event1, event2, event3, event4]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='start=2020-02-19T11:22:33')
    expected_events = [event2, event3, event4]
    assert_events_in_response(expected_events, response)

    # End parameter

    response = get_list(api_client, query_string='end=2020-02-19T11:22:32')
    expected_events = [event1]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='end=2020-02-19T11:22:33')
    expected_events = [event1, event2]
    assert_events_in_response(expected_events, response)

    # Start and end parameters

    response = get_list(api_client, query_string='start=2020-02-19T11:22:33&end=2020-02-19T11:22:33')
    expected_events = [event2]
    assert_events_in_response(expected_events, response)


@pytest.mark.django_db
def test_start_end_today(api_client, make_event):
    parse_date = dateutil.parser.parse
    event1 = make_event('1', parse_date('2020-02-19 23:00:00+02'), parse_date('2020-02-19 23:30:00+02'))
    event2 = make_event('2', parse_date('2020-02-19 23:30:00+02'), parse_date('2020-02-20 00:00:00+02'))
    event3 = make_event('3', parse_date('2020-02-19 23:30:00+02'), parse_date('2020-02-20 00:30:00+02'))
    event4 = make_event('4', parse_date('2020-02-20 00:00:00+02'), parse_date('2020-02-20 00:30:00+02'))
    event5 = make_event('5', parse_date('2020-02-20 12:00:00+02'), parse_date('2020-02-20 13:00:00+02'))
    event6 = make_event('6', parse_date('2020-02-21 00:00:00+02'), parse_date('2020-02-21 01:00:00+02'))
    event7 = make_event('7', parse_date('2020-02-21 12:00:00+02'), parse_date('2020-02-21 13:00:00+02'))
    event8 = make_event('8')   # postponed event

    def times():
        yield '2020-02-20 00:00:00+02'
        yield '2020-02-20 12:00:00+02'
        yield '2020-02-20 23:59:59+02'

    # Start parameter

    with freeze_time(times):
        response = get_list(api_client, query_string='start=today')
        expected_events = [event3, event4, event5, event6, event7, event8]
        assert_events_in_response(expected_events, response)

    # End parameter

    with freeze_time(times):
        response = get_list(api_client, query_string='end=today')
        expected_events = [event1, event2, event3, event4, event5, event6]
        assert_events_in_response(expected_events, response)

    # Start and end parameters

    with freeze_time(times):
        response = get_list(api_client, query_string='start=today&end=today')
        expected_events = [event3, event4, event5, event6]
        assert_events_in_response(expected_events, response)


@pytest.mark.django_db
def test_start_end_now(api_client, make_event):
    parse_date = dateutil.parser.parse
    event1 = make_event('1', parse_date('2020-02-19 23:00:00+02'), parse_date('2020-02-19 23:30:00+02'))
    event2 = make_event('2', parse_date('2020-02-19 23:30:00+02'), parse_date('2020-02-20 00:00:00+02'))
    event3 = make_event('3', parse_date('2020-02-19 23:30:00+02'), parse_date('2020-02-20 00:30:00+02'))
    event4 = make_event('4', parse_date('2020-02-20 00:00:00+02'), parse_date('2020-02-20 00:30:00+02'))
    event5 = make_event('5', parse_date('2020-02-20 12:00:00+02'), parse_date('2020-02-20 13:00:00+02'))
    event6 = make_event('6', parse_date('2020-02-21 00:00:00+02'), parse_date('2020-02-21 01:00:00+02'))
    event7 = make_event('7', parse_date('2020-02-21 12:00:00+02'), parse_date('2020-02-21 13:00:00+02'))
    event8 = make_event('8')   # postponed event

    # Start parameter

    with freeze_time('2020-02-20 00:30:00+02'):
        response = get_list(api_client, query_string='start=now')
        expected_events = [event5, event6, event7, event8]
        assert_events_in_response(expected_events, response)

    # End parameter

    with freeze_time('2020-02-20 12:00:00+02'):
        response = get_list(api_client, query_string='end=now')
        expected_events = [event1, event2, event3, event4, event5]
        assert_events_in_response(expected_events, response)

    # Start and end parameters

    with freeze_time('2020-02-20 12:00:00+02'):
        response = get_list(api_client, query_string='start=now&end=now')
        expected_events = [event5]
        assert_events_in_response(expected_events, response)


@pytest.mark.django_db
def test_start_end_events_without_endtime(api_client, make_event):
    parse_date = dateutil.parser.parse
    event1 = make_event('1', parse_date('2020-02-19 23:00:00+02'))
    event2 = make_event('2', parse_date('2020-02-20 12:00:00+02'))
    event3 = make_event('3', parse_date('2020-02-21 12:34:56+02'))
    event4 = make_event('4')   # postponed event

    # Start parameter

    response = get_list(api_client, query_string='start=2020-02-19T23:00:00')
    expected_events = [event1, event2, event3, event4]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='start=2020-02-20T01:00:00')
    expected_events = [event2, event3, event4]
    assert_events_in_response(expected_events, response)

    # End parameter

    response = get_list(api_client, query_string='end=2020-02-20T12:00:00')
    expected_events = [event1, event2]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='end=2020-02-21T23:00:00')
    expected_events = [event1, event2, event3]
    assert_events_in_response(expected_events, response)

    # Start and end parameters

    response = get_list(api_client, query_string='start=2020-02-19T23:00:00&end=2020-02-21T12:34:56')
    expected_events = [event1, event2, event3]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='start=2020-02-19T23:00:01&end=2020-02-21T12:34:55')
    expected_events = [event2]
    assert_events_in_response(expected_events, response)

    # Kulke special case: multiple day event but no specific start or end times, only dates
    event1.start_time = parse_date('2020-02-19 00:00:00+02')
    event1.end_time = parse_date('2020-02-21 00:00:00+02')
    event1.has_start_time = False
    event1.has_end_time = False
    event1.save()
    # Kulke special case: single day event, specific start but no end time
    event2.start_time = parse_date('2020-02-20 18:00:00+02')
    event2.end_time = parse_date('2020-02-21 00:00:00+02')
    event2.has_start_time = True
    event2.has_end_time = False
    event2.save()

    # Start parameter for Kulke special case

    response = get_list(api_client, query_string='start=2020-02-20T12:00:00')
    # long event (no exact start) that already started should be included
    expected_events = [event1, event2, event3, event4]
    assert_events_in_response(expected_events, response)

    response = get_list(api_client, query_string='start=2020-02-20T21:00:00')
    # short event (exact start) that already started should not be included
    expected_events = [event1, event3, event4]
    assert_events_in_response(expected_events, response)
