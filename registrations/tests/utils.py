from typing import Optional

from django.core import mail
from django_orghierarchy.models import Organization

from helevents.models import User
from helevents.tests.factories import UserFactory


def assert_invitation_email_is_sent(email: str, event_name: str) -> None:
    assert mail.outbox[0].to[0] == email
    assert mail.outbox[0].subject.startswith("Oikeudet myönnetty osallistujalistaan")
    assert (
        f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty oikeudet lukea "
        f"tapahtuman <strong>{event_name}</strong> osallistujalista."
        in str(mail.outbox[0].alternatives[0])
    )


def create_user_by_role(
    user_role: str, organization: Organization, additional_roles: Optional[dict] = None
) -> User:
    user = UserFactory(is_superuser=user_role == "superuser")

    user_role_mapping = {
        "superuser": lambda usr: None,
        "admin": lambda usr: usr.admin_organizations.add(organization),
        "registration_admin": lambda usr: usr.registration_admin_organizations.add(
            organization
        ),
        "financial_admin": lambda usr: usr.financial_admin_organizations.add(
            organization
        ),
        "regular_user": lambda usr: usr.organization_memberships.add(organization),
    }
    if isinstance(additional_roles, dict):
        user_role_mapping.update(additional_roles)

    # Apply role to user.
    user_role_mapping[user_role](user)

    return user
