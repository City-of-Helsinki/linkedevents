import pytest

from events.api import (
    _filter_event_queryset,
    _get_queryset_from_cache,
    _get_queryset_from_cache_many,
)
from events.models import Event


@pytest.mark.django_db
def test_queryset_from_cache(django_cache, event):
    django_cache.set("local_ids", {event.id: "lapsi"})

    params = {"local_ongoing_OR": "lapsi,musiikki"}
    queryset = Event.objects

    queryset = _get_queryset_from_cache(
        params, "local_ongoing_OR", "local_ids", "OR", queryset
    )

    assert queryset.first().id == event.id


@pytest.mark.django_db
def test_missing_cache_not_throwing_error_and_returns_none(django_cache):
    django_cache.set("local_ids", {})

    params = {"local_ongoing_OR": "lapsi,musiikki"}
    queryset = Event.objects

    queryset = _get_queryset_from_cache(
        params, "local_ongoing_OR", "local_ids", "OR", queryset
    )

    assert queryset.first() is None


@pytest.mark.django_db
def test_queryset_from_cache_many(django_cache, event):
    django_cache.set("internet_ids", {})
    django_cache.set("local_ids", {event.id: "lapsi"})

    params = {"all_ongoing_OR": "lapsi,musiikki"}
    queryset = Event.objects

    queryset = _get_queryset_from_cache_many(
        params, "all_ongoing_OR", ["internet_ids", "local_ids"], "OR", queryset
    )

    assert queryset.first().id == event.id


@pytest.mark.django_db
def test_missing_cache_many_returns_original_queryset(django_cache, event, caplog):
    django_cache.set("local_ids", {event.id: "lapsi"})

    params = {"all_ongoing_OR": "musiikki"}
    queryset = _get_queryset_from_cache_many(
        params, "all_ongoing_OR", ["internet_ids", "local_ids"], "OR", Event.objects
    )

    assert queryset.first().id == event.id
    assert "Missed cache" in caplog.text


@pytest.mark.django_db
def test_empty_internet_cache_is_valid(django_cache, caplog):
    django_cache.set("internet_ids", {})

    params = {"internet_ongoing_OR": "lapsi,musiikki"}
    queryset = Event.objects

    queryset = _get_queryset_from_cache(
        params, "internet_ongoing_OR", "internet_ids", "OR", queryset
    )

    assert queryset.first() is None
    assert "Missed cache internet_ids" not in caplog.text


@pytest.mark.django_db
def test_missing_internet_cache_is_logged(django_cache, caplog):
    django_cache.delete("internet_ids")

    params = {"internet_ongoing_OR": "lapsi,musiikki"}
    _get_queryset_from_cache(
        params, "internet_ongoing_OR", "internet_ids", "OR", Event.objects
    )

    assert "Missed cache internet_ids" in caplog.text


@pytest.mark.django_db
def test_missing_cache_many_not_throwing_error_and_returns_none(django_cache):
    django_cache.set("local_ids", {})

    params = {"all_ongoing_OR": "lapsi,musiikki"}
    queryset = Event.objects

    queryset = _get_queryset_from_cache_many(
        params, "all_ongoing_OR", ["internet_ids", "local_ids"], "OR", queryset
    )

    assert queryset.first() is None


@pytest.mark.django_db
def test_filter_event_queryset_all_ongoing_with_empty_caches_returns_no_events(
    django_cache, event
):
    django_cache.set("internet_ids", {})
    django_cache.set("local_ids", {})

    queryset = _filter_event_queryset(Event.objects.all(), {"all_ongoing": "true"})

    assert queryset.count() == 0


@pytest.mark.django_db
def test_filter_event_queryset_all_ongoing_with_missing_cache_keeps_events(
    django_cache, event, caplog
):
    django_cache.set("local_ids", {event.id: "lapsi"})
    django_cache.delete("internet_ids")

    queryset = _filter_event_queryset(Event.objects.all(), {"all_ongoing": "true"})

    assert list(queryset) == [event]
    assert "Missed cache" in caplog.text
