# -*- coding: utf-8 -*-
from datetime import timedelta
from django.utils import timezone

import pytest
from .utils import versioned_reverse as reverse

from events.tests.utils import assert_event_data_is_equal
from events.tests.test_event_post import create_with_post
from events.models import Event


# === util methods ===

def update_with_put(api_client, event_id, event_data):
    response = api_client.put(event_id, event_data, format='json')
    return response


# === tests ===

@pytest.mark.django_db
def test__update_a_draft_with_put(api_client, minimal_event_dict, user):

    # create an event
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop('location')
    minimal_event_dict.pop('keywords')
    minimal_event_dict['publication_status'] = 'draft'
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    data2 = response.data
    print('got the post response')
    print(data2)

    # store updates
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)
    print('got the put response')
    print(response2.data)

    # assert
    assert_event_data_is_equal(data2, response2.data)


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

    for key in ('name', ):
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
    data2['keywords'] = data2['keywords'][:1]
    data2['in_language'] = data2['in_language'][:2]

    # store updates
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)

    # assert
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__reschedule_an_event_with_put(api_client, complex_event_dict, user):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # create a new datetime
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat()
    data2 = response.data
    data2['start_time'] = new_datetime
    data2['end_time'] = new_datetime

    # update the event
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend rescheduled the event
    data2['event_status'] = 'EventRescheduled'
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__postpone_an_event_with_put(api_client, complex_event_dict, user):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)
    print('created the event')
    print(response.data)

    # remove the start_time
    data2 = response.data
    data2['start_time'] = None

    # update the event
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)
    print('updated the event')
    print(response2.data)

    # assert backend postponed the event
    data2['event_status'] = 'EventPostponed'
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__cancel_an_event_with_put(api_client, complex_event_dict, user):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # mark the event cancelled
    data2 = response.data
    data2['event_status'] = 'EventCancelled'

    # update the event
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend cancelled the event
    data2['event_status'] = 'EventCancelled'
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__reschedule_a_cancelled_event_with_put(api_client, complex_event_dict, user):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # mark the event cancelled
    data2 = response.data
    data2['event_status'] = 'EventCancelled'

    # update the event
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend cancelled the event
    data2['event_status'] = 'EventCancelled'
    assert_event_data_is_equal(data2, response2.data)

    # create a new datetime and remove the cancelled status
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat()
    data3 = response2.data
    data3['start_time'] = new_datetime
    data3['end_time'] = new_datetime
    data3.pop('event_status')

    # update the event
    event_id = data3.pop('@id')
    response3 = update_with_put(api_client, event_id, data3)

    # assert backend rescheduled the event
    data3['event_status'] = 'EventRescheduled'
    assert_event_data_is_equal(data3, response3.data)


@pytest.mark.django_db
def test__a_non_admin_cannot_update_an_event(api_client, event, complex_event_dict, user):
    event.publisher.admin_users.remove(user)
    api_client.force_authenticate(user)

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict)
    assert response.status_code == 403


@pytest.mark.django_db
def test__correct_api_key_can_update_an_event(api_client, event, complex_event_dict, data_source):

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict)
    assert response.status_code == 403


@pytest.mark.django_db
def test__wrong_api_key_cannot_update_an_event(api_client, event, complex_event_dict, other_data_source):

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict)
    assert response.status_code == 403


@pytest.mark.django_db
def test__empty_api_key_cannot_update_an_event(api_client, event, complex_event_dict,):

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict)
    assert response.status_code == 403