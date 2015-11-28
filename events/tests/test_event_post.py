# -*- coding: utf-8 -*-
import pytest

from events.tests.utils import assert_event_data_is_equal


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
