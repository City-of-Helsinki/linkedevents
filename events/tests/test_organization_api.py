# -*- coding: utf-8 -*-
import pytest

from events.tests.utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_get_organization_class(user, organization, api_client):
    url = reverse('organizationclass-list')
    api_client.force_authenticate(user)

    response = api_client.get(url, format='json')
    response.status_code == 200
