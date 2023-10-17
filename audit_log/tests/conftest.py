import pytest

from audit_log.models import AuditLogEntry


@pytest.mark.django_db
@pytest.fixture(autouse=True)
def use_audit_log(request):
    if "no_use_audit_log" not in request.keywords:
        assert AuditLogEntry.objects.exists() is False

    yield

    if "no_use_audit_log" not in request.keywords:
        assert AuditLogEntry.objects.exists() is True


@pytest.mark.django_db
@pytest.fixture
def use_audit_log_class(request):
    assert AuditLogEntry.objects.exists() is False

    def tearDown(instance):
        assert AuditLogEntry.objects.exists() is True
        super(request.cls, instance).tearDown()

    request.cls.tearDown = tearDown
