from datetime import timedelta

import pytest
from django.db.models import Model

from registrations.utils import code_validity_duration


@pytest.mark.django_db
def test_0055_expiration_update(migrator, registration):
    old_state = migrator.apply_tested_migration(
        ("registrations", "0054_new_general_vat_percentage")
    )

    OldRegistration: Model = old_state.apps.get_model("registrations", "Registration")  # noqa: N806
    OldSeatReservationCode: Model = old_state.apps.get_model(  # noqa: N806
        "registrations", "SeatReservationCode"
    )

    registration = OldRegistration.objects.get(pk=registration.pk)

    reservation_with_one_seat = OldSeatReservationCode.objects.create(
        registration=registration, seats=1
    )
    reservation_with_three_seats = OldSeatReservationCode.objects.create(
        registration=registration, seats=3
    )

    new_state = migrator.apply_tested_migration(
        ("registrations", "0055_seatreservationcode_expiration")
    )
    NewSeatReservationCode: Model = new_state.apps.get_model(  # noqa: N806
        "registrations", "SeatReservationCode"
    )

    reservation_with_one_seat = NewSeatReservationCode.objects.get(
        pk=reservation_with_one_seat.pk
    )
    reservation_with_three_seats = NewSeatReservationCode.objects.get(
        pk=reservation_with_three_seats.pk
    )

    assert (
        reservation_with_one_seat.expiration
        == reservation_with_one_seat.timestamp
        + timedelta(minutes=code_validity_duration(reservation_with_one_seat.seats))
    )
    assert (
        reservation_with_three_seats.expiration
        == reservation_with_three_seats.timestamp
        + timedelta(minutes=code_validity_duration(reservation_with_three_seats.seats))
    )
