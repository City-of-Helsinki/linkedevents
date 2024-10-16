from decimal import Decimal

import pytest
import requests_mock
from django.conf import settings
from django.conf import settings as django_settings
from django.core import mail
from django.test import override_settings
from django.utils import translation
from requests import RequestException
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event
from events.tests.factories import OfferFactory
from events.tests.utils import versioned_reverse as reverse
from registrations.enums import VatPercentage
from registrations.models import (
    VAT_CODE_MAPPING,
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
    RegistrationWebStoreAccount,
    RegistrationWebStoreMerchant,
    RegistrationWebStoreProductMapping,
    SignUp,
    SignUpPayment,
)
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    RegistrationWebStoreAccountFactory,
    RegistrationWebStoreMerchantFactory,
    RegistrationWebStoreProductMappingFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpPaymentFactory,
    SignUpPriceGroupFactory,
    WebStoreAccountFactory,
    WebStoreMerchantFactory,
)
from registrations.tests.test_registration_post import email, hel_email
from registrations.tests.utils import (
    assert_invitation_email_is_sent,
    create_user_by_role,
    get_event_url,
    get_minimal_required_registration_data,
    get_registration_account_data,
    get_registration_merchant_and_account_data,
    get_registration_merchant_data,
)
from web_store.tests.order.test_web_store_order_api_client import DEFAULT_GET_ORDER_DATA
from web_store.tests.product.test_web_store_product_api_client import (
    DEFAULT_GET_PRODUCT_MAPPING_DATA,
    DEFAULT_PRODUCT_ID,
)

edited_email = "edited@email.com"
edited_hel_email = "edited@hel.fi"
event_name = "Foo"

# === util methods ===


def update_registration(api_client, pk, registration_data, data_source=None):
    edit_url = reverse("registration-detail", kwargs={"pk": pk})

    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    response = api_client.put(edit_url, registration_data, format="json")
    return response


def assert_update_registration(api_client, pk, registration_data, data_source=None):
    response = update_registration(api_client, pk, registration_data, data_source)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == pk
    return response


# === tests ===


@pytest.mark.parametrize(
    "user_role",
    [
        "superuser",
        "admin",
        "registration_admin",
        "substitute_user_access",
        "substitute_user_access_without_organization",
    ],
)
@pytest.mark.django_db
def test_can_update_registration(api_client, registration, user_role):
    user = create_user_by_role(
        user_role,
        registration.publisher,
        additional_roles={
            "substitute_user_access": lambda usr: usr.organization_memberships.add(
                registration.publisher
            ),
            "substitute_user_access_without_organization": lambda usr: None,
        },
    )

    if user_role.startswith("substitute_user_access"):
        user.email = hel_email
        user.save(update_fields=["email"])

        RegistrationUserAccessFactory(
            registration=registration, email=hel_email, is_substitute_user=True
        )

    api_client.force_authenticate(user)

    registration_data = get_minimal_required_registration_data(registration.event_id)
    assert_update_registration(api_client, registration.id, registration_data)


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
def test_signup_url_is_not_linked_to_event_offer_on_registration_update(
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

    registration_data = get_minimal_required_registration_data(registration.event_id)
    assert_update_registration(api_client, registration.pk, registration_data)

    blank_values = (None, "")
    offer.refresh_from_db()
    assert offer.info_url_fi in blank_values
    assert offer.info_url_sv in blank_values
    assert offer.info_url_en in blank_values


@pytest.mark.parametrize("user_role", ["financial_admin", "regular_user"])
@pytest.mark.django_db
def test_not_allowed_roles_cannot_update_registration(
    api_client, event, registration, user_role
):
    user = create_user_by_role(user_role, event.publisher)
    api_client.force_authenticate(user)

    registration_data = get_minimal_required_registration_data(registration.event_id)
    response = update_registration(api_client, registration.id, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_can_update_registration_from_another_data_source(
    api_client, event2, other_data_source, organization, registration2, user
):
    other_data_source.owner = organization
    other_data_source.user_editable_resources = True
    other_data_source.save()
    api_client.force_authenticate(user)

    event2.publisher = organization
    event2.save()

    registration_data = get_minimal_required_registration_data(event2.id)
    assert_update_registration(api_client, registration2.id, registration_data)


@pytest.mark.django_db
def test_correct_api_key_can_update_registration(
    api_client, data_source, organization, registration
):
    data_source.owner = organization
    data_source.save()

    registration_data = get_minimal_required_registration_data(registration.event_id)
    assert_update_registration(
        api_client, registration.id, registration_data, data_source
    )


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_cannot_update_registration(
    api_client, organization, other_data_source, registration
):
    other_data_source.owner = organization
    other_data_source.save()

    registration_data = get_minimal_required_registration_data(registration.event_id)
    response = update_registration(
        api_client, registration.id, registration_data, other_data_source
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_without_organization_cannot_update_registration(
    api_client, data_source, registration
):
    registration_data = get_minimal_required_registration_data(registration.event_id)
    response = update_registration(
        api_client, registration.id, registration_data, data_source
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("api_key", ["", "unknown"])
@pytest.mark.django_db
def test_invalid_api_key_cannot_update_registration(api_client, registration, api_key):
    api_client.credentials(apikey=api_key)

    registration_data = get_minimal_required_registration_data(registration.event_id)
    response = update_registration(api_client, registration.id, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.parametrize("user_role", ["admin", "registration_admin"])
@pytest.mark.django_db
def test_admin_or_registration_admin_can_update_registration_regardless_of_user_editable_resources(
    api_client,
    data_source,
    organization,
    registration,
    user_editable_resources,
    user_role,
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    registration_data = get_minimal_required_registration_data(registration.event_id)
    assert_update_registration(api_client, registration.id, registration_data)


@pytest.mark.django_db
def test_user_editable_resources_can_update_registration(
    api_client, data_source, organization, registration, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user)

    registration_data = get_minimal_required_registration_data(registration.event_id)
    assert_update_registration(api_client, registration.id, registration_data)


@pytest.mark.django_db
def test_admin_cannot_update_registrations_event(
    api_client, event, event2, registration, user
):
    """Event field is read-only field and cannot be edited"""
    api_client.force_authenticate(user)

    registration_data = get_minimal_required_registration_data(event2.id)
    assert_update_registration(api_client, registration.id, registration_data)

    registration.refresh_from_db()
    assert registration.event_id == event.pk


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_send_email_to_new_registration_user_access(
    registration, user_api_client, is_substitute_user
):
    user_email = hel_email if is_substitute_user else email

    RegistrationUserAccessFactory(registration=registration, email="delete1@email.com")
    RegistrationUserAccessFactory(registration=registration, email="delete2@email.com")
    assert len(registration.registration_user_accesses.all()) == 2
    mail.outbox.clear()

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_user_accesses": [
            {"email": user_email, "is_substitute_user": is_substitute_user}
        ],
    }

    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        response = assert_update_registration(
            user_api_client, registration.id, registration_data
        )

    #  assert that registration user was created
    registration_user_accesses = response.data["registration_user_accesses"]
    assert len(registration_user_accesses) == 1
    assert registration_user_accesses[0]["email"] == user_email

    #  assert that the email was sent
    registration_user_access = RegistrationUserAccess.objects.get(
        pk=registration_user_accesses[0]["id"]
    )
    assert_invitation_email_is_sent(user_email, event_name, registration_user_access)


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_email_is_not_sent_if_registration_user_access_email_is_not_updated(
    registration, user_api_client, is_substitute_user
):
    user_email = hel_email if is_substitute_user else email

    registration_user_access = RegistrationUserAccessFactory(
        registration=registration,
        email=user_email,
        is_substitute_user=is_substitute_user,
    )
    mail.outbox.clear()

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_user_accesses": [
            {"id": registration_user_access.id, "email": user_email}
        ],
    }
    assert_update_registration(user_api_client, registration.id, registration_data)

    # Assert that registration user is not changed
    registration_user_accesses = registration.registration_user_accesses.all()
    assert len(registration_user_accesses) == 1
    assert registration_user_access.id == registration_user_accesses[0].id
    assert registration_user_accesses[0].email == user_email
    #  assert that the email is not sent
    assert len(mail.outbox) == 0


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_email_is_sent_if_registration_user_access_email_is_updated(
    registration, user_api_client, is_substitute_user
):
    user_email = hel_email if is_substitute_user else email
    edited_user_email = edited_hel_email if is_substitute_user else edited_email

    registration_user_access = RegistrationUserAccessFactory(
        registration=registration,
        email=user_email,
        is_substitute_user=is_substitute_user,
    )
    mail.outbox.clear()

    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        registration_data = {
            **get_minimal_required_registration_data(registration.event_id),
            "registration_user_accesses": [
                {
                    "id": registration_user_access.id,
                    "email": edited_user_email,
                    "is_substitute_user": is_substitute_user,
                }
            ],
        }

        assert_update_registration(user_api_client, registration.id, registration_data)
        #  assert that the email after update was sent
        registration_user_access.refresh_from_db()
        assert_invitation_email_is_sent(
            edited_user_email, event_name, registration_user_access
        )


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_email_is_sent_if_is_substitute_value_of_registration_user_access_is_updated(
    registration, user_api_client, is_substitute_user
):
    user_email = hel_email

    registration_user_access = RegistrationUserAccessFactory(
        registration=registration,
        email=user_email,
        is_substitute_user=is_substitute_user,
    )
    mail.outbox.clear()

    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        registration_data = {
            **get_minimal_required_registration_data(registration.event_id),
            "registration_user_accesses": [
                {
                    "id": registration_user_access.id,
                    "email": hel_email,
                    "is_substitute_user": False if is_substitute_user else True,
                }
            ],
        }

        assert_update_registration(user_api_client, registration.id, registration_data)

        #  assert that the email after update was sent
        registration_user_access.refresh_from_db()
        assert_invitation_email_is_sent(
            user_email, event_name, registration_user_access
        )


@pytest.mark.parametrize(
    "is_substitute_user,user_id,expected_error_code",
    [
        (False, "invalid", "incorrect_type"),
        (True, "invalid", "incorrect_type"),
        (False, 1234567, "does_not_exist"),
        (True, 1234567, "does_not_exist"),
    ],
)
@pytest.mark.django_db
def test_cannot_update_registration_user_access_with_invalid_id(
    registration, user_api_client, is_substitute_user, user_id, expected_error_code
):
    user_email = hel_email if is_substitute_user else email
    edited_user_email = edited_hel_email if is_substitute_user else edited_email

    RegistrationUserAccessFactory(registration=registration, email=user_email)

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_user_accesses": [
            {
                "id": user_id,
                "email": edited_user_email,
                "is_substitute_user": is_substitute_user,
            }
        ],
    }

    response = update_registration(user_api_client, registration.id, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["registration_user_accesses"][0]["id"][0].code
        == expected_error_code
    )


@pytest.mark.django_db
def test_cannot_update_substitute_user_access_without_helsinki_email(
    registration, user_api_client
):
    user_access = RegistrationUserAccessFactory(registration=registration, email=email)

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_user_accesses": [
            {
                "id": user_access.pk,
                "email": edited_email,
                "is_substitute_user": True,
            }
        ],
    }
    response = update_registration(user_api_client, registration.id, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["registration_user_accesses"][0]["is_substitute_user"][0]
        == "The user's email domain is not one of the allowed domains for substitute users."
    )


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_cannot_update_registration_user_access_with_another_registrations_user_accesses_id(
    registration, user_api_client, is_substitute_user
):
    edited_user_email = edited_hel_email if is_substitute_user else edited_email

    another_registrations_user_access = RegistrationUserAccessFactory(
        email="test@test.com", is_substitute_user=is_substitute_user
    )

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_user_accesses": [
            {
                "id": another_registrations_user_access.pk,
                "email": edited_user_email,
                "is_substitute_user": is_substitute_user,
            },
        ],
    }

    response = update_registration(user_api_client, registration.id, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["registration_user_accesses"][0]["id"][0]
        == f'Invalid pk "{another_registrations_user_access.pk}" - object does not exist.'
    )


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_cannot_update_registration_user_access_with_duplicate_email(
    registration, user_api_client, is_substitute_user
):
    email1 = "email1@hel.fi" if is_substitute_user else "email1@test.fi"
    email2 = "email2@hel.fi" if is_substitute_user else "email2@test.fi"

    registration_user_access1 = RegistrationUserAccessFactory(
        registration=registration, email=email1, is_substitute_user=is_substitute_user
    )
    registration_user_access2 = RegistrationUserAccessFactory(
        registration=registration, email=email2, is_substitute_user=is_substitute_user
    )

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_user_accesses": [
            {
                "id": registration_user_access1.id,
                "email": email2,
                "is_substitute_user": is_substitute_user,
            },
            {
                "id": registration_user_access2.id,
                "email": email1,
                "is_substitute_user": is_substitute_user,
            },
        ],
    }

    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        response = update_registration(
            user_api_client, registration.id, registration_data
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_user_accesses"][0].code == "unique"


@pytest.mark.django_db
def test_registration_text_fields_are_sanitized(event, registration, user_api_client):
    allowed_confirmation_message = "Confirmation message: <p>Allowed tag</p>"
    cleaned_confirmation_message = "Confirmation message: Not allowed tag"
    allowed_instructions = "Instructions: <p>Allowed tag</p>"
    cleaned_instructions = "Instructions: Not allowed tag"

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "confirmation_message": {
            "fi": allowed_confirmation_message,
            "sv": "Confirmation message: <h6>Not allowed tag</h6>",
        },
        "instructions": {
            "fi": allowed_instructions,
            "sv": "Instructions: <h6>Not allowed tag</h6>",
        },
    }

    response = update_registration(user_api_client, registration.id, registration_data)
    assert response.data["confirmation_message"]["fi"] == allowed_confirmation_message
    assert response.data["confirmation_message"]["sv"] == cleaned_confirmation_message
    assert response.data["instructions"]["fi"] == allowed_instructions
    assert response.data["instructions"]["sv"] == cleaned_instructions

    registration.refresh_from_db()
    assert registration.confirmation_message_fi == allowed_confirmation_message
    assert registration.confirmation_message_sv == cleaned_confirmation_message
    assert registration.instructions_fi == allowed_instructions
    assert registration.instructions_sv == cleaned_instructions


@pytest.mark.django_db
def test_registration_id_is_audit_logged_on_put(registration, user_api_client):
    registration_data = get_minimal_required_registration_data(registration.event_id)
    assert_update_registration(user_api_client, registration.id, registration_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        registration.pk
    ]


@pytest.mark.django_db
def test_update_price_groups_with_product_mapping_for_registration(
    api_client, event, user
):
    api_client.force_authenticate(user)

    registration = RegistrationFactory(event=event)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    assert RegistrationPriceGroup.objects.count() == 0
    assert RegistrationWebStoreProductMapping.objects.count() == 0
    assert RegistrationWebStoreMerchant.objects.count() == 0
    assert RegistrationWebStoreAccount.objects.count() == 0

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
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

        response = assert_update_registration(
            api_client, registration.pk, registration_data
        )

        assert req_mock.call_count == 2

    assert len(response.data["registration_price_groups"]) == 2

    assert RegistrationPriceGroup.objects.count() == 2

    registration.refresh_from_db()
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
        registration.registration_price_groups.filter(
            price_group=custom_price_group,
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


@pytest.mark.django_db
def test_update_existing_registration_price_group(api_client, event, user):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    registration = RegistrationFactory(event=event)
    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group=default_price_group,
        price=Decimal("10"),
        vat_percentage=VatPercentage.VAT_25_5.value,
        price_without_vat=Decimal("7.97"),
        vat=Decimal("2.03"),
    )

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(
            registration=registration,
            vat_code=VAT_CODE_MAPPING[VatPercentage.VAT_0.value],
        )
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )
    registration_account = RegistrationWebStoreAccountFactory(registration=registration)

    assert RegistrationPriceGroup.objects.count() == 1

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "id": registration_price_group.pk,
                "price_group": custom_price_group.pk,
                "price": Decimal("5"),
                "vat_percentage": VatPercentage.VAT_0.value,
            },
        ],
        **get_registration_merchant_and_account_data(
            merchant=registration_merchant.merchant,
            account=registration_account.account,
        ),
    }

    response = assert_update_registration(
        api_client, registration.pk, registration_data
    )
    assert len(response.data["registration_price_groups"]) == 1
    assert (
        response.data["registration_price_groups"][0]["id"]
        == registration_price_group.pk
    )

    assert RegistrationPriceGroup.objects.count() == 1

    registration.refresh_from_db()
    assert (
        registration.registration_price_groups.filter(
            price_group=custom_price_group,
            price=registration_data["registration_price_groups"][0]["price"],
            vat_percentage=registration_data["registration_price_groups"][0][
                "vat_percentage"
            ],
            price_without_vat=Decimal("5"),
            vat=Decimal("0"),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_update_registration_price_groups_excluded_is_deleted(api_client, event, user):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    registration = RegistrationFactory(event=event)
    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group=default_price_group,
        price=Decimal("10"),
        vat_percentage=VatPercentage.VAT_25_5.value,
        price_without_vat=Decimal("7.97"),
        vat=Decimal("2.03"),
    )

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(
            registration=registration,
            vat_code=VAT_CODE_MAPPING[VatPercentage.VAT_0.value],
        )
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )
    registration_account = RegistrationWebStoreAccountFactory(registration=registration)
    assert RegistrationPriceGroup.objects.count() == 1

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "price_group": custom_price_group.pk,
                "price": Decimal("5"),
                "vat_percentage": VatPercentage.VAT_0.value,
            },
        ],
        **get_registration_merchant_and_account_data(
            merchant=registration_merchant.merchant,
            account=registration_account.account,
        ),
    }

    response = assert_update_registration(
        api_client, registration.pk, registration_data
    )
    assert len(response.data["registration_price_groups"]) == 1
    assert (
        response.data["registration_price_groups"][0]["id"]
        != registration_price_group.pk
    )

    assert RegistrationPriceGroup.objects.count() == 1

    registration.refresh_from_db()
    assert (
        registration.registration_price_groups.filter(
            price_group=custom_price_group,
            price=registration_data["registration_price_groups"][0]["price"],
            vat_percentage=registration_data["registration_price_groups"][0][
                "vat_percentage"
            ],
            price_without_vat=Decimal("5"),
            vat=Decimal("0"),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_cannot_update_price_groups_to_registration_with_different_vat_percentages(
    api_client, event, user
):
    api_client.force_authenticate(user)

    registration = RegistrationFactory(event=event)

    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    assert RegistrationPriceGroup.objects.count() == 0

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
            {
                "price_group": custom_price_group.pk,
                "price": Decimal("15.55"),
                "vat_percentage": VatPercentage.VAT_14.value,
            },
        ],
    }
    response = update_registration(api_client, registration.pk, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"]["price_group"][0] == (
        "All registration price groups must have the same VAT percentage."
    )

    assert RegistrationPriceGroup.objects.count() == 0


@pytest.mark.django_db
def test_cannot_update_registration_with_duplicate_price_groups(
    user, api_client, event
):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    registration = RegistrationFactory(event=event)
    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group=default_price_group,
    )

    assert RegistrationPriceGroup.objects.count() == 1

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
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
    response = update_registration(api_client, registration.pk, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"][1]["price_group"][0] == (
        f"Registration price group with price_group {default_price_group} already exists."
    )

    assert RegistrationPriceGroup.objects.count() == 1


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
def test_update_registration_with_with_optional_product_mapping_accounting_fields(
    user_api_client, event, registration, account_kwargs
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
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

    assert RegistrationWebStoreProductMapping.objects.count() == 0
    assert RegistrationWebStoreAccount.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        assert_update_registration(user_api_client, registration.pk, registration_data)

        assert req_mock.call_count == 2

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
def test_update_registration_product_mapping_merchant_changed(
    user_api_client, event, registration
):
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

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
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
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        assert_update_registration(user_api_client, registration.pk, registration_data)

        assert req_mock.call_count == 2

    assert RegistrationWebStoreProductMapping.objects.count() == 1

    registration_merchant.refresh_from_db()
    assert registration_merchant.merchant_id == new_merchant.pk
    assert registration_merchant.external_merchant_id == new_merchant.merchant_id

    product_mapping.refresh_from_db()
    assert product_mapping.external_product_id == DEFAULT_PRODUCT_ID


@pytest.mark.django_db
def test_update_registration_product_mapping_account_changed(
    user_api_client, event, registration
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )

    registration_account = RegistrationWebStoreAccountFactory(registration=registration)
    new_account = WebStoreAccountFactory(organization=event.publisher)

    product_mapping = RegistrationWebStoreProductMappingFactory(
        registration=registration, external_product_id="4321"
    )

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
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
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        assert_update_registration(user_api_client, registration.pk, registration_data)

        assert req_mock.call_count == 2

    assert RegistrationWebStoreProductMapping.objects.count() == 1

    registration_account.refresh_from_db()
    assert registration_account.account_id == new_account.pk

    product_mapping.refresh_from_db()
    assert product_mapping.external_product_id == DEFAULT_PRODUCT_ID


@pytest.mark.django_db
def test_update_registration_product_mapping_vat_code_changed(
    user_api_client, event, registration
):
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )
    registration_account = RegistrationWebStoreAccountFactory(registration=registration)
    product_mapping = RegistrationWebStoreProductMappingFactory(
        registration=registration, external_product_id="4321"
    )

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "id": registration_price_group.pk,
                "price_group": registration_price_group.price_group_id,
                "price": registration_price_group.price,
                "vat_percentage": VatPercentage.VAT_10.value,
            },
        ],
        **get_registration_merchant_and_account_data(
            registration_merchant.merchant, registration_account.account
        ),
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 1

    assert product_mapping.external_product_id != DEFAULT_PRODUCT_ID
    assert product_mapping.vat_code != VAT_CODE_MAPPING[VatPercentage.VAT_10.value]

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        assert_update_registration(user_api_client, registration.pk, registration_data)

        assert req_mock.call_count == 2

    assert RegistrationWebStoreProductMapping.objects.count() == 1

    product_mapping.refresh_from_db()
    assert product_mapping.external_product_id == DEFAULT_PRODUCT_ID
    assert product_mapping.vat_code == VAT_CODE_MAPPING[VatPercentage.VAT_10.value]


@pytest.mark.django_db
def test_update_registration_with_product_mapping_merchant_missing(
    user_api_client, event, registration
):
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_account_data(account),
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = update_registration(user_api_client, registration.pk, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_merchant"][0] == (
        "This field is required when registration has customer groups."
    )

    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_update_registration_with_product_mapping_account_missing(
    user_api_client, event, registration
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_merchant_data(merchant),
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = update_registration(user_api_client, registration.pk, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_account"][0] == (
        "This field is required when registration has customer groups."
    )

    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_cannot_update_product_mapping_with_price_groups_missing(
    user_api_client, event, registration
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        **get_registration_merchant_and_account_data(merchant, account),
    }

    assert Registration.objects.count() == 1
    assert RegistrationWebStoreProductMapping.objects.count() == 0

    response = update_registration(user_api_client, registration.pk, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration_price_groups"][0] == (
        "This field is required when registration has a merchant or account."
    )

    assert Registration.objects.count() == 1
    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_update_registration_with_product_mapping_api_exception(
    user_api_client, event, registration
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, exc=RequestException)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        response = update_registration(
            user_api_client, registration.pk, registration_data
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert req_mock.call_count == 1

    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_update_registration_with_product_accounting_api_exception(
    user_api_client, event, registration
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.first()
    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": VatPercentage.VAT_25_5.value,
            },
        ],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    assert RegistrationWebStoreProductMapping.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            exc=RequestException,
        )

        response = update_registration(
            user_api_client, registration.pk, registration_data
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert req_mock.call_count == 2

    assert RegistrationWebStoreProductMapping.objects.count() == 0


@pytest.mark.django_db
def test_update_registration_increase_attendee_capacity_move_signups_to_attending(
    api_client, event, django_capture_on_commit_callbacks
):
    user = create_user_by_role("registration_admin", event.publisher)
    api_client.force_authenticate(user)

    registration = RegistrationFactory(event=event, maximum_attendee_capacity=1)

    with django_capture_on_commit_callbacks(execute=True):
        signup = SignUpFactory(
            registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
        )
        signup2 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        signup3 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        signup4 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 0

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "maximum_attendee_capacity": 3,
    }
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        assert_update_registration(api_client, registration.pk, registration_data)
    assert len(callbacks) == 3

    # Since two additional attendee spots were added,
    # two more signups should now be in the "attending" status:
    signup.refresh_from_db()
    assert signup.attendee_status == SignUp.AttendeeStatus.ATTENDING

    signup2.refresh_from_db()
    assert signup2.attendee_status == SignUp.AttendeeStatus.ATTENDING

    signup3.refresh_from_db()
    assert signup3.attendee_status == SignUp.AttendeeStatus.ATTENDING

    signup4.refresh_from_db()
    assert signup4.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 0


@pytest.mark.django_db
def test_update_registration_increase_attendee_capacity_move_signups_to_attending_with_payments(
    api_client, event, django_capture_on_commit_callbacks
):
    user = create_user_by_role("registration_admin", event.publisher)
    api_client.force_authenticate(user)

    registration = RegistrationFactory(event=event, maximum_attendee_capacity=1)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )
    registration_account = RegistrationWebStoreAccountFactory(registration=registration)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    with django_capture_on_commit_callbacks(execute=True):
        signup = SignUpFactory(
            registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
        )
        SignUpPaymentFactory(signup=signup)

        signup2 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        SignUpPriceGroupFactory(
            signup=signup2, registration_price_group=registration_price_group
        )
        SignUpContactPersonFactory(signup=signup2, email="signup2@test.dev")

        signup3 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        SignUpPriceGroupFactory(
            signup=signup3, registration_price_group=registration_price_group
        )
        SignUpContactPersonFactory(signup=signup3, email="signup3@test.dev")

        signup4 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        SignUpPriceGroupFactory(
            signup=signup4, registration_price_group=registration_price_group
        )
        SignUpContactPersonFactory(signup=signup4, email="signup4@test.dev")

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 0

    assert SignUpPayment.objects.count() == 1

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "maximum_attendee_capacity": 3,
        "registration_price_groups": [
            {
                "id": registration_price_group.pk,
                "price_group": registration_price_group.price_group_id,
                "price": registration_price_group.price,
                "vat_percentage": registration_price_group.vat_percentage,
            }
        ],
        **get_registration_merchant_and_account_data(
            registration_merchant.merchant, registration_account.account
        ),
    }
    with (
        requests_mock.Mocker() as req_mock,
        django_capture_on_commit_callbacks(execute=True) as callbacks,
    ):
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            status_code=status.HTTP_201_CREATED,
            json=DEFAULT_GET_ORDER_DATA,
        )

        assert_update_registration(api_client, registration.pk, registration_data)

    assert req_mock.call_count == 2
    assert len(callbacks) == 3

    # Since two additional attendee spots were added,
    # two more signups should now be in the "attending" status with payments:
    assert SignUpPayment.objects.count() == 3

    signup.refresh_from_db()
    assert signup.attendee_status == SignUp.AttendeeStatus.ATTENDING

    signup2.refresh_from_db()
    assert signup2.attendee_status == SignUp.AttendeeStatus.ATTENDING

    signup3.refresh_from_db()
    assert signup3.attendee_status == SignUp.AttendeeStatus.ATTENDING

    signup4.refresh_from_db()
    assert signup4.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 0


@pytest.mark.django_db
def test_increase_attendee_capacity_move_signups_to_attending_with_payments_api_exception(
    api_client, event, django_capture_on_commit_callbacks
):
    user = create_user_by_role("registration_admin", event.publisher)
    api_client.force_authenticate(user)

    registration = RegistrationFactory(event=event, maximum_attendee_capacity=1)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )
    registration_account = RegistrationWebStoreAccountFactory(registration=registration)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    with django_capture_on_commit_callbacks(execute=True):
        signup = SignUpFactory(
            registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
        )
        SignUpPaymentFactory(signup=signup)

        signup2 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        SignUpPriceGroupFactory(
            signup=signup2, registration_price_group=registration_price_group
        )
        SignUpContactPersonFactory(signup=signup2, email="signup2@test.dev")

        signup3 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        price_group3 = SignUpPriceGroupFactory(
            signup=signup3, registration_price_group=registration_price_group
        )
        SignUpContactPersonFactory(signup=signup3, email="signup3@test.dev")

        signup4 = SignUpFactory(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        SignUpPriceGroupFactory(
            signup=signup4, registration_price_group=registration_price_group
        )
        SignUpContactPersonFactory(signup=signup4, email="signup4@test.dev")

    def web_store_match_signup3(request):
        return request.json()["items"][0]["meta"][0]["value"] == str(price_group3.pk)

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 0

    assert SignUpPayment.objects.count() == 1

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "maximum_attendee_capacity": 3,
        "registration_price_groups": [
            {
                "id": registration_price_group.pk,
                "price_group": registration_price_group.price_group_id,
                "price": registration_price_group.price,
                "vat_percentage": registration_price_group.vat_percentage,
            }
        ],
        **get_registration_merchant_and_account_data(
            registration_merchant.merchant, registration_account.account
        ),
    }
    with (
        requests_mock.Mocker() as req_mock,
        django_capture_on_commit_callbacks(execute=True) as callbacks,
    ):
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            status_code=status.HTTP_201_CREATED,
            json=DEFAULT_GET_ORDER_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            additional_matcher=web_store_match_signup3,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

        assert_update_registration(api_client, registration.pk, registration_data)

    assert req_mock.call_count == 2
    assert len(callbacks) == 2

    # Two additional attendee spots were added, but the second signup experienced an
    # API exception after the first one so only the first one was moved to "attending":
    assert SignUpPayment.objects.count() == 2

    signup.refresh_from_db()
    assert signup.attendee_status == SignUp.AttendeeStatus.ATTENDING

    signup2.refresh_from_db()
    assert signup2.attendee_status == SignUp.AttendeeStatus.ATTENDING

    signup3.refresh_from_db()
    assert signup3.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    signup4.refresh_from_db()
    assert signup4.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 1


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
def test_update_registration_maximum_attendee_capacity(
    api_client,
    maximum_attendee_capacity,
    expected_maximum_attendee_capacity,
    expected_status_code,
):
    registration = RegistrationFactory(maximum_attendee_capacity=None)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration_data = {
        "event": {"@id": get_event_url(registration.event_id)},
        "maximum_attendee_capacity": maximum_attendee_capacity,
    }

    response = update_registration(api_client, registration.pk, registration_data)
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
def test_update_registration_minimum_attendee_capacity(
    api_client, minimum_attendee_capacity, expected_minimum_attendee_capacity
):
    registration = RegistrationFactory(minimum_attendee_capacity=None)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration_data = {
        **get_minimal_required_registration_data(registration.event_id),
        "minimum_attendee_capacity": minimum_attendee_capacity,
    }

    assert_update_registration(api_client, registration.pk, registration_data)

    registration.refresh_from_db()
    assert registration.minimum_attendee_capacity == expected_minimum_attendee_capacity
