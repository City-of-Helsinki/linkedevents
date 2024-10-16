from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core import mail
from django.utils.html import conditional_escape
from django.utils.timezone import localtime
from django_orghierarchy.models import Organization
from rest_framework import status

from events.models import Event
from events.tests.utils import versioned_reverse as reverse
from helevents.models import User
from helevents.tests.factories import UserFactory
from registrations.models import (
    RegistrationUserAccess,
    SignUp,
    SignUpGroup,
    SignUpPayment,
)
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpContactPersonFactory,
    SignUpGroupFactory,
    SignUpPaymentFactory,
    SignUpPriceGroupFactory,
)
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_GET_ORDER_DATA,
    DEFAULT_ORDER_ID,
)

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
    first_email = mail.outbox[0]
    assert first_email.to[0] == email

    ui_locale = ui_locale or "fi"
    email_body_string = str(first_email.alternatives[0])

    if registration_user_access.is_substitute_user:
        expected_subject = expected_subject or "Oikeudet myönnetty ilmoittautumiseen"
        expected_body = expected_body or (
            f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty sijaisen käyttöoikeudet "
            f"tapahtuman <strong>{event_name}</strong> ilmoittautumiselle."
        )

        service_base_url = settings.LINKED_EVENTS_UI_URL
        registration_term = "registrations"
    else:
        expected_subject = expected_subject or "Oikeudet myönnetty osallistujalistaan"
        expected_body = expected_body or (
            f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty oikeudet lukea "
            f"tapahtuman <strong>{event_name}</strong> osallistujalista."
        )
        service_base_url = settings.LINKED_REGISTRATIONS_UI_URL
        registration_term = "registration"

    assert first_email.subject.startswith(expected_subject)
    assert expected_body in email_body_string

    participant_list_url = (
        f"{service_base_url}/{ui_locale}/{registration_term}/"
        f"{registration_user_access.registration_id}/attendance-list/"
    )
    assert participant_list_url in email_body_string


def assert_payment_link_email_sent(
    contact_person,
    signup_payment,
    expected_mailbox_length=1,
    expected_subject="",
    expected_text="",
):
    # Email has been sent to the contact person.
    assert len(mail.outbox) == expected_mailbox_length
    email_html_body = str(mail.outbox[0].alternatives[0])
    assert mail.outbox[0].to[0] == contact_person.email
    assert mail.outbox[0].subject == expected_subject
    assert expected_text in email_html_body

    # Payment link is in the email.
    assert len(signup_payment.checkout_url) > 1
    assert conditional_escape(signup_payment.checkout_url) in email_html_body


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
        "admin": lambda usr: (
            usr.admin_organizations.add(organization) if organization else None
        ),
        "registration_admin": lambda usr: (
            usr.registration_admin_organizations.add(organization)
            if organization
            else None
        ),
        "financial_admin": lambda usr: (
            usr.financial_admin_organizations.add(organization)
            if organization
            else None
        ),
        "regular_user": lambda usr: (
            usr.organization_memberships.add(organization) if organization else None
        ),
    }
    if isinstance(additional_roles, dict):
        user_role_mapping.update(additional_roles)

    # Apply role to user.
    user_role_mapping[user_role](user)

    return user


def assert_signup_payment_data_is_correct(
    payment_data,
    user,
    signup: Optional[SignUp] = None,
    signup_group: Optional[SignUpGroup] = None,
    service_language: Optional[str] = None,
):
    checkout_url = DEFAULT_GET_ORDER_DATA["checkoutUrl"]
    logged_in_checkout_url = DEFAULT_GET_ORDER_DATA["loggedInCheckoutUrl"]
    if service_language:
        checkout_url += f"&lang={service_language}"
        logged_in_checkout_url += f"?lang={service_language}"

    if signup:
        assert Decimal(payment_data["amount"]) == signup.total_payment_amount
    else:
        assert Decimal(payment_data["amount"]) == signup_group.total_payment_amount
    assert payment_data["status"] == SignUpPayment.PaymentStatus.CREATED
    assert payment_data["external_order_id"] == DEFAULT_GET_ORDER_DATA["orderId"]
    assert payment_data["checkout_url"] == checkout_url
    assert payment_data["logged_in_checkout_url"] == logged_in_checkout_url
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
    assert signup_payment.external_order_id == DEFAULT_GET_ORDER_DATA["orderId"]
    assert signup_payment.checkout_url == checkout_url
    assert signup_payment.logged_in_checkout_url == logged_in_checkout_url
    assert signup_payment.created_by_id == user.id
    assert signup_payment.created_time is not None


def create_signup_group_with_payment(
    registration, payment_status=SignUpPayment.PaymentStatus.PAID, service_language=None
):
    signup_group = SignUpGroupFactory(registration=registration)

    contact_person_kwargs = {
        "signup_group": signup_group,
        "email": "test@test.com",
    }
    if service_language:
        contact_person_kwargs["service_language"] = service_language
    SignUpContactPersonFactory(**contact_person_kwargs)

    SignUpPaymentFactory(
        signup_group=signup_group,
        signup=None,
        external_order_id=DEFAULT_ORDER_ID,
        status=payment_status,
    )

    return signup_group


def update_price_group_price(price_group, new_price):
    price_group.price = new_price
    price_group.calculate_vat_and_price_without_vat()
    price_group.save()


def create_price_group(price_group_kwargs=None, price=None):
    price_group_kwargs = price_group_kwargs or {}
    price_group = SignUpPriceGroupFactory(**price_group_kwargs)

    if price is not None:
        update_price_group_price(price_group, price)

    return price_group


def create_price_group_for_recurring_event(event_name=None, price=None):
    now = localtime()

    registration_kwargs = {
        "event__start_time": now,
        "event__end_time": now + timedelta(days=28),
        "event__super_event_type": Event.SuperEventType.RECURRING,
    }
    if event_name:
        registration_kwargs["event__name"] = event_name
    registration = RegistrationFactory(**registration_kwargs)

    return create_price_group({"signup__registration": registration}, price=price)


def get_registration_merchant_data(merchant, update_data=None):
    data = {
        "registration_merchant": {
            "merchant": merchant.pk,
        },
    }

    if update_data:
        data.update(update_data)

    return data


def get_registration_account_data(account, update_data=None):
    data = {
        "registration_account": {
            "account": account.pk,
            "name": account.name,
            "company_code": account.company_code,
            "main_ledger_account": account.main_ledger_account,
            "balance_profit_center": account.balance_profit_center,
            "internal_order": account.internal_order,
            "profit_center": account.profit_center,
            "project": account.project,
            "operation_area": account.operation_area,
        },
    }

    if update_data:
        data.update(update_data)

    return data


def get_registration_merchant_and_account_data(
    merchant, account, merchant_update_data=None, account_update_data=None
):
    return {
        **get_registration_merchant_data(merchant, update_data=merchant_update_data),
        **get_registration_account_data(account, update_data=account_update_data),
    }


def get_event_url(detail_pk):
    return reverse("event-detail", kwargs={"pk": detail_pk})


def get_minimal_required_registration_data(event_id):
    return {
        "event": {"@id": get_event_url(event_id)},
        "maximum_attendee_capacity": 1000000,
    }
