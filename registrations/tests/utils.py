from decimal import Decimal
from typing import Optional
from unittest.mock import Mock
from uuid import uuid4

from django.conf import settings
from django.core import mail
from django_orghierarchy.models import Organization
from requests import RequestException
from rest_framework import status

from helevents.models import User
from helevents.tests.factories import UserFactory
from registrations.models import (
    RegistrationUserAccess,
    SignUp,
    SignUpGroup,
    SignUpPayment,
)

DEFAULT_CREATE_ORDER_RESPONSE_JSON = {
    "orderId": str(uuid4()),
    "priceTotal": "100.00",
    "checkoutUrl": "https://checkout.dev/v1/123/",
    "loggedInCheckoutUrl": "https://logged-in-checkout.dev/v1/123/",
}
DEFAULT_CREATE_ORDER_ERROR_RESPONSE = {
    "errors": [
        {"firstName": "error"},
    ],
}


def assert_invitation_email_is_sent(
    email: str,
    event_name: str,
    registration_user_access: RegistrationUserAccess,
    ui_locale: Optional[str] = None,
    expected_subject: Optional[str] = None,
    expected_body: Optional[str] = None,
) -> None:
    assert mail.outbox[0].to[0] == email

    ui_locale = ui_locale or "fi"
    email_body_string = str(mail.outbox[0].alternatives[0])

    if registration_user_access.is_substitute_user:
        expected_subject = expected_subject or "Oikeudet myönnetty ilmoittautumiseen"
        assert mail.outbox[0].subject.startswith(expected_subject)

        expected_body = expected_body or (
            f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty sijaisen käyttöoikeudet "
            f"tapahtuman <strong>{event_name}</strong> ilmoittautumiselle."
        )
        assert expected_body in email_body_string

        service_base_url = settings.LINKED_EVENTS_UI_URL
        registration_term = "registrations"
    else:
        expected_subject = expected_subject or "Oikeudet myönnetty osallistujalistaan"
        assert mail.outbox[0].subject.startswith(expected_subject)

        expected_body = expected_body or (
            f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty oikeudet lukea "
            f"tapahtuman <strong>{event_name}</strong> osallistujalista."
        )
        assert expected_body in email_body_string

        service_base_url = settings.LINKED_REGISTRATIONS_UI_URL
        registration_term = "registration"

    participant_list_url = (
        f"{service_base_url}/{ui_locale}/{registration_term}/"
        f"{registration_user_access.registration_id}/attendance-list/"
    )
    assert participant_list_url in email_body_string


def assert_payment_link_email_sent(
    contact_person, signup_payment, expected_subject, expected_text
):
    # Email has been sent to the contact person.
    assert len(mail.outbox) == 2  # second email = cancellation email
    email_html_body = str(mail.outbox[0].alternatives[0])
    assert mail.outbox[0].to[0] == contact_person.email
    assert mail.outbox[0].subject == expected_subject
    assert expected_text in email_html_body

    # Payment link is in the email.
    assert len(signup_payment.logged_in_checkout_url) > 1
    assert signup_payment.logged_in_checkout_url in email_html_body


def assert_attending_and_waitlisted_signups(
    response,
    expected_status_code: int = status.HTTP_201_CREATED,
    expected_signups_count: int = 2,
    expected_attending: int = 2,
    expected_waitlisted: int = 0,
) -> None:
    assert SignUp.objects.count() == expected_signups_count
    assert (
        SignUp.objects.filter(attendee_status=SignUp.AttendeeStatus.ATTENDING).count()
        == expected_attending
    )
    assert (
        SignUp.objects.filter(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST
        ).count()
        == expected_waitlisted
    )

    assert response.status_code == expected_status_code
    if expected_status_code == status.HTTP_403_FORBIDDEN:
        assert response.json()["detail"] == "The waiting list is already full"


def create_user_by_role(
    user_role: str,
    organization: Optional[Organization] = None,
    additional_roles: Optional[dict] = None,
) -> User:
    user = UserFactory(is_superuser=user_role == "superuser")

    user_role_mapping = {
        "superuser": lambda usr: None,
        "admin": lambda usr: usr.admin_organizations.add(organization)
        if organization
        else None,
        "registration_admin": lambda usr: usr.registration_admin_organizations.add(
            organization
        )
        if organization
        else None,
        "financial_admin": lambda usr: usr.financial_admin_organizations.add(
            organization
        )
        if organization
        else None,
        "regular_user": lambda usr: usr.organization_memberships.add(organization)
        if organization
        else None,
    }
    if isinstance(additional_roles, dict):
        user_role_mapping.update(additional_roles)

    # Apply role to user.
    user_role_mapping[user_role](user)

    return user


def get_web_store_order_response(payment_amount: Optional[Decimal] = None):
    resp_json = DEFAULT_CREATE_ORDER_RESPONSE_JSON.copy()

    if payment_amount is not None:
        resp_json["priceTotal"] = str(payment_amount)

    return resp_json


def get_web_store_failed_order_response(
    web_store_api_status_code=status.HTTP_400_BAD_REQUEST, has_web_store_api_errors=True
):
    response = Mock(status_code=status.HTTP_400_BAD_REQUEST)

    web_store_api_response = Mock(status_code=web_store_api_status_code)
    web_store_api_response.json.return_value = (
        DEFAULT_CREATE_ORDER_ERROR_RESPONSE if has_web_store_api_errors else {}
    )
    response.raise_for_status.side_effect = RequestException(
        response=web_store_api_response
    )

    return response


def assert_signup_payment_data_is_correct(
    payment_data,
    user,
    signup: Optional[SignUp] = None,
    signup_group: Optional[SignUpGroup] = None,
):
    if signup:
        assert Decimal(payment_data["amount"]) == signup.total_payment_amount
    else:
        assert Decimal(payment_data["amount"]) == signup_group.total_payment_amount
    assert payment_data["status"] == SignUpPayment.PaymentStatus.CREATED
    assert (
        payment_data["external_order_id"]
        == DEFAULT_CREATE_ORDER_RESPONSE_JSON["orderId"]
    )
    assert (
        payment_data["checkout_url"]
        == DEFAULT_CREATE_ORDER_RESPONSE_JSON["checkoutUrl"]
    )
    assert (
        payment_data["logged_in_checkout_url"]
        == DEFAULT_CREATE_ORDER_RESPONSE_JSON["loggedInCheckoutUrl"]
    )
    assert payment_data["created_by"] == str(user)
    assert payment_data["created_time"] is not None

    signup_payment = SignUpPayment.objects.first()
    if signup:
        assert signup_payment.signup_group_id is None
        assert signup_payment.signup_id == signup.pk
        assert signup_payment.amount == signup.total_payment_amount
    else:
        assert signup_payment.signup_group_id == signup_group.pk
        assert signup_payment.signup_id is None
        assert signup_payment.amount == signup_group.total_payment_amount
    assert signup_payment.status == SignUpPayment.PaymentStatus.CREATED
    assert (
        signup_payment.external_order_id
        == DEFAULT_CREATE_ORDER_RESPONSE_JSON["orderId"]
    )
    assert (
        signup_payment.checkout_url == DEFAULT_CREATE_ORDER_RESPONSE_JSON["checkoutUrl"]
    )
    assert (
        signup_payment.logged_in_checkout_url
        == DEFAULT_CREATE_ORDER_RESPONSE_JSON["loggedInCheckoutUrl"]
    )
    assert signup_payment.created_by_id == user.id
    assert signup_payment.created_time is not None
