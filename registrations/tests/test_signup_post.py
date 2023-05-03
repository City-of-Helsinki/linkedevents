from copy import deepcopy
from datetime import date, timedelta

import pytest
from freezegun import freeze_time
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import MandatoryFields, SeatReservationCode, SignUp
from registrations.tests.test_reserve_seats_post import reserve_seats

# === util methods ===


def create_signup(api_client, registration_pk, signup_data):
    # Reserve seats
    seat_reservation_data = {"seats": 1, "waitlist": True}
    response = reserve_seats(api_client, registration_pk, seat_reservation_data)
    assert response.status_code == status.HTTP_201_CREATED

    # Sign up
    create_url = reverse(
        "registration-signup-list",
        kwargs={"pk": registration_pk},
    )
    signup_payload = {
        "reservation_code": response.data["code"],
        "signups": [signup_data],
    }

    response = api_client.post(create_url, signup_payload, format="json")
    return response


def assert_create_signup(api_client, registration_pk, signup_data):
    response = create_signup(api_client, registration_pk, signup_data)
    assert response.status_code == status.HTTP_201_CREATED

    return response


# === tests ===


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_successful_signup(api_client, languages, registration):
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

    assert_create_signup(api_client, registration.id, sign_up_data)
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
def test_cannot_signup_if_reservation_code_is_missing(api_client, registration):
    signup_payload = {
        "signups": [],
    }

    create_url = reverse(
        "registration-signup-list",
        kwargs={"pk": registration.id},
    )
    response = api_client.post(create_url, signup_payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"] == "Reservation code is missing"


@pytest.mark.django_db
def test_cannot_signup_if_reservation_code_is_invalid(api_client, registration):
    signup_payload = {
        "reservation_code": "c5e7d3ba-e48d-447c-b24d-c779950b2acb",
        "signups": [],
    }

    create_url = reverse(
        "registration-signup-list",
        kwargs={"pk": registration.id},
    )
    response = api_client.post(create_url, signup_payload, format="json")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert (
        response.data["detail"]
        == "Reservation code c5e7d3ba-e48d-447c-b24d-c779950b2acb doesn't exist."
    )


@pytest.mark.django_db
def test_cannot_signup_if_reservation_code_is_for_different_registration(
    api_client, registration, registration2
):
    payload = {"seats": 2, "waitlist": True}
    response = reserve_seats(api_client, registration2.id, payload)
    code = response.data["code"]
    signup_payload = {
        "reservation_code": code,
        "signups": [],
    }

    create_url = reverse(
        "registration-signup-list",
        kwargs={"pk": registration.id},
    )
    response = api_client.post(create_url, signup_payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["reservation_code"]
        == f"Registration code {code} doesn't match the registration {registration.id}"
    )


@pytest.mark.django_db
def test_cannot_signup_if_number_of_signups_exceeds_number_reserved_seats(
    api_client, registration
):
    signup_url = reverse("registration-signup-list", kwargs={"pk": registration.id})

    payload = {"seats": 1, "waitlist": True}
    response = reserve_seats(api_client, registration.id, payload)
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
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["signups"]
        == "Number of signups exceeds the number of requested seats"
    )


@pytest.mark.django_db
def test_cannot_signup_if_reservation_code_is_expired(api_client, registration):
    signup_url = reverse("registration-signup-list", kwargs={"pk": registration.id})

    payload = {"seats": 1, "waitlist": True}
    response = reserve_seats(api_client, registration.id, payload)
    seat_reservation_code = SeatReservationCode.objects.get(code=response.data["code"])
    seat_reservation_code.timestamp = seat_reservation_code.timestamp - timedelta(
        days=1
    )
    seat_reservation_code.save()

    sign_up_payload = {
        "reservation_code": response.data["code"],
        "signups": [
            {
                "name": "Mickey Mouse",
                "date_of_birth": "2011-04-07",
                "email": "test3@test.com",
            },
        ],
    }
    response = api_client.post(signup_url, sign_up_payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"] == "Reservation code has expired."


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_cannot_signup_twice_with_same_phone_or_email(api_client, registration):
    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "date_of_birth": "2011-04-07",
    }

    # Create a signup
    assert_create_signup(api_client, registration.id, sign_up_data)

    # Cannot signup with the same email twice
    signup_data_same_email = deepcopy(sign_up_data)
    signup_data_same_email["phone_number"] = "0442222222"
    response = create_signup(api_client, registration.id, signup_data_same_email)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["non_field_errors"][0].code == "unique"

    # Cannot signup with the same phone twice
    signup_data_same_phone = deepcopy(sign_up_data)
    signup_data_same_phone["email"] = "another@email.com"
    response = create_signup(api_client, registration.id, signup_data_same_phone)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["non_field_errors"][0].code == "unique"


@pytest.mark.parametrize("min_age", [None, 0, 10])
@pytest.mark.parametrize("max_age", [None, 0, 100])
@pytest.mark.parametrize("date_of_birth", [None, "1980-12-30"])
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_date_of_birth_is_mandatory_if_audience_min_or_max_age_specified(
    api_client, date_of_birth, min_age, max_age, registration, user
):
    falsy_values = ("", None)

    if (
        min_age not in falsy_values or max_age not in falsy_values
    ) and not date_of_birth:
        expected_status = status.HTTP_400_BAD_REQUEST
        expected_error = "This field must be specified."
    else:
        expected_status = status.HTTP_201_CREATED
        expected_error = None

    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
    }
    if date_of_birth:
        sign_up_data["date_of_birth"] = date_of_birth

    # Update registration
    registration.maximum_attendee_capacity = 1
    registration.audience_min_age = None
    registration.audience_max_age = None

    if min_age not in falsy_values:
        registration.audience_min_age = min_age
    if max_age not in falsy_values:
        registration.audience_max_age = max_age
    registration.save()

    response = create_signup(api_client, registration.id, sign_up_data)
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
    api_client, date_of_birth, expected_error, expected_status, registration
):
    registration.audience_max_age = 40
    registration.audience_min_age = 20
    registration.maximum_attendee_capacity = 1
    registration.save()

    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
        "date_of_birth": date_of_birth,
    }

    response = create_signup(api_client, registration.id, sign_up_data)

    assert response.status_code == expected_status
    if expected_error:
        assert str(response.data["date_of_birth"][0]) == expected_error


@pytest.mark.parametrize(
    "mandatory_field_id",
    [
        MandatoryFields.CITY,
        MandatoryFields.NAME,
        MandatoryFields.PHONE_NUMBER,
        MandatoryFields.STREET_ADDRESS,
        MandatoryFields.ZIPCODE,
    ],
)
@pytest.mark.django_db
def test_signup_mandatory_fields_has_to_be_filled(
    api_client, mandatory_field_id, registration
):
    registration.mandatory_fields = [mandatory_field_id]
    registration.save()

    sign_up_data = {
        "name": "Michael Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "street_address": "Street address",
        "city": "Helsinki",
        "zipcode": "00100",
        "notifications": "sms",
    }
    sign_up_data[mandatory_field_id] = ""

    response = create_signup(api_client, registration.id, sign_up_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert str(response.data[mandatory_field_id][0]) == "This field must be specified."


@pytest.mark.django_db
def test_group_signup_successful_with_waitlist(api_client, registration):
    registration.maximum_attendee_capacity = 1
    registration.save()
    signup_url = reverse("registration-signup-list", kwargs={"pk": registration.id})

    payload = {"seats": 2, "waitlist": True}
    response = reserve_seats(api_client, registration.id, payload)
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
