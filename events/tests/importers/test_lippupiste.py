import json
from copy import deepcopy

import pytest
from django.conf import settings

from events.importer.lippupiste import LippupisteImporter
from events.models import Event
from events.tests.factories import DataSourceFactory, KeywordFactory


@pytest.fixture
def importer():
    importer = LippupisteImporter({"force": False})
    importer.setup()
    return importer


@pytest.fixture(autouse=True)
def tprek_datasource():
    return DataSourceFactory(id="tprek")


@pytest.fixture
def yso_datasource():
    return DataSourceFactory(id="yso")


@pytest.fixture
def drama_keyword(yso_datasource):
    return KeywordFactory(id="yso:p2625", data_source=yso_datasource, name="Draama")


@pytest.fixture
def response_with_one_event(request):
    with open(request.path.parent / "fixtures/lippupiste_response.json") as f:
        return json.load(f)


@pytest.fixture
def response_with_two_events_same_super_event(response_with_one_event):
    response = deepcopy(response_with_one_event)
    event_2 = deepcopy(response["Events"][0])
    event_2["EventId"] += "1"
    response["Events"].append(event_2)
    return response


@pytest.mark.django_db
def test_lippupiste_event_parse(
    requests_mock, drama_keyword, importer, response_with_one_event
):
    requests_mock.get(settings.LIPPUPISTE_EVENT_API_URL, json=response_with_one_event)
    importer.import_events()

    events = Event.objects.all()
    assert events.count() == 1
    assert drama_keyword in events[0].keywords.all()


@pytest.mark.django_db
def test_lippupiste_super_event(
    requests_mock, importer, response_with_two_events_same_super_event
):
    requests_mock.get(
        settings.LIPPUPISTE_EVENT_API_URL,
        json=response_with_two_events_same_super_event,
    )
    importer.import_events()
    assert Event.objects.all().count() == 3
