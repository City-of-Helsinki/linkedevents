from collections import Counter

import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry

from .test_event_get import get_detail, get_list

# Module globals for py.test fixtures
version = "v0.1"


@pytest.mark.django_db
def test__get_event_list_check_fields_exist(api_client, event):
    """
    Tests that event list endpoint returns the image as null.
    """
    response = get_list(api_client, version="v0.1")
    assert not response.data["data"][0]["image"]


@pytest.mark.django_db
def test_event_id_is_audit_logged_on_get_detail_v0_1(api_client, event):
    response = get_detail(api_client, event.pk, version="v0.1")
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [event.pk]


@pytest.mark.django_db
def test_event_id_is_audit_logged_on_get_list_v0_1(api_client, event, event2):
    response = get_list(api_client, version="v0.1")
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([event.pk, event2.pk])


@pytest.mark.django_db
def test__get_event_detail_check_fields_exist(api_client, event):
    """
    Tests that event detail endpoint returns the image as null.
    """
    response = get_detail(api_client, event.pk, version="v0.1")
    assert not response.data["image"]


@pytest.mark.django_db
def test__api_get_event_list_check_fields_exist(api_get_list):
    """
    Tests that event list endpoint returns the image as null.

    TODO: Testing how tests should/could be structured
    This one sets version on module level and does not deal with API client
    """
    response = api_get_list()
    assert not response.data["data"][0]["image"]
