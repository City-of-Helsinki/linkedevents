import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp

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


# === tests ===


@pytest.mark.django_db
def test_admin_user_can_get_signup(api_client, registration, signup, user):
    api_client.force_authenticate(user)

    assert_get_detail(api_client, signup.id)


@pytest.mark.django_db
def test_regular_user_cannot_get_signup(api_client, registration, signup, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_from_other_organization_cannot_get_signup(
    api_client, registration, signup, user2
):
    api_client.force_authenticate(user2)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_with_organization_can_get_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    assert_get_detail(api_client, signup.id)


@pytest.mark.django_db
def test__api_key_with_wrong_organization_cannot_get_signup(
    api_client, data_source, organization2, registration, signup
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_get_signup(
    api_client, organization, other_data_source, registration, signup
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = get_detail(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_user_can_get_signup_list(
    api_client, registration, signup, signup2, user
):
    api_client.force_authenticate(user)

    get_list_and_assert_signups(
        api_client, f"registration={registration.id}", (signup, signup2)
    )


@pytest.mark.django_db
def test_anonymous_user_cannot_get_signup_list(api_client, registration, signup):
    response = get_list(api_client, "")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_get_signup_list(
    api_client, registration, signup, signup2, user
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__get_all_signups_to_which_user_has_admin_role(
    api_client, registration, signup, signup2, user
):
    api_client.force_authenticate(user)

    get_list_and_assert_signups(api_client, "", (signup, signup2))

    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    get_list_and_assert_signups(api_client, "", [])


@pytest.mark.django_db
def test__user_from_other_organization_cannot_get_signup_list(
    api_client, registration, signup, signup2, user2
):
    api_client.force_authenticate(user2)

    response = get_list(api_client, f"registration={registration.id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__cannot_get_signups_of_nonexistent_registration(
    api_client, registration, signup, signup2, user2
):
    api_client.force_authenticate(user2)

    response = get_list(api_client, "registration=not-exist")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "Registration with id not-exist doesn't exist."


@pytest.mark.django_db
def test__api_key_with_organization_can_get_signup_list(
    api_client, data_source, organization, registration, signup, signup2
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    get_list_and_assert_signups(
        api_client, f"registration={registration.id}", (signup, signup2)
    )


@pytest.mark.django_db
def test__api_key_with_wrong_organization_cannot_get_signup_list(
    api_client, data_source, organization2, registration, signup, signup2
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = get_list(api_client, f"registration={registration.id}")
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
        api_client, f"registration={registration.id}&text=field_value_1", (signup,)
    )


@pytest.mark.django_db
def test__signup_list_assert_status_filter(
    api_client, registration, signup, signup2, user
):
    signup.attendee_status = SignUp.AttendeeStatus.ATTENDING
    signup.save()
    signup2.attendee_status = SignUp.AttendeeStatus.WAITING_LIST
    signup2.save()

    api_client.force_authenticate(user)

    get_list_and_assert_signups(
        api_client,
        f"registration={registration.id}&attendee_status={SignUp.AttendeeStatus.ATTENDING}",
        (signup,),
    )
    get_list_and_assert_signups(
        api_client,
        f"registration={registration.id}&attendee_status={SignUp.AttendeeStatus.WAITING_LIST}",
        (signup2,),
    )
    get_list_and_assert_signups(
        api_client,
        f"registration={registration.id}"
        f"&attendee_status={SignUp.AttendeeStatus.ATTENDING},{SignUp.AttendeeStatus.WAITING_LIST}",
        (
            signup,
            signup2,
        ),
    )

    response = get_list(
        api_client, f"registration={registration.id}&attendee_status=invalid-value"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["detail"]
        == "attendee_status can take following values: waitlisted, attending, not invalid-value"
    )


@pytest.mark.django_db
def test_filter_signups(
    api_client, registration, registration2, user, user2, event, event2
):
    api_client.force_authenticate(user=None)
    signup = SignUp.objects.create(
        registration=registration, name="Michael Jackson", email="test@test.com"
    )
    signup2 = SignUp.objects.create(
        registration=registration, name="Michael Jackson2", email="test2@test.com"
    )
    signup3 = SignUp.objects.create(
        registration=registration, name="Michael Jackson3", email="test3@test.com"
    )
    signup4 = SignUp.objects.create(
        registration=registration, name="Michael Jackson4", email="test4@test.com"
    )
    signup5 = SignUp.objects.create(
        registration=registration2,
        name="Joe Biden",
        email="test@test.com",
        extra_info="cdef",
    )
    signup6 = SignUp.objects.create(
        registration=registration2,
        name="Hillary Clinton",
        email="test2@test.com",
        extra_info="abcd",
    )
    signup7 = SignUp.objects.create(
        registration=registration2,
        name="Donald Duck",
        email="test3@test.com",
        membership_number="1234",
    )
    signup8 = SignUp.objects.create(
        registration=registration2,
        name="Mickey Mouse",
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

    #  search signups by name
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=mickey", [signup8]
    )

    #  search signups by membership number
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=34", [signup7, signup8]
    )
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=3456", [signup8]
    )

    #  search signups by extra_info
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=cd", [signup5, signup6]
    )
    get_list_and_assert_signups(
        api_client, f"registration={registration2.id}&text=abcd", [signup6]
    )
