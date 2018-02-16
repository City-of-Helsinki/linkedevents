# -*- coding: utf-8 -*-


from events.tests.utils import assert_keyword_data_is_equal
from events.tests.test_keyword_post import create_with_post
from .utils import versioned_reverse as reverse
from events.auth import ApiKeyUser
import pytest


# === util methods ===


def update_with_put(api_client, kw_id, keyword_data, credentials=None):
    if credentials:
        api_client.credentials(**credentials)
    response = api_client.put(kw_id, keyword_data, format='json')
    return response


# === tests ===


@pytest.mark.django_db
def test__update_a_keyword_with_put(api_client, keyword_dict, user):

    # create an keyword
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, keyword_dict)

    # set up updates
    data2 = response.data

    for key in ('name',):
        for lang in ('fi', 'en'):
            if lang in data2[key]:
                data2[key][lang] = '%s updated' % data2[key][lang]

    kw_id = data2.pop('@id')
    response2 = update_with_put(api_client, kw_id, data2)
    # assert
    assert_keyword_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__a_non_admin_cannot_update_a_keyword(api_client, keyword, keyword_dict, user):
    keyword.publisher.admin_users.remove(user)
    api_client.force_authenticate(user)

    detail_url = reverse('keyword-detail', kwargs={'pk': keyword.pk})
    response = update_with_put(api_client, detail_url, keyword_dict)
    assert response.status_code == 403


@pytest.mark.django_db
def test__an_admin_can_update_an_keyword_from_another_data_source(api_client, keyword2,
                                                                  other_data_source, organization, user):
    other_data_source.owner = organization
    other_data_source.user_editable = True
    other_data_source.save()
    keyword2.publisher = organization
    keyword2.name = {
        'en': 'Test location - updated',
        'fi': 'Testipaikka - updated'
    }
    keyword2.save()
    api_client.force_authenticate(user)

    detail_url = reverse('keyword-detail', kwargs={'pk': keyword2.pk})
    response = api_client.get(detail_url, format='json')
    assert response.status_code == 200
    response = update_with_put(api_client, detail_url, response.data)
    assert response.status_code == 200


@pytest.mark.django_db
def test__correct_api_key_can_update_a_keyword(api_client, keyword, keyword_dict, data_source, organization):

    data_source.owner = organization
    data_source.save()

    detail_url = reverse('keyword-detail', kwargs={'pk': keyword.pk})
    response = update_with_put(api_client, detail_url, keyword_dict,
                               credentials={'apikey': data_source.api_key})
    assert response.status_code == 200
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test__wrong_api_key_cannot_update_a_keyword(api_client, keyword, keyword_dict, data_source, other_data_source):

    detail_url = reverse('keyword-detail', kwargs={'pk': keyword.pk})
    response = update_with_put(api_client, detail_url, keyword_dict,
                               credentials={'apikey': other_data_source.api_key})
    assert response.status_code == 403
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test__api_key_without_organization_cannot_update_a_keyword(api_client, keyword, keyword_dict, data_source):

    detail_url = reverse('keyword-detail', kwargs={'pk': keyword.pk})
    response = update_with_put(api_client, detail_url, keyword_dict,
                               credentials={'apikey': data_source.api_key})
    assert response.status_code == 403


@pytest.mark.django_db
def test__unknown_api_key_cannot_update_a_keyword(api_client, keyword, keyword_dict):

    detail_url = reverse('keyword-detail', kwargs={'pk': keyword.pk})
    response = update_with_put(api_client, detail_url, keyword_dict,
                               credentials={'apikey': 'unknown'})
    assert response.status_code == 401


@pytest.mark.django_db
def test__empty_api_key_cannot_update_a_keyword(api_client, keyword, keyword_dict,):

    detail_url = reverse('keyword-detail', kwargs={'pk': keyword.pk})
    response = update_with_put(api_client, detail_url, keyword_dict,
                               credentials={'apikey': ''})
    assert response.status_code == 401
