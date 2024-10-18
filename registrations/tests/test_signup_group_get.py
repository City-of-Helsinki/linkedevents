from collections import Counter
from decimal import Decimal
from unittest.mock import PropertyMock, patch

import pytest
from django.conf import settings
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPaymentFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.test_signup_get import (
    assert_contact_person_fields_exist,
    assert_payment_fields_exist,
)
from registrations.tests.utils import create_user_by_role

# === util methods ===


def get_detail(api_client, signup_pk, query=None):
    detail_url = reverse(
        "signupgroup-detail",
        kwargs={"pk": signup_pk},
    )

    if query:
        detail_url = "%s?%s" % (detail_url, query)

    return api_client.get(detail_url)


def get_list(api_client, query_string=None):
    url = reverse("signupgroup-list")

    if query_string:
        url = "%s?%s" % (url, query_string)

    return api_client.get(url)


def assert_get_detail(api_client, signup_pk, query=None):
    response = get_detail(api_client, signup_pk, query)
    assert response.status_code == status.HTTP_200_OK
    return response


def assert_signup_group_fields_exist(data):
    fields = (
        "id",
        "registration",
        "signups",
        "contact_person",
        "extra_info",
        "created_time",
        "last_modified_time",
        "created_by",
        "last_modified_by",
        "is_created_by_current_user",
        "anonymization_time",
        "has_contact_person_access",
    )
    if settings.WEB_STORE_INTEGRATION_ENABLED:
        fields += ("payment", "payment_cancellation", "payment_refund")

    assert_fields_exist(data, fields)
    assert_contact_person_fields_exist(data["contact_person"])


def assert_signup_groups_in_response(signups, response, query=""):
    response_signup_ids = {signup["id"] for signup in response.data["data"]}
    expected_signup_ids = {signup.id for signup in signups}
    if query:
        assert response_signup_ids == expected_signup_ids, f"\nquery: {query}"
    else:
        assert response_signup_ids == expected_signup_ids


def get_list_and_assert_signup_groups(api_client, query, signup_groups):
    response = get_list(api_client, query_string=query)
    assert_signup_groups_in_response(signup_groups, response, query)


# === tests ===


@pytest.mark.parametrize("user_role", ["registration_admin", "admin"])
@pytest.mark.django_db
def test_registration_admin_or_registration_created_admin_can_get_signup_group(
    api_client, registration, organization, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    if user_role == "admin":
        registration.created_by = user
        registration.save(update_fields=["created_by"])

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration, signup_group=signup_group)
    SignUpFactory(registration=registration, signup_group=signup_group)
    SignUpContactPersonFactory(signup_group=signup_group)

    response = assert_get_detail(api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is False
    assert response.data["has_contact_person_access"] is False


@pytest.mark.parametrize(
    "user_role",
    [
        "superuser",
        "registration_admin",
        "created_admin",
        "created_regular_user",
        "created_regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_authenticated_user_with_correct_role_can_get_signup_group_with_payment(
    api_client, registration, user_role
):
    user = create_user_by_role(
        user_role,
        registration.publisher,
        additional_roles={
            "created_admin": lambda usr: usr.admin_organizations.add(
                registration.publisher
            ),
            "created_regular_user": lambda usr: usr.organization_memberships.add(
                registration.publisher
            ),
            "created_regular_user_without_organization": lambda usr: None,
        },
    )
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role.startswith("created_") else None,
    )
    SignUpFactory(
        signup_group=signup_group,
        registration=registration,
    )
    SignUpPaymentFactory(signup=None, signup_group=signup_group)

    response = assert_get_detail(api_client, signup_group.pk)
    assert_payment_fields_exist(response.data["payment"])


@pytest.mark.django_db
def test_api_key_with_organization_and_registration_permission_can_get_signup_group_with_payment(
    api_client, data_source, registration
):
    data_source.owner = registration.publisher
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group,
        registration=registration,
    )
    SignUpPaymentFactory(signup=None, signup_group=signup_group)

    response = assert_get_detail(api_client, signup_group.pk)
    assert_payment_fields_exist(response.data["payment"])


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_registration_user_access_can_get_signup_group_when_strongly_identified(
    registration, api_client, is_substitute_user
):
    user = UserFactory(email="user@hel.fi" if is_substitute_user else "user@test.com")
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=is_substitute_user,
    )

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = assert_get_detail(api_client, signup_group.id)
        assert mocked.called is True

    assert response.data["is_created_by_current_user"] is False
    assert response.data["has_contact_person_access"] is False


@pytest.mark.django_db
def test_registration_user_access_cannot_get_signup_group_when_not_strongly_identified(
    registration, user, user_api_client
):
    signup_group = SignUpGroupFactory(registration=registration)

    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = get_detail(user_api_client, signup_group.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert mocked.called is True


@pytest.mark.django_db
def test_substitute_user_can_get_signup_group_without_strong_identification(
    registration, api_client
):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    signup_group = SignUpGroupFactory(registration=registration)

    response = assert_get_detail(api_client, signup_group.id)
    assert response.data["is_created_by_current_user"] is False
    assert response.data["has_contact_person_access"] is False


@patch(
    "helevents.models.UserModelPermissionMixin.token_amr_claim",
    new_callable=PropertyMock,
    return_value=["suomi_fi"],
)
@pytest.mark.django_db
def test_get_contact_person_access_to_signup_group_with_access_code(
    mocked_amr_claim, api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    contact_person = SignUpContactPersonFactory(
        signup_group=signup_group, email="test@test.com"
    )
    access_code = contact_person.create_access_code()

    contact_person.refresh_from_db()
    assert contact_person.user_id is None
    assert contact_person.access_code is not None

    assert user.is_contact_person_of(signup_group) is False
    assert mocked_amr_claim.called is True
    mocked_amr_claim.reset_mock()

    # Use access code.
    response = assert_get_detail(
        api_client, signup_group.id, query=f"access_code={access_code}"
    )
    assert response.data["has_contact_person_access"] is True
    assert_signup_group_fields_exist(response.data)
    assert mocked_amr_claim.called is True
    mocked_amr_claim.reset_mock()

    contact_person.refresh_from_db()
    assert contact_person.user_id == user.id
    assert contact_person.access_code is None

    assert user.is_contact_person_of(signup_group) is True
    assert mocked_amr_claim.called is True


@pytest.mark.django_db
def test_cannot_use_already_used_signup_group_access_code(api_client, registration):
    user = UserFactory()

    user2 = UserFactory()
    api_client.force_authenticate(user2)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    contact_person = SignUpContactPersonFactory(
        signup_group=signup_group, email="test@test.com"
    )

    access_code = contact_person.create_access_code()
    assert access_code is not None

    contact_person.link_user(user)
    contact_person.refresh_from_db()
    assert contact_person.user_id == user.id
    assert contact_person.access_code is None

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = get_detail(
            api_client, signup_group.id, query=f"access_code={access_code}"
        )
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN

    contact_person.refresh_from_db()
    assert contact_person.user_id == user.id
    assert contact_person.access_code is None


@pytest.mark.django_db
def test_contact_person_can_get_signup_group_when_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group, user=user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = assert_get_detail(api_client, signup_group.id)
        assert mocked.called is True

    assert_signup_group_fields_exist(response.data)
    assert response.data["has_contact_person_access"] is True


@pytest.mark.django_db
def test_contact_person_cannot_get_signup_group_when_not_strongly_identified(
    api_client,
    registration,
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group, user=user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = get_detail(api_client, signup_group.id)
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "user_role",
    ["regular_user", "financial_admin", "regular_user_without_organization"],
)
@pytest.mark.django_db
def test_created_regular_user_or_financial_admin_or_user_without_organization_can_get_signup_group(
    api_client, registration, user_role
):
    if user_role == "regular_user_without_organization":
        user = UserFactory()
    else:
        user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    SignUpFactory(registration=registration, signup_group=signup_group)
    SignUpFactory(registration=registration, signup_group=signup_group)
    SignUpContactPersonFactory(signup_group=signup_group)

    response = assert_get_detail(api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is True
    assert response.data["has_contact_person_access"] is False


@pytest.mark.parametrize("user_role", ["regular_user", "financial_admin"])
@pytest.mark.django_db
def test_non_created_regular_user_or_financial_admin_cannot_get_signup_group(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    response = get_detail(api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_non_created_user_without_organization_cannot_get_signup_group(
    api_client, organization
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration__event__publisher=organization)

    response = get_detail(api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_user_from_other_organization_cannot_get_signup_group(
    api_client, user2, organization
):
    signup_group = SignUpGroupFactory(registration__event__publisher=organization)

    api_client.force_authenticate(user2)

    response = get_detail(api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_with_organization_and_registration_permissions_can_get_signup_group(
    api_client, data_source, organization
):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=data_source,
    )
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)
    SignUpContactPersonFactory(signup_group=signup_group)

    data_source.owner = organization
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    response = assert_get_detail(api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is False
    assert response.data["has_contact_person_access"] is False


@pytest.mark.django_db
def test_api_key_with_wrong_organization_cannot_get_signup_group(
    api_client, data_source, organization, organization2
):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=data_source,
    )

    data_source.owner = organization2
    data_source.save(update_fields=["owner"])
    api_client.credentials(apikey=data_source.api_key)

    response = get_detail(api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_cannot_get_signup_group(
    api_client, organization, data_source, other_data_source
):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=data_source,
    )

    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = get_detail(api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("user_role", ["superuser", "registration_admin", "admin"])
@pytest.mark.django_db
def test_superuser_or_registration_admin_or_registration_created_admin_can_get_signup_group_list(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    if user_role == "admin":
        registration.created_by = user
        registration.save(update_fields=["created_by"])

    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)

    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.id}",
        (signup_group, signup_group2),
    )


@pytest.mark.parametrize("user_role", ["admin", "financial_admin", "regular_user"])
@pytest.mark.django_db
def test_non_created_admin_or_financial_admin_or_regular_user_cannot_get_signup_group_list(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_contact_person_cannot_get_signup_group_list(api_client, registration):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group, user=user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = get_list(
            api_client,
            f"registration={registration.id}",
        )
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_registration_user_access_can_get_signup_group_list_when_strongly_identified(
    registration, user, user_api_client
):
    signup_group0 = SignUpGroupFactory(registration=registration)
    signup_group1 = SignUpGroupFactory(registration=registration)

    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        get_list_and_assert_signup_groups(
            user_api_client,
            f"registration={registration.id}",
            [signup_group0, signup_group1],
        )
        assert mocked.called is True


@pytest.mark.django_db
def test_registration_user_access_cannot_get_signup_group_list_when_not_strongly_identified(
    registration, user, user_api_client
):
    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = get_list(user_api_client, f"registration={registration.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert mocked.called is True


@pytest.mark.django_db
def test_anonymous_user_cannot_get_signup_group_list(api_client, registration):
    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    response = get_list(api_client, "")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_all_signup_groups_to_which_user_has_admin_role(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)

    get_list_and_assert_signup_groups(api_client, "", (signup_group, signup_group2))

    user.registration_admin_organizations.clear()
    user.admin_organizations.add(registration.publisher)

    api_client.force_authenticate(user)

    get_list_and_assert_signup_groups(api_client, "", [])


@pytest.mark.django_db
def test_user_from_other_organization_cannot_get_signup_group_list(
    api_client, registration, user2
):
    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    api_client.force_authenticate(user2)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_cannot_get_signup_groups_of_nonexistent_registration(
    api_client, registration, user2
):
    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    api_client.force_authenticate(user2)

    response = get_list(api_client, "registration=not-exist")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration"] == "Invalid registration ID(s) given."


@pytest.mark.django_db
def test_api_key_with_organization_and_user_editable_registrations_can_get_signup_group_list(
    api_client, data_source, organization, registration
):
    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)

    data_source.owner = organization
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])

    api_client.credentials(apikey=data_source.api_key)

    get_list_and_assert_signup_groups(
        api_client, f"registration={registration.id}", (signup_group, signup_group2)
    )


@pytest.mark.django_db
def test_api_key_with_organization_without_user_editable_registrations_cannot_get_signup_group_list(
    api_client, data_source, organization, registration
):
    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    data_source.owner = organization
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_with_wrong_organization_cannot_get_signup_group_list(
    api_client, data_source, organization2, registration
):
    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    data_source.owner = organization2
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "field,contact_person_field",
    [
        ("first_name", False),
        ("last_name", False),
        ("email", True),
        ("membership_number", True),
        ("phone_number", True),
    ],
)
@pytest.mark.django_db
def test_signup_group_list_assert_text_filter(
    field, contact_person_field, api_client, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)

    signup_kwargs = {
        "signup_group": signup_group,
        "registration": registration,
    }
    signup2_kwargs = {
        "signup_group": signup_group2,
        "registration": registration,
    }

    if contact_person_field:
        SignUpContactPersonFactory(
            signup_group=signup_group, **{field: "field_value_1"}
        )
        SignUpContactPersonFactory(
            signup_group=signup_group2, **{field: "field_value_2"}
        )
    else:
        signup_kwargs[field] = "field_value_1"
        signup2_kwargs[field] = "field_value_2"

    SignUpFactory(**signup_kwargs)
    SignUpFactory(**signup2_kwargs)

    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.id}&text=field_value_2",
        [signup_group2],
    )


@pytest.mark.django_db
def test_signup_group_list_assert_status_filter(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )

    signup_group2 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group2,
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )

    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.id}&attendee_status={SignUp.AttendeeStatus.ATTENDING}",
        (signup_group,),
    )
    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.id}&attendee_status={SignUp.AttendeeStatus.WAITING_LIST}",
        (signup_group2,),
    )
    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.id}"
        f"&attendee_status={SignUp.AttendeeStatus.ATTENDING},{SignUp.AttendeeStatus.WAITING_LIST}",
        (
            signup_group,
            signup_group2,
        ),
    )

    response = get_list(
        api_client, f"registration={registration.id}&attendee_status=invalid-value"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_filter_signup_groups(api_client, registration, registration2):
    user = create_user_by_role("registration_admin", registration.publisher)
    user2 = create_user_by_role("registration_admin", registration2.publisher)

    signup_group0 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group0,
        registration=registration,
        first_name="Michael",
        last_name="Jackson",
    )
    SignUpFactory(
        signup_group=signup_group0,
        registration=registration,
        first_name="Michael",
        last_name="Jackson2",
    )
    SignUpContactPersonFactory(signup_group=signup_group0, email="test@test.com")

    signup_group1 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group1,
        registration=registration,
        first_name="Michael",
        last_name="Jackson3",
    )
    SignUpFactory(
        signup_group=signup_group1,
        registration=registration,
        first_name="Michael",
        last_name="Jackson4",
    )
    SignUpContactPersonFactory(signup_group=signup_group1, email="test3@test.com")

    signup_group2 = SignUpGroupFactory(registration=registration2)
    SignUpFactory(
        signup_group=signup_group2,
        registration=registration2,
        first_name="Joe",
        last_name="Biden",
    )
    SignUpFactory(
        signup_group=signup_group2,
        registration=registration2,
        first_name="Hillary",
        last_name="Clinton",
    )
    SignUpContactPersonFactory(signup_group=signup_group2, email="test2@test.com")

    signup_group3 = SignUpGroupFactory(registration=registration2)
    SignUpFactory(
        signup_group=signup_group3,
        registration=registration2,
        first_name="Donald",
        last_name="Duck",
    )
    SignUpFactory(
        signup_group=signup_group3,
        registration=registration2,
        first_name="Mickey",
        last_name="Mouse",
    )
    SignUpContactPersonFactory(
        signup_group=signup_group3,
        email="test4@test.com",
        membership_number="1234",
    )

    api_client.force_authenticate(user)
    get_list_and_assert_signup_groups(
        api_client,
        "",
        [signup_group0, signup_group1],
    )
    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.id}",
        [signup_group0, signup_group1],
    )

    api_client.force_authenticate(user2)
    get_list_and_assert_signup_groups(
        api_client,
        "",
        [signup_group2, signup_group3],
    )
    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration2.id}",
        [signup_group2, signup_group3],
    )

    #  search signups by name (first name - last name)
    get_list_and_assert_signup_groups(
        api_client, f"registration={registration2.id}&text=mickey m", [signup_group3]
    )
    #  search signups by name (last name - first name)
    get_list_and_assert_signup_groups(
        api_client, f"registration={registration2.id}&text=mouse m", [signup_group3]
    )

    #  search signups by membership number
    get_list_and_assert_signup_groups(
        api_client, f"registration={registration2.id}&text=34", [signup_group3]
    )
    get_list_and_assert_signup_groups(
        api_client, f"registration={registration2.id}&text=3456", []
    )


@pytest.mark.django_db
def test_no_signup_groups_found_with_registration_id(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    SignUpGroupFactory(registration=registration)

    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.pk + 1}",
        [],
    )


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_get_detail(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)

    assert_get_detail(api_client, signup_group.id)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        signup_group.pk
    ]


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_get_list(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)

    get_list_and_assert_signup_groups(api_client, "", [signup_group, signup_group2])

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([signup_group.pk, signup_group2.pk])


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_signup_price_group_in_signup_group_data(api_client, registration, user_role):
    languages = ("fi", "sv", "en")

    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup = SignUpFactory(registration=registration, signup_group=signup_group)
    signup_price_group = SignUpPriceGroupFactory(signup=signup)

    response = assert_get_detail(api_client, signup_group.id)
    resp_json = response.json()

    assert_fields_exist(
        resp_json["signups"][0]["price_group"],
        (
            "id",
            "registration_price_group",
            "description",
            "price",
            "vat_percentage",
            "price_without_vat",
            "vat",
        ),
    )
    assert_fields_exist(
        resp_json["signups"][0]["price_group"]["description"], languages
    )

    assert resp_json["signups"][0]["price_group"]["id"] == signup_price_group.pk
    assert resp_json["signups"][0]["price_group"]["registration_price_group"] == (
        signup_price_group.registration_price_group_id
    )
    assert Decimal(resp_json["signups"][0]["price_group"]["price"]) == (
        signup_price_group.registration_price_group.price
    )
    assert Decimal(resp_json["signups"][0]["price_group"]["vat_percentage"]) == (
        signup_price_group.registration_price_group.vat_percentage
    )
    assert Decimal(resp_json["signups"][0]["price_group"]["price_without_vat"]) == (
        signup_price_group.registration_price_group.price_without_vat
    )
    assert Decimal(resp_json["signups"][0]["price_group"]["vat"]) == (
        signup_price_group.registration_price_group.vat
    )
    for lang in languages:
        assert resp_json["signups"][0]["price_group"]["description"][lang] == getattr(
            signup_price_group.registration_price_group.price_group,
            f"description_{lang}",
        )


@pytest.mark.django_db
def test_soft_deleted_signup_group_not_found(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration, deleted=True)

    response = get_detail(api_client, signup_group.pk)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_soft_deleted_signup_groups_not_in_list(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration, deleted=True)

    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.pk}",
        [signup_group, signup_group2],
    )
