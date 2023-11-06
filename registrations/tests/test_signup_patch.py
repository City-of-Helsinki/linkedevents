from unittest.mock import patch, PropertyMock

import pytest
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpProtectedDataFactory,
)

# === util methods ===


def patch_signup(api_client, signup_pk, signup_data):
    signup_url = reverse(
        "signup-detail",
        kwargs={"pk": signup_pk},
    )

    response = api_client.patch(signup_url, signup_data, format="json")
    return response


def assert_patch_signup(api_client, signup_pk, signup_data):
    response = patch_signup(api_client, signup_pk, signup_data)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == signup_pk

    return response


# === tests ===


@pytest.mark.parametrize(
    "user_role,allowed_to_patch",
    [
        ("admin", False),
        ("registration_admin", True),
        ("registration_user_superuser", True),
        ("registration_user_admin", True),
        ("created_user", False),
    ],
)
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_can_patch_presence_status_of_signup_based_on_role(
    api_client, registration, user_role, allowed_to_patch
):
    user = UserFactory(is_superuser=user_role == "registration_user_superuser")

    if user_role in ("registration_user_superuser", "registration_user_admin"):
        RegistrationUserAccessFactory(registration=registration, email=user.email)

    user_role_mapping = {
        "admin": lambda usr: usr.admin_organizations.add(registration.publisher),
        "registration_admin": lambda usr: usr.registration_admin_organizations.add(
            registration.publisher
        ),
        "registration_user_admin": lambda usr: usr.registration_admin_organizations.add(
            registration.publisher
        ),
        "registration_user_superuser": lambda usr: None,
        "created_user": lambda usr: None,
    }
    user_role_mapping[user_role](user)

    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "created_user" else None,
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = patch_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()

    if allowed_to_patch:
        assert response.status_code == status.HTTP_200_OK
        assert response.data["presence_status"] == SignUp.PresenceStatus.PRESENT
        assert signup.presence_status == SignUp.PresenceStatus.PRESENT
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_patch_extra_info_of_signup_with_empty_data(api_client, registration, signup):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)

    signup = SignUpFactory(registration=registration)
    SignUpProtectedDataFactory(
        signup=signup, registration=registration, extra_info="Extra info"
    )
    assert signup.extra_info == "Extra info"

    api_client.force_authenticate(user)

    signup_data = {
        "extra_info": "",
    }

    assert_patch_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    del signup.extra_info
    assert signup.extra_info == ""


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_patch_user_consent(api_client, registration, signup):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    assert signup.user_consent is False

    signup_data = {
        "user_consent": True,
    }
    assert_patch_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.user_consent is True


@pytest.mark.django_db
def test_registration_user_who_created_signup_can_patch_presence_status(
    api_client, event
):
    user = UserFactory()

    registration = RegistrationFactory(
        event=event,
    )

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(
        registration=registration,
        phone_number="0441234567",
        street_address="Street address",
        created_by=user,
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        assert_patch_signup(api_client, signup.id, signup_data)
        assert mocked.called is True

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.PRESENT


@pytest.mark.parametrize("identification_method", ["heltunnistussuomifi", None])
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_user_can_patch_signup_presence_status_based_on_identification_method(
    api_client, registration, user, identification_method
):
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(registration=registration)
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=identification_method,
    ) as mocked:
        response = patch_signup(api_client, signup.id, signup_data)
        assert mocked.called is True

    signup.refresh_from_db()

    if identification_method is None:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    else:
        assert response.status_code == status.HTTP_200_OK
        assert signup.presence_status == SignUp.PresenceStatus.PRESENT


@pytest.mark.django_db
def test_cannot_remove_only_responsible_person_from_group_through_patch(
    api_client, registration
):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration, signup_group=signup_group)
    responsible_signup = SignUpFactory(
        registration=registration, signup_group=signup_group, responsible_for_group=True
    )

    signup_data = {
        "responsible_for_group": False,
    }

    response = patch_signup(api_client, responsible_signup.id, signup_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["responsible_for_group"][0] == (
        "Cannot set responsible_for_group to False for the only responsible person of a group"
    )


@pytest.mark.django_db
def test_signup_id_is_audit_logged_on_patch(api_client, signup):
    user = UserFactory()
    user.registration_admin_organizations.add(signup.publisher)
    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    assert_patch_signup(api_client, signup.pk, signup_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [signup.pk]
