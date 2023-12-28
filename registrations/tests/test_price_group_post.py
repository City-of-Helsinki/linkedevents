import pytest
from django_orghierarchy.models import Organization
from rest_framework import status
from rest_framework.test import APIClient

from audit_log.models import AuditLogEntry
from events.tests.factories import ApiKeyUserFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.models import User
from registrations.models import PriceGroup
from registrations.tests.utils import create_user_by_role

# === util methods ===


def create_price_group(api_client: APIClient, data: dict):
    url = reverse("pricegroup-list")
    response = api_client.post(url, data, format="json")

    return response


def assert_create_price_group(api_client: APIClient, data: dict):
    response = create_price_group(api_client, data)
    assert response.status_code == status.HTTP_201_CREATED

    return response


def assert_create_price_group_and_check_values(
    api_client: APIClient, organization: Organization, user: User
):
    assert PriceGroup.objects.count() == 8

    data = {
        "publisher": organization.pk,
        "description": {
            "fi": "FI desc",
            "sv": "SV desc",
            "en": "EN desc",
        },
        "is_free": True,
    }
    response = assert_create_price_group(api_client, data)

    assert PriceGroup.objects.count() == 9

    price_group = PriceGroup.objects.last()
    assert price_group.publisher_id == data["publisher"]
    assert price_group.created_by_id == user.id
    assert price_group.created_time is not None
    assert price_group.is_free is True
    for lang, desc in data["description"].items():
        assert response.data["description"][lang] == desc
        assert getattr(price_group, f"description_{lang}") == desc


def assert_create_price_group_not_allowed(
    api_client: APIClient, organization: Organization
):
    assert PriceGroup.objects.count() == 8

    data = {
        "publisher": organization.pk,
        "description": {
            "en": "Test Price Group",
        },
        "is_free": True,
    }
    response = create_price_group(api_client, data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert PriceGroup.objects.count() == 8


# === tests ===


@pytest.mark.parametrize(
    "other_role",
    [
        "admin",
        "registration_admin",
        "financial_admin",
        "regular_user",
    ],
)
@pytest.mark.django_db
def test_superuser_can_create_price_group_regardless_of_other_roles(
    api_client, organization, other_role
):
    user = create_user_by_role(other_role, organization)
    user.is_superuser = True
    user.save(update_fields=["is_superuser"])

    api_client.force_authenticate(user)

    assert_create_price_group_and_check_values(api_client, organization, user)


@pytest.mark.django_db
def test_financial_admin_can_create_price_group(api_client, organization):
    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    assert_create_price_group_and_check_values(api_client, organization, user)


@pytest.mark.django_db
def test_price_group_create_text_fields_are_sanitized(api_client, organization):
    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    assert PriceGroup.objects.count() == 8

    data = {
        "publisher": organization.pk,
        "description": {
            "en": "<p>Test Price Group</p>",
        },
    }
    assert_create_price_group(api_client, data)

    assert PriceGroup.objects.count() == 9
    assert PriceGroup.objects.last().description == "Test Price Group"


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_create_price_group(
    api_client, organization, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    assert_create_price_group_not_allowed(api_client, organization)


@pytest.mark.django_db
def test_anonymous_user_cannot_create_price_group(api_client, organization):
    assert PriceGroup.objects.count() == 8

    data = {
        "publisher": organization.pk,
        "description": {"en": "Test Price Group"},
    }
    response = create_price_group(api_client, data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert PriceGroup.objects.count() == 8


@pytest.mark.django_db
def test_apikey_user_with_financial_admin_rights_can_create_price_group(
    api_client, organization, data_source
):
    apikey_user = ApiKeyUserFactory(data_source=data_source)
    api_client.credentials(apikey=data_source.api_key)

    data_source.owner = organization
    data_source.user_editable_registration_price_groups = True
    data_source.save(update_fields=["owner", "user_editable_registration_price_groups"])

    assert_create_price_group_and_check_values(api_client, organization, apikey_user)


@pytest.mark.django_db
def test_apikey_user_without_financial_admin_rights_cannot_create_price_group(
    api_client, organization, data_source
):
    data_source.owner = organization
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    assert_create_price_group_not_allowed(api_client, organization)


@pytest.mark.django_db
def test_unknown_apikey_user_cannot_create_price_group(api_client, organization):
    assert PriceGroup.objects.count() == 8

    api_client.credentials(apikey="bs")

    data = {
        "publisher": organization.pk,
        "description": {"en": "Test Price Group"},
    }
    response = create_price_group(api_client, data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert PriceGroup.objects.count() == 8


@pytest.mark.parametrize("publisher", ["", None, "not_given"])
@pytest.mark.django_db
def test_cannot_create_signup_group_without_publisher(api_client, publisher):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    assert PriceGroup.objects.count() == 8

    data = {
        "description": {"en": "Test Price Group"},
    }
    if publisher != "not_given":
        data["publisher"] = publisher

    response = create_price_group(api_client, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert PriceGroup.objects.count() == 8


@pytest.mark.parametrize("description", ["", None, "not_given"])
@pytest.mark.django_db
def test_cannot_create_signup_group_without_description(
    api_client, organization, description
):
    user = create_user_by_role("superuser", organization)
    api_client.force_authenticate(user)

    assert PriceGroup.objects.count() == 8

    data = {
        "publisher": organization.pk,
    }
    if description != "not_given":
        data["description"] = {"en": description}

    response = create_price_group(api_client, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert PriceGroup.objects.count() == 8


@pytest.mark.django_db
def test_price_group_id_is_audit_logged_on_post(api_client, organization):
    user = create_user_by_role("superuser", organization)
    api_client.force_authenticate(user)

    data = {
        "publisher": organization.pk,
        "description": {"en": "Test"},
    }
    response = assert_create_price_group(api_client, data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]
