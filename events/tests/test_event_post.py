# -*- coding: utf-8 -*-
from datetime import timedelta

import pytest
from django.utils import timezone, translation
from django.utils.encoding import force_text
from .utils import versioned_reverse as reverse

from events.tests.utils import assert_event_data_is_equal
from events.models import Event
from django.conf import settings


@pytest.fixture
def list_url():
    return reverse('event-list')


# === util methods ===

def create_with_post(api_client, event_data):
    # save with post
    response = api_client.post(reverse('event-list'), event_data, format='json')
    assert response.status_code == 201, str(response.content)

    # double-check with get
    resp2 = api_client.get(response.data['@id'])
    assert resp2.status_code == 200, str(response.content)

    return resp2


# === tests ===

@pytest.mark.django_db
def test__create_a_minimal_event_with_post(api_client,
                                           minimal_event_dict,
                                           user):
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)


@pytest.mark.django_db
def test__cannot_create_an_event_ending_before_start_time(list_url,
                                                          api_client,
                                                          minimal_event_dict,
                                                          user):
    api_client.force_authenticate(user=user)
    minimal_event_dict['end_time'] = (timezone.now() + timedelta(days=1)).isoformat()
    minimal_event_dict['start_time'] = (timezone.now() + timedelta(days=2)).isoformat()
    response = api_client.post(list_url, minimal_event_dict, format='json')
    assert response.status_code == 400
    assert 'end_time' in response.data


@pytest.mark.django_db
def test__create_a_draft_event_without_location_and_keyword(list_url,
                                                            api_client,
                                                            minimal_event_dict,
                                                            user):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop('location')
    minimal_event_dict.pop('keywords')
    minimal_event_dict['publication_status'] = 'draft'
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)

    # the drafts should not be visible to unauthorized users
    api_client.logout()
    resp2 = api_client.get(response.data['@id'])
    assert '@id' not in resp2.data

@pytest.mark.django_db
def test__cannot_create_a_draft_event_without_a_name(list_url,
                                                               api_client,
                                                               minimal_event_dict,
                                                               user):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop('name')
    minimal_event_dict['publication_status'] = 'draft'
    response = api_client.post(list_url, minimal_event_dict, format='json')
    assert response.status_code == 400
    assert 'name' in response.data


@pytest.mark.django_db
def test__cannot_publish_an_event_without_location(list_url,
                                                               api_client,
                                                               minimal_event_dict,
                                                               user):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop('location')
    response = api_client.post(list_url, minimal_event_dict, format='json')
    assert response.status_code == 400
    assert 'location' in response.data


@pytest.mark.django_db
def test__cannot_publish_an_event_without_keywords(list_url,
                                                               api_client,
                                                               minimal_event_dict,
                                                               user):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop('keywords')
    response = api_client.post(list_url, minimal_event_dict, format='json')
    assert response.status_code == 400
    assert 'keywords' in response.data


@pytest.mark.django_db
def test__create_a_complex_event_with_post(api_client,
                                           complex_event_dict,
                                           user):
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)
    assert_event_data_is_equal(complex_event_dict, response.data)


@pytest.mark.django_db
def test__autopopulated_fields(
        api_client, minimal_event_dict, user, user2, other_data_source, organization, organization2):

    # create an event
    api_client.force_authenticate(user=user)

    # try to set values for autopopulated fields
    minimal_event_dict.update(
        data_source=other_data_source.id,
        created_by=user2.id,
        last_modified_by=user2.id,
        organization=organization2.id
    )
    response = create_with_post(api_client, minimal_event_dict)

    event = Event.objects.get(id=response.data['id'])
    assert event.created_by == user
    assert event.last_modified_by == user
    assert event.created_time is not None
    assert event.last_modified_time is not None
    assert event.data_source.id == settings.SYSTEM_DATA_SOURCE_ID
    assert event.publisher == organization


# location field is used for JSONLDRelatedField tests
@pytest.mark.django_db
@pytest.mark.parametrize("input,expected", [
    ({'location': {'@id': '/v1/place/test%20location/'}}, 201),
    ({'location': {'@id': ''}}, 400),  # field required
    ({'location': {'foo': 'bar'}}, 400),  # incorrect json
    ({'location': '/v1/place/test%20location/'}, 400),  # incorrect json
    ({'location': 7}, 400),  # incorrect json
    ({'location': None}, 400),  # cannot be null
    ({}, 400),  # field required
])
def test__jsonld_related_field(api_client, minimal_event_dict, list_url, place, user, input, expected):
    api_client.force_authenticate(user)

    del minimal_event_dict['location']
    minimal_event_dict.update(input)

    response = api_client.post(list_url, minimal_event_dict, format='json')
    assert response.status_code == expected
    if expected >= 400:
        # check that there is a error message for location field
        assert 'location' in response.data


@pytest.mark.django_db
def test_start_time_and_end_time_validation(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)

    minimal_event_dict['start_time'] = timezone.now() - timedelta(days=2)
    minimal_event_dict['end_time'] = timezone.now() - timedelta(days=1)

    with translation.override('en'):
        response = api_client.post(reverse('event-list'), minimal_event_dict, format='json')
    assert response.status_code == 400
    assert 'Start time cannot be in the past.' in response.data['start_time']
    assert 'End time cannot be in the past.' in response.data['end_time']


@pytest.mark.django_db
def test_description_and_short_description_required_in_name_languages(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)

    minimal_event_dict['name'] = {'fi': 'nimi', 'sv': 'namn'}
    minimal_event_dict['short_description'] = {'fi': 'lyhyt kuvaus'}
    minimal_event_dict['description'] = {'sv': 'description in swedish'}

    with translation.override('en'):
        response = api_client.post(reverse('event-list'), minimal_event_dict, format='json')

    # there should be only one error
    assert len(response.data['short_description']) == 1
    assert len(response.data['description']) == 1

    assert (force_text(response.data['short_description']['sv']) ==
            'This field must be specified before an event is published.')
    assert (force_text(response.data['description']['fi']) ==
            'This field must be specified before an event is published.')


@pytest.mark.django_db
def test_short_description_cannot_exceed_160_chars(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)

    minimal_event_dict['short_description']['fi'] = 'x' * 161

    with translation.override('en'):
        response = api_client.post(reverse('event-list'), minimal_event_dict, format='json')
    assert response.status_code == 400
    assert (force_text(response.data['short_description']['fi'] ==
            'Short description length must be 160 characters or less'))


@pytest.mark.django_db
@pytest.mark.parametrize("offers, expected", [
    ([{'is_free': True}], 201),
    ([{'is_free': False, 'price': {'fi': 4}}], 201),
    ([{'description': 'foo'}, {'is_free': True}], 201),

    ([{'is_free': False}], 400)
])
def test_price_info_required(api_client, minimal_event_dict, user, offers, expected):
    api_client.force_authenticate(user)
    minimal_event_dict['offers'] = offers

    with translation.override('en'):
        response = api_client.post(reverse('event-list'), minimal_event_dict, format='json')

    assert response.status_code == expected
    if expected == 400:
        assert force_text(response.data['offers'][0]) == 'Price info must be specified before an event is published.'
