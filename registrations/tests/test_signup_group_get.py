from collections import Counter
from unittest.mock import patch, PropertyMock

import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SignUpFactory,
    SignUpGroupFactory,
)

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
        "extra_info",
        "created_time",
        "last_modified_time",
        "created_by",
        "last_modified_by",
        "is_created_by_current_user",
    )
    assert_fields_exist(data, fields)


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


@pytest.mark.django_db
def test_registration_admin_user_can_get_signup_group(
    user_api_client, registration, organization, user
):
    organization.registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration, signup_group=signup_group)
    SignUpFactory(registration=registration, signup_group=signup_group)

    response = assert_get_detail(user_api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is False


@pytest.mark.django_db
def test_registration_user_access_can_get_signup_group_when_strongly_identified(
    registration, user, user_api_client
):
    signup_group = SignUpGroupFactory(registration=registration)

    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        response = assert_get_detail(user_api_client, signup_group.id)
        assert mocked.called is True
    assert response.data["is_created_by_current_user"] is False


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
        return_value=None,
    ) as mocked:
        response = get_detail(user_api_client, signup_group.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert mocked.called is True


@pytest.mark.django_db
def test_regular_non_created_user_cannot_get_signup_group(
    user_api_client, user, organization
):
    signup_group = SignUpGroupFactory(registration__event__publisher=organization)

    organization.regular_users.add(user)
    organization.admin_users.remove(user)

    response = get_detail(user_api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_regular_created_user_can_get_signup_group(user_api_client, user, organization):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization, created_by=user
    )
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)

    organization.regular_users.add(user)
    organization.admin_users.remove(user)

    response = assert_get_detail(user_api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is True


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
def test_created_user_without_organization_can_get_signup_group(
    api_client, organization
):
    user = UserFactory()
    api_client.force_authenticate(user)
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization, created_by=user
    )
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)

    response = assert_get_detail(api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is True


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

    data_source.owner = organization
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    response = assert_get_detail(api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)
    assert response.data["is_created_by_current_user"] is False


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


@pytest.mark.django_db
def test_registration_admin_user_can_get_signup_group_list(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)

    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)

    api_client.force_authenticate(user)

    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.id}",
        (signup_group, signup_group2),
    )


@pytest.mark.django_db
def test_admin_user_cannot_get_signup_group_list(api_client, registration):
    user = UserFactory()
    user.admin_organizations.add(registration.publisher)

    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    api_client.force_authenticate(user)

    response = get_list(api_client, f"registration={registration.id}")
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
        return_value="heltunnistussuomifi",
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
        return_value=None,
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
def test_regular_user_cannot_get_signup_group_list(api_client, registration, user):
    SignUpGroupFactory(registration=registration)
    SignUpGroupFactory(registration=registration)

    default_org = user.get_default_organization()
    default_org.regular_users.add(user)
    default_org.admin_users.remove(user)

    api_client.force_authenticate(user)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_get_all_signup_groups_to_which_user_has_admin_role(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)

    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)

    api_client.force_authenticate(user)

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
    "field",
    ["first_name", "email", "membership_number", "phone_number"],
)
@pytest.mark.django_db
def test_signup_group_list_assert_text_filter(api_client, registration, field):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)

    signup_group = SignUpGroupFactory(registration=registration)
    signup_kwargs = {
        "signup_group": signup_group,
        "registration": registration,
        **{field: "field_value_2"},
    }
    SignUpFactory(**signup_kwargs)

    signup_group2 = SignUpGroupFactory(registration=registration)
    signup2_kwargs = {
        "signup_group": signup_group2,
        "registration": registration,
        **{field: "field_value_1"},
    }
    SignUpFactory(**signup2_kwargs)

    api_client.force_authenticate(user)

    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.id}&text=field_value_1",
        [signup_group2],
    )


@pytest.mark.django_db
def test_signup_group_list_assert_status_filter(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)

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

    api_client.force_authenticate(user)

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
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)

    user2 = UserFactory()
    user2.registration_admin_organizations.add(registration2.publisher)

    signup_group0 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group0,
        registration=registration,
        first_name="Michael",
        last_name="Jackson",
        email="test@test.com",
    )
    SignUpFactory(
        signup_group=signup_group0,
        registration=registration,
        first_name="Michael",
        last_name="Jackson2",
        email="test2@test.com",
    )

    signup_group1 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group1,
        registration=registration,
        first_name="Michael",
        last_name="Jackson3",
        email="test3@test.com",
    )
    SignUpFactory(
        signup_group=signup_group1,
        registration=registration,
        first_name="Michael",
        last_name="Jackson4",
        email="test4@test.com",
    )

    signup_group2 = SignUpGroupFactory(registration=registration2)
    SignUpFactory(
        signup_group=signup_group2,
        registration=registration2,
        first_name="Joe",
        last_name="Biden",
        email="test@test.com",
    )
    SignUpFactory(
        signup_group=signup_group2,
        registration=registration2,
        first_name="Hillary",
        last_name="Clinton",
        email="test2@test.com",
    )

    signup_group3 = SignUpGroupFactory(registration=registration2)
    SignUpFactory(
        signup_group=signup_group3,
        registration=registration2,
        first_name="Donald",
        last_name="Duck",
        email="test3@test.com",
        membership_number="1234",
    )
    SignUpFactory(
        signup_group=signup_group3,
        registration=registration2,
        first_name="Mickey",
        last_name="Mouse",
        email="test4@test.com",
        membership_number="3456",
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
        api_client, f"registration={registration2.id}&text=3456", [signup_group3]
    )


@pytest.mark.django_db
def test_no_signup_groups_found_with_registration_id(api_client, registration):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    SignUpGroupFactory(registration=registration)

    get_list_and_assert_signup_groups(
        api_client,
        f"registration={registration.pk + 1}",
        [],
    )


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_get_detail(api_client):
    signup_group = SignUpGroupFactory()

    user = UserFactory()
    user.registration_admin_organizations.add(signup_group.publisher)
    api_client.force_authenticate(user)

    assert_get_detail(api_client, signup_group.id)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        signup_group.pk
    ]


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_get_list(api_client, registration):
    signup_group = SignUpGroupFactory(registration=registration)
    signup_group2 = SignUpGroupFactory(registration=registration)

    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    get_list_and_assert_signup_groups(api_client, "", [signup_group, signup_group2])

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([signup_group.pk, signup_group2.pk])
