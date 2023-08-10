import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp

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
def test__update_signup(user_api_client, registration, signup, user):
    new_signup_name = "Edited name"

    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.name != new_signup_name
    assert db_signup.last_modified_by_id is None

    signup_data = {
        "registration": registration.id,
        "name": new_signup_name,
        "date_of_birth": "2015-01-01",
    }

    assert_update_signup(user_api_client, signup.id, signup_data)
    db_signup = SignUp.objects.get(pk=signup.id)
    assert db_signup.name == new_signup_name
    assert db_signup.last_modified_by_id == user.id


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__cannot_update_attendee_status_of_signup(
    user_api_client, registration, signup
):
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
    user_api_client, registration, registration2, signup
):
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
def test__non_admin_cannot_update_signup(api_client, registration, signup, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    response = update_signup(api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__api_key_with_organization_can_update_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    assert_update_signup(api_client, signup.id, signup_data)


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


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test__user_editable_resources_can_update_signup(
    user_api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    assert_update_signup(user_api_client, signup.id, signup_data)


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_delete_signup(
    user_api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()

    signup_data = {
        "registration": registration.id,
        "name": "Edited name",
        "date_of_birth": "2015-01-01",
    }
    response = update_signup(user_api_client, signup.id, signup_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
