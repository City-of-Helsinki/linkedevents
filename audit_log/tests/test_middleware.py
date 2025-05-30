from unittest.mock import Mock, patch

import pytest

from audit_log.middleware import AuditLogMiddleware

# === util methods ===


def _get_response(_request):
    return Mock(status_code=200)


# === tests ===


@pytest.mark.parametrize("audit_log_enabled", [True, False])
def test_middleware_audit_log_setting(settings, audit_log_enabled):
    settings.AUDIT_LOG_ENABLED = audit_log_enabled

    with patch("audit_log.middleware.commit_to_audit_log") as mocked:
        middleware = AuditLogMiddleware(_get_response)
        middleware(Mock(path="/v1/"))
        assert mocked.called is audit_log_enabled


@pytest.mark.parametrize("path_prefix", ["", "/linkedevents"])
@pytest.mark.parametrize(
    "path,expected_called",
    [
        ("/v1/signup/", True),
        ("/v0.1/signup/", True),
        ("/gdpr-api/v1/user/uuid/", True),
        ("/nope/v1/signup/", False),
        ("/admin/", False),
        ("/pysocial/", False),
        ("/helusers/", False),
        ("/", False),
    ],
)
@pytest.mark.django_db
def test_middleware_audit_logged_paths(settings, path_prefix, path, expected_called):
    settings.AUDIT_LOG_ENABLED = True

    with patch("audit_log.middleware.commit_to_audit_log") as mocked:
        middleware = AuditLogMiddleware(_get_response)
        middleware(Mock(path=path_prefix + path))
        assert mocked.called is expected_called
