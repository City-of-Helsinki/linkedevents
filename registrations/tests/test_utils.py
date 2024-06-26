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
from registrations.exceptions import WebStoreAPIError
from registrations.tests.factories import (
    RegistrationWebStoreProductMappingFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpPriceGroupFactory,
)
from registrations.utils import (
    create_events_ics_file_content,
    create_web_store_api_order,
    get_access_code_for_contact_person,
    get_checkout_url_with_lang_param,
    get_web_store_order,
    get_web_store_order_status,
    get_web_store_payment,
    get_web_store_payment_status,
    get_web_store_refund_payment_status,
)
from web_store.order.enums import WebStoreOrderRefundStatus, WebStoreOrderStatus
from web_store.payment.enums import WebStorePaymentStatus
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_GET_ORDER_DATA,
    DEFAULT_ORDER_ID,
)
from web_store.tests.payment.test_web_store_payment_api_client import (
    DEFAULT_GET_PAYMENT_DATA,
    DEFAULT_GET_REFUND_PAYMENT_DATA,
)


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
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
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
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
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
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
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
def test_get_web_store_order_status(order_id, payment_status):
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
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
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


@pytest.mark.parametrize("order_id", [DEFAULT_ORDER_ID, "1234"])
@pytest.mark.parametrize(
    "payment_status",
    [payment_status.value for payment_status in WebStoreOrderRefundStatus],
)
def test_get_web_store_refund_payment_status(order_id, payment_status):
    payment_response_json = DEFAULT_GET_REFUND_PAYMENT_DATA.copy()
    payment_response_json["status"] = payment_status

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/refund-payment/{order_id}",
            json=payment_response_json,
        )

        payment_status = get_web_store_refund_payment_status(order_id)

        assert req_mock.call_count == 1

    assert payment_response_json["status"] == payment_status


@pytest.mark.parametrize(
    "status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
)
def test_get_web_store_refund_payment_status_request_exception(status_code):
    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(WebStoreAPIError) as exc_info,
    ):
        req_mock.get(
            f"{django_settings.WEB_STORE_API_BASE_URL}payment/admin/refund-payment/"
            f"{DEFAULT_ORDER_ID}",
            status_code=status_code,
        )

        get_web_store_refund_payment_status(DEFAULT_ORDER_ID)

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
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
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
