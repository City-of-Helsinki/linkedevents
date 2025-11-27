from decimal import Decimal

import pytest
from django_orghierarchy.models import Organization
from rest_framework import status
from rest_framework.test import APIClient

from audit_log.models import AuditLogEntry
from events.tests.factories import ApiKeyUserFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.models import User
from linkedevents.utils import get_fixed_lang_codes
from registrations.models import PriceGroup
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationPriceGroupFactory,
)
from registrations.tests.test_price_group_put import _NEW_DESCRIPTION_EN
from registrations.tests.utils import create_user_by_role

default_price_group_data = {
    "description": {
        "en": "English description",
    },
}

# === util methods ===


def patch_price_group(api_client: APIClient, price_group_pk: str | int, data: dict):
    url = reverse(
        "pricegroup-detail",
        kwargs={"pk": price_group_pk},
    )

    return api_client.patch(url, data, format="json")


def assert_patch_price_group(
    api_client: APIClient, price_group_pk: str | int, data: dict
):
    response = patch_price_group(api_client, price_group_pk, data)
    assert response.status_code == status.HTTP_200_OK

    return response


def assert_patch_price_group_and_check_values(
    api_client: APIClient,
    organization: Organization,
    price_group: PriceGroup,
    user: User,
):
    assert PriceGroup.objects.count() == 9

    assert price_group.publisher_id == organization.pk
    assert price_group.description != _NEW_DESCRIPTION_EN
    assert price_group.last_modified_by_id is None
    assert price_group.last_modified_time is not None
    last_modified_time = price_group.last_modified_time

    data = {
        "description": {
            "en": _NEW_DESCRIPTION_EN,
        },
        "is_free": True,
    }
    assert_patch_price_group(api_client, price_group.pk, data)

    assert PriceGroup.objects.count() == 9

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk
    assert price_group.description == _NEW_DESCRIPTION_EN
    assert price_group.last_modified_by_id == user.id
    assert price_group.last_modified_time > last_modified_time


def assert_patch_price_group_not_allowed(
    api_client: APIClient, organization: Organization, price_group: PriceGroup
):
    assert PriceGroup.objects.count() == 9

    assert price_group.publisher_id == organization.pk
    assert price_group.description != _NEW_DESCRIPTION_EN

    data = {
        "description": {
            "en": _NEW_DESCRIPTION_EN,
        },
        "is_free": True,
    }
    response = patch_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert PriceGroup.objects.count() == 9

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk
    assert price_group.description != _NEW_DESCRIPTION_EN


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
def test_superuser_can_patch_price_group_regardless_of_other_roles(
    api_client, organization, other_role
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role(other_role, organization)
    user.is_superuser = True
    user.save(update_fields=["is_superuser"])

    api_client.force_authenticate(user)

    assert_patch_price_group_and_check_values(
        api_client, organization, price_group, user
    )


@pytest.mark.django_db
def test_financial_admin_can_patch_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    assert_patch_price_group_and_check_values(
        api_client, organization, price_group, user
    )


@pytest.mark.django_db
def test_price_group_update_text_fields_are_sanitized(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    data = {
        "description": {
            "en": "<p>Test Price Group</p>",
        },
    }
    assert_patch_price_group(api_client, price_group.pk, data)

    price_group.refresh_from_db()
    assert price_group.description == "Test Price Group"


@pytest.mark.django_db
def test_can_patch_publisher_if_price_group_not_used(
    api_client, organization, organization2
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    data = {
        "publisher": organization2.pk,
    }
    response = patch_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_200_OK

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization2.pk


@pytest.mark.django_db
def test_cannot_patch_publisher_if_price_group_used(
    api_client, organization, organization2
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    RegistrationPriceGroupFactory(
        registration__event__publisher=organization,
        price_group=price_group,
        price=Decimal("10"),
    )

    data = {
        "publisher": organization2.pk,
    }
    response = patch_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()[0] == (
        "You may not change the publisher of a price group that has been used in registrations."
    )

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_patch_price_group(
    api_client, organization, user_role
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    assert_patch_price_group_not_allowed(api_client, organization, price_group)


@pytest.mark.django_db
def test_user_of_another_organization_cannot_patch_price_group(
    api_client, organization, organization2
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization2)
    api_client.force_authenticate(user)

    assert_patch_price_group_not_allowed(api_client, organization, price_group)


@pytest.mark.django_db
def test_anonymous_user_cannot_patch_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    response = patch_price_group(api_client, price_group.pk, default_price_group_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk
    assert price_group.description != _NEW_DESCRIPTION_EN


@pytest.mark.django_db
def test_apikey_user_with_financial_admin_rights_can_patch_price_group(
    api_client, organization, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    apikey_user = ApiKeyUserFactory(data_source=data_source)
    api_client.credentials(apikey=data_source.api_key)

    data_source.owner = organization
    data_source.user_editable_registration_price_groups = True
    data_source.save(update_fields=["owner", "user_editable_registration_price_groups"])

    assert_patch_price_group_and_check_values(
        api_client, organization, price_group, apikey_user
    )


@pytest.mark.django_db
def test_apikey_user_without_financial_admin_rights_cannot_patch_price_group(
    api_client, organization, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    data_source.owner = organization
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    assert_patch_price_group_not_allowed(api_client, organization, price_group)


@pytest.mark.django_db
def test_apikey_user_of_another_organization_cannot_patch_price_group(
    api_client, organization, organization2, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    data_source.owner = organization2
    data_source.user_editable_registration_price_groups = True
    data_source.save(update_fields=["owner", "user_editable_registration_price_groups"])

    api_client.credentials(apikey=data_source.api_key)

    assert_patch_price_group_not_allowed(api_client, organization, price_group)


@pytest.mark.django_db
def test_unknown_apikey_user_cannot_patch_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    api_client.credentials(apikey="bs")

    response = patch_price_group(api_client, price_group.pk, default_price_group_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk
    assert price_group.description != default_price_group_data["description"]


@pytest.mark.parametrize(
    "user_role, expected_status_code",
    [
        ("superuser", status.HTTP_400_BAD_REQUEST),
        ("financial_admin", status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_cannot_patch_default_price_group(
    api_client, organization, user_role, expected_status_code
):
    price_group = PriceGroup.objects.filter(publisher=None).first()

    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    response = patch_price_group(api_client, price_group.pk, default_price_group_data)
    assert response.status_code == expected_status_code


@pytest.mark.django_db
def test_price_group_id_is_audit_logged_on_patch(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("superuser", organization)
    api_client.force_authenticate(user)

    assert_patch_price_group(api_client, price_group.pk, default_price_group_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        price_group.pk
    ]


@pytest.mark.parametrize(
    "description,lang",
    [
        ("FI", "fi"),
        ("SV", "sv"),
        ("EN", "en"),
    ],
)
@pytest.mark.django_db
def test_can_patch_description_for_different_languages(
    api_client, organization, description, lang
):
    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    description_lang_key = f"description_{lang}"

    price_group = PriceGroupFactory(
        publisher=organization, **{description_lang_key: "Valid description"}
    )

    data = {"description": {lang: description}}

    assert getattr(price_group, description_lang_key) != description

    assert_patch_price_group(api_client, price_group.pk, data)

    price_group.refresh_from_db()
    assert getattr(price_group, description_lang_key) == description


@pytest.mark.parametrize("description", ["", None])
@pytest.mark.parametrize("lang", ["fi", "sv", "en"])
@pytest.mark.django_db
def test_cannot_patch_description_with_empty_value(
    api_client, organization, description, lang
):
    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    description_lang_key = f"description_{lang}"

    price_group = PriceGroupFactory(
        publisher=organization, **{description_lang_key: "Valid description"}
    )

    data = {"description": {lang: description}}

    assert getattr(price_group, description_lang_key) != description

    response = patch_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    price_group.refresh_from_db()
    assert getattr(price_group, description_lang_key) != description


@pytest.mark.parametrize(
    "description_lang_code", [lang_code for lang_code in get_fixed_lang_codes()]
)
@pytest.mark.django_db
def test_cannot_patch_signup_group_with_a_description_that_exceeds_max_length(
    api_client, organization, description_lang_code
):
    user = create_user_by_role("superuser", organization)
    api_client.force_authenticate(user)

    price_group = PriceGroupFactory(publisher=organization)

    data = {
        "description": {
            description_lang_code: "a" * 256,
        },
    }

    response = patch_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["description"][0]
        == "Description can be at most 255 characters long."
    )
