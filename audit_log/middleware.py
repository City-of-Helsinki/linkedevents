import re

from django.conf import settings

from audit_log.utils import commit_to_audit_log

_AUDIT_LOGGED_ENDPOINTS_RE = re.compile(
    r"^(/linkedevents)?/(v1|v0.1|gdpr-api|data-analytics)/"
)


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if self._should_commit_to_audit_log(request, response):
            commit_to_audit_log(request, response)

        return response

    @staticmethod
    def _should_commit_to_audit_log(request, response):
        return (
            settings.AUDIT_LOG_ENABLED
            and re.match(_AUDIT_LOGGED_ENDPOINTS_RE, request.path)
            and 200 <= response.status_code < 300
            and request.user.is_authenticated
        )
