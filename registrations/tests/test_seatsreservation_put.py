from datetime import timedelta

import pytest
from django.utils.timezone import localtime
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import SeatReservationCode
from registrations.tests.test_seatsreservation_post import assert_reserve_seats


def update_seats_reservation(api_client, pk, reservation_data):
    detail_url = reverse("seatreservationcode-detail", kwargs={"pk": pk})
    response = api_client.put(detail_url, reservation_data, format="json")

    return response


def assert_update_seats_reservation(api_client, pk, reservation_data):
    response = update_seats_reservation(api_client, pk, reservation_data)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["seats"] == reservation_data["seats"]

    return response


@pytest.mark.django_db
def test_update_seats_reservation(api_client, event, registration):
    registration.maximum_attendee_capacity = 2
    registration.save()

    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)
    reservation_data = {
        "seats": 2,
        "registration": registration.id,
        "code": reservation.code,
    }
    assert_update_seats_reservation(api_client, reservation.id, reservation_data)


@pytest.mark.django_db
def test_seats_amount_has_not_limit_if_maximum_attendee_capacity_is_none(
    api_client, event, registration
):
    registration.maximum_attendee_capacity = None
    registration.save()

    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)

    reservation_data = {
        "seats": 10000,
        "registration": registration.id,
        "code": reservation.code,
    }
    assert_update_seats_reservation(api_client, reservation.id, reservation_data)


@pytest.mark.django_db
def test_seats_value_is_required(api_client, event, registration):
    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)

    reservation_data = {
        "registration": registration.id,
        "code": reservation.code,
    }
    response = update_seats_reservation(api_client, reservation.id, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0].code == "required"


@pytest.mark.django_db
def test_code_value_is_required(api_client, event, registration):
    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)

    reservation_data = {
        "seats": 1,
        "registration": registration.id,
    }
    response = update_seats_reservation(api_client, reservation.id, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"][0].code == "required"


@pytest.mark.django_db
def test_code_value_must_match(api_client, event, registration):
    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)

    reservation_data = {
        "seats": 1,
        "registration": registration.id,
        "code": "invalid_code",
    }
    response = update_seats_reservation(api_client, reservation.id, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"][0] == "The value doesn't match."


@pytest.mark.django_db
def test_cannot_update_registration(api_client, event, registration, registration2):
    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)

    reservation_data = {
        "seats": 1,
        "code": reservation.code,
        "registration": registration2.id,
    }
    response = update_seats_reservation(api_client, reservation.id, reservation_data)
    assert response.data["registration"] == registration.id


@pytest.mark.django_db
def test_cannot_update_expired_reservation(api_client, event, registration):
    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)
    reservation.timestamp = localtime() - timedelta(days=1)
    reservation.save()

    reservation_data = {
        "seats": 1,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = assert_reserve_seats(api_client, reservation_data)

    response = update_seats_reservation(api_client, reservation.id, reservation_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Cannot update expired seats reservation."


@pytest.mark.django_db
def test_cannot_update_timestamp(api_client, event, registration):
    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)
    timestamp = reservation.timestamp

    reservation_data = {
        "seats": 2,
        "registration": registration.id,
        "code": reservation.code,
        "timestamp": localtime() + timedelta(minutes=15),
    }
    assert_update_seats_reservation(api_client, reservation.id, reservation_data)

    updated_reservation = SeatReservationCode.objects.get(id=reservation.id)
    assert updated_reservation.seats == 2
    assert updated_reservation.timestamp == timestamp


@pytest.mark.django_db
def test_cannot_reserve_seats_if_there_are_not_enough_seats_available(
    api_client, event, registration
):
    registration.maximum_attendee_capacity = 2
    registration.save()

    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)

    reservation_data = {
        "seats": 3,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = update_seats_reservation(api_client, reservation.id, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0] == "Not enough seats available. Capacity left: 2."


@pytest.mark.django_db
def test_update_seats_reservation_in_waiting_list(
    api_client, event, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save()

    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)
    reservation_data = {
        "seats": 2,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = assert_update_seats_reservation(
        api_client, reservation.id, reservation_data
    )
    assert response.data["in_waitlist"] == True


@pytest.mark.django_db
def test_waiting_list_seats_amount_has_not_limit_if_waiting_list_capacity_is_none(
    api_client, event, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = None
    registration.save()

    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)
    reservation_data = {
        "seats": 10000,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = assert_update_seats_reservation(
        api_client, reservation.id, reservation_data
    )
    assert response.data["in_waitlist"] == True


@pytest.mark.django_db
def test_cannot_reserve_seats_waiting_list_if_there_are_not_enough_seats_available(
    api_client, event, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save()

    reservation = SeatReservationCode.objects.create(seats=1, registration=registration)
    reservation_data = {
        "seats": 3,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = update_seats_reservation(api_client, reservation.id, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["seats"][0]
        == "Not enough capacity in the waiting list. Capacity left: 2."
    )
