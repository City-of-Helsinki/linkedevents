# -*- coding: utf-8 -*-
import pytest
from .utils import versioned_reverse as reverse

from events.tests.utils import assert_event_data_is_equal
from events.models import Event
from events.api import SYSTEM_DATA_SOURCE_ID


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
def test__create_a_draft_event_without_location_and_keyword(api_client,
                                                            minimal_event_dict,
                                                            user):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop('location')
    minimal_event_dict.pop('keywords')
    minimal_event_dict['publication_status'] = 'draft'
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)


@pytest.mark.django_db
def test__cannot_publish_an_event_without_location(list_url,
                                                               api_client,
                                                               minimal_event_dict,
                                                               user):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop('location')
    response = api_client.post(list_url, minimal_event_dict, format='json')
    assert response.status_code == 400
    assert ('Location' in error for error in response.data['non_field_errors'])


@pytest.mark.django_db
def test__cannot_publish_an_event_without_keywords(list_url,
                                                               api_client,
                                                               minimal_event_dict,
                                                               user):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop('keywords')
    response = api_client.post(list_url, minimal_event_dict, format='json')
    assert response.status_code == 400
    assert ('Keywords' in error for error in response.data['non_field_errors'])


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
    assert event.data_source.id == SYSTEM_DATA_SOURCE_ID
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
        assert ('location' in response.data) or ('Location' in error for error in response.data['non_field_errors'])
