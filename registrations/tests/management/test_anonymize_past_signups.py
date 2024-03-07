from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils.timezone import localtime

from events.tests.factories import EventFactory
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpFactory,
    SignUpGroupFactory,
)


@pytest.mark.django_db
def test_anonymize_past_signups():
    future_event = EventFactory(end_time=localtime() + timedelta(days=31))
    past_event = EventFactory(end_time=localtime() - timedelta(days=31))
    future_registration = RegistrationFactory(event=future_event)
    past_registration = RegistrationFactory(event=past_event)
    future_signup_group = SignUpGroupFactory(registration=future_registration)
    future_signup_in_group = SignUpFactory(
        registration=future_registration, signup_group=future_signup_group
    )
    future_signup = SignUpFactory(registration=future_registration)
    past_signup_group = SignUpGroupFactory(registration=past_registration)
    past_signup_in_group = SignUpFactory(
        registration=past_registration, signup_group=past_signup_group
    )
    past_signup = SignUpFactory(registration=past_registration)

    call_command("anonymize_past_signups")

    future_signup_group.refresh_from_db()
    future_signup_in_group.refresh_from_db()
    future_signup.refresh_from_db()
    past_signup_group.refresh_from_db()
    past_signup_in_group.refresh_from_db()
    past_signup.refresh_from_db()
    assert future_signup_group.anonymization_time is None
    assert future_signup_in_group.anonymization_time is None
    assert future_signup.anonymization_time is None
    assert past_signup_group.anonymization_time is not None
    assert past_signup_in_group.anonymization_time is not None
    assert past_signup.anonymization_time is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "enrolment_time_delta,event_time_delta",
    [
        (0, -31),
        (31, -31),
        (-29, -31),
        (-31, 0),
        (-31, 31),
        (-31, -29),
    ],
)
def test_do_not_anonymize_if_enrolment_end_time_and_end_time_are_not_over_30_days_in_past(
    enrolment_time_delta, event_time_delta
):
    event = EventFactory(end_time=localtime() + timedelta(days=event_time_delta))
    registration = RegistrationFactory(
        event=event,
        enrolment_end_time=localtime() + timedelta(days=enrolment_time_delta),
    )
    signup_group = SignUpGroupFactory(registration=registration)
    signup_in_group = SignUpFactory(
        registration=registration, signup_group=signup_group
    )
    signup = SignUpFactory(registration=registration)

    call_command("anonymize_past_signups")

    signup_group.refresh_from_db()
    signup_in_group.refresh_from_db()
    signup.refresh_from_db()
    assert signup_group.anonymization_time is None
    assert signup_in_group.anonymization_time is None
    assert signup.anonymization_time is None


@pytest.mark.django_db
def test_anonymize_if_enrolment_end_time_and_end_time_are_over_30_days_in_past():
    event = EventFactory(end_time=localtime() - timedelta(days=31))
    registration = RegistrationFactory(
        event=event,
        enrolment_end_time=localtime() - timedelta(days=31),
    )
    signup_group = SignUpGroupFactory(registration=registration)
    signup_in_group = SignUpFactory(
        registration=registration, signup_group=signup_group
    )
    signup = SignUpFactory(registration=registration)

    call_command("anonymize_past_signups")

    signup_group.refresh_from_db()
    signup_in_group.refresh_from_db()
    signup.refresh_from_db()
    assert signup_group.anonymization_time is not None
    assert signup_in_group.anonymization_time is not None
    assert signup.anonymization_time is not None
