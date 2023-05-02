import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp

# === util methods ===


def get_list(api_client: APIClient, registration_pk: str, query_string: str = None):
    url = reverse(
        "registration-signup-list",
        kwargs={"pk": registration_pk},
    )

    if query_string:
        url = "%s?%s" % (url, query_string)

    return api_client.get(url)


def assert_signups_in_response(signups: list, response: dict, query: str = ""):
    response_signup_ids = {signup["id"] for signup in response.data}
    expected_signup_ids = {signup.id for signup in signups}
    if query:
        assert response_signup_ids == expected_signup_ids, f"\nquery: {query}"
    else:
        assert response_signup_ids == expected_signup_ids


def get_list_and_assert_signups(
    api_client: APIClient, registration_pk: str, query: str, signups: list
):
    response = get_list(api_client, registration_pk, query_string=query)
    assert_signups_in_response(signups, response, query)


def get_detail(
    api_client: APIClient, registration_pk: str, signup_pk: str, query: str = None
):
    detail_url = reverse(
        "registration-signup-detail",
        kwargs={"pk": registration_pk, "signup_pk": signup_pk},
    )

    if query:
        detail_url = "%s?%s" % (detail_url, query)

    return api_client.get(detail_url)


def assert_get_detail(
    api_client: APIClient, registration_pk: str, signup_pk: str, query: str = None
):
    response = get_detail(api_client, registration_pk, signup_pk, query)
    assert response.status_code == status.HTTP_200_OK


# === tests ===


@pytest.mark.django_db
def test_admin_user_can_get_signup(api_client, registration, signup, user):
    api_client.force_authenticate(user)

    assert_get_detail(api_client, registration.id, signup.id)


@pytest.mark.django_db
def test_anonymous_user_can_get_signup_by_cancellation_code(
    api_client, registration, signup
):
    assert_get_detail(
        api_client,
        registration.id,
        signup.id,
        f"cancellation_code={signup.cancellation_code}",
    )


@pytest.mark.django_db
def test_anonymous_user_cannot_get_signup_with_mailformed_code(
    api_client, registration, signup
):
    response = get_detail(
        api_client, registration.id, signup.id, "cancellation_code=invalid_code"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "Malformed UUID."


@pytest.mark.django_db
def test_anonymous_user_cannot_get_signup_with_wrong_code(
    api_client, registration, signup, signup2
):
    response = get_detail(
        api_client,
        registration.id,
        signup.id,
        f"cancellation_code={signup2.cancellation_code}",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "Cancellation code did not match any signup"


@pytest.mark.django_db
def test_regular_user_cannot_get_signup(api_client, registration, signup, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = get_detail(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_from_other_organization_cannot_get_signup(
    api_client, registration, signup, user2
):
    api_client.force_authenticate(user2)

    response = get_detail(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_with_organization_can_get_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    assert_get_detail(api_client, registration.id, signup.id)


@pytest.mark.django_db
def test__api_key_with_wrong_organization_cannot_get_signup(
    api_client, data_source, organization2, registration, signup
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = get_detail(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_user_can_get_signup_list(
    api_client, registration, signup, signup2, user
):
    api_client.force_authenticate(user)

    get_list_and_assert_signups(api_client, registration.id, "", (signup, signup2))


@pytest.mark.django_db
def test_anonymous_user_cannot_get_signup_list(api_client, registration, signup):
    response = get_list(api_client, registration.id, "")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_get_signup_list(
    api_client, registration, signup, signup2, user
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = get_list(api_client, registration.id, "")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_from_other_organization_cannot_get_signup_list(
    api_client, registration, signup, signup2, user2
):
    api_client.force_authenticate(user2)

    response = get_list(api_client, registration.id, "")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_with_organization_can_get_signup_list(
    api_client, data_source, organization, registration, signup, signup2
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    get_list_and_assert_signups(api_client, registration.id, "", (signup, signup2))


@pytest.mark.django_db
def test__api_key_with_wrong_organization_cannot_get_signup_list(
    api_client, data_source, organization2, registration, signup, signup2
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = get_list(api_client, registration.id, "")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "field",
    ["name", "email", "extra_info", "membership_number", "phone_number"],
)
@pytest.mark.django_db
def test__signup_list_assert_text_filter(
    api_client, field, registration, signup, signup2, user
):
    setattr(signup, field, "field_value_1")
    signup.save()
    setattr(signup2, field, "field_value_2")
    signup2.save()

    api_client.force_authenticate(user)
    get_list_and_assert_signups(
        api_client, registration.id, f"text=field_value_1", (signup, signup2)
    )


@pytest.mark.django_db
def test__signup_list_assert_text_filter(
    api_client, registration, signup, signup2, user
):
    signup.attendee_status = SignUp.AttendeeStatus.ATTENDING
    signup.save()
    signup2.attendee_status = SignUp.AttendeeStatus.WAITING_LIST
    signup2.save()

    api_client.force_authenticate(user)

    get_list_and_assert_signups(
        api_client,
        registration.id,
        f"attendee_status={SignUp.AttendeeStatus.ATTENDING}",
        (signup,),
    )
    get_list_and_assert_signups(
        api_client,
        registration.id,
        f"attendee_status={SignUp.AttendeeStatus.WAITING_LIST}",
        (signup2,),
    )
    get_list_and_assert_signups(
        api_client,
        registration.id,
        f"attendee_status={SignUp.AttendeeStatus.ATTENDING},{SignUp.AttendeeStatus.WAITING_LIST}",
        (
            signup,
            signup2,
        ),
    )

    response = get_list(api_client, registration.id, "attendee_status=invalid-value")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["detail"]
        == "attendee_status can take following values: waitlisted, attending, not invalid-value"
    )
