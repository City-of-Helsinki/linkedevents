import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import RegistrationUserAccess, SignUp

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
def test__registration_admin_can_update_signup(
    user_api_client, registration, signup, user
):
    user.get_default_organization().registration_admin_users.add(user)

    new_signup_name = "Edited name"

    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name != new_signup_name
    assert db_signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": "2015-01-01",
    }

    assert_update_signup(user_api_client, signup.id, signup_data)
    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name == new_signup_name
    assert db_signup.last_modified_by_id == user.id


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__regular_admin_cannot_update_signup(user_api_client, registration, signup):
    new_signup_name = "Edited name"

    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name != new_signup_name
    assert db_signup.first_name == signup.first_name
    assert db_signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": "2015-01-01",
    }

    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name == signup.first_name
    assert db_signup.last_modified_by_id is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__created_regular_user_can_update_signup(
    user_api_client, registration, signup, user
):
    signup.created_by = user
    signup.save(update_fields=["created_by"])

    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    new_signup_name = "Edited name"

    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name != new_signup_name
    assert db_signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": "2015-01-01",
    }

    assert_update_signup(user_api_client, signup.id, signup_data)
    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name == new_signup_name
    assert db_signup.last_modified_by_id == user.id


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__non_created_regular_user_cannot_update_signup(
    user_api_client, registration, signup, user
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    new_signup_name = "Edited name"

    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name != new_signup_name
    assert db_signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": "2015-01-01",
    }

    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.first_name != new_signup_name
    assert db_signup.last_modified_by_id is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__cannot_update_attendee_status_of_signup(
    registration, signup, user_api_client, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup.attendee_status = SignUp.AttendeeStatus.ATTENDING
    signup.save()

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
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
def test__cannot_update_registration_of_signup(
    registration, registration2, signup, user_api_client, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_data = {
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
        "registration": registration2.id,
    }

    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["registration"]
        == "You may not change the registration of an existing object."
    )


@pytest.mark.django_db
def test__registration_user_access_cannot_update_signup(
    registration, signup, user, user_api_client
):
    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccess.objects.create(registration=registration, email=user.email)

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__regular_user_cannot_update_signup(
    registration, signup, user, user_api_client
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__api_key_with_organization_and_registration_permission_can_update_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.user_editable_registrations = True
    data_source.owner = organization
    data_source.save(update_fields=["user_editable_registrations", "owner"])
    api_client.credentials(apikey=data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    assert_update_signup(api_client, signup.id, signup_data)


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__api_key_with_organization_without_registration_permission_cannot_update_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.save(update_fields=["owner"])
    api_client.credentials(apikey=data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_of_other_organization_cannot_update_signup(
    api_client, data_source, organization2, registration, signup
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_update_signup(
    api_client, organization, other_data_source, registration, signup
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_update_signup(api_client, registration, signup):
    api_client.credentials(apikey="unknown")

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
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
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    assert_update_signup(user_api_client, signup.id, signup_data)
