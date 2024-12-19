import pytest

from registrations.exports import RegistrationSignUpsExportXLSX
from registrations.models import SignUp
from registrations.tests.factories import SignUpContactPersonFactory, SignUpFactory


@pytest.fixture
def signup_registration(registration):
    signup_1 = SignUpFactory(
        registration=registration,
        first_name="John",
        last_name="Doe",
        phone_number="123456789",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    SignUpContactPersonFactory(
        signup=signup_1, email="contact1@example.com", phone_number="123456789"
    )

    signup_2 = SignUpFactory(
        registration=registration,
        first_name="Jane",
        last_name="Smith",
        phone_number="987654321",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    SignUpContactPersonFactory(
        signup=signup_2, email="contact2@example.com", phone_number="987654321"
    )

    signup_3 = SignUpFactory(
        registration=registration,
        first_name="Wait",
        last_name="Listed",
        phone_number="3254454",
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )
    SignUpContactPersonFactory(
        signup=signup_3, email="contact2@example.com", phone_number="45645637"
    )

    return registration


@pytest.mark.django_db
def test_signup_order(signup_registration):
    registration = signup_registration
    exporter = RegistrationSignUpsExportXLSX(registration)
    table_data = exporter._get_signups_table_data()

    assert table_data[0][0] == "Doe John"
    assert table_data[1][0] == "Smith Jane"
    assert table_data[2][0] == "Listed Wait"


@pytest.mark.django_db
def test_attendee_name_format(signup_registration):
    registration = signup_registration
    exporter = RegistrationSignUpsExportXLSX(registration)
    table_data = exporter._get_signups_table_data()

    assert table_data[0][0] == "Doe John"
