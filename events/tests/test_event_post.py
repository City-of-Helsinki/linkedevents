# -*- coding: utf-8 -*-
import pytest

from events.tests.utils import assert_event_data_is_equal
from events.models import Event
from events.api import SYSTEM_DATA_SOURCE_ID

# === util methods ===

def create_with_post(api_client, event_data):
    # save with post
    response = api_client.post('/v0.1/event/', event_data, format='json')
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
