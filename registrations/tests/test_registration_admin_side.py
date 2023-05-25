from datetime import datetime, timedelta

import pytest
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp
from registrations.tests.test_seatsreservation_post import assert_reserve_seats
from registrations.tests.test_signup_post import create_signup


@pytest.mark.django_db
def test_event_with_open_registrations_and_places_at_the_event(
    api_client, registration, registration2, user, user2
):
    """Show the events that have:
    - registration open AND places available at the event
    """
    event_url = reverse("event-list")

    response = api_client.get(f"{event_url}?enrolment_open=true", format="json")
    assert len(response.data["data"]) == 2

    # if registration is expired the respective event should not be returned
    registration2.enrolment_start_time = datetime.now() - timedelta(days=10)
    registration2.enrolment_end_time = datetime.now() - timedelta(days=5)
    registration2.save()
    response = api_client.get(f"{event_url}?enrolment_open=true", format="json")
    assert len(response.data["data"]) == 1
    assert registration.event.id == response.data["data"][0]["id"]

    # if there are no seats, the respective event should not be returned
    registration2.enrolment_start_time = datetime.now()
    registration2.enrolment_end_time = datetime.now() + timedelta(days=5)
    registration2.maximum_attendee_capacity = 1
    registration2.save()
    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "date_of_birth": (datetime.now() - timedelta(days=3650)).strftime("%Y-%m-%d"),
    }

    response = create_signup(api_client, registration2.id, sign_up_payload)
    response = api_client.get(f"{event_url}?enrolment_open=true", format="json")
    assert len(response.data["data"]) == 1
    assert registration.event.id == response.data["data"][0]["id"]

    # if maximum attendee capacity is None event should be returned
    registration2.enrolment_start_time = datetime.now()
    registration2.enrolment_end_time = datetime.now() + timedelta(days=5)
    registration2.maximum_attendee_capacity = None
    registration2.save()
    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "date_of_birth": (datetime.now() - timedelta(days=3650)).strftime("%Y-%m-%d"),
    }

    response = create_signup(api_client, registration2.id, sign_up_payload)
    response = api_client.get(f"{event_url}?enrolment_open=true", format="json")
    assert len(response.data["data"]) == 2


@pytest.mark.django_db
def test_event_with_open_registrations_and_places_at_the_event_or_waiting_list(
    api_client, registration, registration2, registration3, user, user2
):
    """Return the events that have:
    - registration open AND places available at the event OR in the waiting list
                   enrolment open |  places available | waitlist places | return
    registration        yes       |        yes        |      yes        |   yes
    registration        yes       |        no         |      yes        |   yes
    registration        yes       |        no         |      no         |   no
    registration        yes       |        no         |      None       |   yes
    registration        no        |        yes        |      yes        |   no
    """

    event_url = reverse("event-list")

    # seats at the event available
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 2

    # if registration is expired the respective event should not be returned
    registration2.enrolment_start_time = datetime.now() - timedelta(days=10)
    registration2.enrolment_end_time = datetime.now() - timedelta(days=5)
    registration2.maximum_attendee_capacity = 20
    registration2.waiting_list_capacity = 10
    registration2.save()
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 1
    assert registration.event.id == response.data["data"][0]["id"]

    # no seats at event, places in waiting list
    registration2.enrolment_start_time = datetime.now()
    registration2.enrolment_end_time = datetime.now() + timedelta(days=5)
    registration2.maximum_attendee_capacity = 1
    registration2.waiting_list_capacity = 10
    registration2.save()
    sign_up_payload = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "date_of_birth": (datetime.now() - timedelta(days=3650)).strftime("%Y-%m-%d"),
    }
    response = create_signup(api_client, registration2.id, sign_up_payload)
    assert response.status_code == status.HTTP_201_CREATED
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 2

    # no seats at event, no places in waiting list
    registration2.enrolment_start_time = datetime.now()
    registration2.enrolment_end_time = datetime.now() + timedelta(days=5)
    registration2.maximum_attendee_capacity = 1
    registration2.waiting_list_capacity = 0
    registration2.save()
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 1

    # seats at event, waiting list capacity null
    registration2.enrolment_start_time = datetime.now()
    registration2.enrolment_end_time = datetime.now() + timedelta(days=5)
    registration2.maximum_attendee_capacity = 10
    registration2.waiting_list_capacity = None
    registration2.save()
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 2


@pytest.mark.django_db
def test_seat_reservation_without_code():
    pass


@pytest.mark.django_db
def test_seat_reservation_with_code_too_many_signups():
    """more sign ups in the request than allocated to specific code"""
    pass


@pytest.mark.django_db
def test_seat_reservation_with_code_success_event_seats_only():
    pass


@pytest.mark.django_db
def test_seat_reservation_with_code_success_event_seats_and_waitlist():
    pass


@pytest.mark.django_db
def test_seat_reservation_with_code_success_waitlist_only():
    pass


@pytest.mark.django_db
def test_group_signup_successful_with_waitlist(api_client, registration):
    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.audience_min_age = None
    registration.audience_max_age = None
    registration.save()

    reservation_data = {"seats": 2, "registration": registration.id}
    reservation_response = assert_reserve_seats(api_client, reservation_data)

    sign_up_payload = {
        "reservation_code": reservation_response.data["code"],
        "signups": [
            {
                "name": "User 1",
                "email": "test1@test.com",
            },
            {
                "name": "User 2",
                "email": "test2@test.com",
            },
        ],
    }
    signup_url = reverse("registration-signup", kwargs={"pk": registration.id})
    response = api_client.post(signup_url, sign_up_payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert registration.signups.count() == 2

    reservation_response = assert_reserve_seats(api_client, reservation_data)
    sign_up_payload = {
        "reservation_code": reservation_response.data["code"],
        "signups": [
            {
                "name": "User 3",
                "email": "test3@test.com",
            },
            {
                "name": "User 4",
                "email": "test4@test.com",
            },
        ],
    }
    response = api_client.post(signup_url, sign_up_payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert registration.signups.count() == 4
    assert (
        registration.signups.filter(
            attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()
        == 2
    )
    assert (
        registration.signups.filter(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST
        ).count()
        == 2
    )


def test_seat_reservation_without_code():
    pass


@pytest.mark.django_db
def test_seat_reservation_with_code_too_many_signups():
    """more sign ups in the request than allocated to specific code"""
    pass


@pytest.mark.django_db
def test_seat_reservation_with_code_success_event_seats_only():
    pass


@pytest.mark.django_db
def test_seat_reservation_with_code_success_event_seats_and_waitlist():
    pass


@pytest.mark.django_db
def test_seat_reservation_with_code_success_waitlist_only():
    pass
