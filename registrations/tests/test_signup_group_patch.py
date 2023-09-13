import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp
from registrations.tests.factories import SignUpFactory, SignUpGroupFactory

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


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_admin_can_patch_signup_group_extra_info(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup0 = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="signup0 extra info",
    )
    signup1 = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="signup1 extra info",
    )

    signup_group_data = {"extra_info": "signup group extra info"}

    assert signup_group.extra_info is None
    assert signup0.extra_info == "signup0 extra info"
    assert signup1.extra_info == "signup1 extra info"

    response = assert_patch_signup_group(
        user_api_client, signup_group.id, signup_group_data
    )
    assert response.data["extra_info"] == signup_group_data["extra_info"]

    signup_group.refresh_from_db()
    signup0.refresh_from_db()
    signup1.refresh_from_db()
    assert signup_group.extra_info == signup_group_data["extra_info"]
    assert signup0.extra_info == "signup0 extra info"
    assert signup1.extra_info == "signup1 extra info"


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_admin_cannot_patch_signup_group_extra_info(user_api_client, registration):
    signup_group = SignUpGroupFactory(registration=registration)
    signup0 = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="signup0 extra info",
    )
    signup1 = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="signup1 extra info",
    )

    signup_group_data = {"extra_info": "signup group extra info"}

    assert signup_group.extra_info is None
    assert signup0.extra_info == "signup0 extra info"
    assert signup1.extra_info == "signup1 extra info"

    response = patch_signup_group(user_api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup_group.refresh_from_db()
    signup0.refresh_from_db()
    signup1.refresh_from_db()
    assert signup_group.extra_info is None
    assert signup0.extra_info == "signup0 extra info"
    assert signup1.extra_info == "signup1 extra info"


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_regular_user_cannot_patch_signup_group_extra_info(
    user_api_client, registration, user
):
    default_org = user.get_default_organization()
    default_org.regular_users.add(user)
    default_org.admin_users.remove(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup0 = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="signup0 extra info",
    )
    signup1 = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        extra_info="signup1 extra info",
    )

    signup_group_data = {"extra_info": "signup group extra info"}

    assert signup_group.extra_info is None
    assert signup0.extra_info == "signup0 extra info"
    assert signup1.extra_info == "signup1 extra info"

    response = patch_signup_group(user_api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup_group.refresh_from_db()
    signup0.refresh_from_db()
    signup1.refresh_from_db()
    assert signup_group.extra_info is None
    assert signup0.extra_info == "signup0 extra info"
    assert signup1.extra_info == "signup1 extra info"


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_admin_can_patch_signups_data(user_api_client, registration, user):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup0 = SignUpFactory(signup_group=signup_group, registration=registration)
    signup1 = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_group_data = {
        "signups": [
            {"id": signup0.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {"id": signup1.pk, "extra_info": "signup1 extra info"},
        ]
    }

    assert signup0.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup1.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup0.extra_info is None
    assert signup1.extra_info is None

    assert_patch_signup_group(user_api_client, signup_group.id, signup_group_data)

    signup0.refresh_from_db()
    signup1.refresh_from_db()
    assert signup0.presence_status == SignUp.PresenceStatus.PRESENT
    assert signup1.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup0.extra_info is None
    assert signup1.extra_info == "signup1 extra info"


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_admin_cannot_patch_signups_data(user_api_client, registration):
    signup_group = SignUpGroupFactory(registration=registration)
    signup0 = SignUpFactory(signup_group=signup_group, registration=registration)
    signup1 = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_group_data = {
        "signups": [
            {"id": signup0.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {"id": signup1.pk, "extra_info": "signup1 extra info"},
        ]
    }

    assert signup0.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup1.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup0.extra_info is None
    assert signup1.extra_info is None

    response = patch_signup_group(user_api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup0.refresh_from_db()
    signup1.refresh_from_db()
    assert signup0.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup1.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup0.extra_info is None
    assert signup1.extra_info is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_regular_user_cannot_patch_signups_data(user_api_client, registration, user):
    default_org = user.get_default_organization()
    default_org.regular_users.add(user)
    default_org.admin_users.remove(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup0 = SignUpFactory(signup_group=signup_group, registration=registration)
    signup1 = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_group_data = {
        "signups": [
            {"id": signup0.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {"id": signup1.pk, "extra_info": "signup1 extra info"},
        ]
    }

    assert signup0.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup1.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup0.extra_info is None
    assert signup1.extra_info is None

    response = patch_signup_group(user_api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup0.refresh_from_db()
    signup1.refresh_from_db()
    assert signup0.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup1.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup0.extra_info is None
    assert signup1.extra_info is None
