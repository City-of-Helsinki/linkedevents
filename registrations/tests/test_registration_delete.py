import pytest
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse


def delete_registration(api_client, id):
    delete_url = reverse("registration-detail", kwargs={"pk": id})
    return api_client.delete(delete_url)


@pytest.mark.django_db
def test_delete_registration(api_client, registration, user):
    api_client.force_authenticate(user)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    detail_url = reverse("registration-detail", kwargs={"pk": registration.id})
    response = api_client.get(detail_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    response = api_client.get(detail_url + "?show_deleted=true")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["deleted"] == True


@pytest.mark.django_db
def test__unauthenticated_user_cannot_delete_registration(api_client, registration):
    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_admin_cannot_delete_registration(api_client, registration, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_delete_registration(
    api_client, data_source, organization, registration, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_editable_resources_can_delete_registration(
    api_client, data_source, organization, registration, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test__api_key_with_organization_can_delete_registration(
    api_client, data_source, organization, registration
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test__api_key_of_other_organization_cannot_delete_registration(
    api_client, data_source, organization2, registration
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_update_registration(
    api_client, organization, other_data_source, registration
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_delete_keywordset(api_client, registration):
    api_client.credentials(apikey="unknown")

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
