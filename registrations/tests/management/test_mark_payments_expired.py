from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import translation
from django.utils.timezone import localtime
from rest_framework import status

from events.models import Event
from events.tests.factories import LanguageFactory
from registrations.models import SignUp, SignUpPayment
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationWebStoreProductMappingFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPaymentFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.utils import assert_payment_link_email_sent
from web_store.payment.enums import WebStorePaymentStatus
from web_store.tests.order.test_web_store_order_api_client import DEFAULT_GET_ORDER_DATA
from web_store.tests.payment.test_web_store_payment_api_client import (
    DEFAULT_GET_PAYMENT_DATA,
)
from web_store.tests.utils import get_mock_response

_CONTACT_PERSON_EMAIL = "test@test.com"
_CONTACT_PERSON2_EMAIL = "test2@test.com"
_EVENT_NAME = "Foo"


def _assert_email_sent(expected_recipient_email, expected_subject):
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to[0] == expected_recipient_email
    assert mail.outbox[0].subject == expected_subject


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_secondary_heading,expected_text",
    [
        (
            "en",
            f"Registration payment expired - {_EVENT_NAME}",
            "Registration payment expired",
            f"Registration to the event {_EVENT_NAME} has been cancelled due to an expired payment.",
            f"Your registration to the event <strong>{_EVENT_NAME}</strong> has been "
            "cancelled due no payment received within the payment period.",
        ),
        (
            "fi",
            f"Ilmoittautumismaksu vanhentunut - {_EVENT_NAME}",
            "Ilmoittautumismaksu vanhentunut",
            f"Ilmoittautuminen tapahtumaan {_EVENT_NAME} on peruttu ilmoittautumismaksun "
            f"vanhenemisen vuoksi.",
            f"Ilmoittautumisesi tapahtumaan <strong>{_EVENT_NAME}</strong> on "
            f"peruttu, koska ilmoittautumismaksua ei ole maksettu maksuajan loppuun mennessä.",
        ),
        (
            "sv",
            f"Registreringsbetalning har gått ut - {_EVENT_NAME}",
            "Registreringsbetalning har gått ut",
            f"Anmälan till evenemanget {_EVENT_NAME} har ställts in på grund av att "
            "betalningen har gått ut.",
            f"Din anmälan till evenemanget <strong>{_EVENT_NAME}</strong> har "
            "ställts in eftersom ingen betalning mottogs inom betalningsperioden.",
        ),
    ],
)
@pytest.mark.django_db
def test_mark_payments_expired(
    service_language,
    expected_subject,
    expected_heading,
    expected_secondary_heading,
    expected_text,
):
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)
    one_days_ago = now - timedelta(days=1)
    one_day_from_now = now + timedelta(days=1)

    with translation.override(service_language):
        registration = RegistrationFactory(event__name=_EVENT_NAME)
    service_lang = LanguageFactory(pk=service_language, service_language=True)

    not_marked = SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=one_day_from_now,
        external_order_id="1234",
        signup__registration=registration,
    )
    marked = SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
        signup__registration=registration,
    )
    marked2 = SignUpPaymentFactory(
        signup=None,
        signup_group=SignUpGroupFactory(registration=registration),
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=one_days_ago,
        external_order_id="5678",
    )

    contact_person = SignUpContactPersonFactory(
        signup=marked.signup, email=_CONTACT_PERSON_EMAIL, service_language=service_lang
    )
    contact_person2 = SignUpContactPersonFactory(
        signup_group=marked2.signup_group,
        email=_CONTACT_PERSON2_EMAIL,
        service_language=service_lang,
    )

    assert not_marked.status == SignUpPayment.PaymentStatus.CREATED
    assert not_marked.deleted is False
    assert not_marked.signup.deleted is False
    assert not_marked.last_modified_by is None
    not_marked_last_modified_time = not_marked.last_modified_time

    assert marked.status == SignUpPayment.PaymentStatus.CREATED
    assert marked.deleted is False
    assert marked.signup.deleted is False
    assert marked.last_modified_by is None
    marked_last_modified_time = marked.last_modified_time

    assert marked2.status == SignUpPayment.PaymentStatus.CREATED
    assert marked2.deleted is False
    assert marked2.signup_group.deleted is False
    assert marked2.last_modified_by is None
    marked2_last_modified_time = marked2.last_modified_time

    mocked_api_response = get_mock_response(status_code=status.HTTP_404_NOT_FOUND)
    with (
        patch("requests.get") as mocked_get_payment_request,
        patch("requests.post") as mocked_cancel_order_request,
    ):
        mocked_get_payment_request.return_value = mocked_api_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True
    assert mocked_cancel_order_request.called is True

    not_marked.refresh_from_db()
    assert not_marked.status == SignUpPayment.PaymentStatus.CREATED
    assert not_marked.deleted is False
    assert not_marked.signup.deleted is False
    assert not_marked.last_modified_by is None
    assert not_marked.last_modified_time == not_marked_last_modified_time

    marked.refresh_from_db()
    assert marked.status == SignUpPayment.PaymentStatus.EXPIRED
    assert marked.deleted is True
    assert marked.signup.deleted is True
    assert marked.last_modified_by is None
    assert marked.last_modified_time > marked_last_modified_time

    marked2.refresh_from_db()
    assert marked2.status == SignUpPayment.PaymentStatus.EXPIRED
    assert marked2.deleted is True
    assert marked2.signup_group.deleted is True
    assert marked2.last_modified_by is None
    assert marked2.last_modified_time > marked2_last_modified_time

    assert len(mail.outbox) == 2

    assert mail.outbox[0].to[0] == contact_person.email
    assert mail.outbox[0].subject == expected_subject
    message_html_string = str(mail.outbox[0].alternatives[0])
    assert expected_heading in message_html_string
    assert expected_secondary_heading in message_html_string
    assert expected_text in message_html_string

    assert mail.outbox[1].to[0] == contact_person2.email
    assert mail.outbox[1].subject == expected_subject
    message_html_string2 = str(mail.outbox[1].alternatives[0])
    assert expected_heading in message_html_string2
    assert expected_secondary_heading in message_html_string2
    assert expected_text in message_html_string2


@pytest.mark.parametrize(
    "event_type,expected_subject,expected_heading,expected_secondary_heading,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            f"Registration payment expired - {_EVENT_NAME}",
            "Registration payment expired",
            f"Registration to the event {_EVENT_NAME} has been cancelled due to "
            f"an expired payment.",
            f"Your registration to the event <strong>{_EVENT_NAME}</strong> has been "
            "cancelled due no payment received within the payment period.",
        ),
        (
            Event.TypeId.COURSE,
            f"Registration payment expired - {_EVENT_NAME}",
            "Registration payment expired",
            f"Registration to the course {_EVENT_NAME} has been cancelled due to "
            f"an expired payment.",
            f"Your registration to the course <strong>{_EVENT_NAME}</strong> has been "
            "cancelled due no payment received within the payment period.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            f"Registration payment expired - {_EVENT_NAME}",
            "Registration payment expired",
            f"Registration to the volunteering {_EVENT_NAME} has been cancelled due to "
            f"an expired payment.",
            f"Your registration to the volunteering <strong>{_EVENT_NAME}</strong> has been "
            "cancelled due no payment received within the payment period.",
        ),
    ],
)
@pytest.mark.django_db
def test_payment_expired_event_type(
    event_type,
    expected_subject,
    expected_heading,
    expected_secondary_heading,
    expected_text,
):
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)

    registration = RegistrationFactory(
        event__name=_EVENT_NAME, event__type_id=event_type
    )
    service_lang = LanguageFactory(pk="en", service_language=True)

    payment = SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
        signup__registration=registration,
    )

    contact_person = SignUpContactPersonFactory(
        signup=payment.signup,
        email=_CONTACT_PERSON_EMAIL,
        service_language=service_lang,
    )

    mocked_api_response = get_mock_response(status_code=status.HTTP_404_NOT_FOUND)
    with (
        patch("requests.get") as mocked_get_payment_request,
        patch("requests.post") as mocked_cancel_order_request,
    ):
        mocked_get_payment_request.return_value = mocked_api_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True
    assert mocked_cancel_order_request.called is True

    assert len(mail.outbox) == 1

    assert mail.outbox[0].to[0] == contact_person.email
    assert mail.outbox[0].subject == expected_subject
    message_html_string = str(mail.outbox[0].alternatives[0])
    assert expected_heading in message_html_string
    assert expected_secondary_heading in message_html_string
    assert expected_text in message_html_string


@pytest.mark.django_db
def test_mark_payments_expired_signup_moved_to_waitlisted_with_payment_link():
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)

    registration = RegistrationFactory(event__name=_EVENT_NAME)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(registration=registration)

    service_language = LanguageFactory(pk="en", service_language=True)

    payment = SignUpPaymentFactory(
        signup__registration=registration,
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
    )

    contact_person = SignUpContactPersonFactory(
        signup=payment.signup,
        email=_CONTACT_PERSON_EMAIL,
        service_language=service_language,
    )

    waitlisted_signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )
    contact_person2 = SignUpContactPersonFactory(
        signup=waitlisted_signup,
        first_name="Test",
        last_name="Test",
        email=_CONTACT_PERSON2_EMAIL,
        service_language=service_language,
    )
    SignUpPriceGroupFactory(signup=waitlisted_signup)

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2

    mocked_get_payment_api_response = get_mock_response(
        status_code=status.HTTP_404_NOT_FOUND
    )
    mocked_create_order_api_response = get_mock_response(
        status_code=status.HTTP_201_CREATED, json_return_value=DEFAULT_GET_ORDER_DATA
    )

    with (
        patch("requests.get") as mocked_get_payment_request,
        patch("requests.post") as mocked_create_payment_request,
    ):
        mocked_get_payment_request.return_value = mocked_get_payment_api_response
        mocked_create_payment_request.return_value = mocked_create_order_api_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True
    assert mocked_create_payment_request.called is True

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 1

    waitlisted_signup.refresh_from_db()
    assert waitlisted_signup.attendee_status == SignUp.AttendeeStatus.ATTENDING

    new_payment = SignUpPayment.objects.first()
    assert new_payment.signup_id == waitlisted_signup.pk

    assert_payment_link_email_sent(
        contact_person2,
        new_payment,
        expected_mailbox_length=2,
        expected_subject=f"Payment required for registration confirmation - {_EVENT_NAME}",
        expected_text="You have been selected to be moved from the waiting list of the event "
        "<strong>Foo</strong> to a participant. Please use the "
        "payment link to confirm your participation. The payment link expires in "
        "%(hours)s hours" % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
    )
    assert mail.outbox[1].to[0] == contact_person.email
    assert mail.outbox[1].subject == f"Registration payment expired - {_EVENT_NAME}"


@pytest.mark.django_db
def test_payment_expired_order_cancellation_api_exception():
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)

    registration = RegistrationFactory(event__name=_EVENT_NAME)
    service_lang = LanguageFactory(pk="en", service_language=True)

    payment = SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
        signup__registration=registration,
    )

    contact_person = SignUpContactPersonFactory(
        signup=payment.signup,
        email=_CONTACT_PERSON_EMAIL,
        service_language=service_lang,
    )

    mocked_api_get_response = get_mock_response(status_code=status.HTTP_404_NOT_FOUND)
    mocked_api_post_response = get_mock_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    with (
        patch("requests.get") as mocked_get_payment_request,
        patch("requests.post") as mocked_cancel_order_request,
    ):
        mocked_get_payment_request.return_value = mocked_api_get_response
        mocked_cancel_order_request.return_value = mocked_api_post_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True
    assert mocked_cancel_order_request.called is True

    _assert_email_sent(
        contact_person.email, f"Registration payment expired - {_EVENT_NAME}"
    )


@pytest.mark.django_db
def test_mark_payments_expired_payment_cancelled():
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)

    registration = RegistrationFactory(event__name=_EVENT_NAME)
    service_language = LanguageFactory(pk="en", service_language=True)

    payment = SignUpPaymentFactory(
        signup__registration=registration,
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
    )

    contact_person = SignUpContactPersonFactory(
        signup=payment.signup,
        email=_CONTACT_PERSON_EMAIL,
        service_language=service_language,
    )

    assert payment.status == SignUpPayment.PaymentStatus.CREATED
    assert payment.deleted is False
    assert payment.signup.deleted is False

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 1

    api_payment_data = DEFAULT_GET_PAYMENT_DATA.copy()
    api_payment_data["status"] = WebStorePaymentStatus.CANCELLED.value
    mocked_api_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=api_payment_data
    )
    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_api_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True

    assert SignUpPayment.objects.count() == 0
    assert SignUp.objects.count() == 0

    _assert_email_sent(contact_person.email, f"Registration cancelled - {_EVENT_NAME}")


@pytest.mark.django_db
def test_mark_payments_expired_payment_cancelled_signup_moved_to_waitlisted_with_payment_link():
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)

    registration = RegistrationFactory(event__name=_EVENT_NAME)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(registration=registration)

    service_language = LanguageFactory(pk="en", service_language=True)

    payment = SignUpPaymentFactory(
        signup__registration=registration,
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
    )

    contact_person = SignUpContactPersonFactory(
        signup=payment.signup,
        email=_CONTACT_PERSON_EMAIL,
        service_language=service_language,
    )

    waitlisted_signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )
    contact_person2 = SignUpContactPersonFactory(
        signup=waitlisted_signup,
        first_name="Test",
        last_name="Test",
        email=_CONTACT_PERSON2_EMAIL,
        service_language=service_language,
    )
    SignUpPriceGroupFactory(signup=waitlisted_signup)

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2

    api_payment_data = DEFAULT_GET_PAYMENT_DATA.copy()
    api_payment_data["status"] = WebStorePaymentStatus.CANCELLED.value
    mocked_get_payment_api_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=api_payment_data
    )
    mocked_create_order_api_response = get_mock_response(
        status_code=status.HTTP_201_CREATED, json_return_value=DEFAULT_GET_ORDER_DATA
    )

    with (
        patch("requests.get") as mocked_get_payment_request,
        patch("requests.post") as mocked_create_payment_request,
    ):
        mocked_get_payment_request.return_value = mocked_get_payment_api_response
        mocked_create_payment_request.return_value = mocked_create_order_api_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True
    assert mocked_create_payment_request.called is True

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 1

    waitlisted_signup.refresh_from_db()
    assert waitlisted_signup.attendee_status == SignUp.AttendeeStatus.ATTENDING

    new_payment = SignUpPayment.objects.first()
    assert new_payment.signup_id == waitlisted_signup.pk

    assert_payment_link_email_sent(
        contact_person2,
        new_payment,
        expected_mailbox_length=2,
        expected_subject=f"Payment required for registration confirmation - {_EVENT_NAME}",
        expected_text="You have been selected to be moved from the waiting list of the event "
        "<strong>Foo</strong> to a participant. Please use the "
        "payment link to confirm your participation. The payment link expires in "
        "%(hours)s hours" % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
    )
    assert mail.outbox[1].to[0] == contact_person.email
    assert mail.outbox[1].subject == f"Registration cancelled - {_EVENT_NAME}"


@pytest.mark.parametrize("has_contact_person", [True, False])
@pytest.mark.django_db
def test_mark_payments_expired_payment_paid(has_contact_person):
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)

    registration = RegistrationFactory(event__name=_EVENT_NAME)
    service_language = LanguageFactory(pk="en", service_language=True)

    payment = SignUpPaymentFactory(
        signup__registration=registration,
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
    )

    if has_contact_person:
        contact_person = SignUpContactPersonFactory(
            signup=payment.signup,
            email=_CONTACT_PERSON_EMAIL,
            first_name="Contact Person #1",
            service_language=service_language,
        )

    assert payment.status == SignUpPayment.PaymentStatus.CREATED
    assert payment.deleted is False
    assert payment.signup.deleted is False

    api_payment_data = DEFAULT_GET_PAYMENT_DATA.copy()
    api_payment_data["status"] = WebStorePaymentStatus.PAID.value
    mocked_api_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=api_payment_data
    )
    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_api_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True

    payment.refresh_from_db()
    assert payment.status == SignUpPayment.PaymentStatus.PAID
    assert payment.deleted is False
    assert payment.signup.deleted is False

    if has_contact_person:
        _assert_email_sent(
            contact_person.email, f"Registration confirmation - {_EVENT_NAME}"
        )
    else:
        assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_mark_payments_expired_payer_in_payment_phase():
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)
    payment_phase_timestamp = fourteen_days_ago + timedelta(minutes=1)

    payment = SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
    )

    SignUpContactPersonFactory(signup=payment.signup, email=_CONTACT_PERSON_EMAIL)

    assert payment.status == SignUpPayment.PaymentStatus.CREATED
    assert payment.deleted is False
    assert payment.signup.deleted is False

    api_payment_data = DEFAULT_GET_PAYMENT_DATA.copy()
    api_payment_data["status"] = WebStorePaymentStatus.CREATED.value
    api_payment_data["timestamp"] = payment_phase_timestamp.strftime("%Y%m%d-%H%M%S")
    mocked_api_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=api_payment_data
    )
    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_api_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True

    payment.refresh_from_db()
    assert payment.status == SignUpPayment.PaymentStatus.CREATED
    assert payment.deleted is False
    assert payment.signup.deleted is False

    assert len(mail.outbox) == 0


@pytest.mark.parametrize(
    "api_status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
)
@pytest.mark.django_db
def test_mark_payments_expired_web_store_api_exception(api_status_code):
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)

    payment = SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id="4321",
    )

    SignUpContactPersonFactory(signup=payment.signup, email=_CONTACT_PERSON_EMAIL)

    assert payment.status == SignUpPayment.PaymentStatus.CREATED
    assert payment.deleted is False
    assert payment.signup.deleted is False

    mocked_api_response = get_mock_response(status_code=api_status_code)
    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_api_response

        call_command("mark_payments_expired")

    assert mocked_get_payment_request.called is True

    payment.refresh_from_db()
    assert payment.status == SignUpPayment.PaymentStatus.CREATED
    assert payment.deleted is False
    assert payment.signup.deleted is False

    assert len(mail.outbox) == 0
