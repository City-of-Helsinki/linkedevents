from typing import Optional

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from data_analytics.tests.utils import (
    get_detail_and_assert_object_in_response,
    get_list_and_assert_objects_in_response,
)
from events.tests.factories import DataSourceFactory
from events.tests.utils import assert_fields_exist

_LIST_URL = reverse("data_analytics:datasource-list")


def get_detail_url(data_source_pk: str):
    return reverse("data_analytics:datasource-detail", kwargs={"pk": data_source_pk})


def get_detail(api_client: APIClient, data_source_pk: str):
    return api_client.get(get_detail_url(data_source_pk), format="json")


def get_list(api_client: APIClient, query: Optional[str] = None):
    url = _LIST_URL

    if query:
        url += f"?{query}"

    return api_client.get(url, format="json")


def assert_data_source_fields_exist(data):
    fields = (
        "id",
        "name",
        "has_api_key",
        "owner",
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
def test_get_data_source_detail(user_api_client, data_source):
    response = get_detail_and_assert_object_in_response(
        user_api_client, get_detail, data_source.pk
    )

    assert_data_source_fields_exist(response.data)


@pytest.mark.django_db
def test_get_data_source_list(user_api_client, data_source):
    data_source2 = DataSourceFactory()

    get_list_and_assert_objects_in_response(
        user_api_client, get_list, [data_source.pk, data_source2.pk]
    )
