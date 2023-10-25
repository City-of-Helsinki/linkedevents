from typing import Union
from unittest.mock import patch, PropertyMock

import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.factories import OrganizationFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SignUpFactory,
    SignUpGroupFactory,
)

# === util methods ===


def _get_signups_export(
    api_client: APIClient,
    registration_id: Union[str, int],
    file_format: str,
    query_string: str = None,
):
    url = reverse(
        "registration-signups-export",
        kwargs={"pk": registration_id, "file_format": file_format},
    )

    if query_string:
        url = "%s?%s" % (url, query_string)

    response = api_client.get(url)

    return response


def _assert_correct_content(response):
    assert response.headers["Content-Type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.headers["Content-Disposition"] == (
        'attachment; filename="registered_persons.xlsx"'
    )
    assert len(response.content) > 0


def _assert_get_signups_export(
    api_client: APIClient,
    registration_id: Union[str, int],
    file_format: str,
    query_string: str = None,
):
    response = _get_signups_export(
        api_client, registration_id, file_format, query_string=query_string
    )

    assert response.status_code == status.HTTP_200_OK
    _assert_correct_content(response)

    return response


def _create_default_signups_data(registration):
    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration, signup_group=signup_group)

    SignUpFactory(registration=registration)
    SignUpFactory(registration=registration)


# === tests ===


@pytest.mark.parametrize("user_role", ["admin", "regular_user"])
@pytest.mark.django_db
def test_signup_export_forbidden_for_organization_admin_and_regular_user(
    registration, api_client, user_role
):
    _create_default_signups_data(registration)

    user = UserFactory()

    if user_role == "admin":
        user.admin_organizations.add(registration.publisher)
    else:
        user.organization_memberships.add(registration.publisher)

    api_client.force_authenticate(user)

    response = _get_signups_export(api_client, registration.id, file_format="xlsx")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("user_role", ["admin", "regular_user"])
@pytest.mark.django_db
def test_signup_export_forbidden_for_admin_and_regular_user_of_another_organization(
    registration, api_client, user_role
):
    _create_default_signups_data(registration)

    organization2 = OrganizationFactory()

    user = UserFactory()

    if user_role == "admin":
        user.admin_organizations.add(organization2)
    else:
        user.organization_memberships.add(organization2)

    api_client.force_authenticate(user)

    response = _get_signups_export(api_client, registration.id, file_format="xlsx")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_export_forbidden_for_weakly_identified_registration_user(
    registration, api_client
):
    _create_default_signups_data(registration)

    user = UserFactory()
    user.organization_memberships.add(registration.publisher)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    api_client.force_authenticate(user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=None,
    ) as mocked:
        response = _get_signups_export(api_client, registration.id, file_format="xlsx")

        assert mocked.called is True

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_export_forbidden_for_user_without_organization(
    registration, api_client
):
    _create_default_signups_data(registration)

    user = UserFactory()
    api_client.force_authenticate(user)

    response = _get_signups_export(api_client, registration.id, file_format="xlsx")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_export_unauthorized_for_anonymous_user(registration, api_client):
    _create_default_signups_data(registration)

    response = _get_signups_export(api_client, registration.id, file_format="xlsx")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_signup_export_forbidden_for_apikey_without_registration_permissions(
    data_source, registration, api_client
):
    _create_default_signups_data(registration)

    api_client.credentials(apikey=data_source.api_key)

    response = _get_signups_export(api_client, registration.id, file_format="xlsx")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_export_forbidden_for_apikey_of_another_organization(
    data_source, registration, api_client
):
    _create_default_signups_data(registration)

    organization2 = OrganizationFactory()
    data_source.owner = organization2
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])

    api_client.credentials(apikey=data_source.api_key)

    response = _get_signups_export(api_client, registration.id, file_format="xlsx")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_export_forbidden_for_apikey_with_wrong_data_source(
    registration, other_data_source, api_client
):
    _create_default_signups_data(registration)

    other_data_source.owner = registration.publisher
    other_data_source.save(update_fields=["owner"])
    api_client.credentials(apikey=other_data_source.api_key)

    response = _get_signups_export(api_client, registration.id, file_format="xlsx")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_export_unauthorized_for_apikey_with_unknown_data_source(
    registration, api_client
):
    _create_default_signups_data(registration)

    api_client.credentials(apikey="unknown")

    response = _get_signups_export(api_client, registration.id, file_format="xlsx")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    "other_role",
    [
        "admin",
        "registration_admin",
        "registration_user_access",
        "regular_user",
        "none",
    ],
)
@pytest.mark.django_db
def test_signup_export_allowed_for_superuser_regardless_of_other_roles(
    registration, api_client, other_role
):
    _create_default_signups_data(registration)

    user = UserFactory(is_superuser=True)

    other_role_mapping = {
        "admin": lambda usr: usr.admin_organizations.add(registration.publisher),
        "registration_admin": lambda usr: usr.registration_admin_organizations.add(
            registration.publisher
        ),
        "registration_user_access": lambda usr: RegistrationUserAccessFactory(
            registration=registration, email=user.email
        ),
        "regular_user": lambda usr: usr.organization_memberships.add(
            registration.publisher
        ),
        "none": lambda usr: None,
    }
    other_role_mapping[other_role](user)

    api_client.force_authenticate(user)

    _assert_get_signups_export(api_client, registration.id, file_format="xlsx")


@pytest.mark.django_db
def test_signup_export_allowed_for_registration_admin(registration, api_client):
    _create_default_signups_data(registration)

    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    _assert_get_signups_export(api_client, registration.id, file_format="xlsx")


@pytest.mark.django_db
def test_signup_export_allowed_for_strongly_identified_registration_user(
    registration, api_client
):
    _create_default_signups_data(registration)

    user = UserFactory()
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value="heltunnistussuomifi",
    ) as mocked:
        _assert_get_signups_export(api_client, registration.id, file_format="xlsx")

        assert mocked.called is True


@pytest.mark.django_db
def test_signup_export_allowed_for_apikey_with_registration_permission(
    registration, api_client
):
    _create_default_signups_data(registration)

    data_source = registration.event.data_source

    data_source.owner = registration.publisher
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])

    api_client.credentials(apikey=data_source.api_key)

    _assert_get_signups_export(api_client, registration.id, file_format="xlsx")


@pytest.mark.parametrize(
    "file_format,allowed",
    [
        ("xlsx", True),
        ("docx", False),
        ("pdf", False),
        ("txt", False),
        ("completely-made-up", False),
        (123, False),
    ],
)
@pytest.mark.django_db
def test_export_file_formats(registration, api_client, file_format, allowed):
    _create_default_signups_data(registration)

    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    base_url = f"http://testserver/v1/registration/{registration.id}/signups/export"

    assert reverse(
        "registration-signups-export",
        kwargs={"pk": registration.id, "file_format": "xlsx"},
    ).startswith(base_url)

    url = f"{base_url}/{file_format}/"
    response = api_client.get(url)

    if allowed:
        assert response.status_code == status.HTTP_200_OK
        _assert_correct_content(response)
    else:
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    "ui_language,allowed",
    [
        ("fi", True),
        ("sv", True),
        ("en", True),
        ("fi-FI", False),
        ("sv-SV", False),
        ("en-GB", False),
        ("no", False),
        ("completely-made-up", False),
        ("xlsx", False),
        (123, False),
    ],
)
@pytest.mark.django_db
def test_ui_language_parameter(registration, api_client, ui_language, allowed):
    _create_default_signups_data(registration)

    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    response = _get_signups_export(
        api_client,
        registration.id,
        file_format="xlsx",
        query_string=f"ui_language={ui_language}",
    )

    if allowed:
        assert response.status_code == status.HTTP_200_OK
        _assert_correct_content(response)
    else:
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_registration_not_found(api_client):
    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    response = _get_signups_export(api_client, 999, file_format="xlsx")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_without_signups_data(registration, api_client):
    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    _assert_get_signups_export(api_client, registration.id, file_format="xlsx")
