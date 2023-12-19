from decimal import Decimal
from typing import Union

import pytest
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.test import APIClient

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import PriceGroup
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationPriceGroupFactory,
)

# === util methods ===


def delete_price_group(api_client: APIClient, price_group_pk: Union[str, int]):
    url = reverse(
        "pricegroup-detail",
        kwargs={"pk": price_group_pk},
    )

    return api_client.delete(url)


def assert_delete_price_group(api_client: APIClient, price_group_pk: Union[str, int]):
    assert PriceGroup.objects.count() == 9

    response = delete_price_group(api_client, price_group_pk)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert PriceGroup.objects.count() == 8

    return response


def assert_delete_price_group_not_allowed(
    api_client: APIClient, price_group_pk: Union[str, int]
):
    assert PriceGroup.objects.count() == 9

    response = delete_price_group(api_client, price_group_pk)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert PriceGroup.objects.count() == 9


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
def test_superuser_can_delete_price_group_regardless_of_other_roles(
    api_client, organization, other_role
):
    price_group = PriceGroupFactory(publisher=organization)

    user = UserFactory(is_superuser=True)

    other_role_mapping = {
        "admin": lambda usr: usr.admin_organizations.add(organization),
        "registration_admin": lambda usr: usr.registration_admin_organizations.add(
            organization
        ),
        "financial_admin": lambda usr: usr.financial_admin_organizations.add(
            organization
        ),
        "regular_user": lambda usr: usr.organization_memberships.add(organization),
    }
    other_role_mapping[other_role](user)

    api_client.force_authenticate(user)

    assert_delete_price_group(api_client, price_group.pk)


@pytest.mark.django_db
def test_financial_admin_can_delete_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    user = UserFactory()
    user.financial_admin_organizations.add(organization)
    api_client.force_authenticate(user)

    assert_delete_price_group(api_client, price_group.pk)


@pytest.mark.django_db
def test_cannot_delete_price_group_if_used_in_registrations(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    RegistrationPriceGroupFactory(
        registration__event__publisher=organization,
        price_group=price_group,
        price=Decimal("10"),
    )

    user = UserFactory()
    user.financial_admin_organizations.add(organization)
    api_client.force_authenticate(user)

    assert PriceGroup.objects.count() == 9

    with pytest.raises(ProtectedError):
        delete_price_group(api_client, price_group.pk)

    assert PriceGroup.objects.count() == 9


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_delete_price_group(
    api_client, organization, user_role
):
    price_group = PriceGroupFactory(publisher=organization)

    user = UserFactory()

    user_role_mapping = {
        "admin": lambda usr: usr.admin_organizations.add(organization),
        "registration_admin": lambda usr: usr.registration_admin_organizations.add(
            organization
        ),
        "regular_user": lambda usr: usr.organization_memberships.add(organization),
    }
    user_role_mapping[user_role](user)

    api_client.force_authenticate(user)

    assert_delete_price_group_not_allowed(api_client, price_group.pk)


@pytest.mark.django_db
def test_user_of_another_organization_cannot_delete_price_group(
    api_client, organization, organization2
):
    price_group = PriceGroupFactory(publisher=organization)

    user = UserFactory()
    user.financial_admin_organizations.add(organization2)
    api_client.force_authenticate(user)

    assert_delete_price_group_not_allowed(api_client, price_group.pk)


@pytest.mark.django_db
def test_anonymous_user_cannot_delete_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    assert PriceGroup.objects.count() == 9

    response = delete_price_group(api_client, price_group.pk)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert PriceGroup.objects.count() == 9


@pytest.mark.django_db
def test_apikey_user_with_financial_admin_rights_can_delete_price_group(
    api_client, organization, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    data_source.owner = organization
    data_source.user_editable_registration_price_groups = True
    data_source.save(update_fields=["owner", "user_editable_registration_price_groups"])

    api_client.credentials(apikey=data_source.api_key)

    assert_delete_price_group(api_client, price_group.pk)


@pytest.mark.django_db
def test_apikey_user_without_financial_admin_rights_cannot_delete_price_group(
    api_client, organization, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    data_source.owner = organization
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    assert_delete_price_group_not_allowed(api_client, price_group.pk)


@pytest.mark.django_db
def test_apikey_user_of_another_organization_cannot_delete_price_group(
    api_client, organization, organization2, data_source
):
    price_group = PriceGroupFactory(publisher=organization)

    data_source.owner = organization2
    data_source.user_editable_registration_price_groups = True
    data_source.save(update_fields=["owner", "user_editable_registration_price_groups"])

    api_client.credentials(apikey=data_source.api_key)

    assert_delete_price_group_not_allowed(api_client, price_group.pk)


@pytest.mark.django_db
def test_unknown_apikey_user_cannot_delete_price_group(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    api_client.credentials(apikey="bs")

    assert PriceGroup.objects.count() == 9

    response = delete_price_group(api_client, price_group.pk)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert PriceGroup.objects.count() == 9


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_cannot_delete_default_price_group(api_client, organization, user_role):
    price_group = PriceGroup.objects.filter(publisher=None).first()

    user = UserFactory(is_superuser=user_role == "superuser")
    if user_role == "financial_admin":
        user.financial_admin_organizations.add(organization)
    api_client.force_authenticate(user)

    assert PriceGroup.objects.count() == 8

    response = delete_price_group(api_client, price_group.pk)
    if user.is_superuser:
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()[0] == "You may not delete a default price group."
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN

    assert PriceGroup.objects.count() == 8


@pytest.mark.django_db
def test_price_group_id_is_audit_logged_on_delete(api_client, organization):
    price_group = PriceGroupFactory(publisher=organization)

    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    assert_delete_price_group(api_client, price_group.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        price_group.pk
    ]
