import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse


def get_list(api_client):
    url = reverse("organizationclass-list")

    return api_client.get(url, format="json")


def assert_organization_classes_in_response(response, classes):
    response_ids = {o_class["id"] for o_class in response.data["data"]}
    expected_ids = {o_class.id for o_class in classes}
    assert response_ids == expected_ids


def get_list_and_assert_organization_classes(
    api_client,
    classes,
):
    response = get_list(api_client)
    assert response.status_code == status.HTTP_200_OK
    assert_organization_classes_in_response(response, classes)


def get_detail(api_client, detail_pk):
    detail_url = reverse("organizationclass-detail", kwargs={"pk": detail_pk})
    return api_client.get(detail_url, format="json")


def assert_get_organization_class(api_client, detail_pk):
    response = get_detail(api_client, detail_pk)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "user2_with_user_type",
    ["org_admin", "superuser"],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_admin_and_superuser_can_get_organization_classes(
    api_client, organization, organization_class, user2_with_user_type
):
    api_client.force_authenticate(user2_with_user_type)

    get_list_and_assert_organization_classes(api_client, [organization_class])


@pytest.mark.django_db
def test_organization_class_id_is_audit_logged_get_detail(
    user_api_client, organization_class
):
    response = get_detail(user_api_client, organization_class.pk)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        organization_class.pk
    ]


@pytest.mark.django_db
def test_organization_class_id_is_audit_logged_get_list(
    user_api_client, organization, organization_class
):
    response = get_list(user_api_client)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        organization_class.pk
    ]


@pytest.mark.django_db
def test_anonymous_user_cannot_get_organization_classes(api_client, organization_class):
    response = get_list(api_client)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_get_organization_classes(
    api_client, organization, organization_class, user
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = get_list(api_client)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_user_can_get_organization_classes(
    api_client, data_source, organization, organization_class
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    get_list_and_assert_organization_classes(api_client, [organization_class])


@pytest.mark.django_db
def test_anonymous_user_can_retrieve_organization_class(api_client, organization_class):
    assert_get_organization_class(api_client, organization_class.id)
