from unittest.mock import patch, PropertyMock

import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import MandatoryFields, SignUp
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
    SignUpFactory,
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
def test_registration_admin_can_patch_presence_status_of_signup(api_client, event):
    user = UserFactory()
    user.registration_admin_organizations.add(event.publisher)

    registration = RegistrationFactory(
        event=event,
        audience_min_age=10,
        mandatory_fields=[MandatoryFields.PHONE_NUMBER, MandatoryFields.STREET_ADDRESS],
    )

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
def test_registration_user_can_patch_signup_presence_status_signup_if_strongly_identified(
    api_client, event, user
):
    registration = RegistrationFactory(
        event=event,
        audience_min_age=10,
        mandatory_fields=[MandatoryFields.PHONE_NUMBER, MandatoryFields.STREET_ADDRESS],
    )

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
def test_registration_user_cannot_patch_signup_presence_status_signup_if_not_strongly_identified(
    api_client, event, user
):
    registration = RegistrationFactory(
        event=event,
        audience_min_age=10,
        mandatory_fields=[MandatoryFields.PHONE_NUMBER, MandatoryFields.STREET_ADDRESS],
    )

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
def test_admin_cannot_patch_presence_status_of_signup(user_api_client, event, signup):
    registration = RegistrationFactory(
        event=event,
        audience_min_age=10,
        mandatory_fields=[MandatoryFields.PHONE_NUMBER, MandatoryFields.STREET_ADDRESS],
    )

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
def test_created_user_cannot_patch_presence_status_of_signup(api_client, event, user):
    registration = RegistrationFactory(
        event=event,
        audience_min_age=10,
        mandatory_fields=[MandatoryFields.PHONE_NUMBER, MandatoryFields.STREET_ADDRESS],
    )

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
