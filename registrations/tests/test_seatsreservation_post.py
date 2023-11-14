from datetime import timedelta

import pytest
from django.utils.timezone import localtime
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory


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
def test_authenticated_admin_user_can_create_seats_reservation(
    user_api_client, registration
):
    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation_data = {"seats": 1, "registration": registration.id}
    response = assert_reserve_seats(user_api_client, reservation_data)
    assert response.data["in_waitlist"] is False


@pytest.mark.django_db
def test_authenticated_regular_user_can_create_seats_reservation(
    api_client, registration
):
    user = UserFactory()
    user.organization_memberships.add(registration.publisher)

    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    api_client.force_authenticate(user)

    reservation_data = {"seats": 1, "registration": registration.id}
    response = assert_reserve_seats(api_client, reservation_data)
    assert response.data["in_waitlist"] is False


@pytest.mark.django_db
def test_anonymous_user_cannot_create_seats_reservation(api_client, registration):
    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation_data = {"seats": 1, "registration": registration.id}
    response = reserve_seats(api_client, reservation_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_seats_amount_has_not_limit_if_maximum_attendee_capacity_is_none(
    user_api_client, registration
):
    registration.maximum_attendee_capacity = None
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation_data = {"seats": 10000, "registration": registration.id}
    response = assert_reserve_seats(user_api_client, reservation_data)
    assert response.data["in_waitlist"] is False


@pytest.mark.django_db
def test_seats_value_is_required(user_api_client, registration):
    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation_data = {"registration": registration.id}
    response = reserve_seats(user_api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0].code == "required"


@pytest.mark.django_db
def test_seats_cannot_be_greater_than_maximum_group_size(user_api_client, registration):
    registration.maximum_attendee_capacity = None
    registration.maximum_group_size = 5
    registration.save(update_fields=["maximum_attendee_capacity", "maximum_group_size"])

    reservation_data = {"registration": registration.id, "seats": 6}
    response = reserve_seats(user_api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0].code == "max_group_size"


@pytest.mark.django_db
def test_cannot_reserve_seats_if_enrolment_is_not_opened(user_api_client, registration):
    registration.enrolment_start_time = localtime() + timedelta(days=1)
    registration.enrolment_end_time = localtime() + timedelta(days=2)
    registration.save(update_fields=["enrolment_start_time", "enrolment_end_time"])

    reservation_data = {"seats": 1, "registration": registration.id}
    response = reserve_seats(user_api_client, reservation_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is not yet open."


@pytest.mark.django_db
def test_cannot_reserve_seats_if_enrolment_is_closed(user_api_client, registration):
    registration.enrolment_start_time = localtime() - timedelta(days=2)
    registration.enrolment_end_time = localtime() - timedelta(days=1)
    registration.save(update_fields=["enrolment_start_time", "enrolment_end_time"])

    reservation_data = {"seats": 1, "registration": registration.id}
    response = reserve_seats(user_api_client, reservation_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is already closed."


@pytest.mark.django_db
def test_cannot_reserve_seats_if_there_are_not_enough_seats_available(
    user_api_client, registration
):
    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation_data = {"seats": 3, "registration": registration.id}
    response = reserve_seats(user_api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0] == "Not enough seats available. Capacity left: 2."

    reservation_data["seats"] = 1
    response = assert_reserve_seats(user_api_client, reservation_data)
    assert response.data["in_waitlist"] is False

    reservation_data["seats"] = 2
    response = reserve_seats(user_api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["seats"][0] == "Not enough seats available. Capacity left: 1."


@pytest.mark.django_db
def test_reserve_seats_to_waiting_list(user_api_client, registration, signup, signup2):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save(
        update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
    )

    reservation_data = {"seats": 1, "registration": registration.id}
    response = assert_reserve_seats(user_api_client, reservation_data)
    assert response.data["in_waitlist"] is True


@pytest.mark.django_db
def test_waiting_list_seats_amount_has_not_limit_if_waiting_list_capacity_is_none(
    user_api_client, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = None
    registration.save(
        update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
    )

    reservation_data = {"seats": 10000, "registration": registration.id}
    response = assert_reserve_seats(user_api_client, reservation_data)
    assert response.data["in_waitlist"] is True


@pytest.mark.django_db
def test_cannot_reserve_seats_waiting_list_if_there_are_not_enough_seats_available(
    user_api_client, registration, signup, signup2
):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save(
        update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
    )

    reservation_data = {"seats": 3, "registration": registration.id}
    response = reserve_seats(user_api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["seats"][0]
        == "Not enough capacity in the waiting list. Capacity left: 2."
    )

    reservation_data["seats"] = 1
    response = assert_reserve_seats(user_api_client, reservation_data)
    assert response.data["in_waitlist"] is True

    reservation_data["seats"] = 2
    response = reserve_seats(user_api_client, reservation_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["seats"][0]
        == "Not enough capacity in the waiting list. Capacity left: 1."
    )


@pytest.mark.django_db
def test_seatreservation_id_is_audit_logged_on_post(registration, user_api_client):
    registration.maximum_attendee_capacity = 2
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation_data = {"seats": 1, "registration": registration.id}

    response = assert_reserve_seats(user_api_client, reservation_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]
