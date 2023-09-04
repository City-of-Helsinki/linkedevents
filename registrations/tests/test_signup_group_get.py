import pytest
from rest_framework import status

from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from registrations.tests.factories import SignUpFactory, SignUpGroupFactory

# === util methods ===


def get_detail(api_client, signup_pk, query=None):
    detail_url = reverse(
        "signupgroup-detail",
        kwargs={"pk": signup_pk},
    )

    if query:
        detail_url = "%s?%s" % (detail_url, query)

    return api_client.get(detail_url)


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
    )
    assert_fields_exist(data, fields)


# === tests ===


@pytest.mark.django_db
def test_admin_user_can_get_signup_group_with_signups(user_api_client, organization):
    signup_group = SignUpGroupFactory(registration__event__publisher=organization)
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)

    response = assert_get_detail(user_api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)


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


@pytest.mark.django_db
def test_user_from_other_organization_cannot_get_signup_group(
    api_client, user2, organization
):
    signup_group = SignUpGroupFactory(registration__event__publisher=organization)

    api_client.force_authenticate(user2)

    response = get_detail(api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_with_organization_can_get_signup(
    api_client, data_source, organization
):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=data_source,
    )
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)
    SignUpFactory(registration=signup_group.registration, signup_group=signup_group)

    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = assert_get_detail(api_client, signup_group.id)
    assert len(response.json()["signups"]) == 2
    assert_signup_group_fields_exist(response.data)


@pytest.mark.django_db
def test_api_key_with_wrong_organization_cannot_get_signup(
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
def test_api_key_from_wrong_data_source_cannot_get_signup(
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
