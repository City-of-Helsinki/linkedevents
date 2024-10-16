import freezegun
import pytest
from django.utils import translation
from django.utils.timezone import localtime

from notifications.exceptions import NotificationTemplateError
from notifications.utils import format_date, format_datetime


@pytest.mark.parametrize(
    "language,expected_formatted_datetime",
    [
        ("fi", "1.2.2024 klo 3:30"),
        ("en", "1 Feb 2024 at 3:30"),
        ("sv", "1.2.2024 kl. 3:30"),
    ],
)
@freezegun.freeze_time("2024-02-01 03:30:00+02:00")
def test_format_datetime_according_to_language(language, expected_formatted_datetime):
    dt = localtime()

    with translation.override(language):
        assert format_datetime(dt, lang=language) == expected_formatted_datetime


@pytest.mark.parametrize("language", ["wrong", "", None])
@freezegun.freeze_time("2024-02-01 03:30:00+02:00")
def test_format_datetime_invalid_language(language):
    dt = localtime()

    with pytest.raises(NotificationTemplateError):
        format_datetime(dt, lang=language)


@pytest.mark.parametrize(
    "language,expected_formatted_date",
    [
        ("fi", "1.2.2024"),
        ("en", "1 Feb 2024"),
        ("sv", "1.2.2024"),
    ],
)
@freezegun.freeze_time("2024-02-01 03:30:00+02:00")
def test_format_date_according_to_language(language, expected_formatted_date):
    dt = localtime()

    with translation.override(language):
        assert format_date(dt, lang=language) == expected_formatted_date


@pytest.mark.parametrize("language", ["wrong", "", None])
@freezegun.freeze_time("2024-02-01 03:30:00+02:00")
def test_format_date_invalid_language(language):
    dt = localtime()

    with pytest.raises(NotificationTemplateError):
        format_date(dt, lang=language)
