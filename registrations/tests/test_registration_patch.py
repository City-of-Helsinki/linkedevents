from decimal import Decimal
from typing import Union

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from events.tests.utils import versioned_reverse as reverse
from registrations.models import PriceGroup, RegistrationPriceGroup
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationPriceGroupFactory,
)

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
    assert response.status_code == status.HTTP_200_OK

    return response


# === tests ===


@pytest.mark.django_db
def test_patch_registration_price_group(api_client, user, registration):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()
    custom_price_group = PriceGroupFactory(publisher=registration.publisher)

    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group=default_price_group,
        price=Decimal("10"),
        vat_percentage=RegistrationPriceGroup.VatPercentage.VAT_24,
        price_without_vat=Decimal("8.06"),
        vat=Decimal("1.94"),
    )
    assert registration_price_group.price_group_id == default_price_group.pk
    assert registration_price_group.price == Decimal("10")
    assert (
        registration_price_group.vat_percentage
        == RegistrationPriceGroup.VatPercentage.VAT_24
    )
    assert registration_price_group.price_without_vat == Decimal("8.06")
    assert registration_price_group.vat == Decimal("1.94")

    registration_data = {
        "registration_price_groups": [
            {
                "id": registration_price_group.pk,
                "price_group": custom_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_10,
            },
        ],
    }
    assert_patch_registration(api_client, registration.pk, registration_data)

    registration_price_group.refresh_from_db()
    assert registration_price_group.price_group_id == custom_price_group.pk
    assert registration_price_group.price == Decimal("10")
    assert (
        registration_price_group.vat_percentage
        == RegistrationPriceGroup.VatPercentage.VAT_10
    )
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
                "vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_0,
            },
            {
                "price_group": default_price_group.pk,
                "price": Decimal("5"),
                "vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_0,
            },
        ],
    }
    response = patch_registration(api_client, registration.pk, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"][1]["price_group"][0] == (
        f"Registration price group with price_group {default_price_group} already exists."
    )

    assert RegistrationPriceGroup.objects.count() == 1
