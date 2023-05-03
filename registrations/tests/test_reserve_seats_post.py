import uuid
from datetime import timedelta

import pytest
from dateutil.parser import parse
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse

# === util methods ===


def reserve_seats(api_client, registration_pk, seat_reservation_data):
    reservation_url = reverse(
        "registration-reserve-seats", kwargs={"pk": registration_pk}
    )
    return api_client.post(reservation_url, seat_reservation_data, format="json")


# === tests ===


@pytest.mark.django_db
def test_seat_reservation_code_request_enough_seats_no_waitlist(
    api_client, registration, settings
):
    payload = {"seats": registration.maximum_attendee_capacity - 2, "waitlist": False}
    response = reserve_seats(api_client, registration.id, payload)
    duration = settings.SEAT_RESERVATION_DURATION + payload["seats"]
    assert response.status_code == status.HTTP_201_CREATED
    assert uuid.UUID(response.data["code"])
    assert response.data["seats"] == registration.maximum_attendee_capacity - 2
    assert response.data["expiration"] == parse(response.data["timestamp"]) + timedelta(
        minutes=duration
    )


@pytest.mark.django_db
def test_seat_reservation_code_request_enough_seats_with_waitlist(
    api_client, registration
):
    payload = {"seats": registration.maximum_attendee_capacity + 2, "waitlist": True}
    response = reserve_seats(api_client, registration.id, payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert uuid.UUID(response.data["code"])
    assert response.data["seats"] == registration.maximum_attendee_capacity + 2


@pytest.mark.django_db
def test_seat_reservation_code_request_not_enough_seats_no_waitlist(
    api_client, registration
):
    payload = {"seats": registration.maximum_attendee_capacity + 2, "waitlist": False}
    response = reserve_seats(api_client, registration.id, payload)
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_seat_reservation_code_request_not_enough_seats_with_waitlist(
    api_client, registration
):
    payload = {
        "seats": registration.maximum_attendee_capacity
        + registration.waiting_list_capacity
        + 2,
        "waitlist": True,
    }
    response = reserve_seats(api_client, registration.id, payload)
    assert response.status_code == status.HTTP_409_CONFLICT
