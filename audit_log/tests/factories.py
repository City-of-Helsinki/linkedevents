from datetime import datetime, timezone
from uuid import uuid4

import factory
from django.conf import settings

from audit_log.enums import Operation, Role, Status
from audit_log.models import AuditLogEntry

_DEFAULT_UUID = uuid4()


def _create_default_message():
    current_time = datetime.now(tz=timezone.utc)
    iso_8601_date = f"{current_time.replace(tzinfo=None).isoformat(sep='T', timespec='milliseconds')}Z"

    return {
        "audit_event": {
            "origin": settings.AUDIT_LOG_ORIGIN,
            "status": Status.SUCCESS.value,
            "date_time_epoch": int(current_time.timestamp() * 1000),
            "date_time": iso_8601_date,
            "actor": {
                "role": Role.ADMIN.value,
                "uuid": str(_DEFAULT_UUID),
                "ip_address": "1.2.3.4",
            },
            "operation": Operation.READ.value,
            "target": "/v1/signup/",
        }
    }


class AuditLogEntryFactory(factory.django.DjangoModelFactory):
    message = factory.LazyFunction(_create_default_message)

    class Meta:
        model = AuditLogEntry
