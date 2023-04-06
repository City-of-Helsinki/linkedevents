import pytest
from rest_framework import status

from .utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_keywordset_delete(api_client, user, keyword_set):
    api_client.force_authenticate(user)

    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = api_client.get(delete_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test__unauthenticated_user_cannot_delete_keywordset(api_client, keyword_set):
    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_admin_cannot_delete_keywordset(api_client, keyword_set, user):
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_delete_keywordset(
    api_client, keyword_set, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()

    api_client.force_authenticate(user)

    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_editable_resources_can_delete_keywordset(
    api_client, keyword_set, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()

    api_client.force_authenticate(user)

    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test__api_key_with_organization_can_delete_keywordset(
    api_client, keyword_set, data_source, organization
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test__api_key_of_other_organization_cannot_delete_keywordset(
    api_client, keyword_set, data_source, organization2
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_update_keywordset(
    api_client, keyword_set, organization, other_data_source
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_delete_keywordset(api_client, keyword_set):
    api_client.credentials(apikey="unknown")

    delete_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.id})
    response = api_client.delete(delete_url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
