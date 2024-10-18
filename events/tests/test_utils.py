from datetime import datetime, timedelta

import pytest
import pytz
from django.conf import settings as django_settings
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import ParseError

from events.tests.test_event_get import get_list
from events.tests.test_event_post import create_with_post
from events.utils import (
    clean_text_fields,
    parse_end_time,
    parse_time,
    start_of_day,
    start_of_next_day,
    start_of_previous_day,
)


@pytest.fixture
def local_tz():
    return pytz.timezone(django_settings.TIME_ZONE)


@pytest.mark.django_db
def test_parse_time_iso8601(local_tz):
    assert parse_time("2022-07-17T17:17:17+03:00") == (
        local_tz.localize(datetime(2022, 7, 17, 17, 17, 17)),
        False,
    )


@pytest.mark.django_db
def test_parse_time_iso8601_invalid_offset(local_tz):
    with pytest.raises(ParseError) as ex:
        parse_time("2022-07-17T17:17:17+25:00")
    assert "time in invalid format" in str(ex.value)

    with pytest.raises(ParseError) as ex:
        parse_time("2022-07-17T17:17:17+23:00")
    assert "out of bounds" in str(ex.value)


@pytest.mark.django_db
def test_parse_time_invalid_format(local_tz):
    with pytest.raises(ParseError) as ex:
        parse_time("asdfdsaasdf")
    assert "time in invalid format" in str(ex.value)


@pytest.mark.django_db
def test_parse_time_overflow_error(local_tz):
    # Underlying overflow error that needs to be separately
    # handled by parse_time
    with pytest.raises(ParseError) as ex:
        parse_time("999999999999999999")
    assert "time in invalid format" in str(ex.value)


@pytest.mark.django_db
def test_parse_time_dst_handling(local_tz):
    assert parse_end_time("2022-3-27") == (
        local_tz.localize(datetime(2022, 3, 28)),
        True,
    )
    assert parse_end_time("2022-10-30") == (
        local_tz.localize(datetime(2022, 10, 31)),
        True,
    )

    # This is right in the middle of a DST change from DST (+3) to normal
    # time (+2) where a local time without timezone information would
    # be ambiguous
    with freeze_time("2022-10-30 03:30:00+02:00"):
        assert parse_time("today") == (
            local_tz.localize(datetime(2022, 10, 30)),
            True,
        )
        assert parse_end_time("today") == (
            local_tz.localize(datetime(2022, 10, 31)),
            True,
        )

        assert parse_time("now") == (timezone.now(), False)
        assert parse_end_time("now") == (timezone.now(), False)


@pytest.mark.django_db
def test_start_of_day(local_tz):
    naive_dt = datetime(2022, 3, 27)
    aware_dt = local_tz.localize(naive_dt)
    utc_dt = aware_dt.astimezone(pytz.utc)

    assert start_of_day(aware_dt) == aware_dt
    assert start_of_day(utc_dt) == aware_dt


@pytest.mark.django_db
def test_start_of_next_day(local_tz):
    naive_dt = datetime(2022, 3, 27)
    aware_dt = local_tz.localize(naive_dt)
    utc_dt = aware_dt.astimezone(pytz.utc)

    naive_tomorrow_dt = datetime(2022, 3, 28)
    aware_tomorrow_dt = local_tz.localize(naive_tomorrow_dt)

    assert start_of_next_day(aware_dt) == aware_tomorrow_dt
    assert start_of_next_day(utc_dt) == aware_tomorrow_dt


@pytest.mark.django_db
def test_start_of_previous_day(local_tz):
    naive_dt = datetime(2022, 3, 27)
    aware_dt = local_tz.localize(naive_dt)
    utc_dt = aware_dt.astimezone(pytz.utc)

    naive_previous_dt = datetime(2022, 3, 26)
    aware_previous_dt = local_tz.localize(naive_previous_dt)

    assert start_of_previous_day(aware_dt) == aware_previous_dt
    assert start_of_previous_day(utc_dt) == aware_previous_dt


@pytest.mark.django_db
def test_inconsistent_tz_default(api_client, minimal_event_dict, user, settings):
    """
    Sadly the behaviour naive datetimes of GET and POST in events API is
    inconsistent. POST assumes naive datetimes are in UTC, while GET assumes
    naive datetimes are in local time. Fixing this breaks other tests and
    backwards compatibility, so this test is here to ensure that
    linkedevents remains inconsistent.

    At least these tests rely on this incorrect behaviour:
    * test_event_get.test_start_end_iso_date_time
    * test_event_get.test_start_end_events_without_endtime
    """
    api_client.force_authenticate(user=user)

    # Ensure test runs on a time zone that is different from UTC
    settings.TIME_ZONE = "Europe/Helsinki"

    # pick some DST irrelevant date in the future
    # January 1st next year at 15:00:00
    # This is the naive time we use to create the event
    future_naive_dt = datetime(timezone.now().year + 1, 1, 1, 15)
    future_naive_dt_str = future_naive_dt.isoformat()

    # Bump by two hours... this is the naive time that will actually find the event
    offset_naive_dt = future_naive_dt + timedelta(hours=2)
    offset_naive_dt_str = offset_naive_dt.isoformat()

    minimal_event_dict["start_time"] = future_naive_dt_str
    minimal_event_dict["end_time"] = future_naive_dt_str
    create_with_post(api_client, minimal_event_dict)

    list_with_original_create_dt = get_list(
        api_client,
        query_string=f"start={future_naive_dt_str}&end={future_naive_dt_str}",
    )
    assert (
        list_with_original_create_dt.json()["meta"]["count"] == 0
    ), list_with_original_create_dt.json()

    list_with_offset_create_dt = get_list(
        api_client,
        query_string=f"start={offset_naive_dt_str}&end={offset_naive_dt_str}",
    )
    assert (
        list_with_offset_create_dt.json()["meta"]["count"] == 1
    ), list_with_offset_create_dt.json()


@pytest.mark.parametrize(
    "data, allowed_html_fields, strip, expected_result",
    [
        # No allowed_html_fields specified
        ({"field1": "<p>Text</p>"}, [], False, {"field1": "&lt;p&gt;Text&lt;/p&gt;"}),
        ({"field1": "<p>Text</p>"}, [], True, {"field1": "Text"}),
        # allowed_html_fields specified
        (
            {"field1": "<p>Text</p>", "field2": "<p>Text</p>"},
            ["field1"],
            False,
            {"field1": "<p>Text</p>", "field2": "&lt;p&gt;Text&lt;/p&gt;"},
        ),
        (
            {"field1": "<p>Text</p>", "field2": "<p>Text</p>"},
            ["field1"],
            True,
            {"field1": "<p>Text</p>", "field2": "Text"},
        ),
        # Only <p> should be allowed
        (
            {"field1": "<p><b>Text</b></p>"},
            ["field1"],
            False,
            {"field1": "<p>&lt;b&gt;Text&lt;/b&gt;</p>"},
        ),
        ({"field1": "<p><b>Text</b></p>"}, ["field1"], True, {"field1": "<p>Text</p>"}),
        # Ampersands
        ({"field1": "Text & more text"}, [], False, {"field1": "Text & more text"}),
        ({"field1": "Text & more text"}, [], True, {"field1": "Text & more text"}),
        ({"field1": "Text &amp; more text"}, [], False, {"field1": "Text & more text"}),
        ({"field1": "Text &amp; more text"}, [], True, {"field1": "Text & more text"}),
    ],
)
def test_clean_text_fields_handles_various_inputs(
    settings, data, allowed_html_fields, strip, expected_result
):
    settings.BLEACH_ALLOWED_TAGS = ["p"]
    result = clean_text_fields(data, allowed_html_fields, strip)
    assert result == expected_result
