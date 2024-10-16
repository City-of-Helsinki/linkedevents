from decimal import Decimal
from typing import Union

import pytest
import requests_mock
from django.conf import settings as django_settings
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from events.tests.factories import OfferFactory
from events.tests.utils import versioned_reverse as reverse
from registrations.enums import VatPercentage
from registrations.models import (
    VAT_CODE_MAPPING,
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationWebStoreProductMapping,
)
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    RegistrationWebStoreAccountFactory,
    RegistrationWebStoreMerchantFactory,
    RegistrationWebStoreProductMappingFactory,
    WebStoreAccountFactory,
    WebStoreMerchantFactory,
)
from registrations.tests.test_registration_post import email
from registrations.tests.test_registration_put import edited_email, edited_hel_email
from registrations.tests.utils import (
    create_user_by_role,
    get_registration_merchant_and_account_data,
)
from web_store.tests.product.test_web_store_product_api_client import (
    DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
    DEFAULT_GET_PRODUCT_MAPPING_DATA,
    DEFAULT_PRODUCT_ID,
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
        RegistrationWebStoreProductMappingFactory(
            registration=registration,
            vat_code=VAT_CODE_MAPPING[VatPercentage.VAT_10.value],
        )

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()
    custom_price_group = PriceGroupFactory(publisher=registration.publisher)

    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group=default_price_group,
        price=Decimal("10"),
        vat_percentage=VatPercentage.VAT_25_5.value,
        price_without_vat=Decimal("7.97"),
        vat=Decimal("2.03"),
    )
    assert registration_price_group.price_group_id == default_price_group.pk
    assert registration_price_group.price == Decimal("10")
    assert registration_price_group.vat_percentage == VatPercentage.VAT_25_5.value
    assert registration_price_group.price_without_vat == Decimal("7.97")
    assert registration_price_group.vat == Decimal("2.03")

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


@pytest.mark.django_db
def test_patch_registration_product_mapping_merchant_changed(
    user_api_client, event, registration
):
    RegistrationPriceGroupFactory(registration=registration)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )
        new_merchant = WebStoreMerchantFactory(
            organization=event.publisher, merchant_id="1234"
        )

    registration_account = RegistrationWebStoreAccountFactory(registration=registration)
    product_mapping = RegistrationWebStoreProductMappingFactory(
        registration=registration, external_product_id="4321"
    )

    registration_data = {
        **get_registration_merchant_and_account_data(
            new_merchant, registration_account.account
        ),
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 1

    assert registration_merchant.merchant_id != new_merchant.pk
    assert registration_merchant.external_merchant_id != new_merchant.merchant_id

    assert product_mapping.external_product_id != DEFAULT_PRODUCT_ID

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
        )

        assert_patch_registration(user_api_client, registration.pk, registration_data)

        assert req_mock.call_count == 2

    assert RegistrationWebStoreProductMapping.objects.count() == 1

    registration_merchant.refresh_from_db()
    assert registration_merchant.merchant_id == new_merchant.pk
    assert registration_merchant.external_merchant_id == new_merchant.merchant_id

    product_mapping.refresh_from_db()
    assert product_mapping.external_product_id == DEFAULT_PRODUCT_ID


@pytest.mark.django_db
def test_patch_registration_product_mapping_account_changed(
    user_api_client, event, registration
):
    RegistrationPriceGroupFactory(registration=registration)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )

    registration_account = RegistrationWebStoreAccountFactory(registration=registration)
    new_account = WebStoreAccountFactory(organization=event.publisher)

    product_mapping = RegistrationWebStoreProductMappingFactory(
        registration=registration, external_product_id="4321"
    )

    registration_data = {
        **get_registration_merchant_and_account_data(
            registration_merchant.merchant, new_account
        ),
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 1

    assert registration_account.account_id != new_account.pk

    assert product_mapping.external_product_id != DEFAULT_PRODUCT_ID

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
        )

        assert_patch_registration(user_api_client, registration.pk, registration_data)

        assert req_mock.call_count == 2

    assert RegistrationWebStoreProductMapping.objects.count() == 1

    registration_account.refresh_from_db()
    assert registration_account.account_id == new_account.pk

    product_mapping.refresh_from_db()
    assert product_mapping.external_product_id == DEFAULT_PRODUCT_ID


@pytest.mark.django_db
def test_patch_registration_with_product_mapping_merchant_missing(
    user_api_client, event, registration
):
    WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        "registration_merchant": {},
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = patch_registration(user_api_client, registration.pk, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_merchant"][0] == (
        "This field is required when registration has customer groups."
    )

    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_patch_registration_with_product_mapping_account_missing(
    user_api_client, event, registration
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        "registration_account": {},
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = patch_registration(user_api_client, registration.pk, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_account"][0] == (
        "This field is required when registration has customer groups."
    )

    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_cannot_patch_product_mapping_with_price_groups_missing(
    user_api_client, event, registration
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    registration_data = {
        "registration_price_groups": [],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    assert Registration.objects.count() == 1
    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = patch_registration(user_api_client, registration.pk, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"][0] == (
        "This field is required when registration has a merchant or account."
    )

    assert Registration.objects.count() == 1
    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.parametrize(
    "maximum_attendee_capacity, expected_maximum_attendee_capacity, expected_status_code",
    [
        ("", None, status.HTTP_400_BAD_REQUEST),
        (None, None, status.HTTP_400_BAD_REQUEST),
        (0, 0, status.HTTP_200_OK),
        (1, 1, status.HTTP_200_OK),
        (1000000, 1000000, status.HTTP_200_OK),
    ],
)
@pytest.mark.django_db
def test_patch_registration_maximum_attendee_capacity(
    api_client,
    maximum_attendee_capacity,
    expected_maximum_attendee_capacity,
    expected_status_code,
):
    registration = RegistrationFactory(maximum_attendee_capacity=None)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration_data = {
        "maximum_attendee_capacity": maximum_attendee_capacity,
    }

    response = patch_registration(api_client, registration.pk, registration_data)
    assert response.status_code == expected_status_code

    registration.refresh_from_db()
    assert registration.maximum_attendee_capacity == expected_maximum_attendee_capacity


@pytest.mark.parametrize(
    "minimum_attendee_capacity, expected_minimum_attendee_capacity",
    [
        (None, None),
        (0, 0),
        (1, 1),
        (1000000, 1000000),
    ],
)
@pytest.mark.django_db
def test_patch_registration_minimum_attendee_capacity(
    api_client, minimum_attendee_capacity, expected_minimum_attendee_capacity
):
    registration = RegistrationFactory(minimum_attendee_capacity=None)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration_data = {
        "minimum_attendee_capacity": minimum_attendee_capacity,
    }

    assert_patch_registration(api_client, registration.pk, registration_data)

    registration.refresh_from_db()
    assert registration.minimum_attendee_capacity == expected_minimum_attendee_capacity
