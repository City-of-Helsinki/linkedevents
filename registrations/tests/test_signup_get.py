from collections import Counter
from unittest.mock import patch, PropertyMock

import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.conftest import APIClient
from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import RegistrationUserAccessFactory, SignUpFactory

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


def assert_signup_fields_exist(data):
    fields = (
        "id",
        "service_language",
        "created_time",
        "last_modified_time",
        "created_by",
        "last_modified_by",
        "responsible_for_group",
        "first_name",
        "last_name",
        "date_of_birth",
        "city",
        "email",
        "extra_info",
        "membership_number",
        "phone_number",
        "notifications",
        "attendee_status",
        "street_address",
        "zipcode",
        "presence_status",
        "registration",
        "signup_group",
        "native_language",
        "user_consent",
        "is_created_by_current_user",
    )
    assert_fields_exist(data, fields)


# === tests ===


@pytest.mark.django_db
def test_admin_user_cannot_get_signup(registration, signup, user_api_client):
    response = get_detail(user_api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_registration_admin_user_can_get_signup(
    user_api_client, registration, signup, user
):
    default_organization = user.get_default_organization()
    default_organization.admin_users.remove(user)
    default_organization.registration_admin_users.add(user)

    response = assert_get_detail(user_api_client, signup.id)
    assert response.data["is_created_by_current_user"] is False


@pytest.mark.django_db
def test_registration_user_access_can_get_signup_when_strongly_identified(
    registration, signup, user, user_api_client
):
    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        response = assert_get_detail(user_api_client, signup.id)
        assert mocked.called is True
    assert_signup_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is False


@pytest.mark.django_db
def test_registration_user_access_cannot_get_signup_when_not_strongly_identified(
    registration, signup, user, user_api_client
):
    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=None,
    ) as mocked:
        response = get_detail(user_api_client, signup.id)
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_regular_non_created_user_cannot_get_signup(
    user_api_client, registration, signup, user
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    response = get_detail(user_api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_regular_created_user_can_get_signup(
    user_api_client, registration, signup, user
):
    signup.created_by = user
    signup.save(update_fields=["created_by"])

    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    response = assert_get_detail(user_api_client, signup.id)
    assert_signup_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is True


@pytest.mark.django_db
def test_non_created_user_without_organization_cannot_get_signup(
    api_client, registration, signup
):
    user = UserFactory()
    api_client.force_authenticate(user)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_created_user_without_organization_can_get_signup(api_client, registration):
    user = UserFactory()
    api_client.force_authenticate(user)
    signup = SignUpFactory(created_by=user)

    response = assert_get_detail(api_client, signup.id)
    assert_signup_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is True


@pytest.mark.django_db
def test_user_from_other_organization_cannot_get_signup(
    api_client, registration, signup, user2
):
    api_client.force_authenticate(user2)

    response = get_detail(api_client, signup.id)
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


@pytest.mark.django_db
def test_superuser_can_get_signup_list(
    api_client, registration, signup, signup2, super_user
):
    api_client.force_authenticate(super_user)
    get_list_and_assert_signups(
        api_client, f"registration={registration.id}", [signup, signup2]
    )


@pytest.mark.django_db
def test_admin_user_cannot_get_signup_list(
    registration, signup, signup2, user_api_client
):
    response = get_list(user_api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_registration_admin_user_can_get_signup_list(
    registration, signup, signup2, user_api_client, user
):
    default_organization = user.get_default_organization()
    default_organization.admin_users.remove(user)
    default_organization.registration_admin_users.add(user)

    get_list_and_assert_signups(
        user_api_client, f"registration={registration.id}", (signup, signup2)
    )


@pytest.mark.django_db
def test_registration_user_access_can_get_signup_list_when_strongly_identified(
    registration, signup, signup2, user, user_api_client
):
    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        get_list_and_assert_signups(
            user_api_client, f"registration={registration.id}", [signup, signup2]
        )
        assert mocked.called is True


@pytest.mark.django_db
def test_registration_user_access_cannot_get_signup_list_when_not_strongly_identified(
    registration, signup, signup2, user, user_api_client
):
    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=None,
    ) as mocked:
        response = get_list(user_api_client, f"registration={registration.id}")
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_anonymous_user_cannot_get_signup_list(api_client, registration, signup):
    response = get_list(api_client, "")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_get_signup_list(
    registration, signup, signup2, user, user_api_client
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    response = get_list(user_api_client, f"registration={registration.id}")
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
    user_api_client,
):
    default_organization = user.get_default_organization()

    # Admin user is not allowed to see signups
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
        return_value=None,
    ) as mocked:
        get_list_and_assert_signups(user_api_client, "", [])
        assert mocked.called is True

    # Registration user is allowed to see signups if they are strongly identified
    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
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
    assert response.data["detail"] == "Registration with id not-exist doesn't exist."


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
    "field",
    ["first_name", "email", "membership_number", "phone_number"],
)
@pytest.mark.django_db
def test_signup_list_assert_text_filter(
    field, registration, signup, signup2, user_api_client, user
):
    user.get_default_organization().registration_admin_users.add(user)

    setattr(signup, field, "field_value_1")
    signup.save()
    setattr(signup2, field, "field_value_2")
    signup2.save()

    get_list_and_assert_signups(
        user_api_client, f"registration={registration.id}&text=field_value_1", [signup]
    )


@pytest.mark.django_db
def test_signup_list_assert_attendee_status_filter(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)

    signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
    )
    signup2 = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )

    api_client.force_authenticate(user)

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
def test_filter_signups(
    api_client, registration, registration2, user, user2, event, event2
):
    user.get_default_organization().registration_admin_users.add(user)
    user2.get_default_organization().registration_admin_users.add(user2)

    signup = SignUpFactory(
        registration=registration,
        first_name="Michael",
        last_name="Jackson",
        email="test@test.com",
    )
    signup2 = SignUpFactory(
        registration=registration,
        first_name="Michael",
        last_name="Jackson2",
        email="test2@test.com",
    )
    signup3 = SignUpFactory(
        registration=registration,
        first_name="Michael",
        last_name="Jackson3",
        email="test3@test.com",
    )
    signup4 = SignUpFactory(
        registration=registration,
        first_name="Michael",
        last_name="Jackson4",
        email="test4@test.com",
    )
    signup5 = SignUpFactory(
        registration=registration2,
        first_name="Joe",
        last_name="Biden",
        email="test@test.com",
    )
    signup6 = SignUpFactory(
        registration=registration2,
        first_name="Hillary",
        last_name="Clinton",
        email="test2@test.com",
    )
    signup7 = SignUpFactory(
        registration=registration2,
        first_name="Donald",
        last_name="Duck",
        email="test3@test.com",
        membership_number="1234",
    )
    signup8 = SignUpFactory(
        registration=registration2,
        first_name="Mickey",
        last_name="Mouse",
        email="test4@test.com",
        membership_number="3456",
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
def test_signup_id_is_audit_logged_on_get_detail(api_client, signup):
    user = UserFactory()
    user.registration_admin_organizations.add(signup.publisher)
    api_client.force_authenticate(user)

    assert_get_detail(api_client, signup.id)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [signup.pk]


@pytest.mark.django_db
def test_signup_id_is_audit_logged_on_get_list(api_client, signup, signup2):
    user = UserFactory()
    user.registration_admin_organizations.add(signup.publisher)
    api_client.force_authenticate(user)

    get_list_and_assert_signups(api_client, "", [signup, signup2])

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([signup.pk, signup2.pk])
