from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from events.importer import yso
from events.importer.yso import YsoImporter
from events.search_index.signals import (
    search_index_updates_suppressed,
    suppress_search_index_updates,
)
from events.tests.factories import EventFactory, KeywordFactory
from linkedevents import __version__


def test_load_graph_into_memory_sends_user_agent(requests_mock, settings):
    settings.OUTBOUND_USER_AGENT = f"Test/{__version__}"
    url = "http://localhost/yso"
    requests_mock.get(
        url,
        text="<http://example.org/subject> <http://example.org/predicate> "
        "<http://example.org/object> .",
    )

    importer = YsoImporter.__new__(YsoImporter)
    importer.load_graph_into_memory(url)

    assert (
        requests_mock.request_history[0].headers["User-Agent"] == f"Test/{__version__}"
    )


def make_importer():
    importer = YsoImporter.__new__(YsoImporter)
    importer.load_graph_into_memory = Mock(return_value=object())
    return importer


@pytest.mark.django_db
@override_settings(EVENT_SEARCH_INDEX_SIGNALS_ENABLED=True)
def test_import_keywords_bulk_updates_affected_event_ids():
    importer = make_importer()

    def save_keywords(_graph):
        assert search_index_updates_suppressed()
        importer._affected_event_ids.update(["event:1", "event:2", "event:1"])

    importer.save_keywords = Mock(side_effect=save_keywords)

    with patch.object(
        yso.EventSearchIndexService, "bulk_update_search_indexes"
    ) as bulk_update:
        importer.import_keywords()

    importer.save_keywords.assert_called_once()
    bulk_update.assert_called_once_with({"event:1", "event:2"})


@pytest.mark.django_db
@override_settings(EVENT_SEARCH_INDEX_SIGNALS_ENABLED=False)
def test_import_keywords_does_not_bulk_update_when_signals_are_disabled():
    importer = make_importer()
    importer.save_keywords = Mock()

    with patch(
        "events.importer.yso.EventSearchIndexService.bulk_update_search_indexes"
    ) as bulk_update:
        importer.import_keywords()

    importer.save_keywords.assert_called_once()
    bulk_update.assert_not_called()


@pytest.mark.django_db
@override_settings(EVENT_SEARCH_INDEX_SIGNALS_ENABLED=True)
def test_import_keywords_bulk_updates_when_saving_keywords_fails():
    importer = make_importer()

    def save_keywords(_graph):
        importer._affected_event_ids.add("event:1")
        raise RuntimeError("keyword import failed")

    importer.save_keywords = Mock(side_effect=save_keywords)

    with (
        patch(
            "events.importer.yso.EventSearchIndexService.bulk_update_search_indexes"
        ) as bulk_update,
        pytest.raises(RuntimeError, match="keyword import failed"),
    ):
        importer.import_keywords()

    bulk_update.assert_called_once_with({"event:1"})


@pytest.mark.django_db
@override_settings(EVENT_SEARCH_INDEX_SIGNALS_ENABLED=True)
def test_collect_keyword_events_collects_keyword_and_audience_events():
    importer = make_importer()
    importer._affected_event_ids = set()
    keyword = KeywordFactory()
    audience_keyword = KeywordFactory()
    with suppress_search_index_updates():
        keyword_events = EventFactory.create_batch(2)
        audience_events = EventFactory.create_batch(2)
        for event in keyword_events:
            event.keywords.add(keyword)
        for event in audience_events:
            event.audience.add(audience_keyword)

    importer._collect_keyword_events(keyword)
    importer._collect_keyword_events(audience_keyword)

    assert importer._affected_event_ids == {
        event.pk for event in [*keyword_events, *audience_events]
    }


@pytest.mark.django_db
@override_settings(EVENT_SEARCH_INDEX_SIGNALS_ENABLED=True)
def test_deprecate_and_replace_collects_affected_event_ids():
    importer = make_importer()
    importer._affected_event_ids = set()
    keyword = KeywordFactory()
    with suppress_search_index_updates():
        events = EventFactory.create_batch(3)
        events[0].keywords.add(keyword)
        events[1].keywords.add(keyword)
        events[2].audience.add(keyword)

    graph = Mock()
    with patch(
        "events.importer.yso.deprecate_and_replace", return_value=True
    ) as replace:
        assert importer._deprecate_and_replace(graph, keyword)

    replace.assert_called_once_with(graph, keyword)
    assert importer._affected_event_ids == {event.pk for event in events}
