from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import AnonymousUser
from elasticsearch import Elasticsearch, TransportError
from freezegun import freeze_time

from audit_log.enums import Operation, Role, Status
from audit_log.models import AuditLogEntry
from audit_log.tests.factories import AuditLogEntryFactory
from audit_log.utils import (
    _get_remote_address,
    commit_to_audit_log,
    send_audit_log_entries_to_elasticsearch,
)
from events.tests.factories import ApiKeyUserFactory, OrganizationFactory
from helevents.tests.factories import UserFactory


def _assert_basic_log_entry_data(log_entry):
    current_time = datetime.now(tz=timezone.utc)
    iso_8601_date = f"{current_time.replace(tzinfo=None).isoformat(sep='T', timespec='milliseconds')}Z"

    assert log_entry.message["audit_event"]["origin"] == "linkedevents"
    assert log_entry.message["audit_event"]["date_time_epoch"] == int(
        current_time.timestamp() * 1000
    )
    assert log_entry.message["audit_event"]["date_time"] == iso_8601_date


@freeze_time("2023-10-17 13:30:00+02:00")
@pytest.mark.no_use_audit_log
@pytest.mark.parametrize(
    "status_code,audit_status",
    [
        (200, Status.SUCCESS.value),
        (201, Status.SUCCESS.value),
        (204, Status.SUCCESS.value),
        (299, Status.SUCCESS.value),
        (301, Status.REDIRECT.value),
        (307, Status.REDIRECT.value),
        (308, Status.REDIRECT.value),
        (399, Status.REDIRECT.value),
        (400, Status.FAILED.value),
        (401, Status.FORBIDDEN.value),
        (403, Status.FORBIDDEN.value),
        (405, Status.FAILED.value),
        (409, Status.FAILED.value),
        (499, Status.FAILED.value),
        (500, Status.FAILED.value),
        (502, Status.FAILED.value),
        (599, Status.FAILED.value),
        (None, Status.FAILED.value),
    ],
)
@pytest.mark.django_db
def test_commit_to_audit_log_response_status(status_code, audit_status):
    user = UserFactory()

    req_mock = Mock(
        method="GET",
        user=user,
        path="/v1/endpoint",
        headers={"x-forwarded-for": "1.2.3.4:80"},
    )
    res_mock = Mock(status_code=status_code)

    assert AuditLogEntry.objects.count() == 0

    commit_to_audit_log(req_mock, res_mock)

    assert AuditLogEntry.objects.count() == 1
    log_entry = AuditLogEntry.objects.first()
    assert log_entry.message["audit_event"]["status"] == audit_status
    _assert_basic_log_entry_data(log_entry)


@freeze_time("2023-10-17 13:30:00+02:00")
@pytest.mark.no_use_audit_log
@pytest.mark.parametrize(
    "http_method,audit_operation",
    [
        ("GET", Operation.READ.value),
        ("HEAD", Operation.READ.value),
        ("OPTIONS", Operation.READ.value),
        ("POST", Operation.CREATE.value),
        ("PUT", Operation.UPDATE.value),
        ("PATCH", Operation.UPDATE.value),
        ("DELETE", Operation.DELETE.value),
    ],
)
@pytest.mark.django_db
def test_commit_to_audit_log_crud_operations(http_method, audit_operation):
    user = UserFactory()

    req_mock = Mock(
        method=http_method,
        user=user,
        path="/v1/endpoint",
        headers={"x-forwarded-for": "1.2.3.4:80"},
    )
    res_mock = Mock(status_code=200)

    assert AuditLogEntry.objects.count() == 0

    commit_to_audit_log(req_mock, res_mock)

    assert AuditLogEntry.objects.count() == 1
    log_entry = AuditLogEntry.objects.first()
    assert log_entry.message["audit_event"]["operation"] == audit_operation
    assert log_entry.message["audit_event"]["target"] == "/v1/endpoint"
    _assert_basic_log_entry_data(log_entry)


@freeze_time("2023-10-17 13:30:00+02:00")
@pytest.mark.no_use_audit_log
@pytest.mark.parametrize(
    "user_role,audit_role",
    [
        ("admin", Role.ADMIN.value),
        ("registration_admin", Role.ADMIN.value),
        ("regular_user", Role.USER.value),
        ("anonymous", Role.ANONYMOUS.value),
        ("apikey_user", Role.ADMIN.value),
        ("superuser", Role.ADMIN.value),
        ("system", Role.SYSTEM.value),
    ],
)
@pytest.mark.django_db
def test_commit_to_audit_log_actor_data(user_role, audit_role):
    organization = OrganizationFactory()

    if user_role == "apikey_user":
        user = ApiKeyUserFactory(data_source__owner=organization)
    elif user_role == "anonymous":
        user = AnonymousUser()
    elif user_role == "system":
        user = None
    else:
        user = UserFactory(is_superuser=user_role == "superuser")

    org_role_mapping = {
        "admin": lambda usr: usr.admin_organizations.add(organization),
        "registration_admin": lambda usr: usr.registration_admin_organizations.add(
            organization
        ),
        "regular_user": lambda usr: usr.organization_memberships.add(organization),
    }
    org_role = org_role_mapping.get(user_role)
    if callable(org_role):
        org_role(user)

    req_mock = Mock(
        method="GET",
        user=user,
        path="/v1/endpoint",
        headers={"x-forwarded-for": "1.2.3.4:80"},
    )
    res_mock = Mock(status_code=200)

    assert AuditLogEntry.objects.count() == 0

    commit_to_audit_log(req_mock, res_mock)

    assert AuditLogEntry.objects.count() == 1
    log_entry = AuditLogEntry.objects.first()
    assert log_entry.message["audit_event"]["actor"]["role"] == audit_role
    assert log_entry.message["audit_event"]["actor"]["ip_address"] == "1.2.3.4"
    if hasattr(user, "uuid"):
        assert log_entry.message["audit_event"]["actor"]["uuid"] == str(user.uuid)
    _assert_basic_log_entry_data(log_entry)


@pytest.mark.no_use_audit_log
@pytest.mark.parametrize(
    "remote_address,expected,x_forwarded_for",
    [
        ("1.2.3.4:443", "1.2.3.4", True),
        ("1.2.3.4", "1.2.3.4", True),
        (
            "[2001:0db8:85a3:0000:0000:8a2e:0370:7334]:443",
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            True,
        ),
        (
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            True,
        ),
        ("1.2.3.4", "1.2.3.4", False),
        (
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            False,
        ),
    ],
)
def test_get_remote_address(remote_address, expected, x_forwarded_for):
    req_mock = Mock(
        headers={"x-forwarded-for": remote_address} if x_forwarded_for else {},
        META={"REMOTE_ADDR": remote_address} if not x_forwarded_for else {},
    )
    assert _get_remote_address(req_mock) == expected


@pytest.mark.parametrize(
    "has_unsent_entries,has_sent_entries",
    [
        (True, False),
        (True, True),
        (False, False),
    ],
)
@pytest.mark.no_use_audit_log
@pytest.mark.django_db
def test_send_audit_log_entries_to_elasticsearch(has_unsent_entries, has_sent_entries):
    if has_unsent_entries:
        AuditLogEntryFactory()
        AuditLogEntryFactory()

    if has_sent_entries:
        AuditLogEntryFactory(is_sent=True)
        AuditLogEntryFactory(is_sent=True)

    assert AuditLogEntry.objects.filter(is_sent=False).count() == (
        2 if has_unsent_entries else 0
    )
    assert AuditLogEntry.objects.filter(is_sent=True).count() == (
        2 if has_sent_entries else 0
    )

    es_client = Elasticsearch(
        [
            {
                "host": "http://testserver",
                "port": 1234,
            }
        ],
    )

    with patch("elasticsearch.Elasticsearch.index") as mocked_es_index:
        mocked_es_index.return_value = {"result": "created"}

        sent_entries, total_entries = send_audit_log_entries_to_elasticsearch(es_client)

        assert mocked_es_index.called is has_unsent_entries

    assert sent_entries == (2 if has_unsent_entries else 0)
    assert total_entries == (2 if has_unsent_entries else 0)

    assert AuditLogEntry.objects.filter(is_sent=False).count() == 0


@pytest.mark.parametrize(
    "es_return_value",
    [
        {"result": "something-else-than-created"},
        TransportError("ElasticSearch Transport Error"),
    ],
)
@pytest.mark.no_use_audit_log
@pytest.mark.django_db
def test_send_audit_log_entries_to_elasticsearch_failure(es_return_value):
    AuditLogEntryFactory()
    AuditLogEntryFactory()

    assert AuditLogEntry.objects.filter(is_sent=False).count() == 2

    es_client = Elasticsearch(
        [
            {
                "host": "http://testserver",
                "port": 1234,
            }
        ],
    )

    def raise_exception(*args, **kwargs):
        raise es_return_value

    with patch("elasticsearch.Elasticsearch.index") as mocked_es_index:
        if isinstance(es_return_value, Exception):
            mocked_es_index.side_effect = raise_exception

            with pytest.raises(es_return_value.__class__):
                send_audit_log_entries_to_elasticsearch(es_client)
        else:
            mocked_es_index.return_value = es_return_value

            sent_entries, total_entries = send_audit_log_entries_to_elasticsearch(
                es_client
            )

            assert sent_entries == 0
            assert total_entries == 2

        assert mocked_es_index.called is True

    assert AuditLogEntry.objects.filter(is_sent=False).count() == 2
