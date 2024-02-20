from datetime import timedelta

from django.core.management import BaseCommand
from django.db.models import DateTimeField, ExpressionWrapper, F
from django.utils.timezone import localtime

from registrations.models import SeatReservationCode
from registrations.utils import code_validity_duration


class Command(BaseCommand):
    help = (
        "Deletes SeatReservationCode instances whose expiration time has passed at "
        "the current moment."
    )

    def handle(self, *args, **options):
        now = localtime()

        SeatReservationCode.objects.annotate(
            expires_at=ExpressionWrapper(
                F("timestamp")
                + timedelta(minutes=1) * code_validity_duration(F("seats")),
                output_field=DateTimeField(),
            )
        ).filter(expires_at__lt=now).delete()
