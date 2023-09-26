import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp, SignUpGroup
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
)

new_signup_group_extra_info = "Edited extra info"

# === util methods ===


def update_signup_group(
    api_client, signup_group_pk, signup_group_data, query_string=None
):
    signup_group_url = reverse(
        "signupgroup-detail",
        kwargs={"pk": signup_group_pk},
    )

    if query_string:
        signup_group_url = "%s?%s" % (signup_group_url, query_string)

    response = api_client.put(signup_group_url, signup_group_data, format="json")
    return response


def assert_update_signup_group(
    api_client, signup_group_pk, signup_group_data, query_string=None
):
    response = update_signup_group(
        api_client, signup_group_pk, signup_group_data, query_string
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == signup_group_pk

    return response


# === tests ===


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_admin_can_update_signup_group(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup0 = SignUpFactory(signup_group=signup_group, registration=registration)
    signup1 = SignUpFactory(signup_group=signup_group, registration=registration)

    new_signup_name = "Edited name"

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    assert signup0.first_name != new_signup_name
    assert signup0.last_modified_by_id is None

    assert signup1.first_name != new_signup_name
    assert signup1.last_modified_by_id is None

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
        "signups": [
            {"id": signup0.id, "first_name": new_signup_name},
            {"extra_info": "This sign-up does not exist"},
        ],
    }

    assert_update_signup_group(user_api_client, signup_group.id, signup_group_data)

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    signup_group.refresh_from_db()
    del signup_group.extra_info
    assert signup_group.extra_info == new_signup_group_extra_info
    assert signup_group.last_modified_by_id == user.id

    signup0.refresh_from_db()
    assert signup0.first_name == new_signup_name
    assert signup0.last_modified_by_id == user.id

    signup1.refresh_from_db()
    assert signup1.first_name != new_signup_name
    assert signup1.last_modified_by_id is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_created_admin_can_update_signup_group(registration, user, user_api_client):
    signup_group = SignUpGroupFactory(registration=registration, created_by=user)

    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }

    assert_update_signup_group(user_api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    del signup_group.extra_info
    assert signup_group.extra_info == new_signup_group_extra_info
    assert signup_group.last_modified_by_id == user.id


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_can_update_signup_group_with_empty_extra_info(
    registration, user, user_api_client
):
    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    SignUpGroupProtectedDataFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="Extra info",
    )

    assert signup_group.extra_info == "Extra info"
    assert signup_group.last_modified_by_id is None

    signup_group_data = {
        "registration": registration.id,
        "extra_info": "",
    }

    assert_update_signup_group(user_api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    del signup_group.extra_info
    assert signup_group.protected_data.extra_info == ""
    assert signup_group.last_modified_by_id == user.id


@pytest.mark.parametrize(
    "user_role,created_by",
    [
        ("admin", False),
        ("registration_user", False),
        ("regular", False),
        ("regular_without_organization", False),
        ("admin", True),
        ("registration_user", True),
        ("regular", True),
        ("regular_without_organization", True),
    ],
)
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_can_update_signup_group_based_on_role_and_created_by(
    api_client, registration, user_role, created_by
):
    user = UserFactory()

    user_role_mapping = {
        "admin": lambda usr: usr.admin_organizations.add(registration.publisher),
        "registration_user": lambda usr: RegistrationUserAccessFactory(
            registration=registration, email=usr.email
        ),
        "regular": lambda usr: usr.organization_memberships.add(registration.publisher),
        "regular_without_organization": lambda usr: None,
    }
    user_role_mapping[user_role](user)

    signup_group_kwargs = {
        "registration": registration,
    }
    if created_by:
        signup_group_kwargs["created_by"] = user
    signup_group = SignUpGroupFactory(**signup_group_kwargs)
    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    new_extra_info = "Edited extra info"

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_extra_info,
    }

    api_client.force_authenticate(user)

    response = update_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    del signup_group.extra_info  # refresh cached_property

    if created_by:
        assert response.status_code == status.HTTP_200_OK
        assert signup_group.extra_info == new_extra_info
        assert signup_group.last_modified_by_id == user.id
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert signup_group.extra_info is None
        assert signup_group.last_modified_by_id is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_cannot_update_attendee_status_of_signup_in_group(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )

    signup_group_data = {
        "registration": registration.id,
        "signups": [
            {"id": signup.id, "attendee_status": SignUp.AttendeeStatus.WAITING_LIST}
        ],
    }

    response = update_signup_group(user_api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["attendee_status"]
        == "You may not change the attendee_status of an existing object."
    )


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_cannot_update_registration_of_signup_group(
    user_api_client, registration, registration2, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)

    signup_group_data = {
        "registration": registration2.id,
    }

    response = update_signup_group(user_api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["registration"][0]
        == "You may not change the registration of an existing object."
    )


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_api_key_with_organization_and_user_editable_registrations_can_update_signup_group(
    api_client, data_source, organization, registration
):
    signup_group = SignUpGroupFactory(registration=registration)

    data_source.owner = organization
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }
    assert_update_signup_group(api_client, signup_group.id, signup_group_data)


@pytest.mark.django_db
def test_api_key_of_other_organization_with_user_editable_registrations_cannot_update_signup_group(
    api_client, data_source, organization2, registration
):
    signup_group = SignUpGroupFactory(registration=registration)

    data_source.owner = organization2
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }
    response = update_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_with_user_editable_registrations_cannot_update_signup_group(
    api_client, organization, other_data_source, registration
):
    signup_group = SignUpGroupFactory(registration=registration)

    other_data_source.owner = organization
    other_data_source.user_editable_registrations = True
    other_data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=other_data_source.api_key)

    signup_group_data = {
        "registration": registration.id,
        "name": new_signup_group_extra_info,
    }
    response = update_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_unknown_api_key_cannot_update_signup_group(api_client, registration):
    signup_group = SignUpGroupFactory(registration=registration)

    api_client.credentials(apikey="unknown")

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }

    response = update_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_user_editable_resources_can_update_signup_group(
    user_api_client, data_source, organization, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)

    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save(update_fields=["owner", "user_editable_resources"])

    signup_group_data = {
        "registration": registration.id,
        "extra_info": "Edited extra_info",
    }

    assert_update_signup_group(user_api_client, signup_group.id, signup_group_data)


@pytest.mark.django_db
def test_non_user_editable_resources_cannot_update_signup_group(
    user_api_client, data_source, organization, registration
):
    signup_group = SignUpGroupFactory(registration=registration)

    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save(update_fields=["owner", "user_editable_resources"])

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }

    response = update_signup_group(user_api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
