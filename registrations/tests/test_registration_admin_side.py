import uuid
from copy import deepcopy
from datetime import date, datetime, timedelta

import pytest
from dateutil.parser import parse
from django.core import mail
from freezegun import freeze_time
from rest_framework import status

from events.models import Event
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import MandatoryField, SignUp


def sign_up(api_client, registration_id, sign_up_data):
    api_client.force_authenticate(user=None)

    # Reserve seats
    reservation_url = reverse(
        "registration-reserve-seats", kwargs={"pk": registration_id}
    )
    seat_reservation_data = {"seats": 1, "waitlist": True}
    response = api_client.post(reservation_url, seat_reservation_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    # Sign up
    sign_up_payload = {
        "reservation_code": response.data["code"],
        "signups": [sign_up_data],
    }
    signup_url = reverse("registration-signup", kwargs={"pk": registration_id})
    response = api_client.post(signup_url, sign_up_payload, format="json")

    return response


@pytest.mark.django_db
def test_successful_sign_up(api_client, languages, registration):
    """User reserves seats and then signs up."""
    sign_up_data = {
        "name": "Michael Jackson",
        "date_of_birth": "2011-04-07",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
        "service_language": "fi",
        "native_language": "fi",
        "street_address": "my street",
        "zipcode": "myzip1",
    }

    response = sign_up(api_client, registration.id, sign_up_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert SignUp.objects.count() == 1

    signup = SignUp.objects.first()
    assert signup.attendee_status == SignUp.AttendeeStatus.ATTENDING
    assert signup.name == sign_up_data["name"]
    assert signup.date_of_birth == date(2011, 4, 7)
    assert signup.email == sign_up_data["email"]
    assert signup.phone_number == sign_up_data["phone_number"]
    assert signup.notifications == SignUp.NotificationType.SMS
    assert signup.native_language.pk == "fi"
    assert signup.service_language.pk == "fi"
    assert signup.street_address == sign_up_data["street_address"]
    assert signup.zipcode == sign_up_data["zipcode"]


@pytest.mark.django_db
def test_cannot_sign_up_twice_with_same_phone_or_email(api_client, registration):
    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "date_of_birth": "2011-04-07",
    }

    response = sign_up(api_client, registration.id, sign_up_data)
    assert response.status_code == status.HTTP_201_CREATED

    # cannot signup with the same email twice
    sign_up_data_same_email = deepcopy(sign_up_data)
    sign_up_data_same_email["phone_number"] = "0442222222"
    response = sign_up(api_client, registration.id, sign_up_data_same_email)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["non_field_errors"][0].code == "unique"

    # cannot signup with the same phone twice
    sign_up_data_same_phone = deepcopy(sign_up_data)
    sign_up_data_same_phone["email"] = "another@email.com"
    response = sign_up(api_client, registration.id, sign_up_data_same_phone)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["non_field_errors"][0].code == "unique"


@pytest.mark.django_db
def test_current_attendee_and_waitlist_count(api_client, user, event):
    registration_url = reverse("registration-list")
    registration_data = {
        "event": event.id,
        "maximum_attendee_capacity": 1,
        "waiting_list_capacity": 1,
    }
    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
    }
    sign_up_data2 = {
        "name": "Michael Jackson 2",
        "email": "test2@test.com",
        "phone_number": "20441111111",
        "notifications": "sms",
    }

    # Create registration
    api_client.force_authenticate(user)
    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    api_client.force_authenticate(user=None)

    registration_detail_url = reverse(
        "registration-detail", kwargs={"pk": registration_id}
    )

    response = api_client.get(registration_detail_url, format="json")
    assert response.data["current_attendee_count"] == 0
    assert response.data["current_waiting_list_count"] == 0

    response = sign_up(api_client, registration_id, sign_up_data)
    assert response.status_code == status.HTTP_201_CREATED
    response = api_client.get(registration_detail_url, format="json")
    assert response.data["current_attendee_count"] == 1
    assert response.data["current_waiting_list_count"] == 0

    response = sign_up(api_client, registration_id, sign_up_data2)
    assert response.status_code == status.HTTP_201_CREATED
    response = api_client.get(registration_detail_url, format="json")
    assert response.data["current_attendee_count"] == 1
    assert response.data["current_waiting_list_count"] == 1


@pytest.mark.parametrize("min_age", [None, 10])
@pytest.mark.parametrize("max_age", [None, 100])
@pytest.mark.parametrize("date_of_birth", [None, "1980-12-30"])
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_signup_age_is_mandatory_if_audience_min_or_max_age_specified(
    api_client, user, event, date_of_birth, min_age, max_age
):
    if (min_age or max_age) and not date_of_birth:
        expected_status = status.HTTP_400_BAD_REQUEST
        expected_error = "Date of birth must be specified."
    else:
        expected_status = status.HTTP_201_CREATED
        expected_error = None

    registration_url = reverse("registration-list")
    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
    }
    if date_of_birth:
        sign_up_data["date_of_birth"] = date_of_birth

    # Create registration
    api_client.force_authenticate(user)
    registration_data = {"event": event.id, "maximum_attendee_capacity": 1}
    if min_age:
        registration_data["audience_min_age"] = min_age
    if max_age:
        registration_data["audience_max_age"] = max_age
    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    response = sign_up(api_client, registration_id, sign_up_data)

    assert response.status_code == expected_status

    if expected_error:
        assert str(response.data["date_of_birth"][0]) == expected_error


@pytest.mark.parametrize(
    "date_of_birth,expected_status,expected_error",
    [
        ("2011-04-07", status.HTTP_400_BAD_REQUEST, "The participant is too young."),
        ("1879-03-14", status.HTTP_400_BAD_REQUEST, "The participant is too old."),
        ("2000-02-29", status.HTTP_201_CREATED, None),
    ],
)
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_signup_age_has_to_match_the_audience_min_max_age(
    api_client, user, event, date_of_birth, expected_status, expected_error
):
    registration_url = reverse("registration-list")
    registration_data = {
        "event": event.id,
        "audience_max_age": 40,
        "audience_min_age": 20,
        "maximum_attendee_capacity": 1,
    }
    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
        "date_of_birth": date_of_birth,
    }

    api_client.force_authenticate(user)
    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    response = sign_up(api_client, registration_id, sign_up_data)

    assert response.status_code == expected_status

    if expected_error:
        assert str(response.data["date_of_birth"][0]) == expected_error


@pytest.mark.parametrize(
    "mandatory_field_id,field_id",
    [
        (
            MandatoryField.DefaultMandatoryField.ADDRESS,
            "street_address",
        ),
        (MandatoryField.DefaultMandatoryField.CITY, "city"),
        (
            MandatoryField.DefaultMandatoryField.CITY,
            "zipcode",
        ),
        (MandatoryField.DefaultMandatoryField.NAME, "name"),
        (
            MandatoryField.DefaultMandatoryField.PHONE_NUMBER,
            "phone_number",
        ),
    ],
)
@pytest.mark.django_db
def test_signup_mandatory_fields_has_to_be_filled(
    api_client, event, field_id, mandatory_field_id, user
):
    registration_url = reverse("registration-list")
    registration_data = {
        "event": event.id,
        "mandatory_fields": [mandatory_field_id],
    }

    api_client.force_authenticate(user)
    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "street_address": "Street address",
        "city": "Helsinki",
        "zipcode": "00100",
        "notifications": "sms",
    }
    sign_up_data[field_id] = ""

    response = sign_up(api_client, registration_id, sign_up_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert str(response.data[field_id][0]) == "This field must be specified."


@pytest.mark.skip(reason="Currently there's no way to cancel a signup.")
@pytest.mark.django_db
def test_signup_deletion(api_client, user, event):
    registration_url = reverse("registration-list")
    signup_url = reverse("signup-list")

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}

    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "registration": registration_id,
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
        "date_of_birth": "2011-04-07",
    }

    response = api_client.post(signup_url, sign_up_payload, format="json")
    delete_payload = {"cancellation_code": response.data["cancellation_code"]}

    response = api_client.delete(signup_url, delete_payload, format="json")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Currently there's no way to cancel a signup.")
@pytest.mark.django_db
def test_signup_deletion_missing_signup(api_client, user, event):
    registration_url = reverse("registration-list")

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    signup_url = reverse("signup-list")

    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "registration": registration_id,
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
        "date_of_birth": "2011-04-07",
    }

    response = api_client.post(signup_url, sign_up_payload, format="json")
    delete_payload = {"cancellation_code": response.data["cancellation_code"]}

    response = api_client.delete(signup_url, delete_payload, format="json")
    response = api_client.delete(signup_url, delete_payload, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.skip(reason="Currently there's no way to cancel a signup.")
@pytest.mark.django_db
def test_signup_deletion_wrong_code(api_client, user, event):
    registration_url = reverse("registration-list")
    signup_url = reverse("signup-list")

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}

    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "registration": registration_id,
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
        "date_of_birth": "2011-04-07",
    }

    response = api_client.post(signup_url, sign_up_payload, format="json")
    delete_payload = {"cancellation_code": "not a code"}

    response = api_client.delete(signup_url, delete_payload, format="json")
    assert str(response.data["detail"]) == "Malformed UUID."
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.skip(reason="Currently there's no way to cancel a signup.")
@pytest.mark.django_db
def test_signup_deletion_leads_to_changing_status_of_first_waitlisted_user(
    api_client, user, event
):
    registration_url = reverse("registration-list")

    api_client.force_authenticate(user)
    registration_data = {"event": event.id, "maximum_attendee_capacity": 1}

    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "registration": registration_id,
        "name": "Michael Jackson1",
        "email": "test@test.com",
    }
    signup_url = reverse("signup-list")

    response = api_client.post(signup_url, sign_up_payload, format="json")
    delete_payload = {"cancellation_code": response.data["cancellation_code"]}

    sign_up_payload2 = {
        "registration": registration_id,
        "name": "Michael Jackson2",
        "email": "test1@test.com",
    }
    api_client.post(signup_url, sign_up_payload2, format="json")

    sign_up_payload3 = {
        "registration": registration_id,
        "name": "Michael Jackson3",
        "email": "test2@test.com",
    }
    api_client.post(signup_url, sign_up_payload3, format="json")

    assert (
        SignUp.objects.get(email="test2@test.com").attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )
    assert (
        SignUp.objects.get(email="test1@test.com").attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )
    assert (
        SignUp.objects.get(email="test@test.com").attendee_status
        == SignUp.AttendeeStatus.ATTENDING
    )

    response = api_client.delete(signup_url, delete_payload, format="json")
    assert (
        SignUp.objects.get(email="test1@test.com").attendee_status
        == SignUp.AttendeeStatus.ATTENDING
    )
    assert (
        SignUp.objects.get(email="test2@test.com").attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )


@pytest.mark.django_db
def test_email_sent_on_successful_signup(api_client, registration):
    sign_up_data = {
        "name": "Michael Jackson",
        "date_of_birth": "2011-04-07",
        "email": "test@test.com",
    }

    response = sign_up(api_client, registration.id, sign_up_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert sign_up_data["name"] in response.data["attending"]["people"][0]["name"]
    #  assert that the email was sent
    assert len(mail.outbox) == 1


@pytest.mark.skip(reason="Currently there's no way to cancel a signup.")
@pytest.mark.django_db
def test_get_signup_info_with_cancel_code_no_auth(api_client, user, event):
    registration_url = reverse("registration-list")
    signup_url = reverse("signup-list")

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}

    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "registration": registration_id,
        "name": "Michael Jackson",
        "email": "test@test.com",
    }
    response = api_client.post(signup_url, sign_up_payload, format="json")

    response = api_client.get(
        f'{signup_url}?cancellation_code={response.data["cancellation_code"]}'
    )
    assert response.data["name"] == "Michael Jackson"


@pytest.mark.skip(
    reason="No way to filter signups currently. SignUpViewSet doesn't implement any endpoints."
)
@pytest.mark.django_db
def test_filter_signups(api_client, user, user2, event, event2):
    registration_url = reverse("registration-list")

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    response = api_client.post(registration_url, registration_data, format="json")
    registration_id = response.data["id"]

    api_client.force_authenticate(user2)
    registration_data = {"event": event2.id}
    response = api_client.post(registration_url, registration_data, format="json")
    registration_id2 = response.data["id"]

    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "registration": registration_id,
        "name": "Michael Jackson",
        "email": "test@test.com",
    }
    sign_up_payload1 = {
        "registration": registration_id,
        "name": "Michael Jackson1",
        "email": "test1@test.com",
    }
    sign_up_payload2 = {
        "registration": registration_id,
        "name": "Michael Jackson2",
        "email": "test2@test.com",
    }
    sign_up_payload3 = {
        "registration": registration_id,
        "name": "Michael Jackson3",
        "email": "test3@test.com",
    }
    sign_up_payload4 = {
        "registration": registration_id2,
        "name": "Joe Biden",
        "email": "test@test.com",
        "extra_info": "cdef",
    }
    sign_up_payload5 = {
        "registration": registration_id2,
        "name": "Hillary Clinton",
        "email": "test1@test.com",
        "extra_info": "abcd",
    }
    sign_up_payload6 = {
        "registration": registration_id2,
        "name": "Donald Duck",
        "email": "test2@test.com",
        "membership_number": "1234",
    }
    sign_up_payload7 = {
        "registration": registration_id2,
        "name": "Mickey Mouse",
        "email": "test3@test.com",
        "membership_number": "3456",
    }
    signup_url = reverse("signup-list")
    response = api_client.post(signup_url, sign_up_payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    api_client.post(signup_url, sign_up_payload1, format="json")
    api_client.post(signup_url, sign_up_payload2, format="json")
    api_client.post(signup_url, sign_up_payload3, format="json")
    api_client.post(signup_url, sign_up_payload4, format="json")
    api_client.post(signup_url, sign_up_payload5, format="json")
    api_client.post(signup_url, sign_up_payload6, format="json")
    api_client.post(signup_url, sign_up_payload7, format="json")

    search_url = f"{signup_url}?registrations={registration_id},{registration_id+10}"
    # one has to be logged in to browse signups
    response = api_client.get(search_url)
    assert response.status_code == 403

    api_client.force_authenticate(user)
    response = api_client.get(search_url)
    assert len(response.data) == 4

    #  registration id from an event that is not managed by the user results in zero signups
    api_client.force_authenticate(user2)
    response = api_client.get(search_url)
    assert len(response.data) == 0

    #  when no registration id is provided, giving signups from all the events that are managed by the user
    search_url = signup_url
    response = api_client.get(search_url)
    assert len(response.data) == 4

    #  search signups by name
    search_url = f"{signup_url}?text=mickey"
    response = api_client.get(search_url)
    assert len(response.data) == 1

    #  search signups by membership number
    search_url = f"{signup_url}?text=34"
    response = api_client.get(search_url)
    assert len(response.data) == 2
    search_url = f"{signup_url}?text=3456"
    response = api_client.get(search_url)
    assert len(response.data) == 1

    #  search signups by extra_info
    search_url = f"{signup_url}?text=cd"
    response = api_client.get(search_url)
    assert len(response.data) == 2
    search_url = f"{signup_url}?text=abcd"
    response = api_client.get(search_url)
    assert len(response.data) == 1

    #  search signups by membership number
    search_url = f"{signup_url}?events={event2.id}"
    response = api_client.get(search_url)
    assert len(response.data) == 4


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

    response = sign_up(api_client, registration2.id, sign_up_payload)
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

    response = sign_up(api_client, registration2.id, sign_up_payload)
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
    response = sign_up(api_client, registration2.id, sign_up_payload)
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
def test_seat_reservation_code_request_enough_seats_no_waitlist(
    api_client, event, registration, settings
):
    reservation_url = reverse(
        "registration-reserve-seats", kwargs={"pk": registration.id}
    )
    payload = {"seats": registration.maximum_attendee_capacity - 2, "waitlist": False}
    response = api_client.post(reservation_url, payload, format="json")
    duration = settings.SEAT_RESERVATION_DURATION + payload["seats"]
    assert response.status_code == status.HTTP_201_CREATED
    assert uuid.UUID(response.data["code"])
    assert response.data["seats"] == registration.maximum_attendee_capacity - 2
    assert response.data["expiration"] == parse(response.data["timestamp"]) + timedelta(
        minutes=duration
    )


@pytest.mark.django_db
def test_seat_reservation_code_request_enough_seats_with_waitlist(
    api_client, event, registration
):
    reservation_url = reverse(
        "registration-reserve-seats", kwargs={"pk": registration.id}
    )
    payload = {"seats": registration.maximum_attendee_capacity + 2, "waitlist": True}
    response = api_client.post(reservation_url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert uuid.UUID(response.data["code"])
    assert response.data["seats"] == registration.maximum_attendee_capacity + 2


@pytest.mark.django_db
def test_seat_reservation_code_request_not_enough_seats_no_waitlist(
    api_client, event, registration
):
    reservation_url = reverse(
        "registration-reserve-seats", kwargs={"pk": registration.id}
    )
    payload = {"seats": registration.maximum_attendee_capacity + 2, "waitlist": False}
    response = api_client.post(reservation_url, payload, format="json")
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_seat_reservation_code_request_not_enough_seats_with_waitlist(
    api_client, event, registration
):
    reservation_url = reverse(
        "registration-reserve-seats", kwargs={"pk": registration.id}
    )
    payload = {
        "seats": registration.maximum_attendee_capacity
        + registration.waiting_list_capacity
        + 2,
        "waitlist": True,
    }
    response = api_client.post(reservation_url, payload, format="json")
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_group_signup_successful_with_waitlist(api_client, registration):
    reservation_url = reverse(
        "registration-reserve-seats", kwargs={"pk": registration.id}
    )
    signup_url = reverse("registration-signup", kwargs={"pk": registration.id})
    registration.maximum_attendee_capacity = 1
    registration.save()
    payload = {"seats": 2, "waitlist": True}
    response = api_client.post(reservation_url, payload, format="json")
    sign_up_payload = {
        "reservation_code": response.data["code"],
        "signups": [
            {
                "name": "Mickey Mouse",
                "date_of_birth": "2011-04-07",
                "email": "test3@test.com",
            },
            {
                "name": "Minney Mouse",
                "date_of_birth": "2011-04-07",
                "email": "test2@test.com",
            },
        ],
    }

    response = api_client.post(signup_url, sign_up_payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert registration.signups.count() == 2


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
