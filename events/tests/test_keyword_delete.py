# -*- coding: utf-8 -*-
import pytest
from .utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_keyword_delete(api_client, user, keyword):
    api_client.force_authenticate(user)

    response = api_client.delete(reverse('keyword-detail', kwargs={'pk': keyword.id}))
    assert response.status_code == 204

    response = api_client.get(reverse('keyword-detail', kwargs={'pk': keyword.id}))
    assert response.status_code == 410
