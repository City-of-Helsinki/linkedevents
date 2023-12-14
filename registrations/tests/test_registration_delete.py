import pytest
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory


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


@pytest.mark.django_db
def test_financial_admin_cannot_delete_registration(api_client, registration):
    user = UserFactory()
    user.financial_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unauthenticated_user_cannot_delete_registration(api_client, registration):
    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__registration_with_signups_cannot_be_deleted(
    api_client, registration, signup, user
):
    api_client.force_authenticate(user)
    response = delete_registration(api_client, registration.id)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Registration with signups cannot be deleted"


@pytest.mark.django_db
def test__non_admin_cannot_delete_registration(api_client, registration, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_admin_can_delete_registration_regardless_of_non_user_editable_resources(
    user_api_client, data_source, organization, registration, user_editable_resources
):
    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    response = delete_registration(user_api_client, registration.id)
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_registration_admin_can_delete_registration_regardless_of_non_user_editable_resources(
    user_api_client,
    data_source,
    organization,
    registration,
    user,
    user_editable_resources,
):
    user.get_default_organization().registration_admin_users.add(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    response = delete_registration(user_api_client, registration.id)
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
def test__api_key_from_wrong_data_source_cannot_delete_registration(
    api_client, organization, other_data_source, registration
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_delete_registration(api_client, registration):
    api_client.credentials(apikey="unknown")

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_registration_id_is_audit_logged_on_delete(user_api_client, registration):
    response = delete_registration(user_api_client, registration.id)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        registration.pk
    ]
