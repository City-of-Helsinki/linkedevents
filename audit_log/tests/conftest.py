import pytest
from django.conf import settings

from audit_log.models import AuditLogEntry


@pytest.mark.django_db
@pytest.fixture(autouse=True)
def use_audit_log(request):
    audit_log_enabled = (
        settings.AUDIT_LOG_ENABLED and "no_use_audit_log" not in request.keywords
    )

    if audit_log_enabled:
        assert AuditLogEntry.objects.exists() is False

    yield

    if audit_log_enabled:
        assert AuditLogEntry.objects.exists() is True


@pytest.mark.django_db
@pytest.fixture
def use_audit_log_class(request):
    if settings.AUDIT_LOG_ENABLED:
        assert AuditLogEntry.objects.exists() is False

    def tearDown(instance):
        if settings.AUDIT_LOG_ENABLED:
            assert AuditLogEntry.objects.exists() is True
        super(request.cls, instance).tearDown()

    request.cls.tearDown = tearDown
