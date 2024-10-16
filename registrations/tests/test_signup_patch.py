from decimal import Decimal
from typing import Optional
from unittest.mock import PropertyMock, patch

import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.enums import VatPercentage
from registrations.models import SignUp, SignUpContactPerson
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPriceGroupFactory,
    SignUpProtectedDataFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.utils import create_user_by_role

description_fields = ("description_fi", "description_sv", "description_en")
new_signup_name = "Edited first name"

# === util methods ===


def patch_signup(
    api_client, signup_pk, signup_data, query_string: Optional[str] = None
):
    signup_url = reverse(
        "signup-detail",
        kwargs={"pk": signup_pk},
    )

    if query_string:
        signup_url = "%s?%s" % (signup_url, query_string)

    response = api_client.patch(signup_url, signup_data, format="json")
    return response


def assert_patch_signup(
    api_client, signup_pk, signup_data, query_string: Optional[str] = None
):
    response = patch_signup(
        api_client, signup_pk, signup_data, query_string=query_string
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == signup_pk

    return response


def assert_patch_signup_price_group_failed(
    api_client,
    signup,
    signup_data,
    signup_price_group,
    new_registration_price_group,
    status_code=status.HTTP_400_BAD_REQUEST,
):
    assert signup.price_group.pk == signup_price_group.pk
    assert (
        signup.price_group.registration_price_group_id
        != new_registration_price_group.pk
    )
    assert signup.price_group.price != new_registration_price_group.price
    assert (
        signup.price_group.price_without_vat
        != new_registration_price_group.price_without_vat
    )
    assert signup.price_group.vat != new_registration_price_group.vat
    assert (
        signup.price_group.vat_percentage != new_registration_price_group.vat_percentage
    )
    for description_field in description_fields:
        assert getattr(signup_price_group, description_field) != getattr(
            new_registration_price_group.price_group, description_field
        )

    response = patch_signup(api_client, signup.id, signup_data)
    assert response.status_code == status_code

    signup.refresh_from_db()
    assert signup.price_group.pk == signup_price_group.pk
    assert (
        signup.price_group.registration_price_group_id
        != new_registration_price_group.pk
    )
    assert signup.price_group.price != new_registration_price_group.price
    assert (
        signup.price_group.price_without_vat
        != new_registration_price_group.price_without_vat
    )
    assert signup.price_group.vat != new_registration_price_group.vat
    assert (
        signup.price_group.vat_percentage != new_registration_price_group.vat_percentage
    )
    for description_field in description_fields:
        assert getattr(signup_price_group, description_field) != getattr(
            new_registration_price_group.price_group, description_field
        )

    return response


# === tests ===


@pytest.mark.parametrize(
    "user_role, expected_status_code, expected_presence_status",
    [
        ("admin", status.HTTP_403_FORBIDDEN, SignUp.PresenceStatus.NOT_PRESENT),
        (
            "financial_admin",
            status.HTTP_403_FORBIDDEN,
            SignUp.PresenceStatus.NOT_PRESENT,
        ),
        (
            "registration_created_admin",
            status.HTTP_200_OK,
            SignUp.PresenceStatus.PRESENT,
        ),
        ("registration_admin", status.HTTP_200_OK, SignUp.PresenceStatus.PRESENT),
        (
            "registration_user_superuser",
            status.HTTP_200_OK,
            SignUp.PresenceStatus.PRESENT,
        ),
        ("registration_user_admin", status.HTTP_200_OK, SignUp.PresenceStatus.PRESENT),
        ("created_user", status.HTTP_403_FORBIDDEN, SignUp.PresenceStatus.NOT_PRESENT),
    ],
)
@pytest.mark.django_db
def test_can_patch_presence_status_of_signup_based_on_role(
    api_client,
    organization,
    user_role,
    expected_status_code,
    expected_presence_status,
):
    user = create_user_by_role(
        user_role,
        organization,
        additional_roles={
            "registration_created_admin": lambda usr: usr.admin_organizations.add(
                organization
            ),
            "registration_user_admin": lambda usr: usr.registration_admin_organizations.add(
                organization
            ),
            "registration_user_superuser": lambda usr: None,
            "created_user": lambda usr: None,
        },
    )
    if user_role == "registration_user_superuser":
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])
    api_client.force_authenticate(user)

    registration = RegistrationFactory(
        event__publisher=organization,
        created_by=user if user_role == "registration_created_admin" else None,
    )
    if user_role in ("registration_user_superuser", "registration_user_admin"):
        RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "created_user" else None,
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    response = patch_signup(api_client, signup.id, signup_data)
    assert response.status_code == expected_status_code
    if response.status_code == status.HTTP_200_OK:
        assert response.data["presence_status"] == expected_presence_status

    signup.refresh_from_db()
    assert signup.presence_status == expected_presence_status


@pytest.mark.django_db
def test_contact_person_can_patch_signup_when_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    signup_data = {
        "first_name": new_signup_name,
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_patch_signup(
            api_client,
            signup.id,
            signup_data,
        )
        assert mocked.called is True

    signup.refresh_from_db()
    assert signup.first_name == new_signup_name
    assert signup.last_modified_by_id == user.id


@pytest.mark.django_db
def test_contact_person_cannot_patch_signup_when_not_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    signup_data = {
        "first_name": new_signup_name,
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = patch_signup(
            api_client,
            signup.id,
            signup_data,
        )
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup.refresh_from_db()
    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None


@pytest.mark.django_db
def test_patch_extra_info_of_signup_with_empty_data(api_client, registration, signup):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpProtectedDataFactory(
        signup=signup, registration=registration, extra_info="Extra info"
    )
    assert signup.extra_info == "Extra info"

    signup_data = {
        "extra_info": "",
    }

    assert_patch_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    del signup.extra_info
    assert signup.extra_info == ""


@pytest.mark.django_db
def test_patch_user_consent(api_client, registration, signup):
    user = create_user_by_role("registration_admin", registration.publisher)
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
def test_patch_phone_number(api_client, registration, signup):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    assert signup.phone_number is None

    signup_data = {
        "phone_number": "0401111111",
    }
    assert_patch_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.phone_number == signup_data["phone_number"]


@pytest.mark.django_db
def test_strongly_identified_registration_user_access_can_patch_presence_status(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(
        registration=registration,
        street_address="Street address",
    )
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_patch_signup(api_client, signup.id, signup_data)
        assert mocked.called is True

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.PRESENT


@pytest.mark.django_db
def test_can_patch_presence_status_with_registration_price_groups(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    RegistrationPriceGroupFactory(
        registration=registration, price_group__publisher=registration.publisher
    )

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup = SignUpFactory(registration=registration, created_by=user)
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }
    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_patch_signup(api_client, signup.id, signup_data)
        assert mocked.called is True

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.PRESENT


@pytest.mark.django_db
def test_non_strongly_identified_registration_user_access_cannot_patch_signup_presence_status(
    api_client, registration
):
    user = UserFactory()
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
        return_value=[],
    ) as mocked:
        response = patch_signup(api_client, signup.id, signup_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        assert mocked.called is True

    signup.refresh_from_db()
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@pytest.mark.django_db
def test_registration_substitute_user_can_patch_signup(api_client, registration):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    signup = SignUpFactory(registration=registration)
    assert signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert signup.extra_info is None

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
        "extra_info": "new extra info",
    }

    assert_patch_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    del signup.extra_info
    assert signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert signup.extra_info == signup_data["extra_info"]


@pytest.mark.django_db
def test_can_patch_signup_contact_person(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
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


@pytest.mark.django_db
def test_contact_person_deleted_when_signup_linked_to_group_in_patch(
    api_client, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
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
    user = create_user_by_role("registration_admin", signup.registration.publisher)
    api_client.force_authenticate(user)

    signup_data = {
        "presence_status": SignUp.PresenceStatus.PRESENT,
    }

    assert_patch_signup(api_client, signup.pk, signup_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [signup.pk]


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_patch_signup_price_group(api_client, registration, user_role):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )

    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group__publisher=registration.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )
    signup_price_group = SignUpPriceGroupFactory(signup=signup)

    assert signup.price_group.pk == signup_price_group.pk
    assert (
        signup.price_group.registration_price_group_id
        != new_registration_price_group.pk
    )
    assert signup.price_group.price != new_registration_price_group.price
    assert (
        signup.price_group.vat_percentage != new_registration_price_group.vat_percentage
    )
    assert (
        signup.price_group.price_without_vat
        != new_registration_price_group.price_without_vat
    )
    assert signup.price_group.vat != new_registration_price_group.vat
    for description_field in description_fields:
        assert getattr(signup.price_group, description_field) != getattr(
            new_registration_price_group.price_group, description_field
        )

    signup_data = {
        "price_group": {
            "id": signup_price_group.pk,
            "registration_price_group": new_registration_price_group.pk,
        },
    }
    assert_patch_signup(api_client, signup.id, signup_data)

    signup.refresh_from_db()
    assert signup.price_group.pk == signup_price_group.pk
    assert (
        signup.price_group.registration_price_group_id
        == new_registration_price_group.pk
    )
    assert signup.price_group.price == new_registration_price_group.price
    assert (
        signup.price_group.vat_percentage == new_registration_price_group.vat_percentage
    )
    assert (
        signup.price_group.price_without_vat
        == new_registration_price_group.price_without_vat
    )
    assert signup.price_group.vat == new_registration_price_group.vat
    for description_field in description_fields:
        assert getattr(signup.price_group, description_field) == getattr(
            new_registration_price_group.price_group, description_field
        )


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_cannot_patch_signup_price_group_with_wrong_registration_price_group(
    api_client, registration, registration2, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )

    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=registration2,
        price_group__publisher=registration2.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )
    signup_price_group = SignUpPriceGroupFactory(signup=signup)

    signup_data = {
        "price_group": {
            "id": signup_price_group.pk,
            "registration_price_group": new_registration_price_group.pk,
        },
    }
    response = assert_patch_signup_price_group_failed(
        api_client,
        signup,
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
def test_cannot_patch_signup_with_another_signups_price_group(
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

    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group__publisher=registration.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )
    signup_price_group = SignUpPriceGroupFactory(signup=signup)
    signup_price_group2 = SignUpPriceGroupFactory(signup=signup2)

    signup_data = {
        "price_group": {
            "id": signup_price_group2.pk,
            "registration_price_group": new_registration_price_group.pk,
        },
    }

    assert_patch_signup(api_client, signup.id, signup_data)

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


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.parametrize("price_group_data", [None, {}])
@pytest.mark.django_db
def test_patch_signup_price_group_is_required(
    api_client, registration, user_role, price_group_data
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    RegistrationPriceGroupFactory(
        registration=registration, price_group__publisher=registration.publisher
    )

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )

    signup_data = {
        "price_group": price_group_data,
    }
    response = patch_signup(api_client, signup.id, signup_data)
    assert response.data["price_group"][0] == (
        "Price group selection is mandatory for this registration."
    )
