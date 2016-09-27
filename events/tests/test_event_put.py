# -*- coding: utf-8 -*-
from datetime import timedelta
from django.utils import timezone

import pytest
from .utils import versioned_reverse as reverse

from events.tests.utils import assert_event_data_is_equal
from events.tests.test_event_post import create_with_post
from .conftest import DATETIME
from events.models import Event
from django.conf import settings


# === util methods ===

def update_with_put(api_client, event_id, event_data, credentials=None):
    if credentials:
        api_client.credentials(**credentials)
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

    # try to cancel marking as rescheduled
    data2['event_status'] = 'EventScheduled'
    response3 = api_client.put(event_id, data2, format='json')

    # assert the event does not revert back to scheduled
    assert response3.status_code == 400
    assert 'event_status' in response3.data

    # create a new datetime again
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat()
    data2 = response2.data
    data2['start_time'] = new_datetime
    data2['end_time'] = new_datetime

    # update the event again
    response2 = update_with_put(api_client, event_id, data2)

    # assert the event remains rescheduled
    data2['event_status'] = 'EventRescheduled'
    assert_event_data_is_equal(data2, response2.data)

@pytest.mark.django_db
def test__postpone_an_event_with_put(api_client, complex_event_dict, user):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # remove the start_time
    data2 = response.data
    data2['start_time'] = None

    # update the event
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend postponed the event
    data2['event_status'] = 'EventPostponed'
    assert_event_data_is_equal(data2, response2.data)

    # try to cancel marking as postponed
    data2 = response2.data
    data2['event_status'] = 'EventScheduled'
    response3 = api_client.put(event_id, data2, format='json')

    # assert the event does not revert back to scheduled
    assert response3.status_code == 400
    assert 'event_status' in response2.data

    # reschedule and try to cancel marking
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat()
    data2['start_time'] = new_datetime
    data2['end_time'] = new_datetime
    data2['event_status'] = 'EventScheduled'
    response3 = api_client.put(event_id, data2, format='json')

    # assert the event does not revert back to scheduled
    assert response3.status_code == 400
    assert 'event_status' in response3.data

    # reschedule, but do not try to cancel marking
    data2 = response2.data
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat()
    data2['start_time'] = new_datetime
    data2['end_time'] = new_datetime
    data2.pop('event_status')
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)

    # assert the event is marked rescheduled
    data2['event_status'] = 'EventRescheduled'
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
def test__cancel_a_postponed_event_with_put(api_client, complex_event_dict, user):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # remove the start_time
    data2 = response.data
    data2['start_time'] = None

    # update the event
    event_id = data2.pop('@id')
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend postponed the event
    data2['event_status'] = 'EventPostponed'
    assert_event_data_is_equal(data2, response2.data)

    # mark the event cancelled
    data2 = response.data
    data2['event_status'] = 'EventCancelled'

    # update the event
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend cancelled the event
    data2['event_status'] = 'EventCancelled'
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__cancel_a_rescheduled_event_with_put(api_client, complex_event_dict, user):

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

    # mark the event cancelled
    data2 = response.data
    data2['event_status'] = 'EventCancelled'

    # update the event
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


# the following values may not be posted
@pytest.mark.django_db
@pytest.mark.parametrize("non_permitted_input,non_permitted_response", [
    ({'id': 'not_allowed:1'}, 400), # may not fake id
    ({'id': settings.SYSTEM_DATA_SOURCE_ID + ':changed'}, 400), # may not change object id
    ({'data_source': 'theotherdatasourceid'}, 400),  # may not fake data source
    ({'publisher': 'test_organization2'}, 400),  # may not fake organization
])
def test__non_editable_fields_at_put(api_client, minimal_event_dict, user,
                                     non_permitted_input, non_permitted_response):
    # create the event first
    api_client.force_authenticate(user)
    response = create_with_post(api_client, minimal_event_dict)
    data2 = response.data
    event_id = data2.pop('@id')

    # try to put non permitted values
    data2.update(non_permitted_input)

    response2 = api_client.put(event_id, data2, format='json')
    assert response2.status_code == non_permitted_response
    if non_permitted_response >= 400:
        # check that there is an error message for the corresponding field
        assert list(non_permitted_input)[0] in response2.data


@pytest.mark.django_db
def test__a_non_admin_cannot_update_an_event(api_client, event, complex_event_dict, user):
    event.publisher.admin_users.remove(user)
    api_client.force_authenticate(user)

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict)
    assert response.status_code == 403


@pytest.mark.django_db
def test__correct_api_key_can_update_an_event(api_client, event, complex_event_dict, data_source, organization):

    data_source.owner = organization
    data_source.save()

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict,
                               credentials={'apikey': data_source.api_key})
    assert response.status_code == 200


@pytest.mark.django_db
def test__wrong_api_key_cannot_update_an_event(api_client, event, complex_event_dict, data_source, other_data_source,
                                               organization, organization2):

    data_source.owner = organization
    data_source.save()
    other_data_source.owner = organization2
    other_data_source.save()
    del(complex_event_dict['publisher'])

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict,
                               credentials={'apikey': other_data_source.api_key})
    print(response.data)
    assert response.status_code == 403


@pytest.mark.django_db
def test__api_key_without_organization_cannot_update_an_event(api_client, event, complex_event_dict, data_source):

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict,
                               credentials={'apikey': data_source.api_key})
    assert response.status_code == 403


@pytest.mark.django_db
def test__unknown_api_key_cannot_update_an_event(api_client, event, complex_event_dict):

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict,
                               credentials={'apikey': 'unknown'})
    assert response.status_code == 401


@pytest.mark.django_db
def test__empty_api_key_cannot_update_an_event(api_client, event, complex_event_dict,):

    detail_url = reverse('event-detail', kwargs={'pk': event.pk})
    response = update_with_put(api_client, detail_url, complex_event_dict,
                               credentials={'apikey': ''})
    assert response.status_code == 401