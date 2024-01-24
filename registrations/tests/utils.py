from typing import Optional

from django.conf import settings
from django.core import mail
from django_orghierarchy.models import Organization
from rest_framework import status

from helevents.models import User
from helevents.tests.factories import UserFactory
from registrations.models import RegistrationUserAccess, SignUp


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
