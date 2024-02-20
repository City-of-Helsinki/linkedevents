from datetime import timedelta

import pytest
from django.utils.timezone import localtime

from events.tests.factories import EventFactory, PlaceFactory
from registrations.utils import create_event_ics_file_content


@pytest.mark.django_db
def test_ics_file_cannot_be_created_without_start_time():
    event = EventFactory(start_time=None)
    with pytest.raises(
        ValueError,
        match="Event doesn't have start_time or name. Ics file cannot be created.",
    ):
        create_event_ics_file_content(event)


@pytest.mark.freeze_time("2024-01-01")
@pytest.mark.django_db
def test_ics_file_cannot_be_created_without_name():
    event = EventFactory(start_time=localtime(), name_fi=None)
    with pytest.raises(
        ValueError,
        match="Event doesn't have start_time or name. Ics file cannot be created.",
    ):
        create_event_ics_file_content(event)


@pytest.mark.freeze_time("2024-01-01")
@pytest.mark.django_db
def test_create_ics_file_content():
    event = EventFactory(
        id="helsinki:123",
        name_fi="Event name",
        short_description_fi="Event description",
        location=PlaceFactory(
            name_fi="Place name",
            street_address_fi="Streen address",
            address_locality_fi="Helsinki",
        ),
        start_time=localtime(),
        end_time=localtime() + timedelta(days=10),
    )
    (filename, ics) = create_event_ics_file_content(event)

    assert filename == "event_helsinki:123.ics"
    assert (
        ics
        == b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//linkedevents.hel.fi//NONSGML API//EN\r\nBEGIN:VEVENT\r\nSUMMARY:Event name\r\nDTSTART;TZID=Europe/Helsinki:20240101T020000\r\nDTEND;TZID=Europe/Helsinki:20240111T020000\r\nDESCRIPTION:Event description\r\nLOCATION:Place name\\, Streen address\\, Helsinki\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )


@pytest.mark.freeze_time("2024-01-01")
@pytest.mark.django_db
def test_create_ics_file_content_with_start_time_as_end_time():
    event = EventFactory(
        id="helsinki:123",
        name_fi="Event name",
        short_description_fi="Event description",
        location=PlaceFactory(
            name_fi="Place name",
            street_address_fi="Streen address",
            address_locality_fi="Helsinki",
        ),
        start_time=localtime(),
        end_time=None,
    )
    (filename, ics) = create_event_ics_file_content(event)

    assert filename == "event_helsinki:123.ics"
    assert (
        ics
        == b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//linkedevents.hel.fi//NONSGML API//EN\r\nBEGIN:VEVENT\r\nSUMMARY:Event name\r\nDTSTART;TZID=Europe/Helsinki:20240101T020000\r\nDTEND;TZID=Europe/Helsinki:20240101T020000\r\nDESCRIPTION:Event description\r\nLOCATION:Place name\\, Streen address\\, Helsinki\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
