from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from events.api import EventFilter
from events.models import Event
from events.tests.factories import EventFactory, KeywordFactory, PlaceFactory
from events.tests.utils import create_super_event


@pytest.mark.django_db
def test_get_event_list_hide_recurring_children_true():
    event_1 = EventFactory()
    event_2 = EventFactory(data_source=event_1.data_source)
    super_1 = create_super_event([event_1, event_2], event_1.data_source)
    filter_set = EventFilter()

    result = filter_set.filter_hide_recurring_children(
        Event.objects.all(), "hide_recurring_children", True
    )

    assert result.count() == 1
    assert super_1 in result


@pytest.mark.django_db
def test_get_event_list_hide_recurring_children_false():
    event_1 = EventFactory()
    event_2 = EventFactory(data_source=event_1.data_source)
    super_1 = create_super_event([event_1, event_2], event_1.data_source)
    filter_set = EventFilter()

    result = filter_set.filter_hide_recurring_children(
        Event.objects.all(), "hide_recurring_children", False
    )

    assert result.count() == 3
    assert super_1 in result
    assert event_1 in result
    assert event_2 in result


def test_filter_full_text_wrong_language():
    request = Mock()
    request.query_params = {"x_full_text_language": "unknown"}
    filter_set = EventFilter(request=request)
    with pytest.raises(ValidationError):
        filter_set.filter_x_full_text(None, "x_full_text", "something")


@pytest.mark.django_db()
@pytest.mark.parametrize(
    "language",
    [
        "fi",
        "en",
        "sv",
    ],
)
def test_get_event_list_full_text(language):
    place_fi = PlaceFactory(
        name_fi="Test Place", name_en="Something else", name_sv="Something else"
    )
    place_en = PlaceFactory(
        name_en="Test Place", name_fi="Something else", name_sv="Something else"
    )
    place_sv = PlaceFactory(
        name_sv="Test Place", name_en="Something else", name_fi="Something else"
    )
    kw_fi = KeywordFactory(
        name_fi="Test Keyword", name_en="Something else", name_sv="Something else"
    )
    kw_en = KeywordFactory(
        name_en="Test Keyword", name_fi="Something else", name_sv="Something else"
    )
    kw_sv = KeywordFactory(
        name_sv="Test Keyword", name_en="Something else", name_fi="Something else"
    )
    event_fi = EventFactory(
        id="test:fi",
        name_fi="Test Event",
        name_en="Something else",
        name_sv="Something else",
        location=place_fi,
    )
    event_en = EventFactory(
        id="test:en",
        name_en="Test Event",
        name_fi="Something else",
        name_sv="Something else",
        location=place_en,
    )
    event_sv = EventFactory(
        id="test:sv",
        name_sv="Test Event",
        name_en="Something else",
        name_fi="Something else",
        location=place_sv,
    )

    event_fi.keywords.set([kw_fi])
    event_en.keywords.set([kw_en])
    event_sv.keywords.set([kw_sv])

    call_command("refresh_full_text", "--create-no-transaction")

    request = Mock()
    request.query_params = {"x_full_text_language": language}

    filter_set = EventFilter(request=request)

    def do_filter(query):
        return filter_set.filter_x_full_text(
            Event.objects.all(), "x_full_text", f"{query}"
        )

    result = do_filter("Test Event")
    assert result.count() == 1
    assert result[0].id == f"test:{language}"

    result = do_filter("Test Place")
    assert result.count() == 1
    assert result[0].id == f"test:{language}"

    result = do_filter("Test Keyword")
    assert result.count() == 1
    assert result[0].id == f"test:{language}"


@pytest.mark.django_db
@pytest.mark.parametrize("ongoing", [True, False])
def test_get_event_list_ongoing(ongoing):
    now = timezone.now()
    event_end_before = EventFactory(end_time=now - timedelta(hours=1))
    event_end_after = EventFactory(end_time=now + timedelta(hours=1))

    filter_set = EventFilter()

    qs = filter_set.filter_x_ongoing(Event.objects.all(), "x_ongoing", ongoing)

    assert qs.count() == 1
    if ongoing:
        assert event_end_after in qs
    else:
        assert event_end_before in qs
