from datetime import datetime, timedelta
from typing import Optional, Union

import pytest
import requests_mock
from django.conf import settings
from django.core import mail
from django.utils.timezone import localtime
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event
from events.tests.factories import LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import (
    Registration,
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpPayment,
    SignUpPaymentCancellation,
    SignUpPaymentRefund,
)
from registrations.tests.factories import (
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPaymentCancellationFactory,
    SignUpPaymentFactory,
    SignUpPaymentRefundFactory,
)
from web_store.order.enums import (
    WebStoreOrderRefundStatus,
    WebStoreOrderStatus,
    WebStoreOrderWebhookEventType,
    WebStoreRefundWebhookEventType,
)
from web_store.payment.enums import (
    WebStorePaymentStatus,
    WebStorePaymentWebhookEventType,
)
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_GET_ORDER_DATA,
    DEFAULT_ORDER_ID,
    DEFAULT_REFUND_ID,
)
from web_store.tests.payment.test_web_store_payment_api_client import (
    DEFAULT_GET_PAYMENT_DATA,
    DEFAULT_GET_REFUND_PAYMENTS_DATA,
    DEFAULT_PAYMENT_ID,
)

_DEFAULT_GET_ORDER_URL = (
    f"{settings.WEB_STORE_API_BASE_URL}order/admin/{DEFAULT_ORDER_ID}"
)
_DEFAULT_GET_PAYMENT_URL = (
    f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{DEFAULT_ORDER_ID}"
)
_DEFAULT_GET_REFUND_URL = f"{settings.WEB_STORE_API_BASE_URL}payment/admin/refunds/{DEFAULT_REFUND_ID}/payment"


# === util methods ===


def create_recurring_event_for_registration(registration: Registration) -> None:
    now = localtime()

    registration.event.start_time = now
    registration.event.end_time = now + timedelta(days=28)
    registration.event.super_event_type = Event.SuperEventType.RECURRING
    registration.event.save()


def create_signup_payment(
    external_order_id: str = DEFAULT_ORDER_ID,
    payment_status: str = SignUpPayment.PaymentStatus.CREATED,
    user: Optional[settings.AUTH_USER_MODEL] = None,
    create_contact_person: bool = True,
    service_language: str = "en",
) -> SignUpPayment:
    payment = SignUpPaymentFactory(
        external_order_id=external_order_id,
        status=payment_status,
        signup__created_by=user,
        created_by=user,
    )

    if not create_contact_person:
        return payment

    language = LanguageFactory(pk=service_language, service_language=True)

    # Needed when testing confirmation email messages.
    registration = payment.signup_or_signup_group.registration
    registration.event.name = "Foo"
    registration.event.save()

    SignUpContactPersonFactory(
        signup=payment.signup_or_signup_group,
        email="test@test.com",
        service_language=language,
    )

    return payment


def create_signup_group_payment(
    external_order_id: str = DEFAULT_ORDER_ID,
    payment_status: str = SignUpPayment.PaymentStatus.CREATED,
    user: Optional[settings.AUTH_USER_MODEL] = None,
    create_contact_person: bool = True,
    service_language: str = "en",
) -> SignUpPayment:
    signup_group = SignUpGroupFactory(created_by=user)

    payment = SignUpPaymentFactory(
        signup=None,
        signup_group=signup_group,
        external_order_id=external_order_id,
        status=payment_status,
        created_by=user,
    )

    if not create_contact_person:
        return payment

    language = LanguageFactory(pk=service_language, service_language=True)

    # Needed when testing confirmation email messages.
    signup_group.registration.event.name = "Foo"
    signup_group.registration.event.save()

    SignUpContactPersonFactory(
        signup_group=payment.signup_or_signup_group,
        email="test@test.com",
        service_language=language,
    )

    return payment


def get_webhook_data(
    order_id: str, event_type: str, update_data: Optional[dict] = None
):
    data = {
        "orderId": order_id,
        "namespace": settings.WEB_STORE_API_NAMESPACE,
        "eventType": event_type,
        "eventTimestamp": f"{datetime.now().isoformat(sep='T', timespec='milliseconds')}Z",
    }

    if update_data:
        data.update(update_data)

    return data


def post_webhook(api_client, data: dict, webhook_type: str, action_endpoint: str):
    api_client.credentials(HTTP_WEBHOOK_API_KEY=settings.WEB_STORE_WEBHOOK_API_KEY)

    url = reverse(f"{webhook_type}_webhooks-{action_endpoint}")
    response = api_client.post(url, data, format="json")

    return response


def assert_post_webhook(api_client, data: dict, action_endpoint: str):
    webhook_type = "payment" if action_endpoint != "refund" else "refund"
    response = post_webhook(api_client, data, webhook_type, action_endpoint)

    assert response.status_code == status.HTTP_200_OK


def assert_payment_paid(api_client, data: dict, payment: SignUpPayment):
    previous_modified_time = payment.last_modified_time

    assert_post_webhook(api_client, data, "payment")

    payment.refresh_from_db()
    assert payment.status == SignUpPayment.PaymentStatus.PAID
    assert payment.last_modified_time > previous_modified_time


def assert_confirmation_email_sent_to_contact_person(
    contact_person: SignUpContactPerson,
    expected_subject: Optional[str] = None,
    expected_text: Optional[str] = None,
):
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to[0] == contact_person.email

    if expected_subject:
        assert mail.outbox[0].subject == expected_subject

    if expected_text:
        message_string = str(mail.outbox[0].alternatives[0])
        assert expected_text in message_string


def assert_confirmation_sent_to_contact_person(
    signup_or_signup_group: Union[SignUpGroup, SignUp],
):
    if not signup_or_signup_group.actual_contact_person:
        assert len(mail.outbox) == 0
        return

    assert_confirmation_email_sent_to_contact_person(
        signup_or_signup_group.actual_contact_person,
        expected_text=(
            "Congratulations! Your registration has been confirmed for the event "
            "<strong>Foo</strong>."
        ),
    )

    if isinstance(signup_or_signup_group, SignUp):
        signup_type = "signup"
    else:
        signup_type = "signup-group"

    message_string = str(mail.outbox[0].alternatives[0])
    signup_edit_url = (
        f"{settings.LINKED_REGISTRATIONS_UI_URL}/en"
        f"/registration/{signup_or_signup_group.registration_id}/"
        f"{signup_type}/{signup_or_signup_group.id}/edit?access_code="
    )
    assert signup_edit_url in message_string


def assert_payment_cancelled(
    api_client, data: dict, action_endpoint: str, payment: SignUpPayment
):
    assert_post_webhook(api_client, data, action_endpoint)

    assert SignUpPayment.objects.count() == 0
    assert SignUpPaymentCancellation.objects.count() == 0
    if isinstance(payment.signup_or_signup_group, SignUp):
        assert SignUp.objects.count() == 0
    else:
        assert SignUpGroup.objects.count() == 0


def assert_payment_refunded(
    api_client, data: dict, payment: SignUpPayment, partial_refund: bool = False
):
    assert_post_webhook(api_client, data, "refund")

    assert SignUpPayment.objects.count() == 0 if not partial_refund else 1
    assert SignUpPaymentRefund.objects.count() == 0
    if isinstance(payment.signup_or_signup_group, SignUp):
        assert SignUp.objects.count() == 0
    else:
        assert SignUpGroup.objects.count() == 0 if not partial_refund else 1


def assert_payment_refund_failed(api_client, data: dict, payment: SignUpPayment):
    assert_post_webhook(api_client, data, "refund")

    assert SignUpPayment.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 0
    if isinstance(payment.signup_or_signup_group, SignUp):
        assert SignUp.objects.count() == 1
    else:
        assert SignUpGroup.objects.count() == 1

    assert len(mail.outbox) == 0


def assert_payment_or_refund_id_audit_logged(
    obj: Union[SignUpPayment, SignUpPaymentRefund],
) -> None:
    assert AuditLogEntry.objects.count() == 1

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [obj.pk]


# === tests ===


@pytest.mark.parametrize(
    "view_name",
    [
        "payment_webhooks-payment",
        "payment_webhooks-order",
        "refund_webhooks-refund",
    ],
)
@pytest.mark.parametrize(
    "http_method", ["get", "put", "patch", "delete", "options", "head"]
)
@pytest.mark.django_db
def test_webhook_method_not_allowed(api_client, view_name, http_method):
    url = reverse(view_name)

    api_client.credentials(HTTP_WEBHOOK_API_KEY=settings.WEB_STORE_WEBHOOK_API_KEY)

    response = getattr(api_client, http_method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "credentials",
    [
        {},
        {"HTTP_WEBHOOK_API_KEY": "wrong"},
    ],
)
@pytest.mark.parametrize(
    "view_name",
    [
        "payment_webhooks-payment",
        "payment_webhooks-order",
        "refund_webhooks-refund",
    ],
)
@pytest.mark.django_db
def test_webhook_unauthorized(api_client, credentials, view_name):
    api_client.credentials(**credentials)

    url = reverse(view_name)

    response = api_client.post(url, {}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "created_by_user,has_contact_person",
    [
        (None, True),
        (UserFactory, True),
        (None, False),
        (UserFactory, False),
    ],
)
@pytest.mark.django_db
def test_payment_paid_webhook_for_signup_payment(
    api_client, created_by_user, has_contact_person
):
    payment = create_signup_payment(
        user=created_by_user() if callable(created_by_user) else created_by_user,
        create_contact_person=has_contact_person,
    )

    assert payment.status == SignUpPayment.PaymentStatus.CREATED

    data = get_webhook_data(
        payment.external_order_id,
        WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
        {"paymentId": DEFAULT_PAYMENT_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_PAYMENT_URL,
            json=DEFAULT_GET_PAYMENT_DATA,
        )

        assert_payment_paid(api_client, data, payment)
        assert_confirmation_sent_to_contact_person(payment.signup_or_signup_group)

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(payment)


@pytest.mark.parametrize(
    "created_by_user,has_contact_person",
    [
        (None, True),
        (UserFactory, True),
        (None, False),
        (UserFactory, False),
    ],
)
@pytest.mark.django_db
def test_payment_paid_webhook_for_signup_group_payment(
    api_client, created_by_user, has_contact_person
):
    payment = create_signup_group_payment(
        user=created_by_user() if callable(created_by_user) else created_by_user,
        create_contact_person=has_contact_person,
    )

    assert payment.status == SignUpPayment.PaymentStatus.CREATED

    data = get_webhook_data(
        payment.external_order_id,
        WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
        {"paymentId": DEFAULT_PAYMENT_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_PAYMENT_URL,
            json=DEFAULT_GET_PAYMENT_DATA,
        )

        assert_payment_paid(api_client, data, payment)
        assert_confirmation_sent_to_contact_person(payment.signup_or_signup_group)

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(payment)


@pytest.mark.parametrize(
    "service_lang,expected_subject,expected_text",
    [
        (
            "en",
            "Registration cancelled - Foo",
            "You have successfully cancelled your registration to the event "
            "<strong>Foo</strong>. Your payment for the registration has been refunded.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu - Foo",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi tapahtumaan "
            "<strong>Foo</strong>. Ilmoittautumismaksusi on hyvitetty.",
        ),
        (
            "sv",
            "Registreringen avbruten - Foo",
            "Du har avbrutit din registrering till evenemanget "
            "<strong>Foo</strong>. Din betalning för registreringen har återbetalats.",
        ),
    ],
)
@pytest.mark.django_db
def test_refund_paid_webhook_for_signup_payment(
    api_client, service_lang, expected_subject, expected_text
):
    payment = create_signup_payment(
        create_contact_person=True,
        payment_status=SignUpPayment.PaymentStatus.PAID,
        service_language=service_lang,
    )
    refund = SignUpPaymentRefundFactory(
        payment=payment,
        signup=payment.signup,
        amount=payment.amount,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_PAID.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=DEFAULT_GET_REFUND_PAYMENTS_DATA,
        )

        assert_payment_refunded(api_client, data, payment)
        assert_confirmation_email_sent_to_contact_person(
            payment.signup.contact_person,
            expected_subject,
            expected_text,
        )

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(refund)


@pytest.mark.parametrize(
    "service_lang,expected_subject,expected_text",
    [
        (
            "en",
            "Registration cancelled - Foo",
            "You have successfully cancelled your registration to the event "
            "<strong>Foo</strong>. Your payment for the registration has been refunded.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu - Foo",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi tapahtumaan "
            "<strong>Foo</strong>. Ilmoittautumismaksusi on hyvitetty.",
        ),
        (
            "sv",
            "Registreringen avbruten - Foo",
            "Du har avbrutit din registrering till evenemanget "
            "<strong>Foo</strong>. Din betalning för registreringen har återbetalats.",
        ),
    ],
)
@pytest.mark.django_db
def test_refund_paid_webhook_for_signup_group_payment(
    api_client, service_lang, expected_subject, expected_text
):
    payment = create_signup_group_payment(
        payment_status=SignUpPayment.PaymentStatus.PAID,
        service_language=service_lang,
    )
    refund = SignUpPaymentRefundFactory(
        payment=payment,
        signup=None,
        signup_group=payment.signup_group,
        amount=payment.amount,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_PAID.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=DEFAULT_GET_REFUND_PAYMENTS_DATA,
        )

        assert_payment_refunded(api_client, data, payment)
        assert_confirmation_email_sent_to_contact_person(
            payment.signup_group.contact_person,
            expected_subject,
            expected_text,
        )

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(refund)


@pytest.mark.parametrize(
    "service_lang,expected_subject,expected_text",
    [
        (
            "en",
            "Registration cancelled - Recurring: Foo",
            "You have successfully cancelled your registration to the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>. Your payment for the registration has "
            "been refunded.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu - Sarja: Foo",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>. Ilmoittautumismaksusi on hyvitetty.",
        ),
        (
            "sv",
            "Registreringen avbruten - Serie: Foo",
            "Du har avbrutit din registrering till serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>. Din betalning för registreringen har "
            "återbetalats.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_refund_paid_webhook_for_recurring_event_signup_payment(
    api_client, service_lang, expected_subject, expected_text
):
    payment = create_signup_payment(
        create_contact_person=True,
        payment_status=SignUpPayment.PaymentStatus.PAID,
        service_language=service_lang,
    )

    create_recurring_event_for_registration(payment.signup.registration)

    refund = SignUpPaymentRefundFactory(
        payment=payment,
        signup=payment.signup,
        amount=payment.amount,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_PAID.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=DEFAULT_GET_REFUND_PAYMENTS_DATA,
        )

        assert_payment_refunded(api_client, data, payment)
        assert_confirmation_email_sent_to_contact_person(
            payment.signup.contact_person,
            expected_subject,
            expected_text,
        )

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(refund)


@pytest.mark.parametrize(
    "service_lang,expected_subject,expected_text",
    [
        (
            "en",
            "Registration cancelled - Recurring: Foo",
            "You have successfully cancelled your registration to the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>. Your payment for the registration has "
            "been refunded.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu - Sarja: Foo",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>. Ilmoittautumismaksusi on hyvitetty.",
        ),
        (
            "sv",
            "Registreringen avbruten - Serie: Foo",
            "Du har avbrutit din registrering till serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>. Din betalning för registreringen har "
            "återbetalats.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_refund_paid_webhook_for_recurring_event_signup_group_payment(
    api_client, service_lang, expected_subject, expected_text
):
    payment = create_signup_group_payment(
        payment_status=SignUpPayment.PaymentStatus.PAID,
        service_language=service_lang,
    )

    create_recurring_event_for_registration(payment.signup_group.registration)

    refund = SignUpPaymentRefundFactory(
        payment=payment,
        signup=None,
        signup_group=payment.signup_group,
        amount=payment.amount,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_PAID.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=DEFAULT_GET_REFUND_PAYMENTS_DATA,
        )

        assert_payment_refunded(api_client, data, payment)
        assert_confirmation_email_sent_to_contact_person(
            payment.signup_group.contact_person,
            expected_subject,
            expected_text,
        )

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(refund)


@pytest.mark.parametrize(
    "service_lang, expected_subject, expected_text",
    [
        (
            "en",
            "Registration cancelled - Foo",
            "You have successfully cancelled a registration to the event "
            "<strong>Foo</strong>. Your payment has been partially refunded "
            "for the amount of the cancelled registration.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu - Foo",
            "Olet onnistuneesti peruuttanut ilmoittautumisen tapahtumaan "
            "<strong>Foo</strong>. Ilmoittautumismaksusi on osittain hyvitetty peruutetun "
            "ilmoittautumisen osuutta vastaavalta osalta.",
        ),
        (
            "sv",
            "Registreringen avbruten - Foo",
            "Du har avbrutit en registrering till evenemanget "
            "<strong>Foo</strong>. Din betalning för registreringen har delvits återbetalats "
            "för beloppet för den avbrutna registreringen.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_partial_refund_paid_webhook_for_signup_group_payment(
    api_client, service_lang, expected_subject, expected_text
):
    payment = create_signup_group_payment(
        payment_status=SignUpPayment.PaymentStatus.PAID,
        service_language=service_lang,
    )
    refund = SignUpPaymentRefundFactory(
        payment=payment,
        signup=SignUpFactory(
            signup_group=payment.signup_group,
            registration=payment.signup_group.registration,
        ),
        amount=payment.amount - 1,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_PAID.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=DEFAULT_GET_REFUND_PAYMENTS_DATA,
        )

        assert_payment_refunded(api_client, data, payment, partial_refund=True)
        assert_confirmation_email_sent_to_contact_person(
            payment.signup_group.contact_person,
            expected_subject,
            expected_text,
        )

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(refund)


@pytest.mark.django_db
def test_refund_failed_webhook_for_signup_payment(api_client):
    payment = create_signup_payment(
        create_contact_person=True,
        payment_status=SignUpPayment.PaymentStatus.PAID,
    )
    refund = SignUpPaymentRefundFactory(
        payment=payment,
        signup=payment.signup,
        amount=payment.amount,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_FAILED.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    refund_payment_data = [DEFAULT_GET_REFUND_PAYMENTS_DATA[0].copy()]
    refund_payment_data[0]["status"] = WebStoreOrderRefundStatus.CANCELLED.value

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=refund_payment_data,
        )

        assert_payment_refund_failed(api_client, data, payment)

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(refund)


@pytest.mark.django_db
def test_refund_failed_webhook_for_signup_group_payment(api_client):
    payment = create_signup_group_payment(
        payment_status=SignUpPayment.PaymentStatus.PAID,
    )
    refund = SignUpPaymentRefundFactory(
        payment=payment,
        signup=None,
        signup_group=payment.signup_group,
        amount=payment.amount,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_FAILED.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    refund_payment_data = [DEFAULT_GET_REFUND_PAYMENTS_DATA[0].copy()]
    refund_payment_data[0]["status"] = WebStoreOrderRefundStatus.CANCELLED.value

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=refund_payment_data,
        )

        assert_payment_refund_failed(api_client, data, payment)

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(refund)


@pytest.mark.django_db
def test_partial_refund_failed_webhook_for_signup_group_payment(api_client):
    payment = create_signup_group_payment(
        payment_status=SignUpPayment.PaymentStatus.PAID,
    )
    refund = SignUpPaymentRefundFactory(
        payment=payment,
        signup=SignUpFactory(
            signup_group=payment.signup_group,
            registration=payment.signup_group.registration,
        ),
        amount=payment.amount - 1,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_FAILED.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    refund_payment_data = [DEFAULT_GET_REFUND_PAYMENTS_DATA[0].copy()]
    refund_payment_data[0]["status"] = WebStoreOrderRefundStatus.CANCELLED.value

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=refund_payment_data,
        )

        assert_payment_refund_failed(api_client, data, payment)

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(refund)


@pytest.mark.django_db
def test_order_cancelled_webhook_for_signup_payment(api_client):
    payment = create_signup_payment()
    SignUpPaymentCancellationFactory(payment=payment, signup=payment.signup)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPaymentCancellation.objects.count() == 1
    assert SignUp.objects.count() == 1

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
    )

    web_store_response_data = DEFAULT_GET_ORDER_DATA.copy()
    web_store_response_data.update({"status": WebStoreOrderStatus.CANCELLED.value})

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_ORDER_URL,
            json=web_store_response_data,
        )

        assert_payment_cancelled(api_client, data, "order", payment)

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(payment)


@pytest.mark.django_db
def test_order_cancelled_webhook_for_signup_group_payment(api_client):
    payment = create_signup_group_payment()

    assert SignUpPayment.objects.count() == 1
    assert SignUpGroup.objects.count() == 1

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
    )

    web_store_response_data = DEFAULT_GET_ORDER_DATA.copy()
    web_store_response_data.update({"status": WebStoreOrderStatus.CANCELLED.value})

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_ORDER_URL,
            json=web_store_response_data,
        )

        assert_payment_cancelled(api_client, data, "order", payment)

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(payment)


@pytest.mark.parametrize(
    "service_lang,expected_subject,expected_text",
    [
        (
            "en",
            "Registration cancelled - Recurring: Foo",
            "Your registration and payment for the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> have been cancelled.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu - Sarja: Foo",
            "Ilmoittautumisesi ja maksusi sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> on peruttu.",
        ),
        (
            "sv",
            "Registreringen avbruten - Serie: Foo",
            "Din registrering och betalning för serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> har ställts in.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_order_cancelled_webhook_for_recurring_event_signup_payment(
    api_client, service_lang, expected_subject, expected_text
):
    payment = create_signup_payment(
        create_contact_person=True, service_language=service_lang
    )
    SignUpPaymentCancellationFactory(payment=payment, signup=payment.signup)

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 1

    create_recurring_event_for_registration(payment.signup.registration)

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
    )

    web_store_response_data = DEFAULT_GET_ORDER_DATA.copy()
    web_store_response_data.update({"status": WebStoreOrderStatus.CANCELLED.value})

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_ORDER_URL,
            json=web_store_response_data,
        )

        assert_payment_cancelled(api_client, data, "order", payment)
        assert_confirmation_email_sent_to_contact_person(
            payment.signup.contact_person,
            expected_subject,
            expected_text,
        )

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(payment)


@pytest.mark.parametrize(
    "service_lang, expected_subject, expected_text",
    [
        (
            "en",
            "Registration cancelled - Recurring: Foo",
            "Your registration and payment for the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> have been cancelled.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu - Sarja: Foo",
            "Ilmoittautumisesi ja maksusi sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> on peruttu.",
        ),
        (
            "sv",
            "Registreringen avbruten - Serie: Foo",
            "Din registrering och betalning för serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> har ställts in.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_order_cancelled_webhook_for_recurring_event_signup_group_payment(
    api_client, service_lang, expected_subject, expected_text
):
    payment = create_signup_group_payment(
        create_contact_person=True, service_language=service_lang
    )
    SignUpPaymentCancellationFactory(payment=payment, signup_group=payment.signup_group)

    assert SignUpPayment.objects.count() == 1
    assert SignUpGroup.objects.count() == 1

    create_recurring_event_for_registration(payment.signup_group.registration)

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
    )

    web_store_response_data = DEFAULT_GET_ORDER_DATA.copy()
    web_store_response_data.update({"status": WebStoreOrderStatus.CANCELLED.value})

    assert AuditLogEntry.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_ORDER_URL,
            json=web_store_response_data,
        )

        assert_payment_cancelled(api_client, data, "order", payment)
        assert_confirmation_email_sent_to_contact_person(
            payment.signup_group.contact_person,
            expected_subject,
            expected_text,
        )

        assert req_mock.call_count == 1

    assert_payment_or_refund_id_audit_logged(payment)


@pytest.mark.parametrize(
    "webhook_type, action_endpoint, event_type, webhook_data",
    [
        (
            "payment",
            "payment",
            WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
            {"paymentId": DEFAULT_PAYMENT_ID},
        ),
        ("payment", "order", WebStoreOrderWebhookEventType.ORDER_CANCELLED.value, None),
        (
            "refund",
            "refund",
            WebStoreRefundWebhookEventType.REFUND_PAID.value,
            {"refundId": DEFAULT_REFUND_ID},
        ),
        (
            "refund",
            "refund",
            WebStoreRefundWebhookEventType.REFUND_FAILED.value,
            {"refundId": DEFAULT_REFUND_ID},
        ),
    ],
)
@pytest.mark.django_db
def test_invalid_order_id(
    api_client, webhook_type, action_endpoint, event_type, webhook_data
):
    data = get_webhook_data(
        "wrong",
        event_type,
        webhook_data,
    )

    response = post_webhook(api_client, data, webhook_type, action_endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "webhook_type, action_endpoint, event_type, webhook_data",
    [
        (
            "payment",
            "payment",
            WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
            {"paymentId": DEFAULT_PAYMENT_ID},
        ),
        ("payment", "order", WebStoreOrderWebhookEventType.ORDER_CANCELLED.value, None),
        (
            "refund",
            "refund",
            WebStoreRefundWebhookEventType.REFUND_PAID.value,
            {"refundId": DEFAULT_REFUND_ID},
        ),
        (
            "refund",
            "refund",
            WebStoreRefundWebhookEventType.REFUND_FAILED.value,
            {"refundId": DEFAULT_REFUND_ID},
        ),
    ],
)
@pytest.mark.django_db
def test_invalid_namespace(
    api_client, webhook_type, action_endpoint, event_type, webhook_data
):
    update_data = {"namespace": "wrong"}
    if webhook_data:
        update_data.update(webhook_data)

    data = get_webhook_data(
        DEFAULT_ORDER_ID,
        event_type,
        update_data,
    )

    response = post_webhook(api_client, data, webhook_type, action_endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "webhook_type, action_endpoint, webhook_data",
    [
        ("payment", "payment", {"paymentId": DEFAULT_PAYMENT_ID}),
        ("payment", "order", None),
        ("refund", "refund", {"refundId": DEFAULT_REFUND_ID}),
    ],
)
@pytest.mark.django_db
def test_wrong_event_type(api_client, webhook_type, action_endpoint, webhook_data):
    data = get_webhook_data(
        DEFAULT_ORDER_ID,
        "wrong",
        webhook_data,
    )

    response = post_webhook(api_client, data, webhook_type, action_endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "webhook_type, action_endpoint, event_type, webhook_data",
    [
        (
            "payment",
            "payment",
            WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
            {"paymentId": DEFAULT_PAYMENT_ID},
        ),
        ("payment", "order", WebStoreOrderWebhookEventType.ORDER_CANCELLED.value, None),
        (
            "refund",
            "refund",
            WebStoreRefundWebhookEventType.REFUND_PAID.value,
            {"refundId": DEFAULT_REFUND_ID},
        ),
        (
            "refund",
            "refund",
            WebStoreRefundWebhookEventType.REFUND_FAILED.value,
            {"refundId": DEFAULT_REFUND_ID},
        ),
    ],
)
@pytest.mark.django_db
def test_payment_not_found(
    api_client, webhook_type, action_endpoint, event_type, webhook_data
):
    data = get_webhook_data(
        DEFAULT_ORDER_ID,
        event_type,
        webhook_data,
    )

    response = post_webhook(api_client, data, webhook_type, action_endpoint)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "event_type",
    [
        WebStoreRefundWebhookEventType.REFUND_PAID.value,
        WebStoreRefundWebhookEventType.REFUND_FAILED.value,
    ],
)
@pytest.mark.django_db
def test_refund_not_found(api_client, event_type):
    payment = create_signup_payment(
        create_contact_person=True,
        payment_status=SignUpPayment.PaymentStatus.PAID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreRefundWebhookEventType.REFUND_PAID.value,
        {"refundId": DEFAULT_REFUND_ID},
    )

    response = post_webhook(api_client, data, "refund", "refund")
    assert response.status_code == status.HTTP_404_NOT_FOUND

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "action_endpoint, event_type, api_url, api_response_status_code",
    [
        (
            "payment",
            WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
            _DEFAULT_GET_PAYMENT_URL,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            "payment",
            WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
            _DEFAULT_GET_PAYMENT_URL,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        (
            "order",
            WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
            _DEFAULT_GET_ORDER_URL,
            status.HTTP_403_FORBIDDEN,
        ),
        (
            "order",
            WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
            _DEFAULT_GET_ORDER_URL,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            "order",
            WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
            _DEFAULT_GET_ORDER_URL,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
@pytest.mark.django_db
def test_payment_and_order_webhook_web_store_api_request_exception(
    api_client, action_endpoint, event_type, api_url, api_response_status_code
):
    payment = create_signup_group_payment()

    data = get_webhook_data(
        payment.external_order_id,
        event_type,
        {"paymentId": DEFAULT_PAYMENT_ID} if action_endpoint == "payment" else None,
    )

    with requests_mock.Mocker() as req_mock:
        req_mock.get(api_url, status_code=api_response_status_code)

        response = post_webhook(api_client, data, "payment", action_endpoint)
        assert response.status_code == status.HTTP_409_CONFLICT

        assert req_mock.call_count == 1

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "event_type",
    [
        WebStoreRefundWebhookEventType.REFUND_PAID.value,
        WebStoreRefundWebhookEventType.REFUND_FAILED.value,
    ],
)
@pytest.mark.parametrize(
    "status_code",
    [
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
)
@pytest.mark.django_db
def test_refund_webhook_web_store_api_request_exception(
    api_client, event_type, status_code
):
    payment = create_signup_payment(
        create_contact_person=True,
        payment_status=SignUpPayment.PaymentStatus.PAID,
    )

    SignUpPaymentRefundFactory(
        payment=payment,
        signup=payment.signup,
        amount=payment.amount,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        event_type,
        {"refundId": DEFAULT_REFUND_ID},
    )

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            status_code=status_code,
        )

        response = post_webhook(api_client, data, "refund", "refund")
        assert response.status_code == status.HTTP_409_CONFLICT

        assert req_mock.call_count == 1

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.django_db
def test_webhook_and_web_store_payment_status_mismatch(api_client):
    payment = create_signup_group_payment()

    data = get_webhook_data(
        payment.external_order_id,
        WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
        {"paymentId": DEFAULT_PAYMENT_ID},
    )

    web_store_response_data = DEFAULT_GET_PAYMENT_DATA.copy()
    web_store_response_data.update({"status": WebStorePaymentStatus.CREATED.value})

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_PAYMENT_URL,
            json=web_store_response_data,
        )

        response = post_webhook(api_client, data, "payment", "payment")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert req_mock.call_count == 1

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.django_db
def test_webhook_and_web_store_order_status_mismatch(api_client):
    payment = create_signup_group_payment()

    data = get_webhook_data(
        payment.external_order_id, WebStoreOrderWebhookEventType.ORDER_CANCELLED.value
    )

    web_store_response_data = DEFAULT_GET_ORDER_DATA.copy()
    web_store_response_data.update({"status": WebStoreOrderStatus.DRAFT.value})

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_ORDER_URL,
            json=web_store_response_data,
        )

        response = post_webhook(api_client, data, "payment", "order")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert req_mock.call_count == 1

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "event_type, refund_payment_status",
    [
        (
            WebStoreRefundWebhookEventType.REFUND_PAID.value,
            WebStoreOrderRefundStatus.CREATED.value,
        ),
        (
            WebStoreRefundWebhookEventType.REFUND_PAID.value,
            WebStoreOrderRefundStatus.CANCELLED.value,
        ),
        (
            WebStoreRefundWebhookEventType.REFUND_FAILED.value,
            WebStoreOrderRefundStatus.CREATED.value,
        ),
        (
            WebStoreRefundWebhookEventType.REFUND_FAILED.value,
            WebStoreOrderRefundStatus.PAID_ONLINE.value,
        ),
    ],
)
@pytest.mark.django_db
def test_webhook_and_web_store_refund_status_mismatch(
    api_client, event_type, refund_payment_status
):
    payment = create_signup_payment(
        create_contact_person=True,
        payment_status=SignUpPayment.PaymentStatus.PAID,
    )

    SignUpPaymentRefundFactory(
        payment=payment,
        signup=payment.signup,
        amount=payment.amount,
        external_refund_id=DEFAULT_REFUND_ID,
    )

    data = get_webhook_data(
        payment.external_order_id,
        event_type,
        {"refundId": DEFAULT_REFUND_ID},
    )

    refund_payment_data = [DEFAULT_GET_REFUND_PAYMENTS_DATA[0].copy()]
    refund_payment_data[0]["status"] = refund_payment_status

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            _DEFAULT_GET_REFUND_URL,
            json=refund_payment_data,
        )

        response = post_webhook(api_client, data, "refund", "refund")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert req_mock.call_count == 1

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0
