from unittest.mock import patch, PropertyMock

import pytest
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.notifications import NotificationType
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
)

# === util methods ===


def patch_signup_group(api_client, signup_group_pk, signup_group_data):
    signup_group_url = reverse(
        "signupgroup-detail",
        kwargs={"pk": signup_group_pk},
    )

    response = api_client.patch(signup_group_url, signup_group_data, format="json")
    return response


def assert_patch_signup_group(api_client, signup_group_pk, signup_group_data):
    response = patch_signup_group(api_client, signup_group_pk, signup_group_data)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == signup_group_pk

    return response


# === tests ===


@pytest.mark.parametrize(
    "user_role,allowed_to_patch",
    [
        ("admin", False),
        ("registration_admin", True),
        ("regular", False),
        ("superuser", True),
    ],
)
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_patch_signup_group_extra_info_based_on_user_role(
    api_client, event, user_role, allowed_to_patch
):
    user = UserFactory(is_superuser=True if user_role == "superuser" else False)
    api_client.force_authenticate(user)

    other_user = UserFactory()

    user_role_mapping = {
        "admin": lambda usr: usr.admin_organizations.add(event.publisher),
        "registration_admin": lambda usr: usr.registration_admin_organizations.add(
            event.publisher
        ),
        "regular": lambda usr: usr.organization_memberships.add(event.publisher),
        "superuser": lambda usr: None,
    }
    user_role_mapping[user_role](user)

    registration = RegistrationFactory(event=event)

    signup_group = SignUpGroupFactory(registration=registration, created_by=other_user)
    assert signup_group.extra_info is None

    signup_group_data = {"extra_info": "signup group extra info"}
    response = patch_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    del signup_group.extra_info  # refresh cached_property

    if allowed_to_patch:
        assert response.status_code == status.HTTP_200_OK
        assert response.data["extra_info"] == signup_group_data["extra_info"]
        assert signup_group.extra_info == signup_group_data["extra_info"]
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert signup_group.extra_info is None


@pytest.mark.parametrize("admin_type", ["superuser", "registration_admin"])
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_user_who_is_superuser_or_registration_admin_can_patch_signups_data(
    api_client, registration, admin_type
):
    user = UserFactory(is_superuser=True if admin_type == "superuser" else False)
    if admin_type == "registration_admin":
        user.registration_admin_organizations.add(registration.publisher)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {
                "id": second_signup.pk,
                "extra_info": "signup2 extra info",
                "user_consent": True,
            },
        ]
    }

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None
    assert second_signup.user_consent is False

    api_client.force_authenticate(user)

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    del first_signup.extra_info
    del second_signup.extra_info

    assert first_signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info == "signup2 extra info"
    assert second_signup.user_consent is True


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_user_who_created_signup_group_can_patch_signups_data(
    api_client, registration
):
    user = UserFactory()
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    first_signup = SignUpFactory(
        signup_group=signup_group, registration=registration, created_by=user
    )
    second_signup = SignUpFactory(
        signup_group=signup_group, registration=registration, created_by=user
    )

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {
                "id": second_signup.pk,
                "extra_info": "signup2 extra info",
                "user_consent": True,
            },
        ]
    }

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None
    assert second_signup.user_consent is False

    api_client.force_authenticate(user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        assert_patch_signup_group(api_client, signup_group.id, signup_group_data)
        assert mocked.called is True

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    del first_signup.extra_info  # refresh cached_property
    del second_signup.extra_info  # refresh cached_property

    assert first_signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info == "signup2 extra info"
    assert second_signup.user_consent is True


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "regular",
    ],
)
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_admin_or_regular_user_cannot_patch_signups_data(
    api_client, registration, user_role
):
    user = UserFactory()

    if user_role == "admin":
        user.admin_organizations.add(registration.publisher)
    else:
        user.organization_memberships.add(registration.publisher)

    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {"id": second_signup.pk, "extra_info": "signup2 extra info"},
        ]
    }

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None

    api_client.force_authenticate(user)

    response = patch_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    del first_signup.extra_info
    del second_signup.extra_info

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_user_can_patch_signups_presence_status_if_strongly_identified(
    api_client, registration, user
):
    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
        ]
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        assert_patch_signup_group(api_client, signup_group.id, signup_group_data)
        assert mocked.called is True

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    assert first_signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_user_cannot_patch_signups_presence_status_if_not_strongly_identified(
    api_client, registration, user
):
    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
        ]
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=None,
    ) as mocked:
        response = patch_signup_group(api_client, signup_group.id, signup_group_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert mocked.called is True

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_created_user_cannot_patch_presence_status_of_signups(
    api_client, registration, user
):
    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
        ]
    }

    response = patch_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_can_patch_signup_group_contact_person(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    SignUpFactory(signup_group=signup_group, registration=registration)
    contact_person = SignUpContactPersonFactory(signup_group=signup_group)

    assert contact_person.notifications == NotificationType.NO_NOTIFICATION
    assert contact_person.membership_number is None

    signup_group_data = {
        "contact_person": {
            "notifications": NotificationType.EMAIL,
            "membership_number": "1234",
        },
    }

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    contact_person.refresh_from_db()
    assert contact_person.notifications == NotificationType.EMAIL
    assert contact_person.membership_number == "1234"


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_missing_contact_person_created_on_patch(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)

    assert getattr(signup_group, "contact_person", None) is None
    assert getattr(signup, "contact_person", None) is None

    signup_group_data = {
        "contact_person": {
            "notifications": NotificationType.EMAIL,
            "membership_number": "1234",
        },
    }

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    signup.refresh_from_db()
    assert signup_group.contact_person.notifications == NotificationType.EMAIL
    assert signup_group.contact_person.membership_number == "1234"
    assert getattr(signup, "contact_person", None) is None


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_patch(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    signup_group_data = {"extra_info": "test test"}

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        signup_group.pk
    ]
