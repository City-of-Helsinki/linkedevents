from datetime import timedelta

import pytest
from django.utils.timezone import localtime
from django.utils.translation import activate
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse


def reserve_seats(api_client, reservation_data):
    reservation_url = reverse("seatreservationcode-list")
    response = api_client.post(reservation_url, reservation_data, format="json")

    return response


def assert_reserve_seats(api_client, reservation_data):
    response = reserve_seats(api_client, reservation_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["seats"] == reservation_data["seats"]
    return response


@pytest.mark.django_db
def test_create_seats_reservation(api_client, event, registration):
    registration.maximum_attendee_capacity = 2
    registration.save()

    reservation_data = {"seats": 1, "registration": registration.id}
    response = assert_reserve_seats(api_client, reservation_data)
    assert response.data["in_waitlist"] == False


@pytest.mark.django_db
def test_seats_amount_has_not_limit_if_maximum_attendee_capacity_is_none(
    api_client, event, registration
):
    registration.maximum_attendee_capacity = None
    registration.save()

    reservation_data = {"seats": 10000, "registration": registration.id}
    response = assert_reserve_seats(api_client, reservation_data)
    assert response.data["in_waitlist"] == False


@pytest.mark.django_db
def test_seats_value_is_required(api_client, event, registration):
    registration.maximum_attendee_capacity = 2
    registration.save()

    reservation_data = {"registration": registration.id}
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0].code == "required"


@pytest.mark.django_db
def test_seats_cannot_be_greater_than_maximum_group_size(
    api_client, event, registration
):
    registration.maximum_attendee_capacity = None
    registration.maximum_group_size = 5
    registration.save()

    reservation_data = {"registration": registration.id, "seats": 6}
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0].code == "max_group_size"


@pytest.mark.django_db
def test_cannot_reserve_seats_if_enrolment_is_not_opened(
    api_client, event, registration
):
    registration.enrolment_start_time = localtime() + timedelta(days=1)
    registration.enrolment_end_time = localtime() + timedelta(days=2)
    registration.save()

    reservation_data = {"seats": 1, "registration": registration.id}
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is not yet open."


@pytest.mark.django_db
def test_cannot_reserve_seats_if_enrolment_is_closed(api_client, event, registration):
    registration.enrolment_start_time = localtime() - timedelta(days=2)
    registration.enrolment_end_time = localtime() - timedelta(days=1)
    registration.save()

    reservation_data = {"seats": 1, "registration": registration.id}
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is already closed."


@pytest.mark.django_db
def test_cannot_reserve_seats_if_there_are_not_enough_seats_available(
    api_client, event, registration
):
    activate("en")

    registration.maximum_attendee_capacity = 2
    registration.save()

    reservation_data = {"seats": 3, "registration": registration.id}
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0] == "Not enough seats available. Capacity left: 2."

    reservation_data["seats"] = 1
    response = assert_reserve_seats(api_client, reservation_data)
    assert response.data["in_waitlist"] == False

    reservation_data["seats"] = 2
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0] == "Not enough seats available. Capacity left: 1."


@pytest.mark.django_db
def test_reserve_seats_to_waiting_list(
    api_client, event, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save()

    reservation_data = {"seats": 1, "registration": registration.id}
    response = assert_reserve_seats(api_client, reservation_data)
    assert response.data["in_waitlist"] == True


@pytest.mark.django_db
def test_waiting_list_seats_amount_has_not_limit_if_waiting_list_capacity_is_none(
    api_client, event, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = None
    registration.save()

    reservation_data = {"seats": 10000, "registration": registration.id}
    response = assert_reserve_seats(api_client, reservation_data)
    assert response.data["in_waitlist"] == True


@pytest.mark.django_db
def test_cannot_reserve_seats_waiting_list_if_there_are_not_enough_seats_available(
    api_client, event, registration, signup, signup2
):
    activate("en")

    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save()

    reservation_data = {"seats": 3, "registration": registration.id}
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["seats"][0]
        == "Not enough capacity in the waiting list. Capacity left: 2."
    )

    reservation_data["seats"] = 1
    response = assert_reserve_seats(api_client, reservation_data)
    assert response.data["in_waitlist"] == True

    reservation_data["seats"] = 2
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["seats"][0]
        == "Not enough capacity in the waiting list. Capacity left: 1."
    )
