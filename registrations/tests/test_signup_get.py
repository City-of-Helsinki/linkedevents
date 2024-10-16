from collections import Counter
from decimal import Decimal
from unittest.mock import PropertyMock, patch

import pytest
from django.conf import settings
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.conftest import APIClient
from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpPaymentFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.utils import create_user_by_role

# === util methods ===


def get_list(api_client: APIClient, query_string: str = None):
    url = reverse("signup-list")

    if query_string:
        url = "%s?%s" % (url, query_string)

    return api_client.get(url)


def assert_signups_in_response(signups: list, response: dict, query: str = ""):
    response_signup_ids = {signup["id"] for signup in response.data["data"]}
    expected_signup_ids = {signup.id for signup in signups}
    if query:
        assert response_signup_ids == expected_signup_ids, f"\nquery: {query}"
    else:
        assert response_signup_ids == expected_signup_ids


def get_list_and_assert_signups(api_client: APIClient, query: str, signups: list):
    response = get_list(api_client, query_string=query)
    assert_signups_in_response(signups, response, query)


def get_detail(api_client: APIClient, signup_pk: str, query: str = None):
    detail_url = reverse(
        "signup-detail",
        kwargs={"pk": signup_pk},
    )

    if query:
        detail_url = "%s?%s" % (detail_url, query)

    return api_client.get(detail_url)


def assert_get_detail(api_client: APIClient, signup_pk: str, query: str = None):
    response = get_detail(api_client, signup_pk, query)
    assert response.status_code == status.HTTP_200_OK

    return response


def assert_contact_person_fields_exist(data):
    fields = (
        "id",
        "first_name",
        "last_name",
        "service_language",
        "native_language",
        "membership_number",
        "email",
        "phone_number",
        "notifications",
    )
    assert_fields_exist(data, fields)


def assert_payment_fields_exist(data):
    fields = (
        "id",
        "created_time",
        "last_modified_time",
        "created_by",
        "last_modified_by",
        "external_order_id",
        "checkout_url",
        "logged_in_checkout_url",
        "amount",
        "status",
    )
    assert_fields_exist(data, fields)


def assert_signup_fields_exist(data):
    fields = (
        "id",
        "created_time",
        "last_modified_time",
        "created_by",
        "last_modified_by",
        "first_name",
        "last_name",
        "date_of_birth",
        "phone_number",
        "city",
        "extra_info",
        "attendee_status",
        "street_address",
        "zipcode",
        "presence_status",
        "registration",
        "signup_group",
        "user_consent",
        "is_created_by_current_user",
        "contact_person",
        "anonymization_time",
        "price_group",
        "has_contact_person_access",
    )
    if settings.WEB_STORE_INTEGRATION_ENABLED:
        fields += ("payment", "payment_cancellation", "payment_refund")

    assert_fields_exist(data, fields)
    assert_contact_person_fields_exist(data["contact_person"])


# === tests ===


@pytest.mark.parametrize("user_role", ["regular_user", "admin", "financial_admin"])
@pytest.mark.django_db
def test_registration_non_created_user_or_admin_or_financial_admin_cannot_get_signup(
    registration, signup, user2, api_client, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    registration.created_by = user2
    registration.save(update_fields=["created_by"])

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_registration_created_admin_can_get_signup(registration, signup, api_client):
    user = create_user_by_role("admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.created_by = user
    registration.save(update_fields=["created_by"])

    response = assert_get_detail(api_client, signup.id)
    assert_signup_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is False
    assert response.data["has_contact_person_access"] is False


@pytest.mark.parametrize(
    "user_role",
    ["regular_user", "admin", "financial_admin", "regular_user_without_organization"],
)
@pytest.mark.django_db
def test_created_user_or_admin_or_financial_admin_can_get_signup(
    registration, signup, api_client, user_role
):
    if user_role == "regular_user_without_organization":
        user = UserFactory()
    else:
        user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup.created_by = user
    signup.save(update_fields=["created_by"])

    response = assert_get_detail(api_client, signup.id)
    assert_signup_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is True
    assert response.data["has_contact_person_access"] is False


@pytest.mark.django_db
def test_registration_admin_user_can_get_signup(api_client, signup):
    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    response = assert_get_detail(api_client, signup.id)
    assert response.data["is_created_by_current_user"] is False
    assert response.data["has_contact_person_access"] is False


@pytest.mark.django_db
def test_non_created_user_without_organization_cannot_get_signup(
    api_client, registration, signup
):
    user = UserFactory()
    api_client.force_authenticate(user)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_user_from_other_organization_cannot_get_signup(
    api_client, registration, signup, user2
):
    api_client.force_authenticate(user2)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_registration_user_access_can_get_signup_when_strongly_identified(
    registration, signup, api_client, is_substitute_user
):
    user = UserFactory(email="user@hel.fi" if is_substitute_user else "user@test.com")
    user.organization_memberships.add(signup.publisher)
    api_client.force_authenticate(user)

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
        response = assert_get_detail(api_client, signup.id)
        assert mocked.called is True

    assert_signup_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is False
    assert response.data["has_contact_person_access"] is False


@pytest.mark.django_db
def test_registration_user_access_cannot_get_signup_when_not_strongly_identified(
    registration, signup, api_client
):
    user = UserFactory()
    user.organization_memberships.add(signup.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = get_detail(api_client, signup.id)
        assert mocked.called is True

    assert response.status_code == status.HTTP_403_FORBIDDEN


@patch(
    "helevents.models.UserModelPermissionMixin.token_amr_claim",
    new_callable=PropertyMock,
    return_value=["suomi_fi"],
)
@pytest.mark.django_db
def test_get_contact_person_access_to_signup_with_access_code(
    mocked_amr_claim, api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    contact_person = SignUpContactPersonFactory(signup=signup, email="test@test.com")

    access_code = contact_person.create_access_code()
    assert access_code is not None

    contact_person.refresh_from_db()
    assert contact_person.user_id is None
    assert contact_person.access_code is not None

    assert user.is_contact_person_of(signup) is False
    assert mocked_amr_claim.called is True
    mocked_amr_claim.reset_mock()

    # Use access code.
    response = assert_get_detail(
        api_client, signup.id, query=f"access_code={access_code}"
    )
    assert response.data["has_contact_person_access"] is True
    assert_signup_fields_exist(response.data)
    assert mocked_amr_claim.called is True
    mocked_amr_claim.reset_mock()

    contact_person.refresh_from_db()
    assert contact_person.user_id == user.id
    assert contact_person.access_code is None

    assert user.is_contact_person_of(signup) is True
    assert mocked_amr_claim.called is True


@pytest.mark.django_db
def test_cannot_use_already_used_signup_access_code(api_client, registration):
    user = UserFactory()

    user2 = UserFactory()
    api_client.force_authenticate(user2)

    signup = SignUpFactory(registration=registration)
    contact_person = SignUpContactPersonFactory(signup=signup, email="test@test.com")

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
        response = get_detail(api_client, signup.id, query=f"access_code={access_code}")
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN

    contact_person.refresh_from_db()
    assert contact_person.user_id == user.id
    assert contact_person.access_code is None


@pytest.mark.django_db
def test_contact_person_can_get_signup_when_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = assert_get_detail(api_client, signup.id)
        assert mocked.called is True

    assert response.data["has_contact_person_access"] is True
    assert_signup_fields_exist(response.data)


@pytest.mark.django_db
def test_contact_person_cannot_get_signup_when_not_strongly_identified(
    api_client, registration
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = get_detail(api_client, signup.id)
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_with_organization_and_registration_permission_can_get_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    response = assert_get_detail(api_client, signup.id)
    assert_signup_fields_exist(response.data)
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
def test_authenticated_user_with_correct_role_can_get_signup_with_payment(
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

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role.startswith("created_") else None,
    )
    SignUpPaymentFactory(signup=signup)

    response = assert_get_detail(api_client, signup.id)
    assert_payment_fields_exist(response.data["payment"])


@pytest.mark.django_db
def test_api_key_with_organization_and_registration_permission_can_get_signup_with_payment(
    api_client, data_source, registration
):
    data_source.owner = registration.publisher
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    signup = SignUpFactory(registration=registration)
    SignUpPaymentFactory(signup=signup)

    response = assert_get_detail(api_client, signup.id)
    assert_payment_fields_exist(response.data["payment"])


@pytest.mark.django_db
def test_api_key_with_organization_without_registration_permission_cannot_get_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.save(update_fields=["owner"])
    api_client.credentials(apikey=data_source.api_key)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_with_wrong_organization_cannot_get_signup(
    api_client, data_source, organization2, registration, signup
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_cannot_get_signup(
    api_client, organization, other_data_source, registration, signup
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("user_role", ["superuser", "admin", "registration_admin"])
@pytest.mark.django_db
def test_superuser_or_created_admin_or_registration_admin_can_get_signup_list(
    api_client, registration, signup, signup2, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    if user_role == "admin":
        registration.created_by = user
        registration.save(update_fields=["created_by"])

    get_list_and_assert_signups(
        api_client, f"registration={registration.id}", [signup, signup2]
    )


@pytest.mark.parametrize("user_role", ["admin", "financial_admin"])
@pytest.mark.django_db
def test_registration_non_created_admin_or_financial_admin_cannot_get_signup_list(
    registration, signup, signup2, api_client, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_contact_person_cannot_get_signup_list(api_client, registration):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    signup2 = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup2, user=user)

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


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_registration_user_access_can_get_signup_list_when_strongly_identified(
    registration, signup, signup2, api_client, is_substitute_user
):
    user = UserFactory(email="user@hel.fi" if is_substitute_user else "user@test.com")
    user.organization_memberships.add(signup.publisher)
    api_client.force_authenticate(user)

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
        get_list_and_assert_signups(
            api_client, f"registration={registration.id}", [signup, signup2]
        )
        assert mocked.called is True


@pytest.mark.django_db
def test_registration_user_access_cannot_get_signup_list_when_not_strongly_identified(
    registration, signup, signup2, api_client
):
    user = UserFactory()
    user.organization_memberships.add(signup.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = get_list(api_client, f"registration={registration.id}")
        assert mocked.called is True

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_substitute_user_can_get_signup_list_when_not_strongly_identified(
    registration, signup, signup2, api_client
):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(signup.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    get_list_and_assert_signups(
        api_client, f"registration={registration.id}", [signup, signup2]
    )


@pytest.mark.django_db
def test_anonymous_user_cannot_get_signup_list(api_client, registration, signup):
    response = get_list(api_client, "")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_get_signup_list(registration, signup, signup2, api_client):
    user = create_user_by_role("regular_user", registration.publisher)
    api_client.force_authenticate(user)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_get_all_signups_to_which_user_has_admin_role(
    api_client,
    registration,
    registration2,
    signup,
    signup2,
    signup3,
    super_user,
    user,
    user2,
    user_api_client,
):
    default_organization = user.get_default_organization()

    registration.created_by = user2
    registration.save(update_fields=["created_by"])

    registration2.created_by = user2
    registration2.save(update_fields=["created_by"])

    # Admin user is not allowed to see signups (if registration not created by user)
    get_list_and_assert_signups(user_api_client, "", [])

    # Registration admin user is allowed to see signups
    default_organization.admin_users.remove(user)
    default_organization.registration_admin_users.add(user)

    # Superuser is allowed to see all signups
    signup3.registration = registration2
    signup3.save()
    api_client.force_authenticate(super_user)
    get_list_and_assert_signups(api_client, "", [signup, signup2, signup3])

    # Regular user is not allowed to see signups
    default_organization.regular_users.add(user)
    default_organization.registration_admin_users.remove(user)
    get_list_and_assert_signups(user_api_client, "", [])

    # Registration user is not allowed to see signups if they are not strongly identified
    RegistrationUserAccessFactory(registration=registration, email=user.email)
    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        get_list_and_assert_signups(user_api_client, "", [])
        assert mocked.called is True

    # Registration user is allowed to see signups if they are strongly identified
    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        get_list_and_assert_signups(user_api_client, "", [signup, signup2])
        assert mocked.called is True


@pytest.mark.django_db
def test_user_from_other_organization_cannot_get_signup_list(
    api_client, registration, signup, signup2, user2
):
    api_client.force_authenticate(user2)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_cannot_get_signups_of_nonexistent_registration(
    api_client, registration, signup, signup2, user2
):
    api_client.force_authenticate(user2)

    response = get_list(api_client, "registration=not-exist")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration"] == "Invalid registration ID(s) given."


@pytest.mark.django_db
def test_api_key_with_organization_can_get_signup_list(
    api_client, data_source, organization, registration, signup, signup2
):
    data_source.owner = organization
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    get_list_and_assert_signups(
        api_client, f"registration={registration.id}", [signup, signup2]
    )


@pytest.mark.django_db
def test_api_key_with_wrong_organization_cannot_get_signup_list(
    api_client, data_source, organization2, registration, signup, signup2
):
    data_source.owner = organization2
    data_source.save()
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
def test_signup_list_assert_text_filter(
    field, contact_person_field, registration, signup, signup2, api_client
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    if contact_person_field:
        setattr(signup.contact_person, field, "field_value_1")
        signup.contact_person.save(update_fields=[field])
        setattr(signup2.contact_person, field, "field_value_2")
        signup2.contact_person.save(update_fields=[field])
    else:
        setattr(signup, field, "field_value_1")
        signup.save()
        setattr(signup2, field, "field_value_2")
        signup2.save()

    get_list_and_assert_signups(
        api_client, f"registration={registration.id}&text=field_value_1", [signup]
    )


@pytest.mark.django_db
def test_signup_list_assert_attendee_status_filter(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
    )
    signup2 = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )

    get_list_and_assert_signups(
        api_client,
        f"registration={registration.id}&attendee_status={SignUp.AttendeeStatus.ATTENDING}",
        [signup],
    )
    get_list_and_assert_signups(
        api_client,
        f"registration={registration.id}&attendee_status={SignUp.AttendeeStatus.WAITING_LIST}",
        [signup2],
    )
    get_list_and_assert_signups(
        api_client,
        f"registration={registration.id}&attendee_status={SignUp.AttendeeStatus.ATTENDING},"
        f"{SignUp.AttendeeStatus.WAITING_LIST}",
        [
            signup,
            signup2,
        ],
    )

    response = get_list(
        api_client, f"registration={registration.id}&attendee_status=invalid-value"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_signup_list_orders_by_id_by_default(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_first = SignUpFactory(
        registration=registration,
        first_name="The First",
        last_name="Attendee",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    signup_second = SignUpFactory(
        registration=registration,
        first_name="Second",
        last_name="Attendee",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    signup_third = SignUpFactory(
        registration=registration,
        first_name="A Last",
        last_name="Attendee",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )

    response = get_list(
        api_client,
        query_string=f"registration={registration.id}&attendee_status={SignUp.AttendeeStatus.ATTENDING}",
    )
    data = response.data["data"]
    assert data[0]["id"] == signup_first.id
    assert data[1]["id"] == signup_second.id
    assert data[2]["id"] == signup_third.id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ordering",
    (
        ("first_name", ("A Last", "Second", "The First")),
        ("-first_name", ("The First", "Second", "A Last")),
        ("last_name", ("Second", "A Last", "The First")),
        ("-last_name", ("The First", "A Last", "Second")),
    ),
)
def test_signup_list_orders_by_name(api_client, registration, ordering):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    SignUpFactory(
        registration=registration,
        first_name="The First",
        last_name="C Attendee",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    SignUpFactory(
        registration=registration,
        first_name="Second",
        last_name="A Attendee",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    SignUpFactory(
        registration=registration,
        first_name="A Last",
        last_name="B Attendee",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )

    response = get_list(
        api_client,
        query_string=f"registration={registration.id}&"
        f"attendee_status={SignUp.AttendeeStatus.ATTENDING}&"
        f"sort={ordering[0]}",
    )
    names = tuple([data["first_name"] for data in response.data["data"]])
    assert names == ordering[1]


@pytest.mark.django_db
def test_filter_signups(api_client, registration, registration2, event, event2):
    user = create_user_by_role("registration_admin", registration.publisher)
    user2 = create_user_by_role("registration_admin", registration2.publisher)

    signup = SignUpFactory(
        registration=registration,
        first_name="Michael",
        last_name="Jackson",
    )
    SignUpContactPersonFactory(signup=signup, email="test@test.com")

    signup2 = SignUpFactory(
        registration=registration,
        first_name="Michael",
        last_name="Jackson2",
    )
    SignUpContactPersonFactory(signup=signup2, email="test2@test.com")

    signup3 = SignUpFactory(
        registration=registration,
        first_name="Michael",
        last_name="Jackson3",
    )
    SignUpContactPersonFactory(signup=signup3, email="test3@test.com")

    signup4 = SignUpFactory(
        registration=registration,
        first_name="Michael",
        last_name="Jackson4",
    )
    SignUpContactPersonFactory(signup=signup4, email="test4@test.com")

    signup5 = SignUpFactory(
        registration=registration2,
        first_name="Joe",
        last_name="Biden",
    )
    SignUpContactPersonFactory(signup=signup5, email="test@test.com")

    signup6 = SignUpFactory(
        registration=registration2,
        first_name="Hillary",
        last_name="Clinton",
    )
    SignUpContactPersonFactory(signup=signup6, email="test2@test.com")

    signup7 = SignUpFactory(
        registration=registration2,
        first_name="Donald",
        last_name="Duck",
    )
    SignUpContactPersonFactory(
        signup=signup7, email="test3@test.com", membership_number="1234"
    )

    signup8 = SignUpFactory(
        registration=registration2,
        first_name="Mickey",
        last_name="Mouse",
    )
    SignUpContactPersonFactory(
        signup=signup8, email="test4@test.com", membership_number="3456"
    )

    api_client.force_authenticate(user)
    get_list_and_assert_signups(
        api_client,
        "",
        [signup, signup2, signup3, signup4],
    )
    get_list_and_assert_signups(
        api_client,
        f"registration={registration.id}",
        [signup, signup2, signup3, signup4],
    )

    api_client.force_authenticate(user2)
    get_list_and_assert_signups(
        api_client,
        "",
        [signup5, signup6, signup7, signup8],
    )
    get_list_and_assert_signups(
        api_client,
        f"registration={registration2.id}",
        [signup5, signup6, signup7, signup8],
    )

    #  search signups by name (first name - last name)
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=mickey m", [signup8]
    )
    #  search signups by name (last name - first name)
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=mouse m", [signup8]
    )

    #  search signups by membership number
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=34", [signup7, signup8]
    )
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=3456", [signup8]
    )


@pytest.mark.django_db
def test_no_signups_found_with_registration_id(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    SignUpFactory(registration=registration)

    get_list_and_assert_signups(
        api_client,
        f"registration={registration.pk + 1}",
        [],
    )


@pytest.mark.django_db
def test_signup_id_is_audit_logged_on_get_detail(api_client, signup):
    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert_get_detail(api_client, signup.id)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [signup.pk]


@pytest.mark.django_db
def test_signup_id_is_audit_logged_on_get_list(api_client, signup, signup2):
    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    get_list_and_assert_signups(api_client, "", [signup, signup2])

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([signup.pk, signup2.pk])


@pytest.mark.parametrize(
    "is_superuser,organization_role_attr",
    [
        (False, "registration_admin_organizations"),
        (True, "registration_admin_organizations"),
        (True, "admin_organizations"),
        (True, "organization_memberships"),
        (True, None),
    ],
)
@pytest.mark.django_db
def test_signups_list_ordering(
    api_client, registration, is_superuser, organization_role_attr
):
    user = UserFactory(is_superuser=is_superuser)
    if organization_role_attr is not None:
        getattr(user, organization_role_attr).add(registration.publisher)
    api_client.force_authenticate(user)

    signups = [
        SignUpFactory(
            registration=registration,
            first_name="",
            last_name="",
        ),
        SignUpFactory(
            registration=registration,
            first_name="",
            last_name=None,
        ),
        SignUpFactory(
            registration=registration,
            first_name="Abc",
            last_name="Abc",
        ),
        SignUpFactory(
            registration=registration,
            first_name="Bcd",
            last_name="Bcd",
        ),
        SignUpFactory(
            registration=registration,
            first_name="Bcd",
            last_name="Cde",
        ),
        SignUpFactory(
            registration=registration,
            first_name="Äää",
            last_name="Ööö",
        ),
        SignUpFactory(
            registration=registration,
            first_name="Äöö",
            last_name="Äää",
        ),
        SignUpFactory(
            registration=registration,
            first_name="Öää",
            last_name="Äää",
        ),
        SignUpFactory(
            registration=registration,
            first_name=None,
            last_name=None,
        ),
    ]

    page_size = 3
    page_start = 0
    page_end = page_size
    for page in range(1, 4):
        response = get_list(
            api_client, query_string=f"page={page}&page_size={page_size}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == page_size

        for index, signup in enumerate(signups[page_start:page_end]):
            assert response.data["data"][index]["id"] == signup.id

        page_start += page_size
        page_end += page_size


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_get_signup_with_price_group(api_client, registration, user_role):
    languages = ("fi", "sv", "en")

    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    signup_price_group = SignUpPriceGroupFactory(signup=signup)

    response = assert_get_detail(api_client, signup.id)

    assert_fields_exist(
        response.data["price_group"],
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
    assert_fields_exist(response.data["price_group"]["description"], languages)

    assert response.data["price_group"]["id"] == signup_price_group.pk
    assert response.data["price_group"]["registration_price_group"] == (
        signup_price_group.registration_price_group_id
    )
    assert Decimal(response.data["price_group"]["price"]) == (
        signup_price_group.registration_price_group.price
    )
    assert Decimal(response.data["price_group"]["vat_percentage"]) == (
        signup_price_group.registration_price_group.vat_percentage
    )
    assert Decimal(response.data["price_group"]["price_without_vat"]) == (
        signup_price_group.registration_price_group.price_without_vat
    )
    assert Decimal(response.data["price_group"]["vat"]) == (
        signup_price_group.registration_price_group.vat
    )
    for lang in languages:
        assert response.data["price_group"]["description"][lang] == getattr(
            signup_price_group.registration_price_group.price_group,
            f"description_{lang}",
        )


@pytest.mark.django_db
def test_soft_deleted_signup_not_found(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration, deleted=True)

    response = get_detail(api_client, signup.pk)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_soft_deleted_signups_not_in_list(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    signup2 = SignUpFactory(registration=registration)
    SignUpFactory(registration=registration, deleted=True)

    get_list_and_assert_signups(
        api_client,
        f"registration={registration.pk}",
        [signup, signup2],
    )
