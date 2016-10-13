# -*- coding: utf-8 -*-
from .utils import versioned_reverse as reverse
import pytest
from .utils import get


def get_list(api_client, version='v1', data=None):
    list_url = reverse('place-list', version=version)
    return get(api_client, list_url, data=data)


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
