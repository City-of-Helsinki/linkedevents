from typing import Optional
from uuid import UUID

import pytest
import requests_mock
from django.db.models import QuerySet
from django.urls import reverse
from helusers.settings import api_token_auth_settings
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.factories import LanguageFactory
from helevents.models import User
from helevents.tests.conftest import get_api_token_for_user_with_scopes
from helevents.tests.factories import UserFactory
from registrations.models import SignUp, SignUpGroup
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpProtectedDataFactory,
)

# === util methods ===


def _get_signup_group_profile_data(signup_group: Optional[SignUpGroup]) -> dict:
    if not signup_group:
        return {"key": "SIGNUP_GROUP", "value": None}

    return {
        "key": "SIGNUPGROUP",
        "children": [
            {"key": "ID", "value": signup_group.id},
            {"key": "REGISTRATION_ID", "value": signup_group.registration_id},
            {"key": "EXTRA_INFO", "value": signup_group.extra_info},
            {"key": "SIGNUPS_COUNT", "value": signup_group.signups.count()},
        ],
    }


def _get_signup_profile_data(signup: SignUp) -> dict:
    return {
        "key": "SIGNUP",
        "children": [
            {"key": "FIRST_NAME", "value": signup.first_name},
            {"key": "LAST_NAME", "value": signup.last_name},
            {
                "key": "DATE_OF_BIRTH",
                "value": signup.date_of_birth.strftime("%Y-%m-%d")
                if signup.date_of_birth
                else None,
            },
            {"key": "CITY", "value": signup.city},
            {"key": "STREET_ADDRESS", "value": signup.street_address},
            {"key": "ZIPCODE", "value": signup.zipcode},
            {"key": "EMAIL", "value": signup.email},
            {"key": "PHONE_NUMBER", "value": signup.phone_number},
            {
                "key": "NATIVE_LANGUAGE",
                "value": str(signup.native_language),
            },
            {
                "key": "SERVICE_LANGUAGE",
                "value": str(signup.service_language),
            },
            {"key": "REGISTRATION_ID", "value": signup.registration_id},
            _get_signup_group_profile_data(signup.signup_group),
            {
                "key": "RESPONSIBLE_FOR_GROUP",
                "value": signup.responsible_for_group,
            },
            {"key": "EXTRA_INFO", "value": signup.extra_info},
            {
                "key": "MEMBERSHIP_NUMBER",
                "value": signup.membership_number,
            },
            {
                "key": "NOTIFICATIONS",
                "value": dict(SignUp.NOTIFICATION_TYPES)[signup.notifications],
            },
            {
                "key": "ATTENDEE_STATUS",
                "value": dict(SignUp.ATTENDEE_STATUSES)[signup.attendee_status],
            },
            {
                "key": "PRESENCE_STATUS",
                "value": dict(SignUp.PRESENCE_STATUSES)[signup.presence_status],
            },
        ],
    }


def _get_signups_profile_data(signups_qs: QuerySet[SignUp]) -> list[dict]:
    signup_datas = []

    for signup in signups_qs:
        signup_data = _get_signup_profile_data(signup)
        signup_datas.append(signup_data)

    return signup_datas


def _get_user_data(user: User) -> list[dict]:
    return [
        {"key": "ID", "value": user.id},
        {"key": "FIRST_NAME", "value": user.first_name},
        {"key": "LAST_NAME", "value": user.last_name},
        {"key": "EMAIL", "value": user.email},
        {
            "key": "SIGNUP_CREATED_BY",
            "children": _get_signups_profile_data(
                user.signup_created_by.select_related("signup_group").all()
            ),
        },
    ]


def _get_gdpr_data(api_client: APIClient, user_uuid: UUID):
    gdpr_profile_url = reverse("helsinki_gdpr:gdpr_v1", kwargs={"uuid": user_uuid})
    return api_client.get(gdpr_profile_url)


def _assert_profile_data_in_response(response, user: User):
    profile_data = {"key": "USER", "children": _get_user_data(user)}
    assert response.json() == profile_data


# === tests ===


@pytest.mark.django_db
def test_authenticated_user_can_get_own_data(api_client, settings):
    settings.GDPR_API_QUERY_SCOPE = api_token_auth_settings.API_SCOPE_PREFIX

    user = UserFactory()

    language_en = LanguageFactory(id="en", name="English")
    language_fi = LanguageFactory(id="fi", name="Suomi", service_language=True)

    registration = RegistrationFactory()

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)

    first_signup = SignUpFactory(
        registration=registration,
        signup_group=signup_group,
        responsible_for_group=True,
        first_name="Mickey",
        last_name="Mouse",
        email="test@test.com",
        city="Test City",
        street_address="Test Street 1",
        zipcode="12345",
        phone_number="+123123456789",
        native_language=language_en,
        service_language=language_fi,
        membership_number="00000",
        notifications=SignUp.NotificationType.EMAIL,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
        presence_status=SignUp.PresenceStatus.PRESENT,
        created_by=user,
    )
    SignUpProtectedDataFactory(
        registration=registration,
        signup=first_signup,
        date_of_birth="1928-05-15",
        extra_info="Test extra info #1",
    )

    second_signup = SignUpFactory(
        registration=registration,
        first_name="James",
        last_name="Bond",
        email="test007@test.com",
        city="Test City #2",
        street_address="Test Street 2",
        zipcode="12121",
        phone_number="+123000111222",
        native_language=language_en,
        service_language=language_en,
        membership_number="00001",
        notifications=SignUp.NotificationType.SMS,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        presence_status=SignUp.PresenceStatus.NOT_PRESENT,
        created_by=user,
    )
    SignUpProtectedDataFactory(
        registration=registration,
        signup=second_signup,
        date_of_birth="1920-11-11",
        extra_info="Test extra info #2",
    )

    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            user.uuid, [settings.GDPR_API_QUERY_SCOPE], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        response = _get_gdpr_data(api_client, user.uuid)
        assert response.status_code == status.HTTP_200_OK

    _assert_profile_data_in_response(response, user)


@pytest.mark.django_db
def test_authenticated_user_cannot_get_other_users_data(api_client, settings):
    settings.GDPR_API_QUERY_SCOPE = api_token_auth_settings.API_SCOPE_PREFIX

    user = UserFactory()
    other_user = UserFactory()

    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            user.uuid, [settings.GDPR_API_QUERY_SCOPE], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        response = _get_gdpr_data(api_client, other_user.uuid)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_non_authenticated_user_cannot_get_any_data(api_client, settings):
    settings.GDPR_API_QUERY_SCOPE = api_token_auth_settings.API_SCOPE_PREFIX

    user = UserFactory()

    response = _get_gdpr_data(api_client, user.uuid)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
