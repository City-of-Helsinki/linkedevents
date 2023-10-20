from datetime import datetime, timezone
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from elasticsearch import Elasticsearch

from audit_log.enums import Operation, Role, Status
from audit_log.models import AuditLogEntry
from events.auth import ApiKeyUser

_OPERATION_MAPPING = {
    "GET": Operation.READ.value,
    "HEAD": Operation.READ.value,
    "OPTIONS": Operation.READ.value,
    "POST": Operation.CREATE.value,
    "PUT": Operation.UPDATE.value,
    "PATCH": Operation.UPDATE.value,
    "DELETE": Operation.DELETE.value,
}


def _get_response_status(response: HttpResponse) -> str:
    if not getattr(response, "status_code", None):
        return Status.FAILED.value

    if 200 <= response.status_code < 300:
        return Status.SUCCESS.value
    elif 300 <= response.status_code < 400:
        return Status.REDIRECT.value
    elif response.status_code in (401, 403):
        return Status.FORBIDDEN.value
    else:
        return Status.FAILED.value


def _get_operation_name(request: HttpRequest) -> str:
    return _OPERATION_MAPPING.get(request.method, f"Unknown: {request.method}")


def _get_remote_address(request: HttpRequest) -> str:
    if not request.headers.get("x-forwarded-for"):
        return request.META.get("REMOTE_ADDR")

    remote_addr = request.headers.get("x-forwarded-for", "").split(",")[0]

    # Remove port number from remote_addr
    if "." in remote_addr and ":" in remote_addr:
        # IPv4 with port (`x.x.x.x:x`)
        remote_addr = remote_addr.split(":")[0]
    elif "[" in remote_addr:
        # IPv6 with port (`[:::]:x`)
        remote_addr = remote_addr[1:].split("]")[0]

    return remote_addr


def _get_user_role(user: get_user_model()) -> str:
    if user is None:
        return Role.SYSTEM.value

    if isinstance(user, AnonymousUser):
        return Role.ANONYMOUS.value

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


def _get_actor_data(request: HttpRequest) -> dict[str, Optional[str]]:
    user = getattr(request, "user", None)
    uuid = getattr(user, "uuid", None)

    return {
        "role": _get_user_role(user),
        "uuid": str(uuid) if uuid else None,
        "ip_address": _get_remote_address(request),
    }


def commit_to_audit_log(request: HttpRequest, response: HttpResponse) -> None:
    current_time = datetime.now(tz=timezone.utc)
    iso_8601_date = f"{current_time.replace(tzinfo=None).isoformat(sep='T', timespec='milliseconds')}Z"

    message = {
        "audit_event": {
            "origin": settings.AUDIT_LOG_ORIGIN,
            "status": _get_response_status(response),
            "date_time_epoch": int(current_time.timestamp() * 1000),
            "date_time": iso_8601_date,
            "actor": _get_actor_data(request),
            "operation": _get_operation_name(request),
            "target": request.path,
        }
    }

    AuditLogEntry.objects.create(message=message)


def _get_entry_document_for_elasticsearch(entry: AuditLogEntry) -> dict:
    message = entry.message.copy()
    message["@timestamp"] = message["audit_event"]["date_time"]

    return message


@transaction.atomic
def send_audit_log_entries_to_elasticsearch(client: Elasticsearch) -> tuple[int, int]:
    sent_entries = 0
    total_entries = 0

    es_op_type = "create"
    es_status_created = "created"
    entry_update_fields = ["is_sent"]
    entries = (
        AuditLogEntry.objects.select_for_update()
        .filter(is_sent=False)
        .order_by("created_at")
    )

    for entry in entries:
        document = _get_entry_document_for_elasticsearch(entry)

        response = client.index(
            index=settings.ELASTICSEARCH_APP_AUDIT_LOG_INDEX,
            id=str(entry.id),
            document=document,
            op_type=es_op_type,
        )

        if response.get("result") == es_status_created:
            entry.is_sent = True
            entry.save(update_fields=entry_update_fields)
            sent_entries += 1

        total_entries += 1

    return sent_entries, total_entries
