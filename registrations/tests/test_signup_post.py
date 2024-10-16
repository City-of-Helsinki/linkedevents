from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
import requests_mock
from django.conf import settings
from django.core import mail
from django.test import override_settings
from django.utils import translation
from django.utils.timezone import localtime
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event, Language
from events.tests.factories import LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from registrations.models import (
    MandatoryFields,
    SeatReservationCode,
    SignUp,
    SignUpContactPerson,
    SignUpPayment,
    SignUpPriceGroup,
    web_store_price_group_meta_key,
)
from registrations.notifications import NotificationType
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    RegistrationWebStoreAccountFactory,
    RegistrationWebStoreMerchantFactory,
    RegistrationWebStoreProductMappingFactory,
    SeatReservationCodeFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.test_signup_patch import description_fields
from registrations.tests.utils import (
    DEFAULT_CREATE_ORDER_ERROR_RESPONSE,
    assert_attending_and_waitlisted_signups,
    assert_payment_link_email_sent,
    assert_signup_payment_data_is_correct,
    create_user_by_role,
)
from web_store.tests.order.test_web_store_order_api_client import DEFAULT_GET_ORDER_DATA
from web_store.tests.product.test_web_store_product_api_client import (
    DEFAULT_GET_PRODUCT_MAPPING_DATA,
    DEFAULT_PRODUCT_ID,
)

test_access_code = "803aabab-8fa5-4c26-a372-7792a8b8456f"
test_email1 = "test@email.com"
test_street_address = "my street"
default_signups_data = {
    "signups": [
        {
            "first_name": "Michael",
            "last_name": "Jackson",
            "extra_info": "Extra info",
            "date_of_birth": "2011-04-07",
            "phone_number": "0401111111",
            "street_address": test_street_address,
            "zipcode": "myzip1",
            "user_consent": True,
            "contact_person": {
                "first_name": "Mickey",
                "last_name": "Mouse",
                "email": test_email1,
                "phone_number": "0441111111",
                "notifications": "sms",
                "service_language": "fi",
                "native_language": "fi",
            },
        }
    ],
}

# === util methods ===


def create_signups(api_client, signups_data):
    create_url = reverse("signup-list")
    response = api_client.post(create_url, signups_data, format="json")

    return response


def assert_create_signups(api_client, signups_data):
    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_201_CREATED

    return response


def assert_default_contact_person_created(contact_person_data):
    assert SignUpContactPerson.objects.count() == 1

    contact_person = SignUpContactPerson.objects.first()
    assert contact_person.email == contact_person_data["email"]
    assert contact_person.phone_number == contact_person_data["phone_number"]
    assert contact_person.notifications == NotificationType.SMS
    assert contact_person.native_language.pk == "fi"
    assert contact_person.service_language.pk == "fi"


def assert_default_signup_created(signups_data, user):
    assert SignUp.objects.count() == 1
    assert SeatReservationCode.objects.count() == 0

    signup = SignUp.objects.first()
    assert signup.attendee_status == SignUp.AttendeeStatus.ATTENDING
    assert signup.first_name == signups_data["signups"][0]["first_name"]
    assert signup.last_name == signups_data["signups"][0]["last_name"]
    assert signup.phone_number == signups_data["signups"][0]["phone_number"]
    if signups_data["signups"][0].get("date_of_birth"):
        assert signup.date_of_birth == date(2011, 4, 7)
    else:
        assert signup.date_of_birth is None
    if signups_data["signups"][0].get("extra_info"):
        assert signup.extra_info == signups_data["signups"][0]["extra_info"]
    else:
        assert signup.extra_info in [None, ""]
    assert signup.street_address == signups_data["signups"][0]["street_address"]
    assert signup.zipcode == signups_data["signups"][0]["zipcode"]
    assert signup.created_by_id == user.id
    assert signup.last_modified_by_id == user.id
    assert signup.created_time is not None
    assert signup.last_modified_time is not None
    assert signup.user_consent is signups_data["signups"][0]["user_consent"]

    assert_default_contact_person_created(signups_data["signups"][0]["contact_person"])


# === tests ===


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "financial_admin",
        "regular_user",
        "regular_user_without_organization",
        "registration_user_access",
        "registration_substitute_user",
    ],
)
@pytest.mark.django_db
def test_authenticated_users_can_create_signups(registration, api_client, user_role):
    LanguageFactory(pk="fi", service_language=True)

    user_email = (
        hel_email if user_role == "registration_substitute_user" else "user@test.com"
    )

    user = create_user_by_role(
        user_role,
        registration.publisher,
        additional_roles={
            "regular_user_without_organization": lambda usr: None,
            "registration_user_access": lambda usr: RegistrationUserAccessFactory(
                registration=registration,
                email=user_email,
            ),
            "registration_substitute_user": lambda usr: RegistrationUserAccessFactory(
                registration=registration, email=user_email, is_substitute_user=True
            ),
        },
    )
    user.email = user_email
    user.save(update_fields=["email"])

    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)

    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signups_data = default_signups_data
    signups_data["registration"] = registration.id
    signups_data["reservation_code"] = reservation.code

    assert_create_signups(api_client, signups_data)
    assert_default_signup_created(signups_data, user)


@pytest.mark.parametrize(
    "user_role",
    [
        "superuser",
        "admin",
        "registration_admin",
        "financial_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_authenticated_user_can_create_signups_with_payments(api_client, user_role):
    language = LanguageFactory(pk="fi", service_language=True)

    with translation.override(language.pk):
        registration = RegistrationFactory(event__name="Foo")

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreMerchantFactory(registration=registration)
    RegistrationWebStoreAccountFactory(registration=registration)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    user = create_user_by_role(
        user_role,
        registration.publisher,
        additional_roles=(
            {
                "regular_user_without_organization": lambda usr: None,
            }
            if user_role == "regular_user_without_organization"
            else None
        ),
    )
    api_client.force_authenticate(user)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )
    signups_data["signups"][0]["contact_person"].update(
        {
            "native_language": language.pk,
            "service_language": language.pk,
        }
    )

    order_item_id = "1234"

    assert SignUpPayment.objects.count() == 0
    assert (
        SignUpPriceGroup.objects.filter(external_order_item_id=order_item_id).count()
        == 0
    )

    mocked_web_store_json = deepcopy(DEFAULT_GET_ORDER_DATA)
    mocked_web_store_json["priceTotal"] = str(registration_price_group.price)
    mocked_web_store_json["items"] = [
        {
            "orderItemId": order_item_id,
            "meta": [
                {
                    "key": web_store_price_group_meta_key,
                }
            ],
        },
    ]

    def get_response(request, context):
        price_group = SignUpPriceGroup.objects.first()
        mocked_web_store_json["items"][0]["meta"][0]["value"] = price_group.pk

        return mocked_web_store_json

    with translation.override(language.pk), requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            status_code=status.HTTP_201_CREATED,
            json=get_response,
        )

        response = assert_create_signups(api_client, signups_data)

        assert req_mock.call_count == 1

    assert SignUpPayment.objects.count() == 1
    assert (
        SignUpPriceGroup.objects.filter(external_order_item_id=order_item_id).count()
        == 1
    )

    assert_default_signup_created(signups_data, user)
    assert_signup_payment_data_is_correct(
        response.data[0]["payment"],
        user,
        SignUp.objects.first(),
        service_language=language.pk,
    )

    # Payment link is sent via email.
    assert_payment_link_email_sent(
        SignUpContactPerson.objects.first(),
        SignUpPayment.objects.first(),
        expected_subject="Maksu vaaditaan ilmoittautumisen vahvistamiseksi - Foo",
        expected_text="Voit vahvistaa ilmoittautumisesi tapahtumaan <strong>Foo</strong> "
        "oheisen maksulinkin avulla. Maksulinkki vanhenee %(hours)s tunnin kuluttua."
        % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
    )


@pytest.mark.parametrize(
    "user_role",
    [
        "superuser",
        "admin",
        "registration_admin",
        "financial_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_update_web_store_product_mapping_if_merchant_id_has_changed(
    api_client, registration, user_role
):
    language = LanguageFactory(pk="fi", service_language=True)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )
    RegistrationWebStoreAccountFactory(registration=registration)

    registration_merchant.external_merchant_id = "1234"
    registration_merchant.save(update_fields=["external_merchant_id"])

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    user = create_user_by_role(
        user_role,
        registration.publisher,
        additional_roles=(
            {
                "regular_user_without_organization": lambda usr: None,
            }
            if user_role == "regular_user_without_organization"
            else None
        ),
    )
    api_client.force_authenticate(user)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )

    assert SignUpPayment.objects.count() == 0

    web_store_response_json = deepcopy(DEFAULT_GET_ORDER_DATA)
    web_store_response_json["priceTotal"] = str(registration_price_group.price)

    with requests_mock.Mocker() as req_mock:
        product_base_url = f"{settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(product_base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{product_base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            status_code=status.HTTP_201_CREATED,
            json=web_store_response_json,
        )

        response = assert_create_signups(api_client, signups_data)

        assert req_mock.call_count == 3

    assert SignUpPayment.objects.count() == 1

    assert_default_signup_created(signups_data, user)
    assert_signup_payment_data_is_correct(
        response.data[0]["payment"],
        user,
        SignUp.objects.first(),
        service_language=language.pk,
    )


@pytest.mark.django_db
def test_can_create_signup_with_create_payment_as_false_in_payload(
    registration, api_client
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(pk="fi", service_language=True)
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "create_payment": False,
        }
    )

    assert SignUpPayment.objects.count() == 0

    assert_create_signups(api_client, signups_data)

    assert SignUpPayment.objects.count() == 0


@pytest.mark.django_db
def test_create_signup_payment_without_pricetotal_in_response(api_client):
    language = LanguageFactory(pk="fi", service_language=True)

    with translation.override(language.pk):
        registration = RegistrationFactory(event__name="Foo")

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreMerchantFactory(registration=registration)
    RegistrationWebStoreAccountFactory(registration=registration)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    user = create_user_by_role(
        "registration_admin",
        registration.publisher,
    )
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )

    assert SignUpPayment.objects.count() == 0

    mocked_web_store_api_json = deepcopy(DEFAULT_GET_ORDER_DATA)
    del mocked_web_store_api_json["priceTotal"]

    with (
        translation.override(language.pk),
        requests_mock.Mocker() as req_mock,
    ):
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            json=mocked_web_store_api_json,
        )

        response = assert_create_signups(api_client, signups_data)

        assert req_mock.call_count == 1

    assert SignUpPayment.objects.count() == 1

    assert_default_signup_created(signups_data, user)
    assert_signup_payment_data_is_correct(
        response.data[0]["payment"],
        user,
        SignUp.objects.first(),
        service_language=language.pk,
    )

    # Payment link is sent via email.
    assert_payment_link_email_sent(
        SignUpContactPerson.objects.first(),
        SignUpPayment.objects.first(),
        expected_subject="Maksu vaaditaan ilmoittautumisen vahvistamiseksi - Foo",
        expected_text="Voit vahvistaa ilmoittautumisesi tapahtumaan <strong>Foo</strong> "
        "oheisen maksulinkin avulla. Maksulinkki vanhenee %(hours)s tunnin kuluttua."
        % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
    )


@pytest.mark.parametrize(
    "status_code, api_response, expected_error_message",
    [
        (
            status.HTTP_400_BAD_REQUEST,
            DEFAULT_CREATE_ORDER_ERROR_RESPONSE,
            f"Payment API experienced an error (code: {status.HTTP_400_BAD_REQUEST})",
        ),
        (
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {},
            f"Payment API experienced an error (code: {status.HTTP_500_INTERNAL_SERVER_ERROR})",
        ),
    ],
)
@pytest.mark.django_db
def test_create_signup_payment_web_store_api_error(
    registration, api_client, status_code, api_response, expected_error_message
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreMerchantFactory(registration=registration)
    RegistrationWebStoreAccountFactory(registration=registration)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    LanguageFactory(pk="fi", service_language=True)
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )

    assert SignUpPayment.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            status_code=status_code,
            json=api_response,
        )

        response = create_signups(api_client, signups_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == expected_error_message

        assert req_mock.call_count == 1

    assert SignUpPayment.objects.count() == 0


@pytest.mark.parametrize(
    "first_name,last_name",
    [
        ("Test", None),
        (None, "Test"),
        ("Test", ""),
        ("", "Test"),
        ("", None),
        (None, ""),
        (None, None),
        ("", ""),
    ],
)
@pytest.mark.django_db
def test_create_signup_payment_contact_person_name_missing(
    api_client, registration, first_name, last_name
):
    LanguageFactory(pk="fi", service_language=True)
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "contact_person": {
                "first_name": first_name,
                "last_name": last_name,
            },
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )

    assert SignUpPayment.objects.count() == 0

    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert SignUpPayment.objects.count() == 0

    assert response.data["signups"][0]["contact_person"][0] == (
        "Contact person's first and last name are required to make a payment."
    )


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-10")])
@pytest.mark.django_db
def test_create_signup_payment_with_zero_or_negative_price(
    api_client, registration, price
):
    LanguageFactory(pk="fi", service_language=True)
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration, price=price
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )

    assert SignUpPayment.objects.count() == 0

    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert SignUpPayment.objects.count() == 0

    assert response.data["signups"][0]["price_group"][0] == (
        "Participants must have a price group with price greater than 0 "
        "selected to make a payment."
    )


@pytest.mark.django_db
def test_create_signup_payment_signup_is_waitlisted(api_client):
    language = LanguageFactory(pk="en", service_language=True)

    registration = RegistrationFactory(
        maximum_attendee_capacity=0,
        waiting_list_capacity=1,
        event__name="Foo",
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )
    signups_data["signups"][0]["contact_person"].update(
        {
            "native_language": language.pk,
            "service_language": language.pk,
        }
    )

    assert SignUpPayment.objects.count() == 0

    assert_create_signups(api_client, signups_data)

    assert SignUpPayment.objects.count() == 0

    assert SignUp.objects.count() == 1
    assert SignUp.objects.first().attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Waiting list seat reserved - Foo"


@pytest.mark.django_db
def test_create_signup_payment_with_multiple_signups(api_client, registration):
    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    reservation = SeatReservationCodeFactory(seats=2, registration=registration)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )
    signups_data["signups"].append(
        {
            "first_name": "Mickey",
            "last_name": "Mouse",
            "extra_info": "Extra info",
            "date_of_birth": "2010-04-07",
            "phone_number": "0401111111",
            "street_address": test_street_address,
            "zipcode": "myzip1",
            "user_consent": True,
            "contact_person": {
                "first_name": "Mickey",
                "last_name": "Mouse",
                "email": test_email1,
                "phone_number": "0441111111",
                "notifications": "sms",
                "service_language": "en",
                "native_language": "en",
            },
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )

    assert SignUpPayment.objects.count() == 0

    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert SignUpPayment.objects.count() == 0

    assert response.data["signups"][0] == (
        "Only one signup is supported when creating a Talpa web store payment."
    )


@pytest.mark.django_db
def test_can_create_signups_with_empty_extra_info_and_date_of_birth(
    user, user_api_client
):
    LanguageFactory(id="fi", service_language=True)

    reservation = SeatReservationCodeFactory(seats=1)

    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signups_data = default_signups_data
    signups_data["registration"] = reservation.registration.id
    signups_data["reservation_code"] = reservation.code
    signups_data["signups"][0]["extra_info"] = ""
    signups_data["signups"][0]["date_of_birth"] = None

    assert_create_signups(user_api_client, signups_data)
    assert_default_signup_created(signups_data, user)


@pytest.mark.django_db
def test_non_authenticated_user_cannot_create_signups(api_client, registration):
    LanguageFactory(id="fi", service_language=True)
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signups_data = default_signups_data.copy()
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_non_authenticated_user_cannot_create_signups_with_payments(
    api_client, registration
):
    LanguageFactory(id="fi", service_language=True)
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    signups_data = deepcopy(default_signups_data)
    signups_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
        }
    )
    signups_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
            "create_payment": True,
        }
    )

    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_add_signups_to_group(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(id="fi", service_language=True)
    reservation = SeatReservationCodeFactory(registration=registration, seats=2)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group)

    assert signup_group.signups.count() == 1
    assert SeatReservationCode.objects.count() == 1
    assert SignUpContactPerson.objects.count() == 1

    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "signup_group": signup_group.id,
                "first_name": "Michael",
                "last_name": "Jackson",
                "date_of_birth": "2011-04-07",
                "street_address": test_street_address,
                "zipcode": "myzip1",
            },
            {
                "signup_group": signup_group.id,
                "first_name": "Mickey",
                "last_name": "Mouse",
                "date_of_birth": "1928-05-15",
                "street_address": test_street_address,
                "zipcode": "myzip1",
                "user_consent": True,
            },
        ],
    }

    assert_create_signups(api_client, signups_data)

    signup_group.refresh_from_db()
    assert signup_group.signups.count() == 3
    assert SeatReservationCode.objects.count() == 0

    new_signup = signup_group.signups.filter(first_name="Michael").first()
    assert new_signup.registration_id == registration.id
    assert new_signup.created_by_id == user.id
    assert new_signup.last_modified_by_id == user.id
    assert new_signup.created_time is not None
    assert new_signup.last_modified_time is not None
    assert new_signup.user_consent is False

    new_signup2 = signup_group.signups.filter(first_name="Mickey").first()
    assert new_signup2.registration_id == registration.id
    assert new_signup2.created_by_id == user.id
    assert new_signup2.last_modified_by_id == user.id
    assert new_signup2.created_time is not None
    assert new_signup2.last_modified_time is not None
    assert new_signup2.user_consent is True

    assert SignUpContactPerson.objects.count() == 1
    assert (
        SignUpContactPerson.objects.filter(
            signup_id__in=(new_signup.pk, new_signup2.pk)
        ).count()
        == 0
    )


@pytest.mark.parametrize("user_role", ["regular_user", "admin"])
@pytest.mark.django_db
def test_registration_user_access_cannot_signup_if_enrolment_is_not_opened(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
    )

    registration.enrolment_start_time = localtime() + timedelta(days=1)
    registration.enrolment_end_time = localtime() + timedelta(days=2)
    registration.save(update_fields=["enrolment_start_time", "enrolment_end_time"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is not yet open."


@pytest.mark.django_db
def test_non_created_event_admin_cannot_signup_if_enrolment_is_closed(
    api_client, registration
):
    user = create_user_by_role("admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.enrolment_start_time = localtime() - timedelta(days=2)
    registration.enrolment_end_time = localtime() - timedelta(days=1)
    registration.save(update_fields=["enrolment_start_time", "enrolment_end_time"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is already closed."


@pytest.mark.django_db
def test_created_event_admin_can_signup_if_enrolment_is_closed(
    api_client, registration
):
    user = create_user_by_role("admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.created_by = user
    registration.enrolment_start_time = localtime() - timedelta(days=2)
    registration.enrolment_end_time = localtime() - timedelta(days=1)
    registration.save(
        update_fields=["created_by", "enrolment_start_time", "enrolment_end_time"]
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    assert_create_signups(api_client, signups_data)


@pytest.mark.parametrize("user_role", ["superuser", "registration_admin", "admin"])
@pytest.mark.django_db
def test_superuser_or_registration_admin_can_signup_if_enrolment_is_closed(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    if user_role == "admin":
        # A user with both an event admin and a registration admin role.
        user.registration_admin_organizations.add(registration.publisher)

    api_client.force_authenticate(user)

    registration.enrolment_start_time = localtime() - timedelta(days=2)
    registration.enrolment_end_time = localtime() - timedelta(days=1)
    registration.save(update_fields=["enrolment_start_time", "enrolment_end_time"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    assert_create_signups(api_client, signups_data)


@pytest.mark.django_db
def test_substitute_user_can_signup_if_enrolment_is_closed(api_client, registration):
    user = create_user_by_role("regular_user", registration.publisher)
    user.email = hel_email
    user.save(update_fields=["email"])

    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    registration.enrolment_start_time = localtime() - timedelta(days=2)
    registration.enrolment_end_time = localtime() - timedelta(days=1)
    registration.save(update_fields=["enrolment_start_time", "enrolment_end_time"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    assert_create_signups(api_client, signups_data)


@pytest.mark.django_db
def test_cannot_signup_if_reservation_code_is_missing(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signups_payload = {
        "registration": registration.id,
        "signups": [],
    }

    response = create_signups(api_client, signups_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0].code == "required"


@pytest.mark.django_db
def test_amount_if_signups_cannot_be_greater_than_maximum_group_size(api_client, event):
    user = create_user_by_role("registration_admin", event.publisher)
    api_client.force_authenticate(user)

    registration = RegistrationFactory(
        event=event,
        maximum_group_size=2,
        audience_max_age=None,
        audience_min_age=None,
        maximum_attendee_capacity=None,
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=3)
    code = reservation.code
    signup_payload = {
        "first_name": "Mickey",
        "last_name": "Mouse",
        "contact_person": {
            "email": "test3@test.com",
        },
    }
    signups_payload = {
        "registration": registration.id,
        "reservation_code": code,
        "signups": [signup_payload, signup_payload, signup_payload],
    }
    response = create_signups(api_client, signups_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0].code == "max_group_size"


@pytest.mark.django_db
def test_cannot_signup_if_reservation_code_is_invalid(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signups_payload = {
        "registration": registration.id,
        "reservation_code": "c5e7d3ba-e48d-447c-b24d-c779950b2acb",
        "signups": [],
    }

    response = create_signups(api_client, signups_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code doesn't exist."


@pytest.mark.django_db
def test_cannot_signup_if_reservation_code_is_for_different_registration(
    api_client, registration, registration2
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration2, seats=2)
    code = reservation.code
    signups_payload = {
        "registration": registration.id,
        "reservation_code": code,
        "signups": [],
    }

    response = create_signups(api_client, signups_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code doesn't exist."


@pytest.mark.django_db
def test_cannot_signup_if_number_of_signups_exceeds_number_reserved_seats(
    api_client, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "Mickey",
                "last_name": "Mouse",
                "contact_person": {
                    "email": "test3@test.com",
                },
            },
            {
                "first_name": "Minney",
                "last_name": "Mouse",
                "contact_person": {
                    "email": "test2@test.com",
                },
            },
        ],
    }
    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["signups"][0]
        == "Number of signups exceeds the number of requested seats"
    )


@pytest.mark.django_db
def test_cannot_signup_if_reservation_code_is_expired(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    reservation.timestamp = reservation.timestamp - timedelta(days=1)
    reservation.save()

    signups_payload = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "Mickey",
                "last_name": "Mouse",
                "date_of_birth": "2011-04-07",
                "contact_person": {
                    "email": "test3@test.com",
                },
            },
        ],
    }
    response = create_signups(api_client, signups_payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code has expired."


@pytest.mark.django_db
def test_can_signup_twice_with_same_phone_or_email(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=3)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": "2011-04-07",
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    signup_data_same_email = deepcopy(signup_data)
    signup_data_same_email["contact_person"]["phone_number"] = "0442222222"
    signup_data_same_phone = deepcopy(signup_data)
    signup_data_same_phone["contact_person"]["email"] = "another@email.com"
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data, signup_data_same_email, signup_data_same_phone],
    }

    # Create a signups
    assert_create_signups(api_client, signups_data)


@pytest.mark.parametrize("min_age", [None, 0, 10])
@pytest.mark.parametrize("max_age", [None, 0, 100])
@pytest.mark.parametrize("date_of_birth", [None, "1980-12-30"])
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_date_of_birth_is_mandatory_if_audience_min_or_max_age_specified(
    api_client, date_of_birth, min_age, max_age, organization
):
    user = create_user_by_role("registration_admin", organization)
    api_client.force_authenticate(user)

    falsy_values = ("", None)

    registration = RegistrationFactory(
        event__publisher=organization,
        maximum_attendee_capacity=1,
        audience_min_age=min_age if min_age not in falsy_values else None,
        audience_max_age=max_age if max_age not in falsy_values else None,
        enrolment_start_time=localtime(),
        enrolment_end_time=localtime() + timedelta(days=10),
    )

    if (
        min_age not in falsy_values or max_age not in falsy_values
    ) and not date_of_birth:
        expected_status = status.HTTP_400_BAD_REQUEST
        expected_error = "This field must be specified."
    else:
        expected_status = status.HTTP_201_CREATED
        expected_error = None

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }
    if date_of_birth:
        signup_data["date_of_birth"] = date_of_birth

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    response = create_signups(api_client, signups_data)
    assert response.status_code == expected_status

    if expected_error:
        assert response.data["signups"][0]["date_of_birth"][0] == expected_error


@pytest.mark.parametrize(
    "date_of_birth,expected_status,expected_error,has_event_start_time",
    [
        (
            "2004-03-13",
            status.HTTP_400_BAD_REQUEST,
            "The participant is too young.",
            False,
        ),
        (
            "2004-03-13",
            status.HTTP_201_CREATED,
            None,
            True,
        ),
        (
            "1982-03-13",
            status.HTTP_400_BAD_REQUEST,
            "The participant is too old.",
            False,
        ),
        (
            "1983-03-13",
            status.HTTP_400_BAD_REQUEST,
            "The participant is too old.",
            True,
        ),
        ("2000-02-29", status.HTTP_201_CREATED, None, False),
    ],
)
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_signup_age_has_to_match_the_audience_min_max_age(
    api_client,
    organization,
    date_of_birth,
    expected_error,
    expected_status,
    has_event_start_time,
):
    user = create_user_by_role("registration_admin", organization)
    api_client.force_authenticate(user)

    registration = RegistrationFactory(
        event__publisher=organization,
        event__start_time=(
            localtime() + timedelta(days=365) if has_event_start_time else None
        ),
        event__end_time=localtime() + timedelta(days=2 * 365),
        audience_max_age=40,
        audience_min_age=20,
        enrolment_start_time=localtime(),
        enrolment_end_time=localtime() + timedelta(days=10),
        maximum_attendee_capacity=1,
    )

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": date_of_birth,
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    response = create_signups(api_client, signups_data)

    assert response.status_code == expected_status
    if expected_error:
        assert response.data["signups"][0]["date_of_birth"][0] == expected_error


@pytest.mark.parametrize(
    "mandatory_field_id",
    [
        MandatoryFields.CITY,
        MandatoryFields.FIRST_NAME,
        MandatoryFields.LAST_NAME,
        MandatoryFields.PHONE_NUMBER,
        MandatoryFields.STREET_ADDRESS,
        MandatoryFields.ZIPCODE,
    ],
)
@pytest.mark.django_db
def test_signup_mandatory_fields_has_to_be_filled(
    api_client, mandatory_field_id, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.mandatory_fields = [mandatory_field_id]
    registration.save(update_fields=["mandatory_fields"])

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "street_address": "Street address",
        "city": "Helsinki",
        "zipcode": "00100",
        mandatory_field_id: "",
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["signups"][0][mandatory_field_id][0]
        == "This field must be specified."
    )


@pytest.mark.django_db
def test_cannot_signup_with_not_allowed_service_language(
    api_client, languages, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    languages[0].service_language = False
    languages[0].save(update_fields=["service_language"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "Michael",
                "last_name": "Jackson",
                "date_of_birth": "2011-04-07",
                "contact_person": {
                    "email": test_email1,
                    "service_language": languages[0].pk,
                },
            }
        ],
    }

    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["signups"][0]["contact_person"]["service_language"][0].code
        == "does_not_exist"
    )


@pytest.mark.django_db
def test_group_signup_successful_with_waitlist(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save()

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)
    signups_payload = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "User",
                "last_name": "1",
                "contact_person": {
                    "email": "test1@test.com",
                },
            },
            {
                "first_name": "User",
                "last_name": "2",
                "contact_person": {
                    "email": "test2@test.com",
                },
            },
        ],
    }
    assert_create_signups(api_client, signups_payload)
    assert registration.signups.count() == 2

    reservation2 = SeatReservationCodeFactory(registration=registration, seats=2)
    signups_payload = {
        "registration": registration.id,
        "reservation_code": reservation2.code,
        "signups": [
            {
                "first_name": "User",
                "last_name": "3",
                "contact_person": {
                    "email": "test3@test.com",
                },
            },
            {
                "first_name": "User",
                "last_name": "4",
                "contact_person": {
                    "email": "test4@test.com",
                },
            },
        ],
    }
    assert_create_signups(api_client, signups_payload)
    assert registration.signups.count() == 4
    assert (
        registration.signups.filter(
            attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()
        == 2
    )
    assert (
        registration.signups.filter(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST
        ).count()
        == 2
    )


@pytest.mark.parametrize(
    "maximum_attendee_capacity,waiting_list_capacity,expected_signups_count,"
    "expected_attending,expected_waitlisted,expected_status_code",
    [
        (0, 0, 0, 0, 0, status.HTTP_403_FORBIDDEN),
        (1, 1, 2, 1, 1, status.HTTP_201_CREATED),
        (1, 0, 1, 1, 0, status.HTTP_201_CREATED),
        (0, 1, 1, 0, 1, status.HTTP_201_CREATED),
        (2, 1, 2, 2, 0, status.HTTP_201_CREATED),
        (0, 2, 2, 0, 2, status.HTTP_201_CREATED),
        (None, None, 2, 2, 0, status.HTTP_201_CREATED),
        (None, 1, 2, 2, 0, status.HTTP_201_CREATED),
        (1, None, 2, 1, 1, status.HTTP_201_CREATED),
        (0, None, 2, 0, 2, status.HTTP_201_CREATED),
    ],
)
@pytest.mark.django_db
def test_maximum_attendee_and_waiting_list_capacities(
    api_client,
    maximum_attendee_capacity,
    waiting_list_capacity,
    expected_signups_count,
    expected_attending,
    expected_waitlisted,
    expected_status_code,
):
    registration = RegistrationFactory(
        maximum_attendee_capacity=maximum_attendee_capacity,
        waiting_list_capacity=waiting_list_capacity,
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)
    signups_payload = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "User",
                "last_name": "1",
                "email": "test1@test.com",
            },
            {
                "first_name": "User",
                "last_name": "2",
                "email": "test2@test.com",
            },
        ],
    }

    assert SignUp.objects.count() == 0

    response = create_signups(api_client, signups_payload)

    assert_attending_and_waitlisted_signups(
        response,
        expected_status_code,
        expected_signups_count,
        expected_attending,
        expected_waitlisted,
    )


@pytest.mark.parametrize(
    "maximum_attendee_capacity,waiting_list_capacity,expected_signups_count,"
    "expected_attending,expected_waitlisted,expected_status_code",
    [
        (0, 0, 0, 0, 0, status.HTTP_403_FORBIDDEN),
        (1, 1, 2, 1, 1, status.HTTP_201_CREATED),
        (1, 0, 1, 1, 0, status.HTTP_201_CREATED),
        (0, 1, 1, 0, 1, status.HTTP_201_CREATED),
        (2, 1, 2, 1, 1, status.HTTP_201_CREATED),
        (0, 2, 2, 0, 2, status.HTTP_201_CREATED),
        (None, None, 2, 1, 1, status.HTTP_201_CREATED),
        (None, 1, 2, 1, 1, status.HTTP_201_CREATED),
        (1, None, 2, 1, 1, status.HTTP_201_CREATED),
        (0, None, 2, 0, 2, status.HTTP_201_CREATED),
    ],
)
@pytest.mark.django_db
def test_maximum_attendee_and_waiting_list_capacities_with_attendee_status_given_in_post_data(
    api_client,
    maximum_attendee_capacity,
    waiting_list_capacity,
    expected_signups_count,
    expected_attending,
    expected_waitlisted,
    expected_status_code,
):
    registration = RegistrationFactory(
        maximum_attendee_capacity=maximum_attendee_capacity,
        waiting_list_capacity=waiting_list_capacity,
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)
    signups_payload = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "User",
                "last_name": "1",
                "email": "test1@test.com",
                "attendee_status": SignUp.AttendeeStatus.WAITING_LIST,
            },
            {
                "first_name": "User",
                "last_name": "2",
                "email": "test2@test.com",
                "attendee_status": SignUp.AttendeeStatus.ATTENDING,
            },
        ],
    }

    assert SignUp.objects.count() == 0

    response = create_signups(api_client, signups_payload)

    assert_attending_and_waitlisted_signups(
        response,
        expected_status_code,
        expected_signups_count,
        expected_attending,
        expected_waitlisted,
    )


@pytest.mark.parametrize(
    "service_language,username,expected_subject,expected_heading,expected_secondary_heading,expected_text",
    [
        (
            "en",
            "Username",
            "Registration confirmation",
            "Welcome Username",
            "Registration to the event Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the event <strong>Foo</strong>.",
        ),
        (
            "fi",
            "Käyttäjänimi",
            "Vahvistus ilmoittautumisesta",
            "Tervetuloa Käyttäjänimi",
            "Ilmoittautuminen tapahtumaan Foo on tallennettu.",
            "Onnittelut! Ilmoittautumisesi on vahvistettu tapahtumaan <strong>Foo</strong>.",
        ),
        (
            "sv",
            "Användarnamn",
            "Bekräftelse av registrering",
            "Välkommen Användarnamn",
            "Anmälan till evenemanget Foo har sparats.",
            "Grattis! Din registrering har bekräftats för evenemanget <strong>Foo</strong>.",
        ),
        (
            "en",
            None,
            "Registration confirmation",
            "Welcome",
            "Registration to the event Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the event <strong>Foo</strong>.",
        ),
        (
            "fi",
            None,
            "Vahvistus ilmoittautumisesta",
            "Tervetuloa",
            "Ilmoittautuminen tapahtumaan Foo on tallennettu.",
            "Onnittelut! Ilmoittautumisesi on vahvistettu tapahtumaan <strong>Foo</strong>.",
        ),
        (
            "sv",
            None,
            "Bekräftelse av registrering",
            "Välkommen",
            "Anmälan till evenemanget Foo har sparats.",
            "Grattis! Din registrering har bekräftats för evenemanget <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_email_sent_on_successful_signup(
    api_client,
    expected_heading,
    expected_secondary_heading,
    expected_subject,
    expected_text,
    registration,
    service_language,
    username,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(id=service_language, name=service_language, service_language=True)

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        reservation = SeatReservationCodeFactory(registration=registration, seats=1)
        signup_data = {
            "first_name": "Michael",
            "last_name": "Jackson",
            "date_of_birth": "2011-04-07",
            "contact_person": {
                "first_name": username,
                "email": test_email1,
                "service_language": service_language,
            },
        }
        signups_data = {
            "registration": registration.id,
            "reservation_code": reservation.code,
            "signups": [signup_data],
        }

        with patch(
            "registrations.models.SignUpContactPerson.create_access_code"
        ) as mocked_access_code:
            mocked_access_code.return_value = test_access_code
            response = assert_create_signups(api_client, signups_data)
            assert mocked_access_code.called is True

        assert signup_data["first_name"] in response.data[0]["first_name"]

        contact_person = SignUpContactPerson.objects.first()
        signup_edit_url = (
            f"{settings.LINKED_REGISTRATIONS_UI_URL}/{service_language}"
            f"/registration/{registration.id}/signup/{contact_person.signup_id}/edit"
            f"?access_code={test_access_code}"
        )

        #  assert that the email was sent
        message_string = str(mail.outbox[0].alternatives[0])
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_heading in message_string
        assert expected_secondary_heading in message_string
        assert expected_text in message_string
        assert signup_edit_url in message_string
        if username is None:
            assert f"{expected_heading} None" not in message_string


@pytest.mark.parametrize(
    "service_language,username,expected_subject,expected_heading,expected_secondary_heading,"
    "expected_text",
    [
        (
            "en",
            "Username",
            "Registration confirmation - Recurring: Foo",
            "Welcome Username",
            "Registration to the recurring event Foo 1 Feb 2024 - 29 Feb 2024 has been saved.",
            "Congratulations! Your registration has been confirmed for the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>.",
        ),
        (
            "fi",
            "Käyttäjänimi",
            "Vahvistus ilmoittautumisesta - Sarja: Foo",
            "Tervetuloa Käyttäjänimi",
            "Ilmoittautuminen sarjatapahtumaan Foo 1.2.2024 - 29.2.2024 on tallennettu.",
            "Onnittelut! Ilmoittautumisesi on vahvistettu sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
        (
            "sv",
            "Användarnamn",
            "Bekräftelse av registrering - Serie: Foo",
            "Välkommen Användarnamn",
            "Anmälan till serieevenemanget Foo 1.2.2024 - 29.2.2024 har sparats.",
            "Grattis! Din registrering har bekräftats för serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
        (
            "en",
            None,
            "Registration confirmation - Recurring: Foo",
            "Welcome",
            "Registration to the recurring event Foo 1 Feb 2024 - 29 Feb 2024 has been saved.",
            "Congratulations! Your registration has been confirmed for the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>.",
        ),
        (
            "fi",
            None,
            "Vahvistus ilmoittautumisesta - Sarja: Foo",
            "Tervetuloa",
            "Ilmoittautuminen sarjatapahtumaan Foo 1.2.2024 - 29.2.2024 on tallennettu.",
            "Onnittelut! Ilmoittautumisesi on vahvistettu sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
        (
            "sv",
            None,
            "Bekräftelse av registrering - Serie: Foo",
            "Välkommen",
            "Anmälan till serieevenemanget Foo 1.2.2024 - 29.2.2024 har sparats.",
            "Grattis! Din registrering har bekräftats för serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_email_sent_on_successful_signup_to_a_recurring_event(
    api_client,
    expected_heading,
    expected_secondary_heading,
    expected_subject,
    expected_text,
    service_language,
    username,
):
    LanguageFactory(id=service_language, name=service_language, service_language=True)

    with translation.override(service_language):
        now = localtime()
        registration = RegistrationFactory(
            event__start_time=now,
            event__end_time=now + timedelta(days=28),
            event__super_event_type=Event.SuperEventType.RECURRING,
            event__name="Foo",
        )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": "2011-04-07",
        "contact_person": {
            "first_name": username,
            "email": test_email1,
            "service_language": service_language,
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    with (
        translation.override(service_language),
        patch(
            "registrations.models.SignUpContactPerson.create_access_code"
        ) as mocked_access_code,
    ):
        mocked_access_code.return_value = test_access_code
        response = assert_create_signups(api_client, signups_data)
        assert mocked_access_code.called is True

    assert signup_data["first_name"] in response.data[0]["first_name"]

    contact_person = SignUpContactPerson.objects.first()
    signup_edit_url = (
        f"{settings.LINKED_REGISTRATIONS_UI_URL}/{service_language}"
        f"/registration/{registration.id}/signup/{contact_person.signup_id}/edit"
        f"?access_code={test_access_code}"
    )

    #  assert that the email was sent
    message_string = str(mail.outbox[0].alternatives[0])
    assert mail.outbox[0].subject.startswith(expected_subject)
    assert expected_heading in message_string
    assert expected_secondary_heading in message_string
    assert expected_text in message_string
    assert signup_edit_url in message_string
    if username is None:
        assert f"{expected_heading} None" not in message_string


@pytest.mark.parametrize("user_role", ["regular_user", "registration_admin"])
@pytest.mark.django_db
def test_access_code_not_sent_on_successful_signup_if_user_has_edit_rights(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    user.email = test_email1
    user.save(update_fields=["email"])
    api_client.force_authenticate(user)

    service_language = LanguageFactory(id="fi", service_language=True)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": "2011-04-07",
        "contact_person": {
            "first_name": "Test",
            "email": test_email1,
            "service_language": service_language.pk,
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    with patch(
        "registrations.models.SignUpContactPerson.create_access_code"
    ) as mocked_access_code:
        assert_create_signups(api_client, signups_data)
        assert mocked_access_code.called is False

    #  assert that the email was sent
    message_string = str(mail.outbox[0].alternatives[0])
    assert mail.outbox[0].subject.startswith("Vahvistus ilmoittautumisesta")
    assert "access_code" not in message_string


@pytest.mark.parametrize(
    "event_type,expected_heading,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "Registration to the event Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the event <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.COURSE,
            "Registration to the course Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the course <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "Registration to the volunteering Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the volunteering <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_confirmation_template_has_correct_text_per_event_type(
    api_client,
    event_type,
    expected_heading,
    expected_text,
    languages,
    registration,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "service_language": "en",
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    response = assert_create_signups(api_client, signups_data)
    assert signup_data["first_name"] in response.data[0]["first_name"]

    #  assert that the email was sent
    assert expected_heading in str(mail.outbox[0].alternatives[0])
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,confirmation_message",
    [
        ("en", "Confirmation message"),
        ("fi", "Vahvistusviesti"),
        # Use default language if confirmation message is not defined to service language
        ("sv", "Vahvistusviesti"),
    ],
)
@pytest.mark.django_db
def test_confirmation_message_is_shown_in_service_language(
    api_client,
    confirmation_message,
    languages,
    registration,
    service_language,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    Language.objects.get_or_create(
        id=service_language, defaults={"name": service_language}
    )

    registration.confirmation_message_en = "Confirmation message"
    registration.confirmation_message_fi = "Vahvistusviesti"
    registration.save()

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "service_language": service_language,
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    assert_create_signups(api_client, signups_data)
    assert confirmation_message in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_text",
    [
        (
            "en",
            "Waiting list seat reserved",
            "You have successfully registered for the event <strong>Foo</strong> waiting list.",
        ),
        (
            "fi",
            "Paikka jonotuslistalla varattu",
            "Olet onnistuneesti ilmoittautunut tapahtuman <strong>Foo</strong> jonotuslistalle.",
        ),
        (
            "sv",
            "Väntelista plats reserverad",
            "Du har framgångsrikt registrerat dig för evenemangets <strong>Foo</strong> väntelista.",
        ),
    ],
)
@pytest.mark.django_db
def test_different_email_sent_if_user_is_added_to_waiting_list(
    user_api_client,
    expected_subject,
    expected_text,
    languages,
    registration,
    service_language,
    signup,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()
        registration.maximum_attendee_capacity = 1
        registration.save()
        reservation = SeatReservationCodeFactory(registration=registration, seats=1)
        signup_data = {
            "first_name": "Michael",
            "last_name": "Jackson",
            "contact_person": {
                "email": test_email1,
                "service_language": service_language,
            },
        }
        signups_data = {
            "registration": registration.id,
            "reservation_code": reservation.code,
            "signups": [signup_data],
        }

        response = assert_create_signups(user_api_client, signups_data)
        assert signup_data["first_name"] in response.data[0]["first_name"]

        #  assert that the email was sent
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_text",
    [
        (
            "en",
            "Waiting list seat reserved - Recurring: Foo",
            "You have successfully registered for the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> waiting list.",
        ),
        (
            "fi",
            "Paikka jonotuslistalla varattu - Sarja: Foo",
            "Olet onnistuneesti ilmoittautunut sarjatapahtuman "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> jonotuslistalle.",
        ),
        (
            "sv",
            "Väntelista plats reserverad - Serie: Foo",
            "Du har framgångsrikt registrerat dig för serieevenemangets "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> väntelista.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_different_email_sent_if_user_is_added_to_waiting_list_of_a_recurring_event(
    api_client,
    service_language,
    expected_subject,
    expected_text,
):
    LanguageFactory(id=service_language, name=service_language, service_language=True)

    with translation.override(service_language):
        now = localtime()
        registration = RegistrationFactory(
            event__start_time=now,
            event__end_time=now + timedelta(days=28),
            event__super_event_type=Event.SuperEventType.RECURRING,
            event__name="Foo",
            maximum_attendee_capacity=1,
        )

    # Attending seat already reserved by this signup.
    SignUpFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "service_language": service_language,
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    with translation.override(service_language):
        response = assert_create_signups(api_client, signups_data)

    assert signup_data["first_name"] in response.data[0]["first_name"]

    #  assert that the email was sent
    assert mail.outbox[0].subject.startswith(expected_subject)
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "event_type,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "You have successfully registered for the event <strong>Foo</strong> waiting list.",
        ),
        (
            Event.TypeId.COURSE,
            "You have successfully registered for the course <strong>Foo</strong> waiting list.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "You have successfully registered for the volunteering <strong>Foo</strong> waiting list.",
        ),
    ],
)
@pytest.mark.django_db
def test_confirmation_to_waiting_list_template_has_correct_text_per_event_type(
    api_client,
    event_type,
    expected_text,
    languages,
    registration,
    signup,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()
    registration.maximum_attendee_capacity = 1
    registration.save()

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "service_language": "en",
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    response = assert_create_signups(api_client, signups_data)
    assert signup_data["first_name"] in response.data[0]["first_name"]
    #  assert that the email was sent
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "event_type,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "You have successfully registered for the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> waiting list.",
        ),
        (
            Event.TypeId.COURSE,
            "You have successfully registered for the recurring course "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> waiting list.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "You have successfully registered for the recurring volunteering "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> waiting list.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_confirmation_to_waiting_list_email_has_correct_text_per_event_type_for_a_recurring_event(
    api_client,
    event_type,
    expected_text,
):
    service_language = LanguageFactory(id="en", name="English", service_language=True)

    now = localtime()
    registration = RegistrationFactory(
        event__start_time=now,
        event__end_time=now + timedelta(days=28),
        event__super_event_type=Event.SuperEventType.RECURRING,
        event__type_id=event_type,
        event__name="Foo",
        maximum_attendee_capacity=1,
    )

    # Attending seat already reserved by this signup.
    SignUpFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "service_language": service_language.pk,
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    response = assert_create_signups(api_client, signups_data)
    assert signup_data["first_name"] in response.data[0]["first_name"]

    #  assert that the email was sent
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_signup_text_fields_are_sanitized(languages, registration, api_client):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signups_data = {
        "registration": reservation.registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "Michael <p>Html</p>",
                "last_name": "Jackson <p>Html</p>",
                "extra_info": "Extra info <p>Html</p>",
                "street_address": f"{test_street_address} <p>Html</p>",
                "zipcode": "<p>zip</p>",
                "contact_person": {
                    "phone_number": "<p>0441111111</p>",
                },
            }
        ],
    }

    response = assert_create_signups(api_client, signups_data)
    response_signup = response.data[0]
    assert response_signup["first_name"] == "Michael Html"
    assert response_signup["last_name"] == "Jackson Html"
    assert response_signup["extra_info"] == "Extra info Html"
    assert response_signup["contact_person"]["phone_number"] == "0441111111"
    assert response_signup["street_address"] == f"{test_street_address} Html"
    assert response_signup["zipcode"] == "zip"


@pytest.mark.django_db
def test_signup_id_is_audit_logged_on_post(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(pk="fi", service_language=True)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signups_data = default_signups_data
    signups_data["registration"] = registration.id
    signups_data["reservation_code"] = reservation.code

    response = assert_create_signups(api_client, signups_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data[0]["id"]
    ]


@pytest.mark.parametrize(
    "user_role",
    ["superuser", "admin", "registration_admin", "financial_admin", "regular_user"],
)
@pytest.mark.django_db
def test_can_create_signup_with_price_group(api_client, registration, user_role):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(id="fi", service_language=True)
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration, price_group__publisher=registration.publisher
    )

    signups_data = deepcopy(default_signups_data)
    signups_data["registration"] = registration.id
    signups_data["reservation_code"] = reservation.code
    signups_data["signups"][0]["price_group"] = {
        "registration_price_group": registration_price_group.pk
    }

    assert SignUp.objects.count() == 0
    assert SignUpPriceGroup.objects.count() == 0

    assert_create_signups(api_client, signups_data)

    assert SignUp.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1

    price_group = SignUpPriceGroup.objects.first()
    assert price_group.signup_id == SignUp.objects.first().pk
    assert price_group.registration_price_group_id == registration_price_group.pk
    assert price_group.price == registration_price_group.price
    assert price_group.vat_percentage == registration_price_group.vat_percentage
    assert price_group.price_without_vat == registration_price_group.price_without_vat
    assert price_group.vat == registration_price_group.vat
    for description_field in description_fields:
        assert getattr(price_group, description_field) == getattr(
            registration_price_group.price_group, description_field
        )


@pytest.mark.django_db
def test_can_create_signups_with_the_same_registration_price_group(
    api_client, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(id="fi", service_language=True)
    reservation = SeatReservationCodeFactory(registration=registration, seats=2)
    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration, price_group__publisher=registration.publisher
    )

    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "Mickey",
                "last_name": "Mouse",
                "attendee_status": SignUp.AttendeeStatus.ATTENDING,
                "price_group": {
                    "registration_price_group": registration_price_group.pk,
                },
            },
            {
                "first_name": "Donald",
                "last_name": "Duck",
                "attendee_status": SignUp.AttendeeStatus.ATTENDING,
                "price_group": {
                    "registration_price_group": registration_price_group.pk,
                },
            },
        ],
    }

    assert SignUp.objects.count() == 0
    assert SignUpPriceGroup.objects.count() == 0

    assert_create_signups(api_client, signups_data)

    assert SignUp.objects.count() == 2
    assert SignUpPriceGroup.objects.count() == 2

    common_kwargs = {
        "registration_price_group": registration_price_group.pk,
        "description_fi": registration_price_group.price_group.description_fi,
        "description_sv": registration_price_group.price_group.description_sv,
        "description_en": registration_price_group.price_group.description_en,
        "price": registration_price_group.price,
        "vat_percentage": registration_price_group.vat_percentage,
        "price_without_vat": registration_price_group.price_without_vat,
        "vat": registration_price_group.vat,
    }
    assert (
        SignUpPriceGroup.objects.filter(
            signup__first_name=signups_data["signups"][0]["first_name"], **common_kwargs
        ).count()
        == 1
    )
    assert (
        SignUpPriceGroup.objects.filter(
            signup__first_name=signups_data["signups"][1]["first_name"], **common_kwargs
        ).count()
        == 1
    )


@pytest.mark.parametrize(
    "user_role",
    ["superuser", "admin", "registration_admin", "financial_admin", "regular_user"],
)
@pytest.mark.django_db
def test_cannot_create_signup_with_another_registrations_price_group(
    api_client, registration, registration2, languages, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration2, price_group__publisher=registration2.publisher
    )

    signups_data = deepcopy(default_signups_data)
    signups_data["registration"] = registration.id
    signups_data["reservation_code"] = reservation.code
    signups_data["signups"][0]["price_group"] = {
        "registration_price_group": registration_price_group.pk
    }

    assert SignUp.objects.count() == 0
    assert SignUpPriceGroup.objects.count() == 0

    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0]["price_group"][0] == (
        "Price group is not one of the allowed price groups for this registration."
    )

    assert SignUp.objects.count() == 0
    assert SignUpPriceGroup.objects.count() == 0


@pytest.mark.parametrize(
    "user_role",
    ["superuser", "admin", "registration_admin", "financial_admin", "regular_user"],
)
@pytest.mark.django_db
def test_cannot_create_signup_without_price_group_if_registration_has_price_groups(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(id="fi", service_language=True)
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    RegistrationPriceGroupFactory(
        registration=registration, price_group__publisher=registration.publisher
    )

    signups_data = deepcopy(default_signups_data)
    signups_data["registration"] = registration.id
    signups_data["reservation_code"] = reservation.code

    assert SignUp.objects.count() == 0
    assert SignUpPriceGroup.objects.count() == 0

    response = create_signups(api_client, signups_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0]["price_group"][0] == (
        "Price group selection is mandatory for this registration."
    )

    assert SignUp.objects.count() == 0
    assert SignUpPriceGroup.objects.count() == 0


@pytest.mark.django_db
def test_not_added_to_waiting_list_if_attending_signup_is_soft_deleted(api_client):
    registration = RegistrationFactory(
        confirmation_message_en="Confirmation message",
        maximum_attendee_capacity=1,
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    soft_deleted_signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
    )
    soft_deleted_signup.soft_delete()

    service_language = LanguageFactory(id="en", service_language=True)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "contact_person": {
            "email": test_email1,
            "service_language": service_language.pk,
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }

    assert SignUp.objects.count() == 0
    assert SignUp.all_objects.count() == 1

    assert_create_signups(api_client, signups_data)

    assert len(mail.outbox) == 1
    assert registration.confirmation_message_en in str(mail.outbox[0].alternatives[0])

    assert SignUp.objects.count() == 1
    assert SignUp.all_objects.count() == 2
    assert SignUp.objects.first().attendee_status == SignUp.AttendeeStatus.ATTENDING
