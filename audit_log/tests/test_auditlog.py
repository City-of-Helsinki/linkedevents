import pytest
from django.conf import settings
from rest_framework.test import APIClient

from audit_log.enums import Operation
from audit_log.models import AuditLogEntry
from events.models import DataSource
from events.tests.factories import ApiKeyUserFactory, OrganizationFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory


@pytest.mark.django_db
def test_auditlog_does_not_commit_anonymous_request():
    api_client = APIClient()
    response = api_client.get(reverse("event-list"))
    assert response.status_code == 200
    assert AuditLogEntry.objects.count() == 0


@pytest.mark.django_db
def test_auditlog_commits_authenticated_request():
    user = UserFactory()
    api_client = APIClient()
    api_client.force_authenticate(user=user)
    assert AuditLogEntry.objects.count() == 0

    response = api_client.get(reverse("event-list"))

    assert response.status_code == 200
    assert AuditLogEntry.objects.count() == 1

    log_entry = AuditLogEntry.objects.first()
    assert log_entry.message["audit_event"]["actor"]["uuid"] == str(user.uuid)
    assert log_entry.message["audit_event"]["operation"] == Operation.READ.value
    assert log_entry.message["audit_event"]["target"]["path"] == "/v1/event/"


@pytest.mark.django_db
def test_auditlog_apikey_authenticated_request():
    data_source = DataSource.objects.create(
        id=settings.SYSTEM_DATA_SOURCE_ID,
        api_key="test_api_key",
        user_editable_resources=True,
        user_editable_organizations=True,
        owner=OrganizationFactory(),
    )

    api_client = APIClient()
    user = ApiKeyUserFactory(data_source=data_source)
    api_client.credentials(apikey=data_source.api_key)
    assert AuditLogEntry.objects.count() == 0

    response = api_client.get(reverse("event-list"))

    assert response.status_code == 200
    assert AuditLogEntry.objects.count() == 1

    log_entry = AuditLogEntry.objects.first()
    assert log_entry.message["audit_event"]["actor"]["uuid"] == str(user.uuid)
    assert log_entry.message["audit_event"]["operation"] == Operation.READ.value
    assert log_entry.message["audit_event"]["target"]["path"] == "/v1/event/"
