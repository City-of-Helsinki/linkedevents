# -*- coding: utf-8 -*-
import pytest
from .utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_place_delete(api_client, user, place):
    api_client.force_authenticate(user)

    response = api_client.delete(reverse('place-detail', kwargs={'pk': place.id}))
    assert response.status_code == 204

    response = api_client.get(reverse('place-detail', kwargs={'pk': place.id}))
    assert response.status_code == 410
