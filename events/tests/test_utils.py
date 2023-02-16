from datetime import datetime

import pytest
import pytz
from django.conf import settings
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import ParseError

from events.utils import parse_time


@pytest.fixture
def local_tz():
    return pytz.timezone(settings.TIME_ZONE)


@pytest.mark.django_db
def test_parse_time_iso8601(local_tz):
    assert parse_time("2022-07-17T17:17:17+03:00", True) == (
        local_tz.localize(datetime(2022, 7, 17, 17, 17, 17)),
        True,
    )


@pytest.mark.django_db
def test_parse_time_iso8601_invalid_offset(local_tz):
    with pytest.raises(ParseError) as ex:
        parse_time("2022-07-17T17:17:17+25:00", True)
    assert "time in invalid format" in str(ex.value)

    with pytest.raises(ParseError) as ex:
        parse_time("2022-07-17T17:17:17+23:00", True)
    assert "out of bounds" in str(ex.value)


@pytest.mark.django_db
def test_parse_time_invalid_format(local_tz):
    with pytest.raises(ParseError) as ex:
        parse_time("asdfdsaasdf", True)
    assert "time in invalid format" in str(ex.value)


@pytest.mark.django_db
def test_parse_time_overflow_error(local_tz):
    # Underlying overflow error that needs to be separately
    # handled by parse_time
    with pytest.raises(ParseError) as ex:
        parse_time("999999999999999999", False)
    assert "time in invalid format" in str(ex.value)


@pytest.mark.django_db
def test_parse_time_dst_handling(local_tz):
    assert parse_time("2022-3-27", False) == (
        local_tz.localize(datetime(2022, 3, 28)),
        False,
    )
    assert parse_time("2022-10-30", False) == (
        local_tz.localize(datetime(2022, 10, 31)),
        False,
    )

    # This is right in the middle of a DST change from DST (+3) to normal
    # time (+2) where a local time without timezone information would
    # be ambiguous
    with freeze_time("2022-10-30 03:30:00+02:00"):
        assert parse_time("today", True) == (
            local_tz.localize(datetime(2022, 10, 30)),
            False,
        )
        assert parse_time("today", False) == (
            local_tz.localize(datetime(2022, 10, 31)),
            False,
        )

        assert parse_time("now", True) == (timezone.now(), True)
        assert parse_time("now", False) == (timezone.now(), True)
