from decimal import Decimal
from unittest.mock import PropertyMock, patch

import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.enums import VatPercentage
from registrations.models import (
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpPriceGroup,
)
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.test_signup_patch import description_fields
from registrations.tests.utils import create_user_by_role

new_signup_first_name = "Edited name"
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


def assert_signup_group_price_group_update_failed(
    api_client,
    signup_group_pk,
    signup_group_data,
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

    response = update_signup_group(api_client, signup_group_pk, signup_group_data)
    assert response.status_code == status_code

    assert SignUpPriceGroup.objects.count() == price_groups_count

    signup_price_group.refresh_from_db()
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


@pytest.mark.django_db
def test_registration_admin_can_update_signup_group(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup1 = SignUpFactory(signup_group=signup_group, registration=registration)
    signup2 = SignUpFactory(signup_group=signup_group, registration=registration)

    new_signup_phone_number = "040111111"

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    assert signup1.first_name != new_signup_first_name
    assert signup1.last_modified_by_id is None
    assert signup1.user_consent is False

    assert signup2.first_name != new_signup_first_name
    assert signup2.last_modified_by_id is None

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
        "signups": [
            {
                "id": signup1.id,
                "first_name": new_signup_first_name,
                "user_consent": True,
                "phone_number": new_signup_phone_number,
            },
            {"extra_info": "This sign-up does not exist"},
        ],
    }

    assert_update_signup_group(api_client, signup_group.id, signup_group_data)

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    signup_group.refresh_from_db()
    del signup_group.extra_info
    assert signup_group.extra_info == new_signup_group_extra_info
    assert signup_group.last_modified_by_id == user.id

    signup1.refresh_from_db()
    assert signup1.first_name == new_signup_first_name
    assert signup1.phone_number == new_signup_phone_number
    assert signup1.last_modified_by_id == user.id
    assert signup1.user_consent is True

    signup2.refresh_from_db()
    assert signup2.first_name != new_signup_first_name
    assert signup2.last_modified_by_id is None


@pytest.mark.django_db
def test_contact_person_can_update_signup_group_when_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group, user=user)

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
        "signups": [
            {
                "id": signup.id,
                "first_name": new_signup_first_name,
            },
        ],
    }

    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    assert signup.first_name != new_signup_first_name
    assert signup.last_modified_by_id is None

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_update_signup_group(
            api_client,
            signup_group.id,
            signup_group_data,
        )
        assert mocked.called is True

    signup_group.refresh_from_db()
    del signup_group.extra_info  # Refresh cached property; test will fail otherwise
    assert signup_group.extra_info == new_signup_group_extra_info
    assert signup_group.last_modified_by_id == user.id

    signup.refresh_from_db()
    assert signup.first_name == new_signup_first_name
    assert signup.last_modified_by_id == user.id


@pytest.mark.django_db
def test_contact_person_cannot_update_signup_group_when_not_strongly_identified(
    api_client,
    registration,
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group, user=user)

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
        "signups": [
            {
                "id": signup.id,
                "first_name": new_signup_first_name,
            },
        ],
    }

    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    assert signup.first_name != new_signup_first_name
    assert signup.last_modified_by_id is None

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = update_signup_group(
            api_client,
            signup_group.id,
            signup_group_data,
        )
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup_group.refresh_from_db()
    del signup_group.extra_info  # Refresh cached property
    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    signup.refresh_from_db()
    assert signup.first_name != new_signup_first_name
    assert signup.last_modified_by_id is None


@pytest.mark.django_db
def test_registration_created_admin_can_update_signup_group(organization, api_client):
    user = create_user_by_role("admin", organization)
    api_client.force_authenticate(user)

    registration = RegistrationFactory(
        event__publisher=organization,
        created_by=user,
    )
    signup_group = SignUpGroupFactory(registration=registration)

    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }

    assert_update_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    del signup_group.extra_info
    assert signup_group.extra_info == new_signup_group_extra_info
    assert signup_group.last_modified_by_id == user.id


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
    "user_role",
    [
        "admin",
        "financial_admin",
        "registration_user",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.parametrize("created_by", [True, False])
@pytest.mark.django_db
def test_can_update_signup_group_based_on_role_and_created_by(
    api_client, registration, user_role, created_by
):
    user = create_user_by_role(
        user_role,
        registration.publisher,
        additional_roles={
            "registration_user": lambda usr: RegistrationUserAccessFactory(
                registration=registration, email=usr.email
            ),
            "regular_user_without_organization": lambda usr: None,
        },
    )
    api_client.force_authenticate(user)

    signup_group_kwargs = {
        "registration": registration,
    }
    if created_by:
        signup_group_kwargs["created_by"] = user
    signup_group = SignUpGroupFactory(**signup_group_kwargs)
    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }

    response = update_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    del signup_group.extra_info  # refresh cached_property

    if created_by:
        assert response.status_code == status.HTTP_200_OK
        assert signup_group.extra_info == new_signup_group_extra_info
        assert signup_group.last_modified_by_id == user.id
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert signup_group.extra_info is None
        assert signup_group.last_modified_by_id is None


@pytest.mark.django_db
def test_strongly_identified_registration_user_access_cannot_update_signup_group(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }
    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = update_signup_group(api_client, signup_group.id, signup_group_data)
        assert mocked.called is True

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_registration_substitute_user_can_update_signup_group(api_client, registration):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    RegistrationUserAccessFactory(
        registration=registration, email=user.email, is_substitute_user=True
    )

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }
    assert_update_signup_group(api_client, signup_group.id, signup_group_data)


@pytest.mark.django_db
def test_cannot_update_attendee_status_of_signup_in_group(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

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

    response = update_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["attendee_status"]
        == "You may not change the attendee_status of an existing object."
    )


@pytest.mark.django_db
def test_cannot_update_registration_of_signup_group(
    api_client, registration, registration2
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    signup_group_data = {
        "registration": registration2.id,
    }

    response = update_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["registration"][0]
        == "You may not change the registration of an existing object."
    )


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


@pytest.mark.parametrize("api_key", ["", "unknown"])
@pytest.mark.django_db
def test_invalid_api_key_cannot_update_signup_group(api_client, registration, api_key):
    signup_group = SignUpGroupFactory(registration=registration)

    api_client.credentials(apikey=api_key)

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }

    response = update_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_non_user_editable_resources_cannot_update_signup_group(
    user_api_client, user2, data_source, organization, registration
):
    registration.created_by = user2
    registration.save(update_fields=["created_by"])

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


@pytest.mark.django_db
def test_signup_group_text_fields_are_sanitized(registration, api_client):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)
    contact_person = SignUpContactPersonFactory(signup_group=signup_group)

    signup_group_data = {
        "extra_info": "Extra info for group <p>Html</p>",
        "registration": registration.id,
        "signups": [
            {
                "id": signup.id,
                "first_name": "Michael <p>Html</p>",
                "last_name": "Jackson <p>Html</p>",
                "phone_number": "<p>0401111111</p>",
                "extra_info": "Extra info <p>Html</p>",
                "street_address": "Street address <p>Html</p>",
                "zipcode": "<p>zip</p>",
            }
        ],
        "contact_person": {
            "first_name": "Michael <p>Html</p>",
            "last_name": "Jackson <p>Html</p>",
            "phone_number": "<p>0441111111</p>",
        },
    }

    assert_update_signup_group(api_client, signup_group.id, signup_group_data)
    signup_group.refresh_from_db()
    assert signup_group.extra_info == "Extra info for group Html"

    signup.refresh_from_db()
    assert signup.first_name == "Michael Html"
    assert signup.last_name == "Jackson Html"
    assert signup.phone_number == "0401111111"
    assert signup.extra_info == "Extra info Html"
    assert signup.street_address == "Street address Html"
    assert signup.zipcode == "zip"

    contact_person.refresh_from_db()
    assert contact_person.first_name == "Michael Html"
    assert contact_person.last_name == "Jackson Html"
    assert contact_person.phone_number == "0441111111"


@pytest.mark.django_db
def test_signup_group_update_contact_person(registration, api_client):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)
    contact_person = SignUpContactPersonFactory(
        signup_group=signup_group, email="old@test.com"
    )

    assert contact_person.phone_number is None
    assert contact_person.email == "old@test.com"

    signup_group_data = {
        "extra_info": "Extra info for group",
        "registration": registration.id,
        "signups": [
            {
                "id": signup.id,
                "first_name": "Michael",
                "last_name": "Jackson",
            }
        ],
        "contact_person": {
            "phone_number": "0441111111",
            "email": "new@test.com",
        },
    }

    assert_update_signup_group(api_client, signup_group.id, signup_group_data)

    contact_person.refresh_from_db()
    assert contact_person.phone_number == "0441111111"
    assert contact_person.email == "new@test.com"


@pytest.mark.django_db
def test_signup_group_missing_contact_person_created_on_update(
    registration, api_client
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)

    assert getattr(signup_group, "contact_person", None) is None

    signup_group_data = {
        "extra_info": "Extra info for group",
        "registration": registration.id,
        "signups": [
            {
                "id": signup.id,
                "first_name": "Michael",
                "last_name": "Jackson",
            }
        ],
        "contact_person": {
            "phone_number": "0441111111",
        },
    }

    assert_update_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    assert signup_group.contact_person.phone_number == "0441111111"


@pytest.mark.django_db
def test_contact_person_can_be_null_on_signup_group_update(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    contact_person = SignUpContactPersonFactory(signup_group=signup_group)

    assert SignUpContactPerson.objects.count() == 1
    assert signup_group.contact_person.pk == contact_person.pk

    signup_group_data = {
        "extra_info": "Updated extra info",
        "registration": registration.id,
        "contact_person": None,
    }

    assert_update_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()

    assert SignUpContactPerson.objects.count() == 1
    assert signup_group.contact_person.pk == contact_person.pk


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_put(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
    }

    assert_update_signup_group(api_client, signup_group.pk, signup_group_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        signup_group.pk
    ]


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_can_update_signup_groups_price_group(api_client, registration, user_role):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_price_group = SignUpPriceGroupFactory(signup=signup, price=Decimal("10"))
    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=signup.registration,
        price_group__publisher=signup.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )

    signup_group_data = {
        "registration": registration.id,
        "signups": [
            {
                "id": signup.id,
                "price_group": {
                    "id": signup_price_group.pk,
                    "registration_price_group": new_registration_price_group.pk,
                },
            }
        ],
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

    assert_update_signup_group(api_client, signup_group.id, signup_group_data)

    assert SignUpPriceGroup.objects.count() == 1

    signup_price_group.refresh_from_db()
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


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_cannot_update_signup_group_without_selecting_price_group_if_registration_has_price_groups(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup = SignUpFactory(signup_group=signup_group, registration=registration)

    RegistrationPriceGroupFactory(
        registration=registration,
        price_group__publisher=registration.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )

    signup_group_data = {
        "registration": registration.id,
        "signups": [
            {
                "id": signup.id,
                "extra_info": new_signup_group_extra_info,
            }
        ],
    }

    assert SignUpPriceGroup.objects.count() == 0

    response = update_signup_group(api_client, signup_group.pk, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0]["price_group"][0] == (
        "Price group selection is mandatory for this registration."
    )

    assert SignUpPriceGroup.objects.count() == 0


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_cannot_update_signup_price_group_with_wrong_signup_groups_registration(
    api_client, registration, registration2, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_price_group = SignUpPriceGroupFactory(signup=signup, price=Decimal("10"))
    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=registration2,
        price_group__publisher=registration2.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )

    signup_group_data = {
        "registration": registration.id,
        "signups": [
            {
                "id": signup.id,
                "price_group": {
                    "id": signup_price_group.pk,
                    "registration_price_group": new_registration_price_group.pk,
                },
            }
        ],
    }

    response = assert_signup_group_price_group_update_failed(
        api_client,
        signup_group.pk,
        signup_group_data,
        signup_price_group,
        new_registration_price_group,
    )
    assert response.data["signups"][0]["price_group"][0] == (
        "Price group is not one of the allowed price groups for this registration."
    )


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_cannot_update_signup_group_with_another_signups_price_group(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup = SignUpFactory(signup_group=signup_group, registration=registration)
    signup2 = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_price_group = SignUpPriceGroupFactory(
        signup=signup,
        description="Old Description",
        price=Decimal("10"),
    )
    signup_price_group2 = SignUpPriceGroupFactory(
        signup=signup2,
        description="Old Description #2",
        price=Decimal("20"),
    )
    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group__publisher=registration.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )

    signup_group_data = {
        "registration": registration.id,
        "signups": [
            {
                "id": signup.id,
                "price_group": {
                    "id": signup_price_group2.pk,
                    "registration_price_group": new_registration_price_group.pk,
                },
            },
        ],
    }

    assert_update_signup_group(api_client, signup_group.pk, signup_group_data)

    signup_price_group.refresh_from_db()
    assert signup_price_group.signup_id == signup.pk
    assert (
        signup_price_group.registration_price_group_id
        == new_registration_price_group.pk
    )

    signup_price_group2.refresh_from_db()
    assert signup_price_group2.signup_id == signup2.pk
    assert (
        signup_price_group2.registration_price_group_id
        != new_registration_price_group.pk
    )
