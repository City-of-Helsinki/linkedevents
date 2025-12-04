from decimal import Decimal

import pytest
from django_orghierarchy.models import Organization
from resilient_logger.models import ResilientLogEntry
from rest_framework import status
from rest_framework.test import APIClient

from events.tests.factories import ApiKeyUserFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.models import User
from linkedevents.utils import get_fixed_lang_codes
from registrations.models import PriceGroup
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationPriceGroupFactory,
)
from registrations.tests.utils import create_user_by_role

_NEW_DESCRIPTION_FI = "FI desc"
_NEW_DESCRIPTION_SV = "SV desc"
_NEW_DESCRIPTION_EN = "EN desc"
default_price_group_data = {
    "description": {
        "en": "English description",
    },
}


# === util methods ===


def update_price_group(api_client: APIClient, price_group_pk: str | int, data: dict):
    url = reverse(
        "pricegroup-detail",
        kwargs={"pk": price_group_pk},
    )

    return api_client.put(url, data, format="json")


def assert_update_price_group(
    api_client: APIClient, price_group_pk: str | int, data: dict
):
    response = update_price_group(api_client, price_group_pk, data)
    assert response.status_code == status.HTTP_200_OK

    return response


def assert_update_price_group_and_check_values(
    api_client: APIClient,
    organization: Organization,
    price_group: PriceGroup,
    user: User,
):
    assert (
        PriceGroup.objects.count() == 9
    )  # eight default price groups + one created in the test

    assert price_group.publisher_id == organization.pk
    assert price_group.description_fi != _NEW_DESCRIPTION_FI
    assert price_group.description_sv != _NEW_DESCRIPTION_SV
    assert price_group.description_en != _NEW_DESCRIPTION_EN
    assert price_group.is_free is False
    assert price_group.last_modified_by_id is None
    assert price_group.last_modified_time is not None
    last_modified_time = price_group.last_modified_time

    data = {
        "publisher": organization.pk,
        "description": {
            "fi": _NEW_DESCRIPTION_FI,
            "sv": _NEW_DESCRIPTION_SV,
            "en": _NEW_DESCRIPTION_EN,
        },
        "is_free": True,
    }
    response = assert_update_price_group(api_client, price_group.pk, data)
    assert response.data["description"]["fi"] == _NEW_DESCRIPTION_FI
    assert response.data["description"]["sv"] == _NEW_DESCRIPTION_SV
    assert response.data["description"]["en"] == _NEW_DESCRIPTION_EN

    assert PriceGroup.objects.count() == 9

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk
    assert price_group.description_fi == _NEW_DESCRIPTION_FI
    assert price_group.description_sv == _NEW_DESCRIPTION_SV
    assert price_group.description_en == _NEW_DESCRIPTION_EN
    assert price_group.is_free is True
    assert price_group.last_modified_by_id == user.id
    assert price_group.last_modified_time > last_modified_time


def assert_update_price_group_not_allowed(
    api_client: APIClient, organization: Organization, price_group: PriceGroup
):
    assert (
        PriceGroup.objects.count() == 9
    )  # eight default price groups + one created in the test

    assert price_group.publisher_id == organization.pk
    assert price_group.description_fi != _NEW_DESCRIPTION_FI
    assert price_group.description_sv != _NEW_DESCRIPTION_SV
    assert price_group.description_en != _NEW_DESCRIPTION_EN
    assert price_group.is_free is False

    data = {
        "publisher": organization.pk,
        "description": {
            "fi": _NEW_DESCRIPTION_FI,
            "sv": _NEW_DESCRIPTION_SV,
            "en": _NEW_DESCRIPTION_EN,
        },
        "is_free": True,
    }
    response = update_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert PriceGroup.objects.count() == 9

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk
    assert price_group.description_fi != _NEW_DESCRIPTION_FI
    assert price_group.description_sv != _NEW_DESCRIPTION_SV
    assert price_group.description_en != _NEW_DESCRIPTION_EN
    assert price_group.is_free is False


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
def test_superuser_can_update_price_group_regardless_of_other_roles(
    api_client, organization, other_role
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role(other_role, organization)
    user.is_superuser = True
    user.save(update_fields=["is_superuser"])

    api_client.force_authenticate(user)

    assert_update_price_group_and_check_values(
        api_client, organization, price_group, user
    )


@pytest.mark.django_db
def test_financial_admin_can_update_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    assert_update_price_group_and_check_values(
        api_client, organization, price_group, user
    )


@pytest.mark.django_db
def test_price_group_update_text_fields_are_sanitized(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    data = {
        "publisher": organization.pk,
        "description": {"en": "<p>Test Price Group</p>"},
    }
    assert_update_price_group(api_client, price_group.pk, data)

    price_group.refresh_from_db()
    assert price_group.description == "Test Price Group"


@pytest.mark.django_db
def test_can_change_publisher_if_price_group_not_used(
    api_client, organization, organization2
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization)
    api_client.force_authenticate(user)

    data = {
        "publisher": organization2.pk,
        "description": {"en": price_group.description},
    }
    response = update_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_200_OK

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization2.pk


@pytest.mark.django_db
def test_cannot_change_publisher_if_price_group_used(
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
        "description": {"en": price_group.description},
    }
    response = update_price_group(api_client, price_group.pk, data)
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
def test_not_allowed_user_roles_cannot_update_price_group(
    api_client, organization, user_role
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    assert_update_price_group_not_allowed(api_client, organization, price_group)


@pytest.mark.django_db
def test_user_of_another_organization_cannot_update_price_group(
    api_client, organization, organization2
):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("financial_admin", organization2)
    api_client.force_authenticate(user)

    assert_update_price_group_not_allowed(api_client, organization, price_group)


@pytest.mark.django_db
def test_anonymous_user_cannot_update_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    data = {
        "publisher": organization.pk,
        **default_price_group_data,
    }
    response = update_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk
    assert price_group.description != _NEW_DESCRIPTION_EN


@pytest.mark.django_db
def test_apikey_user_with_financial_admin_rights_can_update_price_group(
    api_client, organization, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    apikey_user = ApiKeyUserFactory(data_source=data_source)
    api_client.credentials(apikey=data_source.api_key)

    data_source.owner = organization
    data_source.user_editable_registration_price_groups = True
    data_source.save(update_fields=["owner", "user_editable_registration_price_groups"])

    assert_update_price_group_and_check_values(
        api_client, organization, price_group, apikey_user
    )


@pytest.mark.django_db
def test_apikey_user_without_financial_admin_rights_cannot_update_price_group(
    api_client, organization, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    data_source.owner = organization
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    assert_update_price_group_not_allowed(api_client, organization, price_group)


@pytest.mark.django_db
def test_apikey_user_of_another_organization_cannot_update_price_group(
    api_client, organization, organization2, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    data_source.owner = organization2
    data_source.user_editable_registration_price_groups = True
    data_source.save(update_fields=["owner", "user_editable_registration_price_groups"])

    api_client.credentials(apikey=data_source.api_key)

    assert_update_price_group_not_allowed(api_client, organization, price_group)


@pytest.mark.django_db
def test_unknown_apikey_user_cannot_update_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    api_client.credentials(apikey="bs")

    data = {
        "publisher": organization.pk,
        **default_price_group_data,
    }
    response = update_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    price_group.refresh_from_db()
    assert price_group.publisher_id == organization.pk
    assert price_group.description != data["description"]


@pytest.mark.parametrize(
    "user_role, expected_status_code",
    [
        ("superuser", status.HTTP_400_BAD_REQUEST),
        ("financial_admin", status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_cannot_update_default_price_group(
    api_client, organization, user_role, expected_status_code
):
    price_group = PriceGroup.objects.filter(publisher=None).first()

    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    data = {
        "publisher": organization.pk,
        **default_price_group_data,
    }
    response = update_price_group(api_client, price_group.pk, data)
    assert response.status_code == expected_status_code


@pytest.mark.django_db
def test_price_group_id_is_audit_logged_on_put(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    user = create_user_by_role("superuser", organization)
    api_client.force_authenticate(user)

    data = {
        "publisher": organization.pk,
        **default_price_group_data,
    }
    assert_update_price_group(api_client, price_group.pk, data)

    audit_log_entry = ResilientLogEntry.objects.first()
    assert audit_log_entry.context["target"]["object_ids"] == [price_group.pk]


@pytest.mark.parametrize(
    "description_lang_code", [lang_code for lang_code in get_fixed_lang_codes()]
)
@pytest.mark.django_db
def test_cannot_put_signup_group_with_a_description_that_exceeds_max_length(
    api_client, organization, description_lang_code
):
    user = create_user_by_role("superuser", organization)
    api_client.force_authenticate(user)

    price_group = PriceGroupFactory(publisher=organization)

    data = {
        "publisher": organization.pk,
        "description": {
            description_lang_code: "a" * 256,
        },
    }
    if description_lang_code not in ("fi", "sv", "en"):
        data["description"]["fi"] = "This is required"

    response = update_price_group(api_client, price_group.pk, data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["description"][0]
        == "Description can be at most 255 characters long."
    )
