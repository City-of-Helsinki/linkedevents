from datetime import timedelta

import pytest
from django.utils.timezone import localtime

from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp


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
    registration2.enrolment_start_time = localtime() - timedelta(days=10)
    registration2.enrolment_end_time = localtime() - timedelta(days=5)
    registration2.save()
    response = api_client.get(f"{event_url}?enrolment_open=true", format="json")
    assert len(response.data["data"]) == 1
    assert registration.event.id == response.data["data"][0]["id"]

    # if there are no seats, the respective event should not be returned
    registration2.enrolment_start_time = localtime()
    registration2.enrolment_end_time = localtime() + timedelta(days=5)
    registration2.maximum_attendee_capacity = 1
    registration2.save()
    api_client.force_authenticate(user=None)

    SignUp.objects.create(
        registration=registration2,
        name="Michael Jackson",
        email="test@test.com",
    )
    response = api_client.get(f"{event_url}?enrolment_open=true", format="json")
    assert len(response.data["data"]) == 1
    assert registration.event.id == response.data["data"][0]["id"]

    # if maximum attendee capacity is None event should be returned
    registration2.enrolment_start_time = localtime()
    registration2.enrolment_end_time = localtime() + timedelta(days=5)
    registration2.maximum_attendee_capacity = None
    registration2.save()
    api_client.force_authenticate(user=None)

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
    registration2.enrolment_start_time = localtime() - timedelta(days=10)
    registration2.enrolment_end_time = localtime() - timedelta(days=5)
    registration2.maximum_attendee_capacity = 20
    registration2.waiting_list_capacity = 10
    registration2.save()
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 1
    assert registration.event.id == response.data["data"][0]["id"]

    # no seats at event, places in waiting list
    registration2.enrolment_start_time = localtime()
    registration2.enrolment_end_time = localtime() + timedelta(days=5)
    registration2.maximum_attendee_capacity = 1
    registration2.waiting_list_capacity = 10
    registration2.save()

    SignUp.objects.create(
        registration=registration2,
        name="Michael Jackson",
        email="test@test.com",
    )
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 2

    # no seats at event, no places in waiting list
    registration2.enrolment_start_time = localtime()
    registration2.enrolment_end_time = localtime() + timedelta(days=5)
    registration2.maximum_attendee_capacity = 1
    registration2.waiting_list_capacity = 0
    registration2.save()
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 1

    # seats at event, waiting list capacity null
    registration2.enrolment_start_time = localtime()
    registration2.enrolment_end_time = localtime() + timedelta(days=5)
    registration2.maximum_attendee_capacity = 10
    registration2.waiting_list_capacity = None
    registration2.save()
    response = api_client.get(
        f"{event_url}?enrolment_open_waitlist=true", format="json"
    )
    assert len(response.data["data"]) == 2
