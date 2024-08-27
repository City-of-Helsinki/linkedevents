from collections import Counter
from datetime import timedelta

import freezegun
import pytest
from django.core.management import call_command
from django.utils.timezone import localtime

from registrations.models import SeatReservationCode
from registrations.tests.factories import (
    RegistrationFactory,
    SeatReservationCodeFactory,
)
from registrations.utils import code_validity_duration


@freezegun.freeze_time("2024-02-16 16:45:00+02:00")
@pytest.mark.django_db
def test_delete_expired_seatreservations(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        registration = RegistrationFactory(
            maximum_attendee_capacity=5, waiting_list_capacity=5
        )

    now = localtime()
    expired_timestamp = now - timedelta(minutes=code_validity_duration(1) + 1)
    expired_timestamp2 = now - timedelta(minutes=code_validity_duration(2) + 1)
    exactly_expiration_threshold = now - timedelta(minutes=code_validity_duration(1))

    with django_capture_on_commit_callbacks(execute=True):
        expired_reservation = SeatReservationCodeFactory(
            registration=registration, seats=1
        )
        SeatReservationCode.objects.filter(pk=expired_reservation.pk).update(
            timestamp=expired_timestamp
        )

        non_expired_reservation = SeatReservationCodeFactory(
            registration=registration, seats=1
        )
        non_expired_reservation2 = SeatReservationCodeFactory(
            registration=registration, seats=1
        )
        SeatReservationCode.objects.filter(pk=non_expired_reservation2.pk).update(
            timestamp=exactly_expiration_threshold
        )

        expired_reservation2 = SeatReservationCodeFactory(
            registration=registration, seats=2
        )
        SeatReservationCode.objects.filter(pk=expired_reservation2.pk).update(
            timestamp=expired_timestamp2
        )

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 3
    assert registration.remaining_waiting_list_capacity == 5

    assert SeatReservationCode.objects.count() == 4

    with django_capture_on_commit_callbacks(execute=True):
        call_command("delete_expired_seat_reservations")

    assert SeatReservationCode.objects.count() == 2
    assert Counter(SeatReservationCode.objects.values_list("pk", flat=True)) == Counter(
        [non_expired_reservation.pk, non_expired_reservation2.pk]
    )

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 3
    assert registration.remaining_waiting_list_capacity == 5
