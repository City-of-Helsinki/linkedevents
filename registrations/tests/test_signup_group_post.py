from copy import deepcopy
from datetime import datetime, timedelta
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
from events.models import Event
from events.tests.factories import LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import (
    MandatoryFields,
    SeatReservationCode,
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpGroupProtectedData,
    SignUpPayment,
    SignUpPriceGroup,
    web_store_price_group_meta_key,
)
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    RegistrationWebStoreAccountFactory,
    RegistrationWebStoreMerchantFactory,
    RegistrationWebStoreProductMappingFactory,
    SeatReservationCodeFactory,
    SignUpFactory,
    SignUpGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
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
test_email1 = "test@test.com"
test_email2 = "mickey@test.com"
default_signups_data = [
    {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": "2011-04-07",
        "street_address": "my street",
        "zipcode": "myzip1",
        "attendee_status": SignUp.AttendeeStatus.WAITING_LIST,
        "user_content": False,
    },
    {
        "first_name": "Mickey",
        "last_name": "Mouse",
        "date_of_birth": "1928-05-15",
        "street_address": "my street",
        "zipcode": "myzip1",
        "attendee_status": SignUp.AttendeeStatus.ATTENDING,
        "user_content": True,
    },
]
default_signup_group_data = {
    "extra_info": "Extra info for group",
    "signups": default_signups_data,
    "contact_person": {
        "first_name": "Mickey",
        "last_name": "Mouse",
        "email": test_email2,
        "phone_number": "0441111111",
        "notifications": "sms",
        "service_language": "en",
        "native_language": "en",
    },
}

# === util methods ===


def create_signup_group(api_client, signup_group_data):
    create_url = reverse("signupgroup-list")
    response = api_client.post(create_url, signup_group_data, format="json")

    return response


def assert_create_signup_group(api_client, signup_group_data):
    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_201_CREATED

    return response


def assert_contact_person_data(contact_person, contact_person_data):
    assert contact_person.phone_number == contact_person_data["phone_number"]
    assert contact_person.notifications == contact_person_data["notifications"]
    assert contact_person.native_language.pk == contact_person_data["native_language"]
    assert contact_person.service_language.pk == contact_person_data["service_language"]


def assert_signup_data(signup, signup_data, user):
    assert signup.attendee_status == signup_data["attendee_status"]
    assert signup.first_name == signup_data["first_name"]
    assert signup.last_name == signup_data["last_name"]
    assert (
        signup.date_of_birth
        == datetime.strptime(signup_data["date_of_birth"], "%Y-%m-%d").date()
    )
    assert signup.street_address == signup_data["street_address"]
    assert signup.zipcode == signup_data["zipcode"]
    assert signup.created_by_id == user.id
    assert signup.last_modified_by_id == user.id
    assert signup.created_time is not None
    assert signup.last_modified_time is not None
    assert signup.user_consent is signup_data.get("user_consent", False)


def assert_signup_group_data(signup_group, signup_group_data, reservation):
    assert signup_group.registration_id == reservation.registration_id

    assert SignUpGroupProtectedData.objects.count() == 1
    if signup_group_data["extra_info"] is None:
        assert signup_group.extra_info is None
    else:
        assert signup_group.extra_info == signup_group_data["extra_info"]


def assert_default_signup_group_created(reservation, signup_group_data, user):
    assert SignUpGroup.objects.count() == 1
    signup_group = SignUpGroup.objects.first()
    assert_signup_group_data(signup_group, signup_group_data, reservation)

    assert_contact_person_data(
        signup_group.contact_person, signup_group_data["contact_person"]
    )

    assert SignUp.objects.count() == 2
    assert (
        SignUp.objects.filter(
            registration_id=reservation.registration_id, signup_group_id=signup_group.id
        ).count()
        == 2
    )

    signup0 = SignUp.objects.filter(first_name="Michael").first()
    assert_signup_data(signup0, signup_group_data["signups"][0], user)

    signup1 = SignUp.objects.filter(first_name="Mickey").first()
    assert_signup_data(signup1, signup_group_data["signups"][1], user)

    assert SeatReservationCode.objects.count() == 0


# === tests ===


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
def test_allowed_user_roles_can_create_signup_group(
    api_client, organization, user_role
):
    if user_role == "regular_user_without_organization":
        user = UserFactory()
    else:
        user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert_create_signup_group(api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


@pytest.mark.django_db
def test_registration_substitute_user_can_create_signup_group(api_client, registration):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert_create_signup_group(api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


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
def test_allowed_user_roles_can_create_signup_group_with_payment(api_client, user_role):
    registration = RegistrationFactory(event__name="Foo")

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

    reservation = SeatReservationCodeFactory(seats=2, registration=registration)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)
    registration_price_group2 = RegistrationPriceGroupFactory(registration=registration)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
            "create_payment": True,
        }
    )
    signup_group_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )
    signup_group_data["signups"][1].update(
        {
            "price_group": {"registration_price_group": registration_price_group2.pk},
        }
    )

    order_item_id = "1234"
    order_item_id2 = "4321"

    assert SignUpPayment.objects.count() == 0
    assert (
        SignUpPriceGroup.objects.filter(
            external_order_item_id__in=(order_item_id, order_item_id2)
        ).count()
        == 0
    )

    mocked_web_store_json = deepcopy(DEFAULT_GET_ORDER_DATA)
    mocked_web_store_json["priceTotal"] = str(
        registration_price_group.price + registration_price_group2.price
    )
    mocked_web_store_json["items"] = [
        {
            "orderItemId": order_item_id,
            "meta": [
                {
                    "key": web_store_price_group_meta_key,
                }
            ],
        },
        {
            "orderItemId": order_item_id2,
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

        price_group2 = SignUpPriceGroup.objects.last()
        mocked_web_store_json["items"][1]["meta"][0]["value"] = price_group2.pk

        return mocked_web_store_json

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            status_code=status.HTTP_201_CREATED,
            json=get_response,
        )

        response = assert_create_signup_group(api_client, signup_group_data)

        assert req_mock.call_count == 1

    assert SignUpPayment.objects.count() == 1
    assert (
        SignUpPriceGroup.objects.filter(external_order_item_id=order_item_id).count()
        == 1
    )
    assert (
        SignUpPriceGroup.objects.filter(external_order_item_id=order_item_id2).count()
        == 1
    )

    assert_signup_payment_data_is_correct(
        response.data["payment"],
        user,
        signup_group=SignUpGroup.objects.first(),
        service_language="en",
    )

    # Payment link is sent via email.
    assert_payment_link_email_sent(
        SignUpContactPerson.objects.first(),
        SignUpPayment.objects.first(),
        expected_subject="Payment required for registration confirmation - Foo",
        expected_text="Please use the payment link to confirm your registration for the event "
        "<strong>Foo</strong>. The payment link expires in %(hours)s hours."
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
def test_signup_group_update_web_store_product_mapping_if_merchant_id_has_changed(
    api_client, registration, user_role
):
    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        registration_merchant = RegistrationWebStoreMerchantFactory(
            registration=registration
        )
    RegistrationWebStoreAccountFactory(registration=registration)

    registration_merchant.external_merchant_id = "1234"
    registration_merchant.save(update_fields=["external_merchant_id"])

    reservation = SeatReservationCodeFactory(seats=2, registration=registration)
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

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
            "create_payment": True,
        }
    )
    signup_group_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )
    signup_group_data["signups"][1].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )

    assert SignUpPayment.objects.count() == 0

    total_payment_amount = registration_price_group.price * 2
    mocked_web_store_json = deepcopy(DEFAULT_GET_ORDER_DATA)
    mocked_web_store_json["priceTotal"] = str(total_payment_amount)

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
            json=mocked_web_store_json,
        )

        response = assert_create_signup_group(api_client, signup_group_data)

        assert req_mock.call_count == 3

    assert SignUpPayment.objects.count() == 1

    assert_signup_payment_data_is_correct(
        response.data["payment"],
        user,
        signup_group=SignUpGroup.objects.first(),
        service_language="en",
    )


@pytest.mark.django_db
def test_can_create_signup_group_with_create_payment_as_false_in_payload(
    registration, api_client
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    reservation = SeatReservationCodeFactory(seats=2, registration=registration)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
            "create_payment": False,
        }
    )

    assert SignUpPayment.objects.count() == 0

    assert_create_signup_group(api_client, signup_group_data)

    assert SignUpPayment.objects.count() == 0


@pytest.mark.django_db
def test_create_signup_group_payment_without_pricetotal_in_response(api_client):
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

    reservation = SeatReservationCodeFactory(seats=2, registration=registration)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)
    registration_price_group2 = RegistrationPriceGroupFactory(registration=registration)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
            "create_payment": True,
        }
    )
    signup_group_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )
    signup_group_data["signups"][1].update(
        {
            "price_group": {"registration_price_group": registration_price_group2.pk},
        }
    )

    assert SignUpPayment.objects.count() == 0

    mocked_web_store_api_json = deepcopy(DEFAULT_GET_ORDER_DATA)
    del mocked_web_store_api_json["priceTotal"]

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            json=mocked_web_store_api_json,
        )

        response = assert_create_signup_group(api_client, signup_group_data)

        assert req_mock.call_count == 1

    assert SignUpPayment.objects.count() == 1

    assert_signup_payment_data_is_correct(
        response.data["payment"],
        user,
        signup_group=SignUpGroup.objects.first(),
        service_language="en",
    )

    # Payment link is sent via email.
    assert_payment_link_email_sent(
        SignUpContactPerson.objects.first(),
        SignUpPayment.objects.first(),
        expected_subject="Payment required for registration confirmation - Foo",
        expected_text="Please use the payment link to confirm your registration for the event "
        "<strong>Foo</strong>. The payment link expires in %(hours)s hours."
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
def test_create_signup_group_payment_web_store_api_error(
    registration, api_client, status_code, api_response, expected_error_message
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreMerchantFactory(registration=registration)
    RegistrationWebStoreAccountFactory(registration=registration)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    reservation = SeatReservationCodeFactory(seats=2, registration=registration)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
            "create_payment": True,
        }
    )
    signup_group_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )
    signup_group_data["signups"][1].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )

    assert SignUpPayment.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            status_code=status_code,
            json=api_response,
        )
        response = create_signup_group(api_client, signup_group_data)

        assert req_mock.call_count == 1

    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert SignUpPayment.objects.count() == 0

    assert response.data[0] == expected_error_message


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
def test_create_signup_group_payment_contact_person_name_missing(
    api_client, registration, first_name, last_name
):
    reservation = SeatReservationCodeFactory(seats=2, registration=registration)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
            "create_payment": True,
        }
    )
    signup_group_data["contact_person"].update(
        {
            "first_name": first_name,
            "last_name": last_name,
        }
    )

    signup_group_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )

    signup_group_data["signups"][1].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )

    assert SignUpPayment.objects.count() == 0

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert SignUpPayment.objects.count() == 0

    assert response.data["contact_person"][0] == (
        "Contact person's first and last name are required to make a payment."
    )


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-10")])
@pytest.mark.django_db
def test_create_signup_payment_with_zero_or_negative_price(
    api_client, registration, price
):
    reservation = SeatReservationCodeFactory(seats=2, registration=registration)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration, price=price
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
            "create_payment": True,
        }
    )
    signup_group_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )
    signup_group_data["signups"][1].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )

    assert SignUpPayment.objects.count() == 0

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert SignUpPayment.objects.count() == 0

    assert response.data["signups"][0] == (
        "Participants must have a price group with price greater than 0 "
        "selected to make a payment."
    )


@pytest.mark.parametrize("maximum_attendee_capacity", [0, 1])
@pytest.mark.django_db
def test_create_signup_group_payment_signup_is_waitlisted(
    api_client, maximum_attendee_capacity
):
    registration = RegistrationFactory(
        maximum_attendee_capacity=maximum_attendee_capacity,
        waiting_list_capacity=2 if maximum_attendee_capacity == 0 else 1,
        event__name="Foo",
    )

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreMerchantFactory(registration=registration)
    RegistrationWebStoreAccountFactory(registration=registration)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    reservation = SeatReservationCodeFactory(seats=2, registration=registration)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data.update(
        {
            "registration": registration.pk,
            "reservation_code": reservation.code,
            "create_payment": True,
        }
    )
    signup_group_data["signups"][0].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )
    signup_group_data["signups"][1].update(
        {
            "price_group": {"registration_price_group": registration_price_group.pk},
        }
    )

    assert SignUpPayment.objects.count() == 0

    mocked_web_store_api_response = deepcopy(DEFAULT_GET_ORDER_DATA)
    mocked_web_store_api_response["priceTotal"] = str(registration_price_group.price)

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            json=mocked_web_store_api_response,
        )

        assert_create_signup_group(api_client, signup_group_data)

    assert SignUpPayment.objects.count() == maximum_attendee_capacity

    if maximum_attendee_capacity:
        # Payment link is sent via email for the attending signup.
        assert_payment_link_email_sent(
            SignUpContactPerson.objects.first(),
            SignUpPayment.objects.first(),
            expected_subject="Payment required for registration confirmation - Foo",
            expected_text="Please use the payment link to confirm your registration for the event "
            "<strong>Foo</strong>. The payment link expires in %(hours)s hours."
            % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
        )
    else:
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Waiting list seat reserved - Foo"


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
def test_signup_group_maximum_attendee_and_waiting_list_capacities(
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

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0

    response = create_signup_group(api_client, signup_group_data)

    if expected_status_code == status.HTTP_403_FORBIDDEN:
        assert SignUpGroup.objects.count() == 0
    else:
        assert SignUpGroup.objects.count() == 1

    assert_attending_and_waitlisted_signups(
        response,
        expected_status_code,
        expected_signups_count,
        expected_attending,
        expected_waitlisted,
    )


@pytest.mark.parametrize(
    "signups_data", [{}, {"signups": []}, {"signups": default_signups_data}]
)
@pytest.mark.django_db
def test_cannot_create_group_without_signups_or_responsible_person(
    api_client, organization, signups_data
):
    user = create_user_by_role("registration_admin", organization)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = {
        "extra_info": "Extra info for group",
        "registration": reservation.registration_id,
        "reservation_code": reservation.code,
    }
    signup_group_data.update(signups_data)

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize(
    "contact_person_data, expected_error_message",
    [
        ({}, "This field is required."),
        (
            {"contact_person": {}},
            "Contact person information must be provided for a group.",
        ),
        ({"contact_person": None}, "This field may not be null."),
    ],
)
@pytest.mark.django_db
def test_cannot_create_group_without_contact_person(
    api_client,
    organization,
    contact_person_data,
    expected_error_message,
):
    user = create_user_by_role("registration_admin", organization)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = {
        "extra_info": "Extra info for group",
        "registration": reservation.registration_id,
        "reservation_code": reservation.code,
        "signups": default_signups_data,
    }
    signup_group_data.update(contact_person_data)

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["contact_person"][0] == expected_error_message


@pytest.mark.django_db
def test_registration_admin_can_create_signup_group_with_empty_extra_info_or_date_of_birth(
    api_client, registration
):
    LanguageFactory(id="fi", service_language=True)
    LanguageFactory(id="en", service_language=True)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SignUpGroupProtectedData.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code
    signup_group_data["extra_info"] = ""
    signup_group_data["date_of_birth"] = None

    assert_create_signup_group(api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


@pytest.mark.django_db
def test_non_authenticated_user_cannot_create_signup_group(api_client, languages):
    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0

    reservation = SeatReservationCodeFactory(seats=2)
    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0


@pytest.mark.parametrize("user_role", ["regular_user", "admin"])
@pytest.mark.django_db
def test_registration_user_access_cannot_signup_group_if_enrolment_is_not_opened(
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
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is not yet open."


@pytest.mark.django_db
def test_non_created_event_admin_cannot_signup_group_if_enrolment_is_closed(
    api_client, registration, user
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
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is already closed."


@pytest.mark.django_db
def test_created_event_admin_can_signup_group_if_enrolment_is_closed(
    api_client, registration, user
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
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    assert_create_signup_group(api_client, signup_group_data)


@pytest.mark.parametrize("user_role", ["superuser", "registration_admin", "admin"])
@pytest.mark.django_db
def test_superuser_or_registration_admin_can_signup_group_if_enrolment_is_closed(
    api_client, registration, user, user_role
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
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    assert_create_signup_group(api_client, signup_group_data)


@pytest.mark.django_db
def test_substitute_user_can_signup_group_if_enrolment_is_closed(
    api_client, registration, user
):
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
    registration.save(
        update_fields=["created_by", "enrolment_start_time", "enrolment_end_time"]
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    assert_create_signup_group(api_client, signup_group_data)


@pytest.mark.django_db
def test_cannot_signup_group_if_registration__is_missing(api_client, organization):
    user = create_user_by_role("registration_admin", organization)
    api_client.force_authenticate(user)

    signup_group_data = {
        "signups": [],
    }

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration"][0].code == "required"


@pytest.mark.django_db
def test_cannot_signup_group_if_reservation_code_is_missing(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group_data = {
        "registration": registration.id,
        "signups": [],
    }

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0].code == "required"


@pytest.mark.django_db
def test_amount_if_group_signups_cannot_be_greater_than_maximum_group_size(
    api_client, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.audience_min_age = None
    registration.audience_max_age = None
    registration.maximum_attendee_capacity = None
    registration.maximum_group_size = 2
    registration.save(
        update_fields=[
            "audience_min_age",
            "audience_max_age",
            "maximum_attendee_capacity",
            "maximum_group_size",
        ]
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=3)
    code = reservation.code
    signup_data = {
        "first_name": "Mickey",
        "last_name": "Mouse",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": code,
        "signups": [signup_data, signup_data, signup_data],
        "contact_person": {
            "email": test_email1,
        },
    }
    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0].code == "max_group_size"


@pytest.mark.django_db
def test_cannot_signup_group_if_reservation_code_is_invalid(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group_data = {
        "registration": registration.id,
        "reservation_code": "c5e7d3ba-e48d-447c-b24d-c779950b2acb",
        "signups": [],
        "contact_person": {},
    }

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code doesn't exist."


@pytest.mark.django_db
def test_cannot_signup_group_if_reservation_code_is_for_different_registration(
    api_client, registration, registration2
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration2, seats=2)
    code = reservation.code
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": code,
        "signups": [],
        "contact_person": {},
    }

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code doesn't exist."


@pytest.mark.django_db
def test_cannot_signup_group_if_number_of_signups_exceeds_number_reserved_seats(
    api_client, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "contact_person": {
            "email": test_email1,
        },
        "signups": [
            {
                "first_name": "Mickey",
                "last_name": "Mouse",
            },
            {
                "first_name": "Minney",
                "last_name": "Mouse",
            },
        ],
    }
    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["signups"][0]
        == "Number of signups exceeds the number of requested seats"
    )


@pytest.mark.django_db
def test_cannot_signup_group_if_reservation_code_is_expired(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    reservation.timestamp = reservation.timestamp - timedelta(days=1)
    reservation.save(update_fields=["timestamp"])

    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "contact_person": {
            "email": test_email1,
        },
        "signups": [
            {
                "first_name": "Mickey",
                "last_name": "Mouse",
                "date_of_birth": "2011-04-07",
            },
        ],
    }
    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code has expired."


@pytest.mark.django_db
def test_can_group_signup_twice_with_same_phone_or_email(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    # First signup
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": "2011-04-07",
    }

    contact_person_data = {
        "email": test_email1,
        "phone_number": "0441111111",
    }

    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "contact_person": contact_person_data,
        "signups": [signup_data],
    }

    assert_create_signup_group(api_client, signup_group_data)

    # Second signup
    contact_person_data_same_email = deepcopy(contact_person_data)
    contact_person_data_same_email["phone_number"] = "0442222222"

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_group_data["reservation_code"] = reservation.code
    signup_group_data["contact_person"] = contact_person_data_same_email

    assert_create_signup_group(api_client, signup_group_data)

    # Third signup
    contact_person_data_same_phone = deepcopy(contact_person_data)
    contact_person_data_same_phone["email"] = "another@email.com"

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data["reservation_code"] = reservation.code
    signup_group_data["contact_person"] = contact_person_data_same_phone

    assert_create_signup_group(api_client, signup_group_data)


@pytest.mark.parametrize("min_age", [None, 0, 10])
@pytest.mark.parametrize("max_age", [None, 0, 100])
@pytest.mark.parametrize("date_of_birth", [None, "1980-12-30"])
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_signup_group_date_of_birth_is_mandatory_if_audience_min_or_max_age_specified(
    api_client, date_of_birth, min_age, max_age, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    falsy_values = ("", None)

    # Update registration
    registration.maximum_attendee_capacity = 1
    registration.audience_min_age = None
    registration.audience_max_age = None
    registration.enrolment_start_time = localtime()
    registration.enrolment_end_time = localtime() + timedelta(days=10)

    if min_age not in falsy_values:
        registration.audience_min_age = min_age
    if max_age not in falsy_values:
        registration.audience_max_age = max_age
    registration.save()

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
    }
    if date_of_birth:
        signup_data["date_of_birth"] = date_of_birth

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }
    response = create_signup_group(api_client, signup_group_data)
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
def test_signup_group_age_has_to_match_the_audience_min_max_age(
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
    }
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }

    response = create_signup_group(api_client, signup_group_data)

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
def test_signup_group_mandatory_fields_has_to_be_filled(
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
    }
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }

    response = create_signup_group(api_client, signup_group_data)
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
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "Michael",
                "last_name": "Jackson",
                "date_of_birth": "2011-04-07",
            }
        ],
        "contact_person": {
            "email": test_email1,
            "service_language": languages[0].pk,
        },
    }

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["contact_person"]["service_language"][0].code == "does_not_exist"
    )


@pytest.mark.django_db
def test_signup_group_successful_with_waitlist(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save(
        update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
    )
    assert registration.signup_groups.count() == 0
    assert registration.signups.count() == 0

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)
    signup_group_payload = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "User",
                "last_name": "1",
            },
            {
                "first_name": "User",
                "last_name": "2",
            },
        ],
        "contact_person": {
            "email": "test1@test.com",
        },
    }
    assert_create_signup_group(api_client, signup_group_payload)
    assert registration.signup_groups.count() == 1
    assert registration.signups.count() == 2

    reservation2 = SeatReservationCodeFactory(registration=registration, seats=2)
    signup_group_payload2 = {
        "registration": registration.id,
        "reservation_code": reservation2.code,
        "signups": [
            {
                "first_name": "User",
                "last_name": "3",
            },
            {
                "first_name": "User",
                "last_name": "4",
            },
        ],
        "contact_person": {
            "email": "test4@test.com",
        },
    }
    assert_create_signup_group(api_client, signup_group_payload2)
    assert registration.signup_groups.count() == 2
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
    "service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "en",
            "Registration confirmation",
            "Group registration to the event Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the event <strong>Foo</strong>.",
        ),
        (
            "fi",
            "Vahvistus ilmoittautumisesta",
            "Ryhmäilmoittautuminen tapahtumaan Foo on tallennettu.",
            "Onnittelut! Ilmoittautumisesi on vahvistettu tapahtumaan <strong>Foo</strong>.",
        ),
        (
            "sv",
            "Bekräftelse av registrering",
            "Gruppregistrering till evenemanget Foo har sparats.",
            "Grattis! Din registrering har bekräftats för evenemanget <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_email_sent_on_successful_signup_group(
    api_client,
    expected_heading,
    expected_subject,
    expected_text,
    registration,
    service_language,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(id=service_language, name=service_language, service_language=True)
    assert SignUp.objects.count() == 0

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        reservation = SeatReservationCodeFactory(registration=registration, seats=1)
        signup_data = {
            "first_name": "Michael",
            "last_name": "Jackson",
            "date_of_birth": "2011-04-07",
        }
        signup_group_data = {
            "registration": registration.id,
            "reservation_code": reservation.code,
            "signups": [signup_data],
            "contact_person": {
                "email": test_email1,
                "service_language": service_language,
            },
        }

        with patch(
            "registrations.models.SignUpContactPerson.create_access_code"
        ) as mocked_access_code:
            mocked_access_code.return_value = test_access_code
            assert_create_signup_group(api_client, signup_group_data)
            assert mocked_access_code.called is True

        assert SignUp.objects.count() == 1
        assert SignUp.objects.first().attendee_status == SignUp.AttendeeStatus.ATTENDING

        contact_person = SignUpContactPerson.objects.first()
        signup_group_edit_url = (
            f"{settings.LINKED_REGISTRATIONS_UI_URL}/{service_language}"
            f"/registration/{registration.id}/signup-group/{contact_person.signup_group_id}/edit"
            f"?access_code={test_access_code}"
        )

        #  assert that the email was sent
        message_string = str(mail.outbox[0].alternatives[0])
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_heading in message_string
        assert expected_text in message_string
        assert signup_group_edit_url in message_string


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "en",
            "Registration confirmation - Recurring: Foo",
            "Group registration to the recurring event Foo 1 Feb 2024 - 29 Feb 2024 has been saved.",
            "Congratulations! Your registration has been confirmed for the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>.",
        ),
        (
            "fi",
            "Vahvistus ilmoittautumisesta - Sarja: Foo",
            "Ryhmäilmoittautuminen sarjatapahtumaan Foo 1.2.2024 - 29.2.2024 on tallennettu.",
            "Onnittelut! Ilmoittautumisesi on vahvistettu sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
        (
            "sv",
            "Bekräftelse av registrering - Serie: Foo",
            "Gruppregistrering till serieevenemanget Foo 1.2.2024 - 29.2.2024 har sparats.",
            "Grattis! Din registrering har bekräftats för serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_email_sent_on_successful_signup_group_to_a_recurring_event(
    api_client,
    expected_heading,
    expected_subject,
    expected_text,
    service_language,
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
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": service_language,
        },
    }

    assert SignUp.objects.count() == 0

    with (
        translation.override(service_language),
        patch(
            "registrations.models.SignUpContactPerson.create_access_code"
        ) as mocked_access_code,
    ):
        mocked_access_code.return_value = test_access_code
        assert_create_signup_group(api_client, signup_group_data)
        assert mocked_access_code.called is True

    assert SignUp.objects.count() == 1
    assert SignUp.objects.first().attendee_status == SignUp.AttendeeStatus.ATTENDING

    contact_person = SignUpContactPerson.objects.first()
    signup_group_edit_url = (
        f"{settings.LINKED_REGISTRATIONS_UI_URL}/{service_language}"
        f"/registration/{registration.id}/signup-group/{contact_person.signup_group_id}/edit"
        f"?access_code={test_access_code}"
    )

    #  assert that the email was sent
    message_string = str(mail.outbox[0].alternatives[0])
    assert mail.outbox[0].subject.startswith(expected_subject)
    assert expected_heading in message_string
    assert expected_text in message_string
    assert signup_group_edit_url in message_string


@pytest.mark.parametrize("user_role", ["regular_user", "registration_admin"])
@pytest.mark.django_db
def test_access_code_not_sent_on_successful_signup_group_if_user_has_edit_rights(
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
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": service_language.pk,
        },
    }

    with patch(
        "registrations.models.SignUpContactPerson.create_access_code"
    ) as mocked_access_code:
        assert_create_signup_group(api_client, signup_group_data)
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
            "Group registration to the event Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the event <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.COURSE,
            "Group registration to the course Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the course <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "Group registration to the volunteering Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the volunteering <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_signup_group_confirmation_template_has_correct_text_per_event_type(
    api_client,
    event_type,
    expected_heading,
    expected_text,
    languages,
    registration,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert SignUp.objects.count() == 0

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_groups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": "en",
        },
    }

    assert_create_signup_group(api_client, signup_groups_data)
    assert SignUp.objects.count() == 1
    assert SignUp.objects.first().attendee_status == SignUp.AttendeeStatus.ATTENDING

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
def test_signup_group_confirmation_message_is_shown_in_service_language(
    api_client,
    confirmation_message,
    registration,
    service_language,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(id=service_language, name=service_language, service_language=True)

    registration.confirmation_message_en = "Confirmation message"
    registration.confirmation_message_fi = "Vahvistusviesti"
    registration.save(
        update_fields=["confirmation_message_en", "confirmation_message_fi"]
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": service_language,
        },
    }

    assert_create_signup_group(api_client, signup_group_data)
    assert confirmation_message in str(mail.outbox[0].alternatives[0])


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
    registration,
    service_language,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    LanguageFactory(id=service_language, name=service_language, service_language=True)

    registration.confirmation_message_en = "Confirmation message"
    registration.confirmation_message_fi = "Vahvistusviesti"
    registration.save(
        update_fields=["confirmation_message_en", "confirmation_message_fi"]
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": service_language,
        },
    }

    assert_create_signup_group(api_client, signup_group_data)
    assert confirmation_message in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "en",
            "Waiting list seat reserved",
            "The registration for the event <strong>Foo</strong> waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the event if a place becomes available.",
        ),
        (
            "fi",
            "Paikka jonotuslistalla varattu",
            "Ilmoittautuminen tapahtuman <strong>Foo</strong> jonotuslistalle onnistui.",
            "Jonotuslistalta siirretään automaattisesti tapahtuman osallistujaksi mikäli paikka "
            "vapautuu.",
        ),
        (
            "sv",
            "Väntelista plats reserverad",
            "Registreringen till väntelistan för <strong>Foo</strong>-evenemanget lyckades.",
            "Du flyttas automatiskt över från väntelistan för att bli deltagare i evenemanget om "
            "en plats blir ledig.",
        ),
    ],
)
@pytest.mark.django_db
def test_signup_group_different_email_sent_if_user_is_added_to_waiting_list(
    api_client,
    expected_subject,
    expected_heading,
    expected_text,
    languages,
    registration,
    service_language,
    signup,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert SignUp.objects.count() == 1

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        registration.maximum_attendee_capacity = 1
        registration.save(update_fields=["maximum_attendee_capacity"])

        reservation = SeatReservationCodeFactory(registration=registration, seats=1)
        signup_data = {
            "first_name": "Michael",
            "last_name": "Jackson",
        }
        signup_group_data = {
            "registration": registration.id,
            "reservation_code": reservation.code,
            "signups": [signup_data],
            "contact_person": {
                "email": "michael@test.com",
                "service_language": service_language,
            },
        }

        assert_create_signup_group(api_client, signup_group_data)
        assert SignUp.objects.count() == 2
        assert (
            SignUp.objects.filter(first_name=signup_data["first_name"])
            .first()
            .attendee_status
            == SignUp.AttendeeStatus.WAITING_LIST
        )

        #  assert that the email was sent
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_heading in str(mail.outbox[0].alternatives[0])
        assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "en",
            "Waiting list seat reserved - Recurring: Foo",
            "The registration for the recurring event <strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>"
            " waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the event if a place becomes available.",
        ),
        (
            "fi",
            "Paikka jonotuslistalla varattu - Sarja: Foo",
            "Ilmoittautuminen sarjatapahtuman <strong>Foo 1.2.2024 - 29.2.2024</strong>"
            " jonotuslistalle onnistui.",
            "Jonotuslistalta siirretään automaattisesti tapahtuman osallistujaksi mikäli paikka "
            "vapautuu.",
        ),
        (
            "sv",
            "Väntelista plats reserverad - Serie: Foo",
            "Registreringen till väntelistan för serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> lyckades.",
            "Du flyttas automatiskt över från väntelistan för att bli deltagare i evenemanget om "
            "en plats blir ledig.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_signup_group_different_email_sent_if_user_is_added_to_waiting_list_of_a_recurring_event(
    api_client,
    service_language,
    expected_subject,
    expected_heading,
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
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": "michael@test.com",
            "service_language": service_language,
        },
    }

    assert SignUp.objects.count() == 1

    with translation.override(service_language):
        assert_create_signup_group(api_client, signup_group_data)

    assert SignUp.objects.count() == 2
    assert (
        SignUp.objects.filter(first_name=signup_data["first_name"])
        .first()
        .attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )

    #  assert that the email was sent
    assert mail.outbox[0].subject.startswith(expected_subject)
    assert expected_heading in str(mail.outbox[0].alternatives[0])
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "event_type,expected_heading,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "The registration for the event <strong>Foo</strong> waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the event if a place becomes available.",
        ),
        (
            Event.TypeId.COURSE,
            "The registration for the course <strong>Foo</strong> waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the course if a place becomes available.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "The registration for the volunteering <strong>Foo</strong> waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the volunteering if a place becomes available.",
        ),
    ],
)
@pytest.mark.django_db
def test_signup_group_confirmation_to_waiting_list_template_has_correct_text_per_event_type(
    api_client,
    event_type,
    expected_heading,
    expected_text,
    languages,
    registration,
    signup,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert SignUp.objects.count() == 1

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    registration.maximum_attendee_capacity = 1
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": "michael@test.com",
            "service_language": "en",
        },
    }

    assert_create_signup_group(api_client, signup_group_data)
    assert SignUp.objects.count() == 2
    assert (
        SignUp.objects.filter(first_name=signup_data["first_name"])
        .first()
        .attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )

    #  assert that the email was sent
    assert expected_heading in str(mail.outbox[0].alternatives[0])
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "event_type,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "The registration for the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> waiting list was successful.",
        ),
        (
            Event.TypeId.COURSE,
            "The registration for the recurring course "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> waiting list was successful.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "The registration for the recurring volunteering "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> waiting list was successful.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_group_confirmation_to_waiting_list_has_correct_text_per_event_type_for_a_recurring_event(
    api_client,
    event_type,
    expected_text,
):
    LanguageFactory(id="en", name="English", service_language=True)

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
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": "michael@test.com",
            "service_language": "en",
        },
    }

    assert SignUp.objects.count() == 1

    assert_create_signup_group(api_client, signup_group_data)

    assert SignUp.objects.count() == 2
    assert (
        SignUp.objects.filter(first_name=signup_data["first_name"])
        .first()
        .attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )

    #  assert that the email was sent
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_signup_group_text_fields_are_sanitized(languages, organization, api_client):
    user = create_user_by_role("registration_admin", organization)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=1)
    signup_group_data = {
        "extra_info": "Extra info for group <p>Html</p>",
        "signups": [
            {
                "first_name": "Michael <p>Html</p>",
                "last_name": "Jackson <p>Html</p>",
                "extra_info": "Extra info <p>Html</p>",
                "street_address": "Street address <p>Html</p>",
                "zipcode": "<p>zip</p>",
            }
        ],
        "registration": reservation.registration_id,
        "reservation_code": reservation.code,
        "contact_person": {
            "first_name": "Michael <p>Html</p>",
            "last_name": "Jackson <p>Html</p>",
            "phone_number": "<p>0441111111</p>",
        },
    }

    response = assert_create_signup_group(api_client, signup_group_data)

    response_signup = response.data["signups"][0]
    assert response.data["extra_info"] == "Extra info for group Html"
    assert response_signup["first_name"] == "Michael Html"
    assert response_signup["last_name"] == "Jackson Html"
    assert response_signup["extra_info"] == "Extra info Html"
    assert response_signup["street_address"] == "Street address Html"
    assert response_signup["zipcode"] == "zip"

    signup_group = SignUpGroup.objects.get(pk=response.data["id"])
    assert signup_group.extra_info == "Extra info for group Html"

    signup = SignUp.objects.get(pk=response_signup["id"])
    assert signup.first_name == "Michael Html"
    assert signup.last_name == "Jackson Html"
    assert signup.extra_info == "Extra info Html"
    assert signup.street_address == "Street address Html"
    assert signup.zipcode == "zip"

    contact_person = signup_group.contact_person
    assert contact_person.first_name == "Michael Html"
    assert contact_person.last_name == "Jackson Html"
    assert contact_person.phone_number == "0441111111"


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_post(api_client, registration):
    reservation = SeatReservationCodeFactory(seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    response = assert_create_signup_group(api_client, signup_group_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]


@pytest.mark.django_db
def test_can_can_create_signup_group_with_signup_price_groups(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)

    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration, price_group__publisher=registration.publisher
    )

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data["registration"] = registration.pk
    signup_group_data["reservation_code"] = reservation.code
    signup_group_data["signups"][0]["price_group"] = {
        "registration_price_group": registration_price_group.pk,
    }
    signup_group_data["signups"][1]["price_group"] = {
        "registration_price_group": registration_price_group.pk,
    }

    assert SignUp.objects.count() == 0
    assert SignUpPriceGroup.objects.count() == 0

    assert_create_signup_group(api_client, signup_group_data)

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
            signup__first_name=signup_group_data["signups"][0]["first_name"],
            **common_kwargs,
        ).count()
        == 1
    )
    assert (
        SignUpPriceGroup.objects.filter(
            signup__first_name=signup_group_data["signups"][1]["first_name"],
            **common_kwargs,
        ).count()
        == 1
    )


@pytest.mark.parametrize(
    "user_role",
    ["superuser", "admin", "registration_admin", "financial_admin", "regular_user"],
)
@pytest.mark.django_db
def test_cannot_create_signup_group_without_price_group_if_registration_has_price_groups(
    api_client, registration, languages, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    RegistrationPriceGroupFactory(
        registration=registration,
        price_group__publisher=registration.publisher,
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data["registration"] = registration.pk
    signup_group_data["reservation_code"] = reservation.code

    assert SignUpPriceGroup.objects.count() == 0

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0]["price_group"][0] == (
        "Price group selection is mandatory for this registration."
    )

    assert SignUpPriceGroup.objects.count() == 0


@pytest.mark.parametrize(
    "user_role",
    ["superuser", "admin", "registration_admin", "financial_admin", "regular_user"],
)
@pytest.mark.django_db
def test_cannot_create_signup_group_with_another_registrations_price_group(
    api_client, registration, registration2, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration2,
        price_group__publisher=registration2.publisher,
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)

    signup_group_data = deepcopy(default_signup_group_data)
    signup_group_data["registration"] = registration.pk
    signup_group_data["reservation_code"] = reservation.code
    signup_group_data["signups"][0]["price_group"] = {
        "registration_price_group": registration_price_group.pk,
    }

    assert SignUpPriceGroup.objects.count() == 0

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0]["price_group"][0] == (
        "Price group is not one of the allowed price groups for this registration."
    )

    assert SignUpPriceGroup.objects.count() == 0


@pytest.mark.django_db
def test_not_added_to_waiting_list_if_attending_signup_group_is_soft_deleted(
    api_client,
):
    registration = RegistrationFactory(
        confirmation_message_en="Confirmation message",
        maximum_attendee_capacity=1,
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    soft_deleted_signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        registration=registration,
        signup_group=soft_deleted_signup_group,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    soft_deleted_signup_group.soft_delete()

    service_language = LanguageFactory(id="en", service_language=True)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": service_language.pk,
        },
    }

    assert SignUpGroup.objects.count() == 0
    assert SignUpGroup.all_objects.count() == 1
    assert SignUp.objects.count() == 0

    assert_create_signup_group(api_client, signup_group_data)

    assert len(mail.outbox) == 1
    assert registration.confirmation_message_en in str(mail.outbox[0].alternatives[0])

    assert SignUpGroup.objects.count() == 1
    assert SignUpGroup.all_objects.count() == 2
    assert SignUp.objects.count() == 1
    assert SignUp.objects.first().attendee_status == SignUp.AttendeeStatus.ATTENDING
