from decimal import Decimal
from typing import Union

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from events.tests.factories import OfferFactory
from events.tests.utils import versioned_reverse as reverse
from registrations.enums import VatPercentage
from registrations.models import PriceGroup, RegistrationPriceGroup
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    RegistrationWebStoreProductMappingFactory,
)
from registrations.tests.test_registration_post import email
from registrations.tests.test_registration_put import edited_email, edited_hel_email
from registrations.tests.utils import create_user_by_role

# === util methods ===


def patch_registration(
    api_client: APIClient,
    pk: Union[str, int],
    data: dict,
):
    url = reverse("registration-detail", kwargs={"pk": pk})

    response = api_client.patch(url, data, format="json")
    return response


def assert_patch_registration(
    api_client: APIClient,
    pk: Union[str, int],
    data: dict,
):
    response = patch_registration(api_client, pk, data)
    print(response.data)
    assert response.status_code == status.HTTP_200_OK

    return response


# === tests ===


@pytest.mark.parametrize(
    "info_url_fi,info_url_sv,info_url_en",
    [
        (None, None, None),
        (None, None, ""),
        (None, "", ""),
        ("", None, None),
        ("", "", None),
        ("", "", ""),
    ],
)
@pytest.mark.django_db
def test_signup_url_is_not_linked_to_event_offer_on_registration_patch(
    api_client, registration, info_url_fi, info_url_sv, info_url_en
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    offer = OfferFactory(
        event=registration.event,
        info_url_fi=info_url_fi,
        info_url_sv=info_url_sv,
        info_url_en=info_url_en,
    )

    registration_data = {"audience_max_age": 10}
    assert_patch_registration(api_client, registration.pk, registration_data)

    blank_values = (None, "")
    offer.refresh_from_db()
    assert offer.info_url_fi in blank_values
    assert offer.info_url_sv in blank_values
    assert offer.info_url_en in blank_values


@pytest.mark.django_db
def test_patch_registration_price_group(api_client, user, registration):
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(registration=registration)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()
    custom_price_group = PriceGroupFactory(publisher=registration.publisher)

    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group=default_price_group,
        price=Decimal("10"),
        vat_percentage=VatPercentage.VAT_24.value,
        price_without_vat=Decimal("8.06"),
        vat=Decimal("1.94"),
    )
    assert registration_price_group.price_group_id == default_price_group.pk
    assert registration_price_group.price == Decimal("10")
    assert registration_price_group.vat_percentage == VatPercentage.VAT_24.value
    assert registration_price_group.price_without_vat == Decimal("8.06")
    assert registration_price_group.vat == Decimal("1.94")

    registration_data = {
        "registration_price_groups": [
            {
                "id": registration_price_group.pk,
                "price_group": custom_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_10.value,
            },
        ],
    }
    assert_patch_registration(api_client, registration.pk, registration_data)

    registration_price_group.refresh_from_db()
    assert registration_price_group.price_group_id == custom_price_group.pk
    assert registration_price_group.price == Decimal("10")
    assert registration_price_group.vat_percentage == VatPercentage.VAT_10.value
    assert registration_price_group.price_without_vat == Decimal("9.09")
    assert registration_price_group.vat == Decimal("0.91")


@pytest.mark.django_db
def test_cannot_patch_registration_with_duplicate_price_groups(
    user, api_client, registration
):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group=default_price_group,
    )

    assert RegistrationPriceGroup.objects.count() == 1

    registration_data = {
        "registration_price_groups": [
            {
                "id": registration_price_group.pk,
                "price_group": default_price_group.pk,
                "price": Decimal("5"),
                "vat_percentage": VatPercentage.VAT_0.value,
            },
            {
                "price_group": default_price_group.pk,
                "price": Decimal("5"),
                "vat_percentage": VatPercentage.VAT_0.value,
            },
        ],
    }
    response = patch_registration(api_client, registration.pk, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"][1]["price_group"][0] == (
        f"Registration price group with price_group {default_price_group} already exists."
    )

    assert RegistrationPriceGroup.objects.count() == 1


@pytest.mark.django_db
def test_can_patch_substitute_user_access_with_helsinki_email(
    registration, user_api_client
):
    user_access = RegistrationUserAccessFactory(registration=registration, email=email)

    assert user_access.email != edited_hel_email
    assert user_access.is_substitute_user is False

    registration_data = {
        "registration_user_accesses": [
            {
                "id": user_access.pk,
                "email": edited_hel_email,
                "is_substitute_user": True,
            }
        ],
    }

    assert_patch_registration(user_api_client, registration.pk, registration_data)

    user_access.refresh_from_db()
    assert user_access.email == edited_hel_email
    assert user_access.is_substitute_user is True


@pytest.mark.django_db
def test_cannot_patch_substitute_user_access_without_helsinki_email(
    registration, user_api_client
):
    user_access = RegistrationUserAccessFactory(registration=registration, email=email)

    registration_data = {
        "registration_user_accesses": [
            {
                "id": user_access.pk,
                "email": edited_email,
                "is_substitute_user": True,
            }
        ],
    }

    response = patch_registration(user_api_client, registration.pk, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["registration_user_accesses"][0]["is_substitute_user"][0]
        == "The user's email domain is not one of the allowed domains for substitute users."
    )
