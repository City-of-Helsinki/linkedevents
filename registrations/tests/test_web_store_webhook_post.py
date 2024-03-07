from datetime import datetime
from typing import Optional, Union
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core import mail
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.factories import LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp, SignUpGroup, SignUpPayment
from registrations.tests.factories import (
    SignUpContactPersonFactory,
    SignUpGroupFactory,
    SignUpPaymentFactory,
)
from web_store.order.enums import WebStoreOrderStatus, WebStoreOrderWebhookEventType
from web_store.payment.enums import (
    WebStorePaymentStatus,
    WebStorePaymentWebhookEventType,
)
from web_store.tests.order.test_web_store_order_api_client import DEFAULT_GET_ORDER_DATA
from web_store.tests.payment.test_web_store_payment_api_client import (
    DEFAULT_GET_PAYMENT_DATA,
)
from web_store.tests.utils import get_mock_response

_EXTERNAL_ORDER_ID = "c748b9cb-c2da-4340-a746-fe44fec9cc64"
_PAYMENT_ID = "36985766-eb07-42c2-8277-9508630f42d1"


# === util methods ===


def create_signup_payment(
    external_order_id: str = _EXTERNAL_ORDER_ID,
    user: Optional[settings.AUTH_USER_MODEL] = None,
    create_contact_person: bool = True,
) -> SignUpPayment:
    payment = SignUpPaymentFactory(
        external_order_id=external_order_id,
        signup__created_by=user,
        created_by=user,
    )

    if not create_contact_person:
        return payment

    # Needed when testing confirmation email messages.
    registration = payment.signup_or_signup_group.registration
    registration.event.name = "Foo"
    registration.event.save()

    english = LanguageFactory(pk="en", service_language=True)
    SignUpContactPersonFactory(
        signup=payment.signup_or_signup_group,
        email="test@test.com",
        service_language=english,
    )

    return payment


def create_signup_group_payment(
    external_order_id: str = _EXTERNAL_ORDER_ID,
    user: Optional[settings.AUTH_USER_MODEL] = None,
    create_contact_person: bool = True,
) -> SignUpPayment:
    signup_group = SignUpGroupFactory(created_by=user)

    payment = SignUpPaymentFactory(
        signup=None,
        signup_group=signup_group,
        external_order_id=external_order_id,
        created_by=user,
    )

    if not create_contact_person:
        return payment

    # Needed when testing confirmation email messages.
    signup_group.registration.event.name = "Foo"
    signup_group.registration.event.save()

    english = LanguageFactory(pk="en", service_language=True)
    SignUpContactPersonFactory(
        signup_group=payment.signup_or_signup_group,
        email="test@test.com",
        service_language=english,
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


def post_webhook(api_client, data: dict, action_endpoint: str):
    url = reverse(f"webhook-{action_endpoint}")
    response = api_client.post(url, data, format="json")

    return response


def assert_post_webhook(api_client, data: dict, action_endpoint: str):
    response = post_webhook(api_client, data, action_endpoint)

    assert response.status_code == status.HTTP_200_OK


def assert_payment_paid(api_client, data: dict, payment: SignUpPayment):
    previous_modified_time = payment.last_modified_time

    assert_post_webhook(api_client, data, "payment")

    payment.refresh_from_db()
    assert payment.status == SignUpPayment.PaymentStatus.PAID
    assert payment.last_modified_time > previous_modified_time


def assert_confirmation_sent_to_contact_person(
    signup_or_signup_group: Union[SignUpGroup, SignUp]
):
    if not signup_or_signup_group.actual_contact_person:
        assert len(mail.outbox) == 0
        return

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to[0] == signup_or_signup_group.actual_contact_person.email

    message_string = str(mail.outbox[0].alternatives[0])
    assert (
        "Congratulations! Your registration has been confirmed for the event <strong>Foo</strong>."
        in message_string
    )

    if isinstance(signup_or_signup_group, SignUp):
        signup_type = "signup"
    else:
        signup_type = "signup-group"

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
    if isinstance(payment.signup_or_signup_group, SignUp):
        assert SignUp.objects.count() == 0
    else:
        assert SignUpGroup.objects.count() == 0

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to[0] == payment.signup_or_signup_group.contact_person.email
    message_string = str(mail.outbox[0].alternatives[0])
    assert (
        "Your registration and payment for the event <strong>Foo</strong> have been cancelled."
        in message_string
    )


def assert_payment_id_audit_logged(payment: SignUpPayment) -> None:
    assert AuditLogEntry.objects.count() == 1

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        payment.pk
    ]


# === tests ===


@pytest.mark.parametrize(
    "http_method", ["get", "put", "patch", "delete", "options", "head"]
)
@pytest.mark.django_db
def test_payment_webhook_method_not_allowed(api_client, data_source, http_method):
    url = reverse("webhook-payment")

    api_client.credentials(apikey=data_source.api_key)

    response = getattr(api_client, http_method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "http_method", ["get", "put", "patch", "delete", "options", "head"]
)
@pytest.mark.django_db
def test_order_webhook_method_not_allowed(api_client, data_source, http_method):
    url = reverse("webhook-order")

    api_client.credentials(apikey=data_source.api_key)

    response = getattr(api_client, http_method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "action_endpoint,event_type",
    [
        ("payment", WebStorePaymentWebhookEventType.PAYMENT_PAID.value),
        ("order", WebStoreOrderWebhookEventType.ORDER_CANCELLED.value),
    ],
)
@pytest.mark.django_db
def test_not_authorized_without_apikey(api_client, action_endpoint, event_type):
    payment = create_signup_payment()

    data = get_webhook_data(
        payment.external_order_id,
        event_type,
        {"paymentId": _PAYMENT_ID} if action_endpoint == "payment" else None,
    )

    assert payment.status == SignUpPayment.PaymentStatus.CREATED

    response = post_webhook(api_client, data, action_endpoint)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    payment.refresh_from_db()
    assert payment.status == SignUpPayment.PaymentStatus.CREATED

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
    api_client, data_source, created_by_user, has_contact_person
):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_payment(
        user=created_by_user() if callable(created_by_user) else created_by_user,
        create_contact_person=has_contact_person,
    )

    assert payment.status == SignUpPayment.PaymentStatus.CREATED

    data = get_webhook_data(
        payment.external_order_id,
        WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
        {"paymentId": _PAYMENT_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    mocked_get_payment_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=DEFAULT_GET_PAYMENT_DATA
    )
    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_get_payment_response

        assert_payment_paid(api_client, data, payment)
        assert_confirmation_sent_to_contact_person(payment.signup_or_signup_group)

        assert mocked_get_payment_request.called is True

    assert_payment_id_audit_logged(payment)


@pytest.mark.django_db
def test_payment_paid_webhook_for_signup_payment_with_waitlisted_status(
    api_client, data_source
):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_payment(user=UserFactory())
    payment.signup.attendee_status = SignUp.AttendeeStatus.WAITING_LIST
    payment.signup.save(update_fields=["attendee_status"])

    assert payment.status == SignUpPayment.PaymentStatus.CREATED
    assert payment.signup.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    data = get_webhook_data(
        payment.external_order_id,
        WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
        {"paymentId": _PAYMENT_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    mocked_get_payment_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=DEFAULT_GET_PAYMENT_DATA
    )
    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_get_payment_response

        assert_payment_paid(api_client, data, payment)
        assert_confirmation_sent_to_contact_person(payment.signup_or_signup_group)

        assert mocked_get_payment_request.called is True

    payment.signup.refresh_from_db()
    assert payment.signup.attendee_status == SignUp.AttendeeStatus.ATTENDING

    assert_payment_id_audit_logged(payment)


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
    api_client, data_source, created_by_user, has_contact_person
):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_group_payment(
        user=created_by_user() if callable(created_by_user) else created_by_user,
        create_contact_person=has_contact_person,
    )

    assert payment.status == SignUpPayment.PaymentStatus.CREATED

    data = get_webhook_data(
        payment.external_order_id,
        WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
        {"paymentId": _PAYMENT_ID},
    )

    assert AuditLogEntry.objects.count() == 0

    mocked_get_payment_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=DEFAULT_GET_PAYMENT_DATA
    )
    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_get_payment_response

        assert_payment_paid(api_client, data, payment)
        assert_confirmation_sent_to_contact_person(payment.signup_or_signup_group)

        assert mocked_get_payment_request.called is True

    assert_payment_id_audit_logged(payment)


@pytest.mark.django_db
def test_payment_cancelled_webhook_for_signup_payment(api_client, data_source):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_payment()

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 1

    data = get_webhook_data(
        payment.external_order_id,
        WebStorePaymentWebhookEventType.PAYMENT_CANCELLED.value,
    )

    web_store_response_data = DEFAULT_GET_PAYMENT_DATA.copy()
    web_store_response_data.update({"status": WebStorePaymentStatus.CANCELLED.value})
    mocked_get_payment_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=web_store_response_data
    )

    assert AuditLogEntry.objects.count() == 0

    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_get_payment_response

        assert_payment_cancelled(api_client, data, "payment", payment)
        assert mocked_get_payment_request.called is True

    assert_payment_id_audit_logged(payment)


@pytest.mark.django_db
def test_payment_cancelled_webhook_for_signup_group_payment(api_client, data_source):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_group_payment()

    assert SignUpPayment.objects.count() == 1
    assert SignUpGroup.objects.count() == 1

    data = get_webhook_data(
        payment.external_order_id,
        WebStorePaymentWebhookEventType.PAYMENT_CANCELLED.value,
    )

    web_store_response_data = DEFAULT_GET_PAYMENT_DATA.copy()
    web_store_response_data.update({"status": WebStorePaymentStatus.CANCELLED.value})
    mocked_get_payment_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=web_store_response_data
    )

    assert AuditLogEntry.objects.count() == 0

    with patch("requests.get") as mocked_get_payment_request:
        mocked_get_payment_request.return_value = mocked_get_payment_response

        assert_payment_cancelled(api_client, data, "payment", payment)
        assert mocked_get_payment_request.called is True

    assert_payment_id_audit_logged(payment)


@pytest.mark.django_db
def test_order_cancelled_webhook_for_signup_payment(api_client, data_source):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_payment()

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 1

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
    )

    web_store_response_data = DEFAULT_GET_ORDER_DATA.copy()
    web_store_response_data.update({"status": WebStoreOrderStatus.CANCELLED.value})
    mocked_get_order_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=web_store_response_data
    )

    assert AuditLogEntry.objects.count() == 0

    with patch("requests.get") as mocked_get_order_request:
        mocked_get_order_request.return_value = mocked_get_order_response

        assert_payment_cancelled(api_client, data, "order", payment)
        assert mocked_get_order_request.called is True

    assert_payment_id_audit_logged(payment)


@pytest.mark.django_db
def test_order_cancelled_webhook_for_signup_group_payment(api_client, data_source):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_group_payment()

    assert SignUpPayment.objects.count() == 1
    assert SignUpGroup.objects.count() == 1

    data = get_webhook_data(
        payment.external_order_id,
        WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
    )

    web_store_response_data = DEFAULT_GET_ORDER_DATA.copy()
    web_store_response_data.update({"status": WebStoreOrderStatus.CANCELLED.value})
    mocked_get_order_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=web_store_response_data
    )

    assert AuditLogEntry.objects.count() == 0

    with patch("requests.get") as mocked_get_order_request:
        mocked_get_order_request.return_value = mocked_get_order_response

        assert_payment_cancelled(api_client, data, "order", payment)
        assert mocked_get_order_request.called is True

    assert_payment_id_audit_logged(payment)


@pytest.mark.parametrize(
    "action_endpoint,event_type",
    [
        ("payment", WebStorePaymentWebhookEventType.PAYMENT_PAID.value),
        ("order", WebStoreOrderWebhookEventType.ORDER_CANCELLED.value),
    ],
)
@pytest.mark.django_db
def test_invalid_order_id(api_client, data_source, action_endpoint, event_type):
    api_client.credentials(apikey=data_source.api_key)

    data = get_webhook_data(
        "wrong",
        event_type,
        {"paymentId": _PAYMENT_ID} if action_endpoint == "payment" else None,
    )

    response = post_webhook(api_client, data, action_endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "action_endpoint,event_type",
    [
        ("payment", WebStorePaymentWebhookEventType.PAYMENT_PAID.value),
        ("order", WebStoreOrderWebhookEventType.ORDER_CANCELLED.value),
    ],
)
@pytest.mark.django_db
def test_invalid_namespace(api_client, data_source, action_endpoint, event_type):
    api_client.credentials(apikey=data_source.api_key)

    update_data = {"namespace": "wrong"}
    if action_endpoint == "payment":
        update_data["paymentId"] = _PAYMENT_ID

    data = get_webhook_data(
        _EXTERNAL_ORDER_ID,
        event_type,
        update_data,
    )

    response = post_webhook(api_client, data, action_endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize("action_endpoint", ["payment", "order"])
@pytest.mark.django_db
def test_wrong_event_type(api_client, data_source, action_endpoint):
    api_client.credentials(apikey=data_source.api_key)

    data = get_webhook_data(
        _EXTERNAL_ORDER_ID,
        "wrong",
        {"paymentId": _PAYMENT_ID} if action_endpoint == "payment" else None,
    )

    response = post_webhook(api_client, data, action_endpoint)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "action_endpoint,event_type",
    [
        ("payment", WebStorePaymentWebhookEventType.PAYMENT_PAID.value),
        ("order", WebStoreOrderWebhookEventType.ORDER_CANCELLED.value),
    ],
)
@pytest.mark.django_db
def test_payment_not_found(api_client, data_source, action_endpoint, event_type):
    api_client.credentials(apikey=data_source.api_key)

    data = get_webhook_data(
        _EXTERNAL_ORDER_ID,
        event_type,
        {"paymentId": _PAYMENT_ID} if action_endpoint == "payment" else None,
    )

    response = post_webhook(api_client, data, action_endpoint)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "action_endpoint,event_type,api_response_status_code",
    [
        (
            "payment",
            WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            "payment",
            WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        (
            "order",
            WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
            status.HTTP_403_FORBIDDEN,
        ),
        (
            "order",
            WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            "order",
            WebStoreOrderWebhookEventType.ORDER_CANCELLED.value,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
@pytest.mark.django_db
def test_web_store_api_request_exception(
    api_client, data_source, action_endpoint, event_type, api_response_status_code
):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_group_payment()

    data = get_webhook_data(
        payment.external_order_id,
        event_type,
        {"paymentId": _PAYMENT_ID} if action_endpoint == "payment" else None,
    )

    mocked_api_response = get_mock_response(status_code=api_response_status_code)

    with patch("requests.get") as mocked_api_request:
        mocked_api_request.return_value = mocked_api_response

        response = post_webhook(api_client, data, action_endpoint)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert mocked_api_request.called is True

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.parametrize(
    "event_type,web_store_payment_status",
    [
        (
            WebStorePaymentWebhookEventType.PAYMENT_PAID.value,
            WebStorePaymentStatus.CREATED.value,
        ),
        (
            WebStorePaymentWebhookEventType.PAYMENT_CANCELLED.value,
            WebStorePaymentStatus.PAID.value,
        ),
    ],
)
@pytest.mark.django_db
def test_webhook_and_web_store_payment_status_mismatch(
    api_client, data_source, event_type, web_store_payment_status
):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_group_payment()

    data = get_webhook_data(
        payment.external_order_id,
        event_type,
        {"paymentId": _PAYMENT_ID},
    )

    web_store_response_data = DEFAULT_GET_PAYMENT_DATA.copy()
    web_store_response_data.update({"status": web_store_payment_status})
    mocked_api_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=web_store_response_data
    )

    with patch("requests.get") as mocked_api_request:
        mocked_api_request.return_value = mocked_api_response

        response = post_webhook(api_client, data, "payment")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert mocked_api_request.called is True

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0


@pytest.mark.django_db
def test_webhook_and_web_store_order_status_mismatch(api_client, data_source):
    api_client.credentials(apikey=data_source.api_key)

    payment = create_signup_group_payment()

    data = get_webhook_data(
        payment.external_order_id, WebStoreOrderWebhookEventType.ORDER_CANCELLED.value
    )

    web_store_response_data = DEFAULT_GET_ORDER_DATA.copy()
    web_store_response_data.update({"status": WebStoreOrderStatus.DRAFT.value})
    mocked_api_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=web_store_response_data
    )

    with patch("requests.get") as mocked_api_request:
        mocked_api_request.return_value = mocked_api_response

        response = post_webhook(api_client, data, "order")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert mocked_api_request.called is True

    assert len(mail.outbox) == 0

    assert AuditLogEntry.objects.count() == 0
