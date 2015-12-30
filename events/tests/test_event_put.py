# -*- coding: utf-8 -*-
import pytest
from django.core.urlresolvers import reverse

from events.tests.utils import assert_event_data_is_equal
from events.tests.test_event_post import create_with_post


# === util methods ===

def update_with_put(api_client, event_id, event_data):
    response = api_client.put(event_id, event_data, format='json')
    return response


# === tests ===

@pytest.mark.django_db
def test__update_an_event_with_put(api_client, complex_event_dict, user):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # dummy inputs
    TEXT = 'text updated'
    URL = "http://localhost"

    # set up updates
    data2 = response.data

    for key in ('name', 'headline'):
        for lang in ('fi', 'en', 'sv'):
            if lang in data2[key]:
                data2[key][lang] = '%s updated' % data2[key][lang]

    data2['offers'] = [
        {
            "is_free": False,
            "price": {"en": TEXT, "sv": TEXT, "fi": TEXT},
            "description": {"en": TEXT, "fi": TEXT},
            "info_url": {"en": URL, "sv": URL, "fi": URL}
        }
    ]
    data2['keywords'] = data2['keywords'][:2]

    # store updates
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)

    # assert
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__a_non_admin_cannot_update_an_event(api_client, event, complex_event_dict, user):
    event.publisher.admin_users.remove(user)
    api_client.force_authenticate(user)

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict)
    assert response.status_code == 403
