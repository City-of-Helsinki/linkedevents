from decimal import Decimal
from unittest.mock import patch, PropertyMock
from uuid import UUID

import pytest
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.enums import VatPercentage
from registrations.models import (
    RegistrationPriceGroup,
    SignUp,
    SignUpContactPerson,
    SignUpPriceGroup,
)
from registrations.tests.factories import (
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPriceGroupFactory,
    SignUpProtectedDataFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.test_signup_patch import description_fields
from registrations.tests.utils import create_user_by_role

new_signup_name = "Edited name"
new_date_of_birth = "2015-01-01"
new_phone_number = "+35812345678"

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


def assert_signup_price_group_update_failed(
    api_client,
    signup_pk,
    signup_data,
    signup_price_group,
    new_registration_price_group,
    price_groups_count=1,
    status_code=status.HTTP_400_BAD_REQUEST,
):
    assert SignUpPriceGroup.objects.count() == price_groups_count

    assert (
        signup_price_group.registration_price_group_id
        != new_registration_price_group.pk
    )
    assert signup_price_group.price != new_registration_price_group.price
    assert (
        signup_price_group.vat_percentage != new_registration_price_group.vat_percentage
    )
    assert (
        signup_price_group.price_without_vat
        != new_registration_price_group.price_without_vat
    )
    assert signup_price_group.vat != new_registration_price_group.vat
    for description_field in description_fields:
        assert getattr(signup_price_group, description_field) != getattr(
            new_registration_price_group.price_group, description_field
        )

    response = update_signup(api_client, signup_pk, signup_data)
    assert response.status_code == status_code

    assert SignUpPriceGroup.objects.count() == price_groups_count

    signup_price_group.refresh_from_db()
    assert signup_price_group.signup_id == signup_pk
    assert (
        signup_price_group.registration_price_group_id
        != new_registration_price_group.pk
    )
    assert signup_price_group.price != new_registration_price_group.price
    assert (
        signup_price_group.vat_percentage != new_registration_price_group.vat_percentage
    )
    assert (
        signup_price_group.price_without_vat
        != new_registration_price_group.price_without_vat
    )
    assert signup_price_group.vat != new_registration_price_group.vat
    for description_field in description_fields:
        assert getattr(signup_price_group, description_field) != getattr(
            new_registration_price_group.price_group, description_field
        )

    return response


# === tests ===


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_admin_can_update_signup(api_client, signup):
    user = UserFactory()
    user.registration_admin_organizations.add(signup.publisher)
    api_client.force_authenticate(user)

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None
    assert signup.user_consent is False

    signup_data = {
        "registration": signup.registration_id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
        "phone_number": new_phone_number,
        "user_consent": True,
    }

    assert_update_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.first_name == new_signup_name
    assert signup.phone_number == new_phone_number
    assert signup.last_modified_by_id == user.id
    assert signup.user_consent is True


@pytest.mark.django_db
def test_contact_person_can_update_signup_when_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    signup_data = {
        "registration": signup.registration_id,
        "first_name": new_signup_name,
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_update_signup(
            api_client,
            signup.id,
            signup_data,
        )
        assert mocked.called is True

    signup.refresh_from_db()
    assert signup.first_name == new_signup_name
    assert signup.last_modified_by_id == user.id


@pytest.mark.django_db
def test_contact_person_can_update_signup_when_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    signup_data = {
        "registration": signup.registration_id,
        "first_name": new_signup_name,
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = update_signup(
            api_client,
            signup.id,
            signup_data,
        )
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup.refresh_from_db()
    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_registration_created_admin_can_update_signup(
    registration, user, user_api_client
):
    registration.created_by = user
    registration.save(update_fields=["created_by"])

    signup = SignUpFactory(registration=registration)

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None
    assert signup.user_consent is False
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
        "date_of_birth": new_date_of_birth,
        "phone_number": new_phone_number,
        "user_consent": True,
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    assert_update_signup(user_api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.first_name == new_signup_name
    assert signup.phone_number == new_phone_number
    assert signup.last_modified_by_id == user.id
    assert signup.user_consent is True
    assert signup.presence_status == SignUp.PresenceStatus.PRESENT


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
def test_created_financial_admin_can_update_signup(registration, api_client):
    user = UserFactory()
    user.financial_admin_organizations.add(registration.publisher)
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
    assert signup.last_modified_by_id == user.pk


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_non_created_financial_admin_cannot_update_signup(
    registration, user2, api_client
):
    user = UserFactory()
    user.financial_admin_organizations.add(registration.publisher)
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
def test_non_created_admin_cannot_update_signup(registration, user2, user_api_client):
    registration.created_by = user2
    registration.save(update_fields=["created_by"])

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
        "phone_number": new_phone_number,
    }

    assert_update_signup(user_api_client, signup.id, signup_data)

    db_signup.refresh_from_db()
    assert db_signup.first_name == new_signup_name
    assert db_signup.phone_number == new_phone_number
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
        "phone_number": new_phone_number,
    }

    assert_update_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.first_name == new_signup_name
    assert signup.phone_number == new_phone_number
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
        return_value=["suomi_fi"],
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
        return_value=["suomi_fi"],
    ) as mocked:
        assert_update_signup(api_client, signup.id, signup_data)
        assert mocked.called is True


@pytest.mark.django_db
def test_registration_substitute_user_can_update_signup(registration, api_client):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    signup = SignUpFactory(registration=registration, first_name="user")
    assert signup.first_name != new_signup_name

    signup_data = {
        "registration": registration.id,
        "first_name": new_signup_name,
    }

    assert_update_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.first_name == new_signup_name


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
    contact_person = SignUpContactPersonFactory(signup=signup)

    signup_data = {
        "registration": registration.id,
        "first_name": "Michael <p>Html</p>",
        "last_name": "Jackson <p>Html</p>",
        "contact_person": {
            "phone_number": "<p>0441111111</p>",
        },
        "extra_info": "Extra info <p>Html</p>",
        "street_address": "Edited street address <p>Html</p>",
        "zipcode": "<p>zip</p>",
    }

    assert_update_signup(user_api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.last_modified_by_id == user.id
    assert signup.first_name == "Michael Html"
    assert signup.last_name == "Jackson Html"
    assert signup.extra_info == "Extra info Html"
    assert signup.street_address == "Edited street address Html"
    assert signup.zipcode == "zip"

    contact_person.refresh_from_db()
    assert contact_person.phone_number == "0441111111"


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_contact_person_deleted_when_signup_linked_to_group_in_update(
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
        "registration": registration.id,
        "signup_group": signup_group.id,
        "contact_person": {
            "phone_number": "<p>0441111111</p>",
        },
    }

    assert_update_signup(api_client, signup.id, signup_data)

    signup_group.refresh_from_db()
    signup.refresh_from_db()

    assert SignUpContactPerson.objects.count() == 1
    assert signup_group.contact_person.pk == group_contact_person.pk
    assert getattr(signup, "contact_person", None) is None


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_contact_person_can_be_null_on_signup_update(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    contact_person = SignUpContactPersonFactory(signup=signup)

    assert SignUpContactPerson.objects.count() == 1
    assert signup.contact_person.pk == contact_person.pk

    signup_data = {
        "registration": registration.id,
        "extra_info": "Updated extra info",
        "contact_person": None,
    }

    assert_update_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()

    assert SignUpContactPerson.objects.count() == 1
    assert signup.contact_person.pk == contact_person.pk


@pytest.mark.django_db
def test_signup_id_is_audit_logged_on_put(api_client, registration, signup):
    user = UserFactory()
    user.registration_admin_organizations.add(signup.publisher)
    api_client.force_authenticate(user)

    signup_data = {
        "registration": registration.id,
        "extra_info": "test test",
    }

    assert_update_signup(api_client, signup.pk, signup_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [signup.pk]


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_can_update_signup_price_group(api_client, registration, user_role):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )

    signup_price_group = SignUpPriceGroupFactory(signup=signup, price=Decimal("10"))
    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=signup.registration,
        price_group__publisher=signup.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )

    signup_data = {
        "registration": signup.registration_id,
        "price_group": {
            "id": signup_price_group.pk,
            "registration_price_group": new_registration_price_group.pk,
        },
    }

    assert SignUpPriceGroup.objects.count() == 1

    assert (
        signup_price_group.registration_price_group_id
        != new_registration_price_group.pk
    )
    assert signup_price_group.price != new_registration_price_group.price
    assert (
        signup_price_group.vat_percentage != new_registration_price_group.vat_percentage
    )
    assert (
        signup_price_group.price_without_vat
        != new_registration_price_group.price_without_vat
    )
    assert signup_price_group.vat != new_registration_price_group.vat
    for description_field in description_fields:
        assert getattr(signup_price_group, description_field) != getattr(
            new_registration_price_group.price_group, description_field
        )

    assert_update_signup(api_client, signup.id, signup_data)

    assert SignUpPriceGroup.objects.count() == 1

    signup_price_group.refresh_from_db()
    assert signup_price_group.signup_id == signup.pk
    assert (
        signup_price_group.registration_price_group_id
        == new_registration_price_group.pk
    )
    assert signup_price_group.price == new_registration_price_group.price
    assert (
        signup_price_group.vat_percentage == new_registration_price_group.vat_percentage
    )
    assert (
        signup_price_group.price_without_vat
        == new_registration_price_group.price_without_vat
    )
    assert signup_price_group.vat == new_registration_price_group.vat
    for description_field in description_fields:
        assert getattr(signup_price_group, description_field) == getattr(
            new_registration_price_group.price_group, description_field
        )


@pytest.mark.django_db
def test_can_update_price_group_to_signup(api_client, registration, signup):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group__publisher=registration.publisher,
    )

    signup_data = {
        "registration": registration.pk,
        "price_group": {
            "registration_price_group": registration_price_group.pk,
        },
    }

    assert getattr(signup, "price_group", None) is None

    assert_update_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.price_group.registration_price_group_id == registration_price_group.pk


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_cannot_update_signup_without_selecting_price_group_if_registration_has_price_groups(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )

    RegistrationPriceGroupFactory(
        registration=registration,
        price_group__publisher=registration.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )

    signup_data = {
        "registration": signup.registration_id,
    }

    assert SignUpPriceGroup.objects.count() == 0

    response = update_signup(api_client, signup.pk, signup_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["price_group"][0] == (
        "Price group selection is mandatory for this registration."
    )

    assert SignUpPriceGroup.objects.count() == 0


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_cannot_update_signup_price_group_from_wrong_registration(
    api_client, registration, registration2, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )

    signup_price_group = SignUpPriceGroupFactory(
        signup=signup,
        description="Old Description",
        price=Decimal("10"),
    )
    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=registration2,
        price_group__publisher=registration2.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )

    signup_data = {
        "registration": signup.registration_id,
        "price_group": {
            "id": signup_price_group.pk,
            "registration_price_group": new_registration_price_group.pk,
        },
    }

    response = assert_signup_price_group_update_failed(
        api_client,
        signup.pk,
        signup_data,
        signup_price_group,
        new_registration_price_group,
    )
    assert response.data["price_group"][0] == (
        "Price group is not one of the allowed price groups for this registration."
    )


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_cannot_update_signup_with_another_signups_price_group(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup2 = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )

    signup_price_group = SignUpPriceGroupFactory(
        signup=signup,
        description="Old Description",
        price=Decimal("10"),
    )
    signup_price_group2 = SignUpPriceGroupFactory(
        signup=signup2,
        description="Old Description",
        price=Decimal("10"),
    )
    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=signup.registration,
        price_group__publisher=signup.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )

    signup_data = {
        "registration": signup.registration_id,
        "price_group": {
            "id": signup_price_group2.pk,
            "registration_price_group": new_registration_price_group.pk,
        },
    }

    response = assert_signup_price_group_update_failed(
        api_client,
        signup.pk,
        signup_data,
        signup_price_group,
        new_registration_price_group,
        price_groups_count=2,
    )
    assert response.data["price_group"][0] == (
        "Price group is already assigned to another participant."
    )
