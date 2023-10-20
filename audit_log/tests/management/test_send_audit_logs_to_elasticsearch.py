from unittest.mock import patch

import pytest
from django.core.management import call_command, CommandError
from django.test import override_settings

from audit_log.models import AuditLogEntry
from audit_log.tests.factories import AuditLogEntryFactory

_TEST_SETTINGS = {
    "ENABLE_SEND_AUDIT_LOG": True,
    "ELASTICSEARCH_HOST": "http://testserver",
    "ELASTICSEARCH_PORT": 1234,
    "ELASTICSEARCH_USERNAME": "test_uname",
    "ELASTICSEARCH_PASSWORD": "test_pw",
}


@pytest.mark.no_use_audit_log
@pytest.mark.django_db
@override_settings(**_TEST_SETTINGS)
def test_send_audit_logs_to_elasticsearch_success():
    AuditLogEntryFactory()
    AuditLogEntryFactory()

    assert AuditLogEntry.objects.filter(is_sent=False).count() == 2

    with patch("elasticsearch.Elasticsearch.index") as mocked_es_index:
        mocked_es_index.return_value = {"result": "created"}

        call_command("send_audit_logs_to_elasticsearch")

        assert mocked_es_index.called is True

    assert AuditLogEntry.objects.filter(is_sent=False).count() == 0


@pytest.mark.parametrize("manual", [True, False])
@pytest.mark.no_use_audit_log
@pytest.mark.django_db
@override_settings(**_TEST_SETTINGS)
def test_send_audit_logs_to_elasticsearch_with_manual_override_success(
    settings, manual
):
    settings.AUDIT_LOG_ENABLED = False
    settings.ENABLE_SEND_AUDIT_LOG = False

    AuditLogEntryFactory()
    AuditLogEntryFactory()

    assert AuditLogEntry.objects.filter(is_sent=False).count() == 2

    with patch("elasticsearch.Elasticsearch.index") as mocked_es_index:
        if manual:
            mocked_es_index.return_value = {"result": "created"}

        call_command("send_audit_logs_to_elasticsearch", manual=manual)

        assert mocked_es_index.called is manual

    assert AuditLogEntry.objects.filter(is_sent=False).count() == (0 if manual else 2)


@pytest.mark.parametrize(
    "setting_name,setting_value",
    [
        ("ENABLE_SEND_AUDIT_LOG", False),
        ("ELASTICSEARCH_HOST", ""),
        ("ELASTICSEARCH_PORT", 0),
        ("ELASTICSEARCH_USERNAME", ""),
        ("ELASTICSEARCH_PASSWORD", ""),
    ],
)
@pytest.mark.no_use_audit_log
@pytest.mark.django_db
@override_settings(**_TEST_SETTINGS)
def test_send_audit_logs_to_elasticsearch_improperly_configured(
    settings, setting_name, setting_value
):
    for name, value in _TEST_SETTINGS.items():
        assert getattr(settings, name) == value

    setattr(settings, setting_name, setting_value)

    AuditLogEntryFactory()
    AuditLogEntryFactory()

    assert AuditLogEntry.objects.filter(is_sent=False).count() == 2

    with patch("elasticsearch.Elasticsearch.index") as mocked_es_index:
        if settings.ENABLE_SEND_AUDIT_LOG:
            with pytest.raises(CommandError):
                call_command("send_audit_logs_to_elasticsearch")
        else:
            call_command("send_audit_logs_to_elasticsearch")

        assert mocked_es_index.called is False

    assert AuditLogEntry.objects.filter(is_sent=False).count() == 2
