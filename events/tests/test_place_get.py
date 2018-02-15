# -*- coding: utf-8 -*-
from django.core.management import call_command

from .utils import versioned_reverse as reverse
import pytest
from .utils import get
from .test_event_get import get_detail as get_event_detail


def get_list(api_client, version='v1', data=None):
    list_url = reverse('place-list', version=version)
    return get(api_client, list_url, data=data)


def get_detail(api_client, detail_pk, version='v1', data=None):
    detail_url = reverse('place-detail', version=version, kwargs={'pk': detail_pk})
    return get(api_client, detail_url, data=data)


@pytest.mark.django_db
def test_get_place_detail(api_client, place):
    response = get_detail(api_client, place.pk)
    assert response.data['id'] == place.id


@pytest.mark.django_db
def test_get_unknown_place_detail_check_404(api_client):
    response = api_client.get(reverse('place-detail', kwargs={'pk': 'möö'}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_place_detail_check_redirect_and_event_remap(api_client, event, place, place2):
    call_command('update_n_events')
    response = get_detail(api_client, place.pk)
    assert response.data['id'] == place.id
    assert response.data['n_events'] == 1
    event_response = get_event_detail(api_client, event.pk)
    assert event_response.data['location']['@id'] == reverse('place-detail', kwargs={'pk': place.id})
    place.replaced_by = place2
    place.deleted = True
    place.save()
    call_command('update_n_events')
    url = reverse('place-detail', version='v1', kwargs={'pk': place.pk})
    response = api_client.get(url, data=None, format='json')
    assert response.status_code == 301
    response2 = api_client.get(response.url, data=None, format='json')
    assert response2.data['id'] == place2.id
    assert response2.data['n_events'] == 1
    event_response2 = get_event_detail(api_client, event.pk)
    assert event_response2.data['location']['@id'] == reverse('place-detail', kwargs={'pk': place2.id})
    with pytest.raises(Exception):
        place2.replaced_by = place
        place.save()


@pytest.mark.django_db
def test_get_place_list_verify_division_filter(api_client, place, place2, place3, administrative_division,
                                               administrative_division2):
    place.divisions = [administrative_division]
    place2.divisions = [administrative_division2]
    place3.divisions.clear()

    # filter using one value
    response = get_list(api_client, data={'show_all_places': 1, 'division': administrative_division.ocd_id})
    data = response.data['data']
    assert len(data) == 1
    assert place.id in [entry['id'] for entry in data]

    # filter using two values
    filter_value = '%s,%s' % (administrative_division.ocd_id, administrative_division2.ocd_id)
    response = get_list(api_client, data={'show_all_places': 1, 'division': filter_value})
    data = response.data['data']
    assert len(data) == 2
    ids = [entry['id'] for entry in data]
    assert place.id in ids
    assert place2.id in ids


@pytest.mark.django_db
def test_get_place_list_check_division(api_client, place, administrative_division, municipality):
    place.divisions = [administrative_division]

    response = get_list(api_client, data={'show_all_places': 1})
    division = response.data['data'][0]['divisions'][0]

    assert division['type'] == 'neighborhood'
    assert division['name'] == {'en': 'test division'}
    assert division['ocd_id'] == 'ocd-division/test:1'
    assert division['municipality'] == 'test municipality'
