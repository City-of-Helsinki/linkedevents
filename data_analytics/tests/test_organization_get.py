from datetime import timedelta

import freezegun
import pytest
import requests_mock
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime
from django_orghierarchy.models import Organization
from helusers.settings import api_token_auth_settings
from knox import crypto
from knox.settings import CONSTANTS, knox_settings
from resilient_logger.models import ResilientLogEntry
from rest_framework import status
from rest_framework.test import APIClient

from data_analytics.tests.factories import DataAnalyticsApiTokenFactory
from data_analytics.tests.utils import (
    get_detail_and_assert_object_in_response,
    get_list_and_assert_objects_in_response,
)
from events.tests.factories import OrganizationFactory
from events.tests.utils import assert_fields_exist
from helevents.tests.conftest import get_api_token_for_user_with_scopes

_LIST_URL = reverse("data_analytics:organization-list")


def get_detail_url(organization_pk: str):
    return reverse("data_analytics:organization-detail", kwargs={"pk": organization_pk})


def get_detail(api_client: APIClient, organization_pk: str):
    return api_client.get(get_detail_url(organization_pk), format="json")


def get_list(api_client: APIClient, query: str | None = None):
    url = _LIST_URL

    if query:
        url += f"?{query}"

    return api_client.get(url, format="json")


def assert_organization_fields_exist(data):
    fields = (
        "id",
        "data_source",
        "name",
        "classification",
        "parent",
        "internal_type",
        "dissolution_date",
        "created_time",
        "last_modified_time",
    )
    assert_fields_exist(data, fields)


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.parametrize("method", ["head", "post", "put", "patch", "delete"])
@pytest.mark.django_db
def test_disallowed_http_methods(user_api_client, organization, url_type, method):
    url = _LIST_URL if url_type == "list" else get_detail_url(organization.pk)

    response = getattr(user_api_client, method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_get_organization_detail(
    user_api_client, organization, organization2, organization_class
):
    organization2.parent = organization
    organization2.classification = organization_class
    organization2.save(update_fields=["parent", "classification"])

    response = get_detail_and_assert_object_in_response(
        user_api_client, get_detail, organization2.pk
    )
    assert_organization_fields_exist(response.data)


@pytest.mark.django_db
def test_get_organization_list(user_api_client, organization, organization2):
    get_list_and_assert_objects_in_response(
        user_api_client, get_list, [organization.pk, organization2.pk]
    )


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_anonymous_user_cannot_get_organizations(api_client, organization, url_type):
    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, organization.pk)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_normal_authenticated_user_cannot_get_events(
    api_client, organization, super_user, url_type
):
    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            super_user.uuid, [api_token_auth_settings.API_SCOPE_PREFIX], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        if url_type == "list":
            response = get_list(api_client)
        else:
            response = get_detail(api_client, organization.pk)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_apikey_user_cannot_get_organizations(
    api_client, organization, data_source, url_type
):
    data_source.owner = organization
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, organization.pk)

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
def test_expired_token_cannot_get_organizations(
    api_client, organization, user, url_type, expired, expected_status_code
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
        response = get_detail(api_client, organization.pk)

    assert response.status_code == expected_status_code


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_organization_id_is_audit_logged_on_get(
    user_api_client, organization, url_type
):
    if url_type == "list":
        get_list(user_api_client)
    else:
        get_detail(user_api_client, organization.pk)

    audit_log_entry = ResilientLogEntry.objects.first()
    assert audit_log_entry.context["target"]["object_ids"] == [organization.pk]


@freezegun.freeze_time("2024-05-17 12:00:00+03:00")
@pytest.mark.parametrize(
    "last_modified_dt,expected_organizations",
    [("2024-05-17", 3), ("2024-05-17T16:00:00%2b03:00", 1)],
)
@pytest.mark.django_db
def test_filter_organization_list_by_last_modified_time(
    user_api_client, last_modified_dt, expected_organizations
):
    organization = OrganizationFactory()
    organization2 = OrganizationFactory()
    organization3 = OrganizationFactory()

    Organization.objects.filter(pk=organization3.pk).update(
        last_modified_time=localtime() + timedelta(hours=5)
    )

    organizations = {
        3: [organization.pk, organization2.pk, organization3.pk],
        1: [organization3.pk],
    }

    get_list_and_assert_objects_in_response(
        user_api_client,
        get_list,
        organizations[expected_organizations],
        query=f"last_modified_gte={last_modified_dt}",
    )
