# -*- coding: utf-8 -*-
import pytest
from .utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_list_endpoint_delete(api_client, user, event):
    api_client.force_authenticate(user)

    response = api_client.delete(reverse('event-list'), format='json')
    assert response.status_code == 405


@pytest.mark.django_db
def test_event_delete(api_client, user, event):
    api_client.force_authenticate(user)

    response = api_client.delete(reverse('event-detail', kwargs={'pk': event.id}))
    assert response.status_code == 204

    response = api_client.get(reverse('event-detail', kwargs={'pk': event.id}))
    assert response.status_code == 410
