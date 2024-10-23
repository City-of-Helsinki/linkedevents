# ruff: noqa: F841
import pytest
from django.conf import settings as django_settings
from sentry_sdk import capture_exception
from sentry_sdk.scrubber import EventScrubber
from sentry_sdk.serializer import global_repr_processors

from events.tests.factories import ApiKeyUserFactory
from helevents.tests.factories import UserFactory


def _assert_sensitive_fields_scrubbed(events, fields):
    (event,) = events

    frames = event["exception"]["values"][0]["stacktrace"]["frames"]
    (frame,) = frames

    for field in fields:
        assert frame["vars"][field] == "[Filtered]"


@pytest.mark.django_db
def test_anonymize_user_repr_function():
    assert len(global_repr_processors) == 1

    user = UserFactory()
    user_repr = global_repr_processors[0](user, None)
    assert user_repr == f"<{user.__class__.__name__}: {user.username}>"

    apikey_user = ApiKeyUserFactory()
    apikey_user_repr = global_repr_processors[0](apikey_user, None)
    assert (
        apikey_user_repr
        == f"<{apikey_user.__class__.__name__}: {apikey_user.username}>"
    )

    nonetype_repr = global_repr_processors[0](None, None)
    assert nonetype_repr == NotImplemented


def test_custom_denylist_part1(sentry_init, sentry_capture_events):
    sentry_init(event_scrubber=EventScrubber(denylist=django_settings.SENTRY_DENYLIST))
    events = sentry_capture_events()

    try:
        access_code = "1234"
        user_name = "John Doe"
        user_email = "user@test.dev"
        user_phone_number = "+3581234567890"
        first_name = "John"
        last_name = "Doe"
        phone_number = "+3581234567890"
        raise ValueError()
    except ValueError:
        capture_exception()

    _assert_sensitive_fields_scrubbed(
        events,
        (
            "access_code",
            "user_name",
            "user_email",
            "user_phone_number",
            "first_name",
            "last_name",
            "phone_number",
        ),
    )


def test_custom_denylist_part2(sentry_init, sentry_capture_events):
    sentry_init(event_scrubber=EventScrubber(denylist=django_settings.SENTRY_DENYLIST))
    events = sentry_capture_events()

    try:
        email = "user@test.dev"
        city = "Helsinki"
        street_address = "Test street 1"
        zipcode = "00100"
        postal_code = "00100"
        date_of_birth = "1970-01-01"
        membership_number = "123456"
        raise ValueError()
    except ValueError:
        capture_exception()

    _assert_sensitive_fields_scrubbed(
        events,
        (
            "email",
            "city",
            "street_address",
            "zipcode",
            "postal_code",
            "date_of_birth",
            "membership_number",
        ),
    )


def test_custom_denylist_part3(sentry_init, sentry_capture_events):
    sentry_init(event_scrubber=EventScrubber(denylist=django_settings.SENTRY_DENYLIST))
    events = sentry_capture_events()

    try:
        native_language = "fi"
        service_language = "en"
        extra_info = "extra info"
        raise ValueError()
    except ValueError:
        capture_exception()

    _assert_sensitive_fields_scrubbed(
        events, ("native_language", "service_language", "extra_info")
    )
