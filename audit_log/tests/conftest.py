from functools import wraps

import pytest
from django.conf import settings

from audit_log.models import AuditLogEntry


@pytest.mark.django_db
@pytest.fixture(autouse=True)
def test_audit_log(request):
    audit_log_enabled = (
        settings.AUDIT_LOG_ENABLED and "no_test_audit_log" not in request.keywords
    )

    if audit_log_enabled:
        assert AuditLogEntry.objects.exists() is False

    yield

    if audit_log_enabled:
        assert AuditLogEntry.objects.exists() is True


@pytest.mark.django_db
@pytest.fixture
def test_audit_log_class(request):
    if settings.AUDIT_LOG_ENABLED:

        def audit_log_test_wrapper(test_function):
            @wraps(test_function)
            def wrapper(*args, **kwargs):
                assert AuditLogEntry.objects.exists() is False

                test_function()

                assert AuditLogEntry.objects.exists() is True

            return wrapper

        setattr(
            request.cls,
            request.function.__name__,
            audit_log_test_wrapper(request.function),
        )
