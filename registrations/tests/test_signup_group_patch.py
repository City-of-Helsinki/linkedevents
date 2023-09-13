from unittest.mock import patch, PropertyMock

import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
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
    first_signup = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="signup1 extra info",
    )
    second_signup = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="signup2 extra info",
    )

    signup_group_data = {"extra_info": "signup group extra info"}

    assert signup_group.extra_info is None
    assert first_signup.extra_info == "signup1 extra info"
    assert second_signup.extra_info == "signup2 extra info"

    api_client.force_authenticate(user)

    response = patch_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    first_signup.refresh_from_db()
    second_signup.refresh_from_db()

    if allowed_to_patch:
        assert response.status_code == status.HTTP_200_OK
        assert response.data["extra_info"] == signup_group_data["extra_info"]
        assert signup_group.extra_info == signup_group_data["extra_info"]
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert signup_group.extra_info is None

    assert first_signup.extra_info == "signup1 extra info"
    assert second_signup.extra_info == "signup2 extra info"


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
            {"id": second_signup.pk, "extra_info": "signup2 extra info"},
        ]
    }

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None

    api_client.force_authenticate(user)

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    assert first_signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info == "signup2 extra info"


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
