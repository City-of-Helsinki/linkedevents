import logging

from resilient_logger.sources import ResilientLogSource

from audit_log.enums import Operation, Role, Status
from events.auth import ApiKeyUser
from registrations.auth import WebStoreWebhookUser

_OPERATION_MAPPING = {
    "GET": Operation.READ.value,
    "HEAD": Operation.READ.value,
    "OPTIONS": Operation.READ.value,
    "POST": Operation.CREATE.value,
    "PUT": Operation.UPDATE.value,
    "PATCH": Operation.UPDATE.value,
    "DELETE": Operation.DELETE.value,
}


def _get_response_status(response):
    if 200 <= response.status_code < 300:
        return Status.SUCCESS.value
    else:
        return f"Unknown: {response.status_code}"


def _get_operation_name(request):
    return _OPERATION_MAPPING.get(request.method, f"Unknown: {request.method}")


def _get_remote_address(request):
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",")[0] or None

    if not client_ip:
        client_ip = request.META.get("REMOTE_ADDR")

    if client_ip:
        # Strip port from ip address if present
        if "[" in client_ip:
            # Bracketed IPv6 like [2001:db8::1]:1234
            client_ip = client_ip.lstrip("[").split("]")[0]
        elif "." in client_ip and client_ip.count(":") == 1:
            # IPv4 with port
            client_ip = client_ip.split(":")[0]
    return client_ip


def _get_user_role(user):
    if user is None:
        return Role.SYSTEM.value

    if not user.is_authenticated:
        return Role.ANONYMOUS.value

    if isinstance(user, WebStoreWebhookUser):
        return Role.EXTERNAL.value

    if (
        user.is_superuser
        or user.admin_organizations.exists()
        or user.registration_admin_organizations.exists()
        or isinstance(user, ApiKeyUser)
        and user.apikey_registration_admin_organizations.exists()
    ):
        return Role.ADMIN.value

    if user.is_external:
        return Role.EXTERNAL.value

    return Role.USER.value


def _get_actor_data(request):
    user = getattr(request, "user", None)
    uuid = getattr(user, "uuid", None)

    return {
        "role": _get_user_role(user),
        "uuid": str(uuid) if uuid else None,
        "ip_address": _get_remote_address(request),
    }


def _get_target(request):
    audit_logged_object_ids = getattr(request, "_audit_logged_object_ids", set())

    target = {"path": request.path, "object_ids": list(audit_logged_object_ids)}

    if hasattr(request, "_audit_logged_object_ids"):
        delattr(request, "_audit_logged_object_ids")

    return target


def commit_to_audit_log(request, response):
    status = _get_response_status(response)

    ResilientLogSource.create_structured(
        level=logging.NOTSET,
        message=status,
        actor=_get_actor_data(request),
        operation=_get_operation_name(request),
        target=_get_target(request),
        extra={"status": status},
    )
