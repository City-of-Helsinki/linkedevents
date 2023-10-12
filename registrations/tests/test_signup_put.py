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

new_signup_name = "Edited name"
new_date_of_birth = "2015-01-01"

# === util methods ===


def update_signup(api_client, signup_pk, signup_data, query_string=None):
    signup_url = reverse(
        "signup-detail",
        kwargs={"pk": signup_pk},
    )

    if query_string:
        signup_url = "%s?%s" % (signup_url, query_string)

    response = api_client.put(signup_url, signup_data, format="json")
    return response


def assert_update_signup(api_client, signup_pk, signup_data, query_string=None):
    response = update_signup(api_client, signup_pk, signup_data, query_string)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == signup_pk

    return response


# === tests ===


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_admin_can_update_signup(
    user_api_client, registration, signup, user
):
    user.get_default_organization().registration_admin_users.add(user)

    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name != new_signup_name
    assert db_signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    assert_update_signup(user_api_client, signup.id, signup_data)
    db_signup.refresh_from_db()
    assert db_signup.first_name == new_signup_name
    assert db_signup.last_modified_by_id == user.id


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_created_admin_can_update_signup(registration, user, user_api_client):
    signup = SignUpFactory(registration=registration, created_by=user)
    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    assert_update_signup(user_api_client, signup.id, signup_data)
    signup.refresh_from_db()
    assert signup.first_name == new_signup_name
    assert signup.last_modified_by_id == user.id


@pytest.mark.django_db
def test_can_update_signup_with_empty_extra_info_and_date_of_birth(
    user, user_api_client, registration
):
    signup = SignUpFactory(
        registration=registration,
        created_by=user,
    )
    SignUpProtectedDataFactory(
        signup=signup,
        registration=registration,
        extra_info="Old extra info",
        date_of_birth="2023-10-03",
    )
    assert signup.extra_info == "Old extra info"
    assert signup.date_of_birth == "2023-10-03"
    assert signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "extra_info": "",
        "date_of_birth": None,
    }

    assert_update_signup(user_api_client, signup.id, signup_data)

    signup.refresh_from_db()
    del signup.extra_info
    del signup.date_of_birth

    assert signup.extra_info == ""
    assert signup.date_of_birth is None
    assert signup.last_modified_by_id == user.id


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_non_created_admin_cannot_update_signup(registration, user_api_client):
    signup = SignUpFactory(registration=registration)
    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup.refresh_from_db()
    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_created_regular_user_can_update_signup(
    user_api_client, registration, signup, user
):
    signup.created_by = user
    signup.save(update_fields=["created_by"])

    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name != new_signup_name
    assert db_signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    assert_update_signup(user_api_client, signup.id, signup_data)

    db_signup.refresh_from_db()
    assert db_signup.first_name == new_signup_name
    assert db_signup.last_modified_by_id == user.id


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.parametrize("is_organization_member", [False, True])
@pytest.mark.django_db
def test_created_regular_user_cannot_update_signup_presence_status(
    api_client, registration, is_organization_member
):
    user = UserFactory()
    if is_organization_member:
        user.organization_memberships.add(registration.publisher)

    signup = SignUpFactory(registration=registration, created_by=user)

    new_signup_name = "Edited name"

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": "2015-01-01",
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    api_client.force_authenticate(user)

    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup.refresh_from_db()
    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_non_created_regular_user_cannot_update_signup(
    user_api_client, registration, signup, user
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name != new_signup_name
    assert db_signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    db_signup.refresh_from_db()
    assert db_signup.first_name != new_signup_name
    assert db_signup.last_modified_by_id is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_created_user_without_organization_can_update_signup(api_client, registration):
    user = UserFactory()
    api_client.force_authenticate(user)
    signup = SignUpFactory(registration=registration, created_by=user)

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    assert_update_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.first_name == new_signup_name
    assert signup.last_modified_by_id == user.id


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_non_created_user_without_organization_cannot_update_signup(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)
    signup = SignUpFactory(registration=registration)

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    signup.refresh_from_db()
    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_cannot_update_attendee_status_of_signup(
    registration, signup, user_api_client, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup.attendee_status = SignUp.AttendeeStatus.ATTENDING
    signup.save()

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
        "attendee_status": SignUp.AttendeeStatus.WAITING_LIST,
    }

    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["attendee_status"]
        == "You may not change the attendee_status of an existing object."
    )


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_cannot_update_registration_of_signup(
    registration, registration2, signup, user_api_client, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_data = {
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
        "registration": registration2.id,
    }

    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["registration"]
        == "You may not change the registration of an existing object."
    )


@pytest.mark.django_db
def test_registration_user_access_cannot_update_signup(
    registration, signup, api_client
):
    user = UserFactory()

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    api_client.force_authenticate(user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        response = update_signup(api_client, signup.id, signup_data)
        assert mocked.called is True

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_registration_user_access_who_created_signup_can_update(
    registration, api_client
):
    user = UserFactory()

    RegistrationUserAccessFactory(registration=registration, email=user.email)
    signup = SignUpFactory(
        registration=registration,
        first_name="Name",
        created_by=user,
    )

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }

    api_client.force_authenticate(user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        assert_update_signup(api_client, signup.id, signup_data)
        assert mocked.called is True


@pytest.mark.parametrize("admin_type", ["superuser", "registration_admin"])
@pytest.mark.django_db
def test_registration_user_access_who_is_superuser_or_registration_admin_can_update_signup(
    registration, signup, api_client, admin_type
):
    user = UserFactory(is_superuser=True if admin_type == "superuser" else False)
    if admin_type == "registration_admin":
        user.registration_admin_organizations.add(registration.publisher)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup_data = {
        "registration": registration.id,
        "first_name": "Edited name",
        "date_of_birth": "2015-01-01",
    }

    assert signup.first_name != signup_data["first_name"]
    assert signup.date_of_birth is None

    api_client.force_authenticate(user)

    assert_update_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    del signup.date_of_birth
    assert signup.first_name == signup_data["first_name"]
    assert signup.date_of_birth.strftime("%Y-%m-%d") == signup_data["date_of_birth"]


@pytest.mark.django_db
def test_regular_user_cannot_update_signup(registration, signup, user, user_api_client):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }
    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_api_key_with_organization_and_registration_permission_can_update_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.user_editable_registrations = True
    data_source.owner = organization
    data_source.save(update_fields=["user_editable_registrations", "owner"])
    api_client.credentials(apikey=data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }
    assert_update_signup(api_client, signup.id, signup_data)


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_api_key_with_organization_without_registration_permission_cannot_update_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.save(update_fields=["owner"])
    api_client.credentials(apikey=data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }
    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_of_other_organization_cannot_update_signup(
    api_client, data_source, organization2, registration, signup
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }
    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_cannot_update_signup(
    api_client, organization, other_data_source, registration, signup
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }
    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_unknown_api_key_cannot_update_signup(api_client, registration, signup):
    api_client.credentials(apikey="unknown")

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }
    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_registration_admin_can_update_signup_regardless_of_non_user_editable_resources(
    data_source,
    organization,
    registration,
    signup,
    user_api_client,
    user,
    user_editable_resources,
):
    user.get_default_organization().registration_admin_users.add(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
    }
    assert_update_signup(user_api_client, signup.id, signup_data)


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_signup_text_fields_are_sanitized(user_api_client, registration, user):
    user.get_default_organization().registration_admin_users.add(user)

    signup = SignUpFactory(registration=registration)
    signup_data = {
        "registration": registration.id,
        "first_name": "Michael <p>Html</p>",
        "last_name": "Jackson <p>Html</p>",
        "extra_info": "Extra info <p>Html</p>",
        "phone_number": "<p>0441111111</p>",
        "street_address": "Edited street address <p>Html</p>",
        "zipcode": "<p>zip</p>",
    }

    assert_update_signup(user_api_client, signup.id, signup_data)
    signup.refresh_from_db()
    assert signup.last_modified_by_id == user.id
    assert signup.first_name == "Michael Html"
    assert signup.last_name == "Jackson Html"
    assert signup.extra_info == "Extra info Html"
    assert signup.phone_number == "0441111111"
    assert signup.street_address == "Edited street address Html"
    assert signup.zipcode == "zip"
