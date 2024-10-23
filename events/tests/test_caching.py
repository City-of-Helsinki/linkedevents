import pytest

from events.api import _get_queryset_from_cache, _get_queryset_from_cache_many
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
    django_cache.set("local_ids", {event.id: "lapsi"})

    params = {"all_ongoing_OR": "lapsi,musiikki"}
    queryset = Event.objects

    queryset = _get_queryset_from_cache_many(
        params, "all_ongoing_OR", ["internet_ids", "local_ids"], "OR", queryset
    )

    assert queryset.first().id == event.id


@pytest.mark.django_db
def test_missing_cache_many_not_throwing_error_and_returns_none(django_cache):
    django_cache.set("local_ids", {})

    params = {"all_ongoing_OR": "lapsi,musiikki"}
    queryset = Event.objects

    queryset = _get_queryset_from_cache_many(
        params, "all_ongoing_OR", ["internet_ids", "local_ids"], "OR", queryset
    )

    assert queryset.first() is None
