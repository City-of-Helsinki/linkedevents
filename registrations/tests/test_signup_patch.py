import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import MandatoryFields, SignUp
from registrations.tests.factories import RegistrationUserAccessFactory

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


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__registration_admin_can_patch_presence_status_of_signup(
    api_client, registration, signup, user
):
    user.get_default_organization().registration_admin_users.add(user)

    registration.audience_min_age = 10
    registration.mandatory_fields = [
        MandatoryFields.PHONE_NUMBER,
        MandatoryFields.STREET_ADDRESS,
    ]
    registration.save()
    signup.date_of_birth = "2011-01-01"
    signup.phone_number = "0441234567"
    signup.street_address = "Street address"
    signup.save()
    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = assert_patch_signup(api_client, signup.id, signup_data)
    assert response.data["presence_status"] == SignUp.PresenceStatus.PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__registration_user_can_patch_presence_status_of_signup(
    api_client, registration, signup, user
):
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    registration.audience_min_age = 10
    registration.mandatory_fields = [
        MandatoryFields.PHONE_NUMBER,
        MandatoryFields.STREET_ADDRESS,
    ]
    registration.save()

    signup.date_of_birth = "2011-01-01"
    signup.phone_number = "0441234567"
    signup.street_address = "Street address"
    signup.save(update_fields=["date_of_birth", "phone_number", "street_address"])

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = assert_patch_signup(api_client, signup.id, signup_data)
    assert response.data["presence_status"] == SignUp.PresenceStatus.PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__admin_cannot_patch_presence_status_of_signup(
    api_client, registration, signup, user
):
    user.get_default_organization().admin_users.add(user)

    registration.audience_min_age = 10
    registration.mandatory_fields = [
        MandatoryFields.PHONE_NUMBER,
        MandatoryFields.STREET_ADDRESS,
    ]
    registration.save()

    signup.date_of_birth = "2011-01-01"
    signup.phone_number = "0441234567"
    signup.street_address = "Street address"
    signup.save()

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = patch_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__created_user_cannot_patch_presence_status_of_signup(
    api_client, registration, signup, user
):
    registration.audience_min_age = 10
    registration.mandatory_fields = [
        MandatoryFields.PHONE_NUMBER,
        MandatoryFields.STREET_ADDRESS,
    ]
    registration.save()

    signup.date_of_birth = "2011-01-01"
    signup.phone_number = "0441234567"
    signup.street_address = "Street address"
    signup.created_by = user
    signup.save(
        update_fields=["date_of_birth", "phone_number", "street_address", "created_by"]
    )

    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = patch_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
