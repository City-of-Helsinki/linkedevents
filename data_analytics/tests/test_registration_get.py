from datetime import timedelta
from typing import Optional

import freezegun
import pytest
import requests_mock
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime
from helusers.settings import api_token_auth_settings
from knox import crypto
from knox.settings import CONSTANTS, knox_settings
from rest_framework import status
from rest_framework.test import APIClient

from audit_log.models import AuditLogEntry
from data_analytics.tests.factories import DataAnalyticsAuthTokenFactory
from data_analytics.tests.utils import (
    get_detail_and_assert_object_in_response,
    get_list_and_assert_objects_in_response,
)
from events.tests.utils import assert_fields_exist
from helevents.tests.conftest import get_api_token_for_user_with_scopes
from registrations.models import Registration
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpFactory,
    SignUpGroupFactory,
)

_LIST_URL = reverse("data_analytics:registration-list")


def get_detail_url(registration_pk: int):
    return reverse("data_analytics:registration-detail", kwargs={"pk": registration_pk})


def get_detail(api_client: APIClient, registration_pk: int):
    return api_client.get(get_detail_url(registration_pk), format="json")


def get_list(api_client: APIClient, query: Optional[str] = None):
    url = _LIST_URL

    if query:
        url += f"?{query}"

    return api_client.get(url, format="json")


def assert_registration_fields_exist(data):
    fields = (
        "id",
        "event",
        "attendee_registration",
        "audience_min_age",
        "audience_max_age",
        "enrolment_start_time",
        "enrolment_end_time",
        "maximum_attendee_capacity",
        "minimum_attendee_capacity",
        "waiting_list_capacity",
        "maximum_group_size",
        "remaining_attendee_capacity",
        "remaining_waiting_list_capacity",
        "signup_groups",
        "signups",
        "created_time",
        "last_modified_time",
    )
    assert_fields_exist(data, fields)


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.parametrize("method", ["head", "post", "put", "patch", "delete"])
@pytest.mark.django_db
def test_disallowed_http_methods(user_api_client, registration, url_type, method):
    url = _LIST_URL if url_type == "list" else get_detail_url(registration.pk)

    response = getattr(user_api_client, method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_get_registration_detail(user_api_client, registration):
    SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration)

    response = get_detail_and_assert_object_in_response(
        user_api_client, get_detail, registration.pk
    )
    assert_registration_fields_exist(response.data)

    assert_fields_exist(
        response.data["signup_groups"],
        registration.signup_groups.values_list("pk", flat=True),
    )
    assert_fields_exist(
        response.data["signups"], registration.signups.values_list("pk", flat=True)
    )


@pytest.mark.django_db
def test_get_registration_list(user_api_client, registration, registration2):
    get_list_and_assert_objects_in_response(
        user_api_client, get_list, [registration.pk, registration2.pk]
    )


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_anonymous_user_cannot_get_registrations(api_client, registration, url_type):
    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, registration.pk)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_normal_authenticated_user_cannot_get_registrations(
    api_client, registration, super_user, url_type
):
    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            super_user.uuid, [api_token_auth_settings.API_SCOPE_PREFIX], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        if url_type == "list":
            response = get_list(api_client)
        else:
            response = get_detail(api_client, registration.pk)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_apikey_user_cannot_get_registrations(
    api_client, registration, data_source, url_type
):
    data_source.owner = registration.publisher
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, registration.pk)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.parametrize(
    "expired,expected_status_code",
    [
        (True, status.HTTP_401_UNAUTHORIZED),
        (False, status.HTTP_200_OK),
    ],
)
@pytest.mark.django_db
def test_expired_token_cannot_get_registrations(
    api_client, registration, user, url_type, expired, expected_status_code
):
    if expired:
        expiry = timezone.now() - timedelta(days=1)
    else:
        expiry = timezone.now() + timedelta(days=1)
    token = crypto.create_token_string()
    DataAnalyticsAuthTokenFactory(
        user=user,
        digest=crypto.hash_token(token),
        token_key=token[: CONSTANTS.TOKEN_KEY_LENGTH],
        expiry=expiry,
    )

    api_client.credentials(
        HTTP_AUTHORIZATION=f"{knox_settings.AUTH_HEADER_PREFIX} {token}"
    )

    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, registration.pk)

    assert response.status_code == expected_status_code


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_registration_id_is_audit_logged_on_get(
    user_api_client, registration, url_type
):
    if url_type == "list":
        get_list(user_api_client)
    else:
        get_detail(user_api_client, registration.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        registration.pk
    ]


@freezegun.freeze_time("2024-05-17 12:00:00+03:00")
@pytest.mark.parametrize(
    "last_modified_dt,expected_registrations",
    [("2024-05-17", 3), ("2024-05-17T16:00:00%2b03:00", 1)],
)
@pytest.mark.django_db
def test_filter_registration_list_by_last_modified_time(
    user_api_client, last_modified_dt, expected_registrations
):
    registration = RegistrationFactory()
    registration2 = RegistrationFactory()
    registration3 = RegistrationFactory()

    Registration.objects.filter(pk=registration3.pk).update(
        last_modified_time=localtime() + timedelta(hours=5)
    )

    registrations = {
        3: [registration.pk, registration2.pk, registration3.pk],
        1: [registration3.pk],
    }

    get_list_and_assert_objects_in_response(
        user_api_client,
        get_list,
        registrations[expected_registrations],
        query=f"last_modified_gte={last_modified_dt}",
    )
