from datetime import timedelta

import pytest
from django.utils.timezone import localtime
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.tests.factories import SeatReservationCodeFactory
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
def test_authenticated_admin_user_can_update_seats_reservation(
    user_api_client, event, registration
):
    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    reservation_data = {
        "seats": 2,
        "registration": registration.id,
        "code": reservation.code,
    }
    assert_update_seats_reservation(user_api_client, reservation.id, reservation_data)


@pytest.mark.django_db
def test_authenticated_regular_user_can_update_seats_reservation(
    user_api_client, event, registration, user
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    reservation_data = {
        "seats": 2,
        "registration": registration.id,
        "code": reservation.code,
    }
    assert_update_seats_reservation(user_api_client, reservation.id, reservation_data)


@pytest.mark.django_db
def test_anonymous_user_cannot_update_seats_reservation(
    api_client, event, registration
):
    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    reservation_data = {
        "seats": 2,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = update_seats_reservation(api_client, reservation.id, reservation_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_seats_amount_has_not_limit_if_maximum_attendee_capacity_is_none(
    user_api_client, event, registration
):
    registration.maximum_attendee_capacity = None
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)

    reservation_data = {
        "seats": 10000,
        "registration": registration.id,
        "code": reservation.code,
    }
    assert_update_seats_reservation(user_api_client, reservation.id, reservation_data)


@pytest.mark.django_db
def test_seats_value_is_required(user_api_client, event, registration):
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)

    reservation_data = {
        "registration": registration.id,
        "code": reservation.code,
    }
    response = update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0].code == "required"


@pytest.mark.django_db
def test_code_value_is_required(user_api_client, event, registration):
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)

    reservation_data = {
        "seats": 1,
        "registration": registration.id,
    }
    response = update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"][0].code == "required"


@pytest.mark.django_db
def test_code_value_must_match(user_api_client, event, registration):
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)

    reservation_data = {
        "seats": 1,
        "registration": registration.id,
        "code": "invalid_code",
    }
    response = update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"][0] == "The value doesn't match."


@pytest.mark.django_db
def test_cannot_update_registration(
    user_api_client, event, registration, registration2
):
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)

    reservation_data = {
        "seats": 1,
        "code": reservation.code,
        "registration": registration2.id,
    }
    response = update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.data["registration"] == registration.id


@pytest.mark.django_db
def test_cannot_update_expired_reservation(user_api_client, event, registration):
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    reservation.timestamp = localtime() - timedelta(days=1)
    reservation.save(update_fields=["timestamp"])

    reservation_data = {
        "seats": 1,
        "registration": registration.id,
        "code": reservation.code,
    }
    assert_reserve_seats(user_api_client, reservation_data)

    response = update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Cannot update expired seats reservation."


@pytest.mark.django_db
def test_cannot_update_timestamp(user_api_client, event, registration):
    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    timestamp = reservation.timestamp

    reservation_data = {
        "seats": 2,
        "registration": registration.id,
        "code": reservation.code,
        "timestamp": localtime() + timedelta(minutes=15),
    }
    assert_update_seats_reservation(user_api_client, reservation.id, reservation_data)

    reservation.refresh_from_db()
    assert reservation.seats == 2
    assert reservation.timestamp == timestamp


@pytest.mark.django_db
def test_cannot_reserve_seats_if_there_are_not_enough_seats_available(
    user_api_client, event, registration
):
    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)

    reservation_data = {
        "seats": 3,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0] == "Not enough seats available. Capacity left: 2."


@pytest.mark.django_db
def test_update_seats_reservation_in_waiting_list(
    user_api_client, event, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save(
        update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
    )

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    reservation_data = {
        "seats": 2,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = assert_update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.data["in_waitlist"] is True


@pytest.mark.django_db
def test_waiting_list_seats_amount_has_not_limit_if_waiting_list_capacity_is_none(
    user_api_client, event, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = None
    registration.save(
        update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
    )

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    reservation_data = {
        "seats": 10000,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = assert_update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.data["in_waitlist"] is True


@pytest.mark.django_db
def test_cannot_reserve_seats_waiting_list_if_there_are_not_enough_seats_available(
    user_api_client, event, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save(
        update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
    )

    reservation = SeatReservationCodeFactory(seats=1, registration=registration)
    reservation_data = {
        "seats": 3,
        "registration": registration.id,
        "code": reservation.code,
    }
    response = update_seats_reservation(
        user_api_client, reservation.id, reservation_data
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["seats"][0]
        == "Not enough capacity in the waiting list. Capacity left: 2."
    )
