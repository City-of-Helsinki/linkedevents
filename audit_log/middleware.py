import re

from django.conf import settings

from audit_log.utils import commit_to_audit_log

_AUDIT_LOGGED_ENDPOINTS_RE = re.compile(r"^/(v1|v0.1|gdpr-api)/")


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if settings.AUDIT_LOG_ENABLED and re.match(
            _AUDIT_LOGGED_ENDPOINTS_RE, request.path
        ):
            commit_to_audit_log(request, response)

        return response
