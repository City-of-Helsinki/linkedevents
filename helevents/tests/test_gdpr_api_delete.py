from unittest.mock import patch
from uuid import UUID

import pytest
import requests_mock
from django.urls import reverse
from helusers.settings import api_token_auth_settings
from rest_framework import status

from events.tests.conftest import APIClient
from helevents.models import User
from helevents.tests.conftest import get_api_token_for_user_with_scopes
from helevents.tests.factories import UserFactory
from registrations.models import (
    SignUp,
    SignUpGroup,
    SignUpGroupProtectedData,
    SignUpProtectedData,
)
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
    SignUpProtectedDataFactory,
)

# === util methods ===


def _delete_gdpr_data(api_client: APIClient, user_uuid: UUID):
    gdpr_profile_url = reverse("helsinki_gdpr:gdpr_v1", kwargs={"uuid": user_uuid})
    return api_client.delete(gdpr_profile_url)


# === tests ===


@pytest.mark.django_db
def test_authenticated_user_can_delete_own_data(api_client, settings):
    settings.GDPR_API_DELETE_SCOPE = api_token_auth_settings.API_SCOPE_PREFIX

    user = UserFactory()

    registration = RegistrationFactory()

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    first_signup = SignUpFactory(
        signup_group=signup_group, registration=registration, created_by=user
    )
    second_signup = SignUpFactory(registration=registration, created_by=user)

    SignUpGroupProtectedDataFactory(
        signup_group=signup_group, registration=registration
    )
    SignUpProtectedDataFactory(signup=first_signup, registration=registration)
    SignUpProtectedDataFactory(signup=second_signup, registration=registration)

    assert User.objects.count() == 1
    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    assert SignUpGroupProtectedData.objects.count() == 1
    assert SignUpProtectedData.objects.count() == 2

    with (
        requests_mock.Mocker() as req_mock,
        patch(
            "registrations.signals._signup_or_group_post_delete"
        ) as mocked_signup_post_delete,
    ):
        auth_header = get_api_token_for_user_with_scopes(
            user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        response = _delete_gdpr_data(api_client, user.uuid)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert mocked_signup_post_delete.called is True

    assert User.objects.count() == 0
    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0

    assert SignUpGroupProtectedData.objects.count() == 1
    assert SignUpProtectedData.objects.count() == 2


@pytest.mark.django_db
def test_authenticated_user_cannot_delete_other_users_data(api_client, settings):
    settings.GDPR_API_DELETE_SCOPE = api_token_auth_settings.API_SCOPE_PREFIX

    user = UserFactory()
    other_user = UserFactory()

    registration = RegistrationFactory()

    signup_group = SignUpGroupFactory(registration=registration, created_by=other_user)
    first_signup = SignUpFactory(
        registration=registration, signup_group=signup_group, created_by=other_user
    )
    second_signup = SignUpFactory(registration=registration, created_by=other_user)

    SignUpGroupProtectedDataFactory(
        signup_group=signup_group, registration=registration
    )
    SignUpProtectedDataFactory(signup=first_signup, registration=registration)
    SignUpProtectedDataFactory(signup=second_signup, registration=registration)

    assert User.objects.count() == 2
    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    assert SignUpGroupProtectedData.objects.count() == 1
    assert SignUpProtectedData.objects.count() == 2

    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        response = _delete_gdpr_data(api_client, other_user.uuid)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    assert User.objects.count() == 2
    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    assert SignUpGroupProtectedData.objects.count() == 1
    assert SignUpProtectedData.objects.count() == 2


@pytest.mark.django_db
def test_non_authenticated_user_cannot_delete_any_data(api_client, settings):
    settings.GDPR_API_DELETE_SCOPE = api_token_auth_settings.API_SCOPE_PREFIX

    user = UserFactory()

    registration = RegistrationFactory()

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    first_signup = SignUpFactory(
        registration=registration, signup_group=signup_group, created_by=user
    )
    second_signup = SignUpFactory(registration=registration, created_by=user)

    SignUpGroupProtectedDataFactory(
        signup_group=signup_group, registration=registration
    )
    SignUpProtectedDataFactory(signup=first_signup, registration=registration)
    SignUpProtectedDataFactory(signup=second_signup, registration=registration)

    assert User.objects.count() == 1
    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    assert SignUpGroupProtectedData.objects.count() == 1
    assert SignUpProtectedData.objects.count() == 2

    response = _delete_gdpr_data(api_client, user.uuid)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert User.objects.count() == 1
    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    assert SignUpGroupProtectedData.objects.count() == 1
    assert SignUpProtectedData.objects.count() == 2
