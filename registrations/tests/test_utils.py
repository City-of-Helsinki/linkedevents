from datetime import timedelta
from unittest.mock import patch
from uuid import UUID

import pytest
from django.utils import translation
from django.utils.timezone import localtime

from events.tests.factories import EventFactory, PlaceFactory
from helevents.tests.factories import UserFactory
from registrations.tests.factories import SignUpContactPersonFactory, SignUpFactory
from registrations.utils import (
    create_event_ics_file_content,
    get_access_code_for_contact_person,
    get_checkout_url_with_lang_param,
)


def _get_checkout_url_and_language_code_test_params():
    test_params = []

    for lang_code in ["fi", "sv", "en"]:
        for checkout_url, param_prefix in [
            ("https://checkout.dev/v1/123/?user=abcdefg", "&"),
            ("https://logged-in-checkout.dev/v1/123/", "?"),
        ]:
            test_params.append(
                (
                    checkout_url,
                    lang_code,
                    f"{checkout_url}{param_prefix}lang={lang_code}",
                )
            )

    return test_params


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
    filename, ics = create_event_ics_file_content(event)

    assert filename == "event_helsinki:123.ics"
    assert (
        ics
        == b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//linkedevents.hel.fi//NONSGML "
        b"API//EN\r\nBEGIN:VEVENT\r\nSUMMARY:Event "
        b"name\r\nDTSTART;TZID=Europe/Helsinki:20240101T020000\r\nDTEND;TZID=Europe/Helsinki"
        b":20240111T020000\r\nDESCRIPTION:Event description\r\nLOCATION:Place name\\, "
        b"Streen address\\, Helsinki\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
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
    filename, ics = create_event_ics_file_content(event)

    assert filename == "event_helsinki:123.ics"
    assert (
        ics
        == b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//linkedevents.hel.fi//NONSGML "
        b"API//EN\r\nBEGIN:VEVENT\r\nSUMMARY:Event name\r\nDTSTART;TZID=Europe/"
        b"Helsinki:20240101T020000\r\nDTEND;TZID=Europe/Helsinki"
        b":20240101T020000\r\nDESCRIPTION:Event description\r\nLOCATION:Place name\\, "
        b"Streen address\\, Helsinki\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )


@pytest.mark.parametrize(
    "language,name_value,expected_fallback_language",
    [
        ("fi", "Event name", "en"),
        ("fi", "Evenemangets namn", "sv"),
        ("sv", "Event name", "en"),
        ("sv", "Tapahtuman nimi", "fi"),
        ("en", "Tapahtuman nimi", "fi"),
        ("en", "Evenemangets namn", "sv"),
    ],
)
@pytest.mark.django_db
def test_create_ics_file_using_fallback_languages(
    language, name_value, expected_fallback_language
):
    with translation.override(expected_fallback_language):
        event = EventFactory(
            id="helsinki:123",
            name=name_value,
            short_description_fi="Event description",
            location=PlaceFactory(
                name_fi="Place name",
                street_address_fi="Streen address",
                address_locality_fi="Helsinki",
            ),
            start_time=localtime(),
            end_time=localtime() + timedelta(days=10),
        )

    assert getattr(event, f"name_{language}") is None
    assert getattr(event, f"name_{expected_fallback_language}") == name_value

    filename, ics = create_event_ics_file_content(event, language=language)

    assert filename == "event_helsinki:123.ics"
    assert f"SUMMARY:{name_value}" in str(ics)


@pytest.mark.parametrize(
    "language,expected_fallback_language",
    [
        ("fi", "en"),
        ("sv", "en"),
        ("en", "fi"),
    ],
)
@pytest.mark.django_db
def test_create_ics_file_correct_fallback_language_used_if_event_name_is_none(
    language, expected_fallback_language
):
    event = EventFactory(
        id="helsinki:123",
        name=None,
        short_description_fi="Event description",
        location=PlaceFactory(
            name_fi="Place name",
            street_address_fi="Streen address",
            address_locality_fi="Helsinki",
        ),
        start_time=localtime(),
        end_time=localtime() + timedelta(days=10),
    )

    assert getattr(event, f"name_{language}") is None
    assert getattr(event, f"name_{expected_fallback_language}") is None

    with (
        pytest.raises(
            ValueError,
            match="Event doesn't have start_time or name. Ics file cannot be created.",
        ),
        patch("django.utils.translation.override") as mocked_translation_override,
    ):
        create_event_ics_file_content(event, language=language)

        mocked_translation_override.assert_called_with(expected_fallback_language)


@pytest.mark.parametrize(
    "has_contact_person,has_user,expected_access_code_type",
    [
        (True, True, str),
        (True, False, str),
        (False, True, None),
        (False, False, None),
    ],
)
@pytest.mark.django_db
def test_get_access_code_for_contact_person(
    has_contact_person, has_user, expected_access_code_type
):
    contact_person = (
        SignUpContactPersonFactory(
            signup=SignUpFactory(),
            email="test@test.com",
        )
        if has_contact_person
        else None
    )
    user = UserFactory() if has_user else None

    access_code = get_access_code_for_contact_person(contact_person, user)

    if expected_access_code_type is str:
        assert str(UUID(access_code)) == access_code
    else:
        assert access_code is None


@pytest.mark.parametrize(
    "checkout_url, lang_code, expected_checkout_url",
    _get_checkout_url_and_language_code_test_params(),
)
def test_get_checkout_url_with_lang_param(
    checkout_url, lang_code, expected_checkout_url
):
    new_checkout_url = get_checkout_url_with_lang_param(checkout_url, lang_code)

    assert new_checkout_url == expected_checkout_url
    assert checkout_url != new_checkout_url
