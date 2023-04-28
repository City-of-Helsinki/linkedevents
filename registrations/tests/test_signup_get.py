import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.utils import versioned_reverse as reverse


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
def test__api_key_with_organization_can_get_sign_up(
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
