from datetime import timedelta

import freezegun
import pytest
import requests_mock
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime
from helusers.settings import api_token_auth_settings
from knox import crypto
from knox.settings import CONSTANTS, knox_settings
from munigeo.models import AdministrativeDivision
from rest_framework import status
from rest_framework.test import APIClient

from audit_log.models import AuditLogEntry
from data_analytics.tests.factories import DataAnalyticsApiTokenFactory
from data_analytics.tests.utils import (
    get_detail_and_assert_object_in_response,
    get_list_and_assert_objects_in_response,
)
from events.tests.utils import assert_fields_exist
from helevents.tests.conftest import get_api_token_for_user_with_scopes

_LIST_URL = reverse("data_analytics:administrativedivision-list")


def get_detail_url(division_pk: int):
    return reverse(
        "data_analytics:administrativedivision-detail", kwargs={"pk": division_pk}
    )


def get_detail(api_client: APIClient, division_pk: int):
    return api_client.get(get_detail_url(division_pk), format="json")


def get_list(api_client: APIClient, query: str | None = None):
    url = _LIST_URL

    if query:
        url += f"?{query}"

    return api_client.get(url, format="json")


def assert_division_fields_exist(data):
    fields = (
        "id",
        "modified_at",
        "type",
        "ocd_id",
        "municipality",
        "name",
    )
    assert_fields_exist(data, fields)


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.parametrize("method", ["head", "post", "put", "patch", "delete"])
@pytest.mark.django_db
def test_disallowed_http_methods(
    user_api_client, administrative_division, url_type, method
):
    url = (
        _LIST_URL if url_type == "list" else get_detail_url(administrative_division.pk)
    )

    response = getattr(user_api_client, method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_get_division_detail(user_api_client, administrative_division):
    response = get_detail_and_assert_object_in_response(
        user_api_client, get_detail, administrative_division.pk
    )

    assert_division_fields_exist(response.data)
    assert_fields_exist(response.data["name"], ("en",))


@pytest.mark.django_db
def test_get_division_list(
    user_api_client, administrative_division, administrative_division2
):
    get_list_and_assert_objects_in_response(
        user_api_client,
        get_list,
        [administrative_division.pk, administrative_division2.pk],
    )


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_anonymous_user_cannot_get_divisions(
    api_client, administrative_division, url_type
):
    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, administrative_division.pk)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_normal_authenticated_user_cannot_get_divisions(
    api_client, administrative_division, super_user, url_type
):
    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            super_user.uuid, [api_token_auth_settings.API_SCOPE_PREFIX], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        if url_type == "list":
            response = get_list(api_client)
        else:
            response = get_detail(api_client, administrative_division.pk)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_apikey_user_cannot_get_divisions(
    api_client, administrative_division, organization, data_source, url_type
):
    data_source.owner = organization
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, administrative_division.pk)

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
def test_expired_token_cannot_get_divisions(
    api_client, administrative_division, user, url_type, expired, expected_status_code
):
    if expired:
        expiry = timezone.now() - timedelta(days=1)
    else:
        expiry = timezone.now() + timedelta(days=1)
    token = crypto.create_token_string()
    DataAnalyticsApiTokenFactory(
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
        response = get_detail(api_client, administrative_division.pk)

    assert response.status_code == expected_status_code


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_division_id_is_audit_logged_on_get(
    user_api_client, administrative_division, url_type
):
    if url_type == "list":
        get_list(user_api_client)
    else:
        get_detail(user_api_client, administrative_division.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        administrative_division.pk
    ]


@freezegun.freeze_time("2024-05-17 12:00:00+03:00")
@pytest.mark.parametrize(
    "last_modified_dt,expected_divisions",
    [("2024-05-17", 3), ("2024-05-17T16:00:00%2b03:00", 1)],
)
@pytest.mark.django_db
def test_filter_divison_list_by_last_modified_time(
    user_api_client,
    administrative_division_type,
    municipality,
    last_modified_dt,
    expected_divisions,
):
    administrative_division = AdministrativeDivision.objects.create(
        type=administrative_division_type,
        ocd_id="ocd-division/test:1",
        municipality=municipality,
    )
    administrative_division2 = AdministrativeDivision.objects.create(
        type=administrative_division_type,
        ocd_id="ocd-division/test:2",
        municipality=municipality,
    )
    administrative_division3 = AdministrativeDivision.objects.create(
        type=administrative_division_type,
        ocd_id="ocd-division/test:3",
        municipality=municipality,
    )

    AdministrativeDivision.objects.filter(pk=administrative_division3.pk).update(
        modified_at=localtime() + timedelta(hours=5)
    )

    administrative_divisions = {
        3: [
            administrative_division.pk,
            administrative_division2.pk,
            administrative_division3.pk,
        ],
        1: [administrative_division3.pk],
    }

    get_list_and_assert_objects_in_response(
        user_api_client,
        get_list,
        administrative_divisions[expected_divisions],
        query=f"last_modified_gte={last_modified_dt}",
    )
