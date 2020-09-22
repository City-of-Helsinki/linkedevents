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


@pytest.mark.django_db
def test__non_user_editable_cannot_delete_a_keyword(api_client, keyword, data_source, organization, user):
    data_source.owner = organization
    data_source.user_editable = False
    data_source.save()

    api_client.force_authenticate(user=user)

    response = api_client.delete(reverse('keyword-detail', kwargs={'pk': keyword.id}))
    assert response.status_code == 403


@pytest.mark.django_db
def test__user_editable_can_delete_a_keyword(api_client, keyword, data_source, organization, user):
    data_source.owner = organization
    data_source.user_editable = True
    data_source.save()

    api_client.force_authenticate(user=user)

    response = api_client.delete(reverse('keyword-detail', kwargs={'pk': keyword.id}))
    assert response.status_code == 204

    response = api_client.get(reverse('keyword-detail', kwargs={'pk': keyword.id}))
    assert response.status_code == 410
