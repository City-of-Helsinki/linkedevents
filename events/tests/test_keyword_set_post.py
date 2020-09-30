# -*- coding: utf-8 -*-

from events.tests.utils import assert_keyword_set_data_is_equal
from .utils import versioned_reverse as reverse
from events.auth import ApiKeyUser
import pytest


# === util methods ===


def create_with_post(api_client, keyword_set_data, data_source=None, version='v1'):
    create_url = reverse('keywordset-list', version=version)
    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    # save with post
    response = api_client.post(create_url, keyword_set_data, format='json')
    assert response.status_code == 201, str(response.content)

    # double-check with get
    resp2 = api_client.get(response.data['@id'])
    assert resp2.status_code == 200, str(resp2.content)

    return resp2


# === tests ===


@pytest.mark.django_db
def test__create_keyword_set_with_post(api_client, keyword_set_dict, user):
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, keyword_set_dict)
    assert_keyword_set_data_is_equal(keyword_set_dict, response.data)


@pytest.mark.django_db
def test__cannot_create_an_keyword_set_with_existing_id(api_client, keyword_set_dict, user):
    api_client.force_authenticate(user=user)

    response1 = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response1.status_code == 201

    keyword_set_dict['id'] = response1.data['@id']
    response2 = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response2.status_code == 400


@pytest.mark.django_db
def test__a_non_user_cannot_create_a_keyword_set(api_client, keyword_set_dict):
    response = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response.status_code == 401


@pytest.mark.django_db
def test__a_non_admin_cannot_create_a_keyword_set(api_client, keyword_set_dict, user):
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test__api_key_with_organization_can_create_a_keyword_set(api_client, keyword_set_dict, data_source, organization):

    data_source.owner = organization
    data_source.save()

    response = create_with_post(api_client, keyword_set_dict, data_source)
    assert_keyword_set_data_is_equal(keyword_set_dict, response.data)
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test__api_key_without_organization_cannot_create_a_keyword_set(api_client, keyword_set_dict, data_source):
    api_client.credentials(apikey=data_source.api_key)
    response = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test__unknown_api_key_cannot_create_a_keyword_set(api_client, keyword_set_dict):

    api_client.credentials(apikey='unknown')
    response = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response.status_code == 401


@pytest.mark.django_db
def test__empty_api_key_cannot_create_a_keyword_set(api_client, keyword_set_dict):

    api_client.credentials(apikey='')
    response = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response.status_code == 401


@pytest.mark.django_db
def test__non_user_editable_cannot_create_keyword_set(api_client,
                                                      keyword,
                                                      keyword_set_dict,
                                                      data_source,
                                                      organization,
                                                      user):
    data_source.owner = organization
    data_source.user_editable = False
    data_source.save()
    api_client.force_authenticate(user=user)
    response = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test__user_editable_can_create_keyword_set(api_client, keyword, keyword_set_dict, data_source, organization, user):
    data_source.owner = organization
    data_source.user_editable = True
    data_source.save()
    api_client.force_authenticate(user=user)
    response = api_client.post(reverse('keywordset-list'), keyword_set_dict, format='json')
    assert response.status_code == 201
