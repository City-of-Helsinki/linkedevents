# -*- coding: utf-8 -*-
from datetime import timedelta
from copy import deepcopy

import pytz
from django.utils import timezone
from django.core.management import call_command

import pytest
from .utils import versioned_reverse as reverse

from events.tests.utils import assert_event_data_is_equal
from events.tests.test_event_post import create_with_post
from .conftest import keyword_id, location_id
from events.models import Event, Keyword, Place
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
def test__keyword_n_events_updated(api_client, minimal_event_dict, user, data_source):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    call_command('update_n_events')
    assert Keyword.objects.get(id=data_source.id + ':test').n_events == 1
    data2 = response.data
    print('got the post response')
    print(data2)

    # change the keyword and add an audience
    event_id = data2.pop('@id')
    data2['keywords'] = [{'@id': keyword_id(data_source, 'test2')}]
    data2['audience'] = [{'@id': keyword_id(data_source, 'test3')}]
    response2 = update_with_put(api_client, event_id, data2)
    print('got the put response')
    print(response2.data)
    call_command('update_n_events')
    assert Keyword.objects.get(id=data_source.id + ':test').n_events == 0
    assert Keyword.objects.get(id=data_source.id + ':test2').n_events == 1
    assert Keyword.objects.get(id=data_source.id + ':test3').n_events == 1


@pytest.mark.django_db
def test__location_n_events_updated(api_client, minimal_event_dict, user, data_source,
                                    other_data_source, place2):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    call_command('update_n_events')
    assert Place.objects.get(id=data_source.id + ':test_location').n_events == 1
    data2 = response.data
    print('got the post response')
    print(data2)

    # change the location
    event_id = data2.pop('@id')
    data2['location'] = {'@id': location_id(place2)}
    response2 = update_with_put(api_client, event_id, data2)
    print('got the put response')
    print(response2.data)
    call_command('update_n_events')
    assert Place.objects.get(id=data_source.id + ':test_location').n_events == 0
    assert Place.objects.get(id=other_data_source.id + ':test_location_2').n_events == 1


@pytest.mark.django_db
def test__update_minimal_event_with_autopopulated_fields_with_put(api_client, minimal_event_dict, user, organization):

    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    data = response.data

    assert_event_data_is_equal(minimal_event_dict, data)
    event_id = data['@id']

    response2 = update_with_put(api_client, event_id, minimal_event_dict)
    assert_event_data_is_equal(data, response2.data)
    event = Event.objects.get(id=data['id'])
    assert event.created_by == user
    assert event.last_modified_by == user
    assert event.created_time is not None
    assert event.last_modified_time is not None
    assert event.data_source.id == settings.SYSTEM_DATA_SOURCE_ID
    assert event.publisher == organization
    # events are automatically marked as ending at midnight, local time
    assert event.end_time == timezone.localtime(timezone.now() + timedelta(days=2)).\
        replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
    assert event.has_end_time is False

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
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat().replace('+00:00', 'Z')
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
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat().replace('+00:00', 'Z')
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
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat().replace('+00:00', 'Z')
    data2['start_time'] = new_datetime
    data2['end_time'] = new_datetime
    data2['event_status'] = 'EventScheduled'
    response3 = api_client.put(event_id, data2, format='json')

    # assert the event does not revert back to scheduled
    assert response3.status_code == 400
    assert 'event_status' in response3.data

    # reschedule, but do not try to cancel marking
    data2 = response2.data
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat().replace('+00:00', 'Z')
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
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat().replace('+00:00', 'Z')
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
    new_datetime = (timezone.now() + timedelta(days=3)).isoformat().replace('+00:00', 'Z')
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
def test__an_admin_can_update_an_event_from_another_data_source(api_client, event2, keyword, offer,
                                                                other_data_source, organization, user):
    other_data_source.owner = organization
    other_data_source.user_editable = True
    other_data_source.save()
    event2.publisher = organization
    event2.keywords.add(keyword)  # keyword is needed in testing POST and PUT with event data
    event2.offers.add(offer)  # ditto for offer
    event2.save()
    api_client.force_authenticate(user)

    detail_url = reverse('event-detail', kwargs={'pk': event2.pk})
    response = api_client.get(detail_url, format='json')
    assert response.status_code == 200
    response = update_with_put(api_client, detail_url, response.data)
    assert response.status_code == 200


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


@pytest.mark.django_db
def test_multiple_event_update(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)
    minimal_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict_2['name']['fi'] = 'testing_2'

    # create events first
    resp = create_with_post(api_client, minimal_event_dict)
    minimal_event_dict['id'] = resp.data['id']
    resp = create_with_post(api_client, minimal_event_dict_2)
    minimal_event_dict_2['id'] = resp.data['id']

    minimal_event_dict['name']['fi'] = 'updated_name'
    minimal_event_dict_2['name']['fi'] = 'updated_name_2'

    response = api_client.put(reverse('event-list'), [minimal_event_dict, minimal_event_dict_2], format='json')
    assert response.status_code == 200

    event_names = set(Event.objects.values_list('name_fi', flat=True))

    assert event_names == {'updated_name', 'updated_name_2'}


@pytest.mark.django_db
def test_multiple_event_update_with_incorrect_json(api_client, minimal_event_dict, organization, data_source):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)
    response = api_client.put(reverse('event-list'), minimal_event_dict, format='json')
    assert response.status_code == 400


@pytest.mark.django_db
def test_multiple_event_update_second_fails(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)
    minimal_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict_2['name']['fi'] = 'testing_2'

    # create events first
    resp = create_with_post(api_client, minimal_event_dict)
    minimal_event_dict['id'] = resp.data['id']
    resp = create_with_post(api_client, minimal_event_dict_2)
    minimal_event_dict_2['id'] = resp.data['id']

    minimal_event_dict['name']['fi'] = 'updated_name'
    minimal_event_dict_2.pop('name')  # name is required, so the event update event should fail

    response = api_client.put(reverse('event-list'), [minimal_event_dict, minimal_event_dict_2], format='json')
    assert response.status_code == 400
    assert 'name' in response.data[1]

    event_names = set(Event.objects.values_list('name_fi', flat=True))

    # verify that first event isn't updated either
    assert event_names == {'testing', 'testing_2'}


@pytest.mark.django_db
def test_cannot_edit_events_in_the_past(api_client, event, minimal_event_dict, user):
    api_client.force_authenticate(user)

    event.start_time = timezone.now() - timedelta(days=2)
    event.end_time = timezone.now() - timedelta(days=1)
    event.save(update_fields=('start_time', 'end_time'))

    response = api_client.put(reverse('event-detail', kwargs={'pk': event.id}), minimal_event_dict, format='json')
    assert response.status_code == 403
    assert 'Cannot edit a past event' in str(response.content)
