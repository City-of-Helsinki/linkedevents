from collections import Counter
from datetime import timedelta

import freezegun
import pytest
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase
from django.utils.timezone import localtime

from events.tests.factories import EventFactory
from registrations.models import (
    SeatReservationCode,
    SignUpGroupProtectedData,
    SignUpProtectedData,
)
from registrations.tests.factories import (
    RegistrationFactory,
    SeatReservationCodeFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
)
from registrations.utils import code_validity_duration

_ENCRYPTION_KEY = "c87a6669a1ded2834f1dfd0830d86ef6cdd20372ac83e8c7c23feffe87e6a051"
_ENCRYPTION_KEY2 = "f1a79d4b60a947b988beaf1eae871289fb03f2b9fd443d67107a7d05d05f831e"


@pytest.mark.django_db
def test_encrypt_fields_with_new_key(settings):
    old_keys = (_ENCRYPTION_KEY,)
    new_keys = (_ENCRYPTION_KEY2, _ENCRYPTION_KEY)
    settings.FIELD_ENCRYPTION_KEYS = old_keys

    signup_group_extra_info = "Signup group extra info"

    first_signup_extra_info = "First signup extra info"
    first_signup_dob = "2023-01-01"

    second_signup_extra_info = "Second signup extra info"
    second_signup_dob = "2023-02-02"

    signup_group = SignUpGroupFactory()
    signup_group_protected_data = SignUpGroupProtectedDataFactory(
        registration=signup_group.registration,
        signup_group=signup_group,
        extra_info=signup_group_extra_info,
    )

    first_signup = SignUpFactory(
        registration=signup_group.registration, signup_group=signup_group
    )
    first_signup_protected_data = SignUpProtectedData(
        registration=signup_group.registration,
        signup=first_signup,
        extra_info=first_signup_extra_info,
        date_of_birth=first_signup_dob,
    )

    second_signup = SignUpFactory(registration=signup_group.registration)
    second_signup_protected_data = SignUpProtectedData(
        registration=signup_group.registration,
        signup=second_signup,
        extra_info=second_signup_extra_info,
        date_of_birth=second_signup_dob,
    )

    def assert_encrypted_with_keys(keys):
        assert signup_group_protected_data.extra_info == signup_group_extra_info

        assert first_signup_protected_data.extra_info == first_signup_extra_info
        assert first_signup_protected_data.date_of_birth == first_signup_dob

        assert second_signup_protected_data.extra_info == second_signup_extra_info
        assert second_signup_protected_data.date_of_birth == second_signup_dob

        signup_group_extra_info_field = SignUpGroupProtectedData._meta.get_field(
            "extra_info"
        )
        assert signup_group_extra_info_field.keys == keys
        del signup_group_extra_info_field.keys

        signup_extra_info_field = SignUpProtectedData._meta.get_field("extra_info")
        assert signup_extra_info_field.keys == keys
        del signup_extra_info_field.keys

    # Test that fields have been encrypted with the old key
    assert_encrypted_with_keys(old_keys)

    settings.FIELD_ENCRYPTION_KEYS = new_keys
    call_command("encrypt_fields_with_new_key")

    # Test that fields have been encrypted with the new key
    assert_encrypted_with_keys(new_keys)


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


@freezegun.freeze_time("2024-02-16 16:45:00+02:00")
@pytest.mark.django_db(transaction=True)
def test_delete_expired_seatreservations():
    registration = RegistrationFactory(
        maximum_attendee_capacity=5, waiting_list_capacity=5
    )

    now = localtime()
    expired_timestamp = now - timedelta(minutes=code_validity_duration(1) + 1)
    expired_timestamp2 = now - timedelta(minutes=code_validity_duration(2) + 1)
    exactly_expiration_threshold = now - timedelta(minutes=code_validity_duration(1))

    expired_reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    SeatReservationCode.objects.filter(pk=expired_reservation.pk).update(
        timestamp=expired_timestamp
    )

    non_expired_reservation = SeatReservationCodeFactory(
        registration=registration, seats=1
    )
    non_expired_reservation2 = SeatReservationCodeFactory(
        registration=registration, seats=1
    )
    SeatReservationCode.objects.filter(pk=non_expired_reservation2.pk).update(
        timestamp=exactly_expiration_threshold
    )

    expired_reservation2 = SeatReservationCodeFactory(
        registration=registration, seats=2
    )
    SeatReservationCode.objects.filter(pk=expired_reservation2.pk).update(
        timestamp=expired_timestamp2
    )

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 1
    assert registration.remaining_waiting_list_capacity == 5

    assert SeatReservationCode.objects.count() == 4

    call_command("delete_expired_seat_reservations")

    assert SeatReservationCode.objects.count() == 2
    assert Counter(SeatReservationCode.objects.values_list("pk", flat=True)) == Counter(
        [non_expired_reservation.pk, non_expired_reservation2.pk]
    )

    registration.refresh_from_db()
    assert registration.remaining_attendee_capacity == 3
    assert registration.remaining_waiting_list_capacity == 5
