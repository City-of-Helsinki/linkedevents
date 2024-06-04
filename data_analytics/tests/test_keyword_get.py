from datetime import timedelta

import pytest
import requests_mock
from django.urls import reverse
from django.utils import timezone
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

_LIST_URL = reverse("data_analytics:keyword-list")


def get_detail_url(keyword_pk: str):
    return reverse("data_analytics:keyword-detail", kwargs={"pk": keyword_pk})


def get_detail(api_client: APIClient, keyword_pk: str):
    return api_client.get(get_detail_url(keyword_pk), format="json")


def get_list(api_client: APIClient):
    return api_client.get(_LIST_URL, format="json")


def assert_keyword_fields_exist(data):
    fields = (
        "id",
        "name",
        "deprecated",
        "alt_labels",
        "n_events",
        "created_time",
        "last_modified_time",
    )
    assert_fields_exist(data, fields)


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.parametrize("method", ["head", "post", "put", "patch", "delete"])
@pytest.mark.django_db
def test_disallowed_http_methods(user_api_client, keyword, url_type, method):
    url = _LIST_URL if url_type == "list" else get_detail_url(keyword.pk)

    response = getattr(user_api_client, method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_get_keyword_detail(user_api_client, keyword):
    response = get_detail_and_assert_object_in_response(
        user_api_client, get_detail, keyword.pk
    )

    assert_keyword_fields_exist(response.data)
    assert_fields_exist(
        response.data["alt_labels"], keyword.alt_labels.values_list("name", flat=True)
    )


@pytest.mark.django_db
def test_get_keyword_list(user_api_client, keyword, keyword2):
    get_list_and_assert_objects_in_response(
        user_api_client, get_list, [keyword.pk, keyword2.pk]
    )


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_anonymous_user_cannot_get_keywords(api_client, keyword, url_type):
    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, keyword.pk)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_normal_authenticated_user_cannot_get_keywords(
    api_client, keyword, super_user, url_type
):
    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            super_user.uuid, [api_token_auth_settings.API_SCOPE_PREFIX], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        if url_type == "list":
            response = get_list(api_client)
        else:
            response = get_detail(api_client, keyword.pk)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_apikey_user_cannot_get_keywords(api_client, keyword, data_source, url_type):
    data_source.owner = keyword.publisher
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, keyword.pk)

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
def test_expired_token_cannot_get_events(
    api_client, keyword, user, url_type, expired, expected_status_code
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
        response = get_detail(api_client, keyword.pk)

    assert response.status_code == expected_status_code


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_keyword_id_is_audit_logged_on_get(user_api_client, keyword, url_type):
    if url_type == "list":
        get_list(user_api_client)
    else:
        get_detail(user_api_client, keyword.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        keyword.pk
    ]
