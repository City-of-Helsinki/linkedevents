from datetime import timedelta

import pytest
import requests_mock
from django.conf import settings
from django.test import override_settings
from django.utils.timezone import localtime
from freezegun import freeze_time
from rest_framework import status

from events.tests.factories import EventFactory
from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp, SignUpGroup
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationWebStoreProductMappingFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPaymentFactory,
)
from registrations.tests.utils import create_user_by_role
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_GET_ORDER_DATA,
    DEFAULT_ORDER_ID,
)
from web_store.tests.payment.test_web_store_payment_api_client import (
    DEFAULT_GET_PAYMENT_DATA,
)


def delete_signup(api_client, signup_pk):
    signup_url = reverse("signup-detail", kwargs={"pk": signup_pk})
    return api_client.delete(signup_url)


def delete_signup_group(api_client, signup_group_pk):
    signup_group_url = reverse("signupgroup-detail", kwargs={"pk": signup_group_pk})
    return api_client.delete(signup_group_url)


@pytest.fixture
def registration_with_future_event():
    """Create a registration with an event starting 8 days from now."""
    now = localtime()
    event_start = now + timedelta(days=8)
    event = EventFactory(
        start_time=event_start,
        end_time=event_start + timedelta(hours=3),
    )
    registration = RegistrationFactory(event=event)
    RegistrationWebStoreProductMappingFactory(registration=registration)
    return registration


@pytest.mark.django_db
@pytest.mark.parametrize(
    "current_date,event_date,deadline_days,response_status_code",
    [
        ("2025-11-02", "2025-11-10", 7, status.HTTP_204_NO_CONTENT),
        ("2025-11-03", "2025-11-10", 7, status.HTTP_204_NO_CONTENT),
        ("2025-11-04", "2025-11-10", 7, status.HTTP_400_BAD_REQUEST),
        ("2026-11-09", "2025-11-10", 7, status.HTTP_400_BAD_REQUEST),
        ("2025-11-01", "2025-11-15", 14, status.HTTP_204_NO_CONTENT),
        ("2025-11-02", "2025-11-15", 14, status.HTTP_400_BAD_REQUEST),
    ],
)
@pytest.mark.django_db
def test_refund_deadline_threshold_and_setting(
    api_client,
    current_date,
    event_date,
    deadline_days,
    response_status_code,
):
    event_year, event_month, event_day = map(int, event_date.split("-"))
    event_datetime = localtime().replace(
        year=event_year,
        month=event_month,
        day=event_day,
        hour=15,
        minute=0,
        second=0,
        microsecond=0,
    )
    event = EventFactory(
        start_time=event_datetime, end_time=event_datetime + timedelta(hours=3)
    )
    registration = RegistrationFactory(event=event)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpPaymentFactory(signup=signup, external_order_id=DEFAULT_ORDER_ID)

    with override_settings(WEB_STORE_REFUND_DEADLINE_DAYS=deadline_days):
        with freeze_time(f"{current_date} 12:00:00"):
            with requests_mock.Mocker() as req_mock:
                req_mock.get(
                    f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{DEFAULT_ORDER_ID}",
                    json=DEFAULT_GET_PAYMENT_DATA,
                )
                req_mock.post(
                    f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
                    json={"refunds": [{"refundId": "test-refund-id"}]},
                )

                response = delete_signup(api_client, signup.pk)

                assert response.status_code == response_status_code


@pytest.mark.django_db
def test_refund_allowed_when_event_has_no_start_time(api_client):
    event = EventFactory(start_time=None, has_start_time=False)
    registration = RegistrationFactory(event=event)
    RegistrationWebStoreProductMappingFactory(registration=registration)

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpPaymentFactory(signup=signup, external_order_id=DEFAULT_ORDER_ID)

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{DEFAULT_ORDER_ID}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json={"refunds": [{"refundId": "test-refund-id"}]},
        )

        response = delete_signup(api_client, signup.pk)

        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_signup_group_refund_is_blocked_by_deadline(
    api_client, registration_with_future_event, settings
):
    settings.WEB_STORE_REFUND_DEADLINE_DAYS = 7
    user = create_user_by_role(
        "registration_admin", registration_with_future_event.publisher
    )
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration_with_future_event)
    SignUpFactory(
        signup_group=signup_group,
        registration=registration_with_future_event,
        first_name="Test",
        last_name="User",
    )
    SignUpPaymentFactory(
        signup_group=signup_group, signup=None, external_order_id=DEFAULT_ORDER_ID
    )

    with freeze_time(
        registration_with_future_event.event.start_time
        - timedelta(days=settings.WEB_STORE_REFUND_DEADLINE_DAYS - 1)
    ):
        with requests_mock.Mocker() as req_mock:
            payment_mock = req_mock.get(
                f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{DEFAULT_ORDER_ID}",
                json=DEFAULT_GET_PAYMENT_DATA,
            )

            response = delete_signup_group(api_client, signup_group.pk)

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Refund is not allowed" in str(response.data)
            assert SignUpGroup.objects.filter(pk=signup_group.pk).exists()
            assert payment_mock.called


@pytest.mark.django_db
def test_sign_up_group_partial_refund_is_blocked_by_deadline(
    api_client, registration_with_future_event, settings
):
    settings.WEB_STORE_REFUND_DEADLINE_DAYS = 7
    user = create_user_by_role(
        "registration_admin", registration_with_future_event.publisher
    )
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration_with_future_event)
    signup1 = SignUpFactory(
        signup_group=signup_group,
        registration=registration_with_future_event,
        first_name="Test1",
        last_name="User1",
    )
    SignUpFactory(
        signup_group=signup_group,
        registration=registration_with_future_event,
        first_name="Test2",
        last_name="User2",
    )
    SignUpPaymentFactory(
        signup_group=signup_group, signup=None, external_order_id=DEFAULT_ORDER_ID
    )

    with freeze_time(
        registration_with_future_event.event.start_time
        - timedelta(days=settings.WEB_STORE_REFUND_DEADLINE_DAYS - 1)
    ):
        with requests_mock.Mocker() as req_mock:
            get_payment_data_mock = req_mock.get(
                f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{DEFAULT_ORDER_ID}",
                json=DEFAULT_GET_PAYMENT_DATA,
            )

            response = delete_signup(api_client, signup1.pk)
            assert get_payment_data_mock.called

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Refund is not allowed" in str(response.data)
            assert SignUp.objects.filter(pk=signup1.pk).exists()


@pytest.mark.django_db
def test_unpaid_order_cancellation_allowed_within_deadline(
    api_client, registration_with_future_event, settings
):
    settings.WEB_STORE_REFUND_DEADLINE_DAYS = 7
    user = create_user_by_role(
        "registration_admin", registration_with_future_event.publisher
    )
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration_with_future_event)
    SignUpPaymentFactory(signup=signup, external_order_id=DEFAULT_ORDER_ID)

    with freeze_time(
        registration_with_future_event.event.start_time
        - timedelta(days=settings.WEB_STORE_REFUND_DEADLINE_DAYS - 1)
    ):
        with requests_mock.Mocker() as req_mock:
            payment_mock = req_mock.get(
                f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{DEFAULT_ORDER_ID}",
                status_code=404,
            )
            order_mock = req_mock.get(
                f"{settings.WEB_STORE_API_BASE_URL}order/admin/{DEFAULT_ORDER_ID}",
                json=DEFAULT_GET_ORDER_DATA,
            )
            cancel_mock = req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}order/{DEFAULT_ORDER_ID}/cancel",
                json={},
            )

            response = delete_signup(api_client, signup.pk)

            assert response.status_code == status.HTTP_204_NO_CONTENT
            # Signup still exists because waiting for webhook
            assert SignUp.objects.filter(pk=signup.pk).exists()
            assert payment_mock.called
            assert order_mock.called
            assert cancel_mock.called
