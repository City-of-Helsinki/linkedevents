import datetime

import pytest
from django.utils.timezone import activate

from events.importer import harrastushaku
from events.importer.harrastushaku import HarrastushakuImporter, SubEventTimeRange
from events.models import DataSource


def make_timetable(
    id=None,
    activity_id=None,
    weekday=None,
    starttime=None,
    endtime=None,
    repetition=None,
):
    return {
        "id": id or "1",
        "activity_id": activity_id or "1",
        "weekday": weekday or "1",
        "starttime": starttime or "12:00",
        "endtime": endtime or "13:00",
        "repetition": repetition or "0",
    }


@pytest.fixture
def importer():
    DataSource.objects.get_or_create(id="tprek", defaults={"name": "tprek"})
    return HarrastushakuImporter(dict())


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        ("1700690400", "2023-11-23T00:00:00+02:00"),
        ("1695848400", "2023-09-28T00:00:00+03:00"),
    ],
)
@pytest.mark.django_db
def test_get_datetime_from_data_success(timestamp, expected):
    data = {
        "datetime": timestamp,
    }
    dt = harrastushaku.get_datetime_from_data(data, "datetime")
    assert isinstance(dt, datetime.datetime)
    assert dt.isoformat() == expected


@pytest.mark.parametrize("val", [None, False, ""])
@pytest.mark.django_db
def test_get_datetime_from_data_falsey(val):
    data = {
        "datetime": val,
    }
    dt = harrastushaku.get_datetime_from_data(data, "datetime")
    assert dt is None


@pytest.mark.parametrize(
    "start_date,end_date,timetables,expected",
    [
        # No timetables
        ("2023-01-02", "2023-01-02", [], []),
        # Start date > end date
        ("2023-01-03", "2023-01-02", [make_timetable()], []),
        # Start time > end time
        (
            "2023-01-02",
            "2023-01-02",
            [make_timetable(starttime="13:01", endtime="13:00")],
            [],
        ),
        # Start time == end time
        (
            "2023-01-02",
            "2023-01-02",
            [make_timetable(starttime="13:00", endtime="13:00")],
            [],
        ),
        # One day event on Monday, timetable on Tuesday
        ("2023-01-02", "2023-01-02", [make_timetable(weekday="2")], []),
        # One day event
        (
            "2023-01-02",
            "2023-01-02",
            [make_timetable()],
            [("2023-01-02T12:00:00+02:00", "2023-01-02T13:00:00+02:00")],
        ),
        # Timetable occurs on Monday, time range has one Monday
        (
            "2023-01-02",
            "2023-01-08",
            [make_timetable()],
            [("2023-01-02T12:00:00+02:00", "2023-01-02T13:00:00+02:00")],
        ),
        # Timetable occurs on Monday, time range has two Mondays
        (
            "2023-01-02",
            "2023-01-09",
            [make_timetable()],
            [
                ("2023-01-02T12:00:00+02:00", "2023-01-02T13:00:00+02:00"),
                ("2023-01-09T12:00:00+02:00", "2023-01-09T13:00:00+02:00"),
            ],
        ),
        # Multiple timetables
        (
            "2023-01-02",
            "2023-01-03",
            [
                make_timetable(id="1"),
                make_timetable(id="2", starttime="13:00", endtime="14:00"),
                make_timetable(id="3", weekday="2"),
            ],
            [
                ("2023-01-02T12:00:00+02:00", "2023-01-02T13:00:00+02:00"),
                ("2023-01-02T13:00:00+02:00", "2023-01-02T14:00:00+02:00"),
                ("2023-01-03T12:00:00+02:00", "2023-01-03T13:00:00+02:00"),
            ],
        ),
        # Timetable during DST
        (
            "2023-03-27",
            "2023-03-27",
            [make_timetable()],
            [("2023-03-27T12:00:00+03:00", "2023-03-27T13:00:00+03:00")],
        ),
    ],
)
@pytest.mark.django_db
def test_build_sub_event_time_ranges(
    start_date, end_date, timetables, expected, importer
):
    activate("Europe/Helsinki")
    # Convert ISO datetimes from expected to SubEventTimeRange objects
    expected_subtime_ranges = [
        SubEventTimeRange(*(datetime.datetime.fromisoformat(dt_str) for dt_str in d))
        for d in expected
    ]
    # Convert ISO dates to datetime.date objects
    start_date = datetime.date.fromisoformat(start_date)
    end_date = datetime.date.fromisoformat(end_date)

    result = importer.build_sub_event_time_ranges(start_date, end_date, timetables)

    assert len(result) == len(expected_subtime_ranges)
    assert result == expected_subtime_ranges
