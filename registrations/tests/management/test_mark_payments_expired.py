from datetime import timedelta

import pytest
import requests_mock
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import translation
from django.utils.timezone import localtime
from freezegun import freeze_time
from rest_framework import status

from events.models import Event
from events.tests.factories import LanguageFactory
from registrations.models import SignUp, SignUpPayment
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationWebStoreAccountFactory,
    RegistrationWebStoreMerchantFactory,
    RegistrationWebStoreProductMappingFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPaymentFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.utils import assert_payment_link_email_sent
from web_store.payment.enums import WebStorePaymentStatus
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_CANCEL_ORDER_DATA,
    DEFAULT_GET_ORDER_DATA,
    DEFAULT_ORDER_ID,
)
from web_store.tests.payment.test_web_store_payment_api_client import (
    DEFAULT_GET_PAYMENT_DATA,
)

_CONTACT_PERSON_EMAIL = "test@test.com"
_CONTACT_PERSON2_EMAIL = "test2@test.com"
_EVENT_NAME = "Foo"


def _assert_email_sent(expected_recipient_email, expected_subject):
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to[0] == expected_recipient_email
    assert mail.outbox[0].subject == expected_subject


def _test_payments_expired(
    registration,
    datetime_now,
    service_language,
    expected_subject,
    expected_heading,
    expected_secondary_heading,
    expected_text,
):
    fourteen_days_ago = datetime_now - timedelta(days=14)
    one_days_ago = datetime_now - timedelta(days=1)
    one_day_from_now = datetime_now + timedelta(days=1)

    not_marked = SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=one_day_from_now,
        external_order_id="1234",
        signup__registration=registration,
    )
    marked = SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED,
        expires_at=fourteen_days_ago,
        external_order_id=DEFAULT_ORDER_ID,
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
        signup=marked.signup,
        email=_CONTACT_PERSON_EMAIL,
        service_language=service_language,
    )
    contact_person2 = SignUpContactPersonFactory(
        signup_group=marked2.signup_group,
        email=_CONTACT_PERSON2_EMAIL,
        service_language=service_language,
    )

    assert not_marked.status == SignUpPayment.PaymentStatus.CREATED
    assert not_marked.deleted is False
    assert not_marked.signup.deleted is False

    assert marked.status == SignUpPayment.PaymentStatus.CREATED
    assert marked.deleted is False
    assert marked.signup.deleted is False

    assert marked2.status == SignUpPayment.PaymentStatus.CREATED
    assert marked2.deleted is False
    assert marked2.signup_group.deleted is False

    marked2_order_data = DEFAULT_GET_ORDER_DATA.copy()
    marked2_order_data["orderId"] = marked2.external_order_id

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{marked.external_order_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{marked2.external_order_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/{marked.external_order_id}/cancel",
            json=DEFAULT_CANCEL_ORDER_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/{marked2.external_order_id}/cancel",
            json=marked2_order_data,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 4

    not_marked.refresh_from_db()
    assert not_marked.status == SignUpPayment.PaymentStatus.CREATED
    assert not_marked.deleted is False
    assert not_marked.signup.deleted is False

    marked.refresh_from_db()
    assert marked.status == SignUpPayment.PaymentStatus.EXPIRED
    assert marked.deleted is True
    assert marked.signup.deleted is True

    marked2.refresh_from_db()
    assert marked2.status == SignUpPayment.PaymentStatus.EXPIRED
    assert marked2.deleted is True
    assert marked2.signup_group.deleted is True

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
    service_lang = LanguageFactory(pk=service_language, service_language=True)

    with translation.override(service_lang.pk):
        registration = RegistrationFactory(event__name=_EVENT_NAME)

    _test_payments_expired(
        registration,
        now,
        service_lang,
        expected_subject,
        expected_heading,
        expected_secondary_heading,
        expected_text,
    )


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_secondary_heading,expected_text",
    [
        (
            "en",
            f"Registration payment expired - Recurring: {_EVENT_NAME}",
            "Registration payment expired",
            f"Registration to the recurring event {_EVENT_NAME} 1 Feb 2024 - 29 Feb 2024 "
            "has been cancelled due to an expired payment.",
            "Your registration to the recurring event "
            f"<strong>{_EVENT_NAME} 1 Feb 2024 - 29 Feb 2024</strong> has been "
            "cancelled due no payment received within the payment period.",
        ),
        (
            "fi",
            f"Ilmoittautumismaksu vanhentunut - Sarja: {_EVENT_NAME}",
            "Ilmoittautumismaksu vanhentunut",
            f"Ilmoittautuminen sarjatapahtumaan {_EVENT_NAME} 1.2.2024 - 29.2.2024 "
            "on peruttu ilmoittautumismaksun vanhenemisen vuoksi.",
            "Ilmoittautumisesi sarjatapahtumaan "
            f"<strong>{_EVENT_NAME} 1.2.2024 - 29.2.2024</strong> on "
            "peruttu, koska ilmoittautumismaksua ei ole maksettu maksuajan loppuun mennessä.",
        ),
        (
            "sv",
            f"Registreringsbetalning har gått ut - Serie: {_EVENT_NAME}",
            "Registreringsbetalning har gått ut",
            f"Anmälan till serieevenemanget {_EVENT_NAME} 1.2.2024 - 29.2.2024 "
            "har ställts in på grund av att betalningen har gått ut.",
            "Din anmälan till serieevenemanget "
            f"<strong>{_EVENT_NAME} 1.2.2024 - 29.2.2024</strong> har "
            "ställts in eftersom ingen betalning mottogs inom betalningsperioden.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_mark_payments_expired_for_recurring_event(
    service_language,
    expected_subject,
    expected_heading,
    expected_secondary_heading,
    expected_text,
):
    now = localtime()
    service_lang = LanguageFactory(pk=service_language, service_language=True)

    with translation.override(service_lang.pk):
        registration = RegistrationFactory(
            event__start_time=now,
            event__end_time=now + timedelta(days=28),
            event__super_event_type=Event.SuperEventType.RECURRING,
            event__name=_EVENT_NAME,
        )

    _test_payments_expired(
        registration,
        now,
        service_lang,
        expected_subject,
        expected_heading,
        expected_secondary_heading,
        expected_text,
    )


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
        external_order_id=DEFAULT_ORDER_ID,
        signup__registration=registration,
    )

    contact_person = SignUpContactPersonFactory(
        signup=payment.signup,
        email=_CONTACT_PERSON_EMAIL,
        service_language=service_lang,
    )

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/{payment.external_order_id}/cancel",
            json=DEFAULT_CANCEL_ORDER_DATA,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 2

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
        RegistrationWebStoreMerchantFactory(registration=registration)
    RegistrationWebStoreAccountFactory(registration=registration)
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

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/{payment.external_order_id}/cancel",
            json=DEFAULT_CANCEL_ORDER_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            json=DEFAULT_GET_ORDER_DATA,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 3

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

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/{payment.external_order_id}/cancel",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 2

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
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=api_payment_data,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 1

    assert SignUpPayment.objects.count() == 0
    assert SignUp.objects.count() == 0

    _assert_email_sent(contact_person.email, f"Registration cancelled - {_EVENT_NAME}")


@pytest.mark.django_db
def test_mark_payments_expired_payment_cancelled_signup_moved_to_waitlisted_with_payment_link():
    now = localtime()
    fourteen_days_ago = now - timedelta(days=14)

    registration = RegistrationFactory(event__name=_EVENT_NAME)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreMerchantFactory(registration=registration)
    RegistrationWebStoreAccountFactory(registration=registration)
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
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=api_payment_data,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            json=DEFAULT_GET_ORDER_DATA,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 2

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
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=api_payment_data,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 1

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
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=api_payment_data,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 1

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

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=api_status_code,
        )

        call_command("mark_payments_expired")

        assert req_mock.call_count == 1

    payment.refresh_from_db()
    assert payment.status == SignUpPayment.PaymentStatus.CREATED
    assert payment.deleted is False
    assert payment.signup.deleted is False

    assert len(mail.outbox) == 0
