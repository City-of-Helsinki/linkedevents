from datetime import timedelta
from unittest.mock import patch
from uuid import UUID

import freezegun
import pytest
import pytz
import requests_mock
from django.conf import settings as django_settings
from django.test import override_settings
from django.utils import translation
from django.utils.timezone import localtime
from rest_framework import status

from events.models import Event, PublicationStatus
from events.tests.factories import EventFactory, LanguageFactory, PlaceFactory
from helevents.tests.factories import UserFactory
from registrations.exceptions import WebStoreAPIError, WebStoreRefundValidationError
from registrations.tests.factories import (
    RegistrationWebStoreProductMappingFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpPaymentFactory,
    SignUpPriceGroupFactory,
    WebStoreMerchantFactory,
)
from registrations.utils import (
    cancel_web_store_order,
    create_events_ics_file_content,
    create_or_update_web_store_merchant,
    create_web_store_api_order,
    create_web_store_product_accounting,
    create_web_store_product_mapping,
    create_web_store_refunds,
    get_access_code_for_contact_person,
    get_checkout_url_with_lang_param,
    get_web_store_order,
    get_web_store_order_status,
    get_web_store_payment,
    get_web_store_payment_status,
    get_web_store_refund_payment_status,
    get_web_store_refund_payments,
)
from web_store.order.enums import WebStoreOrderRefundStatus, WebStoreOrderStatus
from web_store.payment.enums import WebStorePaymentStatus
from web_store.tests.merchant.test_web_store_merchant_api_client import (
    DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
    DEFAULT_MERCHANT_ID,
)
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_CANCEL_ORDER_DATA,
    DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE,
    DEFAULT_GET_ORDER_DATA,
    DEFAULT_ORDER_ID,
    DEFAULT_REFUND_ID,
)
from web_store.tests.payment.test_web_store_payment_api_client import (
    DEFAULT_GET_PAYMENT_DATA,
    DEFAULT_GET_REFUND_PAYMENTS_DATA,
)
from web_store.tests.product.test_web_store_product_api_client import (
    DEFAULT_GET_PRODUCT_ACCOUNTING_DATA,
    DEFAULT_GET_PRODUCT_MAPPING_DATA,
    DEFAULT_PRODUCT_ID,
)

_COMMON_WEB_STORE_EXCEPTION_STATUS_CODES = [
    status.HTTP_400_BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_500_INTERNAL_SERVER_ERROR,
]


def _get_checkout_url_and_language_code_test_params():
    test_params = []

    for lang_code in ["fi", "sv", "en"]:
        for checkout_url, param_prefix in [
            ("https://checkout.dev/v1/123/?user=abcdefg", "&"),
            ("https://logged-in-checkout.dev/v1/123/", "?"),
        ]:
            test_params.append(
                (
                    checkout_url,
                    lang_code,
                    f"{checkout_url}{param_prefix}lang={lang_code}",
                )
            )

    return test_params


def assert_ics_file_cannot_be_created_without_start_time(event):
    with pytest.raises(
        ValueError,
        match="Event doesn't have start_time or name. Ics file cannot be created.",
    ):
        create_events_ics_file_content([event])


def assert_ics_file_cannot_be_created_without_name(event):
    with pytest.raises(
        ValueError,
        match="Event doesn't have start_time or name. Ics file cannot be created.",
    ):
        create_events_ics_file_content([event])


@pytest.mark.django_db
def test_ics_file_cannot_be_created_without_start_time():
    event = EventFactory(start_time=None)
    assert_ics_file_cannot_be_created_without_start_time(event)


@pytest.mark.django_db
def test_recurring_event_ics_file_cannot_be_created_without_start_time():
    recurring_event = EventFactory(super_event_type=Event.SuperEventType.RECURRING)

    now = localtime()
    EventFactory(
        super_event=recurring_event,
        start_time=now,
    )
    EventFactory(
        super_event=recurring_event,
        start_time=None,
    )
    EventFactory(
        super_event=recurring_event,
        start_time=now,
    )

    assert_ics_file_cannot_be_created_without_start_time(recurring_event)


@pytest.mark.freeze_time("2024-01-01")
@pytest.mark.django_db
def test_ics_file_cannot_be_created_without_name():
    event = EventFactory(start_time=localtime(), name_fi=None)
    assert_ics_file_cannot_be_created_without_name(event)


@pytest.mark.django_db
def test_recurring_event_ics_file_cannot_be_created_without_name():
    recurring_event = EventFactory(super_event_type=Event.SuperEventType.RECURRING)

    now = localtime()
    EventFactory(
        super_event=recurring_event,
        start_time=now,
        name_fi="Sub-event 1",
    )
    EventFactory(super_event=recurring_event, start_time=now, name_fi=None)
    EventFactory(
        super_event=recurring_event,
        start_time=now,
        name_fi="Sub-event 3",
    )

    assert_ics_file_cannot_be_created_without_name(recurring_event)


@pytest.mark.freeze_time("2024-01-01")
@pytest.mark.django_db
def test_create_ics_file_content():
    event = EventFactory(
        id="helsinki:123",
        name_fi="Event name",
        short_description_fi="Event description",
        location=PlaceFactory(
            name_fi="Place name",
            street_address_fi="Streen address",
            address_locality_fi="Helsinki",
        ),
        start_time=localtime(),
        end_time=localtime() + timedelta(days=10),
    )

    ics = create_events_ics_file_content([event])
    assert (
        ics
        == b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//linkedevents.hel.fi//NONSGML "
        b"API//EN\r\nBEGIN:VEVENT\r\nSUMMARY:Event "
        b"name\r\nDTSTART;TZID=Europe/Helsinki:20240101T020000\r\nDTEND;TZID=Europe/Helsinki"
        b":20240111T020000\r\nDESCRIPTION:Event description\r\nLOCATION:Place name\\, "
        b"Streen address\\, Helsinki\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )


@pytest.mark.freeze_time("2024-06-01")
@pytest.mark.django_db
def test_create_recurring_event_ics_file_content():
    recurring_event = EventFactory(
        id="helsinki:023", super_event_type=Event.SuperEventType.RECURRING
    )

    now = localtime()

    # 1st June 2024
    EventFactory(
        super_event=recurring_event,
        id="helsinki:123",
        name_fi="Event 1",
        short_description_fi="Event description 1",
        location=PlaceFactory(
            name_fi="Place name 1",
            street_address_fi="Street address 1",
            address_locality_fi="Helsinki",
        ),
        start_time=now,
        end_time=now + timedelta(days=1),
    )

    # 9th June 2024
    EventFactory(
        super_event=recurring_event,
        id="helsinki:223",
        name_fi="Event 2",
        short_description_fi="Event description 2",
        location=PlaceFactory(
            name_fi="Place name 2",
            street_address_fi="Street address 2",
            address_locality_fi="Vantaa",
        ),
        start_time=now + timedelta(days=8),
        end_time=now + timedelta(days=9),
    )

    # 16th June 2024
    EventFactory(
        super_event=recurring_event,
        id="helsinki:323",
        name_fi="Event 3",
        short_description_fi="Event description 3",
        location=PlaceFactory(
            name_fi="Place name 3",
            street_address_fi="Street address 3",
            address_locality_fi="Espoo",
        ),
        start_time=now + timedelta(days=15),
        end_time=now + timedelta(days=16),
    )

    sub_events = recurring_event.sub_events.filter(
        deleted=False,
        event_status=Event.Status.SCHEDULED,
        publication_status=PublicationStatus.PUBLIC,
    )

    ics = create_events_ics_file_content(sub_events)
    assert (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//linkedevents.hel.fi//NONSGML "
        b"API//EN\r\nBEGIN:VEVENT\r\nSUMMARY:Event 1\r\n"
        b"DTSTART;TZID=Europe/Helsinki:20240601T030000\r\nDTEND;TZID=Europe/Helsinki"
        b":20240602T030000\r\nDESCRIPTION:Event description 1\r\n"
        b"LOCATION:Place name 1\\, Street address 1\\, "
        b"Helsinki\r\nEND:VEVENT\r\n"
        b"BEGIN:VEVENT\r\nSUMMARY:Event 2\r\n"
        b"DTSTART;TZID=Europe/Helsinki:20240609T030000\r\nDTEND;TZID=Europe/Helsinki"
        b":20240610T030000\r\nDESCRIPTION:Event description 2\r\n"
        b"LOCATION:Place name 2\\, Street address 2\\, "
        b"Vantaa\r\nEND:VEVENT\r\n"
        b"BEGIN:VEVENT\r\nSUMMARY:Event 3\r\n"
        b"DTSTART;TZID=Europe/Helsinki:20240616T030000\r\nDTEND;TZID=Europe/Helsinki"
        b":20240617T030000\r\nDESCRIPTION:Event description 3\r\n"
        b"LOCATION:Place name 3\\, Street address 3\\, "
        b"Espoo\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    ) == ics


@pytest.mark.freeze_time("2024-01-01")
@pytest.mark.django_db
def test_create_ics_file_content_with_start_time_as_end_time():
    event = EventFactory(
        id="helsinki:123",
        name_fi="Event name",
        short_description_fi="Event description",
        location=PlaceFactory(
            name_fi="Place name",
            street_address_fi="Streen address",
            address_locality_fi="Helsinki",
        ),
        start_time=localtime(),
        end_time=None,
    )

    ics = create_events_ics_file_content([event])
    assert (
        ics
        == b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//linkedevents.hel.fi//NONSGML "
        b"API//EN\r\nBEGIN:VEVENT\r\nSUMMARY:Event name\r\nDTSTART;TZID=Europe/"
        b"Helsinki:20240101T020000\r\nDTEND;TZID=Europe/Helsinki"
        b":20240101T020000\r\nDESCRIPTION:Event description\r\nLOCATION:Place name\\, "
        b"Streen address\\, Helsinki\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )


@pytest.mark.parametrize(
    "language,name_value,expected_fallback_language",
    [
        ("fi", "Event name", "en"),
        ("fi", "Evenemangets namn", "sv"),
        ("sv", "Event name", "en"),
        ("sv", "Tapahtuman nimi", "fi"),
        ("en", "Tapahtuman nimi", "fi"),
        ("en", "Evenemangets namn", "sv"),
    ],
)
@pytest.mark.django_db
def test_create_ics_file_using_fallback_languages(
    language, name_value, expected_fallback_language
):
    with translation.override(expected_fallback_language):
        event = EventFactory(
            id="helsinki:123",
            name=name_value,
            short_description_fi="Event description",
            location=PlaceFactory(
                name_fi="Place name",
                street_address_fi="Streen address",
                address_locality_fi="Helsinki",
            ),
            start_time=localtime(),
            end_time=localtime() + timedelta(days=10),
        )

    assert getattr(event, f"name_{language}") is None
    assert getattr(event, f"name_{expected_fallback_language}") == name_value

    ics = create_events_ics_file_content([event], language=language)
    assert f"SUMMARY:{name_value}" in str(ics)


@pytest.mark.parametrize(
    "language,expected_fallback_language",
    [
        ("fi", "en"),
        ("sv", "en"),
        ("en", "fi"),
    ],
)
@pytest.mark.django_db
def test_create_ics_file_correct_fallback_language_used_if_event_name_is_none(
    language, expected_fallback_language
):
    event = EventFactory(
        id="helsinki:123",
        name=None,
        short_description_fi="Event description",
        location=PlaceFactory(
            name_fi="Place name",
            street_address_fi="Streen address",
            address_locality_fi="Helsinki",
        ),
        start_time=localtime(),
        end_time=localtime() + timedelta(days=10),
    )

    assert getattr(event, f"name_{language}") is None
    assert getattr(event, f"name_{expected_fallback_language}") is None

    with (
        pytest.raises(
            ValueError,
            match="Event doesn't have start_time or name. Ics file cannot be created.",
        ),
        patch("django.utils.translation.override") as mocked_translation_override,
    ):
        create_events_ics_file_content([event], language=language)

        mocked_translation_override.assert_called_with(expected_fallback_language)


@pytest.mark.parametrize(
    "has_contact_person,has_user,expected_access_code_type",
    [
        (True, True, str),
        (True, False, str),
        (False, True, None),
        (False, False, None),
    ],
)
@pytest.mark.django_db
def test_get_access_code_for_contact_person(
    has_contact_person, has_user, expected_access_code_type
):
    contact_person = (
        SignUpContactPersonFactory(
            signup=SignUpFactory(),
            email="test@test.com",
        )
        if has_contact_person
        else None
    )
    user = UserFactory() if has_user else None

    access_code = get_access_code_for_contact_person(contact_person, user)

    if expected_access_code_type is str:
        assert str(UUID(access_code)) == access_code
    else:
        assert access_code is None


@pytest.mark.parametrize(
    "checkout_url, lang_code, expected_checkout_url",
    _get_checkout_url_and_language_code_test_params(),
)
def test_get_checkout_url_with_lang_param(
    checkout_url, lang_code, expected_checkout_url
):
    new_checkout_url = get_checkout_url_with_lang_param(checkout_url, lang_code)

    assert new_checkout_url == expected_checkout_url
    assert checkout_url != new_checkout_url


@pytest.mark.parametrize(
    "order_id",
    [DEFAULT_ORDER_ID, "1234"],
)
def test_get_web_store_order(order_id):
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/admin/{order_id}",
            json=DEFAULT_GET_ORDER_DATA,
        )

        order_response_json = get_web_store_order(order_id)

        assert req_mock.call_count == 1

    assert order_response_json == DEFAULT_GET_ORDER_DATA


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_get_web_store_order_request_exception(status_code):
    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError) as exc_info,
    ):
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/admin/{DEFAULT_ORDER_ID}",
            status_code=status_code,
        )

        get_web_store_order(DEFAULT_ORDER_ID)

        assert req_mock.call_count == 1

    assert exc_info.value.args[1] == status_code


@pytest.mark.parametrize(
    "order_id",
    [DEFAULT_ORDER_ID, "1234"],
)
def test_get_web_store_payment(order_id):
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/{order_id}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )

        order_response_json = get_web_store_payment(order_id)

        assert req_mock.call_count == 1

    assert order_response_json == DEFAULT_GET_PAYMENT_DATA


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_get_web_store_payment_request_exception(status_code):
    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError) as exc_info,
    ):
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/{DEFAULT_ORDER_ID}",
            status_code=status_code,
        )

        get_web_store_payment(DEFAULT_ORDER_ID)

        assert req_mock.call_count == 1

    assert exc_info.value.args[1] == status_code


@pytest.mark.parametrize("order_id", [DEFAULT_ORDER_ID, "1234"])
@pytest.mark.parametrize(
    "order_status", [order_status.value for order_status in WebStoreOrderStatus]
)
def test_get_web_store_order_status(order_id, order_status):
    order_response_json = DEFAULT_GET_ORDER_DATA.copy()
    order_response_json["status"] = order_status

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/admin/{order_id}",
            json=order_response_json,
        )

        order_status = get_web_store_order_status(order_id)

        assert req_mock.call_count == 1

    assert order_response_json["status"] == order_status


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_get_web_store_order_status_request_exception(status_code):
    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError) as exc_info,
    ):
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/admin/{DEFAULT_ORDER_ID}",
            status_code=status_code,
        )

        get_web_store_order_status(DEFAULT_ORDER_ID)

        assert req_mock.call_count == 1

    assert exc_info.value.args[1] == status_code


@pytest.mark.parametrize("order_id", [DEFAULT_ORDER_ID, "1234"])
@pytest.mark.parametrize(
    "payment_status", [payment_status.value for payment_status in WebStorePaymentStatus]
)
def test_get_web_store_payment_status(order_id, payment_status):
    payment_response_json = DEFAULT_GET_PAYMENT_DATA.copy()
    payment_response_json["status"] = payment_status

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/{order_id}",
            json=payment_response_json,
        )

        payment_status = get_web_store_payment_status(order_id)

        assert req_mock.call_count == 1

    assert payment_response_json["status"] == payment_status


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_get_web_store_payment_status_request_exception(status_code):
    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError) as exc_info,
    ):
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/{DEFAULT_ORDER_ID}",
            status_code=status_code,
        )

        get_web_store_payment_status(DEFAULT_ORDER_ID)

        assert req_mock.call_count == 1

    assert exc_info.value.args[1] == status_code


@pytest.mark.parametrize("refund_id", [DEFAULT_REFUND_ID, "1234"])
def test_get_web_store_refund_payments(refund_id):
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/refunds/{refund_id}/payment",
            json=DEFAULT_GET_REFUND_PAYMENTS_DATA,
        )

        payments = get_web_store_refund_payments(refund_id)

        assert req_mock.call_count == 1

    assert len(payments) == 1
    assert payments[0] == DEFAULT_GET_REFUND_PAYMENTS_DATA[0]


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_get_web_store_refund_payments_request_exception(status_code):
    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError) as exc_info,
    ):
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/refunds/"
            f"{DEFAULT_REFUND_ID}/payment",
            status_code=status_code,
        )

        get_web_store_refund_payments(DEFAULT_REFUND_ID)

        assert req_mock.call_count == 1

    assert exc_info.value.args[1] == status_code


@pytest.mark.parametrize("refund_id", [DEFAULT_REFUND_ID, "1234"])
@pytest.mark.parametrize(
    "payment_status",
    [payment_status.value for payment_status in WebStoreOrderRefundStatus],
)
def test_get_web_store_refund_payment_status(refund_id, payment_status):
    payment_response_json = [DEFAULT_GET_REFUND_PAYMENTS_DATA[0].copy()]
    payment_response_json[0]["status"] = payment_status

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/refunds/{refund_id}/payment",
            json=payment_response_json,
        )

        payment_status = get_web_store_refund_payment_status(refund_id)

        assert req_mock.call_count == 1

    assert payment_response_json[0]["status"] == payment_status


def test_get_web_store_refund_payment_status_none():
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/refunds/"
            f"{DEFAULT_REFUND_ID}/payment",
            json=[],
        )

        payment_status = get_web_store_refund_payment_status(DEFAULT_REFUND_ID)

        assert req_mock.call_count == 1

    assert payment_status is None


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_get_web_store_refund_payment_status_request_exception(status_code):
    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError) as exc_info,
    ):
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/refunds/"
            f"{DEFAULT_REFUND_ID}/payment",
            status_code=status_code,
        )

        get_web_store_refund_payment_status(DEFAULT_REFUND_ID)

        assert req_mock.call_count == 1

    assert exc_info.value.args[1] == status_code


@pytest.mark.django_db
def test_create_web_store_api_order():
    signup = SignUpFactory()

    SignUpPriceGroupFactory(signup=signup)
    contact_person = SignUpContactPersonFactory(signup=signup)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(
            registration=signup.registration,
        )

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/",
            json=DEFAULT_GET_ORDER_DATA,
        )

        resp_json = create_web_store_api_order(signup, contact_person, localtime())
        assert resp_json == DEFAULT_GET_ORDER_DATA

        assert req_mock.call_count == 1


@pytest.mark.parametrize(
    "created_by, user_uuid",
    [
        (None, str(None)),
        (UserFactory, "123e4567-e89b-12d3-a456-426614174000"),
    ],
)
@pytest.mark.django_db
def test_create_web_store_api_order_created_by(created_by, user_uuid):
    signup = SignUpFactory(
        created_by=created_by(uuid=user_uuid) if created_by else None
    )

    SignUpPriceGroupFactory(signup=signup)
    contact_person = SignUpContactPersonFactory(signup=signup)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(
            registration=signup.registration,
        )

    with patch(
        "web_store.order.clients.WebStoreOrderAPIClient.create_order"
    ) as mocked_create_order:
        create_web_store_api_order(signup, contact_person, localtime())

        assert mocked_create_order.called is True
        assert mocked_create_order.call_args[0][0]["user"] == user_uuid


@pytest.mark.parametrize(
    "contact_person, language_code, customer_data_type",
    [
        (None, "fi", type(None)),
        (SignUpContactPersonFactory, "en", dict),
    ],
)
@pytest.mark.django_db
def test_create_web_store_api_order_contact_person(
    contact_person, language_code, customer_data_type
):
    signup = SignUpFactory()

    SignUpPriceGroupFactory(signup=signup)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(
            registration=signup.registration,
        )

    if contact_person:
        language = LanguageFactory(pk=language_code)
        contact_person = contact_person(signup=signup, service_language=language)

    with patch(
        "web_store.order.clients.WebStoreOrderAPIClient.create_order"
    ) as mocked_create_order:
        create_web_store_api_order(signup, contact_person, localtime())

        assert mocked_create_order.called is True
        assert mocked_create_order.call_args[0][0]["language"] == language_code
        assert (
            isinstance(
                mocked_create_order.call_args[0][0].get("customer"), customer_data_type
            )
            is True
        )


@pytest.mark.parametrize(
    "expiration_datetime_timezone, expected_timestamp_string",
    [
        ("UTC", "2024-06-11T11:00:00"),
        ("Europe/Helsinki", "2024-06-11T11:00:00"),
    ],
)
@freezegun.freeze_time("2024-06-11 11:00:00+03:00")
@pytest.mark.django_db
def test_create_web_store_api_order_expiration_datetime(
    expiration_datetime_timezone, expected_timestamp_string
):
    signup = SignUpFactory()

    SignUpPriceGroupFactory(signup=signup)
    contact_person = SignUpContactPersonFactory(signup=signup)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(
            registration=signup.registration,
        )

    localized_expiration_datetime = localtime().astimezone(
        pytz.timezone(expiration_datetime_timezone)
    )
    with patch(
        "web_store.order.clients.WebStoreOrderAPIClient.create_order"
    ) as mocked_create_order:
        create_web_store_api_order(
            signup, contact_person, localized_expiration_datetime
        )

        assert mocked_create_order.called is True
        assert (
            mocked_create_order.call_args[0][0]["lastValidPurchaseDateTime"]
            == expected_timestamp_string
        )


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
@pytest.mark.django_db
def test_create_web_store_api_order_request_exception(status_code):
    signup = SignUpFactory()

    SignUpPriceGroupFactory(signup=signup)
    contact_person = SignUpContactPersonFactory(signup=signup)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(
            registration=signup.registration,
        )

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError),
    ):
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/",
            status_code=status_code,
        )

        create_web_store_api_order(signup, contact_person, localtime())

        assert req_mock.call_count == 1


@pytest.mark.parametrize(
    "account_data",
    [
        # Mandatory data
        {
            "vatCode": "47",
            "balanceProfitCenter": "1234567890",
            "companyCode": "1234",
            "mainLedgerAccount": "123456",
        },
        # With optional data
        {
            "vatCode": "47",
            "balanceProfitCenter": "1234567890",
            "companyCode": "1234",
            "mainLedgerAccount": "123456",
            "internalOrder": "0987654321",
            "profitCenter": "7654321",
            "project": "1234560987654321",
            "operationArea": "654321",
        },
    ],
)
def test_create_web_store_product_accounting(account_data):
    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}product/{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_ACCOUNTING_DATA,
        )

        resp_json = create_web_store_product_accounting(
            DEFAULT_PRODUCT_ID, account_data
        )
        assert resp_json == DEFAULT_GET_PRODUCT_ACCOUNTING_DATA

        assert req_mock.call_count == 1


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_create_web_store_product_accounting_request_exception(status_code):
    account_data = {
        "vatCode": "47",
        "balanceProfitCenter": "1234567890",
        "companyCode": "1234",
        "mainLedgerAccount": "123456",
    }

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError),
    ):
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}product/{DEFAULT_PRODUCT_ID}/accounting",
            status_code=status_code,
        )

        create_web_store_product_accounting(DEFAULT_PRODUCT_ID, account_data)

        assert req_mock.call_count == 1


@pytest.mark.django_db
def test_cancel_web_store_order():
    payment = SignUpPaymentFactory(
        external_order_id=DEFAULT_ORDER_ID, created_by=UserFactory()
    )

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/{DEFAULT_ORDER_ID}/cancel",
            json=DEFAULT_CANCEL_ORDER_DATA,
        )

        resp_json = cancel_web_store_order(payment)
        assert resp_json == DEFAULT_CANCEL_ORDER_DATA

        assert req_mock.call_count == 1


@pytest.mark.django_db
def test_cancel_web_store_order_created_by():
    payment = SignUpPaymentFactory(
        external_order_id=DEFAULT_ORDER_ID, created_by=UserFactory()
    )

    with patch(
        "web_store.order.clients.WebStoreOrderAPIClient.cancel_order"
    ) as mocked_cancel_order:
        cancel_web_store_order(payment)

        assert mocked_cancel_order.call_args[1]["user_uuid"] == str(
            payment.created_by.uuid
        )


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
@pytest.mark.django_db
def test_cancel_web_store_order_request_exception(status_code):
    payment = SignUpPaymentFactory(
        external_order_id=DEFAULT_ORDER_ID, created_by=UserFactory()
    )

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError),
    ):
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/{DEFAULT_ORDER_ID}/cancel",
            status_code=status_code,
        )

        cancel_web_store_order(payment)

        assert req_mock.call_count == 1


def test_create_web_store_product_mapping():
    product_mapping_data = {
        "namespace": django_settings.WEB_STORE_API_NAMESPACE,
        "namespaceEntityId": "1",
        "merchantId": DEFAULT_MERCHANT_ID,
    }

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}product/",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        resp_json = create_web_store_product_mapping(product_mapping_data)
        assert resp_json == DEFAULT_GET_PRODUCT_MAPPING_DATA

        assert req_mock.call_count == 1


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_create_web_store_product_mapping_request_exception(status_code):
    product_mapping_data = {
        "namespace": django_settings.WEB_STORE_API_NAMESPACE,
        "namespaceEntityId": "1",
        "merchantId": DEFAULT_MERCHANT_ID,
    }

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError),
    ):
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}product/",
            status_code=status_code,
        )

        create_web_store_product_mapping(product_mapping_data)

        assert req_mock.call_count == 1


def test_create_web_store_refunds():
    orders_data = [
        {
            "orderId": DEFAULT_ORDER_ID,
            "items": [
                {
                    "orderItemId": "a30328ca-a756-4ecc-a4c4-59af874a2c8a",
                    "quantity": 1,
                },
            ],
        }
    ]

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json=DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE,
        )

        resp_json = create_web_store_refunds(orders_data)
        assert resp_json == DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE

        assert req_mock.call_count == 1


def test_create_web_store_refunds_with_errors():
    orders_data = [
        {
            "orderId": DEFAULT_ORDER_ID,
            "items": [
                {
                    "orderItemId": "a30328ca-a756-4ecc-a4c4-59af874a2c8a",
                    "quantity": 1,
                },
            ],
        }
    ]

    response_data = DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE.copy()
    response_data["errors"] = [
        {"code": "validation-error", "message": "Refund validation error"},
    ]

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreRefundValidationError),
    ):
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json=response_data,
        )

        create_web_store_refunds(orders_data)

        assert req_mock.call_count == 1


def test_create_web_store_refunds_with_partial_errors():
    orders_data = [
        {
            "orderId": DEFAULT_ORDER_ID,
            "items": [
                {
                    "orderItemId": "a30328ca-a756-4ecc-a4c4-59af874a2c8a",
                    "quantity": 1,
                },
            ],
        },
        {
            "orderId": "e9c7b7e4-12fd-4c39-94b1-5e11b4cbb239",
            "items": [
                {
                    "orderItemId": "56f7d830-13d1-4277-b282-dc61f1f0671a",
                    "quantity": 1,
                },
            ],
        },
    ]

    response_data = DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE.copy()
    response_data["errors"] = [
        {"code": "validation-error", "message": "Refund validation error"},
    ]

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json=response_data,
        )

        resp_json = create_web_store_refunds(orders_data)
        assert resp_json == response_data

        assert req_mock.call_count == 1


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
def test_create_web_store_refunds_request_exception(status_code):
    orders_data = [
        {
            "orderId": DEFAULT_ORDER_ID,
            "items": [
                {
                    "orderItemId": "a30328ca-a756-4ecc-a4c4-59af874a2c8a",
                    "quantity": 1,
                },
            ],
        }
    ]

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError),
    ):
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            status_code=status_code,
        )

        create_web_store_refunds(orders_data)

        assert req_mock.call_count == 1


@pytest.mark.django_db
def test_create_or_update_web_store_merchant_create():
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        new_merchant = WebStoreMerchantFactory()
    assert new_merchant.merchant_id == ""

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/create/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}",
            json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
        )

        create_or_update_web_store_merchant(new_merchant, True)

        assert req_mock.call_count == 1

    new_merchant.refresh_from_db()
    assert new_merchant.merchant_id == DEFAULT_MERCHANT_ID


@pytest.mark.django_db
def test_create_or_update_web_store_merchant_update():
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        new_merchant = WebStoreMerchantFactory(merchant_id=DEFAULT_MERCHANT_ID)

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{DEFAULT_MERCHANT_ID}",
            json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
        )

        create_or_update_web_store_merchant(new_merchant, False)

        assert req_mock.call_count == 1

    new_merchant.refresh_from_db()
    assert new_merchant.merchant_id == DEFAULT_MERCHANT_ID


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
@pytest.mark.django_db
def test_create_or_update_web_store_merchant_create_request_exception(status_code):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        new_merchant = WebStoreMerchantFactory()

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError),
    ):
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/create/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}",
            status_code=status_code,
        )

        create_or_update_web_store_merchant(new_merchant, True)

        assert req_mock.call_count == 1


@pytest.mark.parametrize(
    "status_code",
    _COMMON_WEB_STORE_EXCEPTION_STATUS_CODES,
)
@pytest.mark.django_db
def test_create_or_update_web_store_merchant_update_request_exception(status_code):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        new_merchant = WebStoreMerchantFactory(merchant_id=DEFAULT_MERCHANT_ID)

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError),
    ):
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{DEFAULT_MERCHANT_ID}",
            status_code=status_code,
        )

        create_or_update_web_store_merchant(new_merchant, False)

        assert req_mock.call_count == 1
