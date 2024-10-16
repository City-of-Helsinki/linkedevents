from decimal import Decimal
from typing import Optional
from unittest.mock import PropertyMock, patch

import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.enums import VatPercentage
from registrations.models import SignUp
from registrations.notifications import NotificationType
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.test_signup_patch import description_fields
from registrations.tests.utils import create_user_by_role

# === util methods ===


def patch_signup_group(
    api_client, signup_group_pk, signup_group_data, query_string: Optional[str] = None
):
    signup_group_url = reverse(
        "signupgroup-detail",
        kwargs={"pk": signup_group_pk},
    )

    if query_string:
        signup_group_url = "%s?%s" % (signup_group_url, query_string)

    response = api_client.patch(signup_group_url, signup_group_data, format="json")
    return response


def assert_patch_signup_group(
    api_client, signup_group_pk, signup_group_data, query_string: Optional[str] = None
):
    response = patch_signup_group(
        api_client, signup_group_pk, signup_group_data, query_string=query_string
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == signup_group_pk

    return response


def assert_patch_signup_group_price_group_failed(
    api_client,
    signup_group_pk,
    signup_group_data,
    signup_price_group,
    new_registration_price_group,
    status_code=status.HTTP_400_BAD_REQUEST,
):
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

    response = patch_signup_group(api_client, signup_group_pk, signup_group_data)
    assert response.status_code == status_code

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


@pytest.mark.parametrize(
    "user_role,allowed_to_patch",
    [
        ("admin", False),
        ("registration_created_admin", True),
        ("registration_admin", True),
        ("financial_admin", False),
        ("regular_user", False),
        ("superuser", True),
    ],
)
@pytest.mark.django_db
def test_patch_signup_group_extra_info_based_on_user_role(
    api_client, event, user_role, allowed_to_patch
):
    user = create_user_by_role(
        user_role,
        event.publisher,
        additional_roles={
            "registration_created_admin": lambda usr: usr.admin_organizations.add(
                event.publisher
            ),
        },
    )
    api_client.force_authenticate(user)

    other_user = UserFactory()

    registration = RegistrationFactory(
        event=event,
        created_by=user if user_role == "registration_created_admin" else None,
    )

    signup_group = SignUpGroupFactory(registration=registration, created_by=other_user)
    assert signup_group.extra_info is None

    signup_group_data = {"extra_info": "signup group extra info"}
    response = patch_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    del signup_group.extra_info  # refresh cached_property

    if allowed_to_patch:
        assert response.status_code == status.HTTP_200_OK
        assert response.data["extra_info"] == signup_group_data["extra_info"]
        assert signup_group.extra_info == signup_group_data["extra_info"]
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert signup_group.extra_info is None


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "registration_created_admin"]
)
@pytest.mark.django_db
def test_registration_user_access_who_is_superuser_or_registration_admin_can_patch_signups_data(
    api_client, registration, user_role
):
    user = create_user_by_role(
        user_role,
        registration.publisher,
        additional_roles={
            "registration_created_admin": lambda usr: usr.admin_organizations.add(
                registration.publisher
            )
        },
    )
    api_client.force_authenticate(user)

    if user_role == "registration_created_admin":
        registration.created_by = user
        registration.save(update_fields=["created_by"])

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {
                "id": second_signup.pk,
                "extra_info": "signup2 extra info",
                "user_consent": True,
            },
        ]
    }

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None
    assert second_signup.user_consent is False

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    del first_signup.extra_info
    del second_signup.extra_info

    assert first_signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info == "signup2 extra info"
    assert second_signup.user_consent is True


@pytest.mark.django_db
def test_registration_user_access_who_created_signup_group_can_patch_signups_data(
    api_client, registration
):
    user = UserFactory()
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    first_signup = SignUpFactory(
        signup_group=signup_group, registration=registration, created_by=user
    )
    second_signup = SignUpFactory(
        signup_group=signup_group, registration=registration, created_by=user
    )

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {
                "id": second_signup.pk,
                "extra_info": "signup2 extra info",
                "phone_number": "0401111111",
                "user_consent": True,
            },
        ]
    }

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None
    assert second_signup.user_consent is False

    api_client.force_authenticate(user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_patch_signup_group(api_client, signup_group.id, signup_group_data)
        assert mocked.called is True

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    del first_signup.extra_info  # refresh cached_property
    del second_signup.extra_info  # refresh cached_property

    assert first_signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.phone_number == "0401111111"
    assert first_signup.extra_info is None
    assert second_signup.extra_info == "signup2 extra info"
    assert second_signup.user_consent is True


@pytest.mark.django_db
def test_contact_person_can_patch_signup_group_when_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group, user=user)

    new_signup_group_extra_info = "Edited extra info"
    new_signup_name = "Edited first name"

    signup_group_data = {
        "extra_info": new_signup_group_extra_info,
        "signups": [
            {
                "id": signup.id,
                "first_name": new_signup_name,
            },
        ],
    }

    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_patch_signup_group(api_client, signup_group.id, signup_group_data)
        assert mocked.called is True

    signup_group.refresh_from_db()
    del signup_group.extra_info
    assert signup_group.extra_info == new_signup_group_extra_info
    assert signup_group.last_modified_by_id == user.id

    signup.refresh_from_db()
    assert signup.first_name == new_signup_name
    assert signup.last_modified_by_id == user.id


@pytest.mark.django_db
def test_contact_person_cannot_patch_signup_group_when_not_strongly_identified(
    api_client,
    registration,
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group, user=user)

    new_signup_group_extra_info = "Edited extra info"
    new_signup_name = "Edited name"

    signup_group_data = {
        "registration": registration.id,
        "extra_info": new_signup_group_extra_info,
        "signups": [
            {
                "id": signup.id,
                "first_name": new_signup_name,
            },
        ],
    }

    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = patch_signup_group(
            api_client,
            signup_group.id,
            signup_group_data,
        )
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN

    signup_group.refresh_from_db()
    del signup_group.extra_info
    assert signup_group.extra_info is None
    assert signup_group.last_modified_by_id is None

    signup.refresh_from_db()
    assert signup.first_name != new_signup_name
    assert signup.last_modified_by_id is None


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "financial_admin",
        "regular_user",
    ],
)
@pytest.mark.django_db
def test_admin_or_financial_admin_or_regular_user_cannot_patch_signups_data(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
            {"id": second_signup.pk, "extra_info": "signup2 extra info"},
        ]
    }

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None

    response = patch_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    del first_signup.extra_info
    del second_signup.extra_info

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert first_signup.extra_info is None
    assert second_signup.extra_info is None


@pytest.mark.django_db
def test_registration_user_access_can_patch_signups_presence_status_if_strongly_identified(
    api_client, registration
):
    user = create_user_by_role("regular_user", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
        ]
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_patch_signup_group(api_client, signup_group.id, signup_group_data)
        assert mocked.called is True

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    assert first_signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@pytest.mark.django_db
def test_registration_user_access_cannot_patch_signups_presence_status_if_not_strongly_identified(
    api_client, registration
):
    user = create_user_by_role("regular_user", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
        ]
    }

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = patch_signup_group(api_client, signup_group.id, signup_group_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert mocked.called is True

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@pytest.mark.django_db
def test_registration_substitute_user_can_patch_signup_presence_status_if_not_strongly_identified(
    api_client, registration
):
    user = create_user_by_role("regular_user", registration.publisher)
    user.email = hel_email
    user.save(update_fields=["email"])

    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
        ]
    }

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    assert first_signup.presence_status == SignUp.PresenceStatus.PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@pytest.mark.django_db
def test_created_user_cannot_patch_presence_status_of_signups(api_client, registration):
    user = create_user_by_role("regular_user", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    first_signup = SignUpFactory(signup_group=signup_group, registration=registration)
    second_signup = SignUpFactory(signup_group=signup_group, registration=registration)

    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT

    signup_group_data = {
        "signups": [
            {"id": first_signup.pk, "presence_status": SignUp.PresenceStatus.PRESENT},
        ]
    }

    response = patch_signup_group(api_client, signup_group.id, signup_group_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    first_signup.refresh_from_db()
    second_signup.refresh_from_db()
    assert first_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT
    assert second_signup.presence_status == SignUp.PresenceStatus.NOT_PRESENT


@pytest.mark.django_db
def test_can_patch_signup_group_contact_person(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    SignUpFactory(signup_group=signup_group, registration=registration)
    contact_person = SignUpContactPersonFactory(signup_group=signup_group)

    assert contact_person.notifications == NotificationType.NO_NOTIFICATION
    assert contact_person.membership_number is None

    signup_group_data = {
        "contact_person": {
            "notifications": NotificationType.EMAIL,
            "membership_number": "1234",
        },
    }

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    contact_person.refresh_from_db()
    assert contact_person.notifications == NotificationType.EMAIL
    assert contact_person.membership_number == "1234"


@pytest.mark.django_db
def test_missing_contact_person_created_on_patch(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    signup = SignUpFactory(signup_group=signup_group, registration=registration)

    assert getattr(signup_group, "contact_person", None) is None
    assert getattr(signup, "contact_person", None) is None

    signup_group_data = {
        "contact_person": {
            "notifications": NotificationType.EMAIL,
            "membership_number": "1234",
        },
    }

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    signup_group.refresh_from_db()
    signup.refresh_from_db()
    assert signup_group.contact_person.notifications == NotificationType.EMAIL
    assert signup_group.contact_person.membership_number == "1234"
    assert getattr(signup, "contact_person", None) is None


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_patch(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    signup_group_data = {"extra_info": "test test"}

    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        signup_group.pk
    ]


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_can_patch_signup_groups_price_group(api_client, registration, user_role):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup = SignUpFactory(signup_group=signup_group, registration=registration)

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

    signup_group_data = {
        "signups": [
            {
                "id": signup.pk,
                "price_group": {
                    "id": signup_price_group.pk,
                    "registration_price_group": new_registration_price_group.pk,
                },
            }
        ]
    }
    assert_patch_signup_group(api_client, signup_group.id, signup_group_data)

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
def test_cannot_patch_signup_groups_price_group_with_wrong_registration_price_group(
    api_client, registration, registration2, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup = SignUpFactory(signup_group=signup_group, registration=registration)

    new_registration_price_group = RegistrationPriceGroupFactory(
        registration=registration2,
        price_group__publisher=registration2.publisher,
        price=Decimal("1.23"),
        vat_percentage=VatPercentage.VAT_10.value,
        vat=Decimal("0.11"),
        price_without_vat=Decimal("1.12"),
    )
    signup_price_group = SignUpPriceGroupFactory(signup=signup)

    signup_group_data = {
        "signups": [
            {
                "id": signup.pk,
                "price_group": {
                    "id": signup_price_group.pk,
                    "registration_price_group": new_registration_price_group.pk,
                },
            }
        ]
    }

    response = assert_patch_signup_group_price_group_failed(
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
def test_cannot_patch_signup_group_with_another_signups_price_group(
    api_client, registration, signup, signup2, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup = SignUpFactory(signup_group=signup_group, registration=registration)
    signup2 = SignUpFactory(signup_group=signup_group, registration=registration)

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

    signup_group_data = {
        "signups": [
            {
                "id": signup.pk,
                "price_group": {
                    "id": signup_price_group2.pk,
                    "registration_price_group": new_registration_price_group.pk,
                },
            }
        ]
    }

    assert_patch_signup_group(api_client, signup_group.pk, signup_group_data)

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
