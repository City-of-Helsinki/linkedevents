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
from data_analytics.tests.factories import DataAnalyticsApiTokenFactory
from data_analytics.tests.utils import (
    get_detail_and_assert_object_in_response,
    get_list_and_assert_objects_in_response,
)
from events.models import Event
from events.tests.factories import (
    EventFactory,
    KeywordFactory,
    LanguageFactory,
    OfferFactory,
)
from events.tests.utils import assert_fields_exist
from helevents.tests.conftest import get_api_token_for_user_with_scopes

_LIST_URL = reverse("data_analytics:event-list")


def get_detail_url(event_pk: str):
    return reverse("data_analytics:event-detail", kwargs={"pk": event_pk})


def get_detail(api_client: APIClient, event_pk: str):
    return api_client.get(get_detail_url(event_pk), format="json")


def get_list(api_client: APIClient, query: Optional[str] = None):
    url = _LIST_URL

    if query:
        url += f"?{query}"

    return api_client.get(url, format="json")


def assert_event_fields_exist(data):
    fields = (
        "id",
        "name",
        "publisher",
        "deleted",
        "date_published",
        "provider",
        "event_status",
        "publication_status",
        "location",
        "environment",
        "start_time",
        "end_time",
        "has_start_time",
        "has_end_time",
        "super_event",
        "super_event_type",
        "type_id",
        "local",
        "in_language",
        "replaced_by",
        "maximum_attendee_capacity",
        "minimum_attendee_capacity",
        "enrolment_start_time",
        "enrolment_end_time",
        "keywords",
        "audience",
        "audience_min_age",
        "audience_max_age",
        "offers",
        "created_time",
        "last_modified_time",
    )
    assert_fields_exist(data, fields)


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.parametrize("method", ["head", "post", "put", "patch", "delete"])
@pytest.mark.django_db
def test_disallowed_http_methods(user_api_client, event, url_type, method):
    url = _LIST_URL if url_type == "list" else get_detail_url(event.pk)

    response = getattr(user_api_client, method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_get_event_detail(user_api_client, event):
    language = LanguageFactory(pk="fi")
    event.in_language.add(language)

    keyword = KeywordFactory()
    event.keywords.add(keyword)

    audience = KeywordFactory()
    event.audience.add(audience)

    offer = OfferFactory(event=event)

    response = get_detail_and_assert_object_in_response(
        user_api_client, get_detail, event.pk
    )
    assert_event_fields_exist(response.data)

    assert_fields_exist(response.data["in_language"], (language.pk,))

    assert_fields_exist(response.data["keywords"], (keyword.pk,))
    assert_fields_exist(response.data["audience"], (audience.pk,))

    assert_fields_exist(response.data["offers"], (offer.pk,))


@pytest.mark.django_db
def test_get_event_list(user_api_client, event, event2):
    get_list_and_assert_objects_in_response(
        user_api_client, get_list, [event.pk, event2.pk]
    )


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_anonymous_user_cannot_get_events(api_client, event, url_type):
    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, event.pk)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_normal_authenticated_user_cannot_get_events(
    api_client, event, super_user, url_type
):
    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            super_user.uuid, [api_token_auth_settings.API_SCOPE_PREFIX], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        if url_type == "list":
            response = get_list(api_client)
        else:
            response = get_detail(api_client, event.pk)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_apikey_user_cannot_get_events(api_client, event, data_source, url_type):
    data_source.owner = event.publisher
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    if url_type == "list":
        response = get_list(api_client)
    else:
        response = get_detail(api_client, event.pk)

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
    api_client, event, user, url_type, expired, expected_status_code
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
        response = get_detail(api_client, event.pk)

    assert response.status_code == expected_status_code


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_event_id_is_audit_logged_on_get(user_api_client, event, url_type):
    if url_type == "list":
        get_list(user_api_client)
    else:
        get_detail(user_api_client, event.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [event.pk]


@freezegun.freeze_time("2024-05-17 12:00:00+03:00")
@pytest.mark.parametrize(
    "last_modified_dt,expected_events",
    [("2024-05-17", 3), ("2024-05-17T16:00:00%2b03:00", 1)],
)
@pytest.mark.django_db
def test_filter_event_list_by_last_modified_time(
    user_api_client, last_modified_dt, expected_events
):
    event = EventFactory()
    event2 = EventFactory()
    event3 = EventFactory()

    Event.objects.filter(pk=event3.pk).update(
        last_modified_time=localtime() + timedelta(hours=5)
    )

    events = {
        3: [event.pk, event2.pk, event3.pk],
        1: [event3.pk],
    }

    get_list_and_assert_objects_in_response(
        user_api_client,
        get_list,
        events[expected_events],
        query=f"last_modified_gte={last_modified_dt}",
    )
