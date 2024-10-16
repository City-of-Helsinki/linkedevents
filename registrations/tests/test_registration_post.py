from decimal import Decimal

import pytest
import requests_mock
from django.conf import settings as django_settings
from django.test import override_settings
from django.utils import translation
from requests import RequestException
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event
from events.tests.factories import OfferFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.enums import VatPercentage
from registrations.models import (
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
    RegistrationWebStoreAccount,
    RegistrationWebStoreMerchant,
    RegistrationWebStoreProductMapping,
)
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationUserAccessFactory,
    WebStoreAccountFactory,
    WebStoreMerchantFactory,
)
from registrations.tests.utils import (
    assert_invitation_email_is_sent,
    create_user_by_role,
    get_event_url,
    get_minimal_required_registration_data,
    get_registration_account_data,
    get_registration_merchant_and_account_data,
    get_registration_merchant_data,
)
from registrations.utils import get_signup_create_url
from web_store.tests.product.test_web_store_product_api_client import (
    DEFAULT_GET_PRODUCT_MAPPING_DATA,
    DEFAULT_PRODUCT_ID,
)

email = "user@email.com"
hel_email = "user@hel.fi"
event_name = "Foo"

# === util methods ===


def create_registration(api_client, registration_data, data_source=None):
    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    create_url = reverse("registration-list")
    response = api_client.post(create_url, registration_data, format="json")
    return response


def assert_create_registration(api_client, registration_data, data_source=None):
    response = create_registration(api_client, registration_data, data_source)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["event"] == registration_data["event"]

    return response


# === tests ===


@pytest.mark.django_db
def test_create_registration(user, api_client, event):
    api_client.force_authenticate(user)

    registration_data = get_minimal_required_registration_data(event.id)
    assert_create_registration(api_client, registration_data)


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
def test_signup_url_is_linked_to_event_offer_without_info_url(
    user_api_client, event, info_url_fi, info_url_sv, info_url_en
):
    offer = OfferFactory(
        event=event,
        info_url_fi=info_url_fi,
        info_url_sv=info_url_sv,
        info_url_en=info_url_en,
    )

    assert Registration.objects.count() == 0

    registration_data = get_minimal_required_registration_data(event.id)
    assert_create_registration(user_api_client, registration_data)

    assert Registration.objects.count() == 1
    registration = Registration.objects.first()

    offer.refresh_from_db()
    assert offer.info_url_fi == get_signup_create_url(registration, "fi")
    assert offer.info_url_sv == get_signup_create_url(registration, "sv")
    assert offer.info_url_en == get_signup_create_url(registration, "en")


@pytest.mark.parametrize(
    "info_url_field,info_url_value,blank_value",
    [
        ("info_url_fi", "https://test.com", None),
        ("info_url_sv", "https://test.com", None),
        ("info_url_en", "https://test.com", None),
        ("info_url_fi", "https://test.com", ""),
        ("info_url_sv", "https://test.com", ""),
        ("info_url_en", "https://test.com", ""),
    ],
)
@pytest.mark.django_db
def test_signup_url_is_not_linked_to_event_offer_with_info_url(
    user_api_client, event, info_url_field, info_url_value, blank_value
):
    fields = ("info_url_fi", "info_url_sv", "info_url_en")

    offer_kwargs = {info_url_field: info_url_value}
    for field in fields:
        if field != info_url_field:
            offer_kwargs[field] = blank_value

    offer = OfferFactory(event=event, **offer_kwargs)
    assert getattr(offer, info_url_field) == info_url_value

    registration_data = get_minimal_required_registration_data(event.id)
    assert_create_registration(user_api_client, registration_data)

    offer.refresh_from_db()
    assert getattr(offer, info_url_field) == info_url_value

    blank_values = (blank_value,)
    for field in fields:
        if field != info_url_field:
            assert getattr(offer, field) in blank_values


@pytest.mark.django_db
def test_superuser_can_create_registration(api_client, event):
    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "maximum_attendee_capacity": 10,
    }
    assert_create_registration(api_client, registration_data)


@pytest.mark.django_db
def test_only_one_registration_per_event_is_allowed(
    user, api_client, event, registration
):
    api_client.force_authenticate(user)
    registration_data = get_minimal_required_registration_data(event.id)

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cannot_create_registration_with_event_in_invalid_format(
    api_client, organization, user
):
    api_client.force_authenticate(user)
    registration_data = {
        "event": "invalid-format",
        "maximum_attendee_capacity": 1000000,
    }

    response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["event"][0] == "Incorrect JSON. Expected JSON, received str."


@pytest.mark.django_db
def test_cannot_create_registration_with_nonexistent_event(
    api_client, organization, user
):
    api_client.force_authenticate(user)
    registration_data = {
        "event": {"@id": "nonexistent-id"},
        "maximum_attendee_capacity": 1000000,
    }

    response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_maximum_group_size_cannot_be_less_than_one(user, api_client, event):
    api_client.force_authenticate(user)
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "maximum_group_size": 0,
    }

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["maximum_group_size"][0].code == "min_value"


@pytest.mark.django_db
def test_unauthenticated_user_cannot_create_registration(api_client, event):
    api_client.force_authenticate(None)

    registration_data = get_minimal_required_registration_data(event.id)
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_role", ["financial_admin", "regular_user"])
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_create_registration(
    api_client, event, user_role
):
    user = create_user_by_role(user_role, event.publisher)
    api_client.force_authenticate(user)

    registration_data = get_minimal_required_registration_data(event.id)

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_user_from_other_organization_cannot_create_registration(
    api_client, event, user2
):
    api_client.force_authenticate(user2)

    registration_data = get_minimal_required_registration_data(event.id)

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_can_create_registration_with_datasource_permission_missing(
    api_client, event, other_data_source, user
):
    event.data_source = other_data_source
    event.save()
    api_client.force_authenticate(user)

    registration_data = get_minimal_required_registration_data(event.id)

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_api_key_with_organization_can_create_registration(
    api_client, data_source, event, organization
):
    data_source.owner = organization
    data_source.save()

    registration_data = get_minimal_required_registration_data(event.id)
    assert_create_registration(api_client, registration_data, data_source)


@pytest.mark.django_db
def test_api_key_with_wrong_data_source_cannot_create_registration(
    api_client, data_source, event, organization, other_data_source
):
    other_data_source.owner = organization
    other_data_source.save()

    registration_data = get_minimal_required_registration_data(event.id)
    response = create_registration(api_client, registration_data, other_data_source)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("api_key", ["", "unknown"])
@pytest.mark.django_db
def test_invalid_api_key_cannot_create_registration(api_client, event, api_key):
    api_client.credentials(apikey=api_key)

    registration_data = get_minimal_required_registration_data(event.id)
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.parametrize("user_role", ["admin", "registration_admin"])
@pytest.mark.django_db
def test_admin_or_registration_admin_can_create_registration_regardless_of_user_editable_resources(
    api_client, data_source, event, organization, user_editable_resources, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    registration_data = get_minimal_required_registration_data(event.id)
    assert_create_registration(api_client, registration_data)


@pytest.mark.django_db
def test_user_editable_resources_can_create_registration(
    api_client, data_source, event, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user=user)

    registration_data = get_minimal_required_registration_data(event.id)
    assert_create_registration(api_client, registration_data, data_source)


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_send_email_to_registration_user_access(
    event, user_api_client, is_substitute_user
):
    user_email = hel_email if is_substitute_user else email

    with translation.override("fi"):
        event.type_id = Event.TypeId.GENERAL
        event.name = event_name
        event.save()

        registration_data = {
            **get_minimal_required_registration_data(event.id),
            "registration_user_accesses": [
                {"email": user_email, "is_substitute_user": is_substitute_user}
            ],
        }
        assert_create_registration(user_api_client, registration_data)

        #  assert that the email was sent
        registration_user_access = RegistrationUserAccess.objects.first()
        assert_invitation_email_is_sent(
            user_email, event_name, registration_user_access
        )


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_cannot_create_registration_user_accesses_with_duplicate_emails(
    event, user_api_client, is_substitute_user
):
    user_email = hel_email if is_substitute_user else email

    with translation.override("fi"):
        event.type_id = Event.TypeId.GENERAL
        event.name = event_name
        event.save()

        registration_data = {
            **get_minimal_required_registration_data(event.id),
            "registration_user_accesses": [
                {
                    "email": user_email,
                    "is_substitute_user": is_substitute_user,
                },
                {
                    "email": user_email,
                    "is_substitute_user": is_substitute_user,
                },
            ],
        }
        response = create_registration(user_api_client, registration_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["registration_user_accesses"][1]["email"][0].code == "unique"
        )


@pytest.mark.django_db
def test_cannot_create_substitute_user_without_helsinki_email(event, user_api_client):
    with translation.override("fi"):
        event.type_id = Event.TypeId.GENERAL
        event.name = event_name
        event.save()

        registration_data = {
            **get_minimal_required_registration_data(event.id),
            "registration_user_accesses": [
                {
                    "email": email,
                    "is_substitute_user": True,
                },
            ],
        }
        response = create_registration(user_api_client, registration_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["registration_user_accesses"][0]["is_substitute_user"][0]
            == "The user's email domain is not one of the allowed domains for substitute users."
        )


@pytest.mark.django_db
def test_create_registration_with_another_registrations_user_accesses(
    event, user_api_client
):
    another_registrations_user_access = RegistrationUserAccessFactory(
        email="test@test.com",
    )

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_user_accesses": [
            {
                "id": another_registrations_user_access.pk,
                "email": another_registrations_user_access.email,
            },
        ],
    }

    assert Registration.objects.count() == 1
    assert RegistrationUserAccess.objects.count() == 1

    response = create_registration(user_api_client, registration_data)
    assert response.status_code == status.HTTP_201_CREATED

    assert Registration.objects.count() == 2
    assert RegistrationUserAccess.objects.count() == 2

    assert (
        RegistrationUserAccess.objects.filter(
            registration=Registration.objects.first(),
            email=another_registrations_user_access.email,
        )
        .first()
        .pk
        == another_registrations_user_access.pk
    )
    assert (
        RegistrationUserAccess.objects.filter(
            registration=Registration.objects.last(),
            email=another_registrations_user_access.email,
        )
        .first()
        .pk
        != another_registrations_user_access.pk
    )


@pytest.mark.django_db
def test_registration_text_fields_are_sanitized(event, user_api_client):
    allowed_confirmation_message = "Confirmation message: <p>Allowed tag</p>"
    cleaned_confirmation_message = "Confirmation message: Not allowed tag"
    allowed_instructions = "Instructions: <p>Allowed tag</p>"
    cleaned_instructions = "Instructions: Not allowed tag"

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "confirmation_message": {
            "fi": allowed_confirmation_message,
            "sv": "Confirmation message: <h6>Not allowed tag</h6>",
        },
        "instructions": {
            "fi": allowed_instructions,
            "sv": "Instructions: <h6>Not allowed tag</h6>",
        },
    }

    response = assert_create_registration(user_api_client, registration_data)
    assert response.data["confirmation_message"]["fi"] == allowed_confirmation_message
    assert response.data["confirmation_message"]["sv"] == cleaned_confirmation_message
    assert response.data["instructions"]["fi"] == allowed_instructions
    assert response.data["instructions"]["sv"] == cleaned_instructions


@pytest.mark.django_db
def test_registration_id_is_audit_logged_on_post(user_api_client, event):
    registration_data = get_minimal_required_registration_data(event.id)
    response = assert_create_registration(user_api_client, registration_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]


@pytest.mark.django_db
def test_create_registration_with_price_groups_and_product_mapping(
    user, api_client, event
):
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    assert RegistrationPriceGroup.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0
    assert RegistrationWebStoreMerchant.objects.count() == 0
    assert RegistrationWebStoreAccount.objects.count() == 0

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
            {
                "price_group": custom_price_group.pk,
                "price": Decimal("15.55"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        response = assert_create_registration(api_client, registration_data)

        assert req_mock.call_count == 2

    assert len(response.data["registration_price_groups"]) == 2

    assert RegistrationPriceGroup.objects.count() == 2
    assert (
        RegistrationPriceGroup.objects.filter(
            price_group=default_price_group.pk,
            price=registration_data["registration_price_groups"][0]["price"],
            vat_percentage=registration_data["registration_price_groups"][0][
                "vat_percentage"
            ],
            price_without_vat=Decimal("7.97"),
            vat=Decimal("2.03"),
        ).count()
        == 1
    )
    assert (
        RegistrationPriceGroup.objects.filter(
            price_group=custom_price_group.pk,
            price=registration_data["registration_price_groups"][1]["price"],
            vat_percentage=registration_data["registration_price_groups"][1][
                "vat_percentage"
            ],
            price_without_vat=Decimal("12.39"),
            vat=Decimal("3.16"),
        ).count()
        == 1
    )

    assert RegistrationWebStoreProductMapping.objects.count() == 1
    assert RegistrationWebStoreMerchant.objects.count() == 1
    assert RegistrationWebStoreAccount.objects.count() == 1

    registration = Registration.objects.first()
    assert (
        RegistrationWebStoreProductMapping.objects.filter(
            registration=registration
        ).count()
        == 1
    )
    assert (
        RegistrationWebStoreMerchant.objects.filter(
            registration=registration,
            merchant=merchant,
            external_merchant_id=merchant.merchant_id,
        ).count()
        == 1
    )
    assert (
        RegistrationWebStoreAccount.objects.filter(
            registration=registration, **registration_data["registration_account"]
        ).count()
        == 1
    )


@pytest.mark.parametrize(
    "price,vat_percentage",
    [
        (Decimal("10"), VatPercentage.VAT_25_5.value),
        (Decimal("10"), VatPercentage.VAT_0.value),
        (None, VatPercentage.VAT_25_5.value),
    ],
)
@pytest.mark.django_db
def test_create_registration_with_a_free_price_group_and_product_mapping(
    user, api_client, event, price, vat_percentage
):
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=True
    ).first()

    assert RegistrationPriceGroup.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0
    assert RegistrationWebStoreMerchant.objects.count() == 0
    assert RegistrationWebStoreAccount.objects.count() == 0

    price_group_data = {
        "price_group": default_price_group.pk,
        "vat_percentage": vat_percentage,
    }
    if price is not None:
        price_group_data["price"] = price

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [price_group_data],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        response = assert_create_registration(api_client, registration_data)

    assert len(response.data["registration_price_groups"]) == 1

    assert RegistrationPriceGroup.objects.count() == 1

    registration_price_group = RegistrationPriceGroup.objects.first()
    assert registration_price_group.price == Decimal("0")
    assert registration_price_group.vat_percentage == vat_percentage
    assert registration_price_group.price_without_vat == Decimal("0")
    assert registration_price_group.vat == Decimal("0")

    assert RegistrationWebStoreProductMapping.objects.count() == 1
    assert RegistrationWebStoreMerchant.objects.count() == 1
    assert RegistrationWebStoreAccount.objects.count() == 1


@pytest.mark.django_db
def test_cannot_create_registration_price_groups_with_different_vat_percentages(
    user, api_client, event
):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    assert RegistrationPriceGroup.objects.count() == 0

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
            {
                "price_group": custom_price_group.pk,
                "price": Decimal("15.55"),
                "vat_percentage": VatPercentage.VAT_10.value,
            },
        ],
    }
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"]["price_group"][0] == (
        "All registration price groups must have the same VAT percentage."
    )

    assert RegistrationPriceGroup.objects.count() == 0


@pytest.mark.parametrize(
    "price,vat_percentage",
    [
        (-10, VatPercentage.VAT_25_5.value),
        (Decimal("-10"), VatPercentage.VAT_25_5.value),
        (Decimal("-10"), VatPercentage.VAT_0.value),
        (Decimal("10.123"), VatPercentage.VAT_25_5.value),
        (Decimal("10.1234"), VatPercentage.VAT_25_5.value),
        (None, VatPercentage.VAT_25_5.value),
    ],
)
@pytest.mark.django_db
def test_cannot_create_registration_with_wrong_or_missing_price_group_price(
    user, api_client, event, price, vat_percentage
):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    assert RegistrationPriceGroup.objects.count() == 0

    price_group_data = {
        "price_group": default_price_group.pk,
        "vat_percentage": vat_percentage,
    }
    if price is not None:
        price_group_data["price"] = price

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [price_group_data],
    }
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert RegistrationPriceGroup.objects.count() == 0


@pytest.mark.parametrize(
    "vat_percentage",
    [
        1,
        12,
        100,
        Decimal("1"),
        Decimal("12"),
        Decimal("100"),
        Decimal("24.1"),
        "",
        None,
    ],
)
@pytest.mark.django_db
def test_cannot_create_registration_with_wrong_or_missing_price_group_vat_percentage(
    user, api_client, event, vat_percentage
):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    assert RegistrationPriceGroup.objects.count() == 0

    price_group_data = {
        "price_group": default_price_group.pk,
        "price": Decimal("10"),
    }
    if vat_percentage is not None:
        price_group_data["vat_percentage"] = vat_percentage

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [price_group_data],
    }
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert RegistrationPriceGroup.objects.count() == 0


@pytest.mark.django_db
def test_cannot_create_registration_with_duplicate_price_groups(
    user, api_client, event
):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    assert RegistrationPriceGroup.objects.count() == 0

    price_group_data = {
        "price_group": default_price_group.pk,
        "price": Decimal("10"),
        "vat_percentage": VatPercentage.VAT_25_5.value,
    }
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [price_group_data, price_group_data],
    }
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"][1]["price_group"][0] == (
        f"Registration price group with price_group {default_price_group} already exists."
    )

    assert RegistrationPriceGroup.objects.count() == 0


@pytest.mark.parametrize(
    "account_kwargs",
    [
        {
            "internal_order": "1234567890",
            "profit_center": "1234567",
            "project": "1234567890654321",
            "operation_area": "654321",
        },
        {
            "internal_order": "1234567890",
            "profit_center": "1234567",
            "project": "1234567890654321",
        },
        {
            "internal_order": "1234567890",
            "profit_center": "1234567",
        },
        {
            "internal_order": "1234567890",
        },
        {},
    ],
)
@pytest.mark.django_db
def test_create_registration_with_optional_product_mapping_accounting_fields(
    user_api_client, event, account_kwargs
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_merchant_data(merchant),
        **get_registration_account_data(account, account_kwargs),
    }

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0
    assert RegistrationWebStoreAccount.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        assert_create_registration(user_api_client, registration_data)

        assert req_mock.call_count == 2

    assert Registration.objects.count() == 1
    assert RegistrationWebStoreProductMapping.objects.count() == 1

    registration = Registration.objects.first()
    assert (
        RegistrationWebStoreProductMapping.objects.filter(
            registration=registration,
            external_product_id=DEFAULT_PRODUCT_ID,
        ).count()
        == 1
    )
    assert (
        RegistrationWebStoreAccount.objects.filter(
            registration=registration, **registration_data["registration_account"]
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_create_registration_with_product_mapping_merchant_missing(
    user_api_client, event
):
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_account_data(account),
    }

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = create_registration(user_api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_merchant"][0] == (
        "This field is required when registration has customer groups."
    )

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_create_registration_with_product_mapping_account_missing(
    user_api_client, event
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_merchant_data(merchant),
    }

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = create_registration(user_api_client, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_account"][0] == (
        "This field is required when registration has customer groups."
    )

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_cannot_create_product_mapping_with_price_groups_missing(
    user_api_client, event
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        **get_registration_merchant_and_account_data(merchant, account),
    }

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = create_registration(user_api_client, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"][0] == (
        "This field is required when registration has a merchant or account."
    )

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_create_registration_with_product_mapping_api_exception(user_api_client, event):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"

        req_mock.post(
            base_url,
            exc=RequestException,
        )
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        response = create_registration(user_api_client, registration_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert req_mock.call_count == 1

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_create_registration_with_product_accounting_api_exception(
    user_api_client, event
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"

        req_mock.post(
            base_url,
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            exc=RequestException,
        )

        response = create_registration(user_api_client, registration_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert req_mock.call_count == 2

    assert Registration.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.parametrize(
    "maximum_attendee_capacity, expected_maximum_attendee_capacity, expected_status_code",
    [
        ("", None, status.HTTP_400_BAD_REQUEST),
        (None, None, status.HTTP_400_BAD_REQUEST),
        (0, 0, status.HTTP_201_CREATED),
        (1, 1, status.HTTP_201_CREATED),
        (1000000, 1000000, status.HTTP_201_CREATED),
    ],
)
@pytest.mark.django_db
def test_create_registration_maximum_attendee_capacity(
    api_client,
    event,
    django_capture_on_commit_callbacks,
    maximum_attendee_capacity,
    expected_maximum_attendee_capacity,
    expected_status_code,
):
    user = create_user_by_role("registration_admin", event.publisher)
    api_client.force_authenticate(user)

    registration_data = {
        "event": {"@id": get_event_url(event.pk)},
        "maximum_attendee_capacity": maximum_attendee_capacity,
    }

    assert Registration.objects.count() == 0

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = create_registration(api_client, registration_data)
        assert response.status_code == expected_status_code

    if expected_status_code == status.HTTP_201_CREATED:
        assert Registration.objects.count() == 1
        assert len(callbacks) == 1

        registration = Registration.objects.first()
        assert (
            registration.maximum_attendee_capacity == expected_maximum_attendee_capacity
        )
        assert (
            registration.remaining_attendee_capacity
            == expected_maximum_attendee_capacity
        )
    else:
        assert Registration.objects.count() == 0
        assert len(callbacks) == 0


@pytest.mark.parametrize(
    "waiting_list_capacity, expected_waiting_list_capacity, expected_status_code",
    [
        ("", None, status.HTTP_400_BAD_REQUEST),
        (None, None, status.HTTP_201_CREATED),
        (0, 0, status.HTTP_201_CREATED),
        (1, 1, status.HTTP_201_CREATED),
        (1000000, 1000000, status.HTTP_201_CREATED),
    ],
)
@pytest.mark.django_db
def test_create_registration_waiting_list_capacity(
    api_client,
    event,
    django_capture_on_commit_callbacks,
    waiting_list_capacity,
    expected_waiting_list_capacity,
    expected_status_code,
):
    user = create_user_by_role("registration_admin", event.publisher)
    api_client.force_authenticate(user)

    registration_data = {
        "event": {"@id": get_event_url(event.pk)},
        "maximum_attendee_capacity": 1000001,
        "waiting_list_capacity": waiting_list_capacity,
    }

    assert Registration.objects.count() == 0

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = create_registration(api_client, registration_data)
        assert response.status_code == expected_status_code

    if expected_status_code == status.HTTP_201_CREATED:
        assert Registration.objects.count() == 1
        assert len(callbacks) == 1

        registration = Registration.objects.first()
        assert registration.waiting_list_capacity == expected_waiting_list_capacity
        assert (
            registration.remaining_waiting_list_capacity
            == expected_waiting_list_capacity
        )
    else:
        assert Registration.objects.count() == 0
        assert len(callbacks) == 0


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
def test_create_registration_minimum_attendee_capacity(
    api_client,
    event,
    django_capture_on_commit_callbacks,
    minimum_attendee_capacity,
    expected_minimum_attendee_capacity,
):
    user = create_user_by_role("registration_admin", event.publisher)
    api_client.force_authenticate(user)

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "minimum_attendee_capacity": minimum_attendee_capacity,
    }

    assert Registration.objects.count() == 0

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        assert_create_registration(api_client, registration_data)
    assert len(callbacks) == 1

    assert Registration.objects.count() == 1
    registration = Registration.objects.first()
    assert registration.minimum_attendee_capacity == expected_minimum_attendee_capacity


@pytest.mark.parametrize(
    "vat_percentage, expected_price_without_vat, expected_vat_amount",
    [
        (
            VatPercentage.VAT_0.value,
            Decimal("10"),
            Decimal("0"),
        ),
        (
            VatPercentage.VAT_10.value,
            Decimal("9.09"),
            Decimal("0.91"),
        ),
        (
            VatPercentage.VAT_14.value,
            Decimal("8.77"),
            Decimal("1.23"),
        ),
        (
            VatPercentage.VAT_25_5.value,
            Decimal("7.97"),
            Decimal("2.03"),
        ),
    ],
)
@pytest.mark.django_db
def test_create_registration_and_price_group_with_different_vat_percentages(
    user,
    api_client,
    event,
    vat_percentage,
    expected_price_without_vat,
    expected_vat_amount,
):
    user = create_user_by_role("registration_admin", event.publisher)
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    assert Registration.objects.count() == 0
    assert RegistrationPriceGroup.objects.count() == 0

    price_with_vat = Decimal("10")
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        **get_registration_merchant_and_account_data(merchant, account),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": price_with_vat,
                "vat_percentage": vat_percentage,
            },
        ],
    }

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"

        req_mock.post(
            base_url,
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        assert_create_registration(api_client, registration_data)

    assert Registration.objects.count() == 1
    assert RegistrationPriceGroup.objects.count() == 1

    registration_price_group = RegistrationPriceGroup.objects.first()
    assert registration_price_group.vat_percentage == vat_percentage
    assert registration_price_group.price == price_with_vat
    assert registration_price_group.price_without_vat == expected_price_without_vat
    assert registration_price_group.vat == expected_vat_amount
