from unittest.mock import patch, PropertyMock

import pytest
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp, SignUpContactPerson
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
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
        ("registration_created_admin", True),
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

    if user_role == "registration_created_admin":
        registration.created_by = user
        registration.save(update_fields=["created_by"])

    if user_role in ("registration_user_superuser", "registration_user_admin"):
        RegistrationUserAccessFactory(registration=registration, email=user.email)

    user_role_mapping = {
        "admin": lambda usr: usr.admin_organizations.add(registration.publisher),
        "registration_created_admin": lambda usr: usr.admin_organizations.add(
            registration.publisher
        ),
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
    api_client, registration, identification_method
):
    user = UserFactory()
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(registration=registration)
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

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


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_can_patch_signup_contact_person(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    contact_person = SignUpContactPersonFactory(signup=signup)

    assert SignUpContactPerson.objects.count() == 1
    assert contact_person.membership_number is None

    signup_data = {"contact_person": {"membership_number": "1234"}}

    assert_patch_signup(api_client, signup.id, signup_data)

    contact_person.refresh_from_db()
    assert SignUpContactPerson.objects.count() == 1
    assert contact_person.membership_number == "1234"


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_contact_person_deleted_when_signup_linked_to_group_in_patch(
    api_client, registration
):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    group_contact_person = SignUpContactPersonFactory(signup_group=signup_group)

    signup = SignUpFactory(registration=registration)
    signup_contact_person = SignUpContactPersonFactory(signup=signup)

    assert SignUpContactPerson.objects.count() == 2
    assert signup_group.contact_person.pk == group_contact_person.pk
    assert signup.contact_person.pk == signup_contact_person.pk

    signup_data = {
        "signup_group": signup_group.id,
    }

    assert_patch_signup(api_client, signup.id, signup_data)

    signup_group.refresh_from_db()
    signup.refresh_from_db()

    assert SignUpContactPerson.objects.count() == 1
    assert signup_group.contact_person.pk == group_contact_person.pk
    assert getattr(signup, "contact_person", None) is None


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
