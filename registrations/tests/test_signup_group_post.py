from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from django.core import mail
from django.utils import translation
from django.utils.timezone import localtime
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event
from events.tests.factories import LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import (
    MandatoryFields,
    SeatReservationCode,
    SignUp,
    SignUpGroup,
    SignUpGroupProtectedData,
)
from registrations.tests.factories import (
    RegistrationFactory,
    SeatReservationCodeFactory,
)
from registrations.tests.test_signup_post import assert_attending_and_waitlisted_signups

test_email1 = "test@test.com"
test_email2 = "mickey@test.com"
default_signups_data = [
    {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": "2011-04-07",
        "street_address": "my street",
        "zipcode": "myzip1",
        "attendee_status": SignUp.AttendeeStatus.WAITING_LIST,
        "user_content": False,
    },
    {
        "first_name": "Mickey",
        "last_name": "Mouse",
        "date_of_birth": "1928-05-15",
        "street_address": "my street",
        "zipcode": "myzip1",
        "attendee_status": SignUp.AttendeeStatus.ATTENDING,
        "user_content": True,
    },
]
default_signup_group_data = {
    "extra_info": "Extra info for group",
    "signups": default_signups_data,
    "contact_person": {
        "email": test_email2,
        "phone_number": "0441111111",
        "notifications": "sms",
        "service_language": "en",
        "native_language": "en",
    },
}

# === util methods ===


def create_signup_group(api_client, signup_group_data):
    create_url = reverse("signupgroup-list")
    response = api_client.post(create_url, signup_group_data, format="json")

    return response


def assert_create_signup_group(api_client, signup_group_data):
    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_201_CREATED

    return response


def assert_contact_person_data(contact_person, contact_person_data):
    assert contact_person.phone_number == contact_person_data["phone_number"]
    assert contact_person.notifications == contact_person_data["notifications"]
    assert contact_person.native_language.pk == contact_person_data["native_language"]
    assert contact_person.service_language.pk == contact_person_data["service_language"]


def assert_signup_data(signup, signup_data, user):
    assert signup.attendee_status == signup_data["attendee_status"]
    assert signup.first_name == signup_data["first_name"]
    assert signup.last_name == signup_data["last_name"]
    assert (
        signup.date_of_birth
        == datetime.strptime(signup_data["date_of_birth"], "%Y-%m-%d").date()
    )
    assert signup.street_address == signup_data["street_address"]
    assert signup.zipcode == signup_data["zipcode"]
    assert signup.created_by_id == user.id
    assert signup.last_modified_by_id == user.id
    assert signup.created_time is not None
    assert signup.last_modified_time is not None
    assert signup.user_consent is signup_data.get("user_consent", False)


def assert_signup_group_data(signup_group, signup_group_data, reservation):
    assert signup_group.registration_id == reservation.registration_id

    assert SignUpGroupProtectedData.objects.count() == 1
    if signup_group_data["extra_info"] is None:
        assert signup_group.extra_info is None
    else:
        assert signup_group.extra_info == signup_group_data["extra_info"]


def assert_default_signup_group_created(reservation, signup_group_data, user):
    assert SignUpGroup.objects.count() == 1
    signup_group = SignUpGroup.objects.first()
    assert_signup_group_data(signup_group, signup_group_data, reservation)

    assert_contact_person_data(
        signup_group.contact_person, signup_group_data["contact_person"]
    )

    assert SignUp.objects.count() == 2
    assert (
        SignUp.objects.filter(
            registration_id=reservation.registration_id, signup_group_id=signup_group.id
        ).count()
        == 2
    )

    signup0 = SignUp.objects.filter(first_name="Michael").first()
    assert_signup_data(signup0, signup_group_data["signups"][0], user)

    signup1 = SignUp.objects.filter(first_name="Mickey").first()
    assert_signup_data(signup1, signup_group_data["signups"][1], user)

    assert SeatReservationCode.objects.count() == 0


# === tests ===


@pytest.mark.django_db
def test_registration_admin_can_create_signup_group(api_client, organization):
    user = UserFactory()
    user.registration_admin_organizations.add(organization)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert_create_signup_group(api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


@pytest.mark.parametrize(
    "maximum_attendee_capacity,waiting_list_capacity,expected_signups_count,"
    "expected_attending,expected_waitlisted,expected_status_code",
    [
        (0, 0, 0, 0, 0, status.HTTP_403_FORBIDDEN),
        (1, 1, 2, 1, 1, status.HTTP_201_CREATED),
        (1, 0, 1, 1, 0, status.HTTP_201_CREATED),
        (0, 1, 1, 0, 1, status.HTTP_201_CREATED),
        (2, 1, 2, 1, 1, status.HTTP_201_CREATED),
        (0, 2, 2, 0, 2, status.HTTP_201_CREATED),
        (None, None, 2, 1, 1, status.HTTP_201_CREATED),
        (None, 1, 2, 1, 1, status.HTTP_201_CREATED),
        (1, None, 2, 1, 1, status.HTTP_201_CREATED),
        (0, None, 2, 0, 2, status.HTTP_201_CREATED),
    ],
)
@pytest.mark.django_db
def test_signup_group_maximum_attendee_and_waiting_list_capacities(
    api_client,
    maximum_attendee_capacity,
    waiting_list_capacity,
    expected_signups_count,
    expected_attending,
    expected_waitlisted,
    expected_status_code,
):
    registration = RegistrationFactory(
        maximum_attendee_capacity=maximum_attendee_capacity,
        waiting_list_capacity=waiting_list_capacity,
    )

    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0

    response = create_signup_group(api_client, signup_group_data)

    if expected_status_code == status.HTTP_403_FORBIDDEN:
        assert SignUpGroup.objects.count() == 0
    else:
        assert SignUpGroup.objects.count() == 1

    assert_attending_and_waitlisted_signups(
        response,
        expected_status_code,
        expected_signups_count,
        expected_attending,
        expected_waitlisted,
    )


@pytest.mark.parametrize(
    "signups_state", ["none", "empty", "without_responsible_person"]
)
@pytest.mark.django_db
def test_cannot_create_group_without_signups_or_responsible_person(
    api_client, organization, signups_state
):
    user = UserFactory()
    user.registration_admin_organizations.add(organization)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = {
        "extra_info": "Extra info for group",
        "registration": reservation.registration_id,
        "reservation_code": reservation.code,
    }

    if signups_state == "empty":
        signup_group_data["signups"] = []
    elif signups_state == "without_responsible_person":
        signup_group_data["signups"] = deepcopy(default_signups_data)

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize(
    "contact_person_state,contact_person_data,expected_error_message",
    [
        ("not_provided", "", "This field is required."),
        ("empty", {}, "Contact person information must be provided for a group."),
        ("none", None, "This field may not be null."),
    ],
)
@pytest.mark.django_db
def test_cannot_create_group_without_contact_person(
    api_client,
    organization,
    contact_person_state,
    contact_person_data,
    expected_error_message,
):
    user = UserFactory()
    user.registration_admin_organizations.add(organization)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = {
        "extra_info": "Extra info for group",
        "registration": reservation.registration_id,
        "reservation_code": reservation.code,
        "signups": default_signups_data,
    }
    if contact_person_state != "not_provided":
        signup_group_data["contact_person"] = contact_person_data

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["contact_person"][0] == expected_error_message


@pytest.mark.django_db
def test_registration_admin_can_create_signup_group_with_empty_extra_info_or_date_of_birth(
    api_client, registration
):
    LanguageFactory(id="fi", service_language=True)
    LanguageFactory(id="en", service_language=True)

    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SignUpGroupProtectedData.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code
    signup_group_data["extra_info"] = ""
    signup_group_data["date_of_birth"] = None

    assert_create_signup_group(api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


@pytest.mark.django_db
def test_organization_admin_can_create_signup_group(
    languages, organization, user, user_api_client
):
    reservation = SeatReservationCodeFactory(seats=2)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert_create_signup_group(user_api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


@pytest.mark.django_db
def test_financial_admin_can_create_signup_group(registration, api_client):
    LanguageFactory(pk="en", service_language=True)

    user = UserFactory()
    user.financial_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert_create_signup_group(api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


@pytest.mark.django_db
def test_regular_user_can_create_signup_group(
    languages, organization, user, user_api_client
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    reservation = SeatReservationCodeFactory(seats=2)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert_create_signup_group(user_api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


@pytest.mark.django_db
def test_user_without_organization_can_create_signup_group(
    api_client, languages, organization
):
    user = UserFactory()
    api_client.force_authenticate(user)

    reservation = SeatReservationCodeFactory(seats=2)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0
    assert SeatReservationCode.objects.count() == 1

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    assert_create_signup_group(api_client, signup_group_data)
    assert_default_signup_group_created(reservation, signup_group_data, user)


@pytest.mark.django_db
def test_non_authenticated_user_cannot_create_signup_group(api_client, languages):
    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0

    reservation = SeatReservationCodeFactory(seats=2)
    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    response = create_signup_group(api_client, signup_group_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0


@pytest.mark.django_db
def test_cannot_signup_group_if_enrolment_is_not_opened(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    registration.enrolment_start_time = localtime() + timedelta(days=1)
    registration.enrolment_end_time = localtime() + timedelta(days=2)
    registration.save(update_fields=["enrolment_start_time", "enrolment_end_time"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is not yet open."


@pytest.mark.django_db
def test_cannot_signup_group_if_enrolment_is_closed(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    registration.enrolment_start_time = localtime() - timedelta(days=2)
    registration.enrolment_end_time = localtime() - timedelta(days=1)
    registration.save(update_fields=["enrolment_start_time", "enrolment_end_time"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
        },
    }
    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Enrolment is already closed."


@pytest.mark.django_db
def test_cannot_signup_group_if_registration_is_missing(
    user_api_client, organization, user
):
    organization.registration_admin_users.add(user)

    signup_group_data = {
        "signups": [],
    }

    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["registration"][0].code == "required"


@pytest.mark.django_db
def test_cannot_signup_group_if_reservation_code_is_missing(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group_data = {
        "registration": registration.id,
        "signups": [],
    }

    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0].code == "required"


@pytest.mark.django_db
def test_amount_if_group_signups_cannot_be_greater_than_maximum_group_size(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    registration.audience_min_age = None
    registration.audience_max_age = None
    registration.maximum_attendee_capacity = None
    registration.maximum_group_size = 2
    registration.save(
        update_fields=[
            "audience_min_age",
            "audience_max_age",
            "maximum_attendee_capacity",
            "maximum_group_size",
        ]
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=3)
    code = reservation.code
    signup_data = {
        "first_name": "Mickey",
        "last_name": "Mouse",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": code,
        "signups": [signup_data, signup_data, signup_data],
        "contact_person": {
            "email": test_email1,
        },
    }
    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0].code == "max_group_size"


@pytest.mark.django_db
def test_cannot_signup_group_if_reservation_code_is_invalid(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group_data = {
        "registration": registration.id,
        "reservation_code": "c5e7d3ba-e48d-447c-b24d-c779950b2acb",
        "signups": [],
        "contact_person": {},
    }

    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code doesn't exist."


@pytest.mark.django_db
def test_cannot_signup_group_if_reservation_code_is_for_different_registration(
    user_api_client, registration, registration2, user
):
    user.get_default_organization().registration_admin_users.add(user)

    reservation = SeatReservationCodeFactory(registration=registration2, seats=2)
    code = reservation.code
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": code,
        "signups": [],
        "contact_person": {},
    }

    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code doesn't exist."


@pytest.mark.django_db
def test_cannot_signup_group_if_number_of_signups_exceeds_number_reserved_seats(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "contact_person": {
            "email": test_email1,
        },
        "signups": [
            {
                "first_name": "Mickey",
                "last_name": "Mouse",
            },
            {
                "first_name": "Minney",
                "last_name": "Mouse",
            },
        ],
    }
    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["signups"][0]
        == "Number of signups exceeds the number of requested seats"
    )


@pytest.mark.django_db
def test_cannot_signup_group_if_reservation_code_is_expired(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    reservation.timestamp = reservation.timestamp - timedelta(days=1)
    reservation.save(update_fields=["timestamp"])

    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "contact_person": {
            "email": test_email1,
        },
        "signups": [
            {
                "first_name": "Mickey",
                "last_name": "Mouse",
                "date_of_birth": "2011-04-07",
            },
        ],
    }
    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reservation_code"][0] == "Reservation code has expired."


@pytest.mark.django_db
def test_can_group_signup_twice_with_same_phone_or_email(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    # First signup
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": "2011-04-07",
    }

    contact_person_data = {
        "email": test_email1,
        "phone_number": "0441111111",
    }

    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "contact_person": contact_person_data,
        "signups": [signup_data],
    }

    assert_create_signup_group(user_api_client, signup_group_data)

    # Second signup
    contact_person_data_same_email = deepcopy(contact_person_data)
    contact_person_data_same_email["phone_number"] = "0442222222"

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_group_data["reservation_code"] = reservation.code
    signup_group_data["contact_person"] = contact_person_data_same_email

    assert_create_signup_group(user_api_client, signup_group_data)

    # Third signup
    contact_person_data_same_phone = deepcopy(contact_person_data)
    contact_person_data_same_phone["email"] = "another@email.com"

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data["reservation_code"] = reservation.code
    signup_group_data["contact_person"] = contact_person_data_same_phone

    assert_create_signup_group(user_api_client, signup_group_data)


@pytest.mark.parametrize("min_age", [None, 0, 10])
@pytest.mark.parametrize("max_age", [None, 0, 100])
@pytest.mark.parametrize("date_of_birth", [None, "1980-12-30"])
@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_signup_group_date_of_birth_is_mandatory_if_audience_min_or_max_age_specified(
    user_api_client, date_of_birth, min_age, max_age, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    falsy_values = ("", None)

    # Update registration
    registration.maximum_attendee_capacity = 1
    registration.audience_min_age = None
    registration.audience_max_age = None
    registration.enrolment_start_time = localtime()
    registration.enrolment_end_time = localtime() + timedelta(days=10)

    if min_age not in falsy_values:
        registration.audience_min_age = min_age
    if max_age not in falsy_values:
        registration.audience_max_age = max_age
    registration.save()

    if (
        min_age not in falsy_values or max_age not in falsy_values
    ) and not date_of_birth:
        expected_status = status.HTTP_400_BAD_REQUEST
        expected_error = "This field must be specified."
    else:
        expected_status = status.HTTP_201_CREATED
        expected_error = None

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    if date_of_birth:
        signup_data["date_of_birth"] = date_of_birth

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }
    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == expected_status

    if expected_error:
        assert response.data["signups"][0]["date_of_birth"][0] == expected_error


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
def test_signup_group_age_has_to_match_the_audience_min_max_age(
    user_api_client, date_of_birth, expected_error, expected_status, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    registration.audience_max_age = 40
    registration.audience_min_age = 20
    registration.enrolment_start_time = localtime()
    registration.enrolment_end_time = localtime() + timedelta(days=10)
    registration.maximum_attendee_capacity = 1
    registration.save()

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "date_of_birth": date_of_birth,
    }
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }

    response = create_signup_group(user_api_client, signup_group_data)

    assert response.status_code == expected_status
    if expected_error:
        assert response.data["signups"][0]["date_of_birth"][0] == expected_error


@pytest.mark.parametrize(
    "mandatory_field_id",
    [
        MandatoryFields.CITY,
        MandatoryFields.FIRST_NAME,
        MandatoryFields.LAST_NAME,
        MandatoryFields.PHONE_NUMBER,
        MandatoryFields.STREET_ADDRESS,
        MandatoryFields.ZIPCODE,
    ],
)
@pytest.mark.django_db
def test_signup_group_mandatory_fields_has_to_be_filled(
    user_api_client, mandatory_field_id, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    registration.mandatory_fields = [mandatory_field_id]
    registration.save(update_fields=["mandatory_fields"])

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "street_address": "Street address",
        "city": "Helsinki",
        "zipcode": "00100",
        mandatory_field_id: "",
    }
    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "phone_number": "0441111111",
            "notifications": "sms",
        },
    }

    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["signups"][0][mandatory_field_id][0]
        == "This field must be specified."
    )


@freeze_time("2023-03-14 03:30:00+02:00")
@pytest.mark.django_db
def test_cannot_signup_with_not_allowed_service_language(
    user_api_client, languages, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    languages[0].service_language = False
    languages[0].save(update_fields=["service_language"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "Michael",
                "last_name": "Jackson",
                "date_of_birth": "2011-04-07",
            }
        ],
        "contact_person": {
            "email": test_email1,
            "service_language": languages[0].pk,
        },
    }

    response = create_signup_group(user_api_client, signup_group_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["contact_person"]["service_language"][0].code == "does_not_exist"
    )


@pytest.mark.django_db
def test_signup_group_successful_with_waitlist(user_api_client, registration, user):
    user.get_default_organization().registration_admin_users.add(user)

    registration.maximum_attendee_capacity = 2
    registration.waiting_list_capacity = 2
    registration.save(
        update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
    )
    assert registration.signup_groups.count() == 0
    assert registration.signups.count() == 0

    reservation = SeatReservationCodeFactory(registration=registration, seats=2)
    signup_group_payload = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [
            {
                "first_name": "User",
                "last_name": "1",
            },
            {
                "first_name": "User",
                "last_name": "2",
            },
        ],
        "contact_person": {
            "email": "test1@test.com",
        },
    }
    assert_create_signup_group(user_api_client, signup_group_payload)
    assert registration.signup_groups.count() == 1
    assert registration.signups.count() == 2

    reservation2 = SeatReservationCodeFactory(registration=registration, seats=2)
    signup_group_payload2 = {
        "registration": registration.id,
        "reservation_code": reservation2.code,
        "signups": [
            {
                "first_name": "User",
                "last_name": "3",
            },
            {
                "first_name": "User",
                "last_name": "4",
            },
        ],
        "contact_person": {
            "email": "test4@test.com",
        },
    }
    assert_create_signup_group(user_api_client, signup_group_payload2)
    assert registration.signup_groups.count() == 2
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


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "en",
            "Registration confirmation",
            "Group registration to the event Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the event <strong>Foo</strong>.",
        ),
        (
            "fi",
            "Vahvistus ilmoittautumisesta",
            "Ryhmäilmoittautuminen tapahtumaan Foo on tallennettu.",
            "Onnittelut! Ilmoittautumisesi on vahvistettu tapahtumaan <strong>Foo</strong>.",
        ),
        (
            "sv",
            "Bekräftelse av registrering",
            "Gruppregistrering till evenemanget Foo har sparats.",
            "Grattis! Din registrering har bekräftats för evenemanget <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_email_sent_on_successful_signup_group(
    user_api_client,
    expected_heading,
    expected_subject,
    expected_text,
    registration,
    service_language,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    LanguageFactory(id=service_language, name=service_language, service_language=True)
    assert SignUp.objects.count() == 0

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        reservation = SeatReservationCodeFactory(registration=registration, seats=1)
        signup_data = {
            "first_name": "Michael",
            "last_name": "Jackson",
            "date_of_birth": "2011-04-07",
        }
        signup_group_data = {
            "registration": registration.id,
            "reservation_code": reservation.code,
            "signups": [signup_data],
            "contact_person": {
                "email": test_email1,
                "service_language": service_language,
            },
        }

        assert_create_signup_group(user_api_client, signup_group_data)
        assert SignUp.objects.count() == 1
        assert SignUp.objects.first().attendee_status == SignUp.AttendeeStatus.ATTENDING

        #  assert that the email was sent
        message_string = str(mail.outbox[0].alternatives[0])
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_heading in message_string
        assert expected_text in message_string


@pytest.mark.parametrize(
    "event_type,expected_heading,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "Group registration to the event Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the event <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.COURSE,
            "Group registration to the course Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the course <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "Group registration to the volunteering Foo has been saved.",
            "Congratulations! Your registration has been confirmed for the volunteering <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_signup_group_confirmation_template_has_correct_text_per_event_type(
    user_api_client,
    event_type,
    expected_heading,
    expected_text,
    languages,
    registration,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    assert SignUp.objects.count() == 0

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_groups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": "en",
        },
    }

    assert_create_signup_group(user_api_client, signup_groups_data)
    assert SignUp.objects.count() == 1
    assert SignUp.objects.first().attendee_status == SignUp.AttendeeStatus.ATTENDING

    #  assert that the email was sent
    assert expected_heading in str(mail.outbox[0].alternatives[0])
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,confirmation_message",
    [
        ("en", "Confirmation message"),
        ("fi", "Vahvistusviesti"),
        # Use default language if confirmation message is not defined to service language
        ("sv", "Vahvistusviesti"),
    ],
)
@pytest.mark.django_db
def test_signup_group_confirmation_message_is_shown_in_service_language(
    user_api_client,
    confirmation_message,
    registration,
    service_language,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    LanguageFactory(id=service_language, name=service_language, service_language=True)

    registration.confirmation_message_en = "Confirmation message"
    registration.confirmation_message_fi = "Vahvistusviesti"
    registration.save(
        update_fields=["confirmation_message_en", "confirmation_message_fi"]
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": service_language,
        },
    }

    assert_create_signup_group(user_api_client, signup_group_data)
    assert confirmation_message in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,confirmation_message",
    [
        ("en", "Confirmation message"),
        ("fi", "Vahvistusviesti"),
        # Use default language if confirmation message is not defined to service language
        ("sv", "Vahvistusviesti"),
    ],
)
@pytest.mark.django_db
def test_confirmation_message_is_shown_in_service_language(
    user_api_client,
    confirmation_message,
    registration,
    service_language,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    LanguageFactory(id=service_language, name=service_language, service_language=True)

    registration.confirmation_message_en = "Confirmation message"
    registration.confirmation_message_fi = "Vahvistusviesti"
    registration.save(
        update_fields=["confirmation_message_en", "confirmation_message_fi"]
    )

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": test_email1,
            "service_language": service_language,
        },
    }

    assert_create_signup_group(user_api_client, signup_group_data)
    assert confirmation_message in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "en",
            "Waiting list seat reserved",
            "The registration for the event <strong>Foo</strong> waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the event if a place becomes available.",
        ),
        (
            "fi",
            "Paikka jonotuslistalla varattu",
            "Ilmoittautuminen tapahtuman <strong>Foo</strong> jonotuslistalle onnistui.",
            "Jonotuslistalta siirretään automaattisesti tapahtuman osallistujaksi mikäli paikka "
            "vapautuu.",
        ),
        (
            "sv",
            "Väntelista plats reserverad",
            "Registreringen till väntelistan för <strong>Foo</strong>-evenemanget lyckades.",
            "Du flyttas automatiskt över från väntelistan för att bli deltagare i evenemanget om "
            "en plats blir ledig.",
        ),
    ],
)
@pytest.mark.django_db
def test_signup_group_different_email_sent_if_user_is_added_to_waiting_list(
    user_api_client,
    expected_subject,
    expected_heading,
    expected_text,
    languages,
    registration,
    service_language,
    signup,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    assert SignUp.objects.count() == 1

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        registration.maximum_attendee_capacity = 1
        registration.save(update_fields=["maximum_attendee_capacity"])

        reservation = SeatReservationCodeFactory(registration=registration, seats=1)
        signup_data = {
            "first_name": "Michael",
            "last_name": "Jackson",
        }
        signup_group_data = {
            "registration": registration.id,
            "reservation_code": reservation.code,
            "signups": [signup_data],
            "contact_person": {
                "email": "michael@test.com",
                "service_language": service_language,
            },
        }

        assert_create_signup_group(user_api_client, signup_group_data)
        assert SignUp.objects.count() == 2
        assert (
            SignUp.objects.filter(first_name=signup_data["first_name"])
            .first()
            .attendee_status
            == SignUp.AttendeeStatus.WAITING_LIST
        )

        #  assert that the email was sent
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_heading in str(mail.outbox[0].alternatives[0])
        assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "event_type,expected_heading,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "The registration for the event <strong>Foo</strong> waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the event if a place becomes available.",
        ),
        (
            Event.TypeId.COURSE,
            "The registration for the course <strong>Foo</strong> waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the course if a place becomes available.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "The registration for the volunteering <strong>Foo</strong> waiting list was successful.",
            "You will be automatically transferred from the waiting list to become a participant "
            "in the volunteering if a place becomes available.",
        ),
    ],
)
@pytest.mark.django_db
def test_signup_group_confirmation_to_waiting_list_template_has_correct_text_per_event_type(
    user_api_client,
    event_type,
    expected_heading,
    expected_text,
    languages,
    registration,
    signup,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    assert SignUp.objects.count() == 1

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    registration.maximum_attendee_capacity = 1
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)

    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
    }
    signup_group_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
        "contact_person": {
            "email": "michael@test.com",
            "service_language": "en",
        },
    }

    assert_create_signup_group(user_api_client, signup_group_data)
    assert SignUp.objects.count() == 2
    assert (
        SignUp.objects.filter(first_name=signup_data["first_name"])
        .first()
        .attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )

    #  assert that the email was sent
    assert expected_heading in str(mail.outbox[0].alternatives[0])
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_signup_group_text_fields_are_sanitized(
    languages, organization, user, user_api_client
):
    user.get_default_organization().registration_admin_users.add(user)

    reservation = SeatReservationCodeFactory(seats=1)
    signup_group_data = {
        "extra_info": "Extra info for group <p>Html</p>",
        "signups": [
            {
                "first_name": "Michael <p>Html</p>",
                "last_name": "Jackson <p>Html</p>",
                "extra_info": "Extra info <p>Html</p>",
                "street_address": "Street address <p>Html</p>",
                "zipcode": "<p>zip</p>",
            }
        ],
        "registration": reservation.registration_id,
        "reservation_code": reservation.code,
        "contact_person": {
            "first_name": "Michael <p>Html</p>",
            "last_name": "Jackson <p>Html</p>",
            "phone_number": "<p>0441111111</p>",
        },
    }

    response = assert_create_signup_group(user_api_client, signup_group_data)

    response_signup = response.data["signups"][0]
    assert response.data["extra_info"] == "Extra info for group Html"
    assert response_signup["first_name"] == "Michael Html"
    assert response_signup["last_name"] == "Jackson Html"
    assert response_signup["extra_info"] == "Extra info Html"
    assert response_signup["street_address"] == "Street address Html"
    assert response_signup["zipcode"] == "zip"

    signup_group = SignUpGroup.objects.get(pk=response.data["id"])
    assert signup_group.extra_info == "Extra info for group Html"

    signup = SignUp.objects.get(pk=response_signup["id"])
    assert signup.first_name == "Michael Html"
    assert signup.last_name == "Jackson Html"
    assert signup.extra_info == "Extra info Html"
    assert signup.street_address == "Street address Html"
    assert signup.zipcode == "zip"

    contact_person = signup_group.contact_person
    assert contact_person.first_name == "Michael Html"
    assert contact_person.last_name == "Jackson Html"
    assert contact_person.phone_number == "0441111111"


@pytest.mark.django_db
def test_signup_group_id_is_audit_logged_on_post(api_client, registration):
    reservation = SeatReservationCodeFactory(seats=2)

    LanguageFactory(pk="fi", service_language=True)
    LanguageFactory(pk="en", service_language=True)

    signup_group_data = default_signup_group_data
    signup_group_data["registration"] = reservation.registration_id
    signup_group_data["reservation_code"] = reservation.code

    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    response = assert_create_signup_group(api_client, signup_group_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]
