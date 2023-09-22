from unittest.mock import patch, PropertyMock

import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SignUpFactory,
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


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_admin_can_patch_presence_status_of_signup(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)

    signup = SignUpFactory(
        registration=registration,
        date_of_birth="2011-01-01",
        phone_number="0441234567",
        street_address="Street address",
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = assert_patch_signup(api_client, signup.id, signup_data)
    assert response.data["presence_status"] == SignUp.PresenceStatus.PRESENT

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.PRESENT


@pytest.mark.parametrize("admin_type", ["superuser", "registration_admin"])
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_user_who_is_superuser_or_registration_admin_can_patch_signup_presence_status(
    api_client, registration, admin_type
):
    user = UserFactory(is_superuser=True if admin_type == "superuser" else False)
    if admin_type == "registration_admin":
        user.registration_admin_organizations.add(registration.publisher)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(
        registration=registration,
        date_of_birth="2011-01-01",
        phone_number="0441234567",
        street_address="Street address",
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    assert_patch_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.PRESENT


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
def test_registration_user_can_patch_signup_presence_status_if_strongly_identified(
    api_client, registration, user
):
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(
        registration=registration,
        date_of_birth="2011-01-01",
        phone_number="0441234567",
        street_address="Street address",
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


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_user_cannot_patch_signup_presence_status_if_not_strongly_identified(
    api_client, registration, user
):
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(
        registration=registration,
        date_of_birth="2011-01-01",
        phone_number="0441234567",
        street_address="Street address",
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=None,
    ) as mocked:
        response = patch_signup(api_client, signup.id, signup_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert mocked.called is True

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_admin_cannot_patch_presence_status_of_signup(user_api_client, registration):
    signup = SignUpFactory(
        registration=registration,
        date_of_birth="2011-01-01",
        phone_number="0441234567",
        street_address="Street address",
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = patch_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_created_user_cannot_patch_presence_status_of_signup(api_client, registration, user):
    signup = SignUpFactory(
        registration=registration,
        date_of_birth="2011-01-01",
        phone_number="0441234567",
        street_address="Street address",
        created_by=user,
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = patch_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
